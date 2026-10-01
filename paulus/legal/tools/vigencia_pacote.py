"""
O pacote de vigência que vai no instalador (docs/PLANO-PILOTO.md, N12).

A L10 dava o histórico de cada dispositivo pelas notas do compilado, com
dois limites: sem o texto da redação anterior e sem a vacatio legis. Os dois
estão no Planalto, em outro lugar:

  - **o texto anterior**: de cada código, o Planalto publica uma versão com as
    redações antigas riscadas (<strike>), cada uma com a própria nota
    ("Redação dada pela Lei X") - o CC em l10406.htm, a CLT em del5452.htm...
    Este script fica com a versão que tem mais riscados (a guardada no
    instalador ou a outra) e anota, por artigo e por dispositivo, cada
    redação riscada, na ordem;
  - **a vacatio legis**: de cada lei que as notas citam (os links das notas),
    a data da publicação no DOU e a cláusula de vigência ("entra em vigor na
    data de sua publicação", "após decorridos 90 dias"...). A data em que a
    mudança passou a valer é a publicação mais o prazo (LC 95/1998, art. 8º,
    § 1º). Cláusula que não diz um prazo simples fica marcada, e a tela diz.

Roda na máquina de quem monta o instalador (o Planalto aceita programa, sem
pressa: uma lei a cada 0,4 s); o PAULUS instalado não baixa nada disso.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/vigencia_pacote.py
"""

from __future__ import annotations

import gzip
import html
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

RAIZ = Path(__file__).resolve().parents[1]
ACERVO = RAIZ / "config" / "acervo-inicial"
SAIDA = ACERVO / "vigencia-pacote.json.gz"
PAUSA = 0.4
sys.path.insert(0, str(RAIZ / "src"))

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
EXTENSO = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
           "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "quarenta e cinco": 45, "sessenta": 60,
           "noventa": 90, "cento e vinte": 120, "cento e oitenta": 180, "duzentos e setenta": 270, "trezentos e sessenta e cinco": 365}


def _baixar(url: str) -> str:
    import requests

    r = requests.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0 (PAULUS, montagem do instalador)"})
    if r.status_code != 200:
        return ""
    cab = r.content[:4000].lower()
    return r.content.decode("utf-8", errors="replace") if b"utf-8" in cab else r.content.decode("cp1252", errors="replace")


