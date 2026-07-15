"""Agente de terminal com motor Gemini e failover de chaves."""
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

import claude
import config
import ferramentas
import local
import openai_compat
import permissao
from gemini import PoolChaves, carregar_chaves, chamar

console = Console()

SYSTEM = """Você é um agente de IA de terminal que também é um AGENTE DE CÓDIGO:
lê, escreve e edita os arquivos do PROJETO do usuário (o diretório de onde o
hrx foi chamado), roda comandos e versiona com git. Trabalhe como um bom
engenheiro: primeiro ENTENDA o projeto (liste, busque, leia os arquivos
relevantes) e só então edite; faça mudanças pequenas e verificáveis.

Ferramentas de arquivo (agem no PROJETO real, com números de linha):
- listar_diretorio(caminho, recursivo)  lista arquivos ("." = raiz do projeto); recursivo=True mostra a árvore
- buscar_codigo(padrao, caminho, ext)  procura texto/regex nos arquivos (tipo grep -rn); ex: buscar_codigo("def main", ext=".py")
- ler_arquivo(caminho, inicio, fim)    lê o arquivo; inicio/fim = intervalo de linhas (1-based), opcional
- escrever_arquivo(caminho, conteudo)  cria/sobrescreve um arquivo
- editar_arquivo(caminho, procurar, substituir)  busca-e-substitui exato num arquivo existente

Outras ferramentas:
- criar_planilha(nome, dados, cabecalho)  cria Excel .xlsx
- criar_pdf(nome, titulo, conteudo, tabela)  cria PDF
- rodar_comando(comando)        executa comando no shell (roda no diretório do projeto)
- git(args)                     versiona: git("status"), git("diff"), git("commit -m 'msg'")
- consultar_cve(consulta)       consulta CVEs no NVD por ID (CVE-2021-44228) ou palavra-chave
- memoria_salvar(texto, tipo) / memoria_listar() / memoria_esquecer(alvo)  memória entre sessões
- buscar_docs(consulta)         busca nos documentos do usuário (base de conhecimento, não é o código)

EDIÇÃO DE CÓDIGO: para alterar um arquivo, LEIA antes (ler_arquivo) e use
editar_arquivo com um trecho 'procurar' único e literal (copie a indentação
exata). Para arquivo novo ou reescrita total, use escrever_arquivo. Depois de
editar, confira com git diff e/ou rodando os testes.

GIT: use a ferramenta git para versionamento (status, diff, log, branch, add,
commit, push...). Ela age no repositório do diretório atual do usuário. Antes de
commitar, veja o que mudou (status/diff) e escreva uma mensagem descritiva.

SEGURANÇA (uso defensivo / educacional / CTF): você ajuda em análise defensiva.
Pode rodar scans (ex: nmap via rodar_comando — passa pela confirmação de risco) e
INTERPRETAR o resultado; consultar CVEs com consultar_cve; ler e analisar logs
(tail/grep via rodar_comando); e gerar regras YARA/Sigma (escreva o conteúdo e
salve com escrever_arquivo). Só escaneie/teste alvos próprios, autorizados, ou de
laboratório/CTF; se o alvo for de terceiros, pergunte sobre a autorização antes.

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

Nunca invente resultado de ferramenta. Uma ferramenta por vez. Responda em português."""

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
        "   [dim italic]— seu agente de IA no terminal.[/]")
    mem = f" · [dim]{n_memorias} memória(s)[/dim]" if n_memorias else ""
    projeto = f" · [dim]{config.PROJETO}[/dim]" if getattr(config, "PROJETO", "") else ""
    console.print(f"  [dim]{rotulo_motor}[/dim]{mem}"
                  f"{projeto}"
                  f"[dim] · digite [/dim][cyan]/ajuda[/cyan][dim] para comandos[/dim]")
    console.print(Rule(style="grey30"))


