# 🦾 JARVIS — agente de IA de terminal

Agente de IA que roda no terminal, movido pelo **Qwen local** ou pela **API do
Gemini**, com **rotação automática de chaves** (failover), **ferramentas** (arquivos,
planilhas, PDFs) e interface estilizada. Instalável como comando global
`jarvis` no Linux e no Windows.

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

O instalador configura o Qwen local como padrão em `~/.config/jarvis/ambiente`.
O modelo e o executável ficam, por padrão, em `~/agente-ia/bin/modelo.gguf` e
`~/agente-ia/bin/llamafile`. Ajuste esses caminhos nesse arquivo caso necessário.

Para voltar ao Gemini, troque `JARVIS_MOTOR=local` por `JARVIS_MOTOR=gemini` em
`~/.config/jarvis/ambiente` e preencha `~/.config/jarvis/chaves.txt`.

### Windows
Copie a pasta `windows/` (ou o zip gerado) para a máquina e dê dois cliques em
`INSTALAR.bat`. Depois, em um novo terminal: `jarvis`.

## Uso

```bash
jarvis                 # chat interativo
jarvis "sua tarefa"    # pergunta única (one-shot)
```

Comandos no chat: `/motor`, `/chaves` (status das chaves no Gemini), `/limpar`,
`/ajuda`, `/sair`.

## Configuração (`config.py`)

- `NOME` — nome exibido no banner
- `MODELO` — modelo Gemini (padrão `gemini-2.0-flash`)
- `COMANDOS_PERMITIDOS` — whitelist do `rodar_comando`

## Arquitetura

```
agente.py        loop ReAct + interface (rich)
gemini.py        cliente Gemini + pool de chaves com failover
local.py         cliente do endpoint OpenAI-compatível local
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
