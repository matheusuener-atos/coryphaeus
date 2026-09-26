"""
Testes do e-mail.

O que quebra num cliente de e-mail nao e o caminho feliz: e o assunto em
ISO-8859-1 que o servidor brasileiro manda, o travessao do Outlook que vira
caractere invisivel, o HTML sem versao em texto, a senha recusada. E, do lado
que importa mais, e-mail saindo sem ninguem ter mandado sair.

Entao os testes cobrem:

  - cabecalho e corpo com acento, em varias codificacoes
  - prazo detectado por regra, sem confundir data qualquer com prazo
  - senha guardada nunca em texto
  - envio sem permissao NAO envia - vai para a fila
  - o rascunho da IA nao carrega assinatura inventada

IMAP e SMTP sao trocados por dubles: assim o caminho inteiro roda sem
credencial de verdade e sem tocar a rede.

    python tests/test_correio.py
"""

from __future__ import annotations

import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import correio  # noqa: E402
import correio_contas  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


# ----------------------------------------------------------- ler mensagem


def test_cabecalho_com_acento() -> None:
    """
    Assunto em portugues chega codificado, e quase nunca em UTF-8.

    O `=97` no meio e o caso real: o Outlook manda travessao em cp1252 mas
    declara iso-8859-1, onde esse byte e caractere de controle. Sem correcao,
    o assunto chega com um caractere invisivel no meio.
    """
    print("\ncabecalho e corpo com acento")
    bruto = (
        b"From: =?iso-8859-1?Q?Priscila_Almeida?= <priscila@coobramex.com.br>\r\n"
        b"To: matheus@escritorio.adv.br\r\n"
        b"Subject: =?iso-8859-1?Q?Re:_procura=E7=E3o_=97_falta_a_via?=\r\n"
        b"Date: Mon, 08 Sep 2026 09:12:33 -0300\r\n"
        b"Content-Type: text/plain; charset=iso-8859-1\r\n\r\n"
        b"Bom dia \x97 \x93tudo certo\x94? Preciso protocolar at\xe9 12/12/2099.\r\n"
    )
    m = correio.montar_mensagem(bruto, uid="1")

    checar("procuração" in m.assunto, f"decodifica acento no assunto ({m.assunto!r})")
    checar("—" in m.assunto, "travessao do Outlook vira travessao, nao caractere invisivel")
    checar("até" in m.corpo, "decodifica acento no corpo")
    checar("“tudo certo”" in m.corpo, "aspas curvas do Outlook chegam legiveis")
    checar(
        not any("\x80" <= c <= "\x9f" for c in m.assunto + m.corpo),
        "nenhum caractere de controle sobra no texto",
    )
    checar(m.de_nome == "Priscila Almeida", f"le o nome do remetente ({m.de_nome!r})")
    checar(m.de_email == "priscila@coobramex.com.br", "le o endereco do remetente")

    # Assunto em UTF-8 base64, o outro formato comum.
    utf8 = (
        b"From: a@b.com\r\n"
        b"Subject: =?utf-8?B?QXVkacOqbmNpYSBtYXJjYWRh?=\r\n"
        b"Date: Mon, 08 Sep 2026 09:12:33 -0300\r\n\r\ncorpo\r\n"
    )
    checar(correio.montar_mensagem(utf8).assunto == "Audiência marcada",
           "decodifica assunto em UTF-8 base64")

    # Sem assunto nenhum nao pode virar linha vazia na lista.
    vazio = correio.montar_mensagem(b"From: a@b.com\r\nDate: Mon, 08 Sep 2026 09:00:00 -0300\r\n\r\n")
    checar(vazio.assunto == "(sem assunto)", "mensagem sem assunto ganha rotulo")


