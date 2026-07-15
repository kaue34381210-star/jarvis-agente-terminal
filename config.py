"""Configuração do agente de terminal (motores plugáveis)."""
import json
import os
import sys


def _base() -> str:
    if os.environ.get("AGENTE_BASE"):
        return os.path.abspath(os.environ["AGENTE_BASE"])
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE = _base()

# --- Config persistente do motor (escrita pelo /config): motor selecionado,
# chaves de API e modelos. Fica FORA do repo, em ~/.config/hrx. ---
ARQ_MOTOR = os.path.expanduser(
    os.environ.get("HRX_MOTOR_CFG", "~/.config/hrx/motor.json"))

# --- Config persistente do perfil do agente: nome, tom, idioma e projeto
# atual. Fica separada do motor para manter as duas coisas independentes. ---
ARQ_PERFIL = os.path.expanduser(
    os.environ.get("HRX_PERFIL_CFG", "~/.config/hrx/perfil.json"))


def _carregar_motor_cfg() -> dict:
    try:
        with open(ARQ_MOTOR, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


_CFG = _carregar_motor_cfg()


def _carregar_perfil_cfg() -> dict:
    try:
        with open(ARQ_PERFIL, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


_PERFIL = _carregar_perfil_cfg()


def _cfg(env: str, chave: str, padrao):
    """Resolve uma config: /config > variável de ambiente > padrão."""
    v = _CFG.get(chave)
    if v not in (None, ""):
        return v
    return os.environ.get(env, padrao)


def salvar_motor(dados: dict) -> None:
    """Persiste as opções do /config fora do projeto e protege as chaves."""
    pasta = os.path.dirname(ARQ_MOTOR)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    temporario = ARQ_MOTOR + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporario, ARQ_MOTOR)
    try:
        os.chmod(ARQ_MOTOR, 0o600)
    except OSError:  # Windows não possui chmod POSIX equivalente
        pass


def salvar_perfil(dados: dict) -> None:
    """Persiste o perfil do agente fora do projeto e protege o arquivo."""
    pasta = os.path.dirname(ARQ_PERFIL)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    temporario = ARQ_PERFIL + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporario, ARQ_PERFIL)
    try:
        os.chmod(ARQ_PERFIL, 0o600)
    except OSError:  # Windows não possui chmod POSIX equivalente
        pass

def _pref(env: str, chave: str, padrao):
    """Resolve uma preferência do perfil: arquivo > variável de ambiente > padrão."""
    v = _PERFIL.get(chave)
    if v not in (None, ""):
        return v
    return os.environ.get(env, padrao)


# --- Identidade / preferências do agente ---
NOME = _pref("AGENTE_NOME", "nome", "HRX CODE")   # troque à vontade
TOM = str(_pref("AGENTE_TOM", "tom", "direto")).strip().lower()
IDIOMA = str(_pref("AGENTE_IDIOMA", "idioma", "pt-BR")).strip()
PROJETO = str(_pref("AGENTE_PROJETO", "projeto", "")).strip()

# --- Seleção de motor: gemini · local · openai · deepseek · ollama · claude ---
MOTOR = str(_cfg("HRX_MOTOR", "motor", "gemini")).strip().lower()

# --- Motor Gemini ---
MODELO = _cfg("GEMINI_MODELO", "gemini_modelo", "gemini-2.0-flash")

# --- Motor local (llama.cpp/llamafile servindo um .gguf; endpoint estilo OpenAI) ---
LOCAL_URL = _cfg("HRX_LOCAL_URL", "local_url", "http://127.0.0.1:8080/v1/chat/completions")
MODELO_LOCAL = _cfg("HRX_MODELO_LOCAL", "local_modelo", "Qwen2.5-7B-Instruct")
LOCAL_TIMEOUT = int(os.environ.get("HRX_LOCAL_TIMEOUT", "180"))  # 7B é lento

# --- Motores por API ---------------------------------------------------------
# Protocolo OpenAI (/v1/chat/completions): OpenAI, DeepSeek, Ollama.
OPENAI_URL = _cfg("OPENAI_URL", "openai_url", "https://api.openai.com/v1/chat/completions")
OPENAI_MODELO = _cfg("OPENAI_MODELO", "openai_modelo", "gpt-4o-mini")
OPENAI_API_KEY = _cfg("OPENAI_API_KEY", "openai_key", "")

