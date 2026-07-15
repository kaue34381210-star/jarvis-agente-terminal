"""Configuração do agente de terminal (motor Gemini)."""
import os
import sys


def _base() -> str:
    if os.environ.get("AGENTE_BASE"):
        return os.path.abspath(os.environ["AGENTE_BASE"])
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE = _base()

# --- Identidade ---
NOME = os.environ.get("AGENTE_NOME", "JARVIS")   # troque à vontade

# --- Seleção de motor: 'gemini' (API + failover) ou 'local' (Qwen self-hosted) ---
MOTOR = os.environ.get("JARVIS_MOTOR", "gemini").strip().lower()

# --- Motor Gemini ---
MODELO = os.environ.get("GEMINI_MODELO", "gemini-2.0-flash")

# --- Motor local (llama.cpp/llamafile servindo um .gguf; endpoint estilo OpenAI) ---
LOCAL_URL = os.environ.get("JARVIS_LOCAL_URL", "http://127.0.0.1:8080/v1/chat/completions")
MODELO_LOCAL = os.environ.get("JARVIS_MODELO_LOCAL", "Qwen2.5-7B-Instruct")
LOCAL_TIMEOUT = int(os.environ.get("JARVIS_LOCAL_TIMEOUT", "180"))  # 7B é lento


def _arq_chaves() -> str:
    # 1) definido pelo instalador (shim exporta JARVIS_CHAVES)
    if os.environ.get("JARVIS_CHAVES"):
        return os.environ["JARVIS_CHAVES"]
    # 2) local padrão de config do usuário (sobrevive a reinstalação)
    cfg = os.path.expanduser("~/.config/jarvis/chaves.txt")
    if os.path.exists(cfg):
        return cfg
    # 3) ao lado do código (modo dev)
    return os.path.join(BASE, "chaves.txt")


ARQ_CHAVES = _arq_chaves()   # 1 chave por linha (NUNCA versionar)
TEMPERATURA = 0.3
TIMEOUT = 60          # segundos por request
MAX_ITER = 10         # trava anti-loop do ReAct

# --- Sandbox de arquivos: o agente só mexe aqui (configurável por env) ---
WORKSPACE = os.environ.get("AGENTE_WORKSPACE", os.path.join(BASE, "workspace"))
DADOS = os.environ.get("AGENTE_DADOS", os.path.join(BASE, "dados"))

# --- Git: opera no diretório de onde o jarvis foi chamado (fora da sandbox) ---
REPO = os.environ.get("AGENTE_REPO", os.getcwd())

# --- Memória persistente: fatos/decisões que o agente lembra entre sessões ---
MEMORIA = os.path.join(DADOS, "memoria.json")

# --- Segurança: aprovação inteligente (🟢🟡🔴) em aprovacao.py ---
# Não é mais uma whitelist que bloqueia: estes executáveis são tratados
# como SEMPRE 🟢 seguros (rodam sem pedir confirmação), somados aos padrões
# de leitura já reconhecidos. Qualquer outro comando é classificado por risco.
COMANDOS_PERMITIDOS = {
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "date", "whoami",
    "hostname", "grep", "find", "head", "tail", "wc",
}
TIMEOUT_COMANDO = 30