def _montar_system() -> str:
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
    memorias = ferramentas.carregar_memorias()
    base = SYSTEM
    if bloco_pref:
        base += "\n\nPREFERÊNCIAS DO AGENTE:\n" + bloco_pref
    if not memorias:
        return base
    linhas = "\n".join(f"- #{m['id']} [{m.get('tipo', 'fato')}] {m['texto']}"
                       for m in memorias)
    return (base + "\n\nMEMÓRIA (o que você já sabe deste usuário/ambiente — "
            "use e respeite):\n" + linhas)


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


def _aprovar_comando(pol: permissao.Politica, comando: str, ferramenta: str = None):
    """Gate interativo 🟢🟡🔴 usando a política da sessão.
    Retorna (permitido, resultado_bloqueio)."""
    nivel, motivo = pol.classificar(comando, ferramenta=ferramenta)

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


def _janela(historico: list) -> list:
    """Mantém as mensagens mais RECENTES dentro do orçamento de contexto, pra
    conversa longa não estourar o limite do modelo (especialmente o local)."""
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
        f"sempre permitidos: {len(pol.sempre)}",
        f"mensagens na conversa: {len(historico)}",
        f"memórias salvas: {len(memoria)}",
        f"última mensagem: {ultima}",
    ]
    return "\n".join(linhas)


