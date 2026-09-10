"""
PAULUS - Documento de texto.

Guarda o documento, conta versoes, e transforma o que o editor produz em PDF e
em DOCX.

O editor da tela escreve HTML, porque e o que um campo editavel do navegador
sabe produzir sem biblioteca nenhuma. Mas HTML nao e o documento: e a forma de
digitar. O documento de verdade e a lista de blocos que sai daqui - paragrafo,
alinhamento, trechos em negrito - e e dela que saem tanto o PDF quanto o DOCX.

Isso importa porque um caminho separado para cada formato produz dois
documentos diferentes com o mesmo nome. Num contrato, "a versao em PDF esta
diferente da versao em Word" nao e detalhe de formatacao.

O PDF e o formato canonico: e o que a tela de pre-visualizacao mostra, e o que
vai para a assinatura. O DOCX existe para quem precisa continuar editando no
Word, e a tela diz isso.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

# A4 com margens de 2,5 cm, como o wireframe pede.
MARGEM_CM = 2.5
FONTE_PADRAO = "Georgia"
CORPO_PT = 12

ALINHAMENTOS = {
    "esquerda": "Alinhado à esquerda",
    "centro": "Centralizado",
    "direita": "Alinhado à direita",
    "justificado": "Justificado",
}


@dataclass
class Trecho:
    """Um pedaco de texto com a mesma formatacao do inicio ao fim."""

    texto: str = ""
    negrito: bool = False
    italico: bool = False
    sublinhado: bool = False
    riscado: bool = False


@dataclass
class Bloco:
    """Um paragrafo, titulo ou item de lista."""

    tipo: str = "paragrafo"          # paragrafo | titulo1..3 | item | numerado
    alinhamento: str = "esquerda"
    trechos: list[Trecho] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "".join(t.texto for t in self.trechos)

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "alinhamento": self.alinhamento,
            "texto": self.texto,
            "trechos": [t.__dict__ for t in self.trechos],
        }


# ------------------------------------------------------------ ler o HTML


BLOCOS = {
    "p": "paragrafo", "div": "paragrafo",
    "h1": "titulo1", "h2": "titulo2", "h3": "titulo3",
    "li": "item",
}
MARCAS = {
    "b": "negrito", "strong": "negrito",
    "i": "italico", "em": "italico",
    "u": "sublinhado",
    "s": "riscado", "strike": "riscado", "del": "riscado",
}


class _Leitor(HTMLParser):
    """
    Le o HTML do editor e devolve blocos.

    Nao pretende entender HTML em geral: entende o que um campo editavel
    produz. Marcacao desconhecida vira texto, nunca some - perder texto de um
    contrato por causa de uma tag inesperada seria o pior resultado possivel.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocos: list[Bloco] = []
        self._atual: Bloco | None = None
        self._marcas: list[str] = []
        self._lista: list[str] = []       # pilha de ul/ol
        self._ignorar = 0

    # ---------------------------------------------------------- estrutura

    def _abrir(self, tipo: str, alinhamento: str = "") -> None:
        self._fechar()
        self._atual = Bloco(tipo=tipo, alinhamento=alinhamento or "esquerda")

    def _fechar(self) -> None:
        if self._atual and self._atual.trechos:
            self.blocos.append(self._atual)
        self._atual = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorar += 1
            return

        atributos = dict(attrs)
        if tag == "br":
            self._quebra()
            return
        if tag in ("ul", "ol"):
            self._lista.append(tag)
            return
        if tag in BLOCOS:
            tipo = BLOCOS[tag]
            if tag == "li":
                tipo = "numerado" if (self._lista and self._lista[-1] == "ol") else "item"
            self._abrir(tipo, _alinhamento(atributos))
            return
        if tag in MARCAS:
            self._marcas.append(MARCAS[tag])
            return
        # span com estilo: negrito e italico tambem chegam assim.
        if tag == "span":
            estilo = (atributos.get("style") or "").lower()
            if "bold" in estilo or "font-weight: 7" in estilo:
                self._marcas.append("negrito")
            elif "italic" in estilo:
                self._marcas.append("italico")
            elif "underline" in estilo:
                self._marcas.append("sublinhado")
            else:
                self._marcas.append("")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._ignorar = max(0, self._ignorar - 1)
            return
        if tag in ("ul", "ol"):
            if self._lista:
                self._lista.pop()
            return
        if tag in BLOCOS:
            self._fechar()
            return
        if tag in MARCAS or tag == "span":
            if self._marcas:
                self._marcas.pop()

    def handle_data(self, dados):
        if self._ignorar:
            return
        self._texto(dados)

    def _quebra(self) -> None:
        """<br> e quebra de verdade, dentro do paragrafo."""
        if self._atual is None:
            self._atual = Bloco()
        if self._atual.trechos:
            self._atual.trechos[-1].texto += "\n"
        else:
            self._atual.trechos.append(Trecho(texto="\n"))

    def _texto(self, bruto: str) -> None:
        texto = bruto.replace("\xa0", " ")

        # Espaco e quebra de linha ENTRE tags sao formatacao do HTML, nao
        # conteudo. Tratar isso como texto criava um paragrafo vazio a cada
        # linha do fonte - um documento de nove blocos virava dezessete, e o
        # PDF saia com o dobro de espaco entre as clausulas.
        if not texto.strip():
            if self._atual and self._atual.trechos:
                if not self._atual.trechos[-1].texto.endswith((" ", "\n")):
                    self._atual.trechos[-1].texto += " "
            return

        # Quebra de linha DENTRO do texto e espaco, na regra do HTML. Só o <br>
        # quebra. Sem isto, um paragrafo escrito em tres linhas no fonte saia
        # do PDF quebrado em tres linhas no meio da frase.
        texto = re.sub(r"\s+", " ", texto)

        if self._atual is None:
            self._atual = Bloco()

        marcas = set(self._marcas)
        self._atual.trechos.append(Trecho(
            texto=texto,
            negrito="negrito" in marcas,
            italico="italico" in marcas,
            sublinhado="sublinhado" in marcas,
            riscado="riscado" in marcas,
        ))

    def resultado(self) -> list[Bloco]:
        self._fechar()
        return self.blocos


