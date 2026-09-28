"""
A memoria da conversa (I4): o que veio antes entra na pergunta de agora.

Ate aqui cada pergunta ia ao modelo so com a instrucao e o texto dela. "E a
multa?", depois de "qual o prazo do contrato ACME?", chegava como "e a
multa?" - e a busca procurava "multa" no acervo inteiro, e o modelo escolhia
um contrato qualquer. Duas pecas resolvem isso, e nenhuma usa o modelo:

- **a reescrita da continuacao, por regra, antes da busca.** A pergunta que
  comeca com "e o", "e a", "e no", "e quanto"..., ou que diz "ele", "dela",
  "nesse" sem sujeito proprio, herda o sujeito da anterior: "e a multa?" vira
  "qual a multa do contrato ACME?". E isso que a busca e o modelo leem; a
  conversa guarda o que a pessoa escreveu;
- **os dois ultimos pares pergunta/resposta** vao como mensagens anteriores,
  cortados em ~600 tokens no total. A resposta e cortada no fim de frase, sem
  resumo por modelo: resumir custaria uma chamada a cada pergunta.

Por que regra, e nao o modelo: reescrever com o modelo custaria uma leitura a
mais por pergunta (~10 s nesta maquina) e erraria de jeitos imprevisiveis. A
regra erra de jeito previsivel - e, quando nao reconhece a continuacao, a
pergunta segue como sempre foi.
"""

from __future__ import annotations

import re
import unicodedata

# Portugues com acento da perto de 3 caracteres por token neste modelo
# (habilidades/perguntar.py, medido).
CHARS_POR_TOKEN = 3
LIMITE_TOKENS = 600
PARES = 2


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


# ------------------------------------------------------------- historico

