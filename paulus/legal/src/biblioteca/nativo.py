"""
O acervo que já vem com o PAULUS (config/acervo-inicial/, montado por
tools/acervo_inicial.py): a Constituição e os códigos, no texto compilado do
Planalto, e os enunciados das súmulas do STJ, do STF e das vinculantes (N8).

Na abertura, o que ainda não entrou nesta máquina entra - uma vez só. O que
entrou fica anotado em <dados>/leis/acervo-inicial.json: quem apagar um código
ou as súmulas não os vê voltar na abertura seguinte. Nada sai da máquina: os
arquivos estão no instalador.

Servidor de teste (PAULUS_SEM_AVISOS) e PAULUS_ACERVO_INICIAL=0 não instalam.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
from datetime import datetime
from pathlib import Path

ACERVO = Path(__file__).resolve().parents[2] / "config" / "acervo-inicial"
_trava = threading.Lock()


def indice() -> dict:
    try:
        return json.loads((ACERVO / "indice.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"codigos": {}, "sumulas": {}}


def _registro(pasta_leis: Path) -> dict:
    try:
        return json.loads((pasta_leis / "acervo-inicial.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"codigos": {}, "sumulas": {}}


def _salvar(pasta_leis: Path, reg: dict) -> None:
    pasta_leis.mkdir(parents=True, exist_ok=True)
    (pasta_leis / "acervo-inicial.json").write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def ficha_das_sumulas(nome: str) -> dict:
    from biblioteca import ficha as ficha_mod

    tribunal = {"Súmulas do STJ": "Superior Tribunal de Justiça", "Súmulas do STF": "Supremo Tribunal Federal",
                "Súmulas vinculantes do STF": "Supremo Tribunal Federal"}.get(nome, "")
    # O STJ uniformiza a lei federal: as súmulas dele são destas áreas (o
    # trabalho é do TST, e a Constituição, do STF). Os enunciados quase não
    # citam lei, e a regra das áreas por citação (ficha.areas_sugeridas) só
    # acharia "penal".
    areas = ["civil", "consumidor", "processo civil", "penal", "processo penal", "tributário", "administrativo",
             "previdenciário", "empresarial", "família e sucessões"] if tribunal else []
    # O STF guarda a Constituição (N8): as súmulas dele são de todas essas e do constitucional e do trabalho.
    if tribunal == "Supremo Tribunal Federal":
        areas = ["constitucional"] + areas + ["trabalho"]
    return {**ficha_mod.vazia("sumulas"), "titulo": nome, "autor": tribunal, "origem": "oficial",
            "areas": areas, "confirmada": True}


def texto_das_sumulas(chave: str) -> str:
    dados = indice()["sumulas"].get(chave) or {}
    return gzip.decompress((ACERVO / dados["arquivo"]).read_bytes()).decode("utf-8") if dados else ""


def desligado() -> bool:
    return bool(os.environ.get("PAULUS_SEM_AVISOS")) or os.environ.get("PAULUS_ACERVO_INICIAL") == "0"


def instalar(leis, material, pasta_leis: Path, *, forcar: bool = False) -> dict:
    """
    Põe o que falta do acervo. Devolve {'codigos': [...entraram], 'sumulas': [...], 'erros': [...]}.
    `forcar` põe de novo também o que já foi posto e depois apagado (o botão da tela).
    """
    feito = {"codigos": [], "sumulas": [], "erros": []}
    if not forcar and desligado():
        return feito
    idx = indice()
    with _trava:
        reg = _registro(Path(pasta_leis))
        ja = {l["codigo"] for l in leis.instalados() if l["instalado"]}
        for codigo, dados in idx.get("codigos", {}).items():
            if codigo in ja or (codigo in reg["codigos"] and not forcar):
                reg["codigos"].setdefault(codigo, {"em": "", "ja_estava": True})
                continue
            try:
                Path(pasta_leis).mkdir(parents=True, exist_ok=True)
                alvo = Path(pasta_leis) / dados["arquivo"].removesuffix(".gz")
                alvo.write_bytes(gzip.decompress((ACERVO / dados["arquivo"]).read_bytes()))
                r = leis.importar(alvo, codigo)
            except (OSError, ValueError, KeyError) as exc:
                feito["erros"].append(f"{codigo}: {exc}")
                continue
            reg["codigos"][codigo] = {"em": datetime.now().isoformat(timespec="seconds"), "artigos": r["artigos"]}
            feito["codigos"].append(codigo)
        for chave, dados in idx.get("sumulas", {}).items():
            existe = material.item(reg["sumulas"].get(chave, {}).get("id", "")) if reg["sumulas"].get(chave) else None
            if existe or (chave in reg["sumulas"] and not forcar):
                continue
            try:
                item = material.absorver_texto(dados["nome"], texto_das_sumulas(chave), ficha_das_sumulas(dados["nome"]))
            except (OSError, ValueError, KeyError) as exc:
                feito["erros"].append(f"súmulas {chave}: {exc}")
                continue
            reg["sumulas"][chave] = {"em": datetime.now().isoformat(timespec="seconds"), "id": item["id"]}
            feito["sumulas"].append(chave)
        reg["montado_em"] = idx.get("montado_em", "")
        _salvar(Path(pasta_leis), reg)
    return feito


def situacao(leis, material, pasta_leis: Path) -> dict:
    """Para a tela: o que o acervo traz e o que está nesta máquina."""
    idx, reg = indice(), _registro(Path(pasta_leis))
    ja = {l["codigo"]: l for l in leis.instalados()}
    codigos = [{"codigo": c, "nome": ja.get(c, {}).get("nome", c), "artigos": d.get("artigos", 0),
                "instalado": bool(ja.get(c, {}).get("instalado"))} for c, d in idx.get("codigos", {}).items()]
    sumulas = []
    for chave, d in idx.get("sumulas", {}).items():
        id_ = (reg["sumulas"].get(chave) or {}).get("id", "")
        sumulas.append({"chave": chave, "nome": d["nome"], "enunciados": d["enunciados"],
                        "instalado": bool(id_ and material.item(id_)), "id": id_ if id_ and material.item(id_) else ""})
    return {"montado_em": idx.get("montado_em", ""), "codigos": codigos, "sumulas": sumulas,
            "falta": sum(not c["instalado"] for c in codigos) + sum(not s["instalado"] for s in sumulas)}
