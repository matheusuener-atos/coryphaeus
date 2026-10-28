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


def pares_respondidos(mensagens) -> list[tuple[str, str]]:
    """
    Todos os pares (pergunta, resposta) ja respondidos, do mais antigo ao mais
    novo. Resposta parada no meio nao entra: ela nao e o que o PAULUS
    respondeu, e o que ele tinha escrito ate ali.
    """
    achados: list[tuple[str, str]] = []
    lista = list(mensagens or [])
    i = len(lista) - 1
    while i >= 1:
        resposta, pergunta = lista[i], lista[i - 1]
        if (getattr(resposta, "autor", "") == "paulus" and getattr(pergunta, "autor", "") == "pessoa"
                and (getattr(resposta, "texto", "") or "").strip()
                and not getattr(resposta, "interrompida", False)):
            achados.append((pergunta.texto.strip(), resposta.texto.strip()))
            i -= 2
        else:
            i -= 1
    achados.reverse()
    return achados


def historico(mensagens, limite_tokens: int = LIMITE_TOKENS, pares: int = PARES, resumo: str = "") -> list[dict]:
    """
    Os ultimos `pares` pares (pessoa, paulus) ja respondidos, como mensagens
    do chat, cabendo em `limite_tokens`.

    `mensagens` sao as da conversa ANTES da pergunta de agora (objetos com
    `autor` e `texto`). `resumo` e o que ficou para tras dessas trocas (ver
    "o resumo da conversa longa", abaixo): vai na frente, como um par, fora
    da conta do limite - ele ja tem o teto dele.
    """
    achados = pares_respondidos(mensagens)[-pares:] if pares > 0 else []
    if not achados:
        return _com_resumo([], resumo)

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
    return _com_resumo(saida, resumo)


def _com_resumo(saida: list[dict], resumo: str) -> list[dict]:
    # Um par, como as outras mensagens: pergunta e resposta se alternam, e ha
    # modelo (e provedor da nuvem) que recusa duas falas seguidas da pessoa.
    if not resumo:
        return saida
    return [{"role": "user", "content": PEDIDO_DO_RESUMO}, {"role": "assistant", "content": resumo}] + saida


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


# O pedido de ação não é pergunta elíptica: "Abre o contrato que fizemos
# juntos nesta conversa aqui no editor" (caso real de 13/10/2026) virava "qual
# Abre o contrato que fizemos juntos no contrato aqui no editor conversa aqui
# no editor?" - o "nesta" trocado pelo sujeito da anterior. O verbo de comando
# na frente (depois só de gentileza ou abertura) diz que a frase é um pedido.
GENTILEZA = {
    "por", "favor", "pfv", "pls", "pode", "podes", "poderia", "consegue", "me", "voce", "vc", "que", "preciso",
    "quero", "gostaria", "de", "ai", "entao", "so", "ja", "agora", "ok", "certo", "sim", "isso", "mesmo", "eu",
    "beleza", "perfeito", "otimo", "bom", "oi", "ola", "paulus", "tambem", "agr", "la",
}
RE_COMANDO = re.compile(
    r"^(?:abr[ae]|abrir|crie|cria|criar|cadastr[ae]|cadastrar|agend[ae]|agendar|marqu?e|marca|anot[ae]|mand[ae]|"
    r"envi[ae]|enviar|redij[ao]|redigir|escrev[ae]|escrever|fa[cz]a|faz|fazer|ger[ae]|gerar|emit[ae]|mostr[ae]|"
    r"mostrar|exib[ae]|exibir|salv[ae]|salvar|lev[ae]|levar|coloqu?e|coloca|ponha|poe|assin[ae]|assinar|grav[ae]|"
    r"gravar|apagu?e|apaga|exclu[ai]|mov[ae]|organiz[ae]|traduz[a]?|traduzir|convert[ae]|resum[ae]|resumir|"
    r"revis[ae]|revisar|corrij[a]|corrig[ae]|troqu?e|troca|substitu[ai]|inclu[ai]|adicion[ae]|registr[ae]|"
    r"lembr[ae]|elabor[ae]|prepar[ae]|mont[ae]|copi[ae]|imprim[ae]|baix[ae]|compartilh[ae]|leia|ler|procur[ae]|"
    r"busqu?e|busca|encontr[ae]|list[ae]|explique|explica|calcul[ae]|compar[ae]|analis[ae]|verifiqu?e|"
    r"confir[ae]|confira|extrai[a]?|extraia|tire|tira|separ[ae]|junt[ae]|edit[ae]|editar|aplique|aplica|"
    r"atualiz[ae]|preench[ae]|imprimir|digitaliz[ae]|renome[ie]|arquiv[ae]|transcrev[ae]|dit[ae])$")


