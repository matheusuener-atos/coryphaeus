"""
PAULUS - Contas de e-mail.

Guarda as contas do escritorio: endereco, servidor de entrada e de saida,
assinatura e o que o assistente pode fazer com cada uma. A senha nunca fica em
texto: vai para a DPAPI, como a do certificado.

Duas formas de entrar:

- senha (ou senha de app) no IMAP e no SMTP - o que a hospedagem de um
  escritorio brasileiro oferece, e o que funciona sem registro nenhum;
- login do Google ou da Microsoft (OAuth 2.0, src/correio_oauth.py), com
  client ID do aplicativo PAULUS (src/oauth_app.py). Guarda o
  refresh token na DPAPI; o access token fica so na memoria.

Contas Microsoft nao aceitam mais senha no IMAP. Sem o login da Microsoft
no programa, a tela diz isso antes de a pessoa tentar; com ele, oferece o
"Entrar com Microsoft".
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
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
# Sem o login da Microsoft no programa nao ha como entrar; com ele, o caminho e o login.
AVISO_MICROSOFT = (
    "A Microsoft desativou a entrada por senha no IMAP e no SMTP das contas Outlook, "
    "Hotmail e Microsoft 365 — elas só entram pelo login da Microsoft, que esta versão "
    "do PAULUS ainda não traz. Por enquanto, use outra conta."
)
AVISO_MICROSOFT_OAUTH = (
    "A Microsoft não aceita senha no IMAP e no SMTP das contas Outlook, Hotmail e "
    "Microsoft 365. Use \"Entrar com Microsoft\": o login acontece no navegador, na "
    "página da própria Microsoft."
)

# Qual login serve para cada dominio conhecido.
OAUTH_POR_DOMINIO = {
    "gmail.com": "google", "googlemail.com": "google",
    "outlook.com": "microsoft", "hotmail.com": "microsoft", "live.com": "microsoft",
}

# Servidores de cada login: o token so vale nos servidores do proprio provedor.
SERVIDORES_OAUTH = {
    "google": {"imap_host": "imap.gmail.com", "imap_porta": 993, "smtp_host": "smtp.gmail.com", "smtp_porta": 587},
    "microsoft": {"imap_host": "outlook.office365.com", "imap_porta": 993,
                  "smtp_host": "smtp.office365.com", "smtp_porta": 587},
}
ROTULO_AUTENTICACAO = {"senha": "senha", "google": "login Google", "microsoft": "login Microsoft"}

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
    # "senha" (IMAP/SMTP com senha ou senha de app), "google" ou "microsoft"
    # (login OAuth). Conta gravada antes disto existir continua "senha".
    autenticacao: str = "senha"
    refresh_protegido: str = ""          # refresh token do login, na DPAPI
    precisa_entrar: bool = False         # a autorizacao venceu ou foi revogada

    @property
    def por_login(self) -> bool:
        return self.autenticacao in SERVIDORES_OAUTH

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
        if self.por_login and self.precisa_entrar:
            return "precisa entrar de novo"
        if self.ultimo_erro:
            return "com problema"
        if self.por_login:
            return "conectada" if self.refresh_protegido else "precisa entrar de novo"
        if not self.senha_protegida:
            return "sem senha guardada"
        return "conectada"

    def to_dict(self, *, em_uso: bool = False, tem_credencial: bool | None = None) -> dict:
        dados = asdict(self)
        dados.pop("senha_protegida", None)      # nunca sai daqui, nem protegida
        dados.pop("refresh_protegido", None)
        if tem_credencial is None:
            tem_credencial = bool(self.refresh_protegido if self.por_login else self.senha_protegida)
        resumo = f"IMAP {self.imap_porta} · SMTP {self.smtp_porta}"
        if self.por_login:
            resumo += " · " + ROTULO_AUTENTICACAO[self.autenticacao]
        dados.update(
            iniciais=self.iniciais,
            dominio=self.dominio,
            situacao=self.situacao,
            # Para a conta de login, "tem senha" quer dizer "tem autorizacao
            # valida": e o que a tela usa para oferecer Reconectar.
            tem_senha=bool(tem_credencial) and not (self.por_login and self.precisa_entrar),
            por_login=self.por_login,
            rotulo_autenticacao=ROTULO_AUTENTICACAO.get(self.autenticacao, "senha"),
            em_uso=em_uso,
            resumo_servidor=resumo,
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


def detectar(email: str, *, sondar: bool = True, espera: float = 2.0,
             oauth: dict | None = None) -> dict:
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
        # `oauth` diz quais logins tem client ID cadastrado: {"google": True, ...}.
        provedor = OAUTH_POR_DOMINIO.get(dominio, "")
        com_login = bool(provedor and (oauth or {}).get(provedor))
        sem_senha = bool(conhecido.get("bloqueado"))
        aviso = ""
        if sem_senha:
            aviso = AVISO_MICROSOFT_OAUTH if com_login else AVISO_MICROSOFT
        return {
            "achou": True,
            "imap_host": conhecido["imap_host"],
            "imap_porta": 993,
            "smtp_host": conhecido["smtp_host"],
            "smtp_porta": 587,
            "como": f"servidor conhecido do {conhecido.get('rotulo', dominio)}",
            "ajuda": conhecido.get("ajuda", ""),
            # Bloqueado so quando nao ha como entrar: senha nao serve e o
            # login do provedor nao esta cadastrado.
            "bloqueado": sem_senha and not com_login,
            "senha_nao_serve": sem_senha,
            "oauth": provedor,
            "oauth_disponivel": com_login,
            "aviso": aviso,
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
        # Login OAuth: access token so em memoria, {id: (token, expira_em)};
        # refresh token em memoria quando a DPAPI nao esta disponivel.
        self._tokens: dict[str, tuple[str, float]] = {}
        self._refresh_vivos: dict[str, str] = {}
        self._trava_token = threading.Lock()
        # Quem sabe os client IDs e o api.py (src/oauth_app.py); aqui so se pede.
        # credenciais_oauth(provedor) -> {"client_id": ..., "client_secret": ...}
        self.credenciais_oauth = lambda provedor: {}
        # Endpoints trocados nos testes, para nunca bater no servidor real.
        self.endpoints_oauth: dict[str, dict] = {}
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
                conta = Conta(**campos)
            except TypeError:
                continue
            if conta.autenticacao not in ROTULO_AUTENTICACAO:
                conta.autenticacao = "senha"
            self.itens.append(conta)

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
            if conta.por_login:
                # Quem digita uma senha de app numa conta que entrava pelo
                # login escolheu voltar para a senha: o login sai de cena.
                conta.autenticacao = "senha"
                conta.refresh_protegido = ""
                conta.precisa_entrar = False
                self._tokens.pop(conta.id, None)
                self._refresh_vivos.pop(conta.id, None)
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
        if conta.por_login:
            return ""
        return self._vivas.get(conta.id) or segredos.revelar(conta.senha_protegida)

    # ------------------------------------------------------ login OAuth

    def ligar_oauth(self, provedor: str, email: str, nome: str, tokens: dict) -> Conta:
        """
        Guarda a conta que acabou de entrar pelo login do provedor.

        Se o endereco ja existia (com senha, ou com login vencido), a mesma
        conta passa a entrar pelo login: assinatura, permissoes e posicao na
        lista ficam como estavam. A senha antiga, se havia, e apagada - nao
        serve para mais nada e so seria um segredo a mais no disco.
        """
        if provedor not in SERVIDORES_OAUTH:
            raise ValueError("provedor desconhecido")
        if not RE_EMAIL.match(email or ""):
            raise ValueError("o login não devolveu um endereço de e-mail válido")
        refresh = str(tokens.get("refresh_token") or "")
        if not refresh:
            raise ValueError("o login não devolveu a autorização duradoura")

        conta = self.por_email(email)
        novo = conta is None
        if novo:
            conta = Conta(id=uuid.uuid4().hex[:12], email=email)
        conta.nome = conta.nome or nome
        for campo, valor in SERVIDORES_OAUTH[provedor].items():
            setattr(conta, campo, valor)
        conta.imap_ssl = True
        conta.smtp_tls = True
        conta.autenticacao = provedor
        conta.senha_protegida = ""
        conta.precisa_entrar = False
        conta.ultimo_erro = ""
        self._vivas.pop(conta.id, None)
        self._guardar_refresh(conta, refresh)
        self._tokens[conta.id] = (str(tokens["access_token"]), float(tokens.get("expira_em") or 0))

        with self._trava:
            if novo:
                self.itens.append(conta)
        self.salvar()
        return conta

    def _guardar_refresh(self, conta: Conta, refresh: str) -> None:
        protegido = segredos.proteger(refresh)
        conta.refresh_protegido = protegido
        # Sem DPAPI, o refresh token fica so na memoria: melhor entrar de novo
        # depois de fechar o programa do que deixar a chave legivel no disco.
        if protegido:
            self._refresh_vivos.pop(conta.id, None)
        else:
            self._refresh_vivos[conta.id] = refresh

    def _refresh(self, conta: Conta) -> str:
        return self._refresh_vivos.get(conta.id) or segredos.revelar(conta.refresh_protegido)

    def tem_credencial(self, conta: Conta) -> bool:
        """Se da para falar com o servidor sem perguntar nada - sem ir a rede."""
        if conta.por_login:
            return bool(self._refresh(conta)) and not conta.precisa_entrar
        return bool(self.senha(conta))

    def credencial(self, conta: Conta) -> str:
        """
        O que o IMAP e o SMTP recebem: a senha, ou o access token do login.

        O token e renovado aqui, antes de vencer. Se a renovacao for recusada
        (autorizacao revogada, ou os 7 dias do modo Teste do Google), a conta
        fica marcada "precisa entrar de novo" e levanta ErroOAuth. Queda de
        rede nao marca nada: levanta o erro e tenta de novo na proxima vez.
        """
        if not conta.por_login:
            return self.senha(conta)

        import correio_oauth

        with self._trava_token:
            token, expira = self._tokens.get(conta.id, ("", 0.0))
            if token and expira - time.time() > correio_oauth.MARGEM_RENOVAR:
                return token

            refresh = self._refresh(conta)
            if not refresh or conta.precisa_entrar:
                self._marcar_para_entrar(conta)
                raise correio_oauth.ErroOAuth(
                    f"é preciso entrar de novo com {correio_oauth.rotulo(conta.autenticacao)} em {conta.email}",
                    precisa_entrar=True,
                )
            credenciais = self.credenciais_oauth(conta.autenticacao) or {}
            if not credenciais.get("client_id"):
                raise correio_oauth.ErroOAuth(
                    f"esta versão do PAULUS não traz o login do {correio_oauth.rotulo(conta.autenticacao)}"
                )
            try:
                tokens = correio_oauth.renovar(
                    conta.autenticacao, credenciais, refresh,
                    endpoint=self.endpoints_oauth.get(conta.autenticacao, {}).get("token", ""),
                )
            except correio_oauth.ErroOAuth as exc:
                if exc.precisa_entrar:
                    self._marcar_para_entrar(conta)
                raise

            self._tokens[conta.id] = (str(tokens["access_token"]), float(tokens["expira_em"]))
            # A Microsoft troca o refresh token a cada renovacao; o Google, nao.
            novo_refresh = str(tokens.get("refresh_token") or "")
            if novo_refresh and novo_refresh != refresh:
                self._guardar_refresh(conta, novo_refresh)
                self.salvar()
            return tokens["access_token"]

    def _marcar_para_entrar(self, conta: Conta) -> None:
        import correio_oauth

        self._tokens.pop(conta.id, None)
        conta.precisa_entrar = True
        conta.ultimo_erro = (
            f"a autorização do {correio_oauth.rotulo(conta.autenticacao)} venceu ou foi revogada "
            "- entre de novo"
        )
        self.salvar()

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
        self._tokens.pop(id_, None)
        self._refresh_vivos.pop(id_, None)
        self.salvar()
        return True

    def esquecer_senhas(self) -> int:
        """
        Apaga toda senha guardada, mantendo as contas cadastradas.

        Vale tambem para o login: o refresh token e a chave da conta tanto
        quanto a senha. A conta de login fica "precisa entrar de novo".
        """
        quantas = 0
        for conta in self.itens:
            if conta.senha_protegida:
                conta.senha_protegida = ""
                quantas += 1
            if conta.refresh_protegido or conta.id in self._refresh_vivos:
                conta.refresh_protegido = ""
                conta.precisa_entrar = True
                quantas += 1
        self._vivas.clear()
        self._tokens.clear()
        self._refresh_vivos.clear()
        self.salvar()
        return quantas

    def para_tela(self) -> dict:
        atual = self.em_uso
        return {
            "contas": [
                c.to_dict(em_uso=(atual is not None and c.id == atual.id),
                          tem_credencial=self.tem_credencial(c) if c.por_login else None)
                for c in self.itens
            ],
            "em_uso": atual.id if atual else "",
            "permissoes": [
                {"chave": k, "titulo": t, "explica": e} for k, t, e in PERMISSOES
            ],
            "pode_guardar_senha": segredos.disponivel(),
            "aviso_microsoft": AVISO_MICROSOFT,
        }
