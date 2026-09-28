"""
A conexao do acesso de fora (R7): de "desligado" a "https://<nome>.paulus.ia.br
atendendo", sem o advogado abrir painel nenhum. E o passo "Acesso a
distancia" do assistente de configuracao, e o mesmo em Configuracoes ›
Acesso de fora:

  1. o titular escolhe o endereco - sugerido a partir do nome do escritorio
     ("Moura & Associados Advocacia" -> moura-associados), com a
     disponibilidade conferida no Worker enquanto digita;
  2. cria a propria conta, com o autenticador confirmado - sem ela, ninguem
     entra de fora;
  3. o PAULUS escolhe a porta fixa (livre, entre 47000 e 47999) e pede ao
     Worker de paulus.ia.br, que reserva o nome por 15 min; abre o navegador em
     paulus.ia.br/conectar com o codigo curto;
  4. o titular confere o codigo, passa pelo Turnstile e confirma;
  5. o PAULUS pergunta a cada 3 s; quando fica pronto, guarda o token e o
     segredo (DPAPI), grava endereco, sitekey do Turnstile e porta, e liga o
     tunel.

Depois: desligar (mantem o endereco), trocar a porta e remover (apaga tudo,
la e aqui). E, se o Worker disser que o endereco foi liberado por falta de
uso, o PAULUS desliga, apaga o que guardou e avisa.
"""

from __future__ import annotations

import random
import re
import socket
import threading
import time
import unicodedata
import uuid
import webbrowser

from acesso.provisao import ErroProvisao, ErroRemovido, Provisao

FAIXA_DE_PORTAS = (47000, 47999)
INTERVALO_S = 3.0

# O que o nome do escritorio tem e o endereco nao precisa: "Moura &
# Associados Advocacia" vira moura-associados, e nao
# moura-associados-advocacia. "Associados" fica - e parte do nome.
_PALAVRAS_DE_FORA = {"advocacia", "advogados", "advogado", "advogada", "advogadas", "escritorio", "sociedade",
                     "ltda", "eireli", "me", "epp", "ss", "sa", "s", "de", "da", "do", "das", "dos", "e"}
RESERVADOS = {"www", "api", "conectar", "admin", "suporte", "paulus", "atos", "app", "mail", "email", "smtp",
              "imap", "pop", "ftp", "ns1", "ns2", "contato", "status", "blog", "dev", "teste", "testes", "staging",
              "cdn", "static", "assets", "login", "entrar", "conta", "contas", "painel", "ajuda", "site",
              "oficial", "seguranca", "pagamento", "apoio", "apoiar", "loja"}


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _encurtar(partes: list[str], limite: int = 24) -> str:
    saida = ""
    for p in partes:
        proximo = (saida + "-" + p) if saida else p
        if len(proximo) > limite:
            break
        saida = proximo
    return saida or ("-".join(partes)[:limite].strip("-"))


def sugerir_endereco(nome_escritorio: str) -> str:
    """O nome do endereco a partir do nome do escritorio: minusculas, sem acento, hifens, ate 24."""
    palavras = re.findall(r"[a-z0-9]+", _plano(nome_escritorio))
    uteis = [p for p in palavras if p not in _PALAVRAS_DE_FORA]
    slug = _encurtar(uteis)
    if len(slug) < 3:
        slug = _encurtar(palavras)
    if len(slug) < 3:
        slug = "escritorio"
    if slug in RESERVADOS:
        slug = _encurtar([slug, "adv"])
    return slug