def pede_acao(pergunta: str) -> bool:
    """A frase começa (depois de gentileza) com um verbo de comando: é pedido, e não pergunta elíptica."""
    palavras = re.findall(r"[a-z0-9]+", _plano(pergunta))
    for palavra in palavras[:6]:
        if palavra in GENTILEZA:
            continue
        return bool(RE_COMANDO.match(palavra))
    return False


# Pergunta elíptica pelo pronome: curta, começando por interrogativo, sem um
# documento seu - "qual o valor dele?". Frase maior que isso já se sustenta.
MAX_PALAVRAS_PRONOME = 7
MAX_PALAVRAS_EMENDA = 10


def e_continuacao(pergunta: str) -> bool:
    """
    A pergunta é elíptica de verdade ("e o prazo?", "e dele?", "qual o valor
    dele?") e precisa do sujeito da anterior. Pedido de ação e frase completa
    por si não são: a memória não as reescreve.
    """
    plano = _plano(pergunta)
    if not plano or pede_acao(pergunta):
        return False
    palavras = plano.split()
    if RE_EMENDA.match(plano):
        return len(palavras) <= MAX_PALAVRAS_EMENDA and not tem_sujeito_proprio(pergunta)
    if len(palavras) > MAX_PALAVRAS_PRONOME or not (plano.startswith(INTERROGATIVOS) or palavras[0] == "e"):
        return False
    if any(re.sub(r"[^a-z]", "", p) in DOCUMENTOS for p in palavras):
        return False
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


# ----------------------------------------------- o resumo da conversa longa
#
# Os dois ultimos pares nao bastam numa conversa longa: o que foi combinado
# na terceira pergunta some na sexta. O resumo guarda o que saiu da janela, e
# nao custa uma chamada por pergunta (o motivo de nao haver resumo antes):
#
# - so e refeito quando um par SAI da janela, e em segundo plano, depois da
#   resposta - a pergunta de agora usa o resumo que ja existe e nao espera;
# - so pela nuvem (api._cliente_do_resumo): neste computador ele ocupava o
#   modelo de 10 a 30 s depois de cada resposta, e a pergunta seguinte
#   esperava. Sem a nuvem para os resumos, a conversa fica com os dois ultimos
#   pares, como antes;
# - e incremental: o resumo anterior mais os pares que sairam, nunca a
#   conversa inteira de novo;
# - nao inventa: resumo com numero que nao esta no texto de onde veio e
#   descartado (o modelo pequeno troca "10 dias" por uma data);
# - falhou, pula as 3 vezes seguintes antes de tentar de novo - modelo fora do
#   ar nao vira uma chamada perdida a cada pergunta.
#
# Ideia do Google AI Edge Gallery (SummarizationContextCompactor), com as
# regras daqui. Fica em `trabalho.contexto["resumo_conversa"]`.

PEDIDO_DO_RESUMO = "Antes destas últimas mensagens, sobre o que conversamos? (resumo, para contexto)"
RESUMO_MAX = 700          # caracteres: ~230 tokens, perto de um par da janela
PULAR_DEPOIS_DE_FALHA = 3
NOVOS_POR_VEZ = 10        # pares de uma vez; mais que isso, os mais velhos ficam so no resumo de antes
SISTEMA_DO_RESUMO = (
    "Você guarda a memória de uma conversa de um escritório de advocacia brasileiro. Escreva o resumo "
    "atualizado em português do Brasil, em até 110 palavras, em frases curtas, sem listas nem títulos. "
    "Guarde os documentos, pessoas e empresas citados, os números, valores, prazos e datas exatamente como "
    "aparecem, o que foi pedido, o que foi respondido e o que ficou pendente. Não acrescente nada que não "
    "esteja no texto e não dê opinião."
)
_RE_NUMERO = re.compile(r"\d[\d.,/]*")


def _marca(par: tuple[str, str]) -> str:
    """O que identifica um par: a conversa reaberta ou a resposta retomada mudam os pares."""
    pergunta, resposta = par
    return _plano(pergunta)[:80] + "|" + _plano(resposta)[:80]


def _estado_do_resumo(contexto: dict) -> dict:
    return contexto.get("resumo_conversa") or {}


def resumo_vigente(contexto: dict, pares: list[tuple[str, str]]) -> str:
    """O resumo guardado, se ainda descreve o comeco destes pares; "" se nao."""
    r = _estado_do_resumo(contexto)
    cobertos = int(r.get("pares") or 0)
    if not r.get("texto") or cobertos <= 0 or cobertos > len(pares):
        return ""
    if r.get("marca") != _marca(pares[cobertos - 1]):
        return ""
    return r["texto"]


def fora_da_janela(pares: list[tuple[str, str]], janela: int = PARES) -> int:
    return max(0, len(pares) - janela)


