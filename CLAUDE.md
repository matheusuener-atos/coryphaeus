# coryphaeus

## Publicar uma versão do PAULUS

Só quando o usuário pedir ("publica", "solta uma versão"). No dia a dia ele testa rodando o app pelo terminal, sem instalar.

Para publicar, chame o agente `publicar` (`.claude/agents/publicar.md`), com os testes passando e tudo no commit. Ele roda `paulus/legal/tools/publicar.py`, que monta o instalador, testa a instalação numa pasta temporária, cria a release no GitHub e atualiza o site e o `atualizacao.json`. Os PAULUS instalados recebem a versão pela atualização automática. Se o agente responder `FALHOU`, conte ao usuário o que falhou e não publique por outro caminho.
