"""Slash commands customizáveis do HRX CODE.

Cada arquivo `.md` em `~/.config/hrx/comandos/` vira um comando `/nome` no chat.
O corpo do arquivo é injetado como pergunta do usuário — o modelo continua no
mesmo fluxo (ReAct + ferramentas + gate 🟢🟡🔴), só que o prompt vem pronto.

Formato do arquivo (frontmatter é opcional):

    ---
    descricao: uma linha resumindo o que este comando faz
    ---
    Prompt que será enviado ao agente.
    Use {argumentos} para injetar o que veio depois do comando (opcional).

Comando colidindo com built-in (/ajuda, /config, /motor, /memoria, ...) é
ignorado silenciosamente — os built-ins vencem.
"""
import os

_DIR_ENV = "HRX_COMANDOS_DIR"
_DIR_PADRAO = "~/.config/hrx/comandos"

# Nomes reservados: qualquer /coisa tratada em agente._comando_especial. Manter
# em sincronia com aquele arquivo — colisão silenciosa aqui, não quebra.
BUILTIN = frozenset({
    "/sair", "/quit", "/exit", "/ajuda", "/help",
    "/config", "/perfil", "/debug", "/novo", "/reset",
    "/modo", "/permissoes", "/permissões", "/perm",
    "/memoria", "/memorias", "/motor", "/chaves", "/limpar",
    "/comandos", "/resumo",
})

_CHAVES_DESC = ("descricao", "descrição", "desc", "description")

_CACHE: dict = None


def dir_comandos() -> str:
    return os.path.expanduser(os.environ.get(_DIR_ENV, _DIR_PADRAO))


def _parse(texto: str) -> tuple:
    """Extrai (descricao, corpo). Frontmatter YAML-like leve, opcional."""
    descricao = ""
    corpo = texto
    if texto.startswith("---\n") or texto.startswith("---\r\n"):
        marca = "\n---\n"
        fim = texto.find(marca, 4)
        if fim > 0:
            header = texto[4:fim]
            corpo = texto[fim + len(marca):]
            for linha in header.splitlines():
                if ":" not in linha:
                    continue
                k, v = linha.split(":", 1)
                if k.strip().lower() in _CHAVES_DESC:
                    descricao = v.strip().strip('"').strip("'")
                    break
    return descricao, corpo.strip()


def carregar(forcar: bool = False) -> dict:
    """Lê todos os `.md` da pasta e devolve {'/nome': {descricao, corpo, arquivo}}.
    Cacheado; passe forcar=True para reler do disco."""
    global _CACHE
    if _CACHE is not None and not forcar:
        return _CACHE
    resultado = {}
    pasta = dir_comandos()
    if not os.path.isdir(pasta):
        _CACHE = {}
        return _CACHE
    for nome_arq in sorted(os.listdir(pasta)):
        if not nome_arq.lower().endswith(".md"):
            continue
        nome_cmd = "/" + os.path.splitext(nome_arq)[0].lower()
        if nome_cmd in BUILTIN:
            continue
        caminho = os.path.join(pasta, nome_arq)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                texto = f.read()
        except OSError:
            continue
        descricao, corpo = _parse(texto)
        if corpo:
            resultado[nome_cmd] = {"descricao": descricao,
                                   "corpo": corpo,
                                   "arquivo": caminho}
    _CACHE = resultado
    return _CACHE


def expandir(entrada: str):
    """Se `entrada` começa com um comando customizado, devolve o prompt
    expandido (com {argumentos} substituído por tudo depois do comando).
    Devolve None se não for um comando customizado."""
    partes = entrada.strip().split(None, 1)
    if not partes:
        return None
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""
    dados = carregar().get(cmd)
    if not dados:
        return None
    corpo = dados["corpo"]
    if "{argumentos}" in corpo or "{args}" in corpo:
        corpo = corpo.replace("{argumentos}", args).replace("{args}", args)
    elif args:
        corpo = corpo + "\n\n" + args
    return corpo


def recarregar() -> dict:
    """Zera o cache e relê o disco. Útil para o comando /comandos recarregar."""
    return carregar(forcar=True)
