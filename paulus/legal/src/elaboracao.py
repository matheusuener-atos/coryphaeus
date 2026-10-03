"""
A elaboração com profundidade (03/10/2026): depois de entender o pedido
(src/entrevista.py), o trabalho pesado, nas etapas do nível escolhido
(src/profundidade.py):

- **análise** (Ministro): riscos, ambiguidades, interpretações alternativas,
  inconsistências e consequências práticas, antes de planejar;
- **plano** (Advogado, Juiz, Ministro): a estrutura, o conteúdo de cada
  parte, as escolhas jurídicas e o porquê - no Juiz e no Ministro, com as
  alternativas consideradas;
- **redação**: o texto, que chega à tela enquanto é escrito;
- **revisão** (Juiz, Ministro): um revisor sênior confronta o texto com o
  pedido e as respostas e aponta o que falta, o que está fraco e o que está
  errado; se houver ponto de gravidade alta ou média, o texto é reescrito
  inteiro com as correções, e a tela troca o rascunho pela versão revista.

Tudo pela nuvem (`nuvem.chamada`), com UMA máscara para o pedido inteiro: o
"[CPF 1]" do plano é o mesmo da redação. Entre as etapas o texto anda com os
marcadores; só o que vai para a tela volta com os dados.

O que o texto final não pode fazer, a instrução diz e a conferência de
sempre (src/citacoes.py) cobre na resposta: inventar nome, CPF, número de
processo ou valor - o que falta vira [●] -, e citar artigo que não existe.
"""

from __future__ import annotations

import json
import re

TITULOS = {"analise": "Analisar riscos e interpretações", "plano": "Planejar a estrutura",
           "redacao": "Redigir", "revisao": "Revisar criticamente"}

INSTRUCAO_TRABALHO = """

TRABALHO JURÍDICO
Você está produzindo um trabalho profissional para o escritório (peça, contrato, parecer, notificação...). \
Entregue o trabalho pronto para uso, completo para o tipo de documento e para o nível pedido - não um \
modelo genérico.
- Dado que não foi informado (nomes, CPF, endereços, valores, datas, números de processo) fica como [●] no \
texto. Nunca invente esses dados, nem marcadores como [CPF 3] ou [E-MAIL 2]: campo a preencher é sempre [●].
- Fundamente com os dispositivos legais certos, com número e lei (por exemplo: "art. 95 do Estatuto da \
Terra (Lei 4.504/1964)"). Não ponha entre aspas texto de lei que você não tenha recebido.
- Use a forma do documento: títulos, cláusulas numeradas, parágrafos, pedidos - o que aquele tipo pede.
- Texto simples, sem markdown: nada de asteriscos, cerquilhas ou tabelas. Títulos e nomes de cláusula em \
MAIÚSCULAS, cada um na sua linha.
- Respeite as normas cogentes: cláusula que a lei proíbe é nula. Se o pedido ou as respostas pedirem algo \
vedado, adapte ao que a lei permite (do jeito mais próximo do que foi pedido) e explique nas notas.
- Sem comentário sobre o próprio processo no meio do texto.
- No fim, depois de uma linha só com "---", uma seção curta "Notas para o advogado": as escolhas que você \
fez (as premissas e o que o advogado pediu para você decidir), os pontos a conferir e os campos [●] a \
preencher."""

