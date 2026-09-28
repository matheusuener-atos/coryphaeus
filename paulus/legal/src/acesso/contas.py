"""
Contas, senha, TOTP e sessoes remotas (R2).

Quem entra de fora entra com uma conta do escritorio: e-mail, senha e o
codigo do aplicativo autenticador (TOTP). Tudo com a biblioteca padrao:

  - senha: `hashlib.scrypt` (n=2**14, r=8, p=1), sal proprio por conta. O
    scrypt e lento DE PROPOSITO e gasta memoria: cada tentativa custa ~50 ms
    e 16 MB aqui, o que torna adivinhar senha em lote caro para quem roubou
    o arquivo, e imperceptivel para quem digita a propria;
  - TOTP: RFC 6238 com `hmac` e `hashlib` - 30 s, 6 digitos, uma janela de
    folga para cada lado (relogio do celular adiantado ou atrasado ate 30 s).
    O mesmo codigo nao vale duas vezes: quem o viu por cima do ombro chega
    tarde;
  - o segredo do TOTP vai protegido pela DPAPI (src/segredos.py). Fora do
    Windows nao ha onde guardar: o modulo diz que esta indisponivel;
  - 10 codigos de recuperacao de uso unico, dos quais so o hash fica.

Sessao remota: cookie aleatorio, e o servidor guarda so o sha256 dele. Expira
em 30 min sem uso e em 12 h no total, e leva um token anti-CSRF que toda rota
que altera algo confere.

Forca bruta: 5 erros seguidos bloqueiam 15 min, e cada novo bloqueio dobra o
tempo. O erro conta por e-mail digitado - exista a conta ou nao -, para que o
bloqueio nao sirva de oraculo de "este e-mail tem conta".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import struct
import threading
import time
from pathlib import Path

PAPEIS = ("titular", "colaborador")
MIN_SENHA = 10
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
# scrypt com n=2**14 e r=8 pede 16 MB; o teto padrao do OpenSSL e 32 MB, e
# e melhor dizer do que depender dele.
SCRYPT_MEMORIA = 64 * 1024 * 1024

TOTP_PASSO = 30
TOTP_DIGITOS = 6
TOTP_JANELA = 1
EMISSOR = "PAULUS"
CODIGOS_DE_RECUPERACAO = 10

SESSAO_OCIOSA_S = 30 * 60
SESSAO_TOTAL_S = 12 * 60 * 60
# Entre a senha certa e o codigo do autenticador: cinco minutos.
PENDENTE_S = 5 * 60

ERROS_ATE_BLOQUEAR = 5
BLOQUEIO_S = 15 * 60

# Alem da conta, o endereco de internet de onde vem o erro: a tela de entrar
# fica exposta a internet, e quem tenta muitas contas diferentes nunca chega
# ao 5o erro de nenhuma. 20 falhas em 10 minutos fecham a porta por 1 hora.
IP_FALHAS_ATE_BLOQUEAR = 20
IP_JANELA_S = 10 * 60
IP_BLOQUEIO_S = 60 * 60


class ErroConta(ValueError):
    """Pedido que nao da para cumprir; a mensagem vai para a tela."""


class ErroEntrada(ValueError):
    """Entrada recusada. `ate` e quando o bloqueio acaba (0 se nao ha)."""

    def __init__(self, mensagem: str, ate: float = 0.0) -> None:
        super().__init__(mensagem)
        self.ate = ate


# ------------------------------------------------------------------ senha

def resumo_da_senha(senha: str, sal: bytes) -> str:
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, maxmem=SCRYPT_MEMORIA, **SCRYPT).hex()


def conferir_forca(senha: str) -> None:
    if len(senha or "") < MIN_SENHA:
        raise ErroConta(f"a senha precisa ter pelo menos {MIN_SENHA} caracteres")


# ------------------------------------------------------------------- TOTP

def novo_segredo() -> str:
    """20 bytes aleatorios em base32, sem o '=' do fim - o que os autenticadores leem."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _bytes_do_segredo(segredo: str) -> bytes:
    limpo = segredo.replace(" ", "").upper()
    return base64.b32decode(limpo + "=" * (-len(limpo) % 8))


