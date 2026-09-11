"""
O que o Word não faz para um advogado brasileiro.

O editor em si o Word já faz — negrito, alinhamento, lista. Repetir isso aqui
seria trabalho sem ganho. O que este módulo faz é o que é específico de
redigir contrato em português do Brasil, e que hoje se faz na mão:

**Renumerar cláusulas.** Inserir uma cláusula no meio obriga a renumerar todas
as seguintes — e as referências cruzadas que apontavam para elas. É o erro
mais comum e mais chato de um contrato: a cláusula 7 que cita "a cláusula 4"
quando a 4 virou 5.

**Qualificar as partes.** O parágrafo de qualificação é a parte mais repetitiva
de qualquer peça, e os dados já estão em Cadastros. Digitar de novo é onde
entram os erros de CPF e de endereço.

**Achar referência quebrada.** "Conforme cláusula 12" num contrato que tem
nove.

Duas decisões:

**O estilo do documento manda.** Medido nos contratos reais deste escritório,
existem pelo menos dois: "1ª CLAUSULA –" e "CLÁUSULA 1ª –", com e sem acento,
com hífen ou travessão. Renumerar não é reformatar: o que muda é o número, e
só ele.

**Nada é alterado em silêncio.** Toda operação devolve o que mudou, linha a
linha, para a tela mostrar antes de gravar.
"""

from __future__ import annotations

import re
import unicodedata

# "1ª CLAUSULA –", "2ª CLÁUSULA -", "6ª CLAUSULA  –": o numero vem antes.
RE_NUMERO_ANTES = re.compile(
    r"(?P<numero>\d{1,3})(?P<ordinal>[ªaº°]?)(?P<entre>\s+)"
    r"(?P<palavra>CL[ÁA]USULA)",
    re.IGNORECASE,
)

# "CLÁUSULA 1ª –", "CLAUSULA 12 -": o numero vem depois.
RE_NUMERO_DEPOIS = re.compile(
    r"(?P<palavra>CL[ÁA]USULA)(?P<entre>\s+)(?P<numero>\d{1,3})(?P<ordinal>[ªaº°]?)",
    re.IGNORECASE,
)

# "CLÁUSULA PRIMEIRA", "CLÁUSULA DÉCIMA SEGUNDA": o ordinal por extenso.
POR_EXTENSO = [
    "primeira", "segunda", "terceira", "quarta", "quinta", "sexta", "sétima",
    "oitava", "nona", "décima", "décima primeira", "décima segunda",
    "décima terceira", "décima quarta", "décima quinta", "décima sexta",
    "décima sétima", "décima oitava", "décima nona", "vigésima",
    "vigésima primeira", "vigésima segunda", "vigésima terceira",
    "vigésima quarta", "vigésima quinta", "vigésima sexta", "vigésima sétima",
    "vigésima oitava", "vigésima nona", "trigésima",
]
_POR_EXTENSO_PLANO = [
    "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn")
    for p in POR_EXTENSO
]
# Com e sem acento: o texto real traz "DÉCIMA SEGUNDA" e "DECIMA SEGUNDA", e
# aceitar só uma das formas deixava metade dos contratos de fora. As mais
# longas vêm primeiro para "décima segunda" não casar só em "décima".
_FORMAS_EXTENSO = sorted(
    {re.escape(p) for p in POR_EXTENSO} | {re.escape(p) for p in _POR_EXTENSO_PLANO},
    key=len, reverse=True,
)
RE_EXTENSO = re.compile(
    r"(?P<palavra>CL[ÁA]USULA)(?P<entre>\s+)(?P<extenso>"
    + "|".join(_FORMAS_EXTENSO)
    + r")\b",
    re.IGNORECASE,
)

# "conforme a cláusula 4", "nos termos da cláusula 7ª": a referencia cruzada.
RE_REFERENCIA = re.compile(
    r"cl[áa]usula\s+(?P<numero>\d{1,3})(?:[ªaº°])?",
    re.IGNORECASE,
)


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _mesma_caixa(molde: str, palavra: str) -> str:
    """Escreve `palavra` na caixa de `molde` — o documento manda no estilo."""
    if molde.isupper():
        return palavra.upper()
    if molde.istitle():
        return palavra.title()
    return palavra.lower()


# ------------------------------------------------------------- encontrar


def _abre_o_bloco(texto: str, posicao: int) -> bool:
    """
    A marca está no começo de um parágrafo?

    É o que separa o título da cláusula da referência a ela. "3ª CLÁUSULA – Da
    posse, conforme cláusula 2" tem as duas coisas: a primeira abre o
    parágrafo, a segunda mora no meio da frase. Sem essa distinção, renumerar
    reescrevia a referência como se fosse um título — e a cláusula seguinte
    saía com o número errado.
    """
    i = posicao - 1
    while i >= 0 and texto[i] in " \t ":
        i -= 1
    if i < 0:
        return True
    # ">" fecha a tag do bloco no HTML do editor; "\n", no texto puro.
    return texto[i] in "\n\r>"