def test_anexos_e_html() -> None:
    print("\nanexos e mensagem so em HTML")
    msg = EmailMessage()
    msg["From"] = "Cartório <cartorio@exemplo.com.br>"
    msg["Subject"] = "Protocolo 4471"
    msg["Date"] = "Tue, 09 Sep 2026 14:00:00 -0300"
    msg.set_content("Segue em anexo.")
    msg.add_attachment(b"%PDF-1.4 x" * 100, maintype="application", subtype="pdf",
                       filename="protocolo_4471.pdf")

    m = correio.montar_mensagem(msg.as_bytes(), uid="2")
    checar(m.tem_anexo, "percebe que tem anexo")
    checar(len(m.anexos) == 1, f"conta 1 anexo (achou {len(m.anexos)})")
    checar(m.anexos[0]["nome"] == "protocolo_4471.pdf", "le o nome do anexo")
    checar(m.anexos[0]["bytes"] > 0, "sabe o tamanho do anexo")
    checar("Segue em anexo" in m.corpo, "o corpo continua legivel com anexo junto")

    html = EmailMessage()
    html["From"] = "a@b.com"
    html["Subject"] = "Proposta"
    html["Date"] = "Wed, 10 Sep 2026 08:00:00 -0300"
    html.set_content(
        "<html><body><p>Bom dia.</p><p>Renova&ccedil;&atilde;o com <b>8%</b>.</p>"
        "<script>roubar()</script><style>p{color:red}</style></body></html>",
        subtype="html",
    )
    m2 = correio.montar_mensagem(html.as_bytes(), uid="3")
    checar("Renovação com 8%" in m2.corpo, f"converte HTML em texto legivel ({m2.corpo!r})")
    checar("roubar" not in m2.corpo, "script do HTML nao vai para a tela")
    checar("color:red" not in m2.corpo, "estilo do HTML nao vira texto")


def test_prazo() -> None:
    """
    Data nao e prazo. O erro anterior do projeto foi sugerir conferir um
    vencimento de 2021 - passado nao e prazo, e historico.
    """
    print("\nprazo detectado por regra")
    achar = lambda t: correio.detectar_prazo(t)[0]

    checar(achar("Preciso protocolar até 12/12/2099.") == "2099-12-12", "acha prazo com data futura")
    checar(achar("O prazo vence em 20/11/2099") == "2099-11-20", "acha prazo escrito de outro jeito")
    checar(achar("Audiência marcada para 20/11/2099") == "2099-11-20", "audiencia conta como prazo")
    checar(achar("Reunião dia 20/11/2099 para conversar") == "", "data sozinha NAO e prazo")
    checar(achar("O prazo venceu em 10/01/2020") == "", "prazo que ja passou NAO e prazo")
    checar(achar("Bom dia, tudo bem?") == "", "texto sem data nao inventa prazo")
    checar(achar("") == "", "texto vazio nao quebra")

    _, trecho = correio.detectar_prazo("Bom dia. Preciso protocolar até 12/12/2099. Obrigada.")
    checar("protocolar" in trecho, f"devolve a frase onde o prazo apareceu ({trecho!r})")


class _IMAPFalso:
    """
    Duble do imaplib com resposta no formato que o servidor devolve mesmo.

    O formato importa: a marca vem como bytes com "UID 101 FLAGS (...)" e o
    corpo vem numa tupla ao lado. Errar essa leitura faz a caixa aparecer
    vazia sem erro nenhum - que e o pior tipo de falha.
    """

    logins: list[tuple] = []
    falhar_login = False

    def __init__(self, host, porta, timeout=None):
        self.host, self.porta = host, porta

    def login(self, usuario, senha):
        if _IMAPFalso.falhar_login:
            raise Exception("AUTHENTICATIONFAILED invalid credentials")
        _IMAPFalso.logins.append((usuario, senha))
        return ("OK", [b""])

    def select(self, pasta, readonly=False):
        return ("OK", [b"3"])

    def uid(self, comando, *args):
        if comando == "SEARCH":
            return ("OK", [b"101 102 103"])
        if comando == "FETCH":
            return ("OK", self._fetch(args[0]))
        return ("OK", [b""])

    def _fetch(self, conjunto):
        respostas = []
        for uid in conjunto.split(","):
            corpo = _CABECALHOS.get(uid)
            if corpo is None:
                continue
            marca = (
                f"1 (UID {uid} FLAGS ({_FLAGS[uid]}) "
                f"BODYSTRUCTURE ({_ESTRUTURA[uid]}) "
                'BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)] {%d}' % len(corpo)
            )
            respostas.append((marca.encode(), corpo))
            respostas.append(b")")
        return respostas

    def logout(self):
        pass


