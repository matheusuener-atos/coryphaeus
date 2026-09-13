"""
O texto do documento, guardado e mapeado: onde cada caractere cai na pagina.

O pipeline atual ja extrai o texto de PDF, DOCX, TXT e MD (src/extract.py) e
depois joga fora tudo o que nao for o texto corrido. Esta camada nao extrai de
novo: ela persiste o que ja foi extraido e acrescenta a unica coisa que
faltava - o **mapa de layout**, a correspondencia entre a posicao de um
caractere e a pagina em que ele esta.

Sem esse mapa nao existe proveniencia citavel. "Esta escrito no documento" e
uma afirmacao que ninguem confere; "p. 12" e uma que qualquer pessoa confere
em cinco segundos. O mapa e pre-requisito da verificacao de span, e a
verificacao e o que separa esta camada de um chute bem formatado.

De onde sai o mapa: o extrator de PDF deste programa ja marca cada pagina com
`[pagina N]` no comeco. Em vez de reabrir o PDF para contar caracteres por
pagina - o que exigiria extrair duas vezes e correr o risco de as duas saidas
diferirem -, o mapa e lido dessas marcas. O texto guardado e byte a byte o
mesmo que o buscador ja usa, e por isso os offsets valem para os dois.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# A marca que src/extract.py poe no comeco de cada pagina do PDF.
RE_MARCA_PAGINA = re.compile(r"^\[pagina (\d+)\]$", re.M)

# O que a normalizacao unifica antes de comparar texto com citacao.
ASPAS = {
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'", "′": "'", "″": '"',
}
TRACOS = {"–": "-", "—": "-", "‒": "-", "―": "-", "−": "-"}
LIGADURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
INVISIVEIS = {"­", "​", "‌", "‍", "﻿"}


@dataclass
class Pagina:
    numero: int
    inicio: int
    fim: int

    def to_dict(self) -> dict:
        return {"pagina": self.numero, "inicio": self.inicio, "fim": self.fim}

    @classmethod
    def from_dict(cls, dados: dict) -> "Pagina":
        return cls(numero=int(dados["pagina"]), inicio=int(dados["inicio"]), fim=int(dados["fim"]))


def mapa_de_paginas(texto: str) -> list[Pagina]:
    """
    Onde comeca e acaba cada pagina, dentro do texto extraido.

    Documento sem pagina - DOCX, TXT, e-mail colado - devolve uma faixa so,
    com numero 0. E a resposta honesta: dizer "p. 1" num .txt seria inventar
    uma pagina que ninguem vai achar no arquivo.
    """
    marcas = list(RE_MARCA_PAGINA.finditer(texto or ""))
    if not marcas:
        return [Pagina(numero=0, inicio=0, fim=len(texto or ""))]

    paginas: list[Pagina] = []
    for i, marca in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        paginas.append(Pagina(numero=int(marca.group(1)), inicio=marca.start(), fim=fim))
    return paginas


def pagina_de(paginas: list[Pagina], posicao: int) -> int | None:
    """A pagina de um caractere. None quando o documento nao tem paginas."""
    for pagina in paginas:
        if pagina.inicio <= posicao < pagina.fim:
            return pagina.numero or None
    return (paginas[-1].numero or None) if paginas else None


@dataclass
class Normalizado:
    """
    O texto preparado para comparar, e o caminho de volta ao original.

    `mapa[i]` e a posicao, no texto original, do caractere `i` do texto
    normalizado. E por ele que um trecho encontrado na forma normalizada vira
    um span citavel no arquivo de verdade: sem o caminho de volta, a citacao
    apontaria para um texto que so existe dentro do programa.
    """

    plano: str
    mapa: list[int]

    def original(self, inicio: int, fim: int) -> tuple[int, int]:
        """A faixa equivalente no texto original, do jeito que ele foi guardado."""
        if not self.mapa:
            return (0, 0)
        inicio = max(0, min(inicio, len(self.mapa) - 1))
        fim = max(inicio + 1, min(fim, len(self.mapa)))
        comeco = self.mapa[inicio]
        # O fim aponta para DEPOIS do ultimo caractere, entao usa-se o ultimo
        # caractere de verdade mais um: senao a citacao sai com uma letra a
        # menos, justamente a que fecha a palavra.
        ultimo = self.mapa[fim - 1]
        return (comeco, ultimo + 1)


def normalizar(texto: str) -> Normalizado:
    """
    O texto sem as diferencas que nao mudam o que esta escrito.

    Um modelo que cita um trecho quase nunca devolve os mesmos bytes: ele
    junta espacos, troca aspas curvas por retas, desfaz a quebra de linha e
    nao repete o hifen que so existia porque a palavra estava partida no fim
    da linha. Comparar sem normalizar reprovaria citacoes corretas - e
    citacao reprovada vira `verified: false`, ou seja, um fato verdadeiro que
    a camada deixa de usar.

    O que NAO se faz aqui: tirar acento e baixar a caixa. "Nao" e "não" sao a
    mesma palavra para buscar, mas a citacao que vai para a tela tem de sair
    como esta no documento - e e o span devolvido daqui que a tela mostra.
    """
    plano: list[str] = []
    mapa: list[int] = []
    i, total = 0, len(texto or "")

    while i < total:
        caractere = texto[i]

        if caractere in INVISIVEIS:
            i += 1
            continue

        # Palavra partida no fim da linha: "consti-\ntuicao" e uma palavra so,
        # e nenhum modelo cita o hifen.
        if caractere == "-":
            adiante = i + 1
            while adiante < total and texto[adiante] in " \t\r":
                adiante += 1
            if adiante < total and texto[adiante] == "\n":
                adiante += 1
                while adiante < total and texto[adiante] in " \t\r":
                    adiante += 1
                if adiante < total and texto[adiante].isalpha():
                    i = adiante
                    continue

        if caractere.isspace():
            if plano and plano[-1] != " ":
                plano.append(" ")
                mapa.append(i)
            i += 1
            continue

        trocado = LIGADURAS.get(caractere) or ASPAS.get(caractere) or TRACOS.get(caractere)
        if trocado is None and unicodedata.category(caractere) == "Mn":
            # Acento solto (texto decomposto) some: ele nao muda a palavra e
            # faria a comparacao falhar contra um modelo que compoe.
            i += 1
            continue
        for letra in (trocado or caractere):
            plano.append(letra)
            mapa.append(i)
        i += 1

    # Espaco no fim nao serve para nada e atrapalha o casamento exato.
    while plano and plano[-1] == " ":
        plano.pop()
        mapa.pop()
    return Normalizado(plano="".join(plano), mapa=mapa)


def trecho_legivel(texto: str, inicio: int, fim: int, folga: int = 0) -> str:
    """O pedaco do original, sem as marcas de pagina, para mostrar na tela."""
    inicio = max(0, inicio - folga)
    fim = min(len(texto), fim + folga)
    bruto = texto[inicio:fim]
    return " ".join(RE_MARCA_PAGINA.sub(" ", bruto).split())
