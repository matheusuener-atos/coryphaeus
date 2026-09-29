"""
O PAULUS do servidor vinculado a uma conta Google (docs/PLANO-EQUIPE.md, E5).

Decisao do dono (28/09/2026): o PAULUS que fica no servidor do escritorio e
vinculado a conta Google de quem o administra - no assistente de
configuracao, ou depois, em Configuracoes (da para pular). Vinculado, ele
ABRE TRAVADO: a janela do servidor pede "Entrar com Google" a cada abertura
(e o codigo do celular, se a conta de titular dessa pessoa tem o
autenticador). "Manter aberto neste computador" desliga a trava.

A trava e do servidor, e nao so da tela: travado, o porteiro (acesso/
porteiro.py) recusa com 423 tudo o que nao e a propria tela de destravar -
uma chamada direta a API, com a chave da janela, tambem para ali.

O login e o de aplicativo instalado (correio_oauth, com loopback em
127.0.0.1), so com `openid email profile`: serve para saber QUEM e, nao para
ler e-mail. Nada do vinculo sai desta maquina alem do login no Google - e do
id_token (assinado pelo Google, vale 1 hora), que vai ao Worker de
paulus.ia.br so para provar de que conta e o endereco do acesso de fora: e
assim que a mesma conta retoma o endereco depois de reinstalar. Ele fica so
na memoria.
"""

from __future__ import annotations

import base64
import json
import threading
import time
import webbrowser

from fastapi import HTTPException, Request
from pydantic import BaseModel

import correio_oauth


def _exp_do_id_token(token: str) -> float:
    try:
        meio = token.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(meio + "=" * (-len(meio) % 4))).get("exp") or 0)
    except (IndexError, ValueError, TypeError):
        return 0.0


ESCOPOS_IDENTIDADE = "openid email profile"
# Vincular e ja conectar o Gmail, a Agenda e o Drive da mesma conta, num login
# so (o Google pede as permissoes todas numa tela de consentimento).
ESCOPOS_COM_SERVICOS = ("openid email profile https://mail.google.com/ https://www.googleapis.com/auth/calendar.events "
                        "https://www.googleapis.com/auth/drive.file")


class ErroVinculo(RuntimeError):
    """O que impede agora; a frase vai para a tela."""


