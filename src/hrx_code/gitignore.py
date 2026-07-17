"""Regras de exclusão para as ferramentas de navegação do projeto.

Somente o ``.gitignore`` da raiz de ``config.REPO`` é interpretado; arquivos
``.gitignore`` aninhados não são suportados. Regras privadas adicionais podem
ser mantidas em ``config.DADOS/.hrxignore`` sem entrar no repositório.
"""
import os
from pathlib import PurePosixPath

from pathspec import GitIgnoreSpec

from . import config
from . import undo


# Diretórios caros ou internos nunca são percorridos, mesmo quando o usuário
# pede para não respeitar os arquivos de ignore.
IGNORAR_SEMPRE = frozenset({
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
})

# Preserva a higiene anterior em projetos que ainda não possuem .gitignore.
_FALLBACK = (
    "build/",
    "dist/",
    ".next/",
    ".turbo/",
    "target/",
    ".idea/",
    ".gradle/",
)

_CACHE = {}


def _fingerprint(caminho: str):
    try:
        stat = os.stat(caminho)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _linhas(caminho: str) -> list[str]:
    try:
        with open(caminho, "r", encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().splitlines()
    except OSError:
        return []


def _spec() -> GitIgnoreSpec:
    raiz = os.path.realpath(config.REPO)
    gitignore = os.path.join(raiz, ".gitignore")
    privado = os.path.join(os.path.realpath(config.DADOS), ".hrxignore")
    chave = (raiz, privado)
    fingerprint = (_fingerprint(gitignore), _fingerprint(privado))
    cache = _CACHE.get(chave)
    if cache and cache[0] == fingerprint:
        return cache[1]

    linhas = _linhas(gitignore) if fingerprint[0] is not None else list(_FALLBACK)
    linhas.extend(_linhas(privado))
    spec = GitIgnoreSpec.from_lines(linhas)
    _CACHE[chave] = (fingerprint, spec)
    return spec


def _relativo_posix(caminho: str) -> str:
    relativo = os.path.relpath(caminho, config.REPO)
    if relativo == ".":
        return ""
    return relativo.replace(os.sep, "/")


def deve_ignorar(caminho: str, diretorio: bool = False,
                 respeitar_gitignore: bool = True) -> bool:
    """Diz se um caminho deve ser omitido das ferramentas de navegação."""
    if undo.caminho_protegido(caminho):
        return True
    relativo = _relativo_posix(caminho)
    partes = PurePosixPath(relativo).parts
    partes_internas = partes if diretorio else partes[:-1]
    if any(parte in IGNORAR_SEMPRE for parte in partes_internas):
        return True
    if not respeitar_gitignore or not relativo:
        return False
    candidato = relativo + "/" if diretorio else relativo
    return _spec().match_file(candidato)