_CABECALHOS = {
    "101": (
        b"From: =?iso-8859-1?Q?Priscila_Almeida?= <priscila@coobramex.com.br>\r\n"
        b"Subject: Re: procura=?iso-8859-1?Q?=E7=E3o?=\r\n"
        b"Date: Mon, 08 Sep 2026 09:12:33 -0300\r\n\r\n"
    ),
    "102": (
        b"From: Fornecedor A <compras@fornecedor.com.br>\r\n"
        b"Subject: Prazo para renovar ate 30/12/2099\r\n"
        b"Date: Tue, 09 Sep 2026 10:00:00 -0300\r\n\r\n"
    ),
    "103": (
        b"From: Cartorio <cartorio@exemplo.com.br>\r\n"
        b"Subject: Protocolo pronto\r\n"
        b"Date: Wed, 10 Sep 2026 11:00:00 -0300\r\n\r\n"
    ),
}
_FLAGS = {"101": "", "102": "\\Seen \\Answered", "103": "\\Seen"}
_ESTRUTURA = {
    "101": '"text" "plain" NIL',
    "102": '"text" "plain" NIL',
    "103": '("text" "plain" NIL)("application" "pdf" ("name" "p.pdf") NIL NIL "base64" 240 NIL ("attachment" ("filename" "p.pdf")))',
}


def test_listar_caixa() -> None:
    print("\nleitura da caixa pelo IMAP")
    conta = correio_contas.Conta(
        id="c1", email="matheus@escritorio.adv.br",
        imap_host="imap.escritorio.adv.br", imap_porta=993,
    )
    original = correio.imaplib.IMAP4_SSL
    correio.imaplib.IMAP4_SSL = _IMAPFalso
    _IMAPFalso.logins = []
    _IMAPFalso.falhar_login = False
    try:
        clientes = {"priscila@coobramex.com.br": "Priscila Almeida (COOBRAMEX)"}
        d = correio.listar(conta, "senha", clientes=clientes)

        checar(d["total"] == 3, f"conta o total da caixa (achou {d['total']})")
        checar(len(d["mensagens"]) == 3, "traz as tres mensagens")

        # Mais novas primeiro.
        assuntos = [m["assunto"] for m in d["mensagens"]]
        checar(assuntos[0].startswith("Protocolo"),
               f"a mais nova vem primeiro (achou {assuntos[0]!r})")

        por_uid = {m["uid"]: m for m in d["mensagens"]}
        checar(por_uid["101"]["lido"] is False, "sabe o que nao foi lido")
        checar(por_uid["102"]["lido"] is True, "sabe o que ja foi lido")
        checar(por_uid["102"]["respondido"] is True, "sabe o que ja foi respondido")
        checar(por_uid["103"]["tem_anexo"] is True,
               "descobre o anexo pela estrutura, sem baixar o anexo")
        checar(por_uid["101"]["tem_anexo"] is False, "e nao inventa anexo onde nao tem")
        checar("procuração" in por_uid["101"]["assunto"],
               f"decodifica o assunto na listagem ({por_uid['101']['assunto']!r})")
        checar(por_uid["102"]["prazo"] == "2099-12-30",
               f"acha prazo no assunto, sem abrir a mensagem ({por_uid['102']['prazo']!r})")
        checar(por_uid["101"]["de_cadastro"].startswith("Priscila"),
               "marca quem ja e cliente cadastrado")
        checar(por_uid["103"]["de_cadastro"] == "", "e nao marca quem nao e")
        checar(all(not m["corpo"] for m in d["mensagens"]),
               "NENHUM corpo foi baixado - a listagem le so cabecalho")
        checar(d["nao_lidos"] == 1, f"conta os nao lidos (achou {d['nao_lidos']})")

        # Filtro que depende da estrutura, nao do servidor.
        so_anexo = correio.listar(conta, "senha", filtro="com_anexo")
        checar(len(so_anexo["mensagens"]) == 1, "filtro de anexo funciona")

        so_clientes = correio.listar(conta, "senha", filtro="de_clientes", clientes=clientes)
        checar(len(so_clientes["mensagens"]) == 1, "filtro de clientes funciona")

        # Senha recusada vira erro em portugues.
        _IMAPFalso.falhar_login = True
        try:
            correio.listar(conta, "errada")
            checar(False, "senha recusada vira erro tratado")
        except correio.ErroCorreio as exc:
            checar("senha" in str(exc).lower(), f"senha recusada vira erro em portugues ({exc})")
    finally:
        correio.imaplib.IMAP4_SSL = original
        _IMAPFalso.falhar_login = False



def test_enderecos() -> None:
    print("\nleitura de destinatarios")
    lidos = correio.enderecos("Fulano <a@b.com>, c@d.com.br; lixo, C@D.COM.BR")
    checar(lidos == ["a@b.com", "c@d.com.br"],
           f"le, normaliza e nao repete (achou {lidos})")
    checar(correio.enderecos("") == [], "campo vazio devolve lista vazia")
    checar(correio.enderecos("sem arroba") == [], "texto sem arroba nao vira endereco")


