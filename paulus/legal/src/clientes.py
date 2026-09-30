"""
Visão por cliente e muralha ética (docs/PLANO-PILOTO.md, L3).

A mesma base para as duas coisas: reconhecer que "Empresa X Ltda.",
"EMPRESA X" e "Empresa X - ME" são a mesma entidade.

- **A entidade** (`chave`, `mesma`): sem acento, sem pontuação, sem a forma
  jurídica (Ltda., S/A, ME, EPP, EIRELI...) e sem "de/da/do". Com os dois
  documentos, manda o documento: CPF igual, ou a mesma raiz do CNPJ (os 8
  primeiros dígitos: a matriz e as filiais), é a mesma; documento diferente
  não é, mesmo com o nome igual. Sem documento, o nome: chave igual é "a
  mesma"; quase igual (as palavras quase todas em comum) é "parece ser" -
  e a tela diz qual das duas.
- **A parte contrária** de cada Serviço (`servicos.partes`, migração 029).
- **Conflito de interesse** (`conflitos`): o cliente que é parte contrária em
  outro Serviço, e a parte contrária que é cliente do escritório. Avisa, não
  bloqueia: quem decide é o advogado.
- **Muralha ética**: a separação por equipe já existe (quem não está na
  equipe não vê o Serviço de fora). O conflito diz, além disso, quem está na
  equipe dos dois lados - é essa pessoa que a muralha precisa separar.
- **Tudo sobre o cliente** (`visao`): os Serviços, os processos (L2), os
  prazos e compromissos, os documentos (os ligados e os em que ele aparece
  como parte, pelo nome ou pelo documento), as partes contrárias, os outros
  nomes com que ele aparece e os conflitos.
"""

from __future__ import annotations

import json
import re
import unicodedata

from fastapi import HTTPException, Request
from pydantic import BaseModel

FORMAS = {"ltda", "limitada", "me", "epp", "eireli", "sa", "cia", "companhia", "mei", "slu", "ss", "sociedade",
          "anonima", "empresarial", "simples", "unipessoal"}
LIGA = {"de", "da", "do", "das", "dos", "e", "a", "o"}
PAPEIS = {"contraria": "parte contrária", "interessado": "interessado"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c))


