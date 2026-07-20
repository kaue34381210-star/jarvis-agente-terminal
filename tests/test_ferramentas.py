import socket
from unittest.mock import Mock

import pytest

from hrx_code import config
from hrx_code import ferramentas
from hrx_code import permissao


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    raiz = tmp_path / "projeto"
    dados = tmp_path / "dados"
    raiz.mkdir()
    monkeypatch.setattr(config, "REPO", str(raiz))
    monkeypatch.setattr(config, "DADOS", str(dados))
    monkeypatch.setattr(config, "MEMORIA", str(dados / "memoria.json"))
    permissao.usar(None)
    yield raiz
    permissao.usar(None)


@pytest.mark.parametrize(
    "endereco",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "2001:db8::1",
        "::ffff:127.0.0.1",
    ],
)
def test_validar_url_publica_bloqueia_todo_ip_nao_global(monkeypatch, endereco):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (endereco, 0))
        ],
    )

    with pytest.raises(ValueError, match="IP não público bloqueado"):
        ferramentas._validar_url_publica("https://exemplo.test/recurso")


def test_validar_url_publica_aceita_ip_global(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )

    url = "https://exemplo.test/recurso"

    assert ferramentas._validar_url_publica(url) == url


def test_request_ip_fixado_preserva_host_e_configura_tls(monkeypatch):
    sessao = Mock()
    sessao.trust_env = True
    resposta = Mock()
    sessao.get.return_value = resposta
    monkeypatch.setattr(ferramentas.requests, "Session", lambda: sessao)

    retornada, resultado = ferramentas._request_ip_fixado(
        "https://exemplo.test:8443/docs?q=1",
        "93.184.216.34",
        {"User-Agent": "teste"},
    )

    assert retornada is sessao
    assert resultado is resposta
    assert sessao.trust_env is False
    adaptador = sessao.mount.call_args.args[1]
    assert adaptador.hostname == "exemplo.test"
    pool = adaptador.poolmanager.connection_pool_kw
    assert pool["assert_hostname"] == "exemplo.test"
    assert pool["server_hostname"] == "exemplo.test"
    sessao.get.assert_called_once_with(
        "https://93.184.216.34:8443/docs?q=1",
        headers={"User-Agent": "teste", "Host": "exemplo.test:8443"},
        timeout=15,
        allow_redirects=False,
        stream=True,
    )


def test_buscar_web_exige_trinco_antes_de_resolver_dns(projeto, monkeypatch):
    resolver = Mock(side_effect=AssertionError("DNS não deveria ser consultado"))
    monkeypatch.setattr(ferramentas, "_resolver_url_publica", resolver)
    permissao.usar(permissao.Politica())

    resultado = ferramentas.buscar_web("https://exemplo.test/segredo")

    assert "não passou pela aprovação" in resultado
    resolver.assert_not_called()


def test_buscar_web_pinna_novo_ip_em_cada_redirect(monkeypatch):
    class Resposta:
        def __init__(self, status, headers=None, corpo=b""):
            self.status_code = status
            self.headers = headers or {}
            self.is_redirect = 300 <= status < 400
            self.ok = 200 <= status < 300
            self.encoding = "utf-8"
            self.corpo = corpo

        def close(self):
            pass

        def iter_content(self, _tamanho):
            yield self.corpo

    resolucoes = []
    requisicoes = []
    respostas = iter([
        Resposta(302, {"Location": "https://destino.test/final"}),
        Resposta(200, {"Content-Type": "text/plain"}, b"conteudo"),
    ])

    def resolver(url):
        resolucoes.append(url)
        return {"origem.test": "93.184.216.34",
                "destino.test": "142.250.79.46"}[url.split("/")[2]]

    def request(url, ip, headers):
        requisicoes.append((url, ip, headers))
        return Mock(), next(respostas)

    monkeypatch.setattr(ferramentas, "_resolver_url_publica", resolver)
    monkeypatch.setattr(ferramentas, "_request_ip_fixado", request)

    resultado = ferramentas.buscar_web("https://origem.test/inicio")

    assert resolucoes == [
        "https://origem.test/inicio",
        "https://destino.test/final",
    ]
    assert [(url, ip) for url, ip, _ in requisicoes] == [
        ("https://origem.test/inicio", "93.184.216.34"),
        ("https://destino.test/final", "142.250.79.46"),
    ]
    assert resultado == "# https://destino.test/final\n\nconteudo"


def test_lista_e_busca_ignoram_artefatos(projeto):
    (projeto / "src").mkdir()
    (projeto / "src" / "app.py").write_text("# TODO: revisar\n", encoding="utf-8")
    (projeto / "build").mkdir()
    (projeto / "build" / "gerado.py").write_text("# TODO: ignorar\n", encoding="utf-8")

    arvore = ferramentas.listar_diretorio(".", recursivo=True)
    resultado = ferramentas.buscar_codigo("TODO", ext=".py")

    assert "src/" in arvore
    assert "build/" not in arvore
    assert "src/app.py:1" in resultado
    assert "gerado.py" not in resultado


