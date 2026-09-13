"""
Que documento e este, e de que juizo ele veio.

Duas secoes pequenas, e as duas seguem a mesma ordem: **regra primeiro,
modelo no que sobrar.** O vocabulario de um documento juridico entrega o tipo
dele no cabecalho - "CONTRATO DE PRESTACAO DE SERVICOS", "PROCURACAO",
"NOTIFICACAO EXTRAJUDICIAL" -, e o programa ja sabia fazer isso antes desta
camada existir (src/classify.py). Chamar o modelo para reconhecer o que uma
lista de termos reconhece seria pagar um minuto por documento para acertar
menos.

O modelo entra so quando a regra nao decide - e o resultado dele vem marcado
como deduzido, nunca como explicito: ele nao esta citando o documento, esta
concluindo sobre ele.

Com o assistente desligado a secao continua existindo, com o que a regra
achou. E o desenho de um programa que roda numa maquina onde o modelo as
vezes nao esta ligado.
"""

from __future__ import annotations

import re

from .base import Pedido, Resultado, limpar

ID = "doc-classifier/v1"
SECAO = "classification"
NIVEL = 1
PROMPT_VERSAO = "classification/v1"

# Os tipos que a regra ja conhece (src/classify.py) mapeados para o vocabulario
# do formato. A regra e mais especifica que o formato de proposito - "compra e
# venda" diz mais que "contrato" -, e as duas coisas ficam guardadas: a
# especifica para a tela, a geral para quem ler o metadata de fora.
DA_REGRA = {
    "compra_e_venda": "contract", "locacao": "contract", "prestacao_servicos": "contract",
    "nda": "contract", "distrato": "contract", "trabalhista": "contract",
    "procuracao": "power_of_attorney", "peticao": "court_filing", "outro": "other",
}

# A lista fechada que o modelo pode responder, quando a regra nao decide.
DO_MODELO = {
    "contrato": "contract", "procuracao": "power_of_attorney", "peticao": "court_filing",
    "notificacao": "notice", "recibo": "receipt", "sentenca": "decision",
    "parecer": "legal_opinion", "comprovante": "receipt", "outro": "other",
}

INSTRUCAO = (
    "Diga que TIPO de documento juridico e o texto abaixo. Responda com uma das "
    "palavras: contrato, procuracao, peticao, notificacao, recibo, sentenca, "
    "parecer, outro. Uma palavra so, sem explicar."
)


def extrair(pedido: Pedido) -> Resultado:
    from classify import ROTULOS, detectar_tipo

    bruto = detectar_tipo(pedido.comeco)
    tipo = DA_REGRA.get(bruto, "other")
    rotulo = ROTULOS.get(bruto, "")
    origem, certeza = "regra", "high"

    if bruto == "outro" and pedido.client is not None:
        # O modelo so fala quando a regra nao decide - e mesmo ai a resposta
        # e uma palavra de uma lista fechada, nao texto livre.
        try:
            resposta = pedido.client.ask(
                INSTRUCAO + "\n\nTexto:\n" + pedido.comeco[:2500], "",
                sistema="Voce classifica documentos juridicos. Responda uma palavra so.")
            palavra = re.sub(r"[^a-z]", "", limpar(resposta).lower()[:20])
            if palavra in DO_MODELO and palavra != "outro":
                tipo, bruto, rotulo = DO_MODELO[palavra], palavra, palavra.capitalize()
                origem, certeza = "modelo", "medium"
        except Exception as exc:
            return Resultado(objeto={}, status="failed", erro=str(exc)[:160])

    decidiu = tipo != "other"
    objeto = {
        "document_type": tipo,
        "document_type_br": bruto,
        "rotulo": rotulo,
        "language": "pt-BR",
        "certainty": certeza if decidiu else "unknown",
        # Classificacao e conclusao, nao citacao: ela nao aponta trecho. So
        # entra como fato do nivel 0 quando foi a REGRA que decidiu, pelo
        # vocabulario do proprio documento - ai a evidencia e o texto dele.
        "verified": decidiu and origem == "regra",
        "produced_by": ID,
        "origem": origem,
    }
    return Resultado(objeto=objeto, modelo=(getattr(pedido.client, "model", "") if origem == "modelo" else ""))
