"""
PAULUS - Ler e enviar e-mail.

IMAP e SMTP da biblioteca padrao. Sem servico no meio, sem copia na nuvem: a
conexao sai desta maquina direto para o servidor do escritorio.

Uma escolha guia o modulo todo, e e a promessa que o rodape da tela faz:
"mensagens ficam no seu servidor, leio so o que voce abrir". Entao a listagem
puxa cabecalho, nao mensagem - assunto, remetente, data, se tem anexo. O corpo
so e baixado quando a pessoa abre aquele e-mail. Isso e privacidade e tambem e
velocidade: caixa com 4 mil mensagens abre em segundos.

O assistente entra depois, e so quando chamado. Rodar o modelo em cima de cada
mensagem que chega custaria cerca de um minuto por e-mail nesta maquina - a
caixa de entrada ficaria inutil. Prazo e detectado por regra, que e instantaneo;
o modelo so escreve rascunho quando alguem pede.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import re
import smtplib
import socket
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, parsedate_to_datetime
from pathlib import Path

TEMPO_LIMITE = 20          # segundos por operacao de rede
MAX_ANEXO_BYTES = 20 * 1024 * 1024

FILTROS = {
    "tudo": "Tudo",
    "nao_lidos": "Não lidos",
    "com_anexo": "Com anexo",
    "de_clientes": "De clientes",
}

# Palavras que, junto de uma data, indicam prazo - nao so mencao de calendario.
PALAVRAS_PRAZO = (
    "prazo", "vence", "vencimento", "protocolar", "protocolo", "audiencia",
    "audiência", "ate o dia", "até o dia", "improrrogavel", "improrrogável",
    "impreterivelmente", "urgente", "contestacao", "contestação", "recurso",
)


class ErroCorreio(RuntimeError):
    """Falha de conexao ou de login, ja traduzida para o portugues."""


# ------------------------------------------------------------ a mensagem


@dataclass
class Mensagem:
    uid: str = ""
    de_nome: str = ""
    de_email: str = ""
    para: str = ""
    cc: str = ""                  # quem mais recebeu (o "responder a todos")
    assunto: str = ""
    quando: str = ""              # ISO
    quando_curto: str = ""        # "09:12", "ontem", "3 set"
    lido: bool = False
    respondido: bool = False
    tem_anexo: bool = False
    previa: str = ""
    corpo: str = ""
    anexos: list[dict] = field(default_factory=list)
    prazo: str = ""               # data ISO, quando o texto indica um
    prazo_trecho: str = ""
    de_cadastro: str = ""         # nome do cliente, quando o remetente e um
    # A versao em HTML, limpa (sem script, formulario nem evento), com as
    # imagens embutidas (cid:) ja dentro. A tela mostra num iframe isolado,
    # com CSP que nao busca nada de fora ate a pessoa pedir.
    html: str = ""
    imagens_remotas: int = 0      # imagens de fora, bloqueadas por padrao
    sinalizada: bool = False      # a estrela (\Flagged no IMAP, a mesma do Gmail)

    def to_dict(self) -> dict:
        return asdict(self)


def _decodificar(carga: bytes, charset: str | None) -> str:
    """
    Bytes para texto, com a correcao que todo cliente de e-mail faz.

    Outlook manda travessao, aspas curvas e reticencias em cp1252 mas declara
    iso-8859-1 - onde esses bytes sao caracteres de controle. Decodificar ao pe
    da letra poe caractere invisivel no meio do assunto. Navegador e cliente de
    e-mail tratam iso-8859-1 como cp1252 justamente por isso.
    """
    nome = (charset or "utf-8").strip().lower().replace("_", "-")
    if nome in ("iso-8859-1", "latin-1", "latin1", "iso8859-1", "us-ascii", "ascii"):
        nome = "cp1252"
    try:
        return carga.decode(nome, errors="replace")
    except LookupError:
        return carga.decode("utf-8", errors="replace")


def _corrigir_c1(texto: str) -> str:
    """
    Conserta travessao e aspas curvas que viraram caractere invisivel.

    A politica moderna do modulo `email` ja decodifica o cabecalho antes de
    entregar, entao a correcao por bytes nao alcanca esse caminho: o que sobra
    e um caractere de controle (U+0080 a U+009F) no meio do assunto. Esses
    codigos nao aparecem em texto de verdade - quando aparecem, sao cp1252 lido
    como iso-8859-1, e a tabela do cp1252 diz o que era.
    """
    if not any("\x80" <= c <= "\x9f" for c in texto):
        return texto
    saida = []
    for c in texto:
        if "\x80" <= c <= "\x9f":
            saida.append(bytes([ord(c)]).decode("cp1252", errors="replace"))
        else:
            saida.append(c)
    return "".join(saida)


def _texto_cabecalho(bruto) -> str:
    """
    Decodifica cabecalho com acento.

    Assunto em portugues chega como =?iso-8859-1?Q?Procura=E7=E3o?= com muita
    frequencia - servidor brasileiro antigo nao usa UTF-8. Sem isto a tela
    mostraria o codigo em vez do assunto.
    """
    if not bruto:
        return ""
    try:
        pedacos = []
        for carga, charset in decode_header(str(bruto)):
            if isinstance(carga, bytes):
                pedacos.append(_decodificar(carga, charset))
            else:
                pedacos.append(str(carga))
        return _corrigir_c1("".join(pedacos)).strip()
    except Exception:
        return _corrigir_c1(str(bruto)).strip()


def _quando_curto(quando: datetime | None) -> str:
    if not quando:
        return ""
    agora = datetime.now(quando.tzinfo)
    dia = quando.date()
    if dia == agora.date():
        return quando.strftime("%H:%M")
    if dia == (agora - timedelta(days=1)).date():
        return "ontem"
    if (agora.date() - dia).days < 300:
        meses = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"]
        return f"{dia.day} {meses[dia.month - 1]}"
    return dia.strftime("%d/%m/%Y")


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def detectar_prazo(texto: str) -> tuple[str, str]:
    """
    Acha data que parece prazo, e devolve (data ISO, trecho onde apareceu).

    Data sozinha nao e prazo: "reuniao dia 12" e outra coisa. Exige uma palavra
    de prazo por perto, e exige que a data esteja no futuro - prazo que ja
    passou nao e prazo, e historico. Foi o mesmo erro que a sugestao de tarefas
    cometeu antes, propondo conferir vencimento de 2021.
    """
    from classify import detectar_data

    if not texto:
        return "", ""

    hoje = datetime.now().date().isoformat()
    limpo = _sem_acento(texto)

    for bruto in re.split(r"(?<=[.!?\n])\s+", texto):
        frase = _sem_acento(bruto)
        if not any(p in frase for p in (_sem_acento(x) for x in PALAVRAS_PRAZO)):
            continue
        data = detectar_data(bruto)
        if data and data > hoje:
            return data, " ".join(bruto.split())[:160]

    # Sem frase clara, tenta o texto inteiro - mas so se houver palavra de prazo.
    if any(_sem_acento(p) in limpo for p in PALAVRAS_PRAZO):
        data = detectar_data(texto)
        if data and data > hoje:
            return data, ""
    return "", ""


LIMITE_IMAGEM_EMBUTIDA = 2 * 1024 * 1024
LIMITE_EMBUTIDAS_TOTAL = 6 * 1024 * 1024


def _corpo_legivel(msg) -> tuple[str, list[dict], str, int]:
    """
    Texto da mensagem, a lista de anexos (sem baixar os anexos), e a versao
    em HTML ja limpa com a contagem de imagens de fora.

    Imagem embutida (Content-ID, citada no HTML como cid:) nao e anexo: e a
    logo do remetente, o grafico do corpo. Vai para dentro do HTML como data
    URI. A que o HTML nao cita continua na lista de anexos.
    """
    import base64

    anexos: list[dict] = []
    texto = ""
    html = ""
    embutidas: dict[str, tuple[str, bytes, dict]] = {}

    for parte in msg.walk():
        if parte.is_multipart():
            continue
        disposicao = (parte.get_content_disposition() or "").lower()
        tipo = parte.get_content_type()
        nome = _texto_cabecalho(parte.get_filename())
        cid = str(parte.get("Content-ID") or "").strip().strip("<>")

        if cid and tipo.startswith("image/") and disposicao != "attachment":
            carga = parte.get_payload(decode=True) or b""
            embutidas[cid] = (tipo, carga, {
                "nome": nome or "imagem", "tipo": tipo, "bytes": len(carga),
                "kb": round(len(carga) / 1024, 1), "parte": nome or tipo,
            })
            continue

        if disposicao == "attachment" or (nome and tipo != "text/plain"):
            carga = parte.get_payload(decode=True) or b""
            anexos.append({
                "nome": nome or "anexo",
                "tipo": tipo,
                "bytes": len(carga),
                "kb": round(len(carga) / 1024, 1),
                "parte": nome or tipo,
            })
            continue

        # Decodifica pelos bytes, nao por get_content(): e aqui que a
        # correcao de iso-8859-1 para cp1252 precisa valer tambem no corpo.
        carga = parte.get_payload(decode=True)
        if carga is None:
            try:
                conteudo = str(parte.get_content())
            except Exception:
                continue
        else:
            conteudo = _decodificar(carga, parte.get_content_charset())

        if tipo == "text/plain" and not texto:
            texto = conteudo
        elif tipo == "text/html" and not html:
            html = conteudo

    if not texto and html:
        texto = _html_para_texto(html)

    # Embutida que o HTML cita vira data URI; a que nao cita e anexo de verdade.
    dados_cid: dict[str, str] = {}
    total = 0
    for cid, (tipo, carga, ficha) in embutidas.items():
        citada = html and re.search(r"cid:" + re.escape(cid), html, re.I)
        if citada and len(carga) <= LIMITE_IMAGEM_EMBUTIDA and total + len(carga) <= LIMITE_EMBUTIDAS_TOTAL:
            total += len(carga)
            dados_cid[cid] = f"data:{tipo};base64," + base64.b64encode(carga).decode("ascii")
        elif not citada:
            anexos.append(ficha)

    seguro, remotas = sanitizar_html(_corrigir_c1(html), dados_cid) if html else ("", 0)
    return _corrigir_c1(texto).strip(), anexos, seguro, remotas


# Tags que nao tem o que fazer num e-mail mostrado: executam codigo, enviam
# dados, carregam outra pagina ou mudam o endereco base.
_TAGS_PROIBIDAS = ("script", "iframe", "frame", "frameset", "object", "embed", "applet",
                   "form", "base", "meta", "link", "portal", "template")


def sanitizar_html(html: str, dados_cid: dict | None = None) -> tuple[str, int]:
    """
    O HTML de um e-mail pronto para o iframe isolado, e quantas imagens de fora ele pede.

    Nao e a unica barreira: a tela mostra num iframe sem permissao de script e
    com CSP que so aceita o que veio dentro do e-mail. Aqui sai o que nao
    tem motivo de estar - codigo, formulario, eventos, links javascript: -, e
    as imagens embutidas (cid:) entram como data URI.
    """
    dados_cid = dados_cid or {}
    limpo = html
    for tag in _TAGS_PROIBIDAS:
        limpo = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", "", limpo, flags=re.S | re.I)
        limpo = re.sub(rf"</?{tag}\b[^>]*>", "", limpo, flags=re.I)
    # Eventos (onclick, onload...) e enderecos que executam codigo.
    limpo = re.sub(r"""\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", limpo, flags=re.I)
    limpo = re.sub(r"""(href|src|action|formaction|xlink:href)\s*=\s*(["']?)\s*(javascript|vbscript|data:text/html)[^"'\s>]*\2""",
                   r'\1="#"', limpo, flags=re.I)
    limpo = re.sub(r"@import[^;]+;", "", limpo, flags=re.I)
    limpo = re.sub(r"expression\s*\(", "(", limpo, flags=re.I)

    def trocar_cid(m):
        cid = m.group(2)
        return f'{m.group(1)}"{dados_cid[cid]}"' if cid in dados_cid else m.group(0)

    limpo = re.sub(r"""(src\s*=\s*)["']cid:([^"']+)["']""", trocar_cid, limpo, flags=re.I)

    remotas = len(re.findall(r"""<img\b[^>]*\bsrc\s*=\s*["']?\s*https?:""", limpo, flags=re.I))
    remotas += len(re.findall(r"""url\(\s*["']?\s*https?:""", limpo, flags=re.I))
    return limpo.strip(), remotas


