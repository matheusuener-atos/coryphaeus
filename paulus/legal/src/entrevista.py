"""
A entrevista contextual: entender o trabalho antes de executar (03/10/2026).

    Primeiro entenda o trabalho. Depois descubra o que falta. Só então execute.

O pedido "preciso fazer um contrato de arrendamento rural" ia direto ao modelo
e voltava um modelo genérico; o advogado gastava as mensagens seguintes
dizendo "não é isso", "você nem perguntou". Aqui, antes de redigir, o modelo
da nuvem lê o pedido e decide uma de três coisas:

- o pedido está claro: executa (e diz, numa frase, o que vai fazer);
- falta pouco: poucas perguntas dirigidas;
- o pedido é complexo ou aberto: um módulo de definição mais completo.

**Não há formulário pronto.** O que é fixo são os componentes da tela
(escolha única, múltipla, texto, data, valor, parte, documento, sim/não) e as
saídas que valem para toda pergunta - "Não sei", "Decida por mim", "Quero
explicar", "Continuar com o que temos", "Responder depois". O conteúdo de cada
pergunta é do modelo, pedido a pedido, e cada uma traz o porquê: o que ela
muda no trabalho. Pergunta sem porquê não passa (`conferir`).

A entrevista pode ter rodadas: depois das respostas, uma nova análise pode
perceber uma consequência ("como haverá benfeitorias do arrendatário, como
ficam no fim do contrato?") e trazer só esse módulo. A profundidade
(src/profundidade.py) dá o teto de perguntas e de rodadas e a postura - o
Ministro procura o que o próprio advogado não percebeu; o Estagiário só
pergunta o que impede a tarefa.

O que é regra e fica em código: quem é pedido de trabalho (`e_trabalho`, sem
modelo - pergunta simples não ganha burocracia), a conferência do que o modelo
devolveu, o estado da entrevista na conversa e o texto que vai para a
elaboração (`briefing`).
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid

TIPOS = ("escolha", "multipla", "texto", "texto_longo", "data", "valor", "sim_nao", "parte", "documento")
# O que a tela já oferece em toda pergunta: o modelo não repete como opção.
_OPCOES_DA_TELA = re.compile(r"^(outr[oa]s?|outra coisa|nao sei|n[aã]o sei|decida por mim|quero explicar|"
                             r"prefiro explicar|depende|nenhum[a]?|n/?a)\b", re.IGNORECASE)


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------ é pedido de trabalho?

# As peças e os documentos que um escritório produz. "ação" entra com os verbos
# de propor ("entrar com uma ação de despejo").
_PECAS = (r"contrato|aditivo|distrato|peti[cç][aã]o|peticao|inicial|contesta[cç][aã]o|contestacao|r[eé]plica|replica|"
          r"recurso|apela[cç][aã]o|apelacao|agravo|embargos|contrarraz[oõ]es|contrarrazoes|raz[oõ]es|memoriais|"
          r"parecer|notifica[cç][aã]o|notificacao|procura[cç][aã]o|procuracao|substabelecimento|acordo|termo|"
          r"declara[cç][aã]o|declaracao|requerimento|mandado de seguran[cç]a|habeas corpus|queixa[- ]crime|"
          r"impugna[cç][aã]o|impugnacao|manifesta[cç][aã]o|manifestacao|of[ií]cio|oficio|estatuto|ata|"
          r"pol[ií]tica|politica|regimento|testamento|escritura|minuta|pe[cç]a|peca|defesa|a[cç][aã]o|acao|"
          r"exce[cç][aã]o|excecao|reclama[cç][aã]o trabalhista|reclamacao trabalhista|carta de cobran[cç]a|"
          r"due diligence|compliance|plano de partilha|partilha|invent[aá]rio|inventario|div[oó]rcio|divorcio")
_PRODUZIR = (r"elabor\w*|redi[gj]\w*|minut\w*|fa[cç]a|fazer|faz|fizesse|prepar\w*|mont[ae]\w*|cri[ae]r?|"
             r"escrev\w*|ger[ae]r?|preciso de|preciso|quero|gostaria de|gostaria|precisamos|vamos fazer|"
             r"ajuiz\w*|propor|entrar com|ingressar com|interpor|apresentar|me ajud\w* (?:a|com)")
_REVISAR = r"revis\w*|analis\w*|aprimor\w*|melhor[ae]\w*|adapt\w*|reescrev\w*|refa[cçz]\w*|aperfei[cç]o\w*"
RE_PRODUZIR = re.compile(r"\b(?:" + _PRODUZIR + r")\b(?:\W+\w+){0,5}?\W+(?:um|uma|o|a|os|as|novo|nova|meu|minha|"
                         r"nosso|nossa|este|esta|esse|essa)?\s*(?:" + _PECAS + r")\b", re.IGNORECASE)
RE_REVISAR = re.compile(r"\b(?:" + _REVISAR + r")\b(?:\W+\w+){0,4}?\W+(?:" + _PECAS + r")\b", re.IGNORECASE)
# Pergunta de informação ("qual o prazo do recurso?") não é trabalho a produzir.
RE_PERGUNTA = re.compile(r"^\s*(qual|quais|quando|onde|quanto|quantos|quantas|quem|como funciona|o que (?:é|e|diz|significa)|"
                         r"existe|h[aá] |tem |posso|pode|devo|explique|explica|me explique|o que)\b", re.IGNORECASE)
RE_SO_RESUMO = re.compile(r"\b(resum\w*|traduz\w*|tradu[cç]\w*)\b", re.IGNORECASE)
# "Quero saber o valor do contrato", "preciso ver a procuração": é consulta.
RE_CONSULTA = re.compile(r"\b(?:quero|gostaria(?: de)?|preciso(?: de)?|precisamos)\s+(?:de\s+)?(?:saber|ver|entender|"
                         r"conferir|consultar|verificar|confirmar|achar|encontrar|localizar|ler|abrir|mostrar|imprimir|"
                         r"assinar|enviar|mandar)\b", re.IGNORECASE)
# "Analise o contrato e me diga a multa": a análise é o caminho da pergunta.
RE_ANALISE_E_DIGA = re.compile(r"\be\s+(?:me\s+)?(?:diga|informe|responda|mostre|fale)\b", re.IGNORECASE)


def e_trabalho(pergunta: str) -> bool:
    """
    O pedido é de produzir ou retrabalhar uma peça (contrato, petição,
    parecer...)? Por regra, sem modelo: "Explique o art. 335" e "qual o valor
    do contrato?" seguem pelo caminho de sempre, sem entrevista nem etapas.
    """
    texto = " ".join(str(pergunta or "").split())
    if not texto or len(texto) > 4000:
        return False
    if RE_SO_RESUMO.search(texto) or RE_CONSULTA.search(texto):
        return False
    if RE_ANALISE_E_DIGA.search(texto) and not RE_PRODUZIR.search(texto):
        return False
    if RE_PERGUNTA.search(texto) and not re.search(r"^\s*(?:posso|pode|podes|poderia)\s+(?:voc[eê]\s+)?(?:" + _PRODUZIR + r")",
                                                   texto, re.IGNORECASE):
        return False
    return bool(RE_PRODUZIR.search(texto) or RE_REVISAR.search(texto))


# Durante uma entrevista aberta, o texto livre é resposta - a não ser que seja,
# claramente, outra coisa: outra pergunta de informação, ou outro trabalho.
def parece_outro_assunto(texto: str, pedido: str) -> bool:
    t = " ".join(str(texto or "").split())
    if not t:
        return False
    if RE_PERGUNTA.search(t) and t.rstrip().endswith("?") and len(t) > 25:
        return True
    if e_trabalho(t):
        pecas = lambda s: {m.group(0).lower() for m in re.finditer(_PECAS, _plano(s))}  # noqa: E731
        return not (pecas(t) & pecas(pedido))
    return False


# ------------------------------------------------------------ a instrução

INSTRUCAO = """Você é o PAULUS, assistente jurídico de um escritório de advocacia brasileiro. Hoje é {hoje}.
Um advogado do escritório fez um pedido de TRABALHO (elaborar, revisar ou adaptar uma peça). Antes de \
executar, você decide se já entende o trabalho o bastante para fazê-lo bem - como um advogado sênior faria \
ao receber a tarefa de um colega.

