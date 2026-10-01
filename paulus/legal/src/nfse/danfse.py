"""
O DANFSe — o documento auxiliar da NFS-e, em PDF, gerado a partir do XML.

A API de geração do DANFSe do Ambiente Nacional foi suspensa em 03/08/2026
(NT 008, v1.02, §1): o documento passa a ser gerado pelo software do
emitente, no leiaute da NT 008. Este módulo segue os blocos e a ordem da NT
(§2.1): identificação com QR Code para a consulta pública, prestador,
tomador, destinatário, intermediário, serviço, tributação municipal,
federal, IBS/CBS, valor total e informações complementares; uma página A4,
retrato, borda de 1 ponto e linhas de 0,5 ponto, títulos de bloco em caixa
alta com fundo cinza claro.

Diferenças conhecidas, ditas em vez de escondidas: a fonte é a Helvetica do
PDF (de métrica igual à Arial pedida) e a logomarca oficial da NFS-e não vem
embutida (o cabeçalho traz "NFS-e" em texto). Em produção restrita o
cabeçalho diz "NFS-e SEM VALIDADE JURÍDICA" (§2).

Tudo o que é impresso sai do XML da nota: "não poderão ser impressas
informações que não constem do arquivo da NFS-e" (§2.1).
"""

from __future__ import annotations

import io

from lxml import etree

from . import tabelas
from .dinheiro import centavos_do_xml, reais

NS = {"n": "http://www.sped.fazenda.gov.br/nfse"}
URL_CONSULTA = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave="


def url_qr(chave: str) -> str:
    """O endereço do QR Code (NT 008, §2.4.3)."""
    return URL_CONSULTA + chave


def _t(no, caminho: str) -> str:
    if no is None:
        return ""
    return (no.findtext(caminho, default="", namespaces=NS) or "").strip()


def _r(texto: str) -> str:
    return reais(centavos_do_xml(texto)) if texto else "-"


def _doc(no) -> str:
    import campos_br

    for tag in ("CNPJ", "CPF", "NIF"):
        v = _t(no, f"n:{tag}")
        if v:
            return campos_br.exibir_documento(v) if tag != "NIF" else v
    return "-"


def _pct(texto: str) -> str:
    """"5.00" -> "5,00%" (o número do XML, escrito como se lê no Brasil)."""
    return (texto.replace(".", ",") + "%") if texto else "-"


def _data_hora(iso: str) -> str:
    if not iso:
        return "-"
    d, _, h = iso.partition("T")
    p = d.split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" + (f" {h[:8]}" if h else "") if len(p) == 3 else iso


def _endereco(no) -> tuple[str, str, str]:
    """(endereço, município/UF, IBGE/CEP) de um grupo end/enderNac."""
    if no is None:
        return "-", "-", "-"
    cmun = _t(no, "n:endNac/n:cMun") or _t(no, "n:cMun")
    cep = _t(no, "n:endNac/n:CEP") or _t(no, "n:CEP")
    m = tabelas.municipio(cmun) or {}
    linha = ", ".join(x for x in (_t(no, "n:xLgr"), _t(no, "n:nro"), _t(no, "n:xCpl"), _t(no, "n:xBairro")) if x)
    return linha or "-", (f"{m.get('nome', '')}/{m.get('uf', '')}" if m else (cmun or "-")), f"{cmun or '-'} / {cep or '-'}"