def achar_clausulas(texto: str) -> list[dict]:
    """
    Onde estão as cláusulas, e em que estilo cada uma está escrita.

    Não normaliza nada: devolve o que está lá. Renumerar depois troca só o
    número, deixando acento, travessão e caixa como o documento os tem.
    """
    achadas: list[dict] = []

    for padrao, estilo in ((RE_NUMERO_ANTES, "antes"),
                           (RE_NUMERO_DEPOIS, "depois"),
                           (RE_EXTENSO, "extenso")):
        for m in padrao.finditer(texto or ""):
            if not _abre_o_bloco(texto, m.start()):
                continue
            if estilo == "extenso":
                plano = _sem_acento(m.group("extenso"))
                numero = _POR_EXTENSO_PLANO.index(plano) + 1 if plano in _POR_EXTENSO_PLANO else 0
            else:
                numero = int(m.group("numero"))
            achadas.append({
                "estilo": estilo,
                "numero": numero,
                "inicio": m.start(),
                "fim": m.end(),
                "texto": m.group(0),
            })

    # Um mesmo pedaço pode casar em dois padrões ("1ª CLÁUSULA 2" não existe,
    # mas sobreposição por erro de digitação, sim). Fica o primeiro.
    achadas.sort(key=lambda a: a["inicio"])
    limpas: list[dict] = []
    for a in achadas:
        if limpas and a["inicio"] < limpas[-1]["fim"]:
            continue
        limpas.append(a)
    return limpas


def estilo_do_documento(texto: str) -> str:
    """O estilo que o documento usa mais. Empate fica com o primeiro que apareceu."""
    achadas = achar_clausulas(texto)
    if not achadas:
        return ""
    contagem: dict[str, int] = {}
    for a in achadas:
        contagem[a["estilo"]] = contagem.get(a["estilo"], 0) + 1
    maior = max(contagem.values())
    for a in achadas:
        if contagem[a["estilo"]] == maior:
            return a["estilo"]
    return achadas[0]["estilo"]


# ------------------------------------------------------------- renumerar


def renumerar(texto: str, comecar_em: int = 1, seguir_referencias: bool = True) -> dict:
    """
    Põe as cláusulas em sequência — e leva as referências junto.

    Renumerar sem mexer nas referências cruzadas é metade do trabalho, e a
    metade que sobra é a que dá problema: a cláusula 7 que cita "a cláusula 4"
    quando a 4 virou 5. Cada troca sai na lista, porque renumerar contrato sem
    mostrar o que mudou é pedir para a pessoa aceitar no escuro.
    """
    achadas = achar_clausulas(texto)
    if not achadas:
        return {"texto": texto, "trocas": [], "referencias": [], "clausulas": 0}

    # De que número para que número cada cláusula foi. É esse mapa que as
    # referências seguem.
    de_para = {a["numero"]: ordem
               for ordem, a in enumerate(achadas, start=comecar_em)
               if a["numero"]}

    # Tudo o que vai ser reescrito, na ordem em que aparece: cláusulas e, se
    # pedido, as referências a elas. Um único passo, para as posições não se
    # deslocarem no meio do caminho.
    pedacos: list[dict] = []
    for ordem, a in enumerate(achadas, start=comecar_em):
        pedacos.append({**a, "novo": _escrever_clausula(a, ordem, texto),
                        "virou": ordem, "tipo": "clausula"})

    trocas_ref: list[dict] = []
    if seguir_referencias:
        for r in referencias(texto):
            destino = de_para.get(r["numero"])
            if not destino or destino == r["numero"]:
                continue
            novo = RE_REFERENCIA.sub(
                lambda m: m.group(0).replace(m.group("numero"), str(destino), 1),
                r["texto"], count=1)
            pedacos.append({"inicio": r["inicio"], "fim": r["inicio"] + len(r["texto"]),
                            "texto": r["texto"], "novo": novo,
                            "numero": r["numero"], "virou": destino, "tipo": "referencia"})

    pedacos.sort(key=lambda p: p["inicio"])

    trocas: list[dict] = []
    saida: list[str] = []
    fim_anterior = 0
    for p in pedacos:
        saida.append(texto[fim_anterior:p["inicio"]])
        saida.append(p["novo"])
        fim_anterior = p["fim"]
        if p["novo"] != p["texto"]:
            registro = {"de": p["texto"].strip(), "para": p["novo"].strip(),
                        "era": p["numero"], "virou": p["virou"], "tipo": p["tipo"]}
            trocas.append(registro)
            if p["tipo"] == "referencia":
                trocas_ref.append(registro)

    saida.append(texto[fim_anterior:])
    return {"texto": "".join(saida), "trocas": trocas,
            "referencias": trocas_ref, "clausulas": len(achadas)}