def rodar(motor_chamar, pol: permissao.Politica, historico: list, pergunta: str) -> str:
    """Executa um turno do usuário mantendo o HISTÓRICO da conversa.
    `motor_chamar(mensagens) -> texto` (Gemini ou local). `historico` é a lista
    de mensagens da conversa (sem o system); é mutada in-place, então persiste
    entre os turnos do REPL — é isso que dá memória de curto prazo ao agente.
    `pol` é a política de permissões da sessão."""
    system_msg = {"role": "system", "content": _montar_system()}
    historico.append({"role": "user", "content": pergunta})
    for _ in range(config.MAX_ITER):
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
            permitido, bloqueio = _aprovar_comando(pol, comando, ferramenta=nome)
            if permitido:
                pol.liberar(comando)          # abre o trinco só p/ esta chamada
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
        "5": ("ollama", "Ollama local"), "6": ("local", "Llamafile / Qwen local"),
    }
    console.print(Panel(
        "[cyan]1[/cyan] Gemini\n[cyan]2[/cyan] ChatGPT / OpenAI\n"
        "[cyan]3[/cyan] DeepSeek\n[cyan]4[/cyan] Claude\n"
        "[cyan]5[/cyan] Ollama local\n[cyan]6[/cyan] Llamafile / Qwen local",
        title="⚙ configurar motor", border_style="cyan", padding=(0, 2)))
    escolha = _perguntar("  escolha [1-6] (Enter cancela) › ")
    if escolha not in opcoes:
        console.print("  [dim]configuração cancelada.[/dim]")
        return

    motor, rotulo = opcoes[escolha]
    dados = dict(config._CFG)
    dados["motor"] = motor
    campos = {
        "openai": ("openai", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
        "deepseek": ("deepseek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
        "claude": ("claude", "https://api.anthropic.com/v1/messages", "claude-opus-4-8"),
        "ollama": ("ollama", "http://127.0.0.1:11434/v1/chat/completions", "llama3.1"),
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
        dados.update({"local_url": url, "local_modelo": modelo})
    else:
        prefixo, url_padrao, modelo_padrao = campos[motor]
        atual = config.provedor(motor)
        url = _perguntar(f"  URL [{atual.get('url', url_padrao)}] › ") or atual.get("url", url_padrao)
        modelo = _perguntar(f"  modelo [{atual.get('modelo', modelo_padrao)}] › ") or atual.get("modelo", modelo_padrao)
        chave = "" if motor == "ollama" else _ler_segredo("  chave API (Enter mantém a atual) › ")
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
    """Trata /comandos. `pool` é None quando o motor é local. `pol` é a política
    de permissões, `historico` a conversa atual (mutável). Retorna True se
    consumiu a entrada."""
    cmd = entrada.lower()
    partes = cmd.split()
    if cmd in ("/sair", "sair", "exit", "quit", "/quit"):
        console.print("[dim]até mais 👋[/dim]")
        raise SystemExit(0)
    if cmd in ("/ajuda", "/help"):
        console.print(Panel(
            "[cyan]/motor[/cyan]       mostra qual motor está em uso\n"
            "[cyan]/config[/cyan]      escolhe e configura o motor de IA\n"
            "[cyan]/perfil[/cyan]      mostra/edita nome, tom, idioma e projeto\n"
            "[cyan]/chaves[/cyan]      status das chaves (só motor gemini)\n"
            "[cyan]/debug[/cyan]       mostra o estado interno do agente\n"
            "[cyan]/resumo[/cyan]      resume a conversa atual\n"
            "[cyan]/modo[/cyan] [dim]<m>[/dim]   permissões: [dim]blindado · cauteloso · auto[/dim]\n"
            "[cyan]/permissoes[/cyan]  mostra modo e a lista 'sempre permitir'\n"
            "[cyan]/memoria[/cyan]     mostra o que o HRX CODE já lembra\n"
            "[cyan]/novo[/cyan]        começa uma conversa nova (esquece o contexto)\n"
            "[cyan]/limpar[/cyan]      limpa a tela\n"
            "[cyan]/sair[/cyan]        encerra",
            title="comandos", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/config":
        _configurar_motor()
        console.print("  [dim]A nova configuração será usada na próxima vez que abrir o HRX CODE.[/dim]")
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
    if cmd in ("/permissoes", "/permissões", "/perm"):
        sempre = ", ".join(sorted(pol.sempre)) if pol.sempre else "(nenhum)"
        console.print(Panel(
            f"modo: [cyan]{pol.modo}[/cyan]\n"
            f"sempre permitir: [green]{sempre}[/green]",
            title="🔐 permissões", border_style="grey37", padding=(0, 2)))
        return True
    if cmd in ("/memoria", "/memorias"):
        console.print(Panel(ferramentas.memoria_listar(),
                            title="🧠 memória", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/motor":
        if config.MOTOR == "local":
            estado = "[green]no ar[/green]" if local.disponivel() else "[red]fora do ar[/red]"
            console.print(f"  motor: [cyan]local[/cyan] · {config.MODELO_LOCAL} · "
                          f"{config.LOCAL_URL} ({estado})")
        elif config.MOTOR == "gemini":
            console.print(f"  motor: [cyan]gemini[/cyan] · {config.MODELO} · "
                          f"{pool.n if pool else 0} chave(s)")
        else:
            p = config.provedor(config.MOTOR)
            tem = "[green]chave ok[/green]" if p.get("chave") else \
                ("[dim]sem chave[/dim]" if p.get("exige_chave") else "[dim]local[/dim]")
            console.print(f"  motor: [cyan]{config.MOTOR}[/cyan] · "
                          f"{p.get('modelo', '?')} · {tem}")
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
    """Monta (motor_chamar, pool, rotulo) conforme config.MOTOR.
    pool só existe no motor gemini (failover de chaves); nos outros é None."""
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

    # Motores por API (protocolo OpenAI: openai/deepseek/ollama; Anthropic: claude)
    if config.MOTOR in ("openai", "deepseek", "ollama", "claude"):
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
    motor_chamar, pool, rotulo = _preparar_motor()
    banner(rotulo, len(ferramentas.carregar_memorias()))

    # política de permissões da sessão (modo via HRX_MODO; registra o
    # singleton que as ferramentas consultam pelo trinco).
    pol = permissao.Politica(modo=getattr(config, "MODO", "cauteloso"),
                             seguros_extra=getattr(config, "COMANDOS_PERMITIDOS", ()))
    permissao.usar(pol)

    historico: list = []   # conversa viva; persiste entre turnos do REPL

    arg = " ".join(sys.argv[1:]).strip()
    if arg:  # modo one-shot
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