def dados_do_xml(xml: bytes) -> dict:
    """O que vai no DANFSe, tirado só do XML da NFS-e."""
    raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    inf = raiz.find("n:infNFSe", NS)
    dps = inf.find("n:DPS/n:infDPS", NS)
    prest_dps = dps.find("n:prest", NS)
    emit = inf.find("n:emit", NS)
    toma = dps.find("n:toma", NS)
    trib = dps.find("n:valores/n:trib", NS)
    val = inf.find("n:valores", NS)
    ib = inf.find("n:IBSCBS", NS)
    ib_dps = dps.find("n:IBSCBS", NS)
    chave = (inf.get("Id") or "")[3:]
    dom = tabelas.dominio
    op = _t(prest_dps, "n:regTrib/n:opSimpNac")
    end_emit = _endereco(emit.find("n:enderNac", NS)) if emit is not None else ("-", "-", "-")
    end_toma = _endereco(toma.find("n:end", NS)) if toma is not None else ("-", "-", "-")
    tp_ret = _t(trib, "n:tribFed/n:piscofins/n:tpRetPisCofins")
    ctribnac = _t(dps, "n:serv/n:cServ/n:cTribNac")
    loc = _t(dps, "n:serv/n:locPrest/n:cLocPrestacao")
    mloc = tabelas.municipio(loc) or {}
    minc = tabelas.municipio(_t(inf, "n:cLocIncid")) or {}
    v_liq = centavos_do_xml(_t(val, "n:vLiq")) if _t(val, "n:vLiq") else 0
    v_ibs = centavos_do_xml(_t(ib, "n:totCIBS/n:gIBS/n:vIBSTot")) if ib is not None and _t(ib, "n:totCIBS/n:gIBS/n:vIBSTot") else 0
    v_cbs = centavos_do_xml(_t(ib, "n:totCIBS/n:gCBS/n:vCBS")) if ib is not None and _t(ib, "n:totCIBS/n:gCBS/n:vCBS") else 0
    tot_nf = _t(ib, "n:totCIBS/n:vTotNF") if ib is not None else ""
    return {
        "homologacao": _t(dps, "n:tpAmb") == "2",
        "municipio_emissor": _t(inf, "n:xLocEmi"),
        "chave": chave,
        "numero": _t(inf, "n:nNFSe"),
        "competencia": _data_hora(_t(dps, "n:dCompet")),
        "emissao_nfse": _data_hora(_t(inf, "n:dhProc")),
        "numero_dps": _t(dps, "n:nDPS"),
        "serie_dps": _t(dps, "n:serie"),
        "emissao_dps": _data_hora(_t(dps, "n:dhEmi")),
        "emitente": {"1": "Prestador", "2": "Tomador", "3": "Intermediário"}.get(_t(dps, "n:tpEmit"), "-"),
        "situacao": {"100": "NFS-e gerada", "102": "Gerada por decisão judicial/administrativa"}.get(_t(inf, "n:cStat"), _t(inf, "n:cStat")),
        "finalidade": "Regular" if _t(ib_dps, "n:finNFSe") in ("", "0") else _t(ib_dps, "n:finNFSe"),
        "prestador": {"doc": _doc(emit), "im": _t(emit, "n:IM") or _t(prest_dps, "n:IM") or "-",
                      "fone": _t(emit, "n:fone") or "-", "nome": _t(emit, "n:xNome") or "-",
                      "municipio": end_emit[1], "ibge_cep": end_emit[2], "endereco": end_emit[0],
                      "email": _t(emit, "n:email") or "-",
                      "simples": dom("opcao_simples").get(op, op or "-"),
                      "apuracao": dom("regime_apuracao_sn").get(_t(prest_dps, "n:regTrib/n:regApTribSN"), "-")},
        "tomador": None if toma is None else {
            "doc": _doc(toma), "im": _t(toma, "n:IM") or "-", "fone": _t(toma, "n:fone") or "-",
            "nome": _t(toma, "n:xNome") or "-", "municipio": end_toma[1], "ibge_cep": end_toma[2],
            "endereco": end_toma[0], "email": _t(toma, "n:email") or "-"},
        "servico": {"codigo": f"{ctribnac[:2]}.{ctribnac[2:4]}.{ctribnac[4:]}" if len(ctribnac) == 6 else ctribnac,
                    "codigo_mun": _t(dps, "n:serv/n:cServ/n:cTribMun") or "-",
                    "nbs": _t(dps, "n:serv/n:cServ/n:cNBS") or "-",
                    "local": f"{mloc.get('nome', loc)}/{mloc.get('uf', '')}" if loc else "-",
                    "descricao_codigo": _t(inf, "n:xTribNac") or (tabelas.servico(ctribnac) or {}).get("descricao", "-"),
                    "descricao": _t(dps, "n:serv/n:cServ/n:xDescServ")},
        "iss": {"tributacao": dom("tributacao_iss").get(_t(trib, "n:tribMun/n:tribISSQN"), "-"),
                "incidencia": f"{minc.get('nome', '-')}/{minc.get('uf', '')}",
                "regime_especial": dom("regime_especial").get(_t(prest_dps, "n:regTrib/n:regEspTrib"), "-"),
                "bc": _r(_t(val, "n:vBC")), "aliquota": _pct(_t(val, "n:pAliqAplic")),
                "retencao": dom("retencao_iss").get(_t(trib, "n:tribMun/n:tpRetISSQN"), "-"),
                "iss": _r(_t(val, "n:vISSQN")),
                "desconto": _r(_t(dps, "n:valores/n:vDescCondIncond/n:vDescIncond"))},
        "federal": {"irrf": _r(_t(trib, "n:tribFed/n:vRetIRRF")), "cp": _r(_t(trib, "n:tribFed/n:vRetCP")),
                    "contribuicoes": _r(_t(trib, "n:tribFed/n:vRetCSLL")),
                    "pis": _r(_t(trib, "n:tribFed/n:piscofins/n:vPis")), "cofins": _r(_t(trib, "n:tribFed/n:piscofins/n:vCofins")),
                    "descricao": dom("retencao_pis_cofins").get(tp_ret, "-") if tp_ret else "-"},
        "ibscbs": None if ib is None else {
            "cst": f"{_t(ib_dps, 'n:valores/n:trib/n:gIBSCBS/n:CST')} / {_t(ib_dps, 'n:valores/n:trib/n:gIBSCBS/n:cClassTrib')}",
            "indop": f"{_t(ib_dps, 'n:cIndOp')} / {_t(ib, 'n:cLocalidadeIncid')} / {_t(ib, 'n:xLocalidadeIncid')}",
            "bc": _r(_t(ib, "n:valores/n:vBC")),
            "p_ibs_uf": _pct(_t(ib, "n:valores/n:uf/n:pIBSUF")), "p_ibs_mun": _pct(_t(ib, "n:valores/n:mun/n:pIBSMun")),
            "p_ef_uf": _pct(_t(ib, "n:valores/n:uf/n:pAliqEfetUF")), "p_ef_mun": _pct(_t(ib, "n:valores/n:mun/n:pAliqEfetMun")),
            "v_ibs_uf": _r(_t(ib, "n:totCIBS/n:gIBS/n:gIBSUFTot/n:vIBSUF")), "v_ibs_mun": _r(_t(ib, "n:totCIBS/n:gIBS/n:gIBSMunTot/n:vIBSMun")),
            "v_ibs": _r(_t(ib, "n:totCIBS/n:gIBS/n:vIBSTot")), "p_cbs": _pct(_t(ib, "n:valores/n:fed/n:pCBS")),
            "p_ef_cbs": _pct(_t(ib, "n:valores/n:fed/n:pAliqEfetCBS")), "v_cbs": _r(_t(ib, "n:totCIBS/n:gCBS/n:vCBS"))},
        "total": {"servico": _r(_t(dps, "n:valores/n:vServPrest/n:vServ")),
                  "desc_incond": _r(_t(dps, "n:valores/n:vDescCondIncond/n:vDescIncond")),
                  "desc_cond": _r(_t(dps, "n:valores/n:vDescCondIncond/n:vDescCond")),
                  "retencoes": _r(_t(val, "n:vTotalRet")), "liquido": _r(_t(val, "n:vLiq")),
                  "ibscbs": reais(v_ibs + v_cbs) if ib is not None else "-",
                  "liquido_ibscbs": _r(tot_nf) if tot_nf else reais(v_liq)},
        "complementares": _t(dps, "n:serv/n:infoCompl/n:xInfComp"),
        "tot_trib": " · ".join(x for x in (
            ("Federal " + _pct(_t(trib, "n:totTrib/n:pTotTrib/n:pTotTribFed"))) if _t(trib, "n:totTrib/n:pTotTrib/n:pTotTribFed") else "",
            ("Estadual " + _pct(_t(trib, "n:totTrib/n:pTotTrib/n:pTotTribEst"))) if _t(trib, "n:totTrib/n:pTotTrib/n:pTotTribEst") else "",
            ("Municipal " + _pct(_t(trib, "n:totTrib/n:pTotTrib/n:pTotTribMun"))) if _t(trib, "n:totTrib/n:pTotTrib/n:pTotTribMun") else "",
            ("Simples Nacional " + _pct(_t(trib, "n:totTrib/n:pTotTribSN"))) if _t(trib, "n:totTrib/n:pTotTribSN") else "") if x),
        "substituida": _t(dps, "n:subst/n:chSubstda"),
    }