def motivo_do_formato(slug: str) -> str:
    """A mesma regra do Worker, dita aqui antes de perguntar la."""
    s = str(slug or "")
    if len(s) < 3:
        return "use pelo menos 3 letras"
    if len(s) > 24:
        return "use no máximo 24 letras"
    if not re.fullmatch(r"[a-z0-9-]+", s):
        return "use só letras minúsculas sem acento, números e hífen"
    if s.startswith("-") or s.endswith("-"):
        return "não comece nem termine com hífen"
    if s in RESERVADOS:
        return "esse nome é reservado"
    return ""


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
        servico.conexao = self

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

    def _instalacao(self) -> str:
        instalacao = self._prefs().get("instalacao_id") or ""
        if not instalacao:
            instalacao = uuid.uuid4().hex
            self._gravar(instalacao_id=instalacao)
        return instalacao

    # ----------------------------------------------------------- o nome

    def disponivel(self, nome: str) -> dict:
        """
        O endereco esta livre? A regra do formato e conferida aqui (sem
        rede); o resto, no Worker - que tambem sugere uma alternativa.
        """
        slug = str(nome or "").strip().lower()
        motivo = motivo_do_formato(slug)
        if motivo:
            alternativa = sugerir_endereco(slug)
            return {"disponivel": False, "motivo": motivo, "sugestao": alternativa if alternativa != slug else ""}
        try:
            return self.provisao.disponivel(slug, self._instalacao())
        except ErroProvisao as exc:
            return {"disponivel": None, "motivo": str(exc), "sugestao": ""}

    # ----------------------------------------------------------- conectar

    def iniciar(self, nome_escritorio: str, slug: str) -> dict:
        nome = " ".join(str(nome_escritorio or "").split())
        slug = str(slug or "").strip().lower()
        if not self.servico.contas.disponivel():
            raise ErroConexao("este computador não tem como guardar os segredos do acesso de fora com proteção")
        vinculo = getattr(self.servico, "vinculo", None)
        if vinculo is not None and not vinculo.vinculado():
            raise ErroConexao("vincule este PAULUS à sua conta Google antes (Configurações › Escritório e equipe)")
        if not self.titulares_prontos():
            raise ErroConexao("primeiro crie a conta do titular e confirme o autenticador")
        if len(nome) < 2:
            raise ErroConexao("diga o nome do escritório")
        motivo = motivo_do_formato(slug)
        if motivo:
            raise ErroConexao("endereço: " + motivo)
        if not self.servico.cloudflared()["basta"]:
            raise ErroConexao("falta o cloudflared neste computador: reinstale o PAULUS (o instalador traz)")
        if self.servico.cofre.tem():
            raise ErroConexao("este PAULUS já está conectado; para trocar, remova antes")
        instalacao = self._instalacao()
        porta = porta_livre_na_faixa()
        try:
            r = self.provisao.iniciar(instalacao, nome, slug, porta)
        except ErroProvisao as exc:
            raise ErroConexao(str(exc)) from exc
        with self._trava:
            self._pedido = {"codigo_usuario": r["codigo_usuario"], "url": r["url"], "expira_em": r["expira_em"],
                            "porta": porta, "estado": "esperando", "nome": nome, "slug": slug,
                            "endereco": f"{slug}.paulus.ia.br"}
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
                # Venceu: o nome escolhido continua no pedido, e "tentar de
                # novo" usa o mesmo.
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
        self._gravar(hostname=entrega["hostname"], turnstile_sitekey=entrega.get("turnstile_sitekey", ""),
                     porta=int(porta), ligado=True, liberado="")
        self._marcar("concluido")
        self.servico.anotar(acao="conexao", alvo=entrega["hostname"], pessoa="janela local")
        self.servico.iniciar()

    # ------------------------------------------------------------ depois

    def verificar_endereco(self) -> None:
        """
        Pergunta ao Worker como esta o endereco. Liberado por falta de uso (ou
        removido de outro lugar): desliga, apaga o que guardou e avisa.
        """
        segredo = self.servico.cofre.segredo() if self.servico.cofre.tem() else ""
        if not segredo:
            return
        try:
            self.provisao.situacao(segredo)
        except ErroRemovido as exc:
            self.servico.endereco_liberado(exc.motivo)
        except ErroProvisao:
            pass  # sem internet agora: pergunta de novo na proxima abertura

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
        except ErroRemovido as exc:
            self.servico.endereco_liberado(exc.motivo)
            raise ErroConexao("o endereço foi liberado por falta de uso; conecte de novo") from exc
        except ErroProvisao as exc:
            raise ErroConexao(str(exc)) from exc
        self.servico.parar()
        self.servico.porta_ocupada = False
        self._gravar(porta=nova)
        self.servico.iniciar()
        return nova

    def remover(self) -> dict:
        """Apaga o endereco na conta do Atos e tudo o que ficou guardado aqui; o nome fica livre."""
        segredo = self.servico.cofre.segredo() if self.servico.cofre.tem() else ""
        avisos: list = []
        if segredo:
            try:
                avisos = self.provisao.remover(segredo).get("avisos") or []
            except ErroRemovido:
                avisos = ["o endereço já tinha sido liberado"]
            except ErroProvisao as exc:
                raise ErroConexao(str(exc)) from exc
        hostname = self._prefs().get("hostname", "")
        self.servico.parar()
        self.servico.cofre.apagar()
        self._gravar(ligado=False, hostname="", turnstile_sitekey="", porta=0, liberado="")
        self.servico.contas.encerrar_sessoes()
        self.servico.anotar(acao="removido", alvo=hostname, pessoa="janela local")
        with self._trava:
            self._pedido = None
        return {"ok": True, "avisos": avisos}
