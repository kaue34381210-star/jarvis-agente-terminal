"""Agente de IA para terminal."""
import json
import sys
import getpass
import importlib
import os

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from . import claude
from . import comandos
from . import config
from . import ferramentas
from . import local
from . import openai_compat
from . import permissao
from .gemini import PoolChaves, carregar_chaves, chamar
from .versao import __version__

console = Console()

SYSTEM = """Você é o HRX CODE, um agente de IA interativo para engenharia de
software no terminal. Você lê, escreve e edita os arquivos do PROJETO do
usuário (o diretório de onde o hrx foi chamado), executa comandos e trabalha
com Git. Responda no idioma configurado e siga o tom do usuário.

ESTILO:
- Seja conciso, direto e específico. Em perguntas simples, prefira 1 a 3 frases.
- Responda primeiro ao pedido atual, sem preâmbulos, conclusões repetitivas ou
  explicações que o usuário não solicitou.
- Quando uma tarefa produzir um resultado, informe o resultado principal e só
  os detalhes necessários para verificá-lo.
- Ao citar código, use caminho:linha sempre que houver números de linha.
- Não use emojis, exceto se o usuário pedir.

AUTONOMIA E ESCOPO:
- Faça exatamente o que foi pedido. Não amplie a tarefa nem altere arquivos
  alheios sem necessidade.
- Para uma ação concreta e segura, avance sem perguntar novamente se o usuário
  quer que você faça. Pergunte somente quando faltar uma decisão indispensável
  que mudaria materialmente o resultado.
- Não invente arquivos, comandos, dependências, APIs, URLs, resultados ou
  capacidades. Use as ferramentas para verificar fatos do projeto.
- Nunca exponha, registre ou inclua segredos, chaves e tokens em código ou Git.

Ferramentas de arquivo (agem no PROJETO real, com números de linha):
- listar_diretorio(caminho, recursivo, respeitar_gitignore=True)  lista arquivos ("." = raiz do projeto); recursivo=True mostra a árvore; false inclui arquivos ignorados, exceto diretórios internos pesados
- buscar_codigo(padrao, caminho, ext, contexto=0, respeitar_gitignore=True)  procura texto/regex nos arquivos; contexto inclui linhas antes/depois; false busca também arquivos ignorados, exceto diretórios internos pesados
- ler_arquivo(caminho, inicio, fim)    lê o arquivo; inicio/fim = intervalo de linhas (1-based), opcional
- escrever_arquivo(caminho, conteudo)  cria/sobrescreve um arquivo; caminhos externos ao projeto exigem confirmação de alto risco
- editar_arquivo(caminho, procurar, substituir, ocorrencia=None, tudo=False)  substitui trecho literal; se houver várias ocorrências, escolha ocorrencia=N (1-based) ou tudo=True
- aplicar_patch(caminho, patch)  aplica hunks de diff unificado com detecção de conflito e escrita atômica
- listar_undo(limite=10)  lista operações recentes disponíveis para desfazer
- desfazer_ultima(caminho=None)  restaura a última mutação (opcionalmente de um caminho); sempre exige confirmação explícita de alto risco

Outras ferramentas:
- criar_planilha(nome, dados, cabecalho)  cria Excel .xlsx (caminhos externos exigem confirmação de alto risco)
- criar_pdf(nome, titulo, conteudo, tabela)  cria PDF (mesma política de caminho)
- rodar_comando(comando)        executa comando no shell (roda no diretório do projeto)
- git(args)                     versiona: git("status"), git("diff"), git("commit -m 'msg'")
- consultar_cve(consulta)       consulta CVEs no NVD por ID (CVE-2021-44228) ou palavra-chave
- buscar_web(url, max_chars)    baixa uma URL pública e devolve o texto em ~markdown (docs, issues, blogs, stack traces)
- memoria_salvar(texto, tipo) / memoria_listar() / memoria_esquecer(alvo)  memória entre sessões
- buscar_docs(consulta)         busca nos documentos do usuário (base de conhecimento, não é o código)

FLUXO DE ENGENHARIA:
- Primeiro entenda o projeto: liste, busque e leia os arquivos relevantes,
  incluindo instruções do repositório, configuração, testes e código vizinho.
- Antes de usar uma biblioteca ou comando, confirme que o projeto já o utiliza
  ou que ele está declarado. Respeite estilo, arquitetura, nomes e padrões
  existentes.
- Leia o arquivo e o contexto dos imports antes de editar. Prefira editar um
  arquivo existente; crie arquivo novo somente quando for necessário ao pedido.
- Não crie documentação espontaneamente e não adicione comentários ao código,
  salvo quando o usuário pedir ou o projeto exigir esse padrão.
- Faça mudanças pequenas, completas e verificáveis. Não deixe implementações
  parciais, marcadores ou erros conhecidos sem informar claramente.
- Depois de editar, confira o diff e execute os testes relevantes. Ao concluir
  uma mudança de código, rode também lint, formatação, typecheck ou build quando
  esses comandos estiverem definidos no projeto. Nunca alegue que passaram sem
  executá-los.

EDIÇÃO DE ARQUIVOS: prefira aplicar_patch para mudanças localizadas ou com mais
de um trecho, usando contexto suficiente para detectar conflitos. Use
editar_arquivo apenas com um trecho 'procurar' literal, copiando a indentação
exata. Se ele não for único, escolha `ocorrencia=N` (1-based) ou `tudo=True`;
não combine as duas opções. Para arquivo novo ou reescrita total, use
escrever_arquivo.
Preserve alterações existentes do usuário e não desfaça mudanças fora do escopo.

GIT: use a ferramenta git para inspecionar e versionar o repositório do projeto.
Você pode consultar status, diff e histórico quando isso ajudar a tarefa. Nunca
faça commit, push, merge, rebase, tag ou descarte alterações sem pedido explícito
do usuário. Antes de um commit solicitado, confira status e diff, preserve
mudanças alheias e escreva uma mensagem descritiva.

SEGURANÇA (somente uso defensivo, educacional ou CTF autorizado): recuse criar,
modificar ou melhorar código destinado a invasão, persistência, evasão, roubo de
credenciais, exfiltração, destruição ou acesso não autorizado. Você pode analisar
vulnerabilidades, logs e malware de forma defensiva; consultar CVEs; produzir
regras de detecção YARA/Sigma; fortalecer sistemas; e executar scans em alvos
próprios, explicitamente autorizados ou de laboratório/CTF. Se um alvo externo
não tiver autorização clara, pergunte antes de testar. Ao recusar, seja breve e,
quando possível, ofereça uma alternativa defensiva segura.

MEMÓRIA: quando o usuário pedir para "lembrar/guardar/anotar" algo, ou revelar
uma preferência estável (gestor de pacotes, comando de deploy, decisão de projeto),
use memoria_salvar. As memórias já conhecidas chegam no início desta conversa —
use-as e respeite-as; não pergunte o que já está lá.

APROVAÇÃO: os comandos passam por um filtro de risco (🟢 seguro roda direto,
🟡 pede confirmação, 🔴 exige 'sim' explícito). Se o usuário RECUSAR um comando,
NÃO insista: proponha uma alternativa mais segura ou explique o que faria.

PROTOCOLO (obrigatório): responda SEMPRE com UM único objeto JSON, nada fora dele.
- Para usar ferramenta:
  {"pensamento": "...", "ferramenta": "nome", "args": {...}}
- Para responder ao usuário:
  {"pensamento": "...", "resposta": "texto (pode usar markdown)"}

Use apenas nomes de ferramentas e argumentos descritos acima. Nunca invente
resultado de ferramenta. Use uma ferramenta por vez e continue até concluir a
tarefa ou encontrar um bloqueio real."""

