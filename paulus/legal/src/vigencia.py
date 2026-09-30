"""
Lei com vigência (docs/PLANO-PILOTO.md, L10): o histórico de cada artigo,
dispositivo por dispositivo, e a situação dele numa data.

De onde sai: das notas que o Planalto põe no texto compilado - "(Redação
dada pela Lei nº 8.884, de 11.6.1994)", "(Incluído pela Lei nº 13.874, de
2019)", "(Revogado pela ...)", "(Vide ...)", "(VETADO)" - que o PAULUS já
guarda com o artigo (src/leis.py). O M6 da Biblioteca usava só o ano da
última alteração; aqui cada dispositivo (caput, parágrafo, inciso, alínea)
ganha a própria linha do tempo.

**O que dá para dizer numa data** (`situacao`): se o dispositivo já existia
(o código já vigorava, e o "Incluído" é de antes), se estava revogado, e se
a redação era esta ou uma anterior. **O que não dá**, e a tela diz: o texto
da redação anterior (o compilado do Planalto quase nunca o guarda: o CDC não
traz nenhum), e a vacatio legis - a data que vale é a da lei que mudou, não a
de quando ela entrou em vigor. O início da vigência de cada código é o do
texto original (tabela `INICIO`).
"""

from __future__ import annotations

import re
from datetime import date

from fastapi import HTTPException
from pydantic import BaseModel

# O início da vigência do texto original de cada código guardado.
INICIO = {
    "cc": ("2003-01-11", "Lei nº 10.406, de 10.1.2002, com um ano de vacatio legis"),
    "cpc": ("2016-03-18", "Lei nº 13.105, de 16.3.2015, com um ano de vacatio legis"),
    "cdc": ("1991-03-11", "Lei nº 8.078, de 11.9.1990, com 180 dias de vacatio legis"),
    "cf": ("1988-10-05", "promulgada em 5.10.1988"),
    "ctn": ("1967-01-01", "Lei nº 5.172, de 25.10.1966, em vigor em 1º.1.1967"),
    "clt": ("1943-11-10", "Decreto-Lei nº 5.452, de 1º.5.1943, em vigor em 10.11.1943"),
    "cp": ("1942-01-01", "Decreto-Lei nº 2.848, de 7.12.1940, em vigor em 1º.1.1942"),
    "cpp": ("1942-01-01", "Decreto-Lei nº 3.689, de 3.10.1941, em vigor em 1º.1.1942"),
    "eca": ("1990-10-14", "Lei nº 8.069, de 13.7.1990, com 90 dias de vacatio legis"),
    "inquilinato": ("1991-12-20", "Lei nº 8.245, de 18.10.1991, 60 dias depois da publicação"),
    "ctb": ("1998-01-22", "Lei nº 9.503, de 23.9.1997, 120 dias depois da publicação"),
}

RE_NOTA = re.compile(r"\((?P<o_que>Reda[çc][ãa]o dada|Inclu[íi]d[oa]|Acrescid[oa]|Acrescentad[oa]|Revogad[oa]|Renumerad[oa]|Vide|"
                     r"Vig[êe]ncia|VETADO|Vetad[oa])(?P<resto>[^)]*)\)", re.IGNORECASE)
RE_LEI = re.compile(r"(?:pel[oa]s?\s+)?(?P<tipo>Lei Complementar|Lei|Emenda Constitucional|Medida Provis[óo]ria|Decreto-Lei|Decreto)"
                    r"\s*n?[º°o.]*\s*(?P<numero>[\d.]+(?:-\d+)?)[^,)]*?,?\s*de\s*(?P<data>\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{4}|\d{4})",
                    re.IGNORECASE)
# Onde começa cada dispositivo, no texto de uma linha só: parágrafo, parágrafo
# único, inciso (romano seguido de travessão) e alínea.
RE_DISPOSITIVO = re.compile(r"(?:(?<=\s)|^)(?P<rotulo>§\s*\d+\s*[ºo°]?(?:-[A-Z])?|Parágrafo único\.?|"
                            r"(?P<romano>[IVXLC]{1,6})\s*[-–]\s|(?P<alinea>[a-z])\)\s)")

