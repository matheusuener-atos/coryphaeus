"""
Trechos pela estrutura do documento, e nao por tamanho fixo (I5).

A busca quebrava o texto em blocos de 1.200 caracteres. O bloco cortava onde
o tamanho mandava: a clausula 9 comecava num trecho e terminava no outro, e
quem achava o trecho achava meia clausula - com a multa num pedaco e a
condicao dela no outro. Documento juridico ja vem dividido pelo autor, em
clausulas, secoes e artigos; a divisao dele e a unidade de sentido.

Dois regimes:

- **B - pecas e contratos:** quebra no cabecalho (CLAUSULA, DOS FATOS, DO
  DIREITO, DOS PEDIDOS, DISPOSITIVO, VOTO, EMENTA, numeracao romana e
  decimal). Secao acima de ~1000 tokens vira janelas de ~700 com 96 de
  sobreposicao, sem sair dela; secao abaixo de 80 tokens se junta a vizinha
  inteira.
- **A - leis:** a unidade e o artigo, com os paragrafos e incisos dele.

O que nao se faz nunca: um trecho que termina no meio de uma clausula e
continua na seguinte. Juntar duas secoes pequenas inteiras pode; cortar uma
e emendar na outra, nao.

Cada trecho sabe onde esta: `char_start`/`char_end` no texto extraido, as
paginas (do mapa de layout, src/inteligencia/texto.py), e um `chunk_id`
estavel - o mesmo documento da sempre os mesmos ids, e reindexar do zero
tambem. `text_embed` leva o caminho na frente ("Contrato ACME > CLAUSULA
9a"), para a busca achar a clausula pelo nome do documento.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CHARS_POR_TOKEN = 3
MAXIMO_TOKENS = 1000
JANELA_TOKENS = 700
SOBREPOSICAO_TOKENS = 96
MINIMO_TOKENS = 80

REGIME_PECA = "B"
REGIME_LEI = "A"

# Um cabecalho de peca ou contrato: no comeco da linha, curto, e de um dos
# jeitos que o direito brasileiro escreve secao.
RE_CABECALHO = re.compile(
    r"^[ \t]*(?:"
    r"CL[ÁA]USULA\b[^\n]{0,120}"
    r"|Cl[áa]usula\s+(?:\d+|[A-Za-zçãéêíóôú]+)[ªºa-z]*\b[^\n]{0,120}"
    r"|D[OA]S?\s+(?:FATOS?|DIREITO|PEDIDOS?|FUNDAMENTOS?|PRELIMINAR(?:ES)?|M[ÉE]RITO|PROVAS?|REQUERIMENTOS?|"
    r"TUTELA[^\n]{0,60}|VALOR DA CAUSA|HONOR[ÁA]RIOS[^\n]{0,40}|OBJETO|PRE[ÇC]O|PRAZO|FORO|"
    r"OBRIGA[ÇC][ÕO]ES[^\n]{0,60}|RESCIS[ÃA]O|DISPOSI[ÇC][ÕO]ES[^\n]{0,60}|PARTES)\b[^\n]{0,80}"
    r"|DISPOSITIVO\b|VOTO\b|EMENTA\b|AC[ÓO]RD[ÃA]O\b|RELAT[ÓO]RIO\b|SENTEN[ÇC]A\b|DECIS[ÃA]O\b"
    r"|[IVXLC]{1,6}\s*[-–—.)]\s+[A-ZÀ-Ý][^\n]{0,120}"
    r"|\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+[A-ZÀ-Ý][A-ZÀ-Ý ,;/()-]{3,}[^\n]{0,80}"
    r")[ \t]*$",
    re.M,
)

# Um artigo de lei: "Art. 1º", "Art. 12.", "Artigo 5" no comeco da linha.
RE_ARTIGO = re.compile(r"^[ \t]*(?:Art\.?|Artigo)\s*\d+[ºo°]?[\s.:-]", re.M)


@dataclass
class Fatia:
    """Um pedaco pronto: onde comeca e acaba no texto, e o caminho ate ele."""

    char_start: int
    char_end: int
    caminho: str
    regime: str


def versao_de(sha1: str, texto: str, nome: str = "") -> str:
    """
    A versao do documento, para o `chunk_id`: o sha1 do arquivo (sem ele, o
    do texto) junto com o nome. O mesmo arquivo da o mesmo id em qualquer
    reindexacao; arquivo mudado, id novo - e o trecho antigo nao passa pelo
    novo. O nome entra porque "contrato.pdf" e "contrato (1).pdf" com o mesmo
    conteudo sao dois documentos no Acervo, e um id nao pode apontar para os
    dois.
    """
    base = sha1 or hashlib.sha1((texto or "").encode("utf-8")).hexdigest()
    return hashlib.sha1(f"{base}\0{nome}".encode("utf-8")).hexdigest()[:12]


def chunk_id(versao: str, char_start: int) -> str:
    return f"chunk_{versao}_{char_start:08d}"


def regime_de(texto: str) -> str:
    """Lei (artigos no comeco da linha, e mais deles que clausulas) ou peca/contrato."""
    artigos = len(RE_ARTIGO.findall(texto or ""))
    clausulas = len(re.findall(r"^[ \t]*CL[ÁA]USULA\b|^[ \t]*Cl[áa]usula\s", texto or "", re.M))
    return REGIME_LEI if artigos >= 3 and artigos > clausulas else REGIME_PECA


def _secoes(texto: str, regime: str) -> list[tuple[int, int, str]]:
    """(inicio, fim, titulo) de cada secao; o que vem antes do 1o cabecalho e o preambulo."""
    padrao = RE_ARTIGO if regime == REGIME_LEI else RE_CABECALHO
    marcas = [m for m in padrao.finditer(texto)]
    inicios = [m.start() for m in marcas]
    titulos = [" ".join(texto[m.start():texto.find("\n", m.start()) if texto.find("\n", m.start()) != -1
                              else len(texto)].split())[:80] for m in marcas]
    secoes: list[tuple[int, int, str]] = []
    if not inicios or inicios[0] > 0:
        secoes.append((0, inicios[0] if inicios else len(texto), ""))
    for i, inicio in enumerate(inicios):
        fim = inicios[i + 1] if i + 1 < len(inicios) else len(texto)
        titulo = titulos[i]
        if regime == REGIME_LEI:
            titulo = re.match(r"(?:Art\.?|Artigo)\s*\d+[ºo°]?", titulo.strip()).group(0) if re.match(
                r"(?:Art\.?|Artigo)\s*\d+[ºo°]?", titulo.strip()) else titulo
        secoes.append((inicio, fim, titulo))
    return [(a, b, t) for a, b, t in secoes if texto[a:b].strip()]


def _ajustar(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    """Sem espaco nas pontas: o trecho comeca e termina em texto."""
    while inicio < fim and texto[inicio].isspace():
        inicio += 1
    while fim > inicio and texto[fim - 1].isspace():
        fim -= 1
    return inicio, fim


def _janelas(texto: str, inicio: int, fim: int) -> list[tuple[int, int]]:
    """
    Janelas de ~700 tokens com 96 de sobreposicao, dentro de [inicio, fim) e
    cortando em fim de frase ou de linha - nunca no meio de palavra.
    """
    tamanho = JANELA_TOKENS * CHARS_POR_TOKEN
    sobra = SOBREPOSICAO_TOKENS * CHARS_POR_TOKEN
    saida: list[tuple[int, int]] = []
    atual = inicio
    while atual < fim:
        limite = min(fim, atual + tamanho)
        if limite < fim:
            pedaco = texto[atual:limite]
            corte = max(pedaco.rfind(". "), pedaco.rfind(".\n"), pedaco.rfind(";\n"), pedaco.rfind("\n"))
            if corte < len(pedaco) // 2:
                corte = pedaco.rfind(" ")
            if corte > len(pedaco) // 2:
                limite = atual + corte + 1
        saida.append((atual, limite))
        if limite >= fim:
            break
        proximo = max(atual + 1, limite - sobra)
        # O comeco da janela seguinte tambem cai em palavra inteira.
        espaco = texto.find(" ", proximo, limite)
        atual = espaco + 1 if espaco != -1 else proximo
    return saida


def fatiar(texto: str, titulo: str = "") -> list[Fatia]:
    """
    As fatias do documento, em ordem.

    Secao grande vira janelas dentro dela; secoes pequenas vizinhas se juntam
    inteiras ate passarem do minimo (ou do maximo, o que vier antes).
    """
    texto = texto or ""
    if not texto.strip():
        return []
    regime = regime_de(texto)
    secoes = _secoes(texto, regime)
    minimo = MINIMO_TOKENS * CHARS_POR_TOKEN
    maximo = MAXIMO_TOKENS * CHARS_POR_TOKEN

    # Juntar as pequenas: o grupo cresce so enquanto estiver abaixo do minimo
    # (e o proximo couber inteiro no maximo). Crescer ate o maximo juntaria
    # seis clausulas curtas num trecho so, e a busca devolveria as seis para
    # quem perguntou de uma.
    grupos: list[list[tuple[int, int, str]]] = []
    for secao in secoes:
        # Na lei a unidade e o artigo: juntar artigos seria devolver o art. 4
        # para quem procurou o art. 5. So o preambulo (sem titulo) se junta.
        if regime == REGIME_LEI and grupos and secao[2]:
            grupos.append([secao])
            continue
        if grupos:
            ultimo = grupos[-1]
            tamanho = ultimo[-1][1] - ultimo[0][0]
            if tamanho < minimo and tamanho + (secao[1] - secao[0]) <= maximo:
                ultimo.append(secao)
                continue
        grupos.append([secao])
    # A ultima, se ficou pequena, volta para a anterior.
    if len(grupos) > 1 and regime != REGIME_LEI:
        ultimo = grupos[-1]
        if ultimo[-1][1] - ultimo[0][0] < minimo and ultimo[-1][1] - grupos[-2][0][0] <= maximo:
            grupos[-2].extend(grupos.pop())

    fatias: list[Fatia] = []
    for grupo in grupos:
        inicio, fim = grupo[0][0], grupo[-1][1]
        nomes = [t for _, _, t in grupo if t]
        caminho = " > ".join(p for p in (titulo, " + ".join(nomes[:3]) + (" …" if len(nomes) > 3 else "")) if p)
        if fim - inicio <= maximo:
            a, b = _ajustar(texto, inicio, fim)
            if b > a:
                fatias.append(Fatia(a, b, caminho, regime))
            continue
        # Grupo grande e sempre uma secao so (as grandes nao se juntam).
        for a, b in _janelas(texto, inicio, fim):
            a, b = _ajustar(texto, a, b)
            if b > a:
                fatias.append(Fatia(a, b, caminho, regime))
    return fatias
