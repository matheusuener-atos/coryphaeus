"""
As rotas do assistente de configuração novo (src/rotas_boas_vindas.py,
frontend/js/23-boas-vindas.js), com a nuvem e o Google de mentira:

  - GET /api/assinatura: sem conta Google, "nenhuma"; com o login recente e
    sem a nuvem aqui, ativa a nuvem desta instalação com essa conta e lê a
    assinatura e o cadastro do site (nome do escritório, CPF ou CNPJ, OAB,
    telefone, endereço numa linha); depois, pelo segredo, sem precisar do
    login; "renova em" só na mensal no cartão; venceu e nunca assinou;
    o cache curto (a tela pergunta a cada 5 s); sem rede, o último plano
    conhecido; trocar de conta no assistente passa a nuvem para a de agora,
    mas a nuvem ativada antes por outra conta não muda daqui;
  - POST /api/conexoes/autorizar: um consentimento só, com os escopos dos
    serviços marcados, incremental e com a conta certa sugerida; quem abre o
    navegador é a tela; sem a conta de e-mail, pede o Gmail junto; o
    serviço desligado na Minha conta é recusado; a volta guarda a autorização
    na conta do escritório e GET /api/conexoes passa a dizer o que ficou
    autorizado (sem perder o que a rota já dizia do WhatsApp); outra conta
    Google na volta é recusada; cancelar desiste só do consentimento;
  - "Trocar de conta" é o /api/vinculo/desvincular de sempre;
  - toda rota que o assistente chama existe no servidor; as novas são só da
    janela do escritório.

Nada sai da máquina: a nuvem é `nuvem.PEDIR`, o Google da troca do código é
um http.server local e o "navegador" é uma chamada HTTP à porta de volta.
Dados numa pasta temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_boas_vindas.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-boas-vindas-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_SEM_VOZ"] = "1"
os.environ["PAULUS_GOOGLE_CLIENT_ID"] = "cliente-de-teste.apps.googleusercontent.com"
os.environ["PAULUS_GOOGLE_CLIENT_SECRET"] = "segredo-de-teste"
os.environ.pop("PAULUS_COBRANCA", None)
os.environ.pop("PAULUS_INSTALADO", None)
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
MAIL = "https://mail.google.com/"
AGENDA = "https://www.googleapis.com/auth/calendar.events"
DRIVE = "https://www.googleapis.com/auth/drive.file"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, segundos: float = 10.0) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.05)
    return bool(cond())


def _id_token(email: str, nome: str = "") -> str:
    def parte(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return parte({"alg": "none"}) + "." + parte({"email": email, "name": nome}) + ".x"


# ------------------------------------------------------------ a nuvem de mentira

class Resposta:
    def __init__(self, status: int, dados: dict) -> None:
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


def resumo(email: str, *, vigente: bool, periodo: str = "mensal", ciclo: bool = True, cortesia: bool = False) -> dict:
    return {"ok": True, "email": email, "plano_vigente": vigente, "cortesia": cortesia, "periodo": periodo,
            "plano": {"id": "escritorio", "nome": "Escritório"},
            "assinatura": {"id": "pre1", "situacao": "authorized" if vigente else "cancelled", "periodo": periodo} if ciclo else None,
            "ciclo": {"inicio": "2026-10-07T15:00:00.000Z", "fim": "2026-11-07T15:00:00.000Z"} if ciclo else None,
            "pago_ate": "2027-10-07T15:00:00.000Z" if periodo == "anual" else None}


CADASTRO_HELENA = {"nome_escritorio": "Moura Advogados", "documento": "52998224725", "oab": "PA 12345", "telefone": "91988887777",
                   "endereco": {"cep": "66010000", "logradouro": "Av. Presidente Vargas", "numero": "100", "complemento": "sala 2",
                                "bairro": "Campina", "cidade": "Belém", "uf": "PA", "cmun": "1501402"}}


class NuvemFalsa:
    """O Worker de paulus.ia.br: contas por e-mail, cada uma com o segredo, a situação e o cadastro."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.fora = False
        self.tokens = {"tok-helena": "helena@moura.adv.br", "tok-caio": "caio@silva.adv.br"}
        self.contas = {
            "helena@moura.adv.br": {"resumo": resumo("helena@moura.adv.br", vigente=True), "cadastro": dict(CADASTRO_HELENA)},
            "caio@silva.adv.br": {"resumo": resumo("caio@silva.adv.br", vigente=False, ciclo=False), "cadastro": None},
        }

    def segredo(self, email: str) -> str:
        return "pia_" + ("a1" if email.startswith("helena") else "b2") * 12 + "_" + "c3" * 32

    def de_quem(self, cabecalhos) -> str:
        auth = str((cabecalhos or {}).get("Authorization") or "")
        return next((e for e in self.contas if auth == "Bearer " + self.segredo(e)), "")

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        caminho = url.split("paulus.ia.br", 1)[-1]
        self.chamadas.append({"metodo": metodo, "caminho": caminho, "corpo": corpo, "quem": self.de_quem(cabecalhos)})
        if self.fora:
            raise ConnectionError("sem internet")
        if caminho == "/api/ia/ativar":
            email = self.tokens.get((corpo or {}).get("id_token"), "")
            if not email:
                return Resposta(401, {"erro": "a confirmação do Google venceu"})
            return Resposta(200, {"segredo": self.segredo(email), "conta": self.contas[email]["resumo"]})
        if caminho == "/api/ia/site/situacao":
            email = self.tokens.get((corpo or {}).get("id_token"), "")
            if not email:
                return Resposta(401, {"erro": "a confirmação do Google venceu"})
            return Resposta(200, {**self.contas[email]["resumo"], "cadastro": self.contas[email]["cadastro"]})
        quem = self.de_quem(cabecalhos)
        if not quem:
            return Resposta(401, {"erro": "não autorizado"})
        if caminho == "/api/ia/conta":
            return Resposta(200, self.contas[quem]["resumo"])
        if caminho == "/api/ia/cadastro":
            return Resposta(200, {"ok": True, "email": quem, "cadastro": self.contas[quem]["cadastro"]})
        if caminho in ("/api/ia/sair", "/api/ia/consentimento"):
            return Resposta(200, {"ok": True})
        if caminho == "/api/ia/google":
            return Resposta(200, {"ok": True, "pendente": None})
        return Resposta(404, {"erro": "rota não existe"})

    def foram(self, caminho: str) -> list[dict]:
        return [c for c in self.chamadas if c["caminho"] == caminho]