def codigo_totp(segredo: str, passo: int) -> str:
    """O codigo do passo `passo` (instante // 30), RFC 6238 com SHA-1."""
    mac = hmac.new(_bytes_do_segredo(segredo), struct.pack(">Q", passo), hashlib.sha1).digest()
    corte = mac[-1] & 0x0F
    numero = struct.unpack(">I", mac[corte:corte + 4])[0] & 0x7FFFFFFF
    return str(numero % 10 ** TOTP_DIGITOS).zfill(TOTP_DIGITOS)


def passo_que_confere(segredo: str, codigo: str, instante: float, janela: int = TOTP_JANELA) -> int | None:
    """O passo em que `codigo` vale, dentro da janela de folga; None se nenhum."""
    codigo = "".join(ch for ch in str(codigo or "") if ch.isdigit())
    if len(codigo) != TOTP_DIGITOS:
        return None
    agora = int(instante // TOTP_PASSO)
    achado = None
    for d in range(-janela, janela + 1):
        # Confere todos, sem sair no primeiro: o tempo de resposta nao diz
        # qual passo bateu.
        if hmac.compare_digest(codigo_totp(segredo, agora + d), codigo):
            achado = agora + d
    return achado


def uri_otpauth(segredo: str, email: str) -> str:
    from urllib.parse import quote

    # Os dois-pontos entre emissor e conta ficam literais: e o formato que os
    # autenticadores mostram como "PAULUS (ana@...)".
    rotulo = quote(f"{EMISSOR}:{email}", safe=":")
    return (f"otpauth://totp/{rotulo}?secret={segredo}&issuer={quote(EMISSOR)}"
            f"&algorithm=SHA1&digits={TOTP_DIGITOS}&period={TOTP_PASSO}")


def qr_svg(texto: str, lado: int = 216) -> str:
    """
    O QR do otpauth:// em SVG. O desenho sai do reportlab, que o programa ja
    usa para o PDF - sem dependencia nova. Sem ele, a tela mostra so o texto.
    """
    try:
        from reportlab.graphics import renderSVG
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
    except ImportError:
        return ""
    w = QrCodeWidget(texto, barLevel="M")
    x0, y0, x1, y1 = w.getBounds()
    largura, altura = x1 - x0, y1 - y0
    d = Drawing(lado, lado, transform=[lado / largura, 0, 0, lado / altura, 0, 0])
    d.add(w)
    svg = renderSVG.drawToString(d)
    inicio = svg.find("<svg")
    return svg[inicio:] if inicio >= 0 else svg


def novos_codigos_de_recuperacao() -> list[str]:
    """10 codigos XXXX-XXXX, sem letra que se confunde (0/O, 1/I)."""
    letras = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(letras) for _ in range(4)) + "-" +
            "".join(secrets.choice(letras) for _ in range(4)) for _ in range(CODIGOS_DE_RECUPERACAO)]


