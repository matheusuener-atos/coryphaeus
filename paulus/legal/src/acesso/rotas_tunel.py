"""
As rotas do assistente de conexao (R7). Todas so pela janela local: ligar,
desligar, trocar a porta e remover o acesso de fora e mexer na propria
seguranca - uma sessao de fora nao pode fazer nada disso, nem por engano de
politica (a rota confere de novo).
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel

from acesso.conexao import ErroConexao
from acesso.rotas import so_local


class PedidoDeConexao(BaseModel):
    nome: str
    email: str


class Ligar(BaseModel):
    ligado: bool


def montar(servico, conexao, r) -> None:
    def falhar(exc: Exception):
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    @r.get("/api/acesso/tunel")
    def tunel_situacao(request: Request) -> dict:
        so_local(request)
        return {"situacao": servico.situacao(), "conexao": conexao.andamento(),
                "titulares": [{"nome": c["nome"], "email": c["email"]} for c in conexao.titulares_prontos()],
                "energia": servico.energia() if hasattr(servico, "energia") else {}}

    @r.post("/api/acesso/tunel/conectar")
    def tunel_conectar(dados: PedidoDeConexao, request: Request) -> dict:
        so_local(request)
        try:
            return conexao.iniciar(dados.nome, dados.email)
        except ErroConexao as exc:
            falhar(exc)

    @r.post("/api/acesso/tunel/cancelar")
    def tunel_cancelar(request: Request) -> dict:
        so_local(request)
        conexao.cancelar()
        return {"ok": True}

    @r.post("/api/acesso/tunel/ligar")
    def tunel_ligar(dados: Ligar, request: Request) -> dict:
        so_local(request)
        conexao.ligar(dados.ligado)
        return {"situacao": servico.situacao()}

    @r.post("/api/acesso/tunel/porta")
    def tunel_porta(request: Request) -> dict:
        so_local(request)
        try:
            return {"porta": conexao.trocar_porta(), "situacao": servico.situacao()}
        except ErroConexao as exc:
            falhar(exc)

    @r.post("/api/acesso/tunel/sincronizar")
    def tunel_sincronizar(request: Request) -> dict:
        so_local(request)
        conexao.sincronizar_emails()
        return {"ok": not conexao.erro, "erro": conexao.erro}

    @r.post("/api/acesso/tunel/remover")
    def tunel_remover(request: Request) -> dict:
        so_local(request)
        try:
            return conexao.remover()
        except ErroConexao as exc:
            falhar(exc)