def _alinhamento(atributos: dict) -> str:
    estilo = (atributos.get("style") or "").lower()
    for chave, valor in (("center", "centro"), ("right", "direita"), ("justify", "justificado")):
        if f"text-align: {chave}" in estilo or f"text-align:{chave}" in estilo:
            return valor
    return (atributos.get("align") or "").lower().replace("center", "centro") or "esquerda"


def ler_html(html: str) -> list[Bloco]:
    """O HTML do editor virando documento."""
    leitor = _Leitor()
    leitor.feed(html or "")
    leitor.close()
    return leitor.resultado()


def para_texto(blocos: list[Bloco]) -> str:
    """O documento em texto puro - para busca, contagem e para o assistente."""
    return "\n".join(b.texto for b in blocos).strip()


def contar(blocos: list[Bloco]) -> dict:
    """
    Palavras, caracteres e uma estimativa de paginas.

    Paginas so o gerador de PDF sabe de verdade; aqui e estimativa para a
    barra de status, e a tela de pre-visualizacao mostra o numero real.
    """
    texto = para_texto(blocos)
    palavras = len([p for p in re.split(r"\s+", texto) if p])
    return {
        "palavras": palavras,
        "caracteres": len(texto),
        "blocos": len(blocos),
        "paginas_estimadas": max(1, round(palavras / 450 + 0.4)),
    }


# ------------------------------------------------------------------ PDF