def _resumo(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def _limpo(codigo: str) -> str:
    return "".join(ch for ch in str(codigo or "").upper() if ch.isalnum())


# ----------------------------------------------------------------- contas

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS contas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    papel TEXT NOT NULL,
    senha_sal TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    totp_guardado TEXT NOT NULL DEFAULT '',
    totp_confirmado INTEGER NOT NULL DEFAULT 0,
    totp_ultimo_passo INTEGER NOT NULL DEFAULT 0,
    recuperacao TEXT NOT NULL DEFAULT '[]',
    criada REAL NOT NULL,
    atualizada REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessoes (
    hash TEXT PRIMARY KEY,
    conta_id INTEGER NOT NULL,
    csrf TEXT NOT NULL,
    criada REAL NOT NULL,
    ultimo_uso REAL NOT NULL,
    totp_em REAL NOT NULL DEFAULT 0,
    email_access TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tentativas (
    email TEXT PRIMARY KEY,
    erros INTEGER NOT NULL DEFAULT 0,
    bloqueios INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tentativas_ip (
    ip TEXT PRIMARY KEY,
    falhas TEXT NOT NULL DEFAULT '[]',
    bloqueado_ate REAL NOT NULL DEFAULT 0
);
"""


class Contas:
    """
    As contas do escritorio num SQLite proprio, na pasta de dados.

    `proteger`/`revelar` guardam o segredo do TOTP (DPAPI por padrao). O
    `relogio` e trocavel para o teste andar no tempo sem esperar.
    `ao_bloquear(email, nome, ate)` e chamado a cada bloqueio - e por onde
    o aviso chega a janela local.
    """

    def __init__(self, caminho: Path, *, proteger=None, revelar=None, relogio=time.time, ao_bloquear=None) -> None:
        import segredos

        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._proteger = proteger or segredos.proteger
        self._revelar = revelar or segredos.revelar
        self._disponivel = (lambda: True) if proteger else segredos.disponivel
        self.relogio = relogio
        self.ao_bloquear = ao_bloquear
        self._trava = threading.RLock()
        self._pendentes: dict[str, tuple[int, float, str, str]] = {}
        with self._db() as c:
            c.executescript(_ESQUEMA)

    def _db(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.caminho, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def disponivel(self) -> bool:
        """Sem onde guardar o segredo do TOTP com protecao, nao ha acesso de fora."""
        return bool(self._disponivel())

    # --------------------------------------------------------- consultar

    @staticmethod
    def _publica(linha: sqlite3.Row) -> dict:
        return {
            "id": linha["id"], "nome": linha["nome"], "email": linha["email"], "papel": linha["papel"],
            "totp_confirmado": bool(linha["totp_confirmado"]),
            "codigos_restantes": len(json.loads(linha["recuperacao"] or "[]")),
            "criada": linha["criada"], "atualizada": linha["atualizada"],
        }

    def listar(self) -> list[dict]:
        with self._db() as c:
            return [self._publica(l) for l in c.execute("SELECT * FROM contas ORDER BY id")]

    def obter(self, conta_id: int) -> dict | None:
        with self._db() as c:
            l = c.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()
        return self._publica(l) if l else None

    def emails(self) -> list[str]:
        return [c["email"] for c in self.listar()]

    def tem_titular_pronto(self) -> bool:
        return any(c["papel"] == "titular" and c["totp_confirmado"] for c in self.listar())

    # ----------------------------------------------------------- mudar

    @staticmethod
    def _email(email: str) -> str:
        e = str(email or "").strip().lower()
        if "@" not in e or "." not in e.split("@")[-1] or " " in e or len(e) > 200:
            raise ErroConta("e-mail inválido")
        return e

    def criar(self, nome: str, email: str, papel: str, senha: str) -> dict:
        """
        Cria a conta e devolve, UMA vez, o que so aparece agora: o endereco
        otpauth://, o QR e os codigos de recuperacao. O primeiro cadastro e
        sempre titular - sem titular nao ha quem cuide das contas.
        """
        if not self.disponivel():
            raise ErroConta("este computador não tem onde guardar o segredo do autenticador com proteção")
        nome = str(nome or "").strip()
        if not nome:
            raise ErroConta("diga o nome da pessoa")
        email = self._email(email)
        conferir_forca(senha)
        with self._trava:
            primeira = not self.listar()
            papel = "titular" if primeira else papel
            if papel not in PAPEIS:
                raise ErroConta("papel inválido")
            sal = secrets.token_bytes(16)
            segredo = novo_segredo()
            guardado = self._proteger(segredo)
            if not guardado:
                raise ErroConta("não consegui proteger o segredo do autenticador")
            codigos = novos_codigos_de_recuperacao()
            agora = self.relogio()
            try:
                with self._db() as c:
                    cur = c.execute(
                        "INSERT INTO contas (nome, email, papel, senha_sal, senha_hash, totp_guardado, recuperacao, criada, atualizada)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (nome, email, papel, sal.hex(), resumo_da_senha(senha, sal), guardado,
                         json.dumps([_resumo(_limpo(x)) for x in codigos]), agora, agora))
                    conta_id = cur.lastrowid
            except sqlite3.IntegrityError as exc:
                raise ErroConta("já existe uma conta com esse e-mail") from exc
        uri = uri_otpauth(segredo, email)
        return {"conta": self.obter(conta_id), "otpauth": uri, "segredo": segredo, "qr_svg": qr_svg(uri),
                "codigos_recuperacao": codigos}

    def editar(self, conta_id: int, *, nome: str | None = None, email: str | None = None,
               papel: str | None = None) -> dict:
        with self._trava:
            atual = self.obter(conta_id)
            if not atual:
                raise ErroConta("conta não encontrada")
            novo_papel = papel if papel is not None else atual["papel"]
            if novo_papel not in PAPEIS:
                raise ErroConta("papel inválido")
            if atual["papel"] == "titular" and novo_papel != "titular" and self._titulares() <= 1:
                raise ErroConta("o escritório precisa de pelo menos um titular")
            campos = {"nome": (str(nome).strip() if nome is not None else atual["nome"]) or atual["nome"],
                      "email": self._email(email) if email is not None else atual["email"],
                      "papel": novo_papel}
            try:
                with self._db() as c:
                    c.execute("UPDATE contas SET nome = ?, email = ?, papel = ?, atualizada = ? WHERE id = ?",
                              (campos["nome"], campos["email"], campos["papel"], self.relogio(), conta_id))
            except sqlite3.IntegrityError as exc:
                raise ErroConta("já existe uma conta com esse e-mail") from exc
            # Mudou papel ou e-mail: quem estava dentro entra de novo, com o
            # que vale agora.
            if campos["papel"] != atual["papel"] or campos["email"] != atual["email"]:
                self.encerrar_sessoes(conta_id)
        return self.obter(conta_id)

    def _titulares(self) -> int:
        return sum(1 for c in self.listar() if c["papel"] == "titular")

    def remover(self, conta_id: int) -> None:
        with self._trava:
            atual = self.obter(conta_id)
            if not atual:
                raise ErroConta("conta não encontrada")
            if atual["papel"] == "titular" and self._titulares() <= 1:
                raise ErroConta("não dá para remover o único titular")
            self.encerrar_sessoes(conta_id)
            with self._db() as c:
                c.execute("DELETE FROM contas WHERE id = ?", (conta_id,))

    def senha_confere(self, conta_id: int, senha: str) -> bool:
        linha = self._linha(conta_id)
        if not linha:
            return False
        return hmac.compare_digest(resumo_da_senha(str(senha or ""), bytes.fromhex(linha["senha_sal"])),
                                   linha["senha_hash"])

    def trocar_senha(self, conta_id: int, nova: str) -> int:
        """Troca a senha e derruba todas as sessoes da conta. Devolve quantas caíram."""
        conferir_forca(nova)
        sal = secrets.token_bytes(16)
        with self._db() as c:
            n = c.execute("UPDATE contas SET senha_sal = ?, senha_hash = ?, atualizada = ? WHERE id = ?",
                          (sal.hex(), resumo_da_senha(nova, sal), self.relogio(), conta_id)).rowcount
        if not n:
            raise ErroConta("conta não encontrada")
        return self.encerrar_sessoes(conta_id)

    def _linha(self, conta_id: int) -> sqlite3.Row | None:
        with self._db() as c:
            return c.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()

    def _segredo(self, linha) -> str:
        return self._revelar(linha["totp_guardado"]) if linha and linha["totp_guardado"] else ""

    def confirmar_totp(self, conta_id: int, codigo: str) -> bool:
        """O primeiro codigo do autenticador prova que o cadastro deu certo."""
        linha = self._linha(conta_id)
        segredo = self._segredo(linha)
        if not segredo:
            return False
        passo = passo_que_confere(segredo, codigo, self.relogio())
        if passo is None:
            return False
        with self._db() as c:
            c.execute("UPDATE contas SET totp_confirmado = 1, totp_ultimo_passo = ?, atualizada = ? WHERE id = ?",
                      (passo, self.relogio(), conta_id))
        return True

    def refazer_totp(self, conta_id: int) -> dict:
        """Celular perdido: segredo novo, sessoes derrubadas, confirmar de novo."""
        linha = self._linha(conta_id)
        if not linha:
            raise ErroConta("conta não encontrada")
        segredo = novo_segredo()
        guardado = self._proteger(segredo)
        if not guardado:
            raise ErroConta("não consegui proteger o segredo do autenticador")
        with self._db() as c:
            c.execute("UPDATE contas SET totp_guardado = ?, totp_confirmado = 0, totp_ultimo_passo = 0,"
                      " atualizada = ? WHERE id = ?", (guardado, self.relogio(), conta_id))
        self.encerrar_sessoes(conta_id)
        uri = uri_otpauth(segredo, linha["email"])
        return {"otpauth": uri, "segredo": segredo, "qr_svg": qr_svg(uri)}

    def novos_codigos(self, conta_id: int) -> list[str]:
        codigos = novos_codigos_de_recuperacao()
        with self._db() as c:
            n = c.execute("UPDATE contas SET recuperacao = ?, atualizada = ? WHERE id = ?",
                          (json.dumps([_resumo(_limpo(x)) for x in codigos]), self.relogio(), conta_id)).rowcount
        if not n:
            raise ErroConta("conta não encontrada")
        return codigos

    # ------------------------------------------------------ forca bruta

    def _bloqueado_ate(self, email: str) -> float:
        with self._db() as c:
            l = c.execute("SELECT bloqueado_ate FROM tentativas WHERE email = ?", (email,)).fetchone()
        return float(l["bloqueado_ate"]) if l else 0.0

    def _errou(self, email: str) -> float:
        """Conta o erro; no quinto, bloqueia. Devolve ate quando (0 se nao bloqueou)."""
        with self._trava, self._db() as c:
            l = c.execute("SELECT * FROM tentativas WHERE email = ?", (email,)).fetchone()
            erros = (l["erros"] if l else 0) + 1
            bloqueios = l["bloqueios"] if l else 0
            ate = 0.0
            if erros >= ERROS_ATE_BLOQUEAR:
                ate = self.relogio() + BLOQUEIO_S * (2 ** bloqueios)
                bloqueios += 1
                erros = 0
            c.execute("INSERT INTO tentativas (email, erros, bloqueios, bloqueado_ate) VALUES (?, ?, ?, ?)"
                      " ON CONFLICT(email) DO UPDATE SET erros = excluded.erros, bloqueios = excluded.bloqueios,"
                      " bloqueado_ate = CASE WHEN excluded.bloqueado_ate > 0 THEN excluded.bloqueado_ate"
                      " ELSE tentativas.bloqueado_ate END",
                      (email, erros, bloqueios, ate))
        if ate and self.ao_bloquear:
            conta = self._conta_por_email(email)
            try:
                self.ao_bloquear(email, conta["nome"] if conta else "", ate)
            except Exception:  # noqa: BLE001 - o aviso nao pode destravar a conta
                pass
        return ate

    def ip_bloqueado_ate(self, ip: str) -> float:
        if not ip:
            return 0.0
        with self._db() as c:
            l = c.execute("SELECT bloqueado_ate FROM tentativas_ip WHERE ip = ?", (ip,)).fetchone()
        return float(l["bloqueado_ate"]) if l else 0.0

    def _errou_ip(self, ip: str) -> float:
        """Conta a falha deste endereco; na 20a em 10 minutos, fecha por 1 hora."""
        if not ip:
            return 0.0
        agora = self.relogio()
        with self._trava, self._db() as c:
            l = c.execute("SELECT * FROM tentativas_ip WHERE ip = ?", (ip,)).fetchone()
            falhas = [t for t in json.loads(l["falhas"]) if agora - t <= IP_JANELA_S] if l else []
            falhas.append(agora)
            ate = 0.0
            if len(falhas) >= IP_FALHAS_ATE_BLOQUEAR:
                ate, falhas = agora + IP_BLOQUEIO_S, []
            c.execute("INSERT INTO tentativas_ip (ip, falhas, bloqueado_ate) VALUES (?, ?, ?)"
                      " ON CONFLICT(ip) DO UPDATE SET falhas = excluded.falhas,"
                      " bloqueado_ate = CASE WHEN excluded.bloqueado_ate > 0 THEN excluded.bloqueado_ate"
                      " ELSE tentativas_ip.bloqueado_ate END", (ip, json.dumps(falhas), ate))
        if ate and self.ao_bloquear:
            try:
                self.ao_bloquear("", "o endereço " + ip, ate)
            except Exception:  # noqa: BLE001 - o aviso nao pode destravar a porta
                pass
        return ate

    def _porta_do_ip(self, ip: str) -> None:
        ate = self.ip_bloqueado_ate(ip)
        if ate > self.relogio():
            raise ErroEntrada("muitas tentativas erradas deste endereço; tente de novo mais tarde", ate)

    def _acertou(self, email: str) -> None:
        with self._db() as c:
            c.execute("DELETE FROM tentativas WHERE email = ?", (email,))

    def _conta_por_email(self, email: str) -> sqlite3.Row | None:
        with self._db() as c:
            return c.execute("SELECT * FROM contas WHERE email = ?", (email,)).fetchone()

    def _recusar(self, email: str, mensagem: str, ip: str = "") -> None:
        ate_ip = self._errou_ip(ip)
        ate = self._errou(email)
        if ate_ip:
            raise ErroEntrada("muitas tentativas erradas deste endereço; tente de novo mais tarde", ate_ip)
        if ate:
            raise ErroEntrada("muitas tentativas erradas: a conta ficou bloqueada por "
                              f"{round((ate - self.relogio()) / 60)} min", ate)
        raise ErroEntrada(mensagem)

    # ----------------------------------------------------------- entrar

    def entrar_com_senha(self, email: str, senha: str, *, ip: str = "") -> str:
        """
        Primeira metade do login. Devolve um token de pendencia (5 min) que
        so vale para mandar o codigo do autenticador.

        "Conta que nao existe" e "senha errada" dao a mesma resposta, no mesmo
        tempo - o scrypt roda do mesmo jeito -, e contam para o bloqueio igual:
        a tela de entrar nao pode servir para descobrir quem tem conta.
        """
        self._porta_do_ip(ip)
        try:
            email = self._email(email)
        except ErroConta as exc:
            self._errou_ip(ip)
            raise ErroEntrada("e-mail ou senha errados") from exc
        ate = self._bloqueado_ate(email)
        if ate > self.relogio():
            raise ErroEntrada("conta bloqueada por tentativas erradas; tente de novo mais tarde", ate)
        linha = self._conta_por_email(email)
        sal = bytes.fromhex(linha["senha_sal"]) if linha else b"\0" * 16
        certo = resumo_da_senha(str(senha or ""), sal)
        if not linha or not hmac.compare_digest(certo, linha["senha_hash"]):
            self._recusar(email, "e-mail ou senha errados", ip)
        if not linha["totp_confirmado"]:
            raise ErroEntrada("esta conta ainda não confirmou o autenticador no computador do escritório")
        pendente = secrets.token_urlsafe(24)
        with self._trava:
            self._limpar_pendentes()
            self._pendentes[_resumo(pendente)] = (linha["id"], self.relogio() + PENDENTE_S, email, "")
        return pendente

    def _limpar_pendentes(self) -> None:
        agora = self.relogio()
        for k in [k for k, v in self._pendentes.items() if v[1] < agora]:
            self._pendentes.pop(k, None)

    def _conferir_codigo(self, linha, codigo: str) -> bool:
        """Codigo do autenticador (uma vez so) ou de recuperacao (uma vez so)."""
        segredo = self._segredo(linha)
        limpo = _limpo(codigo)
        if segredo and limpo.isdigit():
            passo = passo_que_confere(segredo, limpo, self.relogio())
            if passo is not None and passo > int(linha["totp_ultimo_passo"]):
                with self._db() as c:
                    c.execute("UPDATE contas SET totp_ultimo_passo = ? WHERE id = ?", (passo, linha["id"]))
                return True
            return False
        restantes = json.loads(linha["recuperacao"] or "[]")
        alvo = _resumo(limpo)
        achou = next((r for r in restantes if hmac.compare_digest(r, alvo)), None)
        if not achou:
            return False
        restantes.remove(achou)
        with self._db() as c:
            c.execute("UPDATE contas SET recuperacao = ? WHERE id = ?", (json.dumps(restantes), linha["id"]))
        return True

    def entrar_com_codigo(self, pendente: str, codigo: str, *, ip: str = "") -> dict:
        """Segunda metade: o codigo certo abre a sessao. Devolve cookie, csrf e a conta."""
        self._porta_do_ip(ip)
        with self._trava:
            self._limpar_pendentes()
            dado = self._pendentes.get(_resumo(str(pendente or "")))
        if not dado:
            raise ErroEntrada("a entrada expirou: digite a senha de novo")
        conta_id, _, email, _ = dado
        ate = self._bloqueado_ate(email)
        if ate > self.relogio():
            raise ErroEntrada("conta bloqueada por tentativas erradas; tente de novo mais tarde", ate)
        linha = self._linha(conta_id)
        if not linha or not self._conferir_codigo(linha, codigo):
            self._recusar(email, "código errado", ip)
        with self._trava:
            self._pendentes.pop(_resumo(str(pendente)), None)
        self._acertou(email)
        with self._db() as c:
            c.execute("UPDATE tentativas SET bloqueios = 0 WHERE email = ?", (email,))
        sessao, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        agora = self.relogio()
        with self._db() as c:
            c.execute("INSERT INTO sessoes (hash, conta_id, csrf, criada, ultimo_uso, totp_em, email_access, ip)"
                      " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (_resumo(sessao), conta_id, csrf, agora, agora, agora, "", ip))
        return {"sessao": sessao, "csrf": csrf, "conta": self._publica(linha)}

    # ---------------------------------------------------------- sessao

    def sessao(self, token: str | None, *, tocar: bool = True) -> dict | None:
        """
        A sessao viva deste cookie, com a conta, ou None. Vencida por
        inatividade ou por idade, sai do banco na hora.
        """
        if not token:
            return None
        h = _resumo(str(token))
        agora = self.relogio()
        with self._db() as c:
            l = c.execute("SELECT s.*, c.nome, c.email, c.papel FROM sessoes s JOIN contas c ON c.id = s.conta_id"
                          " WHERE s.hash = ?", (h,)).fetchone()
            if not l:
                return None
            if agora - l["ultimo_uso"] > SESSAO_OCIOSA_S or agora - l["criada"] > SESSAO_TOTAL_S:
                c.execute("DELETE FROM sessoes WHERE hash = ?", (h,))
                return None
            if tocar:
                c.execute("UPDATE sessoes SET ultimo_uso = ? WHERE hash = ?", (agora, h))
        return {"conta_id": l["conta_id"], "nome": l["nome"], "email": l["email"], "papel": l["papel"],
                "csrf": l["csrf"], "criada": l["criada"], "totp_em": l["totp_em"],
                "email_access": l["email_access"], "hash": h}

    @staticmethod
    def csrf_confere(sessao: dict, enviado: str | None) -> bool:
        return bool(enviado) and hmac.compare_digest(str(enviado), sessao["csrf"])

    def sair(self, token: str | None) -> None:
        if token:
            with self._db() as c:
                c.execute("DELETE FROM sessoes WHERE hash = ?", (_resumo(str(token)),))

    def encerrar_sessoes(self, conta_id: int | None = None) -> int:
        """Todas as sessoes (ou as de uma conta). Devolve quantas caíram."""
        with self._db() as c:
            if conta_id is None:
                return c.execute("DELETE FROM sessoes").rowcount
            return c.execute("DELETE FROM sessoes WHERE conta_id = ?", (conta_id,)).rowcount

    def sessoes_abertas(self) -> list[dict]:
        agora = self.relogio()
        with self._db() as c:
            linhas = c.execute("SELECT s.conta_id, s.criada, s.ultimo_uso, s.ip, c.nome, c.email FROM sessoes s"
                               " JOIN contas c ON c.id = s.conta_id ORDER BY s.ultimo_uso DESC").fetchall()
        return [dict(l) for l in linhas
                if agora - l["ultimo_uso"] <= SESSAO_OCIOSA_S and agora - l["criada"] <= SESSAO_TOTAL_S]

    def confirmar_de_novo(self, sessao: dict, codigo: str) -> bool:
        """
        O codigo do autenticador pedido de novo, no meio da sessao: aprovar de
        fora um item que manda algo para fora do escritorio (R3). Nao conta
        como erro de login - quem esta aqui ja entrou -, mas o codigo continua
        valendo uma vez so.
        """
        linha = self._linha(sessao["conta_id"])
        if not linha or not self._conferir_codigo(linha, codigo):
            return False
        with self._db() as c:
            c.execute("UPDATE sessoes SET totp_em = ? WHERE hash = ?", (self.relogio(), sessao["hash"]))
        return True