TIPOS = {"reda": "redação", "incl": "inclusão", "acre": "inclusão", "revo": "revogação", "renu": "renumeração",
         "vide": "remissão", "vig": "vigência", "veta": "veto"}


def _tipo(o_que: str) -> str:
    o = o_que.lower()
    for chave, t in TIPOS.items():
        if o.startswith(chave):
            return t
    return "nota"


def _data(bruto: str) -> tuple[str, bool]:
    """('AAAA-MM-DD', exata?) - só o ano vira 1º de janeiro, marcado como não exato."""
    b = re.sub(r"\s", "", bruto or "")
    m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", b)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat(), True
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}", b):
        return f"{b}-01-01", False
    return "", False


def notas(texto: str) -> list[dict]:
    saida = []
    for m in RE_NOTA.finditer(texto or ""):
        tipo = _tipo(m.group("o_que"))
        lei = RE_LEI.search(m.group("resto") or "")
        quando, exata = _data(lei.group("data")) if lei else ("", False)
        saida.append({"tipo": tipo, "nota": " ".join(m.group(0).split()),
                      "lei": f"{lei.group('tipo')} nº {lei.group('numero')}" if lei else "",
                      "data": quando, "data_exata": exata})
    return saida


def dispositivos(texto: str) -> list[dict]:
    """O caput, os parágrafos, os incisos e as alíneas, cada um com o texto e as notas dele."""
    texto = " ".join((texto or "").split())
    cortes = []
    for m in RE_DISPOSITIVO.finditer(texto):
        # Inciso só depois de ":" ou ";" ou de outro dispositivo - senão "I -" no meio da frase viraria inciso.
        antes = texto[:m.start()].rstrip()
        # E parágrafo também: "art. 373, § 1º" no meio de um inciso é referência, não parágrafo novo.
        if antes and antes[-1] not in ":;)." and not antes.endswith("Vigência"):
            continue
        cortes.append(m)
    saida = []
    pedaco_inicio = 0
    rotulo_atual, paragrafo = "caput", ""
    inciso = ""
    marcas = [(0, "caput", None)] + [(m.start(), m.group("rotulo"), m) for m in cortes]
    for i, (inicio, rotulo, m) in enumerate(marcas):
        fim = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto)
        trecho = texto[inicio:fim].strip()
        if not trecho:
            continue
        if m is None:
            nome = "caput"
        elif m.group("romano"):
            inciso = m.group("romano")
            nome = (paragrafo + ", " if paragrafo else "") + "inciso " + inciso
        elif m.group("alinea"):
            nome = (paragrafo + ", " if paragrafo else "") + (f"inciso {inciso}, " if inciso else "") + "alínea " + m.group("alinea")
        else:
            numero = re.search(r"\d+(?:-[A-Z])?", rotulo)
            paragrafo = "parágrafo único" if rotulo.lower().startswith("parágrafo") else f"§ {numero.group(0) if numero else ''}º"
            inciso = ""
            nome = paragrafo
        ns = notas(trecho)
        limpo = " ".join(RE_NOTA.sub("", trecho).replace(" Vigência", "").split())
        saida.append({"rotulo": nome, "texto": limpo, "notas": ns, "vetado": any(n["tipo"] == "veto" for n in ns),
                      "revogado": any(n["tipo"] == "revogação" for n in ns)})
    return saida


def _br(iso: str, exata: bool = True) -> str:
    if not iso:
        return ""
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}" if exata else a


