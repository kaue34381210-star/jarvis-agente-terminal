"""Teste do adaptador HTTP do motor local, sem iniciar um modelo real."""
from unittest.mock import Mock, patch

import local


def testar_chamada():
    resposta = Mock()
    resposta.status_code = 200
    resposta.json.return_value = {"choices": [{"message": {"content": "  olá  "}}]}
    with patch("local.requests.post", return_value=resposta) as post:
        texto, extra = local.chamar([{"role": "user", "content": "oi"}])
    assert (texto, extra) == ("olá", None)
    corpo = post.call_args.kwargs["json"]
    assert corpo["messages"] == [{"role": "user", "content": "oi"}]
    assert corpo["stream"] is False


def testar_disponibilidade():
    health = Mock(ok=True)
    with patch("local.requests.get", return_value=health):
        assert local.disponivel() is True


if __name__ == "__main__":
    testar_chamada()
    testar_disponibilidade()
    print("✅ adaptador local funcionando")
