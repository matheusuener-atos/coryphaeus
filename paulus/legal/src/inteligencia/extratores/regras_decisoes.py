"""
O que foi DECIDIDO - a segunda colecao de extensao (spec, passo 7).

O dispositivo de uma sentenca brasileira e a parte mais formular de todo o
direito processual. "JULGO PROCEDENTE o pedido", "INDEFIRO a tutela",
"HOMOLOGO o acordo", "NEGO PROVIMENTO ao recurso" - sempre em primeira pessoa,
sempre no comeco da frase, quase sempre em caixa alta. Nada disso precisa de
um modelo para ser encontrado, e a pergunta que isso responde e a mais direta
que um escritorio faz: deu ou nao deu?

O que decide este arquivo e uma propriedade do portugues que aqui trabalha a
favor: **as palavras opostas se contem.** "Indefiro" contem "defiro".
"Improcedente" contem "procedente". Um classificador que procurasse a
primeira pista da lista responderia "deferido" para "INDEFIRO" - e seria o
erro mais caro que esta camada poderia cometer, porque tem exatamente a cara
de uma resposta certa.

A regra que resolve isso e a mesma que ja governa os rotulos das outras
colecoes: vence a pista que aparece MAIS CEDO na frase. Em "INDEFIRO",
"indefiro" comeca na posicao 0 e "defiro" na 2 - entao e indeferimento. Em
"DEFIRO", "indefiro" nao aparece. O mesmo vale para "JULGO PARCIALMENTE
PROCEDENTE", onde "parcialmente" vem antes de "procedente" e a decisao e
parcial. Nao ha lista de excecoes: ha ordem de leitura.
"""

from __future__ import annotations

import re

from . import frases
from .base import Pedido, Resultado, item_do_span

ID = "decision-rules/v1"
SECAO = "decisions"
NIVEL = 0
PROMPT_VERSAO = ""

# Os verbos do dispositivo, em primeira pessoa, mais as formulas do acordao e
# do despacho ordinatorio.
#
# Ficaram de fora de proposito dois que pareceriam obvios: "decreto", porque
# "Decreto no 9.580/2018" e citacao de norma e aparece muito mais do que
# "decreto a revelia"; e "declaro", porque "DECLARO para os devidos fins" e o
# comeco de toda declaracao, que nao decide nada.
RE_DECISAO = re.compile(
    r"\b(julgo|defiro|indefiro|homologo|condeno|absolvo|concedo|denego|extingo"
    r"|acolho|rejeito|revogo|mantenho|reformo|anulo|arbitro os honor[áa]rios"
    r"|(?:dou|nego)\s+(?:parcial\s+)?provimento|acordam"
    r"|cite-se|intime-se|expe[çc]a-se|arquive-se|cumpra-se|publique-se"
    r"|registre-se|manifeste-se|oficie-se)\b",
    re.IGNORECASE)

# A ordem DENTRO de cada tupla nao importa; a posicao no texto sim. Quem
# escolhe e `rotulo_por_pista`, que devolve o rotulo cuja pista comeca mais
# cedo na frase - e e isso que separa "defiro" de "indefiro".
TIPOS = {
    "partial": ("parcialmente", "em parte", "parcial provimento"),
    "merits_denied": ("improcedente", "improcedencia"),
    "merits_granted": ("procedente", "procedencia"),
    "denied": ("indefiro", "nego provimento", "negar provimento", "denego",
               "rejeito", "nao acolho", "improver"),
    "granted": ("defiro", "concedo", "dou provimento", "dar provimento", "acolho",
                "prover o recurso"),
    "homologated": ("homologo", "homologar", "homologacao"),
    "extinguished": ("extingo", "extinto", "extincao", "extinta"),
    "conviction": ("condeno", "condenar", "condenacao"),
    "acquittal": ("absolvo", "absolver"),
    "order": ("cite-se", "intime-se", "expeca-se", "expeda-se", "arquive-se",
              "cumpra-se", "publique-se", "registre-se", "manifeste-se", "oficie-se"),
}

MAXIMO = 30


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for encontro in RE_DECISAO.finditer(texto or ""):
        inicio = encontro.start()
        fim = frases.fim_da_clausula(texto, inicio)
        trecho = texto[inicio:fim]
        # "Publique-se. Registre-se. Intime-se." fecha toda sentenca do pais e
        # nao decide nada - e o "pede deferimento" do outro lado do balcao.
        # O verbo sozinho e formula; o verbo com objeto ("Intime-se o reu para
        # pagar em 15 dias") e determinacao, e essa fica.
        sobra = frases.chave(trecho[encontro.end() - inicio:]).strip(" .;,-")
        if len(sobra) < 4:
            continue
        achados.append({"inicio": inicio, "fim": fim, "texto": trecho,
                        "verb": frases.limpo(encontro.group(1)).lower()})
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
            id_=f"decision_{len(itens) + 1:03d}",
            # `kind` aqui E o desfecho: e o campo que o roteador sabe filtrar
            # em qualquer colecao, e guardar a mesma coisa duas vezes com dois
            # nomes seria criar duas versoes da verdade para manter iguais.
            dados={"text": texto, "kind": frases.rotulo_por_pista(texto, TIPOS, "other"),
                   "verb": achado["verb"]},
            produzido_por=ID,
        ))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