def _texto(trecho: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", trecho)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(html.unescape(t).replace("\xa0", " ").split())


# ------------------------------------------------------------ os riscados

RE_BLOCO = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")
RE_RISCO = re.compile(r"(?is)<strike\b[^>]*>(.*?)</strike>|<(?:span|font)\b[^>]*line-through[^>]*>(.*?)</(?:span|font)>")
RE_ART = re.compile(r"^Art\.?\s*(\d{1,4}(?:\.\d{3})?)\s*[ºo°]?\s*((?:[-‐‑‒–—]\s*[A-Z]{1,2})*)", re.IGNORECASE)
RE_ROTULO = re.compile(r"^(?:(?P<par>§\s*\d+\s*[ºo°]?(?:-[A-Z])?)|(?P<unico>Parágrafo único)|(?P<romano>[IVXLC]{1,6})\s*[-–]\s|(?P<alinea>[a-z])\)\s)")


def _chave(numero: str, sufixo: str, base: int) -> str:
    import leis

    return str(leis._ordem(numero, sufixo) + base)


def riscados(pagina: str) -> dict[str, list[dict]]:
    """{chave do artigo: [{"rotulo", "texto"}]}: cada redação riscada, na ordem da página."""
    import leis

    saida: dict[str, list[dict]] = {}
    atual, base = "", 0
    paragrafo, inciso = "", ""
    for m in RE_BLOCO.finditer(pagina):
        bruto = m.group(1)
        inteiro = _texto(bruto)
        if not inteiro:
            continue
        if re.search(r"ATO DAS DISPOSI[ÇC][ÕO]ES CONSTITUCIONAIS TRANSIT[ÓO]RIAS", inteiro, re.IGNORECASE) and len(inteiro) < 80:
            base = leis.ADCT_BASE
        partes = [_texto(r.group(1) or r.group(2) or "") for r in RE_RISCO.finditer(bruto)]
        partes = [p for p in partes if p]
        normal = _texto(RE_RISCO.sub(" ", bruto))
        for alvo in ([normal] if normal else []) + partes:
            a = RE_ART.match(alvo)
            if a:
                atual = _chave(a.group(1), re.sub(r"\s", "", a.group(2) or ""), base)
                paragrafo, inciso = "", ""
                break
        for p in partes:
            if not atual:
                continue
            r = RE_ROTULO.match(p)
            if RE_ART.match(p):
                rotulo = "caput"
            elif r and r.group("par"):
                n = re.search(r"\d+(?:-[A-Z])?", r.group("par"))
                paragrafo, inciso = f"§ {n.group(0)}º", ""
                rotulo = paragrafo
            elif r and r.group("unico"):
                paragrafo, inciso = "parágrafo único", ""
                rotulo = paragrafo
            elif r and r.group("romano"):
                inciso = r.group("romano")
                rotulo = (paragrafo + ", " if paragrafo else "") + "inciso " + inciso
            elif r and r.group("alinea"):
                rotulo = (paragrafo + ", " if paragrafo else "") + (f"inciso {inciso}, " if inciso else "") + "alínea " + r.group("alinea")
            else:
                continue
            saida.setdefault(atual, []).append({"rotulo": rotulo, "texto": p[:4000]})
        # O rótulo do que não está riscado também move o parágrafo e o inciso da vez.
        r = RE_ROTULO.match(normal or "")
        if r and r.group("par"):
            n = re.search(r"\d+(?:-[A-Z])?", r.group("par"))
            paragrafo, inciso = f"§ {n.group(0)}º", ""
        elif r and r.group("unico"):
            paragrafo, inciso = "parágrafo único", ""
        elif r and r.group("romano"):
            inciso = r.group("romano")
    return saida


# ------------------------------------------------------------ a lei e a vacatio

RE_TITULO = re.compile(r"(?P<tipo>LEI COMPLEMENTAR|EMENDA CONSTITUCIONAL(?: DE REVIS[ÃA]O)?|MEDIDA PROVIS[ÓO]RIA|DECRETO-LEI|DECRETO|LEI)"
                       r"\s*N\s?[º°o.]*\s*(?P<numero>[\d.]+(?:-[A-Z\d]+)?)\s*,?\s*DE\s*(?P<dia>\d{1,2})\s?[º°o]?\s*DE\s*(?P<mes>[A-ZÇÃ]+)\s*DE\s*(?P<ano>\d{4})",
                       re.IGNORECASE)
RE_DOU = re.compile(r"publicad[oa]\s+n[oa]\s+D\.?\s*O\.?\s*U\.?\s*(?:de|em)?\s*(\d{1,2})[º°o]?\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{2,4})", re.IGNORECASE)
RE_VIGOR = re.compile(r"(?:entra(?:rá|ra)?|entrar[aã]o|entram)\s+em\s+vigor[^.;]{0,220}", re.IGNORECASE)


def _numero_extenso(t: str) -> int | None:
    t = t.strip().lower()
    if t.isdigit():
        return int(t)
    return EXTENSO.get(t)


def clausula(texto: str, publicacao: str) -> dict:
    """{"vacatio_dias", "vigor", "clausula", "simples"}: o que a cláusula de vigência diz, e a data que sai dela."""
    achadas = [" ".join(m.group(0).split()) for m in RE_VIGOR.finditer(texto)]
    if not achadas:
        return {"clausula": "", "simples": False, "vigor": "", "vacatio_dias": None}
    # A cláusula geral costuma ser a última; mais de uma com prazos diferentes: vigência em partes.
    principal = achadas[-1]
    p = principal.lower()
    dias = None
    if re.search(r"na data (?:de )?(?:da )?sua publica", p) or re.search(r"data de sua publica", p):
        dias = 0
    m = re.search(r"(\d{1,4}|[a-zçãé]+(?: e [a-zçãé]+){0,3})\s*(?:\([^)]{0,40}\))?\s*(dias?|meses|m[eê]s|anos?)\s+(?:ap[óo]s|depois|da|de|contados)", p)
    if dias is None and m:
        n = _numero_extenso(m.group(1))
        if n:
            dias = n if m.group(2).startswith("dia") else (n * 365 if m.group(2).startswith("ano") else None)
    m = re.search(r"decorridos?\s+(\d{1,4}|[a-zçãé]+(?: e [a-zçãé]+){0,3})\s*(?:\([^)]{0,40}\))?\s*(dias?|anos?)", p)
    if dias is None and m:
        n = _numero_extenso(m.group(1))
        if n:
            dias = n if m.group(2).startswith("dia") else n * 365
    explicita = re.search(r"em\s+(\d{1,2})[º°o]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", p)
    vigor = ""
    if explicita and dias is None and explicita.group(2) in MESES:
        try:
            vigor = date(int(explicita.group(3)), MESES[explicita.group(2)], int(explicita.group(1))).isoformat()
        except ValueError:
            vigor = ""
    if dias is not None and publicacao:
        vigor = (date.fromisoformat(publicacao) + timedelta(days=dias)).isoformat()
    # "Esta Lei entra em vigor: I - ...; II - ...": prazos por dispositivo - vigência em partes.
    partes = len({a.lower() for a in achadas}) > 1 or principal.rstrip().endswith(":") or bool(re.search(r"vigor\s*:", p))
    if partes:
        dias, vigor = None, ""
    return {"clausula": principal[:300], "simples": bool(vigor) and not partes, "vigor": vigor, "vacatio_dias": dias,
            "em_partes": partes}


def lei(url: str) -> dict | None:
    pagina = _baixar(url)
    if not pagina:
        return None
    texto = _texto(pagina)
    # O título da própria lei: o que tem o número do nome do arquivo ("L10.695.htm" -> 10695). A página
    # pode citar outra lei antes (a que ela altera), e pegar a primeira trocava uma pela outra.
    do_arquivo = re.sub(r"\D", "", re.sub(r"(?i)\.htm.*$", "", url.rsplit("/", 1)[-1])).lstrip("0")
    titulos = [m for m in RE_TITULO.finditer(texto) if m.group("mes").lower() in MESES]
    t = next((m for m in titulos if re.sub(r"\D", "", m.group("numero")).lstrip("0") == do_arquivo), None) or (titulos[0] if titulos else None)
    if not t:
        return None
    try:
        assinatura = date(int(t.group("ano")), MESES[t.group("mes").lower()], int(t.group("dia"))).isoformat()
    except ValueError:
        return None
    publicacao, exata = assinatura, False
    for d in RE_DOU.finditer(texto):
        ano = int(d.group(3))
        ano = ano + (1900 if ano > 30 else 2000) if ano < 100 else ano
        try:
            candidata = date(ano, int(d.group(2)), int(d.group(1)))
        except ValueError:
            continue
        # A publicação de verdade vem até uns dias depois da assinatura; a de anos depois é republicação.
        if 0 <= (candidata - date.fromisoformat(assinatura)).days <= 60:
            publicacao, exata = candidata.isoformat(), True
            break
    tipo = t.group("tipo").title().replace("-Lei", "-Lei").replace("Provisória", "Provisória")
    numero = t.group("numero").rstrip(".")
    return {"tipo": tipo, "numero": numero, "ano": t.group("ano"), "assinatura": assinatura, "publicacao": publicacao,
            "publicacao_exata": exata, "url": url, **clausula(texto, publicacao)}


def chave_da_lei(tipo: str, numero: str, ano: str) -> str:
    """A mesma chave nas notas do compilado ("Lei nº 8.884, de 11.6.1994") e no título da lei."""
    t = tipo.lower().replace("ó", "o").replace("ã", "a")
    t = "emenda" if t.startswith("emenda") else ("lc" if "complementar" in t else ("mp" if "medida" in t else
                                                 ("decreto-lei" if "decreto-lei" in t else ("decreto" if t.startswith("decreto") else "lei"))))
    return f"{t}|{re.sub(r'[^0-9A-Za-z-]', '', numero).lstrip('0')}|{ano}"


# ------------------------------------------------------------ juntar

def main() -> int:
    idx = json.loads((ACERVO / "indice.json").read_text(encoding="utf-8"))
    anteriores, fontes, links = {}, {}, set()
    for cod, d in idx["codigos"].items():
        guardado = gzip.decompress((ACERVO / d["arquivo"]).read_bytes()).decode("cp1252", errors="replace")
        fonte = d["fonte"]
        alt = (re.sub(r"compilad[oa]\.htm$", ".htm", fonte) if re.search(r"compilad[oa]\.htm$", fonte)
               else re.sub(r"\.htm$", "compilada.htm", fonte))
        outro = _baixar(alt)
        time.sleep(PAUSA)
        escolhida, de_onde = (outro, alt) if outro.lower().count("<strike") > guardado.lower().count("<strike") else (guardado, fonte)
        r = riscados(escolhida)
        anteriores[cod] = r
        fontes[cod] = de_onde
        for m in re.finditer(r'<a[^>]*href="([^"#]+)(?:#[^"]*)?"[^>]*>(?:(?!</a>).){0,300}?(Reda|Inclu|Revog|Acresc|Renumer|Vig)',
                             guardado + escolhida, re.S | re.I):
            if re.search(r"\.htm", m.group(1), re.I):
                links.add(urljoin(fonte, m.group(1)))
        print(f"{cod}: {sum(len(v) for v in r.values())} redações riscadas em {len(r)} artigos ({de_onde.rsplit('/', 1)[-1]})")
    print(f"{len(links)} leis citadas nas notas")
    leis_ = {}
    for i, url in enumerate(sorted(links), 1):
        try:
            x = lei(url)
        except Exception as exc:  # noqa: BLE001 - uma lei que falha não para o pacote
            print("  falhou:", url, str(exc)[:80])
            x = None
        if x:
            leis_[chave_da_lei(x["tipo"], x["numero"], x["ano"])] = x
        if i % 50 == 0:
            print(f"  {i}/{len(links)}")
        time.sleep(PAUSA)
    simples = sum(1 for x in leis_.values() if x["simples"])
    print(f"{len(leis_)} leis lidas; {simples} com vigência de prazo simples")
    if len(leis_) < 300 or sum(len(v) for c in anteriores.values() for v in c.values()) < 1000:
        print("pouco demais: nada gravado")
        return 1
    pacote = {"montado_em": datetime.now().isoformat(timespec="seconds"), "fontes": fontes, "anteriores": anteriores, "leis": leis_}
    SAIDA.write_bytes(gzip.compress(json.dumps(pacote, ensure_ascii=False).encode("utf-8")))
    # Relido agora, e não o do começo: outra montagem (a do STF) pode ter gravado no meio-tempo.
    idx = json.loads((ACERVO / "indice.json").read_text(encoding="utf-8"))
    idx["vigencia"] = {"arquivo": SAIDA.name, "leis": len(leis_), "leis_simples": simples,
                       "redacoes_riscadas": sum(len(v) for c in anteriores.values() for v in c.values()),
                       "montado_em": pacote["montado_em"]}
    (ACERVO / "indice.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("gravado em", SAIDA, f"({SAIDA.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
