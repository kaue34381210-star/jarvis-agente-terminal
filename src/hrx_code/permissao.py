"""Política de permissões da sessão do HRX Code."""
import hashlib
import json
import os

from . import aprovacao
from . import caminhos
from . import config

COMANDO_DE_FERRAMENTA = {
    "rodar_comando": lambda a: str((a or {}).get("comando", "")).strip(),
    "git": lambda a: ("git " + str((a or {}).get("args", ""))).strip(),
    "escrever_arquivo": lambda a: f"escrever_arquivo {(a or {}).get('caminho', '')}".strip(),
    "editar_arquivo": lambda a: f"editar_arquivo {(a or {}).get('caminho', '')}".strip(),
    "aplicar_patch": lambda a: f"aplicar_patch {(a or {}).get('caminho', '')}".strip(),
    "desfazer_ultima": lambda a: f"desfazer_ultima {(a or {}).get('caminho', '')}".strip(),
    "criar_planilha": lambda a: f"criar_planilha {(a or {}).get('nome', '')}".strip(),
    "criar_pdf": lambda a: f"criar_pdf {(a or {}).get('nome', '')}".strip(),
    "buscar_web": lambda a: f"buscar_web {(a or {}).get('url', '')}".strip(),
}

FERRAMENTAS_ESCRITA = {"escrever_arquivo", "editar_arquivo", "aplicar_patch",
                       "criar_planilha", "criar_pdf"}

FERRAMENTAS_SEMPRE_VERMELHAS = {"desfazer_ultima"}

CAMPO_CAMINHO = {
    "escrever_arquivo": "caminho",
    "editar_arquivo": "caminho",
    "aplicar_patch": "caminho",
    "criar_planilha": "nome",
    "criar_pdf": "nome",
}

MODOS = ("blindado", "cauteloso", "auto")

_MULTI = {"git", "pip", "pip3", "pipx", "npm", "pnpm", "yarn", "docker",
          "podman", "kubectl", "cargo", "go", "apt", "apt-get", "dnf", "yum",
          "pacman", "brew", "systemctl", "service"}

_PADROES_ARGS = {
    "git": {"args": ""},
    "editar_arquivo": {"ocorrencia": None, "tudo": False},
    "desfazer_ultima": {"caminho": None},
    "criar_planilha": {"cabecalho": None},
    "criar_pdf": {"titulo": None, "conteudo": None, "tabela": None},
    "buscar_web": {"max_chars": 8000},
}


def exige_aprovacao(nome: str) -> bool:
    return nome in COMANDO_DE_FERRAMENTA


def comando_de(nome: str, args: dict) -> str:
    fn = COMANDO_DE_FERRAMENTA.get(nome)
    return fn(args) if fn else ""


def assinatura(comando: str) -> str:
    """Reduz um comando à assinatura usada por "sempre permitir"."""
    toks = comando.split()
    if not toks:
        return ""
    exe = os.path.basename(toks[0]).lower()
    if exe in _MULTI and len(toks) > 1 and not toks[1].startswith("-"):
        return f"{exe} {toks[1].lower()}"
    return exe


def _token_trinco(comando: str, ferramenta: str, args: dict) -> tuple:
    canonicos = dict(args or {})
    for campo, padrao in _PADROES_ARGS.get(ferramenta, {}).items():
        if canonicos.get(campo) == padrao:
            canonicos.pop(campo, None)
    serializado = json.dumps(
        canonicos, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    digest = hashlib.sha256(serializado.encode("utf-8")).hexdigest()
    return comando, ferramenta, digest


class Politica:
    """Estado de permissões de uma sessão."""

    def __init__(self, modo: str = None, seguros_extra=(), dry_run: bool = False):
        modo = (modo or "cauteloso").strip().lower()
        self.modo = modo if modo in MODOS else "cauteloso"
        self.seguros_extra = set(seguros_extra)
        self.dry_run = bool(dry_run)
        self.sempre = set()
        self._trinco = None

    def classificar(self, comando: str, ferramenta: str = None, args: dict = None):
        """Classifica um comando conforme o modo e as permissões da sessão.

        Riscos vermelhos e escritas fora do projeto nunca são rebaixados.
        """
        if ferramenta in FERRAMENTAS_SEMPRE_VERMELHAS:
            return ("vermelho",
                    "undo pode sobrescrever ou remover arquivo e nunca é rebaixável")
        if ferramenta in FERRAMENTAS_ESCRITA:
            campo = CAMPO_CAMINHO[ferramenta]
            informado = str((args or {}).get(campo, ""))
            try:
                alvo = caminhos.resolver(config.REPO, informado)
                interno = caminhos.esta_dentro(config.REPO, alvo)
            except ValueError:
                return "vermelho", "caminho de escrita inválido"
            if not interno:
                return "vermelho", f"escreve fora do projeto: {alvo}"
            nivel, motivo = "amarelo", "escreve/sobrescreve arquivo no projeto"
        else:
            nivel, motivo = aprovacao.classificar(comando, seguros_extra=self.seguros_extra)
        if nivel == "amarelo" and assinatura(comando) in self.sempre:
            return "verde", "sempre permitido nesta sessão"
        if nivel == "amarelo" and self.modo == "auto":
            return "verde", motivo + " · modo auto"
        if nivel == "verde" and self.modo == "blindado":
            return "amarelo", motivo + " · modo blindado"
        return nivel, motivo

    def liberar_sempre(self, comando: str) -> str:
        assi = assinatura(comando)
        self.sempre.add(assi)
        return assi

    def liberar(self, comando: str, ferramenta: str = None,
                args: dict = None) -> None:
        """Autoriza uma execução da ferramenta para o comando."""
        self._trinco = _token_trinco(comando, ferramenta, args)

    def consumir(self, comando: str, ferramenta: str = None,
                 args: dict = None) -> bool:
        """Consome a autorização de uso único do comando."""
        token = _token_trinco(comando, ferramenta, args)
        ok = self._trinco is not None and self._trinco == token
        self._trinco = None
        return ok


_ATUAL = None


def usar(politica: Politica) -> None:
    global _ATUAL
    _ATUAL = politica


def ativa():
    return _ATUAL


def consumir(comando: str, ferramenta: str = None, args: dict = None) -> bool:
    """Valida a autorização quando há uma política ativa."""
    if _ATUAL is None:
        return True
    return _ATUAL.consumir(comando, ferramenta=ferramenta, args=args)
