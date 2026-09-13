"""
O numero do processo - a unica coisa deste sistema que se confere sozinha.

O numero unico do CNJ (Resolucao 65/2008) tem a forma

    NNNNNNN-DD.AAAA.J.TR.OOOO

e os dois digitos do meio sao verificadores: eles sao calculados a partir do
resto pelo modulo 97 base 10 (ISO 7064). Isso muda tudo. Em qualquer outro
campo, "achei" significa "encontrei algo com esta cara"; aqui significa
"encontrei algo que so pode ter sido gerado por um tribunal, porque a conta
fecha". Um digito errado - de leitura de OCR, de digitacao, de um modelo
alucinando - derruba a verificacao.

Por isso a regra de ouro deste modulo: **um modelo de linguagem nunca emite
numero de processo.** Ele pode apontar onde o numero aparece; quem le o numero
e uma expressao regular, e quem diz se ele e valido e a aritmetica.
"""

from __future__ import annotations

import re

from .base import Pedido, Resultado, item_do_span

ID = "case-number-rules/v1"
SECAO = "case"
NIVEL = 0
PROMPT_VERSAO = ""

# A forma pontuada, que e como aparece em peca e em capa de processo.
RE_CNJ = re.compile(r"\b(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})\b")

# A forma crua, que e como sai de sistema e de planilha. Exigir os 20 digitos
# seguidos evita casar com CNPJ, telefone ou numero de nota.
RE_CNJ_CRU = re.compile(r"(?<!\d)(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})(?!\d)")

# Os segmentos do Judiciario, para a tela poder dizer de onde veio o processo.
JUSTICAS = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}


def digito_verificador(numero: str, ano: str, justica: str, tribunal: str, origem: str) -> str:
    """
    Os dois digitos que o CNJ calcula - modulo 97 base 10, ISO 7064.

    A conta e: junta-se o numero sequencial, o ano, o segmento, o tribunal e a
    origem, acrescentam-se dois zeros no lugar do verificador, e o digito e
    98 menos o resto da divisao por 97.
    """
    corpo = f"{numero}{ano}{justica}{tribunal}{origem}00"
    return f"{98 - (int(corpo) % 97):02d}"


def valido(numero: str, dv: str, ano: str, justica: str, tribunal: str, origem: str) -> bool:
    return digito_verificador(numero, ano, justica, tribunal, origem) == dv


def formatar(numero: str, dv: str, ano: str, justica: str, tribunal: str, origem: str) -> str:
    return f"{numero}-{dv}.{ano}.{justica}.{tribunal}.{origem}"


def achar(texto: str) -> list[dict]:
    """Todos os numeros de processo do texto, com posicao e validade."""
    achados: list[dict] = []
    vistos: set[str] = set()

    for regex, pontuado in ((RE_CNJ, True), (RE_CNJ_CRU, False)):
        for encontro in regex.finditer(texto or ""):
            numero, dv, ano, justica, tribunal, origem = encontro.groups()
            formatado = formatar(numero, dv, ano, justica, tribunal, origem)
            if formatado in vistos:
                continue
            # Ano de processo fora de 1900-2099 e quase sempre outra coisa com
            # vinte digitos - uma chave de nota fiscal, por exemplo.
            if not ("1900" <= ano <= "2099"):
                continue
            vistos.add(formatado)
            achados.append({
                "numero": formatado,
                "valido": valido(numero, dv, ano, justica, tribunal, origem),
                "ano": int(ano),
                "justica": JUSTICAS.get(justica, ""),
                "tribunal": tribunal,
                "pontuado": pontuado,
                "inicio": encontro.start(),
                "fim": encontro.end(),
            })
    return sorted(achados, key=lambda a: a["inicio"])


def extrair(pedido: Pedido) -> Resultado:
    """
    A secao `case` do documento.

    Quando ha mais de um numero - uma peca que cita o processo principal e um
    agravo -, o escolhido e o primeiro VALIDO, nao o primeiro qualquer: numero
    com digito errado costuma ser citacao de sistema ou erro de OCR, e ele
    ficaria no lugar do numero real. Os demais ficam listados, porque um
    documento que menciona tres processos e uma informacao, nao um estorvo.
    """
    achados = achar(pedido.texto)
    if not achados:
        return Resultado(objeto={}, status="ok")

    escolhido = next((a for a in achados if a["valido"]), achados[0])
    item = item_do_span(
        pedido, escolhido["inicio"], escolhido["fim"],
        id_="case_001",
        dados={"case_number": escolhido["numero"]},
        produzido_por=ID,
    )

    objeto = {
        "case_number": escolhido["numero"],
        "case_number_valid": escolhido["valido"],
        "year": escolhido["ano"],
        "court_segment": escolhido["justica"],
        "quote": item.quote,
        "certainty": "explicit",
        "verified": True,
        "source": item.source.to_dict(),
        "produced_by": ID,
    }
    outros = [a["numero"] for a in achados if a["numero"] != escolhido["numero"]]
    if outros:
        objeto["other_numbers"] = outros[:10]
    # Numero com digito errado nao e apresentado como numero do processo: ele
    # fica dito como tal, para alguem conferir no papel.
    if not escolhido["valido"]:
        objeto["certainty"] = "uncertain"
        objeto["verified"] = False
        objeto["note"] = "o dígito verificador não fecha — confira no documento"
    return Resultado(objeto=objeto)
