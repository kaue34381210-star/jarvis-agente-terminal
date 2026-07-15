# 🦾 HRX CODE — agente de IA de terminal

Agente de IA de terminal com motor padrão **local** e suporte a
**Gemini**, **ChatGPT/OpenAI**, **DeepSeek**, **Claude** e **Ollama**.
Tem rotação automática das chaves Gemini, ferramentas para código e documentos,
além de uma interface estilizada. Roda direto do repositório com
`python agente.py`.

> *HRX CODE — seu agente de IA no terminal.*

## Recursos

- **Failover de chaves:** pool de N chaves grátis; quando uma estoura o limite
  (HTTP 429), a próxima assume sozinha, com cooldown por chave.
- **Ferramentas (loop ReAct):**
  - `ler_arquivo`, `escrever_arquivo`, `editar_arquivo`, `listar_diretorio`
  - `criar_planilha` (Excel `.xlsx`), `criar_pdf` (PDF com tabela)
  - `rodar_comando` (whitelist de segurança), `buscar_docs` (RAG simples)
- **Sandbox:** o agente só lê/escreve dentro de `workspace/` e lê `dados/`.
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
pip install rich requests openpyxl reportlab
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
python agente.py            # chat interativo
python agente.py "tarefa"   # pergunta única (one-shot)
```

Dica para subir o motor local em outro terminal: `./iniciar-qwen.sh`.
Dica: crie um atalho `hrx` apontando para `.venv/bin/python agente.py`.

Comandos no chat: `/config` (escolhe e configura o motor), `/motor`, `/chaves`
(status das chaves no Gemini), `/debug`, `/resumo`, `/limpar`, `/ajuda`,
`/sair`.

Use `/config` para selecionar Gemini, ChatGPT/OpenAI, DeepSeek, Claude, Ollama
ou o Qwen/llamafile local. O padrão inicial é o motor local. A configuração,
incluindo chaves, fica em `~/.config/hrx/motor.json` com permissão restrita;
reinicie o HRX CODE após salvar para aplicar o novo motor. Se faltar uma
chave, o assistente oferece a configuração ao iniciar.

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
gemini.py        cliente Gemini + pool de chaves com failover
local.py         cliente do endpoint OpenAI-compatível local
openai_compat.py adaptador para OpenAI, DeepSeek e Ollama
claude.py        adaptador para a API Messages da Anthropic
iniciar-qwen.sh  inicia o llamafile com o modelo GGUF
ferramentas.py   ferramentas sandboxed
config.py        configuração
teste_failover.py  simula o failover sem gastar quota
```

Teste o failover sem consumir API:
```bash
python teste_failover.py
```

Teste o adaptador local sem carregar o modelo:
```bash
python teste_local.py
```

## Segurança

- Chaves ficam fora do código e fora do git (`chaves.txt`, ignorado).
- O agente não acessa nada fora de `workspace/` e `dados/`.
- `rodar_comando` só executa comandos da whitelist.
- O free tier do Gemini pode usar prompts para treino — **não envie dados
  sensíveis**.

## Licença

**Uso gratuito, proprietária.** Você pode usar e compartilhar cópias exatas do
HRX CODE de graça, mas **não pode modificar nem vender**. Não é software de
código aberto. Veja os termos completos em [`LICENSE`](LICENSE).

© 2026 Kauê. Todos os direitos reservados.
