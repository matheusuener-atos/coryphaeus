"""
O convite (docs/PLANO-EQUIPE.md, E4): o PAULUS fica no servidor, e quem entra
para a equipe nao precisa ir ate ele.

  1. o titular, na janela do servidor, convida: nome e e-mail. Sai um link
     https://<escritorio>.paulus.ia.br/convite/<codigo>, que vale 7 dias e
     uma vez - para mandar pelo WhatsApp;
  2. a pessoa abre o link no proprio celular, passa pela verificacao contra
     robos e escolhe a senha: a conta nasce ali, como colaborador, com as
     permissoes que o titular deixou no convite;
  3. le o QR com o Google Authenticator e digita o codigo: a conta fica
     pronta, e o convite deixa de valer. Os codigos de recuperacao aparecem
     nesse momento, uma vez.

Do codigo do convite, so o hash fica guardado. Quem abandona no meio pode
abrir o link de novo: a senha e o QR sao refeitos.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

VALIDADE_S = 7 * 24 * 3600

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS convites (
    hash TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    permissoes TEXT NOT NULL DEFAULT '{}',
    criado REAL NOT NULL,
    expira REAL NOT NULL,
    conta_id INTEGER NOT NULL DEFAULT 0,
    usado REAL NOT NULL DEFAULT 0,
    revogado REAL NOT NULL DEFAULT 0,
    ultimos TEXT NOT NULL DEFAULT ''
);
"""


class ErroConvite(RuntimeError):
    """O convite nao serve (vencido, usado, revogado, nao existe); a frase vai para a tela."""


def _resumo(codigo: str) -> str:
    return hashlib.sha256(str(codigo or "").encode("utf-8")).hexdigest()


