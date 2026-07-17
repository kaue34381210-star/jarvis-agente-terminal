import importlib
import json

import pytest

from hrx_code import agente
from hrx_code import config


@pytest.fixture
def motor_cfg_isolado(tmp_path, monkeypatch):
    caminho = tmp_path / "motor.json"
    monkeypatch.setenv("HRX_MOTOR_CFG", str(caminho))
    yield caminho
    monkeypatch.undo()
    importlib.reload(config)


@pytest.mark.parametrize(
    ("valor_arquivo", "valor_ambiente", "esperado"),
    [
        (" Completa ", "compacta", "completa"),
        (None, " Completa ", "completa"),
        (None, None, "compacta"),
    ],
)
def test_memoria_prompt_respeita_precedencia_e_normalizacao(
    motor_cfg_isolado, monkeypatch, valor_arquivo, valor_ambiente, esperado
):
    if valor_arquivo is not None:
        motor_cfg_isolado.write_text(
            json.dumps({"memoria_prompt": valor_arquivo}), encoding="utf-8"
        )
    if valor_ambiente is None:
        monkeypatch.delenv("HRX_MEMORIA_PROMPT", raising=False)
    else:
        monkeypatch.setenv("HRX_MEMORIA_PROMPT", valor_ambiente)

    importlib.reload(config)

    assert config.MEMORIA_PROMPT == esperado


def test_comando_memoria_modo_persiste_e_preserva_motor(
    motor_cfg_isolado, monkeypatch
):
    inicial = {
        "motor": "ollama",
        "ollama_modelo": "qwen2.5-coder",
        "memoria_prompt": "compacta",
    }
    motor_cfg_isolado.write_text(json.dumps(inicial), encoding="utf-8")
    monkeypatch.setenv("HRX_MEMORIA_PROMPT", "compacta")
    importlib.reload(config)

    consumido = agente._comando_especial(
        None, None, None, [], "/memoria modo completa"
    )

    esperado = {**inicial, "memoria_prompt": "completa"}
    assert consumido is True
    assert json.loads(motor_cfg_isolado.read_text(encoding="utf-8")) == esperado
    assert config._CFG == esperado
    assert config.MEMORIA_PROMPT == "completa"
