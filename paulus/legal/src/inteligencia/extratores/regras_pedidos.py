"""
O que a peca PEDE - a primeira das colecoes de extensao (spec, passo 7).

Numa peticao o pedido nao esta escondido: ele esta escrito com verbo proprio,
quase sempre na mesma frase e quase sempre enumerado. "Requer a citacao do
reu", "pugna pela procedencia", "pleiteia a condenacao". Por isso esta
colecao e regra, e nao modelo: o que um modelo de tres bilhoes de parametros
faria aqui e reescrever com outras palavras o que ja esta escrito com estas -
e reescrever e onde ele erra.

Duas armadilhas do portugues juridico decidem este arquivo.

**O infinitivo nao pede nada.** Uma procuracao diz "confere poderes para
requerer e/ou efetivar toda documentacao". Isso e um poder, nao um pedido -
e o acervo deste escritorio e cheio de procuracoes. O verbo so conta na forma
finita: "requer" pede, "requerer" nao. `\\brequer\\b` nao casa dentro de
"requerer", e e essa a linha que separa as duas coisas.

**"Pede deferimento" nao e pedido.** E a formula de encerramento de toda peca
do pais. Guardada como pedido, ela apareceria em primeiro lugar na resposta a
"quais os pedidos?" - e seria a unica coisa errada numa lista certa.
"""

from __future__ import annotations

import re

from . import frases
from .base import Pedido, Resultado, item_do_span

ID = "request-rules/v1"
SECAO = "requests"
NIVEL = 0
PROMPT_VERSAO = ""

# So a forma finita. O infinitivo (requerer, pedir, pleitear, postular) fica
# de fora de proposito: ele aparece em lista de poderes de procuracao e em
# citacao de lei, e nos dois casos ninguem esta pedindo nada.
RE_PEDIDO = re.compile(
    r"\b(requer(?:-se|-lhe)?|requeiro|requeremos|requerem|requer-se-lhe"
    r"|pede-se|pedem|pedimos|peco"
    r"|pleiteia|pleiteiam|postula|postulam|pugna|pugnam"
    r"|protesta por|requerendo|pugnando|postulando)\b",
    re.IGNORECASE)

# A formula de encerramento, em todas as redacoes que ela tem. Comparada com o
# trecho ja sem acento e numa linha so.
ENCERRAMENTO = (
    "pede deferimento", "pede e espera deferimento", "pede-se deferimento",
    "pedem deferimento", "requer deferimento", "espera deferimento",
    "pede e aguarda deferimento", "nestes termos pede",
)

TIPOS = {
    "injunction": ("tutela de urgencia", "tutela antecipada", "tutela provisoria",
                   "antecipacao de tutela", "liminar", "medida cautelar",
                   "tutela de evidencia"),
    "citation": ("citacao", "cite-se", "citar o reu", "notificacao do", "intimacao do reu"),
    "condemnation": ("condenacao", "condene", "condenar", "seja condenad",
                     "indenizacao", "ressarcimento", "restituicao", "devolucao"),
    "merits": ("procedencia", "julgue procedente", "julgado procedente",
               "acolhimento do pedido", "improcedencia", "julgue improcedente",
               "extincao do processo", "extincao sem"),
    "evidence_production": ("producao de prova", "prova pericial", "prova testemunhal",
                            "prova documental", "depoimento pessoal", "oitiva",
                            "pericia", "juntada de documento", "expedicao de oficio"),
    "free_justice": ("justica gratuita", "gratuidade da justica", "gratuidade judiciaria",
                     "assistencia judiciaria", "beneficio da gratuidade"),
    "fees": ("honorarios", "custas processuais", "sucumbencia", "custas e honorarios"),
    "procedural": ("designacao de audiencia", "audiencia de conciliacao", "vista dos autos",
                   "dilacao de prazo", "prazo suplementar", "suspensao do processo",
                   "arquivamento", "desentranhamento", "prioridade", "segredo de justica",
                   "inversao do onus", "retificacao", "habilitacao", "penhora", "bloqueio"),
}

# Uma peca com mais de tantos pedidos nao e mais uma lista: e o processo
# inteiro. O corte existe para a resposta continuar sendo resposta.
MAXIMO = 40


def _e_encerramento(trecho: str) -> bool:
    plano = frases.chave(trecho).rstrip(".")
    return any(plano.startswith(f) or plano == f for f in ENCERRAMENTO) or len(plano) < 14


def achar(texto: str) -> list[dict]:
    """Cada pedido escrito, com onde ele comeca e onde acaba."""
    achados: list[dict] = []
    for encontro in RE_PEDIDO.finditer(texto or ""):
        inicio = encontro.start()
        fim = frases.fim_da_clausula(texto, inicio)
        trecho = texto[inicio:fim]

        # "Ante o exposto, requer:" anuncia; quem pede sao as alineas.
        if trecho.rstrip().endswith(":"):
            for item_inicio, item_fim in frases.itens_da_lista(texto, fim):
                corpo = texto[item_inicio:item_fim]
                if _e_encerramento(corpo):
                    continue
                achados.append({"inicio": item_inicio, "fim": item_fim,
                                "verb": encontro.group(1).lower(), "texto": corpo})
            continue

        if _e_encerramento(trecho):
            continue
        achados.append({"inicio": inicio, "fim": fim,
                        "verb": encontro.group(1).lower(), "texto": trecho})
    return achados


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        marca = frases.chave(achado["texto"])
        if marca in vistos:
            continue
        vistos.add(marca)
        texto = frases.limpo(achado["texto"]).rstrip(" ;.")
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"request_{len(itens) + 1:03d}",
            dados={"text": texto, "kind": frases.rotulo_por_pista(texto, TIPOS, "other"),
                   "verb": achado["verb"]},
            produzido_por=ID,
        ))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
