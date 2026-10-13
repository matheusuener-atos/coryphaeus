"""
A conversa que continua do que acabou de ser dito (13/10/2026).

Caso real, conversa "Contrato Obedi Lourenço", com o contrato em PDF no
escopo e a nuvem respondendo (Llama 3.3 70B):

1. "O que você acha dele? Está bom assim?" -> resposta genérica e "a análise
   de um contrato deve ser feita por um profissional qualificado, como um
   advogado" - para um advogado. Depois, quatro melhorias sugeridas.
2. "Encontre partes no contrato que remetem a: <as 4>" -> "Cláusula 3ª,
   Parágrafo 1º", "Cláusula 10ª, Parágrafo 2º" - parágrafos que o contrato
   não tem (a conferência é src/citacoes.py, `conferir_clausulas`).
3. "Então vamos ajustar o que falta. Me pergunte aqui e eu te digo como será
   feito" -> resumiu as cláusulas de novo, como pergunta solta sobre o PDF:
   a memória (src/memoria.py) levava ~600 tokens dos dois últimos pares, e
   a lista das quatro melhorias chegava cortada; e nada no caminho sabia que
   "me pergunte" é pedir perguntas.

O que fica aqui, tudo por regra:

- **opinião** ("o que acha", "está bom", "revise", "analise criticamente"):
  a instrução de revisão como colega - riscos concretos, o que falta, base
  legal, sugestões aplicáveis - e a ressalva de leigo ("consulte um
  advogado") tirada da resposta, que é lida por advogado;
- **continuidade** ("o que falta", "esses pontos", "isso que você sugeriu",
  "faça isso"): a última resposta do Paulus inteira vai como objeto;
- **"me pergunte"**: os pontos da última resposta viram perguntas, uma por
  ponto, no cartão de perguntas que a redação já usa (js/92-entrevista.js);
  respondidas, o cartão "aplicar os ajustes" - nada gravado antes do sim. O
  sim abre o rascunho no editor (o trabalho redigido aqui, ou a cópia
  editável do documento do Acervo) e pede a mudança ao assistente do editor,
  que a deixa marcada para manter ou descartar.
"""

from __future__ import annotations

import re
import unicodedata
import uuid


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").lower().split())


# ------------------------------------------------------------ opinião

RE_OPINIAO = re.compile(
    r"\b(?:o que (?:voce|vc|tu) (?:acha|achou|pensa)|qual (?:a )?(?:sua|tua) (?:opiniao|avaliacao|visao|impressao)|"
    r"(?:esta|ficou|ta|esta ficando) (?:bom|boa|ok|adequad[oa]|complet[oa]|redondo|razoavel)|"
    r"(?:revise|revisa|revisar|analise|analisa|analisar|avalie|avalia|avaliar|critique|critica)\b.{0,40}"
    r"(?:critic\w*|a fundo|com rigor|o contrato|a minuta|a peca|o documento|dele|dela|isso|este|esse|esta|essa)|"
    r"(?:tem|ha|existe) (?:algum|alguma)? ?(?:problema|risco|falha|lacuna|erro)|pontos? (?:fracos?|de atencao)|"
    r"(?:pode|da para|poderia) melhorar|o que (?:falta|melhorar|mudar|ajustar)\b)")

INSTRUCAO_OPINIAO = """PEDIDO DE OPINIÃO OU REVISÃO
Quem pede é advogado(a) do escritório: responda como um colega revisor. Diga o que acha, com franqueza:
- os riscos concretos para o cliente do escritório, cláusula por cláusula quando couber;
- o que falta (cláusula, prazo, consequência, garantia) e o que está ambíguo;
- a base legal de cada ponto, com o dispositivo (o programa confere na base de leis);
- sugestões aplicáveis, já no texto que entraria no documento quando for curto.
Não mande procurar outro profissional do direito, não diga que a análise deve ser feita por outra \
pessoa e não dê garantia de resultado. Cite cláusula, parágrafo ou inciso só como estão no documento lido."""


def pede_opiniao(texto: str) -> bool:
    return bool(RE_OPINIAO.search(_plano(texto)))


