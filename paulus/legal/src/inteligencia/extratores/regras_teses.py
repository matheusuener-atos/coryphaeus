"""
Quem alega o que - a quinta colecao de extensao (spec, passo 7).

Esta e a colecao mais delicada das sete, e vale dizer por que antes de dizer
como. As outras guardam coisas que o documento FEZ: pediu, decidiu, juntou.
Esta guarda o que ele ATRIBUI a alguem - "o autor alega que o servico nao foi
prestado". Sair errado aqui nao produz um dado errado: produz uma afirmacao
que uma das partes nao fez, e num escritorio isso e pior do que nao saber.

Duas travas, e as duas sao deterministicas.

**O verbo tem de vir com "que".** "Alega", "sustenta" e "aduz" sao palavras
que aparecem em portugues juridico fora de qualquer alegacao - "sustentacao
oral", "sustentavel", "aduzir prova". Exigir o "que" da subordinada a poucas
palavras de distancia reduz o achado a construcao que realmente introduz uma
tese: alguem afirma alguma coisa.

**Quem alegou sai da frase, ou nao sai.** "O autor alega que" tem sujeito;
"alega-se que" nao tem. No segundo caso o campo fica vazio, e nao "autor" por
ser o mais provavel - atribuir uma tese a parte errada e exatamente o erro
que esta colecao nao pode cometer. O sujeito e procurado pela proximidade ao
verbo, antes dele de preferencia, porque "Alega o reu que o autor nao pagou"
tem dois papeis na mesma frase e so um deles esta alegando.
"""

from __future__ import annotations

import re

from . import frases
from .base import ALCANCE, Pedido, Resultado, escolher_kind, item_do_span, volta_de

ID = "claim-rules/v1"
SECAO = "claims"
NIVEL = 0
PROMPT_VERSAO = ""

# O verbo de dizer, seguido da subordinada. O "que" pode estar a algumas
# palavras de distancia ("sustenta, ainda, que"), mas nao depois de pontuacao
# forte - dali em diante ja e outra frase.
RE_TESE = re.compile(
    r"\b(alega|alegam|alega-se|sustenta|sustentam|sustenta-se|aduz|aduzem|aduz-se"
    r"|afirma|afirmam|afirma-se|argumenta|argumentam|argumenta-se|assevera|asseveram"
    r"|defende|defendem|narra|narram|noticia|aponta|apontam|invoca|invocam"
    r"|alegou|sustentou|aduziu|afirmou|argumentou|asseverou|apontou)"
    r"\b[^.;:!?]{0,40}?\bque\b",
    re.IGNORECASE)

# Quem, no processo, pode estar alegando. Os nomes proprios ficam de fora de
# proposito: aqui interessa o papel, e o nome ja esta na citacao.
PAPEIS = {
    "plaintiff": ("o autor", "a autora", "os autores", "requerente", "exequente",
                  "demandante", "reclamante", "a inicial", "a peticao inicial",
                  "o credor", "o promovente"),
    "defendant": ("o reu", "a re", "os reus", "requerid", "executad", "demandad",
                  "reclamad", "a contestacao", "a defesa", "o devedor", "o promovido"),
    "court": ("o juiz", "a juiza", "o juizo", "o tribunal", "o relator", "a sentenca",
              "o acordao", "o magistrado"),
    "expert": ("o perito", "a perita", "o laudo", "a pericia", "o assistente tecnico"),
    "witness": ("a testemunha", "as testemunhas", "o depoente"),
    "prosecutor": ("o ministerio publico", "o promotor", "o parquet", "a procuradoria"),
    "third_party": ("o terceiro", "o interessado", "o assistente"),
}

MAXIMO = 40


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for encontro in RE_TESE.finditer(texto or ""):
        verbo = encontro.start()
        inicio, fim = frases.frase(texto, verbo)
        fim = max(fim, encontro.end())
        achados.append({
            "inicio": inicio, "fim": fim, "texto": texto[inicio:fim],
            "verb": frases.limpo(encontro.group(1)).lower(),
            # Pista antes do verbo vence; so na falta dela e que se olha
            # adiante, e ai perto, para pegar "Alega o reu que...".
            "holder": escolher_kind(volta_de(texto, verbo, antes=ALCANCE, depois=30), PAPEIS),
        })
    return achados


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        marca = frases.chave(achado["texto"])
        if len(marca) < 20 or marca in vistos:
            continue
        vistos.add(marca)
        dados = {"text": frases.limpo(achado["texto"]).rstrip(" ;."),
                 "verb": achado["verb"]}
        if achado["holder"]:
            dados["holder"] = achado["holder"]
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"claim_{len(itens) + 1:03d}", dados=dados, produzido_por=ID))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
