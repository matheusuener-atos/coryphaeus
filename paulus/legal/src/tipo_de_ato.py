"""
O prazo pelo tipo de ato (docs/PLANO-PILOTO.md, N1).

A L2 sugeria sempre 15 dias úteis. Aqui o PAULUS reconhece, por regra, o ato
que a intimação comunica e o ramo do processo, e sugere o prazo da lei:

  - **o ato**: pela movimentação anterior do DataJud (a sentença, o acórdão, a
    decisão, o despacho que veio antes da intimação) ou pelo texto inteiro da
    publicação do DJEN ("julgo procedente", "ACÓRDÃO", "DECISÃO", "cite-se");
  - **o ramo**: cível, juizado especial, trabalho ou penal - pela classe, pelo
    órgão, pelo grau e pelo segmento da Justiça no número CNJ;
  - **o prazo que o juiz fixou** ("manifeste-se no prazo de 5 (cinco) dias")
    vale mais que o da lei, num despacho ou numa decisão; numa sentença ou num
    acórdão o prazo do texto costuma ser o de cumprir a condenação, e fica só
    como lembrete.

Continua sendo sugestão: o PAULUS não sabe de que lado o escritório está
(Fazenda, Ministério Público e Defensoria contam em dobro), nem se a decisão
está no rol do agravo. O porquê de cada sugestão vai junto, e as alternativas
(os embargos de declaração, por exemplo) também.
"""

from __future__ import annotations

import re
import unicodedata

EXTENSO = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "quinze": 15, "vinte": 20, "trinta": 30,
           "quarenta e cinco": 45, "sessenta": 60, "noventa": 90}

LEMBRETE = ("Contam em dobro a Fazenda Pública, o Ministério Público e a Defensoria (CPC, arts. 180, 183 e 186), "
            "e os litisconsortes com advogados diferentes em autos físicos (art. 229).")


def _n(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t.lower()).strip()


def _p(ato, dias, uteis, base):
    return {"ato": ato, "dias": dias, "uteis": uteis, "base": base}