def _html_para_texto(html: str) -> str:
    """
    O suficiente para ler um e-mail, sem trazer biblioteca para isso.

    Nao pretende renderizar HTML: tira script, estilo e marcacao, e devolve o
    texto. E-mail de escritorio quase sempre tem versao em texto puro; isto e
    para quando nao tem.
    """
    import html as _html

    limpo = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    limpo = re.sub(r"<br\s*/?>", "\n", limpo, flags=re.I)
    limpo = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", limpo, flags=re.I)
    limpo = re.sub(r"<[^>]+>", " ", limpo)
    limpo = _html.unescape(limpo)
    limpo = re.sub(r"[ \t]+", " ", limpo)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", limpo).strip()


def montar_mensagem(bruto: bytes, uid: str = "", *, so_cabecalho: bool = False) -> Mensagem:
    """Transforma os bytes que o servidor devolveu numa Mensagem."""
    msg = email.message_from_bytes(bruto, policy=email.policy.default)

    remetentes = getaddresses([str(msg.get("From", ""))])
    nome, endereco = remetentes[0] if remetentes else ("", "")

    try:
        quando = parsedate_to_datetime(str(msg.get("Date", "")))
    except (TypeError, ValueError):
        quando = None

    item = Mensagem(
        uid=uid,
        de_nome=_texto_cabecalho(nome) or endereco.split("@")[0],
        de_email=endereco.lower(),
        para=_texto_cabecalho(msg.get("To", "")),
        cc=_texto_cabecalho(msg.get("Cc", "")),
        assunto=_texto_cabecalho(msg.get("Subject", "")) or "(sem assunto)",
        quando=quando.isoformat() if quando else "",
        quando_curto=_quando_curto(quando),
    )

    if so_cabecalho:
        return item

    item.corpo, item.anexos, item.html, item.imagens_remotas = _corpo_legivel(msg)
    item.tem_anexo = bool(item.anexos)
    item.previa = " ".join(item.corpo.split())[:180]
    item.prazo, item.prazo_trecho = detectar_prazo(f"{item.assunto}\n{item.corpo}")
    return item


