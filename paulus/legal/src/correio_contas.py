"""
PAULUS - Contas de e-mail.

Guarda as contas do escritorio: endereco, servidor de entrada e de saida,
assinatura e o que o assistente pode fazer com cada uma. A senha nunca fica em
texto: vai para a DPAPI, como a do certificado.

IMAP e SMTP, nao OAuth. A razao e pratica, nao ideologica: OAuth para Gmail ou
Microsoft exige registrar um aplicativo, publicar politica de privacidade,
verificar dominio e passar por revisao de seguranca - semanas de espera e custo
antes da primeira linha funcionar. IMAP com senha de aplicativo funciona hoje,
de graca, e e o que a hospedagem de um escritorio brasileiro oferece.

O preco dessa escolha aparece na tela em vez de virar surpresa: contas da
Microsoft nao aceitam mais senha no IMAP, e a tela diz isso antes de a pessoa
tentar.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import segredos

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)

# Servidores conhecidos, para nao sondar a rede quando ja se sabe a resposta.
CONHECIDOS: dict[str, dict] = {
    "gmail.com": {
        "imap_host": "imap.gmail.com", "smtp_host": "smtp.gmail.com",
        "rotulo": "Gmail",
        "ajuda": (
            "O Gmail não aceita a sua senha normal aqui. Ligue a verificação em duas "
            "etapas na conta Google e gere uma Senha de app em "
            "myaccount.google.com/apppasswords — são 16 letras. Use ela no lugar da senha."
        ),
    },
    "googlemail.com": {"imap_host": "imap.gmail.com", "smtp_host": "smtp.gmail.com", "rotulo": "Gmail"},
    "outlook.com": {
        "imap_host": "outlook.office365.com", "smtp_host": "smtp.office365.com",
        "rotulo": "Microsoft", "bloqueado": True,
    },
    "hotmail.com": {
        "imap_host": "outlook.office365.com", "smtp_host": "smtp.office365.com",
        "rotulo": "Microsoft", "bloqueado": True,
    },
    "live.com": {
        "imap_host": "outlook.office365.com", "smtp_host": "smtp.office365.com",
        "rotulo": "Microsoft", "bloqueado": True,
    },
    "yahoo.com.br": {"imap_host": "imap.mail.yahoo.com", "smtp_host": "smtp.mail.yahoo.com", "rotulo": "Yahoo"},
    "yahoo.com": {"imap_host": "imap.mail.yahoo.com", "smtp_host": "smtp.mail.yahoo.com", "rotulo": "Yahoo"},
    "uol.com.br": {"imap_host": "imap.uol.com.br", "smtp_host": "smtps.uol.com.br", "rotulo": "UOL"},
    "bol.com.br": {"imap_host": "imap.bol.com.br", "smtp_host": "smtps.bol.com.br", "rotulo": "BOL"},
    "terra.com.br": {"imap_host": "imap.terra.com.br", "smtp_host": "smtp.terra.com.br", "rotulo": "Terra"},
    "zoho.com": {"imap_host": "imap.zoho.com", "smtp_host": "smtp.zoho.com", "rotulo": "Zoho"},
}

# Aviso especifico: a Microsoft desligou a entrada por senha nesses protocolos.
AVISO_MICROSOFT = (
    "A Microsoft desativou a entrada por senha no IMAP e no SMTP das contas Outlook, "
    "Hotmail e Microsoft 365 — elas exigem OAuth, que este programa ainda não faz. "
    "Se o seu escritório usa Microsoft 365, o caminho por enquanto é outra conta ou "
    "o e-mail do próprio domínio, pela hospedagem."
)

# Candidatos a sondar quando o dominio nao esta na tabela. E o que um cliente
# de e-mail faz: tenta os nomes de sempre antes de perguntar.
PADROES_IMAP = ("imap.{d}", "mail.{d}", "imaps.{d}", "email.{d}")
PADROES_SMTP = ("smtp.{d}", "mail.{d}", "smtps.{d}", "email.{d}")

PERMISSOES = [
    ("pode_rascunhar", "Escrever rascunhos para você revisar",
     "Eu preparo a resposta; você lê e decide. Nada sai sem você."),
    ("pode_anexar", "Anexar documentos da biblioteca",
     "Posso juntar ao e-mail um arquivo que já está no acervo."),
    ("pode_enviar_sem_confirmar", "Enviar sem confirmação",
     "Desligado, todo envio para na fila de aprovações. Ligue sabendo disso."),
]


@dataclass
class Conta:
    id: str = ""
    email: str = ""
    nome: str = ""                       # como aparece para quem recebe
    imap_host: str = ""
    imap_porta: int = 993
    imap_ssl: bool = True
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_tls: bool = True
    senha_protegida: str = ""
    guardar_senha: bool = True
    assinatura: str = ""
    pode_rascunhar: bool = True
    pode_anexar: bool = True
    pode_enviar_sem_confirmar: bool = False
    ultimo_ok: str = ""                  # quando a conexao funcionou pela ultima vez
    ultimo_erro: str = ""

    @property
    def iniciais(self) -> str:
        parte = self.email.split("@")[0]
        pedacos = [p for p in re.split(r"[._-]+", parte) if p]
        if len(pedacos) >= 2:
            return (pedacos[0][:1] + pedacos[1][:1]).upper()
        return parte[:2].upper()

    @property
    def dominio(self) -> str:
        return self.email.split("@")[-1].lower()

    @property
    def situacao(self) -> str:
        if self.ultimo_erro:
            return "com problema"
        if not self.senha_protegida:
            return "sem senha guardada"
        return "conectada"

    def to_dict(self, *, em_uso: bool = False) -> dict:
        dados = asdict(self)
        dados.pop("senha_protegida", None)      # nunca sai daqui, nem protegida
        dados.update(
            iniciais=self.iniciais,
            dominio=self.dominio,
            situacao=self.situacao,
            tem_senha=bool(self.senha_protegida),
            em_uso=em_uso,
            resumo_servidor=f"IMAP {self.imap_porta} · SMTP {self.smtp_porta}",
            quando_ok=_quando_relativo(self.ultimo_ok),
        )
        return dados


def _quando_relativo(iso: str) -> str:
    """"há 2 min", "há 1 h" - o wireframe fala assim, e a pessoa tambem."""
    if not iso:
        return ""
    try:
        quando = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    segundos = (datetime.now() - quando).total_seconds()
    if segundos < 90:
        return "agora há pouco"
    if segundos < 3600:
        return f"há {int(segundos // 60)} min"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    return f"há {int(segundos // 86400)} dia(s)"


# ------------------------------------------------------- achar o servidor


def detectar(email: str, *, sondar: bool = True, espera: float = 2.0) -> dict:
    """
    Descobre os servidores de um endereco.

    Primeiro a tabela do que ja se sabe. Dominio proprio - que e o caso da
    maioria dos escritorios - nao esta em tabela nenhuma, entao o programa
    tenta os nomes de sempre e ve quem atende. E o que um cliente de e-mail
    faz; a diferenca e dizer que esta fazendo.
    """
    dominio = (email or "").split("@")[-1].strip().lower()
    if not dominio:
        return {"achou": False, "motivo": "informe o endereço de e-mail primeiro"}

    conhecido = CONHECIDOS.get(dominio)
    if conhecido:
        return {
            "achou": True,
            "imap_host": conhecido["imap_host"],
            "imap_porta": 993,
            "smtp_host": conhecido["smtp_host"],
            "smtp_porta": 587,
            "como": f"servidor conhecido do {conhecido.get('rotulo', dominio)}",
            "ajuda": conhecido.get("ajuda", ""),
            "bloqueado": bool(conhecido.get("bloqueado")),
            "aviso": AVISO_MICROSOFT if conhecido.get("bloqueado") else "",
        }

    if not sondar:
        return {"achou": False, "motivo": "domínio próprio - preencha os servidores à mão"}

    imap, smtp = _sondar(dominio, espera)

    if not imap and not smtp:
        return {
            "achou": False,
            "motivo": (
                "não achei o servidor deste domínio. Quem hospeda o e-mail do "
                "escritório sabe informar: costuma ser algo como imap.seudominio.com.br"
            ),
        }

    return {
        "achou": True,
        "imap_host": imap or f"imap.{dominio}",
        "imap_porta": 993,
        "smtp_host": smtp or f"smtp.{dominio}",
        "smtp_porta": 587,
        "como": "encontrei sondando os nomes de servidor mais comuns deste domínio",
        "parcial": not (imap and smtp),
    }


def _sondar(dominio: str, espera: float) -> tuple[str, str]:
    """
    Tenta os oito candidatos de uma vez.

    Em serie isto levava dezesseis segundos: o tempo limite do socket vale para
    a conexao, e a resolucao de nome de um dominio que nao existe demora por
    fora dele. Dezesseis segundos depois de um clique a pessoa ja concluiu que
    o programa travou. Em paralelo, o custo passa a ser o do candidato mais
    lento, nao a soma de todos.

    A escolha continua sendo por prioridade, nao por quem respondeu primeiro:
    imap.dominio vale mais que mail.dominio mesmo que o segundo atenda antes.
    """
    from concurrent.futures import ThreadPoolExecutor

    tentativas = [("imap", p.format(d=dominio), 993) for p in PADROES_IMAP]
    tentativas += [("smtp", p.format(d=dominio), 587) for p in PADROES_SMTP]

    def atende(alvo: str, porta: int) -> bool:
        try:
            with socket.create_connection((alvo, porta), timeout=espera):
                return True
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=len(tentativas)) as pool:
        respostas = list(pool.map(lambda t: atende(t[1], t[2]), tentativas))

    achados = {"imap": "", "smtp": ""}
    for (papel, alvo, _), ok in zip(tentativas, respostas):
        if ok and not achados[papel]:
            achados[papel] = alvo
    return achados["imap"], achados["smtp"]


# ------------------------------------------------------------- o cadastro


class Contas:
    """
    As contas do escritorio, em disco.

    A ordem importa: o wireframe diz "ordem define quem envia por padrao", e a
    primeira da lista e a conta em uso.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._trava = threading.Lock()
        self.itens: list[Conta] = []
        # Senha digitada agora, guardada so na memoria do processo. Existe para
        # quem escolheu nao guardar a senha em disco nao ter que redigitar a
        # cada mensagem aberta.
        self._vivas: dict[str, str] = {}
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            return
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in bruto.get("contas", []):
            campos = {k: v for k, v in item.items() if k in Conta.__dataclass_fields__}
            try:
                self.itens.append(Conta(**campos))
            except TypeError:
                continue

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": 1, "contas": [asdict(c) for c in self.itens]}
        self.caminho.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    # ------------------------------------------------------------- acesso

    def obter(self, id_: str) -> Conta | None:
        return next((c for c in self.itens if c.id == id_), None)

    def por_email(self, email: str) -> Conta | None:
        alvo = (email or "").strip().lower()
        return next((c for c in self.itens if c.email.lower() == alvo), None)

    @property
    def em_uso(self) -> Conta | None:
        """A primeira da lista envia por padrao."""
        return self.itens[0] if self.itens else None

    def salvar_conta(self, dados: dict, senha: str = "") -> Conta:
        email = str(dados.get("email", "")).strip()
        if not RE_EMAIL.match(email):
            raise ValueError("esse endereço de e-mail não parece completo")

        conta = self.obter(str(dados.get("id", ""))) or self.por_email(email)
        novo = conta is None
        if novo:
            conta = Conta(id=uuid.uuid4().hex[:12])

        conta.email = email
        conta.nome = str(dados.get("nome", "")).strip() or conta.nome
        for campo in ("imap_host", "smtp_host", "assinatura"):
            if campo in dados:
                setattr(conta, campo, str(dados[campo]).strip())
        for campo in ("imap_porta", "smtp_porta"):
            if campo in dados:
                setattr(conta, campo, int(dados[campo] or 0) or getattr(conta, campo))
        for campo in ("imap_ssl", "smtp_tls", "guardar_senha",
                      "pode_rascunhar", "pode_anexar", "pode_enviar_sem_confirmar"):
            if campo in dados:
                setattr(conta, campo, bool(dados[campo]))

        if senha:
            if conta.guardar_senha:
                conta.senha_protegida = segredos.proteger(senha)
            conta.ultimo_erro = ""

        with self._trava:
            if novo:
                self.itens.append(conta)
        self.salvar()
        return conta

    def lembrar(self, id_: str, senha: str) -> None:
        self._vivas[id_] = senha

    def esquecer_viva(self, id_: str = "") -> None:
        if id_:
            self._vivas.pop(id_, None)
        else:
            self._vivas.clear()

    def senha(self, conta: Conta) -> str:
        """A senha em uso: a digitada agora, a guardada, ou nenhuma."""
        return self._vivas.get(conta.id) or segredos.revelar(conta.senha_protegida)

    def marcar_ok(self, conta: Conta) -> None:
        conta.ultimo_ok = datetime.now().isoformat(timespec="seconds")
        conta.ultimo_erro = ""
        self.salvar()

    def marcar_erro(self, conta: Conta, mensagem: str) -> None:
        conta.ultimo_erro = mensagem
        self.salvar()

    def usar(self, id_: str) -> bool:
        """Poe a conta no comeco da lista - e ela passa a enviar por padrao."""
        conta = self.obter(id_)
        if not conta:
            return False
        with self._trava:
            self.itens.remove(conta)
            self.itens.insert(0, conta)
        self.salvar()
        return True

    def apagar(self, id_: str) -> bool:
        conta = self.obter(id_)
        if not conta:
            return False
        with self._trava:
            self.itens.remove(conta)
        self._vivas.pop(id_, None)
        self.salvar()
        return True

    def esquecer_senhas(self) -> int:
        """Apaga toda senha guardada, mantendo as contas cadastradas."""
        quantas = 0
        for conta in self.itens:
            if conta.senha_protegida:
                conta.senha_protegida = ""
                quantas += 1
        self._vivas.clear()
        self.salvar()
        return quantas

    def para_tela(self) -> dict:
        atual = self.em_uso
        return {
            "contas": [c.to_dict(em_uso=(atual is not None and c.id == atual.id)) for c in self.itens],
            "em_uso": atual.id if atual else "",
            "permissoes": [
                {"chave": k, "titulo": t, "explica": e} for k, t, e in PERMISSOES
            ],
            "pode_guardar_senha": segredos.disponivel(),
            "aviso_microsoft": AVISO_MICROSOFT,
        }
