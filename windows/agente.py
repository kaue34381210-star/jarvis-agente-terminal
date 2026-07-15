"""Agente de terminal com motor Gemini e failover de chaves."""
import json
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

import aprovacao
import config
import ferramentas
import local
from gemini import PoolChaves, carregar_chaves, chamar

console = Console()

SYSTEM = """Você é um agente de IA que resolve tarefas via terminal usando ferramentas.

Ferramentas:
- ler_arquivo(caminho)          lê arquivo do workspace
- escrever_arquivo(caminho, conteudo)  cria/sobrescreve arquivo de texto
- editar_arquivo(caminho, procurar, substituir)  busca-e-substitui num arquivo
- listar_diretorio(caminho)     lista arquivos ("." = raiz)
- criar_planilha(nome, dados, cabecalho)  cria Excel .xlsx; dados = lista de linhas (listas) ou de dicionários
- criar_pdf(nome, titulo, conteudo, tabela)  cria PDF; conteudo = texto/lista de parágrafos; tabela = lista de linhas (1ª = cabeçalho)
- rodar_comando(comando)        executa comando no shell do sistema
- git(args)                     roda git no projeto atual, ex: git("status"), git("commit -m 'msg'")
- consultar_cve(consulta)       consulta CVEs no NVD por ID (CVE-2021-44228) ou palavra-chave
- memoria_salvar(texto, tipo)   guarda um fato/decisão/comando pra lembrar nas próximas sessões
- memoria_listar()              mostra tudo que já foi guardado na memória
- memoria_esquecer(alvo)        remove memória por #id ou por termo
- buscar_docs(consulta)         busca nos documentos do usuário

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

MASCARA = r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣶⣾⣽⠋⠷⢶⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⠚⠁⠸⣿⣿⠃⠀⠀⠀⣼⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠉⢹⠀⠀⠀⢀⢻⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⠀⠀⠘⠀⠈⣀⣀⣀⣞⡼⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠯⣽⢶⠋⠙⠓⠒⠛⠋⣠⣼⣿⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢆⠀⠈⠀⠀⠀⠀⣠⢺⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡆⢰⣆⣀⣸⣰⠁⢿⣿⣿⣿⠀⢀⡀⠀⠀⠀⠀⠀⣀⣀⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣀⣀⣀⡀⠀⠀⠀⣀⣤⣼⡟⣏⣉⣋⡏⢷⣾⣿⣿⣿⡟⠁⠈⠒⢤⠖⠈⠉⠉⣰⠏⠉⠦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢠⠋⠉⠀⣾⡗⢉⣵⢆⠉⠀⡏⢿⣹⣿⣿⣧⣿⣿⢟⡿⠋⠘⢶⠾⢿⣶⣊⣀⣀⣀⣴⡏⠀⠀⠀⠈⠳⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⢠⢃⣠⣤⣾⣇⣴⠟⠁⠈⠳⣤⡷⢾⣿⣿⣿⣿⣻⡥⠤⠂⠀⠀⠀⠉⠲⢼⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠘⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⢀⣿⠋⣿⣿⡿⠟⠁⠀⠀⠀⠀⠀⢀⣼⣿⣭⡀⠀⠀⠙⣄⠀⠀⠀⠀⢀⣠⡤⠜⢻⣿⣿⣿⣿⣿⣷⣄⠀⠀⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⣼⣿⣿⣿⣿⠀⠀⠀⠀⡠⠊⠀⢠⣿⡝⠛⢻⣷⠀⠀⠀⠈⢧⡴⠚⠋⠁⠀⠀⢀⣼⣿⣶⣶⣤⡉⠹⣿⣧⡀⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⣿⣿⢿⡿⣿⠀⠀⢀⡔⠁⠀⠀⢸⣹⡄⠀⣰⠟⠀⠀⠀⠀⠀⢱⣄⠀⢀⡠⠖⠉⠸⣿⣿⠿⠿⣧⡀⠈⢿⣿⢆⢧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠸⠟⠉⠈⢧⡏⡇⠀⡜⠀⠀⠀⠀⠀⠉⠙⠎⠁⠀⠀⠀⣀⣠⣤⡼⡍⢷⡍⠀⠀⠀⢀⣿⡘⡆⠀⢸⠿⠶⣶⣇⠀⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠸⡇⣧⢠⡗⠀⠀⠀⠢⢄⣀⣀⣤⣤⡖⠊⠉⠉⠁⠀⠀⠙⢆⠻⣆⠀⠀⣰⣿⣧⡇⠀⢠⠀⠀⠀⢹⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢸⠃⣿⣾⠀⠀⠀⢀⣠⣾⡿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠈⢦⠙⣗⠋⢹⣿⣿⣿⠀⣼⠳⣄⠀⠘⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣾⣦⣿⣿⡆⠀⣴⣿⠟⢃⠀⣿⣿⣿⣿⡏⠛⠻⢿⣶⣄⠀⠀⠀⢣⣼⡆⢸⡟⢻⣿⣾⡃⢠⣿⣿⠚⠳⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⡜⣽⣿⣦⣙⢇⣼⣿⣿⣦⡘⡆⢻⣿⣿⣿⣷⣤⠞⠋⠁⢻⣿⣦⣴⣿⣿⣿⣼⠃⠀⠹⣿⣴⣿⢿⠏⠳⡄⠱⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⢰⠏⢸⠈⢿⣿⣿⣿⢿⣧⡃⠘⡗⢾⣿⣿⣿⣿⠀⠀⣀⣤⣿⠛⠛⢿⣿⣿⡛⠁⠀⠀⠀⢸⣟⢁⡾⠀⣀⡨⣦⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⢀⣿⡒⢺⣶⣼⣿⣿⣿⡇⢧⠛⢦⣇⢸⣿⣿⣿⣿⡴⠞⠉⠀⢻⡀⣀⡤⣿⣿⣡⠀⠀⠀⠠⣿⣿⣿⣇⠉⠁⠀⠘⢿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⣾⣿⣷⣾⣿⣿⣿⣿⣿⣇⠌⢷⡀⠙⢻⣿⣿⣿⡉⠀⠀⠠⠟⢸⠟⢁⡤⠼⣿⣿⡄⠀⠀⠀⢸⢿⣿⣿⠀⠀⠀⠀⣸⣟⡄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⢃⡏⢆⢠⠙⢶⣌⣿⣿⣿⣿⣿⣶⣄⣠⢏⡴⠋⡇⠀⠇⢹⣣⠀⠀⠀⠈⡏⢻⣿⣄⡀⠀⣴⣿⠋⣇⠀⠀⠀⠀⠀⠀⠀⠀
⠀⣿⣿⣿⣿⣿⣿⣿⣿⠇⢸⡏⠈⢻⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⢱⢀⣼⣤⣿⣇⠀⠀⠀⢸⣼⣿⠿⠿⢻⣿⣿⡄⢸⠀⠀⠀⠀⠀⠀⠀⠀
⠀⣿⣿⣿⣿⣿⣿⣿⢇⣀⣸⣆⣠⠎⠉⠉⢻⣾⣿⣿⣿⣿⣿⣿⣧⣄⠀⠀⣸⡿⢾⠛⠻⠿⠆⣀⠀⠀⠙⢧⣤⣴⡾⢛⡿⠀⢸⠀⠀⠀⠀⠀⠀⠀⠀
⢰⠙⣿⣿⣿⣿⡿⠁⣸⠁⡎⠉⢻⣦⣀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣮⣿⡇⠘⣧⠀⠀⠀⠈⡇⠀⠀⢸⣿⣿⢿⣋⠁⠀⣾⠀⠀⠀⠀⠀⠀⠀⠀
⢸⣾⣿⣿⣿⣏⠀⢰⡇⢸⠁⠀⠀⢻⣿⣷⣤⡀⢹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠸⣇⠀⠀⠀⢱⠀⣠⣺⣿⣾⣟⡻⠷⡀⣿⠀⠀⠀⠀⠀⠀⠀⠀
⢸⢈⣿⣿⣿⣿⣄⣾⠃⡄⠀⠀⢀⣼⠙⢿⣿⣿⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⢹⡆⠀⠀⢸⣶⣿⣿⣯⠈⢦⠀⢀⠿⣿⠀⠀⠀⠀⠀⠀⠀⠀
⠘⢏⣼⢟⡛⣻⣿⡟⢠⠃⢀⣴⣿⡇⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⢸⣿⣿⣿⣿⣿⠀⠀⠀⢻⣆⠀⢸⣿⣻⣿⢿⣷⣌⣦⠏⡴⠉⠀⠀⠀⠀⠀⠀⠀⠀
⠘⢿⣿⣿⣿⣿⣿⡿⢾⣾⣿⣿⣿⠃⠀⢸⣿⣿⣿⣿⣿⣿⠙⣿⠘⣿⣿⣿⣿⣿⡀⠀⠀⠈⣿⡆⢸⡿⣿⣿⣿⣿⣿⣿⡾⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠈⠉⠉⠉⠰⣿⠿⠀⠱⢝⢿⣿⠀⠀⢸⣿⣿⣿⣿⣿⣿⠀⢿⣧⣿⣿⣿⢟⠉⠩⣲⢄⣰⣿⣿⣾⡇⠀⠉⠛⠛⠛⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"""

