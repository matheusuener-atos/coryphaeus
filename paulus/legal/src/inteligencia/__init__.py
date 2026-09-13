"""
A camada de inteligencia de documentos - `legal-document/v0`.

Isto nao e um sistema novo: e uma camada em cima do que ja existe. O programa
ja le PDF e DOCX, ja quebra em trechos, ja busca por BM25 e ja conversa com o
modelo local. O que faltava era memoria: a mesma pergunta trivial - "quem e o
autor?" - fazia o modelo processar o documento inteiro de novo, toda vez, com
resultado que podia variar entre execucoes.

A camada torna persistente o que ja foi entendido uma vez. Cada documento
ganha um metadata com os fatos conferidos, e quem vai responder consulta o
metadata ANTES de montar contexto. Quando o metadata nao basta, o fluxo de
hoje continua exatamente como e - incluindo ler o documento inteiro.

**A regra de ouro e nunca regredir.** Ausencia de metadata, metadata velho,
campo nao verificado ou duvida do roteador resultam sempre no comportamento
atual. A camada so pode acrescentar caminho rapido, nunca tirar caminho que
ja existe. Por isso ela e ligavel por chave e reversivel a qualquer momento:
com `INTELIGENCIA=0` o programa volta a ser o de antes.

    PERGUNTA -> METADATA -> (se preciso) INDICE -> (se preciso) TRECHOS ->
    (se preciso) DOCUMENTO -> MODELO -> RESPOSTA COM FONTE

Os modulos:

    esquema.py    o formato legal-document/v0 e o que conta como fato
    texto.py      o texto guardado e o mapa de paginas (proveniencia citavel)
    guarda.py     a biblioteca em disco e o indice para achar rapido
    alinhar.py    a conferencia de citacao contra o texto - a barreira
    catalogo.py   quem extrai o que, com qual modelo (configuracao, nao codigo)
    extratores/   um especialista por tarefa: regra primeiro, modelo no resto
    roteador.py   quanto custa responder esta pergunta
    portas.py     os tres pontos de encaixe no programa de hoje
"""

from __future__ import annotations

VERSAO_ESQUEMA = "legal-document/v0"
