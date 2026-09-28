# coryphaeus

## Publicar ao fim de cada implementação

Ao fim de toda implementação bem-sucedida no PAULUS (`paulus/legal`), com os testes passando e o commit feito, chame o agente `publicar` (`.claude/agents/publicar.md`). Ele roda `tools/publicar.py`, que monta o instalador, testa a instalação numa pasta temporária, cria a release no GitHub e atualiza o site e o `atualizacao.json`. Os PAULUS instalados recebem a versão pela atualização automática.

Não chame o agente para mudanças só de documentação, só do site ou que ficaram pela metade. Se ele responder `FALHOU`, conte ao usuário o que falhou e não publique por outro caminho.
