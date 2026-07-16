# Changelog

Todas as mudanças relevantes do HRX Code serão registradas neste arquivo.

## [Não publicado]

### Alterado

- Código-fonte migrado para o pacote `src/hrx_code` com imports relativos.
- CLI também pode ser iniciada com `python -m hrx_code`.
- Testes atualizados para validar a API do pacote e o novo ponto de entrada.

## [0.1.0] - 2026-07-16

### Adicionado

- CLI instalável pelo comando `hrx`.
- Loop ReAct com ferramentas de código, terminal, Git, web e documentos.
- Suporte a Gemini, OpenAI, DeepSeek, Groq, Claude, Ollama e modelos locais.
- Rotação de chaves Gemini com cooldown e failover automático.
- Memória persistente, perfis e comandos customizados.
- Classificação de risco em três níveis e autorização de uso único.
- Isolamento de caminhos, proteção contra symlinks e validação contra SSRF.
- Suíte com 56 testes executada em quatro versões do Python.

[Não publicado]: https://github.com/kaue34381210-star/hrx-code/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kaue34381210-star/hrx-code/releases/tag/v0.1.0
