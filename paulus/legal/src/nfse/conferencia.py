"""
A conferência antes de aprovar: o XSD oficial, as regras de negócio que dá
para checar aqui e os avisos do cartão.

Erro bloqueia (a nota não vai para Aprovações nem é assinada); aviso não.
Cada erro diz qual campo e, quando vem de uma regra da Sefin, o código dela —
para a pessoa saber que a Sefin recusaria do mesmo jeito.
"""

from __future__ import annotations

import re
import threading
from datetime import date
from pathlib import Path

from lxml import etree

import campos_br

from . import tabelas
from .dps import INDOP_EXIGE_ENDERECO

PASTA_XSD = Path(__file__).resolve().parent / "xsd"
# O XSD que confere a DPS (docs/PROGRESSO-NFSE.md, N2). A página de produção
# ainda lista o de 09/02/2026, mas nele a série da DPS tem o padrão
# "^0{0,4}\d{1,5}$" — e no XML Schema "^" e "$" são caracteres comuns, não
# âncoras: nenhuma série passa num validador que segue a norma (o da Sefin
# aceita porque traduz o padrão para o regex do .NET). O de 27/07/2026, da
# produção restrita, corrigiu o padrão e já aceita o CNPJ alfanumérico, que
# a produção recebe desde 10/08/2026. Os dois ficam guardados; a conferência
# usa o corrigido nos dois ambientes.
XSD_POR_AMBIENTE = {"producao_restrita": "1.01-20260727", "producao": "1.01-20260727"}

_esquemas: dict[tuple[str, str], etree.XMLSchema] = {}
_trava = threading.Lock()

# Nome do elemento do XSD -> o que a pessoa entende.
CAMPOS = {
    "tpAmb": "ambiente", "dhEmi": "data e hora da emissão", "serie": "série", "nDPS": "número da DPS",
    "dCompet": "competência", "cLocEmi": "município do prestador", "CNPJ": "CNPJ", "CPF": "CPF",
    "IM": "inscrição municipal", "xNome": "nome do tomador", "cMun": "município (IBGE)", "CEP": "CEP",
    "xLgr": "logradouro", "nro": "número do endereço", "xBairro": "bairro", "email": "e-mail",
    "cLocPrestacao": "município da prestação", "cTribNac": "código de tributação nacional",
    "cTribMun": "código de tributação municipal", "xDescServ": "descrição do serviço", "cNBS": "NBS",
    "vServ": "valor do serviço", "pAliq": "alíquota do ISS", "vRetIRRF": "IRRF retido",
    "vRetCSLL": "PIS/COFINS/CSLL retidos", "vRetCP": "CP retida", "CST": "CST", "cClassTrib": "cClassTrib",
    "cIndOp": "indicador da operação", "xInfComp": "informações complementares",
}


def esquema(raiz: str, ambiente: str) -> etree.XMLSchema:
    """O XSD oficial (DPS_v1.01.xsd ou pedRegEvento_v1.01.xsd) do ambiente, carregado uma vez."""
    pasta = PASTA_XSD / XSD_POR_AMBIENTE.get(ambiente, XSD_POR_AMBIENTE["producao_restrita"])
    chave = (str(pasta), raiz)
    with _trava:
        if chave not in _esquemas:
            parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
            _esquemas[chave] = etree.XMLSchema(etree.parse(str(pasta / raiz), parser))
        return _esquemas[chave]


def validar_xsd(xml: bytes, ambiente: str, raiz: str = "DPS_v1.01.xsd") -> list[str]:
    """Os erros do XSD em português curto ("valor do serviço: …"). Vazio = válido."""
    sch = esquema(raiz, ambiente)
    doc = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    if sch.validate(doc):
        return []
    erros = []
    for e in sch.error_log:
        m = re.search(r"\{[^}]*\}(\w+)", e.message)
        campo = CAMPOS.get(m.group(1), m.group(1)) if m else "XML"
        erros.append(f"{campo}: {e.message.split(': ', 1)[-1][:200]} (linha {e.line}; esquema oficial {raiz})")
    return erros


def _doc(valor) -> str:
    return campos_br.normalizado(valor)


