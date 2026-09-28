"""
As rotas do acesso de fora. O api.py so as registra (`app.include_router`).

Duas familias, e a diferenca entre elas e o ponto:

  - entrar, sair e "quem sou eu" servem quem esta de fora (e a janela local,
    que pergunta "sou local?" pela mesma rota);
  - contas, sessoes e o proprio modulo so pela janela local. Estas conferem
    `local` DENTRO da rota, alem do registro de politicas: uma sessao remota
    roubada nao pode criar conta, trocar senha nem religar nada, nem se um dia
    alguem abrir a politica por engano.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from acesso.contas import ErroConta, ErroEntrada
from acesso.remoto import COOKIE_SESSAO


class Entrada(BaseModel):
    email: str
    senha: str


class Codigo(BaseModel):
    pendente: str
    codigo: str


class NovaConta(BaseModel):
    nome: str
    email: str
    papel: str = "colaborador"
    senha: str


class MudarConta(BaseModel):
    nome: str | None = None
    email: str | None = None
    papel: str | None = None


class NovaSenha(BaseModel):
    senha: str


class SoCodigo(BaseModel):
    codigo: str


def e_local(request: Request | None) -> bool:
    """
    Se o pedido veio da janela local. Sem `request` - a rota chamada de dentro
    do proprio programa, como fazem os executores da fila e os testes - e local:
    de fora, todo pedido passa pelo porteiro, que sempre marca o escopo.
    """
    if request is None:
        return True
    return bool(request.scope.get("state", {}).get("paulus_local"))


def pessoa(request: Request | None) -> dict | None:
    """Quem esta de fora, com sessao; None na janela local."""
    if request is None:
        return None
    return request.scope.get("state", {}).get("paulus_pessoa")


def so_local(request: Request) -> None:
    if not e_local(request):
        raise HTTPException(status_code=403, detail="Disponível só no computador do escritório")


def montar(servico, r) -> None:
    """
    Registra as rotas em `r` - o proprio app. `servico` e o AcessoDeFora
    (servico.py): contas, preferencias e o resto.

    Direto no app, e nao num APIRouter incluido: o FastAPI desta versao guarda
    o roteador incluido embrulhado, e as rotas dele somem de `app.routes` -
    que e onde o porteiro e o teste de permissoes procuram cada rota.
    """

    # ------------------------------------------------------------ de fora

    @r.get("/api/acesso/eu")
    def eu(request: Request) -> dict:
        if e_local(request):
            return {"local": True, "pessoa": None}
        p = pessoa(request)
        if not p:
            return {"local": False, "pessoa": None}
        return {"local": False, "csrf": p["csrf"],
                "pessoa": {"nome": p["nome"], "email": p["email"], "papel": p["papel"]}}

    @r.post("/api/acesso/entrar")
    def entrar(dados: Entrada, request: Request) -> dict:
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        email_access = remoto.get("email_access", "")
        if email_access and email_access != dados.email.strip().lower():
            servico.anotar(acao="login_falho", alvo="e-mail do Access diferente", email=email_access,
                           ip=remoto.get("ip", ""), pessoa=dados.email)
            raise HTTPException(status_code=403, detail="entre com a conta do mesmo e-mail que passou pelo Cloudflare")
        try:
            pendente = servico.contas.entrar_com_senha(dados.email, dados.senha)
        except ErroEntrada as exc:
            servico.anotar(acao="login_falho", alvo="senha", email=email_access, ip=remoto.get("ip", ""),
                           pessoa=dados.email)
            raise HTTPException(status_code=429 if exc.ate else 401, detail=str(exc)) from exc
        return {"pendente": pendente}

    @r.post("/api/acesso/entrar/codigo")
    def entrar_codigo(dados: Codigo, request: Request):
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        try:
            s = servico.contas.entrar_com_codigo(dados.pendente, dados.codigo,
                                                 email_access=remoto.get("email_access", ""),
                                                 ip=remoto.get("ip", ""))
        except ErroEntrada as exc:
            servico.anotar(acao="login_falho", alvo="código", email=remoto.get("email_access", ""),
                           ip=remoto.get("ip", ""))
            raise HTTPException(status_code=429 if exc.ate else 401, detail=str(exc)) from exc
        servico.anotar(acao="entrada", alvo="", pessoa=s["conta"]["nome"], email=remoto.get("email_access", ""),
                       ip=remoto.get("ip", ""))
        resp = JSONResponse({"ok": True, "csrf": s["csrf"],
                             "pessoa": {k: s["conta"][k] for k in ("nome", "email", "papel")}})
        # Secure: de fora, a pagina chega pelo https da Cloudflare. HttpOnly:
        # nenhum script da pagina le o cookie. Strict: nenhum outro site
        # consegue fazer o navegador manda-lo.
        resp.set_cookie(COOKIE_SESSAO, s["sessao"], httponly=True, secure=True, samesite="strict", path="/")
        return resp

    @r.post("/api/acesso/sair")
    def sair(request: Request):
        from acesso.porteiro import cabecalhos, cookies

        token = cookies(cabecalhos(request.scope)).get(COOKIE_SESSAO)
        p = pessoa(request)
        servico.contas.sair(token)
        if p:
            remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
            servico.anotar(acao="saida", alvo="", pessoa=p["nome"], email=remoto.get("email_access", ""),
                           ip=remoto.get("ip", ""))
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE_SESSAO, path="/")
        return resp

    # ----------------------------------------------- so na janela local

    @r.get("/api/acesso/contas")
    def contas(request: Request) -> dict:
        so_local(request)
        return {"contas": servico.contas.listar(), "disponivel": servico.contas.disponivel(),
                "sessoes": servico.contas.sessoes_abertas()}

    @r.post("/api/acesso/contas")
    def criar_conta(dados: NovaConta, request: Request) -> dict:
        so_local(request)
        try:
            criada = servico.contas.criar(dados.nome, dados.email, dados.papel, dados.senha)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.contas_mudaram()
        return criada

    @r.patch("/api/acesso/contas/{conta_id}")
    def mudar_conta(conta_id: int, dados: MudarConta, request: Request) -> dict:
        so_local(request)
        try:
            conta = servico.contas.editar(conta_id, nome=dados.nome, email=dados.email, papel=dados.papel)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.contas_mudaram()
        return {"conta": conta}

    @r.delete("/api/acesso/contas/{conta_id}")
    def remover_conta(conta_id: int, request: Request) -> dict:
        so_local(request)
        try:
            servico.contas.remover(conta_id)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.contas_mudaram()
        return {"ok": True}

    @r.post("/api/acesso/contas/{conta_id}/senha")
    def trocar_senha(conta_id: int, dados: NovaSenha, request: Request) -> dict:
        so_local(request)
        try:
            caidas = servico.contas.trocar_senha(conta_id, dados.senha)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "sessoes_encerradas": caidas}

    @r.post("/api/acesso/contas/{conta_id}/autenticador/confirmar")
    def confirmar_autenticador(conta_id: int, dados: SoCodigo, request: Request) -> dict:
        so_local(request)
        if not servico.contas.confirmar_totp(conta_id, dados.codigo):
            raise HTTPException(status_code=400, detail="o código não confere: veja se o relógio do celular está certo")
        servico.contas_mudaram()
        return {"conta": servico.contas.obter(conta_id)}

    @r.post("/api/acesso/contas/{conta_id}/autenticador/refazer")
    def refazer_autenticador(conta_id: int, request: Request) -> dict:
        so_local(request)
        try:
            return servico.contas.refazer_totp(conta_id)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @r.post("/api/acesso/contas/{conta_id}/recuperacao")
    def novos_codigos(conta_id: int, request: Request) -> dict:
        so_local(request)
        try:
            return {"codigos_recuperacao": servico.contas.novos_codigos(conta_id)}
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @r.post("/api/acesso/sessoes/encerrar")
    def encerrar_sessoes(request: Request) -> dict:
        so_local(request)
        return {"encerradas": servico.contas.encerrar_sessoes()}