# A ressalva de leigo ("consulte um advogado", "deve ser feita por um
# profissional qualificado"): quem lê é advogado. A frase inteira sai.
RE_RESSALVA_LEIGO = re.compile(
    r"(?:\b(?:consulte|procure|busque|contrate|recomenda-se consultar)\s+(?:sempre\s+)?(?:um|uma|o seu|seu)\s+"
    r"(?:advogad\w*|profissional|especialista)\b"
    r"|\b(?:recomend\w*|aconselh\w*|sugir\w*|importante|fundamental|essencial|necessari[oa]|indispensavel|prudente|"
    r"deve(?:m|ria)?|vale)\b[^.!?\n]{0,80}\b(?:consult\w*|procur\w*|busc\w*|revis\w*|analis\w*|feit[ao]s?\s+por|"
    r"orientac\w*|orient\w*|assessor\w*|acompanhament\w*|avaliad[ao]s?\s+por|avaliac\w*)\b[^.!?\n]{0,60}?"
    r"\b(?:um|uma|de um|de uma|por um|por uma|com um|com uma|do seu|de seu)\s+(?:advogad\w*|profissional|especialista)\b"
    r"|\b(?:recomend\w*|aconselh\w*|importante|fundamental|essencial|necessari[oa]|prudente)\b[^.!?\n]{0,40}\bque\s+"
    r"(?:um|uma|o|a|seu|sua)\s+(?:advogad\w*|profissional|especialista)\b[^.!?\n]{0,100}\b(?:revis\w*|analis\w*|"
    r"verifiqu\w*|avali\w*|examin\w*|orient\w*|confira|acompanh\w*|elabor\w*)"
    r"|\bnao (?:substitui|dispensa) (?:a )?(?:consulta|analise|orientacao|assessoria)\b)")


def sem_ressalva_de_leigo(texto: str) -> tuple[str, list[str]]:
    """(o texto sem as frases de "consulte um advogado", as frases tiradas)."""
    import citacoes

    if not texto or not RE_RESSALVA_LEIGO.search(_plano(texto)):
        return texto, []
    saida, tiradas = [], []
    for frase in citacoes._frases(texto):
        if frase.strip() and RE_RESSALVA_LEIGO.search(_plano(frase)):
            tiradas.append(" ".join(frase.split()))
            # A quebra de linha que a frase carregava fica: o parágrafo seguinte não cola.
            fim = frase[len(frase.rstrip()):]
            if "\n" in fim:
                saida.append(fim)
            continue
        saida.append(frase)
    limpo = re.sub(r"\n{3,}", "\n\n", "".join(saida)).strip()
    return (limpo or texto), (tiradas if limpo else [])


# ------------------------------------------------------------ continuidade

RE_REFERE_ANTERIOR = re.compile(
    r"\b(?:o que falta|o que faltou|o que voce (?:sugeriu|disse|apontou|falou|listou|propos)|"
    r"(?:esses|estes|aqueles|os) (?:pontos|itens|ajustes|problemas|riscos|topicos|sugestoes)|"
    r"(?:essas|estas|aquelas|as) (?:sugestoes|melhorias|mudancas|alteracoes|lacunas|observacoes|questoes)|"
    r"isso que (?:voce|vc) (?:sugeriu|disse|falou|apontou)|"
    r"(?:faca|faz|aplique|aplica|aplicar|implemente|implementa|ajuste|ajusta|corrija|corrige) (?:isso|isto|tudo|"
    r"o que (?:voce|vc) (?:sugeriu|disse|apontou)|as sugestoes|os ajustes|as melhorias|esses pontos|os pontos)|"
    r"vamos (?:ajustar|corrigir|resolver|aplicar|mexer)|(?:sobre|quanto a|quanto aos?) (?:isso|esses pontos|essas))\b")

RE_PEDE_PERGUNTAS = re.compile(
    r"(?:\b(?:me|mim)\s+(?:pergunte|pergunta|faca (?:as |umas |algumas )?perguntas|faz (?:as |umas )?perguntas)\b|"
    r"\bpergunte-me\b|\bpergunta-me\b|"
    r"\b(?:pode|podes|poderia) (?:me )?perguntar\b|"
    r"\b(?:faca|faz|faça) (?:as|umas|algumas|suas) perguntas\b|"
    r"\bpergunte (?:aqui|o que (?:precisar|falta|for preciso)|tudo|ponto a ponto|um por um|uma por uma)\b|"
    r"\bme pergunta(?:s)? (?:aqui|o que)\b)")