# (tipo do ato, ramo) -> as opções, a primeira é a sugestão. Lista vazia: o
# ato não abre prazo contado daqui (a defesa é na audiência, por exemplo).
TABELA = {
    ("sentenca", "civel"): [_p("Apelação", 15, True, "CPC, art. 1.009 e art. 1.003, § 5º"),
                            _p("Embargos de declaração", 5, True, "CPC, art. 1.023")],
    ("sentenca", "juizado"): [_p("Recurso inominado", 10, True, "Lei 9.099/1995, art. 42 (dias úteis: art. 12-A)"),
                              _p("Embargos de declaração", 5, True, "Lei 9.099/1995, art. 49")],
    ("sentenca", "trabalho"): [_p("Recurso ordinário", 8, True, "CLT, art. 895, I (dias úteis: art. 775)"),
                               _p("Embargos de declaração", 5, True, "CLT, art. 897-A")],
    ("sentenca", "penal"): [_p("Apelação", 5, False, "CPP, art. 593 (dias corridos: art. 798)"),
                            _p("Embargos de declaração", 2, False, "CPP, art. 382")],
    ("acordao", "civel"): [_p("Recurso especial ou extraordinário", 15, True, "CPC, art. 1.029 e art. 1.003, § 5º"),
                           _p("Embargos de declaração", 5, True, "CPC, art. 1.023")],
    ("acordao", "juizado"): [_p("Recurso extraordinário", 15, True, "CPC, art. 1.003, § 5º (no juizado não cabe recurso especial: Súmula 203/STJ)"),
                             _p("Embargos de declaração", 5, True, "Lei 9.099/1995, art. 49")],
    ("acordao", "trabalho"): [_p("Recurso de revista", 8, True, "CLT, art. 896 (dias úteis: art. 775)"),
                              _p("Embargos de declaração", 5, True, "CLT, art. 897-A")],
    ("acordao", "penal"): [_p("Recurso especial ou extraordinário", 15, False, "CPC, art. 1.003, § 5º, c/c CPP, art. 3º (dias corridos: CPP, art. 798)"),
                           _p("Embargos de declaração", 2, False, "CPP, art. 619")],
    ("monocratica", "civel"): [_p("Agravo interno", 15, True, "CPC, art. 1.021 e art. 1.070"),
                               _p("Embargos de declaração", 5, True, "CPC, art. 1.023")],
    ("monocratica", "juizado"): [_p("Agravo interno", 15, True, "CPC, art. 1.021 (confira o regimento da turma recursal)"),
                                 _p("Embargos de declaração", 5, True, "Lei 9.099/1995, art. 49")],
    ("monocratica", "trabalho"): [_p("Agravo", 8, True, "CLT, art. 896, § 12 (confira o regimento do tribunal)"),
                                  _p("Embargos de declaração", 5, True, "CLT, art. 897-A")],
    ("monocratica", "penal"): [_p("Agravo regimental", 5, False, "Lei 8.038/1990, art. 39 (confira o regimento)")],
    ("decisao", "civel"): [_p("Agravo de instrumento", 15, True, "CPC, art. 1.015 e art. 1.003, § 5º — só se a decisão está no rol do art. 1.015 (ou na urgência do Tema 988/STJ)"),
                           _p("Embargos de declaração", 5, True, "CPC, art. 1.023"),
                           _p("Manifestação", 5, True, "CPC, art. 218, § 3º")],
    ("decisao", "juizado"): [_p("Embargos de declaração", 5, True, "Lei 9.099/1995, art. 49 — no juizado, decisão interlocutória não tem agravo pela lei (confira o regimento local)"),
                             _p("Manifestação", 5, True, "CPC, art. 218, § 3º")],
    ("decisao", "trabalho"): [_p("Embargos de declaração", 5, True, "CLT, art. 897-A — decisão interlocutória não tem recurso imediato (CLT, art. 893, § 1º)"),
                              _p("Manifestação", 5, True, "CPC, art. 218, § 3º, c/c CLT, art. 769")],
    ("decisao", "penal"): [_p("Recurso em sentido estrito", 5, False, "CPP, art. 581 e art. 586 — só nas hipóteses do art. 581")],
    ("despacho", "civel"): [_p("Manifestação", 5, True, "CPC, art. 218, § 3º (quando o juiz não fixa o prazo)")],
    ("despacho", "juizado"): [_p("Manifestação", 5, True, "CPC, art. 218, § 3º (quando o juiz não fixa o prazo)")],
    ("despacho", "trabalho"): [_p("Manifestação", 5, True, "CPC, art. 218, § 3º, c/c CLT, art. 769 (quando o juiz não fixa o prazo)")],
    ("despacho", "penal"): [_p("Manifestação", 5, False, "sem prazo geral no CPP: 5 dias, pelo CPC, art. 218, § 3º (c/c CPP, art. 3º) — confira")],
    ("citacao", "civel"): [_p("Contestação", 15, True, "CPC, art. 335 — conta da audiência de conciliação ou da juntada do mandado ou do AR (art. 231)")],
    ("citacao", "juizado"): [],
    ("citacao", "trabalho"): [],
    ("citacao", "penal"): [_p("Resposta à acusação", 10, False, "CPP, art. 396")],
    ("citacao", "execucao"): [_p("Embargos à execução", 15, True, "CPC, art. 915 — conta da juntada do mandado"),
                              _p("Pagamento", 3, True, "CPC, art. 829")],
    ("cumprimento", "civel"): [_p("Pagamento voluntário", 15, True, "CPC, art. 523"),
                               _p("Impugnação ao cumprimento", 15, True, "CPC, art. 525 — conta depois dos 15 dias do pagamento")],
    ("contestacao_juntada", "civel"): [_p("Réplica", 15, True, "CPC, art. 350 e art. 351")],
    ("recurso_juntado", "civel"): [_p("Contrarrazões", 15, True, "CPC, art. 1.010, § 1º, e art. 1.003, § 5º")],
    ("recurso_juntado", "juizado"): [_p("Contrarrazões", 10, True, "Lei 9.099/1995, art. 42, § 2º")],
    ("recurso_juntado", "trabalho"): [_p("Contrarrazões", 8, True, "CLT, art. 900")],
    ("recurso_juntado", "penal"): [_p("Contrarrazões", 8, False, "CPP, art. 600")],
    ("embargos_juntados", "civel"): [_p("Contrarrazões aos embargos de declaração", 5, True, "CPC, art. 1.023, § 2º")],
    ("embargos_juntados", "juizado"): [_p("Contrarrazões aos embargos de declaração", 5, True, "CPC, art. 1.023, § 2º")],
    ("embargos_juntados", "trabalho"): [_p("Contrarrazões aos embargos de declaração", 5, True, "CLT, art. 897-A, § 2º")],
    ("embargos_juntados", "penal"): [_p("Contrarrazões aos embargos de declaração", 2, False, "CPP, art. 619, por analogia — confira")],
}

