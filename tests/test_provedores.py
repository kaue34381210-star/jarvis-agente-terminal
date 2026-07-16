from unittest.mock import Mock

import pytest

from hrx_code import claude
from hrx_code import config
from hrx_code import openai_compat


MENSAGENS = [
    {"role": "system", "content": "Seja direto."},
    {"role": "user", "content": "Olá"},
]


def test_openai_envia_payload_autenticado(monkeypatch):
    resposta = Mock(status_code=200, text="")
    resposta.json.return_value = {
        "choices": [{"message": {"content": "  resposta  "}}]
    }
    post = Mock(return_value=resposta)
    monkeypatch.setattr(openai_compat.requests, "post", post)

    resultado = openai_compat.chamar(
        MENSAGENS, "https://api.exemplo/v1/chat/completions", "modelo-x", "segredo", 9
    )

    assert resultado == ("resposta", None)
    chamada = post.call_args
    assert chamada.kwargs["headers"]["Authorization"] == "Bearer segredo"
    assert chamada.kwargs["json"]["model"] == "modelo-x"
    assert chamada.kwargs["json"]["messages"] == MENSAGENS
    assert chamada.kwargs["json"]["stream"] is False
    assert chamada.kwargs["timeout"] == 9


def test_openai_sem_chave_e_resposta_fora_do_formato(monkeypatch):
    resposta = Mock(status_code=200, text="resposta bruta")
    resposta.json.side_effect = ValueError("json inválido")
    post = Mock(return_value=resposta)
    monkeypatch.setattr(openai_compat.requests, "post", post)

    resultado = openai_compat.chamar(MENSAGENS, "http://local/v1", "local")

    assert resultado == ("resposta bruta", None)
    assert "Authorization" not in post.call_args.kwargs["headers"]


def test_openai_converte_erro_de_rede(monkeypatch):
    monkeypatch.setattr(
        openai_compat.requests,
        "post",
        Mock(side_effect=openai_compat.requests.Timeout("tempo esgotado")),
    )

    with pytest.raises(RuntimeError, match="rede ao falar com modelo-x"):
        openai_compat.chamar(MENSAGENS, "https://api.exemplo/v1", "modelo-x")


def test_openai_rejeita_status_de_erro(monkeypatch):
    resposta = Mock(status_code=401, text="chave inválida")
    monkeypatch.setattr(openai_compat.requests, "post", Mock(return_value=resposta))

    with pytest.raises(RuntimeError, match="modelo-x respondeu 401: chave inválida"):
        openai_compat.chamar(MENSAGENS, "https://api.exemplo/v1", "modelo-x")


def test_claude_separa_e_combina_mensagens_de_sistema():
    system, mensagens = claude._para_claude([
        {"role": "system", "content": "Regra um."},
        {"role": "system", "content": "Regra dois."},
        {"role": "assistant", "content": "Resposta"},
        {"role": "user", "content": "Pergunta"},
    ])

    assert system == "Regra um.\n\nRegra dois."
    assert mensagens == [
        {"role": "assistant", "content": "Resposta"},
        {"role": "user", "content": "Pergunta"},
    ]


def test_claude_envia_payload_e_filtra_blocos_de_texto(monkeypatch):
    resposta = Mock(status_code=200, text="")
    resposta.json.return_value = {
        "content": [
            {"type": "thinking", "thinking": "interno"},
            {"type": "text", "text": "Olá "},
            {"type": "text", "text": "mundo"},
        ]
    }
    post = Mock(return_value=resposta)
    monkeypatch.setattr(claude.requests, "post", post)

    resultado = claude.chamar(
        MENSAGENS,
        "segredo",
        modelo="claude-teste",
        max_tokens=123,
        base_url="https://claude.exemplo/messages",
        timeout=8,
    )

    assert resultado == ("Olá mundo", None)
    chamada = post.call_args
    assert chamada.args[0] == "https://claude.exemplo/messages"
    assert chamada.kwargs["headers"]["x-api-key"] == "segredo"
    assert chamada.kwargs["json"] == {
        "model": "claude-teste",
        "max_tokens": 123,
        "messages": [{"role": "user", "content": "Olá"}],
        "system": "Seja direto.",
    }
    assert chamada.kwargs["timeout"] == 8


def test_claude_converte_erro_de_rede(monkeypatch):
    monkeypatch.setattr(
        claude.requests,
        "post",
        Mock(side_effect=claude.requests.ConnectionError("offline")),
    )

    with pytest.raises(RuntimeError, match="rede ao falar com o Claude"):
        claude.chamar(MENSAGENS, "segredo")


def test_claude_rejeita_status_de_erro(monkeypatch):
    resposta = Mock(status_code=429, text="limite")
    monkeypatch.setattr(claude.requests, "post", Mock(return_value=resposta))

    with pytest.raises(RuntimeError, match="Claude respondeu 429: limite"):
        claude.chamar(MENSAGENS, "segredo")
