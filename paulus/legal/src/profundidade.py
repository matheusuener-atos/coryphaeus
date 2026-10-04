"""
Profundidade: o quanto o PAULUS trabalha um pedido (03/10/2026).

O advogado não escolhe modelo. Escolhe o esforço:

    Estagiário → Bacharel → Advogado → Juiz → Ministro

Cada nível é uma receita, e tudo nela é do programa:

- **entrevista** (src/entrevista.py): quantas perguntas no máximo por rodada,
  quantas rodadas, e o que procurar antes de decidir que já tem o bastante -
  do "só o que impede a tarefa" do Estagiário às lacunas que o próprio
  advogado não percebeu, no Ministro. Mais nível é mais inteligência na escolha
  das perguntas, e não mais perguntas: o teto é teto, e a instrução diz para
  não perguntar o que não muda o trabalho.
- **etapas da elaboração** (src/elaboracao.py): Estagiário escreve direto;
  Bacharel escreve com estrutura; Advogado planeja antes de escrever; Juiz
  planeja com as alternativas, escreve e revisa criticamente, refazendo o que a
  revisão apontar; Ministro começa por uma análise de riscos, ambiguidades e
  consequências, e revisa com o rigor maior.
- **orçamento**: o teto de tokens da resposta escrita, e quanto do documento
  anexado entra inteiro.
- **modelo**: o que está em Configurações › Modelos, para todos os níveis -
  a menos que o escritório escolha um modelo por nível (`profundidade.modelos`).

Fora da nuvem, o modelo deste computador (o 3B) não aguenta as etapas nem a
entrevista: a pergunta segue pelo caminho de sempre, e a tela diz isso.

O consumo de cada nível (`consumo`) é uma conta aproximada - o número de
chamadas e o tamanho do que cada uma escreve -, para a pessoa saber que o
Ministro gasta mais da franquia. Não é preço: o que vale é o que o Worker conta.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ORDEM = ("estagiario", "bacharel", "advogado", "juiz", "ministro")
PADRAO = "advogado"


@dataclass(frozen=True)
class Nivel:
    id: str
    nome: str
    resumo: str            # a linha curta do seletor
    explica: str           # o que muda, em uma frase
    # A entrevista
    perguntas_max: int     # por rodada
    rodadas_max: int
    postura: str           # o que o nível procura antes de executar (vai à instrução)
    # A elaboração
    etapas: tuple = ()     # "analise", "plano", "redacao", "revisao"
    saida_tokens: int = 2000
    documento_caracteres: int = 30000
    # A conta aproximada, em "vezes o Estagiário"
    consumo: float = 1.0
    detalhes: tuple = field(default_factory=tuple)


NIVEIS: dict[str, Nivel] = {
    "estagiario": Nivel(
        id="estagiario", nome="Estagiário", resumo="Rápido · menor profundidade · menor consumo",
        explica="Executa logo. Só pergunta quando falta algo sem o qual não dá para fazer.",
        perguntas_max=2, rodadas_max=1,
        postura=("Pergunte SOMENTE se faltar algo sem o qual a tarefa não pode ser feita (por exemplo: o tipo de "
                 "documento não está claro). Na dúvida, execute com premissas razoáveis e diga quais usou."),
        etapas=("redacao",), saida_tokens=2000, documento_caracteres=20000, consumo=1.0,
        detalhes=("1 chamada", "até ~2 mil tokens escritos")),
    "bacharel": Nivel(
        id="bacharel", nome="Bacharel", resumo="Moderado · melhor estruturação e análise",
        explica="Estrutura melhor e pergunta o que falta de evidente.",
        perguntas_max=3, rodadas_max=1,
        postura=("Identifique as lacunas evidentes - o que qualquer profissional perguntaria antes de começar - e "
                 "pergunte só as que mudam o resultado."),
        etapas=("redacao",), saida_tokens=3500, documento_caracteres=30000, consumo=1.5,
        detalhes=("1 chamada, com estrutura", "até ~3,5 mil tokens escritos")),
    "advogado": Nivel(
        id="advogado", nome="Advogado", resumo="Profissional · profundidade forte · recomendado",
        explica="Analisa o pedido antes de executar, planeja a estrutura e depois redige.",
        perguntas_max=5, rodadas_max=2,
        postura=("Analise a solicitação como um advogado experiente faria antes de redigir: quais informações "
                 "ausentes mudam materialmente a estrutura, as cláusulas, os argumentos ou a estratégia? Pergunte "
                 "essas, numa entrevista curta."),
        etapas=("plano", "redacao"), saida_tokens=6000, documento_caracteres=60000, consumo=2.5,
        detalhes=("planeja e redige", "até ~6 mil tokens escritos")),
    "juiz": Nivel(
        id="juiz", nome="Juiz", resumo="Análise profunda · revisão crítica e alternativas",
        explica="Questiona premissas, pesa alternativas, escreve e revisa criticamente o próprio trabalho.",
        perguntas_max=6, rodadas_max=2,
        postura=("Questione as premissas do pedido. Procure ambiguidades, conflitos entre o que foi dito e "
                 "consequências relevantes que o usuário talvez não tenha considerado. Pergunte o que, se mal "
                 "definido, levaria a um documento ou análise errada ou arriscada."),
        etapas=("plano", "redacao", "revisao"), saida_tokens=7000, documento_caracteres=90000, consumo=4.0,
        detalhes=("planeja, redige e revisa", "refaz o que a revisão apontar", "até ~7 mil tokens escritos")),
    "ministro": Nivel(
        id="ministro", nome="Ministro", resumo="Profundidade máxima · riscos, interpretações e consequências",
        explica="Começa por uma análise de riscos e interpretações, planeja, redige e revisa com o rigor maior.",
        perguntas_max=7, rodadas_max=3,
        postura=("Faça a análise mais profunda possível antes de decidir que já tem contexto suficiente: lacunas "
                 "menos óbvias, riscos, interpretações alternativas, inconsistências, consequências práticas e o "
                 "que costuma gerar litígio nesse tipo de trabalho. Não confunda profundidade com quantidade: se "
                 "três perguntas bastam, faça três - mas que sejam as que um especialista faria."),
        etapas=("analise", "plano", "redacao", "revisao"), saida_tokens=8000, documento_caracteres=120000,
        consumo=6.0,
        detalhes=("analisa riscos, planeja, redige e revisa", "refaz o que a revisão apontar",
                  "até ~8 mil tokens escritos")),
}


def obter(nivel_id: str | None, prefs: dict | None = None) -> Nivel:
    """O nível pedido; vazio ou desconhecido, o padrão do escritório (e, sem ele, Advogado)."""
    nid = str(nivel_id or "").strip().lower()
    if nid in NIVEIS:
        return NIVEIS[nid]
    padrao = str(((prefs or {}).get("profundidade") or {}).get("padrao") or "").lower()
    return NIVEIS.get(padrao, NIVEIS[PADRAO])


def entrevista_ligada(prefs: dict | None) -> bool:
    return bool(((prefs or {}).get("profundidade") or {}).get("entrevista", True))


def modelo_do_nivel(prefs: dict | None, nivel: Nivel, modelo_padrao: str) -> str:
    """O modelo escolhido para o nível em `profundidade.modelos`, ou o de Configurações › Modelos."""
    escolhido = str((((prefs or {}).get("profundidade") or {}).get("modelos") or {}).get(nivel.id) or "").strip()
    return escolhido or modelo_padrao


def limitar(nivel: Nivel, nivel_max: str) -> Nivel:
    """O nível pedido, ou o máximo do plano se o pedido passar dele (src/recursos_do_plano.py)."""
    if nivel_max in ORDEM and ORDEM.index(nivel.id) > ORDEM.index(nivel_max):
        return NIVEIS[nivel_max]
    return nivel


def para_tela(prefs: dict | None = None, nivel_max: str = "ministro", frase_do_nivel=None) -> dict:
    """O seletor: os cinco níveis (os acima do plano, travados, com a frase), o padrão e a entrevista."""
    teto = ORDEM.index(nivel_max) if nivel_max in ORDEM else len(ORDEM) - 1
    niveis = []
    for i, n in enumerate(NIVEIS.values()):
        item = {**{k: v for k, v in asdict(n).items() if k not in ("postura",)}, "etapas": list(n.etapas), "detalhes": list(n.detalhes)}
        if i > teto:
            item["bloqueado"] = True
            item["no_plano"] = frase_do_nivel(n.id) if frase_do_nivel else ""
        niveis.append(item)
    return {
        "niveis": niveis,
        "padrao": limitar(obter("", prefs), nivel_max).id,
        "entrevista": entrevista_ligada(prefs),
    }


# A instrução que vai junto da resposta comum (pergunta sobre documentos ou
# lei) na nuvem: o que muda no jeito de responder. A resposta comum não passa
# pelas etapas da elaboração; a profundidade nela é o cuidado e o teto.
INSTRUCAO_RESPOSTA = {
    "estagiario": "PROFUNDIDADE: Estagiário. Responda direto e curto, só o essencial.",
    "bacharel": "PROFUNDIDADE: Bacharel. Responda de forma organizada, com o fundamento principal.",
    "advogado": ("PROFUNDIDADE: Advogado. Responda como um advogado experiente: o fundamento, as ressalvas que "
                 "importam e o que depende do caso concreto."),
    "juiz": ("PROFUNDIDADE: Juiz. Antes de concluir, considere as interpretações possíveis e as premissas da "
             "pergunta; aponte ambiguidades, a posição dominante e a divergência relevante, e as consequências."),
    "ministro": ("PROFUNDIDADE: Ministro. Faça a análise mais completa: interpretações alternativas, riscos, "
                 "inconsistências, consequências práticas e o que pode ser contestado. Seja rigoroso e explícito "
                 "sobre o que depende de fato ainda não informado."),
}

# O teto da resposta comum na nuvem, por nível.
SAIDA_RESPOSTA = {"estagiario": 1200, "bacharel": 2000, "advogado": 3000, "juiz": 4000, "ministro": 5000}
