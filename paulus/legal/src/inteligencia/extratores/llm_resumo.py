"""
O resumo do documento - e a unica secao que nao e fato.

Tudo o mais nesta camada aponta para um trecho do documento e e conferido
contra ele. Resumo, nao: ele e conclusao do modelo sobre o texto inteiro, e
nao existe span que o sustente. Por isso ele nasce com `extraction_method:
model-inference`, nunca e citado como fonte e, quando entra numa resposta, a
resposta diz que aquilo e leitura do assistente.

Ele existe porque responde barato uma pergunta cara: "do que se trata este
documento?" lida do resumo custa trezentos tokens; lida do documento custa o
documento. E porque, no nivel 1, e ele que evita abrir um processo de 400
paginas para dizer que e uma acao de cobranca.

Duas frases no maximo. Resumo longo vira leitura - e quem quer ler abre o
documento, que continua ali.
"""

from __future__ import annotations

from .base import Pedido, Resultado, limpar

ID = "summarizer/v1"
SECAO = "summary"
NIVEL = 2
PROMPT_VERSAO = "summary/v1"

INSTRUCAO_CURTA = (
    "Escreva UMA frase dizendo do que trata o documento abaixo: que tipo de "
    "documento e, entre quem, e sobre o que. No maximo 25 palavras, em portugues "
    "do Brasil, sem preambulo e sem opiniao. Nao invente nome, valor nem data."
)

INSTRUCAO_LONGA = (
    "Resuma o documento abaixo em ate 3 frases curtas: o que e, entre quem, o que "
    "cada parte se obrigou a fazer e os prazos ou valores principais. Em portugues "
    "do Brasil. Nao invente nada que nao esteja escrito."
)

SISTEMA = (
    "Voce resume documentos juridicos com exatidao. Nao acrescenta clausula, valor, "
    "data ou nome que nao esteja no texto. Responde so o resumo."
)


def extrair(pedido: Pedido) -> Resultado:
    if pedido.client is None:
        return Resultado(status="skipped", erro="sem assistente ligado")

    trecho = pedido.comeco
    try:
        uma = limpar(pedido.client.ask(INSTRUCAO_CURTA + "\n\nDocumento:\n" + trecho, "",
                                       sistema=SISTEMA))
        curto = limpar(pedido.client.ask(INSTRUCAO_LONGA + "\n\nDocumento:\n" + trecho, "",
                                         sistema=SISTEMA))
    except Exception as exc:
        return Resultado(status="failed", erro=str(exc)[:160])

    if not uma and not curto:
        return Resultado(status="failed", erro="o modelo devolveu resumo vazio")

    return Resultado(
        objeto={
            "one_line": uma[:300],
            "short": curto[:900] or None,
            "detailed": None,
            # Fica dito no proprio dado: isto e leitura do modelo, e nao
            # trecho do documento. Quem mostrar isso na tela tem de rotular.
            "certainty": "inferred",
            "verified": False,
            "produced_by": ID,
            "extraction_method": "model-inference",
        },
        modelo=getattr(pedido.client, "model", ""),
    )
