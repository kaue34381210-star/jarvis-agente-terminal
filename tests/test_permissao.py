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
        ("aplicar_patch", "caminho"),
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


@pytest.mark.parametrize(
    "comando",
    [
        "git log --output=/tmp/saida",
        "git -c core.pager=!sh log",
        "git diff --ext-diff",
    ],
)
def test_git_com_flag_sensivel_nao_e_rebaixado_no_modo_auto(projeto, comando):
    pol = permissao.Politica(modo="auto")
    pol.liberar_sempre(comando)

    nivel, motivo = pol.classificar(comando)

    assert nivel == "vermelho"
    assert motivo == "git com flag sensível (grava/executa arbitrário)"


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


def test_dry_run_fica_desativado_por_padrao_e_pode_ser_ativado():
    assert permissao.Politica().dry_run is False
    assert permissao.Politica(dry_run=True).dry_run is True


def test_buscar_web_entra_no_gate_e_exibe_url(projeto):
    args = {"url": "https://exemplo.test/documentacao"}
    comando = permissao.comando_de("buscar_web", args)
    pol = permissao.Politica(modo="cauteloso")

    nivel, _ = pol.classificar(comando, ferramenta="buscar_web", args=args)

    assert permissao.exige_aprovacao("buscar_web") is True
    assert comando == "buscar_web https://exemplo.test/documentacao"
    assert nivel == "amarelo"


def test_trinco_rejeita_args_alterados_e_invalida_autorizacao(projeto):
    pol = permissao.Politica()
    comando = "escrever_arquivo saida.txt"
    aprovados = {"caminho": "saida.txt", "conteudo": "aprovado"}
    alterados = {"caminho": "saida.txt", "conteudo": "trocado"}
    pol.liberar(comando, "escrever_arquivo", aprovados)

    assert pol.consumir(comando, "escrever_arquivo", alterados) is False
    assert pol.consumir(comando, "escrever_arquivo", aprovados) is False


def test_trinco_normaliza_argumentos_padrao_omitidos(projeto):
    pol = permissao.Politica()
    comando = "buscar_web https://exemplo.test"
    pol.liberar(comando, "buscar_web", {"url": "https://exemplo.test"})

    assert pol.consumir(
        comando,
        "buscar_web",
        {"url": "https://exemplo.test", "max_chars": 8000},
    ) is True