# A extensão esperada é o que o tipo de trabalho pede no nível - medido em
# 03/10: sem ela, o Advogado entregava um contrato de 8 cláusulas usando um
# terço do orçamento. Não é para encher: é para não parar no esqueleto.
PROFUNDIDADE_REDACAO = {
    "estagiario": ("NÍVEL: Estagiário. Texto correto e direto, com o essencial do tipo de documento. Extensão: a "
                   "menor que resolva (para um contrato, cerca de 500 a 900 palavras)."),
    "bacharel": ("NÍVEL: Bacharel. Texto bem estruturado, com as cláusulas ou seções que o tipo normalmente traz. "
                 "Extensão: para um contrato ou peça, cerca de 900 a 1.500 palavras."),
    "advogado": ("NÍVEL: Advogado. Texto de advogado experiente: completo, com as cláusulas obrigatórias por lei, as "
                 "proteções que o caso pede para o cliente do escritório (cada uma com o seu mecanismo: prazo, "
                 "procedimento, consequência) e nada decorativo. Siga o PLANO por inteiro. Extensão: para um contrato "
                 "ou peça, cerca de 1.800 a 3.000 palavras."),
    "juiz": ("NÍVEL: Juiz. Texto completo e rigoroso: trate as ambiguidades, as alternativas escolhidas no PLANO e as "
             "consequências; antecipe a objeção da outra parte. Extensão: cerca de 2.500 a 4.000 palavras para um "
             "contrato ou peça."),
    "ministro": ("NÍVEL: Ministro. O trabalho mais completo e rigoroso possível: trate cada risco da ANÁLISE, cada "
                 "ponto do PLANO, as interpretações alternativas e as consequências práticas; antecipe o litígio. "
                 "Extensão: cerca de 3.000 a 5.000 palavras para um contrato ou peça."),
}

ANALISE = """Antes de planejar, analise o trabalho pedido como o especialista mais cuidadoso faria. Em tópicos \
curtos, sem redigir o documento:
1. Riscos jurídicos e práticos para o cliente do escritório.
2. Ambiguidades do pedido e como cada leitura mudaria o trabalho.
3. Interpretações alternativas (doutrina, jurisprudência, posição dominante).
4. Inconsistências entre o que foi dito.
5. Consequências práticas e o que costuma gerar litígio neste tipo de trabalho.
6. O que precisa estar no documento por causa disso."""

PLANO = """Monte o PLANO do trabalho, sem redigi-lo ainda. Em tópicos:
1. As exigências e as VEDAÇÕES legais deste tipo de trabalho: o que a lei e o regulamento tornam obrigatório, \
o que proíbem ou tornam nulo - e se algo do pedido esbarra nisso (então, como adaptar).
2. A estrutura completa, na ordem (seções, cláusulas ou capítulos), com o conteúdo essencial de cada uma.
3. As escolhas jurídicas e o porquê de cada uma{alternativas}.
4. Os dispositivos legais que fundamentam.
5. Os pontos que exigem atenção especial."""

REVISAO = """Você é o revisor sênior do escritório. Revise criticamente o TEXTO abaixo contra o PEDIDO e o que foi \
DEFINIDO. Procure: o que foi pedido e não está no texto; omissões que um advogado experiente notaria; \
contradições; cláusulas ou argumentos fracos; riscos não tratados; fundamento legal errado ou duvidoso; \
cláusula contrária a norma cogente ou vedação legal (nula); cláusula obrigatória por lei que faltou; dado \
inventado (deveria ser [●]){rigor}.
Dado que o advogado não informou (valor, quantidade, data, nome, área) NÃO é problema: fica [●]. Nunca \
peça para preencher com um número.
Responda só com JSON: {{"problemas": [{{"gravidade": "alta", "onde": "cláusula 5", "o_que": "...", \
"correcao": "..."}}], "refazer": true}}
gravidade: "alta" (erro ou omissão que compromete), "media" (fragilidade relevante), "baixa" (ajuste fino). \
"refazer": true se houver algum problema alto ou médio."""

REESCRITA = """Reescreva o TEXTO inteiro, já corrigido conforme a REVISÃO, mantendo o que está bom. Não invente \
valores, quantidades, datas nem nomes: o que o advogado não informou continua [●]. Entregue só o texto final \
completo (com as "Notas para o advogado" no fim), sem comentar a revisão."""


def etapas_do_nivel(nivel) -> list[str]:
    return [e for e in nivel.etapas]


def _sistema(nivel) -> str:
    import instrucao_nuvem

    return instrucao_nuvem.instrucao() + INSTRUCAO_TRABALHO + "\n" + PROFUNDIDADE_REDACAO[nivel.id]


def _base_do_pedido(pedido: str, briefing: str, documentos) -> str:
    partes = [f"PEDIDO DO ADVOGADO: {pedido}"]
    if briefing:
        partes.append(briefing)
    for nome, texto in documentos or []:
        partes.append(f"DOCUMENTO «{nome}»:\n{texto}")
    return "\n\n".join(partes)