RE_PEDE_APLICAR = re.compile(
    r"^(?:(?:entao|ok|pode|beleza|certo|perfeito|otimo|sim|isso|agora|por favor)\W+)*"
    r"(?:aplique|aplica|implemente|implementa|faca|faz|inclua|inclui|coloque|coloca)\s+"
    r"(?:isso|isto|tudo|todas?|as sugestoes|os ajustes|as melhorias|esses pontos|os pontos|essas sugestoes|"
    r"o que (?:voce|vc) sugeriu|essas melhorias)(?:\s+(?:no|ao|na)\s+(?:contrato|documento|minuta|texto|editor))?"
    r"(?:\W+(?:por favor|agora|pra mim|para mim|ai))*\W*$")


def refere_a_anterior(texto: str) -> bool:
    return bool(RE_REFERE_ANTERIOR.search(_plano(texto)))


def pede_perguntas(texto: str) -> bool:
    return bool(RE_PEDE_PERGUNTAS.search(_plano(texto)))


def pede_aplicar(texto: str) -> bool:
    return bool(RE_PEDE_APLICAR.match(_plano(texto)))


INSTRUCAO_CONTINUIDADE = """CONTINUAÇÃO DA CONVERSA
A mensagem da pessoa se refere à SUA ÚLTIMA RESPOSTA (logo acima, no histórico): o objeto do pedido são os \
pontos dela. Trabalhe sobre esses pontos; não recomece do zero nem resuma o documento de novo."""


# ------------------------------------------------------------ os pontos da resposta

RE_ITEM = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+(.+?)\s*$")


def pontos_de(texto: str) -> list[str]:
    """
    Os itens de lista de uma resposta ("* Incluir uma cláusula...", "1. **Prazo
    de entrega**: ..."). Com o título em negrito, fica o título; sem, o item.
    """
    pontos: list[str] = []
    for linha in (texto or "").splitlines():
        m = RE_ITEM.match(linha)
        if not m:
            continue
        item = m.group(1)
        negrito = re.match(r"\*\*(.+?)\*\*\s*:?", item)
        if negrito:
            item = negrito.group(1)
        else:
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
        item = " ".join(item.replace("[sem fonte]", "").split()).strip(" :;")
        item = re.sub(r"\s*\[T\d{1,3}\]", "", item)
        if len(item) >= 8 and item not in pontos:
            pontos.append(item[:400])
    return pontos[:12]


def ultima_com_pontos(mensagens, quantas: int = 3):
    """A resposta mais recente do Paulus (entre as `quantas` últimas) que tem ao menos dois pontos em lista."""
    vistas = 0
    for m in reversed(list(mensagens or [])):
        if getattr(m, "autor", "") != "paulus" or not (getattr(m, "texto", "") or "").strip():
            continue
        if getattr(m, "interrompida", False):
            continue
        vistas += 1
        pontos = pontos_de(m.texto)
        if len(pontos) >= 2:
            return m, pontos
        if vistas >= quantas:
            break
    return None, []


def ultima_resposta(mensagens):
    for m in reversed(list(mensagens or [])):
        if getattr(m, "autor", "") == "paulus" and (getattr(m, "texto", "") or "").strip() \
                and not getattr(m, "interrompida", False):
            return m
    return None


# ------------------------------------------------------------ as perguntas

RE_VERBO_DO_PONTO = re.compile(
    r"^(?:incluir|inserir|acrescentar|adicionar|prever|criar|estabelecer|especificar|definir|detalhar|esclarecer|"
    r"fixar|determinar|indicar|regular|disciplinar|rever|revisar|ajustar|corrigir|completar|preencher)\s+", re.I)
