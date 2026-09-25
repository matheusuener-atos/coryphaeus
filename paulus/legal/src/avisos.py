"""
PAULUS - Avisos do Windows.

Duas coisas, e so no Windows:

  - a notificacao do canto da tela (toast), que fica na Central de
    Notificacoes, com o nome e o icone do PAULUS;
  - o botao do PAULUS piscando na barra de tarefas, ate a pessoa voltar para
    a janela.

A notificacao sai pelo Windows PowerShell 5.1, que traz a API de
notificacoes do Windows (WinRT) sem instalar nada. O pwsh 7 nao traz: por
isso o caminho do powershell.exe e fixo. O texto vai em -EncodedCommand, e
nao na linha de comando: um titulo com aspas ou acento nao quebra nada.

Para o aviso aparecer como "PAULUS Legal", e nao como "Windows PowerShell",
o identificador do programa (o mesmo que a janela usa na barra de tarefas)
e registrado uma vez em HKCU, com nome e icone. Sem instalador e sem atalho.

Quem decide QUANDO avisar e o Vigia, que olha os lembretes, o ciclo de foco
e o alerta de pausa a cada meio minuto, no servidor - assim o aviso chega com
a janela minimizada ou noutra tela.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

# O identificador dos avisos, separado do da janela (Coryphaeus.PaulusLegal,
# em desktop.py). O Windows guarda nome e icone de cada identificador na
# primeira notificacao e nao rele quando o registro muda: o primeiro icone,
# com moldura branca, ficou preso ao da janela. Se o icone do aviso mudar de
# novo, troque o sufixo.
APP_ID = "Coryphaeus.PaulusLegal.Avisos"
COR_DO_ICONE = "FF171716"   # o fundo do quadrado, caso o Windows ponha placa atras
NOME = "PAULUS Legal"
# O "P" desenhado para tamanho pequeno - peso forte, letra grande, quadrado
# escuro de ponta a ponta, sem canto transparente -, que e como o Windows
# mostra o icone do aviso (16 a 24 px).
# O paulus-logo.png nao serve: e um recorte com fundo claro, e o aviso vinha
# com uma borda branca. Trocar o desenho pede nome novo: o Windows guarda o
# icone pelo caminho e nao relê o arquivo.
ICONE = Path(__file__).parent.parent / "frontend" / "img" / "paulus-notificacao.png"
POWERSHELL = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"

_registrado = False
# O numero da janela do PAULUS, quando ele roda na janela propria
# (src/desktop.py avisa). No navegador fica 0 e so a notificacao sai.
_hwnd = 0


def disponivel() -> bool:
    return sys.platform == "win32" and POWERSHELL.exists()


def definir_janela(hwnd: int) -> None:
    global _hwnd
    _hwnd = int(hwnd or 0)


def _registrar() -> None:
    """O nome e o icone que o Windows mostra no aviso. Uma vez por processo."""
    global _registrado
    if _registrado:
        return
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{APP_ID}") as chave:
            winreg.SetValueEx(chave, "DisplayName", 0, winreg.REG_SZ, NOME)
            winreg.SetValueEx(chave, "IconBackgroundColor", 0, winreg.REG_SZ, COR_DO_ICONE)
            if ICONE.exists():
                winreg.SetValueEx(chave, "IconUri", 0, winreg.REG_SZ, str(ICONE))
    except OSError:
        # Sem o registro o aviso ainda sai; so pode vir sem o nome certo.
        pass
    _registrado = True


def _roteiro(titulo: str, texto: str) -> str:
    conteudo = (
        "<toast><visual><binding template='ToastGeneric'>"
        f"<text>{escape(titulo)}</text><text>{escape(texto)}</text>"
        "</binding></visual><audio src='ms-winsoundevent:Notification.Reminder'/></toast>"
    )
    # Dentro de aspas simples do PowerShell, so a aspa simples precisa dobrar.
    conteudo = conteudo.replace("'", "''")
    return (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null\n"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        f"$xml.LoadXml('{conteudo}')\n"
        "$aviso = New-Object Windows.UI.Notifications.ToastNotification $xml\n"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_ID}').Show($aviso)\n"
    )


def notificar(titulo: str, texto: str, *, esperar: bool = False) -> bool:
    """
    Mostra o aviso e pisca o botao na barra de tarefas.

    Roda numa thread: o PowerShell leva meio segundo para abrir, e quem
    chama (o Vigia, uma rota) nao tem por que esperar. Com `esperar`, espera
    e devolve se deu certo - e o que o teste da tela usa.
    """
    if not disponivel():
        return False
    _registrar()
    comando = base64.b64encode(_roteiro(titulo, texto).encode("utf-16-le")).decode("ascii")

    resultado = {"ok": False}

    def mandar() -> None:
        try:
            feito = subprocess.run(
                [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", comando],
                capture_output=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            resultado["ok"] = feito.returncode == 0
        except (OSError, subprocess.SubprocessError):
            resultado["ok"] = False

    piscar()
    if esperar:
        mandar()
        return resultado["ok"]
    threading.Thread(target=mandar, name="aviso-windows", daemon=True).start()
    return True


# ------------------------------------------------------- os tipos de aviso
#
# Cada aviso tem um tipo, e cada tipo se liga ou desliga em Configuracoes.
# Os de evento (resposta, aprovacao, transcricao) so saem com a janela do
# PAULUS fora da frente: com ela na frente, a propria tela ja mostra - um
# aviso no canto por cima do que a pessoa esta olhando seria ruido.
TIPOS: dict[str, dict] = {
    "bem_estar": {"rotulo": "Bem-estar e foco", "padrao": True, "so_fora": False,
                  "explica": "lembretes, fim do ciclo de foco e da pausa, e o alerta de 90 min sem pausa"},
    "resposta": {"rotulo": "Resposta pronta", "padrao": True, "so_fora": True,
                 "explica": "quando o assistente termina de responder e você está em outra janela"},
    "aprovacao": {"rotulo": "Aprovação pendente", "padrao": True, "so_fora": True,
                  "explica": "quando um pedido entra na fila de Aprovações e você está em outra janela"},
    "gravacao": {"rotulo": "Transcrição pronta", "padrao": True, "so_fora": True,
                 "explica": "quando uma gravação termina de ser transcrita e você está em outra janela"},
    "agenda": {"rotulo": "Compromisso chegando", "padrao": True, "so_fora": False,
               "explica": "antes de um compromisso da agenda: no aviso escolhido nele, ou 15 min"},
}
ANTECEDENCIA_DA_AGENDA = timedelta(minutes=15)

_prefs = None


def configurar(prefs) -> None:
    """As preferencias de onde `avisar` le o que esta ligado."""
    global _prefs
    _prefs = prefs


def tipo_ligado(dados: dict, tipo: str) -> bool:
    if not dados.get("avisos_windows", True):
        return False
    return bool((dados.get("avisos_tipos") or {}).get(tipo, TIPOS[tipo]["padrao"]))


def janela_na_frente() -> bool:
    """Se a janela do PAULUS e a que a pessoa esta usando agora. Sem janela
    propria (no navegador), nao da para saber: conta como fora."""
    if sys.platform != "win32" or not _hwnd:
        return False
    try:
        import ctypes

        return int(ctypes.windll.user32.GetForegroundWindow() or 0) == _hwnd
    except Exception:  # noqa: BLE001
        return False


def avisar(tipo: str, titulo: str, texto: str) -> bool:
    """
    O aviso de um tipo, se ele estiver ligado - e, nos de evento, so com a
    janela fora da frente. Devolve se mandou.
    """
    if tipo not in TIPOS or os.environ.get("PAULUS_SEM_AVISOS") or _prefs is None:
        return False
    if not tipo_ligado(_prefs.dados, tipo):
        return False
    if TIPOS[tipo]["so_fora"] and janela_na_frente():
        return False
    return notificar(titulo, texto)


def piscar() -> bool:
    """
    O botao do PAULUS pisca na barra de tarefas ate a janela voltar para a
    frente. Com a janela ja na frente, o Windows nao pisca nada.
    """
    if sys.platform != "win32" or not _hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        FLASHW_TRAY, FLASHW_TIMERNOFG = 0x2, 0xC
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), _hwnd, FLASHW_TRAY | FLASHW_TIMERNOFG, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
        return True
    except Exception:  # noqa: BLE001 - piscar e enfeite; sem ele o aviso sai igual
        return False


# ------------------------------------------------------------------ o vigia


def _no_horario(disponibilidade: dict, agora: datetime) -> bool:
    """Lembrete e alerta so no horario de trabalho das preferencias."""
    d = disponibilidade or {}
    if agora.weekday() not in (d.get("dias") or [0, 1, 2, 3, 4]):
        return False
    inicio, fim = d.get("inicio") or "00:00", d.get("fim") or "23:59"
    return inicio <= agora.strftime("%H:%M") <= fim


class Vigia:
    """
    Olha, a cada meio minuto, se ha motivo para avisar:

      - um lembrete ligado, sem a meta cumprida, cujo intervalo venceu desde
        a ultima vez que foi feito (ou avisado, ou desde que o programa abriu);
      - o ciclo de foco ou a pausa que acabou - avisa sempre, porque foi a
        pessoa quem ligou o relogio;
      - o alerta de 90 min sem pausa, no maximo uma vez por hora.

    Lembrete e alerta respeitam o horario de trabalho das preferencias:
    ninguem quer "beba agua" as onze da noite.
    """

    INTERVALO = 30

    def __init__(self, bem_estar, prefs, agenda=None) -> None:
        self.bem_estar = bem_estar
        self.prefs = prefs
        self.agenda = agenda
        self.compromissos_avisados: set = set()
        self.desde = datetime.now()
        self.avisados: dict[int, datetime] = {}
        self.ciclo_avisado: tuple | None = None
        self.alerta_em: datetime | None = None
        self._parar = threading.Event()

    def ligado(self) -> bool:
        return bool(self.prefs.dados.get("avisos_windows", True)) and disponivel()

    def comecar(self) -> None:
        # PAULUS_SEM_AVISOS=1: um segundo servidor (teste, porta extra) nao
        # manda avisos - senao a pessoa recebe cada lembrete duas vezes.
        if not disponivel() or os.environ.get("PAULUS_SEM_AVISOS"):
            return
        threading.Thread(target=self._rodar, name="vigia-avisos", daemon=True).start()

    def parar(self) -> None:
        self._parar.set()

    def _rodar(self) -> None:
        while not self._parar.wait(self.INTERVALO):
            try:
                if self.ligado():
                    self.olhar()
            except Exception:  # noqa: BLE001 - um erro numa volta nao pode matar o vigia
                continue

    def olhar(self, agora: datetime | None = None) -> list[str]:
        """Uma volta. Devolve os titulos avisados - os testes leem isso."""
        agora = agora or datetime.now()
        feitos: list[str] = []
        no_horario = _no_horario(self.prefs.dados.get("disponibilidade"), agora)

        if self.agenda is not None and tipo_ligado(self.prefs.dados, "agenda"):
            feitos += self._olhar_agenda(agora)

        if not tipo_ligado(self.prefs.dados, "bem_estar"):
            return feitos

        c = self.bem_estar.estado_do_ciclo()
        chave = (c.get("estado"), c.get("comeca_em"))
        if c.get("acabou") and chave != self.ciclo_avisado:
            self.ciclo_avisado = chave
            if c.get("estado") == "foco":
                titulo = "Ciclo de foco terminado"
                texto = f"Hora da pausa de {c.get('pausa_min', 5)} min: levante, beba água e olhe para longe."
            else:
                titulo = "Pausa terminada"
                texto = "Comece o próximo ciclo quando quiser."
            notificar(titulo, texto)
            feitos.append(titulo)

        if no_horario:
            for l in self.bem_estar.lembretes():
                if not l.get("ligado") or l.get("cumprido"):
                    continue
                marcos = [self.desde, self.avisados.get(l["id"])]
                if l.get("ultima_vez"):
                    try:
                        marcos.append(datetime.fromisoformat(l["ultima_vez"]))
                    except ValueError:
                        pass
                ultimo = max(m for m in marcos if m)
                if agora - ultimo >= timedelta(minutes=int(l.get("cada_min") or 60)):
                    self.avisados[l["id"]] = agora
                    texto = f"a cada {int(l['cada_min'])} min" + (f" · {l['meta_texto']}" if l.get("meta_dia") else "")
                    notificar(l["titulo"], texto)
                    feitos.append(l["titulo"])

            alerta = self.bem_estar.alerta()
            if alerta and (not self.alerta_em or agora - self.alerta_em >= timedelta(hours=1)):
                self.alerta_em = agora
                notificar(alerta["titulo"], "Feche este ciclo, beba água e caminhe cinco minutos.")
                feitos.append(alerta["titulo"])

        return feitos

    def _olhar_agenda(self, agora: datetime) -> list[str]:
        """
        Compromisso de hoje que comeca dentro da antecedencia dele - a que a
        pessoa escolheu no compromisso (avisar_min) ou 15 min. Uma vez por
        compromisso e horario: remarcou, avisa de novo.
        """
        feitos = []
        hoje = agora.strftime("%Y-%m-%d")
        for c in self.agenda.listar(hoje, hoje):
            hora = str(c.get("hora") or "")[:5]
            try:
                comeca = datetime.fromisoformat(f"{hoje}T{hora}")
            except ValueError:
                continue
            antes = timedelta(minutes=int(c.get("avisar_min") or 0)) or ANTECEDENCIA_DA_AGENDA
            chave = (c.get("id"), hoje, hora)
            if chave in self.compromissos_avisados or not (agora <= comeca <= agora + antes):
                continue
            self.compromissos_avisados.add(chave)
            minutos = round((comeca - agora).total_seconds() / 60)
            onde = c.get("onde_rotulo") or ""
            texto = f"às {hora}" + (f", em {minutos} min" if minutos else ", agora") + (f" · {onde}" if onde else "")
            notificar(c.get("titulo") or "Compromisso", texto)
            feitos.append(c.get("titulo") or "Compromisso")
        return feitos
