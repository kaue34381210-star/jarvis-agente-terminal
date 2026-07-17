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

ARQ_MOTOR = os.path.expanduser(
    os.environ.get("HRX_MOTOR_CFG", "~/.config/hrx/motor.json"))

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


NOME = _pref("AGENTE_NOME", "nome", "HRX CODE")
TOM = str(_pref("AGENTE_TOM", "tom", "direto")).strip().lower()
IDIOMA = str(_pref("AGENTE_IDIOMA", "idioma", "pt-BR")).strip()
PROJETO = str(_pref("AGENTE_PROJETO", "projeto", "")).strip()

MOTOR = str(_cfg("HRX_MOTOR", "motor", "local")).strip().lower()

MODELO = _cfg("GEMINI_MODELO", "gemini_modelo", "gemini-2.0-flash")

LOCAL_URL = _cfg("HRX_LOCAL_URL", "local_url", "http://127.0.0.1:8080/v1/chat/completions")
MODELO_LOCAL = _cfg("HRX_MODELO_LOCAL", "local_modelo", "Qwen2.5-7B-Instruct")
LOCAL_TIMEOUT = int(os.environ.get("HRX_LOCAL_TIMEOUT", "180"))

OPENAI_URL = _cfg("OPENAI_URL", "openai_url", "https://api.openai.com/v1/chat/completions")
OPENAI_MODELO = _cfg("OPENAI_MODELO", "openai_modelo", "gpt-4o-mini")
OPENAI_API_KEY = _cfg("OPENAI_API_KEY", "openai_key", "")

DEEPSEEK_URL = _cfg("DEEPSEEK_URL", "deepseek_url", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODELO = _cfg("DEEPSEEK_MODELO", "deepseek_modelo", "deepseek-chat")
DEEPSEEK_API_KEY = _cfg("DEEPSEEK_API_KEY", "deepseek_key", "")

OLLAMA_URL = _cfg("OLLAMA_URL", "ollama_url", "http://127.0.0.1:11434/v1/chat/completions")
OLLAMA_MODELO = _cfg("OLLAMA_MODELO", "ollama_modelo", "llama3.1")

GROQ_URL = _cfg("GROQ_URL", "groq_url", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODELO = _cfg("GROQ_MODELO", "groq_modelo", "llama-3.3-70b-versatile")
GROQ_API_KEY = _cfg("GROQ_API_KEY", "groq_key", "")

CLAUDE_URL = _cfg("CLAUDE_URL", "claude_url", "https://api.anthropic.com/v1/messages")
CLAUDE_MODELO = _cfg("CLAUDE_MODELO", "claude_modelo", "claude-opus-4-8")
ANTHROPIC_API_KEY = _cfg("ANTHROPIC_API_KEY", "claude_key", "")
CLAUDE_MAX_TOKENS = int(_cfg("CLAUDE_MAX_TOKENS", "claude_max_tokens", "4096"))


def provedor(nome: str) -> dict:
    """Retorna a configuração resolvida de um motor por API."""
    tabela = {
        "openai":   {"protocolo": "openai", "url": OPENAI_URL, "modelo": OPENAI_MODELO,
                     "chave": OPENAI_API_KEY, "exige_chave": True, "rotulo": "OpenAI"},
        "deepseek": {"protocolo": "openai", "url": DEEPSEEK_URL, "modelo": DEEPSEEK_MODELO,
                     "chave": DEEPSEEK_API_KEY, "exige_chave": True, "rotulo": "DeepSeek"},
        "ollama":   {"protocolo": "openai", "url": OLLAMA_URL, "modelo": OLLAMA_MODELO,
                     "chave": "", "exige_chave": False, "rotulo": "Ollama"},
        "groq":     {"protocolo": "openai", "url": GROQ_URL, "modelo": GROQ_MODELO,
                     "chave": GROQ_API_KEY, "exige_chave": True, "rotulo": "Groq"},
        "claude":   {"protocolo": "anthropic", "url": CLAUDE_URL, "modelo": CLAUDE_MODELO,
                     "chave": ANTHROPIC_API_KEY, "exige_chave": True, "rotulo": "Claude"},
    }
    return tabela.get(nome, {})


MOTORES = ("gemini", "local", "openai", "deepseek", "ollama", "groq", "claude")


def _arq_chaves() -> str:
    if os.environ.get("HRX_CHAVES"):
        return os.environ["HRX_CHAVES"]
    cfg = os.path.expanduser("~/.config/hrx/chaves.txt")
    if os.path.exists(cfg):
        return cfg
    return os.path.join(BASE, "chaves.txt")


ARQ_CHAVES = _arq_chaves()
TEMPERATURA = 0.3
TIMEOUT = 60
MAX_ITER = int(os.environ.get("HRX_MAX_ITER", "20"))

CONTEXTO_MAX_CHARS = int(os.environ.get("HRX_CONTEXTO_MAX_CHARS", "12000"))

DIR_CONFIG = os.path.dirname(ARQ_MOTOR) or os.path.expanduser("~/.config/hrx")
WORKSPACE = os.environ.get(
    "AGENTE_WORKSPACE", os.path.join(DIR_CONFIG, "workspace"))
DADOS = os.environ.get("AGENTE_DADOS", os.path.join(DIR_CONFIG, "dados"))

REPO = os.environ.get("AGENTE_REPO", os.getcwd())

MEMORIA = os.path.join(DADOS, "memoria.json")

MEMORIA_PROMPT = str(_cfg(
    "HRX_MEMORIA_PROMPT", "memoria_prompt", "compacta"
)).strip().lower()
MEMORIA_PROMPT_MAX_ITENS = int(os.environ.get("HRX_MEMORIA_PROMPT_MAX_ITENS", "8"))
MEMORIA_PROMPT_MAX_CHARS = int(os.environ.get("HRX_MEMORIA_PROMPT_MAX_CHARS", "900"))
MEMORIA_PROMPT_RESUMO_A_PARTIR = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_A_PARTIR", "20"))
MEMORIA_PROMPT_RESUMO_ITENS = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_ITENS", "12"))
MEMORIA_PROMPT_RESUMO_CHARS = int(os.environ.get("HRX_MEMORIA_PROMPT_RESUMO_CHARS", "1200"))

COMANDOS_PERMITIDOS = {
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "date", "whoami",
    "hostname", "grep", "find", "head", "tail", "wc",
}
TIMEOUT_COMANDO = 30

MODO = os.environ.get("HRX_MODO", "cauteloso").strip().lower()
DRY_RUN = os.environ.get("HRX_DRY_RUN", "").strip().lower() in {
    "1", "true", "sim", "yes", "on",
}
