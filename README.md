# 🦾 HRX CODE — agente de IA de terminal

Agente de IA de terminal com motor padrão **local** e suporte a
**Gemini**, **ChatGPT/OpenAI**, **DeepSeek**, **Claude** e **Ollama**.
Tem rotação automática das chaves Gemini, ferramentas para código e documentos,
além de uma interface estilizada. Instalado como pacote, disponibiliza o
comando `hrx` no ambiente Python.

> *HRX CODE — seu agente de IA no terminal.*

## Recursos

- **Failover de chaves:** pool de N chaves grátis; quando uma estoura o limite
  (HTTP 429), a próxima assume sozinha, com cooldown por chave.
- **Ferramentas (loop ReAct):**
  - `ler_arquivo`, `escrever_arquivo`, `editar_arquivo`, `listar_diretorio`
  - `criar_planilha` (Excel `.xlsx`), `criar_pdf` (PDF com tabela)
  - `rodar_comando` (classificação de risco), `buscar_docs` (RAG simples)
- **Isolamento de arquivos:** leituras ficam no projeto real; escritas externas
  exigem confirmação explícita de alto risco e escapes por links são bloqueados.
- **UI:** banner ASCII, cores e respostas em markdown (via `rich`).
- **Motor local padrão:** Qwen2.5-7B GGUF em `llamafile`, sem chave, cota ou internet.
- **Motores configuráveis:** escolha o provedor, modelo, URL e chave pelo
  comando `/config`; as credenciais ficam fora do repositório.
- **Memória compacta no prompt:** carrega só um resumo curto das memórias para
  economizar tokens e permitir sessões maiores.

## Instalação

### Pré-requisito
Python 3.10+.

### Passos
```bash
git clone https://github.com/kaue34381210-star/hrx-code.git
cd hrx-code
python -m venv .venv && . .venv/bin/activate
python -m pip install .
hrx --version
```

### Chaves
Configure o motor e a chave pelo comando `/config` dentro do chat (recomendado),
ou, para o Gemini, crie o arquivo de chaves a partir do modelo:

```bash
cp chaves.txt.exemplo chaves.txt   # uma chave por linha
```

`chaves.txt` está no `.gitignore` — nunca vai para o repositório. A escolha de
motor fica em `~/.config/hrx/motor.json`.

## Uso

```bash
hrx                         # chat interativo
hrx "tarefa"                # pergunta única (one-shot)
hrx --help                  # ajuda da linha de comando
```

Dica para subir o motor local em outro terminal: `./iniciar-qwen.sh`.
Se o `llamafile` ou o `.gguf` estiverem em outro lugar, defina
`HRX_LLAMAFILE` e `HRX_MODELO_GGUF`.
Para desenvolvimento, `python agente.py` continua disponível sem instalação.

Comandos no chat: `/config` (escolhe e configura o motor), `/motor`, `/chaves`
(status das chaves no Gemini), `/debug`, `/resumo`, `/limpar`, `/ajuda`,
`/sair`.

Use `/config` para selecionar Gemini, ChatGPT/OpenAI, DeepSeek, Claude, Ollama
ou o Qwen/llamafile local. O padrão inicial é o motor local. A configuração,
incluindo chaves, fica em `~/.config/hrx/motor.json` com permissão restrita;
reinicie o HRX CODE após salvar para aplicar o novo motor. Se faltar uma
chave, o assistente oferece a configuração ao iniciar.

Memórias, documentos internos e o workspace persistente ficam em
`~/.config/hrx/dados/` e `~/.config/hrx/workspace/`, sobrevivendo a upgrades.

## Memória do projeto

As decisões e mudanças importantes deste agente ficam registradas em
[`MEMORIA.md`](MEMORIA.md). Sempre que o comportamento mudar, atualize esse
arquivo junto com o README para manter o histórico útil.

## Configuração (`config.py`)

- `NOME` — nome exibido no banner
- Use `/config` para trocar motor, modelo, URL e chave sem editar arquivos.
- `COMANDOS_PERMITIDOS` — comandos tratados como seguros pela política
- `MEMORIA_PROMPT` — modo da memória no prompt (`compacta` por padrão)
- `/memoria modo compacta|completa` — alterna o modo de carregamento da memória
- `/memoria compacta` — mostra a visão curta da memória
- `/memoria resumir` — força a compactação/resumo da memória
- `/memoria limpar` — apaga memória e resumo salvos

## Arquitetura

```
agente.py        loop ReAct + interface (rich)
pyproject.toml   pacote, dependências e comando `hrx`
versao.py        versão pública do pacote e da CLI
gemini.py        cliente Gemini + pool de chaves com failover
local.py         cliente do endpoint OpenAI-compatível local
openai_compat.py adaptador para OpenAI, DeepSeek e Ollama
claude.py        adaptador para a API Messages da Anthropic
iniciar-qwen.sh  inicia o llamafile com o modelo GGUF
ferramentas.py   ferramentas de código, documentos, memória e terminal
caminhos.py      resolução canônica e proteção contra escapes de diretório
permissao.py     gate de risco e autorização de uso único
config.py        configuração
tests/            suíte automatizada com pytest
```

Instale as dependências de desenvolvimento e rode a suíte completa:
```bash
pip install ".[dev]"
python -m pytest
```

Os mesmos testes rodam no GitHub Actions em Python 3.10, 3.11, 3.12 e 3.13.

## Segurança

- Chaves ficam fora do código e fora do git (`chaves.txt`, ignorado).
- Leituras são limitadas ao projeto, inclusive após resolver links simbólicos.
- Escritas no projeto passam pelo gate; caminhos externos são sempre 🔴 e
  exigem que o usuário digite `sim`, mesmo no modo automático.
- Comandos de terminal são classificados por risco e protegidos por um trinco
  de autorização de uso único.
- O free tier do Gemini pode usar prompts para treino — **não envie dados
  sensíveis**.

## Licença

**Uso gratuito, proprietária.** Você pode usar e compartilhar cópias exatas do
HRX CODE de graça, mas **não pode modificar nem vender**. Não é software de
código aberto. Veja os termos completos em [`LICENSE`](LICENSE).

© 2026 Kauê. Todos os direitos reservados.
