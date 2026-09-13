"""
A que este documento se liga - a sexta colecao de extensao (spec, passo 7).

Esta e a colecao que a spec chama de base para o grafo de conhecimento, e e a
unica das sete cujo valor nao esta na resposta de hoje: esta em poder
perguntar, um dia, "me mostre tudo deste caso" e receber os documentos ligados
em vez de uma busca por palavra. Por enquanto ela responde uma pergunta so, e
util: "este documento fala de algum outro processo?".

O que faz dela uma colecao de regra, e nao de modelo, e que o direito
brasileiro escreve suas ligacoes com formulas fixas:

    distribuido por dependencia aos autos n. X    depende de X
    em apenso ao processo n. X                    apensado a X
    agravo de instrumento contra a decisao ...    recorre de algo
    termo aditivo ao contrato firmado em ...      altera um contrato
    distrato do contrato celebrado em ...         encerra um contrato

Duas decisoes governam o arquivo.

**O proprio processo do documento nao e uma relacao.** O primeiro numero CNJ
valido e o do documento - e o mesmo criterio que `regras_processo` ja usa para
dizer qual e o processo dele. Os OUTROS numeros e que sao referencias a
outros autos. Sem essa regra, todo documento sairia relacionado consigo
mesmo, e o grafo teria um laco em cada no.

**Relacao sem alvo nao e relacao.** "Conforme o termo aditivo" nao liga este
documento a nada: nao diz a que. Entra quem tem o outro lado escrito - um
numero de processo, uma data de celebracao, um documento nomeado -, e o resto
fica de fora, porque uma aresta sem destino e so uma frase.
"""

from __future__ import annotations

import re

from . import frases, regras_processo
from .base import Pedido, Resultado, item_do_span

ID = "relationship-rules/v1"
SECAO = "relationships"
NIVEL = 0
PROMPT_VERSAO = ""

# As formulas de ligacao, e o tipo de aresta que cada uma cria. A ordem aqui
# nao decide nada: quem decide e a pista mais proxima do alvo.
TIPOS = {
    "depends_on": ("por dependencia", "distribuido por dependencia", "preventa",
                   "prevencao"),
    "attached_to": ("em apenso", "apensad", "apensament"),
    # "nos autos de" ficou de fora: ela diz ONDE, nao O QUE. Como pista, ela
    # aparece grudada no numero e ganharia de "agravo de instrumento contra",
    # que esta mais longe e e a que diz qual e a relacao.
    "related_to": ("conexo", "conexa", "conexao com", "continencia", "correlato",
                   "vinculado ao processo", "relativo ao processo"),
    "appeal_of": ("agravo de instrumento contra", "recurso contra", "apelacao contra",
                  "em face da sentenca", "em face da decisao", "recorre da",
                  "embargos de declaracao"),
    "amends": ("termo aditivo", "aditivo ao", "aditamento", "primeiro aditivo",
               "segundo aditivo", "alteracao contratual"),
    "terminates": ("distrato", "rescisao do contrato", "resilicao", "revoga a procuracao",
                   "revogacao do mandato"),
    "substitutes": ("substabelec", "em substituicao ao", "substitui o"),
}

# As formulas que ligam a um documento descrito em vez de a um numero: "termo
# aditivo ao contrato firmado em 12/03/2024". Sem uma delas, um numero de
# processo solto e so uma referencia; com uma delas, e uma aresta com nome.
RE_LIGACAO = re.compile(
    r"\b(termo aditivo|aditivo ao|aditamento ao|alteração contratual"
    r"|distrato|rescis[ãa]o do contrato|resili[çc][ãa]o"
    r"|revoga(?:m|-se)?\s+(?:a|o)\s+(?:procura[çc][ãa]o|mandato|instrumento)"
    r"|substabelec\w*|em substitui[çc][ãa]o ao"
    r"|agravo de instrumento contra|apela[çc][ãa]o contra|recurso contra"
    r"|embargos de declara[çc][ãa]o)",
    re.IGNORECASE)

