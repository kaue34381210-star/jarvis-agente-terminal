"""Histórico transacional e seguro das mutações de arquivos do HRX Code."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import tempfile
import uuid

from . import caminhos
from . import config
from . import permissao


MAX_OPERACOES = 50
MAX_BYTES = 100 * 1024 * 1024


class UndoError(RuntimeError):
    """Erro seguro e esperado do subsistema de undo."""


def _pasta() -> str:
    return os.path.join(config.DADOS, "undo")


def _log() -> str:
    return os.path.join(_pasta(), "operacoes.json")


def _garantir_pasta() -> str:
    pasta = _pasta()
    os.makedirs(pasta, mode=0o700, exist_ok=True)
    try:
        os.chmod(pasta, 0o700)
    except OSError:
        pass
    return pasta


def _hash_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _hash_arquivo(caminho: str) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _estado_arquivo(caminho: str) -> dict:
    estado = os.stat(caminho)
    return {
        "modo_depois": stat.S_IMODE(estado.st_mode),
        "mtime_ns_depois": estado.st_mtime_ns,
        "dispositivo_depois": estado.st_dev,
        "inode_depois": estado.st_ino,
    }


def _ler_registros() -> list[dict]:
    try:
        with open(_log(), "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        return []
    except OSError as erro:
        raise UndoError(f"não foi possível ler o histórico de undo: {erro}") from erro
    except (TypeError, ValueError) as erro:
        raise UndoError("histórico de undo está corrompido") from erro
    if not isinstance(dados, list) or any(
            not isinstance(registro, dict) for registro in dados):
        raise UndoError("histórico de undo está corrompido")
    return dados


def _gravar_registros(registros: list[dict]) -> None:
    pasta = _garantir_pasta()
    fd, temporario = tempfile.mkstemp(prefix=".operacoes-", dir=pasta)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(registros, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, _log())
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def _remover_snapshot(registro: dict) -> None:
    nome = registro.get("snapshot")
    if not nome:
        return
    alvo = os.path.join(_pasta(), os.path.basename(nome))
    try:
        os.unlink(alvo)
    except FileNotFoundError:
        pass
    except OSError:
        # A rotação do log não deve invalidar uma mutação já confirmada.
        pass


def _rotacionar(registros: list[dict]) -> tuple[list[dict], list[dict]]:
    mantidos = list(registros)
    removidos = []

    def tamanho(registro):
        try:
            return max(0, int(registro.get("snapshot_bytes", 0)))
        except (TypeError, ValueError):
            return 0

    total = sum(tamanho(registro) for registro in mantidos)
    while mantidos and (len(mantidos) > MAX_OPERACOES or total > MAX_BYTES):
        antigo = mantidos.pop(0)
        removidos.append(antigo)
        total -= tamanho(antigo)
    return mantidos, removidos


def iniciar_transacao(caminho: str, ferramenta: str) -> dict:
    """Captura o estado anterior, sem publicar ainda uma operação desfazível."""
    alvo = os.path.realpath(os.path.abspath(os.path.expanduser(str(caminho))))
    existe = os.path.isfile(alvo)
    if os.path.exists(alvo) and not existe:
        raise UndoError(f"alvo não é um arquivo regular: {alvo}")

    dados = b""
    modo = None
    snapshot_pendente = None
    if existe:
        tamanho = os.path.getsize(alvo)
        if tamanho > MAX_BYTES:
            raise UndoError(
                f"arquivo tem {tamanho} bytes e excede o limite de undo "
                f"de {MAX_BYTES} bytes; mutação recusada"
            )
        with open(alvo, "rb") as arquivo:
            dados = arquivo.read()
        modo = stat.S_IMODE(os.stat(alvo).st_mode)
        pasta = _garantir_pasta()
        fd, snapshot_pendente = tempfile.mkstemp(prefix=".pendente-", dir=pasta)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as snapshot:
                snapshot.write(dados)
                snapshot.flush()
                os.fsync(snapshot.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if snapshot_pendente and os.path.exists(snapshot_pendente):
                os.unlink(snapshot_pendente)
            raise

    return {
        "id": uuid.uuid4().hex,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "caminho": alvo,
        "ferramenta": ferramenta,
        "existed": existe,
        "criado": not existe,
        "hash_antes": _hash_bytes(dados) if existe else None,
        "hash_depois": None,
        "modo": modo,
        "snapshot": None,
        "snapshot_bytes": len(dados),
        "desfeito": False,
        "snapshot_pendente": snapshot_pendente,
    }


def confirmar_transacao(transacao: dict) -> dict:
    """Publica a operação somente após a escrita ter terminado com sucesso."""
    alvo = transacao["caminho"]
    if not os.path.isfile(alvo):
        raise UndoError("a escrita não produziu um arquivo regular")
    transacao["hash_depois"] = _hash_arquivo(alvo)
    transacao.update(_estado_arquivo(alvo))

    pendente = transacao.pop("snapshot_pendente", None)
    if pendente:
        nome = f"{transacao['id']}.bin"
        os.replace(pendente, os.path.join(_garantir_pasta(), nome))
        transacao["snapshot"] = nome

    registros = _ler_registros()
    registros.append(dict(transacao))
    mantidos, removidos = _rotacionar(registros)
    try:
        _gravar_registros(mantidos)
    except Exception:
        raise
    for registro in removidos:
        _remover_snapshot(registro)
    return transacao


def _restaurar_snapshot(transacao: dict) -> None:
    caminho = transacao["caminho"]
    if transacao["criado"]:
        os.unlink(caminho)
        return
    snapshot = os.path.join(_pasta(), os.path.basename(transacao["snapshot"]))
    if not os.path.isfile(snapshot):
        raise UndoError("snapshot da operação não está disponível")
    pasta = os.path.dirname(caminho)
    fd, temporario = tempfile.mkstemp(prefix=".hrx-undo-", dir=pasta)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as destino, open(snapshot, "rb") as origem:
            for bloco in iter(lambda: origem.read(1024 * 1024), b""):
                destino.write(bloco)
            destino.flush()
            os.fsync(destino.fileno())
        modo = transacao.get("modo")
        if modo is not None:
            os.chmod(temporario, int(modo))
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def abortar_transacao(transacao: dict, restaurar: bool = False) -> None:
    """Descarta o estado pendente; opcionalmente reverte uma escrita falha."""
    erro_restauracao = None
    if restaurar:
        try:
            caminho = transacao["caminho"]
            if transacao["criado"]:
                if os.path.isfile(caminho):
                    os.unlink(caminho)
            else:
                pendente = transacao.get("snapshot_pendente")
                final = transacao.get("snapshot")
                snapshot = pendente or (os.path.join(_pasta(), final) if final else None)
                if snapshot and os.path.isfile(snapshot):
                    pasta = os.path.dirname(caminho)
                    fd, temporario = tempfile.mkstemp(prefix=".hrx-rollback-", dir=pasta)
                    try:
                        with os.fdopen(fd, "wb") as destino, open(snapshot, "rb") as origem:
                            for bloco in iter(lambda: origem.read(1024 * 1024), b""):
                                destino.write(bloco)
                            destino.flush()
                            os.fsync(destino.fileno())
                        modo = transacao.get("modo")
                        if modo is not None:
                            os.chmod(temporario, int(modo))
                        os.replace(temporario, caminho)
                    finally:
                        if os.path.exists(temporario):
                            os.unlink(temporario)
        except OSError as erro:
            erro_restauracao = erro
    if erro_restauracao is not None:
        preservado = (transacao.get("snapshot_pendente")
                      or transacao.get("snapshot") or "indisponível")
        raise UndoError(
            "rollback da mutação falhou; o estado atual foi mantido e o "
            f"snapshot não foi consumido ({preservado}): {erro_restauracao}"
        ) from erro_restauracao
    pendente = transacao.get("snapshot_pendente")
    if pendente and os.path.exists(pendente):
        try:
            os.unlink(pendente)
        except OSError:
            pass
    if transacao.get("snapshot"):
        _remover_snapshot(transacao)


def listar_undo(limite: int = 10) -> str:
    """Lista as operações ativas mais recentes sem expor snapshots."""
    try:
        limite = max(1, int(limite))
    except (TypeError, ValueError):
        return "ERRO: limite deve ser um inteiro positivo"
    try:
        registros = _ler_registros()
    except UndoError as erro:
        return f"ERRO: {erro}"
    ativos = [r for r in registros if not r.get("desfeito")]
    if not ativos:
        return "(nenhuma operação disponível para desfazer)"
    linhas = []
    for registro in reversed(ativos[-limite:]):
        acao = "criou" if registro.get("criado") else "alterou"
        linhas.append(
            f"{registro.get('id')} · {registro.get('timestamp')} · "
            f"{registro.get('ferramenta')} {acao} {registro.get('caminho')}"
        )
    return "\n".join(linhas)


def desfazer_ultima(caminho: str = None) -> str:
    """Desfaz a operação ativa mais recente, recusando estado divergente."""
    args = {"caminho": caminho} if caminho else {}
    comando = permissao.comando_de("desfazer_ultima", args)
    if not permissao.consumir(comando, "desfazer_ultima", args):
        return "ERRO: undo não passou pela aprovação de risco (trinco de segurança)."

    alvo = caminhos.resolver(config.REPO, caminho) if caminho else None
    try:
        registros = _ler_registros()
    except UndoError as erro:
        return f"ERRO: {erro}"
    candidatos = [
        (indice, registro)
        for indice, registro in enumerate(registros)
        if not registro.get("desfeito")
        and (alvo is None or registro.get("caminho") == alvo)
    ]
    if not candidatos:
        detalhe = f" para {alvo}" if alvo else ""
        return f"ERRO: nenhuma operação disponível para desfazer{detalhe}"

    indice, registro = candidatos[-1]
    atual = registro["caminho"]
    if not os.path.isfile(atual):
        return (
            "ERRO: conflito de undo; o arquivo foi removido depois da operação. "
            "Nada foi alterado e a operação continua disponível."
        )
    if _hash_arquivo(atual) != registro.get("hash_depois"):
        return (
            "ERRO: conflito de undo; o arquivo foi alterado depois da operação. "
            "Nada foi alterado e a operação continua disponível."
        )
    estado_atual = _estado_arquivo(atual)
    campos_estado = (
        "modo_depois",
        "mtime_ns_depois",
        "dispositivo_depois",
        "inode_depois",
    )
    if any(
            registro.get(campo) is not None
            and registro.get(campo) != estado_atual[campo]
            for campo in campos_estado):
        return (
            "ERRO: conflito de undo; os metadados do arquivo mudaram depois "
            "da operação. Nada foi alterado e a operação continua disponível."
        )

    pasta = os.path.dirname(atual)
    fd, copia_atual = tempfile.mkstemp(prefix=".hrx-undo-atual-", dir=pasta)
    os.close(fd)
    try:
        os.replace(atual, copia_atual)
    except OSError as erro:
        if os.path.exists(copia_atual):
            os.unlink(copia_atual)
        return f"ERRO: não foi possível preparar o undo; nada foi alterado: {erro}"

    try:
        if not registro.get("criado"):
            _restaurar_snapshot(registro)
    except (OSError, UndoError) as erro:
        try:
            os.replace(copia_atual, atual)
        except OSError as rollback:
            return (
                "ERRO: não foi possível desfazer nem restaurar o estado "
                f"anterior: {erro}; rollback: {rollback}"
            )
        return f"ERRO: não foi possível desfazer; nada foi consumido: {erro}"
    registros[indice]["desfeito"] = True
    registros[indice]["desfeito_em"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    if os.path.isfile(atual):
        hash_restaurado = _hash_arquivo(atual)
        estado_restaurado = _estado_arquivo(atual)
        for outro_indice, outro in enumerate(registros):
            if (outro_indice != indice
                    and not outro.get("desfeito")
                    and outro.get("caminho") == atual
                    and outro.get("hash_depois") == hash_restaurado):
                outro.update(estado_restaurado)
    try:
        _gravar_registros(registros)
    except (OSError, UndoError) as erro:
        try:
            os.replace(copia_atual, atual)
        except OSError as rollback:
            return (
                "ERRO: o histórico não pôde ser atualizado e a restauração "
                f"do estado anterior também falhou: {erro}; rollback: {rollback}"
            )
        return (
            "ERRO: o histórico não pôde ser atualizado; o arquivo permaneceu "
            f"no estado anterior ao undo: {erro}"
        )
    try:
        os.unlink(copia_atual)
    except OSError:
        pass
    acao = "removido" if registro.get("criado") else "restaurado"
    return f"OK: {atual} {acao} pela operação {registro.get('id')}"


def caminho_protegido(caminho: str) -> bool:
    """Indica se um caminho pertence ao armazenamento privado de undo."""
    try:
        pasta = os.path.realpath(_pasta())
        alvo = os.path.realpath(os.path.abspath(os.path.expanduser(str(caminho))))
        return os.path.commonpath((pasta, alvo)) == pasta
    except (TypeError, ValueError):
        return False