DEEPSEEK_URL = _cfg("DEEPSEEK_URL", "deepseek_url", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODELO = _cfg("DEEPSEEK_MODELO", "deepseek_modelo", "deepseek-chat")
DEEPSEEK_API_KEY = _cfg("DEEPSEEK_API_KEY", "deepseek_key", "")

OLLAMA_URL = _cfg("OLLAMA_URL", "ollama_url", "http://127.0.0.1:11434/v1/chat/completions")
OLLAMA_MODELO = _cfg("OLLAMA_MODELO", "ollama_modelo", "llama3.1")

# Protocolo Anthropic (/v1/messages): Claude.
CLAUDE_URL = _cfg("CLAUDE_URL", "claude_url", "https://api.anthropic.com/v1/messages")
CLAUDE_MODELO = _cfg("CLAUDE_MODELO", "claude_modelo", "claude-opus-4-8")
ANTHROPIC_API_KEY = _cfg("ANTHROPIC_API_KEY", "claude_key", "")
CLAUDE_MAX_TOKENS = int(_cfg("CLAUDE_MAX_TOKENS", "claude_max_tokens", "4096"))


# Metadados de cada motor por API — fonte única p/ o dispatcher e o /config.
def provedor(nome: str) -> dict:
    """Config resolvida de um motor por API (base_url, modelo, chave, se exige
    chave e qual protocolo). Retorna {} para gemini/local (tratados à parte)."""
    tabela = {
        "openai":   {"protocolo": "openai", "url": OPENAI_URL, "modelo": OPENAI_MODELO,
                     "chave": OPENAI_API_KEY, "exige_chave": True, "rotulo": "OpenAI"},
        "deepseek": {"protocolo": "openai", "url": DEEPSEEK_URL, "modelo": DEEPSEEK_MODELO,
                     "chave": DEEPSEEK_API_KEY, "exige_chave": True, "rotulo": "DeepSeek"},
        "ollama":   {"protocolo": "openai", "url": OLLAMA_URL, "modelo": OLLAMA_MODELO,
                     "chave": "", "exige_chave": False, "rotulo": "Ollama"},
        "claude":   {"protocolo": "anthropic", "url": CLAUDE_URL, "modelo": CLAUDE_MODELO,
                     "chave": ANTHROPIC_API_KEY, "exige_chave": True, "rotulo": "Claude"},
    }
    return tabela.get(nome, {})


MOTORES = ("gemini", "local", "openai", "deepseek", "ollama", "claude")


def _arq_chaves() -> str:
    # 1) definido pelo instalador (shim exporta HRX_CHAVES)
    if os.environ.get("HRX_CHAVES"):
        return os.environ["HRX_CHAVES"]
    # 2) local padrão de config do usuário (sobrevive a reinstalação)
    cfg = os.path.expanduser("~/.config/hrx/chaves.txt")
    if os.path.exists(cfg):
        return cfg
    # 3) ao lado do código (modo dev)
    return os.path.join(BASE, "chaves.txt")


ARQ_CHAVES = _arq_chaves()   # 1 chave por linha (NUNCA versionar)
TEMPERATURA = 0.3
TIMEOUT = 60          # segundos por request
MAX_ITER = int(os.environ.get("HRX_MAX_ITER", "20"))  # passos do ReAct (código = mais passos)

# --- Contexto da conversa: orçamento (em caracteres) da janela de histórico
# enviada ao modelo a cada turno. Mantém as mensagens mais RECENTES dentro do
# limite pra não estourar o contexto do modelo (o local roda com -c 4096). ---
CONTEXTO_MAX_CHARS = int(os.environ.get("HRX_CONTEXTO_MAX_CHARS", "12000"))

# --- Sandbox de arquivos: o agente só mexe aqui (configurável por env) ---
WORKSPACE = os.environ.get("AGENTE_WORKSPACE", os.path.join(BASE, "workspace"))
DADOS = os.environ.get("AGENTE_DADOS", os.path.join(BASE, "dados"))

# --- Git: opera no diretório de onde o hrx foi chamado (fora da sandbox) ---
REPO = os.environ.get("AGENTE_REPO", os.getcwd())

# --- Memória persistente: fatos/decisões que o agente lembra entre sessões ---
MEMORIA = os.path.join(DADOS, "memoria.json")

# --- Memória no prompt: modo compacto para gastar menos tokens ---
# "compacta" = injeta só um resumo curto; "completa" = lista tudo.
MEMORIA_PROMPT = os.environ.get("HRX_MEMORIA_PROMPT", "compacta").strip().lower()
MEMORIA_PROMPT_MAX_ITENS = int(os.environ.get("HRX_MEMORIA_PROMPT_MAX_ITENS", "8"))
MEMORIA_PROMPT_MAX_CHARS = int(os.environ.get("HRX_MEMORIA_PROMPT_MAX_CHARS", "900"))
MEMORIA_PROMPT_RESUMO_A_PARTIR = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_A_PARTIR", "20"))
MEMORIA_PROMPT_RESUMO_ITENS = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_ITENS", "12"))
MEMORIA_PROMPT_RESUMO_CHARS = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_CHARS", "1200"))

# --- Segurança: aprovação inteligente (🟢🟡🔴) em aprovacao.py ---
# Não é mais uma whitelist que bloqueia: estes executáveis são tratados
# como SEMPRE 🟢 seguros (rodam sem pedir confirmação), somados aos padrões
# de leitura já reconhecidos. Qualquer outro comando é classificado por risco.
COMANDOS_PERMITIDOS = {
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "date", "whoami",
    "hostname", "grep", "find", "head", "tail", "wc",
}
TIMEOUT_COMANDO = 30

# Modo de permissões da sessão (alternável em runtime com /modo):
#   blindado  = pergunta em TUDO (até 🟢)
#   cauteloso = pergunta em 🟡 e 🔴 (padrão)
#   auto      = 🟡 roda direto; só 🔴 pergunta (fluxo ágil p/ tarefas de código)
MODO = os.environ.get("HRX_MODO", "cauteloso").strip().lower()