def conferir(*, prest: dict, nota: dict, conta, municipio: dict | None = None,
             certificado: dict | None = None, lancamento: dict | None = None, hoje: date | None = None) -> tuple[list[str], list[str]]:
    """
    As regras locais e os avisos (seção 2, item 3 do prompt). Devolve
    (erros, avisos). O XSD é conferido à parte, no XML montado.
    """
    hoje = hoje or date.today()
    erros: list[str] = list(conta.erros)
    avisos: list[str] = list(conta.avisos)
    tomador = nota.get("tomador") or {}

    # --- obrigatórios da nota (o que falta é pedido, nunca inventado)
    if not str(nota.get("descricao") or (prest.get("servico") or {}).get("descricao") or "").strip():
        erros.append("falta a descrição do serviço")
    comp = str(nota.get("competencia") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", comp):
        erros.append("falta a competência (data de início da prestação do serviço)")
    else:
        try:
            dc = date.fromisoformat(comp)
            if dc > hoje:
                erros.append("a competência não pode ser depois de hoje (regra E0015 da Sefin)")
            elif (dc.year, dc.month) < (hoje.year, hoje.month):
                avisos.append(f"a competência é de {comp[5:7]}/{comp[:4]}, mês anterior ao atual: confira se o mês "
                              "já foi fechado com o contador")
            ib = prest.get("ibscbs") or {}
            if ib.get("enviar") and dc < date(2026, 1, 1):
                erros.append("IBS/CBS só a partir da competência 01/01/2026 (regra E0850): desligue o grupo para esta nota")
        except ValueError:
            erros.append("competência inválida")

    # --- tomador
    doc = _doc(tomador.get("documento"))
    if not doc:
        erros.append("falta o CPF ou CNPJ do tomador")
    elif len(doc) == 14 and not campos_br.cnpj_valido(doc):
        erros.append("o CNPJ do tomador não confere (dígito verificador; regra E0188)")
    elif len(doc) == 11 and not campos_br.cpf_valido(doc):
        erros.append("o CPF do tomador não confere (dígito verificador)")
    elif len(doc) not in (11, 14):
        erros.append("o documento do tomador precisa ser CPF ou CNPJ")
    if not str(tomador.get("nome") or "").strip():
        erros.append("falta o nome do tomador")
    tem_endereco = all(str(tomador.get(k) or "").strip() for k in ("logradouro", "bairro", "cep", "cmun"))
    ib = prest.get("ibscbs") or {}
    exige_end = (ib.get("enviar") and ib.get("cindop") in INDOP_EXIGE_ENDERECO) or conta.iss_retido
    if not tem_endereco:
        if exige_end:
            erros.append("falta o endereço completo do tomador (logradouro, bairro, CEP e município): "
                         + ("o ISS retido" if conta.iss_retido else f"o indicador da operação {ib.get('cindop')}")
                         + " exige o endereço (regras E0237 / RN 255)")
        else:
            avisos.append("o tomador está sem endereço completo")
    if tomador.get("cep") and not re.fullmatch(r"\d{8}", re.sub(r"\D", "", str(tomador["cep"]))):
        erros.append("o CEP do tomador precisa de 8 dígitos")
    if tomador.get("cmun") and not tabelas.municipio(tomador["cmun"]):
        erros.append("o município do tomador não está na tabela oficial do IBGE")
    if tomador.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(tomador["email"])):
        erros.append("o e-mail do tomador não parece um e-mail (regra E0247)")

    # --- serviço
    ctribnac = nota.get("ctribnac") or (prest.get("servico") or {}).get("ctribnac")
    if not tabelas.servico(ctribnac or ""):
        erros.append("o código de tributação nacional não está na lista oficial (regra E0310)")
    nbs = nota.get("nbs") or (prest.get("servico") or {}).get("nbs")
    if nbs and not tabelas.nbs(nbs):
        erros.append("a NBS não está na tabela oficial (regra E0316)")
    if ib.get("enviar") and not nbs:
        erros.append("com IBS/CBS a NBS é obrigatória (regra E0322)")
    if ib.get("enviar") and (not ib.get("cst") or not ib.get("cclasstrib")):
        erros.append("IBS/CBS: falta o CST e o cClassTrib na configuração (pergunte ao contador)")
    if conta.v_ret_csll and not (prest.get("pis_cofins") or {}).get("cst"):
        erros.append("há PIS/COFINS/CSLL retidos e falta o CST do PIS/COFINS na configuração (pergunte ao contador)")
    inc = nota.get("municipio_incidencia") or prest.get("municipio")
    if inc and not tabelas.municipio(inc):
        erros.append("o município da prestação não está na tabela oficial do IBGE (regra E0302)")
    if conta.informar_paliq and conta.aliquota_iss_bp > 500:
        erros.append("a alíquota do ISS não pode passar de 5% (regra E0595)")
    if conta.informar_paliq and not conta.aliquota_iss_bp:
        erros.append("esta nota precisa da alíquota do ISS e ela não está configurada")
    local = tabelas.local_de_incidencia(ctribnac or "")
    if tomador.get("cmun") and tomador.get("cmun") != prest.get("municipio"):
        if local in ("LP", "ET"):
            avisos.append("o tomador é de outro município e, para este serviço, o ISS incide "
                          + ("no local da prestação" if local == "LP" else "no município do tomador")
                          + " (LC 116): confira o município da prestação")
        elif local == "EP":
            avisos.append("o tomador é de outro município; para este serviço o ISS continua no município do escritório (LC 116, art. 3º)")
    if inc and inc != prest.get("municipio"):
        avisos.append("o município da prestação é diferente do município do escritório: confira a incidência do ISS")

    # --- prestador e regime (as regras que a Sefin aplicaria)
    if prest.get("opcao_simples") == "2" and any((conta.retencoes or {}).values()):
        erros.append("MEI não informa tributos federais (regra E0676)")
    if prest.get("regime_especial", "0") != "0" and conta.iss_retido:
        erros.append("com regime especial não há ISS retido (regra E0588)")

    # --- de onde veio e o que está em volta
    if lancamento and int(lancamento.get("centavos") or 0) != conta.v_serv:
        from .dinheiro import reais

        avisos.append(f"o valor da nota ({reais(conta.v_serv)}) é diferente do recebimento ({reais(int(lancamento['centavos']))})")
    if certificado:
        if certificado.get("vencido"):
            erros.append("o certificado da nota venceu: a Sefin recusa (regra E1203)")
        elif certificado.get("dias_restantes") is not None and certificado["dias_restantes"] <= 30:
            avisos.append(f"o certificado da nota vence em {certificado['dias_restantes']} dia(s)")
    if municipio is not None and not municipio.get("pode_emitir"):
        erros.append(municipio.get("frase") or "o município não emite pelo Sistema Nacional")
    return erros, avisos