def _ler_json(bruto: str) -> dict | None:
    try:
        d = json.loads(bruto)
    except (ValueError, TypeError):
        ini, fim = str(bruto or "").find("{"), str(bruto or "").rfind("}")
        if ini == -1 or fim <= ini:
            return None
        try:
            d = json.loads(bruto[ini:fim + 1])
        except ValueError:
            return None
    return d if isinstance(d, dict) else None


# "Não especifica o valor", "inserir a quantidade exata": o dado que o advogado
# não deu fica [●], e não é defeito do texto. Medido em 03/10: a revisão do
# Juiz pedia o número, e a reescrita inventava "20 sacas". Vira ajuste fino.
RE_DADO_FALTANTE = re.compile(
    r"(?:n[aã]o\s+(?:especifica|informa|define|indica|traz|menciona)|falta(?:m)?|inserir|preencher|informar|especificar)"
    r"\s.{0,40}?\b(?:valor|valores|quantidade|quantia|data|datas|nome|nomes|endere[cç]o|cpf|cnpj|[aá]rea|n[uú]mero|"
    r"percentual|montante|matr[ií]cula)\b", re.IGNORECASE)


# Os marcadores da máscara (src/nuvem.py) têm este formato; um que a máscara
# não criou foi inventado pelo modelo (o Qwen 72B pôs "[CPF 3]" na testemunha,
# 03/10) e, se a máscara um dia tiver esse número, viraria o CPF de outra
# pessoa. Vira [●].
RE_MARCADOR = re.compile(r"\[(?:CPF|CNPJ|E-MAIL|TELEFONE|PROCESSO) \d{1,3}\]")


def limpar_texto(texto: str, mascara=None) -> str:
    """
    O texto final, como a conversa e o editor mostram: os dados de volta, sem
    marcador inventado, sem markdown (cabeçalho "####" e negrito "**") - a
    instrução pede texto simples, e nem todo modelo obedece.
    """
    t = mascara.desfazer(texto) if mascara is not None else str(texto or "")
    t = RE_MARCADOR.sub("[●]", t)
    t = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*", "", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    return t.strip()


def problemas_da_revisao(dados: dict | None) -> tuple[list[dict], bool]:
    """Os problemas conferidos e se é para refazer (só com algum alto ou médio)."""
    lista = []
    for p in (dados or {}).get("problemas") or []:
        if not isinstance(p, dict):
            continue
        g = str(p.get("gravidade") or "").lower()
        g = "alta" if g.startswith("alt") else "media" if g.startswith(("med", "méd")) else "baixa"
        o_que = " ".join(str(p.get("o_que") or "").split())[:300]
        if not o_que:
            continue
        if RE_DADO_FALTANTE.search(o_que + " " + str(p.get("correcao") or "")):
            g = "baixa"
        lista.append({"gravidade": g, "onde": " ".join(str(p.get("onde") or "").split())[:80], "o_que": o_que,
                      "correcao": " ".join(str(p.get("correcao") or "").split())[:400]})
    refazer = any(p["gravidade"] in ("alta", "media") for p in lista)
    return lista[:12], refazer


