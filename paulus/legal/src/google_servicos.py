"""
A conta Google além do Gmail: Agenda, Meet e Drive.

A mesma conta que entra no e-mail (src/correio_oauth.py) ganha, quando a
pessoa pede em Configurações › Conexões, mais uma permissão - a autorização
incremental do Google (include_granted_scopes): o Google soma a permissão nova
às que já existem, e o refresh token passa a valer para todas. Nada muda para
quem só usa o e-mail.

Os escopos, e por que estes:

- Agenda e Meet: `calendar.events` (sensível, sem a avaliação paga). O Meet
  não tem escopo próprio aqui: a sala nasce do evento da Agenda
  (conferenceData), com o link de verdade.
- Drive: `drive.file` (não sensível). O PAULUS só enxerga o que ele mesmo
  pôs no Drive - a pasta PAULUS e o que foi enviado para ela. Ler o Drive
  inteiro pede escopo restrito, com avaliação de segurança paga (CASA). Para o
  Acervo ler o Drive, o caminho sem custo é o Google Drive para computador:
  ele vira uma pasta do Windows ("G:\\Meu Drive"), e o Acervo vigia pastas.

O que sai desta máquina, e quando:

- Agenda: só com "Sincronizar com o Google" ligado, e só título, data, hora,
  duração e o lugar (online/escritório/telefone) de cada compromisso - a
  anotação e o cliente ficam aqui.
- Meet: quando a pessoa pede a sala ("Criar sala no Google Meet" no
  formulário, ou no compromisso já marcado), o evento daquele compromisso vai
  à Agenda do Google na hora - os mesmos campos -, mesmo com a sincronização
  desligada: é a sala que nasce do evento.
- Drive: só o documento que a pessoa manda, pela fila de Aprovações.

Sem biblioteca do Google: HTTP simples, como o login do e-mail.
"""

from __future__ import annotations

import json
import string
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ESCOPOS = {
    "agenda": "https://www.googleapis.com/auth/calendar.events",
    "drive": "https://www.googleapis.com/auth/drive.file",
}
ROTULOS = {"agenda": "Agenda e Meet do Google", "drive": "Google Drive"}
API_AGENDA = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
API_DRIVE = "https://www.googleapis.com/drive/v3/files"
API_DRIVE_ENVIO = "https://www.googleapis.com/upload/drive/v3/files"
PASTA_NO_DRIVE = "PAULUS"
TEMPO_REDE = 20
ONDE_ROTULO = {"online": "Online", "escritorio": "No escritório", "telefone": "Por telefone"}
LIMITE_MULTIPART = 5 * 1024 * 1024


class ErroGoogle(RuntimeError):
    """Erro já em frase de gente. `autorizar` diz qual serviço precisa de permissão."""

    def __init__(self, mensagem: str, *, autorizar: str = "", status: int = 0) -> None:
        super().__init__(mensagem)
        self.autorizar = autorizar
        self.status = status


def _frase_do_erro(resposta, servico: str) -> ErroGoogle:
    try:
        erro = resposta.json().get("error") or {}
    except ValueError:
        erro = {}
    motivo = " ".join(str(x.get("reason", "")) for x in erro.get("errors") or []) + " " + str(erro.get("status", ""))
    mensagem = str(erro.get("message", ""))
    rotulo = ROTULOS.get(servico, "Google")
    if resposta.status_code == 403 and ("insufficient" in motivo.lower() or "SCOPE" in motivo):
        return ErroGoogle(f"falta autorizar o PAULUS a usar {rotulo}: em Configurações › Conexões, clique em Conectar",
                          autorizar=servico, status=403)
    if resposta.status_code == 403 and ("accessNotConfigured" in motivo or "SERVICE_DISABLED" in motivo or "has not been used" in mensagem):
        return ErroGoogle(f"a API de {rotulo} não está ligada no projeto do PAULUS no Google Cloud - "
                          "é um passo de quem publica o programa (docs/google-servicos.md)", status=403)
    if resposta.status_code == 401:
        return ErroGoogle("o Google recusou o acesso: entre de novo com a conta Google em E-mail › Contas", status=401)
    return ErroGoogle(f"o Google respondeu {resposta.status_code}: {mensagem or 'sem detalhe'}"[:240], status=resposta.status_code)