class Vinculo:
    def __init__(self, prefs, contas_do_acesso, credenciais, *, abrir=webbrowser.open, relogio=time.time) -> None:
        self.prefs = prefs
        self.contas = contas_do_acesso
        self.credenciais = credenciais          # () -> {client_id, client_secret} do cliente desktop
        self.abrir = abrir
        self.relogio = relogio
        self._trava = threading.Lock()
        self.destravado = False
        self.entrada = None
        self.finalidade = ""
        self.erro = ""
        self._conta_do_codigo = 0
        # (tokens, email, nome) -> conta de e-mail do escritorio: o api.py liga,
        # para o "vincular com os servicos" ja conectar o Gmail, a Agenda e o Drive.
        self.ligar_servicos = None
        self._com_servicos = False
        # O id_token do ultimo login desta conta (so em memoria) e quem quer
        # saber dele: o acesso de fora diz ao Worker de que conta e o endereco.
        self._id_token = ""
        self._id_token_exp = 0.0
        self.ao_confirmar = None

    # ------------------------------------------------------------ estado

    def dados(self) -> dict:
        return dict(self.prefs.dados.get("vinculo") or {})

    def vinculado(self) -> bool:
        return bool(self.dados().get("email"))

    def travado(self) -> bool:
        d = self.dados()
        return bool(d.get("email")) and not d.get("manter_aberto") and not self.destravado

    def estado(self) -> dict:
        d = self.dados()
        e = self.entrada.andamento() if self.entrada else {}
        return {
            "vinculado": bool(d.get("email")), "email": d.get("email", ""), "nome": d.get("nome", ""),
            "vinculado_em": d.get("em", ""), "manter_aberto": bool(d.get("manter_aberto")),
            "travado": self.travado(), "google": bool(self.credenciais().get("client_id")),
            "fase": e.get("fase", ""), "mensagem": self.erro or e.get("mensagem", ""),
            "url": e.get("url", ""), "finalidade": self.finalidade,
            "precisa_codigo": bool(self._conta_do_codigo),
            "google_recente": bool(self.id_token_valido()),
        }

    def id_token_valido(self, margem: float = 120) -> str:
        """O id_token da conta vinculada, se ainda vale por `margem` segundos; senao ""."""
        if self._id_token and self._id_token_exp - self.relogio() > margem and self.vinculado():
            return self._id_token
        return ""

    # ------------------------------------------------------------ o login

    def iniciar(self, finalidade: str, servicos: bool = False) -> dict:
        """
        Abre o navegador no login do Google: para vincular, ou para destravar.
        `servicos` (so ao vincular): o mesmo login ja conecta o Gmail, a Agenda
        e o Drive dessa conta - sem um segundo login no passo Conexoes.
        """
        # "confirmar": entrar com a mesma conta so para ter um id_token novo
        # (o acesso de fora pede, para o Worker saber de quem e o endereco).
        if finalidade not in ("vincular", "destravar", "confirmar"):
            raise ErroVinculo("finalidade desconhecida")
        if finalidade == "vincular" and self.vinculado() and self.travado():
            raise ErroVinculo("destrave antes de trocar a conta vinculada")
        if finalidade == "confirmar" and (not self.vinculado() or self.travado()):
            raise ErroVinculo("este PAULUS não está vinculado a uma conta Google")
        if finalidade == "destravar" and not self.vinculado():
            raise ErroVinculo("este PAULUS não está vinculado a uma conta Google")
        credenciais = self.credenciais()
        with self._trava:
            if self.entrada and not self.entrada.terminou:
                self.entrada.cancelar()
            self.erro = ""
            self._conta_do_codigo = 0
            self.finalidade = finalidade
            self._com_servicos = bool(servicos and finalidade == "vincular" and self.ligar_servicos)
            try:
                self.entrada = correio_oauth.Entrada(
                    "google", credenciais, self._voltou, abrir=self.abrir,
                    escopos=ESCOPOS_COM_SERVICOS if self._com_servicos else ESCOPOS_IDENTIDADE,
                    so_identidade=not self._com_servicos,
                    login_hint=self.dados().get("email", "") if finalidade in ("destravar", "confirmar") else "")
            except correio_oauth.ErroOAuth as exc:
                raise ErroVinculo(str(exc)) from exc
        return self.entrada.iniciar()

    def _voltou(self, provedor: str, tokens: dict, email: str, nome: str) -> dict:
        email = str(email or "").strip().lower()
        if self.finalidade == "vincular" and self._com_servicos:
            # A mesma conta vira a conta de e-mail do escritorio, com a Agenda e
            # o Drive (os escopos voltam juntos no token).
            self.ligar_servicos(tokens, email, nome)
        if self.finalidade == "vincular":
            self.prefs.atualizar({"vinculo": {"email": email, "nome": nome,
                                              "em": time.strftime("%Y-%m-%dT%H:%M:%S")}})
            # Quem vincula ja e o dono: o nome e o e-mail entram em Meus dados
            # quando estao vazios.
            pessoa = dict(self.prefs.dados.get("pessoa") or {})
            novos = {"email": email}
            if nome and not pessoa.get("nome"):
                novos["nome"] = nome
            # O e-mail de Meus dados passa a ser o do Google; o que havia, se
            # outro, vira o secundario (quando este esta vazio) - nada se perde.
            antigo = str(pessoa.get("email") or "").strip().lower()
            if antigo and antigo != email and not pessoa.get("email_secundario"):
                novos["email_secundario"] = antigo
            self.prefs.atualizar({"pessoa": novos})
            self.destravado = True
            self._guardar_id_token(tokens)
            return {"email": email, "nome": nome}
        esperado = str(self.dados().get("email") or "").lower()
        if email != esperado:
            raise correio_oauth.ErroOAuth(f"esta não é a conta Google deste PAULUS ({esperado}); entre com ela")
        self._guardar_id_token(tokens)
        if self.finalidade == "confirmar":
            return {"email": email, "nome": nome}
        conta = self._conta_de_titular(email)
        if conta:
            # A conta de titular dessa pessoa tem o autenticador: o codigo do
            # celular vem depois do Google, como de fora.
            self._conta_do_codigo = conta["id"]
        else:
            self.destravado = True
        return {"email": email, "nome": nome}

    def _guardar_id_token(self, tokens: dict) -> None:
        token = str((tokens or {}).get("id_token") or "")
        if not token:
            return
        self._id_token, self._id_token_exp = token, _exp_do_id_token(token)
        if self.ao_confirmar:
            try:
                self.ao_confirmar(token)
            except Exception:  # noqa: BLE001 - avisar o Worker nao pode derrubar o login
                pass

    def _conta_de_titular(self, email: str) -> dict | None:
        try:
            return next((c for c in self.contas.listar() if c["email"] == email and c["totp_confirmado"]), None)
        except Exception:  # noqa: BLE001 - sem o banco das contas, fica so o Google
            return None

    def codigo(self, codigo: str) -> None:
        if not self._conta_do_codigo:
            raise ErroVinculo("entre com o Google antes")
        # Sem sessao de fora aqui: "hash" vazio nao marca sessao nenhuma.
        if not self.contas.confirmar_de_novo({"conta_id": self._conta_do_codigo, "hash": ""}, codigo):
            raise ErroVinculo("o código não confere; digite o que aparece agora no celular")
        self._conta_do_codigo = 0
        self.destravado = True

    def cancelar(self) -> None:
        if self.entrada:
            self.entrada.cancelar()

    # ------------------------------------------------------------ depois

    def travar(self) -> None:
        self.destravado = False
        self._conta_do_codigo = 0

    def manter_aberto(self, ligado: bool) -> None:
        if self.travado():
            raise ErroVinculo("destrave antes")
        self.prefs.atualizar({"vinculo": {"manter_aberto": bool(ligado)}})

    def desvincular(self) -> None:
        if self.travado():
            raise ErroVinculo("destrave antes")
        self.prefs.atualizar({"vinculo": {"email": "", "nome": "", "em": "", "manter_aberto": False}})
        self.destravado = False
        self._id_token, self._id_token_exp = "", 0.0


