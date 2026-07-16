import pytest

from hrx_code import config
from hrx_code import permissao


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    monkeypatch.setattr(config, "REPO", str(raiz))
    return raiz


@pytest.mark.parametrize(
    ("ferramenta", "campo"),
    [
        ("escrever_arquivo", "caminho"),
        ("editar_arquivo", "caminho"),
        ("criar_planilha", "nome"),
        ("criar_pdf", "nome"),
    ],
)
def test_escrita_interna_exige_confirmacao_simples(projeto, ferramenta, campo):
    pol = permissao.Politica(modo="cauteloso")
    args = {campo: "saida/arquivo.txt"}

    nivel, motivo = pol.classificar(
        permissao.comando_de(ferramenta, args), ferramenta=ferramenta, args=args
    )

    assert nivel == "amarelo"
    assert "no projeto" in motivo


@pytest.mark.parametrize("caminho", ["../segredo.txt", "/tmp/segredo.txt"])
def test_escrita_externa_e_alto_risco_mesmo_no_modo_auto(projeto, caminho):
    pol = permissao.Politica(modo="auto")
    args = {"caminho": caminho}
    comando = permissao.comando_de("escrever_arquivo", args)
    pol.liberar_sempre(comando)

    nivel, motivo = pol.classificar(
        comando, ferramenta="escrever_arquivo", args=args
    )

    assert nivel == "vermelho"
    assert "fora do projeto" in motivo


def test_escrita_interna_pode_rodar_no_modo_auto(projeto):
    pol = permissao.Politica(modo="auto")
    args = {"caminho": "saida.txt"}

    nivel, motivo = pol.classificar(
        permissao.comando_de("escrever_arquivo", args),
        ferramenta="escrever_arquivo",
        args=args,
    )

    assert nivel == "verde"
    assert "modo auto" in motivo


def test_caminho_vazio_e_alto_risco(projeto):
    pol = permissao.Politica()
    args = {"caminho": ""}

    nivel, motivo = pol.classificar(
        permissao.comando_de("escrever_arquivo", args),
        ferramenta="escrever_arquivo",
        args=args,
    )

    assert nivel == "vermelho"
    assert motivo == "caminho de escrita inválido"
