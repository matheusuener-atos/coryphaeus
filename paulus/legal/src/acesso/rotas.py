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
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from acesso.contas import CONFIAR_S, ErroConta, ErroEntrada
from acesso.remoto import COOKIE_SESSAO
from acesso import permissoes
from acesso.convites import ErroConvite
from acesso.google_login import COOKIE as COOKIE_GOOGLE, ErroGoogle
from acesso.atos_login import COOKIE as COOKIE_ATOS, ErroAtos

# O navegador confiado por 30 dias (contas.confiar).
COOKIE_CONFIA = "paulus_confia"


class Entrada(BaseModel):
    email: str
    senha: str
    # O token do Turnstile da tela de entrar (anti-robo), conferido ANTES da
    # senha: sem ele, a tentativa nem chega a contar.
    turnstile: str = ""


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
    # "Confiar neste navegador por 30 dias" (so de fora).
    confiar: bool = False


class NovoConvite(BaseModel):
    nome: str
    email: str
    permissoes: dict = {}
    email_secundario: str = ""
    seguranca: str = ""


class NivelDeSeguranca(BaseModel):
    nivel: str


class ConfirmarConvite(BaseModel):
    codigo: str


class IrAoGoogle(BaseModel):
    finalidade: str = "entrar"
    convite: str = ""
    turnstile: str = ""
    # O e-mail que entrou da ultima vez neste aparelho (login_hint): com ele,
    # o Google segue direto, sem a tela de escolher a conta.
    dica: str = ""


class IrAAtos(BaseModel):
    finalidade: str = "entrar"
    convite: str = ""
    turnstile: str = ""
    # O e-mail que entrou da ultima vez neste aparelho (login_hint).
    dica: str = ""


class NovaConta(BaseModel):
    nome: str
    email: str
    papel: str = "colaborador"
    # Vazia quando so se entra pelo Google: a conta nasce sem senha que alguem saiba.
    senha: str = ""
    email_secundario: str = ""
    seguranca: str = ""