# --------------------------------------------------------------- conexao


def _por_login(conta) -> str:
    """"google" ou "microsoft" quando a conta entra pelo login OAuth; "" se por senha."""
    modo = getattr(conta, "autenticacao", "senha") or "senha"
    return modo if modo in ("google", "microsoft") else ""


def xoauth2(email_: str, token: str) -> str:
    """A linha do SASL XOAUTH2 (imaplib e smtplib aplicam o base64)."""
    return f"user={email_}\x01auth=Bearer {token}\x01\x01"


def _erro_amigavel(exc: Exception, onde: str, conta=None) -> ErroCorreio:
    texto = str(exc).lower()
    provedor = _por_login(conta) if conta is not None else ""
    recusou = ("authentication" in texto or "authenticate" in texto or "login" in texto
               or "credential" in texto or "xoauth2" in texto)
    if recusou and provedor:
        rotulo = "Google" if provedor == "google" else "Microsoft"
        frase = f"o servidor de {onde} recusou o acesso do login {rotulo}."
        if provedor == "microsoft" and onde == "saída":
            frase += (" Em contas Microsoft 365 de empresa, o administrador pode ter "
                      "desligado o envio autenticado (SMTP AUTH) desta caixa.")
        elif provedor == "microsoft":
            frase += " Em contas Microsoft 365 de empresa, o administrador pode ter desligado o IMAP."
        else:
            frase += " Tente entrar de novo com o Google."
        return ErroCorreio(frase)
    if recusou:
        return ErroCorreio(
            "o servidor recusou a senha. Se for Gmail, precisa ser uma Senha de app, "
            "não a senha da conta."
        )
    if isinstance(exc, socket.timeout) or "timed out" in texto:
        return ErroCorreio(f"o servidor de {onde} não respondeu a tempo - confira o endereço e a porta")
    if isinstance(exc, socket.gaierror) or "name or service" in texto or "getaddrinfo" in texto:
        return ErroCorreio(f"não achei o servidor de {onde} - confira o endereço")
    return ErroCorreio(f"não consegui falar com o servidor de {onde}: {exc}")


def _abrir_imap(conta, senha: str) -> imaplib.IMAP4:
    """
    Conecta e entra. `senha` e a senha da conta - ou, na conta de login
    (Google/Microsoft), o access token, que entra por XOAUTH2.
    """
    if not conta.imap_host:
        raise ErroCorreio("falta o servidor de entrada (IMAP) desta conta")
    provedor = _por_login(conta)
    if not senha:
        raise ErroCorreio("é preciso entrar de novo nesta conta" if provedor else "preciso da senha desta conta")

    try:
        if conta.imap_ssl:
            con = imaplib.IMAP4_SSL(conta.imap_host, conta.imap_porta, timeout=TEMPO_LIMITE)
        else:
            con = imaplib.IMAP4(conta.imap_host, conta.imap_porta, timeout=TEMPO_LIMITE)
            con.starttls()
    except Exception as exc:
        raise _erro_amigavel(exc, "entrada") from exc

    try:
        if provedor:
            linha = xoauth2(conta.email, senha).encode("utf-8")
            con.authenticate("XOAUTH2", lambda _desafio: linha)
        else:
            con.login(conta.email, senha)
    except Exception as exc:
        try:
            con.logout()
        except Exception:
            pass
        raise _erro_amigavel(exc, "entrada", conta) from exc
    return con


def _abrir_smtp(conta, senha: str) -> smtplib.SMTP:
    if not conta.smtp_host:
        raise ErroCorreio("falta o servidor de saída (SMTP) desta conta")

    try:
        if conta.smtp_porta == 465:
            con = smtplib.SMTP_SSL(conta.smtp_host, conta.smtp_porta, timeout=TEMPO_LIMITE)
        else:
            con = smtplib.SMTP(conta.smtp_host, conta.smtp_porta, timeout=TEMPO_LIMITE)
            if conta.smtp_tls:
                con.starttls()
    except Exception as exc:
        raise _erro_amigavel(exc, "saída") from exc

    try:
        if _por_login(conta):
            linha = xoauth2(conta.email, senha)

            # Primeira chamada (sem desafio) manda a linha; se o servidor
            # recusar, ele manda um desafio com o motivo e espera resposta
            # vazia antes do 535 - devolver a linha de novo ficaria em laco.
            def _xoauth2(desafio=None):
                return linha if desafio is None else ""

            con.ehlo_or_helo_if_needed()
            con.auth("XOAUTH2", _xoauth2, initial_response_ok=True)
        else:
            con.login(conta.email, senha)
    except Exception as exc:
        try:
            con.quit()
        except Exception:
            pass
        raise _erro_amigavel(exc, "saída", conta) from exc
    return con


