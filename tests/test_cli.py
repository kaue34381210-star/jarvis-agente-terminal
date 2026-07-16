import sys

import agente
from versao import __version__


def _motor_nao_deve_iniciar():
    raise AssertionError("a CLI de metadados tentou iniciar o motor")


def test_version_nao_inicia_motor(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hrx", "--version"])
    monkeypatch.setattr(agente, "_preparar_motor", _motor_nao_deve_iniciar)

    agente.main()

    assert capsys.readouterr().out.strip() == f"HRX CODE {__version__}"


def test_help_nao_inicia_motor(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hrx", "--help"])
    monkeypatch.setattr(agente, "_preparar_motor", _motor_nao_deve_iniciar)

    agente.main()

    saida = capsys.readouterr().out
    assert "hrx \"tarefa\"" in saida
    assert "hrx --version" in saida
