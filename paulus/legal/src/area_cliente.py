"""
PAULUS - Area do cliente (docs/PLANO-AREA-CLIENTE.md).

O advogado compartilha a pasta de um servico, e o cliente a acompanha pelo
endereco do escritorio (<slug>.paulus.ia.br/cliente/<link>): o resumo, o
andamento, as proximas datas e os documentos que o escritorio separou. O
cliente conversa com o escritorio, manda arquivos e confirma horarios. Tudo o
que ele faz fica registrado.

O MODELO, EM TRES REGRAS

1. Nunca aparece para o cliente - e nao ha botao para mostrar: anotacoes,
   horas, financeiro, a conversa do escritorio com o assistente, a trilha
   interna e a Equipe (so o nome da pessoa responsavel).
2. Aparece por padrao quando a pasta e compartilhada: nome e status, as
   etapas e os compromissos do servico. Cada etapa e cada compromisso tem um
   olhinho para esconder.
3. Documento so aparece com "compartilhar" clicado nele.

A resposta ao cliente e montada por `visao()` a partir de uma LISTA FECHADA de
campos - nunca "o servico inteiro menos o proibido". O "Ver como o cliente" do
escritorio usa a mesma funcao: o advogado ve o que a API entrega, e nao uma
imitacao.

ENTRAR

O link sozinho nao abre nada. O cliente digita o e-mail; se for o da pessoa
do link, um codigo de 6 digitos vai para ele (pelo Worker de paulus.ia.br,
como "Escritorio Tal (via PAVLVS)"), vale 10 minutos e aceita 5 tentativas.
A sessao do cliente nao e uma conta do acesso de fora: cookie proprio, sem
senha, sem TOTP, e so alcanca as rotas /api/cliente/*. O portao de fora
(acesso/remoto.py) entrega essas rotas a `PortaDoCliente`, e nenhuma outra.

O REGISTRO

Cada coisa que o cliente faz entra em `cliente_atividade` (a aba "Atividade
do cliente" da pasta) e no registro encadeado de "quem acessou"
(acesso/auditoria.py). O que nao se promete: print de tela - no celular o
navegador nao fica sabendo. Em troca, cada pagina que o cliente ve, e o PDF
que ele baixa, levam uma marca d'agua com o nome dele, a data e a hora.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import subprocess
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path

COOKIE = "paulus_cliente"
CABECALHO_CSRF = "x-paulus-csrf"
CODIGO_VALE_S = 10 * 60
CODIGO_TENTATIVAS = 5
CODIGOS_POR_HORA = 5
SESSAO_S = 12 * 3600
SESSAO_LEMBRAR_S = 30 * 24 * 3600
# Pedidos de entrada (e-mail e codigo) por endereco de internet, em 10 min.
ENTRADAS_POR_IP = 20
LIMITE_DO_ENVIO = 25 * 1024 * 1024
PASTA_RECEBIDOS = "Recebidos do cliente"
MENSAGEM_MAX = 4000

# O que o cliente pode mandar: o que o escritorio le (PDF, Word, Excel, texto)
# e foto (o RG fotografado no celular e o caso mais comum).
FORMATOS_DO_ENVIO = {".pdf", ".docx", ".xlsx", ".txt", ".jpg", ".jpeg", ".png"}

STATUS_PARA_O_CLIENTE = {
    "andamento": "Em andamento",
    "aguardando": "Aguardando você",
    "revisao": "Em revisão",
    "suspenso": "Suspenso",
    "concluido": "Concluído",
}

ONDE = {"online": "Online", "escritorio": "No escritório", "telefone": "Por telefone"}

# cliente_atividade.acao -> como a aba "Atividade do cliente" diz.
ACOES = {
    "pediu_codigo": "pediu o código de acesso",
    "email_errado": "tentou entrar com outro e-mail",
    "codigo_errado": "errou o código",
    "entrou": "entrou",
    "saiu": "saiu",
    "abriu_pasta": "abriu a pasta",
    "abriu": "abriu o documento",
    "baixou": "baixou o documento",
    "imprimiu": "imprimiu",
    "escreveu": "escreveu ao escritório",
    "enviou": "enviou um arquivo",
    "envio_barrado": "teve um arquivo barrado",
    "concluiu": "marcou como feito",
    "confirmou": "confirmou o horário",
    "remarcar": "pediu para remarcar",
    "agenda": "baixou o horário para a agenda",
}

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PROIBIDOS_NO_NOME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ErroDoCliente(ValueError):
    """O pedido nao pode ser atendido; a mensagem vai para a tela. `status` e o HTTP."""

    def __init__(self, mensagem: str, status: int = 400) -> None:
        super().__init__(mensagem)
        self.status = status


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# O pedido de remarcar chega da tela como "dd/mm/aaaa · período · observação" (o
# calendário, as pílulas e o campo opcional); texto livre também vale, como antes.
_RE_REMARCAR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})(?: · ([^·]{1,40}?))?(?: · (.+))?$")


def _remarcar(sugestao: str) -> dict:
    """O dia, o período e a observação do pedido, quando ele vem no formato da tela. O dia tem de existir e não ter passado."""
    m = _RE_REMARCAR.match(sugestao)
    if not m:
        return {}
    try:
        dia = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        raise ErroDoCliente("essa data não existe: escolha o dia no calendário") from None
    if dia < date.today():
        raise ErroDoCliente("esse dia já passou: escolha outro no calendário")
    return {"dia": dia.isoformat(), "periodo": (m.group(4) or "").strip(), "observacao": (m.group(5) or "").strip()}


def _resumo(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def _json(texto, padrao):
    try:
        return json.loads(texto or "")
    except (TypeError, ValueError):
        return padrao


def email_valido(email: str) -> bool:
    return bool(_EMAIL.match(email or "")) and len(email) <= 200


def mascarar(email: str) -> str:
    """'joao.silva@gmail.com' -> 'j•••••••••@gmail.com': a tela diz para onde foi, sem expor."""
    nome, _, dominio = (email or "").partition("@")
    if not dominio:
        return ""
    return (nome[:1] + "•" * max(len(nome) - 1, 2)) + "@" + dominio


def nome_de_arquivo(nome: str) -> str:
    """O nome que o cliente deu, sem o que o Windows nao aceita."""
    nome = Path(str(nome or "")).name
    nome = _PROIBIDOS_NO_NOME.sub(" ", nome)
    nome = " ".join(nome.split()).strip(" .")
    return nome[:120] or "arquivo"


def conferir_envio(nome: str, conteudo: bytes) -> str:
    """O motivo de recusar o arquivo do cliente, ou "" quando ele pode entrar."""
    import entrada

    sufixo = Path(nome).suffix.lower()
    if sufixo not in FORMATOS_DO_ENVIO:
        return "esse tipo de arquivo não entra: mande PDF, foto (JPG ou PNG), Word, Excel ou texto"
    if not conteudo:
        return "o arquivo está vazio"
    if len(conteudo) > LIMITE_DO_ENVIO:
        return f"o arquivo passa de {LIMITE_DO_ENVIO // (1024 * 1024)} MB"
    if sufixo in (".jpg", ".jpeg"):
        return "" if conteudo.startswith(b"\xff\xd8\xff") else "o nome diz que é foto JPG, mas o conteúdo não é"
    if sufixo == ".png":
        return "" if conteudo.startswith(b"\x89PNG\r\n\x1a\n") else "o nome diz que é imagem PNG, mas o conteúdo não é"
    return entrada.conferir_bytes(nome, conteudo)


def antivirus_do_windows(caminho: Path) -> str:
    """
    O arquivo passa pelo Microsoft Defender antes de entrar na pasta:
    "limpo", "ameaca" ou "sem_antivirus" (o Defender nao esta aqui, ou nao
    respondeu). Sem antivirus, o arquivo entra e a atividade diz que nao
    foi conferido - a tela nao diz que foi.
    """
    exe = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"
    if os.name != "nt" or not exe.exists():
        return "sem_antivirus"
    try:
        r = subprocess.run([str(exe), "-Scan", "-ScanType", "3", "-File", str(caminho), "-DisableRemediation"],
                           capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return "sem_antivirus"
    if r.returncode == 0:
        return "limpo"
    if r.returncode == 2:
        return "ameaca"
    return "sem_antivirus"


# ------------------------------------------------------------ marca d'agua


def _fonte(tamanho: int):
    from PIL import ImageFont

    for nome in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:  # Pillow antigo
        return ImageFont.load_default()


def marcar_png(png: bytes, texto: str) -> bytes:
    """
    A pagina desenhada, com o texto repetido em diagonal, bem claro, e uma
    faixa no pe. Nao impede o print: faz toda copia dizer de onde saiu.
    """
    from PIL import Image, ImageDraw

    pagina = Image.open(io.BytesIO(png)).convert("RGBA")
    w, h = pagina.size
    tamanho = max(14, w // 42)
    fonte = _fonte(tamanho)
    lado = int((w ** 2 + h ** 2) ** 0.5) + 40
    camada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    largura = int(d.textlength(texto, font=fonte)) + tamanho * 5
    passo = tamanho * 7
    for n, y in enumerate(range(0, lado, passo)):
        inicio = -(largura // 2) * (n % 2)
        for x in range(inicio, lado, largura):
            d.text((x, y), texto, font=fonte, fill=(110, 110, 110, 46))
    camada = camada.rotate(28, resample=Image.BICUBIC)
    cx, cy = (lado - w) // 2, (lado - h) // 2
    pagina = Image.alpha_composite(pagina, camada.crop((cx, cy, cx + w, cy + h)))
    faixa = int(tamanho * 1.9)
    pe = ImageDraw.Draw(pagina)
    pe.rectangle((0, h - faixa, w, h), fill=(250, 249, 246, 225))
    pe.text((tamanho, h - faixa + (faixa - tamanho) // 2 - 1), texto, font=_fonte(int(tamanho * .8)), fill=(70, 70, 66, 255))
    saida = io.BytesIO()
    pagina.convert("RGB").save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def marcar_pdf(pdf: bytes, texto: str) -> bytes:
    """O mesmo texto, sobre cada pagina do PDF que o cliente baixa."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    leitor = PdfReader(io.BytesIO(pdf))
    if leitor.is_encrypted:
        try:
            leitor.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise ErroDoCliente("esse PDF é protegido por senha: peça o documento ao escritório", 409) from exc
    escritor = PdfWriter()
    texto_pdf = texto.encode("latin-1", "replace").decode("latin-1")
    for pagina in leitor.pages:
        w, h = float(pagina.mediabox.width), float(pagina.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.saveState()
        c.setFillColorRGB(.45, .45, .45)
        c.setFillAlpha(.16)
        c.setFont("Helvetica", 13)
        c.translate(w / 2, h / 2)
        c.rotate(28)
        largura = c.stringWidth(texto_pdf, "Helvetica", 13) + 60
        lado = int((w ** 2 + h ** 2) ** 0.5)
        for n, y in enumerate(range(-lado // 2, lado // 2, 90)):
            x = -lado // 2 - (largura / 2) * (n % 2)
            while x < lado / 2:
                c.drawString(x, y, texto_pdf)
                x += largura
        c.restoreState()
        c.setFillColorRGB(.3, .3, .3)
        c.setFillAlpha(.8)
        c.setFont("Helvetica", 7.5)
        c.drawString(18, 10, texto_pdf)
        c.save()
        pagina.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
        escritor.add_page(pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def texto_em_pdf(titulo: str, texto: str) -> bytes:
    """
    Documento que nao e PDF (Word, Excel, texto), para o cliente ver na tela:
    o texto que o Acervo leu, em paginas. A formatacao fica de fora - quem
    precisa dela baixa o arquivo original.
    """
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    estilos = getSampleStyleSheet()
    corpo = estilos["BodyText"].clone("corpo", fontSize=10.5, leading=15)
    saida = io.BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2.2 * cm, title=titulo)
    fluxo = [Paragraph(escape(titulo), estilos["Heading2"]), Spacer(1, 6)]
    for bloco in re.split(r"\n\s*\n", texto or "") or [""]:
        bloco = bloco.strip()
        if bloco:
            fluxo.append(Paragraph(escape(bloco).replace("\n", "<br/>"), corpo))
            fluxo.append(Spacer(1, 5))
    if len(fluxo) == 2:
        fluxo.append(Paragraph("(sem texto para mostrar)", corpo))
    doc.build(fluxo)
    return saida.getvalue()


def ics(titulo: str, data: str, hora: str, duracao_min: int, onde: str, descricao: str, uid: str) -> str:
    """O compromisso como evento de agenda (.ics), para o cliente guardar no celular."""
    inicio = datetime.fromisoformat(f"{data}T{(hora or '09:00')[:5]}:00")
    fim = inicio.timestamp() + max(int(duracao_min or 60), 15) * 60
    fmt = "%Y%m%dT%H%M%S"
    limpar = lambda t: str(t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    linhas = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PAVLVS//Area do cliente//PT", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{datetime.now().strftime(fmt)}",
        f"DTSTART:{inicio.strftime(fmt)}", f"DTEND:{datetime.fromtimestamp(fim).strftime(fmt)}",
        f"SUMMARY:{limpar(titulo)}",
    ]
    if onde:
        linhas.append(f"LOCATION:{limpar(onde)}")
    if descricao:
        linhas.append(f"DESCRIPTION:{limpar(descricao)}")
    linhas += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(linhas) + "\r\n"


# ------------------------------------------------------------------ a area


class AreaDoCliente:
    """
    Tudo o que a Area do cliente guarda e decide. As dependencias entram por
    funcao, para o teste trocar: `documentos()` e o Acervo lido (os objetos
    com sha1, path, name e text), `hostname()` o endereco do escritorio,
    `enviar_email(dados)` devolve "" ou a frase do que impediu, `registrar`
    e a auditoria de "quem acessou" e `avisar(titulo, texto)` o aviso ao
    escritorio.
    """

    def __init__(self, base, servicos, pasta_dados: Path, *, documentos=lambda: [], hostname=lambda: "",
                 escritorio=lambda: "", enviar_email=None, registrar=None, avisar=None, ao_receber=None,
                 antivirus=antivirus_do_windows, relogio=time.time) -> None:
        self.base = base
        self.servicos = servicos
        self.pasta_dados = Path(pasta_dados)
        self.documentos = documentos
        self.hostname = hostname
        self.escritorio = escritorio
        self.enviar_email = enviar_email or (lambda dados: "o envio de e-mail não está ligado")
        self.registrar = registrar
        self.avisar = avisar
        # (servico_id, caminho) -> o arquivo recebido entra no Acervo e no servico.
        self.ao_receber = ao_receber
        self.antivirus = antivirus
        self.relogio = relogio
        self._trava = threading.Lock()
        self._entradas: dict[str, list[float]] = {}
        self._vistos: dict[tuple, float] = {}
        self._pdfs: dict[str, bytes] = {}

    # ------------------------------------------------------------ pessoas

    def link(self, pessoa: dict) -> str:
        host = (self.hostname() or "").strip()
        return f"https://{host}/cliente/{pessoa['token']}" if host else ""

    def _pessoa(self, pessoa_id: int) -> dict | None:
        return self.base.um("SELECT * FROM cliente_pessoas WHERE id = ?", (int(pessoa_id),))

    def _por_token(self, token: str) -> dict | None:
        token = str(token or "").strip()
        if not token or len(token) > 64:
            return None
        p = self.base.um("SELECT * FROM cliente_pessoas WHERE token = ?", (token,))
        return p if p and not p["revogado_em"] else None

    def pastas_da_pessoa(self, pessoa_id: int) -> list[int]:
        return [l["servico_id"] for l in self.base.buscar(
            "SELECT cp.servico_id FROM cliente_pastas cp JOIN servicos s ON s.id = cp.servico_id "
            "WHERE cp.pessoa_id = ? ORDER BY s.atualizado_em DESC", (int(pessoa_id),))]

    def pode_ver(self, pessoa_id: int, servico_id: int) -> bool:
        return bool(self.base.um("SELECT 1 AS ok FROM cliente_pastas WHERE pessoa_id = ? AND servico_id = ?",
                                 (int(pessoa_id), int(servico_id))))

    def pessoas_da_pasta(self, servico_id: int) -> list[dict]:
        linhas = self.base.buscar(
            "SELECT p.id, p.nome, p.email, p.token, p.ultimo_acesso, cp.desde, cp.por FROM cliente_pastas cp "
            "JOIN cliente_pessoas p ON p.id = cp.pessoa_id WHERE cp.servico_id = ? ORDER BY cp.desde", (int(servico_id),))
        return [{"id": l["id"], "nome": l["nome"], "email": l["email"], "link": self.link(l),
                 "ultimo_acesso": l["ultimo_acesso"], "desde": l["desde"], "por": l["por"]} for l in linhas]

    def para_a_pasta(self, servico_id: int) -> dict:
        """
        O que a tela da pasta (Servicos) precisa para desenhar o olhinho, o
        "compartilhar" dos documentos e o selo de mensagens - leve, vai em
        toda abertura da pasta.
        """
        pessoas = self.base.contar("cliente_pastas", "servico_id = ?", (int(servico_id),))
        return {"compartilhado": pessoas > 0, "pessoas": pessoas,
                "nao_lidas": self.nao_lidas().get(int(servico_id), 0),
                "documentos": self.documentos_compartilhados_sha1(servico_id),
                "compromissos": [l["id"] for l in self.base.buscar("SELECT id FROM compromissos WHERE servico_id = ?", (int(servico_id),))],
                **self.estado_dos_compromissos(servico_id)}

    def compartilhado(self, servico_id: int) -> bool:
        return bool(self.base.um("SELECT 1 AS ok FROM cliente_pastas WHERE servico_id = ?", (int(servico_id),)))

    def _nome_da_pasta(self, servico_id: int) -> str:
        s = self.base.um("SELECT nome FROM servicos WHERE id = ?", (int(servico_id),))
        if not s:
            raise ErroDoCliente("serviço não encontrado", 404)
        return s["nome"]

    def _responsavel(self, servico_id: int) -> str:
        """O nome da pessoa responsavel (a primeira da Equipe) - so o nome."""
        s = self.base.um("SELECT equipe FROM servicos WHERE id = ?", (int(servico_id),))
        ids = _json(s["equipe"] if s else "[]", [])
        if not ids:
            return ""
        p = self.base.um("SELECT nome FROM cadastros WHERE id = ?", (int(ids[0]),))
        return p["nome"] if p else ""

    def _carta(self, tipo: str, pessoa: dict, servico_id: int | None = None, quem: str = "", **extra) -> str:
        link = self.link(pessoa)
        if not link:
            return "o acesso externo não está conectado"
        dados = {"tipo": tipo, "para": pessoa["email"], "link": link, "nome": pessoa["nome"],
                 "escritorio": self.escritorio() or ""}
        if servico_id is not None:
            dados["pasta"] = self._nome_da_pasta(servico_id)
            dados["advogado"] = quem or self._responsavel(servico_id) or self.escritorio() or ""
        dados.update(extra)
        try:
            return self.enviar_email(dados) or ""
        except Exception as exc:  # noqa: BLE001 - o e-mail que nao sai nao derruba o que ja foi feito
            return str(exc) or "não consegui mandar o e-mail"

    def compartilhar(self, servico_id: int, nome: str, email: str, cadastro_id=None, quem: str = "") -> dict:
        """
        A pasta passa a ser vista por esta pessoa. O e-mail e a chave: o
        mesmo e-mail em outra pasta e a mesma pessoa, com o mesmo link -
        "um link por cliente". O convite vai por e-mail; se nao for, a pasta
        continua compartilhada e a tela oferece o link para mandar por outro
        caminho.
        """
        pasta = self._nome_da_pasta(servico_id)
        nome = " ".join(str(nome or "").split())[:80]
        email = str(email or "").strip().lower()
        if not nome:
            raise ErroDoCliente("diga o nome de quem vai ver a pasta")
        if not email_valido(email):
            raise ErroDoCliente("esse e-mail não parece certo")
        if not (self.hostname() or "").strip():
            raise ErroDoCliente("ligue o acesso externo antes (Configurações › Acesso externo): é por ele que o cliente entra", 409)
        try:
            cadastro_id = int(cadastro_id) if cadastro_id not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            cadastro_id = None
        with self._trava:
            pessoa = self.base.um("SELECT * FROM cliente_pessoas WHERE email = ?", (email,))
            if pessoa is None:
                self.base.escrever(
                    "INSERT INTO cliente_pessoas (nome, email, cadastro_id, token, criado_em, criado_por) VALUES (?, ?, ?, ?, ?, ?)",
                    (nome, email, cadastro_id, secrets.token_urlsafe(18), _agora(), quem))
            elif pessoa["revogado_em"]:
                self.base.escrever("UPDATE cliente_pessoas SET revogado_em = '', nome = ? WHERE id = ?", (nome, pessoa["id"]))
            pessoa = self.base.um("SELECT * FROM cliente_pessoas WHERE email = ?", (email,))
            ja = self.pode_ver(pessoa["id"], servico_id)
            if not ja:
                self.base.escrever("INSERT INTO cliente_pastas (pessoa_id, servico_id, desde, por) VALUES (?, ?, ?, ?)",
                                   (pessoa["id"], int(servico_id), _agora(), quem))
        if not ja:
            self.servicos.trilha(servico_id, f"Pasta compartilhada com {pessoa['nome']} ({email})", quem,
                                 tipo="cliente_compartilhou", dados={"nome": pessoa["nome"], "email": email})
        erro = self._carta("convite", pessoa, servico_id, quem)
        return {"pessoa": {"id": pessoa["id"], "nome": pessoa["nome"], "email": email, "link": self.link(pessoa)},
                "pasta": pasta, "ja_via": ja, "email_enviado": not erro, "erro_email": erro}

    def reenviar(self, servico_id: int, pessoa_id: int, quem: str = "") -> dict:
        pessoa = self._pessoa(pessoa_id)
        if not pessoa or not self.pode_ver(pessoa_id, servico_id):
            raise ErroDoCliente("essa pessoa não vê esta pasta", 404)
        erro = self._carta("convite", pessoa, servico_id, quem)
        return {"email_enviado": not erro, "erro_email": erro, "link": self.link(pessoa)}

    def parar(self, servico_id: int, pessoa_id: int, quem: str = "") -> None:
        """Para de compartilhar: na hora - a proxima pagina que a pessoa pedir ja nao vem."""
        pessoa = self._pessoa(pessoa_id)
        if not pessoa or not self.pode_ver(pessoa_id, servico_id):
            raise ErroDoCliente("essa pessoa não vê esta pasta", 404)
        self.base.escrever("DELETE FROM cliente_pastas WHERE pessoa_id = ? AND servico_id = ?", (int(pessoa_id), int(servico_id)))
        self.servicos.trilha(servico_id, f"Parou de compartilhar com {pessoa['nome']}", quem,
                             tipo="cliente_parou", dados={"nome": pessoa["nome"], "email": pessoa["email"]})

    # ------------------------------------------------------- o que se ve

    def _etapas(self, servico_id: int) -> list[dict]:
        return self.servicos._etapas(int(servico_id))

    def marcar_etapa(self, servico_id: int, indice: int, *, oculta=None, do_cliente=None) -> list[dict]:
        """
        O olhinho de uma etapa e a etapa "do cliente" (a pendencia dele em
        "Para voce"). Etapa do cliente nao tem responsavel da equipe e nunca
        fica escondida - senao ele nao a veria.
        """
        etapas = self._etapas(servico_id)
        if indice < 0 or indice >= len(etapas):
            raise ErroDoCliente("etapa não encontrada", 404)
        e = etapas[indice]
        if oculta is not None:
            e["oculta_cliente"] = bool(oculta)
            if oculta:
                e.pop("cliente", None)
        if do_cliente is not None:
            if do_cliente:
                e["cliente"] = True
                e["oculta_cliente"] = False
                e["responsavel_id"] = None
            else:
                e.pop("cliente", None)
        if not e.get("oculta_cliente"):
            e.pop("oculta_cliente", None)
        self.servicos._empurrar_para_tarefas(int(servico_id), etapas)
        return etapas

    def marcar_compromisso(self, servico_id: int, compromisso_id: int, *, oculto=None, confirmar=None) -> dict:
        c = self.base.um("SELECT id FROM compromissos WHERE id = ? AND servico_id = ?", (int(compromisso_id), int(servico_id)))
        if not c:
            raise ErroDoCliente("compromisso não encontrado nesta pasta", 404)
        if oculto is not None:
            if oculto:
                self.base.escrever("INSERT OR IGNORE INTO cliente_ocultos (servico_id, tipo, item_id) VALUES (?, 'compromisso', ?)",
                                   (int(servico_id), int(compromisso_id)))
                self.base.escrever("DELETE FROM cliente_confirmacoes WHERE compromisso_id = ?", (int(compromisso_id),))
            else:
                self.base.escrever("DELETE FROM cliente_ocultos WHERE servico_id = ? AND tipo = 'compromisso' AND item_id = ?",
                                   (int(servico_id), int(compromisso_id)))
        if confirmar is not None:
            if confirmar:
                self.base.escrever("DELETE FROM cliente_ocultos WHERE servico_id = ? AND tipo = 'compromisso' AND item_id = ?",
                                   (int(servico_id), int(compromisso_id)))
                self.base.escrever(
                    "INSERT INTO cliente_confirmacoes (compromisso_id, servico_id, pedido_em) VALUES (?, ?, ?) "
                    "ON CONFLICT(compromisso_id) DO UPDATE SET pedido_em = excluded.pedido_em, resposta = '', sugestao = '', "
                    "quem = '', respondido_em = ''", (int(compromisso_id), int(servico_id), _agora()))
            else:
                self.base.escrever("DELETE FROM cliente_confirmacoes WHERE compromisso_id = ?", (int(compromisso_id),))
        return self.estado_dos_compromissos(servico_id)

    def estado_dos_compromissos(self, servico_id: int) -> dict:
        ocultos = {l["item_id"] for l in self.base.buscar(
            "SELECT item_id FROM cliente_ocultos WHERE servico_id = ? AND tipo = 'compromisso'", (int(servico_id),))}
        conf = {l["compromisso_id"]: {"pedido_em": l["pedido_em"], "resposta": l["resposta"], "sugestao": l["sugestao"],
                                      "quem": l["quem"], "respondido_em": l["respondido_em"]}
                for l in self.base.buscar("SELECT * FROM cliente_confirmacoes WHERE servico_id = ?", (int(servico_id),))}
        return {"ocultos": sorted(ocultos), "confirmacoes": {str(k): v for k, v in conf.items()}}

    def compartilhar_documento(self, servico_id: int, sha1: str, sim: bool, quem: str = "") -> list[str]:
        sha1 = str(sha1 or "").strip().lower()
        ligado = self.base.um("SELECT nome FROM vinculos WHERE tipo = 'servico' AND alvo_id = ? AND sha1 = ?", (int(servico_id), sha1))
        if not ligado:
            raise ErroDoCliente("esse documento não está nesta pasta", 404)
        if sim:
            self.base.escrever("INSERT OR IGNORE INTO cliente_documentos (servico_id, sha1, desde, por) VALUES (?, ?, ?, ?)",
                               (int(servico_id), sha1, _agora(), quem))
        else:
            self.base.escrever("DELETE FROM cliente_documentos WHERE servico_id = ? AND sha1 = ?", (int(servico_id), sha1))
        return self.documentos_compartilhados_sha1(servico_id)

    def documentos_compartilhados_sha1(self, servico_id: int) -> list[str]:
        return [l["sha1"] for l in self.base.buscar("SELECT sha1 FROM cliente_documentos WHERE servico_id = ?", (int(servico_id),))]

    def _documentos(self, servico_id: int) -> list[dict]:
        """Os compartilhados que continuam ligados a pasta (desligar do servico tira do cliente)."""
        return self.base.buscar(
            "SELECT d.sha1, v.nome, d.desde FROM cliente_documentos d JOIN vinculos v ON v.tipo = 'servico' "
            "AND v.alvo_id = d.servico_id AND v.sha1 = d.sha1 WHERE d.servico_id = ? ORDER BY d.desde DESC", (int(servico_id),))

    def _compromissos(self, servico_id: int, hoje: str) -> list[dict]:
        ocultos = set(self.estado_dos_compromissos(servico_id)["ocultos"])
        linhas = self.base.buscar(
            "SELECT id, titulo, tipo, data, hora, duracao, onde, meet FROM compromissos WHERE servico_id = ? AND data >= ? "
            "ORDER BY data, hora", (int(servico_id), hoje))
        return [l for l in linhas if l["id"] not in ocultos]

    def visao(self, servico_id: int) -> dict:
        """
        O que o cliente ve desta pasta - a LISTA FECHADA. Campo novo no
        servico nao chega aqui sozinho: precisa ser escrito abaixo.
        """
        s = self.base.um("SELECT id, nome, status, etapas, equipe FROM servicos WHERE id = ?", (int(servico_id),))
        if not s:
            raise ErroDoCliente("pasta não encontrada", 404)
        # O que mudou em Tarefas (etapa concluida la) volta antes de mostrar.
        self.servicos.puxar_das_tarefas(int(servico_id))
        etapas = self._etapas(servico_id)
        hoje = date.today().isoformat()
        andamento = []
        for i, e in enumerate(etapas):
            if e.get("oculta_cliente"):
                continue
            andamento.append({"indice": i, "titulo": str(e.get("titulo") or ""), "feita": bool(e.get("feita")),
                              "quando": str(e.get("quando") or ""), "feita_em": str(e.get("feita_em") or "")[:10],
                              "do_cliente": bool(e.get("cliente"))})
        feitas = sum(1 for e in andamento if e["feita"])
        progresso = round(feitas * 100 / len(andamento)) if andamento else (100 if s["status"] == "concluido" else 0)
        conf = self.estado_dos_compromissos(servico_id)["confirmacoes"]
        datas, pendencias = [], []
        for c in self._compromissos(servico_id, hoje):
            confirmacao = conf.get(str(c["id"]))
            item = {"tipo": "compromisso", "id": c["id"], "titulo": c["titulo"], "quando": c["data"], "hora": c["hora"],
                    "duracao": c["duracao"], "onde": ONDE.get(c["onde"] or "", c["onde"] or ""),
                    "sala": c["meet"] if c["onde"] == "online" and str(c["meet"] or "").startswith("https://") else "",
                    "confirmacao": {"resposta": confirmacao["resposta"], "sugestao": confirmacao["sugestao"]} if confirmacao else None}
            datas.append(item)
            if confirmacao and confirmacao["resposta"] != "confirmado":
                pendencias.append(dict(item, pendencia="confirmar"))
        for e in andamento:
            if not e["feita"] and e["quando"] and e["quando"] >= hoje:
                datas.append({"tipo": "etapa", "indice": e["indice"], "titulo": e["titulo"], "quando": e["quando"], "hora": "",
                              "do_cliente": e["do_cliente"]})
            if e["do_cliente"] and not e["feita"]:
                pendencias.append({"tipo": "etapa", "indice": e["indice"], "titulo": e["titulo"], "quando": e["quando"],
                                   "pendencia": "fazer"})
        datas.sort(key=lambda x: (x["quando"], x.get("hora") or ""))
        pendencias.sort(key=lambda x: (x.get("quando") or "9999", x.get("hora") or ""))
        resumo = self.base.um("SELECT texto, publicado_em FROM cliente_resumos WHERE servico_id = ?", (int(servico_id),))
        return {
            "pasta": {"id": s["id"], "nome": s["nome"], "status": s["status"],
                      "status_rotulo": STATUS_PARA_O_CLIENTE.get(s["status"], s["status"]), "progresso": progresso},
            "escritorio": self.escritorio() or "",
            "responsavel": self._responsavel(servico_id),
            "resumo": {"texto": resumo["texto"], "em": resumo["publicado_em"]} if resumo and resumo["texto"] and resumo["publicado_em"] else None,
            "pendencias": pendencias,
            "datas": datas[:12],
            "andamento": andamento,
            "documentos": [{"sha1": d["sha1"], "nome": d["nome"], "desde": d["desde"][:10]} for d in self._documentos(servico_id)],
            "mensagens": self.mensagens(servico_id),
        }

    # --------------------------------------------------------- documentos

    def _arquivo(self, servico_id: int, sha1: str):
        """O documento do Acervo atras de um compartilhado: (Path, Document) - ou 404."""
        sha1 = str(sha1 or "").lower()
        if not any(d["sha1"] == sha1 for d in self._documentos(servico_id)):
            raise ErroDoCliente("documento não encontrado", 404)
        pasta = self.servicos.pasta_de(int(servico_id), criar=False)
        iguais = [d for d in self.documentos() if getattr(d, "sha1", "") == sha1 and Path(d.path).is_file()]
        if pasta:
            iguais.sort(key=lambda d: 0 if str(Path(d.path)).lower().startswith(str(pasta).lower()) else 1)
        if not iguais:
            raise ErroDoCliente("o documento saiu do Acervo do escritório", 410)
        return Path(iguais[0].path), iguais[0]

    def _pdf(self, caminho: Path, doc) -> bytes:
        if caminho.suffix.lower() == ".pdf":
            return caminho.read_bytes()
        chave = f"{getattr(doc, 'sha1', '')}:{caminho.stat().st_mtime}"
        if chave not in self._pdfs:
            if len(self._pdfs) > 20:
                self._pdfs.clear()
            self._pdfs[chave] = texto_em_pdf(caminho.name, getattr(doc, "text", "") or "")
        return self._pdfs[chave]

    def marca(self, nome: str, previa: bool = False) -> str:
        quando = datetime.fromtimestamp(self.relogio()).strftime("%d/%m/%Y %H:%M")
        quem = "Prévia do escritório" if previa else nome
        return f"{quem} · {quando} · {self.escritorio() or 'PAVLVS'}"

    def pagina(self, servico_id: int, sha1: str, numero: int, marca: str, largura: int = 1100) -> tuple[bytes, int, str]:
        """(PNG marcado, total de paginas, nome do documento)."""
        import documento

        caminho, doc = self._arquivo(servico_id, sha1)
        pdf = self._pdf(caminho, doc)
        total = documento.paginas_de(pdf)
        numero = max(1, min(int(numero or 1), total or 1))
        png = documento.pagina_png(pdf, numero, max(400, min(int(largura or 1100), 1600)))
        return marcar_png(png, marca), total, caminho.name

    def baixar(self, servico_id: int, sha1: str, marca: str) -> tuple[bytes, str, str]:
        """
        (conteudo, nome, tipo). PDF sai com a marca em cada pagina; os outros
        formatos saem como estao - a tela diz isso antes de baixar.
        """
        caminho, _doc = self._arquivo(servico_id, sha1)
        if caminho.suffix.lower() == ".pdf":
            return marcar_pdf(caminho.read_bytes(), marca), caminho.name, "application/pdf"
        tipos = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8"}
        return caminho.read_bytes(), caminho.name, tipos.get(caminho.suffix.lower(), "application/octet-stream")

    # ------------------------------------------------------------- entrar

    def _ip_ok(self, ip: str) -> bool:
        agora = self.relogio()
        with self._trava:
            lista = [t for t in self._entradas.get(ip or "-", []) if agora - t < 600]
            if len(lista) >= ENTRADAS_POR_IP:
                self._entradas[ip or "-"] = lista
                return False
            lista.append(agora)
            self._entradas[ip or "-"] = lista
        return True

    def pedir_codigo(self, token: str, email: str, ip: str = "") -> dict:
        """
        O cliente digitou o e-mail. Se for o da pessoa do link, o codigo vai
        para ele. A resposta e a mesma nos dois casos: quem tem o link mas
        nao o e-mail nao descobre qual e.
        """
        if not self._ip_ok(ip):
            raise ErroDoCliente("muitas tentativas seguidas — espere alguns minutos", 429)
        pessoa = self._por_token(token)
        if not pessoa or not self.pastas_da_pessoa(pessoa["id"]):
            raise ErroDoCliente("este link não vale mais — peça um novo ao escritório", 404)
        email = str(email or "").strip().lower()
        resposta = {"ok": True, "para": mascarar(email) if email_valido(email) else ""}
        if not hmac.compare_digest(email, pessoa["email"]):
            self.anotar(pessoa, "email_errado", ip=ip)
            return resposta
        agora = self.relogio()
        linha = self.base.um("SELECT pedidos FROM cliente_codigos WHERE pessoa_id = ?", (pessoa["id"],))
        pedidos = [t for t in _json(linha["pedidos"] if linha else "[]", []) if agora - float(t) < 3600]
        if len(pedidos) >= CODIGOS_POR_HORA:
            raise ErroDoCliente("já mandamos vários códigos na última hora — use o último que chegou, ou espere um pouco", 429)
        codigo = f"{secrets.randbelow(10 ** 6):06d}"
        self.base.escrever(
            "INSERT INTO cliente_codigos (pessoa_id, resumo, expira, tentativas, pedidos) VALUES (?, ?, ?, 0, ?) "
            "ON CONFLICT(pessoa_id) DO UPDATE SET resumo = excluded.resumo, expira = excluded.expira, tentativas = 0, "
            "pedidos = excluded.pedidos",
            (pessoa["id"], _resumo(f"{pessoa['id']}:{codigo}"), agora + CODIGO_VALE_S, json.dumps(pedidos + [agora])))
        erro = self._carta("codigo", pessoa, codigo=codigo)
        if erro:
            raise ErroDoCliente("não consegui mandar o código agora: " + erro, 424)
        self.anotar(pessoa, "pediu_codigo", ip=ip)
        return resposta

    def entrar(self, token: str, codigo: str, lembrar: bool = False, ip: str = "") -> dict:
        """O codigo confere: nasce a sessao. Devolve o cookie, o anti-CSRF e quanto vale."""
        if not self._ip_ok(ip):
            raise ErroDoCliente("muitas tentativas seguidas — espere alguns minutos", 429)
        pessoa = self._por_token(token)
        if not pessoa or not self.pastas_da_pessoa(pessoa["id"]):
            raise ErroDoCliente("este link não vale mais — peça um novo ao escritório", 404)
        codigo = re.sub(r"\D", "", str(codigo or ""))
        linha = self.base.um("SELECT * FROM cliente_codigos WHERE pessoa_id = ?", (pessoa["id"],))
        agora = self.relogio()
        if not linha or not linha["resumo"] or float(linha["expira"]) < agora:
            raise ErroDoCliente("o código venceu — peça outro", 400)
        if int(linha["tentativas"]) >= CODIGO_TENTATIVAS:
            raise ErroDoCliente("o código foi digitado errado muitas vezes — peça outro", 400)
        if not hmac.compare_digest(_resumo(f"{pessoa['id']}:{codigo}"), linha["resumo"]):
            self.base.escrever("UPDATE cliente_codigos SET tentativas = tentativas + 1 WHERE pessoa_id = ?", (pessoa["id"],))
            self.anotar(pessoa, "codigo_errado", ip=ip)
            restam = CODIGO_TENTATIVAS - int(linha["tentativas"]) - 1
            raise ErroDoCliente("código errado" + (f" — restam {restam} tentativas" if restam > 1 else
                                                   (" — resta 1 tentativa" if restam == 1 else " — peça outro")), 400)
        self.base.escrever("UPDATE cliente_codigos SET resumo = '', expira = 0 WHERE pessoa_id = ?", (pessoa["id"],))
        valor = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(18)
        dura = SESSAO_LEMBRAR_S if lembrar else SESSAO_S
        self.base.escrever("DELETE FROM cliente_sessoes WHERE expira < ?", (agora,))
        self.base.escrever("INSERT INTO cliente_sessoes (resumo, pessoa_id, csrf, criada, expira, ip) VALUES (?, ?, ?, ?, ?, ?)",
                           (_resumo(valor), pessoa["id"], csrf, agora, agora + dura, ip))
        self.base.escrever("UPDATE cliente_pessoas SET ultimo_acesso = ? WHERE id = ?", (_agora(), pessoa["id"]))
        self.anotar(pessoa, "entrou", ip=ip)
        return {"cookie": valor, "csrf": csrf, "max_age": dura if lembrar else None}

    def sessao(self, valor: str) -> dict | None:
        """A pessoa da sessao (com o csrf), ou None: vencida, desconhecida ou pessoa desligada."""
        if not valor or len(valor) > 128:
            return None
        s = self.base.um("SELECT * FROM cliente_sessoes WHERE resumo = ?", (_resumo(valor),))
        if not s or float(s["expira"]) < self.relogio():
            return None
        pessoa = self._pessoa(s["pessoa_id"])
        if not pessoa or pessoa["revogado_em"]:
            return None
        return {"id": pessoa["id"], "nome": pessoa["nome"], "email": pessoa["email"], "csrf": s["csrf"]}

    def sair(self, valor: str, ip: str = "") -> None:
        p = self.sessao(valor)
        self.base.escrever("DELETE FROM cliente_sessoes WHERE resumo = ?", (_resumo(valor or ""),))
        if p:
            self.anotar(p, "saiu", ip=ip)

    def eu(self, pessoa: dict) -> dict:
        pastas = []
        for sid in self.pastas_da_pessoa(pessoa["id"]):
            s = self.base.um("SELECT id, nome, status FROM servicos WHERE id = ?", (sid,))
            if s:
                pastas.append({"id": s["id"], "nome": s["nome"], "status_rotulo": STATUS_PARA_O_CLIENTE.get(s["status"], s["status"]),
                               "novas": self.base.contar("cliente_mensagens", "servico_id = ? AND de = 'escritorio' AND quando > ?",
                                                         (sid, self._ultima_vista(pessoa["id"], sid)))})
        return {"pessoa": {"nome": pessoa["nome"], "email": pessoa["email"]}, "escritorio": self.escritorio() or "",
                "pastas": pastas, "csrf": pessoa.get("csrf", "")}

    def _ultima_vista(self, pessoa_id: int, servico_id: int) -> str:
        l = self.base.um("SELECT MAX(quando) AS q FROM cliente_atividade WHERE pessoa_id = ? AND servico_id = ? AND acao = 'abriu_pasta'",
                         (int(pessoa_id), int(servico_id)))
        return (l or {}).get("q") or ""

    # -------------------------------------------------------- o registro

    def anotar(self, pessoa: dict, acao: str, servico_id: int | None = None, alvo: str = "", ip: str = "",
               juntar_s: float = 0) -> None:
        """
        Uma linha na atividade da pasta e outra em "quem acessou". `juntar_s`
        junta a mesma coisa repetida (folhear as paginas do mesmo documento
        vira uma linha so a cada tantos segundos).
        """
        if juntar_s:
            chave = (pessoa["id"], servico_id, acao, alvo)
            agora = self.relogio()
            if agora - self._vistos.get(chave, 0) < juntar_s:
                return
            self._vistos[chave] = agora
        self.base.escrever(
            "INSERT INTO cliente_atividade (pessoa_id, servico_id, acao, alvo, quando, ip) VALUES (?, ?, ?, ?, ?, ?)",
            (pessoa["id"], servico_id, acao, str(alvo or "")[:300], _agora(), str(ip or "")[:64]))
        if self.registrar:
            pasta = ""
            if servico_id:
                s = self.base.um("SELECT nome FROM servicos WHERE id = ?", (int(servico_id),))
                pasta = s["nome"] if s else ""
            try:
                self.registrar(acao="cliente_" + acao, pessoa=f"{pessoa['nome']} (cliente)", email=pessoa.get("email", ""),
                               ip=ip, alvo=" · ".join(x for x in (pasta, str(alvo or "")) if x))
            except Exception:  # noqa: BLE001 - a auditoria nao derruba o pedido
                pass

    def atividade(self, servico_id: int, limite: int = 300) -> list[dict]:
        linhas = self.base.buscar(
            "SELECT a.acao, a.alvo, a.quando, a.ip, p.nome, p.email FROM cliente_atividade a "
            "JOIN cliente_pessoas p ON p.id = a.pessoa_id WHERE a.servico_id = ? "
            "OR (a.servico_id IS NULL AND a.pessoa_id IN (SELECT pessoa_id FROM cliente_pastas WHERE servico_id = ?)) "
            "ORDER BY a.id DESC LIMIT ?", (int(servico_id), int(servico_id), int(limite)))
        return [{"quando": l["quando"], "pessoa": l["nome"], "email": l["email"], "acao": l["acao"],
                 "acao_rotulo": ACOES.get(l["acao"], l["acao"]), "alvo": l["alvo"], "ip": l["ip"]} for l in linhas]

    # -------------------------------------------------------- a conversa

    def mensagens(self, servico_id: int, limite: int = 200) -> list[dict]:
        linhas = self.base.buscar(
            "SELECT id, de, autor, texto, etapa, anexo, quando FROM cliente_mensagens WHERE servico_id = ? "
            "ORDER BY id DESC LIMIT ?", (int(servico_id), int(limite)))
        return list(reversed(linhas))

    def nao_lidas(self) -> dict[int, int]:
        return {l["servico_id"]: l["n"] for l in self.base.buscar(
            "SELECT servico_id, COUNT(*) AS n FROM cliente_mensagens WHERE de = 'cliente' AND lida_em = '' GROUP BY servico_id")}

    def marcar_lidas(self, servico_id: int) -> None:
        self.base.escrever("UPDATE cliente_mensagens SET lida_em = ? WHERE servico_id = ? AND de = 'cliente' AND lida_em = ''",
                           (_agora(), int(servico_id)))

    def _escrever(self, servico_id: int, de: str, autor: str, texto: str, pessoa_id=None, etapa: str = "", anexo: str = "") -> dict:
        texto = str(texto or "").strip()
        if not texto:
            raise ErroDoCliente("escreva a mensagem")
        if len(texto) > MENSAGEM_MAX:
            raise ErroDoCliente(f"a mensagem passa de {MENSAGEM_MAX} letras")
        id_ = self.base.escrever(
            "INSERT INTO cliente_mensagens (servico_id, pessoa_id, de, autor, texto, etapa, anexo, quando) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (int(servico_id), pessoa_id, de, autor[:80], texto, str(etapa or "")[:160], str(anexo or "")[:160], _agora()))
        return self.base.um("SELECT id, de, autor, texto, etapa, anexo, quando FROM cliente_mensagens WHERE id = ?", (id_,))

    def _avisar_escritorio(self, servico_id: int, titulo: str, texto: str) -> None:
        if self.avisar:
            try:
                self.avisar(titulo, texto)
            except Exception:  # noqa: BLE001
                pass

    def cliente_escreve(self, pessoa: dict, servico_id: int, texto: str, etapa: str = "", ip: str = "") -> dict:
        m = self._escrever(servico_id, "cliente", pessoa["nome"], texto, pessoa["id"], etapa)
        self.anotar(pessoa, "escreveu", servico_id, etapa, ip)
        self._avisar_escritorio(servico_id, f"{pessoa['nome']} escreveu", f"{self._nome_da_pasta(servico_id)}: {m['texto'][:120]}")
        return m

    def escritorio_escreve(self, servico_id: int, texto: str, quem: str) -> dict:
        """A resposta do escritorio; cada pessoa que ve a pasta recebe um aviso por e-mail (sem o texto)."""
        m = self._escrever(servico_id, "escritorio", quem or (self.escritorio() or "Escritório"), texto)
        avisados, falhas = 0, []
        for p in self.pessoas_da_pasta(servico_id):
            pessoa = self._pessoa(p["id"])
            erro = self._carta("mensagem", pessoa, servico_id, quem)
            if erro:
                falhas.append(erro)
            else:
                avisados += 1
        return {"mensagem": m, "avisados": avisados, "erro_email": falhas[0] if falhas else ""}

    # ------------------------------------------------- o que o cliente faz

    def _etapa_do_cliente(self, servico_id: int, indice: int) -> dict:
        etapas = self._etapas(servico_id)
        if indice < 0 or indice >= len(etapas) or etapas[indice].get("oculta_cliente") or not etapas[indice].get("cliente"):
            raise ErroDoCliente("essa pendência não existe", 404)
        return etapas[indice]

    def cliente_conclui(self, pessoa: dict, servico_id: int, indice: int, ip: str = "") -> dict:
        e = self._etapa_do_cliente(servico_id, indice)
        if not e.get("feita"):
            self.servicos.etapa_alternar(int(servico_id), indice, quem=f"{pessoa['nome']} (cliente)")
            self.anotar(pessoa, "concluiu", servico_id, e["titulo"], ip)
            self._avisar_escritorio(servico_id, f"{pessoa['nome']} concluiu uma pendência", f"{self._nome_da_pasta(servico_id)}: {e['titulo']}")
        return self.visao(servico_id)

    def cliente_envia(self, pessoa: dict, servico_id: int, nome: str, conteudo: bytes, indice=None, ip: str = "") -> dict:
        """
        O arquivo do cliente: conferido (tipo pelo conteudo, tamanho), passado
        pelo antivirus numa pasta de espera, e so entao posto em "Recebidos do
        cliente", dentro da pasta do servico no Acervo. Nunca e aberto aqui.
        """
        nome = nome_de_arquivo(nome)
        etapa = None
        if indice not in (None, ""):
            etapa = self._etapa_do_cliente(servico_id, int(indice))
        motivo = conferir_envio(nome, conteudo)
        if motivo:
            self.anotar(pessoa, "envio_barrado", servico_id, f"{nome}: {motivo}", ip)
            raise ErroDoCliente(motivo[:1].upper() + motivo[1:] + ".")
        espera = self.pasta_dados / "area_cliente" / "recebendo"
        espera.mkdir(parents=True, exist_ok=True)
        temporario = espera / (uuid.uuid4().hex + Path(nome).suffix.lower())
        temporario.write_bytes(conteudo)
        try:
            veredito = self.antivirus(temporario)
            if veredito == "ameaca":
                self.anotar(pessoa, "envio_barrado", servico_id, f"{nome}: o antivírus barrou", ip)
                self._avisar_escritorio(servico_id, "Arquivo barrado pelo antivírus",
                                        f"{pessoa['nome']} tentou mandar {nome} para {self._nome_da_pasta(servico_id)}.")
                raise ErroDoCliente("O antivírus do escritório barrou este arquivo. Fale com o escritório.", 422)
            pasta = self.servicos.pasta_de(int(servico_id), criar=True)
            if not pasta:
                raise ErroDoCliente("a pasta do escritório não está disponível agora — tente mais tarde", 409)
            destino_dir = pasta / PASTA_RECEBIDOS
            destino_dir.mkdir(parents=True, exist_ok=True)
            destino = destino_dir / nome
            n = 2
            while destino.exists():
                destino = destino_dir / f"{Path(nome).stem} ({n}){Path(nome).suffix}"
                n += 1
            os.replace(temporario, destino)
        finally:
            if temporario.exists():
                try:
                    temporario.unlink()
                except OSError:
                    pass
        conferido = "conferido pelo antivírus" if veredito == "limpo" else "sem antivírus nesta máquina"
        self.anotar(pessoa, "enviou", servico_id, f"{destino.name} ({conferido})", ip)
        if self.ao_receber:
            try:
                self.ao_receber(int(servico_id), destino)
            except Exception:  # noqa: BLE001 - o arquivo ja esta na pasta; o indice pega depois
                pass
        texto = f"Enviei {destino.name}"
        self._escrever(servico_id, "cliente", pessoa["nome"], texto, pessoa["id"], etapa["titulo"] if etapa else "", destino.name)
        self._avisar_escritorio(servico_id, f"{pessoa['nome']} mandou um arquivo", f"{self._nome_da_pasta(servico_id)}: {destino.name}")
        if etapa and not etapa.get("feita"):
            self.servicos.etapa_alternar(int(servico_id), int(indice), quem=f"{pessoa['nome']} (cliente)")
        return {"nome": destino.name, "antivirus": veredito, "visao": self.visao(servico_id)}

    def cliente_responde(self, pessoa: dict, servico_id: int, compromisso_id: int, resposta: str, sugestao: str = "",
                         ip: str = "") -> dict:
        """Confirmo / preciso remarcar - so no compromisso em que o escritorio pediu."""
        if resposta not in ("confirmado", "remarcar"):
            raise ErroDoCliente("resposta inválida")
        hoje = date.today().isoformat()
        c = next((x for x in self._compromissos(servico_id, hoje) if x["id"] == int(compromisso_id)), None)
        pedido = self.base.um("SELECT * FROM cliente_confirmacoes WHERE compromisso_id = ? AND servico_id = ?",
                              (int(compromisso_id), int(servico_id)))
        if not c or not pedido:
            raise ErroDoCliente("esse horário não está esperando resposta", 404)
        sugestao = " ".join(str(sugestao or "").split())[:300]
        if resposta == "remarcar" and not sugestao:
            raise ErroDoCliente("diga que dia e horário ficam melhor para você")
        pedido_novo = _remarcar(sugestao) if resposta == "remarcar" else {}
        self.base.escrever("UPDATE cliente_confirmacoes SET resposta = ?, sugestao = ?, quem = ?, respondido_em = ? WHERE compromisso_id = ?",
                           (resposta, sugestao if resposta == "remarcar" else "", pessoa["nome"], _agora(), int(compromisso_id)))
        quando = datetime.fromisoformat(c["data"]).strftime("%d/%m") + (f" às {c['hora']}" if c["hora"] else "")
        if resposta == "confirmado":
            texto = f"Confirmo {c['titulo']} em {quando}."
            self.anotar(pessoa, "confirmou", servico_id, f"{c['titulo']} · {quando}", ip)
            self.servicos.trilha(servico_id, f"{pessoa['nome']} confirmou: {c['titulo']} ({quando})", f"{pessoa['nome']} (cliente)",
                                 tipo="cliente_confirmou", dados={"titulo": c["titulo"], "quando": quando})
        else:
            texto = f"Preciso remarcar {c['titulo']} ({quando}). Fica melhor: {sugestao}"
            self.anotar(pessoa, "remarcar", servico_id, f"{c['titulo']} · {quando} → {sugestao}", ip)
            self.servicos.trilha(servico_id, f"{pessoa['nome']} pediu para remarcar: {c['titulo']} ({quando})", f"{pessoa['nome']} (cliente)",
                                 tipo="cliente_remarcar", dados={"titulo": c["titulo"], "quando": quando, "sugestao": sugestao, **pedido_novo})
        self._escrever(servico_id, "cliente", pessoa["nome"], texto, pessoa["id"], c["titulo"])
        self._avisar_escritorio(servico_id, f"{pessoa['nome']} respondeu sobre um horário", texto[:160])
        return self.visao(servico_id)

    def ics_do_compromisso(self, servico_id: int, compromisso_id: int) -> tuple[str, str]:
        hoje = date.today().isoformat()
        c = next((x for x in self._compromissos(servico_id, hoje) if x["id"] == int(compromisso_id)), None)
        if not c:
            raise ErroDoCliente("compromisso não encontrado", 404)
        onde = c["meet"] if c["onde"] == "online" and c["meet"] else ONDE.get(c["onde"] or "", c["onde"] or "")
        descricao = f"{self._nome_da_pasta(servico_id)} · {self.escritorio() or ''}".strip(" ·")
        texto = ics(c["titulo"], c["data"], c["hora"], c["duracao"], onde, descricao, f"compromisso-{c['id']}@paulus.ia.br")
        return texto, re.sub(r"[^\w\- ]", "", c["titulo"])[:60].strip() or "compromisso"

    # ------------------------------------------------------------- resumo

    def resumo(self, servico_id: int) -> dict:
        r = self.base.um("SELECT * FROM cliente_resumos WHERE servico_id = ?", (int(servico_id),)) or {}
        return {"texto": r.get("texto", ""), "publicado_em": r.get("publicado_em", ""), "por": r.get("por", ""),
                "rascunho": r.get("rascunho", ""), "rascunho_em": r.get("rascunho_em", "")}

    def publicar_resumo(self, servico_id: int, texto: str, quem: str = "") -> dict:
        """O resumo que o cliente le - so o que o escritorio publicou. Texto vazio tira."""
        self._nome_da_pasta(servico_id)
        texto = str(texto or "").strip()[:3000]
        self.base.escrever(
            "INSERT INTO cliente_resumos (servico_id, texto, publicado_em, por, rascunho, rascunho_em) VALUES (?, ?, ?, ?, '', '') "
            "ON CONFLICT(servico_id) DO UPDATE SET texto = excluded.texto, publicado_em = excluded.publicado_em, "
            "por = excluded.por, rascunho = '', rascunho_em = ''",
            (int(servico_id), texto, _agora() if texto else "", quem))
        if texto:
            self.servicos.trilha(servico_id, "Resumo para o cliente publicado", quem, tipo="cliente_resumo", dados={"texto": texto})
        return self.resumo(servico_id)

    def guardar_rascunho(self, servico_id: int, texto: str) -> dict:
        self.base.escrever(
            "INSERT INTO cliente_resumos (servico_id, rascunho, rascunho_em) VALUES (?, ?, ?) "
            "ON CONFLICT(servico_id) DO UPDATE SET rascunho = excluded.rascunho, rascunho_em = excluded.rascunho_em",
            (int(servico_id), str(texto or "").strip()[:3000], _agora()))
        return self.resumo(servico_id)

    def texto_para_ia(self, servico_id: int) -> str:
        """
        O que o modelo le para escrever o resumo do cliente: SO o que o
        cliente ve (a visao). Anotacao, hora, trilha interna e documento nao
        compartilhado nao chegam ao modelo - e assim nao chegam ao texto.
        """
        v = self.visao(servico_id)
        linhas = [f"Serviço: {v['pasta']['nome']}", f"Situação: {v['pasta']['status_rotulo']} ({v['pasta']['progresso']}% das etapas)"]
        for e in v["andamento"]:
            linhas.append(("[feito] " if e["feita"] else "[a fazer] ") + e["titulo"] +
                          (f" (concluído em {e['feita_em']})" if e["feita"] and e["feita_em"] else "") +
                          (f" (até {e['quando']})" if not e["feita"] and e["quando"] else "") +
                          (" — cabe ao cliente" if e["do_cliente"] else ""))
        for d in v["datas"]:
            if d["tipo"] == "compromisso":
                linhas.append(f"Compromisso marcado: {d['titulo']} em {d['quando']}" + (f" às {d['hora']}" if d["hora"] else ""))
        for d in v["documentos"]:
            linhas.append(f"Documento disponível para o cliente: {d['nome']}")
        return "\n".join(linhas)


INSTRUCAO_RESUMO_CLIENTE = """Você escreve para o CLIENTE de um escritório de advocacia brasileiro, que
não é advogado. Abaixo está o que o escritório mostra a ele sobre o serviço:
as etapas feitas e a fazer, as datas e os documentos. Escreva, em português do
Brasil e em linguagem simples (sem juridiquês, sem latim, sem número de
artigo), um resumo de no máximo dois parágrafos curtos: onde o serviço está,
o que vem a seguir e, se houver, o que depende do cliente. Use só o que está
escrito abaixo; não invente datas, valores, prazos nem chances de resultado,
e não dê opinião sobre o caso. Não use saudação nem assinatura."""


# ----------------------------------------------------------------- a porta


class PortaDoCliente:
    """
    O que o portao de fora (acesso/remoto.py) faz com /cliente/* e
    /api/cliente/*: confere o plano, o limite de corpo e - em tudo o que
    altera, menos entrar - a sessao do cliente e o token anti-CSRF dela. As
    rotas conferem de novo a sessao e se a pessoa ve a pasta pedida.
    """

    SEM_SESSAO = {("POST", "/api/cliente/entrar"), ("POST", "/api/cliente/codigo")}

    def __init__(self, area: AreaDoCliente, ligado=lambda: True, motivo_desligado=lambda: "") -> None:
        self.area = area
        self.ligado = ligado
        self.motivo_desligado = motivo_desligado

    @staticmethod
    def atende(caminho: str) -> bool:
        return caminho.startswith("/api/cliente/") or (caminho.startswith("/cliente/") and caminho.count("/") == 2)

    async def __call__(self, app, scope, receive, send, cab: dict) -> None:
        from acesso.porteiro import cookies, recusar

        metodo = scope.get("method", "GET")
        caminho = scope.get("path", "")
        if not self.ligado():
            await recusar(scope, send, 403, self.motivo_desligado() or "a área do cliente não está ativa neste escritório")
            return
        if caminho.startswith("/api/") and metodo not in ("GET", "HEAD") and (metodo, caminho) not in self.SEM_SESSAO:
            sessao = self.area.sessao(cookies(cab).get(COOKIE))
            if not sessao:
                await recusar(scope, send, 401, "entre de novo: a sessão acabou", [(b"x-paulus-sessao", b"acabou")])
                return
            if not hmac.compare_digest(str(cab.get(CABECALHO_CSRF) or ""), sessao["csrf"]):
                await recusar(scope, send, 403, "pedido sem o token da sessão")
                return
        await app(scope, receive, send)