def testar(conta, senha: str) -> dict:
    """
    Prova a conta antes de guardar.

    Testa as duas pontas: da para ler e da para enviar sao coisas diferentes, e
    falhar so numa e comum - servidor de saida com porta diferente, por exemplo.
    Guardar uma conta que so lê, sem dizer, seria descobrir isso na hora errada.
    """
    resultado = {"entrada": False, "saida": False, "erro_entrada": "", "erro_saida": "", "caixas": 0}

    try:
        con = _abrir_imap(conta, senha)
        try:
            estado, dados = con.list()
            resultado["caixas"] = len(dados) if estado == "OK" and dados else 0
            resultado["entrada"] = True
        finally:
            try:
                con.logout()
            except Exception:
                pass
    except ErroCorreio as exc:
        resultado["erro_entrada"] = str(exc)

    try:
        con = _abrir_smtp(conta, senha)
        try:
            resultado["saida"] = True
        finally:
            try:
                con.quit()
            except Exception:
                pass
    except ErroCorreio as exc:
        resultado["erro_saida"] = str(exc)

    resultado["ok"] = resultado["entrada"] and resultado["saida"]
    return resultado


# -------------------------------------------------------------- ler


def listar(conta, senha: str, *, filtro: str = "tudo", busca: str = "",
           limite: int = 25, antes_de: str = "", clientes: dict | None = None) -> dict:
    """
    Os cabecalhos das mensagens mais recentes.

    So cabecalho: assunto, quem mandou, quando, se tem anexo. O corpo fica no
    servidor ate alguem abrir a mensagem - e a promessa do rodape da tela.
    """
    con = _abrir_imap(conta, senha)
    try:
        estado, _ = con.select("INBOX", readonly=True)
        if estado != "OK":
            raise ErroCorreio("não consegui abrir a caixa de entrada")

        criterio = _criterio(filtro, busca)
        estado, dados = con.uid("SEARCH", None, *criterio)
        if estado != "OK":
            raise ErroCorreio("a busca no servidor não deu certo")

        uids = (dados[0] or b"").split()
        total = len(uids)

        # Do mais novo para o mais velho, e so a pagina pedida.
        uids = list(reversed(uids))
        if antes_de and antes_de.encode() in uids:
            uids = uids[uids.index(antes_de.encode()) + 1:]
        pagina = uids[:max(int(limite), 1)]

        itens = _cabecalhos(con, pagina, clientes or {})

        if filtro == "com_anexo":
            itens = [m for m in itens if m.tem_anexo]
        if filtro == "de_clientes":
            itens = [m for m in itens if m.de_cadastro]

        sem_resposta = sum(1 for m in itens if not m.respondido and not m.lido)
        nao_lidos = sum(1 for m in itens if not m.lido)

        return {
            "mensagens": [m.to_dict() for m in itens],
            "total": total,
            "mostrando": len(itens),
            "nao_lidos": nao_lidos,
            "sem_resposta": sem_resposta,
            "ultimo_uid": itens[-1].uid if itens else "",
            "tem_mais": len(uids) > len(pagina),
        }
    finally:
        try:
            con.logout()
        except Exception:
            pass


def _criterio(filtro: str, busca: str) -> list[str]:
    if busca.strip():
        # OR de assunto e remetente: e o que a pessoa espera de uma busca.
        termo = busca.strip()
        return ["OR", "SUBJECT", f'"{termo}"', "FROM", f'"{termo}"']
    if filtro == "nao_lidos":
        return ["UNSEEN"]
    return ["ALL"]


def _cabecalhos(con, uids: list[bytes], clientes: dict) -> list[Mensagem]:
    if not uids:
        return []

    conjunto = b",".join(uids).decode()
    estado, dados = con.uid(
        "FETCH", conjunto,
        "(FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE)])",
    )
    if estado != "OK" or not dados:
        return []

    itens: dict[str, Mensagem] = {}
    for bloco in dados:
        if not isinstance(bloco, tuple) or len(bloco) < 2:
            continue
        marca = bloco[0].decode("utf-8", errors="replace")
        uid = _campo(marca, "UID")
        if not uid:
            continue

        item = montar_mensagem(bloco[1], uid=uid, so_cabecalho=True)
        item.lido = "\\Seen" in marca
        item.respondido = "\\Answered" in marca
        item.sinalizada = "\\Flagged" in marca
        # BODYSTRUCTURE diz se ha anexo sem baixar byte de anexo nenhum.
        item.tem_anexo = '"attachment"' in marca.lower()
        item.prazo, item.prazo_trecho = detectar_prazo(item.assunto)
        item.de_cadastro = clientes.get(item.de_email, "")
        itens[uid] = item

    # Devolve na ordem em que foram pedidos - o servidor responde fora de ordem.
    return [itens[u.decode()] for u in uids if u.decode() in itens]


def _campo(marca: str, nome: str) -> str:
    achado = re.search(rf"{nome}\s+(\d+)", marca)
    return achado.group(1) if achado else ""


def abrir(conta, senha: str, uid: str, *, marcar_lido: bool = True) -> Mensagem:
    """A mensagem inteira - e so agora ela sai do servidor."""
    con = _abrir_imap(conta, senha)
    try:
        estado, _ = con.select("INBOX", readonly=not marcar_lido)
        if estado != "OK":
            raise ErroCorreio("não consegui abrir a caixa de entrada")

        parte = "(BODY[])" if marcar_lido else "(BODY.PEEK[])"
        estado, dados = con.uid("FETCH", uid, parte)
        if estado != "OK" or not dados or not isinstance(dados[0], tuple):
            raise ErroCorreio("não achei essa mensagem no servidor")

        return montar_mensagem(dados[0][1], uid=uid)
    finally:
        try:
            con.logout()
        except Exception:
            pass