class Google:
    """
    Os serviços do Google de uma conta que já entrou no e-mail.

    `token_de()` devolve o access token (o mesmo que o e-mail usa, renovado
    antes de vencer); `sessao` é trocável nos testes.
    """

    def __init__(self, token_de, sessao=None) -> None:
        self.token_de = token_de
        self.sessao = sessao or requests.Session()
        self._cache_eventos: dict[tuple[str, str], tuple[float, list[dict]]] = {}

    def _chamar(self, servico: str, metodo: str, url: str, **kw) -> dict:
        kw.setdefault("timeout", TEMPO_REDE)
        cabecalhos = dict(kw.pop("headers", {}) or {})
        cabecalhos["Authorization"] = "Bearer " + self.token_de()
        try:
            r = self.sessao.request(metodo, url, headers=cabecalhos, **kw)
        except requests.RequestException as exc:
            raise ErroGoogle("não consegui falar com o Google agora: " + str(exc)[:120]) from exc
        if r.status_code >= 400:
            raise _frase_do_erro(r, servico)
        if r.status_code == 204 or not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {}

    # ------------------------------------------------------------ agenda

    @staticmethod
    def corpo_do_evento(c: dict, meet: bool = False) -> dict:
        """
        O compromisso do PAULUS como evento do Google: título, início, fim e
        lugar. A anotação e o cliente não saem daqui.
        """
        inicio = datetime.fromisoformat(f"{c['data']}T{(c.get('hora') or '09:00')[:5]}").astimezone()
        fim = inicio + timedelta(minutes=int(c.get("duracao") or 60))
        corpo = {
            "summary": c["titulo"],
            "start": {"dateTime": inicio.isoformat(timespec="seconds")},
            "end": {"dateTime": fim.isoformat(timespec="seconds")},
            "description": "Marcado no PAULUS.",
            "extendedProperties": {"private": {"paulus_id": str(c["id"])}},
        }
        if c.get("onde") in ONDE_ROTULO:
            corpo["location"] = ONDE_ROTULO[c["onde"]]
        if meet:
            corpo["conferenceData"] = {"createRequest": {
                "requestId": uuid.uuid4().hex, "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
        return corpo

    @staticmethod
    def sala_do_evento(evento: dict) -> str:
        if evento.get("hangoutLink"):
            return str(evento["hangoutLink"])
        for entrada in (evento.get("conferenceData") or {}).get("entryPoints") or []:
            if entrada.get("entryPointType") == "video" and entrada.get("uri"):
                return str(entrada["uri"])
        return ""

    def enviar_compromisso(self, c: dict, meet: bool = False) -> dict:
        """
        Cria ou atualiza o evento do compromisso. Evento apagado lá (404, 410)
        é criado de novo. Devolve {"google_id", "meet", "link"}.
        """
        corpo = self.corpo_do_evento(c, meet=meet and not c.get("meet"))
        parametros = {"conferenceDataVersion": 1} if "conferenceData" in corpo else {}
        evento = None
        if c.get("google_id"):
            try:
                evento = self._chamar("agenda", "PATCH", f"{API_AGENDA}/{c['google_id']}", json=corpo, params=parametros)
            except ErroGoogle as exc:
                if exc.status not in (404, 410):
                    raise
        if evento is None:
            evento = self._chamar("agenda", "POST", API_AGENDA, json=corpo, params=parametros)
        self._cache_eventos.clear()
        return {"google_id": evento.get("id", ""), "meet": self.sala_do_evento(evento) or c.get("meet", ""),
                "link": evento.get("htmlLink", "")}

    def apagar_compromisso(self, google_id: str) -> None:
        if not google_id:
            return
        try:
            self._chamar("agenda", "DELETE", f"{API_AGENDA}/{google_id}")
        except ErroGoogle as exc:
            if exc.status not in (404, 410):
                raise
        self._cache_eventos.clear()

    def eventos(self, de: str, ate: str, validade: float = 120.0) -> list[dict]:
        """
        Os eventos da agenda principal no período, menos os que o próprio
        PAULUS criou (esses já estão na Agenda). Só para ler: a tela mostra,
        não edita.
        """
        chave = (de, ate)
        guardado = self._cache_eventos.get(chave)
        if guardado and time.time() - guardado[0] < validade:
            return guardado[1]
        inicio = datetime.fromisoformat(de + "T00:00").astimezone().isoformat()
        fim = (datetime.fromisoformat(ate + "T00:00") + timedelta(days=1)).astimezone().isoformat()
        itens: list[dict] = []
        pagina = ""
        for _ in range(10):
            params = {"timeMin": inicio, "timeMax": fim, "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}
            if pagina:
                params["pageToken"] = pagina
            d = self._chamar("agenda", "GET", API_AGENDA, params=params)
            for e in d.get("items") or []:
                if e.get("status") == "cancelled":
                    continue
                if ((e.get("extendedProperties") or {}).get("private") or {}).get("paulus_id"):
                    continue
                itens.append(self._evento_para_tela(e))
            pagina = d.get("nextPageToken", "")
            if not pagina:
                break
        self._cache_eventos[chave] = (time.time(), itens)
        return itens

    @classmethod
    def _evento_para_tela(cls, e: dict) -> dict:
        inicio, fim = e.get("start") or {}, e.get("end") or {}
        if inicio.get("dateTime"):
            a = datetime.fromisoformat(inicio["dateTime"].replace("Z", "+00:00")).astimezone()
            b = datetime.fromisoformat((fim.get("dateTime") or inicio["dateTime"]).replace("Z", "+00:00")).astimezone()
            dia, hora, duracao = a.date().isoformat(), a.strftime("%H:%M"), max(0, int((b - a).total_seconds() // 60))
        else:
            dia, hora, duracao = str(inicio.get("date", ""))[:10], "", 0
        return {"id": e.get("id", ""), "titulo": e.get("summary") or "(sem título)", "data": dia, "hora": hora,
                "duracao": duracao, "link": e.get("htmlLink", ""), "meet": cls.sala_do_evento(e)}

    # ------------------------------------------------------------- drive

    def pasta_no_drive(self, pasta_id: str = "") -> str:
        """A pasta PAULUS no Drive: a guardada, se ainda existe; senão, uma nova."""
        if pasta_id:
            try:
                d = self._chamar("drive", "GET", f"{API_DRIVE}/{pasta_id}", params={"fields": "id,trashed"})
                if d.get("id") and not d.get("trashed"):
                    return d["id"]
            except ErroGoogle as exc:
                if exc.status != 404:
                    raise
        d = self._chamar("drive", "POST", API_DRIVE, params={"fields": "id"},
                         json={"name": PASTA_NO_DRIVE, "mimeType": "application/vnd.google-apps.folder"})
        return d["id"]

    def enviar_ao_drive(self, caminho: Path, pasta_id: str) -> dict:
        """Envia um arquivo para a pasta PAULUS. Devolve id, nome e o link para abrir."""
        caminho = Path(caminho)
        dados = caminho.read_bytes()
        meta = {"name": caminho.name, "parents": [pasta_id]}
        campos = {"fields": "id,name,webViewLink"}
        if len(dados) <= LIMITE_MULTIPART:
            fronteira = "paulus" + uuid.uuid4().hex
            corpo = (f"--{fronteira}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                     + json.dumps(meta) + f"\r\n--{fronteira}\r\nContent-Type: application/octet-stream\r\n\r\n").encode("utf-8") \
                + dados + f"\r\n--{fronteira}--".encode("ascii")
            return self._chamar("drive", "POST", API_DRIVE_ENVIO, params={"uploadType": "multipart", **campos}, data=corpo,
                                headers={"Content-Type": f"multipart/related; boundary={fronteira}"}, timeout=120)
        # Grande: o envio em duas etapas do Google (a sessão, depois os bytes).
        cabecalhos = {"Authorization": "Bearer " + self.token_de(), "Content-Type": "application/json; charset=UTF-8"}
        try:
            r = self.sessao.post(API_DRIVE_ENVIO, params={"uploadType": "resumable", **campos}, json=meta,
                                 headers=cabecalhos, timeout=TEMPO_REDE)
        except requests.RequestException as exc:
            raise ErroGoogle("não consegui falar com o Google agora: " + str(exc)[:120]) from exc
        if r.status_code >= 400:
            raise _frase_do_erro(r, "drive")
        destino = r.headers.get("Location", "")
        try:
            r = self.sessao.put(destino, data=dados, headers={"Content-Length": str(len(dados))}, timeout=600)
        except requests.RequestException as exc:
            raise ErroGoogle("o envio ao Drive caiu no meio: " + str(exc)[:120]) from exc
        if r.status_code >= 400:
            raise _frase_do_erro(r, "drive")
        return r.json()


# ------------------------------------------------ o Drive no computador

def pastas_do_drive_no_computador() -> list[str]:
    """
    Onde o Google Drive para computador deixa o Drive: uma letra de unidade
    com "Meu Drive" (ou "My Drive"), ou a pasta antiga "Google Drive" do
    usuário. Com ela, o Acervo lê o Drive inteiro sem permissão nenhuma.
    """
    achadas: list[str] = []
    for letra in string.ascii_uppercase[3:]:
        for nome in ("Meu Drive", "My Drive"):
            p = Path(f"{letra}:\\{nome}")
            try:
                if p.is_dir():
                    achadas.append(str(p))
            except OSError:
                continue
    antiga = Path.home() / "Google Drive"
    if antiga.is_dir():
        achadas.append(str(antiga))
    return achadas


def hoje_e_depois(dias_antes: int = 7, dias_depois: int = 365) -> tuple[str, str]:
    hoje = date.today()
    return (hoje - timedelta(days=dias_antes)).isoformat(), (hoje + timedelta(days=dias_depois)).isoformat()