GENERICO = _p("Prazo (não reconheci o ato)", 15, True, "sugestão genérica de 15 dias úteis: confira o ato na intimação")

SEM_PRAZO = {
    ("citacao", "juizado"): "No juizado, a contestação é apresentada na audiência (Lei 9.099/1995, art. 30): veja a data dela na citação.",
    ("citacao", "trabalho"): "Na Justiça do Trabalho a defesa é apresentada na audiência (CLT, art. 847): veja a data dela na notificação.",
}

NOMES = {"sentenca": "sentença", "acordao": "acórdão", "monocratica": "decisão monocrática do relator",
         "decisao": "decisão interlocutória", "despacho": "despacho ou ato ordinatório", "citacao": "citação",
         "cumprimento": "intimação no cumprimento de sentença", "contestacao_juntada": "contestação juntada",
         "recurso_juntado": "recurso da outra parte juntado", "embargos_juntados": "embargos de declaração juntados"}

RAMOS = {"civel": "cível", "juizado": "juizado especial", "trabalho": "trabalho", "penal": "penal",
         "execucao": "execução"}

# ------------------------------------------------------------------ o ramo

_RE_PENAL = re.compile(r"penal|criminal|crime|inquerito|habeas corpus|execucao da pena|contravenc|termo circunstanciado|"
                       r"medidas protetivas|acao penal|juri\b")
_RE_JUIZADO = re.compile(r"juizado especial|juizados especiais|turma recursal|\bjec\b|\bjef\b|procedimento do juizado")


def ramo(*, classe: str = "", orgao: str = "", tribunal: str = "", grau: str = "", numero: str = "") -> str:
    """cível, juizado, trabalho ou penal (nessa ordem de conferência: trabalho e penal primeiro)."""
    t = _n(classe) + " | " + _n(orgao)
    trib = _n(tribunal)
    dig = re.sub(r"\D", "", str(numero or ""))
    if trib.startswith("trt") or trib == "tst" or (len(dig) == 20 and dig[13] == "5"):
        return "trabalho"
    if _RE_PENAL.search(t):
        return "penal"
    if _RE_JUIZADO.search(t) or str(grau or "").upper() in ("JE", "TR", "TRU", "TNU"):
        return "juizado"
    return "civel"


def _execucao(classe: str) -> str:
    c = _n(classe)
    if "cumprimento de sentenca" in c or "cumprimento provisorio" in c:
        return "cumprimento"
    if "execucao de titulo extrajudicial" in c or c.startswith("execucao fiscal") or c == "execucao":
        return "execucao"
    return ""


# ------------------------------------------------ o ato, pelo DataJud

_RE_SENTENCA = re.compile(r"\b(procedencia|improcedencia|procedente|improcedente|extincao|extinto|extinta|homologa|"
                          r"sentenca|julgamento|resolucao do merito|prescricao|decadencia|desistencia|"
                          r"indeferimento da peticao inicial|julgado|julgada)")
_RE_ACORDAO = re.compile(r"\b(acordao|provimento|nao-provimento|nao provimento|conhecimento|nao-conhecimento|"
                         r"nao conhecimento|provido|improvido|negado provimento|dado provimento)")
_RE_DECISAO = re.compile(r"\b(decisao|concessao|nao-concessao|nao concessao|antecipacao de tutela|tutela|liminar|"
                         r"deferimento|indeferimento|revogacao|suspensao|conversao|recebimento|bloqueio|penhora)")
_RE_DESPACHO = re.compile(r"\b(despacho|mero expediente|ato ordinatorio|proferido despacho)")
_RE_CITACAO = re.compile(r"\bcita(cao|coes|do|da|r)\b|\bcite-se")
_RE_JUNTADA_CONTESTACAO = re.compile(r"juntada.*contestacao|contestacao.*juntada")
_RE_JUNTADA_EMBARGOS = re.compile(r"juntada.*embargos de declaracao|embargos de declaracao.*juntad")
_RE_JUNTADA_RECURSO = re.compile(r"juntada.*(apelacao|recurso inominado|recurso ordinario|agravo|recurso especial|"
                                 r"recurso extraordinario|recurso de revista)|interposicao de recurso")
_RE_GATILHO = re.compile(r"intima|cita[cç][aã]o|publica[cç][aã]o|disponibiliza|expedi[cç][aã]o de (documento|intima|mandado|carta)",
                         re.IGNORECASE)