PRINCÍPIO: primeiro entenda o trabalho; depois descubra o que falta; só então execute.

COMO PENSAR (preencha "analise" antes de tudo)
1. Que trabalho é este, exatamente, e o que define a estrutura dele no direito brasileiro (a lei que o rege, \
as escolhas que mudam o texto).
2. O que o pedido e as respostas já definem.
3. O que falta e DECIDE o trabalho - a resposta mudaria a estrutura, as cláusulas, as teses, a estratégia \
ou os riscos. Só isso vira pergunta. O resto vira premissa declarada ou campo [●].

DECISÃO
- "executar": o que se sabe basta para um trabalho de qualidade neste nível. Pedido que diz "simples", \
ou que já traz o essencial, executa.
- "perguntar": falta algo que decide o trabalho. Falta pouco: poucas perguntas. Pedido aberto ou \
complexo: um módulo mais completo. Prefira de 2 a 4 perguntas; mais, só se cada uma for decisiva.

NÍVEL DE PROFUNDIDADE ESCOLHIDO: {nivel}. {postura}
No máximo {maximo} perguntas nesta rodada (rodada {rodada} de no máximo {rodadas}). Profundidade é \
inteligência na escolha das perguntas, não quantidade.

NUNCA PERGUNTE
- Qualificação: nome, CPF, CNPJ, RG, endereço, estado civil, profissão, nacionalidade, nome do cônjuge, \
telefone. Isso fica [●] no documento para o advogado preencher.
- O que o próprio pedido já diz, ou o que a definição do instituto já resolve (por exemplo, "o motivo" de \
uma denúncia vazia: denúncia vazia é justamente sem motivo).
- Pergunta vaga ("há outros termos?", "algo mais?").