def precisa_resumir(contexto: dict, pares: list[tuple[str, str]], janela: int = PARES) -> bool:
    """Ha par fora da janela que o resumo ainda nao cobre (e nao estamos pulando por falha)."""
    fora = fora_da_janela(pares, janela)
    if fora == 0:
        return False
    r = _estado_do_resumo(contexto)
    if int(r.get("pular") or 0) > 0:
        return False
    cobertos = int(r.get("pares") or 0) if resumo_vigente(contexto, pares) else 0
    return cobertos < fora


def pedido_de_resumo(contexto: dict, pares: list[tuple[str, str]], janela: int = PARES) -> dict | None:
    """
    O que mandar ao modelo para cobrir os pares que sairam da janela: o
    resumo de antes (se ainda vale) e os pares novos. Devolve None quando nao
    ha o que resumir. `fonte` e o texto contra o qual o resultado e conferido.
    """
    fora = fora_da_janela(pares, janela)
    anterior = resumo_vigente(contexto, pares)
    cobertos = int(_estado_do_resumo(contexto).get("pares") or 0) if anterior else 0
    if cobertos >= fora:
        return None
    novos = pares[cobertos:fora][-NOVOS_POR_VEZ:]
    trocas = "\n\n".join(f"Pessoa: {_cortar(p, 400)}\nPAULUS: {_cortar(r, 900)}" for p, r in novos)
    partes = []
    if anterior:
        partes.append("RESUMO ATÉ AQUI:\n" + anterior)
    partes.append(("TROCAS QUE SE SEGUIRAM:\n" if anterior else "TROCAS:\n") + trocas)
    partes.append("Escreva o resumo atualizado da conversa inteira.")
    return {"sistema": SISTEMA_DO_RESUMO, "texto": "\n\n".join(partes), "fonte": anterior + "\n" + trocas,
            "pares": fora, "marca": _marca(pares[fora - 1])}


def _numeros(texto: str) -> set[str]:
    # "R$ 19.980,00" e "19.980" sao o mesmo numero: os centavos zerados saem.
    return {re.sub(r",0+$", "", n.rstrip(".,/")).replace(".", "").replace(",", "")
            for n in _RE_NUMERO.findall(texto or "")} - {""}


def aceitar_resumo(texto: str, fonte: str) -> str | None:
    """
    O resumo que o modelo escreveu, se der para confiar nele: sem numero que
    nao esteja na fonte, nao vazio, cortado no teto. None descarta.
    """
    texto = " ".join((texto or "").split())
    if len(texto) < 20:
        return None
    if _numeros(texto) - _numeros(fonte):
        return None
    return _cortar(texto, RESUMO_MAX)


def guardar_resumo(contexto: dict, pedido: dict, texto: str | None) -> bool:
    """Grava o resumo aceito, ou conta a falha (e o pulo). Devolve se gravou."""
    r = dict(_estado_do_resumo(contexto))
    if texto:
        contexto["resumo_conversa"] = {"texto": texto, "pares": pedido["pares"], "marca": pedido["marca"]}
        return True
    r["pular"] = PULAR_DEPOIS_DE_FALHA
    contexto["resumo_conversa"] = r
    return False


def contar_pergunta(contexto: dict) -> None:
    """Cada pergunta desconta um pulo da falha."""
    r = _estado_do_resumo(contexto)
    if int(r.get("pular") or 0) > 0:
        contexto["resumo_conversa"] = dict(r, pular=int(r["pular"]) - 1)


def resumir(contexto: dict, pares: list[tuple[str, str]], cliente, janela: int = PARES) -> bool:
    """
    Faz o resumo com `cliente` (ask(question, context, sistema=...)) e grava em
    `contexto`. Para o segundo plano: quem chama ja cedeu a vez as perguntas.
    """
    pedido = pedido_de_resumo(contexto, pares, janela)
    if pedido is None:
        return False
    try:
        bruto = cliente.ask(pedido["texto"], sistema=pedido["sistema"], tarefa="resumos")
    except Exception:  # noqa: BLE001 - modelo fora do ar: conta como falha, a conversa segue
        bruto = ""
    return guardar_resumo(contexto, pedido, aceitar_resumo(bruto, pedido["fonte"]))


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
    # O pedido de ação não deixa sujeito para a pergunta seguinte: "abra o
    # contrato aqui no editor" não é o assunto da conversa.
    if not continuou and not pede_acao(pergunta):
        novo = assunto_de(pergunta)
        if novo:
            contexto["assunto"] = list(novo)
    contexto["ultima_pergunta"] = efetiva
    contar_pergunta(contexto)
    resumo = resumo_vigente(contexto, pares_respondidos(anteriores))
    return efetiva, historico(anteriores, resumo=resumo), continuou


def escopo_anterior(mensagens) -> list[str]:
    """Os documentos a que a resposta anterior se restringiu - a continuacao herda."""
    for m in reversed(list(mensagens or [])):
        if getattr(m, "autor", "") == "paulus":
            return list((getattr(m, "cobertura", None) or {}).get("apenas") or [])
    return []
