"""
O que o documento junta e o que ele chama de prova - a quarta colecao de
extensao (spec, passo 7).

A pergunta que isto responde e das mais praticas que existem: "o que foi
juntado nesse processo?". Hoje ela custa ler o documento inteiro para ir
catando "(doc. 01)", "fls. 45", "conforme laudo pericial" - e o que se procura
esta escrito numa notacao que o direito brasileiro padronizou ha um seculo.

Duas decisoes governam este arquivo.

**O item e a referencia com o que ela nomeia, nao a frase toda.** "Junta-se o
contrato assinado (doc. 01), as notas fiscais (docs. 02/04) e o comprovante de
notificacao (doc. 05)" e uma frase so com tres documentos. Guardar a frase
inteira tres vezes daria uma lista de tres itens iguais; guardar so "doc. 01"
daria uma lista que nao diz o que e cada um. Entao cada referencia recua ate o
separador anterior - virgula, parentese ou comeco de frase - e leva consigo
exatamente o pedaco que a nomeia.

**Prova pedida nao e prova juntada.** "Requer a producao de prova pericial" e
um pedido; "conforme laudo pericial de fls. 120" e uma prova. As duas coisas
aparecem com as mesmas palavras, e confundi-las faria a camada responder
"houve pericia" sobre um processo em que ela so foi requerida. Aqui as duas
entram - porque as duas estao escritas -, mas cada item diz qual e qual, e o
rotulo da resposta sai com "(requerida)" quando for o caso.
"""

from __future__ import annotations

import re

from . import frases
from .base import Pedido, Resultado, item_do_span
from .regras_pedidos import RE_PEDIDO

ID = "evidence-rules/v1"
SECAO = "evidence"
NIVEL = 0
PROMPT_VERSAO = ""

# A notacao forense de referencia a documento: "doc. 01", "docs. 02/04",
# "fls. 45", "fls. 120/135", "anexo II", "em anexo".
RE_REFERENCIA = re.compile(
    r"\b(docs?\.\s*n?[ºo°]?\s*[\dIVXivx]+(?:\s*[/-]\s*[\dIVXivx]+)?"
    r"|fls?\.\s*\d+(?:\s*[/-]\s*\d+)?"
    r"|anexos?\s+[IVX\d]+|em anexo)",
    re.IGNORECASE)

# Os meios de prova, pelo nome que o processo civil brasileiro lhes da. Nomes
# genericos demais ficaram de fora: "testemunha" sozinha pegaria o bloco de
# assinaturas de todo contrato, e "extrato" pegaria a tela de extrato deste
# proprio programa quando ela aparecer num documento.
RE_TIPO = re.compile(
    r"\b(prova\s+(?:documental|testemunhal|pericial|emprestada|oral)"
    r"|laudo(?:\s+pericial)?|per[íi]cia|per[íi]cia\s+cont[áa]bil"
    r"|depoimento(?:\s+pessoal)?|oitiva|rol de testemunhas"
    r"|certid[ãa]o|nota fiscal|notas fiscais|comprovante"
    r"|extrato banc[áa]rio|boletim de ocorr[êe]ncia"
    r"|parecer t[ée]cnico|vistoria|fotografias?|grava[çc][ãa]o)",
    re.IGNORECASE)

TIPOS = {
    "expert": ("pericia", "laudo", "parecer tecnico", "vistoria", "prova pericial"),
    "witness": ("prova testemunhal", "oitiva", "rol de testemunhas", "prova oral"),
    "testimony": ("depoimento",),
    "document": ("doc.", "docs.", "fls.", "fl.", "anexo", "em anexo", "prova documental",
                 "certidao", "nota fiscal", "notas fiscais", "comprovante",
                 "extrato bancario", "boletim de ocorrencia", "fotografia", "gravacao"),
}

# Quanto se recua a partir da referencia para pegar o que ela nomeia. Mais que
# isso ja e a frase anterior falando de outro documento.
RECUO = 130

# O separador que fecha o pedaco anterior: a virgula e o parentese sao o que
# separa um documento do outro dentro da mesma frase.
SEPARADORES = ",;:()[]\n"

