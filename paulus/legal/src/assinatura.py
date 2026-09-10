"""
PAULUS - Assinatura de PDF.

Assina em PAdES com o certificado A1 da pessoa, nesta maquina. O arquivo, a
chave e a senha nao saem daqui em momento nenhum: nao ha servico de assinatura
no meio, nao ha upload.

Duas coisas neste modulo existem por causa de risco juridico, nao de gosto:

1. O selo visivel e o desenho, nao a assinatura. A assinatura e o objeto
   criptografico que cobre o documento inteiro. Por isso um PDF tem UMA
   assinatura mesmo quando o selo aparece em doze paginas - carimbar nao
   assina, e prometer o contrario seria mentira com consequencia.

2. Quem verifica precisa saber de onde vem o certificado. Um autoassinado
   produz assinatura integra e sem valor de ICP-Brasil. O resultado sempre
   carrega essa distincao, e a tela repete.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Tamanho do selo em pontos PDF (1 pt = 1/72 pol). ~8 x 2,2 cm.
SELO_LARGURA = 228
SELO_ALTURA = 62
MARGEM = 28

ESCOLHAS_PAGINA = {
    "todas": "Todas as páginas",
    "ultima": "Só a última página",
    "primeira_ultima": "Primeira e última",
    "intervalo": "Intervalo",
}


# ------------------------------------------------------------- o documento


@dataclass
class Documento:
    caminho: str = ""
    nome: str = ""
    paginas: int = 0
    mb: float = 0.0
    largura: float = 0.0        # da primeira pagina, em pontos
    altura: float = 0.0
    assinaturas: int = 0
    erro: str = ""

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados["ja_assinado"] = self.assinaturas > 0
        return dados


def ler(caminho: Path | str) -> Documento:
    """Quantas paginas, que tamanho, e se ja tem assinatura."""
    alvo = Path(caminho)
    if not alvo.exists():
        return Documento(erro="não achei esse arquivo")
    if alvo.suffix.lower() != ".pdf":
        return Documento(erro="só assino PDF - converta o arquivo antes")

    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(str(alvo))
    except Exception as exc:
        return Documento(erro=f"não consegui abrir o PDF: {exc}")

    try:
        total = len(doc)
        largura = altura = 0.0
        if total:
            pagina = doc[0]
            largura, altura = pagina.get_width(), pagina.get_height()
    finally:
        doc.close()

    return Documento(
        caminho=str(alvo),
        nome=alvo.name,
        paginas=total,
        mb=round(alvo.stat().st_size / (1024 * 1024), 2),
        largura=round(largura, 1),
        altura=round(altura, 1),
        assinaturas=_quantas_assinaturas(alvo),
    )


def _quantas_assinaturas(alvo: Path) -> int:
    from pyhanko.pdf_utils.reader import PdfFileReader

    try:
        with alvo.open("rb") as arq:
            leitor = PdfFileReader(arq)
            return len(leitor.embedded_signatures)
    except Exception:
        return 0


def pagina_png(caminho: Path | str, numero: int, largura: int = 1000) -> bytes:
    """
    Uma pagina desenhada como PNG, para a tela mostrar o documento.

    O desenho acontece aqui, no servidor, e nao com uma biblioteca de PDF
    baixada de CDN: o programa roda sem internet, e o documento e de cliente.
    """
    import io

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(caminho))
    try:
        # Sem isto o PDFium desenha a pagina e ignora os campos de formulario -
        # e o selo de uma assinatura e um campo de formulario. A pessoa veria a
        # pagina "limpa" e concluiria que o documento nao esta assinado.
        try:
            doc.init_forms()
        except Exception:
            pass

        indice = max(0, min(int(numero) - 1, len(doc) - 1))
        pagina = doc[indice]
        escala = max(min(largura / max(pagina.get_width(), 1), 4.0), 0.2)
        imagem = pagina.render(scale=escala, draw_annots=True, may_draw_forms=True).to_pil()
    finally:
        doc.close()

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------- quais paginas


def paginas_alvo(escolha: str, total: int, intervalo: str = "") -> list[int]:
    """
    Traduz a escolha da tela em numeros de pagina (contando de 1).

    Devolve sempre em ordem e sem repetir: pedir "1-3, 2, 12" nao pode virar
    dois selos em cima da pagina 2.
    """
    total = max(int(total), 0)
    if not total:
        return []

    if escolha == "ultima":
        return [total]
    if escolha == "primeira_ultima":
        return sorted({1, total})
    if escolha == "intervalo":
        return _do_intervalo(intervalo, total)
    return list(range(1, total + 1))


def _do_intervalo(texto: str, total: int) -> list[int]:
    """Le "1-3, 7, 12" e ignora com calma o que nao faz sentido."""
    achados: set[int] = set()
    for pedaco in re.split(r"[,;]", texto or ""):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        faixa = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", pedaco)
        if faixa:
            inicio, fim = int(faixa.group(1)), int(faixa.group(2))
            if inicio > fim:
                inicio, fim = fim, inicio
            achados.update(n for n in range(inicio, fim + 1) if 1 <= n <= total)
        elif pedaco.isdigit():
            numero = int(pedaco)
            if 1 <= numero <= total:
                achados.add(numero)
    return sorted(achados)


# ------------------------------------------------------------- o selo


def codigo_de(caminho: Path | str, quando: datetime) -> str:
    """
    Codigo curto para conferir a assinatura no registro.

    Sai do conteudo do arquivo original mais o instante: dois documentos
    diferentes nunca recebem o mesmo codigo, e o mesmo documento assinado duas
    vezes recebe codigos diferentes.
    """
    resumo = hashlib.sha256()
    resumo.update(Path(caminho).read_bytes())
    resumo.update(quando.isoformat().encode("utf-8"))
    return resumo.hexdigest()[:6].upper()


def texto_do_selo(selo: dict, cert, codigo: str, quando: datetime) -> str:
    """
    Monta o que aparece no selo, trocando os campos entre chaves.

    O texto e da pessoa; o programa so preenche {nome}, {cpf}, {data} e {hora}.
    O que a pessoa escolheu esconder - CPF, data, codigo - fica de fora mesmo.
    """
    nome = getattr(cert, "titular", "") or ""
    documento = getattr(cert, "documento", "") or ""
    mostrado = documento if selo.get("mostrar_cpf", True) else _mascarar(documento)

    corpo = str(selo.get("texto") or "").format_map(
        _Campos({
            "nome": nome,
            "cpf": mostrado,
            "cnpj": mostrado,
            "documento": mostrado,
            "data": quando.strftime("%d/%m/%Y"),
            "hora": quando.strftime("%H:%M"),
        })
    )

    linhas = [l for l in corpo.split("\n") if l.strip()]

    if selo.get("mostrar_cpf", True) and documento and documento not in corpo:
        linhas.append(documento)
    if selo.get("mostrar_data", True):
        emissor = getattr(cert, "emissor", "") or ""
        carimbo = quando.strftime("%d/%m/%Y %H:%M")
        linhas.append(f"{carimbo} · {emissor}" if emissor else carimbo)
    if selo.get("mostrar_codigo", True):
        linhas.append(f"confira no PAULUS · código {codigo}")

    return "\n".join(linhas) or nome


class _Campos(dict):
    """Campo desconhecido no texto fica como esta, em vez de derrubar tudo."""

    def __missing__(self, chave):
        return "{" + chave + "}"


def _mascarar(documento: str) -> str:
    digitos = re.sub(r"\D", "", documento)
    if len(digitos) == 11:
        return f"***.{digitos[3:6]}.{digitos[6:9]}-**"
    return ""


def caixa(posicao: str, largura: float, altura: float) -> tuple[int, int, int, int]:
    """Onde o selo cai na pagina, em pontos, a partir do canto escolhido."""
    largura, altura = float(largura or 595), float(altura or 842)

    if posicao == "rodape_esquerda":
        x = MARGEM
        y = MARGEM
    elif posicao == "rodape_centro":
        x = (largura - SELO_LARGURA) / 2
        y = MARGEM
    elif posicao == "topo_direita":
        x = largura - SELO_LARGURA - MARGEM
        y = altura - SELO_ALTURA - MARGEM
    else:  # rodape_direita
        x = largura - SELO_LARGURA - MARGEM
        y = MARGEM

    x = max(0, min(x, largura - SELO_LARGURA))
    y = max(0, min(y, altura - SELO_ALTURA))
    return int(x), int(y), int(x + SELO_LARGURA), int(y + SELO_ALTURA)


def _estilo(texto: str, imagem: Path | None):
    """O desenho do selo: moldura, texto pequeno e, se houver, a rubrica."""
    from pyhanko.pdf_utils.layout import (
        AxisAlignment,
        Margins,
        SimpleBoxLayoutRule,
    )
    from pyhanko.pdf_utils.font.basic import SimpleFontEngineFactory
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStampStyle

    fundo = None
    if imagem and Path(imagem).exists():
        try:
            from pyhanko.pdf_utils.images import PdfImage

            fundo = PdfImage(str(imagem))
        except Exception:
            fundo = None

    return TextStampStyle(
        stamp_text="%(corpo)s",
        border_width=1,
        background=fundo,
        background_opacity=0.35 if fundo else 0.6,
        background_layout=SimpleBoxLayoutRule(
            x_align=AxisAlignment.ALIGN_MIN,
            y_align=AxisAlignment.ALIGN_MID,
            margins=Margins(left=4, right=4, top=4, bottom=4),
        ),
        # O padrao do pyHanko e Courier. Num documento juridico o selo em
        # monoespacada destoa da pagina inteira; Helvetica acompanha o texto.
        text_box_style=TextBoxStyle(
            font=SimpleFontEngineFactory("Helvetica", 0.5),
            font_size=6,
            leading=8,
        ),
    )


# --------------------------------------------------------------- assinar


@dataclass
class Resultado:
    destino: str = ""
    codigo: str = ""
    paginas: list[int] = field(default_factory=list)
    titular: str = ""
    icp_brasil: bool = False
    protegido: bool = False
    quando: str = ""
    erro: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def assinar(
    origem: Path | str,
    destino: Path | str,
    *,
    arquivo_pfx: Path | str,
    senha: str,
    selo: dict,
    escolha_paginas: str = "ultima",
    intervalo: str = "",
    posicao: str = "rodape_direita",
    ponto: tuple[float, float] | None = None,
    senha_pdf: str = "",
    motivo: str = "",
    imagem: Path | None = None,
) -> Resultado:
    """
    Assina o PDF e devolve o que aconteceu.

    O selo pode repetir em varias paginas; a assinatura e uma so, na primeira
    pagina escolhida. As demais recebem uma copia visual do selo, carimbada
    antes de assinar - ou seja, coberta pela assinatura, mas sem fingir ser
    outra assinatura.
    """
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import copy_into_new_writer
    from pyhanko.sign import fields, signers
    from pyhanko.stamp import TextStamp

    origem, destino = Path(origem), Path(destino)
    quando = datetime.now()

    doc = ler(origem)
    if doc.erro:
        return Resultado(erro=doc.erro)
    if not doc.paginas:
        return Resultado(erro="o PDF não tem páginas")

    alvos = paginas_alvo(escolha_paginas, doc.paginas, intervalo)
    if not alvos:
        return Resultado(erro="nenhuma página escolhida")

    # Proteger com senha reescreve o arquivo inteiro, e isso apaga assinatura
    # que ja estava la. Num contrato que a outra parte ja assinou, seria perder
    # a assinatura dela sem avisar - entao aqui recusa em vez de fazer.
    if senha_pdf and doc.assinaturas:
        return Resultado(
            erro=(
                f"este PDF já tem {doc.assinaturas} assinatura(s). Protegê-lo com senha "
                "apagaria essa assinatura. Assine sem a senha, ou proteja uma cópia do "
                "documento antes de qualquer assinatura."
            )
        )

    try:
        assinante = signers.SimpleSigner.load_pkcs12(
            pfx_file=str(arquivo_pfx), passphrase=senha.encode("utf-8")
        )
    except Exception as exc:
        return Resultado(erro=f"não consegui abrir o certificado: {exc}")
    if assinante is None:
        return Resultado(erro="senha do certificado incorreta")

    from certificado import ler as ler_cert

    cert = ler_cert(arquivo_pfx, senha)
    if cert.erro:
        return Resultado(erro=cert.erro)
    if cert.vencido:
        return Resultado(erro=f"o certificado venceu em {cert.valido_ate} - não dá para assinar")

    codigo = codigo_de(origem, quando)
    corpo = texto_do_selo(selo, cert, codigo, quando)
    estilo = _estilo(corpo, imagem)

    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        with origem.open("rb") as entrada:
            leitor = PdfFileReader(entrada)

            # Proteger com senha muda o arquivo inteiro, entao vem antes de
            # assinar: cifrar depois quebraria a assinatura recem-feita.
            if senha_pdf:
                escritor = copy_into_new_writer(leitor)
                escritor.encrypt(senha_pdf, senha_pdf)
            else:
                # PDF salvo pelo Word costuma trazer xref hibrido, e o modo
                # estrito se recusa a assinar. Recusar seria recusar a maioria
                # dos documentos reais de um escritorio: a assinatura sai
                # valida do mesmo jeito, so a leitura do arquivo e tolerante.
                hibrido = bool(leitor.xrefs.hybrid_xrefs_present)
                entrada.seek(0)
                escritor = IncrementalPdfFileWriter(entrada, strict=not hibrido)

            principal, repetidas = alvos[0], alvos[1:]

            for numero in repetidas:
                x, y, _, _ = _posicao_na_pagina(escritor, numero, posicao, ponto, doc)
                TextStamp(escritor, estilo, text_params={"corpo": corpo}).apply(
                    dest_page=numero - 1, x=x, y=y
                )

            x1, y1, x2, y2 = _posicao_na_pagina(escritor, principal, posicao, ponto, doc, caixa_toda=True)
            campo = fields.SigFieldSpec(
                sig_field_name=f"PAULUS {quando.strftime('%Y%m%d%H%M%S')}",
                on_page=principal - 1,
                box=(x1, y1, x2, y2),
            )
            meta = signers.PdfSignatureMetadata(
                field_name=campo.sig_field_name,
                reason=motivo or "Assinatura do documento",
                name=cert.titular,
                subfilter=fields.SigSeedSubFilter.PADES,
            )
            assinador = signers.PdfSigner(
                meta, signer=assinante, stamp_style=estilo, new_field_spec=campo
            )

            with destino.open("wb") as saida:
                assinador.sign_pdf(
                    escritor, output=saida, appearance_text_params={"corpo": corpo}
                )
    except Exception as exc:
        return Resultado(erro=f"não consegui assinar: {exc}")

    return Resultado(
        destino=str(destino),
        codigo=codigo,
        paginas=alvos,
        titular=cert.titular,
        icp_brasil=cert.icp_brasil,
        protegido=bool(senha_pdf),
        quando=quando.isoformat(timespec="seconds"),
    )


def _posicao_na_pagina(escritor, numero: int, posicao: str, ponto, doc: Documento,
                       caixa_toda: bool = False):
    """
    Onde o selo cai. O arrasto na tela manda; sem arrasto, vale o canto.

    A tela envia a posicao em pontos do PDF, com origem no canto de cima - o
    PDF conta do canto de baixo, entao a conversao acontece aqui, num lugar so.
    """
    largura, altura = doc.largura or 595, doc.altura or 842
    if ponto:
        x = max(0.0, min(float(ponto[0]), largura - SELO_LARGURA))
        y = max(0.0, min(altura - float(ponto[1]) - SELO_ALTURA, altura - SELO_ALTURA))
        pontos = (int(x), int(y), int(x + SELO_LARGURA), int(y + SELO_ALTURA))
    else:
        pontos = caixa(posicao, largura, altura)
    return pontos if caixa_toda else pontos


# -------------------------------------------------------------- verificar


def verificar(caminho: Path | str, senha_pdf: str = "") -> list[dict]:
    """
    O que as assinaturas de um PDF dizem de si.

    Sem internet: nao consulta lista de revogacao nem baixa cadeia. Entao
    responde o que da para responder offline - se o documento foi mexido depois
    de assinado, quem assinou e quem emitiu o certificado - e nao afirma que a
    assinatura e valida perante a ICP-Brasil, porque isso exigiria as raizes
    oficiais e uma consulta que este programa nao faz.
    """
    from pyhanko.pdf_utils.reader import PdfFileReader

    from certificado import e_icp

    alvo = Path(caminho)
    if not alvo.exists():
        return []

    # Sem as raizes da ICP-Brasil no disco, montar a cadeia sempre falha, e o
    # pyHanko registra isso como erro. E ruido esperado, nao problema: a
    # confianca na cadeia nao e o que este modulo afirma.
    import logging

    logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)
    logging.getLogger("pyhanko.sign.validation").setLevel(logging.CRITICAL)

    achados: list[dict] = []

    try:
        with alvo.open("rb") as arq:
            leitor = PdfFileReader(arq, strict=False)
            if leitor.security_handler is not None:
                if not senha_pdf:
                    return [{"erro": "o PDF está protegido por senha - informe a senha para conferir"}]
                leitor.decrypt(senha_pdf)
            for assinada in leitor.embedded_signatures:
                achados.append(_uma_assinatura(assinada, e_icp))
    except Exception as exc:
        return [{"erro": f"não consegui ler as assinaturas: {exc}"}]

    return achados


def _uma_assinatura(assinada, e_icp) -> dict:
    from pyhanko.sign.validation import validate_pdf_signature

    quem = emissor = ""
    try:
        cert = assinada.signer_cert
        quem = _cn_asn1(cert.subject.native)
        emissor = _cn_asn1(cert.issuer.native)
    except Exception:
        pass

    # Sem contexto de validacao de propriedade: montar a cadeia exigiria as
    # raizes da ICP-Brasil e consulta de revogacao pela internet. O que da para
    # afirmar offline e o que interessa aqui - o documento foi mexido depois de
    # assinado, ou nao.
    intacta = None
    cobre_tudo = None
    try:
        estado = validate_pdf_signature(assinada, signer_validation_context=None)
        intacta = bool(estado.intact)
        cobre_tudo = "ENTIRE_FILE" in str(estado.coverage)
    except Exception:
        pass

    return {
        "titular": quem,
        "emissor": emissor,
        "icp_brasil": e_icp(emissor),
        "quando": _quando_de(assinada),
        "intacta": intacta,
        "cobre_documento_todo": cobre_tudo,
    }


def _cn_asn1(nome: dict) -> str:
    bruto = nome.get("common_name") if isinstance(nome, dict) else ""
    return str(bruto or "").split(":")[0].strip()


def _quando_de(assinada) -> str:
    for atributo in ("self_reported_timestamp", "signer_reported_dt"):
        valor = getattr(assinada, atributo, None)
        if isinstance(valor, datetime):
            return valor.strftime("%d/%m/%Y %H:%M")
    return ""


# --------------------------------------------------------------- registro


class Registro:
    """
    Historico das assinaturas feitas aqui.

    O selo traz um codigo; sem um lugar para consultar esse codigo, ele seria
    enfeite. E quando alguem pergunta "quando isso foi assinado?", a resposta
    tem que existir fora da memoria de quem assinou.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.itens: list[dict] = []
        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                self.itens = bruto.get("assinaturas", []) if isinstance(bruto, dict) else []
            except (json.JSONDecodeError, OSError):
                self.itens = []

    def anotar(self, resultado: Resultado, origem: Path | str) -> dict:
        item = {
            "quando": resultado.quando,
            "codigo": resultado.codigo,
            "documento": Path(origem).name,
            "origem": str(origem),
            "destino": resultado.destino,
            "titular": resultado.titular,
            "icp_brasil": resultado.icp_brasil,
            "paginas": resultado.paginas,
            "protegido": resultado.protegido,
        }
        self.itens.insert(0, item)
        self.salvar()
        return item

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps({"versao": 1, "assinaturas": self.itens[:500]}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def procurar(self, codigo: str) -> dict | None:
        alvo = (codigo or "").strip().upper()
        return next((i for i in self.itens if i.get("codigo") == alvo), None)

    def para_tela(self, limite: int = 50) -> dict:
        return {"assinaturas": self.itens[:limite], "total": len(self.itens)}


def resumo_em_portugues(cert, doc: Documento, alvos: list[int], senha_pdf: str) -> str:
    """
    A frase que a tela mostra antes de assinar.

    Vale a pena ser exata: e a ultima coisa que a pessoa le antes de usar o
    certificado dela num documento.
    """
    quem = getattr(cert, "titular", "") or "seu certificado"
    tipo = getattr(cert, "tipo", "") or "certificado"

    if not alvos:
        onde = "em nenhuma página"
    elif len(alvos) == doc.paginas and doc.paginas > 1:
        onde = f"em todas as {doc.paginas} páginas"
    elif len(alvos) == 1:
        onde = f"na página {alvos[0]}"
    else:
        onde = "nas páginas " + ", ".join(str(n) for n in alvos)

    frase = f"Vou carimbar o selo {onde} e assinar o documento com o {tipo} de {quem}."
    if senha_pdf:
        frase += " O arquivo sai protegido por senha."
    if len(alvos) > 1:
        frase += " A assinatura digital é uma só e cobre o documento inteiro."
    frase += " Nada é enviado para a internet."
    return frase
