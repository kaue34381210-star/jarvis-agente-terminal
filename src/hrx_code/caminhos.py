"""Resolução segura de caminhos relativos ao projeto do usuário."""
import os


def resolver(base: str, caminho: str) -> str:
    """Retorna um caminho absoluto e real, resolvendo ``~``, ``..`` e links.

    Caminhos relativos usam ``base`` como raiz. A função não impõe uma
    política de acesso; ela apenas produz uma representação canônica para que
    leitores, escritores e o gate de permissões tomem a mesma decisão.
    """
    if not caminho or not str(caminho).strip():
        raise ValueError("caminho vazio")
    raiz = os.path.realpath(os.path.abspath(os.path.expanduser(str(base))))
    informado = os.path.expanduser(str(caminho))
    candidato = informado if os.path.isabs(informado) else os.path.join(raiz, informado)
    return os.path.realpath(os.path.abspath(candidato))


def esta_dentro(base: str, caminho: str) -> bool:
    """True quando o caminho canônico está em ``base`` ou abaixo dela."""
    raiz = os.path.realpath(os.path.abspath(os.path.expanduser(str(base))))
    alvo = resolver(raiz, caminho)
    try:
        return os.path.commonpath((raiz, alvo)) == raiz
    except ValueError:
        # No Windows, caminhos em unidades diferentes não têm ancestral comum.
        return False


def exigir_dentro(base: str, caminho: str) -> str:
    """Resolve ``caminho`` e rejeita escapes da raiz, inclusive por symlink."""
    alvo = resolver(base, caminho)
    if not esta_dentro(base, alvo):
        raise ValueError(f"Caminho fora da área permitida (bloqueado): {caminho}")
    return alvo
