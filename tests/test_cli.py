import subprocess
import sys

from hrx_code import __version__
from hrx_code import agente


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


def test_execucao_com_python_m():
    resultado = subprocess.run(
        [sys.executable, "-m", "hrx_code", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert resultado.stdout.strip() == f"HRX CODE {__version__}"
