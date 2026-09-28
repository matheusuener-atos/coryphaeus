"""
As rotas da conexao do acesso de fora (R7). Todas so pela janela local:
escolher o endereco, conectar, ligar, desligar, trocar a porta e remover o
acesso de fora e mexer na propria seguranca - uma sessao de fora nao pode
fazer nada disso, nem por engano de politica (a rota confere de novo).
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel

from acesso.conexao import ErroConexao, sugerir_endereco
from acesso.rotas import so_local


class PedidoDeConexao(BaseModel):
    nome: str
    slug: str


class Ligar(BaseModel):
    ligado: bool


def montar(servico, conexao, r) -> None:
    def falhar(exc: Exception):
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def nome_do_escritorio() -> str:
        return str((servico.prefs.dados.get("escritorio") or {}).get("nome") or "").strip()

    @r.get("/api/acesso/tunel")
    def tunel_situacao(request: Request) -> dict:
        so_local(request)
        nome = nome_do_escritorio()
        return {"situacao": servico.situacao(), "conexao": conexao.andamento(),
                "titular_pronto": bool(conexao.titulares_prontos()),
                "titulares": [{"nome": c["nome"], "email": c["email"]} for c in conexao.titulares_prontos()],
                "escritorio": nome, "sugestao": sugerir_endereco(nome) if nome else "",
                "energia": servico.energia() if hasattr(servico, "energia") else {},
                "so_google": servico.so_google()}

    @r.get("/api/acesso/tunel/sugestao")
    def tunel_sugestao(nome: str, request: Request) -> dict:
        """O endereco sugerido para um nome de escritorio (o assistente, enquanto a pessoa digita o nome)."""
        so_local(request)
        return {"sugestao": sugerir_endereco(nome)}

    @r.get("/api/acesso/tunel/disponivel")
    def tunel_disponivel(nome: str, request: Request) -> dict:
        """O endereco esta livre? Formato aqui; o resto no Worker, com sugestao."""
        so_local(request)
        return conexao.disponivel(nome)

    @r.post("/api/acesso/tunel/conectar")
    def tunel_conectar(dados: PedidoDeConexao, request: Request) -> dict:
        so_local(request)
        try:
            return conexao.iniciar(dados.nome, dados.slug)
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

    @r.post("/api/acesso/energia/abrir-com-windows")
    def energia_abrir_com_windows(dados: Ligar, request: Request) -> dict:
        """Abrir o PAULUS com o Windows, minimizado (R9): so o programa instalado tem o PAULUS.exe."""
        from acesso import energia

        so_local(request)
        if dados.ligado and not energia.exe_do_programa():
            raise HTTPException(status_code=400, detail="disponível no PAULUS instalado (o PAULUS.exe não foi encontrado)")
        energia.abrir_com_windows(dados.ligado)
        servico.prefs.atualizar({"acesso_remoto": {"abrir_com_windows": bool(dados.ligado)}})
        return {"energia": servico.energia()}

    @r.post("/api/acesso/tunel/remover")
    def tunel_remover(request: Request) -> dict:
        so_local(request)
        try:
            return conexao.remover()
        except ErroConexao as exc:
            falhar(exc)
