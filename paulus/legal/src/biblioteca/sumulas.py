"""
Súmulas e enunciados: um trecho por enunciado (M2).

Uma lista de súmulas cortada em blocos de tamanho fixo junta a Súmula 331 com
metade da 332 - e a busca devolve a errada para quem perguntou da certa. Cada
enunciado é uma unidade de sentido, como o artigo da lei.
"""

from __future__ import annotations

import re

from trechos import Fatia, _ajustar

RE_ENUNCIADO = re.compile(
    r"^[ \t]*(?:S[ÚU]MULA|S[úu]mula|ENUNCIADO|Enunciado|OJ|Orienta[çc][ãa]o Jurisprudencial)"
    r"(?:\s+Vinculante)?\s*(?:n[º°o.]*\s*)?(\d{1,4})\b", re.M)


def parece_sumulas(texto: str) -> bool:
    return len(RE_ENUNCIADO.findall(texto or "")) >= 5


def fatiar(texto: str, titulo: str = "") -> list[Fatia]:
    marcas = list(RE_ENUNCIADO.finditer(texto or ""))
    fatias = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        a, b = _ajustar(texto, m.start(), fim)
        if b > a:
            rotulo = " ".join(texto[m.start():m.end()].split())
            fatias.append(Fatia(a, b, " > ".join(p for p in (titulo, rotulo) if p), "S"))
    return fatias