class Convites:
    def __init__(self, caminho: Path, contas, *, relogio=time.time) -> None:
        self.caminho = Path(caminho)
        self.contas = contas
        self.relogio = relogio
        self._trava = threading.RLock()
        with self._db() as c:
            c.executescript(_ESQUEMA)
            colunas = {l["name"] for l in c.execute("PRAGMA table_info(convites)")}
            if "email_secundario" not in colunas:
                c.execute("ALTER TABLE convites ADD COLUMN email_secundario TEXT NOT NULL DEFAULT ''")
            # O nivel de seguranca da conta que o convite cria (acesso/contas.py NIVEIS).
            if "seguranca" not in colunas:
                c.execute("ALTER TABLE convites ADD COLUMN seguranca TEXT NOT NULL DEFAULT 'padrao'")

    def _db(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.caminho, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _publico(l: sqlite3.Row, agora: float) -> dict:
        if l["usado"]:
            estado = "aceito"
        elif l["revogado"]:
            estado = "revogado"
        elif l["expira"] < agora:
            estado = "vencido"
        else:
            estado = "aberto"
        return {"id": l["hash"][:12], "nome": l["nome"], "email": l["email"], "criado": l["criado"],
                "expira": l["expira"], "estado": estado, "ultimos": l["ultimos"]}

    # ------------------------------------------------------ o titular

    def criar(self, nome: str, email: str, permissoes: dict | None = None, email_secundario: str = "",
              seguranca: str = "padrao") -> tuple[str, dict]:
        """Devolve (codigo, convite). O codigo so existe agora: vai no link."""
        from acesso.contas import ErroConta

        nome = " ".join(str(nome or "").split())
        if not nome:
            raise ErroConvite("diga o nome da pessoa")
        try:
            email = self.contas._email(email)
        except ErroConta as exc:
            raise ErroConvite(str(exc)) from exc
        if email in self.contas.emails():
            raise ErroConvite("já existe uma conta com esse e-mail")
        try:
            secundario = self.contas._email(email_secundario) if str(email_secundario or "").strip() else ""
        except ErroConta as exc:
            raise ErroConvite("e-mail secundário: " + str(exc)) from exc
        # Sem titular, o convidado viraria titular (a primeira conta e sempre
        # titular): primeiro a conta de quem cuida do escritorio.
        if not self.contas.tem_titular_pronto():
            raise ErroConvite("primeiro crie a sua conta de titular, com o autenticador confirmado")
        codigo = secrets.token_urlsafe(24)
        agora = self.relogio()
        with self._trava, self._db() as c:
            # Um convite aberto por e-mail: convidar de novo substitui o anterior.
            c.execute("UPDATE convites SET revogado = ? WHERE email = ? AND usado = 0 AND revogado = 0", (agora, email))
            from acesso.contas import NIVEIS, PADRAO

            c.execute("INSERT INTO convites (hash, nome, email, permissoes, criado, expira, ultimos, email_secundario, seguranca)"
                      " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (_resumo(codigo), nome, email, json.dumps(permissoes or {}), agora, agora + VALIDADE_S, codigo[-4:],
                       secundario, seguranca if seguranca in NIVEIS else PADRAO))
            l = c.execute("SELECT * FROM convites WHERE hash = ?", (_resumo(codigo),)).fetchone()
        return codigo, self._publico(l, agora)

    def listar(self) -> list[dict]:
        agora = self.relogio()
        with self._db() as c:
            return [self._publico(l, agora) for l in c.execute("SELECT * FROM convites ORDER BY criado DESC LIMIT 50")]

    def revogar(self, id_curto: str) -> None:
        with self._db() as c:
            n = c.execute("UPDATE convites SET revogado = ? WHERE substr(hash, 1, 12) = ? AND usado = 0",
                          (self.relogio(), str(id_curto))).rowcount
        if not n:
            raise ErroConvite("convite não encontrado ou já aceito")

    # ------------------------------------------------------ quem foi convidado

    def _valido(self, codigo: str) -> sqlite3.Row:
        with self._db() as c:
            l = c.execute("SELECT * FROM convites WHERE hash = ?", (_resumo(codigo),)).fetchone()
        if not l:
            raise ErroConvite("este convite não existe; peça um novo ao titular")
        if l["usado"]:
            raise ErroConvite("este convite já foi usado; entre com o seu e-mail e a sua senha")
        if l["revogado"]:
            raise ErroConvite("este convite foi cancelado; peça um novo ao titular")
        if l["expira"] < self.relogio():
            raise ErroConvite("este convite venceu (vale 7 dias); peça um novo ao titular")
        return l

    def ver(self, codigo: str) -> dict:
        l = self._valido(codigo)
        return {"nome": l["nome"], "email": l["email"], "expira": l["expira"], "seguranca": l["seguranca"]}

    def aceitar(self, codigo: str, senha: str) -> dict:
        """
        Cria a conta (ou refaz senha e QR de quem abandonou no meio) e devolve
        o que o celular precisa ler agora: o QR e a chave.
        """
        from acesso.contas import ErroConta

        with self._trava:
            l = self._valido(codigo)
            try:
                if l["conta_id"] and self.contas.obter(l["conta_id"]):
                    self.contas.trocar_senha(l["conta_id"], senha)
                    criada = self.contas.refazer_totp(l["conta_id"])
                    conta_id = l["conta_id"]
                else:
                    feita = self.contas.criar(l["nome"], l["email"], "colaborador", senha,
                                              email_secundario=l["email_secundario"], seguranca=l["seguranca"])
                    conta_id = feita["conta"]["id"]
                    criada = feita
                    permissoes = json.loads(l["permissoes"] or "{}")
                    if permissoes and feita["conta"]["papel"] != "titular":
                        self.contas.mudar_permissoes(conta_id, permissoes)
                    with self._db() as c:
                        c.execute("UPDATE convites SET conta_id = ? WHERE hash = ?", (conta_id, l["hash"]))
            except ErroConta as exc:
                raise ErroConvite(str(exc)) from exc
            if l["seguranca"] == "simples":
                # So o Google: nao ha autenticador a ligar - a conta ja esta
                # pronta, e o convite deixa de valer aqui.
                with self._db() as c:
                    c.execute("UPDATE convites SET usado = ? WHERE hash = ?", (self.relogio(), l["hash"]))
                return {"simples": True, "email": l["email"], "nome": l["nome"]}
        return {"qr_svg": criada["qr_svg"], "segredo": criada["segredo"], "otpauth": criada["otpauth"],
                "email": l["email"], "nome": l["nome"]}

    def aceitar_google(self, codigo: str, email: str) -> str:
        """
        O convite aceito pelo Google (E3a): o Google provou o e-mail - que tem
        de ser o do convite; o link repassado a outra pessoa nao serve. A
        conta nasce sem senha que alguem saiba (entra-se pelo Google), e o QR
        fica guardado 10 minutos sob um token de uso unico, que a pagina do
        convite busca ao voltar.
        """
        l = self._valido(codigo)
        if str(email or "").strip().lower() != l["email"]:
            raise ErroConvite(f"este convite é para {l['email']}; entre no Google com essa conta")
        dados = self.aceitar(codigo, secrets.token_urlsafe(32))
        token = secrets.token_urlsafe(24)
        with self._trava:
            agora = self.relogio()
            self._do_google = {k: v for k, v in getattr(self, "_do_google", {}).items() if v[0] > agora}
            self._do_google[_resumo(token)] = (agora + 600, codigo, dados)
        return token

    def do_google(self, codigo: str, token: str) -> dict:
        """O QR do convite aceito pelo Google - uma vez."""
        with self._trava:
            item = getattr(self, "_do_google", {}).pop(_resumo(token), None)
        if not item or item[0] < self.relogio() or item[1] != codigo:
            raise ErroConvite("a volta do Google venceu; abra o convite de novo")
        return item[2]

    def confirmar(self, codigo: str, codigo_totp: str) -> dict:
        """O primeiro codigo do celular: a conta fica pronta, e o convite deixa de valer."""
        with self._trava:
            l = self._valido(codigo)
            if not l["conta_id"]:
                raise ErroConvite("escolha a senha antes")
            if not self.contas.confirmar_totp(l["conta_id"], codigo_totp):
                raise ErroConvite("o código não confere; confira a hora do celular e digite o que aparece agora")
            recuperacao = self.contas.novos_codigos(l["conta_id"])
            with self._db() as c:
                c.execute("UPDATE convites SET usado = ? WHERE hash = ?", (self.relogio(), l["hash"]))
        return {"codigos_recuperacao": recuperacao, "email": l["email"], "nome": l["nome"]}
