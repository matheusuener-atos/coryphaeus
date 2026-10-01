"""
Quem presta o serviço e como ele é tributado — a configuração fiscal.

Configura-se uma vez, em Configurações › Nota fiscal, pelo titular, na janela
do escritório. Cada gravação é uma VERSÃO nova: a nota guarda o número da
versão com que foi montada, e mudar o regime amanhã não reescreve a nota de
ontem (que foi emitida, e tributada, do jeito de ontem).

O PAULUS não decide tributo. Cada retenção tem uma regra que o escritório ou
o contador escreveu, e "não sei, perguntar ao contador" deixa a retenção
desligada — nunca ligada por palpite. Percentual é inteiro em centésimos de
ponto percentual (5% = 500, 1,5% = 150): nada de float em dinheiro nem em
alíquota.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime

import campos_br

from . import tabelas
from .dinheiro import centavos_de_texto

AMBIENTES = {"producao_restrita": "Produção restrita (testes, sem valor fiscal)",
             "producao": "Produção (vale de verdade)"}

# Quando cada retenção se aplica. "nao_sei" é a resposta honesta de quem não
# sabe: a retenção fica desligada e o cartão avisa que falta o contador.
QUANDO_RETER = {
    "nunca": "Nunca",
    "tomador_pj": "Quando o tomador é pessoa jurídica",
    "sempre": "Sempre",
    "nao_sei": "Não sei — perguntar ao contador",
}

RETENCOES = {
    "irrf": "IRRF",
    "pis": "PIS",
    "cofins": "COFINS",
    "csll": "CSLL",
    "cp": "Contribuição previdenciária (CP)",
    "iss": "ISS retido pelo tomador",
}

EXPLICA_RETENCAO = {
    "irrf": "Imposto de renda que o tomador desconta do pagamento e recolhe no seu lugar.",
    "pis": "PIS que o tomador desconta e recolhe. Vai somado com COFINS e CSLL no campo de retenções da nota.",
    "cofins": "COFINS que o tomador desconta e recolhe. Vai somada com PIS e CSLL no campo de retenções da nota.",
    "csll": "CSLL que o tomador desconta e recolhe. Vai somada com PIS e COFINS no campo de retenções da nota.",
    "cp": "Contribuição previdenciária retida pelo tomador, quando a lei manda reter.",
    "iss": "O tomador recolhe o ISS em vez do escritório. Com regime especial (sociedade de profissionais "
           "ou autônomo) a Sefin não aceita ISS retido.",
}

PADRAO: dict = {
    "documento": "",             # CNPJ (ou CPF de advogado autônomo), só dígitos/letras
    "razao_social": "",
    "inscricao_municipal": "",
    "municipio": "",             # código IBGE (7 dígitos)
    "uf": "",
    "endereco": {"logradouro": "", "numero": "", "complemento": "", "bairro": "", "cep": ""},
    "telefone": "",
    "email": "",
    # Regime: os códigos são os do XSD (TSOpSimpNac, TSRegimeApuracaoSimpNac,
    # TSRegEspTrib); "regime_federal" é só o rótulo que o escritório reconhece.
    "opcao_simples": "1",
    "regime_apuracao_sn": "",
    "regime_especial": "0",
    "regime_federal": "",        # presumido | real | simples | mei
    "anexo_simples": "",         # o anexo do Simples (texto, para o contador)
    # O serviço padrão do escritório.
    "servico": {"ctribnac": "171401", "nbs": "", "ctribmun": "", "descricao": "",
                "aliquota_iss_bp": 0},
    "retencoes": {r: {"quando": "nao_sei", "aliquota_bp": 0, "minimo_centavos": 0, "nota": ""} for r in RETENCOES},
    # O CST do PIS/COFINS, que a nota exige quando há PIS/COFINS/CSLL retidos
    # (o grupo piscofins leva a retenção). Enquadramento: o contador diz.
    "pis_cofins": {"cst": ""},
    # IBS/CBS (NT 004): o que a DPS declara. A Sefin calcula; o cartão prevê.
    "ibscbs": {"enviar": True, "cst": "", "cclasstrib": "", "cindop": "100301", "indfinal": "0"},
    # Total aproximado de tributos (Lei 12.741/2012): o percentual informado.
    "total_tributos": {"modo": "percentual", "federal_bp": 0, "estadual_bp": 0, "municipal_bp": 0,
                       "simples_bp": 0},
    "serie": "1",
    # O contador do escritório: para quem vai o .zip do mês (N6), por e-mail com Aprovação.
    "contador": {"nome": "", "email": ""},
    "ambiente": "producao_restrita",
    "revisado_por": "",
    "revisado_em": "",
}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundir(base: dict, novo: dict) -> dict:
    saida = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if k not in saida:
            continue
        if isinstance(saida[k], dict) and isinstance(v, dict):
            saida[k] = _fundir(saida[k], v)
        else:
            saida[k] = v
    return saida


def _inteiro(valor, campo: str, minimo: int = 0, maximo: int | None = None) -> int:
    """Inteiro sem float no caminho: "500", 500 ou "5,00%" não são a mesma coisa —
    só aceita inteiro (em centésimos de ponto percentual ou em centavos)."""
    if isinstance(valor, bool):
        raise ValueError(f"{campo}: valor inválido")
    if isinstance(valor, int):
        n = valor
    else:
        texto = str(valor or "0").strip()
        if not re.fullmatch(r"-?\d+", texto):
            raise ValueError(f"{campo}: use um número inteiro")
        n = int(texto)
    if n < minimo or (maximo is not None and n > maximo):
        raise ValueError(f"{campo}: fora do intervalo permitido")
    return n


def percentual_para_bp(texto: str) -> int:
    """ "5", "5,00", "1,5" ou "0,65" -> pontos-base inteiros (500, 500, 150, 65).
    É o caminho da tela: o que a pessoa digita vira inteiro sem passar por float."""
    t = str(texto or "").strip().replace("%", "").replace(" ", "")
    if not t:
        return 0
    m = re.fullmatch(r"(\d{1,3})(?:[,.](\d{1,2}))?", t)
    if not m:
        raise ValueError("percentual inválido: use, por exemplo, 5 ou 2,5 ou 0,65")
    inteiro, frac = m.group(1), (m.group(2) or "")
    return int(inteiro) * 100 + int(frac.ljust(2, "0") or "0")


def bp_para_texto(bp: int) -> str:
    """500 -> "5,00%"."""
    bp = int(bp or 0)
    return f"{bp // 100},{bp % 100:02d}%"


def conferir(dados: dict) -> tuple[dict, list[str]]:
    """
    Limpa a configuração e diz o que falta para emitir.

    Devolve (limpa, faltas). Erro de formato vira ValueError; falta (campo
    vazio que a nota exige) vira frase na lista, porque configurar aos poucos
    é normal e a tela mostra o que ainda falta.
    """
    c = _fundir(PADRAO, dados or {})
    faltas: list[str] = []

    doc = campos_br.normalizado(c.get("documento"))
    if doc:
        if len(doc) == 14:
            if not campos_br.cnpj_valido(doc):
                raise ValueError("o CNPJ do prestador não confere (dígito verificador)")
        elif len(doc) == 11:
            if not campos_br.cpf_valido(doc):
                raise ValueError("o CPF do prestador não confere (dígito verificador)")
        else:
            raise ValueError("o documento do prestador precisa ser um CNPJ ou um CPF")
    else:
        faltas.append("o CNPJ (ou CPF) do prestador")
    c["documento"] = doc

    c["inscricao_municipal"] = re.sub(r"\s", "", str(c.get("inscricao_municipal") or ""))[:15]
    mun = re.sub(r"\D", "", str(c.get("municipio") or ""))
    if mun:
        achado = tabelas.municipio(mun)
        if not achado:
            raise ValueError("o município do prestador não está na tabela oficial do IBGE")
        c["uf"] = achado["uf"]
    else:
        faltas.append("o município do prestador")
    c["municipio"] = mun

    end = c["endereco"]
    end["cep"] = re.sub(r"\D", "", str(end.get("cep") or ""))
    if end["cep"] and len(end["cep"]) != 8:
        raise ValueError("o CEP do prestador precisa de 8 dígitos")
    c["telefone"] = re.sub(r"\D", "", str(c.get("telefone") or ""))

    if c["opcao_simples"] not in tabelas.dominio("opcao_simples"):
        raise ValueError("situação no Simples Nacional inválida")
    if c["regime_especial"] not in tabelas.dominio("regime_especial"):
        raise ValueError("regime especial de tributação inválido")
    if c["opcao_simples"] == "3":
        if c["regime_apuracao_sn"] not in tabelas.dominio("regime_apuracao_sn"):
            faltas.append("o regime de apuração do Simples (ME/EPP)")
    else:
        # A Sefin rejeita o regime de apuração para quem não é ME/EPP (E0162).
        c["regime_apuracao_sn"] = ""

    s = c["servico"]
    s["ctribnac"] = re.sub(r"\D", "", str(s.get("ctribnac") or "")).zfill(6) if s.get("ctribnac") else ""
    if s["ctribnac"] and not tabelas.servico(s["ctribnac"]):
        raise ValueError("o código de tributação nacional não está na lista oficial de serviços")
    if not s["ctribnac"]:
        faltas.append("o código de tributação nacional do serviço")
    s["nbs"] = re.sub(r"\D", "", str(s.get("nbs") or ""))
    if s["nbs"] and not tabelas.nbs(s["nbs"]):
        raise ValueError("a NBS não está na tabela oficial")
    s["ctribmun"] = re.sub(r"\D", "", str(s.get("ctribmun") or ""))
    if s["ctribmun"] and len(s["ctribmun"]) != 3:
        raise ValueError("o código de tributação municipal tem 3 dígitos")
    s["aliquota_iss_bp"] = _inteiro(s.get("aliquota_iss_bp"), "alíquota do ISS", 0, 500)
    s["descricao"] = str(s.get("descricao") or "").strip()[:2000]

    for nome, r in c["retencoes"].items():
        if r.get("quando") not in QUANDO_RETER:
            raise ValueError(f"{RETENCOES[nome]}: escolha quando reter")
        r["aliquota_bp"] = _inteiro(r.get("aliquota_bp"), RETENCOES[nome], 0, 10000)
        r["minimo_centavos"] = _inteiro(r.get("minimo_centavos"), f"{RETENCOES[nome]} (mínimo)", 0)
        if r["quando"] in ("tomador_pj", "sempre") and nome != "iss" and not r["aliquota_bp"]:
            faltas.append(f"a alíquota de {RETENCOES[nome]}")
    if c["regime_especial"] != "0" and c["retencoes"]["iss"]["quando"] in ("tomador_pj", "sempre"):
        raise ValueError("com regime especial de tributação a Sefin não aceita ISS retido (regra E0588)")
    if c["opcao_simples"] == "2":
        for nome in ("irrf", "pis", "cofins", "csll", "cp"):
            if c["retencoes"][nome]["quando"] in ("tomador_pj", "sempre"):
                raise ValueError("MEI não informa tributos federais na nota (regra E0676)")

    pc = c["pis_cofins"]
    pc["cst"] = re.sub(r"\D", "", str(pc.get("cst") or ""))
    if pc["cst"] and pc["cst"] not in tabelas.dominio("cst_pis_cofins"):
        raise ValueError("o CST do PIS/COFINS não está na tabela do XSD")
    if not pc["cst"] and any(c["retencoes"][k]["quando"] in ("tomador_pj", "sempre") for k in ("pis", "cofins", "csll")):
        faltas.append("o CST do PIS/COFINS (a nota pede quando há PIS/COFINS/CSLL retidos)")

    ib = c["ibscbs"]
    ib["enviar"] = bool(ib.get("enviar"))
    for campo, tam in (("cst", 3), ("cclasstrib", 6), ("cindop", 6)):
        ib[campo] = re.sub(r"\D", "", str(ib.get(campo) or ""))
        if ib[campo] and len(ib[campo]) != tam:
            raise ValueError(f"IBS/CBS: o {campo} tem {tam} dígitos")
    if ib["cindop"] and not tabelas.indop(ib["cindop"]):
        raise ValueError("IBS/CBS: o indicador da operação não está na tabela oficial")
    if ib["enviar"]:
        if not ib["cst"] or not ib["cclasstrib"]:
            faltas.append("o CST e o cClassTrib do IBS/CBS (pergunta ao contador)")
        if not ib["cindop"]:
            faltas.append("o indicador da operação do IBS/CBS")
    ib["indfinal"] = "1" if str(ib.get("indfinal")) == "1" else "0"

    tt = c["total_tributos"]
    if tt.get("modo") not in ("percentual", "simples"):
        raise ValueError("total aproximado de tributos: escolha percentual ou percentual do Simples")
    for campo in ("federal_bp", "estadual_bp", "municipal_bp", "simples_bp"):
        tt[campo] = _inteiro(tt.get(campo), "total aproximado de tributos", 0, 10000)
    # A Sefin aceita o percentual do Simples só de ME/EPP e nega ao não optante
    # (E0712, E0713); o MEI não informa pTotTribSN (E0710).
    if c["opcao_simples"] == "1" and tt["modo"] == "simples":
        tt["modo"] = "percentual"
    if c["opcao_simples"] == "2" and tt["modo"] == "simples":
        tt["modo"] = "percentual"

    ct = c["contador"]
    ct["nome"] = " ".join(str(ct.get("nome") or "").split())[:120]
    ct["email"] = str(ct.get("email") or "").strip()[:120]
    if ct["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", ct["email"]):
        raise ValueError("o e-mail do contador não parece um e-mail")

    serie = re.sub(r"\D", "", str(c.get("serie") or "1")).lstrip("0") or "1"
    # Série de aplicativo próprio: 1 a 49999 (regra E0010).
    if not 1 <= int(serie) <= 49999:
        raise ValueError("a série da DPS de aplicativo próprio vai de 1 a 49999")
    c["serie"] = serie
    if c["ambiente"] not in AMBIENTES:
        raise ValueError("ambiente inválido")
    return c, faltas


def _do_formulario(novo):
    """
    A tela manda percentual como texto ("2,5") em `*_pct` e dinheiro como
    texto ("1.234,56") em `*_reais`; aqui viram `*_bp` e `*_centavos`
    inteiros, sem float no caminho.
    """
    if isinstance(novo, list):
        return [_do_formulario(v) for v in novo]
    if not isinstance(novo, dict):
        return novo
    saida = {}
    for k, v in novo.items():
        if k.endswith("_pct"):
            saida[k[:-4] + "_bp"] = percentual_para_bp(v)
        elif k.endswith("_reais"):
            saida[k[:-6] + "_centavos"] = centavos_de_texto(v)
        else:
            saida[k] = _do_formulario(v)
    return saida


class Prestador:
    """A configuração fiscal com histórico, na base local."""

    def __init__(self, base) -> None:
        self.base = base

    def atual(self) -> dict:
        """A versão em vigor: {id, dados, criado_em, criado_por} (id 0 = nunca configurado)."""
        linha = self.base.um("SELECT * FROM nfse_prestador ORDER BY id DESC LIMIT 1")
        if not linha:
            return {"id": 0, "dados": copy.deepcopy(PADRAO), "criado_em": "", "criado_por": "", "motivo": ""}
        return {**linha, "dados": _fundir(PADRAO, json.loads(linha["dados"] or "{}"))}

    def versao(self, id_: int) -> dict | None:
        linha = self.base.um("SELECT * FROM nfse_prestador WHERE id = ?", (int(id_),))
        if not linha:
            return None
        return {**linha, "dados": _fundir(PADRAO, json.loads(linha["dados"] or "{}"))}

    def historico(self, limite: int = 30) -> list[dict]:
        return self.base.buscar(
            "SELECT id, criado_em, criado_por, motivo FROM nfse_prestador ORDER BY id DESC LIMIT ?", (limite,))

    def gravar(self, novo: dict, quem: str = "", motivo: str = "") -> dict:
        """Grava uma versão nova (se algo mudou) e devolve a atual com as faltas."""
        atual = self.atual()
        # O ambiente não muda por aqui: produção só pela liberação (N8).
        novo = _do_formulario(dict(novo or {}))
        novo.pop("ambiente", None)
        novo.pop("revisado_por", None)
        novo.pop("revisado_em", None)
        combinado = _fundir(atual["dados"], novo)
        limpo, faltas = conferir(combinado)
        if atual["id"] and limpo == atual["dados"]:
            return {**atual, "faltas": faltas, "mudou": False}
        id_ = self.base.escrever(
            "INSERT INTO nfse_prestador (dados, criado_em, criado_por, motivo) VALUES (?,?,?,?)",
            (json.dumps(limpo, ensure_ascii=False, sort_keys=True), _agora(), quem, motivo or "configuração"),
        )
        return {**self.versao(id_), "faltas": faltas, "mudou": True}

    def mudar_ambiente(self, ambiente: str, quem: str, motivo: str) -> dict:
        """Só a liberação da produção (N8) e o "voltar para produção restrita" chamam isto."""
        if ambiente not in AMBIENTES:
            raise ValueError("ambiente inválido")
        atual = self.atual()
        dados = dict(atual["dados"])
        dados["ambiente"] = ambiente
        limpo, _ = conferir(dados)
        id_ = self.base.escrever(
            "INSERT INTO nfse_prestador (dados, criado_em, criado_por, motivo) VALUES (?,?,?,?)",
            (json.dumps(limpo, ensure_ascii=False, sort_keys=True), _agora(), quem, motivo),
        )
        return self.versao(id_)

    def marcar_revisado(self, por: str, quem: str) -> dict:
        """O "revisado por … em …" do checklist da produção (N8)."""
        por = str(por or "").strip()
        if not por:
            raise ValueError("diga quem revisou a configuração")
        atual = self.atual()
        dados = dict(atual["dados"])
        dados["revisado_por"] = por[:120]
        dados["revisado_em"] = datetime.now().date().isoformat()
        id_ = self.base.escrever(
            "INSERT INTO nfse_prestador (dados, criado_em, criado_por, motivo) VALUES (?,?,?,?)",
            (json.dumps(dados, ensure_ascii=False, sort_keys=True), _agora(), quem, "revisão do contador"),
        )
        return self.versao(id_)

    def para_tela(self) -> dict:
        atual = self.atual()
        try:
            _, faltas = conferir(atual["dados"])
        except ValueError as exc:
            faltas = [str(exc)]
        d = atual["dados"]
        mun = tabelas.municipio(d.get("municipio") or "") or {}
        serv = tabelas.servico(d["servico"].get("ctribnac") or "") or {}
        return {
            "versao": atual["id"],
            "criado_em": atual.get("criado_em", ""),
            "dados": d,
            "faltas": faltas,
            "configurado": bool(atual["id"]) and not faltas,
            "municipio_nome": f"{mun.get('nome', '')}/{mun.get('uf', '')}" if mun else "",
            "servico_descricao": serv.get("descricao", ""),
            "ambiente_rotulo": AMBIENTES.get(d.get("ambiente"), ""),
            "opcoes": {
                "opcao_simples": tabelas.dominio("opcao_simples"),
                "regime_apuracao_sn": tabelas.dominio("regime_apuracao_sn"),
                "regime_especial": tabelas.dominio("regime_especial"),
                "quando_reter": QUANDO_RETER,
                "retencoes": RETENCOES,
                "explica_retencao": EXPLICA_RETENCAO,
                "nbs_sugeridas": [{"codigo": c["nbs"], "nbs": c["nbs_pontos"], "descricao": c["descricao_nbs"],
                                    "cindop": c["indop"], "cclasstrib": c["cclasstrib"],
                                    "descricao_cclasstrib": c["descricao_cclasstrib"]}
                                   for c in tabelas.correlacao_do_item(serv.get("item", "17.14"))],
            },
            "historico": self.historico(10),
            "tabelas": tabelas.versoes(),
        }