def gatilho(mov: dict) -> bool:
    """A movimentação comunica algo à parte (e pode abrir prazo)."""
    return bool(_RE_GATILHO.search(f"{mov.get('nome', '')} {mov.get('complemento', '')}"))


def _recursal(grau: str) -> bool:
    return str(grau or "").upper() in ("G2", "TR", "TRU", "TNU", "SUP", "GS")


def ato_do_movimento(mov: dict, *, grau: str = "") -> str:
    """O tipo de ato que uma movimentação do DataJud registra ("" quando não é um ato que abre prazo)."""
    t = _n(f"{mov.get('nome', '')} {mov.get('complemento', '')}")
    if not t:
        return ""
    if "juntada" in t or "peticao" in t:
        if _RE_JUNTADA_EMBARGOS.search(t):
            return "embargos_juntados"
        if _RE_JUNTADA_CONTESTACAO.search(t):
            return "contestacao_juntada"
        if _RE_JUNTADA_RECURSO.search(t):
            return "recurso_juntado"
        return ""
    if re.search(r"decisao monocratica|monocratic", t):
        return "monocratica"
    if _RE_ACORDAO.search(t) and _recursal(grau):
        return "acordao"
    if _RE_SENTENCA.search(t) and not re.search(r"\b(decisao|despacho)\b", t):
        return "acordao" if _recursal(grau) else "sentenca"
    if _RE_DECISAO.search(t):
        return "monocratica" if _recursal(grau) and "decisao" in t else "decisao"
    if _RE_DESPACHO.search(t):
        return "despacho"
    return ""


# ------------------------------------------------ o ato, pelo texto do DJEN

def ato_do_texto(texto: str, *, tipo: str = "", grau: str = "") -> str:
    """O tipo de ato pelo texto da comunicação (o DJEN traz o texto inteiro)."""
    t = _n(texto)[:6000]
    tp = _n(tipo)
    cabeca = t[:600]
    if "citacao" in tp or re.search(r"\bcite-se\b|fica(m)? cita|carta de citacao|mandado de citacao", cabeca):
        return "citacao"
    if re.search(r"\bacordao\b|\bacordam\b|\bementa\b", cabeca):
        return "acordao"
    if re.search(r"decisao monocratica|\bmonocratica", cabeca) or (
            re.search(r"\brelator", t) and re.search(r"nego (seguimento|provimento)|dou provimento|nao conheco do recurso", t)):
        return "monocratica"
    if re.search(r"\bsentenca\b|julgo (im)?procedente|julgo parcialmente procedente|julgo extint|extingo o (processo|feito)|"
                 r"homologo (o|a|por)|resolvo o merito", t):
        return "sentenca"
    if re.search(r"\bdecisao\b|\bdefiro\b|\bindefiro\b|tutela (de urgencia|antecipada|provisoria)|\bliminar", cabeca + " " + t[:2500]):
        return "decisao"
    if re.search(r"\bdespacho\b|ato ordinatorio|intime-se|manifeste-se|vista (a|as|ao|aos) (parte|autor|reu)|"
                 r"diga (a|o) (parte|autor|reu)|especifique(m)? (as )?provas", t):
        return "despacho"
    return ""


_RE_PRAZO_FIXADO = re.compile(
    r"(?:prazo (?:comum |sucessivo |legal |improrrogavel |de ate )*de|no prazo de|em|dentro de)\s+"
    r"(\d{1,3}|[a-z]+(?: e [a-z]+)?)\s*(?:\(([a-z ]{2,30})\)\s*)?(dias?|horas?)(?:\s+(uteis|corridos))?")


def prazo_fixado(texto: str) -> dict | None:
    """O prazo que o próprio ato fixa ("no prazo de 5 (cinco) dias"): {dias, uteis, trecho}. Horas viram dias (48 h = 2)."""
    t = _n(texto)
    for m in _RE_PRAZO_FIXADO.finditer(t):
        bruto, extenso, unidade, tipo = m.group(1), m.group(2), m.group(3), m.group(4)
        n = int(bruto) if bruto.isdigit() else EXTENSO.get(bruto)
        if n is None and extenso:
            n = EXTENSO.get(extenso.strip())
        if not n:
            continue
        if unidade.startswith("hora"):
            if n % 24:
                continue
            n = n // 24
        if not 1 <= n <= 120:
            continue
        ini = max(0, m.start() - 60)
        return {"dias": n, "uteis": tipo != "corridos", "trecho": t[ini:m.end() + 20].strip()}
    return None


# ------------------------------------------------------------------ juntar

