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
a redação era esta ou uma anterior. O início da vigência de cada código é o
do texto original (tabela `INICIO`).

**N12 (o pacote de vigência, tools/vigencia_pacote.py, no instalador):**
  - **o texto da redação anterior**: a versão do código em que o Planalto
    deixa as redações antigas riscadas, cada uma com a própria nota. Numa data
    em que valia uma redação anterior, a resposta traz o texto dela;
  - **a vacatio legis**: de cada lei citada nas notas, a publicação no DOU e
    a cláusula de vigência. A data que vale passa a ser a de quando a mudança
    entrou em vigor; sem cláusula de prazo simples (vigência em partes, ou
    "no primeiro dia do mês seguinte"), fica a data da lei, e a tela diz.
"""

from __future__ import annotations

import functools
import gzip
import json
import re
from datetime import date
from pathlib import Path

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
                    r"\s*n?\s?[º°o.]*\s*(?P<numero>[\d.]+(?:-\d+)?)[^,)]*?,?\s*de\s*(?P<data>\d{1,2}\s*[º°o]?\s*[./]\s*\d{1,2}\s*[./]\s*\d{4}|\d{4})",
                    re.IGNORECASE)
# Onde começa cada dispositivo, no texto de uma linha só: parágrafo, parágrafo
# único, inciso (romano seguido de travessão) e alínea.
RE_DISPOSITIVO = re.compile(r"(?:(?<=\s)|^)(?P<rotulo>§\s*\d+\s*[ºo°]?(?:-[A-Z])?|Parágrafo único\.?|"
                            r"(?P<romano>[IVXLC]{1,6})\s*[-–]\s|(?P<alinea>[a-z])\)\s)")

PACOTE = Path(__file__).resolve().parents[1] / "config" / "acervo-inicial" / "vigencia-pacote.json.gz"


@functools.lru_cache(maxsize=1)
def pacote() -> dict:
    """O pacote de vigência do instalador (N12): as redações riscadas e as leis lidas. Sem ele, como antes."""
    try:
        return json.loads(gzip.decompress(PACOTE.read_bytes()).decode("utf-8"))
    except (OSError, ValueError):
        return {"anteriores": {}, "leis": {}}


def chave_da_lei(tipo: str, numero: str, ano: str) -> str:
    """A mesma chave de tools/vigencia_pacote.py: tipo, número sem pontos e ano."""
    t = tipo.lower().replace("ó", "o").replace("ã", "a")
    t = "emenda" if t.startswith("emenda") else ("lc" if "complementar" in t else ("mp" if "medida" in t else
                                                 ("decreto-lei" if "decreto-lei" in t else ("decreto" if t.startswith("decreto") else "lei"))))
    return f"{t}|{re.sub(r'[^0-9A-Za-z-]', '', numero).lstrip('0')}|{ano}"


def chave_do_artigo(numero: str) -> str:
    """A chave do artigo no pacote: a ordem de src/leis.py (com o ADCT da Constituição à parte)."""
    import leis

    limpo = str(numero or "").strip()
    base = 0
    if re.match(r"(?i)adct\b", limpo):
        base = leis.ADCT_BASE
        limpo = re.sub(r"(?i)^adct[\s,]*(?:art\.?\s*)?", "", limpo)
    cadeia = "".join(re.findall(r"[" + leis.HIFENS + r"][A-Za-z]{1,2}", limpo))
    return str(leis._ordem(limpo, cadeia) + base)


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
    b = re.sub(r"[\sº°o]", "", bruto or "")
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
    """
    As notas, cada uma com a data da lei e, quando o pacote leu a lei (N12), a
    data em que a mudança passou a valer (`efetiva`): a publicação mais a
    vacatio. Sem isso, `efetiva` é a data da lei.
    """
    saida = []
    leis_lidas = pacote().get("leis") or {}
    for m in RE_NOTA.finditer(texto or ""):
        tipo = _tipo(m.group("o_que"))
        lei = RE_LEI.search(m.group("resto") or "")
        quando, exata = _data(lei.group("data")) if lei else ("", False)
        n = {"tipo": tipo, "nota": " ".join(m.group(0).split()),
             "lei": f"{lei.group('tipo')} nº {lei.group('numero')}" if lei else "",
             "data": quando, "data_exata": exata, "efetiva": quando, "efetiva_exata": exata,
             "vigor": "", "publicacao": "", "vacatio_dias": None, "em_partes": False}
        info = leis_lidas.get(chave_da_lei(lei.group("tipo"), lei.group("numero"), quando[:4])) if lei and quando else None
        if info:
            n["publicacao"] = info.get("publicacao") or ""
            n["em_partes"] = bool(info.get("em_partes"))
            if info.get("simples") and info.get("vigor"):
                n.update(vigor=info["vigor"], vacatio_dias=info.get("vacatio_dias"), efetiva=info["vigor"], efetiva_exata=True)
            if not exata and info.get("assinatura"):
                n.update(data=info["assinatura"], data_exata=True)
                if not n["vigor"]:
                    n.update(efetiva=info["assinatura"], efetiva_exata=True)
        saida.append(n)
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


def _quando_valeu(n: dict) -> str:
    """"de 11/06/1994" ou "de 2019, em vigor desde 18/03/2020": a lei e, se for outra, a data em que passou a valer."""
    base = f"de {_br(n['data'], n['data_exata'])}"
    if n.get("vigor") and n["vigor"] != n["data"]:
        base += f", em vigor desde {_br(n['vigor'])}" + (f" ({n['vacatio_dias']} dias de vacatio)" if n.get("vacatio_dias") else "")
    elif n.get("em_partes"):
        base += " (a lei tem vigência em partes: confira a data deste dispositivo)"
    return base


def _versoes(d: dict) -> list[tuple[str, str, dict | None]]:
    """
    As redações do dispositivo na ordem do tempo: (desde quando vale, texto,
    a nota que a trouxe). As riscadas (N12) vêm do pacote; a última é a de hoje.
    """
    def desde(ns):
        datas = [x["efetiva"] for x in ns if x["tipo"] in ("redação", "inclusão") and x["efetiva"]]
        return max(datas) if datas else ""

    saida = []
    for a in d.get("anteriores") or []:
        nota = next((x for x in reversed(a["notas"]) if x["tipo"] in ("redação", "inclusão")), None)
        saida.append((desde(a["notas"]), a["texto"], nota))
    nota_hoje = next((x for x in reversed(d["notas"]) if x["tipo"] in ("redação", "inclusão")), None)
    saida.append((desde(d["notas"]), d["texto"], nota_hoje))
    return saida


def situacao(d: dict, quando: str, codigo: str) -> dict:
    """Como o dispositivo estava em `quando` (AAAA-MM-DD)."""
    inicio = INICIO.get(codigo, ("", ""))[0]
    if inicio and quando < inicio:
        return {"estado": "antes do código", "frase": f"o código ainda não vigorava (desde {_br(inicio)})"}
    if d["vetado"]:
        return {"estado": "vetado", "frase": "vetado: nunca vigorou"}
    for n in d["notas"]:
        # Lei só com o ano, e a data no mesmo ano: não dá para dizer de que lado ela cai.
        if n["efetiva"] and not n["efetiva_exata"] and n["tipo"] in ("inclusão", "revogação", "redação") and quando[:4] == n["efetiva"][:4]:
            return {"estado": "incerto", "frase": f"no ano da {n['lei']} ({n['data'][:4]}), que mudou este dispositivo: "
                                                   "o compilado não traz a data exata, confira"}
    for n in d["notas"]:
        if n["tipo"] == "inclusão" and n["efetiva"] and quando < n["efetiva"]:
            return {"estado": "não existia", "frase": f"ainda não existia: incluído pela {n['lei']}, {_quando_valeu(n)}"}
    revog = [n for n in d["notas"] if n["tipo"] == "revogação" and n["efetiva"]]
    if revog and quando >= min(n["efetiva"] for n in revog):
        n = min(revog, key=lambda x: x["efetiva"])
        return {"estado": "revogado", "frase": f"revogado pela {n['lei']}, {_quando_valeu(n)}"}
    posteriores = [n for n in d["notas"] if n["tipo"] == "redação" and n["efetiva"] and quando < n["efetiva"]]
    if posteriores:
        n = min(posteriores, key=lambda x: x["efetiva"])
        # N12: com as redações riscadas do Planalto, a que valia na data.
        versoes = _versoes(d)
        valia = None
        for desde, texto, _nota in versoes[:-1]:
            if not desde or desde <= quando:
                valia = texto
        if valia:
            return {"estado": "outra redação", "texto": valia,
                    "frase": f"valia a redação anterior à da {n['lei']}, {_quando_valeu(n)}"}
        return {"estado": "outra redação",
                "frase": f"valia uma redação anterior à da {n['lei']}, {_quando_valeu(n)} "
                         "(o Planalto não guarda o texto anterior deste dispositivo)"}
    if revog:
        n = min(revog, key=lambda x: x["efetiva"])
        return {"estado": "vigente", "frase": f"vigente (revogado depois, pela {n['lei']}, {_quando_valeu(n)})"}
    return {"estado": "vigente", "frase": "vigente com esta redação"}


def _sem_rotulo_do_artigo(texto: str) -> str:
    """"Art 39. É vedado..." -> "É vedado...": o caput de hoje vem sem o "Art.", e o riscado também fica assim."""
    return re.sub(r"^Art\.?\s*\d[\d.]*\s*[ºo°]?\s*(?:[-–—]\s*[A-Z]{1,2}\s*)*[.\-–—]?\s*", "", texto)


def do_artigo(artigo: dict, quando: str) -> dict:
    codigo = artigo["codigo"]
    ds = dispositivos(artigo.get("texto", ""))
    hoje = date.today().isoformat()
    # N12: as redações riscadas deste artigo, por dispositivo, na ordem do Planalto.
    riscadas = (pacote().get("anteriores") or {}).get(codigo, {}).get(chave_do_artigo(artigo.get("numero", "")), [])
    for d in ds:
        d["anteriores"] = [{"texto": _sem_rotulo_do_artigo(" ".join(RE_NOTA.sub("", x["texto"]).split())), "notas": notas(x["texto"])}
                           for x in riscadas if x.get("rotulo") == d["rotulo"]]
    for d in ds:
        d["na_data"] = situacao(d, quando, codigo)
        d["hoje"] = situacao(d, hoje, codigo)
        d["diferente"] = d["na_data"]["estado"] != d["hoje"]["estado"]
    historico = sorted(({"dispositivo": d["rotulo"], **n} for d in ds for n in d["notas"] if n["tipo"] != "vigência"),
                       key=lambda n: (n["efetiva"] or "9999", n["dispositivo"]))
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
            "limites": _limites()}


def _limites() -> str:
    """O que a resposta garante, dito conforme o pacote de vigência está ou não no instalador."""
    p = pacote()
    if not p.get("leis"):
        return ("Pela data da lei que mudou (a vacatio legis dela não entra na conta) e pelas notas do texto compilado "
                "do Planalto guardado neste PAULUS; o texto de uma redação anterior não vem no compilado.")
    quando = str(p.get("montado_em") or "")[:10]
    return ("Pelas notas do texto compilado do Planalto e pelo pacote de vigência do instalador (montado em "
            f"{_br(quando) if quando else '?'}): a data em que cada mudança passou a valer é a publicação mais a vacatio "
            "da cláusula de vigência da lei; quando a cláusula não diz um prazo simples, vale a data da lei, e a linha diz. "
            "O texto anterior vem das redações que o Planalto deixa riscadas; onde ele não guardou, a linha diz.")


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
