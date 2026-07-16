"""Adaptador HTTP para a API Messages da Anthropic."""
import requests

from . import config

VERSAO_API = "2023-06-01"


def _para_claude(mensagens: list):
    """Converte mensagens internas para o formato da Anthropic."""
    system = None
    msgs = []
    for m in mensagens:
        if m["role"] == "system":
            system = (system + "\n\n" + m["content"]) if system else m["content"]
            continue
        papel = "assistant" if m["role"] == "assistant" else "user"
        msgs.append({"role": papel, "content": m["content"]})
    return system, msgs


def chamar(mensagens: list, api_key: str, modelo: str = None,
           max_tokens: int = None, base_url: str = None, timeout: int = None,
           on_rotacao=None):
    """Chama a Messages API. Retorna (texto, None)."""
    system, msgs = _para_claude(mensagens)
    body = {
        "model": modelo or config.CLAUDE_MODELO,
        "max_tokens": max_tokens or config.CLAUDE_MAX_TOKENS,
        "messages": msgs,
    }
    if system:
        body["system"] = system
    headers = {
        "x-api-key": api_key,
        "anthropic-version": VERSAO_API,
        "content-type": "application/json",
    }
    try:
        r = requests.post(base_url or config.CLAUDE_URL, json=body,
                          headers=headers, timeout=timeout or config.TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(f"rede ao falar com o Claude: {e}")
    if r.status_code != 200:
        raise RuntimeError(f"Claude respondeu {r.status_code}: {r.text[:300]}")
    data = r.json()
    partes = [b.get("text", "") for b in data.get("content", [])
              if b.get("type") == "text"]
    return "".join(partes).strip(), None