def palavras(nome: str) -> list[str]:
    t = _sem_acento(nome).lower().replace("&", " e ")
    t = re.sub(r"\bs\s*/\s*a\b|\bs\.\s*a\.?(?=\s|$)", " sa ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return [p for p in t.split() if p not in FORMAS and p not in LIGA]


def chave(nome: str) -> str:
    return " ".join(palavras(nome))


def digitos(doc: str) -> str:
    return re.sub(r"\D", "", str(doc or ""))


def mesma(nome_a: str, doc_a: str, nome_b: str, doc_b: str) -> str:
    """"igual", "parecida" ou "" - se as duas são a mesma entidade."""
    da, db = digitos(doc_a), digitos(doc_b)
    if len(da) in (11, 14) and len(db) in (11, 14):
        if da == db or (len(da) == 14 and len(db) == 14 and da[:8] == db[:8]):
            return "igual"
        return ""
    ka, kb = chave(nome_a), chave(nome_b)
    if not ka or not kb:
        return ""
    if ka == kb:
        return "igual"
    pa, pb = set(ka.split()), set(kb.split())
    if min(len(pa), len(pb)) >= 2:
        comum = len(pa & pb) / len(pa | pb)
        if comum >= 0.75 or (pa <= pb or pb <= pa) and len(pa & pb) >= 2:
            return "parecida"
    return ""


def _json(bruto, padrao):
    try:
        return json.loads(bruto) if isinstance(bruto, str) else (bruto or padrao)
    except ValueError:
        return padrao


def limpar_partes(bruto) -> list[dict]:
    saida = []
    for p in bruto or []:
        nome = " ".join(str((p or {}).get("nome") or "").split())[:160]
        if not nome:
            continue
        papel = (p or {}).get("papel") if (p or {}).get("papel") in PAPEIS else "contraria"
        saida.append({"nome": nome, "documento": str((p or {}).get("documento") or "")[:20], "papel": papel})
    return saida[:40]


# ------------------------------------------------------------ o conflito

def _equipe(base, servico_id) -> dict[int, str]:
    l = base.um("SELECT equipe FROM servicos WHERE id = ?", (int(servico_id),)) if servico_id else None
    ids = _json((l or {}).get("equipe"), [])
    if not ids:
        return {}
    marcas = ",".join("?" * len(ids))
    return {int(x["id"]): x["nome"] for x in base.buscar(f"SELECT id, nome FROM cadastros WHERE id IN ({marcas})", tuple(ids))}


def conflitos(base, nome: str, documento: str = "", *, papel: str = "cliente", servico_id=None, cadastro_id=None) -> list[dict]:
    """
    Onde esta entidade já aparece do outro lado. `papel`: "cliente" (a ficha
    de um cliente, ou o cliente de um Serviço) ou "contraria" (a parte
    contrária sendo posta em `servico_id`).
    """
    saida: list[dict] = []
    if not chave(nome) and len(digitos(documento)) not in (11, 14):
        return saida
    if papel == "contraria":
        proprio = (base.um("SELECT cadastro_id FROM servicos WHERE id = ?", (int(servico_id),)) or {}).get("cadastro_id") if servico_id else None
        minha_equipe = _equipe(base, servico_id)
        for c in base.buscar("SELECT id, nome, documento FROM cadastros WHERE tipo = 'cliente'"):
            grau = mesma(nome, documento, c["nome"], c["documento"])
            if not grau:
                continue
            if proprio and int(c["id"]) == int(proprio):
                saida.append({"tipo": "proprio", "grau": grau, "cadastro_id": c["id"],
                              "texto": f"“{c['nome']}” é o próprio cliente deste Serviço"})
                continue
            saida.append({"tipo": "cliente", "grau": grau, "cadastro_id": c["id"],
                          "texto": ("" if grau == "igual" else "parece ser: ") + f"“{c['nome']}” é cliente do escritório"})
            for s in base.buscar("SELECT id, nome FROM servicos WHERE cadastro_id = ? AND status != 'concluido'", (c["id"],)):
                dos_dois = sorted(set(minha_equipe) & set(_equipe(base, s["id"])))
                for pid in dos_dois:
                    saida.append({"tipo": "muralha", "grau": grau, "servico_id": s["id"], "pessoa_id": pid,
                                  "texto": f"{minha_equipe[pid]} está na equipe dos dois lados: deste Serviço e de “{s['nome']}”"})
        return saida
    for s in base.buscar("SELECT s.id, s.nome, s.partes, s.cadastro_id, c.nome AS cliente FROM servicos s"
                         " LEFT JOIN cadastros c ON c.id = s.cadastro_id WHERE s.partes IS NOT NULL AND s.partes != '[]'"):
        if servico_id and int(s["id"]) == int(servico_id):
            continue
        for p in _json(s["partes"], []):
            if p.get("papel") != "contraria":
                continue
            grau = mesma(nome, documento, p.get("nome", ""), p.get("documento", ""))
            if grau:
                saida.append({"tipo": "contraria", "grau": grau, "servico_id": s["id"],
                              "texto": ("" if grau == "igual" else "parece ser: ") + f"“{p['nome']}” é parte contrária no Serviço “{s['nome']}”"
                                       + (f" (cliente {s['cliente']})" if s.get("cliente") else "")})
    return saida


# ------------------------------------------------------------ tudo sobre o cliente

def _partes_nos_documentos(base) -> list[dict]:
    return base.buscar(
        "SELECT f.mostrar, f.chave, d.titulo, d.caminho FROM meta_fatos f JOIN meta_documentos d ON d.versao_atual = f.versao_id"
        " WHERE f.secao = 'parties'")


def visao(estado, cadastro_id: int) -> dict:
    base = estado.base
    c = base.um("SELECT * FROM cadastros WHERE id = ?", (int(cadastro_id),))
    if not c:
        raise LookupError("cadastro não encontrado")
    servicos = base.buscar("SELECT id, nome, status, partes FROM servicos WHERE cadastro_id = ? ORDER BY atualizado_em DESC", (c["id"],))
    ids = [int(s["id"]) for s in servicos]
    marcas = ",".join("?" * len(ids)) or "NULL"
    processos = []
    if getattr(estado, "processos", None) is not None and ids:
        processos = [p for p in estado.processos.listar() if p.get("servico_id") in ids]
    prazos = base.buscar(
        f"SELECT id, titulo, prazo, lista, servico_id FROM tarefas WHERE concluida = 0 AND (cadastro_id = ? OR servico_id IN ({marcas}))"
        " ORDER BY CASE WHEN prazo = '' THEN 1 ELSE 0 END, prazo LIMIT 40", (c["id"], *ids))
    compromissos = base.buscar(
        f"SELECT id, titulo, data, hora FROM compromissos WHERE data >= date('now') AND (cadastro_id = ? OR servico_id IN ({marcas}))"
        " ORDER BY data, hora LIMIT 20", (c["id"], *ids))
    documentos: dict[str, dict] = {}
    for v in base.buscar("SELECT nome FROM vinculos WHERE tipo = 'cadastro' AND alvo_id = ?", (c["id"],)):
        documentos.setdefault(v["nome"], {"nome": v["nome"], "como": "ligado à ficha"})
    for v in base.buscar(f"SELECT nome FROM vinculos WHERE tipo = 'servico' AND alvo_id IN ({marcas})", tuple(ids)):
        documentos.setdefault(v["nome"], {"nome": v["nome"], "como": "de um Serviço"})
    outros_nomes: dict[str, str] = {}
    for f in _partes_nos_documentos(base):
        grau = mesma(c["nome"], c.get("documento") or "", f["mostrar"], "")
        if not grau:
            continue
        nome_doc = f["titulo"] or f["caminho"]
        documentos.setdefault(nome_doc, {"nome": nome_doc, "como": "aparece como parte" + ("" if grau == "igual" else " (parece ser)")})
        if chave(f["mostrar"]) != chave(c["nome"]) or f["mostrar"].strip() != c["nome"].strip():
            outros_nomes.setdefault(f["mostrar"].strip(), grau)
    contrarias = []
    for s in servicos:
        for p in _json(s.get("partes"), []):
            if p.get("papel") == "contraria":
                contrarias.append({"nome": p["nome"], "documento": p.get("documento", ""), "servico": s["nome"], "servico_id": s["id"]})
    return {
        "cliente": {k: c.get(k) for k in ("id", "tipo", "nome", "documento", "email", "telefone")},
        "servicos": [{"id": s["id"], "nome": s["nome"], "status": s["status"]} for s in servicos],
        "processos": [{"id": p["id"], "numero_fmt": p["numero_fmt"], "servico_nome": p.get("servico_nome"), "novas": p.get("novas", 0),
                       "classe": p.get("classe", "")} for p in processos],
        "prazos": prazos, "compromissos": compromissos,
        "documentos": sorted(documentos.values(), key=lambda d: d["nome"].lower())[:80],
        "partes_contrarias": contrarias,
        "outros_nomes": [{"nome": n, "grau": g} for n, g in sorted(outros_nomes.items())][:20],
        "conflitos": conflitos(base, c["nome"], c.get("documento") or "", papel="cliente", cadastro_id=c["id"])
                     if c.get("tipo") == "cliente" else [],
    }


# ------------------------------------------------------------------ rotas

class Partes(BaseModel):
    partes: list[dict] = []


class Consulta(BaseModel):
    nome: str = ""
    documento: str = ""
    papel: str = "cliente"
    servico_id: int | None = None
    cadastro_id: int | None = None


def montar(estado, app) -> None:
    import servicos_acesso

    @app.put("/api/servicos/{id_}/partes")
    def servicos_partes(id_: int, payload: Partes, request: Request = None) -> dict:
        if not estado.base.um("SELECT id FROM servicos WHERE id = ?", (id_,)) or not servicos_acesso.visivel(id_):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        partes = limpar_partes(payload.partes)
        estado.base.escrever("UPDATE servicos SET partes = ? WHERE id = ?", (json.dumps(partes, ensure_ascii=False), id_))
        achados = []
        for p in partes:
            if p["papel"] == "contraria":
                for x in conflitos(estado.base, p["nome"], p["documento"], papel="contraria", servico_id=id_):
                    achados.append(dict(x, parte=p["nome"]))
        return {"partes": partes, "conflitos": achados}

    @app.get("/api/servicos/{id_}/conflitos")
    def servicos_conflitos(id_: int) -> dict:
        """Os conflitos deste Serviço: o cliente dele do outro lado em outro Serviço, e as partes contrárias dele que são clientes."""
        s = estado.base.um("SELECT s.id, s.partes, c.nome, c.documento FROM servicos s LEFT JOIN cadastros c ON c.id = s.cadastro_id"
                           " WHERE s.id = ?", (id_,))
        if not s:
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        achados = [dict(x, parte=s["nome"]) for x in conflitos(estado.base, s.get("nome") or "", s.get("documento") or "",
                                                              papel="cliente", servico_id=id_)] if s.get("nome") else []
        for p in _json(s["partes"], []):
            if p.get("papel") == "contraria":
                achados += [dict(x, parte=p["nome"]) for x in conflitos(estado.base, p["nome"], p.get("documento", ""),
                                                                      papel="contraria", servico_id=id_)]
        return {"conflitos": achados}

    @app.post("/api/clientes/conflitos")
    def clientes_conflitos(payload: Consulta) -> dict:
        return {"conflitos": conflitos(estado.base, payload.nome, payload.documento, papel=payload.papel,
                                       servico_id=payload.servico_id, cadastro_id=payload.cadastro_id)}

    @app.get("/api/clientes/{cadastro_id}/visao")
    def clientes_visao(cadastro_id: int) -> dict:
        try:
            return visao(estado, cadastro_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