def test_le_intervalo_com_numeros_de_linha(projeto):
    (projeto / "dados.txt").write_text("um\ndois\ntres\n", encoding="utf-8")

    resultado = ferramentas.ler_arquivo("dados.txt", inicio=2, fim=3)

    assert "linhas 2-3 de 3" in resultado
    assert "2\tdois" in resultado
    assert "3\ttres" in resultado
    assert "1\tum" not in resultado


def test_le_arquivo_reporta_truncamento_exato(projeto):
    (projeto / "grande.txt").write_text("x" * 21000, encoding="utf-8")

    resultado = ferramentas.ler_arquivo("grande.txt")

    # O prefixo de numeração ("1\t") também faz parte do corpo retornado.
    assert "truncado: 1002 chars omitidos de 21002 totais" in resultado


def test_escrita_exige_e_consome_autorizacao(projeto):
    politica = permissao.Politica()
    permissao.usar(politica)
    args = {"caminho": "saida.txt", "conteudo": "conteúdo"}
    comando = permissao.comando_de("escrever_arquivo", args)

    negado = ferramentas.escrever_arquivo("saida.txt", "conteúdo")
    politica.liberar(comando, "escrever_arquivo", args)
    permitido = ferramentas.escrever_arquivo("saida.txt", "conteúdo")
    reutilizado = ferramentas.escrever_arquivo("saida.txt", "outro")

    assert "não passou" in negado
    assert permitido.startswith("OK:")
    assert (projeto / "saida.txt").read_text(encoding="utf-8") == "conteúdo"
    assert "não passou" in reutilizado


def test_escrita_rejeita_conteudo_trocado_depois_da_aprovacao(projeto):
    politica = permissao.Politica()
    permissao.usar(politica)
    args = {"caminho": "saida.txt", "conteudo": "aprovado"}
    comando = permissao.comando_de("escrever_arquivo", args)
    politica.liberar(comando, "escrever_arquivo", args)

    resultado = ferramentas.escrever_arquivo("saida.txt", "trocado")

    assert "não passou pela aprovação" in resultado
    assert not (projeto / "saida.txt").exists()


def test_edita_todas_as_ocorrencias_com_autorizacao(projeto):
    arquivo = projeto / "app.py"
    arquivo.write_text("antigo\nlinha\nantigo\n", encoding="utf-8")
    politica = permissao.Politica()
    permissao.usar(politica)
    args = {"caminho": "app.py", "procurar": "antigo",
            "substituir": "novo", "tudo": True}
    comando = permissao.comando_de("editar_arquivo", args)
    politica.liberar(comando, "editar_arquivo", args)

    resultado = ferramentas.editar_arquivo(
        "app.py", "antigo", "novo", tudo=True
    )

    assert "2 ocorrência(s)" in resultado
    assert arquivo.read_text(encoding="utf-8") == "novo\nlinha\nnovo\n"


def test_aplica_patch_unificado_com_multiplos_hunks(projeto):
    arquivo = projeto / "app.txt"
    arquivo.write_text("um\ndois\ntres\nquatro\n", encoding="utf-8")
    politica = permissao.Politica()
    permissao.usar(politica)
    patch = """--- a/app.txt
+++ b/app.txt
@@ -1,3 +1,4 @@
 um
-dois
+DOIS
+extra
 tres
@@ -4 +5 @@
-quatro
+QUATRO
"""
    args = {"caminho": "app.txt", "patch": patch}
    comando = permissao.comando_de("aplicar_patch", args)
    politica.liberar(comando, "aplicar_patch", args)

    resultado = ferramentas.aplicar_patch("app.txt", patch)

    assert resultado.startswith("OK: 2 hunk(s)")
    assert arquivo.read_text(encoding="utf-8") == "um\nDOIS\nextra\ntres\nQUATRO\n"


def test_patch_com_conflito_nao_altera_arquivo(projeto):
    arquivo = projeto / "app.txt"
    original = "linha atual\nsegunda\n"
    arquivo.write_text(original, encoding="utf-8")
    politica = permissao.Politica()
    permissao.usar(politica)
    patch = """@@ -1,2 +1,2 @@
-linha antiga
+linha nova
 segunda
"""
    args = {"caminho": "app.txt", "patch": patch}
    comando = permissao.comando_de("aplicar_patch", args)
    politica.liberar(comando, "aplicar_patch", args)

    resultado = ferramentas.aplicar_patch("app.txt", patch)

    assert "conflito" in resultado
    assert "não alterado" in resultado
    assert arquivo.read_text(encoding="utf-8") == original


def test_patch_exige_autorizacao_de_uso_unico(projeto):
    arquivo = projeto / "app.txt"
    arquivo.write_text("antigo\n", encoding="utf-8")
    permissao.usar(permissao.Politica())
    patch = """@@ -1 +1 @@
-antigo
+novo
"""

    resultado = ferramentas.aplicar_patch("app.txt", patch)

    assert "não passou" in resultado
    assert arquivo.read_text(encoding="utf-8") == "antigo\n"


