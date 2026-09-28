"""
Testes da conta Google além do Gmail (src/google_servicos.py e /api/google).

  - o pedido de permissão: escopo novo, somado aos que existem
    (include_granted_scopes), e a conta guarda o que foi concedido;
  - o evento que sai do compromisso: título, horário e lugar - a anotação e o
    cliente não saem; a sala do Meet quando pedida;
  - evento apagado no Google é criado de novo; a sala volta no link;
  - os eventos do Google vêm sem os que o PAULUS criou, e sem os cancelados;
  - os erros em frase de gente: falta autorizar, API desligada no Cloud;
  - Drive: a pasta PAULUS é criada quando falta, e o envio leva nome e bytes;
  - pela API: salvar compromisso manda ao Google (com a sincronização ligada),
    a grade mostra os eventos de lá, a sala do Meet fica no compromisso,
    apagar apaga lá, e enviar ao Drive vira pedido na fila - só sai depois
    do sim;
  - a sala do Meet pedida ao salvar: o evento vai com conferenceData, o link
    volta na hora e entra no convite; já com sala, não cria outra; fora do
    online, não pede; o Google recusou ou a Agenda não está conectada: o
    compromisso fica salvo, sem sala, e o motivo volta (sem nada sair).

Sem internet: o Google é trocado por respostas prontas. Dados numa pasta
temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_google.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-google-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

import correio_oauth  # noqa: E402
import google_servicos as gs  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Resposta:
    def __init__(self, status=200, corpo=None, cabecalhos=None):
        self.status_code = status
        self._corpo = corpo if corpo is not None else {}
        self.content = json.dumps(self._corpo).encode() if corpo is not None else b""
        self.headers = cabecalhos or {}

    def json(self):
        return self._corpo


class GoogleDeMentira:
    """Guarda cada pedido e responde como o Google responderia."""

    def __init__(self):
        self.pedidos = []
        self.eventos = {}
        self.pastas = {}
        self.arquivos = {}

    def request(self, metodo, url, headers=None, params=None, json=None, data=None, timeout=None):
        self.pedidos.append({"metodo": metodo, "url": url, "params": params or {}, "json": json, "data": data, "headers": headers or {}})
        if url.startswith(gs.API_AGENDA):
            resto = url[len(gs.API_AGENDA):].strip("/")
            if metodo == "POST":
                eid = f"ev{len(self.eventos) + 1}"
                ev = dict(json or {}, id=eid, htmlLink=f"https://calendar.google.com/event?eid={eid}")
                if "conferenceData" in (json or {}) and (params or {}).get("conferenceDataVersion") == 1:
                    ev["hangoutLink"] = f"https://meet.google.com/abc-{eid}"
                self.eventos[eid] = ev
                return Resposta(200, ev)
            if metodo == "PATCH":
                if resto not in self.eventos:
                    return Resposta(404, {"error": {"code": 404, "message": "Not Found"}})
                self.eventos[resto].update(json or {})
                if "conferenceData" in (json or {}):
                    self.eventos[resto]["hangoutLink"] = f"https://meet.google.com/abc-{resto}"
                return Resposta(200, self.eventos[resto])
            if metodo == "DELETE":
                self.eventos.pop(resto, None)
                return Resposta(204)
            if metodo == "GET":
                de_la = [
                    {"id": "g1", "summary": "Almoço com o sócio", "start": {"dateTime": "2026-10-05T12:00:00-03:00"},
                     "end": {"dateTime": "2026-10-05T13:30:00-03:00"}, "htmlLink": "https://calendar.google.com/g1"},
                    {"id": "g2", "summary": "Feriado", "start": {"date": "2026-10-12"}, "end": {"date": "2026-10-13"}},
                    {"id": "g3", "summary": "cancelado", "status": "cancelled", "start": {"date": "2026-10-06"}},
                ]
                meus = [e for e in self.eventos.values()]
                return Resposta(200, {"items": de_la + meus})
        if url.startswith(gs.API_DRIVE_ENVIO):
            nome = "arquivo"
            if data and b"application/json" in data:
                nome = json_de_multipart(data).get("name", "arquivo")
            fid = f"f{len(self.arquivos) + 1}"
            self.arquivos[fid] = data
            return Resposta(200, {"id": fid, "name": nome, "webViewLink": f"https://drive.google.com/file/d/{fid}"})
        if url.startswith(gs.API_DRIVE):
            resto = url[len(gs.API_DRIVE):].strip("/")
            if metodo == "GET":
                return Resposta(200, {"id": resto, "trashed": False}) if resto in self.pastas else Resposta(404, {"error": {"code": 404}})
            if metodo == "POST":
                pid = f"pasta{len(self.pastas) + 1}"
                self.pastas[pid] = json
                return Resposta(200, {"id": pid})
        return Resposta(500, {"error": {"message": "rota de teste desconhecida " + url}})


def json_de_multipart(data: bytes) -> dict:
    texto = data.decode("utf-8", "replace")
    inicio = texto.index("{")
    return json.loads(texto[inicio:texto.index("}", inicio) + 1])


def test_permissao() -> None:
    print("\no pedido de permissão ao Google")
    url = correio_oauth.url_autorizacao("google", "id", "http://127.0.0.1:5/", "s", "d", login_hint="adv@gmail.com",
                                        escopos="openid email " + gs.ESCOPOS["agenda"], incremental=True)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    checar(q["scope"] == "openid email " + gs.ESCOPOS["agenda"] and q["include_granted_scopes"] == "true",
           "pede só o escopo novo, somado aos que já existem", q)
    checar(q["access_type"] == "offline" and q["prompt"] == "consent" and q["login_hint"] == "adv@gmail.com",
           "com a autorização duradoura e a mesma conta sugerida")
    normal = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(
        correio_oauth.url_autorizacao("google", "id", "http://127.0.0.1:5/", "s", "d")).query))
    checar("include_granted_scopes" not in normal and "mail.google.com" in normal["scope"], "o login do e-mail continua igual")


def test_evento() -> None:
    print("\no evento que sai do compromisso")
    c = {"id": 7, "titulo": "Reunião com a Cooperativa", "data": "2026-10-05", "hora": "10:00", "duracao": 90,
         "onde": "online", "anotacao": "levar o aditivo assinado", "cadastro_nome": "Cooperativa Vale Verde"}
    corpo = gs.Google.corpo_do_evento(c)
    texto = json.dumps(corpo, ensure_ascii=False)
    checar(corpo["summary"] == c["titulo"] and corpo["location"] == "Online", "título e lugar", corpo)
    checar("aditivo" not in texto and "Cooperativa Vale Verde" not in texto, "a anotação e o cliente não saem daqui")
    checar(corpo["start"]["dateTime"].startswith("2026-10-05T10:00:00") and corpo["end"]["dateTime"].startswith("2026-10-05T11:30:00"),
           "início e fim com o fuso desta máquina", corpo["start"])
    checar(corpo["extendedProperties"]["private"]["paulus_id"] == "7", "marcado como do PAULUS")
    checar("conferenceData" not in corpo and "conferenceData" in gs.Google.corpo_do_evento(c, meet=True),
           "sala do Meet só quando pedida")

    falso = GoogleDeMentira()
    g = gs.Google(lambda: "tok", sessao=falso)
    r = g.enviar_compromisso(dict(c, google_id="sumiu"), meet=True)
    metodos = [(p["metodo"], p["url"].rsplit("/", 1)[-1]) for p in falso.pedidos]
    checar(metodos == [("PATCH", "sumiu"), ("POST", "events")], "evento apagado lá é criado de novo", metodos)
    checar(r["meet"].startswith("https://meet.google.com/") and falso.pedidos[-1]["params"] == {"conferenceDataVersion": 1},
           "a sala do Meet volta com o link de verdade", r)
    r2 = g.enviar_compromisso(dict(c, google_id=r["google_id"], meet=r["meet"]), meet=True)
    checar("conferenceData" not in (falso.pedidos[-1]["json"] or {}) and r2["meet"] == r["meet"],
           "compromisso que já tem sala não pede outra")
    checar(falso.pedidos[0]["headers"]["Authorization"] == "Bearer tok", "usa o token da conta")


def test_eventos_de_la() -> None:
    print("\nos eventos do Google")
    falso = GoogleDeMentira()
    g = gs.Google(lambda: "tok", sessao=falso)
    g.enviar_compromisso({"id": 1, "titulo": "Nosso", "data": "2026-10-05", "hora": "09:00", "duracao": 30})
    ev = g.eventos("2026-10-01", "2026-10-31")
    titulos = [e["titulo"] for e in ev]
    checar(titulos == ["Almoço com o sócio", "Feriado"], "sem os do PAULUS e sem os cancelados", titulos)
    almoco = ev[0]
    checar(almoco["data"] == "2026-10-05" and almoco["duracao"] == 90 and almoco["link"], "hora, duração e link", almoco)
    checar(ev[1]["hora"] == "" and ev[1]["data"] == "2026-10-12", "o dia todo fica sem hora")
    antes = len(falso.pedidos)
    g.eventos("2026-10-01", "2026-10-31")
    checar(len(falso.pedidos) == antes, "relido dentro de dois minutos, vem do que já tinha")


def test_erros() -> None:
    print("\nos erros")

    class Recusa:
        def __init__(self, status, corpo):
            self.r = Resposta(status, corpo)

        def request(self, *a, **k):
            return self.r

    g = gs.Google(lambda: "tok", sessao=Recusa(403, {"error": {"code": 403, "message": "Request had insufficient authentication scopes.",
                                                               "status": "PERMISSION_DENIED", "errors": [{"reason": "insufficientPermissions"}]}}))
    try:
        g.eventos("2026-10-01", "2026-10-02")
        checar(False, "falta de permissão vira frase")
    except gs.ErroGoogle as exc:
        checar(exc.autorizar == "agenda" and "Conectar" in str(exc), "falta de permissão diz onde conectar", str(exc))
    g = gs.Google(lambda: "tok", sessao=Recusa(403, {"error": {"code": 403, "message": "Google Calendar API has not been used in project 1",
                                                               "errors": [{"reason": "accessNotConfigured"}]}}))
    try:
        g.eventos("2026-10-01", "2026-10-03")
        checar(False, "API desligada vira frase")
    except gs.ErroGoogle as exc:
        checar("Google Cloud" in str(exc), "API desligada no Cloud: diz que é passo de quem publica", str(exc))


def test_drive() -> None:
    print("\nDrive")
    falso = GoogleDeMentira()
    g = gs.Google(lambda: "tok", sessao=falso)
    pasta = g.pasta_no_drive("")
    checar(pasta and falso.pastas[pasta]["name"] == "PAULUS", "cria a pasta PAULUS quando falta")
    checar(g.pasta_no_drive(pasta) == pasta, "usa a pasta que já existe")
    arquivo = TMP / "procuração.pdf"
    arquivo.write_bytes(b"%PDF-1.4 conteudo de teste")
    d = g.enviar_ao_drive(arquivo, pasta)
    corpo = falso.arquivos[d["id"]]
    checar(d["name"] == "procuração.pdf" and b"conteudo de teste" in corpo and pasta.encode() in corpo,
           "o envio leva o nome, a pasta e os bytes", d)
    checar(d["webViewLink"].startswith("https://drive.google.com/"), "e devolve o link para abrir")


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api
    from correio_contas import Conta

    c = TestClient(api.app)
    conta = Conta(id="g1", email="adv@gmail.com", autenticacao="google",
                  escopos="https://mail.google.com/ " + gs.ESCOPOS["agenda"] + " " + gs.ESCOPOS["drive"])
    api.estado.contas.itens.append(conta)
    falso = GoogleDeMentira()
    api.estado.google = gs.Google(lambda: "tok", sessao=falso)
    api.estado.prefs.atualizar({"google": {"agenda_sincronizar": True, "agenda_mostrar": True}})

    d = c.get("/api/google").json()
    checar(d["conta"] == "adv@gmail.com" and d["servicos"]["agenda"]["conectado"] and d["servicos"]["drive"]["conectado"],
           "a situação diz o que está conectado", d.get("servicos"))

    comp = c.post("/api/agenda", json={"id": None, "dados": {"titulo": "Audiência de conciliação", "data": "2026-10-05",
                                                           "hora": "14:30", "duracao": 60, "onde": "online",
                                                           "anotacao": "sigilosa"}}).json()
    fim = time.time() + 5
    while time.time() < fim and not (api.estado.agenda.obter(comp["id"]) or {}).get("google_id"):
        time.sleep(0.1)
    salvo = api.estado.agenda.obter(comp["id"])
    checar(salvo.get("google_id"), "salvar manda o compromisso ao Google", salvo.get("google_id"))
    checar(not any("sigilosa" in json.dumps(p.get("json") or {}) for p in falso.pedidos), "sem a anotação")

    g = c.get("/api/agenda?de=2026-10-01&ate=2026-10-31").json()
    do_google = [x for dia in g["dias"].values() for x in dia if x["genero"] == "google"]
    checar([x["titulo"] for x in do_google] == ["Almoço com o sócio", "Feriado"] and g["contagem"].get("google") == 2,
           "a grade mostra os eventos de lá, só para ler", [x["titulo"] for x in do_google])

    m = c.post(f"/api/agenda/{comp['id']}/meet").json()
    checar(m.get("meet", "").startswith("https://meet.google.com/"), "a sala do Meet fica no compromisso", m.get("meet"))

    test_sala_ao_salvar(c, api, conta, falso)

    gid = api.estado.agenda.obter(comp["id"])["google_id"]
    c.delete(f"/api/agenda/{comp['id']}")
    fim = time.time() + 5
    while time.time() < fim and gid in falso.eventos:
        time.sleep(0.1)
    checar(gid not in falso.eventos, "apagar aqui apaga lá")

    s = c.post("/api/google/sincronizar").json()
    checar(s["falhas"] == [] and "google" in s, "sincronizar agora responde o que fez", s)

    doc = Path(api.estado.pasta) / "contrato para o drive.txt"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("Contrato de teste para o Drive.", encoding="utf-8")
    api.estado.recarregar()
    r = c.post("/api/google/drive/enviar", json={"caminhos": [str(doc)]})
    pedido = r.json().get("pedido") or {}
    checar(r.status_code == 200 and pedido.get("categoria") == "google" and not falso.arquivos,
           "enviar ao Drive vira pedido na fila, e nada sai antes do sim", pedido.get("categoria"))
    resp = c.post("/api/aprovacoes/decidir", json={"ids": [pedido["id"]], "aprovar": True})
    checar(falso.arquivos, "depois do sim, o documento vai para a pasta PAULUS do Drive", (resp.status_code, resp.text[:200]))

    api.estado.contas.itens.remove(conta)
    checar(c.post("/api/google/conectar", json={"servico": "agenda"}).status_code == 400,
           "sem conta Google, conectar diz para entrar primeiro no e-mail")


def test_sala_ao_salvar(c, api, conta, falso) -> None:
    """"Criar sala no Google Meet" ligado no formulario: a sala nasce no salvar."""
    print("\na sala do Meet criada ao salvar")
    ficha = {"titulo": "Reunião de alinhamento", "data": "2026-10-07", "hora": "15:00", "duracao": 45, "onde": "online",
             "anotacao": "pauta interna"}
    antes = len(falso.pedidos)
    r = c.post("/api/agenda", json={"id": None, "dados": ficha, "meet": True})
    d = r.json()
    novos = falso.pedidos[antes:]
    checar(r.status_code == 200 and d.get("meet", "").startswith("https://meet.google.com/") and not d.get("meet_erro"),
           "salvar com a sala pedida devolve o link na hora", d)
    checar(len(novos) == 1 and novos[0]["metodo"] == "POST" and "conferenceData" in (novos[0]["json"] or {})
           and novos[0]["params"] == {"conferenceDataVersion": 1},
           "pede ao Google o evento com a sala (conferenceData), uma vez só", [(p["metodo"], p["params"]) for p in novos])
    salvo = api.estado.agenda.obter(d["id"])
    checar(salvo["meet"] == d["meet"] and salvo["google_id"], "o link e o evento ficam guardados no compromisso", salvo.get("meet"))
    checar("pauta interna" not in json.dumps(novos[0]["json"], ensure_ascii=False), "a anotação continua aqui")

    # Editar e salvar de novo com a opcao ligada nao cria outra sala.
    antes = len(falso.pedidos)
    d2 = c.post("/api/agenda", json={"id": d["id"], "dados": dict(ficha, hora="16:00"), "meet": True}).json()
    fim = time.time() + 5
    while time.time() < fim and len(falso.pedidos) == antes:
        time.sleep(0.1)
    checar(d2["meet"] == d["meet"] and not any("conferenceData" in (p["json"] or {}) for p in falso.pedidos[antes:]),
           "compromisso que já tem sala não ganha outra ao salvar", d2.get("meet"))

    # Sala so para reuniao online.
    antes = len(falso.pedidos)
    fora = c.post("/api/agenda", json={"id": None, "dados": dict(ficha, onde="escritorio"), "meet": True}).json()
    fim = time.time() + 5
    while time.time() < fim and len(falso.pedidos) == antes:
        time.sleep(0.1)
    checar(not fora.get("meet") and not any("conferenceData" in (p["json"] or {}) for p in falso.pedidos[antes:]),
           "no escritório não pede sala", fora.get("meet"))

    # O convite que a tela monta leva o link (conviteDe, js/07-agenda.js).
    js = (RAIZ / "frontend" / "js" / "07-agenda.js").read_text(encoding="utf-8")
    salvar = js[js.index("async function salvarFormAgenda"):js.index("async function apagarCompromisso")]
    checar("meet: sala" in salvar and 'conviteDe(c, c.meet || "")' in salvar,
           "o formulário pede a sala e põe o link no convite por e-mail")
    node = shutil.which("node")
    if node:
        pedacos = []
        for nome in ("MESES_NOME", "DIAS_NOME"):
            i = js.index("const " + nome)
            pedacos.append(js[i:js.index(";", i) + 1])
        for nome in ("deIso", "diaPorExtenso", "duracaoEmTexto", "conviteDe"):
            i = js.index("function " + nome + "(")
            pedacos.append(js[i:js.index("\n}\n", i) + 3])
        roteiro = "\n".join(pedacos) + "\nprocess.stdout.write(conviteDe(" + json.dumps(d, ensure_ascii=False) + ", " + json.dumps(d["meet"]) + "));"
        import subprocess
        saida = subprocess.run([node, "-e", roteiro], capture_output=True, text=True, encoding="utf-8")
        checar(d["meet"] in saida.stdout and "Reunião de alinhamento" in saida.stdout,
               "o texto do convite traz o link da sala", saida.stdout or saida.stderr)
    else:
        print("  --   node não encontrado: o texto do convite não foi conferido")

    # O Google recusou: o compromisso fica salvo e o motivo volta, sem fingir.
    class Recusa:
        def request(self, *a, **k):
            return Resposta(403, {"error": {"code": 403, "message": "insufficient", "status": "PERMISSION_DENIED",
                                            "errors": [{"reason": "insufficientPermissions"}]}})

    google_de_antes = api.estado.google
    api.estado.google = gs.Google(lambda: "tok", sessao=Recusa())
    ruim = c.post("/api/agenda", json={"id": None, "dados": dict(ficha, titulo="Recusado"), "meet": True})
    api.estado.google = google_de_antes
    rj = ruim.json()
    checar(ruim.status_code == 200 and rj.get("id") and not rj.get("meet") and "Conectar" in rj.get("meet_erro", ""),
           "o Google recusou: salvo, sem sala, e o motivo volta", rj.get("meet_erro"))

    # Sem a Agenda conectada: nada vai ao Google, e a resposta diz o que falta.
    escopos = conta.escopos
    conta.escopos = "https://mail.google.com/"
    try:
        antes = len(falso.pedidos)
        sem = c.post("/api/agenda", json={"id": None, "dados": dict(ficha, titulo="Sem Agenda"), "meet": True})
        sj = sem.json()
        time.sleep(0.3)
        checar(sem.status_code == 200 and sj.get("id") and not sj.get("meet") and "conecte a Agenda" in sj.get("meet_erro", ""),
               "sem a Agenda conectada: salvo, sem sala, e diz para conectar", sj.get("meet_erro"))
        checar(len(falso.pedidos) == antes, "sem a Agenda conectada, nada sai para o Google")
        checar(c.get("/api/google").json()["servicos"]["agenda"]["conectado"] is False,
               "a tela sabe que a Agenda não está conectada (a opção oferece conectar)")
    finally:
        conta.escopos = escopos


def main() -> int:
    print("=" * 55)
    print("  a conta Google: Agenda, Meet e Drive")
    print("=" * 55)
    try:
        test_permissao()
        test_evento()
        test_eventos_de_la()
        test_erros()
        test_drive()
        test_api()
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