class MudarConta(BaseModel):
    nome: str | None = None
    email: str | None = None
    papel: str | None = None
    email_secundario: str | None = None


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
                "pessoa": {"nome": p["nome"], "email": p["email"], "papel": p["papel"]},
                # O menu esconde o que a pessoa nao ve e abre o que o nivel
                # libera (E2); quem decide de verdade e o portao.
                "permissoes": permissoes.para_a_tela(p.get("permissoes") or {}),
                # O Google de trabalho da pessoa (E3b): e-mail, Agenda e Drive dela.
                "google": servico.google_da_pessoa(p["conta_id"]) if hasattr(servico, "google_da_pessoa") else "",
                "google_disponivel": servico.google.disponivel()}

    @r.get("/api/acesso/entrar/config")
    def entrar_config() -> dict:
        """O que a tela de entrar precisa saber antes do login: a sitekey do Turnstile (entra-se com a Conta Atos)."""
        return {"turnstile_sitekey": servico.preferencias().get("turnstile_sitekey", "")}

    # A senha local (07/10 a 09/10/2026): desde 09/10 a equipe entra com a Conta
    # Atos e nenhuma conta nova nasce com senha. Esta rota so confere a senha de
    # quem ja tinha uma, e nenhuma tela a usa mais; sai junto com a senha das contas.
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
        # Conta de seguranca "simples": a senha basta, sem o passo do codigo.
        s = servico.contas.concluir_sem_codigo(pendente, ip=ip)
        if s:
            servico.anotar(acao="entrada", alvo="sem código (segurança simples)", pessoa=s["conta"]["nome"],
                           email=s["conta"]["email"], ip=ip)
            resp = JSONResponse({"ok": True, "csrf": s["csrf"], "pessoa": {k: s["conta"][k] for k in ("nome", "email", "papel")}})
            resp.set_cookie(COOKIE_SESSAO, s["sessao"], httponly=True, secure=True, samesite="strict", path="/")
            return resp
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
        if dados.confiar and not e_local(request) and servico.contas.nivel(s["conta"]["id"]) == "padrao":
            # So o caminho do login le este cookie; o navegador nao o manda a
            # mais nada.
            resp.set_cookie(COOKIE_CONFIA, servico.contas.confiar(s["conta"]["id"]), max_age=CONFIAR_S,
                            httponly=True, secure=True, samesite="lax", path="/api/acesso")
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
            raise HTTPException(status_code=403, detail="só pelo acesso externo, com a sua conta")
        if p["papel"] != "titular":
            raise HTTPException(status_code=403, detail="só o titular pode fazer isso")
        if not servico.contas.confirmar_de_novo(p, codigo):
            raise HTTPException(status_code=403, detail="o código do autenticador não confere")
        return p

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
                "seguranca_padrao": servico.preferencias().get("seguranca_padrao", "padrao"),
                "vinculo": {"email": (getattr(servico, "vinculo", None).dados().get("email", "") if getattr(servico, "vinculo", None) else ""),
                            "nome": (getattr(servico, "vinculo", None).dados().get("nome", "") if getattr(servico, "vinculo", None) else "")},
                "sessoes": servico.contas.sessoes_abertas()}

    @r.post("/api/acesso/contas")
    def criar_conta(dados: NovaConta, request: Request) -> dict:
        so_local(request)
        # Sem senha (09/10/2026): a pessoa entra com a Conta Atos do e-mail dela e o
        # codigo do autenticador. O endereco pode nem existir ainda - o assistente
        # cria a conta do titular antes de conectar.
        try:
            criada = servico.contas.criar(dados.nome, dados.email, dados.papel, "",
                                          email_secundario=dados.email_secundario,
                                          seguranca=dados.seguranca or servico.preferencias().get("seguranca_padrao", "padrao"))
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.contas_mudaram()
        return criada

    @r.patch("/api/acesso/contas/{conta_id}")
    def mudar_conta(conta_id: int, dados: MudarConta, request: Request) -> dict:
        so_local(request)
        try:
            conta = servico.contas.editar(conta_id, nome=dados.nome, email=dados.email, papel=dados.papel,
                                          email_secundario=dados.email_secundario)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.contas_mudaram()
        return {"conta": conta}

    # ---------------------------------------------------------- convites

    @r.get("/api/acesso/convites")
    def convites_listar(request: Request) -> dict:
        so_local(request)
        return {"convites": servico.convites.listar(), "endereco": servico.preferencias().get("hostname", "")}

    @r.post("/api/acesso/convites")
    def convites_criar(dados: NovoConvite, request: Request) -> dict:
        """O link para mandar pelo WhatsApp: so existe com o acesso de fora conectado."""
        so_local(request)
        vinculo = getattr(servico, "vinculo", None)
        if vinculo is not None and not vinculo.vinculado():
            raise HTTPException(status_code=400, detail="vincule este Paulus à sua conta antes de convidar a equipe")
        host = servico.preferencias().get("hostname", "")
        if not host:
            raise HTTPException(status_code=400, detail="ligue o acesso externo antes: o convite é um link do endereço do escritório")
        # O plano tem vaga? (a conta so nasce no aceite, que confere de novo)
        if servico.contas.vaga is not None:
            servico.contas.vaga(len(servico.contas.listar()))
        try:
            nivel = dados.seguranca or servico.preferencias().get("seguranca_padrao", "padrao")
            codigo, convite = servico.convites.criar(dados.nome, dados.email, dados.permissoes, dados.email_secundario,
                                                     seguranca=nivel)
        except ErroConvite as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.anotar(acao="convite", alvo=f"{convite['nome']} <{convite['email']}>", pessoa="janela local")
        return {"link": f"https://{host}/convite/{codigo}", "convite": convite}

    @r.delete("/api/acesso/convites/{id_}")
    def convites_revogar(id_: str, request: Request) -> dict:
        so_local(request)
        try:
            servico.convites.revogar(id_)
        except ErroConvite as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @r.get("/api/acesso/convite/{codigo}")
    def convite_ver(codigo: str) -> dict:
        try:
            dados = servico.convites.ver(codigo)
        except ErroConvite as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc
        escritorio = str((servico.prefs.dados.get("escritorio") or {}).get("nome") or "")
        return {**dados, "escritorio": escritorio, "turnstile_sitekey": servico.preferencias().get("turnstile_sitekey", "")}

    @r.post("/api/acesso/convite/{codigo}/confirmar")
    def convite_confirmar(codigo: str, dados: ConfirmarConvite, request: Request) -> dict:
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        try:
            feito = servico.convites.confirmar(codigo, dados.codigo)
        except ErroConvite as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.anotar(acao="convite_aceito", alvo=feito["email"], pessoa=feito["nome"], email=feito["email"],
                       ip=remoto.get("ip", ""))
        servico.contas_mudaram()
        return feito

    # ------------------------------------------- entrar com o Google (E3a)

    def _anti_robo(request: Request, token: str) -> None:
        if e_local(request):
            return
        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        veredito = servico.conferir_turnstile(token, remoto.get("ip", ""))
        if veredito == "indisponivel":
            raise HTTPException(status_code=503, detail="não consegui conferir a verificação contra robôs agora; tente de novo em instantes")
        if veredito != "ok":
            raise HTTPException(status_code=403, detail="a verificação contra robôs não passou; tente de novo")

    @r.post("/api/acesso/google/iniciar")
    def google_iniciar(dados: IrAoGoogle, request: Request):
        """O endereco do Google, e o cookie que amarra a volta a este navegador."""
        conta_id = 0
        if dados.finalidade == "servicos":
            # Conectar o proprio Google (E3b): so quem ja entrou, de fora.
            p = pessoa(request)
            if not p:
                raise HTTPException(status_code=403, detail="entre com a sua conta antes de conectar o Google")
            conta_id = p["conta_id"]
        else:
            # Entrar e aceitar convite sao da Conta Atos (09/10/2026): o Google fica
            # so para o e-mail, a Agenda e o Drive de cada pessoa.
            raise HTTPException(status_code=410, detail="agora se entra com a Conta Atos")
        try:
            url, nonce = servico.google.iniciar(dados.finalidade, dados.convite, conta_id, dica=dados.dica)
        except ErroGoogle as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        resp = JSONResponse({"url": url})
        resp.set_cookie(COOKIE_GOOGLE, nonce, max_age=600, httponly=True, secure=True, samesite="lax",
                        path="/api/acesso/google")
        return resp

    @r.get("/api/acesso/google/retorno")
    def google_retorno(request: Request, code: str = "", state: str = "", error: str = ""):
        """
        A volta do Google (repassada pelo Worker de paulus.ia.br). Entrar: vai
        para o codigo do celular. Convite: volta a pagina do convite com o QR.
        O que a pagina precisa vai depois do # - nao sai do navegador.
        """
        from urllib.parse import quote

        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        ip = remoto.get("ip", "")

        def voltar(destino: str) -> RedirectResponse:
            resp = RedirectResponse(destino, status_code=303)
            resp.delete_cookie(COOKIE_GOOGLE, path="/api/acesso/google")
            return resp

        if error or not code:
            return voltar("/#erro=" + quote("o login pelo Google foi cancelado"))
        try:
            quem = servico.google.retorno(code, state, request.cookies.get(COOKIE_GOOGLE, ""))
        except ErroGoogle as exc:
            return voltar("/#erro=" + quote(str(exc)))
        if quem["finalidade"] == "servicos":
            ligar = getattr(servico, "ligar_google", None)
            if ligar is None or not quem["tokens"].get("refresh_token"):
                return voltar("/#google-erro=" + quote("o Google não deu a autorização duradoura; tente de novo"))
            try:
                ligar(quem["conta_id"], quem["email"], quem["nome"], quem["tokens"])
            except ValueError as exc:
                return voltar("/#google-erro=" + quote(str(exc)))
            servico.anotar(acao="google", alvo=quem["email"], ip=ip)
            return voltar("/#google=" + quote(quem["email"]))
        return voltar("/#erro=" + quote("agora se entra com a Conta Atos"))

    def _entrou(quem: dict, rotulo: str, voltar, request: Request, ip: str):
        """
        A volta da Atos, depois de conferida: o convite volta a
        pagina dele com o QR; entrar vai ao codigo do celular (ou direto, no
        navegador confiado e na seguranca simples).
        """
        from urllib.parse import quote

        if quem["finalidade"] == "convite":
            try:
                token = servico.convites.aceitar_google(quem["convite"], quem["email"])
            except ErroConvite as exc:
                return voltar("/convite/" + quote(quem["convite"]) + "#erro=" + quote(str(exc)))
            return voltar("/convite/" + quote(quem["convite"]) + "#g=" + quote(token))
        # Navegador confiado (30 dias) para esta conta: entra sem o codigo.
        try:
            confiado = servico.contas.entrar_confiado(request.cookies.get(COOKIE_CONFIA, ""), quem["email"], ip=ip)
        except (ErroEntrada, ErroConta):
            confiado = None
        if confiado:
            servico.anotar(acao="entrada", alvo="navegador confiado", pessoa=confiado["conta"]["nome"],
                           email=confiado["conta"]["email"], ip=ip)
            resp = voltar("/#entrou")
            resp.set_cookie(COOKIE_SESSAO, confiado["sessao"], httponly=True, secure=True, samesite="strict", path="/")
            return resp
        try:
            pendente = servico.contas.entrar_com_google(quem["email"], ip=ip)
        except ErroEntrada as exc:
            servico.anotar(acao="login_falho", alvo=rotulo, ip=ip, pessoa=quem["email"])
            return voltar("/#erro=" + quote(str(exc)))
        # Conta de seguranca "simples": a conta basta.
        direto = servico.contas.concluir_sem_codigo(pendente, ip=ip)
        if direto:
            servico.anotar(acao="entrada", alvo=rotulo + " (segurança simples)", pessoa=direto["conta"]["nome"],
                           email=direto["conta"]["email"], ip=ip)
            resp = voltar("/#entrou")
            resp.set_cookie(COOKIE_SESSAO, direto["sessao"], httponly=True, secure=True, samesite="strict", path="/")
            return resp
        return voltar("/#g=" + quote(pendente) + "&e=" + quote(quem["email"]))

    # --------------------------------------- entrar com Atos, de fora (09/10)

    @r.post("/api/acesso/atos/iniciar")
    def atos_iniciar(dados: IrAAtos, request: Request):
        """O endereco da Atos, e o cookie que amarra a volta a este navegador."""
        _anti_robo(request, dados.turnstile)
        if dados.finalidade == "convite":
            try:
                servico.convites.ver(dados.convite)
            except ErroConvite as exc:
                raise HTTPException(status_code=410, detail=str(exc)) from exc
        try:
            url, amarra = servico.atos.iniciar(dados.finalidade, dados.convite, dica=dados.dica)
        except ErroAtos as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        resp = JSONResponse({"url": url})
        resp.set_cookie(COOKIE_ATOS, amarra, max_age=600, httponly=True, secure=True, samesite="lax",
                        path="/api/acesso/atos")
        return resp

    @r.get("/api/acesso/atos/retorno")
    def atos_retorno(request: Request, code: str = "", state: str = "", error: str = "", iss: str = ""):
        """A volta da Atos, direto a este escritorio. O que a pagina precisa vai depois do #."""
        from urllib.parse import quote

        remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
        ip = remoto.get("ip", "")

        def voltar(destino: str) -> RedirectResponse:
            resp = RedirectResponse(destino, status_code=303)
            resp.delete_cookie(COOKIE_ATOS, path="/api/acesso/atos")
            return resp

        if error or not code:
            return voltar("/#erro=" + quote("a entrada pela Atos foi cancelada"))
        try:
            quem = servico.atos.retorno(code, state, request.cookies.get(COOKIE_ATOS, ""), iss)
        except ErroAtos as exc:
            return voltar("/#erro=" + quote(str(exc)))
        return _entrou(quem, "Atos", voltar, request, ip)

    @r.get("/api/acesso/convite/{codigo}/google")
    def convite_do_google(codigo: str, t: str = "") -> dict:
        try:
            return servico.convites.do_google(codigo, t)
        except ErroConvite as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc

    @r.put("/api/acesso/contas/{conta_id}/seguranca")
    def mudar_seguranca(conta_id: int, dados: NivelDeSeguranca, request: Request) -> dict:
        """O nivel de seguranca de uma conta: so na janela do servidor."""
        so_local(request)
        try:
            conta = servico.contas.mudar_seguranca(conta_id, dados.nivel)
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.anotar(acao="seguranca", alvo=f"{conta['nome']}: {dados.nivel}", pessoa="janela local")
        servico.contas_mudaram()
        return {"conta": conta}

    @r.put("/api/acesso/seguranca-padrao")
    def mudar_seguranca_padrao(dados: NivelDeSeguranca, request: Request) -> dict:
        """O nivel das contas novas (convite e conta criada aqui)."""
        from acesso.contas import NIVEIS

        so_local(request)
        if dados.nivel not in NIVEIS:
            raise HTTPException(status_code=400, detail="nível de segurança desconhecido")
        servico.prefs.atualizar({"acesso_remoto": {"seguranca_padrao": dados.nivel}})
        return {"seguranca_padrao": dados.nivel}

    @r.get("/api/acesso/permissoes/modulos")
    def permissoes_modulos(request: Request) -> dict:
        """A grade de Configuracoes: os modulos e os niveis de cada um."""
        so_local(request)
        return {"modulos": permissoes.para_a_tela(permissoes.padrao())}

    @r.put("/api/acesso/contas/{conta_id}/permissoes")
    def mudar_permissoes(conta_id: int, dados: dict, request: Request) -> dict:
        so_local(request)
        try:
            conta = servico.contas.mudar_permissoes(conta_id, dados.get("niveis") or {})
        except ErroConta as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        servico.anotar(acao="permissoes", alvo=conta["nome"], pessoa="janela local")
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
