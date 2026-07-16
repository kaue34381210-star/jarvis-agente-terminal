import pytest

from hrx_code import comandos


@pytest.fixture
def pasta_comandos(tmp_path, monkeypatch):
    pasta = tmp_path / "comandos"
    pasta.mkdir()
    monkeypatch.setenv("HRX_COMANDOS_DIR", str(pasta))
    monkeypatch.setattr(comandos, "_CACHE", None)
    return pasta


def test_carrega_frontmatter_e_ignora_reservados(pasta_comandos):
    (pasta_comandos / "revisar.md").write_text(
        "---\ndescricao: Revisa o projeto\n---\nAnalise o código.",
        encoding="utf-8",
    )
    (pasta_comandos / "config.md").write_text("não deve carregar", encoding="utf-8")
    (pasta_comandos / "notas.txt").write_text("não é comando", encoding="utf-8")

    carregados = comandos.carregar()

    assert set(carregados) == {"/revisar"}
    assert carregados["/revisar"]["descricao"] == "Revisa o projeto"
    assert carregados["/revisar"]["corpo"] == "Analise o código."


def test_expande_argumentos_e_anexa_quando_nao_ha_placeholder(pasta_comandos):
    (pasta_comandos / "testar.md").write_text(
        "Rode os testes de {argumentos} e {args}.", encoding="utf-8"
    )
    (pasta_comandos / "explicar.md").write_text(
        "Explique o projeto.", encoding="utf-8"
    )

    assert comandos.expandir("/testar src") == "Rode os testes de src e src."
    assert comandos.expandir("/explicar detalhes") == "Explique o projeto.\n\ndetalhes"
    assert comandos.expandir("/inexistente") is None


def test_cache_so_muda_apos_recarregar(pasta_comandos):
    assert comandos.carregar() == {}
    (pasta_comandos / "publicar.md").write_text("Novo comando.", encoding="utf-8")

    assert comandos.carregar() == {}
    assert "/publicar" in comandos.recarregar()
