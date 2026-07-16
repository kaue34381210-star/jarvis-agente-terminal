"""Classificação heurística de risco para comandos."""
import os
import re

# Padrões perigosos são avaliados antes destas listas.
SEGUROS = {
    "ls", "dir", "pwd", "cat", "type", "head", "tail", "echo", "printf",
    "whoami", "hostname", "date", "uptime", "cal", "df", "du", "free",
    "ps", "top", "htop", "env", "printenv", "set", "which", "where",
    "whereis", "id", "groups", "uname", "arch", "wc", "nl", "sort", "uniq",
    "cut", "column", "tr", "grep", "egrep", "fgrep", "rg", "file", "stat",
    "tree", "basename", "dirname", "realpath", "readlink", "history",
    "man", "help", "clear", "cd", "test", "true", "false",
    "find", "locate", "less", "more", "diff", "comm", "cmp", "pgrep",
    "md5sum", "sha1sum", "sha256sum", "sha512sum", "b2sum", "cksum",
    "lsblk", "lscpu", "lsusb", "lspci", "lsof", "ss", "netstat",
    "ping", "ping6", "dig", "nslookup", "host", "jobs", "alias",
    "command", "apropos", "getent", "hexdump", "xxd", "strings",
}

LEITURA_POR_SUB = {
    "pip": {"list", "show", "freeze", "search", "index", "check", "--version", "-v"},
    "pip3": {"list", "show", "freeze", "search", "index", "check", "--version", "-v"},
    "npm": {"ls", "list", "view", "outdated", "audit", "root", "config", "help", "--version", "-v"},
    "pnpm": {"ls", "list", "outdated", "why", "--version"},
    "yarn": {"list", "why", "info", "--version"},
    "docker": {"ps", "images", "image", "logs", "inspect", "version", "info",
               "stats", "top", "port", "history", "diff", "search"},
    "podman": {"ps", "images", "image", "logs", "inspect", "version", "info", "stats", "top"},
    "kubectl": {"get", "describe", "logs", "version", "top", "explain",
                "api-resources", "config", "cluster-info"},
    "systemctl": {"status", "list-units", "list-unit-files", "is-active",
                  "is-enabled", "is-failed", "show", "cat", "get-default"},
    "service": {"status"},
    "cargo": {"--version", "tree", "search"},
    "go": {"version", "env", "list", "doc"},
    "apt": {"list", "show", "search", "policy", "--version"},
    "apt-get": {"--version"},
    "dnf": {"list", "info", "search", "repolist"},
    "yum": {"list", "info", "search"},
    "brew": {"list", "info", "search", "outdated", "--version"},
}

VERMELHO = [
    (re.compile(r"(^|\s):\s*\(\s*\)\s*\{"), "fork bomb"),
    (re.compile(r"\brm\b"), "remove arquivos/diretórios"),
    (re.compile(r"\brmdir\b"), "remove diretórios"),
    (re.compile(r"\bunlink\b"), "remove arquivo"),
    (re.compile(r"\bshred\b"), "apaga de forma irrecuperável"),
    (re.compile(r"\bdd\b"), "escrita bruta em disco"),
    (re.compile(r"\bmkfs\b|\bfdisk\b|\bparted\b|\bwipefs\b"), "mexe no particionamento do disco"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff|init)\b"), "desliga/reinicia a máquina"),
    (re.compile(r"\bsudo\b|\bsu\b|\bdoas\b"), "eleva privilégios"),
    (re.compile(r"\b(chmod|chown|chgrp)\b.*(-\w*[Rr]|--recursive)"), "muda permissões recursivamente"),
    (re.compile(r"\bgit\b.+push.+(-f\b|--force)"), "git push forçado (reescreve histórico remoto)"),
    (re.compile(r"\bgit\b.+(reset\s+--hard|clean\s+-\w*f)"), "descarta alterações locais do git"),
    (re.compile(r"\b(curl|wget)\b.+\|\s*(sudo\s+)?(sh|bash|zsh|python\d?)"), "baixa e executa script da internet"),
    (re.compile(r"\b(kill|killall|pkill)\b"), "encerra processos"),
    (re.compile(r"\btruncate\b"), "trunca arquivos"),
    (re.compile(r"-delete\b|-exec\b|-execdir\b"), "find executando/apagando arquivos"),
    (re.compile(r">\s*/(etc|bin|sbin|usr|var|boot|dev|lib|sys|proc)\b"), "sobrescreve arquivo de sistema"),
    (re.compile(r"\bmv\b.+\s/(etc|bin|sbin|usr|var|boot|lib)\b"), "move para diretório de sistema"),
    (re.compile(r"\b(iptables|nft|ufw)\b"), "altera regras de firewall"),
    (re.compile(r"\bcrontab\b\s+-r"), "apaga todas as tarefas agendadas"),
]

