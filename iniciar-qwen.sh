#!/usr/bin/env bash
# Inicia o Qwen GGUF com o servidor HTTP compatível com OpenAI do llamafile.
set -euo pipefail

LLAMAFILE="${JARVIS_LLAMAFILE:-$HOME/agente-ia/bin/llamafile}"
MODELO="${JARVIS_MODELO_GGUF:-$HOME/agente-ia/bin/modelo.gguf}"
PORTA="${JARVIS_PORTA:-8080}"
CONTEXTO="${JARVIS_CONTEXTO:-4096}"

if [ ! -x "$LLAMAFILE" ]; then
    echo "Erro: llamafile não encontrado ou não executável: $LLAMAFILE" >&2
    exit 1
fi
if [ ! -f "$MODELO" ]; then
    echo "Erro: modelo GGUF não encontrado: $MODELO" >&2
    exit 1
fi

echo "Iniciando Qwen local em http://127.0.0.1:$PORTA"
echo "Modelo: $MODELO"
exec "$LLAMAFILE" --server --port "$PORTA" -c "$CONTEXTO" -m "$MODELO"
