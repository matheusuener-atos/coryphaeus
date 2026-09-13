"""
O que aconteceu, e quando - a terceira colecao de extensao (spec, passo 7).

A secao `dates` ja guarda as datas do documento, e responde "quando o contrato
foi assinado?". Esta guarda outra coisa: a frase inteira em volta de cada
data, em ordem cronologica. A diferenca parece pequena e nao e.

    dates    2025-08-20  (audiencia)
    events   2025-08-20  "A audiencia de instrucao foi redesignada para o dia
                          20/08/2025, em razao do adiamento requerido pelo reu"

A primeira responde uma pergunta. A segunda responde "o que andou acontecendo
neste processo?", que e a pergunta que alguem faz ao pegar um caso nas maos
pela primeira vez - e que hoje custa ler o documento inteiro.

Duas decisoes que este arquivo carrega:

**Evento e data que o documento NOMEIA.** Esta foi a licao da primeira
medicao: soltos sobre o acervo real, os extratores devolveram coisas como "DO
ESTADO DO PARA 02/09/2026" - um pedaco de cabecalho com uma data dentro -
apresentadas numa linha do tempo como se fossem fatos do caso. Uma data cujo
acontecimento a camada nao consegue nomear nao e um evento: e uma data. E
`dates` ja guarda datas.

Entao a regra e simples e dura: se a frase nao disser o que houve - assinou,
protocolou, venceu, foi publicado, foi designada - a data nao entra aqui.
E a mesma regra que ja governa o resto da camada, aplicada a uma colecao
nova: o rotulo fica vazio em vez de chutar, e o que fica vazio nao responde.

**A ordem e a do calendario, nao a do texto.** As outras colecoes saem na
ordem em que aparecem no documento, que e a ordem da proveniencia. Esta sai
em ordem de data, porque e nisso que uma linha do tempo consiste - e uma
sentenca costuma contar a historia de tras para a frente.
"""

from __future__ import annotations

from . import frases, regras_datas
from .base import Pedido, Resultado, escolher_kind, item_do_span, volta_de

ID = "event-rules/v1"
SECAO = "events"
NIVEL = 0
PROMPT_VERSAO = ""

# O que o documento precisa dizer para a data virar evento. E parecida com a
# tabela de `regras_datas`, e de proposito nao e a mesma: la a pergunta e "que
# data e esta?", aqui e "o que aconteceu?". Por isso entram coisas que nao
# sao tipo de data - nascimento, pagamento, notificacao - e a busca e na frase
# inteira, nao so na vizinhanca do numero.
ACONTECIMENTOS = {
    "signature": ("assinad", "assinou", "assinatura", "celebr", "firmad", "firmou",
                  "pactuad", "outorgad", "subscrit"),
    "filing": ("protocolad", "protocolou", "distribuid", "ajuizad", "ajuizou",
               "peticionad", "juntad", "juntou", "autuad"),
    "publication": ("publicad", "publicou", "diario oficial", "dje", "intimad",
                    "intimacao", "citad"),
    "hearing": ("audiencia", "sessao de julgamento", "designad", "redesignad", "pericia"),
    "deadline": ("prazo", "vencimento", "vence em", "vencer", "vencid", "carencia",
                 "ate o dia", "improrrogavel"),
    "decision": ("julgad", "julgou", "sentenca", "acordao", "decisao", "decidiu",
                 "proferid", "proferiu", "deferid", "indeferid", "homologad"),
    "term": ("vigencia", "vigorar", "validade", "termino", "prorrogad", "rescindid",
             "encerrad", "atualizacao"),
    "notification": ("notificad", "notificou", "notificacao", "cientificad", "comunicad"),
    "payment": ("pagament", "pagou", "pago em", "quitad", "quitou", "liquidad", "deposit"),
    "birth": ("nascid", "nascimento"),
    # O verbo generico de acontecer. Nao e rotulo vazio: o documento esta
    # dizendo que houve algo naquele dia, so nao esta dizendo o que.
    "occurrence": ("ocorreu", "realizad", "realizou", "aconteceu", "houve",
                   "iniciou", "encerrou", "recebeu", "emitid", "emitiu",
                   "expedid", "expediu", "entregue", "entregou"),
}

MAXIMO = 40


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for achado in regras_datas.achar(texto or ""):
        inicio, fim = frases.frase(texto, achado["inicio"])
        # A frase tem de ir ao menos ate o fim da data - uma data no fim de
        # uma frase longa nao pode sair cortada no meio de si mesma.
        fim = max(fim, achado["fim"])
        trecho = texto[inicio:fim]
        # A pista e a MAIS PROXIMA da data, nao a primeira da frase. "A
        # inicial foi protocolada em 14/04/2025 e o reu foi citado em
        # 02/05/2025" e uma frase so com dois eventos diferentes; procurar a
        # primeira pista faria os dois virarem protocolo.
        acontecimento = escolher_kind(volta_de(texto, achado["inicio"]), ACONTECIMENTOS)
        if not acontecimento:
            continue
        achados.append({"inicio": inicio, "fim": fim, "texto": trecho,
                        "date": achado["iso"], "kind": acontecimento})
    achados.sort(key=lambda a: (a["date"], a["inicio"]))
    return achados


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        marca = achado["date"] + "|" + frases.chave(achado["texto"])
        if marca in vistos:
            continue
        vistos.add(marca)
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"event_{len(itens) + 1:03d}",
            dados={"date": achado["date"], "kind": achado["kind"],
                   "text": frases.limpo(achado["texto"]).rstrip(" ;.")},
            produzido_por=ID,
        ))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
