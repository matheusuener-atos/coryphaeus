"""
PAVLVS - Extrato de contribuicoes.

O registro das contribuicoes de quem apoia o projeto, no desenho de
docs/ui/extrato: cada contribuicao (data, tipo, forma, referencia,
situacao, valor), o total confirmado e o periodo, e a natureza do apoio -
voluntario, sem contrapartida.

Ele afirma so o que e verdade: nao e nota fiscal nem documento fiscal (o
comprovante de cada pagamento e o do Mercado Pago, que processou), e nao da
direito a deducao do Imposto de Renda. As cobrancas do cartao vem do
Mercado Pago na hora; os Pix, dos confirmados nesta instalacao.

Tipo: o Pix e uma contribuicao avulsa; cada cobranca do apoio mensal no
cartao e uma recorrente, no mes em que ocorreu. Nao ha "apoio recorrente
sim/nao" no resumo, porque a recorrencia pode ter comecado e parado.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

NOME = "PAVLVS — Extrato de contribuições"
SITE = "paulus.ia.br"
CONTATO = "contato@paulus.ia.br"
FONTES = Path(__file__).resolve().parent / "fontes_pdf"

# A situacao de cada contribuicao, no feminino. So "Confirmada" entra no total.
SITUACOES = {
    "approved": "Confirmada", "pago": "Confirmada", "processed": "Confirmada",
    "pending": "Pendente", "in_process": "Em análise", "scheduled": "Agendada",
    "recycling": "Nova tentativa", "rejected": "Recusada", "cancelled": "Cancelada",
    "refunded": "Devolvida", "charged_back": "Estornada",
}

# As cores do desenho. As linhas sao preto com transparencia sobre o branco
# do papel (.08, .10, .14): aqui ja misturadas.
TINTA = "#1c1c1a"
SECUNDARIO = "#6b6b65"
ROTULO = "#8a8a83"
CORPO = "#3a3a36"
ABERTURA = "#55554f"
LINHA_08 = "#ebebeb"
LINHA_10 = "#e6e6e6"
LINHA_14 = "#dbdbdb"
SELO_FUNDO, SELO_TINTA = "#edf5ee", "#2f6b42"
SELO_NEUTRO_FUNDO, SELO_NEUTRO_TINTA = "#f1f1ee", "#6b6b65"


def _data(texto: str) -> datetime | None:
    texto = str(texto or "").strip()
    for formato in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:32], formato)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def _reais(valor: float) -> str:
    inteiro, centavos = f"{abs(valor):,.2f}".split(".")
    return ("-" if valor < 0 else "") + "R$ " + inteiro.replace(",", ".") + "," + centavos


def montar_linhas(pix: list[dict], cobrancas: list[dict]) -> list[dict]:
    """As contribuicoes juntas, da mais antiga a mais nova, com tipo, forma e situacao."""
    linhas = []
    for p in pix or []:
        linhas.append({"quando": _data(p.get("data")), "tipo": "Avulsa", "forma": "Pix",
                       "referencia": str(p.get("id", ""))[-10:], "situacao": "Confirmada", "confirmada": True,
                       "valor": float(p.get("valor") or 0)})
    for c in cobrancas or []:
        bruto = str(c.get("situacao", ""))
        situacao = SITUACOES.get(bruto, bruto or "—")
        linhas.append({"quando": _data(c.get("data")), "tipo": "Recorrente", "forma": "Cartão de crédito",
                       "referencia": str(c.get("id", ""))[-10:], "situacao": situacao,
                       "confirmada": situacao == "Confirmada", "valor": float(c.get("valor") or 0)})
    linhas.sort(key=lambda l: l["quando"].replace(tzinfo=None) if l["quando"] else datetime.min)
    return linhas


def resumo(linhas: list[dict]) -> dict:
    """Total, periodo (primeira e ultima confirmada) e quantas foram confirmadas."""
    confirmadas = [l for l in linhas if l["confirmada"]]
    datas = [l["quando"] for l in confirmadas if l["quando"]]
    if not datas:
        periodo = "—"
    elif datas[0].date() == datas[-1].date():
        periodo = f"{datas[0]:%d/%m/%Y}"
    else:
        periodo = f"{datas[0]:%d/%m/%Y} a {datas[-1]:%d/%m/%Y}"
    n = len(confirmadas)
    contagem = "nenhuma confirmada" if n == 0 else ("1 confirmada" if n == 1 else f"{n} confirmadas")
    return {"total": sum(l["valor"] for l in confirmadas), "periodo": periodo, "contagem": contagem}


_FAMILIAS: dict[str, str] = {}


def _fontes() -> dict[str, str]:
    """As fontes do desenho (src/fontes_pdf). Sem elas, as do proprio PDF."""
    if _FAMILIAS:
        return _FAMILIAS
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pecas = {"garamond": "PAULUSGaramond", "garamond_medio": "PAULUSGaramondMedio",
             "garamond_italico": "PAULUSGaramondItalico", "texto": "PAULUSManrope",
             "seminegrito": "PAULUSManropeSeminegrito", "negrito": "PAULUSManropeNegrito",
             "mono": "PAULUSMono", "mono_medio": "PAULUSMonoMedio"}
    reserva = {"garamond": "Times-Roman", "garamond_medio": "Times-Roman", "garamond_italico": "Times-Italic",
               "texto": "Helvetica", "seminegrito": "Helvetica-Bold", "negrito": "Helvetica-Bold",
               "mono": "Courier", "mono_medio": "Courier"}
    try:
        for papel, nome in pecas.items():
            if nome not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(nome, str(FONTES / f"{nome}.ttf")))
            _FAMILIAS[papel] = nome
        # <b> no meio do texto corrido vira o Manrope 700
        pdfmetrics.registerFontFamily("PAULUSManrope", normal="PAULUSManrope", bold="PAULUSManropeNegrito",
                                      italic="PAULUSManrope", boldItalic="PAULUSManropeNegrito")
    except Exception:  # noqa: BLE001 - fonte faltando nao impede o extrato
        _FAMILIAS.clear()
        _FAMILIAS.update(reserva)
    return _FAMILIAS


def gerar(pasta: Path, *, nome: str, email: str, pix: list[dict], cobrancas: list[dict]) -> Path:
    """Grava o PDF em `pasta` e devolve o caminho."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate, Paragraph, Spacer,
                                    Table, TableStyle)

    f = _fontes()
    cor = colors.HexColor
    px = 0.75  # o desenho mede em px de tela; 1 px = 0,75 pt

    class Letreiro(Flowable):
        """Uma linha com espacamento entre letras, que o Paragraph nao faz."""

        def __init__(self, texto, fonte, tamanho, tinta, espaco_em=0.0, altura=None, direita=False, base=None):
            super().__init__()
            self.texto, self.fonte, self.tamanho, self.tinta = texto, fonte, tamanho, tinta
            self.espaco = espaco_em * tamanho
            self.altura = altura or tamanho * 1.2
            self.direita = direita
            self.base = self.altura - tamanho if base is None else base
            self.x = 0.0

        def largura(self):
            return stringWidth(self.texto, self.fonte, self.tamanho) + self.espaco * max(len(self.texto) - 1, 0)

        def wrap(self, disponivel, _altura):
            if self.direita:
                self.x = max(disponivel - self.largura(), 0)
                return disponivel, self.altura
            return min(self.largura(), disponivel), self.altura

        def draw(self):
            t = self.canv.beginText(self.x, self.base)
            t.setFont(self.fonte, self.tamanho)
            t.setCharSpace(self.espaco)
            t.setFillColor(cor(self.tinta))
            t.textOut(self.texto)
            self.canv.drawText(t)

    class Topo(Flowable):
        """PAVLVS a esquerda, a assinatura do projeto a direita, na mesma linha de base, e o fio embaixo."""

        def wrap(self, disponivel, _altura):
            self.largura = disponivel
            return disponivel, 18 + 11 * px

        def draw(self):
            c = self.canv
            base = 11 * px + 2
            marca = Letreiro("PAVLVS", f["garamond_medio"], 18, TINTA, 0.12)
            c.saveState()
            t = c.beginText(0, base)
            t.setFont(marca.fonte, 18)
            t.setCharSpace(marca.espaco)
            t.setFillColor(cor(TINTA))
            t.textOut("PAVLVS")
            c.drawText(t)
            direita = Letreiro("PAVLVS · PAULUS LEGAL · SOFTWARE LIVRE", f["mono"], 7, SECUNDARIO, 0.16)
            t = c.beginText(self.largura - direita.largura(), base)
            t.setFont(direita.fonte, 7)
            t.setCharSpace(direita.espaco)
            t.setFillColor(cor(SECUNDARIO))
            t.textOut(direita.texto)
            c.drawText(t)
            c.setStrokeColor(cor(LINHA_10))
            c.setLineWidth(px)
            c.line(0, 0, self.largura, 0)
            c.restoreState()

    class Selo(Flowable):
        """A situacao da contribuicao: verde quando confirmada."""

        def __init__(self, texto, confirmada):
            super().__init__()
            self.texto = texto
            self.fundo, self.tinta = (SELO_FUNDO, SELO_TINTA) if confirmada else (SELO_NEUTRO_FUNDO, SELO_NEUTRO_TINTA)
            self.tamanho = 7.8

        def wrap(self, _disponivel, _altura):
            self.w = stringWidth(self.texto, f["seminegrito"], self.tamanho) + 14 * px
            self.h = self.tamanho + 4
            return self.w, self.h

        def draw(self):
            c = self.canv
            c.setFillColor(cor(self.fundo))
            c.roundRect(0, 0, self.w, self.h, 4 * px, stroke=0, fill=1)
            c.setFillColor(cor(self.tinta))
            c.setFont(f["seminegrito"], self.tamanho)
            c.drawString(7 * px, 2.6, self.texto)

    def estilo(nome_, **kw):
        base = {"fontName": f["texto"], "fontSize": 9, "leading": 9 * 1.55, "textColor": cor(TINTA)}
        base.update(kw)
        return ParagraphStyle(nome_, **base)

    def rotulo(texto, medio=False, tamanho=6.5, direita=False):
        return Letreiro(texto, f["mono_medio"] if medio else f["mono"], tamanho, ROTULO, 0.16, direita=direita)

    forte = f'<font color="{TINTA}"><b>'
    fim_forte = "</b></font>"
    titulo_h2 = estilo("h2", fontName=f["garamond_medio"], fontSize=14, leading=15.4)
    corrido = estilo("corrido", fontSize=8.6, leading=8.6 * 1.6, textColor=cor(CORPO))
    valor_quadro = estilo("valor", fontName=f["seminegrito"])

    pasta.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    destino = pasta / f"PAVLVS - Extrato de contribuições {agora:%Y-%m-%d %H%M%S}.pdf"
    linhas = montar_linhas(pix, cobrancas)
    soma = resumo(linhas)

    margem = 16 * mm
    largura_util = A4[0] - 2 * margem
    rodape_altura = 7 + 8 * px + 10

    def rodape(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(cor(LINHA_10))
        canvas.setLineWidth(px)
        canvas.line(margem, margem + 7 + 8 * px, A4[0] - margem, margem + 7 + 8 * px)
        for texto, x, direita in ((f"{NOME} · emitido em {agora:%d/%m/%Y}", margem, False),
                                  (SITE, A4[0] - margem, True)):
            letreiro = Letreiro(texto, f["mono"], 7, ROTULO, 0.08)
            t = canvas.beginText(x - (letreiro.largura() if direita else 0), margem + 1)
            t.setFont(f["mono"], 7)
            t.setCharSpace(letreiro.espaco)
            t.setFillColor(cor(ROTULO))
            t.textOut(texto)
            canvas.drawText(t)
        canvas.restoreState()

    # O quadro da pagina sem o recuo de 6 pt que o reportlab poe por padrao:
    # texto e tabelas alinham na margem de 16 mm, como no desenho.
    doc = BaseDocTemplate(str(destino), pagesize=A4, title="Extrato de contribuições", author="PAVLVS",
                          subject="Contribuições voluntárias ao PAVLVS (PAULUS Legal)")
    area = Frame(margem, margem + rodape_altura, largura_util, A4[1] - 2 * margem - rodape_altura,
                 leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="pagina", frames=[area], onPage=rodape)])
    h: list = [Topo(), Spacer(1, 22 * px)]

    # Rotulo, titulo e abertura.
    h += [rotulo(f"EMITIDO EM {agora:%d/%m/%Y}", tamanho=7), Spacer(1, 8 * px),
          Letreiro("Extrato de contribuições", f["garamond"], 30, TINTA, -0.015, altura=30 * 1.02 + 4.3, base=4.3 + 4.7), Spacer(1, 8 * px)]
    abertura = Table([[Paragraph("Este extrato apresenta as contribuições voluntárias registradas em apoio ao "
                                 "desenvolvimento e à manutenção do PAVLVS (PAULUS Legal).",
                                 estilo("abertura", fontSize=10, leading=16, textColor=cor(ABERTURA)))]],
                     colWidths=[130 * mm], hAlign="LEFT")
    abertura.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    h += [abertura, Spacer(1, 18 * px)]

    # O quadro: quem apoia e o resumo, 3 x 2.
    def celula(r, v):
        return [rotulo(r), Spacer(1, 3 * px), Paragraph(escape(v), valor_quadro)]

    quadro = Table([[celula("APOIADOR", nome or "Anônimo"), celula("E-MAIL DO RECIBO", email or "—"),
                     celula("EMITIDO EM", f"{agora:%d/%m/%Y} às {agora:%H:%M}")],
                    [celula("TOTAL CONTRIBUÍDO", _reais(soma["total"])), celula("PERÍODO", soma["periodo"]),
                     celula("CONTRIBUIÇÕES", soma["contagem"])]],
                   colWidths=[largura_util * p / 3.4 for p in (1, 1.4, 1)])
    quadro.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16 * px), ("RIGHTPADDING", (0, 0), (-1, -1), 16 * px),
        ("TOPPADDING", (0, 0), (-1, -1), 11 * px), ("BOTTOMPADDING", (0, 0), (-1, -1), 11 * px),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), px, cor(LINHA_10)), ("ROUNDEDCORNERS", [10 * px] * 4),
        ("LINEBEFORE", (1, 0), (-1, -1), px, cor(LINHA_08)), ("LINEABOVE", (0, 1), (-1, 1), px, cor(LINHA_08)),
    ]))
    h += [KeepTogether([quadro]), Spacer(1, 18 * px)]

    # As contribuicoes.
    h += [Paragraph("Contribuições", titulo_h2), Spacer(1, 6 * px)]
    if linhas:
        celula_txt = estilo("celula")
        ref = estilo("ref", fontName=f["mono"], fontSize=8.3, leading=12)
        valor = estilo("valor_linha", alignment=TA_RIGHT)
        cabeca = [rotulo(t, medio=True) for t in ("DATA", "TIPO", "FORMA", "REFERÊNCIA", "SITUAÇÃO")]
        dados = [cabeca + [rotulo("VALOR", medio=True, direita=True)]]
        for l in linhas:
            dados.append([Paragraph(l["quando"].strftime("%d/%m/%Y") if l["quando"] else "—", celula_txt),
                          Paragraph(l["tipo"], celula_txt), Paragraph(l["forma"], celula_txt),
                          Paragraph(escape(l["referencia"] or "—"), ref), Selo(l["situacao"], l["confirmada"]),
                          Paragraph(_reais(l["valor"]), valor)])
        dados.append([Paragraph("Total contribuído", estilo("total", fontName=f["negrito"])), "", "", "", "",
                      Paragraph(_reais(soma["total"]), estilo("total_valor", fontName=f["negrito"], alignment=TA_RIGHT))])
        larguras = [22 * mm, 24 * mm, 34 * mm, 36 * mm, 30 * mm]
        larguras.append(largura_util - sum(larguras))
        tabela = Table(dados, colWidths=larguras, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-2, -1), 8 * px),
            ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, 0), 7 * px), ("BOTTOMPADDING", (0, 0), (-1, 0), 7 * px),
            ("TOPPADDING", (0, 1), (-1, -1), 9 * px), ("BOTTOMPADDING", (0, 1), (-1, -1), 9 * px),
            ("LINEBELOW", (0, 0), (-1, 0), px, cor(LINHA_14)),
            ("LINEBELOW", (0, 1), (-1, -2), px, cor(LINHA_08)),
            ("SPAN", (0, -1), (4, -1)),
        ]))
        h.append(tabela)
        h += [Spacer(1, 2 * px), Paragraph(
            f"Tipo: {forte}Avulsa{fim_forte} é uma contribuição única; {forte}Recorrente{fim_forte} é uma cobrança do "
            "apoio mensal no cartão, registrada no mês em que ocorreu.",
            estilo("nota", fontSize=7.8, leading=7.8 * 1.55, textColor=cor(SECUNDARIO)))]
    else:
        h.append(Paragraph("Nenhuma contribuição registrada até agora.", estilo("vazio", textColor=cor(SECUNDARIO))))

    # Sobre estas contribuicoes.
    fio = Table([[""]], colWidths=[largura_util], rowHeights=[1],
                style=[("LINEABOVE", (0, 0), (-1, -1), px, cor(LINHA_10))])
    sobre = [Spacer(1, 4 * px), fio, Spacer(1, 16 * px + 12 * px), Paragraph("Sobre estas contribuições", titulo_h2),
             Spacer(1, 9 * px),
             Paragraph(f"As contribuições ao PAVLVS são {forte}voluntárias e sem contrapartida{fim_forte}. O PAVLVS "
                       "permanece disponível independentemente da realização de qualquer contribuição.", corrido),
             Spacer(1, 7 * px),
             Paragraph("Contribuir não constitui compra, assinatura ou contratação de serviço e não concede "
                       "funcionalidades, licenças, atendimento diferenciado ou qualquer outra vantagem ao apoiador. Os "
                       "valores recebidos destinam-se voluntariamente a apoiar a continuidade, manutenção e "
                       "desenvolvimento do projeto.", corrido),
             Spacer(1, 9 * px + 6 * px)]
    h3 = estilo("h3", fontName=f["negrito"], fontSize=9, leading=12)

    def coluna(titulo, paragrafos):
        corpo = [Paragraph(titulo, h3)]
        for p in paragrafos:
            corpo += [Spacer(1, 6 * px), Paragraph(p, corrido)]
        return corpo

    fiscal = coluna("Tratamento fiscal", [
        f"A contribuição não constitui doação incentivada e {forte}não gera ao apoiador direito à dedução do "
        f"Imposto de Renda{fim_forte}. Este extrato, portanto, não deve ser utilizado como comprovante de incentivo "
        "ou dedução fiscal.",
        "Eventuais obrigações tributárias relacionadas à transmissão gratuita de valores são regidas pela "
        "legislação aplicável a cada operação.",
    ])
    documento = coluna("Sobre este documento", [
        f"Este extrato é um registro das contribuições identificadas pelo PAVLVS. {forte}Não é nota fiscal nem "
        f"documento fiscal.{fim_forte}",
        "Os pagamentos são processados pelo Mercado Pago. O comprovante da transação emitido pelo meio de "
        "pagamento permanece sendo o comprovante da respectiva operação financeira.",
        f"O {forte}apoio recorrente{fim_forte}, quando ativado pelo apoiador, pode ser interrompido a qualquer "
        f"momento pela opção disponível em {forte}“Apoiar o projeto”{fim_forte}. Após o cancelamento, não serão "
        "realizadas novas contribuições recorrentes.",
    ])
    vao = 24 * px
    colunas = Table([[fiscal, documento]], colWidths=[largura_util / 2] * 2)
    colunas.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), vao / 2),
                                 ("LEFTPADDING", (1, 0), (1, 0), vao / 2), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    h += [KeepTogether(sobre[:6]), *sobre[6:], colunas]

    # Agradecimento e os enderecos.
    obrigado = Paragraph("Obrigado por apoiar a continuidade do PAVLVS como software livre.",
                         estilo("obrigado", fontName=f["garamond_italico"], fontSize=14, leading=16.8))
    link = f'<font color="{TINTA}">'
    enderecos = Paragraph(
        f"{forte}Termos de uso:{fim_forte} {link}<a href=\"https://{SITE}/termos-de-uso\">{SITE}/termos-de-uso</a></font>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;{forte}Política de privacidade:{fim_forte} "
        f"{link}<a href=\"https://{SITE}/politica-de-privacidade\">{SITE}/politica-de-privacidade</a></font>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;{forte}Contato:{fim_forte} {link}<a href=\"mailto:{CONTATO}\">{CONTATO}</a></font>",
        estilo("enderecos", fontSize=7.3, leading=7.3 * 1.55, textColor=cor(SECUNDARIO)))
    fim = Table([[""]], colWidths=[largura_util], rowHeights=[1], style=[("LINEABOVE", (0, 0), (-1, -1), px, cor(LINHA_10))])
    h.append(KeepTogether([Spacer(1, 28 * px), obrigado, Spacer(1, 12 * px), fim, Spacer(1, 8 * px), enderecos]))

    doc.build(h)
    return destino
