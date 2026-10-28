"""
O mapa dos assuntos que o advogado pergunta e dos artigos que os respondem.

A busca de lei por palavra (leis.procurar_assunto) acerta o artigo vizinho
mais do que o certo: medido em 26/10/2026 nas 22 perguntas de prazo de
tools/medir_leis.py, o artigo certo vinha em 1 - "tenho quantos dias para
apelar?" trazia o art. 331 do CPC, "prazo do recurso inominado" trazia o CPC
em vez da Lei dos Juizados.

Aqui o assunto aponta o artigo. O mapa não escreve nada: o que vai para a
resposta é o texto oficial do artigo, guardado da página do Planalto - o mapa
só diz qual. Cada entrada traz um trecho literal que o artigo tem de conter
("15 (quinze) dias"); tests/test_mapa_de_assuntos.py confere todos contra o
texto guardado, e o que o Planalto mudar aparece ali.

Regras de cada entrada (sobre a frase sem acento, em minúsculas):
- `assunto`: precisa casar;
- `com`: se houver, precisa casar também (o contexto: "trabalh", "juizado");
- `sem`: se casar, a entrada não vale (o recurso trabalhista não é o do CPC).
A primeira entrada que vale ganha a frente; as seguintes completam.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TRABALHO = r"trabalh|\bclt\b|reclamat|reclamante|empregad|empregador"
JUIZADO = r"juizad|9\.?099"


@dataclass
class Entrada:
    rotulo: str
    assunto: str
    artigos: list[tuple[str, str, str]]      # (codigo, artigo, trecho que o artigo tem de conter)
    com: str = ""
    sem: str = ""
    _re: dict = field(default_factory=dict, repr=False)

    def vale(self, plano: str) -> bool:
        if not self._re:
            self._re = {k: re.compile(getattr(self, k)) for k in ("assunto", "com", "sem") if getattr(self, k)}
        if not self._re["assunto"].search(plano):
            return False
        if "com" in self._re and not self._re["com"].search(plano):
            return False
        return not ("sem" in self._re and self._re["sem"].search(plano))


E = Entrada
MAPA: list[Entrada] = [
    # --- Juizados Especiais (Lei 9.099/1995) - antes do CPC: o recurso é outro.
    E("recurso inominado", r"recurso inominado|(recurso|recorr\w*)\b.*\bjuizad|\bjuizad.*\b(recurso|recorr)",
      [("juizados", "42", "dez dias")]),
    E("embargos de declaração no juizado", r"embargos de declarac", [("juizados", "49", "cinco dias")], com=JUIZADO),
    # --- Processo do trabalho (CLT)
    E("recurso ordinário trabalhista", r"recurso ordinario", [("clt", "895", "8 (oito) dias")]),
    E("agravo de petição", r"agravo de peticao", [("clt", "897", "8 (oito) dias")]),
    E("embargos de declaração trabalhistas", r"embargos de declarac", [("clt", "897-A", "cinco dias")], com=TRABALHO),
    E("contagem dos prazos trabalhistas", r"dias uteis|dias corridos|contagem d[eo]s? prazo",
      [("clt", "775", "dias úteis")], com=TRABALHO),
    E("prazo das verbas rescisórias", r"verbas rescisorias|pagamento da rescisao|(pagar|pagamento).*rescis",
      [("clt", "477", "dez dias")]),
    E("prescrição trabalhista", r"prescri", [("clt", "11", "cinco anos")], com=TRABALHO),
    E("defesa na audiência trabalhista", r"contesta|defesa", [("clt", "847", "vinte minutos")], com=TRABALHO),
    # --- Processo civil (CPC)
    E("embargos de declaração", r"embargos de declarac", [("cpc", "1.023", "5 (cinco) dias")], sem=TRABALHO + "|" + JUIZADO),
    E("contestação", r"\bcontestar\b|\bcontestacao\b|responde[r]? (a|à) (inicial|acao)|prazo (do|para o) reu",
      [("cpc", "335", "15 (quinze) dias")], sem=TRABALHO + "|" + JUIZADO + r"|manifestar sobre a contestacao|replica"),
    E("réplica", r"\breplica\b|manifestar sobre a contestacao|impugnar a contestacao|manifestacao sobre a contestacao",
      [("cpc", "351", "15 (quinze) dias"), ("cpc", "350", "15 (quinze) dias")]),
    E("apelação", r"\bapela(r|cao)\b", [("cpc", "1.003", "15 (quinze) dias"), ("cpc", "1.009", "apelação")],
      sem=TRABALHO + "|" + JUIZADO),
    E("contrarrazões", r"contrarraz", [("cpc", "1.010", "15 (quinze) dias")], sem=TRABALHO + "|" + JUIZADO),
    E("agravo de instrumento", r"agravo de instrumento", [("cpc", "1.003", "15 (quinze) dias"),
                                                          ("cpc", "1.015", "agravo de instrumento")], sem=TRABALHO),
    E("recursos aos tribunais superiores", r"recurso especial|recurso extraordinario|agravo interno",
      [("cpc", "1.003", "15 (quinze) dias")], sem=TRABALHO),
    E("prazo dos recursos", r"prazo (para|de) recorrer|prazo dos recursos|prazo recursal",
      [("cpc", "1.003", "15 (quinze) dias")], sem=TRABALHO + "|" + JUIZADO),
    E("contagem dos prazos", r"dias uteis|dias corridos|contagem d[eo]s? prazo", [("cpc", "219", "dias úteis")],
      sem=TRABALHO),
    E("prazo em dobro", r"prazo em dobro|prazo dobrado|em dobro", [("cpc", "183", "prazo em dobro"),
                                                                  ("cpc", "229", "prazos contados em dobro")]),
    E("pagamento no cumprimento de sentença", r"cumprimento de sentenca", [("cpc", "523", "15 (quinze) dias")],
      com=r"\bpag", sem=r"impugn"),
    E("impugnação ao cumprimento de sentença", r"impugn.*cumprimento|cumprimento.*impugn",
      [("cpc", "525", "15 (quinze) dias")]),
    E("embargos à execução", r"embargos (a|à) execucao|embargos do executado", [("cpc", "915", "15 (quinze) dias")]),
    E("ação rescisória", r"rescisoria", [("cpc", "975", "2 (dois) anos")], sem=TRABALHO),
    E("abertura do inventário", r"inventario", [("cpc", "611", "2 (dois) meses")], com=r"prazo|aber|instaur|quanto tempo|quando"),
    E("suspensão dos prazos no fim do ano", r"recesso|20 de dezembro|fim do ano|ferias forenses|suspens\w* d[oe]s? prazo",
      [("cpc", "220", "20 de dezembro")]),
    E("petição inicial", r"peticao inicial|requisitos da inicial|qualificacao das partes", [("cpc", "319", "petição inicial")]),
    E("poderes da procuração", r"procurac", [("cpc", "105", "desistir")], com=r"poder|especia|desist|transig|receber"),
    E("honorários de sucumbência", r"honorarios (de )?sucumb|sucumbencia", [("cpc", "85", "dez")], sem=TRABALHO),
    E("valor da causa", r"valor da causa", [("cpc", "292", "valor da causa")], sem=TRABALHO + "|" + JUIZADO),
    # --- Mandado de segurança
    E("prazo do mandado de segurança", r"mandado de seguranca", [("ms", "23", "120 (cento e vinte) dias")],
      com=r"prazo|impetra|decad|quanto tempo|ate quando"),
    # --- Código Civil
    E("prescrição da reparação civil", r"prescri", [("cc", "206", "três anos")],
      com=r"reparac|indeniz|\bdano", sem=TRABALHO),
    E("prescrição geral", r"prescri", [("cc", "205", "dez anos")], com=r"geral|nao fix|regra|menor",
      sem=TRABALHO),
    E("usucapião extraordinária", r"usucapiao extraordinaria", [("cc", "1.238", "quinze anos")]),
    E("usucapião especial urbana", r"usucapiao (especial )?urbana", [("cc", "1.240", "cinco anos")]),
    E("usucapião especial rural", r"usucapiao (especial )?rural", [("cc", "1.239", "cinco anos")]),
    E("usucapião ordinária", r"usucapiao ordinaria", [("cc", "1.242", "dez anos")]),
    # --- Consumidor
    E("vício do produto ou serviço", r"\bvicio", [("cdc", "26", "trinta dias")], com=r"reclam|prazo|quanto tempo|dias"),
    E("direito de arrependimento", r"arrepend|desistir da compra|fora do estabelecimento", [("cdc", "49", "7 dias")]),
    # --- Locação
    E("desocupação depois do despejo", r"desocup", [("inquilinato", "63", "30 (trinta) dias")], com=r"despejo|inquilin|locat"),
    E("ação renovatória", r"renovatoria", [("inquilinato", "51", "um ano")]),
    E("ação revisional de aluguel", r"revisional|revisao do aluguel", [("inquilinato", "19", "três anos")]),
]


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


def artigos_do_assunto(pergunta: str) -> list[tuple[str, str, str]]:
    """Os (codigo, artigo, rotulo) do mapa para a pergunta, na ordem das entradas que valem, sem repetir."""
    plano = _plano(pergunta)
    saida: list[tuple[str, str, str]] = []
    for e in MAPA:
        if e.vale(plano):
            for codigo, artigo, _trecho in e.artigos:
                if not any(c == codigo and a == artigo for c, a, _ in saida):
                    saida.append((codigo, artigo, e.rotulo))
    return saida
