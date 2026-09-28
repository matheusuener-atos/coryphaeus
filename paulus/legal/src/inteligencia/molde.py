"""
O nivel 0 sem modelo: a resposta montada por molde a partir dos fatos ja
conferidos, e a conferencia mecanica do que o modelo escreve quando o molde
nao cobre (I3).

Ate aqui o nivel 0 era texto livre do modelo sobre fatos verificados. Os
fatos estavam certos; a frase, nao necessariamente - um modelo de 3 bilhoes
de parametros copia "0001234-56.2024.8.14.0051" trocando um digito com a
mesma cara de certeza com que copia certo, e ninguem confere um CNJ lido na
tela. Para as perguntas de um dado so (numero do processo, valor, juizo,
partes, data de assinatura, leis citadas) a resposta e o proprio fato:
"O valor da causa e R$ 15.000,00 (p. 2)." Nao ha o que o modelo acrescente,
e ha o que ele pode estragar. Montada aqui, ela sai em milissegundos, sem
fila e sem erro de copia.

Onde o modelo continua (o que o molde nao cobre - varios valores num
documento, prazos, lista de pedidos, o resumo), a resposta passa pela
conferencia: todo numero, data, CNJ, CPF, CNPJ e valor em R$ que ela
escrever tem de estar nos fatos (ou na propria pergunta). Um que nao esteja
derruba a resposta inteira; quem chama usa o molde ou escala.
"""

from __future__ import annotations

import re
import unicodedata

from .roteador import Fato, Pacote

# As intencoes que o molde responde sozinho. (secao, chave); chave None =
# qualquer uma.
COBERTAS = {
    ("case", "case_number"),
    ("amounts", None),
    ("jurisdiction", "court"),
    ("parties", None),
    ("dates", "signature"),
    ("legal_references", None),
}

# Como o rotulo do valor vira sujeito da frase. Sem o artigo certo a frase
# soa traduzida ("O honorarios e") - e resposta que soa errada nao e lida
# como certa.
_SUJEITO_DO_VALOR = {
    "valor da causa": "O valor da causa é",
    "honorários": "Os honorários são de",
    "valor do contrato": "O valor do contrato é",
    "multa": "A multa é de",
    "aluguel": "O aluguel é de",
    "indenização": "A indenização é de",
    "dívida": "A dívida é de",
    "parcela": "A parcela é de",
}


def cobre(pacote: Pacote) -> bool:
    intencao = pacote.intencao
    return ((intencao.secao, intencao.chave) in COBERTAS
            or (intencao.secao, None) in COBERTAS)


def _onde(fato: Fato) -> str:
    """De onde saiu: a pagina, e sem ela o nome do documento."""
    if fato.pagina:
        return f" (p. {fato.pagina})"
    return f" ({fato.documento})" if fato.documento else ""


def _data_br(valor: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (valor or "").strip())
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else valor


# O que numa pergunta diz QUAL valor ela quer. "Qual o valor da multa?" num
# documento em que a regra so achou o aluguel tem um valor so - e ele nao e a
# resposta. Com uma destas palavras na pergunta, o molde so responde se o
# valor achado for daquele tipo; o resto vai para o modelo, que le.
_TIPO_NA_PERGUNTA = {
    "multa": "multa", "aluguel": "aluguel", "honorario": "honorários", "parcela": "parcela",
    "indeniza": "indenização", "divida": "dívida", "causa": "valor da causa",
}
_OUTRO_VALOR = re.compile(r"\b(juros|caucao|garantia|sinal|entrada|mensal|anual|reajust|desconto|"
                          r"aditivo|condomin|iptu|frete|comissao|salario|premio|franquia)")


_PAPEIS = (
    (r"\bautor(a|es)?\b|\brequerente|\bexequente|\breclamante", "autor"),
    (r"\bre(u|us)?\b|\brequerid|\bexecutad|\breclamad", "réu"),
    (r"\bcontratante", "contratante"), (r"\bcontratad", "contratado"),
    (r"\blocador", "locador"), (r"\blocatari", "locatário"),
    (r"\boutorgante", "outorgante"), (r"\boutorgad", "outorgado"),
    (r"\bvendedor", "vendedor"), (r"\bcomprador", "comprador"),
    (r"\bfiador", "fiador"), (r"\badvogad", "advogado"),
)


def _valor_e_o_pedido(pergunta: str, fato: Fato) -> bool:
    plano = _sem_acento(pergunta)
    if _OUTRO_VALOR.search(plano):
        return False
    pedidos = {rotulo for palavra, rotulo in _TIPO_NA_PERGUNTA.items() if palavra in plano}
    return not pedidos or fato.rotulo in pedidos


