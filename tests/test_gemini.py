from unittest.mock import Mock

from hrx_code import gemini


def test_pool_rotaciona_chaves_em_cooldown(monkeypatch):
    agora = [100.0]
    monkeypatch.setattr(gemini.time, "time", lambda: agora[0])
    pool = gemini.PoolChaves(["CHAVE_A", "CHAVE_B"])

    assert pool.proxima_disponivel() == (0, "CHAVE_A")
    pool.penalizar(0, 2)
    assert pool.proxima_disponivel() == (1, "CHAVE_B")
    pool.penalizar(1, 2)
    assert pool.proxima_disponivel() == (0, "CHAVE_A")

    agora[0] += 2.1
    assert pool.proxima_disponivel() == (0, "CHAVE_A")


def test_retry_after_le_recomendacao_da_api():
    resposta = Mock()
    resposta.json.return_value = {
        "error": {
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "12.5s",
                }
            ]
        }
    }

    assert gemini._retry_after(resposta) == 12.5