RE_CLAUSULA_QUE = re.compile(
    r"^(?:uma|um|a|o)?\s*(?:clausula|cláusula|paragrafo|parágrafo|item|disposi[cç][aã]o|previs[aã]o|regra|mecanismo)"
    r"(?:\s+(?:especifica|pr[oó]pria|clara|expressa))?\s+(?:que\s+(?:especifique|estabele[cç]a|defina|preveja|trate|"
    r"regule|discipline|determine|fixe|indique|disponha(?:\s+sobre)?)|sobre|para|de|com)\s+", re.I)


def assunto_do_ponto(ponto: str) -> str:
    """"Incluir uma cláusula que especifique o prazo para a entrega..." -> "o prazo para a entrega..."."""
    texto = " ".join((ponto or "").split()).rstrip(".;:")
    texto = RE_VERBO_DO_PONTO.sub("", texto)
    texto = RE_CLAUSULA_QUE.sub("", texto)
    texto = re.sub(r"^(?:d[oa]s?|um|uma)\s+", "", texto)
    return texto or ponto


def perguntas_dos_pontos(pontos: list[str]) -> list[dict]:
    """Uma pergunta por ponto: como deve ficar, no texto do advogado. O porquê é o ponto sugerido."""
    saida = []
    for i, ponto in enumerate(pontos, 1):
        assunto = assunto_do_ponto(ponto)
        assunto = assunto[:1].upper() + assunto[1:]
        saida.append({"id": f"a{i}", "pergunta": f"{assunto}: como deve ficar?",
                      "porque": "Ponto apontado: " + ponto.rstrip(".") + ".", "tipo": "texto_longo", "opcoes": []})
    return saida


# ------------------------------------------------------------ o estado

def novo(pontos: list[str], alvo: dict, pedido: str) -> dict:
    return {"id": "aj" + uuid.uuid4().hex[:8], "status": "aberta", "pedido": " ".join((pedido or "").split())[:400],
            "pontos": list(pontos), "perguntas": perguntas_dos_pontos(pontos), "respostas": [], "explicacoes": [],
            "alvo": dict(alvo or {})}


def aberto(contexto: dict | None) -> dict | None:
    a = (contexto or {}).get("ajustes")
    return a if isinstance(a, dict) and a.get("status") == "aberta" else None


def respondido(contexto: dict | None, id_: str = "") -> dict | None:
    a = (contexto or {}).get("ajustes")
    if isinstance(a, dict) and a.get("status") == "respondida" and (not id_ or a.get("id") == id_):
        return a
    return None


RE_NUMERADA = re.compile(r"^\s*(?:ponto\s+)?(\d{1,2})\s*[.)\-–—:]\s*(.+)$", re.I)


def respostas_livres(texto: str, estado_a: dict) -> list[dict]:
    """
    A resposta escrita na caixa: "1. 30 dias, multa de 2%" vai para a pergunta
    1; sem número, com uma pergunta só, é dela. O resto vira explicação.
    """
    perguntas = estado_a.get("perguntas") or []
    saida, atual = [], None
    for linha in (texto or "").splitlines():
        m = RE_NUMERADA.match(linha)
        if m and 1 <= int(m.group(1)) <= len(perguntas):
            atual = {"id": perguntas[int(m.group(1)) - 1]["id"], "modo": "valor", "resposta": m.group(2).strip()}
            saida.append(atual)
        elif atual is not None and linha.strip():
            atual["resposta"] += " " + linha.strip()
    if not saida and len(perguntas) == 1 and (texto or "").strip():
        saida.append({"id": perguntas[0]["id"], "modo": "valor", "resposta": texto.strip()})
    return saida


def responde_ajustes(texto: str, estado_a: dict) -> bool:
    """A frase na caixa, com as perguntas abertas, é resposta a elas (e não outro assunto)?"""
    plano = _plano(texto)
    if not plano:
        return False
    if respostas_livres(texto, estado_a):
        return True
    return bool(re.match(r"^(?:decida|decide|pode decidir|siga|continue|pode seguir|aplique|aplica|faca|faz|"
                         r"no (?:primeiro|segundo|terceiro|quarto) ponto|sobre o (?:primeiro|segundo|prazo)|"
                         r"quanto (?:ao|a)|para o ponto|ponto \d)\b", plano))


