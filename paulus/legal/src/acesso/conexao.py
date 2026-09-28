"""
O assistente de conexao (R7): de "desligado" a "https://<escritorio>.paulus.ia.br
atendendo", sem o advogado abrir painel nenhum.

  1. a pessoa confirma o nome do escritorio e o e-mail do titular - que tem de
     ser uma conta de titular com o autenticador confirmado: sem ela, nao ha
     quem entre de fora;
  2. o PAULUS escolhe a porta fixa (livre, entre 47000 e 47999) e pede ao
     Worker de paulus.ia.br; recebe o codigo curto e abre o navegador em
     paulus.ia.br/conectar;
  3. o titular confirma o e-mail pelo Cloudflare Access e aperta Confirmar;
  4. o PAULUS pergunta a cada 3 s; quando fica pronto, guarda o token e o
     segredo (DPAPI), grava endereco e porta, e liga o tunel.

Depois: a lista de quem pode passar pelo Access acompanha as contas, e da para
desligar (mantem o endereco), trocar a porta e remover (apaga tudo, la e aqui).
"""

from __future__ import annotations

import random
import socket
import threading
import time
import uuid
import webbrowser

from acesso.provisao import ErroProvisao, Provisao

FAIXA_DE_PORTAS = (47000, 47999)
INTERVALO_S = 3.0


def porta_livre_na_faixa(tentativas: int = 60) -> int:
    for _ in range(tentativas):
        porta = random.randint(*FAIXA_DE_PORTAS)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    raise RuntimeError("não achei porta livre entre 47000 e 47999")


class ErroConexao(RuntimeError):
    """O que impede de conectar agora; a mensagem vai para a tela."""


