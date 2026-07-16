import os

import pytest

from hrx_code import caminhos


def test_resolve_caminho_relativo_dentro_do_projeto(tmp_path):
    projeto = tmp_path / "projeto"
    projeto.mkdir()

    assert caminhos.resolver(str(projeto), "src/app.py") == str(
        projeto / "src" / "app.py"
    )
    assert caminhos.esta_dentro(str(projeto), "src/app.py") is True


def test_rejeita_traversal_e_prefixo_parecido(tmp_path):
    projeto = tmp_path / "projeto"
    projeto.mkdir()

    assert caminhos.esta_dentro(str(projeto), "../segredo.txt") is False
    assert caminhos.esta_dentro(
        str(projeto), str(tmp_path / "projeto-backup" / "segredo.txt")
    ) is False


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sistema sem symlink")
def test_rejeita_link_simbolico_que_escapa_do_projeto(tmp_path):
    projeto = tmp_path / "projeto"
    externo = tmp_path / "externo"
    projeto.mkdir()
    externo.mkdir()
    (projeto / "atalho").symlink_to(externo, target_is_directory=True)

    assert caminhos.esta_dentro(str(projeto), "atalho/segredo.txt") is False
    with pytest.raises(ValueError, match="fora da área permitida"):
        caminhos.exigir_dentro(str(projeto), "atalho/segredo.txt")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sistema sem symlink")
def test_aceita_link_simbolico_com_destino_interno(tmp_path):
    projeto = tmp_path / "projeto"
    destino = projeto / "destino"
    projeto.mkdir()
    destino.mkdir()
    (projeto / "atalho").symlink_to(destino, target_is_directory=True)

    assert caminhos.esta_dentro(str(projeto), "atalho/arquivo.txt") is True