def juntar(estado_a: dict, respostas: list[dict], explicacao: str = "", acao: str = "") -> None:
    """As respostas (do cartão ou da caixa) entram; "decidir" marca o que ficou sem resposta."""
    por_id = {q["id"]: q for q in estado_a.get("perguntas") or []}
    for r in respostas or []:
        q = por_id.get(str(r.get("id") or ""))
        if q is None:
            continue
        modo = str(r.get("modo") or "valor")
        valor = r.get("resposta")
        valor = ", ".join(str(x) for x in valor) if isinstance(valor, list) else str(valor or "").strip()
        if modo == "valor" and not valor:
            continue
        estado_a["respostas"] = [x for x in estado_a["respostas"] if x["id"] != q["id"]]
        estado_a["respostas"].append({"id": q["id"], "pergunta": q["pergunta"], "resposta": valor[:2000], "modo": modo})
    if (explicacao or "").strip():
        estado_a["explicacoes"].append(explicacao.strip()[:4000])
    if acao == "decidir":
        feitas = {r["id"] for r in estado_a["respostas"]}
        for q in estado_a.get("perguntas") or []:
            if q["id"] not in feitas:
                estado_a["respostas"].append({"id": q["id"], "pergunta": q["pergunta"], "resposta": "", "modo": "decida"})


def ajustes_definidos(estado_a: dict) -> list[dict]:
    """[{ponto, como}] na ordem das perguntas: o que foi respondido, ou "decida" / "sem resposta"."""
    por_id = {r["id"]: r for r in estado_a.get("respostas") or []}
    saida = []
    for q, ponto in zip(estado_a.get("perguntas") or [], estado_a.get("pontos") or []):
        r = por_id.get(q["id"])
        if r is None or r.get("modo") in ("nao_sei", "depois"):
            continue
        como = r["resposta"] if r.get("modo") == "valor" else ""
        saida.append({"ponto": ponto, "como": como, "decida": r.get("modo") == "decida"})
    return saida


def pedido_ao_editor(estado_a: dict) -> str:
    """O pedido que o assistente do editor recebe: cada ponto, e o que o advogado definiu para ele."""
    linhas = []
    for i, a in enumerate(ajustes_definidos(estado_a), 1):
        if a["decida"]:
            linhas.append(f"{i}. {a['ponto']} - o advogado pediu que você decida: adote a solução usual e mais segura "
                          "para o cliente do escritório, sem inventar valor, prazo ou nome (use [●] no que faltar).")
        else:
            linhas.append(f"{i}. {a['ponto']} - definido pelo advogado: {a['como']}")
    explicacoes = " ".join(estado_a.get("explicacoes") or [])
    return ("Ajuste o contrato com o que o advogado definiu, ponto por ponto. Onde já existe cláusula sobre o assunto, "
            "troque o trecho dela; onde não existe, acrescente a cláusula nova, com título no padrão do documento.\n"
            + "\n".join(linhas) + (f"\nObservações do advogado: {explicacoes}" if explicacoes else ""))


def proposta_das_perguntas(estado_a: dict, nivel_nome: str = "") -> dict:
    """O cartão de perguntas da redação (js/92-entrevista.js), com as perguntas dos ajustes."""
    alvo = estado_a.get("alvo") or {}
    return {"tipo": "entrevista", "titulo": "Ajustes no " + ("documento" if not alvo.get("nome") else "contrato"),
            "campos": {}, "porque": "", "falta": "", "pergunta": estado_a.get("pedido", ""),
            "entrevista_id": estado_a["id"], "rodada": 1, "rodadas_max": 1, "nivel": "", "nivel_nome": nivel_nome,
            "trabalho": "ajustes", "entendimento": "", "perguntas": estado_a["perguntas"], "premissas": [],
            "cadastros": [], "documentos": [], "ajustes": True}


def proposta_de_aplicar(estado_a: dict) -> dict:
    alvo = estado_a.get("alvo") or {}
    return {"tipo": "aplicar_ajustes", "titulo": alvo.get("titulo") or alvo.get("nome") or "o documento",
            "campos": {"ajustes_id": estado_a["id"]}, "porque": "você respondeu como cada ponto deve ficar",
            "ajustes": ajustes_definidos(estado_a), "alvo": alvo}
