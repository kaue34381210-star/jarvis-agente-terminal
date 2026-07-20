import pytest

from hrx_code import config
from hrx_code import ferramentas
from hrx_code import permissao


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    raiz = tmp_path / "projeto"
    dados = tmp_path / "dados"
    raiz.mkdir()
    monkeypatch.setattr(config, "REPO", str(raiz))
    monkeypatch.setattr(config, "DADOS", str(dados))
    permissao.usar(permissao.Politica())
    alvo = raiz / "app.txt"
    yield alvo
    permissao.usar(None)


def editar_autorizado(caminho="app.txt", procurar="alvo", substituir="novo",
                      **opcoes):
    politica = permissao.ativa()
    args = {"caminho": caminho, "procurar": procurar,
            "substituir": substituir, **opcoes}
    comando = permissao.comando_de("editar_arquivo", args)
    politica.liberar(comando, "editar_arquivo", args)
    return ferramentas.editar_arquivo(
        caminho, procurar, substituir, **opcoes
    )


def test_match_unico_funciona_sem_escolha(arquivo):
    arquivo.write_text("antes alvo depois\n", encoding="utf-8")

    resultado = editar_autorizado()

    assert resultado.startswith("OK: 1 ocorrência(s)")
    assert arquivo.read_text(encoding="utf-8") == "antes novo depois\n"


def test_edicao_sem_autorizacao_nao_altera_arquivo(arquivo):
    original = "alvo\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = ferramentas.editar_arquivo("app.txt", "alvo", "novo")

    assert "não passou pela aprovação" in resultado
    assert arquivo.read_text(encoding="utf-8") == original


def test_multiplos_sem_escolha_retornam_erro_sem_alterar(arquivo):
    original = "alvo\nmeio\nalvo\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = editar_autorizado()

    assert "'procurar' aparece 2x" in resultado
    assert "`ocorrencia=N` (1..2)" in resultado
    assert "`tudo=True`" in resultado
    assert arquivo.read_text(encoding="utf-8") == original


def test_ocorrencia_substitui_somente_a_escolhida(arquivo):
    arquivo.write_text("alvo\nmeio\nalvo\nfim\nalvo\n", encoding="utf-8")

    resultado = editar_autorizado(ocorrencia=2)

    assert resultado.startswith("OK: 1 ocorrência(s)")
    assert arquivo.read_text(encoding="utf-8") == (
        "alvo\nmeio\nnovo\nfim\nalvo\n"
    )


def test_tudo_substitui_todas_as_ocorrencias(arquivo):
    arquivo.write_text("alvo meio alvo\n", encoding="utf-8")

    resultado = editar_autorizado(tudo=True)

    assert resultado.startswith("OK: 2 ocorrência(s)")
    assert arquivo.read_text(encoding="utf-8") == "novo meio novo\n"


def test_trecho_nao_encontrado_nao_altera_arquivo(arquivo):
    original = "conteúdo original\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = editar_autorizado()

    assert "trecho a procurar não encontrado" in resultado
    assert arquivo.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("opcoes", "erro"),
    [
        ({"ocorrencia": 0}, "'ocorrencia' deve ser um inteiro a partir de 1"),
        ({"ocorrencia": -1}, "'ocorrencia' deve ser um inteiro a partir de 1"),
        ({"ocorrencia": 1.5}, "'ocorrencia' deve ser um inteiro a partir de 1"),
        ({"ocorrencia": True}, "'ocorrencia' deve ser um inteiro a partir de 1"),
        ({"tudo": "sim"}, "'tudo' deve ser booleano"),
        ({"ocorrencia": 1, "tudo": True}, "não ambos"),
    ],
)
def test_opcoes_invalidas_nao_alteram_arquivo(arquivo, opcoes, erro):
    original = "alvo\nalvo\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = editar_autorizado(**opcoes)

    assert erro in resultado
    assert arquivo.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("procurar", "substituir", "erro"),
    [
        ("", "novo", "'procurar' deve ser uma string não vazia"),
        (None, "novo", "'procurar' deve ser uma string não vazia"),
        ("alvo", None, "'substituir' deve ser uma string"),
    ],
)
def test_textos_invalidos_nao_alteram_arquivo(
        arquivo, procurar, substituir, erro):
    original = "alvo\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = editar_autorizado(
        procurar=procurar, substituir=substituir
    )

    assert erro in resultado
    assert arquivo.read_text(encoding="utf-8") == original


def test_ocorrencia_fora_da_quantidade_nao_altera_arquivo(arquivo):
    original = "alvo\nalvo\n"
    arquivo.write_text(original, encoding="utf-8")

    resultado = editar_autorizado(ocorrencia=3)

    assert "fora da faixa" in resultado
    assert "Use um valor de 1 a 2" in resultado
    assert arquivo.read_text(encoding="utf-8") == original