class ConexaoDoTunel:
    def __init__(self, servico, provisao=None, abrir_navegador=webbrowser.open, intervalo: float = INTERVALO_S) -> None:
        self.servico = servico
        self.provisao = provisao or Provisao()
        self.abrir_navegador = abrir_navegador
        self.intervalo = intervalo
        self._trava = threading.Lock()
        self._pedido: dict | None = None
        self._segredo_do_pedido = ""
        self._fio: threading.Thread | None = None
        self.erro = ""
        servico.ao_mudar_contas.append(self.sincronizar_emails)

    # ------------------------------------------------------------- estado

    def _prefs(self) -> dict:
        return self.servico.preferencias()

    def _gravar(self, **mudancas) -> None:
        self.servico.prefs.atualizar({"acesso_remoto": mudancas})

    def andamento(self) -> dict:
        """O que a tela mostra do pedido em andamento - sem o codigo secreto."""
        with self._trava:
            p = dict(self._pedido or {})
        p.pop("codigo_dispositivo", None)
        return {"pedido": p or None, "erro": self.erro}

    def titulares_prontos(self) -> list[dict]:
        return [c for c in self.servico.contas.listar() if c["papel"] == "titular" and c["totp_confirmado"]]

    # ----------------------------------------------------------- conectar

    def iniciar(self, nome_escritorio: str, email_titular: str) -> dict:
        email = str(email_titular or "").strip().lower()
        nome = " ".join(str(nome_escritorio or "").split())
        if not self.servico.contas.disponivel():
            raise ErroConexao("este computador não tem como guardar os segredos do acesso de fora com proteção")
        if not any(c["email"] == email for c in self.titulares_prontos()):
            raise ErroConexao("primeiro crie a conta do titular e confirme o autenticador, logo abaixo, em Contas")
        if len(nome) < 2:
            raise ErroConexao("diga o nome do escritório")
        if not self.servico.cloudflared()["basta"]:
            raise ErroConexao("falta o cloudflared neste computador: reinstale o PAULUS marcando “Acesso de fora”")
        if self.servico.cofre.tem():
            raise ErroConexao("este PAULUS já está conectado; para trocar, remova antes")
        instalacao = self._prefs().get("instalacao_id") or uuid.uuid4().hex
        porta = porta_livre_na_faixa()
        try:
            r = self.provisao.iniciar(instalacao, email, nome, porta)
        except ErroProvisao as exc:
            raise ErroConexao(str(exc)) from exc
        self._gravar(instalacao_id=instalacao)
        with self._trava:
            self._pedido = {"codigo_usuario": r["codigo_usuario"], "url": r["url"], "expira_em": r["expira_em"],
                            "porta": porta, "estado": "esperando", "email": email, "nome": nome}
            self._segredo_do_pedido = r["codigo_dispositivo"]
            self.erro = ""
        try:
            self.abrir_navegador(r["url"])
        except Exception:  # noqa: BLE001 - sem navegador, a tela mostra o endereco para abrir a mao
            pass
        self._fio = threading.Thread(target=self._acompanhar, name="acesso-conexao", daemon=True)
        self._fio.start()
        return self.andamento()

    def cancelar(self) -> None:
        with self._trava:
            self._pedido = None
            self._segredo_do_pedido = ""

    def _acompanhar(self) -> None:
        """Pergunta ao Worker a cada 3 s ate o titular confirmar ou o codigo vencer."""
        while True:
            with self._trava:
                codigo = self._segredo_do_pedido
                pedido = self._pedido
            if not codigo or not pedido:
                return
            try:
                r = self.provisao.estado(codigo)
            except ErroProvisao as exc:
                self.erro = str(exc)
                time.sleep(self.intervalo)
                continue
            estado = r.get("estado")
            if estado == "pronto":
                try:
                    self._concluir(r, pedido["porta"])
                except Exception as exc:  # noqa: BLE001 - a tela diz o que falhou
                    self._marcar("falhou")
                    self.erro = str(exc)
                return
            if estado != "pendente":
                self._marcar("expirado")
                return
            time.sleep(self.intervalo)

    def _marcar(self, estado: str) -> None:
        with self._trava:
            if self._pedido:
                self._pedido["estado"] = estado
            self._segredo_do_pedido = ""

    def _concluir(self, entrega: dict, porta: int) -> None:
        """Guarda o que veio uma vez so, grava o endereco e liga o tunel."""
        self.servico.cofre.guardar(entrega["tunnel_token"], entrega["segredo_instalacao"])
        self._gravar(hostname=entrega["hostname"], aud=entrega["aud"], team_domain=entrega["team_domain"],
                     porta=int(porta), ligado=True)
        self._marcar("concluido")
        self.servico.anotar(acao="conexao", alvo=entrega["hostname"], pessoa="janela local")
        self.sincronizar_emails()
        self.servico.iniciar()

    # ------------------------------------------------------------ depois

    def sincronizar_emails(self) -> None:
        """Cada conta do PAULUS entra na lista do Access; conta removida sai."""
        segredo = self.servico.cofre.segredo() if self.servico.cofre.tem() else ""
        if not segredo:
            return
        emails = [c["email"] for c in self.servico.contas.listar()][:10]
        try:
            self.provisao.emails(segredo, emails)
            self.erro = ""
        except ErroProvisao as exc:
            self.erro = "não consegui atualizar a lista de e-mails em paulus.ia.br: " + str(exc)

    def ligar(self, ligado: bool) -> None:
        """Desligar para o tunel e mantem o endereco; ligar sobe de novo."""
        self._gravar(ligado=bool(ligado))
        if ligado:
            self.servico.iniciar()
        else:
            self.servico.parar()
        self.servico.anotar(acao="ligado" if ligado else "desligado", alvo=self._prefs().get("hostname", ""),
                            pessoa="janela local")

    def trocar_porta(self) -> int:
        """A porta fixa estava ocupada: escolhe outra, avisa o Worker e reabre."""
        segredo = self.servico.cofre.segredo()
        if not segredo:
            raise ErroConexao("este PAULUS não está conectado")
        nova = porta_livre_na_faixa()
        try:
            self.provisao.porta(segredo, nova)
        except ErroProvisao as exc:
            raise ErroConexao(str(exc)) from exc
        self.servico.parar()
        self.servico.porta_ocupada = False
        self._gravar(porta=nova)
        self.servico.iniciar()
        return nova

    def remover(self) -> dict:
        """Apaga o endereco na conta do Atos e tudo o que ficou guardado aqui."""
        segredo = self.servico.cofre.segredo() if self.servico.cofre.tem() else ""
        avisos: list = []
        if segredo:
            try:
                avisos = self.provisao.remover(segredo).get("avisos") or []
            except ErroProvisao as exc:
                raise ErroConexao(str(exc)) from exc
        hostname = self._prefs().get("hostname", "")
        self.servico.parar()
        self.servico.cofre.apagar()
        self._gravar(ligado=False, hostname="", aud="", team_domain="", porta=0)
        self.servico.configurar_conferidor()
        self.servico.contas.encerrar_sessoes()
        self.servico.anotar(acao="removido", alvo=hostname, pessoa="janela local")
        return {"ok": True, "avisos": avisos}