LOGO = r"""
     ██╗  ██╗██████╗ ██╗  ██╗
     ██║  ██║██╔══██╗╚██╗██╔╝
     ███████║██████╔╝ ╚███╔╝
     ██╔══██║██╔══██╗ ██╔██╗
     ██║  ██║██║  ██║██╔╝ ██╗
     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
      ██████╗ ██████╗ ██████╗ ███████╗
     ██╔════╝██╔═══██╗██╔══██╗██╔════╝
     ██║     ██║   ██║██║  ██║█████╗
     ██║     ██║   ██║██║  ██║██╔══╝
     ╚██████╗╚██████╔╝██████╔╝███████╗
      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝"""


def banner(rotulo_motor: str, n_memorias: int = 0) -> None:
    console.print(Text(LOGO, style="bold gold1"))
    console.print(
        "  [bold gold1]HRX CODE[/]"
        "   [dim italic]— agente de IA no terminal.[/]")
    mem = f"[cyan]{n_memorias}[/cyan] memória(s)" if n_memorias else "sem memória salva"
    projeto = getattr(config, "PROJETO", "") or "projeto não definido"
    linhas = [
        f"[dim]motor[/dim] [bold]{rotulo_motor}[/bold]",
        f"[dim]perfil[/dim] [bold]{getattr(config, 'NOME', 'HRX CODE')}[/bold] · [dim]{projeto}[/dim]",
        f"[dim]memória[/dim] [bold]{mem}[/bold]",
    ]
    console.print(Panel(
        "\n".join(linhas),
        border_style="gold1",
        padding=(0, 2),
        title="[bold]status[/bold]",
        subtitle="[dim]digite /ajuda para ver os comandos[/dim]",
    ))
    console.print(Rule(style="grey30"))


REFORCO_LOCAL = """
MODO LOCAL (modelo pequeno) — REGRA CRÍTICA sobre ferramentas:
Quando o usuário pede uma AÇÃO concreta (criar planilha, criar PDF, ler/escrever
arquivo, listar pasta, rodar comando etc.), VOCÊ NÃO PERGUNTA "confirma?" nem
"quer que eu faça?". Emita IMEDIATAMENTE o JSON da ferramenta no MESMO turno,
com os args preenchidos com valores razoáveis (se faltar detalhe, use um nome
de arquivo curto e dados de exemplo — o usuário corrige depois).
NÃO responda em prosa quando a intenção do usuário é uma AÇÃO — responda com
UM objeto JSON só: {"pensamento": "...", "ferramenta": "nome", "args": {...}}.
"""


def _montar_system(consulta: str = "") -> str:
    """SYSTEM + memórias persistentes injetadas no contexto."""
    preferencias = []
    if getattr(config, "NOME", ""):
        preferencias.append(f"- nome: {config.NOME}")
    if getattr(config, "TOM", ""):
        preferencias.append(f"- tom: {config.TOM}")
    if getattr(config, "IDIOMA", ""):
        preferencias.append(f"- idioma: {config.IDIOMA}")
    if getattr(config, "PROJETO", ""):
        preferencias.append(f"- projeto: {config.PROJETO}")
    bloco_pref = "\n".join(preferencias)
    memorias = ferramentas.memoria_contexto(consulta=consulta)
    base = SYSTEM
    if str(getattr(config, "MOTOR", "")).lower() == "local":
        base += "\n" + REFORCO_LOCAL
    if bloco_pref:
        base += "\n\nPREFERÊNCIAS DO AGENTE:\n" + bloco_pref
    if not memorias or memorias == "(nenhuma memória guardada)":
        return base
    return (base + "\n\nMEMÓRIA (o que você já sabe deste usuário/ambiente — "
            "use e respeite):\n" + memorias)


