"""Motor local: modelo servido via llama.cpp/llamafile num endpoint compatível
com a API da OpenAI (/v1/chat/completions). Sem chaves, sem cota, offline.

Subir o servidor (Qwen2.5-7B-Instruct):
    ./iniciar-qwen.sh
"""
import requests
from urllib.parse import urlsplit, urlunsplit

import config

# dica de como subir o modelo, mostrada quando a conexão falha
DICA_SERVIDOR = "./iniciar-qwen.sh"


def disponivel() -> bool:
    """True se o servidor local responde (checagem rápida)."""
    partes = urlsplit(config.LOCAL_URL)
    caminho = partes.path.rstrip("/")
    if caminho.endswith("/v1/chat/completions"):
        base_path = caminho[: -len("/v1/chat/completions")]
    elif caminho.endswith("/chat/completions"):
        base_path = caminho[: -len("/chat/completions")]
    elif "/v1/" in caminho:
        base_path = caminho.rsplit("/v1/", 1)[0]
    else:
        base_path = caminho
    base = urlunsplit((partes.scheme, partes.netloc, base_path.rstrip("/"), "", ""))
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