# ---------------------------------------------------------------- contas


def test_detectar_servidor() -> None:
    print("\ndeteccao de servidor")
    g = correio_contas.detectar("alguem@gmail.com", sondar=False)
    checar(g["achou"] and g["imap_host"] == "imap.gmail.com", "reconhece o Gmail")
    checar("Senha de app" in g.get("ajuda", ""), "explica que o Gmail exige senha de app")

    m = correio_contas.detectar("alguem@outlook.com", sondar=False)
    checar(m.get("bloqueado") is True, "marca conta Microsoft como bloqueada")
    checar("login da Microsoft" in m.get("aviso", "") and "use outra conta" in m.get("aviso", ""),
           "e avisa por que, antes de a pessoa tentar e falhar (e o que fazer por enquanto)")

    proprio = correio_contas.detectar("adv@escritorio-que-nao-existe-xyz.com.br", sondar=False)
    checar(not proprio["achou"], "dominio proprio sem sondar nao inventa servidor")
    checar("mão" in proprio["motivo"], "e diz o que fazer")

    checar(not correio_contas.detectar("", sondar=False)["achou"], "endereco vazio nao quebra")


def test_guardar_conta(tmp: Path) -> None:
    print("\ncadastro de contas")
    import segredos

    contas = correio_contas.Contas(tmp / "contas.json")
    senha = "senha-secreta-do-email"

    conta = contas.salvar_conta({
        "email": "matheus@escritorio.adv.br",
        "nome": "Matheus S. Uener",
        "imap_host": "imap.escritorio.adv.br",
        "smtp_host": "smtp.escritorio.adv.br",
        "guardar_senha": True,
    }, senha)

    checar(conta.id != "", "conta ganha identificador")
    checar(conta.iniciais == "MA", f"monta as iniciais para a tela ({conta.iniciais})")
    checar(conta.dominio == "escritorio.adv.br", "sabe o dominio")

    bruto = (tmp / "contas.json").read_text(encoding="utf-8")
    if segredos.disponivel():
        checar(senha not in bruto, "a senha NAO fica em texto no arquivo")
        checar(contas.senha(conta) == senha, "e volta a ser lida quando precisa")
    else:
        checar(senha not in bruto, "sem DPAPI, a senha nao e gravada de jeito nenhum")

    tela = contas.para_tela()
    checar("senha_protegida" not in str(tela), "a senha nunca sai para a tela, nem protegida")
    checar(tela["contas"][0]["em_uso"], "a primeira conta e a que envia por padrao")

    # Segunda conta, e a troca de quem envia.
    contas.salvar_conta({"email": "financeiro@escritorio.adv.br"}, "outra")
    checar(len(contas.itens) == 2, "guarda duas contas")
    checar(contas.em_uso.email == "matheus@escritorio.adv.br", "a ordem manda em quem envia")
    contas.usar(contas.itens[1].id)
    checar(contas.em_uso.email == "financeiro@escritorio.adv.br", "trocar a conta em uso funciona")

    # Endereco invalido nao entra.
    try:
        contas.salvar_conta({"email": "isso nao e email"}, "x")
        checar(False, "recusa endereco invalido")
    except ValueError:
        checar(True, "recusa endereco invalido")

    quantas = contas.esquecer_senhas()
    checar(quantas >= 1, f"apaga as senhas guardadas (apagou {quantas})")
    checar(contas.senha(contas.itens[0]) == "", "e depois disso nao tem senha nenhuma")

    de_novo = correio_contas.Contas(tmp / "contas.json")
    checar(len(de_novo.itens) == 2, "as contas sobrevivem a fechar o programa")


# ---------------------------------------------------------------- enviar


class _SMTPFalso:
    """Duble do smtplib: registra o que teria sido enviado, sem rede."""

    enviados: list[dict] = []
    falhar_login = False

    def __init__(self, host, porta, timeout=None):
        self.host, self.porta = host, porta

    def starttls(self):
        pass

    def login(self, usuario, senha):
        if _SMTPFalso.falhar_login:
            raise Exception("authentication failed")
        self.usuario = usuario

    def send_message(self, msg, from_addr=None, to_addrs=None):
        _SMTPFalso.enviados.append({
            "de": from_addr, "para": to_addrs,
            "assunto": str(msg.get("Subject", "")),
            "corpo": msg.get_body(preferencelist=("plain",)).get_content(),
            "anexos": [p.get_filename() for p in msg.iter_attachments()],
        })

    def quit(self):
        pass