MAXIMO = 40


def _recuar(texto: str, posicao: int) -> int:
    """
    Do achado para tras, ate o que o nomeia.

    O parentese aberto imediatamente antes nao e separador: "(doc. 01)" e a
    referencia do que veio antes dele, e parar ali entregaria "doc. 01" sem
    dizer que documento e.
    """
    piso = max(0, posicao - RECUO)
    limite = posicao
    while limite > piso and texto[limite - 1] in " \t":
        limite -= 1
    if limite > piso and texto[limite - 1] in "([":
        limite -= 1                       # o parentese da referencia nao conta
    melhor = piso
    for i in range(limite - 1, piso - 1, -1):
        if texto[i] in SEPARADORES:
            melhor = i + 1
            break
    while melhor < posicao and texto[melhor] in " \t\n\r":
        melhor += 1
    return melhor


def achar(texto: str) -> list[dict]:
    """
    Os dois jeitos de uma prova aparecer, e quem ganha quando os dois acham.

    A referencia vem primeiro (`prioridade` 0) porque ela e precisa: ela marca
    UM documento. O nome do meio de prova vem depois porque ele e amplo -
    "prova documental, testemunhal e pericial" e uma enumeracao que so faz
    sentido inteira, e se ela ganhasse de uma referencia engoliria os outros
    documentos da mesma frase.
    """
    candidatos: list[dict] = []
    for encontro in RE_REFERENCIA.finditer(texto or ""):
        fim = encontro.end()
        if texto[fim:fim + 1] in (")", "]"):
            fim += 1
        candidatos.append({"inicio": _recuar(texto, encontro.start()), "fim": fim,
                           "ref": frases.limpo(encontro.group(0)), "prioridade": 0})
    for encontro in RE_TIPO.finditer(texto or ""):
        candidatos.append({"inicio": _recuar(texto, encontro.start()),
                           "fim": max(frases.fim_da_clausula(texto, encontro.end(), 200),
                                      encontro.end()),
                           "ref": "", "prioridade": 1})
    return sorted(frases.sem_sobrepor(candidatos), key=lambda c: c["inicio"])


# Ate onde se procura o verbo que transforma prova em pedido de prova. Uma
# lista de alineas ("a) ...; b) ...") separa por ponto e virgula e pode ficar
# longe do "requer:" que a anunciou.
ALCANCE_DO_PEDIDO = 400


def _pedida(texto: str, inicio: int, fim: int) -> bool:
    """
    A prova esta sendo pedida, ou apresentada?

    Quem responde e o verbo do pedido antes dela - mas so enquanto a frase nao
    tiver acabado. "Requer: a) a pericia contabil" e pedido mesmo com a alinea
    sem verbo proprio; "Requer a citacao. Conforme laudo de fls. 120" nao e -
    o ponto encerrou o pedido, e o laudo ja e outra coisa.
    """
    piso = max(0, inicio - ALCANCE_DO_PEDIDO)
    ultimo = None
    for encontro in RE_PEDIDO.finditer(texto, piso, fim):
        if encontro.start() < fim:
            ultimo = encontro
    if ultimo is None:
        return False
    if ultimo.start() >= inicio:
        return True                       # o verbo esta dentro do proprio trecho
    return not frases.terminou_a_frase(texto, ultimo.end(), inicio)


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        trecho = frases.limpo(pedido.texto[achado["inicio"]:achado["fim"]]).strip(" ,;.")
        marca = frases.chave(trecho)
        if len(marca) < 6 or marca in vistos:
            continue
        vistos.add(marca)
        dados = {
            "text": trecho,
            "kind": frases.rotulo_por_pista(trecho, TIPOS, "document"),
            "stated": ("requested"
                       if _pedida(pedido.texto, achado["inicio"], achado["fim"])
                       else "produced"),
        }
        if achado["ref"]:
            dados["ref"] = achado["ref"]
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"evidence_{len(itens) + 1:03d}", dados=dados, produzido_por=ID))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
