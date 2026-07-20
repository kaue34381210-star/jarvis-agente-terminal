import stat

import pytest

from hrx_code import agente
from hrx_code import config
from hrx_code import permissao


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ('{"acao": "responder", "texto": "ok"}',
         {"acao": "responder", "texto": "ok"}),
        ('prefixo {"acao": "usar", "args": {"x": 1}} sufixo',
         {"acao": "usar", "args": {"x": 1}}),
        ('```json\n{"acao": "responder"}\n```', {"acao": "responder"}),
    ],
)
def test_extrair_json_aceita_objeto_com_texto_ao_redor(texto, esperado):
    assert agente.extrair_json(texto) == esperado


@pytest.mark.parametrize("texto", ["sem json", "prefixo {invalido} sufixo", ""])
def test_extrair_json_invalido_retorna_none(texto):
    assert agente.extrair_json(texto) is None


def test_rodar_desconta_system_do_orcamento_de_contexto(monkeypatch):
    monkeypatch.setattr(config, "CONTEXTO_MAX_CHARS", 40)
    monkeypatch.setattr(agente, "_montar_system", lambda consulta="": "s" * 20)
    recebidas = []

    def motor(mensagens):
        recebidas.append(mensagens)
        return "resposta final"

    historico = [{"role": "user", "content": "mensagem antiga"}]

    agente.rodar(motor, permissao.Politica(), historico, "pergunta")

    mensagens = recebidas[0]
    assert [m["content"] for m in mensagens] == ["s" * 20, "pergunta"]
    assert sum(len(m["content"]) for m in mensagens) <= 40


def test_janela_vazia_quando_system_consumiu_todo_orcamento():
    historico = [{"role": "user", "content": "pergunta"}]

    assert agente._janela(historico, orcamento=0) == []


@pytest.mark.parametrize("preexistente", [False, True])
def test_acrescentar_chave_forca_permissao_600(tmp_path, preexistente):
    caminho = tmp_path / "chaves.txt"
    if preexistente:
        caminho.write_text("anterior\n", encoding="utf-8")
        caminho.chmod(0o644)

    agente._acrescentar_chave(str(caminho), "nova")

    esperado = "anterior\nnova\n" if preexistente else "nova\n"
    assert caminho.read_text(encoding="utf-8") == esperado
    assert stat.S_IMODE(caminho.stat().st_mode) == 0o600
