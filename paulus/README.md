# PAVLVS · Produto jurídico da Atos

O **PAVLVS** reúne assistente de IA, documentos e rotinas de escritório na
máquina do cliente, com integrações e processamento em nuvem conforme a
configuração. PAULUS é o nome preservado nos arquivos, comandos e versões.

O aplicativo está em [`legal/`](legal/). A base Coryphaeus e os serviços do
produto permanecem no [mesmo repositório](../README.md).

## Recursos implementados

| Área | Implementação presente |
| --- | --- |
| Documentos | Acervo, importação, organização, extração e OCR do Windows |
| Assistente | Busca, conversa sobre documentos e rotas locais ou de nuvem |
| Produção | Editor, geração de documentos e assinatura de PDF |
| Escritório | Clientes, serviços, equipe, tarefas, agenda, horas e financeiro |
| Consulta e conexões | Biblioteca jurídica, processos/publicações, e-mail, Drive, acesso remoto e MCP |
| Operação | Instalador Windows, atualização, backup, restauração e diagnóstico |

“Implementado” indica código e testes existentes, não homologação de todas
as integrações nem prova de uso por clientes. Veja o
[estado atual e os limites](legal/docs/ESTADO-ATUAL.md).

## Tecnologia e privacidade

Backend Python/FastAPI, interface web compartilhada com a janela Windows
(pywebview/WebView2), persistência local em SQLite e arquivos. A recuperação
de documentos combina regras e índices; Ollama é um caminho de inferência
local. Os serviços do produto usam Cloudflare Workers.

A nuvem do plano tem preferência quando ativada e consentida, e há opções
com chave própria. Portanto, “100% local” não descreve todas as configurações.
Os provedores, as funcionalidades habilitadas, os bloqueios por origem do
documento e o registro dos envios dependem da configuração do escritório.

## Executar e acompanhar

- [Guia de instalação e execução](legal/docs/QUICKSTART.md).
- [Aplicativo e demonstração](legal/README.md).
- [Testes essenciais e contribuição](legal/CONTRIBUTING.md).
- [Piloto delimitado no portfólio](https://github.com/matheusuener-atos/coryphaeus/issues/1).

A próxima entrega proposta é validar um fluxo completo em um escritório,
com instalação reproduzível, documentos de teste, conferência das fontes e
registro de tempo e falhas. Não há prazo de primeira venda inferido do código.
