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
- buscar_docs(consulta)         busca nos documentos do usuário

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


def banner(n_chaves: int) -> None:
    console.print(Text(MASCARA, style="bold red3"))
    console.print(Text(LOGO, style="bold gold1"))
    console.print(
        "  [bold gold1]J[/]ust [bold gold1]A[/] [bold gold1]R[/]ather "
        "[bold gold1]V[/]ery [bold gold1]I[/]ntelligent [bold gold1]S[/]ystem"
        "   [dim italic]— às suas ordens, senhor.[/]")
    console.print(f"  [dim]{n_chaves} chave(s) carregada(s) · failover automático · "
                  f"digite [/dim][cyan]/ajuda[/cyan][dim] para comandos[/dim]")
    console.print(Rule(style="grey30"))


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


def rodar(pool: PoolChaves, pergunta: str) -> str:
    mensagens = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": pergunta}]
    for _ in range(config.MAX_ITER):
        with console.status("[cyan]pensando...", spinner="dots"):
            texto, _ = chamar(pool, mensagens, on_rotacao=_aviso_rotacao)
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
        if nome == "rodar_comando":
            permitido, bloqueio = _aprovar_comando(str(args.get("comando", "")))
            resultado = ferramentas.executar(nome, args) if permitido else bloqueio
        else:
            resultado = ferramentas.executar(nome, args)
        mensagens.append({"role": "assistant", "content": texto})
        mensagens.append({"role": "user",
                          "content": f"RESULTADO da ferramenta {nome}:\n{resultado}"})
    return "Parei: atingi o limite de passos sem resposta final."


def _comando_especial(pool: PoolChaves, entrada: str) -> bool:
    """Trata /comandos. Retorna True se consumiu a entrada."""
    cmd = entrada.lower()
    if cmd in ("/sair", "sair", "exit", "quit", "/quit"):
        console.print("[dim]até mais 👋[/dim]")
        raise SystemExit(0)
    if cmd in ("/ajuda", "/help"):
        console.print(Panel(
            "[cyan]/chaves[/cyan]   status das chaves (cooldown)\n"
            "[cyan]/limpar[/cyan]   limpa a tela\n"
            "[cyan]/sair[/cyan]     encerra",
            title="comandos", border_style="grey37", padding=(0, 2)))
        return True
    if cmd == "/chaves":
        for i, seg in enumerate(pool.status()):
            estado = "[green]livre[/green]" if seg == 0 else f"[yellow]castigo {seg}s[/yellow]"
            console.print(f"  chave #{i + 1}: {estado}")
        return True
    if cmd == "/limpar":
        console.clear()
        return True
    return False


def main() -> None:
    chaves = carregar_chaves()
    if not chaves:
        console.print(Panel(
            "Nenhuma chave encontrada.\n\n"
            "Crie o arquivo [bold]chaves.txt[/bold] (uma chave por linha) "
            "ou defina a variável [bold]GEMINI_API_KEY[/bold].",
            title="[red]sem chaves", border_style="red"))
        sys.exit(1)

    pool = PoolChaves(chaves)
    banner(len(chaves))

    arg = " ".join(sys.argv[1:]).strip()
    if arg:  # modo one-shot
        try:
            resposta = rodar(pool, arg)
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
            resposta = rodar(pool, entrada)
            console.print()
            console.print(Panel(Markdown(resposta),
                                title=f"[green]{config.NOME}", border_style="green", padding=(1, 2)))
        except SystemExit:
            break
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]erro:[/red] {e}")


if __name__ == "__main__":
    main()