def elaborar(estado, *, trabalho, pedido: str, briefing: str, nivel, documentos=(), pessoa=None, parar=None,
             historico=None):
    """
    Gerador de eventos (tipo, dados):
      ("etapa", {"id", "titulo", "estado": "executando"|"concluido", "detalhe"})
      ("nota", {"texto"})            - o que aparece no bastidor
      ("token", {"t"})               - o texto, com os dados de volta
      ("reescrevendo", {"problemas"})- a revisão pediu para refazer: a tela limpa o rascunho
      ("fim", {"texto", "tokens", "revisao", "etapas", "modelo", "provedor"})
    Erro da nuvem sobe como nuvem.ErroNuvem, com o que já foi escrito em `.parcial`.
    """
    import nuvem
    import profundidade as profundidade_mod
    from habilidade_base import Ponte

    prefs = estado.prefs.dados
    modelo = profundidade_mod.modelo_do_nivel(prefs, nivel, nuvem.config(estado).get("modelo") or "")
    mascara = nuvem.Mascara() if nuvem.config(estado).get("mascarar", True) else None
    sistema = _sistema(nivel)
    ensinado = getattr(getattr(estado, "contextos", None), "bloco", lambda: "")() or ""
    if ensinado.strip():
        sistema += "\n\n" + ensinado.strip()
    base = _base_do_pedido(pedido, briefing, documentos)
    antes = [m for m in (historico or [])[-4:] if m.get("role") in ("user", "assistant")]
    tokens = {"entrada": 0, "saida": 0}
    feitas: list[str] = []
    info = {"modelo": modelo, "provedor": ""}

    def chamar(etapa: str, usuario: str, *, json_mode=False, max_tokens=2000, on_token=None) -> str:
        mensagens = [{"role": "system", "content": sistema}, *antes, {"role": "user", "content": usuario}]
        texto, uso = nuvem.chamada(estado, mensagens, pessoa=pessoa, trabalho=trabalho, etapa=etapa, pergunta=pedido,
                                   mascara=mascara, on_token=on_token, desmascarar=False, json_mode=json_mode,
                                   max_tokens=max_tokens, parar=parar, modelo=modelo, profundidade=nivel.id)
        tokens["entrada"] += int(uso.get("tokens_entrada") or 0)
        tokens["saida"] += int(uso.get("tokens_saida") or 0)
        info["provedor"] = uso.get("provedor", "")
        return texto

    def transmitir(etapa: str, usuario: str, max_tokens: int):
        """A chamada que vai à tela enquanto chega: os pedaços com os dados de volta."""
        desm = nuvem.Desmascarador(mascara)
        ponte = Ponte(lambda empurrar: chamar(etapa, usuario, max_tokens=max_tokens,
                                              on_token=lambda t: empurrar(t)), parar=parar)
        escrito: list[str] = []
        try:
            for pedaco in ponte:
                pronto = desm.entrar(pedaco)
                if pronto:
                    escrito.append(pronto)
                    yield ("token", {"t": pronto})
        except nuvem.ErroNuvem as exc:
            exc.parcial = "".join(escrito) + desm.fim()
            raise
        resto = desm.fim()
        if resto:
            yield ("token", {"t": resto})
        return ponte.resultado or ""

    analise = plano = ""
    if "analise" in nivel.etapas:
        yield ("etapa", {"id": "analise", "titulo": TITULOS["analise"], "estado": "executando", "detalhe": ""})
        analise = chamar("analise", base + "\n\n" + ANALISE, max_tokens=2000)
        feitas.append("analise")
        yield ("nota", {"texto": "analisei riscos, ambiguidades e interpretações antes de planejar"})
        yield ("etapa", {"id": "analise", "titulo": TITULOS["analise"], "estado": "concluido", "detalhe": ""})
    if parar is not None and parar():
        return
    if "plano" in nivel.etapas:
        yield ("etapa", {"id": "plano", "titulo": TITULOS["plano"], "estado": "executando", "detalhe": ""})
        alternativas = (", com as alternativas que você considerou e por que as descartou"
                        if nivel.id in ("juiz", "ministro") else "")
        pedido_plano = base + ("\n\nANÁLISE:\n" + analise if analise else "") + "\n\n" + PLANO.format(alternativas=alternativas)
        plano = chamar("plano", pedido_plano, max_tokens=2500)
        feitas.append("plano")
        partes_do_plano = len(re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", plano))
        yield ("nota", {"texto": f"planejei a estrutura ({partes_do_plano} pontos) antes de redigir"})
        yield ("etapa", {"id": "plano", "titulo": TITULOS["plano"], "estado": "concluido", "detalhe": ""})
    if parar is not None and parar():
        return

    yield ("etapa", {"id": "redacao", "titulo": TITULOS["redacao"], "estado": "executando", "detalhe": ""})
    # Medido em 03/10: com "redija o trabalho completo", o Llama 70B resumia um
    # plano de 24 pontos em 8 cláusulas curtas. Pedir cada seção do plano,
    # com parágrafos, é o que faz o texto chegar à extensão do nível.
    fechamento = ("\n\nAgora redija o trabalho completo: TODAS as seções do PLANO, na ordem, cada uma desenvolvida "
                  "com caput e os parágrafos ou incisos que ela pede (prazos, procedimentos, consequências). Não "
                  "resuma nenhuma seção nem junte duas numa só."
                  if plano else "\n\nAgora redija o trabalho completo.")
    pedido_redacao = (base + ("\n\nANÁLISE:\n" + analise if analise else "") + ("\n\nPLANO:\n" + plano if plano else "")
                      + fechamento)
    rascunho = yield from transmitir("redacao", pedido_redacao, nivel.saida_tokens)
    feitas.append("redacao")
    yield ("etapa", {"id": "redacao", "titulo": TITULOS["redacao"], "estado": "concluido", "detalhe": ""})
    final_mascarado = rascunho
    revisao: dict = {}
    if "revisao" in nivel.etapas and rascunho and not (parar is not None and parar()):
        yield ("etapa", {"id": "revisao", "titulo": TITULOS["revisao"], "estado": "executando", "detalhe": ""})
        rigor = ("; e, com o rigor máximo, cada risco e interpretação da ANÁLISE que o texto não tratou"
                 if nivel.id == "ministro" else "")
        bruto = chamar("revisao", base + ("\n\nANÁLISE:\n" + analise if analise else "") + "\n\nTEXTO:\n" + rascunho
                       + "\n\n" + REVISAO.format(rigor=rigor), json_mode=True, max_tokens=2000)
        problemas, refazer = problemas_da_revisao(_ler_json(bruto))
        revisao = {"problemas": [dict(p, o_que=mascara.desfazer(p["o_que"]) if mascara else p["o_que"],
                                      correcao=mascara.desfazer(p["correcao"]) if mascara else p["correcao"])
                                 for p in problemas], "refeito": False}
        feitas.append("revisao")
        altos = sum(1 for p in problemas if p["gravidade"] in ("alta", "media"))
        if refazer and not (parar is not None and parar()):
            yield ("nota", {"texto": f"a revisão apontou {altos} ponto(s) a corrigir; reescrevendo com as correções"})
            yield ("etapa", {"id": "revisao", "titulo": "Reescrever com as correções", "estado": "executando",
                             "detalhe": f"{altos} ponto(s)"})
            yield ("reescrevendo", {"problemas": altos})
            lista = "\n".join(f"- [{p['gravidade']}] {p['onde']}: {p['o_que']} -> {p['correcao']}" for p in problemas)
            try:
                final_mascarado = yield from transmitir(
                    "reescrita", base + ("\n\nPLANO:\n" + plano if plano else "") + "\n\nTEXTO:\n" + rascunho
                    + "\n\nREVISÃO:\n" + lista + "\n\n" + REESCRITA, nivel.saida_tokens)
            except nuvem.ErroNuvem as exc:
                # A reescrita caiu no meio: fica o rascunho inteiro, e a revisão vai nas notas.
                final_mascarado = ""
                yield ("nota", {"texto": "a reescrita não terminou (" + str(exc) + "); ficou o rascunho, com a revisão anotada"})
            if final_mascarado and not (parar is not None and parar()):
                revisao["refeito"] = True
                feitas.append("reescrita")
            else:
                final_mascarado = rascunho
                yield ("substituir", {"texto": mascara.desfazer(rascunho) if mascara else rascunho})
        else:
            yield ("nota", {"texto": "a revisão não achou ponto alto ou médio a corrigir"
                            + (f" ({len(problemas)} ajuste(s) fino(s) nas notas)" if problemas else "")})
        yield ("etapa", {"id": "revisao", "titulo": TITULOS["revisao"], "estado": "concluido",
                         "detalhe": (f"{altos} corrigido(s)" if revisao.get("refeito") else "sem correção necessária")})
    texto = limpar_texto(final_mascarado, mascara)
    # O que foi para a tela veio cru (com "####" e "**", se o modelo pôs); a
    # versão limpa toma o lugar dela.
    bruto = mascara.desfazer(final_mascarado).strip() if mascara else final_mascarado.strip()
    if texto != bruto:
        yield ("substituir", {"texto": texto})
    yield ("fim", {"texto": texto, "tokens": tokens, "revisao": revisao, "etapas": feitas,
                   "modelo": info["modelo"], "provedor": info["provedor"]})
