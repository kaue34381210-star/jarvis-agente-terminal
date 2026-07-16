from unittest.mock import Mock

import pytest

from hrx_code import config
from hrx_code import ferramentas
from hrx_code import permissao


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    raiz = tmp_path / "projeto"
    dados = tmp_path / "dados"
    raiz.mkdir()
    monkeypatch.setattr(config, "REPO", str(raiz))
    monkeypatch.setattr(config, "DADOS", str(dados))
    monkeypatch.setattr(config, "MEMORIA", str(dados / "memoria.json"))
    permissao.usar(None)
    yield raiz
    permissao.usar(None)


def test_lista_e_busca_ignoram_artefatos(projeto):
    (projeto / "src").mkdir()
    (projeto / "src" / "app.py").write_text("# TODO: revisar\n", encoding="utf-8")
    (projeto / "build").mkdir()
    (projeto / "build" / "gerado.py").write_text("# TODO: ignorar\n", encoding="utf-8")

    arvore = ferramentas.listar_diretorio(".", recursivo=True)
    resultado = ferramentas.buscar_codigo("TODO", ext=".py")

    assert "src/" in arvore
    assert "build/" not in arvore
    assert "src/app.py:1" in resultado
    assert "gerado.py" not in resultado


def test_le_intervalo_com_numeros_de_linha(projeto):
    (projeto / "dados.txt").write_text("um\ndois\ntres\n", encoding="utf-8")

    resultado = ferramentas.ler_arquivo("dados.txt", inicio=2, fim=3)

    assert "linhas 2-3 de 3" in resultado
    assert "2\tdois" in resultado
    assert "3\ttres" in resultado
    assert "1\tum" not in resultado


def test_escrita_exige_e_consome_autorizacao(projeto):
    politica = permissao.Politica()
    permissao.usar(politica)
    args = {"caminho": "saida.txt"}
    comando = permissao.comando_de("escrever_arquivo", args)

    negado = ferramentas.escrever_arquivo("saida.txt", "conteúdo")
    politica.liberar(comando)
    permitido = ferramentas.escrever_arquivo("saida.txt", "conteúdo")
    reutilizado = ferramentas.escrever_arquivo("saida.txt", "outro")

    assert "não passou" in negado
    assert permitido.startswith("OK:")
    assert (projeto / "saida.txt").read_text(encoding="utf-8") == "conteúdo"
    assert "não passou" in reutilizado


def test_edita_todas_as_ocorrencias_com_autorizacao(projeto):
    arquivo = projeto / "app.py"
    arquivo.write_text("antigo\nlinha\nantigo\n", encoding="utf-8")
    politica = permissao.Politica()
    permissao.usar(politica)
    comando = permissao.comando_de("editar_arquivo", {"caminho": "app.py"})
    politica.liberar(comando)

    resultado = ferramentas.editar_arquivo("app.py", "antigo", "novo")

    assert "2 ocorrência(s)" in resultado
    assert arquivo.read_text(encoding="utf-8") == "novo\nlinha\nnovo\n"


def test_comando_nao_chega_ao_subprocess_sem_autorizacao(projeto, monkeypatch):
    executar = Mock(return_value=Mock(stdout="ok\n", stderr="", returncode=0))
    monkeypatch.setattr(ferramentas.subprocess, "run", executar)
    politica = permissao.Politica()
    permissao.usar(politica)

    negado = ferramentas.rodar_comando("echo ok")
    executar.assert_not_called()

    politica.liberar("echo ok")
    permitido = ferramentas.rodar_comando("echo ok")

    assert "não passou" in negado
    assert permitido == "ok"
    assert executar.call_args.kwargs["cwd"] == str(projeto)
    assert executar.call_args.kwargs["shell"] is True


def test_dispatcher_trata_nome_e_argumentos_invalidos():
    assert ferramentas.executar("inexistente", {}) == (
        "ERRO: ferramenta desconhecida 'inexistente'"
    )
    assert ferramentas.executar("ler_arquivo", {"campo": "x"}).startswith(
        "ERRO: argumentos inválidos para ler_arquivo:"
    )