def extrair_json(texto: str):
    t = texto.strip()
    if "```" in t:
        for parte in t.split("```"):
            p = parte.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                try:
                    return json.loads(p)
                except json.JSONDecodeError:
                    pass
    inicio = t.find("{")
    if inicio != -1:
        for fim in range(len(t), inicio, -1):
            try:
                return json.loads(t[inicio:fim])
            except json.JSONDecodeError:
                continue
    return None


def _aviso_rotacao(idx: int, espera: float) -> None:
    console.print(f"  [yellow]⇄ chave #{idx + 1} atingiu o limite — trocando "
                  f"(reset em ~{int(espera)}s)[/yellow]")


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={str(v)[:40]!r}" for k, v in (args or {}).items())


def _perguntar(prompt: str) -> str:
    """Lê confirmação do usuário. Sem terminal interativo → trata como recusa."""
    try:
        return console.input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _ler_segredo(prompt: str) -> str:
    """Lê uma chave sem mostrá-la no terminal; Ctrl+C cancela."""
    try:
        return getpass.getpass(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _aprovar_comando(pol: permissao.Politica, comando: str,
                     ferramenta: str = None, args: dict = None):
    """Aplica o gate interativo da política da sessão."""
    nivel, motivo = pol.classificar(comando, ferramenta=ferramenta, args=args)

    if nivel == "verde":
        console.print(f"  [green]🟢 seguro[/green] [dim]— {motivo}[/dim]")
        return True, None

    if nivel == "amarelo":
        console.print(f"  [yellow]🟡 confirmação[/yellow] [dim]— {motivo}[/dim]")
        r = _perguntar("  [yellow]executar?[/yellow] "
                       "[dim][Enter=sim · n=não · s=sempre][/dim] › ").lower()
        if r in ("s", "sempre", "a", "always"):
            assi = pol.liberar_sempre(comando)
            console.print(f"  [dim]⭐ '{assi}' liberado pra sessão inteira.[/dim]")
            ok = True
        else:
            ok = r not in ("n", "nao", "não", "no", "cancelar")
    else:  # vermelho
        console.print(f"  [red]🔴 ALTO RISCO[/red] [bold red]— {motivo}[/bold red]")
        ok = _perguntar("  [red]para executar digite[/red] [bold]sim[/bold] › ") \
            .lower() == "sim"

    if not ok:
        console.print("  [dim]✋ execução cancelada pelo usuário.[/dim]")
        return False, ("Usuário RECUSOU a execução deste comando. "
                       "Não execute. Proponha uma alternativa mais segura "
                       "ou explique o que o comando faria.")
    return True, None


def _simular_comando(pol: permissao.Politica, nome: str, comando: str,
                     args: dict = None) -> str:
    nivel, motivo = pol.classificar(comando, ferramenta=nome, args=args)
    console.print(
        f"  [cyan]◌ dry-run[/cyan] [dim]— {nivel}: {motivo}; não executado[/dim]"
    )
    return (
        f"DRY-RUN: a ferramenta {nome} não foi executada. "
        f"Classificação prevista: {nivel} ({motivo})."
    )


def _janela(historico: list) -> list:
    """Mantém as mensagens recentes dentro do orçamento de contexto."""
    orcamento = config.CONTEXTO_MAX_CHARS
    total, mantidos = 0, []
    for m in reversed(historico):
        total += len(m.get("content", ""))
        if total > orcamento and mantidos:
            break
        mantidos.append(m)
    return list(reversed(mantidos))


def _resumir_conversa(motor_chamar, historico: list, limite_turnos: int = 12) -> str:
    """Pede ao motor atual um resumo curto e factual da conversa recente."""
    if not historico:
        return "(não há conversa para resumir)"

    trecho = _janela(historico[-max(2, limite_turnos):])
    mensagens = [
        {
            "role": "system",
            "content": (
                "Resuma a conversa de forma curta, objetiva e factual. "
                "Não invente nada. Destaque objetivo atual, decisões, pendências, "
                "erros importantes e próximos passos. Responda em português, "
                "de preferência em tópicos."
            ),
        },
        {
            "role": "user",
            "content": (
                "Resuma o trecho abaixo:\n\n"
                + "\n".join(
                    f"{m.get('role', '?')}: {m.get('content', '')}"
                    for m in trecho
                )
            ),
        },
    ]
    texto = motor_chamar(mensagens)
    return texto.strip() or "(resumo vazio)"


def _debug_estado(pool, pol: permissao.Politica, historico: list) -> str:
    """Monta um snapshot legível do estado atual do agente."""
    memoria = ferramentas.carregar_memorias()
    p = None if config.MOTOR in ("gemini", "local") else config.provedor(config.MOTOR)
    if config.MOTOR == "gemini":
        motor = f"gemini · {config.MODELO} · {pool.n if pool else 0} chave(s)"
    elif config.MOTOR == "local":
        estado = "no ar" if local.disponivel() else "fora do ar"
        motor = f"local · {config.MODELO_LOCAL} · {config.LOCAL_URL} ({estado})"
    elif p:
        chave = "ok" if p.get("chave") else "ausente"
        motor = f"{config.MOTOR} · {p.get('modelo', '?')} · chave {chave}"
    else:
        motor = config.MOTOR

    ultima = historico[-1]["content"] if historico else "(sem mensagens)"
    ultima = ultima.replace("\n", " ")
    if len(ultima) > 120:
        ultima = ultima[:117] + "..."

    linhas = [
        f"motor: {motor}",
        f"config: {config.ARQ_MOTOR}",
        f"perfil: {config.ARQ_PERFIL}",
        f"nome: {getattr(config, 'NOME', '?')}",
        f"tom: {getattr(config, 'TOM', '?')}",
        f"idioma: {getattr(config, 'IDIOMA', '?')}",
        f"projeto: {getattr(config, 'PROJETO', '') or '(vazio)'}",
        f"modo de permissões: {pol.modo}",
        f"dry-run: {'ativado' if pol.dry_run else 'desativado'}",
        f"sempre permitidos: {len(pol.sempre)}",
        f"mensagens na conversa: {len(historico)}",
        f"memórias salvas: {len(memoria)}",
        f"última mensagem: {ultima}",
    ]
    return "\n".join(linhas)


def rodar(motor_chamar, pol: permissao.Politica, historico: list, pergunta: str) -> str:
    """Executa um turno e atualiza o histórico da conversa."""
    historico.append({"role": "user", "content": pergunta})
    for _ in range(config.MAX_ITER):
        contexto = "\n".join(m.get("content", "") for m in historico[-6:])
        system_msg = {"role": "system", "content": _montar_system(consulta=contexto)}
        mensagens = [system_msg] + _janela(historico)
        with console.status("[cyan]pensando...", spinner="dots"):
            texto = motor_chamar(mensagens)
        historico.append({"role": "assistant", "content": texto})
        acao = extrair_json(texto)
        if acao is None:
            return texto
        if "resposta" in acao:
            return str(acao["resposta"])
        nome = acao.get("ferramenta")
        if not nome:
            return texto
        args = acao.get("args", {})
        console.print(f"  [grey50]⚙ {nome}([/grey50][grey62]{_fmt_args(args)}[/grey62][grey50])[/grey50]")
        if permissao.exige_aprovacao(nome):
            comando = permissao.comando_de(nome, args)
            if pol.dry_run:
                resultado = _simular_comando(pol, nome, comando, args)
            else:
                permitido, bloqueio = _aprovar_comando(
                    pol, comando, ferramenta=nome, args=args)
                if permitido:
                    pol.liberar(comando)
                    resultado = ferramentas.executar(nome, args)
                else:
                    resultado = bloqueio
        else:
            resultado = ferramentas.executar(nome, args)
        historico.append({"role": "user",
                          "content": f"RESULTADO da ferramenta {nome}:\n{resultado}"})
    return "Parei: atingi o limite de passos sem resposta final."


def _configurar_motor() -> None:
    """Assistente interativo de configuração persistente dos motores."""
    opcoes = {
        "1": ("gemini", "Gemini"), "2": ("openai", "ChatGPT / OpenAI"),
        "3": ("deepseek", "DeepSeek"), "4": ("claude", "Claude"),
        "5": ("groq", "Groq (Llama 3.3 70B — free tier grande)"),
        "6": ("ollama", "Ollama local"), "7": ("local", "Llamafile / Qwen local"),
    }
    console.print(Panel(
        "[cyan]1[/cyan] Gemini\n[cyan]2[/cyan] ChatGPT / OpenAI\n"
        "[cyan]3[/cyan] DeepSeek\n[cyan]4[/cyan] Claude\n"
        "[cyan]5[/cyan] Groq (Llama 3.3 70B — free tier grande)\n"
        "[cyan]6[/cyan] Ollama local\n[cyan]7[/cyan] Llamafile / Qwen local",
        title="⚙ configurar motor", border_style="cyan", padding=(0, 2)))
    escolha = _perguntar("  escolha [1-7] (Enter cancela) › ")
    if escolha not in opcoes:
        console.print("  [dim]configuração cancelada.[/dim]")
        return

    motor, rotulo = opcoes[escolha]
    dados = {
        "motor": motor,
    }
    if motor == "local":
        dados["local_url"] = getattr(config, "LOCAL_URL", "http://127.0.0.1:8080/v1/chat/completions")
        dados["local_modelo"] = getattr(config, "MODELO_LOCAL", "Qwen2.5-7B-Instruct")
    elif motor == "gemini":
        dados["gemini_modelo"] = getattr(config, "MODELO", "gemini-2.0-flash")
    elif motor == "openai":
        atual = config.provedor(motor)
        dados["openai_url"] = atual.get("url", "https://api.openai.com/v1/chat/completions")
        dados["openai_modelo"] = atual.get("modelo", "gpt-4o-mini")
    elif motor == "deepseek":
        atual = config.provedor(motor)
        dados["deepseek_url"] = atual.get("url", "https://api.deepseek.com/v1/chat/completions")
        dados["deepseek_modelo"] = atual.get("modelo", "deepseek-chat")
    elif motor == "claude":
        atual = config.provedor(motor)
        dados["claude_url"] = atual.get("url", "https://api.anthropic.com/v1/messages")
        dados["claude_modelo"] = atual.get("modelo", "claude-opus-4-8")
    elif motor == "ollama":
        atual = config.provedor(motor)
        dados["ollama_url"] = atual.get("url", "http://127.0.0.1:11434/v1/chat/completions")
        dados["ollama_modelo"] = atual.get("modelo", "llama3.1")
    elif motor == "groq":
        atual = config.provedor(motor)
        dados["groq_url"] = atual.get("url", "https://api.groq.com/openai/v1/chat/completions")
        dados["groq_modelo"] = atual.get("modelo", "llama-3.3-70b-versatile")
    campos = {
        "openai": ("openai", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
        "deepseek": ("deepseek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
        "claude": ("claude", "https://api.anthropic.com/v1/messages", "claude-opus-4-8"),
        "ollama": ("ollama", "http://127.0.0.1:11434/v1/chat/completions", "llama3.1"),
        "groq": ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    }
    if motor == "gemini":
        chave = _ler_segredo("  chave Gemini (Enter mantém as chaves atuais) › ")
        if chave:
            pasta = os.path.dirname(config.ARQ_CHAVES)
            if pasta:
                os.makedirs(pasta, exist_ok=True)
            with open(config.ARQ_CHAVES, "a", encoding="utf-8") as f:
                f.write(chave + "\n")
            try:
                os.chmod(config.ARQ_CHAVES, 0o600)
            except OSError:
                pass
        modelo = _perguntar(f"  modelo Gemini [{config.MODELO}] › ")
        if modelo:
            dados["gemini_modelo"] = modelo
    elif motor == "local":
        url = _perguntar(f"  URL [{config.LOCAL_URL}] › ") or config.LOCAL_URL
        modelo = _perguntar(f"  modelo [{config.MODELO_LOCAL}] › ") or config.MODELO_LOCAL
        if not url.startswith(("http://", "https://")):
            console.print("  [red]URL inválida[/red] — use http:// ou https://")
            return
        if not modelo.strip():
            console.print("  [red]modelo inválido[/red] — informe um nome de modelo.")
            return
        dados.update({"local_url": url, "local_modelo": modelo})
    else:
        prefixo, url_padrao, modelo_padrao = campos[motor]
        atual = config.provedor(motor)
        url = _perguntar(f"  URL [{atual.get('url', url_padrao)}] › ") or atual.get("url", url_padrao)
        modelo = _perguntar(f"  modelo [{atual.get('modelo', modelo_padrao)}] › ") or atual.get("modelo", modelo_padrao)
        chave = "" if motor == "ollama" else _ler_segredo("  chave API (Enter mantém a atual) › ")
        if not url.startswith(("http://", "https://")):
            console.print("  [red]URL inválida[/red] — use http:// ou https://")
            return
        if not modelo.strip():
            console.print("  [red]modelo inválido[/red] — informe um nome de modelo.")
            return
        dados[f"{prefixo}_url"] = url
        dados[f"{prefixo}_modelo"] = modelo
        if chave:
            dados[f"{prefixo}_key"] = chave

    config.salvar_motor(dados)
    importlib.reload(config)
    console.print(f"  [green]✓[/green] {rotulo} configurado e salvo em [dim]{config.ARQ_MOTOR}[/dim].")


def _mostrar_perfil() -> None:
    dados = [
        f"nome: [cyan]{getattr(config, 'NOME', 'HRX CODE')}[/cyan]",
        f"tom: [cyan]{getattr(config, 'TOM', 'direto')}[/cyan]",
        f"idioma: [cyan]{getattr(config, 'IDIOMA', 'pt-BR')}[/cyan]",
        f"projeto: [cyan]{getattr(config, 'PROJETO', '') or '(vazio)'}[/cyan]",
        f"arquivo: [dim]{getattr(config, 'ARQ_PERFIL', '?')}[/dim]",
    ]
    console.print(Panel("\n".join(dados), title="perfil do agente",
                        border_style="grey37", padding=(0, 2)))


def _editar_perfil() -> None:
    atual = {
        "nome": getattr(config, "NOME", "HRX CODE"),
        "tom": getattr(config, "TOM", "direto"),
        "idioma": getattr(config, "IDIOMA", "pt-BR"),
        "projeto": getattr(config, "PROJETO", ""),
    }
    console.print(Panel(
        "[cyan]1[/cyan] nome do agente\n"
        "[cyan]2[/cyan] tom de resposta\n"
        "[cyan]3[/cyan] idioma padrão\n"
        "[cyan]4[/cyan] projeto atual",
        title="⚙ perfil do agente", border_style="cyan", padding=(0, 2)))
    nome = _perguntar(f"  nome [{atual['nome']}] › ") or atual["nome"]
    tom = _perguntar(f"  tom [{atual['tom']}] › ") or atual["tom"]
    idioma = _perguntar(f"  idioma [{atual['idioma']}] › ") or atual["idioma"]
    projeto = _perguntar(f"  projeto [{atual['projeto'] or '(vazio)'}] › ") or atual["projeto"]

    dados = dict(getattr(config, "_PERFIL", {}))
    dados.update({
        "nome": nome.strip(),
        "tom": tom.strip().lower(),
        "idioma": idioma.strip(),
        "projeto": projeto.strip(),
    })
    config.salvar_perfil(dados)
    importlib.reload(config)
    console.print(f"  [green]✓[/green] perfil salvo em [dim]{config.ARQ_PERFIL}[/dim].")


def _comando_especial(motor_chamar, pool, pol: permissao.Politica, historico: list,
                      entrada: str) -> bool:
    """Trata comandos internos e informa se consumiu a entrada."""
    cmd = entrada.lower()
    partes = cmd.split()
    if cmd in ("/sair", "sair", "exit", "quit", "/quit"):
        console.print("[dim]até mais 👋[/dim]")
        raise SystemExit(0)
    if partes and partes[0] == "/undo":
        originais = entrada.strip().split(maxsplit=1)
        caminho = originais[1].strip() if len(originais) > 1 else None
        nome = "desfazer_ultima"
        args = {"caminho": caminho} if caminho else {}
        comando = permissao.comando_de(nome, args)
        if pol.dry_run:
            resultado = _simular_comando(pol, nome, comando, args)
        else:
            permitido, bloqueio = _aprovar_comando(
                pol, comando, ferramenta=nome, args=args
            )
            if permitido:
                pol.liberar(comando)
                resultado = ferramentas.executar(nome, args)
            else:
                resultado = bloqueio
        if resultado:
            console.print(f"  {resultado}")
        return True
    if cmd in ("/ajuda", "/help"):
        console.print(Panel(
            "[cyan]/motor[/cyan]       mostra qual motor está em uso\n"
            "[cyan]/config[/cyan]      escolhe e configura o motor de IA\n"
            "[cyan]/perfil[/cyan]      mostra/edita nome, tom, idioma e projeto\n"
            "[cyan]/chaves[/cyan]      status das chaves (só motor gemini)\n"
            "[cyan]/debug[/cyan]       mostra o estado interno do agente\n"
            "[cyan]/resumo[/cyan]      resume a conversa atual\n"
            "[cyan]/modo[/cyan] [dim]<m>[/dim]   permissões: [dim]blindado · cauteloso · auto[/dim]\n"
            "[cyan]/dry-run[/cyan] [dim]<on|off>[/dim] simula ferramentas sensíveis\n"
            "[cyan]/undo[/cyan] [dim][caminho][/dim] desfaz a última mutação (alto risco)\n"
            "[cyan]/permissoes[/cyan]  mostra modo e a lista 'sempre permitir'\n"
            "[cyan]/memoria[/cyan]     mostra o que o HRX CODE já lembra\n"
            "[cyan]/memoria modo[/cyan] mostra/troca o modo da memória\n"
            "[cyan]/memoria compacta[/cyan] mostra a memória compacta\n"
            "[cyan]/memoria resumir[/cyan] atualiza o resumo da memória\n"
            "[cyan]/memoria limpar[/cyan] limpa memória e resumo\n"
            "[cyan]/novo[/cyan]        começa uma conversa nova (esquece o contexto)\n"
            "[cyan]/comandos[/cyan]    lista seus comandos customizados (~/.config/hrx/comandos)\n"
            "[cyan]/limpar[/cyan]      limpa a tela\n"
            "[cyan]/sair[/cyan]        encerra\n\n"
            "[dim]Motor local: use [/dim][cyan]./iniciar-qwen.sh[/cyan][dim] e, se preciso, [/dim]"
            "[cyan]HRX_LLAMAFILE[/cyan][dim] / [/dim][cyan]HRX_MODELO_GGUF[/cyan][dim].[/dim]",
            title="comandos", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/config":
        _configurar_motor()
        console.print("  [dim]A nova configuração foi salva. Reinicie o HRX CODE para aplicar.[/dim]")
        return True
    if cmd == "/perfil":
        _mostrar_perfil()
        return True
    if partes and partes[0] == "/perfil" and len(partes) > 1 and partes[1] in ("editar", "set", "ajustar"):
        _editar_perfil()
        return True
    if cmd == "/debug":
        console.print(Panel(
            _debug_estado(pool, pol, historico),
            title="debug", border_style="grey37", padding=(0, 2)))
        return True
    if partes and partes[0] == "/resumo":
        limite = 12
        if len(partes) > 1 and partes[1].isdigit():
            limite = max(2, min(24, int(partes[1])))
        resumo = _resumir_conversa(motor_chamar, historico, limite_turnos=limite)
        console.print(Panel(
            resumo,
            title=f"resumo da conversa (últimos {limite} turnos)",
            border_style="grey37",
            padding=(0, 2)))
        return True
    if cmd in ("/novo", "/reset"):
        historico.clear()
        console.print("  [dim]🧹 conversa reiniciada — contexto anterior esquecido.[/dim]")
        return True
    if partes and partes[0] == "/modo":
        if len(partes) > 1:
            novo = partes[1]
            if novo in permissao.MODOS:
                pol.modo = novo
                console.print(f"  [green]✓[/green] modo de permissões: [cyan]{novo}[/cyan]")
            else:
                console.print(f"  [red]modo inválido[/red] — use: "
                              f"{' · '.join(permissao.MODOS)}")
        else:
            console.print(f"  modo atual: [cyan]{pol.modo}[/cyan]  "
                          f"[dim]({' · '.join(permissao.MODOS)})[/dim]")
            console.print("  [dim]blindado=pergunta tudo · cauteloso=🟡🔴 · "
                          "auto=só 🔴[/dim]")
        return True
    if partes and partes[0] in ("/dry-run", "/dryrun", "/simular"):
        if len(partes) == 1:
            estado = "ativado" if pol.dry_run else "desativado"
            console.print(f"  dry-run: [cyan]{estado}[/cyan]")
            return True
        valor = partes[1]
        if valor in ("on", "1", "sim", "yes", "ativar", "ativado"):
            pol.dry_run = True
            console.print("  [green]✓[/green] dry-run [cyan]ativado[/cyan]")
        elif valor in ("off", "0", "nao", "não", "no", "desativar", "desativado"):
            pol.dry_run = False
            console.print("  [green]✓[/green] dry-run [cyan]desativado[/cyan]")
        else:
            console.print("  [red]valor inválido[/red] — use: /dry-run on|off")
        return True
    if cmd in ("/permissoes", "/permissões", "/perm"):
        sempre = ", ".join(sorted(pol.sempre)) if pol.sempre else "(nenhum)"
        dry_run = "ativado" if pol.dry_run else "desativado"
        console.print(Panel(
            f"modo: [cyan]{pol.modo}[/cyan]\n"
            f"dry-run: [cyan]{dry_run}[/cyan]\n"
            f"sempre permitir: [green]{sempre}[/green]",
            title="🔐 permissões", border_style="grey37", padding=(0, 2)))
        return True
    if partes and partes[0] in ("/memoria", "/memorias"):
        if partes and len(partes) > 1 and partes[1] == "modo":
            if len(partes) == 2:
                atual = getattr(config, "MEMORIA_PROMPT", "compacta")
                console.print(f"  modo atual: [cyan]{atual}[/cyan]  "
                              f"[dim](compacta · completa)[/dim]")
                return True
            if len(partes) < 3:
                console.print("  [red]faltou o modo[/red] — use: "
                              "[cyan]/memoria modo compacta[/cyan] ou "
                              "[cyan]/memoria modo completa[/cyan]")
                return True
            novo = partes[2]
            if novo in ("compacta", "completa"):
                dados = dict(config._CFG)
                dados["memoria_prompt"] = novo
                config.salvar_motor(dados)
                importlib.reload(config)
                console.print(f"  [green]✓[/green] memória no prompt: [cyan]{novo}[/cyan]")
            else:
                console.print("  [red]modo inválido[/red] — use: compacta · completa")
            return True
        if partes and len(partes) > 1 and partes[1] == "compacta":
            console.print(Panel(ferramentas.memoria_contexto(),
                                title="🧠 memória compacta", border_style="grey37", padding=(0, 2)))
            return True
        if partes and len(partes) > 1 and partes[1] == "limpar":
            console.print(ferramentas.memoria_limpar())
            return True
        if partes and len(partes) > 1 and partes[1] == "resumir":
            console.print(Panel(ferramentas.memoria_resumir(),
                                title="🧠 resumo da memória", border_style="grey37", padding=(0, 2)))
            return True
        if partes and len(partes) > 2 and partes[1] == "listar" and partes[2] == "compacta":
            console.print(Panel(ferramentas.memoria_contexto(),
                                title="🧠 memória compacta", border_style="grey37", padding=(0, 2)))
            return True
        console.print(Panel(ferramentas.memoria_listar(),
                            title="🧠 memória", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/motor":
        linhas = []
        if config.MOTOR == "local":
            estado = "[green]no ar[/green]" if local.disponivel() else "[red]fora do ar[/red]"
            linhas = [
                "[bold]motor[/bold] [cyan]local[/cyan]",
                f"[bold]modelo[/bold] {config.MODELO_LOCAL}",
                f"[bold]endpoint[/bold] {config.LOCAL_URL}",
                f"[bold]estado[/bold] {estado}",
            ]
        elif config.MOTOR == "gemini":
            linhas = [
                "[bold]motor[/bold] [cyan]gemini[/cyan]",
                f"[bold]modelo[/bold] {config.MODELO}",
                f"[bold]chaves[/bold] {pool.n if pool else 0}",
            ]
        else:
            p = config.provedor(config.MOTOR)
            tem = "[green]chave ok[/green]" if p.get("chave") else \
                ("[dim]sem chave[/dim]" if p.get("exige_chave") else "[dim]local[/dim]")
            linhas = [
                f"[bold]motor[/bold] [cyan]{config.MOTOR}[/cyan]",
                f"[bold]modelo[/bold] {p.get('modelo', '?')}",
                f"[bold]estado[/bold] {tem}",
            ]
        console.print(Panel("\n".join(linhas), title="motor ativo", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/chaves":
        if pool is None:
            console.print("  [dim]motor local — sem chaves.[/dim]")
            return True
        for i, seg in enumerate(pool.status()):
            estado = "[green]livre[/green]" if seg == 0 else f"[yellow]castigo {seg}s[/yellow]"
            console.print(f"  chave #{i + 1}: {estado}")
        return True
    if cmd == "/limpar":
        console.clear()
        return True
    if partes and partes[0] == "/comandos":
        if len(partes) > 1 and partes[1] in ("recarregar", "reload", "atualizar"):
            comandos.recarregar()
            console.print(f"  [green]✓[/green] comandos recarregados de "
                          f"[dim]{comandos.dir_comandos()}[/dim]")
            return True
        mapa = comandos.carregar()
        if not mapa:
            console.print(Panel(
                f"Nenhum comando customizado.\n\n"
                f"Crie arquivos [cyan].md[/cyan] em "
                f"[dim]{comandos.dir_comandos()}[/dim] — o nome do arquivo vira "
                f"o comando. Ex.: [cyan]revisar.md[/cyan] → [cyan]/revisar[/cyan].",
                title="comandos customizados", border_style="grey37",
                padding=(0, 2)))
            return True
        linhas = []
        for nome, dados in sorted(mapa.items()):
            desc = dados.get("descricao") or "[dim](sem descrição)[/dim]"
            linhas.append(f"[cyan]{nome}[/cyan]  {desc}")
        console.print(Panel(
            "\n".join(linhas) + f"\n\n[dim]pasta: {comandos.dir_comandos()}[/dim]\n"
            "[dim]atualize com [/dim][cyan]/comandos recarregar[/cyan]",
            title="comandos customizados", border_style="grey37", padding=(0, 2)))
        return True
    return False


def _erro_sem_chave(rotulo: str) -> None:
    console.print(Panel(
        f"O motor [bold]{rotulo}[/bold] precisa de uma chave de API e nenhuma "
        f"foi encontrada.\n\nConfigure com [cyan]/config[/cyan] (ou defina a "
        f"variável de ambiente correspondente).",
        title="[red]sem chave", border_style="red"))
    if sys.stdin.isatty():
        resposta = _perguntar("  configurar agora? [Enter=sim · n=não] › ").lower()
        if resposta not in ("n", "nao", "não", "no", "cancelar"):
            _configurar_motor()
            console.print("  [dim]Abra o HRX CODE novamente para usar o motor escolhido.[/dim]")
    sys.exit(1)


def _preparar_motor():
    """Monta a função de chamada, o pool e o rótulo do motor configurado."""
    if config.MOTOR not in config.MOTORES:
        raise RuntimeError(
            "HRX_MOTOR inválido: " + repr(config.MOTOR) +
            ". Use um de: " + " · ".join(config.MOTORES) + ".")

    if config.MOTOR == "local":
        online = local.disponivel()
        estado = "[green]no ar[/green]" if online else "[red]fora do ar — suba o servidor[/red]"
        rotulo = f"motor local · {config.MODELO_LOCAL} ({estado})"
        if not online:
            console.print(Panel(
                f"O modelo local não respondeu em [bold]{config.LOCAL_URL}[/bold].\n\n"
                f"Suba o servidor numa outra aba:\n[cyan]{local.DICA_SERVIDOR}[/cyan]",
                title="[yellow]motor local fora do ar", border_style="yellow"))
        return (lambda msgs: local.chamar(msgs)[0]), None, rotulo

    if config.MOTOR in ("openai", "deepseek", "ollama", "groq", "claude"):
        p = config.provedor(config.MOTOR)
        if p["exige_chave"] and not p["chave"]:
            _erro_sem_chave(p["rotulo"])
        if p["protocolo"] == "anthropic":
            fn = (lambda msgs, p=p: claude.chamar(msgs, p["chave"], p["modelo"])[0])
        else:
            fn = (lambda msgs, p=p: openai_compat.chamar(
                msgs, p["url"], p["modelo"], p["chave"] or None)[0])
        return fn, None, f"motor {p['rotulo']} · {p['modelo']}"

    chaves = carregar_chaves()
    if not chaves:
        console.print(Panel(
            "Nenhuma chave encontrada.\n\n"
            "Crie o arquivo [bold]chaves.txt[/bold] (uma chave por linha), defina "
            "[bold]GEMINI_API_KEY[/bold], ou use o motor local com "
            "[bold]HRX_MOTOR=local[/bold].",
            title="[red]sem chaves", border_style="red"))
        sys.exit(1)
    pool = PoolChaves(chaves)
    return (lambda msgs: chamar(pool, msgs, on_rotacao=_aviso_rotacao)[0]), pool, \
        f"motor gemini · {config.MODELO} · {len(chaves)} chave(s)"


def main() -> None:
    args_cli = sys.argv[1:]
    if args_cli == ["--version"]:
        console.print(f"HRX CODE {__version__}")
        return
    if args_cli and args_cli[0] in ("-h", "--help"):
        console.print(
            "HRX CODE — agente de IA no terminal\n\n"
            "Uso:\n"
            "  hrx                 abre o chat interativo\n"
            "  hrx \"tarefa\"       executa uma tarefa única\n"
            "  hrx --version       mostra a versão instalada\n"
            "  hrx --help          mostra esta ajuda"
        )
        return

    motor_chamar, pool, rotulo = _preparar_motor()
    banner(rotulo, len(ferramentas.carregar_memorias()))

    pol = permissao.Politica(
        modo=getattr(config, "MODO", "cauteloso"),
        seguros_extra=getattr(config, "COMANDOS_PERMITIDOS", ()),
        dry_run=getattr(config, "DRY_RUN", False),
    )
    permissao.usar(pol)

    historico: list = []

    arg = " ".join(sys.argv[1:]).strip()
    if arg:
        expandido = comandos.expandir(arg)
        if expandido is not None:
            arg = expandido
        try:
            resposta = rodar(motor_chamar, pol, historico, arg)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]erro:[/red] {e}")
            sys.exit(1)
        console.print(Panel(Markdown(resposta),
                            title=f"[green]{config.NOME}", border_style="green", padding=(1, 2)))
        return

    while True:
        try:
            console.print()
            entrada = console.input("[bold cyan]você[/bold cyan] [cyan]›[/cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]até mais 👋[/dim]")
            break
        if not entrada:
            continue
        try:
            if _comando_especial(motor_chamar, pool, pol, historico, entrada):
                continue
            expandido = comandos.expandir(entrada)
            if expandido is not None:
                console.print(f"  [grey50]▸ expandindo[/grey50] [cyan]"
                              f"{entrada.split()[0]}[/cyan]")
                entrada = expandido
            resposta = rodar(motor_chamar, pol, historico, entrada)
            console.print()
            console.print(Panel(Markdown(resposta),
                                title=f"[green]{config.NOME}", border_style="green", padding=(1, 2)))
        except SystemExit:
            break
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]erro:[/red] {e}")


if __name__ == "__main__":
    main()