def situacao(d: dict, quando: str, codigo: str) -> dict:
    """Como o dispositivo estava em `quando` (AAAA-MM-DD)."""
    inicio = INICIO.get(codigo, ("", ""))[0]
    if inicio and quando < inicio:
        return {"estado": "antes do código", "frase": f"o código ainda não vigorava (desde {_br(inicio)})"}
    if d["vetado"]:
        return {"estado": "vetado", "frase": "vetado: nunca vigorou"}
    for n in d["notas"]:
        # Lei só com o ano, e a data no mesmo ano: não dá para dizer de que lado ela cai.
        if n["data"] and not n["data_exata"] and n["tipo"] in ("inclusão", "revogação", "redação") and quando[:4] == n["data"][:4]:
            return {"estado": "incerto", "frase": f"no ano da {n['lei']} ({n['data'][:4]}), que mudou este dispositivo: "
                                                   "o compilado não traz a data exata, confira"}
    for n in d["notas"]:
        if n["tipo"] == "inclusão" and n["data"] and quando < n["data"]:
            return {"estado": "não existia", "frase": f"ainda não existia: incluído pela {n['lei']}, de {_br(n['data'], n['data_exata'])}"}
    revog = [n for n in d["notas"] if n["tipo"] == "revogação" and n["data"]]
    if revog and quando >= min(n["data"] for n in revog):
        n = min(revog, key=lambda x: x["data"])
        return {"estado": "revogado", "frase": f"revogado pela {n['lei']}, de {_br(n['data'], n['data_exata'])}"}
    posteriores = [n for n in d["notas"] if n["tipo"] == "redação" and n["data"] and quando < n["data"]]
    if posteriores:
        n = min(posteriores, key=lambda x: x["data"])
        return {"estado": "outra redação",
                "frase": f"valia uma redação anterior à da {n['lei']}, de {_br(n['data'], n['data_exata'])} "
                         "(o compilado do Planalto não traz o texto anterior)"}
    if revog:
        n = min(revog, key=lambda x: x["data"])
        return {"estado": "vigente", "frase": f"vigente (revogado depois, pela {n['lei']}, de {_br(n['data'], n['data_exata'])})"}
    return {"estado": "vigente", "frase": "vigente com esta redação"}


def do_artigo(artigo: dict, quando: str) -> dict:
    codigo = artigo["codigo"]
    ds = dispositivos(artigo.get("texto", ""))
    hoje = date.today().isoformat()
    for d in ds:
        d["na_data"] = situacao(d, quando, codigo)
        d["hoje"] = situacao(d, hoje, codigo)
        d["diferente"] = d["na_data"]["estado"] != d["hoje"]["estado"]
    historico = sorted(({"dispositivo": d["rotulo"], **n} for d in ds for n in d["notas"] if n["tipo"] != "vigência"),
                       key=lambda n: (n["data"] or "9999", n["dispositivo"]))
    diferentes = [d["rotulo"] for d in ds if d["diferente"]]
    if ds and ds[0]["na_data"]["estado"] == "antes do código":
        resumo = ds[0]["na_data"]["frase"][0].upper() + ds[0]["na_data"]["frase"][1:] + "."
    elif not diferentes:
        resumo = "Na data, o artigo estava como hoje."
    else:
        resumo = "Na data, estava diferente de hoje: " + ", ".join(diferentes[:8]) + (" e mais" if len(diferentes) > 8 else "") + "."
    inicio = INICIO.get(codigo)
    return {"citacao": artigo.get("citacao", ""), "codigo": codigo, "numero": artigo.get("numero", ""), "data": quando,
            "resumo": resumo, "dispositivos": ds, "historico": historico,
            "inicio_do_codigo": {"data": inicio[0], "como": inicio[1]} if inicio else None,
            "limites": "Pela data da lei que mudou (a vacatio legis dela não entra na conta) e pelas notas do texto compilado "
                       "do Planalto guardado neste PAULUS; o texto de uma redação anterior não vem no compilado."}


# ------------------------------------------------------------------ rotas

def montar(estado, app) -> None:
    @app.get("/api/leis/vigencia")
    def leis_vigencia(codigo: str, numero: str, data: str = "") -> dict:
        quando = data or date.today().isoformat()
        try:
            date.fromisoformat(quando)
        except ValueError:
            raise HTTPException(status_code=400, detail="a data vai como AAAA-MM-DD") from None
        a = estado.leis.artigo(codigo, numero)
        if not a:
            raise HTTPException(status_code=404, detail="artigo não encontrado nos códigos guardados")
        return do_artigo(a, quando)