BOA PERGUNTA (exemplo de outro tipo de trabalho, só para mostrar o padrão)
Pedido: "contrato de locação comercial". Boa: "O escritório representa o locador ou o locatário?" - \
porque: "define a quem as cláusulas de garantia, multa e renovação devem proteger". Boa: "Haverá direito \
à renovação compulsória (Lei 8.245/91, art. 51)?" - porque: "com ele, o contrato precisa de prazo mínimo \
de 5 anos e de cláusulas de luvas e reajuste próprias". Ruim: "Qual o nome do locatário?" (qualificação). \
Ruim: "Qual o tipo de contrato?" (o pedido já diz).

REGRAS DAS PERGUNTAS
- "porque": o que muda NO TEXTO conforme a resposta, concreto (a cláusula, a tese, o dispositivo legal). \
Nada de "isso muda as cláusulas" genérico.
- "impede": true só se, sem a resposta, o trabalho não pode ser feito de jeito nenhum.
- "impacto": "alto" (muda a estrutura ou a estratégia), "medio" (muda cláusulas ou argumentos \
relevantes) ou "baixo" (ajuste fino - melhor virar premissa).
- Opções concretas, deste caso, corretas juridicamente, curtas (até 8 palavras), de 2 a 6. NÃO inclua \
"Outro", "Não sei", "Decida por mim" nem "Quero explicar": a tela já oferece em toda pergunta.
- "sugestao": a opção que você recomendaria, se houver uma claramente melhor (copiada de "opcoes").
- tipo: "escolha" (uma opção), "multipla" (várias - por exemplo, situações especiais a prever), "texto" \
(curto), "texto_longo", "data", "valor" (em reais), "sim_nao", "parte" (uma pessoa ou empresa), \
"documento" (um documento do Acervo do escritório).
- Linguagem de colega, não de formulário.
- Nas rodadas seguintes, só o que as respostas fizeram surgir (consequências, pontos novos). Resposta "não \
sei" num ponto decisivo: pode perguntar de novo UMA vez, explicando em "porque" a consequência de cada \
caminho e oferecendo as alternativas como opções. "Decida por mim": escolha a melhor solução e registre em \
premissas.

"premissas": o que você vai assumir sem perguntar (até 5, curtas e concretas), para o advogado poder \
corrigir. Inclua as escolhas feitas por "decida por mim".
"abertura": uma ou duas frases suas, naturais, ao advogado, que digam o que você percebeu deste pedido \
(por exemplo, quais pontos mudam o trabalho e por quê). Não use fórmula pronta. Para executar, diga em uma \
frase como vai estruturar o trabalho.
"titulo": o título do módulo de perguntas, curto e deste trabalho.
"trabalho": o que será produzido, em poucas palavras (por exemplo: "contrato de locação comercial").
"entendimento": uma frase com o que você entendeu do pedido.
"outro_assunto": true só quando a MENSAGEM NOVA não é sobre este trabalho.

