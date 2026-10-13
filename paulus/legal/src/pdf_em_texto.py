"""
PAULUS - Do PDF a um documento editável, só quando pedido (docs/PLANO-EDITOR.md, E1).

PDF não é editável: o que o arquivo guarda são linhas desenhadas na página,
não parágrafos. A importação de antes punha cada linha visual num parágrafo,
com o "[pagina 3]" da extração, o cabeçalho e o rodapé repetidos em toda
página, e a palavra partida pelo hífen no fim da linha - e fazia isso sozinha,
ao abrir o PDF "para editar".

Agora o PDF continua PDF (lido, citado, comentado no visor ao lado) até a
pessoa pedir a versão editável. Quando ela pede, o texto entra limpo:

  - sem as marcas de página, o cabeçalho e o rodapé que se repetem, e o
    número de página solto;
  - as linhas juntadas em parágrafos (a linha que não termina a frase emenda
    na seguinte), a palavra partida no fim da linha reunida;
  - cabeça de cláusula, parágrafo (§), inciso e título em maiúsculas
    abrindo bloco próprio.
"""

from __future__ import annotations

import re
from collections import Counter

RE_PAGINA = re.compile(r"^\[p[aá]gina \d+\]\s*$", re.I)
RE_NUMERO_DE_PAGINA = re.compile(r"^\s*(?:p[aá]g(?:ina)?\.?\s*)?\d{1,4}\s*(?:(?:de|/)\s*\d{1,4})?\s*$", re.I)
RE_ABRE_BLOCO = re.compile(
    r"^\s*(?:cl[aá]usula\s+\S+|\d{1,3}\s*[ªº°]?\s+cl[aá]usula|§\s*\d|par[aá]grafo\s+(?:[uú]nico|\d|primeiro|segundo|"
    r"terceiro)|[IVXLC]{1,6}\s*[-–—.)]\s|[a-z]\)\s|\d{1,3}(?:\.\d{1,3})*\s*[.)\-–—]\s|art\.?\s*\d|"
    r"(?:outorgante|outorgad[oa]|locador|locat[aá]ri[oa]|vendedor(?:es)?|comprador(?:es)?|contratante|contratad[oa]|"
    r"notificante|notificad[oa])\s*:)", re.I)
FIM_DE_FRASE = (".", ":", ";", "!", "?", "”", '"')


def _linhas_por_pagina(texto: str) -> list[list[str]]:
    paginas: list[list[str]] = [[]]
    for linha in (texto or "").splitlines():
        if RE_PAGINA.match(linha.strip()):
            if paginas[-1]:
                paginas.append([])
            continue
        paginas[-1].append(linha.rstrip())
    return [p for p in paginas if any(x.strip() for x in p)]


def _chave(linha: str) -> str:
    """A linha sem números: "Página 3 de 9" e "Página 4 de 9" são a mesma linha de rodapé."""
    return re.sub(r"\d+", "#", " ".join(linha.split()).lower())


def _pontas(pagina: list[str]) -> list[tuple[int, str]]:
    """(posição, linha) das duas primeiras e das duas últimas linhas com texto da página."""
    vivas = [(i, x) for i, x in enumerate(pagina) if x.strip()]
    return vivas[:2] + [v for v in vivas[-2:] if v not in vivas[:2]]


def _repetidas(paginas: list[list[str]]) -> set[str]:
    """
    Cabeçalho e rodapé: a linha curta, numa das pontas da página, que se
    repete em mais da metade das páginas. Só nas pontas - o corpo pode ter
    frase repetida, e frase do corpo não é rodapé.
    """
    if len(paginas) < 3:
        return set()
    contagem: Counter = Counter()
    for p in paginas:
        contagem.update({_chave(x) for _, x in _pontas(p) if _pode_ser_margem(x)})
    return {k for k, n in contagem.items() if n > len(paginas) / 2 and k.strip("# ")}


def _pode_ser_margem(linha: str) -> bool:
    """
    Curta e sem cara de fim de frase do corpo: "acontece de verdade." no alto
    da página é o parágrafo da página anterior terminando, não cabeçalho.
    """
    t = " ".join(linha.split())
    return 0 < len(t) <= 70 and not (t[0].islower() and t[-1] in ".;:,")


def _e_titulo(linha: str) -> bool:
    letras = [c for c in linha if c.isalpha()]
    return 3 < len(letras) and len(linha) <= 90 and sum(1 for c in letras if c.isupper()) / len(letras) > 0.85


def paragrafos(texto: str) -> list[dict]:
    """[{"tipo": "p"|"h2", "texto": "..."}] do texto extraído do PDF."""
    paginas = _linhas_por_pagina(texto)
    fora = _repetidas(paginas)
    linhas: list[str] = []
    for p in paginas:
        nas_pontas = {i for i, _ in _pontas(p)}
        for i, linha in enumerate(p):
            if not linha.strip():
                linhas.append("")
                continue
            if (i in nas_pontas and _chave(linha) in fora) or RE_NUMERO_DE_PAGINA.match(linha):
                continue
            linhas.append(" ".join(linha.split()))
        linhas.append("")      # a página acabou: a frase pode continuar, mas o parágrafo vazio não é um

    saida: list[dict] = []
    atual = ""

    def fechar() -> None:
        nonlocal atual
        if atual.strip():
            saida.append({"tipo": "p", "texto": atual.strip()})
        atual = ""

    for i, linha in enumerate(linhas):
        if not linha:
            # Linha em branco fecha o parágrafo - menos quando a frase claramente
            # continua (a quebra de página no meio da frase).
            proxima = next((x for x in linhas[i + 1:] if x), "")
            if atual and not atual.rstrip().endswith(FIM_DE_FRASE) and proxima[:1].islower():
                continue
            fechar()
            continue
        if _e_titulo(linha) and not RE_ABRE_BLOCO.match(linha):
            fechar()
            saida.append({"tipo": "h2" if len(saida) == 0 else "p", "texto": linha})
            continue
        if RE_ABRE_BLOCO.match(linha):
            fechar()
            # A cabeça da cláusula em maiúsculas ("CLÁUSULA PRIMEIRA – DO
            # OBJETO") é um bloco só dela; o corpo começa na linha seguinte.
            if _e_titulo(linha):
                saida.append({"tipo": "p", "texto": linha})
            else:
                atual = linha
            continue
        if not atual:
            atual = linha
            continue
        anterior = atual.rstrip()
        if anterior.endswith("-") and linha[:1].islower() and re.search(r"[a-zà-ÿ]-$", anterior):
            atual = anterior[:-1] + linha          # pala-\nvra
        elif anterior.endswith(FIM_DE_FRASE) and linha[:1].isupper():
            fechar()
            atual = linha
        else:
            atual = anterior + " " + linha
    fechar()
    return saida


def para_html(texto: str) -> str:
    import html

    return "".join(f"<{p['tipo']}>{html.escape(p['texto'], quote=False)}</{p['tipo']}>" for p in paragrafos(texto))
