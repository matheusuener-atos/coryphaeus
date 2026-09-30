"""
O aviso de obra anterior à redação atual do artigo (M6).

Uma obra de 2015 comentando o art. 6º do CDC, que a Lei 14.181/2021 alterou,
aparecia como atual. O texto compilado do Planalto traz, ao lado de cada
dispositivo, "(Redação dada pela Lei nº X, de AAAA)", "(Incluído pela...)" e
"(Revogado pela...)"; src/leis.py tira dali o ano mais recente
(`ano_da_alteracao`), e aqui ele é comparado com o ano da ficha da obra.

Não esconde o trecho e não decide se o comentário continua valendo: só avisa.
E não é o motor de vigência (a redação vigente numa data passada): é o mínimo
seguro com o que o Planalto já entrega.
"""

from __future__ import annotations

import re


def aviso(ano_obra: str, alterado_em: int) -> str:
    """O texto do aviso, ou "" quando não há o que avisar."""
    if not alterado_em:
        return ""
    if not re.fullmatch(r"\d{4}", str(ano_obra or "")):
        return "Ano da obra desconhecido; confira a redação."
    if int(ano_obra) < alterado_em:
        return (f"Obra de {ano_obra}; este artigo teve a redação alterada em {alterado_em}. "
                "Confira se o comentário ainda vale.")
    return ""


def do_trecho(trecho, leis) -> list[dict]:
    """Os avisos de um trecho de doutrina: um por artigo que ele comenta e que mudou depois da obra."""
    if leis is None or trecho.origem not in ("doutrina", "comunidade"):
        return []
    saida = []
    for codigo, numero in trecho.dispositivos:
        artigo = leis.artigo(codigo, numero)
        texto = aviso(trecho.ano, artigo["alterado_em"]) if artigo else ""
        if texto:
            saida.append({"artigo": artigo["citacao"], "obra": trecho.obra, "autor": trecho.autor, "aviso": texto})
    return saida


def para_a_resposta(resposta: str, trechos: list, leis) -> str:
    """
    As linhas de aviso do fim da resposta: dos trechos de doutrina que a
    resposta cita (a marca [Tn]); sem marca nenhuma, de todos os que entraram.
    """
    from citacoes import RE_MARCA

    citados = {int(m) for m in RE_MARCA.findall(resposta or "")}
    escolhidos = [t for i, t in enumerate(trechos, start=1) if i in citados] if citados else list(trechos)
    linhas, vistos = [], set()
    for t in escolhidos:
        for a in do_trecho(t, leis):
            chave = (a["obra"], a["artigo"])
            if chave in vistos:
                continue
            vistos.add(chave)
            quem = (a["autor"].split()[-1] if a["autor"] else a["obra"])
            linhas.append(f"⚠ {quem} sobre o {a['artigo']}: {a['aviso']}")
    return "\n".join(linhas)