# O que passa com o PAULUS travado: a propria pagina (a tela de destravar e
# desenhada por ela), os arquivos da casca e as rotas do vinculo.
LIVRES_TRAVADO = ("/api/vinculo",)
ESTATICOS = ("/css/", "/js/", "/img/", "/fontes/", "/marca/")


def passa_travado(metodo: str, caminho: str) -> bool:
    if caminho == "/" or caminho in ("/fontes.css", "/favicon.ico") or caminho.startswith(ESTATICOS):
        return metodo in ("GET", "HEAD")
    if caminho in ("/api/status", "/api/preferencias", "/api/acesso/eu"):
        return metodo in ("GET", "HEAD")
    return any(caminho == p or caminho.startswith(p + "/") for p in LIVRES_TRAVADO)


class Pedido(BaseModel):
    finalidade: str = "destravar"
    servicos: bool = False


class Codigo(BaseModel):
    codigo: str


class Ligar(BaseModel):
    ligado: bool


def montar(app, vinculo: Vinculo) -> None:
    """As rotas do vinculo (so da janela local: de fora, a politica bloqueia)."""
    from acesso.rotas import so_local

    def falhar(exc: Exception):
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/vinculo")
    def vinculo_estado(request: Request) -> dict:
        so_local(request)
        return vinculo.estado()

    @app.post("/api/vinculo/entrar")
    def vinculo_entrar(dados: Pedido, request: Request) -> dict:
        so_local(request)
        try:
            vinculo.iniciar(dados.finalidade, dados.servicos)
        except ErroVinculo as exc:
            falhar(exc)
        return vinculo.estado()

    @app.post("/api/vinculo/cancelar")
    def vinculo_cancelar(request: Request) -> dict:
        so_local(request)
        vinculo.cancelar()
        return vinculo.estado()

    @app.post("/api/vinculo/codigo")
    def vinculo_codigo(dados: Codigo, request: Request) -> dict:
        so_local(request)
        try:
            vinculo.codigo(dados.codigo)
        except ErroVinculo as exc:
            falhar(exc)
        return vinculo.estado()

    @app.post("/api/vinculo/travar")
    def vinculo_travar(request: Request) -> dict:
        so_local(request)
        vinculo.travar()
        return vinculo.estado()

    @app.post("/api/vinculo/manter-aberto")
    def vinculo_manter(dados: Ligar, request: Request) -> dict:
        so_local(request)
        try:
            vinculo.manter_aberto(dados.ligado)
        except ErroVinculo as exc:
            falhar(exc)
        return vinculo.estado()

    @app.post("/api/vinculo/desvincular")
    def vinculo_desvincular(request: Request) -> dict:
        so_local(request)
        try:
            vinculo.desvincular()
        except ErroVinculo as exc:
            falhar(exc)
        return vinculo.estado()
