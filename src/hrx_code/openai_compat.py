"""Adaptador para provedores compatíveis com Chat Completions."""
import requests

from . import config


def chamar(mensagens: list, base_url: str, modelo: str, api_key: str = None,
           timeout: int = None, on_rotacao=None):
    """Chama um endpoint compatível e retorna texto e índice de chave vazio."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": modelo,
        "messages": mensagens,
        "temperature": config.TEMPERATURA,
        "stream": False,
    }
    try:
        r = requests.post(base_url, json=body, headers=headers,
                          timeout=timeout or config.TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(f"rede ao falar com {modelo} ({base_url}): {e}")
    if r.status_code != 200:
        raise RuntimeError(f"{modelo} respondeu {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except (KeyError, IndexError, ValueError):
        return str(r.text)[:500], None