def baixar_anexo(conta, senha: str, uid: str, nome: str) -> tuple[str, bytes]:
    """Um anexo, pelo nome. Devolve (nome do arquivo, conteudo)."""
    con = _abrir_imap(conta, senha)
    try:
        con.select("INBOX", readonly=True)
        estado, dados = con.uid("FETCH", uid, "(BODY.PEEK[])")
        if estado != "OK" or not dados or not isinstance(dados[0], tuple):
            raise ErroCorreio("não achei essa mensagem no servidor")

        msg = email.message_from_bytes(dados[0][1], policy=email.policy.default)
        for parte in msg.walk():
            if parte.is_multipart():
                continue
            achado = _texto_cabecalho(parte.get_filename())
            if achado and achado == nome:
                carga = parte.get_payload(decode=True) or b""
                if len(carga) > MAX_ANEXO_BYTES:
                    raise ErroCorreio("esse anexo é grande demais para abrir aqui")
                return achado, carga
        raise ErroCorreio("não achei esse anexo na mensagem")
    finally:
        try:
            con.logout()
        except Exception:
            pass


def arquivar(conta, senha: str, uid: str) -> bool:
    """
    Tira da caixa de entrada.

    Nao apaga: marca como lida e move para o arquivo morto do servidor. Se o
    servidor nao tiver pasta de arquivo, so marca como lida - melhor nao fazer
    nada do que apagar mensagem de cliente.
    """
    con = _abrir_imap(conta, senha)
    try:
        con.select("INBOX")
        con.uid("STORE", uid, "+FLAGS", "(\\Seen)")

        for pasta in ("Archive", "Arquivo", "[Gmail]/Todos os e-mails", "[Gmail]/All Mail"):
            try:
                estado, _ = con.uid("COPY", uid, f'"{pasta}"')
            except Exception:
                continue
            if estado == "OK":
                con.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                con.expunge()
                return True
        return False
    finally:
        try:
            con.logout()
        except Exception:
            pass


def _uids_validos(uids) -> list[str]:
    """
    So numeros, sem repetir, na ordem em que vieram.

    O UID entra no comando IMAP como texto. Um "1:*" vindo da tela marcaria a
    caixa inteira; um "1 FLAGS" quebraria o comando. Numero ou nada.
    """
    achados: list[str] = []
    for uid in uids or []:
        limpo = str(uid).strip()
        if re.fullmatch(r"\d{1,12}", limpo) and limpo not in achados:
            achados.append(limpo)
    return achados


def marcar_lidas(conta, senha: str, uids, lido: bool = True) -> int:
    """
    Marca (ou desmarca) como lidas. Nao move, nao apaga, nao abre nada.

    E a mesma marca que o webmail poe quando a pessoa abre a mensagem; o
    corpo continua no servidor.
    """
    lista = _uids_validos(uids)
    if not lista:
        return 0
    con = _abrir_imap(conta, senha)
    try:
        estado, _ = con.select("INBOX")
        if estado != "OK":
            raise ErroCorreio("não consegui abrir a caixa de entrada")
        estado, _ = con.uid("STORE", ",".join(lista), "+FLAGS" if lido else "-FLAGS", "(\\Seen)")
        if estado != "OK":
            raise ErroCorreio("o servidor não aceitou marcar as mensagens")
        return len(lista)
    finally:
        try:
            con.logout()
        except Exception:
            pass


def sinalizar(conta, senha: str, uids, sim: bool = True) -> int:
    """
    Poe (ou tira) a estrela. E a marca \\Flagged do IMAP - a mesma estrela do
    Gmail e a "sinalizada" do Outlook -, entao aparece igual no webmail.
    """
    lista = _uids_validos(uids)
    if not lista:
        return 0
    con = _abrir_imap(conta, senha)
    try:
        estado, _ = con.select("INBOX")
        if estado != "OK":
            raise ErroCorreio("não consegui abrir a caixa de entrada")
        estado, _ = con.uid("STORE", ",".join(lista), "+FLAGS" if sim else "-FLAGS", "(\\Flagged)")
        if estado != "OK":
            raise ErroCorreio("o servidor não aceitou a estrela")
        return len(lista)
    finally:
        try:
            con.logout()
        except Exception:
            pass


def arquivar_varias(conta, senha: str, uids) -> dict:
    """
    Tira varias da caixa de entrada numa conexao so.

    A mesma regra de `arquivar`: copia para a pasta de arquivo e so entao
    tira da caixa; sem pasta de arquivo no servidor, so marca como lida.
    Nada e apagado sem antes existir a copia.
    """
    lista = _uids_validos(uids)
    if not lista:
        return {"arquivadas": 0, "so_lidas": 0}
    con = _abrir_imap(conta, senha)
    try:
        con.select("INBOX")
        con.uid("STORE", ",".join(lista), "+FLAGS", "(\\Seen)")
        destino = ""
        for pasta in ("Archive", "Arquivo", "[Gmail]/Todos os e-mails", "[Gmail]/All Mail"):
            try:
                estado, _ = con.uid("COPY", lista[0], f'"{pasta}"')
            except Exception:
                continue
            if estado == "OK":
                destino = pasta
                break
        if not destino:
            return {"arquivadas": 0, "so_lidas": len(lista)}

        movidas = [lista[0]]
        for uid in lista[1:]:
            try:
                estado, _ = con.uid("COPY", uid, f'"{destino}"')
            except Exception:
                continue
            if estado == "OK":
                movidas.append(uid)
        con.uid("STORE", ",".join(movidas), "+FLAGS", "(\\Deleted)")
        con.expunge()
        return {"arquivadas": len(movidas), "so_lidas": len(lista) - len(movidas)}
    finally:
        try:
            con.logout()
        except Exception:
            pass


_LIXEIRAS = ("[Gmail]/Lixeira", "[Gmail]/Trash", "Trash", "Lixeira", "Deleted Items", "Deleted Messages",
             "Itens Excluídos", "INBOX.Trash", "INBOX.Lixeira")


def _pasta_lixeira(con) -> str:
    """
    A lixeira do servidor: a pasta marcada \\Trash (RFC 6154 - o Gmail marca a
    dele, com o nome na lingua da conta) ou, sem marca, um nome conhecido.
    """
    try:
        estado, linhas = con.list()
    except Exception:
        estado, linhas = "NO", []
    nomes = []
    for linha in linhas or []:
        texto = linha.decode("utf-8", "replace") if isinstance(linha, bytes) else str(linha)
        casou = re.match(r'\((?P<marcas>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<nome>.+)$', texto.strip())
        if not casou:
            continue
        nome = casou.group("nome").strip().strip('"')
        if "\\trash" in casou.group("marcas").lower():
            return nome
        nomes.append(nome)
    for candidato in _LIXEIRAS:
        if candidato in nomes:
            return candidato
    return ""


