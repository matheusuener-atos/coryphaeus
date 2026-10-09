"""
A Conta Atos no PAULUS do servidor (09/10/2026; src/vinculo.py,
src/correio_oauth.py) e a entrada de fora por e-mail e senha (07/10/2026;
src/acesso/rotas.py, src/config.py).

A Conta Atos entra como o Google: o navegador abre atos.dev.br/entrar e volta
a 127.0.0.1. Aqui a volta e simulada de verdade - um GET na porta local com o
code e o state - e a troca do codigo (correio_oauth.trocar_codigo) devolve um
id_token de mentira; nada vai a internet.

  - vincular pela Atos: o endereco e o de atos.dev.br, cliente pavlvs-app,
    PKCE S256, volta em 127.0.0.1; vinculado com `por` "atos", Meus dados
    ganham o e-mail e o token fica so na memoria (1 h);
  - travado, destravar volta a Atos com prompt=login e o e-mail vinculado,
    mesmo pedindo o Google; outra conta nao abre; com a titular, o codigo do
    celular vem depois;
  - o vinculo gravado como "senha" (07/10 a 09/10) conta como Conta Atos;
  - o e-mail do escritorio nao aceita a Atos como provedor (ela nao tem caixa);
  - as rotas /api/vinculo/senha/* sairam;
  - o padrao: e-mail e senha valem de fora (so_google desligado), e o `True`
    gravado pela regra antiga cai uma vez;
  - de fora, "Esqueci a senha" da equipe: o codigo vai ao e-mail (em segundo
    plano), a resposta e a mesma com conta ou sem, a senha nova nao abre
    sessao - a entrada continua pedindo o codigo do autenticador -, o codigo
    errado conta, e o Worker sem o tipo "senha" recebe o "codigo".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_vinculo_atos.py
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-vatos-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def token_falso(email: str, nome: str = "") -> str:
    """O formato do id_token da Atos (ES256): aqui so o e-mail, o nome e o exp importam."""
    return _b64({"alg": "ES256", "typ": "JWT", "kid": "atos-teste"}) + "." + _b64(
        {"iss": "https://atos.dev.br", "aud": "pavlvs-app", "sub": "pv-1", "email": email, "name": nome,
         "email_verified": True, "exp": int(time.time()) + 3600}) + ".assinatura"


def test_preferencia() -> None:
    print("\no padrao novo: e-mail e senha valem de fora")
    from config import Preferencias

    pasta = TMP / "prefs"
    pasta.mkdir(parents=True, exist_ok=True)
    novo = Preferencias(pasta / "nao-existe.json")
    checar(novo.dados["acesso_remoto"]["so_google"] is False, "instalacao nova: so_google desligado")
    antigo = pasta / "antigo.json"
    antigo.write_text(json.dumps({"acesso_remoto": {"so_google": True, "ligado": True}}), encoding="utf-8")
    p = Preferencias(antigo)
    checar(p.dados["acesso_remoto"]["so_google"] is False and p.dados["acesso_remoto"]["ligado"] is True,
           "o True gravado pela regra antiga cai para False (e o resto fica)", p.dados["acesso_remoto"])
    escolhido = pasta / "escolhido.json"
    escolhido.write_text(json.dumps({"acesso_remoto": {"so_google": True, "regra_de_entrada": 2}}), encoding="utf-8")
    checar(Preferencias(escolhido).dados["acesso_remoto"]["so_google"] is True,
           "ligado depois da regra nova: fica ligado")


def _voltar_do_navegador(v, email: str, nome: str, code: str = "codigo-da-atos") -> dict:
    """O navegador volta a porta local com o code e o state do pedido; a troca devolve o id_token."""
    import urllib.parse
    import urllib.request

    import correio_oauth

    entrada = v.entrada
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(entrada.url).query))
    trocas = []

    def trocar(provedor, credenciais, code_, verificador, redirect_uri, **_):
        trocas.append({"provedor": provedor, "client_id": credenciais.get("client_id"), "code": code_,
                       "verificador": verificador, "redirect_uri": redirect_uri})
        return {"access_token": "a", "id_token": token_falso(email, nome), "expira_em": time.time() + 3600}

    antes = correio_oauth.trocar_codigo
    correio_oauth.trocar_codigo = trocar
    try:
        urllib.request.urlopen(q["redirect_uri"] + "?" + urllib.parse.urlencode(
            {"code": code, "state": q["state"], "iss": "https://atos.dev.br"}), timeout=5).read()
        entrada.esperar(5)
    finally:
        correio_oauth.trocar_codigo = antes
    return {"consulta": q, "trocas": trocas, "fase": entrada.fase, "mensagem": entrada.mensagem}


def test_vinculo() -> None:
    print("\no vinculo pela Conta Atos")
    import urllib.parse

    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    v = api.estado.vinculo
    prefs = api.estado.prefs.dados
    abertos: list[str] = []
    v.abrir, abrir_antes = (lambda url: abertos.append(url) or True), v.abrir
    local = TestClient(api.app, headers=api.cabecalho_local())
    prefs.setdefault("pessoa", {}).update(nome="", email="contato@antigo.com.br", email_secundario="")
    try:
        print("  vincular")
        r = local.post("/api/vinculo/entrar", json={"finalidade": "vincular", "provedor": "atos"})
        e = r.json()
        checar(r.status_code == 200 and e["fase"] == "aguardando" and e["atos"], "vincular pela Atos: esperando o navegador", r.text[:200])
        url = urllib.parse.urlsplit(abertos[-1])
        q = dict(urllib.parse.parse_qsl(url.query))
        checar(url.scheme + "://" + url.netloc + url.path == "https://atos.dev.br/entrar" and q["client_id"] == "pavlvs-app"
               and q["code_challenge_method"] == "S256" and q["redirect_uri"].startswith("http://127.0.0.1:")
               and q["scope"] == "openid email profile" and "prompt" not in q,
               "o navegador abre atos.dev.br/entrar: pavlvs-app, PKCE S256, volta em 127.0.0.1, sem pedir a senha de novo", q)
        volta = _voltar_do_navegador(v, "Dona@Escritorio.adv.br", "Dona Moura")
        t = volta["trocas"][0] if volta["trocas"] else {}
        checar(volta["fase"] == "pronto" and t.get("provedor") == "atos" and t.get("client_id") == "pavlvs-app"
               and t.get("redirect_uri") == q["redirect_uri"], "a volta troca o codigo na Atos, com o mesmo endereco de volta", volta)
        e = local.get("/api/vinculo").json()
        checar(e["vinculado"] and e["email"] == "dona@escritorio.adv.br" and e["por"] == "atos" and not e["travado"],
               "vinculado pela Conta Atos, e aberto", e)
        checar(bool(v.id_token_valido()) and e["google_recente"], "o id_token da Atos fica so na memoria (1 h)")
        checar(prefs["pessoa"].get("email") == "dona@escritorio.adv.br" and prefs["pessoa"].get("nome") == "Dona Moura"
               and prefs["pessoa"].get("email_secundario") == "contato@antigo.com.br",
               "Meus dados: o e-mail da conta, o nome, e o e-mail antigo no secundario", prefs["pessoa"])
        t = local.get("/api/acesso/tunel").json()
        checar(t["vinculo"]["por"] == "atos" and t["google_recente"], "o acesso externo sabe que a conta e a Atos e esta confirmada",
               t["vinculo"])

        print("  travado")
        local.post("/api/vinculo/travar")
        r = local.get("/api/documentos")
        checar(r.status_code == 423 and "Google" not in r.text and "sua conta" in r.text, "a trava responde 423 sem mandar ao Google",
               r.text[:160])
        r = local.post("/api/vinculo/entrar", json={"finalidade": "destravar", "provedor": "google"})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(abertos[-1]).query))
        checar(r.status_code == 200 and abertos[-1].startswith("https://atos.dev.br/entrar?") and q.get("prompt") == "login"
               and q.get("login_hint") == "dona@escritorio.adv.br",
               "destravar vai a Atos (a conta vinculada, mesmo pedindo o Google), pede a senha de novo e ja traz o e-mail", q)
        volta = _voltar_do_navegador(v, "outra@x.com", "Outra")
        checar(volta["fase"] == "erro" and "dona@escritorio.adv.br" in volta["mensagem"] and "Conta Atos" in volta["mensagem"]
               and local.get("/api/vinculo").json()["travado"], "outra conta: recusada, e continua travado", volta["mensagem"])
        local.post("/api/vinculo/entrar", json={"finalidade": "destravar"})
        volta = _voltar_do_navegador(v, "dona@escritorio.adv.br", "Dona Moura")
        checar(volta["fase"] == "pronto" and not local.get("/api/vinculo").json()["travado"]
               and local.get("/api/documentos").status_code == 200, "a conta certa abre", volta)

        print("  com o autenticador da titular")
        tit = api.estado.acesso_de_fora.contas.criar("Dona", "dona@escritorio.adv.br", "titular", "senha-local-da-dona")
        api.estado.acesso_de_fora.contas.confirmar_totp(tit["conta"]["id"], codigo_totp(tit["segredo"], int(time.time() // 30) - 1))
        local.post("/api/vinculo/travar")
        local.post("/api/vinculo/entrar", json={"finalidade": "destravar"})
        _voltar_do_navegador(v, "dona@escritorio.adv.br", "Dona Moura")
        e = local.get("/api/vinculo").json()
        checar(e["travado"] and e["precisa_codigo"], "depois da Atos, o codigo do celular (como depois do Google)", e)
        r = local.post("/api/vinculo/codigo", json={"codigo": codigo_totp(tit["segredo"], int(time.time() // 30))})
        checar(r.status_code == 200 and not r.json()["travado"], "codigo certo: abre", r.text[:160])

        print("  o tunel pela trava (o codigo da titular)")
        local.post("/api/vinculo/travar")
        checar(local.get("/api/vinculo").json()["autenticador"], "a trava sabe que ha o autenticador da titular")
        for _ in range(5):
            local.post("/api/vinculo/tunel", json={"ligado": True, "codigo": "000000"})
        r = local.post("/api/vinculo/tunel", json={"ligado": True, "codigo": codigo_totp(tit["segredo"], int(time.time() // 30) + 1)})
        checar(r.status_code == 400 and "demais" in r.json().get("detail", ""), "cinco codigos errados param as tentativas", r.text[:160])
        v._erros_titular = []
        ligados: list[bool] = []
        v.ligar_tunel, antes = ligados.append, v.ligar_tunel
        r = local.post("/api/vinculo/tunel", json={"ligado": False, "codigo": "000000"})
        checar(r.status_code == 400 and ligados == [], "o tunel com o codigo errado: nada muda", r.text[:160])
        r = local.post("/api/vinculo/tunel", json={"ligado": False, "codigo": codigo_totp(tit["segredo"], int(time.time() // 30) + 1)})
        checar(r.status_code == 200 and ligados == [False], "com o codigo da titular, a trava desliga o tunel", r.text[:160])
        r = local.post("/api/vinculo/tunel", json={"ligado": True, "codigo": tit["codigos_recuperacao"][1]})
        checar(r.status_code == 200 and ligados == [False, True], "e com uma chave de recuperacao, liga de novo", r.text[:160])
        v.ligar_tunel = antes
        local.post("/api/vinculo/entrar", json={"finalidade": "destravar"})
        _voltar_do_navegador(v, "dona@escritorio.adv.br", "Dona Moura")
        local.post("/api/vinculo/codigo", json={"codigo": tit["codigos_recuperacao"][2]})
        checar(not local.get("/api/vinculo").json()["travado"], "e com a conta e uma chave de recuperacao abre")

        print("  confirmar (o acesso de fora e a nuvem pedem a conta de novo)")
        v._id_token_exp = 0.0
        checar(not v.id_token_valido(), "o token venceu")
        r = local.post("/api/vinculo/entrar", json={"finalidade": "confirmar"})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(abertos[-1]).query))
        checar(r.status_code == 200 and abertos[-1].startswith("https://atos.dev.br/") and "prompt" not in q,
               "confirmar vai a Atos sem pedir a senha de novo (a sessao do navegador basta)", q)
        _voltar_do_navegador(v, "dona@escritorio.adv.br", "Dona Moura")
        checar(local.get("/api/vinculo").json()["google_recente"], "confirmar renova o token")

        print("  o vinculo de 07/10 a 09/10 (gravado como senha)")
        api.estado.prefs.atualizar({"vinculo": {"por": "senha"}})
        checar(local.get("/api/vinculo").json()["por"] == "atos", "\"senha\" conta como Conta Atos")
        local.post("/api/vinculo/travar")
        local.post("/api/vinculo/entrar", json={"finalidade": "destravar"})
        checar(abertos[-1].startswith("https://atos.dev.br/entrar?"), "e destrava pela Atos")
        local.post("/api/vinculo/cancelar")

        print("  o que saiu e o que nao vale")
        r = local.post("/api/vinculo/senha/entrar", json={"email": "dona@escritorio.adv.br", "senha": "x", "finalidade": "destravar"})
        checar(r.status_code in (404, 405, 423), "as rotas /api/vinculo/senha/* sairam", r.status_code)
        r = local.post("/api/vinculo/entrar", json={"finalidade": "vincular", "provedor": "facebook"})
        checar(r.status_code == 400, "provedor desconhecido: recusado", r.text[:120])
        r = local.post("/api/email/oauth/entrar", json={"provedor": "atos", "email": "dona@escritorio.adv.br"})
        checar(r.status_code in (400, 423), "o e-mail do escritorio nao aceita a Atos como provedor", r.text[:160])
    finally:
        v.abrir = abrir_antes


def test_esqueci_da_equipe() -> None:
    print("\nde fora: Esqueci a senha da equipe")
    from fastapi.testclient import TestClient

    import api
    import segredos
    from acesso.contas import codigo_totp

    if not segredos.disponivel():
        print("  --   sem a protecao de dados do Windows: pulado")
        return
    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    cartas: list[dict] = []
    respostas = {"senha": ""}

    def email_do_cliente(dados):
        cartas.append(dict(dados))
        return respostas.get(dados["tipo"], "")

    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    servico.email_do_cliente = email_do_cliente
    servico.cofre.tem = lambda: True
    prefs.update(ligado=True, hostname="moura.paulus.ia.br")

    def esperar_cartas(n: int) -> None:
        fim = time.time() + 5
        while len(cartas) < n and time.time() < fim:
            time.sleep(0.05)

    try:
        c = servico.contas.criar("Edu", "edu@moura.adv.br", "colaborador", "senha-antiga-do-edu")
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30) - 1))
        fora = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.9.9.9"})
        checar(fora.get("/api/acesso/entrar/config").json().get("so_google") is False, "a tela de entrar oferece a senha")

        r = fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "robo"})
        checar(r.status_code == 403 and not cartas, "sem passar pelo anti-robo: 403, nada sai", r.status_code)
        r = fora.post("/api/acesso/senha/esqueci", json={"email": "ninguem@moura.adv.br", "turnstile": "ok"})
        sem_conta = r.json()
        time.sleep(0.2)
        checar(r.status_code == 200 and not cartas, "e-mail sem conta: a mesma resposta, e nenhum e-mail", r.text[:160])
        r = fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        esperar_cartas(1)
        checar(r.status_code == 200 and r.json() == sem_conta, "com conta: a resposta e a mesma", r.text[:160])
        checar(len(cartas) == 1 and cartas[0]["tipo"] == "senha" and cartas[0]["para"] == "edu@moura.adv.br"
               and len(cartas[0]["codigo"]) == 6 and cartas[0]["link"].startswith("https://moura.paulus.ia.br/"),
               "o codigo vai ao e-mail da conta, pelo Worker, com o tipo senha", cartas)
        codigo = cartas[0]["codigo"]
        errado = "000000" if codigo != "000000" else "111111"

        r = fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": errado, "senha": "senha-nova-do-edu"})
        checar(r.status_code == 400 and "não confere" in r.json().get("detail", ""), "codigo errado: recusado", r.text[:160])
        r = fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": codigo, "senha": "curta"})
        checar(r.status_code == 400 and "10" in r.json().get("detail", ""), "senha nova curta: recusada", r.text[:160])
        r = fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": codigo, "senha": "senha-nova-do-edu"})
        d = r.json()
        checar(r.status_code == 200 and d["ok"] and d["codigo_do_celular"] and "paulus_sessao" not in r.headers.get("set-cookie", ""),
               "codigo certo: senha trocada, sem abrir sessao", r.text[:200])
        r = fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": codigo, "senha": "mais-uma-senha-123"})
        checar(r.status_code == 400, "o mesmo codigo nao vale duas vezes", r.status_code)

        r = fora.post("/api/acesso/entrar", json={"email": "edu@moura.adv.br", "senha": "senha-antiga-do-edu", "turnstile": "ok"})
        checar(r.status_code == 401, "a senha antiga deixa de valer", r.status_code)
        r = fora.post("/api/acesso/entrar", json={"email": "edu@moura.adv.br", "senha": "senha-nova-do-edu", "turnstile": "ok"})
        checar(r.status_code == 200 and r.json().get("pendente") and not r.json().get("ok"),
               "a senha nova entra so ate o codigo do autenticador (nao o dispensa)", r.text[:160])

        print("  tentativas e teto")
        servico.contas._trocas.clear()
        cartas.clear()
        fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        esperar_cartas(1)
        codigo = cartas[-1]["codigo"]
        errado = "000000" if codigo != "000000" else "111111"
        for _ in range(5):
            fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": errado, "senha": "senha-nova-do-edu-3"})
        r = fora.post("/api/acesso/senha/redefinir", json={"email": "edu@moura.adv.br", "codigo": codigo, "senha": "senha-nova-do-edu-3"})
        checar(r.status_code == 400 and "peça outro" in r.json().get("detail", ""), "5 erros: nem o codigo certo vale mais", r.text[:160])
        fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        r = fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        checar(r.status_code == 429, "o 4o pedido na mesma hora: 429", r.status_code)
        r = fora.post("/api/acesso/senha/esqueci", json={"email": "outro@moura.adv.br", "turnstile": "ok"})
        checar(r.status_code == 200, "o teto e por e-mail", r.status_code)

        print("  o Worker que ainda nao conhece o tipo senha")
        servico.contas._trocas.clear()
        cartas.clear()
        respostas["senha"] = "tipo de e-mail desconhecido"
        fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        esperar_cartas(2)
        checar([x["tipo"] for x in cartas] == ["senha", "codigo"] and cartas[1]["codigo"] == cartas[0]["codigo"]
               and cartas[1]["link"].startswith("https://moura.paulus.ia.br/cliente/"),
               "vai o codigo pelo tipo da Area do cliente", cartas)

        print("  o escritorio que escolheu so o Google")
        prefs["so_google"] = True
        r = fora.post("/api/acesso/senha/esqueci", json={"email": "edu@moura.adv.br", "turnstile": "ok"})
        checar(r.status_code == 403, "so Google: nao ha senha para trocar", r.status_code)
        prefs["so_google"] = False
    finally:
        prefs.update(ligado=False, hostname="")
        servico.__dict__.pop("conferir_turnstile", None)
        servico.__dict__.pop("email_do_cliente", None)
        servico.cofre.__dict__.pop("tem", None)


def main() -> int:
    print("=" * 55)
    print("  a Conta Atos no servidor e a senha de fora")
    print("=" * 55)
    try:
        test_preferencia()
        test_vinculo()
        test_esqueci_da_equipe()
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