def para_pdf(blocos: list[Bloco], titulo: str = "", rodape: str = "") -> bytes:
    """
    O documento em PDF, no formato que sai para o cliente.

    Este e o formato canonico: e o que a pre-visualizacao mostra e o que vai
    para a assinatura. A pre-visualizacao desenha este mesmo PDF, entao o que
    aparece na tela e o arquivo, nao uma aproximacao em CSS.
    """
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    alinha = {
        "esquerda": TA_LEFT, "centro": TA_CENTER,
        "direita": TA_RIGHT, "justificado": TA_JUSTIFY,
    }
    # Georgia nao vem no reportlab; Times e a serifada equivalente e sempre
    # existe. Trocar sem avisar seria mudar a cara do documento em silencio,
    # entao a tela informa qual fonte o PDF usa.
    estilos = {
        "paragrafo": ParagraphStyle("corpo", fontName="Times-Roman", fontSize=CORPO_PT,
                                    leading=CORPO_PT * 1.5, spaceAfter=8),
        "titulo1": ParagraphStyle("t1", fontName="Times-Bold", fontSize=16,
                                  leading=20, spaceBefore=12, spaceAfter=10),
        "titulo2": ParagraphStyle("t2", fontName="Times-Bold", fontSize=13.5,
                                  leading=18, spaceBefore=10, spaceAfter=8),
        "titulo3": ParagraphStyle("t3", fontName="Times-Bold", fontSize=12,
                                  leading=16, spaceBefore=8, spaceAfter=6),
    }

    saida = io.BytesIO()
    doc = SimpleDocTemplate(
        saida, pagesize=A4,
        leftMargin=MARGEM_CM * cm, rightMargin=MARGEM_CM * cm,
        topMargin=MARGEM_CM * cm, bottomMargin=MARGEM_CM * cm,
        title=titulo or "Documento", author="PAULUS",
    )

    fluxo = []
    itens: list = []
    ordenada = False

    def despejar_lista():
        nonlocal itens, ordenada
        if not itens:
            return
        fluxo.append(ListFlowable(
            itens, bulletType="1" if ordenada else "bullet",
            leftIndent=18, bulletFontName="Times-Roman",
        ))
        fluxo.append(Spacer(1, 6))
        itens = []

    for bloco in blocos:
        marcado = _para_marcacao(bloco)
        if not marcado.strip():
            continue

        if bloco.tipo in ("item", "numerado"):
            if itens and ordenada != (bloco.tipo == "numerado"):
                despejar_lista()
            ordenada = bloco.tipo == "numerado"
            itens.append(ListItem(Paragraph(marcado, estilos["paragrafo"])))
            continue

        despejar_lista()
        estilo = estilos.get(bloco.tipo, estilos["paragrafo"])
        if bloco.tipo == "paragrafo":
            estilo = ParagraphStyle(
                "p", parent=estilos["paragrafo"],
                alignment=alinha.get(bloco.alinhamento, TA_LEFT),
            )
        fluxo.append(Paragraph(marcado, estilo))

    despejar_lista()
    if not fluxo:
        fluxo.append(Paragraph("(documento vazio)", estilos["paragrafo"]))

    doc.build(fluxo, onFirstPage=_numerar(rodape), onLaterPages=_numerar(rodape))
    return saida.getvalue()


