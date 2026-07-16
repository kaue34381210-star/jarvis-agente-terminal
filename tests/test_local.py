from unittest.mock import Mock

from hrx_code import config
from hrx_code import local


def test_chamada_local(monkeypatch):
    resposta = Mock(status_code=200)
    resposta.json.return_value = {
        "choices": [{"message": {"content": "  olá  "}}]
    }
    post = Mock(return_value=resposta)
    monkeypatch.setattr(local.requests, "post", post)

    texto, extra = local.chamar([{"role": "user", "content": "oi"}])

    assert (texto, extra) == ("olá", None)
    corpo = post.call_args.kwargs["json"]
    assert corpo["messages"] == [{"role": "user", "content": "oi"}]
    assert corpo["stream"] is False


def test_disponibilidade_por_health(monkeypatch):
    get = Mock(return_value=Mock(ok=True))
    monkeypatch.setattr(local.requests, "get", get)

    assert local.disponivel() is True


def test_disponibilidade_com_url_customizada(monkeypatch):
    get = Mock(return_value=Mock(ok=True))
    monkeypatch.setattr(local.requests, "get", get)
    monkeypatch.setattr(
        config,
        "LOCAL_URL",
        "http://127.0.0.1:8080/chat/completions",
    )

    assert local.disponivel() is True
    assert get.call_args.args[0] == "http://127.0.0.1:8080/health"
