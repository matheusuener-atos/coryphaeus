"""
Os cadastros pela conversa (pacote de telas de 01/10/2026: `Conversa -
Cadastro`, `Conversa - Equipe`, `Conversa - Despesa fixa`).

  "cadastra a congregação cristã como cliente, ela aparece em vários
   adiantamentos"       -> a ficha preenchida com o que os documentos do
                           Acervo dizem (achar_no_acervo), na coluna ao lado
  "a Larissa Costa começa segunda como estagiária, salário de 1.800. coloca
   ela na equipe e convida pro PAULUS — o e-mail é larissa@gmail.com"
                        -> ler_equipe
  "cadastra o aluguel como despesa fixa, o contrato tá anexo"
                        -> ler_despesa_fixa + ler_contrato (o anexo)

Tudo por regra: o nome procurado no texto dos documentos, o CPF/CNPJ e o
endereco perto dele, o valor e o dia no contrato. O modelo nao entra. O que
a regra achou vem marcado ("lido em 22 documentos") e a pessoa confere antes
de salvar; nada e gravado sem o clique.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, timedelta

import campos_br


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _nfc(texto: str) -> str:
    return unicodedata.normalize("NFC", texto or "")


PARTICULAS = {"da", "de", "do", "das", "dos", "e", "no", "na", "nos", "nas"}


def _nome_proprio(nome: str) -> str:
    nome = " ".join((nome or "").split()).strip(" .,;:-–—")
    if not nome or nome != nome.lower():
        return nome
    return " ".join(p if p in PARTICULAS and i else p[:1].upper() + p[1:] for i, p in enumerate(nome.split()))


# ------------------------------------------------------------- dinheiro e datas

RE_VALOR = re.compile(r"(?:r\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)(\s*mil\b)?(?:\s*reais)?", re.I)


def valor_em_reais(trecho: str) -> str:
    """O primeiro valor do trecho, no jeito brasileiro: "R$ 1.800,00". Vazio sem valor."""
    m = RE_VALOR.search(trecho or "")
    if not m:
        return ""
    bruto, mil = m.group(1), m.group(2)
    inteiro, _, cents = bruto.replace(".", "").partition(",")
    numero = int(inteiro or 0) * (1000 if mil else 1)
    if not numero:
        return ""
    return "R$ " + f"{numero:,}".replace(",", ".") + "," + (cents + "00")[:2]


DIAS_DA_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def data_dita(plano: str, hoje: date) -> str:
    """ "começa segunda" / "a partir de 05/10" / "dia 5" -> ISO. Vazio sem data."""
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", plano)
    if m:
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano += 2000 if ano < 100 else 0
        try:
            return date(ano, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return ""
    m = re.search(r"\b(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b", plano)
    if m:
        dias = (DIAS_DA_SEMANA[m.group(1)] - hoje.weekday()) % 7 or 7
        return (hoje + timedelta(days=dias)).isoformat()
    if re.search(r"\bamanha\b", plano):
        return (hoje + timedelta(days=1)).isoformat()
    if re.search(r"\bhoje\b", plano):
        return hoje.isoformat()
    return ""


# --------------------------------------------------------------- a equipe

RE_EQUIPE = re.compile(
    r"\b(na equipe|no time|pra equipe|para a equipe|ao time|a equipe|na folha|como (?:socio|socia|colaborador|colaboradora|estagiari[oa]|"
    r"advogad[oa]|secretari[oa]|assistente|paralegal|associad[oa]))\b")
RE_VERBO_EQUIPE = re.compile(r"\b(coloca|coloque|colocar|poe|ponha|por|adiciona|adicione|inclui|inclua|cadastra|cadastre|"
                             r"contratamos|contratei|entra|entrou|comeca|comecou|chega)\b")
FUNCOES = ("estagiaria", "estagiario", "advogada", "advogado", "secretaria", "secretario", "assistente", "paralegal",
           "socia", "socio", "associada", "associado", "recepcionista", "contadora", "contador", "estagiaria de direito")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def ler_equipe(texto: str, hoje: date | None = None) -> dict | None:
    """ "a Larissa Costa começa segunda como estagiária, salário de 1.800..." -> os campos da pessoa."""
    hoje = hoje or date.today()
    texto = _nfc(texto)
    plano = _plano(texto)
    if not (RE_EQUIPE.search(plano) and RE_VERBO_EQUIPE.search(plano)):
        return None
    if re.search(r"\b(reuniao|compromisso|audiencia|prazo|tarefa)\b", plano):
        return None
    # O nome: as palavras com maiuscula seguidas (a frase como a pessoa
    # escreveu). Sem maiuscula, o que vem depois de "a"/"o" no comeco.
    m = re.search(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+){0,4})", texto)
    nome = m.group(1) if m else ""
    if nome and _plano(nome.split()[0]) in {"paulus", "coloca", "coloque", "cadastra", "cadastre", "adiciona", "a", "o"}:
        nome = ""
    if not nome:
        m = re.match(r"^\s*(?:o|a)\s+([a-zà-ÿ]+(?:\s+[a-zà-ÿ]+)?)\s+(?:comeca|entra|chega)", texto.lower())
        nome = _nome_proprio(m.group(1)) if m else ""
    funcao = ""
    for f in FUNCOES:
        if re.search(r"\b" + f + r"\b", plano):
            funcao = f
            break
    socio = bool(re.search(r"\bcomo soci[oa]\b|\bsoci[oa]\b", plano))
    salario = ""
    m = re.search(r"\b(?:salario|bolsa|remuneracao|ganha|vai ganhar|pagamento)\s*(?:de|:)?\s*(r\$\s*)?([\d.,]+(?:\s*mil)?)", plano)
    if m:
        salario = valor_em_reais(m.group(2))
    email = (RE_EMAIL.search(texto) or [""])[0] if RE_EMAIL.search(texto) else ""
    inicio = ""
    m = re.search(r"\b(?:comeca|comecou|entra|a partir de|desde|chega)\b(.{0,30})", plano)
    if m:
        inicio = data_dita(m.group(1), hoje)
    convidar = bool(re.search(r"\b(convid\w*|acesso ao paulus|da acesso|de acesso|dar acesso)\b", plano))
    vinculo = "estagio" if funcao.startswith("estagiari") else ("prolabore" if socio else "")
    return {
        "tipo": "socio" if socio else "colaborador", "nome": nome,
        "funcao": (funcao.replace("estagiaria de direito", "estagiária").capitalize()
                   .replace("Estagiaria", "Estagiária").replace("Estagiario", "Estagiário")
                   .replace("Secretaria", "Secretária").replace("Secretario", "Secretário")
                   .replace("Socia", "Sócia").replace("Socio", "Sócio")) if funcao else "",
        "email": email, "salario": salario, "inicio": inicio, "convidar": convidar, "vinculo": vinculo,
    }


# ------------------------------------------------------- a despesa fixa

RE_DESPESA_FIXA = re.compile(r"\b(despesas? fixas?|contas? fixas?|despesas? mensa(?:l|is)|todo mes|todos os meses|mensalmente)\b")
RE_VERBO_DESPESA = re.compile(r"\b(cadastra|cadastre|cadastrar|coloca|coloque|registra|registre|inclui|inclua|lanca|lance|poe|ponha|adiciona|adicione)\b")


def ler_despesa_fixa(texto: str) -> dict | None:
    """ "cadastra o aluguel como despesa fixa..." -> {nome, valor, dia}."""
    texto = _nfc(texto)
    plano = _plano(texto)
    if not (RE_DESPESA_FIXA.search(plano) and RE_VERBO_DESPESA.search(plano)):
        return None
    m = re.search(r"\b(?:cadastra|cadastre|cadastrar|coloca|coloque|registra|registre|inclui|inclua|lanca|lance|poe|ponha|adiciona|adicione)"
                  r"\s+(?:a|o|as|os)?\s*(.+?)\s+(?:como|na|nas|em)\s+(?:despesa|conta)", plano)
    nome = ""
    if m:
        ini = m.start(1)
        nome = _nome_proprio(texto[ini:m.end(1)].lower())
        nome = nome[:1].upper() + nome[1:]
    valor = ""
    m = re.search(r"(r\$\s*[\d.,]+|\b[\d.]+,\d{2}\b|\b\d{1,3}(?:\.\d{3})+\b)", plano)
    if m:
        valor = valor_em_reais(m.group(1))
    dia = 0
    m = re.search(r"\b(?:todo\s+)?dia\s+(\d{1,2})\b", plano)
    if m and 1 <= int(m.group(1)) <= 31:
        dia = int(m.group(1))
    return {"tipo": "despesa", "nome": nome, "valor": valor, "dia": dia}


MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_TELA = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def ler_contrato(texto: str) -> dict:
    """
    O que um contrato de locacao/prestacao diz, por regra: o valor mensal, o
    dia do pagamento, o reajuste (indice e mes), o fim da vigencia e quem
    recebe (nome e CNPJ/CPF). Cada campo vem so quando a regra tem certeza.
    """
    t = " ".join((texto or "").split())
    p = _plano(t)
    achado: dict = {}
    m = re.search(r"(?:aluguel|valor mensal|mensalidade|valor do aluguel|pagara mensalmente|mensalmente)[^.]{0,120}?(r\$\s*[\d.]+,\d{2})", p)
    if not m:
        m = re.search(r"(r\$\s*[\d.]+,\d{2})[^.]{0,60}?(?:por mes|mensais|mensal)", p)
    if m:
        achado["valor"] = valor_em_reais(m.group(1))
    m = re.search(r"(?:ate o|todo|no)\s+dia\s+(\d{1,2})\s*(?:\(\w+\)\s*)?(?:de cada mes|do mes|de cada|mensal|subsequente)", p)
    if m and 1 <= int(m.group(1)) <= 31:
        achado["dia"] = int(m.group(1))
    m = re.search(r"reajust\w*[^.]{0,120}?\b(igp-?m|ipca|inpc|igp-?di)\b", p)
    if m:
        indice = m.group(1).upper().replace("IGPM", "IGP-M").replace("IGPDI", "IGP-DI")
        mes = re.search(r"\b(" + "|".join(MESES) + r")\b", p[m.start():m.end() + 80])
        achado["reajuste"] = f"Reajuste anual pelo {indice}" + (f" em {MESES_TELA[MESES.index(mes.group(1))]}" if mes else "")
    m = re.search(r"(?:vigencia|prazo)[^.]{0,80}?(?:ate|termino em|encerrando-se em)\s+(\d{1,2})/(\d{1,2})/(\d{4})", p)
    if m:
        achado["ate"] = f"{int(m.group(2)):02d}/{m.group(3)}"
    m = re.search(r"\b((?i:locador[a]?|contratad[oa]|credor[a]?|prestador[a]?))\s*:?\s*,?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç&.\- ]{3,80}?)(?:,|\s+(?i:inscrit|pessoa|com sede|cnpj|cpf|portador))", t)
    if m:
        achado["fornecedor"] = m.group(2).strip(" .-")
        perto = t[m.end():m.end() + 200]
        doc = re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{3}\.?\d{3}\.?\d{3}-?\d{2}", perto)
        if doc:
            achado["documento"] = campos_br.formatar_documento(doc.group(0))
    email = RE_EMAIL.search(t)
    if email:
        achado["email"] = email.group(0)
    return achado


# ------------------------------------------------- o nome no Acervo

RE_DOC = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
RE_ENDERECO = re.compile(
    r"\b((?:Av\.?|Avenida|Rua|R\.|Rodovia|Rod\.|Travessa|Tv\.|Estrada|Alameda|Praça|Pça\.?)\s+[^,;\n]{2,60}?,?\s*(?:n[º°o.]?\s*)?\d{1,5}"
    r"(?:[^;\n.]{0,70}?(?:/[A-Z]{2}|-[A-Z]{2}\b))?)", re.I)
RE_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
PALAVRAS_PJ = ("ltda", "s/a", "s.a", "eireli", "me ", "epp", "congregacao", "igreja", "associacao", "cooperativa",
               "instituto", "fundacao", "empresa", "comercio", "industria", "servicos", "condominio", "sindicato",
               "agropecuaria", "transportes", "fazenda", "imobiliaria", "clinica", "escritorio")


def parece_pj(nome: str) -> bool:
    p = " " + _plano(nome) + " "
    return any((" " + k) in p for k in PALAVRAS_PJ)


def _variantes(nome: str) -> list[str]:
    """O nome inteiro e, sem o fim, o comeco que ja e o mesmo nome ("Congregação Cristã" de "...no Brasil")."""
    p = re.sub(r"[^a-z0-9 ]", " ", _plano(nome))
    palavras = [x for x in p.split() if x]
    saida = [" ".join(palavras)]
    if len(palavras) >= 3:
        saida.append(" ".join(palavras[:2]))
    return [s for s in saida if len(s) >= 5]


def _nome_por_extenso(trecho: str, minimo: int) -> str:
    """
    O nome como o documento escreve, ate onde ele vai: "Congregação Cristã"
    pedido acha "CONGREGAÇÃO CRISTÃ NO BRASIL". Depois do pedaco procurado,
    seguem as palavras com maiuscula e as particulas (no, da, de...), e para
    na pontuacao ou na palavra em minuscula.
    """
    palavras = re.split(r"(\s+)", trecho)
    saida, tamanho = [], 0
    for p in palavras:
        if tamanho >= minimo and p.strip():
            limpa = p.strip(",.;:()")
            if not limpa or not (limpa[:1].isupper() or _plano(limpa) in {"no", "na", "do", "da", "de", "dos", "das", "e"}):
                break
            if limpa != p.strip():
                saida.append(p.rstrip(",.;:()"))
                break
        saida.append(p)
        tamanho += len(p)
    nome = "".join(saida).strip(" ,.;:-")
    nome = re.sub(r"\s+(?:no|na|do|da|de|dos|das|e)$", "", nome, flags=re.I)
    return " ".join(nome.split())


def achar_no_acervo(nome: str, documentos, limite: int = 6) -> dict:
    """
    Onde o nome aparece no Acervo e o que ha perto dele em cada documento:
    o CPF/CNPJ, o endereco e a data. `documentos`: objetos com name, path e
    text (o Acervo aberto). Devolve {total, documentos: [...os com dado,
    ate `limite`], sem_dado, campos: {documento, endereco, nome}, origem:
    {campo: n documentos}}.
    """
    variantes = _variantes(nome)
    if not variantes:
        return {"total": 0, "documentos": [], "sem_dado": 0, "campos": {}, "origem": {}}
    achados = []
    for d in documentos or []:
        base = _nfc(getattr(d, "text", "") or "")
        if not base:
            continue
        plano = re.sub(r"[^a-z0-9 ]", " ", _plano(base))
        if len(plano) != len(base):
            plano = plano[:len(base)].ljust(len(base))
        pos = -1
        for v in variantes:
            pos = plano.find(v)
            if pos >= 0:
                break
        if pos < 0:
            continue
        # O plano tem o mesmo tamanho do texto em NFC: as posicoes batem.
        janela = base[max(0, pos - 220):pos + 320]
        trecho = " ".join(base[max(0, pos - 30):pos + 90].split())
        campos = ["nome"]
        doc = RE_DOC.search(janela)
        endereco = RE_ENDERECO.search(janela)
        nome_no_doc = _nome_por_extenso(base[pos:pos + 120], len(variantes[0]))
        item = {"nome": d.name, "sha1": getattr(d, "sha1", "") or "", "trecho": ("…" if pos > 30 else "") + trecho + "…", "campos": campos,
                "documento": "", "endereco": "", "nome_lido": nome_no_doc, "data": ""}
        if doc and not campos_br.problema("cpf-cnpj", doc.group(0)):
            item["documento"] = campos_br.formatar_documento(doc.group(0))
            campos.append(campos_br.rotulo_do_documento(doc.group(0)))
        if endereco:
            item["endereco"] = " ".join(endereco.group(1).split()).strip(" ,.")
            campos.append("endereço")
        data = RE_DATA.search(base)
        if data:
            item["data"] = f"{int(data.group(1)):02d}/{int(data.group(2)):02d}"
        achados.append(item)
    com_dado = [a for a in achados if len(a["campos"]) > 1]
    sem_dado = [a for a in achados if len(a["campos"]) == 1]
    mostrar = (com_dado + sem_dado)[:limite]
    documentos_lidos = Counter(a["documento"] for a in achados if a["documento"])
    enderecos = Counter(a["endereco"] for a in achados if a["endereco"])
    nomes = Counter(a["nome_lido"].upper() for a in achados if a["nome_lido"])
    campos = {}
    origem = {}
    if documentos_lidos:
        campos["documento"], origem["documento"] = documentos_lidos.most_common(1)[0]
    if enderecos:
        campos["endereco"], origem["endereco"] = enderecos.most_common(1)[0]
    origem["nome"] = len(achados)
    return {"total": len(achados), "documentos": mostrar, "sem_dado": max(0, len(achados) - len(mostrar)),
            "campos": campos, "origem": origem,
            "nome_mais_lido": max(nomes.items(), key=lambda kv: (kv[1], len(kv[0])))[0] if nomes else ""}


def aviso_do_documento(documento: str, pessoa: str) -> str:
    """ "confira: é um CPF, não um CNPJ" quando o documento nao combina com o tipo da ficha."""
    if not documento:
        return ""
    problema = campos_br.problema("cpf-cnpj", documento)
    if problema:
        return "confira: " + problema
    cnpj = campos_br.e_cnpj(documento)
    if pessoa == "juridica" and not cnpj:
        return "confira: é um CPF, não um CNPJ"
    if pessoa == "fisica" and cnpj:
        return "confira: é um CNPJ, não um CPF"
    return ""


# ------------------------------------------- a correcao escrita na conversa

RE_DIA = re.compile(r"\b(?:todo\s+)?dia\s+(\d{1,2})\b")


def corrigir(texto: str) -> dict:
    """
    Com a ficha aberta na coluna, o que a frase corrige: CPF/CNPJ, telefone,
    e-mail, valor, dia e endereco, por regra. So o que a frase traz; o resto
    da ficha fica como estava. Vazio: a frase nao e correcao da ficha.
    """
    import intencao

    texto = _nfc(texto)
    plano = _plano(texto)
    saida: dict = {}
    for chave, padrao in (("email", intencao.RE_EMAIL), ("documento", intencao.RE_CNPJ), ("documento", intencao.RE_CPF),
                          ("telefone", intencao.RE_TELEFONE)):
        if chave in saida:
            continue
        m = padrao.search(texto)
        if m:
            saida[chave] = m.group(0).strip()
    m = re.search(r"(r\$\s*[\d.]+(?:,\d{2})?|\b[\d.]+,\d{2}\b)", plano)
    if m:
        saida["valor"] = valor_em_reais(m.group(1))
    m = RE_DIA.search(plano)
    if m and 1 <= int(m.group(1)) <= 31 and not re.search(r"\d{1,2}/\d{1,2}", plano):
        saida["dia"] = int(m.group(1))
    m = intencao.RE_ENDERECO.search(texto)
    if m:
        saida["endereco"] = " ".join(m.group(1).split()).strip(" .,;")
    m = re.search(r"\b(?:o nome (?:e|certo e)|chama-se|se chama|nome:)\s+(.+?)\s*(?:[,.;]|$)", texto, re.I)
    if m:
        saida["nome"] = m.group(1).strip()
    return saida


# ------------------------------------- a qualificacao das partes (varias fichas)
#
# "Vendedores: OBEDI LOURENÇO SANTOS, portador do RG nº 4091179 PC/PA e CPF nº
#  752.043.042-15, e seu conjuge SWEDY PEREIRA SANTOS, ..., ambos residentes e
#  domiciliados à Avenida Araguaia, ..., doravante denominados em conjunto como
#  VENDEDORES;" - o jeito de contrato brasileiro. Cada pessoa vira uma ficha
# de cliente; o que nao tem campo proprio (RG, nacionalidade, estado civil,
# profissao, conjuge, papel) vai para a observacao. Tudo por regra; nada e
# gravado sem o sim no cartao.

# O comeco do rotulo (sem acento, minusculo) e como ele aparece na ficha.
PAPEIS = (
    ("promitente vendedor", "promitente vendedor(a)"), ("promitente comprador", "promitente comprador(a)"),
    ("vendedor", "vendedor(a)"), ("comprador", "comprador(a)"), ("adquirente", "adquirente"),
    ("outorgante", "outorgante"), ("outorgad", "outorgado(a)"), ("locador", "locador(a)"),
    ("locatari", "locatário(a)"), ("contratante", "contratante"), ("contratad", "contratado(a)"),
    ("cedente", "cedente"), ("cessionari", "cessionário(a)"), ("doador", "doador(a)"),
    ("donatari", "donatário(a)"), ("permutante", "permutante"), ("fiador", "fiador(a)"),
    ("credor", "credor(a)"), ("devedor", "devedor(a)"), ("mutuante", "mutuante"), ("mutuari", "mutuário(a)"),
    ("comodante", "comodante"), ("comodatari", "comodatário(a)"), ("interveniente", "interveniente"),
    ("anuente", "anuente"), ("requerente", "requerente"), ("herdeir", "herdeiro(a)"),
    ("inventariante", "inventariante"),
)
# Palavras que dizem "as pessoas do contrato" sem dizer o papel: nunca nome.
PARTES_EM_GERAL = {"partes", "parte", "qualificados", "qualificadas", "qualificado", "qualificada", "pessoas",
                   "envolvidos", "envolvidas", "signatarios", "signatarias", "contratantes"}


def papel_do_rotulo(rotulo: str) -> str:
    """ "Vendedores" -> "vendedor(a)". Vazio quando o rotulo nao e papel de contrato."""
    p = re.sub(r"\((?:a|as|s|es|os)\)", "", _plano(rotulo)).strip(" :")
    p = " ".join(p.split())
    if not p or len(p) > 40:
        return ""
    for comeco, nome in PAPEIS:
        if p.startswith(comeco) and len(p) <= len(comeco) + 6:
            return nome
    return ""


RE_ROTULO_PAPEL = re.compile(r"(?:^|(?<=[\n;.]))[ \t]*(?:\d+[.)-]?[ \t]*)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ() /]{2,40}?)[ \t]*:", re.M)
_MAI = "A-ZÀ-ÖØ-Þ"
RE_NOME_CAIXA_ALTA = re.compile(
    r"(?<![\w/])([" + _MAI + r"][" + _MAI + r"'’]+(?:[ \t]+(?:D[AEO]S?|E|[" + _MAI + r"][" + _MAI + r"'’]+))+)(?![\w/])")
RE_DEPOIS_DO_NOME = re.compile(
    r"\s*[,(]|\s+(?:portador|brasileir|inscrit|casad|solteir|divorciad|vi[uú]v|resident|pessoa|maior|nascid)", re.I)
RE_NOME_MISTO = re.compile(
    r"\s*([" + _MAI + r"][\wÀ-ÿ'’]+(?:\s+(?:d[aeo]s?|e|[" + _MAI + r"][\wÀ-ÿ'’]+)){1,8})")
RE_CONJUGE = re.compile(r",?\s*\be\s+(?:seu|sua)\s+(?:c[oô]njuge|esposa|esposo|marido|mulher|companheir[oa]|convivente)\s*",
                        re.I)
RE_RESIDENCIA = re.compile(
    r"\b(?:(ambos|ambas|todos|todas)\s*,?\s*)?(resident[ea]s?)\s+e\s+domiciliad[oa]s?\s*,?\s*"
    r"(?:(?:à|a|na|no|em|nesta|neste)\s+)?(.+?)\s*"
    r"(?=,\s*(?:doravante|neste\s+ato|portador|inscrit|com\s+(?:o\s+)?(?:cpf|rg))|;|\n\s*\n|$)", re.I | re.S)
RE_RG = re.compile(
    r"(?:\b(?i:r\.?\s?g\.?)(?![\w])|(?i:carteira de identidade|c[ée]dula de identidade))"
    r"[^\d\n]{0,20}?(\d[\d.\-]*\d)"
    r"(?:[ \t]*[-–]?[ \t]*((?!CPF|CNPJ)[A-Z]{2,6}(?:[ \t]*/[ \t]*[A-Z]{2}|-[A-Z]{2})?)(?![\w]))?")
RE_DOC_ROTULADO = re.compile(r"(?i:\b(?:cpf|cnpj)(?:/mf)?)[^\d\n]{0,25}?(" + RE_DOC.pattern + r")")
RE_CEP = re.compile(r"(?<!\d)(\d{2}\.?\d{3}-\d{3})(?!\d)|(?i:cep)[:\s]*(\d{8})(?!\d)")
RE_NACIONALIDADE = re.compile(r"\b(brasileir[oa]|portugu[eê]s[a]?|argentin[oa]|paraguai[oa]|uruguai[oa]|estrangeir[oa]|"
                              r"naturalizad[oa])\b", re.I)
RE_ESTADO_CIVIL = re.compile(r"\b(casad[oa]|solteir[oa]|divorciad[oa]|vi[uú]v[oa]|separad[oa](?:\s+judicialmente)?|"
                             r"em\s+uni[aã]o\s+est[aá]vel|convivente)\b", re.I)
RE_FIM_DA_CABECA = re.compile(r"(?i)\b(?:portador|inscrit|r\.?g\.?(?![\w])|cpf|cnpj|resident|domiciliad|nascid|"
                              r"filh[oa]s?\b|doravante|com sede|pessoa jur)")
NAO_E_NOME = {"cpf", "cnpj", "rg", "ssp", "qualificacao", "clausula", "contrato", "instrumento", "objeto", "imovel"}


def _nome_da_qualificacao(bruto: str) -> str:
    nome = " ".join((bruto or "").split()).strip(" .,;:-–—")
    if nome.isupper():
        nome = _nome_proprio(nome.lower())
    return nome


def _e_palavra_de_papel(palavra: str) -> bool:
    p = _plano(palavra)
    return p in PARTES_EM_GERAL or bool(papel_do_rotulo(p))


def _grupos(texto: str) -> list[tuple[str, int, int, int]]:
    """(papel, onde o rotulo comeca, onde o grupo comeca, onde acaba) - sem rotulo, um grupo so."""
    rotulos = [(m, papel_do_rotulo(m.group(1))) for m in RE_ROTULO_PAPEL.finditer(texto)]
    rotulos = [(m, p) for m, p in rotulos if p]
    if not rotulos:
        return [("", 0, 0, len(texto))]
    saida = []
    for i, (m, papel) in enumerate(rotulos):
        fim = rotulos[i + 1][0].start() if i + 1 < len(rotulos) else len(texto)
        saida.append((papel, m.start(), m.end(), fim))
    return saida


def _fim_do_grupo(texto: str, ini: int, fim: int) -> int:
    """O grupo acaba no "doravante denominados ...;" ou no paragrafo seguinte ao primeiro CPF."""
    trecho = texto[ini:fim]
    m = re.search(r"(?i)doravante[^;\n]*?(?:[;\n]|\.(?:\s|$))", trecho)
    if m:
        fim = min(fim, ini + m.end())
        trecho = texto[ini:fim]
    doc = RE_DOC.search(trecho)
    if doc:
        quebra = re.search(r"\n[ \t]*\n", trecho[doc.end():])
        if quebra:
            fim = min(fim, ini + doc.end() + quebra.start())
    return fim


def _inicios(texto: str, ini: int, fim: int, residencias) -> list[tuple[int, int]]:
    """Onde comeca cada pessoa do grupo: (inicio, fim do nome)."""
    saida = []
    for m in RE_NOME_CAIXA_ALTA.finditer(texto, ini, fim):
        if any(a <= m.start() < b for a, b in residencias):
            continue
        palavras = [_plano(p) for p in m.group(1).split() if _plano(p) not in PARTICULAS]
        if not palavras or any(p in NAO_E_NOME or _e_palavra_de_papel(p) for p in palavras):
            continue
        if not RE_DEPOIS_DO_NOME.match(texto, m.end()):
            continue
        saida.append((m.start(), m.end()))
    if saida:
        return saida
    # Nome em maiuscula e minuscula ("Obedi Lourenço Santos, portador..."):
    # no comeco do grupo e depois de "e seu cônjuge".
    pontos = [ini] + [c.end() for c in RE_CONJUGE.finditer(texto, ini, fim)]
    for p in pontos:
        m = RE_NOME_MISTO.match(texto, p, fim)
        if m and RE_DEPOIS_DO_NOME.match(texto, m.end()):
            saida.append((m.start(1), m.end(1)))
    return saida


def _documento(trecho: str) -> tuple[str, str]:
    """(o CPF/CNPJ com a mascara, o aviso quando nao confere)."""
    m = RE_DOC_ROTULADO.search(trecho)
    bruto = m.group(1) if m else (RE_DOC.search(trecho).group(0) if RE_DOC.search(trecho) else "")
    if not bruto:
        return "", ""
    try:
        return campos_br.formatar_documento(bruto), ""
    except ValueError as exc:
        return bruto, str(exc)


def _profissao(cabeca: str) -> str:
    for item in cabeca.split(","):
        item = " ".join(item.split()).strip(" .;:")
        if not item or RE_NACIONALIDADE.fullmatch(item) or RE_ESTADO_CIVIL.fullmatch(item):
            continue
        if re.search(r"\d", item) or _plano(item) in {"maior", "capaz", "maior e capaz"}:
            continue
        if len(item.split()) <= 4 and re.fullmatch(r"[A-Za-zÀ-ÿ\s'’-]{3,40}", item):
            return item.lower() if not item.islower() and item.isupper() else item
    return ""


def _ler(texto: str) -> tuple[list[dict], int, int]:
    """As pessoas, onde a qualificacao comeca e onde acaba."""
    texto = _nfc(texto)
    pessoas: list[dict] = []
    inicio, fim_total = -1, -1
    for papel, rot, ini, fim in _grupos(texto):
        fim = _fim_do_grupo(texto, ini, fim)
        residencias = [(m.start(), m.end()) for m in RE_RESIDENCIA.finditer(texto, ini, fim)]
        inicios = _inicios(texto, ini, fim, residencias)
        if not inicios:
            continue
        grupo = []
        for i, (a, b) in enumerate(inicios):
            seg_fim = inicios[i + 1][0] if i + 1 < len(inicios) else fim
            seg = texto[a:seg_fim]
            conjuge_depois = RE_CONJUGE.search(seg)
            casado_com_o_seguinte = bool(conjuge_depois and i + 1 < len(inicios)
                                         and not seg[conjuge_depois.end():].strip())
            if casado_com_o_seguinte:
                seg = seg[:conjuge_depois.start()]
            residencia = RE_RESIDENCIA.search(seg)
            proprio = seg[:residencia.start()] if residencia else seg
            documento, aviso = _documento(proprio)
            rg = RE_RG.search(proprio)
            corte = RE_FIM_DA_CABECA.search(proprio, b - a)
            cabeca = proprio[b - a:corte.start() if corte else len(proprio)]
            nacionalidade = RE_NACIONALIDADE.search(proprio)
            civil = RE_ESTADO_CIVIL.search(proprio)
            nome = _nome_da_qualificacao(texto[a:b])
            grupo.append({
                "tipo": "cliente", "nome": nome, "documento": documento, "aviso": aviso,
                "pessoa": "juridica" if (parece_pj(nome) or campos_br.e_cnpj(documento)) else "fisica",
                "endereco": "", "end_cep": "", "papel": papel,
                "rg": " ".join(x for x in (rg.group(1), rg.group(2) or "") if x) if rg else "",
                "nacionalidade": nacionalidade.group(1).lower() if nacionalidade else "",
                "estado_civil": " ".join(civil.group(1).lower().split()) if civil else "",
                "profissao": _profissao(cabeca), "conjuge": "",
                "_casado_com_o_seguinte": casado_com_o_seguinte,
                "_residencia": residencia,
            })
        # O conjuge, dos dois lados.
        for i, p in enumerate(grupo):
            if p.pop("_casado_com_o_seguinte") and i + 1 < len(grupo):
                p["conjuge"] = grupo[i + 1]["nome"]
                grupo[i + 1]["conjuge"] = p["nome"]
        # O endereco: o de cada um; "ambos residentes" (ou o plural) vale para o grupo.
        comum = ""
        for p in grupo:
            r = p.pop("_residencia")
            if not r:
                continue
            endereco = " ".join(r.group(3).split()).strip(" .,;")
            p["endereco"] = endereco
            if r.group(1) or _plano(r.group(2)).endswith("s"):
                comum = endereco
        for p in grupo:
            if not p["endereco"] and comum:
                p["endereco"] = comum
        if not grupo:
            continue
        comeco = rot if rot != ini else inicios[0][0]
        inicio = comeco if inicio < 0 else min(inicio, comeco)
        fim_total = max(fim_total, fim)
        pessoas.extend(grupo)

    vistos: set[str] = set()
    saida = []
    for p in pessoas:
        if not (p["documento"] or p["rg"]) or not p["nome"]:
            continue
        chave = campos_br.so_digitos(p["documento"]) or _plano(p["nome"])
        if chave in vistos:
            continue
        vistos.add(chave)
        cep = RE_CEP.search(p["endereco"])
        if cep:
            digitos = campos_br.so_digitos(cep.group(1) or cep.group(2))
            p["end_cep"] = digitos if len(digitos) == 8 else ""
        p["observacao"] = " · ".join(x for x in (
            p["papel"], p["nacionalidade"], p["estado_civil"], p["profissao"],
            ("RG " + p["rg"]) if p["rg"] else "", ("cônjuge de " + p["conjuge"]) if p["conjuge"] else "") if x)
        saida.append(p)
    return saida, max(inicio, 0), fim_total


def ler_qualificacoes(texto: str) -> list[dict]:
    """
    As pessoas qualificadas no texto, no padrao de contrato brasileiro. Cada
    uma: tipo ("cliente"), nome (em forma propria), pessoa (fisica/juridica),
    documento (CPF/CNPJ com a mascara; `aviso` quando nao confere), endereco,
    end_cep (8 digitos ou vazio), observacao (papel · nacionalidade · estado
    civil · profissao · RG · conjuge) e as pecas dela (papel, rg, conjuge...).
    So entra quem tem nome e CPF/CNPJ ou RG; o mesmo CPF entra uma vez.
    """
    return _ler(texto)[0]


# O que pode vir antes da qualificacao colada sozinha: o titulo dela.
CABECA_DA_QUALIFICACAO = {"qualificacao", "qualificacoes", "das", "da", "partes", "as", "os", "seguintes", "qualificados",
                          "qualificadas", "pessoas", "segue", "seguem", "dados", "e"}


def so_qualificacao(texto: str) -> list[dict] | None:
    """
    A mensagem e SO a qualificacao de duas ou mais pessoas, sem outro pedido
    ("Vendedores: OBEDI ...; Comprador: HUGO ...;")? As pessoas; senao None.
    """
    if "?" in (texto or ""):
        return None
    pessoas, inicio, fim = _ler(texto)
    if len(pessoas) < 2:
        return None
    texto = _nfc(texto)
    antes = re.findall(r"[a-z]+", _plano(texto[:inicio]))
    depois = re.findall(r"[a-z0-9]+", _plano(texto[fim:])) if fim >= 0 else []
    if any(p not in CABECA_DA_QUALIFICACAO for p in antes) or depois:
        return None
    return pessoas


RE_VERBO_PARTES = re.compile(r"\b(cadastr(?:e|a|ar)|registr(?:e|a|ar)|inclu(?:a|i|ir)|adicion(?:e|a|ar)|salv(?:e|a|ar)|"
                             r"coloc(?:a|ar)|coloque|ponha)\b")
SALTAR_NO_PEDIDO = {"as", "os", "a", "o", "todas", "todos", "tambem", "ai", "aqui", "para", "pra", "mim", "e", "ou",
                    "como", "em", "no", "nos", "na", "nas", "cadastros", "cadastro", "sistema", "clientes", "fichas",
                    "de", "do", "da", "dos", "das", "deste", "desta", "dessa", "desse", "neste", "nesta", "nesse",
                    "nessa", "contrato", "instrumento", "documento", "escritura", "minuta", "aberto", "aberta",
                    "anexo", "anexado", "anexada", "ao", "lado", "seguintes", "duas", "dois", "tres", "quatro", "cada",
                    "uma", "um", "promitentes", "promitente"}


def pedido_de_partes(texto: str) -> dict | None:
    """
    "Cadastre as partes", "cadastre os vendedores e os compradores", "inclua
    os qualificados deste contrato": as pessoas estao no documento, e nao na
    frase. {"papeis": [...] (vazio = todas), "inicio": onde o verbo comeca}.
    """
    plano = _plano(texto)
    m = RE_VERBO_PARTES.search(plano)
    if not m:
        return None
    papeis: list[str] = []
    todas = False
    for palavra in re.findall(r"[a-z/]+", plano[m.end():])[:16]:
        if palavra in PARTES_EM_GERAL:
            todas = True
            continue
        papel = papel_do_rotulo(palavra)
        if papel:
            if papel not in papeis:
                papeis.append(papel)
            continue
        if palavra in SALTAR_NO_PEDIDO or palavra == "e/ou":
            continue
        break
    if not (todas or papeis):
        return None
    return {"papeis": [] if todas and not papeis else papeis, "inicio": m.start()}


def do_papel(pessoas: list[dict], papeis) -> list[dict]:
    """So as pessoas dos papeis pedidos (vazio: todas). "contratantes" pede as duas pontas."""
    if not papeis:
        return list(pessoas)
    return [p for p in pessoas if p.get("papel") in papeis]
