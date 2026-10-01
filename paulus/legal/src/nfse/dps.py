"""
A DPS (Declaração de Prestação de Serviço) em XML, no leiaute da NFS-e
Nacional, versão 1.01 (XSD 1.01-20260209 e 1.01-20260727), com o grupo
IBSCBS da NT 004.

A ordem dos elementos é a do XSD (`xs:sequence`), e o documento sai sem
prefixo de namespace e em UTF-8 — a Sefin recusa prefixo (E1228) e outra
codificação (E1229). Quem emite é o prestador (`tpEmit` = 1): por isso a
DPS não leva nome nem endereço do prestador (E0121), só CNPJ/CPF, inscrição
municipal e regime.

Os valores vêm da conta (tributos.py) e entram como texto no formato do XSD
(dinheiro.decimal_xml), nunca de float.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from lxml import etree

from .dinheiro import decimal_xml, percentual_xml

NS = "http://www.sped.fazenda.gov.br/nfse"
VERSAO = "1.01"
FUSO_BRASILIA = timezone(timedelta(hours=-3))

# Os cIndOp que obrigam o endereço do tomador (RN 255 do Anexo I).
INDOP_EXIGE_ENDERECO = {"030102", "050102", "100101", "100301", "100501", "030103", "050103",
                        "100102", "100201", "100302", "100401", "100502", "100601"}


def id_dps(cmun: str, documento: str, serie: str, numero: int) -> str:
    """"DPS" + município(7) + tipo de inscrição(1) + inscrição(14) + série(5) + número(15) (TSIdDPS)."""
    doc = re.sub(r"[^0-9A-Z]", "", str(documento).upper())
    if len(doc) == 11:
        tipo, insc = "1", doc.zfill(14)
    elif len(doc) == 14:
        tipo, insc = "2", doc
    else:
        raise ValueError("o documento do prestador precisa ser CPF ou CNPJ")
    return f"DPS{cmun}{tipo}{insc}{int(serie):05d}{int(numero):015d}"


def dh_emi(quando: datetime | None = None) -> str:
    """Data e hora com fuso, como o XSD pede (AAAA-MM-DDThh:mm:ss-03:00)."""
    q = (quando or datetime.now(FUSO_BRASILIA)).astimezone(FUSO_BRASILIA)
    return q.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"


def _sub(pai, nome: str, texto=None):
    el = etree.SubElement(pai, f"{{{NS}}}{nome}")
    if texto is not None:
        el.text = str(texto)
    return el


def _documento(pai, documento: str) -> None:
    doc = re.sub(r"[^0-9A-Z]", "", str(documento or "").upper())
    if len(doc) == 14:
        _sub(pai, "CNPJ", doc)
    elif len(doc) == 11:
        _sub(pai, "CPF", doc)
    else:
        raise ValueError("documento do tomador precisa ser CPF ou CNPJ")


def _limpa(texto: str, maximo: int) -> str:
    return " ".join(str(texto or "").split())[:maximo]


def montar(*, prest: dict, nota: dict, conta, ambiente: str, serie: str, numero: int,
           quando: datetime | None = None, ver_aplic: str = "PAULUS") -> tuple[bytes, str]:
    """
    Devolve (xml em bytes, Id da DPS). `nota` é o rascunho conferido:
    {competencia, descricao, tomador{...}, municipio_incidencia, ctribnac, nbs, ctribmun,
     informacoes, substitui{chave, motivo, texto}}.
    """
    tomador = nota.get("tomador") or {}
    serv = prest.get("servico") or {}
    cmun_prest = prest["municipio"]
    ident = id_dps(cmun_prest, prest["documento"], serie, numero)

    dps = etree.Element(f"{{{NS}}}DPS", nsmap={None: NS})
    dps.set("versao", VERSAO)
    inf = _sub(dps, "infDPS")
    inf.set("Id", ident)
    _sub(inf, "tpAmb", "1" if ambiente == "producao" else "2")
    _sub(inf, "dhEmi", dh_emi(quando))
    _sub(inf, "verAplic", _limpa(ver_aplic, 20))
    _sub(inf, "serie", str(int(serie)))
    _sub(inf, "nDPS", str(int(numero)))
    _sub(inf, "dCompet", str(nota["competencia"])[:10])
    _sub(inf, "tpEmit", "1")
    _sub(inf, "cLocEmi", cmun_prest)

    subst = nota.get("substitui") or {}
    if subst.get("chave"):
        g = _sub(inf, "subst")
        _sub(g, "chSubstda", subst["chave"])
        _sub(g, "cMotivo", subst["motivo"])
        if subst.get("texto"):
            _sub(g, "xMotivo", _limpa(subst["texto"], 255))

    # Prestador: o emitente é ele mesmo, então nem nome nem endereço (E0121).
    p = _sub(inf, "prest")
    _documento(p, prest["documento"])
    if prest.get("inscricao_municipal"):
        _sub(p, "IM", prest["inscricao_municipal"])
    rt = _sub(p, "regTrib")
    _sub(rt, "opSimpNac", prest["opcao_simples"])
    if prest.get("opcao_simples") == "3" and prest.get("regime_apuracao_sn"):
        _sub(rt, "regApTribSN", prest["regime_apuracao_sn"])
    _sub(rt, "regEspTrib", prest.get("regime_especial") or "0")

    # Tomador.
    if tomador.get("documento"):
        t = _sub(inf, "toma")
        _documento(t, tomador["documento"])
        if tomador.get("inscricao_municipal"):
            _sub(t, "IM", re.sub(r"\s", "", tomador["inscricao_municipal"])[:15])
        _sub(t, "xNome", _limpa(tomador.get("nome"), 300))
        if tomador.get("cmun") and tomador.get("cep") and tomador.get("logradouro"):
            e = _sub(t, "end")
            en = _sub(e, "endNac")
            _sub(en, "cMun", tomador["cmun"])
            _sub(en, "CEP", re.sub(r"\D", "", tomador["cep"]))
            _sub(e, "xLgr", _limpa(tomador["logradouro"], 255))
            _sub(e, "nro", _limpa(tomador.get("numero") or "S/N", 60))
            if tomador.get("complemento"):
                _sub(e, "xCpl", _limpa(tomador["complemento"], 156))
            _sub(e, "xBairro", _limpa(tomador.get("bairro") or "", 60))
        fone = re.sub(r"\D", "", str(tomador.get("telefone") or ""))
        if 6 <= len(fone) <= 20:
            _sub(t, "fone", fone)
        if tomador.get("email"):
            _sub(t, "email", _limpa(tomador["email"], 80))

    # Serviço.
    s = _sub(inf, "serv")
    lp = _sub(s, "locPrest")
    _sub(lp, "cLocPrestacao", nota.get("municipio_incidencia") or cmun_prest)
    cs = _sub(s, "cServ")
    _sub(cs, "cTribNac", nota.get("ctribnac") or serv.get("ctribnac"))
    ctribmun = nota.get("ctribmun") if nota.get("ctribmun") is not None else serv.get("ctribmun")
    if ctribmun:
        _sub(cs, "cTribMun", ctribmun)
    desc = str(nota.get("descricao") or serv.get("descricao") or "").strip()
    _sub(cs, "xDescServ", desc[:2000])
    nbs = nota.get("nbs") or serv.get("nbs")
    if nbs:
        _sub(cs, "cNBS", nbs)
    if nota.get("informacoes"):
        ic = _sub(s, "infoCompl")
        _sub(ic, "xInfComp", str(nota["informacoes"]).strip()[:2000])

    # Valores.
    v = _sub(inf, "valores")
    vsp = _sub(v, "vServPrest")
    _sub(vsp, "vServ", decimal_xml(conta.v_serv))
    if conta.v_desc_incond:
        dc = _sub(v, "vDescCondIncond")
        _sub(dc, "vDescIncond", decimal_xml(conta.v_desc_incond))
    trib = _sub(v, "trib")
    tm = _sub(trib, "tribMun")
    _sub(tm, "tribISSQN", "1")
    _sub(tm, "tpRetISSQN", "2" if conta.iss_retido else "1")
    if conta.informar_paliq:
        _sub(tm, "pAliq", percentual_xml(conta.aliquota_iss_bp))

    r = conta.retencoes or {}
    if conta.v_ret_csll or r.get("cp") or r.get("irrf"):
        tf = _sub(trib, "tribFed")
        if conta.v_ret_csll:
            pc = _sub(tf, "piscofins")
            _sub(pc, "CST", (prest.get("pis_cofins") or {}).get("cst") or "00")
            _sub(pc, "tpRetPisCofins", conta.tp_ret_pis_cofins)
        if r.get("cp"):
            _sub(tf, "vRetCP", decimal_xml(r["cp"]))
        if r.get("irrf"):
            _sub(tf, "vRetIRRF", decimal_xml(r["irrf"]))
        if conta.v_ret_csll:
            _sub(tf, "vRetCSLL", decimal_xml(conta.v_ret_csll))

    tt = prest.get("total_tributos") or {}
    tot = _sub(trib, "totTrib")
    op = prest.get("opcao_simples")
    if op == "3" and tt.get("modo") == "simples":
        _sub(tot, "pTotTribSN", percentual_xml(int(tt.get("simples_bp") or 0)))
    elif op == "2" and not any(int(tt.get(k) or 0) for k in ("federal_bp", "estadual_bp", "municipal_bp")):
        # MEI sem percentual configurado: "não informar" (indTotTrib = 0) é aceito para MEI.
        _sub(tot, "indTotTrib", "0")
    else:
        pt = _sub(tot, "pTotTrib")
        _sub(pt, "pTotTribFed", percentual_xml(int(tt.get("federal_bp") or 0)))
        _sub(pt, "pTotTribEst", percentual_xml(int(tt.get("estadual_bp") or 0)))
        _sub(pt, "pTotTribMun", percentual_xml(int(tt.get("municipal_bp") or 0)))

    # IBS/CBS (NT 004): a DPS declara; a Sefin calcula.
    ib = prest.get("ibscbs") or {}
    if ib.get("enviar"):
        g = _sub(inf, "IBSCBS")
        _sub(g, "finNFSe", "0")
        _sub(g, "indFinal", ib.get("indfinal") or "0")
        _sub(g, "cIndOp", ib["cindop"])
        _sub(g, "indDest", "0")
        vg = _sub(g, "valores")
        tg = _sub(vg, "trib")
        gi = _sub(tg, "gIBSCBS")
        _sub(gi, "CST", ib["cst"])
        _sub(gi, "cClassTrib", ib["cclasstrib"])

    xml = etree.tostring(dps, xml_declaration=True, encoding="UTF-8")
    return xml, ident
