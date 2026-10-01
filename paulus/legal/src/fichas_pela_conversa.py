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
