"""
RTF virando texto puro, sem biblioteca: o bastante para os livros oficiais
(o "Livro de Súmulas, OJs e PNs" do TST vem em RTF, e o PDF dele quebra as
palavras na extração - "poss í-vel"). Lê os grupos, pula os destinos que não
são texto (fontes, cores, estilos, figuras, campos ocultos) e traduz os
escapes de caractere (\\'e9, \\u233?) e de parágrafo.

    texto = rtf_em_texto.converter(Path("livro.rtf").read_bytes())
"""

from __future__ import annotations

import re

# Grupos que não são texto do documento.
DESTINOS_FORA = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "themedata", "colorschememapping",
    "latentstyles", "datastore", "xmlnstbl", "listtable", "listoverridetable", "rsidtbl", "generator",
    "header", "headerl", "headerr", "headerf", "footer", "footerl", "footerr", "footerf", "fldinst",
    "filetbl", "revtbl", "pgdsctbl", "mmathPr", "wgrffmtfilter", "xmlopen", "fchars", "lchars",
    "bkmkstart", "bkmkend", "pnseclvl", "pntext", "pntxta", "pntxtb", "listtext", "protusertbl",
    "defchp", "defpap", "aftnsep", "aftnsepc", "ftnsep", "ftnsepc", "ftncn", "aftncn", "shp", "shpinst",
    "nonshppict", "blipuid", "panose", "falt", "atnid", "atnauthor", "annotation", "author", "operator",
}
ESPECIAIS = {"par": "\n", "line": "\n", "sect": "\n", "page": "\n", "row": "\n", "cell": " | ", "tab": "\t",
             "emdash": "—", "endash": "–", "lquote": "‘", "rquote": "’", "ldblquote": "“", "rdblquote": "”",
             "bullet": "•", "emspace": " ", "enspace": " ", "qmspace": " ", "~": "\xa0", "-": "", "_": "-"}

RE_TOKEN = re.compile(rb"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\([^a-zA-Z])|([{}])|([^\\{}\r\n]+)|[\r\n]+")


def converter(bruto: bytes, codificacao: str = "cp1252") -> str:
    pilha: list[tuple[bool, int]] = []
    pular = False          # dentro de um destino que não é texto
    uc = 1                 # quantos caracteres de reserva seguem um \uN
    a_pular = 0
    saida: list[str] = []
    asterisco = False      # o grupo começou com \* (destino opcional desconhecido)
    for m in RE_TOKEN.finditer(bruto):
        palavra, numero, hexa, simbolo, chave, texto = m.groups()
        if chave == b"{":
            pilha.append((pular, uc))
            asterisco = False
            continue
        if chave == b"}":
            pular, uc = pilha.pop() if pilha else (False, 1)
            continue
        if a_pular and (texto or hexa):
            # O caractere de reserva depois de \uN (o "?" de \u233?).
            if texto:
                consumido = min(a_pular, len(texto))
                texto = texto[consumido:]
                a_pular -= consumido
                if not texto:
                    continue
            else:
                a_pular -= 1
                continue
        if simbolo:
            s = simbolo.decode("latin-1")
            if s == "*":
                asterisco = True
                continue
            if not pular:
                saida.append(ESPECIAIS.get(s, s if s in "\\{}" else ""))
            continue
        if palavra:
            nome = palavra.decode("ascii")
            if asterisco or nome in DESTINOS_FORA:
                pular = True
                asterisco = False
                continue
            if nome == "uc" and numero:
                uc = int(numero)
            elif nome == "u" and numero and not pular:
                n = int(numero)
                saida.append(chr(n + 65536 if n < 0 else n))
                a_pular = uc
            elif not pular and nome in ESPECIAIS:
                saida.append(ESPECIAIS[nome])
            continue
        if hexa and not pular:
            saida.append(bytes([int(hexa, 16)]).decode(codificacao, errors="replace"))
            continue
        if texto and not pular:
            saida.append(texto.decode(codificacao, errors="replace"))
    texto = "".join(saida)
    texto = re.sub(r"[ \t\xa0]+\n", "\n", texto)
    return re.sub(r"\n{3,}", "\n\n", texto)