def gerar(xml: bytes) -> bytes:
    """O PDF do DANFSe (uma página A4)."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    d = dados_do_xml(xml)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"DANFSe {d['numero']} - {d['chave']}")
    c.setAuthor("PAULUS Legal")
    larg, alt = A4
    m = 0.2 * cm
    x0, x1 = m, larg - m
    y = alt - m
    c.setLineWidth(1)
    c.rect(m, m, larg - 2 * m, alt - 2 * m)
    cinza = (0.95, 0.95, 0.95)

    def corta(texto: str, fonte: str, tam: float, largura: float) -> str:
        texto = str(texto or "-")
        if c.stringWidth(texto, fonte, tam) <= largura:
            return texto
        while texto and c.stringWidth(texto + "...", fonte, tam) > largura:
            texto = texto[:-1]
        return texto + "..."

    def titulo_bloco(texto: str) -> None:
        nonlocal y
        h = 10
        c.setFillColorRGB(*cinza)
        c.setLineWidth(0.5)
        c.rect(x0, y - h, x1 - x0, h, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x0 + 3, y - 7.5, texto.upper())
        y -= h

    def linha_campos(campos: list[tuple[str, str]], larguras: list[float] | None = None, h: float = 17,
                     sombra: set | None = None) -> None:
        nonlocal y
        total = x1 - x0
        larguras = larguras or [1 / len(campos)] * len(campos)
        x = x0
        c.setLineWidth(0.5)
        for i, ((rot, val), fr) in enumerate(zip(campos, larguras)):
            w = total * fr
            if sombra and i in sombra:
                c.setFillColorRGB(*cinza)
                c.rect(x, y - h, w, h, fill=1, stroke=0)
                c.setFillColorRGB(0, 0, 0)
            c.rect(x, y - h, w, h)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(x + 2, y - 6.5, corta(rot, "Helvetica-Bold", 6, w - 4))
            c.setFont("Helvetica", 7)
            c.drawString(x + 2, y - 14.5, corta(val, "Helvetica", 7, w - 4))
            x += w
        y -= h

    def texto_bloco(texto: str, h: float) -> None:
        nonlocal y
        c.setLineWidth(0.5)
        c.rect(x0, y - h, x1 - x0, h)
        c.setFont("Helvetica", 7)
        linhas, atual = [], ""
        for palavra in str(texto or "-").split():
            teste = (atual + " " + palavra).strip()
            if c.stringWidth(teste, "Helvetica", 7) > (x1 - x0 - 6):
                linhas.append(atual)
                atual = palavra
            else:
                atual = teste
        linhas.append(atual)
        maximo = max(1, int((h - 4) // 8.5))
        if len(linhas) > maximo:
            linhas = linhas[:maximo]
            linhas[-1] = corta(linhas[-1] + " ...", "Helvetica", 7, x1 - x0 - 6)
        for i, l in enumerate(linhas):
            c.drawString(x0 + 3, y - 8 - i * 8.5, l)
        y -= h

    # --- cabeçalho
    h = 1.3 * cm
    c.setFillColorRGB(*cinza)
    c.rect(x0, y - h, x1 - x0, h, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0 + 6, y - 0.85 * cm, "NFS-e")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(larg / 2, y - 0.5 * cm, "DANFSe v2.0")
    c.drawCentredString(larg / 2, y - 0.85 * cm, "Documento Auxiliar da NFS-e")
    if d["homologacao"]:
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(larg / 2, y - 1.15 * cm, "NFS-e SEM VALIDADE JURÍDICA")
    c.setFont("Helvetica", 8)
    c.drawRightString(x1 - 4, y - 0.45 * cm, d["municipio_emissor"] or "")
    c.setFont("Helvetica", 6)
    c.drawRightString(x1 - 4, y - 0.75 * cm, "Ambiente gerador: Sistema Nacional NFS-e")
    c.drawRightString(x1 - 4, y - 1.0 * cm, "Produção restrita (homologação)" if d["homologacao"] else "Produção")
    y -= h

    # --- identificação + QR
    topo = y
    qr_lado = 2.4 * cm
    coluna_qr = 3.8 * cm
    w_campos = (x1 - x0 - coluna_qr) / (x1 - x0)
    linha_campos([("CHAVE DE ACESSO DA NFS-E", d["chave"])], [w_campos])
    linha_campos([("NÚMERO DA NFS-E", d["numero"]), ("COMPETÊNCIA DA NFS-E", d["competencia"]),
                  ("DATA E HORA DA EMISSÃO DA NFS-E", d["emissao_nfse"])], [w_campos * f for f in (0.3, 0.3, 0.4)])
    linha_campos([("NÚMERO DA DPS", d["numero_dps"]), ("SÉRIE DA DPS", d["serie_dps"]),
                  ("DATA E HORA DA EMISSÃO DA DPS", d["emissao_dps"])], [w_campos * f for f in (0.3, 0.3, 0.4)])
    linha_campos([("EMITENTE DA NFS-E", d["emitente"]), ("SITUAÇÃO DA NFS-E", d["situacao"]),
                  ("FINALIDADE", d["finalidade"])], [w_campos * f for f in (0.3, 0.4, 0.3)], sombra={0})
    qr = QrCodeWidget(url_qr(d["chave"]))
    b = qr.getBounds()
    desenho = Drawing(qr_lado, qr_lado, transform=[qr_lado / (b[2] - b[0]), 0, 0, qr_lado / (b[3] - b[1]), 0, 0])
    desenho.add(qr)
    centro_qr = x1 - coluna_qr / 2
    renderPDF.draw(desenho, c, centro_qr - qr_lado / 2, topo - qr_lado - 0.05 * cm)
    c.setFont("Helvetica", 5)
    for i, t in enumerate(("A autenticidade desta NFS-e pode ser verificada",
                           "pela leitura deste código QR ou pela consulta da",
                           "chave de acesso no portal nacional da NFS-e")):
        c.drawCentredString(centro_qr, topo - qr_lado - 7 - i * 6, t)
    y = min(y, topo - qr_lado - 22)

    # --- prestador
    p = d["prestador"]
    titulo_bloco("Prestador / Fornecedor")
    linha_campos([("CNPJ / CPF / NIF", p["doc"]), ("Inscrição Municipal", p["im"]), ("Telefone", p["fone"])], [0.4, 0.3, 0.3])
    linha_campos([("Nome / Nome Empresarial", p["nome"]), ("Município / UF", p["municipio"]), ("Código IBGE / CEP", p["ibge_cep"])], [0.5, 0.25, 0.25])
    linha_campos([("Endereço", p["endereco"]), ("E-mail", p["email"])], [0.6, 0.4])
    linha_campos([("Simples Nacional na Data de Competência", p["simples"]), ("Regime de Apuração Tributária pelo SN", p["apuracao"])], [0.5, 0.5])

    # --- tomador, destinatário, intermediário
    titulo_bloco("Tomador / Adquirente da Operação")
    t = d["tomador"]
    if t:
        linha_campos([("CNPJ / CPF / NIF", t["doc"]), ("Inscrição Municipal", t["im"]), ("Telefone", t["fone"])], [0.4, 0.3, 0.3])
        linha_campos([("Nome / Nome Empresarial", t["nome"]), ("Município / UF", t["municipio"]), ("Código IBGE / CEP", t["ibge_cep"])], [0.5, 0.25, 0.25])
        linha_campos([("Endereço", t["endereco"]), ("E-mail", t["email"])], [0.6, 0.4])
    else:
        texto_bloco("TOMADOR/ADQUIRENTE DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e", 12)
    titulo_bloco("Destinatário da Operação")
    texto_bloco("O DESTINATÁRIO É O PRÓPRIO TOMADOR/ADQUIRENTE DA OPERAÇÃO", 12)
    titulo_bloco("Intermediário da Operação")
    texto_bloco("INTERMEDIÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e", 12)

    # --- serviço
    s = d["servico"]
    titulo_bloco("Serviço Prestado")
    linha_campos([("Código de Tributação Nacional / Municipal", f"{s['codigo']} / {s['codigo_mun']}"), ("Código da NBS", s["nbs"]),
                  ("Local da Prestação", s["local"])], [0.4, 0.25, 0.35])
    linha_campos([("Descrição do Código de Tributação Nacional", s["descricao_codigo"])])
    titulo_bloco("Descrição do Serviço")
    texto_bloco(s["descricao"], 52)

    # --- ISSQN
    i = d["iss"]
    titulo_bloco("Tributação Municipal (ISSQN)")
    linha_campos([("Tipo de Tributação do ISSQN", i["tributacao"]), ("Município de Incidência do ISSQN", i["incidencia"]),
                  ("Regime Especial de Tributação", i["regime_especial"])], [0.3, 0.35, 0.35])
    linha_campos([("Desconto Incondicionado", i["desconto"]), ("BC ISSQN", i["bc"]), ("Alíquota Aplicada", i["aliquota"]),
                  ("Retenção do ISSQN", i["retencao"]), ("ISSQN Apurado", i["iss"])], [0.2, 0.2, 0.15, 0.25, 0.2])

    # --- federal
    f = d["federal"]
    titulo_bloco("Tributação Federal (exceto CBS)")
    linha_campos([("IRRF", f["irrf"]), ("Contribuição Previdenciária - Retida", f["cp"]), ("Contribuições Sociais - Retidas", f["contribuicoes"]),
                  ("PIS - Débito Apuração Própria", f["pis"]), ("COFINS - Débito Apuração Própria", f["cofins"])])
    linha_campos([("Descrição das Contribuições Sociais - Retidas", f["descricao"])])

    # --- IBS/CBS
    titulo_bloco("Tributação IBS / CBS")
    ib = d["ibscbs"]
    if ib:
        linha_campos([("CST / cClassTrib", ib["cst"]), ("Indicador de Operação / IBGE / Município de Incidência", ib["indop"]),
                      ("Base de Cálculo Após Exclusões e Reduções", ib["bc"])], [0.2, 0.5, 0.3])
        linha_campos([("Alíquota IBS Estadual / Municipal", f"{ib['p_ibs_uf']} / {ib['p_ibs_mun']}"),
                      ("Alíq. Efetiva IBS Estadual", ib["p_ef_uf"]), ("Valor IBS Estadual", ib["v_ibs_uf"]),
                      ("Alíq. Efetiva IBS Municipal", ib["p_ef_mun"]), ("Valor IBS Municipal", ib["v_ibs_mun"])])
        linha_campos([("Valor Total Apurado do IBS", ib["v_ibs"]), ("Alíquota da CBS", ib["p_cbs"]),
                      ("Alíquota Efetiva da CBS", ib["p_ef_cbs"]), ("Valor Total Apurado da CBS", ib["v_cbs"])])
    else:
        texto_bloco("Sem o grupo IBS/CBS nesta NFS-e.", 12)

    # --- total
    tt = d["total"]
    titulo_bloco("Valor Total da NFS-e")
    linha_campos([("Valor da Operação / Serviço", tt["servico"]), ("Desconto Incondicionado", tt["desc_incond"]),
                  ("Desconto Condicionado", tt["desc_cond"]), ("Total das Retenções (ISSQN / Federais)", tt["retencoes"])])
    linha_campos([("Valor Líquido da NFS-e", tt["liquido"]), ("Total do IBS/CBS", tt["ibscbs"]),
                  ("Valor Líquido da NFS-e + IBS/CBS", tt["liquido_ibscbs"])], [0.35, 0.3, 0.35], sombra={2})

    # --- complementares
    titulo_bloco("Informações Complementares")
    extra = []
    if d["substituida"]:
        extra.append(f"Substitui a NFS-e de chave {d['substituida']}.")
    if d["complementares"]:
        extra.append(d["complementares"])
    if d["tot_trib"]:
        extra.append("Totais aproximados dos tributos (Lei 12.741/2012): " + d["tot_trib"])
    texto_bloco(" ".join(extra) or "-", max(30, y - m - 6))
    c.showPage()
    c.save()
    return buf.getvalue()
