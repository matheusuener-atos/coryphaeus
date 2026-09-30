"""
A Biblioteca ajudando a escrever (docs/PLANO-PILOTO.md, L5).

- **Temas repetitivos e IAC do STJ**, oficiais: o Temas.csv do Portal de
  Dados Abertos do STJ (CC-BY), já no instalador (config/acervo-inicial/
  temas-stj.jsonl.gz, montado por tools/temas_stj.py): 1.330 temas, com a
  questão, a tese firmada, a situação e o órgão. "Atualizar pelo STJ" baixa
  o arquivo do portal só quando a pessoa pede. Cada tema fica ligado aos
  artigos que a tese e a questão citam ("art. 206 do CC"), por regra.
- **A posição da casa** por artigo: o que o escritório entende de um artigo,
  escrito pelo titular, que aparece junto do artigo e na fundamentação.
- **A fundamentação sugerida** (`sugerir`): para um trecho da peça, os
  artigos citados nele e os que a busca acha pelas palavras do trecho, as
  súmulas do STJ, os temas e a posição da casa - cada um com o porquê. Sem
  modelo: quem escolhe o que entra é o advogado, e o que entra é o texto
  oficial.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "config" / "acervo-inicial" / "temas-stj.jsonl.gz"
URL_STJ = ("https://dadosabertos.web.stj.jus.br/dataset/4238da2f-c07b-4c1a-b345-4402accacdcf/resource/"
           "df29da13-7d6b-41ba-ad96-cd1a5bbd191c/download/temas.csv")
TIPOS = {"Tema": "Tema Repetitivo", "IAC": "IAC"}
FORA = {"Cancelado", "Cancelada", "Vinculada a Tema", "Sem processo vinculado"}

PARADAS = set("""a o os as um uma uns umas de da do das dos e em no na nos nas por pelo pela pelos pelas para com sem sob sobre
que se ao aos à às ou como mais menos muito não nao já ja seu sua seus suas este esta isso isto esse essa nesta neste
quando qual quais ser ter foi são sao está esta pode deve devem será sera conforme termos presente caso fim artigo art
lei código codigo parte partes autor réu reu requerente requerido excelência excelencia vossa senhor meritíssimo
prevista previsto previstas previstos pois porque assim ainda tambem também entre desde todo toda todos todas cada""".split())

CODIGOS_NA_TESE = [
    (r"c[óo]digo civil|\bcc(?:/2002)?\b", "cc"),
    (r"c[óo]digo de processo civil|\bcpc(?:/2015)?\b", "cpc"),
    (r"c[óo]digo de defesa do consumidor|\bcdc\b", "cdc"),
    (r"c[óo]digo tribut[áa]rio nacional|\bctn\b", "ctn"),
    (r"\bclt\b", "clt"),
    (r"constitui[çc][ãa]o|\bcf(?:/88)?\b", "cf"),
    (r"c[óo]digo penal|\bcp\b", "cp"),
    (r"c[óo]digo de processo penal|\bcpp\b", "cpp"),
    (r"\beca\b|estatuto da crian[çc]a", "eca"),
    (r"lei (?:n[º°o.]*\s*)?8\.?245", "inquilinato"),
    (r"c[óo]digo de tr[âa]nsito|\bctb\b", "ctb"),
]
# O nome do código fica num lookahead: "art. 206 do CC e art. 85 do CPC" acha os dois.
RE_ARTIGO = re.compile(r"\barts?\.?\s*(\d{1,4}(?:\.\d{3})?(?:-[A-Z])?)(?:[º°o])?(?:[^.;]{0,50}?)\b(?:d[oa]s?)\s+(?=([^;,)]{2,40}))",
                       re.IGNORECASE)
RE_ANTIGO = re.compile(r"/(?:19)?(?:16|73)\b|de 1973|de 1916|revogad", re.IGNORECASE)


def _plano(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "").lower()) if not unicodedata.combining(c))


def artigos_citados(texto: str) -> list[str]:
    """["cc:206", "cpc:85"]: os artigos que um texto cita, dos códigos instalados. O CPC/73 e o CC/1916 ficam de fora."""
    saida = []
    for m in RE_ARTIGO.finditer(texto or ""):
        numero, depois = m.group(1).replace(".", ""), m.group(2)
        if RE_ANTIGO.search(depois):
            continue
        for padrao, codigo in CODIGOS_NA_TESE:
            if re.search(padrao, depois, re.IGNORECASE):
                chave = f"{codigo}:{numero}"
                if chave not in saida:
                    saida.append(chave)
                break
    return saida


# ------------------------------------------------------------ os temas

def _linhas_do_csv(texto: str) -> list[dict]:
    saida = []
    for r in csv.DictReader(io.StringIO(texto)):
        if r.get("tipoPrecedente") not in TIPOS or r.get("situacao") in FORA:
            continue
        tese, questao = (r.get("teseFirmada") or "").strip(), (r.get("questaoSubmetidaAJulgamento") or "").strip()
        if not tese and not questao:
            continue
        saida.append({"tipo": TIPOS[r["tipoPrecedente"]], "numero": (r.get("numeroPrecedente") or "").strip(),
                      "situacao": (r.get("situacao") or "").strip(), "questao": " ".join(questao.split()), "tese": " ".join(tese.split()),
                      "orgao": (r.get("orgaoJulgador") or "").strip(), "julgado_em": (r.get("dataJulgamento") or "").strip(),
                      "assuntos": " ".join((r.get("Assuntos") or "").split()),
                      "legislacao": " ".join((r.get("referenciaLegislativa") or "").split())[:600]})
    return saida


def _baixado_em(fonte: str) -> str:
    m = re.search(r"baixado em (\d{4}-\d{2}-\d{2})", fonte or "")
    return m.group(1) if m else ""


class Temas:
    def __init__(self, base) -> None:
        self.base = base

    def quantos(self) -> int:
        return self.base.contar("temas")

    def gravar(self, linhas: list[dict], fonte: str) -> int:
        self.base.escrever("DELETE FROM temas")
        for l in linhas:
            artigos = artigos_citados(" ".join((l.get("tese", ""), l.get("questao", ""), l.get("legislacao", ""))))
            self.base.escrever(
                "INSERT OR REPLACE INTO temas (tipo, numero, situacao, questao, tese, orgao, julgado_em, assuntos, legislacao, artigos, fonte)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (l["tipo"], l["numero"], l["situacao"], l["questao"], l["tese"], l["orgao"], l["julgado_em"], l["assuntos"],
                 l.get("legislacao", ""), json.dumps(artigos), fonte))
        return len(linhas)

    def instalar(self, arquivo: Path = ARQUIVO) -> int:
        """Os temas que vêm no instalador, na primeira abertura (ou se o arquivo do instalador for mais novo)."""
        if not arquivo.exists():
            return 0
        with gzip.open(arquivo, "rt", encoding="utf-8") as f:
            cab = json.loads(f.readline())
            linhas = [json.loads(x) for x in f if x.strip()]
        fonte = f"{cab.get('fonte', 'STJ')} · baixado em {cab.get('baixado_em', '')}"
        ja = self.base.um("SELECT fonte FROM temas LIMIT 1")
        # Já tem temas iguais ou mais novos (o do instalador, ou um "atualizar pelo STJ" depois): fica.
        if ja and _baixado_em(ja["fonte"]) >= cab.get("baixado_em", ""):
            return 0
        return self.gravar(linhas, fonte)

    def atualizar_do_stj(self, baixar=None) -> dict:
        """Baixa o Temas.csv do portal do STJ (só quando a pessoa pede) e troca os temas."""
        if baixar is None:
            import requests

            def baixar(url):
                r = requests.get(url, timeout=120)
                r.raise_for_status()
                r.encoding = "utf-8"
                return r.text
        linhas = _linhas_do_csv(baixar(URL_STJ))
        if len(linhas) < 100:
            raise ValueError("o arquivo do STJ veio sem os temas; nada foi trocado")
        n = self.gravar(linhas, f"Portal de Dados Abertos do STJ · baixado em {datetime.now():%Y-%m-%d}")
        return {"temas": n}

    def _dict(self, l: dict) -> dict:
        d = dict(l)
        d["artigos"] = json.loads(d.get("artigos") or "[]")
        d["rotulo"] = f"{d['tipo']} {d['numero']}/STJ"
        return d

    def procurar(self, termo: str = "", numero: str = "", limite: int = 20) -> list[dict]:
        numero = re.sub(r"\D", "", numero or "")
        if numero:
            return [self._dict(l) for l in self.base.buscar("SELECT * FROM temas WHERE numero = ?", (numero,))]
        palavras = [p for p in re.findall(r"\w+", _plano(termo)) if len(p) > 2 and p not in PARADAS]
        if not palavras:
            return []
        saida = []
        for l in self.base.buscar("SELECT * FROM temas"):
            alvo = _plano(" ".join((l["tese"], l["questao"], l["assuntos"])))
            nota = sum(1 for p in palavras if p in alvo)
            if nota >= max(1, min(len(palavras), 2)):
                saida.append((nota, l))
        saida.sort(key=lambda x: (-x[0], -int(x[1]["numero"] or 0)))
        return [dict(self._dict(l), nota=n) for n, l in saida[:limite]]

    def do_artigo(self, codigo: str, numero: str) -> list[dict]:
        chave = f'"{codigo}:{str(numero).replace(".", "")}"'
        return [self._dict(l) for l in self.base.buscar("SELECT * FROM temas WHERE artigos LIKE ?", (f"%{chave}%",))]


# ------------------------------------------------------------ a posição da casa

class Posicoes:
    def __init__(self, base) -> None:
        self.base = base

    def obter(self, codigo: str, numero: str) -> dict | None:
        return self.base.um("SELECT * FROM posicoes WHERE codigo = ? AND numero = ?", (codigo, str(numero)))

    def gravar(self, codigo: str, numero: str, texto: str, autor: str = "") -> dict | None:
        texto = str(texto or "").strip()[:2000]
        if not texto:
            self.base.escrever("DELETE FROM posicoes WHERE codigo = ? AND numero = ?", (codigo, str(numero)))
            return None
        self.base.escrever("INSERT OR REPLACE INTO posicoes (codigo, numero, texto, autor, atualizado_em) VALUES (?,?,?,?,?)",
                           (codigo, str(numero), texto, autor, datetime.now().isoformat(timespec="seconds")))
        return self.obter(codigo, numero)

    def listar(self) -> list[dict]:
        return self.base.buscar("SELECT * FROM posicoes ORDER BY codigo, CAST(numero AS INTEGER)")


# ------------------------------------------------------------ a fundamentação

def palavras_do_trecho(trecho: str) -> list[str]:
    """As palavras que contam, na ordem do texto (sem as de ligação e as de sempre das peças)."""
    return [p.lower() for p in re.findall(r"[A-Za-zÀ-ÿ]{4,}", trecho or "") if _plano(p.lower()) not in PARADAS and p.lower() not in PARADAS]


def palavras_chave(trecho: str, limite: int = 5) -> list[str]:
    contagem: dict[str, int] = {}
    ordem: dict[str, int] = {}
    for i, k in enumerate(palavras_do_trecho(trecho)):
        contagem[k] = contagem.get(k, 0) + 1
        ordem.setdefault(k, i)
    return [k for k, _ in sorted(contagem.items(), key=lambda x: (-x[1], ordem[x[0]]))[:limite]]


def pares_do_trecho(trecho: str, limite: int = 16) -> list[str]:
    """Pares de palavras vizinhas ("multa moratória", "cláusula penal"): o que o trecho diz, e não cada palavra solta."""
    ps = palavras_do_trecho(trecho)
    saida = []
    for a, b in zip(ps, ps[1:]):
        par = f"{a} {b}"
        if a != b and par not in saida:
            saida.append(par)
    return saida[:limite]


def sugerir(estado, trecho: str) -> dict:
    trecho = " ".join(str(trecho or "").split())[:4000]
    if len(trecho) < 12:
        raise ValueError("escolha um trecho da peça (uma frase ou um parágrafo)")
    temas, posicoes = estado.temas, estado.posicoes
    artigos: dict[str, dict] = {}
    for chave in artigos_citados(trecho):
        codigo, numero = chave.split(":")
        a = estado.leis.artigo(codigo, numero)
        if a:
            artigos[f"{a['codigo']}:{a['numero']}"] = dict(a, porque="citado no trecho", nota=99)
    chaves = palavras_chave(trecho)
    # Os pares de palavras vizinhas pesam 3; cada palavra sozinha, 1. Entra o
    # artigo que somou 3 ou mais: um par, ou três palavras do trecho.
    achados: dict[str, dict] = {}
    for termo, peso in [(par, 3) for par in pares_do_trecho(trecho)] + [(k, 1) for k in chaves]:
        # Cada par traz os 3 melhores: um par só não enche a lista.
        for a in estado.leis.procurar(termo, limite=3 if peso == 3 else 12):
            c = f"{a['codigo']}:{a['numero']}"
            x = achados.setdefault(c, dict(a, _termos=[], _nota=0))
            if termo not in x["_termos"]:
                x["_termos"].append(termo)
                x["_nota"] += peso
    # Em rodízio pelo primeiro termo de cada artigo: cada ideia do trecho ganha
    # lugar, e um assunto só não enche a lista.
    por_termo: dict[str, list] = {}
    for c, a in sorted(achados.items(), key=lambda x: -x[1]["_nota"]):
        if c not in artigos and a["_nota"] >= 3:
            por_termo.setdefault(a["_termos"][0], []).append((c, a))
    while len(artigos) < 8 and any(por_termo.values()):
        for termo in list(por_termo):
            if not por_termo[termo] or len(artigos) >= 8:
                continue
            c, a = por_termo[termo].pop(0)
            artigos[c] = dict({k: v for k, v in a.items() if not k.startswith("_")},
                              porque="tem “" + "”, “".join(a["_termos"][:3]) + "”", nota=a["_nota"])
    saida_artigos = []
    for a in sorted(artigos.values(), key=lambda x: -x["nota"]):
        pos = posicoes.obter(a["codigo"], a["numero"])
        saida_artigos.append({"codigo": a["codigo"], "numero": a["numero"], "citacao": a["citacao"], "texto": a["texto"][:900],
                              "revogado": a.get("revogado", False), "porque": a["porque"],
                              "posicao": pos["texto"] if pos else "",
                              "temas": [t["rotulo"] for t in temas.do_artigo(a["codigo"], a["numero"])][:4]})
    sumulas = []
    material = getattr(estado, "material", None)
    if material is not None and chaves:
        from biblioteca.rotas import procurar_sumulas

        vistos = set()
        for termo in (" ".join(chaves[:2]), chaves[0]):
            for s in procurar_sumulas(material, termo=termo, limite=6):
                if s["numero"] not in vistos:
                    vistos.add(s["numero"])
                    sumulas.append({"numero": s["numero"], "titulo": s["titulo"], "texto": s["texto"][:600], "porque": "tem " + termo})
            if len(sumulas) >= 4:
                break
    lista_temas = [{"rotulo": t["rotulo"], "numero": t["numero"], "tese": t["tese"], "questao": t["questao"],
                    "situacao": t["situacao"], "orgao": t["orgao"], "porque": f"{t['nota']} palavra(s) do trecho"}
                   for t in temas.procurar(" ".join(chaves), limite=5)]
    return {"palavras": chaves, "artigos": saida_artigos, "sumulas": sumulas[:4], "temas": lista_temas}


# ------------------------------------------------------------ na resposta da conversa (N7)

RE_TEMA_CITADO = re.compile(r"\btemas?\s+(?:repetitivos?\s+)?(?:n[º°o.]*\s*)?(\d{1,4})\b", re.IGNORECASE)
RE_SUMULA_CITADA = re.compile(r"\bs[úu]mulas?\s+(vinculantes?\s+)?(?:n[º°o.]*\s*)?(\d{1,3})(?:\s*/\s*|\s+d[oa]\s+|\s+)?(stj|stf)?",
                              re.IGNORECASE)
SIGLA = {"cc": "CC", "cpc": "CPC", "cdc": "CDC", "ctn": "CTN", "clt": "CLT", "cf": "CF", "cp": "CP", "cpp": "CPP",
         "eca": "ECA", "inquilinato": "Lei 8.245/1991", "ctb": "CTB"}
AVISO_RELACIONADOS = ("Ligados por regra aos artigos, temas e súmulas que a pergunta e a resposta citam — não pelo modelo. "
                      "Confira se se aplicam ao caso.")


def relacionados(estado, pergunta: str, resposta: str, fontes=None) -> dict | None:
    """
    O que a Biblioteca tem sobre os artigos que a conversa citou: os temas do
    STJ ligados a eles, as súmulas e os temas citados pelo número, e a posição
    da casa. Não muda a resposta: vai embaixo dela, dito de onde veio.
    """
    texto = f"{pergunta or ''}\n{resposta or ''}"
    artigos = artigos_citados(texto)
    for f in fontes or []:
        if isinstance(f, dict) and f.get("origem") == "lei" and f.get("codigo") and f.get("numero"):
            chave = f"{f['codigo']}:{str(f['numero']).replace('.', '')}"
            if chave not in artigos:
                artigos.append(chave)
    artigos = artigos[:8]
    temas = getattr(estado, "temas", None)
    saida_temas, vistos = [], set()
    if temas is not None:
        for m in RE_TEMA_CITADO.finditer(texto):
            for t in temas.procurar(numero=m.group(1))[:1]:
                if t["numero"] not in vistos:
                    vistos.add(t["numero"])
                    saida_temas.append(_tema_curto(t, f"a conversa cita o {t['rotulo']}"))
        for chave in artigos:
            codigo, numero = chave.split(":")
            for t in temas.do_artigo(codigo, numero)[:3]:
                if t["numero"] not in vistos:
                    vistos.add(t["numero"])
                    saida_temas.append(_tema_curto(t, f"a tese cita o art. {numero} do {SIGLA.get(codigo, codigo.upper())}"))
    saida_sumulas = []
    material = getattr(estado, "material", None)
    if material is not None:
        from biblioteca.rotas import procurar_sumulas

        for m in RE_SUMULA_CITADA.finditer(texto):
            # A vinculante é do STF; sem tribunal escrito, a do STJ (a que o PAULUS tem por inteiro).
            numero = m.group(2)
            tribunal = (m.group(3) or ("stf" if m.group(1) else "stj")).lower()
            if tribunal != "stj" or any(x["numero"] == numero for x in saida_sumulas):
                continue
            for x in procurar_sumulas(material, numero=numero, limite=1):
                saida_sumulas.append({"numero": x["numero"], "titulo": x["titulo"], "texto": x["texto"][:600],
                                      "porque": f"a conversa cita a Súmula {x['numero']}/STJ"})
    saida_posicoes = []
    posicoes = getattr(estado, "posicoes", None)
    if posicoes is not None:
        for chave in artigos:
            codigo, numero = chave.split(":")
            pos = posicoes.obter(codigo, numero)
            if pos:
                saida_posicoes.append({"artigo": f"art. {numero} do {SIGLA.get(codigo, codigo.upper())}", "texto": pos["texto"][:600],
                                       "autor": pos.get("autor") or ""})
    if not (saida_temas or saida_sumulas or saida_posicoes):
        return None
    return {"artigos": [f"art. {c.split(':')[1]} do {SIGLA.get(c.split(':')[0], c.split(':')[0].upper())}" for c in artigos],
            "temas": saida_temas[:6], "sumulas": saida_sumulas[:4], "posicoes": saida_posicoes[:4], "aviso": AVISO_RELACIONADOS}


def _tema_curto(t: dict, porque: str) -> dict:
    return {"rotulo": t["rotulo"], "numero": t["numero"], "tese": (t.get("tese") or "")[:700], "questao": (t.get("questao") or "")[:400],
            "situacao": t.get("situacao") or "", "orgao": t.get("orgao") or "", "porque": porque}


# ------------------------------------------------------------------ rotas

class Trecho(BaseModel):
    trecho: str = ""


class Posicao(BaseModel):
    codigo: str
    numero: str
    texto: str = ""


def montar(estado, app) -> None:
    import threading

    from acesso import rotas as rotas_do_acesso

    estado.temas = Temas(estado.base)
    estado.posicoes = Posicoes(estado.base)
    threading.Thread(target=lambda: estado.temas.instalar(), name="temas-stj", daemon=True).start()

    @app.post("/api/biblioteca/fundamentacao")
    def biblioteca_fundamentacao(payload: Trecho) -> dict:
        try:
            return sugerir(estado, payload.trecho)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.get("/api/biblioteca/temas")
    def biblioteca_temas(termo: str = "", numero: str = "", codigo: str = "", artigo: str = "") -> dict:
        if codigo and artigo:
            lista = estado.temas.do_artigo(codigo, artigo)
        else:
            lista = estado.temas.procurar(termo, numero)
        fonte = estado.base.um("SELECT fonte FROM temas LIMIT 1") or {}
        return {"temas": lista, "total": estado.temas.quantos(), "fonte": fonte.get("fonte", ""),
                "licenca": "CC-BY · Portal de Dados Abertos do STJ"}

    @app.post("/api/biblioteca/temas/atualizar")
    def biblioteca_temas_atualizar() -> dict:
        try:
            return estado.temas.atualizar_do_stj()
        except Exception as exc:  # noqa: BLE001 - rede, portal fora: dito, nada trocado
            raise HTTPException(status_code=502, detail=f"não consegui baixar do STJ agora: {exc}") from None

    @app.get("/api/leis/posicao")
    def leis_posicao(codigo: str, numero: str) -> dict:
        return {"posicao": estado.posicoes.obter(codigo, numero)}

    @app.put("/api/leis/posicao")
    def leis_posicao_gravar(payload: Posicao, request: Request = None) -> dict:
        rotas_do_acesso.so_local(request)
        return {"posicao": estado.posicoes.gravar(payload.codigo, payload.numero, payload.texto, autor="titular")}

    @app.get("/api/leis/posicoes")
    def leis_posicoes() -> dict:
        return {"posicoes": estado.posicoes.listar()}