def test_montar_e_enviar(tmp: Path) -> None:
    print("\nmontar e enviar")
    conta = correio_contas.Conta(
        id="c1", email="matheus@escritorio.adv.br", nome="Matheus S. Uener",
        smtp_host="smtp.escritorio.adv.br", smtp_porta=587,
        assinatura="Matheus S. Uener\nOAB/GO 00000",
    )

    anexo = tmp / "procuracao.pdf"
    anexo.write_bytes(b"%PDF-1.4 conteudo de teste")

    msg = correio.montar_email(
        conta, para=["priscila@coobramex.com.br"], cc=["socio@escritorio.adv.br"],
        assunto="Procuração assinada", corpo="Boa tarde, Priscila.\n\nSegue em anexo.",
        anexos=[anexo],
    )
    corpo = msg.get_body(preferencelist=("plain",)).get_content()

    checar("Matheus S. Uener" in str(msg["From"]), "poe o nome de quem envia")
    checar("OAB/GO 00000" in corpo, "acrescenta a assinatura da conta")
    checar(corpo.index("Segue em anexo") < corpo.index("OAB/GO"),
           "a assinatura vem depois do texto, nao no meio")
    checar([p.get_filename() for p in msg.iter_attachments()] == ["procuracao.pdf"],
           "anexa o arquivo pedido")

    # Anexo que nao existe tem que reclamar antes de enviar.
    try:
        correio.montar_email(conta, para=["a@b.com"], assunto="x", corpo="y",
                             anexos=[tmp / "nao-existe.pdf"])
        checar(False, "recusa anexo que nao existe")
    except correio.ErroCorreio as exc:
        checar("não achei" in str(exc), "recusa anexo que nao existe, dizendo qual")

    # O envio em si, com o duble no lugar do smtplib.
    _SMTPFalso.enviados = []
    _SMTPFalso.falhar_login = False
    original = correio.smtplib.SMTP
    correio.smtplib.SMTP = _SMTPFalso
    try:
        resultado = correio.enviar(conta, "senha", msg, cco=["oculto@exemplo.com"])
        checar(len(_SMTPFalso.enviados) == 1, "entrega a mensagem ao servidor")
        entregue = _SMTPFalso.enviados[0]
        checar("priscila@coobramex.com.br" in entregue["para"], "manda para o destinatario")
        checar("socio@escritorio.adv.br" in entregue["para"], "inclui quem esta em copia")
        checar("oculto@exemplo.com" in entregue["para"], "inclui a copia oculta na entrega")
        checar("Cco" not in str(msg) and "Bcc" not in str(msg),
               "mas a copia oculta NAO aparece no cabecalho da mensagem")
        checar(resultado["assunto"] == "Procuração assinada", "devolve o que foi enviado")

        # Login recusado tem que virar erro em portugues, nao traceback.
        _SMTPFalso.falhar_login = True
        try:
            correio.enviar(conta, "errada", msg)
            checar(False, "senha recusada vira erro tratado")
        except correio.ErroCorreio as exc:
            checar("senha" in str(exc).lower(), f"senha recusada vira erro em portugues ({exc})")
    finally:
        correio.smtplib.SMTP = original
        _SMTPFalso.falhar_login = False


def test_sem_destinatario() -> None:
    print("\nmensagem sem destinatario")
    conta = correio_contas.Conta(id="c1", email="a@b.com", smtp_host="smtp.b.com")
    msg = correio.montar_email(conta, para=["c@d.com"], assunto="x", corpo="y")
    del msg["To"]
    try:
        correio.enviar(conta, "s", msg)
        checar(False, "recusa enviar sem destinatario")
    except correio.ErroCorreio as exc:
        checar("destinatário" in str(exc), "recusa enviar sem destinatario")