# ------------------------------------------------------------ o Google de mentira

class TokenFalso:
    """O oauth2.googleapis.com/token: troca o código pela conta e pelos escopos de `proximo`."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.proximo = {"email": "helena@moura.adv.br", "escopos": ""}
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                tamanho = int(self.headers.get("Content-Length") or 0)
                campos = dict(urllib.parse.parse_qsl(self.rfile.read(tamanho).decode()))
                dono.pedidos.append(campos)
                corpo = {"access_token": "acesso-1", "expires_in": 3599, "refresh_token": "refresh-1", "token_type": "Bearer",
                         "scope": "openid https://www.googleapis.com/auth/userinfo.email " + dono.proximo["escopos"],
                         "id_token": _id_token(dono.proximo["email"], "Helena Moura")}
                bruto = json.dumps(corpo).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bruto)))
                self.end_headers()
                self.wfile.write(bruto)

        self.srv = HTTPServer(("127.0.0.1", 0), Manipulador)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/token"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def fechar(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


def navegador(url: str) -> int:
    """O papel do navegador voltando do Google: GET no endereço de volta, com o state certo e um código."""
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    alvo = q["redirect_uri"].rstrip("/") + "/?" + urllib.parse.urlencode({"state": q["state"], "code": "codigo-bom"})
    try:
        with urllib.request.urlopen(alvo, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


# ------------------------------------------------------------ os testes

def test_rotas_do_assistente() -> None:
    print("\ntoda rota que o assistente chama existe")
    import api
    from acesso import politicas

    js = (RAIZ / "frontend" / "js" / "23-boas-vindas.js").read_text(encoding="utf-8")
    chamadas = sorted({m.split("?")[0] for m in re.findall(r'"(/api/[^"\s]*)"', js)})
    rotas = [getattr(r, "path", "") for r in api.app.routes]
    padroes = [re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(p)) + "$") for p in rotas if p.startswith("/api/")]
    faltam = [c for c in chamadas if not c.endswith("/") and not any(p.match(c) for p in padroes)]
    checar(chamadas and not faltam, f"as {len(chamadas)} rotas do assistente existem no servidor", faltam)
    checar("/api/vinculo/desfazer" not in js and '"/api/vinculo/desvincular"' in js, "o \"Trocar de conta\" chama o desvincular que já existe")
    for rota in ("GET /api/assinatura", "POST /api/conexoes/autorizar", "POST /api/conexoes/cancelar"):
        metodo, caminho = rota.split(" ")
        checar(politicas.de(metodo, caminho) == politicas.BLOQUEADO, rota + ": só na janela do escritório")


def test_assinatura() -> None:
    from fastapi.testclient import TestClient

    import api
    import nuvem
    import rotas_boas_vindas as rbv
    import segredos

    e = api.estado
    local = TestClient(api.app, headers=api.cabecalho_local())
    fake = NuvemFalsa()
    nuvem.PEDIR["fn"] = fake

    def vincular(email: str, token: str, nome: str = "") -> None:
        """Como o passo Conta Google deixa: vinculado, destravado e com o login recente (o id_token, 1 h)."""
        e.prefs.atualizar({"vinculo": {"email": email, "nome": nome, "em": "2026-10-07T12:00:00"}})
        e.vinculo.destravado = True
        e.vinculo._id_token, e.vinculo._id_token_exp = token, time.time() + 3600
        rbv.esquecer()

    print("\na assinatura (GET /api/assinatura)")
    a = local.get("/api/assinatura").json()
    checar(a["ativa"] is False and a["situacao"] == "nenhuma" and "Conta Google" in a.get("motivo", "") and not fake.chamadas,
           "sem conta Google: nenhuma, e nada vai à nuvem", a)
    if not segredos.disponivel():
        print("  pulado: sem DPAPI (o segredo da nuvem não se guarda)")
        return
    e.prefs.atualizar({"escritorio": {"nome": ""}})
    vincular("helena@moura.adv.br", "tok-helena", "Helena Moura")
    a = local.get("/api/assinatura").json()
    ativar = fake.foram("/api/ia/ativar")
    checar(len(ativar) == 1 and ativar[0]["corpo"]["id_token"] == "tok-helena" and nuvem.chave(e, "paulus") == fake.segredo("helena@moura.adv.br"),
           "sem a nuvem aqui: ativa com o login recente da conta que entrou, e guarda o segredo", ativar)
    checar(a["ativa"] is True and a["situacao"] == "ativa" and a["plano"] == "Escritório" and a["renova_em"] == "2026-11-07"
           and a["email"] == "helena@moura.adv.br", "a assinatura ativa, com o plano e quando renova", a)
    p = a["pessoa"]
    checar(a["escritorio"] == "Moura Advogados" and p.get("nome") == "Helena Moura" and p.get("cpf") == "529.982.247-25"
           and p.get("oab") == "PA 12345" and p.get("telefone") == "(91) 98888-7777" and p.get("email") == "helena@moura.adv.br",
           "o escritório e os dados vêm do cadastro do site (o nome, do Google)", p)
    checar(p.get("endereco") == "Av. Presidente Vargas, 100, sala 2 - Campina, Belém - PA, CEP 66010-000", "o endereço numa linha", p.get("endereco"))
    checar(fake.foram("/api/ia/cadastro")[-1]["quem"] == "helena@moura.adv.br", "o cadastro é lido pelo segredo desta conta")
    n = len(fake.chamadas)
    local.get("/api/assinatura")
    checar(len(fake.chamadas) == n, "pedida de novo em seguida (a tela pergunta a cada 5 s), vem do cache curto")

    print("\ndepois, sem o login")
    e.vinculo._id_token_exp = 0.0
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(a["ativa"] and len(fake.foram("/api/ia/ativar")) == 1 and fake.foram("/api/ia/conta")[-1]["quem"] == "helena@moura.adv.br",
           "com a nuvem ativada, confere pelo segredo, sem o login do Google e sem ativar de novo", a)
    fake.contas["helena@moura.adv.br"]["resumo"] = resumo("helena@moura.adv.br", vigente=True, periodo="anual")
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(a["ativa"] and a["renova_em"] == "", "o ano pago de uma vez não diz \"renova em\" (não renova sozinho)", a)
    fake.contas["helena@moura.adv.br"]["resumo"] = resumo("helena@moura.adv.br", vigente=False)
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(a["ativa"] is False and a["situacao"] == "vencida" and a["plano"] == "", "o plano que acabou: vencida", a)
    fake.contas["helena@moura.adv.br"]["cadastro"]["documento"] = "11222333000181"
    fake.contas["helena@moura.adv.br"]["resumo"] = resumo("helena@moura.adv.br", vigente=True)
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(a["pessoa"].get("cpf") == "11.222.333/0001-81", "o CNPJ do cadastro vai no mesmo campo (CPF ou CNPJ)", a["pessoa"])

    print("\nsem rede")
    e.prefs.atualizar({"plano": {"ativo": True, "ate": "2099-01-01T00:00:00+00:00", "nome": "Escritório"}})
    fake.fora = True
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(a["ativa"] and a.get("fonte") == "guardado" and a.get("motivo"), "vale o último plano conhecido desta instalação, e diz por quê", a)
    e.prefs.atualizar({"plano": {"ativo": False, "ate": ""}})
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(not a["ativa"] and a["situacao"] == "nenhuma" and "paulus.ia.br" in a.get("motivo", ""), "sem plano conhecido: não confere, e diz por quê", a)
    fake.fora = False

    print("\ntrocar de conta (o /api/vinculo/desvincular de sempre)")
    e.vinculo.destravado = True
    r = local.post("/api/vinculo/desvincular")
    checar(r.status_code == 200 and not r.json()["vinculado"], "desvincula: o passo Conta Google volta a pedir o Google", r.json())
    rbv.esquecer()
    checar(local.get("/api/assinatura").json()["situacao"] == "nenhuma", "e a assinatura espera a conta nova")
    vincular("caio@silva.adv.br", "tok-caio", "Caio Silva")
    a = local.get("/api/assinatura").json()
    sair = fake.foram("/api/ia/sair")
    checar(sair and sair[-1]["quem"] == "helena@moura.adv.br" and nuvem.chave(e, "paulus") == fake.segredo("caio@silva.adv.br")
           and fake.foram("/api/ia/ativar")[-1]["corpo"]["id_token"] == "tok-caio",
           "a nuvem que o assistente ativou minutos antes passa para a conta de agora", [c["caminho"] for c in fake.chamadas[-4:]])
    checar(a["situacao"] == "nenhuma" and a["email"] == "caio@silva.adv.br", "a conta de agora ainda não assinou: nenhuma", a)

    print("\na nuvem ativada antes por outra conta não muda daqui")
    rbv._ativada_aqui["email"] = ""
    vincular("helena@moura.adv.br", "tok-helena", "Helena Moura")
    n_sair, n_ativar = len(fake.foram("/api/ia/sair")), len(fake.foram("/api/ia/ativar"))
    a = local.get("/api/assinatura").json()
    checar(len(fake.foram("/api/ia/sair")) == n_sair and len(fake.foram("/api/ia/ativar")) == n_ativar
           and nuvem.chave(e, "paulus") == fake.segredo("caio@silva.adv.br"), "nem sai nem ativa: o segredo continua o da outra conta")
    checar(a["ativa"] and fake.foram("/api/ia/site/situacao")[-1]["corpo"]["id_token"] == "tok-helena",
           "e a situação da conta que entrou é lida pelo login recente", a)
    e.vinculo._id_token_exp = 0.0
    rbv.esquecer()
    a = local.get("/api/assinatura").json()
    checar(not a["ativa"] and "caio@silva.adv.br" in a.get("motivo", "") and "entre de novo" in a.get("motivo", ""),
           "sem o login, diz de quem é a nuvem daqui e o que fazer", a)
    caio = fake.contas["caio@silva.adv.br"]["resumo"]
    fake.contas["caio@silva.adv.br"]["resumo"] = {**caio, "email": ""}
    vincular("helena@moura.adv.br", "tok-helena", "Helena Moura")
    n_sair = len(fake.foram("/api/ia/sair"))
    local.get("/api/assinatura")
    checar(len(fake.foram("/api/ia/sair")) == n_sair and nuvem.chave(e, "paulus") == fake.segredo("caio@silva.adv.br"),
           "a nuvem daqui de uma conta que não se sabe qual é também não muda")
    fake.contas["caio@silva.adv.br"]["resumo"] = caio
    nuvem.PEDIR["fn"] = None


def test_conexoes() -> None:
    from fastapi.testclient import TestClient

    import api
    import nuvem
    import rotas_boas_vindas as rbv

    e = api.estado
    local = TestClient(api.app, headers=api.cabecalho_local())
    fake = NuvemFalsa()
    nuvem.PEDIR["fn"] = fake
    token = TokenFalso()
    e.contas.endpoints_oauth = {"google": {"token": token.url}}
    try:
        print("\no passo Conexões (POST /api/conexoes/autorizar)")
        e.prefs.atualizar({"vinculo": {"email": "helena@moura.adv.br", "nome": "Helena Moura"}})
        e.vinculo.destravado = True
        antes = local.get("/api/conexoes").json()
        checar("sessao" in antes and "servicos" in antes and antes["gmail"] is False and antes["agenda"] is False and antes["meet"] is False,
               "GET /api/conexoes continua com o WhatsApp e passa a dizer o que o Google autorizou", {k: antes.get(k) for k in ("gmail", "agenda")})
        r = local.post("/api/conexoes/autorizar", json={"servicos": []})
        checar(r.status_code == 400, "sem serviço marcado: 400")
        r = local.post("/api/conexoes/autorizar", json={"servicos": ["agenda"]})
        checar(r.status_code == 409 and "Gmail" in r.json()["detail"], "sem a conta de e-mail, a Agenda sozinha pede o Gmail junto", r.json())
        r = local.post("/api/conexoes/autorizar", json={"servicos": ["gmail", "agenda", "meet"]})
        d = r.json()
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(d.get("url", "")).query))
        checar(r.status_code == 200 and d["servicos"] == ["gmail", "agenda"] and q.get("login_hint") == "helena@moura.adv.br"
               and q.get("include_granted_scopes") == "true", "um consentimento só, com a conta que entrou sugerida e incremental", d)
        escopos = set(q.get("scope", "").split())
        checar(escopos == {"openid", "email", MAIL, AGENDA}, "pede só os escopos marcados (o Meet vem com a Agenda)", escopos)
        checar(e.entrada_oauth is not None and not e.entrada_oauth.abriu_navegador, "quem abre o navegador é a tela (o servidor não abre outro)")
        token.proximo = {"email": "helena@moura.adv.br", "escopos": MAIL + " " + AGENDA}
        checar(navegador(d["url"]) == 200, "o navegador volta do Google com o código")
        checar(esperar(lambda: e.entrada_oauth.fase == "pronto"), "e o Paulus troca o código e guarda a autorização", (e.entrada_oauth.fase, e.entrada_oauth.mensagem))
        conta = e.contas.por_email("helena@moura.adv.br")
        checar(conta is not None and conta.autenticacao == "google" and not int(conta.dono or 0) and AGENDA in conta.escopos.split()
               and e.contas.tem_credencial(conta), "na conta Google do escritório, cifrada como no login do e-mail")
        checar(token.pedidos and token.pedidos[-1].get("grant_type") == "authorization_code" and token.pedidos[-1].get("code_verifier"),
               "a troca do código com PKCE")
        depois = local.get("/api/conexoes").json()
        checar(depois["gmail"] and depois["agenda"] and depois["meet"] and not depois["drive"] and not depois["drive_leitura"]
               and depois["consentimento"]["fase"] == "pronto", "GET /api/conexoes diz o que ficou autorizado", depois)
        checar(e.prefs.dados["google"]["conta"] == "helena@moura.adv.br" and e.prefs.dados["google"]["agenda_sincronizar"],
               "a Agenda conectada sincroniza, como em Conexões")

        print("\ncom a conta de e-mail, um serviço a mais")
        r = local.post("/api/conexoes/autorizar", json={"servicos": ["drive"]})
        d = r.json()
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(d.get("url", "")).query))
        checar(r.status_code == 200 and set(q.get("scope", "").split()) == {"openid", "email", DRIVE}, "o Drive sozinho já pode (a conta tem o Gmail)", d)

        print("\noutra conta Google na volta")
        token.proximo = {"email": "outra@gmail.com", "escopos": MAIL + " " + DRIVE}
        navegador(d["url"])
        checar(esperar(lambda: e.entrada_oauth.fase == "erro") and "mesma conta" in e.entrada_oauth.mensagem,
               "é recusada: a conta deste Paulus é a outra", e.entrada_oauth.mensagem)
        checar(e.contas.por_email("outra@gmail.com") is None and not local.get("/api/conexoes").json()["drive"], "e nada é guardado")

        print("\ncancelar")
        d = local.post("/api/conexoes/autorizar", json={"servicos": ["drive_leitura"]}).json()
        c = local.post("/api/conexoes/cancelar").json()
        checar(c.get("fase") == "cancelado" and e.entrada_oauth.fase == "cancelado", "desiste da espera do consentimento", c)

        print("\no serviço desligado na Minha conta")
        e.prefs.atualizar({"google": {"desligados": ["drive.file"], "ordem": {"id": "g1", "por": "Minha conta", "quando": "2026-10-07T15:00:00.000Z",
                                                                               "conta": "helena@moura.adv.br", "ligados": ["mail.google.com"], "cumprida": "x"}}})
        r = local.post("/api/conexoes/autorizar", json={"servicos": ["drive"]})
        checar(r.status_code == 409 and "Minha conta" in r.json()["detail"], "conectar aqui não liga o que a Minha conta desligou", r.json())
        e.prefs.atualizar({"google": {"desligados": []}})
        rbv._consentimento["entrada"] = None
    finally:
        nuvem.PEDIR["fn"] = None
        token.fechar()


def main() -> int:
    print("=" * 55)
    print("  as rotas do assistente de configuração")
    print("=" * 55)
    try:
        test_rotas_do_assistente()
        test_assinatura()
        test_conexoes()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
