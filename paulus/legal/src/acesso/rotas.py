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

import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from acesso.contas import ErroConta, ErroEntrada
from acesso.remoto import COOKIE_SESSAO


class Entrada(BaseModel):
    email: str
    senha: str
    # O token do Turnstile da tela de entrar (anti-robo), conferido ANTES da
    # senha: sem ele, a tentativa nem chega a contar.
    turnstile: str = ""


class MinhaSenha(BaseModel):
    atual: str
    nova: str
    codigo: str


# O login responde sempre no mesmo tempo, com senha certa ou errada, com
# conta ou sem: o relogio nao pode dizer quem tem conta. O scrypt ja iguala o
# grosso; este piso tira o que sobra de diferenca (medido: ~0,1 s).
TEMPO_DO_LOGIN_S = 0.45


def _no_tempo(comeco: float) -> None:
    falta = TEMPO_DO_LOGIN_S - (time.monotonic() - comeco)
    if falta > 0:
        time.sleep(falta)


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

    @r.get("/api/acesso/entrar/config")
    def entrar_config() -> dict:
        """O que a tela de entrar precisa saber antes do login: a sitekey do Turnstile."""
        return {"turnstile_sitekey": servico.preferencias().get("turnstile_sitekey", "")}

    @r.post("/api/acesso/entrar")
    def entrar(dados: Entrada, request: Request) -> dict:
        comeco = time.monotonic()
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        ip = remoto.get("ip", "")
        if not e_local(request):
            # O anti-robo vem antes da senha: sem ele, nada e tentado nem
            # contado. Sem o Worker para conferir, ninguem entra.
            veredito = servico.conferir_turnstile(dados.turnstile, ip)
            if veredito != "ok":
                servico.anotar(acao="login_falho", alvo="verificação anti-robô", ip=ip, pessoa=dados.email)
                _no_tempo(comeco)
                if veredito == "indisponivel":
                    raise HTTPException(status_code=503, detail="não consegui conferir a verificação contra robôs "
                                                                "agora; tente de novo em instantes")
                raise HTTPException(status_code=403, detail="a verificação contra robôs não passou; tente de novo")
        try:
            pendente = servico.contas.entrar_com_senha(dados.email, dados.senha, ip=ip)
        except ErroEntrada as exc:
            servico.anotar(acao="login_falho", alvo="senha", ip=ip, pessoa=dados.email)
            _no_tempo(comeco)
            raise HTTPException(status_code=429 if exc.ate else 401, detail=str(exc)) from exc
        _no_tempo(comeco)
        return {"pendente": pendente}

    @r.post("/api/acesso/entrar/codigo")
    def entrar_codigo(dados: Codigo, request: Request):
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        ip = remoto.get("ip", "")
        try:
            s = servico.contas.entrar_com_codigo(dados.pendente, dados.codigo, ip=ip)
        except ErroEntrada as exc:
            servico.anotar(acao="login_falho", alvo="código", ip=ip)
            raise HTTPException(status_code=429 if exc.ate else 401, detail=str(exc)) from exc
        servico.anotar(acao="entrada", alvo="", pessoa=s["conta"]["nome"], email=s["conta"]["email"], ip=ip)
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
            servico.anotar(acao="saida", alvo="", pessoa=p["nome"], email=p["email"], ip=remoto.get("ip", ""))
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE_SESSAO, path="/")
        return resp

    # ------------------------- de fora, do titular, com o codigo de novo

    def _codigo_de_novo(request: Request, codigo: str) -> dict:
        """
        As acoes sensiveis do titular de fora pedem o codigo do autenticador
        AGORA, mesmo com sessao valida: sessao roubada nao troca senha nem
        derruba o escritorio inteiro.
        """
        p = pessoa(request)
        if not p:
            raise HTTPException(status_code=403, detail="só pelo acesso de fora, com a sua conta")
        if p["papel"] != "titular":
            raise HTTPException(status_code=403, detail="só o titular pode fazer isso")
        if not servico.contas.confirmar_de_novo(p, codigo):
            raise HTTPException(status_code=403, detail="o código do autenticador não confere")
        return p

    @r.post("/api/acesso/minha-senha")
    def minha_senha(dados: MinhaSenha, request: Request):
        p = _codigo_de_novo(request, dados.codigo)
        if not servico.contas.senha_confere(p["conta_id"], dados.atual):
            raise HTTPException(status_code=403, detail="a senha atual não confere")
        try:
            servico.contas.trocar_senha(p["conta_id"], dados.nova)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        servico.anotar(acao="senha", alvo="trocou a própria senha", pessoa=p["nome"], email=p["email"],
                       ip=remoto.get("ip", ""))
        # Trocar a senha derruba todas as sessoes da conta - inclusive esta.
        resp = JSONResponse({"ok": True, "detail": "senha trocada: entre de novo"})
        resp.delete_cookie(COOKIE_SESSAO, path="/")
        return resp

    @r.post("/api/acesso/minhas-sessoes/encerrar")
    def minhas_sessoes_encerrar(dados: SoCodigo, request: Request):
        p = _codigo_de_novo(request, dados.codigo)
        caidas = servico.contas.encerrar_sessoes()
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        servico.anotar(acao="sessoes", alvo=f"encerrou {caidas} sessões", pessoa=p["nome"], email=p["email"],
                       ip=remoto.get("ip", ""))
        resp = JSONResponse({"ok": True, "encerradas": caidas})
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