def _cortar(texto: str, limite: int) -> str:
    """O comeco do texto, terminando em fim de frase quando der."""
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    pedaco = texto[:limite]
    fim = max(pedaco.rfind(". "), pedaco.rfind("; "), pedaco.rfind("? "), pedaco.rfind("! "))
    if fim > limite // 2:
        return pedaco[:fim + 1] + " …"
    espaco = pedaco.rfind(" ")
    return (pedaco[:espaco] if espaco > limite // 2 else pedaco).rstrip(",;: ") + " …"


def historico(mensagens, limite_tokens: int = LIMITE_TOKENS, pares: int = PARES) -> list[dict]:
    """
    Os ultimos `pares` pares (pessoa, paulus) ja respondidos, como mensagens
    do chat, cabendo em `limite_tokens`.

    `mensagens` sao as da conversa ANTES da pergunta de agora (objetos com
    `autor` e `texto`). Resposta parada no meio nao entra: ela nao e o que o
    PAULUS respondeu, e o que ele tinha escrito ate ali.
    """
    achados: list[tuple[str, str]] = []
    lista = list(mensagens or [])
    i = len(lista) - 1
    while i >= 1 and len(achados) < pares:
        resposta, pergunta = lista[i], lista[i - 1]
        if (getattr(resposta, "autor", "") == "paulus" and getattr(pergunta, "autor", "") == "pessoa"
                and (getattr(resposta, "texto", "") or "").strip()
                and not getattr(resposta, "interrompida", False)):
            achados.append((pergunta.texto.strip(), resposta.texto.strip()))
            i -= 2
        else:
            i -= 1
    achados.reverse()
    if not achados:
        return []

    orcamento = limite_tokens * CHARS_POR_TOKEN
    # As perguntas vao inteiras (sao curtas: cortar a pergunta e perder o
    # assunto); o que sobra se divide entre as respostas.
    perguntas = [_cortar(p, orcamento // (2 * len(achados))) for p, _ in achados]
    sobra = max(0, orcamento - sum(len(p) for p in perguntas))
    por_resposta = sobra // len(achados)
    saida: list[dict] = []
    for pergunta, (_, resposta) in zip(perguntas, achados):
        saida.append({"role": "user", "content": pergunta})
        saida.append({"role": "assistant", "content": _cortar(resposta, max(40, por_resposta - 2))})
    # A conta final, com a margem das reticencias: o limite e o limite.
    while saida and sum(len(m["content"]) for m in saida) > orcamento:
        maior = max(range(1, len(saida), 2), key=lambda k: len(saida[k]["content"]))
        saida[maior]["content"] = _cortar(saida[maior]["content"], len(saida[maior]["content"]) - 40)
    return saida


def tokens(mensagens: list[dict]) -> int:
    return sum(len(m.get("content", "")) for m in mensagens) // CHARS_POR_TOKEN


# ------------------------------------------------------------- reescrita

# "e a multa?", "e quanto custa?", "e ate quando?" - o "e" que emenda na
# pergunta anterior.
RE_EMENDA = re.compile(r"^e\s+(o|a|os|as|no|na|nos|nas|do|da|quanto|quanta|qual|quais|quem|quando|"
                       r"ate|onde|como|se|sobre|em|para|pra|que|o que)\b")

# Os pronomes que apontam para o assunto da pergunta anterior, e a forma
# que o substituto toma em cada um.
PRONOMES = {
    "ele": "obj", "ela": "obj",
    "dele": "de", "dela": "de", "deste": "de", "desta": "de", "desse": "de", "dessa": "de", "disso": "de",
    "nele": "em", "nela": "em", "neste": "em", "nesta": "em", "nesse": "em", "nessa": "em", "nisso": "em",
}
RE_PRONOME = re.compile(r"\b(" + "|".join(PRONOMES) + r")\b", re.IGNORECASE)

# Os substantivos que nomeiam um documento ou o assunto de um: e deles que
# comeca o sujeito herdado. Com o genero, para o "do"/"da" do substituto.
DOCUMENTOS = {
    "contrato": "m", "aditivo": "m", "aluguel": "m", "processo": "m", "acordo": "m", "termo": "m",
    "distrato": "m", "recibo": "m", "parecer": "m", "mandado": "m", "recurso": "m",
    "locacao": "f", "procuracao": "f", "notificacao": "f", "peticao": "f", "acao": "f", "sentenca": "f",
    "reclamacao": "f", "decisao": "f", "contestacao": "f", "escritura": "f", "declaracao": "f",
}

# Perguntas que se viram sozinhas: sem o "qual" da frente, "a multa?" nao e
# pergunta para a busca nem para o modelo.
INTERROGATIVOS = ("qual", "quais", "quem", "quando", "quanto", "quanta", "quantos", "quantas", "como",
                  "onde", "o que", "ate", "por que", "em que", "que ")

_PALAVRA = r"[A-Za-zÀ-ÿ0-9ºª./-]+"


def _assunto(anterior: str) -> tuple[str, str] | None:
    """
    O sujeito da pergunta anterior: (sintagma, genero), com o sintagma sem
    artigo nem preposicao - "contrato de transporte da Cooperativa", "m".

    Primeiro um documento nomeado ("o aluguel da Clinica Bem Viver"); sem ele,
    uma pessoa ou empresa com nome proprio ("do Joao Batista").
    """
    texto = (anterior or "").strip().rstrip("?.! ")
    palavras = texto.split()
    planas = [_plano(p) for p in palavras]
    for i, plana in enumerate(planas):
        if plana in DOCUMENTOS:
            return " ".join(palavras[i:]), DOCUMENTOS[plana]
    m = re.search(r"\b(do|da|dos|das|de)\s+((?:[A-ZÀ-Ý]" + _PALAVRA + r"\s*)+(?:(?:de|da|do|dos|das|e|&)\s+"
                  r"(?:[A-ZÀ-Ý]" + _PALAVRA + r"\s*)+)*)", texto)
    if m:
        genero = {"do": "m", "dos": "m", "da": "f", "das": "f"}.get(m.group(1), "")
        return m.group(2).strip(), genero
    return None


def _com(forma: str, genero: str, sintagma: str) -> str:
    if forma == "obj":
        artigo = {"m": "o ", "f": "a "}.get(genero, "")
        return artigo + sintagma
    if forma == "em":
        return {"m": "no ", "f": "na "}.get(genero, "em ") + sintagma
    return {"m": "do ", "f": "da "}.get(genero, "de ") + sintagma


def tem_sujeito_proprio(pergunta: str) -> bool:
    """A pergunta nomeia alguem ou algo: um nome proprio depois da primeira palavra."""
    palavras = (pergunta or "").strip().split()[1:]
    return any(re.match(r"[A-ZÀ-Ý][a-zà-ÿ]", p) for p in palavras if _plano(p) not in ("e",))


def e_continuacao(pergunta: str) -> bool:
    plano = _plano(pergunta)
    if not plano:
        return False
    if RE_EMENDA.match(plano):
        return not tem_sujeito_proprio(pergunta)
    return bool(RE_PRONOME.search(pergunta)) and not tem_sujeito_proprio(pergunta)


def assunto_de(pergunta: str) -> tuple[str, str] | None:
    """O sujeito que uma pergunta deixa para a seguinte (ver `_assunto`)."""
    return _assunto(pergunta)


def reescrever(pergunta: str, anterior: str = "", assunto: tuple[str, str] | list | None = None) -> str:
    """
    A pergunta com o sujeito da anterior, quando ela e continuacao; senao, a
    propria pergunta, intacta.

        reescrever("e a multa?", "qual o prazo do contrato ACME?")
            -> "qual a multa do contrato ACME?"

    `assunto` e o sujeito ja herdado, guardado na conversa: numa sequencia de
    continuacoes ele passa adiante como estava, em vez de ser tirado de novo
    da pergunta ja reescrita - "e o locador dela?" depois de "e ate quando
    vai a locacao?" continua sendo sobre o aluguel da Clinica.
    """
    original = (pergunta or "").strip()
    if not e_continuacao(original):
        return original
    herdado = tuple(assunto) if assunto else (_assunto(anterior) if anterior else None)
    if not herdado:
        return original
    sintagma, genero = herdado
    if _plano(sintagma) in _plano(original):
        return original

    texto = original.rstrip("?.! ").strip()
    texto = re.sub(r"^[Ee]\s+", "", texto)
    plano = _plano(texto)
    if not plano.startswith(INTERROGATIVOS):
        plural = re.match(r"^(os|as)\b", plano)
        texto = ("quais " if plural else "qual ") + texto

    trocou = False

    def trocar(m: re.Match) -> str:
        nonlocal trocou
        trocou = True
        return _com(PRONOMES[m.group(1).lower()], genero, sintagma)

    texto = RE_PRONOME.sub(trocar, texto, count=1)
    if not trocou:
        texto = f"{texto} {_com('de', genero, sintagma)}"
    return texto + "?"


# ------------------------------------------------------------- a conversa

def preparar(mensagens, contexto: dict, pergunta: str) -> tuple[str, list[dict], bool]:
    """
    O que a conversa manda adiante: a pergunta efetiva (reescrita, quando e
    continuacao), o historico e se houve continuacao.

    `mensagens` sao as da conversa, com a pergunta de agora por ultimo;
    `contexto` e o `trabalho.contexto`, onde ficam a ultima pergunta efetiva e
    o assunto herdado - gravados aqui para a pergunta seguinte.
    """
    anteriores = list(mensagens or [])
    if anteriores and getattr(anteriores[-1], "autor", "") == "pessoa":
        anteriores = anteriores[:-1]
    efetiva = reescrever(pergunta, contexto.get("ultima_pergunta", ""), contexto.get("assunto"))
    continuou = efetiva != pergunta
    if not continuou:
        novo = assunto_de(pergunta)
        if novo:
            contexto["assunto"] = list(novo)
    contexto["ultima_pergunta"] = efetiva
    return efetiva, historico(anteriores), continuou


def escopo_anterior(mensagens) -> list[str]:
    """Os documentos a que a resposta anterior se restringiu - a continuacao herda."""
    for m in reversed(list(mensagens or [])):
        if getattr(m, "autor", "") == "paulus":
            return list((getattr(m, "cobertura", None) or {}).get("apenas") or [])
    return []