def excluir_varias(conta, senha: str, uids) -> dict:
    """
    Manda para a lixeira do servidor, numa conexao so.

    Nao apaga de vez: copia para a lixeira e so entao tira da caixa - dali a
    pessoa recupera pelo webmail ate a lixeira ser esvaziada (o Gmail esvazia
    sozinho depois de 30 dias). Servidor sem lixeira: nada sai da caixa.
    """
    lista = _uids_validos(uids)
    if not lista:
        return {"excluidas": 0, "sem_lixeira": False}
    con = _abrir_imap(conta, senha)
    try:
        lixeira = _pasta_lixeira(con)
        if not lixeira:
            return {"excluidas": 0, "sem_lixeira": True}
        estado, _ = con.select("INBOX")
        if estado != "OK":
            raise ErroCorreio("não consegui abrir a caixa de entrada")
        movidas = []
        for uid in lista:
            try:
                estado, _ = con.uid("COPY", uid, f'"{lixeira}"')
            except Exception:
                continue
            if estado == "OK":
                movidas.append(uid)
        if movidas:
            con.uid("STORE", ",".join(movidas), "+FLAGS", "(\\Deleted)")
            con.expunge()
        return {"excluidas": len(movidas), "sem_lixeira": False}
    finally:
        try:
            con.logout()
        except Exception:
            pass


# -------------------------------------------------------------- enviar


def montar_email(conta, *, para: list[str], assunto: str, corpo: str,
                 cc: list[str] | None = None, cco: list[str] | None = None,
                 anexos: list[Path] | None = None,
                 responder_a: str = "") -> EmailMessage:
    """
    Monta a mensagem, com assinatura da conta no fim do texto.

    Separada do envio de proposito: assim da para mostrar exatamente o que vai
    sair - "ver como vai chegar" - sem nada ter saido ainda.
    """
    msg = EmailMessage()
    msg["From"] = formataddr((conta.nome or "", conta.email))
    msg["To"] = ", ".join(para)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if assunto:
        msg["Subject"] = assunto
    if responder_a:
        msg["In-Reply-To"] = responder_a
        msg["References"] = responder_a

    texto = corpo.rstrip()
    if conta.assinatura.strip():
        texto += "\n\n--\n" + conta.assinatura.strip()
    msg.set_content(texto)

    for caminho in (anexos or []):
        alvo = Path(caminho)
        if not alvo.exists():
            raise ErroCorreio(f"não achei o anexo {alvo.name}")
        dados = alvo.read_bytes()
        if len(dados) > MAX_ANEXO_BYTES:
            raise ErroCorreio(f"{alvo.name} passa do limite de 20 MB por anexo")
        tipo, _, sub = _tipo_de(alvo).partition("/")
        msg.add_attachment(dados, maintype=tipo, subtype=sub, filename=alvo.name)

    return msg


def _tipo_de(alvo: Path) -> str:
    import mimetypes

    tipo, _ = mimetypes.guess_type(alvo.name)
    return tipo or "application/octet-stream"


def enviar(conta, senha: str, msg: EmailMessage, cco: list[str] | None = None) -> dict:
    """Entrega a mensagem ao servidor de saida da propria conta."""
    destinos = [e for _, e in getaddresses(
        [str(msg.get("To", "")), str(msg.get("Cc", ""))]
    ) if e]
    destinos += [e for e in (cco or []) if e]
    if not destinos:
        raise ErroCorreio("essa mensagem não tem destinatário")

    con = _abrir_smtp(conta, senha)
    try:
        con.send_message(msg, from_addr=conta.email, to_addrs=destinos)
    except Exception as exc:
        raise _erro_amigavel(exc, "saída") from exc
    finally:
        try:
            con.quit()
        except Exception:
            pass

    return {
        "para": destinos,
        "assunto": str(msg.get("Subject", "")),
        "quando": datetime.now().isoformat(timespec="seconds"),
        "anexos": [p.get_filename() for p in msg.iter_attachments()],
    }


def enderecos(texto: str) -> list[str]:
    """
    Le "Fulano <a@b.com>, c@d.com" e devolve so os enderecos validos.

    O ponto e virgula vira virgula antes de qualquer coisa. O Outlook separa
    destinatarios com ponto e virgula, e quem trabalha em escritorio cola essa
    lista aqui - mas na regra do e-mail o ponto e virgula fecha um grupo, e o
    leitor padrao devolve lista vazia para "a@b.com; c@d.com". Um campo "Para"
    preenchido que nao envia para ninguem e pior que um erro.
    """
    achados = []
    limpo = (texto or "").replace(";", ",")
    for _, endereco in getaddresses([limpo]):
        limpo = endereco.strip().lower()
        if limpo and "@" in limpo and limpo not in achados:
            achados.append(limpo)
    return achados


def resumo_do_envio(conta, para: list[str], anexos: list[str], confirmar: bool) -> str:
    """A frase que a tela mostra antes de enviar."""
    quem = ", ".join(para[:3]) + ("…" if len(para) > 3 else "")
    frase = f"Vou enviar para {quem}"
    if anexos:
        frase += f" com {len(anexos)} anexo(s)"
    frase += f", usando a sua conta {conta.email}."
    frase += " O envio sai do seu servidor de e-mail, não do meu."
    if confirmar:
        frase += " Vou pedir sua confirmação antes."
    return frase


# ------------------------------------------------------- rascunho por IA


INSTRUCAO_RESPOSTA = """Voce e assistente de um advogado brasileiro. Escreva
APENAS o corpo de uma resposta curta ao e-mail abaixo, em portugues do Brasil.

Regras:
- 3 a 6 linhas, tom profissional e cordial, sem formalidade excessiva
- responda o que foi perguntado; nao invente fato, prazo, numero nem promessa
- se o e-mail pede algo que voce nao sabe se foi feito, escreva como intencao
  ("vou verificar", "envio ainda hoje"), nunca como fato consumado
- nao escreva assunto, nao escreva saudacao de despedida com nome, nao
  escreva assinatura: o programa acrescenta a assinatura da conta
- nao use marcacao, nem asteriscos, nem listas"""


