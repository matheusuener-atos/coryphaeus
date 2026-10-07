"""
A ordem da Minha conta e do painel sobre o Google do escritório
(src/google_nuvem.py), com a nuvem e o Google de mentira:

  - o que vai à nuvem: só os nomes curtos dos serviços em uso, com o segredo
    da instalação - nada de e-mail ou token; sem a conta da nuvem, nada vai;
    entrar com o Google conta na hora; a conta de uma pessoa da equipe não;
    no máximo a cada 10 minutos, salvo login ou ordem;
  - desligar: o serviço concedido e fora da lista para de ser usado - a
    Agenda e o Meet, o envio ao Drive, a leitura do Drive (a chamada nem
    sai) - e Conexões diz quem desligou e que a permissão continua no Google;
    conectar de novo aqui é recusado; a conta de uma pessoa da equipe não muda;
  - ligar de novo: volta a ser usado; o que a conta nunca concedeu continua
    fora, e o relatório diz a verdade;
  - o Gmail desligado: a caixa não abre, nada sai (nem para a fila) e o
    pedido já aprovado não manda; a Agenda segue; a ordem do painel diz que
    foi a equipe do Paulus;
  - desvincular: sem o Google, o Paulus para de usar tudo e a ordem fica
    pendente; com ele, a concessão é revogada (com o refresh token), a
    autorização guardada sai e a conta pede para entrar de novo - a conta de
    e-mail e o que já foi baixado ficam; entrar de novo começa do zero;
  - sem rede: nada quebra e a volta seguinte tenta de novo;
  - a leitura da conta na nuvem (conta_paulus) cumpre a ordem pendente na hora;
  - as preferências guardam o que foi desligado (sobrevivem a reabrir).

A nuvem é `nuvem.PEDIR`; o Google da revogação é um http.server local; a
Agenda e o Drive são uma sessão de mentira. Nada sai da máquina. Dados numa
pasta temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_google_nuvem.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-google-nuvem-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_SEM_VOZ"] = "1"
os.environ.pop("PAULUS_COBRANCA", None)
os.environ.pop("PAULUS_INSTALADO", None)
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
SEGREDO = "pia_" + "c3" * 12 + "_" + "d4" * 32
EMAIL = "escritorio@gmail.com"
AGENDA = "https://www.googleapis.com/auth/calendar.events"
DRIVE = "https://www.googleapis.com/auth/drive.file"
QUATRO = {"mail.google.com", "calendar.events", "drive.file", "drive.readonly"}


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


def parado() -> bool:
    """Nenhuma volta em segundo plano andando (o login e a leitura da conta as disparam)."""
    import google_nuvem

    return esperar(lambda: not google_nuvem._trava.locked()
                   and not any(t.name == "google-nuvem" and t.is_alive() for t in threading.enumerate()))


# ------------------------------------------------------------ a nuvem de mentira

class Resposta:
    def __init__(self, status: int, dados: dict) -> None:
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


class NuvemFalsa:
    """O Worker de paulus.ia.br: a conta (com a ordem pendente) e a rota do Google."""

    def __init__(self) -> None:
        self.relatos: list[dict] = []
        self.pendente: dict | None = None
        self.fora = False

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        if self.fora:
            raise ConnectionError("sem internet")
        if url.endswith("/api/ia/google") and metodo == "POST":
            self.relatos.append({"corpo": json.loads(json.dumps(corpo)), "cabecalhos": dict(cabecalhos or {})})
            if self.pendente and (corpo or {}).get("aplicado") == self.pendente["id"]:
                self.pendente = None
            return Resposta(200, {"ok": True, "pendente": self.pendente})
        if url.endswith("/api/ia/conta"):
            return Resposta(200, {"ok": True, "plano_vigente": True, "google_pendente": self.pendente})
        return Resposta(404, {"erro": "rota não existe"})

    def ultimo(self) -> dict:
        return self.relatos[-1]["corpo"] if self.relatos else {}


def ordem(id_: str, ligados: list[str], por: str = "Minha conta") -> dict:
    return {"id": id_, "ligados": ligados, "quando": "2026-10-07T15:00:00.000Z", "por": por}


# ------------------------------------------------------------ o Google de mentira

class RevogarFalso:
    """O oauth2.googleapis.com/revoke: anota o token e responde o que `resposta` disser."""

    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.resposta = (200, {})
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                tamanho = int(self.headers.get("Content-Length") or 0)
                campos = dict(urllib.parse.parse_qsl(self.rfile.read(tamanho).decode()))
                dono.tokens.append(campos.get("token", ""))
                codigo, corpo = dono.resposta
                bruto = json.dumps(corpo).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bruto)))
                self.end_headers()
                self.wfile.write(bruto)

        self.srv = HTTPServer(("127.0.0.1", 0), Manipulador)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/revoke"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def fechar(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


class GoogleDeMentira:
    """A sessão da Agenda e do Drive: anota cada pedido."""

    def __init__(self) -> None:
        self.pedidos: list[tuple] = []

    def request(self, metodo, url, **k):
        self.pedidos.append((metodo, url))
        return type("R", (), {"status_code": 200, "content": b"{}", "json": lambda self: {"id": "ev1"}})()


def test_revogar() -> None:
    print("\na revogação no Google (correio_oauth.revogar)")
    import correio_oauth

    g = RevogarFalso()
    try:
        correio_oauth.revogar("google", "refresh-x", endpoint=g.url)
        checar(g.tokens == ["refresh-x"], "manda o token num formulário, como o Google pede", g.tokens)
        g.resposta = (400, {"error": "invalid_token", "error_description": "Token expired or revoked"})
        try:
            correio_oauth.revogar("google", "ja-revogado", endpoint=g.url)
            checar(True, "token que o Google já não reconhece conta como revogado")
        except correio_oauth.ErroOAuth as exc:
            checar(False, "token que o Google já não reconhece conta como revogado", str(exc))
        g.resposta = (503, {"error": "backend_error"})
        try:
            correio_oauth.revogar("google", "y", endpoint=g.url)
            checar(False, "outra recusa levanta, para tentar de novo")
        except correio_oauth.ErroOAuth as exc:
            checar("backend_error" in str(exc), "outra recusa levanta, para tentar de novo", str(exc))
    finally:
        g.fechar()
    try:
        correio_oauth.revogar("google", "z", endpoint="http://127.0.0.1:9/revoke")
        checar(False, "sem falar com o Google, levanta")
    except correio_oauth.ErroOAuth as exc:
        checar("internet" in str(exc), "sem falar com o Google, levanta (e diz para conferir a internet)", str(exc))


def test_ordem() -> None:
    from fastapi.testclient import TestClient

    import api
    import config
    import google_nuvem
    import google_servicos
    import nuvem
    import segredos

    e = api.estado
    local = TestClient(api.app, headers=api.cabecalho_local())
    fake = NuvemFalsa()
    nuvem.PEDIR["fn"] = fake
    revogar = RevogarFalso()
    e.contas.endpoints_oauth = {"google": {"revogar": revogar.url}}
    tokens = {"access_token": "acesso-1", "refresh_token": "refresh-1", "expira_em": time.time() + 3600,
              "scope": "openid https://mail.google.com/ " + AGENDA + " " + DRIVE}
    try:
        print("\nsem a conta da nuvem")
        checar(google_nuvem.conferir(e, forcar=True) == {} and not fake.relatos, "sem a conta da nuvem ativada, nada vai")
        if not segredos.disponivel():
            print("  pulado: sem DPAPI (a chave da nuvem e o refresh token não se guardam)")
            return
        nuvem.guardar_chave(e, "paulus", SEGREDO)
        r = google_nuvem.conferir(e, forcar=True)
        checar(r.get("escopos") == [] and fake.ultimo() == {"escopos": []}, "com a conta e sem Google no Paulus: nenhum serviço", r)

        print("\nentrar com o Google conta à nuvem")
        conta = e.contas.ligar_oauth("google", EMAIL, "Escritório", dict(tokens))
        conta.assinatura = "Dra. Helena Moura"
        e.contas.salvar()
        parado()
        checar(fake.ultimo() == {"escopos": ["calendar.events", "drive.file", "mail.google.com"]},
               "na hora, só os nomes curtos dos serviços concedidos", fake.relatos[-1:])
        cab = fake.relatos[-1]["cabecalhos"]
        checar(cab.get("Authorization") == "Bearer " + SEGREDO, "com o segredo desta instalação")
        n = len(fake.relatos)
        e.contas.ligar_oauth("google", "pessoa@gmail.com", "Pessoa", dict(tokens, refresh_token="refresh-p"), dono=7, cliente="google_web")
        time.sleep(0.3)
        parado()
        checar(len(fake.relatos) == n, "a conta Google de uma pessoa da equipe não entra (nem dispara)")
        checar(google_nuvem.conferir(e) == {} and len(fake.relatos) == n, "dentro dos 10 minutos, sem login nem ordem, não vai de novo")

        print("\ndesligar a Agenda e o Drive (a Minha conta deixa só o Gmail)")
        fake.pendente = ordem("g1000", ["mail.google.com"])
        r = google_nuvem.conferir(e, forcar=True)
        g = e.prefs.dados["google"]
        checar(r.get("ordem") == "g1000" and r.get("cumprida") and fake.pendente is None, "cumprida e contada com o id", r)
        checar(g["desligados"] == ["calendar.events", "drive.file"] and g["ordem"]["conta"] == EMAIL and g["ordem"]["cumprida"],
               "o que a conta concedeu e ficou fora da lista vai para os desligados", g)
        checar(fake.relatos[-1]["corpo"] == {"escopos": ["mail.google.com"], "aplicado": "g1000"},
               "o relato depois de cumprir diz a verdade: só o Gmail", fake.relatos[-1]["corpo"])
        checar(not e.google_tem("agenda") and not e.google_tem("drive"), "o Paulus não usa mais a Agenda nem o Drive")
        sit = local.get("/api/google").json()
        frase = sit["servicos"]["agenda"]["desligado"]
        checar("Minha conta" in frase and "07/10/2026" in frase and EMAIL in frase and "paulus.ia.br/minha-conta" in frase,
               "Conexões diz quem desligou, quando e onde ligar de novo", frase)
        checar(sit["nuvem"]["rotulo"] == "desligado na Minha conta" and set(sit["nuvem"]["servicos"]) == {"agenda", "drive"},
               "com a etiqueta curta, nos dois serviços", sit["nuvem"])
        checar("não revoga um serviço sozinho" in sit["nuvem"]["aviso"] and "permissão continua concedida" in sit["nuvem"]["aviso"],
               "e diz que a permissão continua no Google", sit["nuvem"]["aviso"])
        c = local.post("/api/google/conectar", json={"servico": "agenda"})
        checar(c.status_code == 409 and "Minha conta" in c.json()["detail"], "conectar de novo aqui é recusado: ligar é lá", c.json())
        comp = e.agenda.salvar({"titulo": "Audiência", "data": "2026-10-09", "hora": "10:00", "duracao": 60, "onde": "online"})
        m = local.post(f"/api/agenda/{comp}/meet")
        checar(m.status_code == 409 and "Agenda" in m.json()["detail"], "a sala do Meet não é criada, e o motivo volta", m.json())
        d = local.post("/api/google/drive/enviar", json={"caminhos": [str(TMP / "x.pdf")]})
        checar(d.status_code == 409 and "Drive" in d.json()["detail"], "enviar ao Drive é recusado antes da fila", d.json())
        falso = GoogleDeMentira()
        token_antes, sessao_antes = e.google.token_de, e.google.sessao
        e.google.sessao, e.google.token_de = falso, lambda: "tok"
        try:
            e.google.enviar_compromisso({"id": comp, "titulo": "Audiência", "data": "2026-10-09", "hora": "10:00"})
            checar(False, "a chamada à Agenda nem sai")
        except google_servicos.ErroGoogle as exc:
            checar(not falso.pedidos and "Minha conta" in str(exc), "a chamada à Agenda nem sai (mesmo por um caminho sem conferir)", falso.pedidos)
        finally:
            e.google.sessao, e.google.token_de = sessao_antes, token_antes
        pessoa = e.contas.por_email("pessoa@gmail.com")
        checar(google_nuvem.frase(e, "agenda", pessoa) == "", "a conta Google da pessoa da equipe não muda")
        conta_obj = e.contas.por_email(EMAIL)
        try:
            api._gmail_desligado_ou_409(conta_obj)
            checar(True, "o Gmail, que ficou na lista, continua")
        except Exception as exc:  # noqa: BLE001
            checar(False, "o Gmail, que ficou na lista, continua", str(exc))

        print("\nligar de novo (e o que a conta nunca concedeu)")
        fake.pendente = ordem("g2000", ["mail.google.com", "calendar.events", "drive.readonly"])
        google_nuvem.conferir(e, forcar=True)
        checar(e.prefs.dados["google"]["desligados"] == ["drive.file"] and e.google_tem("agenda"), "a Agenda volta; o Drive (fora da lista) segue desligado")
        checar(not e.google_tem("drive_leitura") and fake.relatos[-1]["corpo"]["escopos"] == ["calendar.events", "mail.google.com"],
               "a leitura do Drive, que a conta nunca concedeu, continua fora - e o relato diz a verdade", fake.relatos[-1]["corpo"])
        recarregadas = config.Preferencias(Path(os.environ["PAULUS_DADOS"]) / "preferencias.json")
        checar(recarregadas.dados["google"]["desligados"] == ["drive.file"] and recarregadas.dados["google"]["ordem"]["id"] == "g2000",
               "o que foi desligado fica guardado (sobrevive a reabrir o programa)", recarregadas.dados["google"])

        print("\no Gmail desligado (pela equipe do Paulus, no painel)")
        fake.pendente = ordem("g3000", ["calendar.events"], por="painel")
        google_nuvem.conferir(e, forcar=True)
        checar(e.prefs.dados["google"]["desligados"] == ["drive.file", "mail.google.com"] and e.google_tem("agenda"),
               "o Gmail e o Drive saem; a Agenda segue")
        cx = local.get("/api/email/caixa", params={"conta_id": conta_obj.id})
        checar(cx.status_code == 409 and "Gmail" in cx.json()["detail"] and "equipe do Paulus" in cx.json()["detail"],
               "a caixa não abre, e diz que foi a equipe do Paulus", cx.json())
        antes = len(e.fila.pendentes)
        en = local.post("/api/email/enviar", json={"conta_id": conta_obj.id, "para": "cliente@exemplo.com.br", "assunto": "Contrato", "corpo": "Segue."})
        depois = len(e.fila.pendentes)
        checar(en.status_code == 409 and antes == depois, "enviar é recusado, sem ir para a fila", (en.status_code, en.json()))
        try:
            api._enviar_de_fato({"conta_id": conta_obj.id, "para": "cliente@exemplo.com.br", "assunto": "x", "corpo": "y"})
            checar(False, "o pedido aprovado antes da ordem não manda")
        except RuntimeError as exc:
            checar("Gmail" in str(exc), "o pedido aprovado antes da ordem não manda", str(exc))
        lista = {x["email"]: x for x in local.get("/api/email/contas").json()["contas"]}
        checar(lista[EMAIL].get("desligada") == "Gmail desligado pela equipe do Paulus" and not lista["pessoa@gmail.com"].get("desligada"),
               "E-mail › Contas diz isso na linha da conta (só na do escritório)", lista[EMAIL].get("desligada"))

        print("\ndesvincular sem falar com o Google")
        fake.pendente = ordem("g4000", [])
        e.contas.endpoints_oauth = {"google": {"revogar": "http://127.0.0.1:9/revoke"}}
        r = google_nuvem.conferir(e, forcar=True)
        checar(r.get("ordem") == "g4000" and not r.get("cumprida") and fake.pendente is not None,
               "a ordem fica pendente (a nuvem continua mostrando)", r)
        checar(set(e.prefs.dados["google"]["desligados"]) == QUATRO and e.contas.tem_credencial(e.contas.por_email(EMAIL)),
               "o Paulus já para de usar tudo, e a autorização fica para revogar depois")
        checar(fake.relatos[-1]["corpo"] == {"escopos": []}, "e conta isso à nuvem, sem dizer que cumpriu", fake.relatos[-1]["corpo"])
        sit = local.get("/api/google").json()
        checar((sit["nuvem"].get("desvinculo") or {}).get("cumprida") is False and "ainda não foi confirmada" in sit["nuvem"]["desvinculo"]["frase"],
               "Conexões diz que a revogação ainda não foi confirmada", sit["nuvem"].get("desvinculo"))

        print("\ndesvincular com o Google")
        e.contas.endpoints_oauth = {"google": {"revogar": revogar.url}}
        revogar.resposta = (200, {})
        anexo = Path(e.pasta) / "anexo que veio do e-mail.pdf"
        anexo.parent.mkdir(parents=True, exist_ok=True)
        anexo.write_bytes(b"%PDF-1.4 anexo")
        r = google_nuvem.conferir(e, forcar=True)
        c2 = e.contas.por_email(EMAIL)
        checar(r.get("cumprida") and revogar.tokens == ["refresh-1"] and fake.pendente is None,
               "revoga no Google com o refresh token e conta que cumpriu", (r, revogar.tokens))
        checar(c2 is not None and c2.precisa_entrar and not c2.escopos and not e.contas.tem_credencial(c2) and not c2.refresh_protegido,
               "a autorização guardada sai: a conta pede para entrar de novo")
        checar(c2.assinatura == "Dra. Helena Moura" and anexo.is_file() and json.loads(
            (Path(os.environ["PAULUS_DADOS"]) / "contas_email.json").read_text(encoding="utf-8"))["contas"][0]["email"] == EMAIL,
               "a conta de e-mail continua cadastrada, e o que foi baixado fica")
        checar(fake.relatos[-1]["corpo"] == {"escopos": [], "aplicado": "g4000"} and e.prefs.dados["google"]["desligados"] == [],
               "o relato diz que nada fica, e não sobra desligado", fake.relatos[-1]["corpo"])
        sit = local.get("/api/google").json()
        checar(sit["precisa_entrar"] and (sit["nuvem"].get("desvinculo") or {}).get("cumprida") is True
               and "revogado no Google" in sit["nuvem"]["desvinculo"]["frase"], "Conexões diz que foi desvinculada e o que fazer", sit["nuvem"])
        lista = {x["email"]: x for x in local.get("/api/email/contas").json()["contas"]}
        checar(lista[EMAIL].get("desligada") == "Desvinculada pela Minha conta do Paulus · entre de novo",
               "e a linha da conta em E-mail › Contas", lista[EMAIL].get("desligada"))

        print("\nentrar de novo começa do zero")
        e.contas.ligar_oauth("google", EMAIL, "Escritório", dict(tokens, access_token="acesso-2", refresh_token="refresh-2",
                                                                    scope="openid https://mail.google.com/ " + AGENDA))
        parado()
        checar(e.google_tem("agenda") and not e.google_tem("drive") and fake.ultimo() == {"escopos": ["calendar.events", "mail.google.com"]},
               "o que o Google concedeu agora é usado e contado", fake.relatos[-1:])

        print("\nsem rede")
        fake.fora = True
        r = google_nuvem.conferir(e, forcar=True)
        checar("erro" in r, "nada quebra: a volta só anota o erro", r)
        fake.fora = False
        n = len(fake.relatos)
        checar(google_nuvem.conferir(e) == {} and len(fake.relatos) == n, "e espera um pouco antes da próxima volta sozinha")
        google_nuvem._mem["relatado"] = time.time() - google_nuvem.INTERVALO_S - 1
        checar(google_nuvem.conferir(e).get("escopos") == ["calendar.events", "mail.google.com"], "passado o intervalo, conta de novo")

        print("\na leitura da conta na nuvem traz a ordem")
        fake.pendente = ordem("g5000", ["mail.google.com"])
        google_nuvem._mem["tentado"] = 0.0
        nuvem.conta_paulus(e, forcar=True)
        checar(esperar(lambda: fake.pendente is None) and parado() and e.prefs.dados["google"]["desligados"] == ["calendar.events"],
               "ler a conta (conta_paulus) cumpre a ordem pendente na hora, em segundo plano")
        n = len(fake.relatos)
        nuvem.conta_paulus(e, forcar=True)
        time.sleep(0.3)
        parado()
        checar(len(fake.relatos) == n, "sem ordem e com o relato recente, ler a conta não manda nada")

        print("\no que sai")
        corpos = [x["corpo"] for x in fake.relatos]
        checar(all(set(c) <= {"escopos", "aplicado"} and set(c["escopos"]) <= QUATRO for c in corpos)
               and not any("@" in json.dumps(c) or "refresh" in json.dumps(c) or "acesso-" in json.dumps(c) for c in corpos),
               "cada relato: só os nomes curtos dos quatro serviços e o id da ordem - nada de e-mail ou token", corpos[:3])
        checar(all(x["cabecalhos"].get("Authorization") == "Bearer " + SEGREDO for x in fake.relatos), "sempre com o segredo da instalação")
    finally:
        parado()
        nuvem.PEDIR["fn"] = None
        revogar.fechar()


def main() -> int:
    print("=" * 55)
    print("  a ordem da Minha conta sobre o Google do escritório")
    print("=" * 55)
    try:
        test_revogar()
        test_ordem()
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
