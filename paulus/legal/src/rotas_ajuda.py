"""
As rotas da ajuda sem pergunta (I9, src/ajuda.py): o cartao do documento, a
correcao de um fato e os prazos que viram proposta em Aprovacoes.

Moram aqui, e nao no api.py: o api.py so chama `montar`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

import ajuda


class Correcao(BaseModel):
    nome: str
    secao: str
    id: str
    valor: str


class DoDocumento(BaseModel):
    nome: str


def _documento(estado, nome: str):
    doc = next((d for d in estado.searcher.documents if d.name == nome), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="documento não está no Acervo")
    return doc


def _meta(estado, doc):
    metas, _ = estado.saber.metadados_de([doc])
    return metas[0] if metas else None


def ligada(estado) -> bool:
    return bool((estado.prefs.dados.get("ia") or {}).get("ajuda", True))


def propor_prazos(estado, meta, nome: str) -> int:
    """
    Os prazos conferidos do documento, cada um como pedido em Aprovacoes -
    uma vez so: o mesmo prazo do mesmo documento nao volta a ser proposto,
    tenha sido aceito ou recusado.
    """
    if meta is None or not ligada(estado):
        return 0
    ja = {(p.dados.get("documento"), p.dados.get("item")) for p in estado.fila._itens.values()
          if p.acao == "ajuda.prazo"}
    novos = 0
    for prazo in ajuda.prazos(meta, nome):
        if (nome, prazo["item"]) in ja:
            continue
        onde = f", p. {prazo['pagina']}" if prazo.get("pagina") else ""
        estado.fila.pedir(
            prazo["titulo"] + " — anotar?", "agenda", acao="ajuda.prazo",
            resumo=f"Achei no documento{onde}: “{prazo['quote']}”. Aprovar anota uma tarefa com esse prazo na Agenda.",
            etiquetas=["da leitura do documento"], prazo=prazo["data"], pedido_por="Leitura do documento",
            dados={"documento": nome, "item": prazo["item"], "data": prazo["data"], "titulo": prazo["titulo"],
                   "pagina": prazo.get("pagina"), "quote": prazo["quote"]})
        novos += 1
    return novos


def executar_prazo(estado, pedido) -> str:
    """O sim em Aprovacoes: a tarefa com o prazo, na Agenda."""
    d = pedido.dados
    onde = f", p. {d['pagina']}" if d.get("pagina") else ""
    estado.tarefas.salvar({"titulo": d["titulo"], "prazo": d["data"],
                           "anotacao": f"Do documento {d['documento']}{onde}: “{d.get('quote', '')}”"}, None)
    return f"tarefa anotada na Agenda para {d['data'][8:10]}/{d['data'][5:7]}/{d['data'][:4]}"


def montar(estado, app, dados_dir: Path) -> None:
    conjunto = Path(dados_dir) / "medicao" / "conjunto-real.jsonl"

    @app.get("/api/ajuda/documento")
    def ajuda_documento(nome: str) -> dict:
        """O cartao do documento, as perguntas que respondem na hora e os prazos achados."""
        doc = _documento(estado, nome)
        meta = _meta(estado, doc)
        if meta is None or not ligada(estado):
            return {"cartao": None, "sugestoes": [], "prazos": [], "analisado": meta is not None}
        return {"cartao": ajuda.cartao(meta, doc.name), "sugestoes": ajuda.sugestoes(estado.saber, doc),
                "prazos": ajuda.prazos(meta, doc.name), "analisado": True}

    @app.post("/api/ajuda/corrigir")
    def ajuda_corrigir(payload: Correcao) -> dict:
        """O valor certo de um fato do cartao: grava como `manual` e vira pergunta do conjunto real."""
        doc = _documento(estado, payload.nome)
        meta = _meta(estado, doc)
        if meta is None:
            raise HTTPException(status_code=409, detail="este documento ainda não foi lido")
        try:
            feito = ajuda.corrigir(estado.saber.biblioteca, meta, doc.name, payload.secao, payload.id,
                                   payload.valor, conjunto)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {**feito, "cartao": ajuda.cartao(meta, doc.name)}

    @app.post("/api/ajuda/prazos")
    def ajuda_prazos(payload: DoDocumento) -> dict:
        """Propor em Aprovacoes os prazos do documento que ainda nao foram propostos."""
        doc = _documento(estado, payload.nome)
        return {"propostos": propor_prazos(estado, _meta(estado, doc), doc.name)}