@pytest.mark.parametrize(
    ("original", "patch", "esperado"),
    [
        (
            "antigo",
            "@@ -1 +1 @@\n-antigo\n\\ No newline at end of file\n+novo\n",
            "novo\n",
        ),
        (
            "antigo\n",
            "@@ -1 +1 @@\n-antigo\n+novo\n\\ No newline at end of file\n",
            "novo",
        ),
    ],
)
def test_patch_respeita_marcador_de_nova_linha(projeto, original, patch, esperado):
    arquivo = projeto / "app.txt"
    arquivo.write_text(original, encoding="utf-8")
    politica = permissao.Politica()
    permissao.usar(politica)
    args = {"caminho": "app.txt", "patch": patch}
    comando = permissao.comando_de("aplicar_patch", args)
    politica.liberar(comando, "aplicar_patch", args)

    resultado = ferramentas.aplicar_patch("app.txt", patch)

    assert resultado.startswith("OK: 1 hunk(s)")
    assert arquivo.read_text(encoding="utf-8") == esperado


def test_comando_nao_chega_ao_subprocess_sem_autorizacao(projeto, monkeypatch):
    executar = Mock(return_value=Mock(stdout="ok\n", stderr="", returncode=0))
    monkeypatch.setattr(ferramentas.subprocess, "run", executar)
    politica = permissao.Politica()
    permissao.usar(politica)

    negado = ferramentas.rodar_comando("echo ok")
    executar.assert_not_called()

    politica.liberar("echo ok", "rodar_comando", {"comando": "echo ok"})
    permitido = ferramentas.rodar_comando("echo ok")

    assert "não passou" in negado
    assert permitido == "ok\n[código de saída: 0]"
    assert executar.call_args.kwargs["cwd"] == str(projeto)
    assert executar.call_args.kwargs["shell"] is True


def test_comando_reporta_truncamento_e_codigo_de_erro(projeto, monkeypatch):
    executar = Mock(return_value=Mock(
        stdout="x" * 9000,
        stderr="falhou",
        returncode=7,
    ))
    monkeypatch.setattr(ferramentas.subprocess, "run", executar)
    politica = permissao.Politica()
    permissao.usar(politica)
    politica.liberar(
        "comando grande", "rodar_comando", {"comando": "comando grande"}
    )

    resultado = ferramentas.rodar_comando("comando grande")

    assert "truncado: 1006 chars omitidos de 9006 totais" in resultado
    assert resultado.endswith("[código de saída: 7]")


def test_git_reporta_saida_truncada_e_codigo(projeto, monkeypatch):
    (projeto / ".git").mkdir()
    executar = Mock(return_value=Mock(
        stdout="y" * 8100,
        stderr="",
        returncode=1,
    ))
    monkeypatch.setattr(ferramentas.subprocess, "run", executar)
    politica = permissao.Politica()
    permissao.usar(politica)
    politica.liberar("git status", "git", {"args": "status"})

    resultado = ferramentas.git("status")

    assert "truncado: 100 chars omitidos de 8100 totais" in resultado
    assert resultado.endswith("[código de saída: 1]")
    executar.assert_called_once_with(
        ["git", "status"],
        cwd=str(projeto),
        capture_output=True,
        text=True,
        timeout=config.TIMEOUT_COMANDO,
    )


def test_busca_reporta_total_real_acima_do_limite(projeto):
    arquivo = projeto / "muitos.txt"
    arquivo.write_text("\n".join(["ACHADO"] * 137), encoding="utf-8")

    resultado = ferramentas.buscar_codigo("ACHADO")

    assert len([linha for linha in resultado.splitlines()
                if linha.startswith("muitos.txt:")]) == 100
    assert "37 resultados omitidos; 137 resultados no total" in resultado


def test_busca_limita_contagem_e_informa_total_minimo(projeto):
    arquivo = projeto / "muitos.txt"
    arquivo.write_text("\n".join(["ACHADO"] * 600), encoding="utf-8")

    resultado = ferramentas.buscar_codigo("ACHADO")

    assert "ao menos 401 resultados omitidos; 500+ resultados no total" in resultado


def test_dispatcher_trata_nome_e_argumentos_invalidos():
    assert ferramentas.executar("inexistente", {}) == (
        "ERRO: ferramenta desconhecida 'inexistente'"
    )
    assert ferramentas.executar("ler_arquivo", {"campo": "x"}).startswith(
        "ERRO: argumentos inválidos para ler_arquivo:"
    )


def test_dispatcher_relanca_excecao_interna_em_debug(monkeypatch):
    def falhar():
        raise RuntimeError("falha interna")

    monkeypatch.setitem(ferramentas.REGISTRO, "falhar", falhar)
    monkeypatch.delenv("HRX_DEBUG", raising=False)
    assert ferramentas.executar("falhar", {}) == (
        "ERRO ao executar falhar: falha interna"
    )

    monkeypatch.setenv("HRX_DEBUG", "1")
    with pytest.raises(RuntimeError, match="falha interna"):
        ferramentas.executar("falhar", {})