def montar(pacote: Pacote, pergunta: str = "") -> str:
    """
    A resposta por molde, ou vazio quando o molde nao responde com certeza.

    Vazio nao e erro: e o sinal de que a pergunta segue para o modelo (com a
    conferencia) ou escala. Os casos de vazio sao os de ambiguidade - dois
    valores num documento para "qual o valor?", duas datas de assinatura - em
    que escolher um seria sortear.
    """
    if pacote.fallback or pacote.inferencia or pacote.enumera or not pacote.fatos or not cobre(pacote):
        return ""
    fatos = pacote.fatos
    secao = pacote.intencao.secao
    um_documento = len({f.documento for f in fatos}) == 1

    if secao == "case":
        if len({f.valor for f in fatos}) != 1:
            return ""
        return f"O número do processo é {fatos[0].valor}{_onde(fatos[0])}."
    if secao == "jurisdiction":
        # O fato e o tribunal. "Qual a vara?" e "qual o foro?" (o foro de
        # eleicao de um contrato) pedem outra coisa - essas vao ao modelo.
        plano = _sem_acento(pergunta)
        if len({f.valor for f in fatos}) != 1 or not re.search(r"\b(tribunal|juizo)\b", plano) \
                or re.search(r"\b(vara|comarca|foro)\b", plano):
            return ""
        return f"O tribunal é {fatos[0].valor}{_onde(fatos[0])}."
    if secao == "amounts":
        if len(fatos) != 1 or not _valor_e_o_pedido(pergunta, fatos[0]):
            return ""
        f = fatos[0]
        sujeito = _SUJEITO_DO_VALOR.get(f.rotulo, f"O {f.rotulo} é" if f.rotulo else "O valor é")
        return f"{sujeito} {f.valor}{_onde(f)}."
    if secao == "dates":
        if len({f.valor for f in fatos}) != 1:
            return ""
        return f"O documento foi assinado em {_data_br(fatos[0].valor)}{_onde(fatos[0])}."
    if not um_documento:
        return ""
    if secao == "parties":
        # "Quem e o reu?" pede o reu, nao a lista de partes. Com um papel na
        # pergunta, so os fatos daquele papel - nenhum, e o molde nao responde.
        plano = _sem_acento(pergunta)
        papeis = {rotulo for padrao, rotulo in _PAPEIS if re.search(padrao, plano)}
        if papeis:
            fatos = [f for f in fatos if f.rotulo in papeis]
            if not fatos:
                return ""
        linhas = [f"- {f.rotulo[:1].upper() + f.rotulo[1:]}: {f.valor}{_onde(f)}" if f.rotulo
                  else f"- {f.valor}{_onde(f)}" for f in fatos]
        return f"As partes de {fatos[0].documento}:\n" + "\n".join(linhas)
    if secao == "legal_references":
        vistas = list(dict.fromkeys((f.valor, _onde(f)) for f in fatos))
        return (f"As referências normativas citadas em {fatos[0].documento}:\n"
                + "\n".join(f"- {valor}{onde}" for valor, onde in vistas))
    return ""


def lista(pacote: Pacote) -> str:
    """
    O molde de lista, para quando o modelo errou uma enumeracao: a lista e a
    propria resposta (os pedidos que constam, as decisoes como escritas).
    """
    if not pacote.enumera or not pacote.fatos:
        return ""
    return (f"Consta de {', '.join(pacote.documentos)}:\n"
            + "\n".join(f"- {f.valor}{_onde(f)}" for f in pacote.fatos))


# ------------------------------------------------------------ conferencia

_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
          "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}

_RE_DATA_BARRA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_RE_DATA_EXTENSO = re.compile(r"\b(\d{1,2})(?:º|o)?\s+de\s+(" + "|".join(_MESES) + r")\s+de\s+(\d{4})\b")
_RE_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# CNJ, CPF e CNPJ: a pontuacao nao importa, os digitos sim.
_RE_DOCUMENTO = re.compile(r"\b\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}\b"
                           r"|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
                           r"|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_RE_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                   if unicodedata.category(c) != "Mn")


def _numero(bruto: str) -> str:
    """
    O valor de um numero escrito a brasileira, como texto canonico:
    "18.500,00" e "18.500" e "18500" viram "18500"; "2,5" vira "2.5".
    """
    if "," in bruto:
        inteiro, _, fracao = bruto.rpartition(",")
        inteiro = inteiro.replace(".", "")
        fracao = fracao.rstrip("0")
        return inteiro.lstrip("0") + ("." + fracao if fracao else "") or "0"
    partes = bruto.split(".")
    if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
        return "".join(partes).lstrip("0") or "0"
    return bruto.lstrip("0") or "0"


def numeros_de(texto: str) -> set[str]:
    """Todo numero de um texto, ja no formato canonico - datas viram AAAA-MM-DD."""
    t = _sem_acento(texto)
    achados: set[str] = set()

    def trocar_data(dia, mes, ano) -> str:
        chave = f"{int(ano):04d}-{int(mes):02d}-{int(dia):02d}"
        achados.add(chave)
        return " "

    t = _RE_DATA_ISO.sub(lambda m: trocar_data(m.group(3), m.group(2), m.group(1)), t)
    t = _RE_DATA_BARRA.sub(lambda m: trocar_data(m.group(1), m.group(2), m.group(3)), t)
    t = _RE_DATA_EXTENSO.sub(lambda m: trocar_data(m.group(1), _MESES[m.group(2)], m.group(3)), t)

    def trocar_documento(m) -> str:
        achados.add("#" + re.sub(r"\D", "", m.group(0)))
        return " "

    t = _RE_DOCUMENTO.sub(trocar_documento, t)
    for m in _RE_NUMERO.finditer(t):
        achados.add(_numero(m.group(0).strip(".,")))
    return achados


def conferir(resposta: str, fatos: list[Fato], pergunta: str = "") -> list[str]:
    """
    Os numeros da resposta que NAO estao nos fatos. Lista vazia = passou.

    Vale para os fatos o valor, a citacao, o rotulo, o nome do documento e a
    pagina; e vale a pergunta ("a sala 402"). Um digito trocado num CNJ, num
    valor ou numa data aparece aqui.
    """
    permitidos: set[str] = set(numeros_de(pergunta))
    for f in fatos:
        permitidos |= numeros_de(" ".join(str(x) for x in (f.valor, f.quote, f.rotulo, f.documento) if x))
        if f.pagina:
            permitidos.add(str(f.pagina))
    return sorted(n for n in numeros_de(resposta) if n not in permitidos)