def test_rascunho_limpo() -> None:
    """
    Assinatura inventada por modelo pequeno num e-mail de escritorio e nome
    errado saindo com OAB errada. Some aqui; a de verdade e a da conta.
    """
    print("\nlimpeza do rascunho da IA")
    sujo = (
        "Assunto: Re: procuração\n\n"
        "Boa tarde, Priscila.\n"
        "**Vou verificar** e envio ainda hoje.\n\n"
        "--\nDr. João Inventado\nOAB/SP 123456\n"
    )
    limpo = correio._limpar_rascunho(sujo)
    checar(not limpo.startswith("Assunto"), "tira a linha de assunto que o modelo insiste em pôr")
    checar("OAB/SP 123456" not in limpo, "tira a assinatura inventada")
    checar("João Inventado" not in limpo, "e o nome inventado junto")
    checar("**" not in limpo, "tira marcacao que nao existe em e-mail")
    checar("Vou verificar" in limpo, "e mantem o texto")
    checar(correio._limpar_rascunho("") == "", "rascunho vazio nao quebra")
    eco = correio._limpar_rascunho("Prezado,\nSegue.\n\nPedido: Reescreva o e-mail em tom mais formal")
    checar(eco == "Prezado,\nSegue.", "corta o pedido que o modelo repete no fim", eco)


# ------------------------------------------------------ a fila decide


def test_sem_permissao_nao_envia(tmp: Path) -> None:
    """
    A regra da casa. E-mail que sai nao volta, entao sem a permissao ligada -
    e ela vem desligada, no programa e na conta - chamar a rota nao pode
    entregar mensagem nenhuma ao servidor.
    """
    print("\nsem permissao, nada e enviado")
    import api

    guardadas = (api.estado.contas, api.estado.envios)
    original = correio.smtplib.SMTP
    _SMTPFalso.enviados = []
    correio.smtplib.SMTP = _SMTPFalso
    try:
        api.estado.contas = correio_contas.Contas(tmp / "contas-api.json")
        api.estado.envios = correio.RegistroEnvios(tmp / "envios-api.json")
        conta = api.estado.contas.salvar_conta({
            "email": "matheus@escritorio.adv.br",
            "imap_host": "imap.x", "smtp_host": "smtp.x",
        }, "senha")
        api.estado.contas.lembrar(conta.id, "senha")

        checar(not api.estado.prefs.pode("enviar_mensagem"),
               "a permissao de enviar sozinho vem desligada")
        checar(not conta.pode_enviar_sem_confirmar,
               "e a conta tambem nasce sem essa permissao")

        pedido = api.PedidoEnvio(
            conta_id=conta.id, para="priscila@coobramex.com.br",
            assunto="Procuração", corpo="Segue.",
        )
        d = api.email_enviar(pedido)

        checar(d.get("aguardando_aprovacao") is True, "o pedido vai para a fila")
        checar(not _SMTPFalso.enviados, "NENHUMA mensagem foi entregue ao servidor")

        p = d["pedido"]
        checar(p["categoria"] == "email", "o pedido entra na categoria certa")
        checar(p["reversivel"] is False, "avisa que nao da para desfazer")
        checar("priscila@coobramex.com.br" in p["resumo"], "o resumo diz para quem vai")
        checar("seu servidor" in p["resumo"], "e que o envio sai do servidor da pessoa")

        # Agora o sim.
        r = api.aprovacoes_decidir(api.Decisao(ids=[p["id"]], aprovar=True))
        checar(not r["falhas"], f"a aprovacao executa sem falha ({r['falhas']})")
        checar(len(_SMTPFalso.enviados) == 1, "so depois do sim a mensagem sai")
        checar("enviado para" in r["feitos"][0].get("resultado", ""),
               f"o resultado registra o envio ({r['feitos'][0].get('resultado')})")
        checar(api.estado.envios.para_tela()["total"] == 1, "e o envio entra no registro")

        api.estado.fila.esquecer(p["id"])

        # Recusar nao pode enviar tambem.
        d2 = api.email_enviar(pedido)
        p2 = d2["pedido"]
        api.aprovacoes_decidir(api.Decisao(ids=[p2["id"]], aprovar=False))
        checar(len(_SMTPFalso.enviados) == 1, "recusar na fila nao envia nada")
        api.estado.fila.esquecer(p2["id"])
    finally:
        correio.smtplib.SMTP = original
        api.estado.contas, api.estado.envios = guardadas


def main() -> int:
    print("=" * 55)
    print("PAULUS - e-mail")
    print("=" * 55)

    test_cabecalho_com_acento()
    test_anexos_e_html()
    test_prazo()
    test_enderecos()
    test_listar_caixa()
    test_detectar_servidor()

    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_guardar_conta(tmp)
        test_montar_e_enviar(tmp)
        test_sem_destinatario()
        test_rascunho_limpo()
        test_sem_permissao_nao_envia(tmp)

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
