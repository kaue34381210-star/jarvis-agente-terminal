"""Adaptador para a API da Anthropic (Claude) — endpoint Messages, via HTTP
puro (requests), coerente com os outros motores do HRX CODE (sem SDK).

Doc oficial: POST https://api.anthropic.com/v1/messages
  headers: x-api-key, anthropic-version: 2023-06-01, content-type: json
  body:    {model, max_tokens, system, messages:[{role:user|assistant, content}]}

Diferenças do protocolo (vs OpenAI): o system vai num campo TOP-LEVEL (não na
lista messages), e não se manda `temperature`/`thinking` (nos modelos Opus 4.x
esses campos dão 400 e sujariam o JSON do protocolo ReAct). Mesma assinatura
dos outros motores: chamar(mensagens) -> (texto, None).
"""
import requests

import config

VERSAO_API = "2023-06-01"


def _para_claude(mensagens: list):
    """Formato interno -> (system, messages) do Claude. Junta os 'system' num
    só campo top-level; o resto vira user/assistant."""
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
