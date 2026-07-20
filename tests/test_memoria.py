import pytest

from hrx_code import config
from hrx_code import ferramentas


@pytest.fixture
def memoria_tmp(tmp_path, monkeypatch):
    dados = tmp_path / "dados"
    monkeypatch.setattr(config, "DADOS", str(dados))
    monkeypatch.setattr(config, "MEMORIA", str(dados / "memoria.json"))
    monkeypatch.setattr(config, "MEMORIA_PROMPT", "compacta")
    monkeypatch.setattr(config, "MEMORIA_PROMPT_RESUMO_A_PARTIR", 20)
    monkeypatch.setattr(config, "MEMORIA_PROMPT_MAX_ITENS", 8)
    monkeypatch.setattr(config, "MEMORIA_PROMPT_MAX_CHARS", 900)
    return dados


def test_salva_lista_e_nao_duplica(memoria_tmp):
    primeira = ferramentas.memoria_salvar("Usar pytest", "preferencia")
    duplicada = ferramentas.memoria_salvar("usar PYTEST", "preferencia")
    lista = ferramentas.memoria_listar()

    assert "memória #1 guardada" in primeira
    assert "já estava na memória" in duplicada
    assert lista == "#1 [preferencia] Usar pytest"


def test_esquece_por_id_e_por_termo(memoria_tmp):
    ferramentas.memoria_salvar("Projeto Alpha", "projeto")
    ferramentas.memoria_salvar("Executar deploy azul", "comando")

    assert "1 memória(s) esquecida(s)" in ferramentas.memoria_esquecer("#1")
    assert "Projeto Alpha" not in ferramentas.memoria_listar()
    assert "1 memória(s) esquecida(s)" in ferramentas.memoria_esquecer("DEPLOY")
    assert ferramentas.memoria_listar() == "(nenhuma memória guardada)"


def test_esquecer_por_termo_lista_todos_os_ids_removidos(memoria_tmp):
    ferramentas.memoria_salvar("Commit da API", "decisao")
    ferramentas.memoria_salvar("Revisar commit antigo", "tarefa")
    ferramentas.memoria_salvar("Manter testes rápidos", "preferencia")

    resultado = ferramentas.memoria_esquecer("commit")

    assert resultado == (
        "IDs removidos: #1, #2\n"
        "OK: 2 memória(s) esquecida(s)."
    )
    assert ferramentas.memoria_listar() == "#3 [preferencia] Manter testes rápidos"


def test_compacta_memorias_antigas_e_limpa_arquivos(memoria_tmp, monkeypatch):
    monkeypatch.setattr(config, "MEMORIA_PROMPT_RESUMO_A_PARTIR", 2)
    monkeypatch.setattr(config, "MEMORIA_PROMPT_MAX_ITENS", 1)
    monkeypatch.setattr(config, "MEMORIA_PROMPT_RESUMO_ITENS", 10)
    monkeypatch.setattr(config, "MEMORIA_PROMPT_RESUMO_CHARS", 2000)

    ferramentas.memoria_salvar("primeira decisão", "decisao")
    ferramentas.memoria_salvar("segunda decisão", "decisao")
    ferramentas.memoria_salvar("informação recente", "fato")
    memorias = ferramentas.carregar_memorias()

    assert memorias[0]["tipo"] == "resumo"
    assert "primeira decisão" in memorias[0]["texto"]
    assert "segunda decisão" in memorias[0]["texto"]
    assert memorias[1]["texto"] == "informação recente"
    assert ferramentas.memoria_limpar() == "OK: memória e resumo limpos."
    assert ferramentas.carregar_memorias() == []
