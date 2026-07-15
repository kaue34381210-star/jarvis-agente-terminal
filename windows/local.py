"""Motor local: modelo servido via llama.cpp/llamafile num endpoint compatível
com a API da OpenAI (/v1/chat/completions). Sem chaves, sem cota, offline.

Subir o servidor (Qwen2.5-7B):
    ~/agente-ia/bin/llamafile --server --port 8080 -c 4096 -m ~/agente-ia/bin/modelo.gguf
"""
import requests

import config

# dica de como subir o modelo, mostrada quando a conexão falha
DICA_SERVIDOR = ("~/agente-ia/bin/llamafile --server --port 8080 -c 4096 "
                 "-m ~/agente-ia/bin/modelo.gguf")


def disponivel() -> bool:
    """True se o servidor local responde (checagem rápida)."""
    base = config.LOCAL_URL.rsplit("/v1/", 1)[0]
    try:
        resposta = requests.get(base + "/health", timeout=3)
        if resposta.ok:
            return True
    except requests.RequestException:
        pass
    try:
        return requests.get(base, timeout=3).ok
    except requests.RequestException:
        return False


def chamar(mensagens: list, on_rotacao=None):
    """Assinatura compatível com gemini.chamar (on_rotacao é ignorado).
    Retorna (texto, None)."""
    body = {
        "model": config.MODELO_LOCAL,
        "messages": mensagens,
        "temperature": config.TEMPERATURA,
        "stream": False,
    }
    try:
        r = requests.post(config.LOCAL_URL, json=body, timeout=config.LOCAL_TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(
            f"Não consegui falar com o modelo local em {config.LOCAL_URL}.\n"
            f"Suba o servidor primeiro:\n    {DICA_SERVIDOR}\n(detalhe: {e})")
    if r.status_code != 200:
        raise RuntimeError(f"modelo local respondeu {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except (KeyError, IndexError, ValueError):
        return str(r.text)[:500], None
