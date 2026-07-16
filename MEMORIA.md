# Memória do projeto

Este arquivo guarda decisões e mudanças importantes do HRX CODE de terminal.
Ele serve como histórico curto do projeto e deve ser atualizado sempre que o
comportamento, os comandos ou a configuração mudarem.

## Mudanças recentes

- Prompt de sistema revisado para tornar o agente mais conciso e autônomo em
  ações seguras, exigir leitura do contexto e respeito às convenções antes de
  editar, validar mudanças com testes e ferramentas do projeto, preservar
  alterações existentes e impedir operações Git mutantes sem pedido explícito.
- Política de segurança do prompt reforçada para aceitar somente atividades
  defensivas, educacionais ou de CTF autorizado, com recusa breve e alternativa
  segura para solicitações ofensivas.
- Código-fonte organizado em `src/hrx_code`, com imports relativos, execução
  por `python -m hrx_code` e comando oficial `hrx` definido no pacote.
- Projeto empacotado via `pyproject.toml`, com dependências declaradas e versão
  única em `src/hrx_code/versao.py`; dados persistentes ficam em
  `~/.config/hrx/` para sobreviver a upgrades do pacote.
- Caminhos agora são canonizados antes do uso: leituras bloqueiam escapes por
  `..` e links simbólicos, enquanto escritas fora do projeto são sempre risco
  vermelho e exigem confirmação explícita, inclusive no modo automático.
- Testes avulsos migrados para uma suíte `pytest`, com execução automática no
  GitHub Actions em Python 3.10 a 3.13 e dependências declaradas em arquivos
  `requirements`.
- Suíte ampliada para 94 testes e cobertura automatizada com `pytest-cov`;
  comandos, memória, ferramentas e provedores agora têm testes dedicados, e o
  CI rejeita cobertura total abaixo de 40%.
- Classificador de risco agora tokeniza e normaliza comandos shell, bloqueando
  ofuscação, executores dinâmicos, código inline e padrões destrutivos do
  Windows. O modo `/dry-run` simula ferramentas sensíveis sem executá-las e
  pode ser ativado na inicialização por `HRX_DRY_RUN=1`.
- Projeto renomeado de "JARVIS" para **HRX CODE** (evitar direitos autorais da
  Marvel). Trocado tudo: marca, logo ASCII, backronym, config dir
  (`~/.config/hrx/`), prefixo de env vars (`HRX_`) e comandos (`hrx`,
  `hrx-qwen`).
- O `run.sh` executa o pacote com `.venv/bin/python -m hrx_code`; instalações
  usam o ponto de entrada `hrx_code.agente:main`.
- Licença definida como **proprietária de uso gratuito** (`LICENSE`): livre para
  usar e compartilhar cópias exatas, proibido modificar ou vender. Não é OSS.
- Adicionado `/perfil` (nome, tom, idioma, projeto) persistido em
  `~/.config/hrx/perfil.json`.
- Adicionado `/config` para escolher e persistir o motor de IA.
- Suporte a Gemini, ChatGPT/OpenAI, DeepSeek, Claude, Ollama e motor local.
- Adicionados `/debug` e `/resumo` no terminal.
- Memória persistente entre sessões com `memoria_salvar`, `memoria_listar` e
  `memoria_esquecer`.
- Memória no prompt agora é carregada em modo compacto por padrão, com limite
  de itens e caracteres para gastar menos tokens e permitir sessões maiores.
- Adicionado `/memoria modo compacta|completa` para alternar a injeção da
  memória no contexto sem editar arquivo.
- Adicionados `/memoria compacta`, `/memoria resumir` e `/memoria limpar`.
- Memória agora gera um resumo persistente quando passa do limite configurado,
  preservando os itens mais recentes e reduzindo o custo de contexto.
- `README.md` atualizado para refletir comandos e organização do projeto.
- Motor local padrao definido como `local` e a dica de inicializacao agora
  aponta para `./iniciar-qwen.sh`.
- Modelo local padronizado como `Qwen2.5-7B-Instruct` nas mensagens e na
  documentacao do projeto.

## Regra prática

- Se mudar um comando, uma configuração ou o fluxo do agente, atualize este
  arquivo.
- Se a alteração for visível para o usuário, atualize também o `README.md`.
- Se a mudança for pequena mas relevante, registre uma linha aqui.
