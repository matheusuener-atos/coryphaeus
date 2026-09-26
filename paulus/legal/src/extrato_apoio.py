"""
PAVLVS - Extrato de apoio.

O comprovante das contribuicoes de quem apoia o projeto: cada pagamento
(data, forma, referencia, situacao, valor), o total, e a natureza do apoio
- uma liberalidade, sem contrapartida, como a doacao do art. 538 do Codigo
Civil.

Ele afirma so o que e verdade: nao e recibo fiscal nem nota fiscal (o
comprovante de cada pagamento e o do Mercado Pago, que processou), e nao e
dedutivel do Imposto de Renda - o apoio ao PAULUS nao esta entre os
incentivos que a lei deixa deduzir (Lei 9.250/1995, art. 12). As cobrancas
do cartao vem do Mercado Pago na hora; os Pix, dos confirmados nesta
instalacao.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

NOME = "PAVLVS - Extrato de apoio"
SITE = "paulus.ia.br"
CONTATO = "contato@paulus.ia.br"

SITUACOES = {
    "approved": "pago", "pago": "pago", "processed": "pago",
    "pending": "pendente", "in_process": "em análise", "scheduled": "agendado",
    "recycling": "nova tentativa", "rejected": "recusado", "cancelled": "cancelado",
    "refunded": "devolvido",
}


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
    """Os pagamentos juntos, do mais antigo ao mais novo, com a situacao em portugues."""
    linhas = []
    for p in pix or []:
        linhas.append({"quando": _data(p.get("data")), "forma": "Pix", "referencia": str(p.get("id", ""))[-10:],
                       "situacao": "pago", "valor": float(p.get("valor") or 0)})
    for c in cobrancas or []:
        linhas.append({"quando": _data(c.get("data")), "forma": "Cartão · mensal", "referencia": str(c.get("id", ""))[-10:],
                       "situacao": SITUACOES.get(str(c.get("situacao", "")), str(c.get("situacao", "")) or "—"),
                       "valor": float(c.get("valor") or 0)})
    linhas.sort(key=lambda l: l["quando"].replace(tzinfo=None) if l["quando"] else datetime.min)
    return linhas


def gerar(pasta: Path, *, nome: str, email: str, pix: list[dict], cobrancas: list[dict],
          assinatura: dict | None = None) -> Path:
    """Grava o PDF em `pasta` e devolve o caminho."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    pasta.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    destino = pasta / f"PAVLVS - Extrato de apoio {agora:%Y-%m-%d %H%M%S}.pdf"
    linhas = montar_linhas(pix, cobrancas)
    pagas = [l for l in linhas if l["situacao"] == "pago"]
    total = sum(l["valor"] for l in pagas)

    tinta = colors.HexColor("#1f1f1e")
    cinza = colors.HexColor("#6b6b66")
    fio = colors.HexColor("#d9d7cf")
    fundo = colors.HexColor("#f6f4ee")
    verde = colors.HexColor("#2f6b3f")

    titulo = ParagraphStyle("titulo", fontName="Times-Roman", fontSize=26, leading=30, textColor=tinta)
    marca = ParagraphStyle("marca", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=cinza)
    texto = ParagraphStyle("texto", fontName="Helvetica", fontSize=9.5, leading=14, textColor=tinta)
    miudo = ParagraphStyle("miudo", fontName="Helvetica", fontSize=8, leading=11.5, textColor=cinza)
    secao = ParagraphStyle("secao", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=tinta, spaceBefore=6)
    rotulo = ParagraphStyle("rotulo", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=cinza)
    numero = ParagraphStyle("numero", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=tinta)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(fio)
        canvas.line(2.2 * cm, 1.6 * cm, A4[0] - 2.2 * cm, 1.6 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(cinza)
        canvas.drawString(2.2 * cm, 1.15 * cm, f"{NOME} · emitido em {agora:%d/%m/%Y às %H:%M} · {SITE}")
        canvas.drawRightString(A4[0] - 2.2 * cm, 1.15 * cm, f"página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2.2 * cm, title=NOME, author="PAVLVS")
    h: list = [Paragraph("PAVLVS · PAULUS LEGAL · SOFTWARE LIVRE", marca), Spacer(1, 6), Paragraph("PAVLVS — Extrato de apoio", titulo), Spacer(1, 6),
               Paragraph("As contribuições voluntárias feitas ao desenvolvimento do PAVLVS (PAULUS Legal), com a data, a forma e a situação de cada pagamento.", texto),
               Spacer(1, 14)]

    # Quem apoia e o resumo, em faixa.
    ficha = [[Paragraph("APOIADOR", rotulo), Paragraph("E-MAIL DO RECIBO", rotulo), Paragraph("EMITIDO EM", rotulo)],
             [Paragraph(escape(nome or "anônimo"), texto), Paragraph(escape(email or "—"), texto), Paragraph(f"{agora:%d/%m/%Y}", texto)]]
    t = Table(ficha, colWidths=[6.2 * cm, 6.2 * cm, 4.2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, 0), 2), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    h += [t, Spacer(1, 14)]

    situacao_ass = "—"
    if assinatura:
        situacao_ass = {"authorized": "ativa", "cancelled": "interrompida", "pending": "esperando o cartão", "paused": "pausada"}.get(
            str(assinatura.get("situacao", "")), str(assinatura.get("situacao", "")) or "—")
        if assinatura.get("valor"):
            situacao_ass = _reais(float(assinatura["valor"])) + " por mês · " + situacao_ass
    resumo = [[Paragraph("TOTAL CONTRIBUÍDO", rotulo), Paragraph("PAGAMENTOS", rotulo), Paragraph("ASSINATURA NO CARTÃO", rotulo)],
              [Paragraph(_reais(total), numero), Paragraph(str(len(pagas)), numero), Paragraph(escape(situacao_ass), texto)]]
    t = Table(resumo, colWidths=[5.4 * cm, 3.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fundo), ("BOX", (0, 0), (-1, -1), 0.6, fio),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, 0), 10),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 12)]))
    h += [t, Spacer(1, 18), Paragraph("Pagamentos", secao), Spacer(1, 6)]

    if linhas:
        dados = [["Data", "Forma", "Referência", "Situação", "Valor"]]
        for l in linhas:
            dados.append([l["quando"].strftime("%d/%m/%Y") if l["quando"] else "—", l["forma"], l["referencia"] or "—",
                          l["situacao"], _reais(l["valor"])])
        dados.append(["", "", "", "Total pago", _reais(total)])
        t = Table(dados, colWidths=[2.6 * cm, 3.6 * cm, 4.0 * cm, 3.2 * cm, 3.2 * cm], repeatRows=1)
        estilo = [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), cinza),
                  ("FONT", (0, 1), (-1, -1), "Helvetica", 9), ("TEXTCOLOR", (0, 1), (-1, -1), tinta),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.8, tinta), ("LINEBELOW", (0, 1), (-1, -2), 0.4, fio),
                  ("ALIGN", (4, 0), (4, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                  ("LEFTPADDING", (0, 0), (-1, -1), 4), ("FONT", (3, -1), (4, -1), "Helvetica-Bold", 9.5),
                  ("LINEABOVE", (3, -1), (4, -1), 0.8, tinta)]
        for i, l in enumerate(linhas, start=1):
            if l["situacao"] == "pago":
                estilo.append(("TEXTCOLOR", (3, i), (3, i), verde))
            if i % 2 == 0:
                estilo.append(("BACKGROUND", (0, i), (-1, i), fundo))
        t.setStyle(TableStyle(estilo))
        h.append(t)
    else:
        h.append(Paragraph("Nenhum pagamento confirmado até agora.", texto))

    h += [Spacer(1, 20), Paragraph("Natureza do apoio", secao), Spacer(1, 4)]
    notas = [
        "<b>Contribuição voluntária, sem contrapartida.</b> O apoio mantém o desenvolvimento do PAVLVS (PAULUS Legal), software livre que roda "
        "na máquina de quem usa, sem cobrança por uso. Quem apoia não recebe produto, serviço nem vantagem em troca: tem a natureza "
        "de liberalidade, como a doação definida no art. 538 do Código Civil (Lei nº 10.406/2002) — o contrato em que uma pessoa, "
        "por liberalidade, transfere do seu patrimônio bens ou vantagens para o de outra.",
        "<b>Não é dedutível do Imposto de Renda.</b> O apoio ao PAVLVS não está entre as doações e os incentivos que a legislação "
        "permite deduzir (como os do art. 12 da Lei nº 9.250/1995). Este extrato não deve ser usado como comprovante de dedução.",
        "<b>Não é recibo fiscal nem nota fiscal.</b> Cada pagamento foi processado pelo Mercado Pago, que envia o comprovante oficial "
        "para o e-mail informado. As cobranças no cartão foram consultadas no Mercado Pago no momento da emissão; os Pix são os "
        "confirmados nesta instalação do PAVLVS.",
        "<b>Cancelar é livre, a qualquer momento.</b> A assinatura mensal é interrompida pela tela “Apoiar o projeto” do PAVLVS, "
        "e nada mais é cobrado depois disso. O nome no mural de apoiadores é opcional; valor e forma de pagamento nunca são publicados.",
        f"Termos de uso: {SITE}/termos-de-uso · Política de privacidade: {SITE}/politica-de-privacidade · Contato: {CONTATO}",
    ]
    for n in notas:
        h += [Paragraph(n, miudo if n.startswith("Termos") else texto), Spacer(1, 6)]
    h += [Spacer(1, 10), Paragraph("Obrigado por manter o PAVLVS livre e gratuito.", ParagraphStyle(
        "obrigado", parent=titulo, fontSize=14, leading=18))]

    doc.build(h, onFirstPage=rodape, onLaterPages=rodape)
    return destino