MAXIMO = 20

# Uma pista depois do numero ainda conta, mas perde para qualquer uma antes.
DEPOIS = 1000


def _tipo_na_frase(texto: str, inicio: int, fim: int, alvo: int,
                   padrao: str = "references_case") -> str:
    """
    Que tipo de ligacao e esta - pela pista mais proxima do numero, na frase.

    Nao serve a janela de tamanho fixo usada nos valores e nas datas: ali a
    pista gruda no achado, aqui ela pode estar no comeco de uma frase longa
    ("Agravo de instrumento contra a decisao proferida em 12/05/2025 nos autos
    da acao de cobranca n. X"). Entao a busca e na frase inteira, e o
    criterio continua o mesmo: a pista antes do alvo vence a pista depois, e a
    mais perto vence a mais longe.
    """
    janela = frases.sem_acento(texto[inicio:fim])
    onde_alvo = alvo - inicio
    melhor, menor = padrao, DEPOIS * 2
    for tipo, pistas in TIPOS.items():
        for pista in pistas:
            comeco = 0
            while True:
                achado = janela.find(pista, comeco)
                if achado < 0:
                    break
                comeco = achado + 1
                termina = achado + len(pista)
                distancia = (onde_alvo - termina if termina <= onde_alvo
                             else achado - onde_alvo + DEPOIS)
                if 0 <= distancia < menor:
                    melhor, menor = tipo, distancia
    return melhor


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []

    # (a) Os numeros de processo que NAO sao o deste documento.
    numeros = regras_processo.achar(texto or "")
    # O processo do documento e o primeiro valido - e, se nenhum fechar o
    # digito verificador, o primeiro que aparecer. E o mesmo criterio que
    # `regras_processo` usa para dizer qual e o processo dele, e tem de ser o
    # mesmo: senao o documento sai relacionado consigo proprio.
    proprio = next((n["numero"] for n in numeros if n["valido"]),
                   numeros[0]["numero"] if numeros else "")
    for achado in numeros:
        if achado["numero"] == proprio:
            continue
        inicio, fim = frases.frase(texto, achado["inicio"], antes=200, depois=120)
        fim = max(fim, achado["fim"])
        achados.append({
            "inicio": inicio, "fim": fim,
            "type": _tipo_na_frase(texto, inicio, fim, achado["inicio"]),
            "target_kind": "case_number", "target": achado["numero"],
            "prioridade": 0,
        })

    # (b) As formulas que ligam a um documento descrito.
    for encontro in RE_LIGACAO.finditer(texto or ""):
        inicio, fim = frases.frase(texto, encontro.start(), antes=60, depois=200)
        trecho = texto[inicio:max(fim, encontro.end())]
        # Sem alvo escrito - uma data, um numero, um "de" que nomeie o outro
        # documento - a frase nao liga este documento a coisa nenhuma.
        if not re.search(r"\d", trecho[encontro.end() - inicio:]):
            continue
        achados.append({
            "inicio": inicio, "fim": max(fim, encontro.end()),
            "type": frases.rotulo_por_pista(frases.sem_acento(trecho), TIPOS, "related_to"),
            "target_kind": "document",
            "target": frases.limpo(trecho[encontro.end() - inicio:])[:120].strip(" ,;."),
            "prioridade": 1,
        })

    return sorted(frases.sem_sobrepor(achados), key=lambda a: a["inicio"])


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        marca = achado["type"] + "|" + frases.chave(achado["target"])
        if marca in vistos:
            continue
        vistos.add(marca)
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"relationship_{len(itens) + 1:03d}",
            dados={"text": frases.limpo(pedido.texto[achado["inicio"]:achado["fim"]]).rstrip(" ;."),
                   "kind": achado["type"], "target_kind": achado["target_kind"],
                   "target": achado["target"]},
            produzido_por=ID))
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
