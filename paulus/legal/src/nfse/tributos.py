"""
A conta dos tributos da nota — por regra, em centavos, com a regra de cada
linha escrita ao lado para o cartão mostrar.

O que é PREVISÃO e o que é DECISÃO fica separado:

- as retenções e o ISS retido são decisão do escritório (a regra que ele ou o
  contador configurou) e vão na DPS como estão aqui;
- o ISS próprio, a base do ISS, o IBS e a CBS são calculados pela Sefin (com a
  alíquota parametrizada pelo município e a Calculadora da reforma) e voltam
  na NFS-e; aqui é a previsão, e a nota emitida mostra o que a Sefin calculou
  (e avisa se diferir).

Fontes (docs/PROGRESSO-NFSE.md, N0): Anexo I, RN DPS/NFS-e (vBC E1295,
vTotalRet E1506, vLiq E1508, pAliq E0595…E0640, retenção E0583/E0588); NT 007
(PIS/COFINS/CSLL retidos somados em vRetCSLL; arredondamento half-even); LC
214/2025, arts. 343, 346 e 348 (IBS 0,1% e CBS 0,9% em 2026, sem
recolhimento para quem cumpre as obrigações acessórias).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .dinheiro import aplicar, percentual_texto, reais

# tpRetPisCofins (NT 007): (PIS, COFINS, CSLL) retidos -> código.
TIPO_RETENCAO_PCC = {
    (False, False, False): "0",
    (True, True, True): "3",
    (True, True, False): "4",
    (True, False, False): "5",
    (False, True, False): "6",
    (False, True, True): "7",
    (False, False, True): "8",
    (True, False, True): "9",
}

# 2026: alíquotas de teste (LC 214/2025, arts. 343 e 346), em pontos-base.
CBS_2026_BP = 90
IBS_UF_2026_BP = 10
IBS_MUN_2026_BP = 0

ROTULO_RETENCAO = {"irrf": "IRRF retido", "pis": "PIS retido", "cofins": "COFINS retida",
                   "csll": "CSLL retida", "cp": "Contribuição previdenciária retida"}


@dataclass
class Linha:
    chave: str
    rotulo: str
    centavos: int
    regra: str
    tipo: str = "valor"          # valor | retencao | previsao | total | info


@dataclass
class Conta:
    v_serv: int = 0
    v_desc_incond: int = 0
    base_iss: int = 0
    aliquota_iss_bp: int = 0
    iss: int = 0
    iss_destacado: bool = False   # a Sefin calcula ISS na nota (fora regime especial/DAS)
    iss_retido: bool = False
    informar_paliq: bool = False
    retencoes: dict = field(default_factory=dict)  # irrf, pis, cofins, csll, cp
    v_ret_csll: int = 0           # PIS + COFINS + CSLL retidos (NT 007)
    tp_ret_pis_cofins: str = "0"
    v_total_ret: int = 0
    v_liq: int = 0
    ibscbs: dict = field(default_factory=dict)
    linhas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    erros: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _tomador_pj(tomador: dict) -> bool:
    doc = "".join(ch for ch in str(tomador.get("documento") or "") if ch.isalnum())
    return len(doc) == 14


def _aplica(quando: str, tomador: dict) -> bool:
    return quando == "sempre" or (quando == "tomador_pj" and _tomador_pj(tomador))


def regra_paliq(prest: dict, iss_retido: bool, municipio_ativo: bool) -> tuple[bool, str]:
    """
    Se a DPS leva a alíquota do ISS (pAliq) — as regras E0600…E0640 do Anexo I,
    literalmente. Devolve (informar, por quê).
    """
    op = prest.get("opcao_simples")
    if op == "2":
        return False, "MEI não informa alíquota (E0600)"
    if prest.get("regime_especial", "0") != "0":
        return False, "com regime especial a alíquota não vai na nota (E0604)"
    if op == "1":
        if municipio_ativo:
            return False, "não optante com município conveniado: a Sefin usa a alíquota do município (E0617)"
        return True, "não optante com município sem convênio ativo: a alíquota vai na nota (E0619)"
    if op == "3":
        if prest.get("regime_apuracao_sn") == "1":
            if iss_retido:
                return True, "Simples com ISS retido: a alíquota do Simples vai na nota (E0621/E0628)"
            return False, "Simples sem retenção: o ISS vai no DAS e a alíquota não vai na nota (E0625/E0631)"
        if municipio_ativo:
            return False, "Simples com ISS fora do DAS e município conveniado: a Sefin usa a alíquota do município (E0635)"
        return True, "Simples com ISS fora do DAS e município sem convênio ativo: a alíquota vai na nota (E0640)"
    return False, "situação no Simples não configurada"


def calcular(prest: dict, nota: dict, *, municipio_ativo: bool = True) -> Conta:
    """
    prest: a configuração fiscal (prestador.PADRAO conferido);
    nota: {valor_centavos, desconto_incond_centavos, competencia, tomador: {documento, cmun}}.
    """
    c = Conta()
    tomador = nota.get("tomador") or {}
    c.v_serv = int(nota.get("valor_centavos") or 0)
    c.v_desc_incond = int(nota.get("desconto_incond_centavos") or 0)
    if c.v_serv <= 0:
        c.erros.append("o valor do serviço precisa ser maior que zero")
        return c
    if c.v_desc_incond < 0 or c.v_desc_incond > c.v_serv:
        c.erros.append("o desconto incondicionado não pode passar do valor do serviço")
        return c
    base = c.v_serv - c.v_desc_incond
    c.linhas.append(Linha("v_serv", "Valor do serviço", c.v_serv, "o valor da nota", "valor"))
    if c.v_desc_incond:
        c.linhas.append(Linha("desc", "Desconto incondicionado", -c.v_desc_incond, "dado na nota, sai da base do ISS", "valor"))

    op = prest.get("opcao_simples", "1")
    especial = prest.get("regime_especial", "0")
    serv = prest.get("servico") or {}
    ret = prest.get("retencoes") or {}

    # ------------------------------------------------------------- ISS
    iss_cfg = ret.get("iss") or {}
    pode_reter_iss = op != "2" and especial == "0"
    c.iss_retido = pode_reter_iss and _aplica(iss_cfg.get("quando", "nao_sei"), tomador)
    c.base_iss = base
    c.aliquota_iss_bp = int(serv.get("aliquota_iss_bp") or 0)
    if op == "2":
        c.linhas.append(Linha("iss", "ISS", 0, "MEI: o ISS vai no DAS do MEI, fora desta nota", "info"))
    elif especial != "0":
        from . import tabelas

        nome = tabelas.dominio("regime_especial").get(especial, especial)
        c.linhas.append(Linha("iss", "ISS", 0, f"regime especial ({nome}): o ISS é recolhido fora desta nota, "
                                               "sem alíquota nem retenção na nota (E0604, E0588)", "info"))
    elif op == "3" and prest.get("regime_apuracao_sn") == "1" and not c.iss_retido:
        c.linhas.append(Linha("iss", "ISS", 0, "Simples Nacional: o ISS vai no DAS, fora desta nota", "info"))
    else:
        c.iss_destacado = True
        if not c.aliquota_iss_bp:
            c.avisos.append("a alíquota do ISS não está configurada: a previsão do ISS fica sem valor "
                            "(a Sefin aplica a alíquota do município)")
        c.iss = aplicar(base, c.aliquota_iss_bp)
        c.linhas.append(Linha("base_iss", "Base do ISS", base, "valor do serviço − desconto incondicionado (E1295)", "previsao"))
        c.linhas.append(Linha("iss", "ISS" + (" retido pelo tomador" if c.iss_retido else ""), c.iss,
                              f"base × {percentual_texto(c.aliquota_iss_bp)} (alíquota configurada; a Sefin aplica a "
                              "parametrizada pelo município e a nota emitida mostra a dela)", "previsao"))
    if pode_reter_iss and iss_cfg.get("quando") == "nao_sei":
        c.avisos.append("ISS retido: não configurado — pergunte ao contador; a nota sai sem ISS retido")
    c.informar_paliq, motivo_paliq = regra_paliq(prest, c.iss_retido, municipio_ativo)
    c.linhas.append(Linha("paliq", "Alíquota do ISS na nota", 0,
                          ("vai na nota: " if c.informar_paliq else "não vai na nota: ") + motivo_paliq, "info"))

    # ------------------------------------------------- retenções federais
    retidos: dict[str, int] = {}
    for k in ("irrf", "pis", "cofins", "csll", "cp"):
        cfg = ret.get(k) or {}
        quando = cfg.get("quando", "nao_sei")
        if op == "2":
            retidos[k] = 0
            continue
        if quando == "nao_sei":
            retidos[k] = 0
            c.avisos.append(f"{ROTULO_RETENCAO[k]}: não configurado — pergunte ao contador; a nota sai sem esta retenção")
            continue
        if not _aplica(quando, tomador):
            retidos[k] = 0
            continue
        valor = aplicar(base, int(cfg.get("aliquota_bp") or 0))
        minimo = int(cfg.get("minimo_centavos") or 0)
        if minimo and valor < minimo:
            c.linhas.append(Linha(k, ROTULO_RETENCAO[k], 0,
                                  f"{percentual_texto(int(cfg.get('aliquota_bp') or 0))} daria {reais(valor)}, abaixo do "
                                  f"mínimo configurado ({reais(minimo)}): não retido", "retencao"))
            retidos[k] = 0
            continue
        retidos[k] = valor
        quem = "sempre" if quando == "sempre" else "tomador pessoa jurídica"
        c.linhas.append(Linha(k, ROTULO_RETENCAO[k], -valor,
                              f"{percentual_texto(int(cfg.get('aliquota_bp') or 0))} × {reais(base)} "
                              f"(regra do escritório: {quem})", "retencao"))
    c.retencoes = retidos
    c.v_ret_csll = retidos["pis"] + retidos["cofins"] + retidos["csll"]
    c.tp_ret_pis_cofins = TIPO_RETENCAO_PCC[(retidos["pis"] > 0, retidos["cofins"] > 0, retidos["csll"] > 0)]
    if c.v_ret_csll:
        c.linhas.append(Linha("v_ret_csll", "PIS + COFINS + CSLL retidos (campo único da nota)", -c.v_ret_csll,
                              f"somados em vRetCSLL, tipo de retenção {c.tp_ret_pis_cofins} (NT 007)", "info"))
    for k, v in retidos.items():
        if v and v >= c.v_serv:
            c.erros.append(f"{ROTULO_RETENCAO[k]} não pode ser igual ou maior que o valor do serviço (E0699/E0700)")

    c.v_total_ret = retidos["cp"] + retidos["irrf"] + c.v_ret_csll + (c.iss if c.iss_retido else 0)
    c.v_liq = c.v_serv - c.v_desc_incond - c.v_total_ret
    if c.v_total_ret:
        c.linhas.append(Linha("v_total_ret", "Total retido", -c.v_total_ret,
                              "CP + IRRF + (PIS+COFINS+CSLL)" + (" + ISS retido" if c.iss_retido else "") + " (E1506)", "total"))
    c.linhas.append(Linha("v_liq", "Valor líquido", c.v_liq,
                          "valor do serviço − descontos − retenções (E1508)", "total"))
    if c.v_liq < 0:
        c.erros.append("o valor líquido ficou negativo: confira as retenções (E1508)")

    # ------------------------------------------------------------ IBS/CBS
    ib = prest.get("ibscbs") or {}
    ano = str(nota.get("competencia") or "")[:4]
    if ib.get("enviar"):
        if ano == "2026":
            # Base de 2026 (RN E1530): vServ − desc. incond. − vISSQN − vPIS − vCOFINS.
            # vPIS/vCOFINS de apuração própria não vão nesta DPS.
            iss_na_base = c.iss if c.iss_destacado else 0
            base_ibs = base - iss_na_base
            cbs = aplicar(base_ibs, CBS_2026_BP)
            ibs_uf = aplicar(base_ibs, IBS_UF_2026_BP)
            c.ibscbs = {"ano": ano, "base": base_ibs, "cbs_bp": CBS_2026_BP, "ibs_uf_bp": IBS_UF_2026_BP,
                        "ibs_mun_bp": IBS_MUN_2026_BP, "cbs": cbs, "ibs_uf": ibs_uf, "ibs_mun": 0,
                        "recolhe": False}
            c.linhas.append(Linha("base_ibscbs", "Base do IBS/CBS", base_ibs,
                                  "valor − desconto incondicionado − ISS (2026, regra E1530)", "previsao"))
            c.linhas.append(Linha("cbs", "CBS", cbs, f"{percentual_texto(CBS_2026_BP)} em 2026 (LC 214, art. 346), "
                                  "antes de redução da classificação, que a Sefin aplica", "previsao"))
            c.linhas.append(Linha("ibs", "IBS", ibs_uf, f"{percentual_texto(IBS_UF_2026_BP)} estadual em 2026 (LC 214, art. 343)",
                                  "previsao"))
            c.linhas.append(Linha("ibscbs_2026", "IBS e CBS em 2026", 0,
                                  "destacados na nota, sem recolhimento para quem cumpre as obrigações acessórias "
                                  "(LC 214, art. 348, §1º); não mudam o valor líquido (vTotNF = vLiq)", "info"))
        else:
            c.ibscbs = {"ano": ano, "recolhe": None}
            c.linhas.append(Linha("ibscbs", "IBS e CBS", 0,
                                  "a Sefin calcula pela alíquota vigente na competência; a nota emitida mostra os valores", "info"))
        if op in ("2", "3") and ano == "2026":
            c.avisos.append("Simples Nacional: o IBS/CBS só passa a valer em 2027 (Resolução CGSN 191/2026); "
                            "mandar o grupo em 2026 é opção do escritório")
    return c