def sugerir_resposta(cliente, mensagem: Mensagem, quem_assina: str = "") -> str:
    """
    Escreve um rascunho de resposta, sob demanda.

    Sob demanda de proposito. Rodar o modelo em cada mensagem que chega custaria
    perto de um minuto por e-mail nesta maquina - a caixa de entrada demoraria
    uma hora para abrir. Prazo sai por regra, instantaneo; texto sai por modelo,
    e so quando alguem clica.

    O que volta e rascunho, nunca envio: quem le decide.
    """
    contexto = (
        f"De: {mensagem.de_nome} <{mensagem.de_email}>\n"
        f"Assunto: {mensagem.assunto}\n\n"
        f"{mensagem.corpo[:3000]}"
    )
    instrucao = INSTRUCAO_RESPOSTA
    if quem_assina:
        instrucao += f"\n- quem responde e {quem_assina}"

    resposta = cliente.ask(instrucao, contexto)
    return _limpar_rascunho(resposta)


def _limpar_rascunho(texto: str) -> str:
    """
    Tira o que o modelo insiste em acrescentar apesar da instrucao.

    Modelo pequeno costuma devolver "Assunto: ..." na primeira linha e uma
    assinatura inventada no fim. Assinatura inventada num e-mail de escritorio
    e nome errado saindo com OAB errada - por isso some aqui, e a assinatura de
    verdade e a da conta.
    """
    linhas = [l.rstrip() for l in (texto or "").strip().split("\n")]

    while linhas and re.match(r"^\s*(assunto|subject|re)\s*:", linhas[0], re.I):
        linhas.pop(0)
    while linhas and not linhas[0].strip():
        linhas.pop(0)

    # Corta a partir de um tracejado de assinatura, ou de onde o modelo
    # comeca a repetir o proprio pedido ("Pedido: ...") ou o contexto.
    for i, linha in enumerate(linhas):
        if (re.fullmatch(r"\s*-{2,}\s*", linha)
                or re.match(r"^\s*(pedido|texto atual do e-mail|instru[cç][aã]o)\s*:", linha, re.I)):
            linhas = linhas[:i]
            break

    limpo = "\n".join(linhas).strip()
    limpo = re.sub(r"\*\*(.+?)\*\*", r"\1", limpo)
    limpo = re.sub(r"^\s*[*-]\s+", "", limpo, flags=re.M)
    return limpo


# ------------------------------------------------ reescrever no Escrever

# Os atalhos do "Pedir aqui" viram pedidos com palavras exatas: modelo pequeno
# segue melhor "reescreva mais formal" do que um rotulo de botao.
PEDIDOS_PRONTOS = {
    "formal": "Reescreva o e-mail em tom mais formal, como um advogado escreve a um cliente ou a outro escritório. Mantenha tudo o que o texto diz.",
    "resumir": "Reescreva o e-mail mais curto, com as mesmas informações, sem perder nome, data, valor ou pedido que estejam nele.",
}

SISTEMA_EMAIL = """Voce ajuda um advogado brasileiro a escrever um e-mail. Responda
em portugues do Brasil.

Devolva APENAS o corpo do e-mail, pronto para enviar: sem assunto, sem
explicar o que mudou, sem aspas em volta, sem marcacao, sem asteriscos.

Nunca invente nome, data, valor, prazo, numero de processo ou promessa que nao
estejam no texto ou no pedido. Se faltar informacao, deixe a lacuna entre
colchetes, por exemplo [DATA].

Nao escreva assinatura nem despedida com nome: o programa acrescenta a
assinatura da conta.

Voce NAO conhece a tela deste programa. Nunca diga onde clicar."""


def reescrever_email(cliente, pedido: str, assunto: str = "", corpo: str = "") -> str:
    """
    O corpo do e-mail reescrito pelo modelo, a pedido.

    Volta como sugestao: a tela mostra, e so fica no e-mail se a pessoa
    mantiver. Nada sai daqui sem passar pelo Enviar de sempre.
    """
    instrucao = PEDIDOS_PRONTOS.get(pedido, pedido).strip()
    if not instrucao:
        raise ValueError("diga o que mudar no e-mail")
    if pedido in PEDIDOS_PRONTOS and not corpo.strip():
        raise ValueError("escreva o texto do e-mail antes - não há o que reescrever")
    contexto = (f"Assunto: {assunto.strip() or '(sem assunto)'}\n\n"
                f"Texto atual do e-mail:\n{corpo.strip()[:4000] or '(vazio)'}")
    resposta = cliente.ask(f"Pedido: {instrucao}", contexto, sistema=SISTEMA_EMAIL)
    limpo = _limpar_rascunho(resposta)
    if not limpo:
        raise ValueError("o modelo devolveu um texto vazio - tente de novo")
    return limpo


# ------------------------------------------------ resumo da caixa

# O modelo so ve o que a lista ja tem: remetente, assunto, data e as marcas do
# servidor. O corpo das mensagens continua no servidor - e a promessa da tela.
RESUMO_MAX_MENSAGENS = 30

INSTRUCAO_RESUMO_CAIXA = """Abaixo esta a lista da caixa de entrada de um
advogado: so remetente, assunto e marcas. Voce NAO leu o texto das mensagens.

Em duas ou tres frases curtas, em portugues do Brasil, diga o que parece pedir
atencao primeiro e por que, citando remetente e assunto. Nao invente o
conteudo das mensagens, nao invente prazo, nao de conselho juridico. Sem
listas, sem marcacao, sem titulo."""


def _quem(m: dict) -> str:
    return (m.get("de_cadastro") or m.get("de_nome") or m.get("de_email") or "?").strip()


def pede_resposta(m: dict) -> bool:
    """A mesma regra da tela: nao respondida e (nao lida ou com prazo)."""
    return not m.get("respondido") and (not m.get("lido") or bool(m.get("prazo")))


