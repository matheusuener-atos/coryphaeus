"""
Dinheiro e percentual em inteiros, do texto da tela ao XML da nota.

Centavo é inteiro. Alíquota é inteiro em pontos-base (1% = 100). A conta
"valor × alíquota" é feita em inteiros e dividida uma vez só, com o
arredondamento que a documentação manda: o bancário (half-even), que a NT 007
fixou para PIS e COFINS e o PAULUS usa em toda a conta para ela ser uma só.

Não há `float` neste módulo, nem em nenhum caminho do dinheiro da nota: o
`financeiro.para_centavos` passa por float e por isso não é usado aqui.
"""

from __future__ import annotations

import re


def centavos_de_texto(texto) -> int:
    """
    "5.000,00", "5000", "R$ 1.234,5" -> centavos inteiros, lendo como se
    escreve no Brasil (ponto de milhar, vírgula decimal). Sem float.
    """
    if isinstance(texto, bool):
        raise ValueError("valor inválido")
    if isinstance(texto, int):
        return texto
    t = str(texto or "").strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if not t:
        return 0
    negativo = t.startswith("-")
    t = t.lstrip("-")
    if "," in t:
        inteiro, _, frac = t.rpartition(",")
        inteiro = inteiro.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        inteiro, frac = t.replace(".", ""), ""
    elif re.fullmatch(r"\d+\.\d{1,2}", t):
        inteiro, _, frac = t.partition(".")
    else:
        inteiro, frac = t, ""
    if not re.fullmatch(r"\d+", inteiro or "0") or not re.fullmatch(r"\d{0,2}", frac):
        raise ValueError(f"valor inválido: {texto}")
    n = int(inteiro or "0") * 100 + int((frac + "00")[:2])
    return -n if negativo else n


def reais(centavos: int) -> str:
    """5000000 -> "R$ 50.000,00"."""
    c = int(centavos)
    sinal = "-" if c < 0 else ""
    inteiro, resto = divmod(abs(c), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def decimal_xml(centavos: int) -> str:
    """O formato do XSD (TSDec15V2): 0, ou "5000.00" — ponto decimal, 2 casas."""
    c = int(centavos)
    if c < 0:
        raise ValueError("valor negativo não vai na nota")
    if c == 0:
        return "0"
    inteiro, resto = divmod(c, 100)
    return f"{inteiro}.{resto:02d}"


def centavos_do_xml(texto: str) -> int:
    """O caminho de volta: "5000.00" (ou "5000") -> 500000."""
    t = str(texto or "").strip()
    if not t:
        return 0
    m = re.fullmatch(r"(\d+)(?:\.(\d{1,2}))?", t)
    if not m:
        raise ValueError(f"valor inválido no XML: {texto}")
    return int(m.group(1)) * 100 + int(((m.group(2) or "") + "00")[:2])


def percentual_xml(bp: int) -> str:
    """Pontos-base no formato do XSD (TSDec1V2 e TSDec2V2/3V2): 500 -> "5.00"."""
    b = int(bp)
    if b < 0:
        raise ValueError("percentual negativo")
    if b == 0:
        return "0"
    return f"{b // 100}.{b % 100:02d}"


def bp_do_xml(texto: str) -> int:
    return centavos_do_xml(texto)  # mesma forma: duas casas decimais


def percentual_texto(bp: int) -> str:
    """500 -> "5,00%"."""
    b = int(bp)
    return f"{b // 100},{b % 100:02d}%"


def dividir_half_even(numerador: int, denominador: int) -> int:
    """numerador / denominador arredondado ao inteiro mais próximo, empate
    para o par (arredondamento bancário). Só inteiros."""
    if denominador <= 0:
        raise ValueError("denominador inválido")
    negativo = numerador < 0
    q, r = divmod(abs(numerador), denominador)
    dobro = 2 * r
    if dobro > denominador or (dobro == denominador and q % 2 == 1):
        q += 1
    return -q if negativo else q


def aplicar(centavos: int, bp: int) -> int:
    """centavos × alíquota (em pontos-base), em centavos, half-even."""
    return dividir_half_even(int(centavos) * int(bp), 10000)
