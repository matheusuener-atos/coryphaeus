"""
PAVLVS - Certificado de conformidade.

O relatorio do que a conferencia das assinaturas de um PDF encontrou, num
documento que da para guardar, imprimir ou mandar junto do arquivo.

Ele afirma so o que a conferencia desta maquina afirma: quem assinou, quem
emitiu o certificado, quando, e se o documento foi alterado depois de
assinado. Nao afirma validade juridica perante a ICP-Brasil: isso exige
consultar revogacao e montar a cadeia ate a raiz oficial, pela internet, e o
proprio relatorio diz isso - e onde fazer (o verificador do ITI).
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path

NOME = "PAVLVS - Certificado de conformidade"
VERIFICADOR_OFICIAL = "validar.iti.gov.br"

ROTULOS_TECNICOS = [
    ("campo", "Campo da assinatura"),
    ("padrao", "Padrão"),
    ("algoritmo_resumo", "Algoritmo de resumo"),
    ("algoritmo_assinatura", "Algoritmo de assinatura"),
    ("numero_de_serie", "Número de série do certificado"),
    ("valido_de", "Certificado válido de"),
    ("valido_ate", "Certificado válido até"),
    ("carimbo_de_tempo", "Carimbo de tempo"),
]


def resumo_do_arquivo(caminho: Path) -> dict:
    """SHA-256, tamanho e paginas: o que identifica ESTE arquivo, e nao outro
    com o mesmo nome."""
    import leitor_pdf

    dados = caminho.read_bytes()
    paginas = 0
    try:
        with leitor_pdf.abrir(dados) as doc:
            paginas = len(doc)
    except Exception:  # noqa: BLE001 - o relatorio sai mesmo sem contar paginas
        pass
    return {"sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados), "paginas": paginas}


def veredito(assinaturas: list[dict]) -> tuple[str, str]:
    """(tom, frase) do resultado geral: ok, alerta ou sem."""
    validas = [a for a in assinaturas if not a.get("erro")]
    if not validas:
        erro = next((a["erro"] for a in assinaturas if a.get("erro")), "")
        return "sem", erro or "Este PDF não tem assinatura digital."
    alteradas = [a for a in validas if a.get("intacta") is False]
    parciais = [a for a in validas if a.get("cobre_documento_todo") is False and a.get("intacta") is not False]
    n = len(validas)
    if alteradas:
        return "alerta", f"{len(alteradas)} de {n} assinatura{'s' if n > 1 else ''}: o documento foi alterado depois de assinado."
    if parciais:
        return "alerta", ("Assinatura íntegra, mas houve acréscimo ao arquivo depois dela "
                          "(outra assinatura ou anotação). O trecho assinado não foi alterado.")
    return "ok", (f"{n} assinatura{'s' if n > 1 else ''} íntegra{'s' if n > 1 else ''}: "
                  "o documento não foi alterado depois de assinado.")


def gerar(caminho: Path | str, assinaturas: list[dict], pasta: Path) -> Path:
    """Monta o PDF do relatorio em `pasta` e devolve o caminho."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    alvo = Path(caminho)
    info = resumo_do_arquivo(alvo)
    agora = datetime.now()
    tom, frase = veredito(assinaturas)

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=colors.Color(.15, .15, .15))
    miudo = ParagraphStyle("miudo", parent=base, fontSize=8, leading=11, textColor=colors.Color(.4, .4, .4))
    marca = ParagraphStyle("marca", parent=base, fontName="Times-Bold", fontSize=22, leading=26, textColor=colors.Color(.09, .09, .09))
    titulo = ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=13, leading=17)
    secao = ParagraphStyle("secao", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=10, spaceAfter=4)
    cor = {"ok": colors.Color(.13, .5, .27), "alerta": colors.Color(.72, .2, .15), "sem": colors.Color(.35, .35, .35)}[tom]
    destaque = ParagraphStyle("destaque", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=cor)

    def tabela(linhas):
        t = Table([[Paragraph(escape(r), miudo), Paragraph(escape(str(v)), base)] for r, v in linhas],
                  colWidths=[5.2 * cm, None])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.Color(.85, .85, .85)),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    fluxo = [
        Paragraph("PAVLVS", marca),
        Paragraph("Certificado de conformidade", titulo),
        Paragraph(f"Conferência feita em {agora:%d/%m/%Y às %H:%M}, nesta máquina, pelo PAULUS Legal.", miudo),
        Spacer(1, 12),
        Paragraph(escape(frase), destaque),
        Paragraph("Documento conferido", secao),
        tabela([
            ("Arquivo", alvo.name),
            ("SHA-256", info["sha256"]),
            ("Tamanho", f"{info['bytes']:,} bytes".replace(",", ".")),
            ("Páginas", info["paginas"] or "—"),
        ]),
    ]

    validas = [a for a in assinaturas if not a.get("erro")]
    for i, a in enumerate(validas, start=1):
        integridade = {True: "íntegra — não alterado depois de assinado",
                       False: "ALTERADO depois de assinado", None: "não foi possível conferir"}[a.get("intacta")]
        cobertura = {True: "o arquivo inteiro", False: "parte do arquivo (houve acréscimo depois)",
                     None: "não informado"}[a.get("cobre_documento_todo")]
        linhas = [
            ("Assinante", a.get("titular") or "—"),
            ("Autoridade certificadora", a.get("emissor") or "—"),
            ("ICP-Brasil", "pelo nome, a AC emissora é da ICP-Brasil (a cadeia não foi conferida)"
             if a.get("icp_brasil") else "a AC emissora não está na lista ICP-Brasil que o programa conhece"),
            ("Assinado em", a.get("quando") or "—"),
            ("Integridade", integridade),
            ("Cobre", cobertura),
        ] + [(r, a["tecnico"][k]) for k, r in ROTULOS_TECNICOS if (a.get("tecnico") or {}).get(k)]
        fluxo += [Paragraph(f"Assinatura {i}" if len(validas) > 1 else "Assinatura", secao), tabela(linhas)]

    fluxo += [
        Paragraph("Limites desta conferência", secao),
        Paragraph(
            "Esta conferência foi feita sem internet. Ela confirma quem assinou, quem emitiu o certificado, "
            "a data registrada e se o documento foi alterado depois da assinatura. Ela não consulta se o "
            "certificado foi revogado nem monta a cadeia até a raiz oficial da ICP-Brasil. Para a validação "
            f"jurídica completa, confira o arquivo original no verificador do ITI: {VERIFICADOR_OFICIAL}.", base),
        Spacer(1, 6),
        Paragraph("O SHA-256 acima identifica o arquivo conferido: qualquer alteração nele muda esse valor.", miudo),
    ]

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillGray(0.45)
        canvas.drawString(2 * cm, 1.2 * cm, f"{NOME} · {alvo.name}"[:110])
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {doc.page}")
        canvas.restoreState()

    saida = io.BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title=NOME, author="PAULUS Legal")
    doc.build(fluxo, onFirstPage=rodape, onLaterPages=rodape)

    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{NOME} - {alvo.stem}.pdf"
    destino.write_bytes(saida.getvalue())
    return destino