def _numerar(rodape: str):
    """Numero de pagina no rodape, como todo documento juridico tem."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    def desenhar(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8.5)
        canvas.setFillGray(0.4)
        if rodape:
            canvas.drawString(MARGEM_CM * cm, 1.4 * cm, rodape[:110])
        canvas.drawRightString(A4[0] - MARGEM_CM * cm, 1.4 * cm, f"página {doc.page}")
        canvas.restoreState()

    return desenhar


def _para_marcacao(bloco: Bloco) -> str:
    """Os trechos do bloco na marcacao curta que o reportlab entende."""
    from xml.sax.saxutils import escape

    partes = []
    for t in bloco.trechos:
        texto = escape(t.texto).replace("\n", "<br/>")
        if not texto:
            continue
        if t.negrito:
            texto = f"<b>{texto}</b>"
        if t.italico:
            texto = f"<i>{texto}</i>"
        if t.sublinhado:
            texto = f"<u>{texto}</u>"
        if t.riscado:
            texto = f"<strike>{texto}</strike>"
        partes.append(texto)
    return "".join(partes)


# ----------------------------------------------------------------- DOCX


def para_docx(blocos: list[Bloco], titulo: str = "") -> bytes:
    """
    O documento em DOCX, para continuar no Word.

    Sai da mesma lista de blocos que gerou o PDF, entao o conteudo e o mesmo. O
    desenho da pagina nao e identico - Word e reportlab quebram linha de jeitos
    diferentes - e a tela diz isso: o PDF e o que vale para assinar e enviar.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    alinha = {
        "esquerda": WD_ALIGN_PARAGRAPH.LEFT,
        "centro": WD_ALIGN_PARAGRAPH.CENTER,
        "direita": WD_ALIGN_PARAGRAPH.RIGHT,
        "justificado": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    estilos = {
        "titulo1": "Heading 1", "titulo2": "Heading 2", "titulo3": "Heading 3",
        "item": "List Bullet", "numerado": "List Number",
    }

    doc = Document()
    for secao in doc.sections:
        secao.left_margin = secao.right_margin = Cm(MARGEM_CM)
        secao.top_margin = secao.bottom_margin = Cm(MARGEM_CM)

    normal = doc.styles["Normal"]
    normal.font.name = FONTE_PADRAO
    normal.font.size = Pt(CORPO_PT)

    for bloco in blocos:
        if not bloco.texto.strip():
            continue
        paragrafo = doc.add_paragraph(style=estilos.get(bloco.tipo))
        if bloco.tipo == "paragrafo":
            paragrafo.alignment = alinha.get(bloco.alinhamento)

        for t in bloco.trechos:
            if not t.texto:
                continue
            corrida = paragrafo.add_run(t.texto)
            corrida.bold = t.negrito
            corrida.italic = t.italico
            corrida.underline = t.sublinhado
            if t.riscado:
                corrida.font.strike = True

    saida = io.BytesIO()
    doc.save(saida)
    return saida.getvalue()


def pagina_png(pdf: bytes, numero: int = 1, largura: int = 900) -> bytes:
    """Uma pagina do PDF desenhada, para a pre-visualizacao."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        indice = max(0, min(int(numero) - 1, len(doc) - 1))
        pagina = doc[indice]
        escala = max(min(largura / max(pagina.get_width(), 1), 4.0), 0.2)
        imagem = pagina.render(scale=escala).to_pil()
    finally:
        doc.close()

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


def paginas_de(pdf: bytes) -> int:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        return len(doc)
    finally:
        doc.close()


# ------------------------------------------------ conferir antes de sair


# Vestigios de modelo que ninguem preencheu. Sair com "R$ ______" num contrato
# de honorarios e o tipo de erro que se descobre depois de enviado.
RE_LACUNA = re.compile(r"_{3,}|\.{4,}|\[\s*\]|\{\{[^}]*\}\}|\bXXX+\b|<<[^>]*>>")
RE_CPF_TXT = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ_TXT = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
# O \s* fora do lookahead volta atras e casa com zero espaco, entao
# "R$ 12.000,00" era apontado como valor sem numero. O espaco tem que
# estar DENTRO do lookahead.
RE_VALOR_VAZIO = re.compile(r"R\$(?!\s*[\d_])", re.IGNORECASE)


def _digitos(texto: str) -> list[int]:
    return [int(c) for c in re.sub(r"\D", "", texto)]


def cpf_valido(texto: str) -> bool:
    """Digito verificador do CPF. Objetivo: ou fecha, ou nao fecha."""
    d = _digitos(texto)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for corte in (9, 10):
        soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
        resto = (soma * 10) % 11 % 10
        if resto != d[corte]:
            return False
    return True


def cnpj_valido(texto: str) -> bool:
    """Digito verificador do CNPJ."""
    d = _digitos(texto)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        corte = len(pesos)
        soma = sum(d[i] * pesos[i] for i in range(corte))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != d[corte]:
            return False
    return True


def conferir(blocos: list[Bloco], fichas: list[dict] | None = None) -> list[dict]:
    """
    O que conferir antes de o documento sair.

    Tudo aqui e regra, nao modelo: roda em milissegundos e a resposta e sempre
    a mesma. Um aviso que muda de opiniao a cada leitura nao serve para conferir
    contrato.

    Nao aponta estilo nem sugere redacao - so o que da para afirmar: lacuna de
    modelo que ficou, documento com digito verificador errado, valor com o
    cifrao e sem numero, e nome que aparece no texto sem bater com a ficha.
    """
    avisos: list[dict] = []
    fichas = fichas or []

    for numero, bloco in enumerate(blocos, start=1):
        texto = bloco.texto
        if not texto.strip():
            continue

        for achado in RE_LACUNA.findall(texto):
            avisos.append({
                "grau": "impede",
                "bloco": numero,
                "titulo": "Falta preencher",
                "detalhe": f"Ficou “{achado.strip()}” no texto: {_recorte(texto, achado)}",
            })

        if RE_VALOR_VAZIO.search(texto):
            avisos.append({
                "grau": "impede",
                "bloco": numero,
                "titulo": "Valor sem número",
                "detalhe": f"Tem “R$” sem valor: {_recorte(texto, 'R$')}",
            })

        for cpf in RE_CPF_TXT.findall(texto):
            if not cpf_valido(cpf):
                avisos.append({
                    "grau": "impede",
                    "bloco": numero,
                    "titulo": "CPF não confere",
                    "detalhe": f"{cpf} não fecha no dígito verificador.",
                })
        for cnpj in RE_CNPJ_TXT.findall(texto):
            if not cnpj_valido(cnpj):
                avisos.append({
                    "grau": "impede",
                    "bloco": numero,
                    "titulo": "CNPJ não confere",
                    "detalhe": f"{cnpj} não fecha no dígito verificador.",
                })

    avisos += _conferir_fichas(blocos, fichas)
    return avisos


def _conferir_fichas(blocos: list[Bloco], fichas: list[dict]) -> list[dict]:
    """
    Cruza os documentos citados no texto com os Cadastros.

    Quando a ficha do cliente existe e o CNPJ do contrato e outro, o mais
    provavel e que alguem copiou de um contrato antigo - e esse e exatamente o
    erro que ninguem percebe relendo.
    """
    if not fichas:
        return []

    texto = para_texto(blocos)
    achados = set(RE_CPF_TXT.findall(texto)) | set(RE_CNPJ_TXT.findall(texto))
    avisos = []

    for ficha in fichas:
        nome = (ficha.get("nome") or "").strip()
        doc = (ficha.get("documento") or "").strip()
        if not nome or not doc or len(nome) < 6:
            continue
        if nome.lower() not in texto.lower():
            continue
        if doc in achados:
            continue
        avisos.append({
            "grau": "confira",
            "bloco": 0,
            "titulo": "Documento diferente do cadastro",
            "detalhe": (
                f"O texto cita {nome}, mas não traz o {('CNPJ' if len(_digitos(doc)) == 14 else 'CPF')} "
                f"{doc} que está no cadastro."
            ),
        })
    return avisos


def _recorte(texto: str, alvo: str, folga: int = 34) -> str:
    onde = texto.find(alvo)
    if onde < 0:
        return " ".join(texto.split())[:80]
    inicio = max(0, onde - folga)
    fim = min(len(texto), onde + len(alvo) + folga)
    pedaco = " ".join(texto[inicio:fim].split())
    return ("…" if inicio else "") + pedaco + ("…" if fim < len(texto) else "")


# ----------------------------------------------------------- o arquivo


class Documentos:
    """
    Documentos e planilhas, com historico.

    Versao nova so quando o conteudo muda de verdade. Gravar a cada tecla
    encheria o historico de ruido e enterraria a versao que interessa - a
    tela promete "v6: clausula de vigencia inserida", nao "v418".
    """

    def __init__(self, base) -> None:
        self.base = base

    def listar(self, tipo: str = "") -> list[dict]:
        sql = (
            "SELECT d.id, d.titulo, d.tipo, d.cadastro_id, d.criado_em, d.atualizado_em,"
            " k.nome AS cadastro_nome, LENGTH(d.corpo) AS tamanho,"
            " (SELECT MAX(numero) FROM versoes v WHERE v.documento_id = d.id) AS versao"
            " FROM documentos d LEFT JOIN cadastros k ON k.id = d.cadastro_id"
        )
        parametros: tuple = ()
        if tipo:
            sql += " WHERE d.tipo = ?"
            parametros = (tipo,)
        sql += " ORDER BY d.atualizado_em DESC"
        itens = self.base.buscar(sql, parametros)
        for i in itens:
            i["versao"] = i["versao"] or 1
        return itens

    def obter(self, id_: int) -> dict | None:
        item = self.base.um(
            "SELECT d.*, k.nome AS cadastro_nome FROM documentos d "
            "LEFT JOIN cadastros k ON k.id = d.cadastro_id WHERE d.id = ?",
            (id_,),
        )
        if item:
            item["versao"] = self.ultima_versao(id_)
        return item

    def criar(self, titulo: str, tipo: str = "texto", corpo: str = "",
              cadastro_id: int | None = None) -> int:
        titulo = " ".join(str(titulo or "").split()) or "Documento sem título"
        id_ = self.base.escrever(
            "INSERT INTO documentos (titulo, tipo, corpo, cadastro_id, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (titulo, tipo if tipo in ("texto", "planilha") else "texto", corpo, cadastro_id),
        )
        self._gravar_versao(id_, corpo, "criado")
        return id_

    def salvar(self, id_: int, corpo: str, titulo: str = "", nota: str = "") -> dict:
        atual = self.base.um("SELECT corpo, titulo FROM documentos WHERE id = ?", (id_,))
        if not atual:
            raise ValueError("documento nao encontrado")

        mudou = atual["corpo"] != corpo
        novo_titulo = " ".join(str(titulo).split()) if titulo else atual["titulo"]

        self.base.escrever(
            "UPDATE documentos SET corpo = ?, titulo = ?, "
            "atualizado_em = datetime('now','localtime') WHERE id = ?",
            (corpo, novo_titulo, id_),
        )
        if mudou:
            self._gravar_versao(id_, corpo, nota)
        return {"id": id_, "versao": self.ultima_versao(id_), "nova_versao": mudou}

    def _gravar_versao(self, id_: int, corpo: str, nota: str) -> int:
        numero = self.ultima_versao(id_) + 1
        self.base.escrever(
            "INSERT INTO versoes (documento_id, numero, corpo, nota, criada_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
            (id_, numero, corpo, nota[:120]),
        )
        return numero

    def ultima_versao(self, id_: int) -> int:
        linha = self.base.um(
            "SELECT MAX(numero) AS n FROM versoes WHERE documento_id = ?", (id_,)
        )
        return int(linha["n"] or 0) if linha else 0

    def versoes(self, id_: int, limite: int = 30) -> list[dict]:
        return self.base.buscar(
            "SELECT id, numero, nota, criada_em, LENGTH(corpo) AS tamanho "
            "FROM versoes WHERE documento_id = ? ORDER BY numero DESC LIMIT ?",
            (id_, limite),
        )

    def corpo_da_versao(self, id_: int, numero: int) -> str | None:
        linha = self.base.um(
            "SELECT corpo FROM versoes WHERE documento_id = ? AND numero = ?",
            (id_, numero),
        )
        return linha["corpo"] if linha else None

    def restaurar(self, id_: int, numero: int) -> dict:
        """
        Volta para uma versao antiga sem apagar o caminho de volta.

        A versao antiga vira uma versao nova. Sobrescrever o historico faria
        do "restaurar" uma operacao sem desfazer - e restaurar por engano e
        exatamente o tipo de coisa que acontece.
        """
        corpo = self.corpo_da_versao(id_, numero)
        if corpo is None:
            raise ValueError("essa versao nao existe")
        return self.salvar(id_, corpo, nota=f"voltou para a v{numero}")

    def apagar(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM documentos WHERE id = ?", (id_,)) > 0

    def contagem(self) -> dict:
        return {
            "texto": self.base.contar("documentos", "tipo = 'texto'"),
            "planilha": self.base.contar("documentos", "tipo = 'planilha'"),
        }


def comparar(antes: str, depois: str) -> list[dict]:
    """
    O que mudou entre duas versoes, por paragrafo.

    Compara o texto, nao o HTML: trocar o editor de <b> para <strong> nao e
    alteracao de contrato, e listar isso como mudanca faria a comparacao
    perder a utilidade justamente no dia em que ela importa.
    """
    import difflib

    a = [b.texto.strip() for b in ler_html(antes) if b.texto.strip()]
    b = [x.texto.strip() for x in ler_html(depois) if x.texto.strip()]

    saida: list[dict] = []
    for marca, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if marca == "equal":
            continue
        if marca == "replace":
            for antes_txt, depois_txt in zip(a[i1:i2], b[j1:j2]):
                saida.append({"tipo": "mudou", "antes": antes_txt, "depois": depois_txt})
            for extra in b[j1 + (i2 - i1):j2]:
                saida.append({"tipo": "entrou", "antes": "", "depois": extra})
            for extra in a[i1 + (j2 - j1):i2]:
                saida.append({"tipo": "saiu", "antes": extra, "depois": ""})
        elif marca == "insert":
            for texto in b[j1:j2]:
                saida.append({"tipo": "entrou", "antes": "", "depois": texto})
        elif marca == "delete":
            for texto in a[i1:i2]:
                saida.append({"tipo": "saiu", "antes": texto, "depois": ""})
    return saida


class Clausulas:
    """
    As clausulas que o escritorio guarda para reaproveitar.

    Conteudo do escritorio, escrito pelo escritorio. E de proposito que aqui
    nao entra texto de lei: o programa nao carrega o Codigo Civil, e pedir o
    artigo ao modelo produziria numero plausivel e errado dentro de um
    contrato. Modelo de clausula que a pessoa mesma escreveu nao tem esse risco.
    """

    def __init__(self, caminho: Path) -> None:
        import json

        self.caminho = Path(caminho)
        self.itens: list[dict] = []
        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                self.itens = bruto.get("clausulas", []) if isinstance(bruto, dict) else []
            except (json.JSONDecodeError, OSError):
                self.itens = []

    def listar(self) -> list[dict]:
        return sorted(self.itens, key=lambda c: c.get("titulo", "").lower())

    def gravar(self, titulo: str, texto: str, id_: str = "") -> dict:
        import uuid

        titulo = " ".join(str(titulo or "").split())
        if not titulo:
            raise ValueError("a cláusula precisa de um título")
        if not str(texto or "").strip():
            raise ValueError("a cláusula precisa de um texto")

        item = next((c for c in self.itens if c.get("id") == id_), None)
        if item is None:
            item = {"id": uuid.uuid4().hex[:10]}
            self.itens.append(item)
        item["titulo"] = titulo
        item["texto"] = str(texto)
        item["atualizada_em"] = datetime.now().isoformat(timespec="seconds")
        self.salvar()
        return item

    def apagar(self, id_: str) -> bool:
        antes = len(self.itens)
        self.itens = [c for c in self.itens if c.get("id") != id_]
        self.salvar()
        return len(self.itens) < antes

    def salvar(self) -> None:
        import json

        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps({"versao": 1, "clausulas": self.itens}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