LOGO = r"""
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"""


def banner(rotulo_motor: str, n_memorias: int = 0) -> None:
    console.print(Text(MASCARA, style="bold red3"))
    console.print(Text(LOGO, style="bold gold1"))
    console.print(
        "  [bold gold1]J[/]ust [bold gold1]A[/] [bold gold1]R[/]ather "
        "[bold gold1]V[/]ery [bold gold1]I[/]ntelligent [bold gold1]S[/]ystem"
        "   [dim italic]— às suas ordens, senhor.[/]")
    mem = f" · [dim]{n_memorias} memória(s)[/dim]" if n_memorias else ""
    console.print(f"  [dim]{rotulo_motor}[/dim]{mem}"
                  f"[dim] · digite [/dim][cyan]/ajuda[/cyan][dim] para comandos[/dim]")
    console.print(Rule(style="grey30"))


def _montar_system() -> str:
    """SYSTEM + memórias persistentes injetadas no contexto."""
    memorias = ferramentas.carregar_memorias()
    if not memorias:
        return SYSTEM
    linhas = "\n".join(f"- #{m['id']} [{m.get('tipo', 'fato')}] {m['texto']}"
                       for m in memorias)
    return (SYSTEM + "\n\nMEMÓRIA (o que você já sabe deste usuário/ambiente — "
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


# Ferramentas que passam pelo filtro de risco 🟢🟡🔴, e como montar a string
# de comando que será classificada a partir dos args.
_COMANDO_DE_FERRAMENTA = {
    "rodar_comando": lambda a: str(a.get("comando", "")),
    "git": lambda a: ("git " + str(a.get("args", ""))).strip(),
}


def _perguntar(prompt: str) -> str:
    """Lê confirmação do usuário. Sem terminal interativo → trata como recusa."""
    try:
        return console.input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _aprovar_comando(comando: str):
    """Filtro de risco 🟢🟡🔴. Retorna (permitido, resultado_bloqueio)."""
    extras = getattr(config, "COMANDOS_PERMITIDOS", ())
    nivel, motivo = aprovacao.classificar(comando, seguros_extra=extras)

    if nivel == "verde":
        console.print(f"  [green]🟢 seguro[/green] [dim]— {motivo}[/dim]")
        return True, None

    if nivel == "amarelo":
        console.print(f"  [yellow]🟡 confirmação[/yellow] [dim]— {motivo}[/dim]")
        ok = _perguntar("  [yellow]executar?[/yellow] [dim][Enter=sim · n=não][/dim] › ") \
            .lower() not in ("n", "nao", "não", "no", "cancelar")
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


def rodar(motor_chamar, pergunta: str) -> str:
    """motor_chamar(mensagens) -> texto do modelo (Gemini ou local)."""
    mensagens = [{"role": "system", "content": _montar_system()},
                 {"role": "user", "content": pergunta}]
    for _ in range(config.MAX_ITER):
        with console.status("[cyan]pensando...", spinner="dots"):
            texto = motor_chamar(mensagens)
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
        extrair_cmd = _COMANDO_DE_FERRAMENTA.get(nome)
        if extrair_cmd:
            permitido, bloqueio = _aprovar_comando(extrair_cmd(args))
            resultado = ferramentas.executar(nome, args) if permitido else bloqueio
        else:
            resultado = ferramentas.executar(nome, args)
        mensagens.append({"role": "assistant", "content": texto})
        mensagens.append({"role": "user",
                          "content": f"RESULTADO da ferramenta {nome}:\n{resultado}"})
    return "Parei: atingi o limite de passos sem resposta final."


def _comando_especial(pool, entrada: str) -> bool:
    """Trata /comandos. `pool` é None quando o motor é local. Retorna True
    se consumiu a entrada."""
    cmd = entrada.lower()
    if cmd in ("/sair", "sair", "exit", "quit", "/quit"):
        console.print("[dim]até mais 👋[/dim]")
        raise SystemExit(0)
    if cmd in ("/ajuda", "/help"):
        console.print(Panel(
            "[cyan]/motor[/cyan]     mostra qual motor está em uso\n"
            "[cyan]/chaves[/cyan]    status das chaves (só motor gemini)\n"
            "[cyan]/memoria[/cyan]   mostra o que o JARVIS já lembra\n"
            "[cyan]/limpar[/cyan]    limpa a tela\n"
            "[cyan]/sair[/cyan]      encerra",
            title="comandos", border_style="grey37", padding=(0, 2)))
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
        else:
            console.print(f"  motor: [cyan]gemini[/cyan] · {config.MODELO} · "
                          f"{pool.n if pool else 0} chave(s)")
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


def _preparar_motor():
    """Monta (motor_chamar, pool, rotulo) conforme config.MOTOR.
    pool é None no motor local."""
    if config.MOTOR not in ("gemini", "local"):
        raise RuntimeError(
            "JARVIS_MOTOR inválido: " + repr(config.MOTOR) +
            ". Use 'local' ou 'gemini'.")
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

    chaves = carregar_chaves()
    if not chaves:
        console.print(Panel(
            "Nenhuma chave encontrada.\n\n"
            "Crie o arquivo [bold]chaves.txt[/bold] (uma chave por linha), defina "
            "[bold]GEMINI_API_KEY[/bold], ou use o motor local com "
            "[bold]JARVIS_MOTOR=local[/bold].",
            title="[red]sem chaves", border_style="red"))
        sys.exit(1)
    pool = PoolChaves(chaves)
    return (lambda msgs: chamar(pool, msgs, on_rotacao=_aviso_rotacao)[0]), pool, \
        f"motor gemini · {config.MODELO} · {len(chaves)} chave(s)"


def main() -> None:
    motor_chamar, pool, rotulo = _preparar_motor()
    banner(rotulo, len(ferramentas.carregar_memorias()))

    arg = " ".join(sys.argv[1:]).strip()
    if arg:  # modo one-shot
        try:
            resposta = rodar(motor_chamar, arg)
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
            if _comando_especial(pool, entrada):
                continue
            resposta = rodar(motor_chamar, entrada)
            console.print()
            console.print(Panel(Markdown(resposta),
                                title=f"[green]{config.NOME}", border_style="green", padding=(1, 2)))
        except SystemExit:
            break
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]erro:[/red] {e}")


if __name__ == "__main__":
    main()
