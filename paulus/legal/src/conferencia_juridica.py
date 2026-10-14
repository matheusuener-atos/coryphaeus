"""
PAULUS - A conferência jurídica do documento (docs/PLANO-EDITOR.md, E6).

Tudo regra, nada de modelo: roda em milissegundos, dá sempre a mesma resposta
e cada aviso aponta o bloco (o nome dele, src/blocos.py). É o que um revisor
de escritório confere antes de o contrato sair, e o que mais escapa na
leitura:

  numeração      cláusula repetida ou pulada (1, 2, 4)
  referências    "conforme a cláusula 9" num contrato de sete; e a referência
                 que passou a apontar para OUTRA cláusula depois de apagar ou
                 inserir uma (a 2ª era "DO PRAZO", agora é "DO ALUGUEL")
  termos         o papel em maiúsculas usado sem definição (INQUILINA num
                 contrato que definiu LOCATÁRIA)
  valores        o número e o extenso que não batem ("R$ 2.600,00 (dois mil e
                 quatrocentos reais)"), também em prazo e percentual
  datas          data que não existe (31 de fevereiro)
  documentos     CPF e CNPJ que não fecham no dígito (documento.conferir)
  lacunas        [●], [VALOR], "____" que ficaram
  leis           artigo citado que não existe no código instalado, ou revogado
  conversa       "Segue a minuta", "Notas para o advogado", "Espero ter
                 ajudado" dentro do corpo

Cada aviso: {"grau": "impede" | "confira", "bloco": id, "rotulo": "Cláusula 3ª",
"titulo": "...", "detalhe": "...", "regra": "..."}.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

import blocos as B
import esboco as E


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------- por extenso

_NUMEROS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
    "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezasseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
    "trinta": 30, "quarenta": 40, "cinquenta": 50, "cinqüenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
    "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200, "trezentos": 300, "trezentas": 300,
    "quatrocentos": 400, "quatrocentas": 400, "quinhentos": 500, "quinhentas": 500, "seiscentos": 600,
    "seiscentas": 600, "setecentos": 700, "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900,
}
_ESCALAS = {"mil": 1000, "milhao": 10 ** 6, "milhoes": 10 ** 6, "bilhao": 10 ** 9, "bilhoes": 10 ** 9}


def numero_do_extenso(texto: str) -> int | None:
    """
    "oitocentos e cinquenta mil" → 850000; "dois mil e seiscentos" → 2600.
    None quando aparece palavra que não é número (o extenso não é só número).
    """
    total = 0
    grupo = 0
    achou = False
    for p in re.findall(r"[a-z]+", _plano(texto)):
        if p in ("e", "de"):
            continue
        if p in _NUMEROS:
            grupo += _NUMEROS[p]
            achou = True
        elif p in _ESCALAS:
            total += max(grupo, 1) * _ESCALAS[p]
            grupo = 0
            achou = True
        else:
            return None
    return total + grupo if achou else None


def _valor(numero: str) -> float | None:
    """'2.600,00' → 2600.0; '30' → 30.0."""
    t = numero.strip()
    try:
        if "," in t:
            return float(t.replace(".", "").replace(",", "."))
        return float(t.replace(".", ""))
    except ValueError:
        return None


RE_REAIS = re.compile(r"R\$\s*([\d.]+(?:,\d{2})?)\s*\(([^)]{3,160})\)")
RE_QUANTIDADE = re.compile(r"(?<![\d.,/])(\d{1,3}(?:\.\d{3})*|\d+)\s*(%|por cento)?\s*\(([a-zA-ZÀ-ÿ ,-]{3,80})\)")


def _reais_do_extenso(texto: str) -> float | None:
    """'dois mil e seiscentos reais e cinquenta centavos' → 2600.5."""
    p = _plano(texto)
    m = re.match(r"\s*(.*?)\s+(?:reais|real)\b(?:\s+e\s+(.*?)\s+centavos?)?", p)
    if not m:
        m2 = re.match(r"\s*(.*?)\s+centavos?\b", p)
        if m2:
            c = numero_do_extenso(m2.group(1))
            return c / 100 if c is not None else None
        return None
    inteiro = numero_do_extenso(m.group(1))
    if inteiro is None:
        return None
    centavos = numero_do_extenso(m.group(2)) if m.group(2) else 0
    if centavos is None:
        return None
    return inteiro + centavos / 100


# ------------------------------------------------------------- datas

_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
          "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
RE_DATA_EXTENSO = re.compile(r"\b(\d{1,2})º?\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|"
                             r"outubro|novembro|dezembro)\s+de\s+(\d{4})\b", re.I)
RE_DATA_NUMERICA = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")


def _data_valida(d: int, m: int, a: int) -> bool:
    try:
        date(a, m, d)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------- termos

PAPEIS = ("LOCADOR", "LOCADORA", "LOCADORES", "LOCATÁRIO", "LOCATÁRIA", "LOCATÁRIOS", "LOCATÁRIAS", "VENDEDOR",
          "VENDEDORA", "VENDEDORES", "COMPRADOR", "COMPRADORA", "COMPRADORES", "CONTRATANTE", "CONTRATANTES",
          "CONTRATADO", "CONTRATADA", "CONTRATADOS", "OUTORGANTE", "OUTORGANTES", "OUTORGADO", "OUTORGADA",
          "NOTIFICANTE", "NOTIFICADO", "NOTIFICADA", "CEDENTE", "CESSIONÁRIO", "CESSIONÁRIA", "DEVEDOR", "DEVEDORA",
          "CREDOR", "CREDORA", "FIADOR", "FIADORA", "FIADORES", "PROMITENTE", "PROMISSÁRIO", "PROMISSÁRIA",
          "INQUILINO", "INQUILINA", "PROPRIETÁRIO", "PROPRIETÁRIA", "COMODANTE", "COMODATÁRIO", "COMODATÁRIA",
          "MUTUANTE", "MUTUÁRIO", "MUTUÁRIA", "DONATÁRIO", "DOADOR", "PERMUTANTE", "AUTOR", "AUTORA", "RÉU", "RÉ",
          "REQUERENTE", "REQUERIDO", "REQUERIDA", "EMBARGANTE", "EMBARGADO", "EXEQUENTE", "EXECUTADO", "EXECUTADA")
RE_DEFINICAO = re.compile(r"(?:doravante\s+(?:denominad[oa]s?|chamad[oa]s?|designad[oa]s?)|simplesmente)\s+(?:como\s+)?"
                          r"[\"“]?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{2,40}?)[\"”]?(?=[\s,;.)]|$)")
RE_ROTULO_DE_PARTE = re.compile(r"^\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{2,30})\s*:")


def _termos_definidos(blocos: list) -> set[str]:
    definidos: set[str] = set()
    for b in blocos:
        for m in RE_DEFINICAO.finditer(b.texto):
            definidos.add(m.group(1).strip())
        m = RE_ROTULO_DE_PARTE.match(b.texto)
        if m:
            definidos.add(m.group(1).strip())
    # "PRIMEIRO CÔNJUGE" define "CÔNJUGE"; "VENDEDORES" cobre "VENDEDOR".
    extras = set()
    for t in definidos:
        for palavra in t.split():
            extras.add(palavra)
    return definidos | extras


def _singular_plural(papel: str) -> set[str]:
    base = papel.rstrip("S")
    return {papel, base, base + "S", base + "ES", base.rstrip("E") + "ES"}


# ------------------------------------------------------------- conversa

RE_CONVERSA_NO_CORPO = re.compile(
    r"(?i)^\s*(?:segue(?:m)?\s+(?:a|o|as|os)\s+(?:minuta|documento|contrato|vers[aã]o)|aqui\s+est[aá]|espero\s+ter\s+"
    r"ajudado|qualquer\s+d[uú]vida|como\s+(?:assistente|modelo\s+de\s+linguagem)|claro[!,]|notas?\s+para\s+o\s+advogado|"
    r"observa[cç][aã]o\s+do\s+assistente)")
RE_LACUNA = re.compile(r"\[\s*(?:●|•|\.{2,}|_+|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9 /º°-]{1,40})\s*\]|_{4,}|\bX{3,}\b")


# ------------------------------------------------------------- conferir

def conferir(blocos: list, *, fichas: list | None = None, leis=None, antes: list | None = None) -> list[dict]:
    """
    Os avisos do documento (as sugestões pendentes contam como aceitas: é o
    documento como ficaria). Com `antes` (o documento antes da rodada), também
    a referência que passou a apontar para outra cláusula.
    """
    import documento as D
    import redacao

    vivos = B.aceito(blocos)
    partes = E.esboco(vivos)
    rotulos = {p.id: p.rotulo for p in partes}
    avisos: list[dict] = []

    def aviso(grau, b, titulo, detalhe, regra, **conserto):
        # `conserto`: o que a revisão do agente precisa para corrigir sozinha
        # (os blocos do trecho repetido, a cláusula e o fecho antes do qual ela vai).
        avisos.append({"grau": grau, "bloco": b.id if hasattr(b, "id") else b, "rotulo": rotulos.get(getattr(b, "id", b), ""),
                       "titulo": titulo, "detalhe": detalhe, "regra": regra, **conserto})

    # numeração
    clausulas = E.clausulas(vivos)
    vistos: dict[int, str] = {}
    esperado = 1
    for c in clausulas:
        n = c["numero"]
        if n in vistos:
            aviso("impede", c["cabeca"], "Cláusula repetida", f"Há duas cláusulas {n}ª. Peça “renumere as cláusulas”.",
                  "numeracao")
        elif n != esperado and clausulas:
            aviso("confira", c["cabeca"], "Numeração fora de sequência",
                  f"Depois da {esperado - 1}ª vem a {n}ª. Peça “renumere as cláusulas”.", "numeracao")
        vistos[n] = c["titulo"]
        esperado = n + 1

    # referências que apontam para o nada
    for b in vivos:
        if b.tipo == "table":
            continue
        for q in redacao.referencias_quebradas("\n".join(x.texto for x in vivos if x.tipo != "table")):
            pass
        break
    texto_todo = "\n".join(x.texto for x in vivos if x.tipo != "table")
    existentes = {c["numero"] for c in clausulas}
    for b, p in zip(vivos, partes):
        if b.tipo == "table" or p.tipo == "clausula":
            continue
        for m in redacao.RE_REFERENCIA.finditer(b.texto):
            n = int(m.group("numero"))
            if existentes and n not in existentes:
                aviso("impede", b, "Referência para cláusula que não existe",
                      f"“{m.group(0)}” — o documento não tem cláusula {n}.", "referencia")

    # a referência que mudou de alvo (apagar ou inserir cláusula). O alvo é a
    # cabeça da cláusula - o bloco -, não o título: o título que ganhou
    # palavras continua sendo a mesma cláusula.
    if antes is not None:
        antes_vivos = B.aceito(antes)
        clausulas_antes = E.clausulas(antes_vivos)
        cabeca_antes = {c["numero"]: c["cabeca"] for c in clausulas_antes}
        titulo_antes = {c["numero"]: _titulo_da_cabeca(c["titulo"]) for c in clausulas_antes}
        cabeca_agora = {c["numero"]: c["cabeca"] for c in clausulas}
        titulo_agora = {c["numero"]: _titulo_da_cabeca(c["titulo"]) for c in clausulas}
        textos_antes = {x.id: x.texto for x in antes_vivos}
        for b, p in zip(vivos, partes):
            if b.tipo == "table" or p.tipo == "clausula":
                continue
            refs_antes = {int(m.group("numero")) for m in redacao.RE_REFERENCIA.finditer(textos_antes.get(b.id, ""))}
            for m in redacao.RE_REFERENCIA.finditer(b.texto):
                n = int(m.group("numero"))
                if (n in refs_antes and cabeca_antes.get(n) and cabeca_agora.get(n)
                        and cabeca_antes[n] != cabeca_agora[n]):
                    aviso("impede", b, "Referência que mudou de cláusula",
                          f"“{m.group(0)}” apontava para a cláusula “{titulo_antes[n].capitalize()}”; agora a {n}ª é "
                          f"“{titulo_agora[n].capitalize()}”. Confira se a referência deve acompanhar.", "referencia")

    # estrutura: o que ficou repetido, fora do lugar ou colado
    _estrutura(vivos, partes, aviso)

    # termos: papel em maiúsculas sem definição
    definidos = _termos_definidos(vivos)
    if definidos:
        cobertos = set()
        for t in definidos:
            cobertos |= _singular_plural(t)
        ja = set()
        for b in vivos:
            for papel in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}\b", b.texto):
                if papel in PAPEIS and papel not in cobertos and papel not in ja:
                    ja.add(papel)
                    aviso("confira", b, "Termo sem definição",
                          f"“{papel}” aparece em maiúsculas como parte, mas o documento não o define "
                          f"(as partes definidas são: {', '.join(sorted(t for t in definidos if t in PAPEIS)) or '—'}).",
                          "termos")

    # valores: número × extenso
    for b in vivos:
        if b.tipo == "table":
            continue
        for m in RE_REAIS.finditer(b.texto):
            numero = _valor(m.group(1))
            extenso = _reais_do_extenso(m.group(2))
            if numero is not None and extenso is not None and abs(numero - extenso) > 0.005:
                aviso("impede", b, "Valor e extenso não batem",
                      f"R$ {m.group(1)} está por extenso como “{m.group(2).strip()}”.", "valores")
        for m in RE_QUANTIDADE.finditer(b.texto):
            if b.texto[max(0, m.start() - 3):m.start()].strip().endswith("R$"):
                continue
            numero = _valor(m.group(1))
            palavras = re.sub(r"(?i)\bpor\s+cento\b", "", m.group(3))
            extenso = numero_do_extenso(palavras)
            if numero is not None and extenso is not None and abs(numero - extenso) > 0.005:
                aviso("impede", b, "Número e extenso não batem",
                      f"{m.group(1)}{m.group(2) or ''} está por extenso como “{m.group(3).strip()}”.", "valores")

    # datas
    for b in vivos:
        for m in RE_DATA_EXTENSO.finditer(b.texto):
            d, mes, a = int(m.group(1)), _MESES[_plano(m.group(2)).replace("ç", "c")], int(m.group(3))
            if not _data_valida(d, mes, a):
                aviso("impede", b, "Data que não existe", f"“{m.group(0)}” não existe no calendário.", "datas")
        for m in RE_DATA_NUMERICA.finditer(b.texto):
            d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if not _data_valida(d, mes, a):
                aviso("impede", b, "Data que não existe", f"“{m.group(0)}” não existe no calendário.", "datas")

    # CPF, CNPJ e as fichas (a regra de documento.conferir, pelo bloco)
    lidos = D.ler_html(B.html(vivos))
    por_indice = [b for b in vivos if b.tipo != "table" or b.linhas]
    for a in D.conferir(lidos, fichas or []):
        if a["titulo"] == "Falta preencher":
            continue                    # as lacunas vêm abaixo, com o nome do bloco
        i = int(a.get("bloco") or 0) - 1
        alvo = por_indice[i] if 0 <= i < len(por_indice) else (vivos[0] if vivos else None)
        if alvo is not None:
            aviso(a["grau"], alvo, a["titulo"], a["detalhe"], "documentos")

    # lacunas
    for b, p in zip(vivos, partes):
        if p.tipo == "assinatura":
            continue
        achadas = list(dict.fromkeys(m.group(0) for m in RE_LACUNA.finditer(b.texto)))
        if achadas:
            aviso("confira", b, "Falta preencher", "Ficou " + ", ".join(f"“{x}”" for x in achadas[:4]) + " no texto.",
                  "lacunas")

    # leis citadas
    if leis is not None:
        avisos += _conferir_leis(vivos, rotulos, leis)

    # conversa de assistente dentro do documento
    for b in vivos:
        if RE_CONVERSA_NO_CORPO.match(b.texto):
            aviso("impede", b, "Conversa dentro do documento",
                  "Este parágrafo é conversa de assistente, não texto do documento — apague-o antes de concluir.",
                  "conversa")
    return avisos


def _curto(texto: str, n: int = 70) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def _estrutura(vivos: list, partes: list, aviso) -> None:
    """
    O que um revisor vê de longe: o parágrafo que aparece duas vezes (o fecho e
    as assinaturas em dobro), a cláusula que ficou depois do fecho, os itens
    "12.1" dentro da Cláusula 13ª, a cabeça que leva o corpo junto.
    """
    rotulo = {p.id: p.rotulo for p in partes}
    lista = [(b, " ".join(_plano(b.texto).split())) for b in vivos if b.tipo != "table"]
    primeira: dict[str, int] = {}
    i = 0
    while i < len(lista):
        b, chave = lista[i]
        j = primeira.get(chave)
        if j is not None and len(chave) >= 25 and not RE_LACUNA.search(b.texto):
            # O trecho repetido inteiro: enquanto o seguinte daqui repete o seguinte de lá
            # (o fecho e as assinaturas em dobro são um aviso só).
            n = 1
            while i + n < len(lista) and j + n < i and lista[i + n][1] and lista[i + n][1] == lista[j + n][1]:
                n += 1
            trecho = [x for x, _ in lista[i:i + n]]
            onde = rotulo.get(lista[j][0].id) or "outro lugar"
            if n == 1:
                aviso("confira", b, "Parágrafo repetido", f"O mesmo texto já está em {onde}: “{_curto(b.texto)}”.",
                      "repetido", blocos=[b.id])
            else:
                aviso("confira", b, "Trecho repetido",
                      f"De “{_curto(b.texto, 40)}” a “{_curto(trecho[-1].texto, 40)}”: {n} parágrafos que já estão "
                      f"em {onde}.", "repetido", blocos=[x.id for x in trecho])
            i += n
            continue
        if chave and chave not in primeira:
            primeira[chave] = i
        i += 1

    fecho = ""
    cabecas = {c["cabeca"]: c for c in E.clausulas(vivos)}
    for b, p in zip(vivos, partes):
        if p.tipo in ("fecho", "data", "assinatura") and not fecho:
            fecho = b.id
        elif p.tipo == "clausula" and fecho:
            aviso("impede", b, "Cláusula depois do fecho",
                  f"A {p.rotulo} está depois do fecho e das assinaturas; o lugar dela é antes deles.", "estrutura",
                  blocos=cabecas.get(b.id, {}).get("blocos", [b.id]), antes_de=fecho)

    fora: dict[str, list] = {}
    for b, p in zip(vivos, partes):
        m = E.RE_SUBITEM.match(b.texto)
        if p.clausula and p.tipo != "clausula" and m and int(m.group(1)) != p.clausula:
            fora.setdefault(p.clausula_rotulo, []).append((b, m))
    for nome, itens in fora.items():
        primeiro, ultimo = itens[0][1], itens[-1][1]
        aqui = int(re.sub(r"\D", "", nome) or 0)
        de, ate = f"{primeiro.group(1)}.{primeiro.group(2)}", f"{ultimo.group(1)}.{ultimo.group(2)}"
        if len(itens) == 1:
            detalhe = f"O item “{de}” está na {nome}: seria {aqui}.{primeiro.group(2)}."
        else:
            detalhe = (f"Os itens “{de}” a “{ate}” estão na {nome}: seriam {aqui}.{primeiro.group(2)} a "
                       f"{aqui}.{ultimo.group(2)}.")
        aviso("confira", itens[0][0], "Itens com o número de outra cláusula", detalhe, "numeracao",
              itens=[{"bloco": b.id, "texto": re.sub(r"^(\s*)\d{1,3}\.", rf"\g<1>{aqui}.", b.texto, count=1)}
                     for b, _ in itens])

    for b, p in zip(vivos, partes):
        if p.tipo == "clausula" and "\n" in b.texto.strip():
            cabeca, resto = b.texto.strip().split("\n", 1)
            if len(resto.strip()) > 20:
                aviso("confira", b, "Cabeça com o corpo junto",
                      f"A cabeça da {p.rotulo} leva junto “{_curto(resto, 60)}”; o corpo deveria ser um parágrafo próprio.",
                      "estrutura", cabeca=cabeca.strip(), corpo=[x.strip() for x in resto.split("\n") if x.strip()])


def _titulo_da_cabeca(cabeca: str) -> str:
    """"CLÁUSULA 2ª – DO PRAZO" → "DO PRAZO" (o nome, sem o número)."""
    t = re.sub(r"(?i)^\s*cl[aá]usula\s+\S+\s*[-–—:.]?\s*", "", cabeca)
    t = re.sub(r"^\s*\d{1,3}\s*[.)\-–—]\s*", "", t)
    return " ".join(t.split()).upper()[:60]


def _conferir_leis(vivos: list, rotulos: dict, leis) -> list[dict]:
    """O artigo citado que não existe no código instalado, ou que está revogado."""
    import leis as leis_mod
    from inteligencia.extratores import regras_leis

    instalados = {c["codigo"] for c in leis.instalados() if c.get("instalado")}
    avisos = []
    for b in vivos:
        if b.tipo == "table":
            continue
        for a in regras_leis.achar(b.texto):
            d = a["dados"]
            if d.get("kind") != "article" or not d.get("article"):
                continue
            codigo = leis_mod.CODIGO_DO_INSTRUMENTO.get(d.get("instrument_id") or "")
            if not codigo or codigo not in instalados:
                continue
            achado = leis.artigo(codigo, str(d["article"]))
            nome = leis_mod.CODIGOS.get(codigo, {}).get("nome", codigo.upper())
            trecho = b.texto[a["inicio"]:a["fim"]]
            if achado is None:
                avisos.append({"grau": "impede", "bloco": b.id, "rotulo": rotulos.get(b.id, ""),
                               "titulo": "Artigo que não existe",
                               "detalhe": f"“{trecho}”: o {nome} instalado não tem o art. {d['article']}.", "regra": "leis"})
            elif achado.get("revogado"):
                avisos.append({"grau": "impede", "bloco": b.id, "rotulo": rotulos.get(b.id, ""),
                               "titulo": "Artigo revogado",
                               "detalhe": f"“{trecho}”: o art. {d['article']} do {nome} está revogado.", "regra": "leis"})
    return avisos


def novos(antes: list[dict], depois: list[dict]) -> list[dict]:
    """Os avisos que a rodada criou (o que já estava errado antes não é dela)."""
    chave = lambda a: (a["regra"], a["titulo"], a["detalhe"])  # noqa: E731
    velhos = {chave(a) for a in antes}
    return [a for a in depois if chave(a) not in velhos]