AMARELO = [
    (re.compile(r"\bsed\b.+-\w*i"), "sed editando arquivo no lugar"),
    (re.compile(r">>?"), "redireciona/sobrescreve saída em arquivo"),
    (re.compile(r"\b(pip\d?|pipx|npm|pnpm|yarn|apt|apt-get|dnf|yum|pacman|brew|cargo|go)\b\s+(install|add|remove|uninstall|update|upgrade|i\b)"), "instala/remove pacotes"),
    (re.compile(r"\bgit\b\s+(add|commit|checkout|switch|merge|rebase|stash|tag|restore|mv|rm|pull|push|apply|cherry-pick|revert)\b"), "altera o repositório git"),
    (re.compile(r"\b(systemctl|service)\b\s+(start|stop|restart|reload|enable|disable)"), "controla serviços do sistema"),
    (re.compile(r"\bdocker\b\s+(run|rm|rmi|stop|kill|build|compose|exec|prune)"), "opera containers Docker"),
]

MUTANTES = {
    "mkdir", "touch", "cp", "mv", "ln", "tee", "install", "make", "cmake",
    "tar", "zip", "unzip", "gzip", "gunzip", "git", "apt", "apt-get", "dnf",
    "yum", "pacman", "brew", "pip", "pip3", "pipx", "npm", "pnpm", "yarn",
    "cargo", "go", "docker", "podman", "kubectl", "systemctl", "service",
    "python", "python3", "node", "bash", "sh", "zsh", "perl", "ruby", "sed",
    "awk", "nmap", "curl", "wget", "ssh", "scp", "rsync",
}

# Flags que permitem a um git de leitura escrever arquivos ou executar código.
GIT_FLAGS_SENSIVEIS = re.compile(
    r"(^|\s)(-c\b|-C\b|--exec-path|--output\b|-O\b|--open-files-in-pager"
    r"|--ext-diff|--upload-pack|--receive-pack|--exec\b|--pager\b)")

NIVEIS = ("verde", "amarelo", "vermelho")


def _executavel(comando: str) -> str:
    partes = comando.strip().split()
    if not partes:
        return ""
    return os.path.basename(partes[0]).lower()


def classificar(comando: str, seguros_extra=()) -> tuple:
    """Devolve (nivel, motivo). nivel ∈ {'verde','amarelo','vermelho'}."""
    c = comando.strip()
    if not c:
        return ("vermelho", "comando vazio")

    for rx, motivo in VERMELHO:
        if rx.search(c):
            return ("vermelho", motivo)

    for rx, motivo in AMARELO:
        if rx.search(c):
            return ("amarelo", motivo)

    exe = _executavel(c)

    if exe == "git":
        if GIT_FLAGS_SENSIVEIS.search(c):
            return ("amarelo", "git com flag sensível")
        sub = (c.split()[1].lower() if len(c.split()) > 1 else "")
        if sub in {"status", "diff", "log", "show", "branch", "remote",
                   "fetch", "rev-parse", "describe", "blame", "ls-files",
                   "shortlog", "reflog", "config", "tag", "cat-file", ""}:
            return ("verde", f"git {sub} (leitura)".strip())
        return ("amarelo", "altera o repositório git")

    if exe in LEITURA_POR_SUB:
        partes = c.split()
        sub = partes[1].lower() if len(partes) > 1 else ""
        if sub in LEITURA_POR_SUB[exe]:
            return ("verde", f"{exe} {sub} (leitura)")

    if exe in SEGUROS or exe in set(seguros_extra):
        return ("verde", "somente leitura")

    if exe in MUTANTES:
        return ("amarelo", "modifica o sistema")

    return ("amarelo", f"comando não classificado ({exe})")
