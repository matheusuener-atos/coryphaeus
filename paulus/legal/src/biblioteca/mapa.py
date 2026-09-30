"""
O que o PAULUS sabe (M7): a biblioteca por área, e o aviso de fora da
cobertura.

Antes, o PAULUS não sabia o que sabia: uma pergunta de direito tributário
num escritório sem nada de tributário era respondida só pelos documentos, e
quem lia não tinha como saber que a biblioteca não tinha o assunto. Agora:

- **a área da pergunta, por regra:** o artigo citado com o código decide ("art.
  150 do CTN" é tributário); sem artigo, o vocabulário curto de cada área,
  escrito à mão em config/areas-biblioteca.json. Empate ou nada: área não
  identificada, e nenhum aviso;
- **a cobertura:** a área tem obra (pela ficha) ou lei instalada (pelo
  código);
- **fora da cobertura:** a resposta segue normalmente (documentos e modelo) e
  ganha, no fim, "Não tenho material de <área> na biblioteca; esta resposta
  usa só os documentos." **Nunca bloqueia a resposta.** Se a biblioteca
  trouxe algo para a pergunta (o manual, por exemplo), não há aviso: a
  resposta usou a biblioteca.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from biblioteca.ficha import AREA_DO_INSTRUMENTO, AREAS

VOCABULARIO = Path(__file__).resolve().parents[2] / "config" / "areas-biblioteca.json"

# A área de cada código de src/leis.py.
AREA_DO_CODIGO = {"cc": "civil", "cpc": "processo civil", "cp": "penal", "clt": "trabalho", "cdc": "consumidor",
                  "cf": "constitucional", "ctn": "tributário", "eca": "família e sucessões",
                  "inquilinato": "imobiliário"}

_vocabulario: dict[str, list[str]] | None = None


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


def vocabulario() -> dict[str, list[str]]:
    global _vocabulario
    if _vocabulario is None:
        try:
            bruto = json.loads(VOCABULARIO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bruto = {}
        _vocabulario = {a: [_plano(t) for t in termos] for a, termos in bruto.items() if a in AREAS}
    return _vocabulario


def area_da_pergunta(pergunta: str) -> str:
    """A área da pergunta, ou "" quando não dá para saber sem chutar."""
    from inteligencia.extratores import regras_leis

    contagem: dict[str, int] = {}
    for a in regras_leis.achar(pergunta or ""):
        area = AREA_DO_INSTRUMENTO.get(a["dados"].get("instrument_id", ""))
        if area:
            contagem[area] = contagem.get(area, 0) + 1
    if not contagem:
        plano = " " + re.sub(r"[^\w\s-]", " ", _plano(pergunta)) + " "
        for area, termos in vocabulario().items():
            n = sum(1 for t in termos if f" {t} " in plano)
            if n:
                contagem[area] = n
    if not contagem:
        return ""
    melhor = max(contagem.values())
    primeiras = [a for a, n in contagem.items() if n == melhor]
    return primeiras[0] if len(primeiras) == 1 else ""


def cobertura(material, leis) -> dict[str, dict]:
    """Por área: as obras (pela ficha) e as leis instaladas."""
    saida: dict[str, dict] = {a: {"obras": [], "leis": []} for a in AREAS}
    for item in getattr(material, "itens", []) or []:
        ficha = item.get("ficha") or {}
        for area in ficha.get("areas") or []:
            if area in saida:
                saida[area]["obras"].append(item)
    if leis is not None:
        for lei in leis.instalados():
            area = AREA_DO_CODIGO.get(lei["codigo"])
            if lei["instalado"] and area:
                saida[area]["leis"].append(lei)
    return saida


def fora_da_cobertura(pergunta: str, material, leis) -> str:
    """A área da pergunta quando a biblioteca não tem nada dela; senão ""."""
    area = area_da_pergunta(pergunta)
    if not area:
        return ""
    c = cobertura(material, leis).get(area) or {}
    return "" if c.get("obras") or c.get("leis") else area


def linha_de_aviso(area: str) -> str:
    return f"Não tenho material de {area} na biblioteca; esta resposta usa só os documentos."


def painel(material, leis, contextos=None) -> dict:
    """A tela Biblioteca: por área, as obras, as leis e os lembretes; por código, as anotações."""
    from biblioteca.ficha import ROTULO_DO_TIPO

    c = cobertura(material, leis)
    lembretes = []
    if contextos is not None:
        try:
            lembretes = contextos.para_tela().get("contextos") or []
        except Exception:  # noqa: BLE001 - sem lembretes, a tela mostra o resto
            lembretes = []
    areas = []
    for area in AREAS:
        obras, leis_da = c[area]["obras"], c[area]["leis"]
        if obras or leis_da:
            areas.append({"area": area,
                          "obras": [{"id": o["id"], "titulo": (o.get("ficha") or {}).get("titulo") or o["nome"],
                                     "autor": (o.get("ficha") or {}).get("autor", ""),
                                     "ano": (o.get("ficha") or {}).get("ano", ""),
                                     "tipo": ROTULO_DO_TIPO.get((o.get("ficha") or {}).get("tipo", ""), "")}
                                    for o in obras],
                          "leis": [{"codigo": l["codigo"], "nome": l["nome"], "artigos": l["artigos"]} for l in leis_da]})
    sem_area = [{"id": o["id"], "titulo": (o.get("ficha") or {}).get("titulo") or o["nome"],
                 "tipo": ROTULO_DO_TIPO.get((o.get("ficha") or {}).get("tipo", ""), "")}
                for o in getattr(material, "itens", []) or [] if not (o.get("ficha") or {}).get("areas")]
    anotacoes = {}
    if material is not None and material.chave("anotacoes"):
        anotacoes = material.anotacoes.contagem()
    codigos = []
    if leis is not None:
        for lei in leis.instalados():
            if lei["instalado"]:
                a = anotacoes.get(lei["codigo"], {"artigos": 0, "anotacoes": 0, "mais_comentados": []})
                codigos.append({"codigo": lei["codigo"], "nome": lei["nome"], "artigos": lei["artigos"],
                                "anotados": a["artigos"], "anotacoes": a["anotacoes"],
                                "mais_comentados": a["mais_comentados"]})
    return {"areas": areas, "sem_area": sem_area, "codigos": codigos, "lembretes": len(lembretes),
            "gavetas": sorted({x.get("gaveta", "") for x in lembretes if x.get("gaveta")})}