Responda só com um objeto JSON, nesta ordem:
{{"analise": {{"trabalho_e_regime": "...", "ja_definido": ["..."], "decisivo_faltando": ["..."]}}, \
"decisao": "perguntar", "trabalho": "...", "entendimento": "...", "abertura": "...", "titulo": "...", \
"perguntas": [{{"id": "lado", "pergunta": "...", "porque": "...", "impede": false, "impacto": "alto", \
"tipo": "escolha", "opcoes": ["...", "..."], "sugestao": ""}}], "premissas": ["..."], "outro_assunto": false}}"""


# Qualificação não é pergunta (vira [●]); o modelo às vezes pergunta mesmo
# assim, e a regra tira. "Quem o escritório representa?" fica: não é dado de
# cadastro, é a estratégia.
RE_QUALIFICACAO = re.compile(
    r"^\s*(?:qual|quais)\s+(?:é|e|são|sao)?\s*(?:o|a|os|as)?\s*(?:nome|nomes|cpf|cnpj|rg|endere[cç]o|estado civil|"
    r"profiss[aã]o|nacionalidade|data de nascimento|telefone|e-?mail|qualifica[cç][aã]o)\b"
    r"|^\s*quem\s+(?:é|e|são|sao|será|sera|serão|serao)\s+(?:o|a|os|as)\s+(?:parte|partes|arrendador|arrendat\w*|"
    r"locador|locat\w*|autor|r[eé]u|outorgante|outorgado|contratante|contratad\w*|comprador|vendedor|"
    r"notificad\w*|notificante|c[oô]njuge)",
    re.IGNORECASE)
# Pergunta vaga não decide nada: "há outros termos?", "há cláusulas
# adicionais que deseja incluir?", "algo mais?". A regra tira.
RE_VAGA = re.compile(
    r"^\s*(?:h[aá]|existe[m]?|tem|deseja|gostaria|quer)\s+(?:de\s+)?(?:incluir\s+)?(?:alg[uo]m[a]?|outr[oa]s?|mais)\s+"
    r"(?:\w+\s+){0,2}?(?:cl[aá]usulas?|termos?|condi[cç](?:[aã]o|[oõ]es)|obriga[cç](?:[aã]o|[oõ]es)|interesses?|"
    r"detalhes?|pontos?|informa[cç](?:[aã]o|[oõ]es)|observa[cç](?:[aã]o|[oõ]es)|particularidades?|"
    r"especificidades?|coisa)"
    r"|^\s*(?:algo|alguma coisa)\s+mais\b"
    r"|^\s*(?:h[aá]|existe[m]?|tem|deseja|gostaria|quer)\b.{0,40}\b(?:adicionais|extras?)\b",
    re.IGNORECASE)

# O raciocínio antes das perguntas, em texto livre (Advogado para cima): é o
# "esforço de raciocínio" da entrevista. Medido em 03/10/2026 com o Llama 3.3
# 70B e o Qwen 2.5 72B: com o raciocínio só dentro do JSON, as perguntas
# saíam genéricas ("há cláusulas adicionais?") e pediam qualificação. Escrito
# antes, ele lembra o regime jurídico e as escolhas típicas do tipo de
# trabalho, e as perguntas saem dele. A análise também vai para a elaboração.
SEPARADOR = "###JSON###"
# Só no Juiz e no Ministro: a análise escrita antes dobrou a espera pela
# nuvem (de ~40 s para ~80 s na medida de 03/10). No Advogado, o padrão, o
# raciocínio fica no campo "analise" do JSON.
ANALISE_LIVRE = {
    "juiz": (260, " (e) as premissas do pedido que merecem ser questionadas, as ambiguidades e as consequências de "
                  "cada leitura;"),
    "ministro": (340, " (e) as premissas do pedido que merecem ser questionadas, as ambiguidades e as consequências de "
                      "cada leitura; (f) as interpretações divergentes (doutrina e jurisprudência), os riscos e o que "
                      "costuma gerar litígio neste tipo de trabalho - inclusive o que o advogado talvez não tenha "
                      "percebido;"),
}
INSTRUCAO_ANALISE = """