def _escrever_clausula(achada: dict, numero: int, texto: str) -> str:
    """Reescreve a marca da cláusula com o número novo, no estilo que ela tem."""
    bruto = achada["texto"]

    if achada["estilo"] == "extenso":
        m = RE_EXTENSO.match(bruto)
        if not m or numero > len(POR_EXTENSO):
            return bruto
        extenso = POR_EXTENSO[numero - 1]
        return m.group("palavra") + m.group("entre") + _mesma_caixa(m.group("extenso"), extenso)

    padrao = RE_NUMERO_ANTES if achada["estilo"] == "antes" else RE_NUMERO_DEPOIS
    m = padrao.match(bruto)
    if not m:
        return bruto

    if achada["estilo"] == "antes":
        return f"{numero}{m.group('ordinal')}{m.group('entre')}{m.group('palavra')}"
    return f"{m.group('palavra')}{m.group('entre')}{numero}{m.group('ordinal')}"


# --------------------------------------------------- referencias cruzadas


def referencias(texto: str) -> list[dict]:
    """
    As menções a "cláusula N" dentro do texto, e se elas apontam para algo.

    O contrato de nove cláusulas que diz "conforme cláusula 12" é um erro que
    passa despercebido na leitura e aparece na discussão.
    """
    numeros = {a["numero"] for a in achar_clausulas(texto) if a["numero"]}

    achadas: list[dict] = []
    for m in RE_REFERENCIA.finditer(texto or ""):
        # O título da cláusula abre o parágrafo; a referência mora no meio da
        # frase. É a mesma regra que separa os dois na hora de renumerar.
        if _abre_o_bloco(texto, m.start()):
            continue
        n = int(m.group("numero"))
        achadas.append({
            "numero": n,
            "texto": m.group(0),
            "inicio": m.start(),
            "existe": n in numeros,
        })
    return achadas


def referencias_quebradas(texto: str) -> list[dict]:
    """Só as que apontam para cláusula que não existe."""
    return [r for r in referencias(texto) if not r["existe"]]


# ------------------------------------------------ qualificação das partes


def qualificar(ficha: dict) -> str:
    """
    O parágrafo de qualificação de uma parte, com o que o cadastro tem.

    O que falta vira lacuna entre colchetes, e não uma invenção: "[ESTADO
    CIVIL]" num contrato é uma coisa que a pessoa preenche; um estado civil
    errado é outra bem diferente.
    """
    nome = str(ficha.get("nome", "")).strip() or "[NOME]"
    documento = str(ficha.get("documento", "")).strip()
    endereco = str(ficha.get("endereco", "")).strip()
    email = str(ficha.get("email", "")).strip()

    juridica = _e_cnpj(documento)
    partes = [nome.upper() if juridica else nome]

    if juridica:
        partes.append("pessoa jurídica de direito privado")
        partes.append(f"inscrita no CNPJ sob o nº {documento}" if documento
                      else "inscrita no CNPJ sob o nº [CNPJ]")
    else:
        partes.append("brasileiro(a)")
        partes.append("[ESTADO CIVIL]")
        partes.append("[PROFISSÃO]")
        partes.append(f"inscrito(a) no CPF sob o nº {documento}" if documento
                      else "inscrito(a) no CPF sob o nº [CPF]")

    partes.append(f"com endereço em {endereco}" if endereco
                  else "com endereço em [ENDEREÇO]")
    if email:
        partes.append(f"endereço eletrônico {email}")

    return ", ".join(partes) + "."


def _e_cnpj(documento: str) -> bool:
    return len(re.sub(r"\D", "", documento or "")) == 14


def o_que_falta(ficha: dict) -> list[str]:
    """
    O que o cadastro não tem e a qualificação vai deixar em branco.

    A tela mostra isso ANTES de inserir: é mais barato completar o cadastro do
    que caçar colchete dentro do contrato depois.
    """
    faltando = []
    if not str(ficha.get("documento", "")).strip():
        faltando.append("CPF ou CNPJ")
    if not str(ficha.get("endereco", "")).strip():
        faltando.append("endereço")
    if not _e_cnpj(str(ficha.get("documento", ""))):
        faltando += ["estado civil", "profissão"]
    return faltando
