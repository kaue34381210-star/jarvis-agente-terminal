#!/usr/bin/env bash
# Instalador do JARVIS: registra o comando `jarvis` no terminal.
# Instala em ~/.local/share/jarvis, chaves em ~/.config/jarvis, comando em ~/.local/bin.
set -e

CMD="jarvis"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/jarvis"
BIN="$HOME/.local/bin"
CFG="$HOME/.config/jarvis"

echo "┌─ Instalando JARVIS ─────────────────────────────"

# 1) código
echo "│ copiando código..."
mkdir -p "$DEST" "$DEST/workspace" "$DEST/dados" "$CFG" "$BIN"
cp "$SRC"/config.py "$SRC"/ferramentas.py "$SRC"/gemini.py "$SRC"/local.py "$SRC"/aprovacao.py "$SRC"/agente.py "$SRC"/iniciar-qwen.sh "$DEST"/
[ -f "$SRC/teste_failover.py" ] && cp "$SRC/teste_failover.py" "$DEST"/
[ -f "$SRC/teste_aprovacao.py" ] && cp "$SRC/teste_aprovacao.py" "$DEST"/
[ -f "$SRC/teste_local.py" ] && cp "$SRC/teste_local.py" "$DEST"/
[ -f "$SRC/README.md" ] && cp "$SRC/README.md" "$DEST"/

# 2) ambiente Python + dependências
echo "│ preparando ambiente Python (rich, requests)..."
[ -x "$DEST/.venv/bin/python" ] || python3 -m venv "$DEST/.venv"
if ! "$DEST/.venv/bin/python" -c 'import rich, requests, openpyxl, reportlab' 2>/dev/null; then
    "$DEST/.venv/bin/pip" install --quiet --upgrade pip rich requests openpyxl reportlab
fi

# 3) arquivo de chaves (só cria o template se ainda não existe — não sobrescreve as suas)
if [ ! -f "$CFG/chaves.txt" ]; then
    cat > "$CFG/chaves.txt" <<'EOF'
# Cole UMA chave da API do Gemini por linha (sem aspas).
# Linhas com # são ignoradas. Este arquivo NÃO vai pro git.
EOF
    chmod 600 "$CFG/chaves.txt"
    echo "│ criado $CFG/chaves.txt (preencha com suas chaves)"
else
    echo "│ mantendo suas chaves em $CFG/chaves.txt"
fi

# 4) configuração do motor. Só é criada uma vez, para preservar ajustes do usuário.
if [ ! -f "$CFG/ambiente" ]; then
    cat > "$CFG/ambiente" <<'EOF'
# Configuração do JARVIS. Altere aqui para trocar de motor.
JARVIS_MOTOR=local
JARVIS_LOCAL_URL=http://127.0.0.1:8080/v1/chat/completions
JARVIS_MODELO_LOCAL=Qwen2.5-7B-Instruct
JARVIS_LOCAL_TIMEOUT=180

# Arquivos locais do Qwen/llamafile.
JARVIS_LLAMAFILE=$HOME/agente-ia/bin/llamafile
JARVIS_MODELO_GGUF=$HOME/agente-ia/bin/modelo.gguf
JARVIS_CONTEXTO=4096
JARVIS_PORTA=8080
EOF
    chmod 600 "$CFG/ambiente"
    echo "│ configurado motor local Qwen em $CFG/ambiente"
else
    echo "│ mantendo configuração em $CFG/ambiente"
fi

# 5) comandos globais (shims)
cat > "$BIN/$CMD" <<EOF
#!/usr/bin/env bash
export AGENTE_BASE="$DEST"
export JARVIS_CHAVES="$CFG/chaves.txt"
if [ -f "$CFG/ambiente" ]; then
    set -a
    . "$CFG/ambiente"
    set +a
fi
exec "$DEST/.venv/bin/python" "$DEST/agente.py" "\$@"
EOF
chmod +x "$BIN/$CMD"
cat > "$BIN/${CMD}-qwen" <<EOF
#!/usr/bin/env bash
if [ -f "$CFG/ambiente" ]; then
    set -a
    . "$CFG/ambiente"
    set +a
fi
exec "$DEST/iniciar-qwen.sh"
EOF
chmod +x "$BIN/${CMD}-qwen"
echo "│ comandos '$CMD' e '${CMD}-qwen' criados em $BIN"

# 6) garante ~/.local/bin no PATH
NO_PATH=1
case ":$PATH:" in *":$BIN:"*) NO_PATH=0 ;; esac
if [ "$NO_PATH" = 1 ]; then
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$rc" ] && ! grep -q 'HOME/.local/bin' "$rc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
        fi
    done
    echo "│ adicionei ~/.local/bin ao PATH (abra um novo terminal ou 'source ~/.bashrc')"
fi

echo "└─────────────────────────────────────────────────"
echo
echo "✅ JARVIS instalado!"
echo "   1) em um terminal, inicie o Qwen: ${CMD}-qwen"
echo "   2) em outro terminal, abra o JARVIS: $CMD"
echo "   configuração: $CFG/ambiente"