def sugerir(*, ato: str, ramo_: str, classe: str = "", fixado: dict | None = None, porque: str = "") -> dict:
    """
    A sugestão: {ato, dias, uteis, base, porque, certeza, alternativas, sem_prazo, tipo, ramo, lembrete}.

    certeza: "fixado" (o juiz escreveu o prazo), "reconhecido" (o ato e o
    ramo batem com a tabela) ou "generico" (não reconheci o ato).
    """
    exe = _execucao(classe)
    chave_ramo = ramo_
    tipo = ato
    if ato == "citacao" and exe == "execucao":
        chave_ramo = "execucao"
    elif exe == "cumprimento" and ato in ("despacho", "decisao", ""):
        tipo, chave_ramo = "cumprimento", "civel"
    opcoes = TABELA.get((tipo, chave_ramo))
    if opcoes is None and tipo:
        opcoes = TABELA.get((tipo, "civel"))
    saida = {"tipo": tipo, "ramo": ramo_, "lembrete": LEMBRETE, "sem_prazo": "", "porque": porque}
    if tipo and opcoes == []:
        saida.update(GENERICO, ato="Sem prazo contado daqui", dias=0, certeza="reconhecido", alternativas=[],
                     sem_prazo=SEM_PRAZO.get((tipo, chave_ramo), "Este ato não abre prazo contado da intimação."))
        return saida
    if fixado and tipo in ("despacho", "decisao", "cumprimento", ""):
        principal = _p("Prazo fixado no ato", fixado["dias"], fixado["uteis"] and ramo_ != "penal",
                       "o prazo escrito na comunicação: “…" + fixado["trecho"] + "…”")
        saida.update(principal, certeza="fixado", alternativas=[o for o in (opcoes or []) if o["dias"] != fixado["dias"]][:2])
        return saida
    if not opcoes:
        saida.update(GENERICO, certeza="generico", alternativas=[])
        return saida
    saida.update(opcoes[0], certeza="reconhecido", alternativas=opcoes[1:])
    if fixado and fixado["dias"] != opcoes[0]["dias"]:
        saida["alternativas"] = saida["alternativas"] + [
            _p("O prazo que o texto menciona", fixado["dias"], fixado["uteis"],
               "“…" + fixado["trecho"] + "…” — numa " + NOMES.get(tipo, "decisão") + " costuma ser o de cumprir, não o de recorrer")]
    return saida


def do_movimento(mov: dict, anteriores: list[dict], *, classe: str = "", orgao: str = "", tribunal: str = "",
                 grau: str = "", numero: str = "") -> dict:
    """A sugestão para uma intimação do DataJud, olhando as movimentações anteriores do mesmo grau."""
    r = ramo(classe=classe, orgao=orgao, tribunal=tribunal, grau=grau, numero=numero)
    texto = f"{mov.get('nome', '')} {mov.get('complemento', '')}"
    if _RE_CITACAO.search(_n(texto)):
        return sugerir(ato="citacao", ramo_=r, classe=classe,
                       porque=f"a própria movimentação é uma citação ({texto.strip()}) · {RAMOS[r]}")
    fixado = prazo_fixado(texto)
    for a in anteriores:
        tipo = ato_do_movimento(a, grau=grau)
        if tipo:
            quando = str(a.get("quando", ""))[:10]
            quando = "/".join(reversed(quando.split("-"))) if quando else "antes"
            return sugerir(ato=tipo, ramo_=r, classe=classe, fixado=fixado,
                           porque=f"a movimentação anterior é “{a.get('nome', '')}” ({quando}), {NOMES.get(tipo, tipo)} · {RAMOS[r]}")
    return sugerir(ato="", ramo_=r, classe=classe, fixado=fixado,
                   porque="não achei, antes desta intimação, a sentença, a decisão ou o despacho que ela comunica · " + RAMOS[r])


def do_texto(texto: str, *, tipo: str = "", classe: str = "", orgao: str = "", tribunal: str = "", numero: str = "") -> dict:
    """A sugestão para uma publicação do DJEN, pelo texto inteiro."""
    r = ramo(classe=classe, orgao=orgao, tribunal=tribunal, numero=numero)
    ato = ato_do_texto(texto, tipo=tipo)
    fixado = prazo_fixado(texto)
    if ato:
        porque = f"o texto é de {NOMES.get(ato, ato)} · {RAMOS[r]}"
    else:
        porque = "não reconheci no texto o tipo de ato · " + RAMOS[r]
    return sugerir(ato=ato, ramo_=r, classe=classe, fixado=fixado, porque=porque)