ANTES DO JSON: escreva primeiro a sua ANÁLISE, em texto livre, até {palavras} palavras, como advogado \
sênior especialista na matéria: (a) o regime jurídico e as leis que regem este trabalho; (b) os elementos \
essenciais e as escolhas estruturais típicas deste tipo de trabalho - o que, na prática, muda o texto de um \
caso para outro; (c) o que o pedido e as respostas já definem; (d) o que falta e decide o trabalho, em ordem \
de importância;{extra} Depois, numa linha só, escreva {separador} e, logo abaixo, o objeto JSON. As perguntas \
saem da sua análise."""


def instrucao(nivel, rodada: int, dia=None) -> str:
    import instrucao_nuvem

    texto = INSTRUCAO.format(hoje=instrucao_nuvem.hoje_por_extenso(dia), nivel=nivel.nome, postura=nivel.postura,
                             maximo=nivel.perguntas_max, rodada=rodada, rodadas=nivel.rodadas_max)
    if nivel.id in ANALISE_LIVRE:
        palavras, extra = ANALISE_LIVRE[nivel.id]
        texto = texto.replace("Responda só com um objeto JSON, nesta ordem:", "O objeto JSON, nesta ordem:")
        texto += INSTRUCAO_ANALISE.format(palavras=palavras, extra=extra, separador=SEPARADOR)
    return texto


def separar_analise(bruto: str) -> tuple[str, str]:
    """(análise em texto livre, o resto com o JSON). Sem o separador, a análise é o que vem antes do primeiro "{"."""
    bruto = str(bruto or "")
    if SEPARADOR in bruto:
        antes, depois = bruto.split(SEPARADOR, 1)
        return antes.strip(), depois
    ini = bruto.find("{")
    return (bruto[:ini].strip(), bruto[ini:]) if ini > 0 else ("", bruto)


def _bloco_respostas(estado_e: dict) -> str:
    linhas = []
    for r in estado_e.get("respostas") or []:
        linhas.append(f"- {r.get('pergunta', '')}: {texto_da_resposta(r)}")
    for e in estado_e.get("explicacoes") or []:
        linhas.append(f"- (nas palavras do advogado) {e}")
    return "\n".join(linhas)


def montar_mensagens(estado_e: dict, nivel, documentos=(), historico=None, mensagem_nova: str = "",
                     dia=None) -> list[dict]:
    """As mensagens da avaliação: a instrução, e o pedido com tudo o que já se sabe."""
    partes = [f"PEDIDO: {estado_e.get('pedido', '')}"]
    antes = ""
    for m in (historico or [])[-4:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            antes += ("Advogado: " if m["role"] == "user" else "PAULUS: ") + m["content"][:700] + "\n"
    if antes:
        partes.insert(0, "CONVERSA ANTERIOR (contexto):\n" + antes.strip())
    for nome, texto in documentos or []:
        partes.append(f"DOCUMENTO ANEXADO «{nome}» (começo):\n{texto[:6000]}")
    respostas = _bloco_respostas(estado_e)
    if respostas:
        partes.append("JÁ RESPONDIDO:\n" + respostas)
    if estado_e.get("premissas"):
        partes.append("PREMISSAS QUE VOCÊ JÁ DECLAROU:\n" + "\n".join("- " + p for p in estado_e["premissas"]))
    if mensagem_nova:
        partes.append("MENSAGEM NOVA DO ADVOGADO: " + mensagem_nova)
    rodada = int(estado_e.get("rodada") or 0) + 1
    return [{"role": "system", "content": instrucao(nivel, rodada, dia)},
            {"role": "user", "content": "\n\n".join(partes)}]


# ------------------------------------------------------------ a conferência

def _ler_json(bruto: str) -> dict | None:
    try:
        dados = json.loads(bruto)
    except (ValueError, TypeError):
        ini, fim = str(bruto or "").find("{"), str(bruto or "").rfind("}")
        if ini == -1 or fim <= ini:
            return None
        try:
            dados = json.loads(bruto[ini:fim + 1])
        except ValueError:
            return None
    return dados if isinstance(dados, dict) else None


def _curto(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n].strip()


def conferir(dados: dict | None, nivel, rodada: int, ja_perguntadas=()) -> dict:
    """
    O que o modelo devolveu, só com o que a tela sabe mostrar: tipo conhecido,
    pergunta com porquê, opções curtas sem as que a tela já oferece, até o teto
    do nível, sem repetir pergunta de rodada anterior. Passou do número de
    rodadas, ou não sobrou pergunta: executar.

    O que cada nível aceita é regra daqui, e não só da instrução: o
    Estagiário só pergunta o que IMPEDE o trabalho; o Bacharel, o que impede ou
    tem impacto alto; do Advogado para cima, impacto alto ou médio - o de
    impacto baixo vira premissa. Qualificação (nome, CPF, endereço...) nunca
    é pergunta: vira [●] no documento.
    """
    dados = dados or {}
    vistas = {_plano(p) for p in ja_perguntadas}
    perguntas = []
    ids = set()
    for i, q in enumerate(dados.get("perguntas") or []):
        if not isinstance(q, dict):
            continue
        texto = _curto(q.get("pergunta"), 220)
        porque = _curto(q.get("porque"), 260)
        if (len(texto) < 4 or not porque or _plano(texto) in vistas or RE_QUALIFICACAO.search(texto)
                or RE_VAGA.search(texto)):
            continue
        impede = q.get("impede") is True or str(q.get("impede")).lower() == "true"
        impacto = str(q.get("impacto") or "medio").strip().lower()
        impacto = "alto" if impacto.startswith("alt") else "baixo" if impacto.startswith("baix") else "medio"
        if nivel.id == "estagiario" and not impede:
            continue
        if nivel.id == "bacharel" and not (impede or impacto == "alto"):
            continue
        if impacto == "baixo" and not impede:
            continue
        tipo = str(q.get("tipo") or "texto").strip().lower()
        tipo = {"unica": "escolha", "single": "escolha", "multiple": "multipla", "multipla_escolha": "multipla",
                "boolean": "sim_nao", "sim/nao": "sim_nao", "longo": "texto_longo", "dinheiro": "valor",
                "pessoa": "parte"}.get(tipo, tipo)
        if tipo not in TIPOS:
            tipo = "texto"
        opcoes = []
        for o in q.get("opcoes") or []:
            o = _curto(o, 80)
            if o and not _OPCOES_DA_TELA.match(_plano(o)) and o not in opcoes:
                opcoes.append(o)
        if tipo == "sim_nao":
            tipo, opcoes = "escolha", ["Sim", "Não"]
        if tipo in ("escolha", "multipla") and len(opcoes) < 2:
            tipo, opcoes = "texto", []
        if tipo not in ("escolha", "multipla"):
            opcoes = []
        sugestao = _curto(q.get("sugestao"), 80)
        if sugestao not in opcoes:
            sugestao = ""
        qid = re.sub(r"[^a-z0-9_]+", "_", _plano(q.get("id") or ""))[:30].strip("_") or f"p{i + 1}"
        qid = f"r{rodada}_{qid}"
        while qid in ids:
            qid += "_"
        ids.add(qid)
        perguntas.append({"id": qid, "pergunta": texto, "porque": porque, "tipo": tipo, "opcoes": opcoes[:6],
                          "sugestao": sugestao})
        vistas.add(_plano(texto))
        if len(perguntas) >= nivel.perguntas_max:
            break
    decisao = str(dados.get("decisao") or "").strip().lower()
    decisao = "perguntar" if decisao.startswith("pergunt") else "executar"
    if not perguntas or rodada > nivel.rodadas_max:
        decisao = "executar"
    if decisao == "executar":
        perguntas = []
    return {
        "decisao": decisao,
        "trabalho": _curto(dados.get("trabalho"), 90),
        "entendimento": _curto(dados.get("entendimento"), 400),
        "abertura": _curto(dados.get("abertura"), 400),
        "titulo": _curto(dados.get("titulo"), 80),
        "perguntas": perguntas,
        "premissas": [_curto(p, 200) for p in (dados.get("premissas") or []) if _curto(p, 200)][:5],
        "outro_assunto": bool(dados.get("outro_assunto")),
    }


# ------------------------------------------------------------ o estado na conversa

def novo_estado(pedido: str, nivel_id: str, documentos=()) -> dict:
    return {"id": uuid.uuid4().hex[:10], "pedido": " ".join(str(pedido or "").split()), "nivel": nivel_id,
            "rodada": 0, "status": "aberta", "trabalho": "", "entendimento": "", "premissas": [],
            "perguntas": [], "respostas": [], "explicacoes": [], "anexos": list(documentos or []),
            "perguntadas": []}


def aberta(contexto: dict | None) -> dict | None:
    e = (contexto or {}).get("entrevista")
    return e if isinstance(e, dict) and e.get("status") == "aberta" else None


MODOS = {"valor": "", "nao_sei": "não sei", "decida": "decida por mim", "depois": "respondo depois"}


def texto_da_resposta(r: dict) -> str:
    modo = r.get("modo") or "valor"
    if modo == "valor":
        v = r.get("resposta")
        if isinstance(v, list):
            return ", ".join(str(x) for x in v if str(x).strip()) or "(sem resposta)"
        return str(v or "").strip() or "(sem resposta)"
    return MODOS.get(modo, modo)


def juntar_respostas(estado_e: dict, respostas: list[dict], explicacao: str = "") -> None:
    """As respostas que vieram da tela, conferidas contra as perguntas da rodada."""
    por_id = {q["id"]: q for q in estado_e.get("perguntas") or []}
    for r in respostas or []:
        q = por_id.get(str(r.get("id") or ""))
        if q is None:
            continue
        modo = str(r.get("modo") or "valor")
        if modo not in MODOS:
            modo = "valor"
        valor = r.get("resposta")
        if isinstance(valor, list):
            valor = [_curto(x, 200) for x in valor if _curto(x, 200)][:12]
            if not valor and modo == "valor":
                continue
        else:
            valor = str(valor or "").strip()[:2000]
            if not valor and modo == "valor":
                continue
        estado_e["respostas"].append({"id": q["id"], "pergunta": q["pergunta"], "resposta": valor, "modo": modo})
    explicacao = str(explicacao or "").strip()
    if explicacao:
        estado_e["explicacoes"].append(explicacao[:4000])


def resumo_para_conversa(estado_e: dict, respostas: list[dict], explicacao: str = "", acao: str = "") -> str:
    """A mensagem da pessoa na conversa, legível: o que ela respondeu nesta rodada."""
    por_id = {q["id"]: q for q in estado_e.get("perguntas") or []}
    linhas = []
    for r in respostas or []:
        q = por_id.get(str(r.get("id") or ""))
        if q is None:
            continue
        t = texto_da_resposta({"resposta": r.get("resposta"), "modo": r.get("modo") or "valor"})
        if t != "(sem resposta)":
            linhas.append(f"{q['pergunta']} — {t}")
    if explicacao.strip():
        linhas.append(explicacao.strip())
    if acao == "continuar":
        linhas.append("Pode continuar com o que temos.")
    elif acao == "decidir":
        linhas.append("Decida por mim o que faltar.")
    return "\n".join(linhas) or "Pode continuar com o que temos."


def proposta(estado_e: dict, avaliacao: dict, nivel, cadastros=(), documentos=()) -> dict:
    """O cartão do módulo de perguntas (js/92-entrevista.js)."""
    return {
        "tipo": "entrevista", "titulo": avaliacao.get("titulo") or "Antes de começar",
        "campos": {}, "porque": "", "falta": "", "pergunta": estado_e.get("pedido", ""),
        "entrevista_id": estado_e["id"], "rodada": estado_e["rodada"], "rodadas_max": nivel.rodadas_max,
        "nivel": nivel.id, "nivel_nome": nivel.nome, "trabalho": avaliacao.get("trabalho") or estado_e.get("trabalho", ""),
        "entendimento": avaliacao.get("entendimento", ""), "perguntas": avaliacao["perguntas"],
        "premissas": avaliacao.get("premissas") or [],
        # Para os campos "parte" e "documento": os nomes que a pessoa já tem.
        "cadastros": list(cadastros or [])[:80], "documentos": list(documentos or [])[:80],
    }


def briefing(estado_e: dict) -> str:
    """O que a elaboração recebe além do pedido: o entendido, as respostas, as premissas, as explicações."""
    partes = []
    if estado_e.get("trabalho"):
        partes.append("TRABALHO: " + estado_e["trabalho"])
    if estado_e.get("entendimento"):
        partes.append("ENTENDIMENTO: " + estado_e["entendimento"])
    respostas = _bloco_respostas(estado_e)
    if respostas:
        partes.append("DEFINIDO COM O ADVOGADO:\n" + respostas)
    decida = [r["pergunta"] for r in estado_e.get("respostas") or [] if r.get("modo") == "decida"]
    nao_sei = [r["pergunta"] for r in estado_e.get("respostas") or [] if r.get("modo") in ("nao_sei", "depois")]
    if decida:
        partes.append("O ADVOGADO PEDIU QUE VOCÊ DECIDA (escolha a melhor solução e diga qual escolheu nas notas):\n"
                      + "\n".join("- " + p for p in decida))
    if nao_sei:
        partes.append("SEM RESPOSTA (adote a solução mais segura para o cliente do escritório, ou deixe a opção "
                      "entre colchetes no texto, e diga isso nas notas):\n" + "\n".join("- " + p for p in nao_sei))
    if estado_e.get("premissas"):
        partes.append("PREMISSAS DECLARADAS:\n" + "\n".join("- " + p for p in estado_e["premissas"]))
    if estado_e.get("analise"):
        partes.append("ANÁLISE FEITA AO ENTENDER O PEDIDO:\n" + estado_e["analise"])
    return "\n\n".join(partes)


# ------------------------------------------------------------ a avaliação

def avaliar(estado, estado_e: dict, nivel, *, trabalho=None, pessoa=None, documentos=(), historico=None,
            mensagem_nova: str = "", parar=None) -> dict | None:
    """
    Uma rodada: o modelo da nuvem lê o pedido com tudo o que já se sabe e
    decide executar ou perguntar; `conferir` deixa só o que vale. None quando
    a nuvem não respondeu ou o JSON não veio - quem chama segue sem entrevista.
    """
    import nuvem
    import profundidade as profundidade_mod

    mensagens = montar_mensagens(estado_e, nivel, documentos=documentos, historico=historico,
                                 mensagem_nova=mensagem_nova)
    modelo = profundidade_mod.modelo_do_nivel(estado.prefs.dados, nivel, nuvem.config(estado).get("modelo") or "")
    mascara = nuvem.Mascara() if nuvem.config(estado).get("mascarar", True) else None
    livre = nivel.id in ANALISE_LIVRE
    try:
        bruto, uso = nuvem.chamada(estado, mensagens, pessoa=pessoa, trabalho=trabalho, etapa="entrevista",
                                   pergunta=estado_e.get("pedido", ""), mascara=mascara, desmascarar=True,
                                   json_mode=not livre, max_tokens=3000 if livre else 2200, parar=parar,
                                   modelo=modelo, profundidade=nivel.id)
    except nuvem.ErroNuvem:
        return None
    analise, resto = separar_analise(bruto) if livre else ("", bruto)
    dados = _ler_json(resto)
    if dados is None:
        return None
    rodada = int(estado_e.get("rodada") or 0) + 1
    avaliacao = conferir(dados, nivel, rodada, ja_perguntadas=estado_e.get("perguntadas") or [])
    if not analise and isinstance(dados.get("analise"), dict):
        # O raciocínio de dentro do JSON também serve à elaboração.
        a = dados["analise"]
        linhas = [str(a.get("trabalho_e_regime") or "").strip()]
        for rotulo, chave in (("Já definido", "ja_definido"), ("Decisivo e faltando", "decisivo_faltando")):
            itens = [str(x).strip() for x in (a.get(chave) or []) if str(x).strip()]
            if itens:
                linhas.append(rotulo + ": " + "; ".join(itens))
        analise = "\n".join(x for x in linhas if x)
    avaliacao["analise"] = analise[:6000]
    avaliacao["tokens"] = int(uso.get("tokens_entrada") or 0) + int(uso.get("tokens_saida") or 0)
    return avaliacao


def aplicar(estado_e: dict, avaliacao: dict) -> None:
    """A avaliação entra no estado da entrevista: a rodada, o entendido, as perguntas da vez."""
    estado_e["rodada"] = int(estado_e.get("rodada") or 0) + 1
    if avaliacao.get("analise"):
        # A análise da última rodada é a que leu tudo o que já foi respondido.
        estado_e["analise"] = avaliacao["analise"]
    for chave in ("trabalho", "entendimento"):
        if avaliacao.get(chave):
            estado_e[chave] = avaliacao[chave]
    for p in avaliacao.get("premissas") or []:
        if p not in estado_e["premissas"]:
            estado_e["premissas"].append(p)
    estado_e["premissas"] = estado_e["premissas"][-8:]
    estado_e["perguntas"] = avaliacao.get("perguntas") or []
    estado_e["perguntadas"] = (estado_e.get("perguntadas") or []) + [q["pergunta"] for q in estado_e["perguntas"]]