def resumo_por_regra(mensagens: list[dict]) -> dict:
    """
    O resumo que sai na hora, sem modelo: contagem, quem mais escreveu e os
    prazos achados no assunto. Tudo o que diz esta nos cabecalhos.
    """
    total = len(mensagens)
    pedem = [m for m in mensagens if pede_resposta(m)]
    nao_lidas = sum(1 for m in mensagens if not m.get("lido"))
    com_anexo = sum(1 for m in mensagens if m.get("tem_anexo"))
    clientes = sum(1 for m in mensagens if m.get("de_cadastro"))

    contagem: dict[str, int] = {}
    for m in mensagens:
        contagem[_quem(m)] = contagem.get(_quem(m), 0) + 1
    remetentes = sorted(contagem.items(), key=lambda x: (-x[1], x[0].lower()))[:3]

    prazos = sorted(
        ({"prazo": m["prazo"], "assunto": m.get("assunto", ""), "de": _quem(m), "uid": m.get("uid", "")}
         for m in mensagens if m.get("prazo") and not m.get("respondido")),
        key=lambda p: p["prazo"],
    )[:3]
    return {
        "total": total,
        "pedem_resposta": len(pedem),
        "nao_lidas": nao_lidas,
        "com_anexo": com_anexo,
        "de_clientes": clientes,
        "remetentes": [{"nome": n, "quantas": q} for n, q in remetentes],
        "prazos": prazos,
    }


def resumir_caixa(cliente, mensagens: list[dict]) -> str:
    """Duas ou tres frases do modelo, a partir so dos cabecalhos."""
    linhas = []
    for m in mensagens[:RESUMO_MAX_MENSAGENS]:
        marcas = []
        if not m.get("lido"):
            marcas.append("não lida")
        if m.get("respondido"):
            marcas.append("respondida")
        if m.get("prazo"):
            marcas.append(f"prazo {m['prazo']}")
        if m.get("de_cadastro"):
            marcas.append("cliente")
        if m.get("tem_anexo"):
            marcas.append("com anexo")
        linhas.append(f"- De: {_quem(m)} | Assunto: {m.get('assunto', '')[:140]}"
                      + (f" | {', '.join(marcas)}" if marcas else ""))
    if not linhas:
        return ""
    resposta = cliente.ask(INSTRUCAO_RESUMO_CAIXA, "\n".join(linhas), sistema=INSTRUCAO_RESUMO_CAIXA)
    limpo = re.sub(r"^\s*(resumo|em resumo)[^\n:]{0,30}:\s*", "", (resposta or "").strip(), flags=re.I)
    limpo = re.sub(r"\*\*(.+?)\*\*", r"\1", limpo)
    return limpo.strip()


def chave_do_resumo(conta_id: str, mensagens: list[dict]) -> str:
    """
    A chave do cache: a conta e as mensagens que o modelo leria.

    So os UIDs, sem as marcas. Abrir uma mensagem muda "lida" e nao pode
    custar mais um minuto de modelo; chegar mensagem nova, sim.
    """
    import hashlib

    uids = ",".join(str(m.get("uid", "")) for m in mensagens[:RESUMO_MAX_MENSAGENS])
    return hashlib.sha1(f"{conta_id}|{uids}".encode("utf-8")).hexdigest()[:16]


class ResumosDaCaixa:
    """
    O resumo do modelo em segundo plano, um de cada vez, guardado por chave.

    A tela nunca espera por ele: pede, recebe "resumindo" e pergunta de novo
    depois. Um pedido novo enquanto outro roda fica na fila - so o ultimo,
    porque o de antes ja nao e a caixa que a pessoa esta vendo.
    """

    LIMITE = 30

    def __init__(self) -> None:
        import threading
        from collections import OrderedDict

        self._trava = threading.Lock()
        self._feitos: OrderedDict[str, dict] = OrderedDict()
        self._rodando = ""
        self._proximo: tuple[str, list[dict], object] | None = None
        self.threads: list = []

    def estado(self, chave: str) -> dict:
        with self._trava:
            if chave in self._feitos:
                return dict(self._feitos[chave])
            if chave == self._rodando:
                return {"estado": "resumindo"}
            if self._proximo and self._proximo[0] == chave:
                return {"estado": "na_fila"}
        return {"estado": "nenhum"}

    def pedir(self, chave: str, mensagens: list[dict], cliente) -> dict:
        import threading

        with self._trava:
            if chave in self._feitos and self._feitos[chave].get("estado") == "pronto":
                return dict(self._feitos[chave])
            if chave == self._rodando:
                return {"estado": "resumindo"}
            if self._rodando:
                self._proximo = (chave, list(mensagens), cliente)
                return {"estado": "na_fila"}
            self._feitos.pop(chave, None)
            self._rodando = chave
        t = threading.Thread(target=self._trabalhar, args=(chave, list(mensagens), cliente), daemon=True)
        self.threads.append(t)
        t.start()
        return {"estado": "resumindo"}

    def _trabalhar(self, chave: str, mensagens: list[dict], cliente) -> None:
        from datetime import datetime as _dt

        try:
            texto = resumir_caixa(cliente, mensagens)
            feito = {"estado": "pronto", "texto": texto, "quando": _dt.now().isoformat(timespec="seconds")}
            if not texto:
                feito = {"estado": "falhou", "erro": "o modelo devolveu um texto vazio"}
        except Exception as exc:  # o erro vai para a tela, nao derruba nada
            feito = {"estado": "falhou", "erro": str(exc)}
        with self._trava:
            self._feitos[chave] = feito
            while len(self._feitos) > self.LIMITE:
                self._feitos.popitem(last=False)
            self._rodando = ""
            proximo, self._proximo = self._proximo, None
        if proximo:
            self.pedir(*proximo)


# ------------------------------------------------------- registro de envios


class RegistroEnvios:
    """
    O que ja saiu daqui.

    O rodape da tela promete "ver registro de envios", e sem um lugar para
    olhar essa promessa e enfeite. Guarda destinatario, assunto e quando -
    nao guarda o corpo: o e-mail enviado ja esta na pasta de enviados do
    servidor, e repetir o texto aqui seria uma segunda copia sem dono.
    """

    def __init__(self, caminho: Path) -> None:
        import json

        self.caminho = Path(caminho)
        self.itens: list[dict] = []
        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                self.itens = bruto.get("envios", []) if isinstance(bruto, dict) else []
            except (json.JSONDecodeError, OSError):
                self.itens = []

    def anotar(self, conta_email: str, resultado: dict) -> dict:
        item = {
            "quando": resultado.get("quando", ""),
            "de": conta_email,
            "para": resultado.get("para", []),
            "assunto": resultado.get("assunto", ""),
            "anexos": [a for a in (resultado.get("anexos") or []) if a],
        }
        self.itens.insert(0, item)
        self.salvar()
        return item

    def salvar(self) -> None:
        import json

        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps({"versao": 1, "envios": self.itens[:500]}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def para_tela(self, limite: int = 50) -> dict:
        return {"envios": self.itens[:limite], "total": len(self.itens)}
