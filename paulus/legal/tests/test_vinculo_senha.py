"""
A conta PAVLVS por e-mail e senha (07/10/2026) - o Google deixa de ser
obrigatorio (src/vinculo.py, src/acesso/rotas.py, src/config.py).

Com o Worker de paulus.ia.br simulado (nuvem.PEDIR: nada vai a internet):

  - criar a conta manda o codigo; confirmar vincula, como a volta do Google:
    Meus dados ganham o e-mail, o token fica so na memoria (vale 1 h) e o
    vinculo sabe que foi "por senha";
  - a regra da senha e conferida antes de ir ao Worker; o pedido leva a versao;
  - travado, so o e-mail vinculado destrava (outro nem vai ao Worker); a senha
    errada volta com a frase do Worker; a certa abre;
  - com a conta de titular desse e-mail, o codigo do celular vem depois da
    senha, como depois do Google;
  - esqueci a senha + redefinir abre; "confirmar" renova o token;
  - a trava responde 423 sem mandar entrar com o Google;
  - o padrao novo: e-mail e senha valem de fora (so_google desligado), e o
    `True` gravado pela regra antiga cai uma vez;
  - de fora, "Esqueci a senha" da equipe: o codigo vai ao e-mail (em segundo
    plano), a resposta e a mesma com conta ou sem, a senha nova nao abre
    sessao - a entrada continua pedindo o codigo do autenticador -, o codigo
    errado conta, e o Worker sem o tipo "senha" recebe o "codigo".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_vinculo_senha.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-vsenha-"))
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
    """O formato do token do Worker (HS256, kid pv1): aqui so o exp importa."""
    return _b64({"alg": "HS256", "typ": "JWT", "kid": "pv1"}) + "." + _b64(
        {"sub": "pv-1", "email": email, "name": nome, "exp": int(time.time()) + 3600}) + ".assinatura"


class Resposta:
    def __init__(self, status: int, dados: dict) -> None:
        self.status_code = status
        self._dados = dados

    def json(self) -> dict:
        return self._dados


class WorkerFalso:
    """As rotas /api/id/* de worker/identidade.js, em memoria."""

    def __init__(self) -> None:
        self.contas: dict[str, dict] = {}
        self.pendentes: dict[str, dict] = {}
        self.recuperar: dict[str, str] = {}
        self.chamadas: list[tuple[str, dict, dict]] = []
        self.codigo = "123456"
        self.ligado = True

    def __call__(self, metodo, url, cab, corpo, stream):
        self.chamadas.append((url, dict(cab or {}), dict(corpo or {})))
        if "/api/id/" not in url:
            return Resposta(404, {"erro": "rota não existe"})
        if not self.ligado:
            return Resposta(503, {"erro": "a entrada com e-mail e senha ainda não está ligada"})
        rota = url.rsplit("/api/id/", 1)[1]
        email = str(corpo.get("email") or "").lower()
        if rota == "entrar":
            c = self.contas.get(email)
            if not c or c["senha"] != corpo.get("senha"):
                return Resposta(401, {"erro": "e-mail ou senha não conferem"})
            return Resposta(200, {"ok": True, "token": token_falso(email, c["nome"]), "email": email, "nome": c["nome"]})
        if rota == "cadastrar":
            self.pendentes[email] = {"senha": corpo["senha"], "nome": corpo.get("nome", ""), "codigo": self.codigo}
            return Resposta(200, {"ok": True, "enviado": True})
        if rota == "confirmar":
            p = self.pendentes.get(email)
            if not p or p["codigo"] != corpo.get("codigo"):
                return Resposta(400, {"erro": "o código não confere"})
            self.contas[email] = {"senha": p["senha"], "nome": p["nome"]}
            return Resposta(200, {"ok": True, "token": token_falso(email, p["nome"]), "email": email, "nome": p["nome"]})
        if rota == "esqueci":
            if email in self.contas:
                self.recuperar[email] = self.codigo
            return Resposta(200, {"ok": True, "enviado": True})
        if rota == "redefinir":
            if self.recuperar.get(email) != corpo.get("codigo"):
                return Resposta(400, {"erro": "o código não confere"})
            self.contas[email]["senha"] = corpo["senha"]
            nome = self.contas[email]["nome"]
            return Resposta(200, {"ok": True, "token": token_falso(email, nome), "email": email, "nome": nome})
        return Resposta(404, {"erro": "rota não existe"})


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


def test_vinculo() -> None:
    print("\no vinculo pela conta PAVLVS de e-mail e senha")
    from fastapi.testclient import TestClient

    import api
    import nuvem
    from acesso.contas import codigo_totp

    worker = WorkerFalso()
    nuvem.PEDIR["fn"] = worker
    try:
        v = api.estado.vinculo
        prefs = api.estado.prefs.dados
        local = TestClient(api.app, headers=api.cabecalho_local())
        prefs.setdefault("pessoa", {}).update(nome="", email="contato@antigo.com.br", email_secundario="")

        print("  criar a conta")
        r = local.post("/api/vinculo/senha/cadastrar", json={"email": "Dona@Escritorio.Adv.br", "senha": "curta1", "nome": "Dona"})
        checar(r.status_code == 400 and "10" in r.json().get("detail", "") and not worker.chamadas,
               "senha curta: recusada aqui, sem ir ao Worker", r.text[:160])
        r = local.post("/api/vinculo/senha/cadastrar", json={"email": "dona@escritorio.adv.br", "senha": "sosoletrasaqui", "nome": "Dona"})
        checar(r.status_code == 400 and "letras e números" in r.json().get("detail", ""), "sem numero: recusada", r.text[:160])
        r = local.post("/api/vinculo/senha/cadastrar", json={"email": "dona@escritorio.adv.br", "senha": "senha-da-dona-1", "nome": "Dona Moura"})
        checar(r.status_code == 200 and r.json() == {"enviado": True, "email": "dona@escritorio.adv.br"}, "cadastrar: o codigo foi pedido",
               r.text[:160])
        url, cab, corpo = worker.chamadas[-1]
        checar(url == nuvem.SITE + "/api/id/cadastrar" and cab.get("X-PAULUS-Versao") and corpo["nome"] == "Dona Moura",
               "vai a paulus.ia.br/api/id/cadastrar, com a versao no cabecalho", (url, cab))
        checar(not local.get("/api/vinculo").json()["vinculado"], "antes do codigo, nada vinculado")
        r = local.post("/api/vinculo/senha/confirmar", json={"email": "dona@escritorio.adv.br", "codigo": "000000", "finalidade": "vincular"})
        checar(r.status_code == 400 and "não confere" in r.json().get("detail", ""), "codigo errado: a frase do Worker", r.text[:160])
        r = local.post("/api/vinculo/senha/confirmar", json={"email": "dona@escritorio.adv.br", "codigo": "123456", "finalidade": "vincular"})
        e = r.json()
        checar(r.status_code == 200 and e["vinculado"] and e["email"] == "dona@escritorio.adv.br" and e["por"] == "senha"
               and not e["travado"], "codigo certo: vinculado por senha, e aberto", e)
        checar(bool(v.id_token_valido()) and e["google_recente"], "o token do Worker fica como o id_token (1 h)")
        r = local.get("/api/vinculo/token-do-site")
        checar(r.status_code == 200 and r.json().get("token") == v.id_token_valido(),
               "o assistente pega o token para abrir o site da assinatura ja conectado", r.text[:120])
        de_fora = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.9.9.9"})
        checar(de_fora.get("/api/vinculo/token-do-site").status_code in (401, 403, 404, 423),
               "o token do site nao sai para quem vem de fora")
        checar(prefs["pessoa"].get("email") == "dona@escritorio.adv.br" and prefs["pessoa"].get("nome") == "Dona Moura"
               and prefs["pessoa"].get("email_secundario") == "contato@antigo.com.br",
               "Meus dados: o e-mail da conta, o nome, e o e-mail antigo no secundario", prefs["pessoa"])
        t = local.get("/api/acesso/tunel").json()
        checar(t["vinculo"]["por"] == "senha" and t["google_recente"], "o acesso externo sabe que a conta e por senha e esta confirmada",
               t["vinculo"])

        print("  travado")
        local.post("/api/vinculo/travar")
        r = local.get("/api/documentos")
        checar(r.status_code == 423 and "Google" not in r.text and "sua conta" in r.text, "a trava responde 423 sem mandar ao Google",
               r.text[:160])
        n = len(worker.chamadas)
        r = local.post("/api/vinculo/senha/entrar", json={"email": "outra@x.com", "senha": "qualquer-1234", "finalidade": "destravar"})
        checar(r.status_code == 400 and "dona@escritorio.adv.br" in r.json().get("detail", "") and len(worker.chamadas) == n,
               "outro e-mail: recusado aqui, sem ir ao Worker", r.text[:160])
        r = local.post("/api/vinculo/senha/entrar", json={"email": "dona@escritorio.adv.br", "senha": "errada-123456", "finalidade": "destravar"})
        checar(r.status_code == 400 and "não conferem" in r.json().get("detail", "") and local.get("/api/vinculo").json()["travado"],
               "senha errada: a frase do Worker, e continua travado", r.text[:160])
        r = local.post("/api/vinculo/senha/entrar", json={"email": "dona@escritorio.adv.br", "senha": "senha-da-dona-1", "finalidade": "destravar"})
        checar(r.status_code == 200 and not r.json()["travado"] and local.get("/api/documentos").status_code == 200,
               "a senha certa abre", r.text[:160])

        print("  com o autenticador da titular")
        t = api.estado.acesso_de_fora.contas.criar("Dona", "dona@escritorio.adv.br", "titular", "senha-local-da-dona")
        api.estado.acesso_de_fora.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))
        local.post("/api/vinculo/travar")
        e = local.post("/api/vinculo/senha/entrar", json={"email": "dona@escritorio.adv.br", "senha": "senha-da-dona-1",
                                                           "finalidade": "destravar"}).json()
        checar(e["travado"] and e["precisa_codigo"], "depois da senha, o codigo do celular (como depois do Google)", e)
        r = local.post("/api/vinculo/codigo", json={"codigo": codigo_totp(t["segredo"], int(time.time() // 30))})
        checar(r.status_code == 200 and not r.json()["travado"], "codigo certo: abre", r.text[:160])

        print("  esqueci a senha")
        local.post("/api/vinculo/travar")
        r = local.post("/api/vinculo/senha/esqueci", json={"email": "dona@escritorio.adv.br"})
        checar(r.status_code == 200 and r.json()["enviado"], "esqueci: o codigo foi pedido", r.text[:160])
        r = local.post("/api/vinculo/senha/redefinir", json={"email": "dona@escritorio.adv.br", "codigo": "123456",
                                                              "senha": "outra", "finalidade": "destravar"})
        checar(r.status_code == 400 and "10" in r.json().get("detail", ""), "senha nova fraca: recusada aqui", r.text[:160])
        r = local.post("/api/vinculo/senha/redefinir", json={"email": "dona@escritorio.adv.br", "codigo": "123456",
                                                              "senha": "senha-nova-da-dona-2", "finalidade": "destravar"})
        e = r.json()
        checar(r.status_code == 200 and e["precisa_codigo"], "senha nova: entra, e o codigo do celular continua", e)
        local.post("/api/vinculo/codigo", json={"codigo": t["codigos_recuperacao"][0]})
        checar(not local.get("/api/vinculo").json()["travado"], "e com o codigo abre")

        print("  confirmar (o acesso de fora e a nuvem pedem a conta de novo)")
        v._id_token_exp = 0.0
        checar(not v.id_token_valido(), "o token venceu")
        r = local.post("/api/vinculo/senha/entrar", json={"email": "dona@escritorio.adv.br", "senha": "senha-nova-da-dona-2",
                                                           "finalidade": "confirmar"})
        checar(r.status_code == 200 and r.json()["google_recente"] and not r.json()["travado"], "confirmar renova o token", r.text[:160])

        print("  sem o Worker ligado")
        worker.ligado = False
        r = local.post("/api/vinculo/senha/esqueci", json={"email": "dona@escritorio.adv.br"})
        checar(r.status_code == 400 and "ainda não está ligada" in r.json().get("detail", ""), "a frase do Worker chega a tela", r.text[:160])
        worker.ligado = True

        print("  desvincular")
        local.post("/api/vinculo/desvincular")
        checar(local.get("/api/vinculo").json()["por"] == "", "desvinculado: sem jeito de entrar gravado")
    finally:
        nuvem.PEDIR["fn"] = None


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
    print("  a conta PAVLVS por e-mail e senha (07/10/2026)")
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
