# 🦾 JARVIS — agente de IA de terminal

Agente de IA de terminal com motores **Gemini**, **ChatGPT/OpenAI**,
**DeepSeek**, **Claude**, **Ollama** e **Qwen local**. Tem rotação automática
das chaves Gemini, ferramentas para código e documentos, além de uma interface
estilizada. Instalável como comando global `jarvis` no Linux e no Windows.

> *Just A Rather Very Intelligent System.*

## Recursos

- **Failover de chaves:** pool de N chaves grátis; quando uma estoura o limite
  (HTTP 429), a próxima assume sozinha, com cooldown por chave.
- **Ferramentas (loop ReAct):**
  - `ler_arquivo`, `escrever_arquivo`, `editar_arquivo`, `listar_diretorio`
  - `criar_planilha` (Excel `.xlsx`), `criar_pdf` (PDF com tabela)
  - `rodar_comando` (whitelist de segurança), `buscar_docs` (RAG simples)
- **Sandbox:** o agente só lê/escreve dentro de `workspace/` e lê `dados/`.
- **UI:** banner ASCII, cores e respostas em markdown (via `rich`).
- **Motor local:** Qwen2.5 GGUF em `llamafile`, sem chave, cota ou internet.
- **Motores configuráveis:** escolha o provedor, modelo, URL e chave pelo
  comando `/config`; as credenciais ficam fora do repositório.

## Instalação

### Pré-requisito
Python 3.10+ (no Windows, marque *"Add python.exe to PATH"*).

### Chaves
Pegue chaves grátis em https://aistudio.google.com/apikey e crie o arquivo de
chaves a partir do modelo:

```bash
cp chaves.txt.exemplo chaves.txt   # e cole suas chaves, uma por linha
```

`chaves.txt` está no `.gitignore` — nunca vai para o repositório.

### Linux
```bash
./instalar.sh          # cria os comandos globais 'jarvis' e 'jarvis-qwen'
jarvis-qwen            # em um terminal: inicia o Qwen local
jarvis                 # em outro terminal: abre o chat
```

O modelo e o executável locais ficam, por padrão, em
`~/agente-ia/bin/modelo.gguf` e `~/agente-ia/bin/llamafile`. Depois de abrir o
JARVIS, use `/config` para escolher o motor. A escolha fica em
`~/.config/jarvis/motor.json`; para Gemini, as chaves também podem ser mantidas
em `~/.config/jarvis/chaves.txt`.

### Windows
Copie a pasta `windows/` (ou o zip gerado) para a máquina e dê dois cliques em
`INSTALAR.bat`. Depois, em um novo terminal: `jarvis`.

## Uso

```bash
jarvis                 # chat interativo
jarvis "sua tarefa"    # pergunta única (one-shot)
```

Comandos no chat: `/config` (escolhe e configura o motor), `/motor`, `/chaves`
(status das chaves no Gemini), `/debug`, `/resumo`, `/limpar`, `/ajuda`,
`/sair`.

Use `/config` para selecionar Gemini, ChatGPT/OpenAI, DeepSeek, Claude, Ollama
ou o Qwen/llamafile local. A configuração, incluindo chaves, fica em
`~/.config/jarvis/motor.json` com permissão restrita; reinicie o JARVIS após
salvar para aplicar o novo motor. Se faltar uma chave, o assistente oferece a
configuração ao iniciar.

## Configuração (`config.py`)

- `NOME` — nome exibido no banner
- Use `/config` para trocar motor, modelo, URL e chave sem editar arquivos.
- `COMANDOS_PERMITIDOS` — comandos tratados como seguros pela política

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
instalar.sh / windows/INSTALAR.bat   instaladores
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

MIT.
