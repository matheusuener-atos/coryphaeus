"""
Onde comeca e onde termina o que foi dito - a ferramenta das colecoes novas.

As secoes do nucleo extraem COISAS: um numero, uma data, um valor. Basta
achar o pedaco e guardar. As colecoes de extensao - pedidos, decisoes,
alegacoes, provas - extraem FRASES: o que alguem pediu, o que o juiz decidiu,
o que a parte alegou. E frase tem inicio e fim, e errar o fim e guardar
metade de um pedido ou o pedido seguinte junto.

Em portugues juridico a frase termina de tres jeitos, e todos importam:

    ...requer a citacao do reu;          o ponto e virgula da enumeracao
    ...julgo procedente o pedido.        o ponto final
    ...pela procedencia\\n                a quebra de linha da peticao

O que este modulo existe para nao errar e o ponto que NAO termina frase, que
em documento juridico e a maioria deles: "art. 300", "fls. 23", "R$ 15.000,00",
"Dr. Silva", "n. 1955". Um corte ali entrega "requer, nos termos do art." como
se fosse o pedido inteiro.
"""

from __future__ import annotations

import re
import unicodedata

# Quanto de texto um item de colecao pode ocupar. Acima disso nao e mais uma
# frase: e um paragrafo inteiro entrando na resposta como se fosse um pedido.
CLAUSULA_MAXIMA = 320

# O que parece fim de frase e nao e. Tudo em minuscula e sem acento - a
# comparacao passa por `sem_acento` antes.
ABREVIACOES = {
    "art", "arts", "artigo", "inc", "incs", "par", "n", "no", "num", "fl", "fls",
    "doc", "docs", "p", "pag", "pags", "cf", "obs", "sr", "sra", "srs", "dr",
    "dra", "drs", "exmo", "exma", "ilmo", "ltda", "cia", "s", "a", "etc", "vs",
    "proc", "reg", "cep", "av", "cnpj", "cpf", "rg", "oab", "un", "cx", "ref",
    "esp", "ed", "ap", "ac", "min", "des", "rel", "j", "publ", "dje", "dj",
}

# A pontuacao que fecha uma clausula. O ponto e virgula fecha sozinho porque e
# como peticao separa pedido de pedido; o ponto so fecha quando o que vem
# antes dele nao e abreviacao nem numero.
RE_FECHA = re.compile(r"[.;:!?]\s|\n")

# Palavra no fim de linha que so pode ser continuacao: nenhuma frase em
# portugues termina em "de", "com" ou "que".
LIGACOES = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "ao", "aos",
    "a", "o", "as", "os", "e", "ou", "com", "por", "para", "que", "sob", "sobre",
    "entre", "sem", "ate", "desde", "pelo", "pela", "pelos", "pelas", "um", "uma",
    "seu", "sua", "seus", "suas", "este", "esta", "esse", "essa", "aquele", "nao",
}

# O comeco de um item de lista: "a)", "1.", "I -", "- ", "•".
RE_ENUMERADOR = re.compile(r"^(?:[a-zA-Z]\)|[ivxIVX]{1,4}\s*[-.)]|\d{1,2}\s*[-.)]|[-*•–])\s*")


def sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


def limpo(texto: str) -> str:
    """Numa linha so, que e como o trecho aparece na resposta."""
    return " ".join((texto or "").split())


def chave(texto: str) -> str:
    """A forma de comparar dois trechos para saber se sao o mesmo."""
    return " ".join(sem_acento(texto).split())


def _abrevia(texto: str, ponto: int) -> bool:
    """O ponto em `ponto` pertence a uma abreviacao ou a um numero?"""
    if ponto + 1 < len(texto) and texto[ponto + 1].isdigit():
        return True                       # 15.000, 8.26.0100
    inicio = ponto
    while inicio > 0 and (texto[inicio - 1].isalnum() or texto[inicio - 1] in "º°ª"):
        inicio -= 1
    palavra = sem_acento(texto[inicio:ponto]).strip("º°ª")
    if not palavra:
        return False
    if palavra.isdigit():
        return True                       # "1. requer", "art. 300. Aplica-se"
    return palavra in ABREVIACOES


def _quebra_real(texto: str, posicao: int) -> bool:
    """
    Esta quebra de linha termina a frase, ou e so a linha do PDF acabando?

    Num PDF a frase quebra onde a pagina quebra. "requer a condenacao do\\nreu
    ao pagamento" e uma frase so, e cortar ali entregaria "requer a condenacao
    do" como se fosse o pedido. A quebra que termina frase e a que tem cara
    disso: paragrafo em branco, item de lista comecando, marcador de pagina,
    ou uma linha que ja tinha acabado em pontuacao.
    """
    anterior = texto[:posicao].rstrip()
    if anterior and anterior[-1] in ".;:!?":
        return True
    if anterior and anterior[-1] == ",":
        return False                      # virgula no fim de linha e continuacao
    resto = texto[posicao + 1:]
    if not resto.strip():
        return True
    if resto[:1] == "\n" or resto.lstrip(" \t")[:1] == "\n":
        return True                       # linha em branco: paragrafo novo
    seguinte = resto.lstrip()
    if seguinte[:1] == "[" or RE_ENUMERADOR.match(seguinte):
        return True                       # marcador de pagina ou item de lista
    # Linha terminada em palavra de ligacao e linha que nao acabou: "propor
    # acao em face de\nJOAO DA SILVA" e uma frase so, mesmo com o nome
    # comecando em maiuscula na linha seguinte.
    ultima = sem_acento(anterior).rsplit(None, 1)[-1] if anterior.split() else ""
    if ultima in LIGACOES:
        return False
    # No resto, quem decide e a linha seguinte: continuacao de linha quebrada
    # comeca em minuscula ou em numero; frase nova comeca em maiuscula.
    return not (seguinte[:1].islower() or seguinte[:1].isdigit())


