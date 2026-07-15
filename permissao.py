"""Política de permissões da sessão do HRX CODE.

Junta numa camada só as quatro peças do controle de execução:

  1. classificação de risco 🟢🟡🔴 (delega a `aprovacao.classificar`);
  2. modo da sessão — `blindado` / `cauteloso` / `auto` — que ajusta o rigor;
  3. lista "sempre permitir" desta sessão (o usuário marca e não pergunta mais);
  4. um TRINCO de uso único que as ferramentas sensíveis conferem — assim
     nenhuma chamada não-aprovada executa, mesmo que um caminho de código novo
     esqueça de passar pelo gate interativo (defesa em profundidade; era a
     pendência apontada na revisão de segurança).

`agente.py` é o gate interativo (pergunta ao humano) e `ferramentas.py` é o
executor; ambos importam ESTE módulo, que é a fonte única da verdade.
"""
import os

import aprovacao

# Ferramentas que exigem aprovação e como derivar, dos args do modelo, a string
# de comando que será classificada/liberada. Fonte única p/ agente e ferramentas.
COMANDO_DE_FERRAMENTA = {
    "rodar_comando": lambda a: str((a or {}).get("comando", "")).strip(),
    "git": lambda a: ("git " + str((a or {}).get("args", ""))).strip(),
    "escrever_arquivo": lambda a: f"escrever_arquivo {(a or {}).get('caminho', '')}".strip(),
    "editar_arquivo": lambda a: f"editar_arquivo {(a or {}).get('caminho', '')}".strip(),
}

# Ferramentas de ESCRITA no projeto: risco fixo 🟡 (não são comando de shell,
# então não passam por aprovacao.classificar; escrevem/sobrescrevem arquivo).
FERRAMENTAS_ESCRITA = {"escrever_arquivo", "editar_arquivo"}

MODOS = ("blindado", "cauteloso", "auto")   # do mais rígido ao mais solto

# Ferramentas "multi-comando": a assinatura do 'sempre permitir' usa 2 tokens
# (ex: "git commit", "npm install") em vez de só o executável.
_MULTI = {"git", "pip", "pip3", "pipx", "npm", "pnpm", "yarn", "docker",
          "podman", "kubectl", "cargo", "go", "apt", "apt-get", "dnf", "yum",
          "pacman", "brew", "systemctl", "service"}


def exige_aprovacao(nome: str) -> bool:
    return nome in COMANDO_DE_FERRAMENTA


def comando_de(nome: str, args: dict) -> str:
    fn = COMANDO_DE_FERRAMENTA.get(nome)
    return fn(args) if fn else ""


def assinatura(comando: str) -> str:
    """Reduz um comando a uma assinatura estável p/ o 'sempre permitir':
    'git commit -m x' -> 'git commit'; 'mkdir build' -> 'mkdir'."""
    toks = comando.split()
    if not toks:
        return ""
    exe = os.path.basename(toks[0]).lower()
    if exe in _MULTI and len(toks) > 1 and not toks[1].startswith("-"):
        return f"{exe} {toks[1].lower()}"
    return exe


class Politica:
    """Estado de permissões de UMA sessão do agente."""

    def __init__(self, modo: str = None, seguros_extra=()):
        modo = (modo or "cauteloso").strip().lower()
        self.modo = modo if modo in MODOS else "cauteloso"
        self.seguros_extra = set(seguros_extra)
        self.sempre = set()       # assinaturas liberadas p/ a sessão inteira
        self._trinco = None       # token de uso único p/ a próxima ferramenta

    def classificar(self, comando: str, ferramenta: str = None):
        """(nivel, motivo) já ajustado pelo modo e pela lista 'sempre'.
        REGRA DE SEGURANÇA: 🔴 nunca é rebaixado — nem por 'sempre', nem por
        modo auto. A assinatura casa 2 tokens, então um 'git commit' liberado
        JAMAIS pode arrastar um 'git commit ... && rm -rf' (que é 🔴).
        `ferramenta` de escrita de arquivo entra fixa em 🟡 (não é shell)."""
        if ferramenta in FERRAMENTAS_ESCRITA:
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

    # --- trinco de uso único (defesa na camada da ferramenta) ---
    def liberar(self, comando: str) -> None:
        """Autoriza a PRÓXIMA execução da ferramenta cujo comando é `comando`."""
        self._trinco = comando

    def consumir(self, comando: str) -> bool:
        """A ferramenta chama isto: True só se o comando foi liberado agora.
        O token é de uso único (some ao ser lido)."""
        ok = self._trinco is not None and self._trinco == comando
        self._trinco = None
        return ok


# ---------------------------------------------------------------------------
# Política ativa da sessão. `ferramentas.py` consulta este singleton pelo trinco.
# ---------------------------------------------------------------------------
_ATUAL = None


def usar(politica: Politica) -> None:
    global _ATUAL
    _ATUAL = politica


def ativa():
    return _ATUAL


def consumir(comando: str) -> bool:
    """Chamado pelas ferramentas sensíveis. Sem política ativa (uso
    programático/testes) não trava; com política ativa, exige token válido."""
    if _ATUAL is None:
        return True
    return _ATUAL.consumir(comando)