def _fechamento(texto: str, inicio: int, limite: int) -> int:
    """A primeira pontuacao que fecha de verdade, ou -1."""
    posicao = inicio
    while posicao < limite:
        achado = RE_FECHA.search(texto, posicao, limite + 1)
        if not achado:
            return -1
        ponto = achado.start()
        if texto[ponto] == "." and _abrevia(texto, ponto):
            posicao = ponto + 1
            continue
        if texto[ponto] == "\n" and not _quebra_real(texto, ponto):
            posicao = ponto + 1
            continue
        return ponto
    return -1


def fim_da_clausula(texto: str, inicio: int, maximo: int = CLAUSULA_MAXIMA) -> int:
    """
    Onde termina a frase que comeca em `inicio`.

    Sem achar fechamento nenhum dentro do limite, corta na ultima palavra
    inteira: melhor um trecho curto e legivel do que um paragrafo inteiro
    entrando na resposta como se fosse um pedido so.
    """
    limite = min(len(texto), inicio + maximo)
    ponto = _fechamento(texto, inicio, limite)
    if ponto >= 0:
        return min(ponto + 1, limite)
    corte = texto.rfind(" ", inicio, limite)
    return corte if corte > inicio else limite


def inicio_da_frase(texto: str, posicao: int, maximo: int = 240) -> int:
    """
    O comeco da frase que contem `posicao`.

    Serve para as alegacoes: o sujeito vem antes do verbo ("o autor alega
    que..."), e sem ele a citacao perde justamente quem alegou.
    """
    piso = max(0, posicao - maximo)
    melhor, onde = piso, piso
    while onde < posicao:
        ponto = _fechamento(texto, onde, posicao)
        if ponto < 0:
            break
        melhor = onde = ponto + 1
    while melhor < posicao and texto[melhor] in " \t\n\r":
        melhor += 1
    return melhor


def clausula(texto: str, posicao: int, maximo: int = CLAUSULA_MAXIMA) -> tuple[int, int]:
    """Do achado ate o fim da frase dele."""
    return posicao, fim_da_clausula(texto, posicao, maximo)


def frase(texto: str, posicao: int, antes: int = 240,
          depois: int = CLAUSULA_MAXIMA) -> tuple[int, int]:
    """A frase inteira em volta do achado - com o sujeito, quando ele existe."""
    return inicio_da_frase(texto, posicao, antes), fim_da_clausula(texto, posicao, depois)


def itens_da_lista(texto: str, inicio: int, maximo_itens: int = 12,
                   maximo: int = 1800) -> list[tuple[int, int]]:
    """
    Os itens enumerados que vem depois de um dois-pontos.

    "Ante o exposto, requer:" nao e um pedido - e o anuncio de varios. Os
    pedidos estao nas alineas seguintes, e guardar so a frase do verbo
    entregaria uma lista de um item que diz "requer". Aqui cada alinea vira um
    item, e a lista acaba onde a enumeracao acaba: no ponto final, no
    paragrafo em branco, ou quando o texto para de enumerar.
    """
    spans: list[tuple[int, int]] = []
    limite = min(len(texto), inicio + maximo)
    posicao, fechamento_anterior = inicio, ":"
    while posicao < limite and len(spans) < maximo_itens:
        while posicao < limite and texto[posicao] in " \t\r\n":
            posicao += 1
        if posicao >= limite:
            break
        marca = RE_ENUMERADOR.match(texto[posicao:limite])
        if not marca and fechamento_anterior not in (":", ";"):
            break             # parou de enumerar: o que vem depois e outra coisa
        if marca:
            posicao += marca.end()
        fim = fim_da_clausula(texto, posicao, CLAUSULA_MAXIMA)
        if fim <= posicao:
            break
        if len(limpo(texto[posicao:fim])) > 3:
            spans.append((posicao, fim))
        fechamento_anterior = texto[fim - 1:fim].strip() or "\n"
        posicao = fim
        if fechamento_anterior == ".":
            break             # o ponto final fecha a enumeracao
    return spans


def rotulo_por_pista(trecho: str, mapa: dict[str, tuple[str, ...]], padrao: str = "") -> str:
    """
    O rotulo cuja pista aparece PRIMEIRO dentro da frase.

    Aqui, ao contrario dos valores e das datas, a pista esta dentro do proprio
    trecho extraido - nao na vizinhanca dele. E o que vem primeiro e o que
    manda: em "requer a condenacao do reu ao pagamento dos honorarios", o
    pedido e a condenacao; os honorarios sao consequencia dela.
    """
    plano = sem_acento(trecho)
    melhor, mais_cedo = padrao, len(plano) + 1
    for rotulo, pistas in mapa.items():
        for pista in pistas:
            onde = plano.find(pista)
            if 0 <= onde < mais_cedo:
                melhor, mais_cedo = rotulo, onde
    return melhor


def sem_repetir(itens: list, texto_de) -> list:
    """A mesma frase escrita duas vezes no documento entra uma vez so."""
    vistos: set[str] = set()
    saida = []
    for item in itens:
        marca = chave(texto_de(item))
        if not marca or marca in vistos:
            continue
        vistos.add(marca)
        saida.append(item)
    return saida
