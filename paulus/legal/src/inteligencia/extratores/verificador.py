"""
O conferidor: a afirmacao esta mesmo no trecho citado?

A verificacao de span (alinhar.py) responde uma pergunta: a citacao existe no
documento? Esta aqui responde a outra, que ela nao alcanca: a citacao que
existe SUSTENTA o que foi afirmado?

A diferenca aparece num caso comum. O modelo extrai "Joao da Silva - REU" e
cita uma frase que existe no documento: "JOAO DA SILVA, brasileiro, casado,
residente em...". A frase e real, o nome e real, e o papel pode estar
invertido - Joao pode ser o AUTOR. A aritmetica nao pega isso; ler, sim.

Duas regras vem da spec e valem repetir:

**Extrator e conferidor nunca sao a mesma chamada.** Auto-verificacao nao
verifica nada: o mesmo modelo, no mesmo passe, confirma o que acabou de dizer.
Aqui e outra chamada, com outro prompt, vendo so a afirmacao e o trecho - sem
o resto do documento e sem saber quem extraiu.

**O conferidor so pode rebaixar.** Ele nunca promove item nenhum a fato: no
maximo confirma o que a verificacao de span ja tinha aceitado. Um verificador
que promove vira uma segunda chance para a alucinacao passar.
"""

from __future__ import annotations

from ..esquema import Item
from .base import limpar

ID = "span-verifier/v1"
PAPEL = "verifier"
PROMPT_VERSAO = "verifier/v1"

INSTRUCAO = (
    "Abaixo ha uma AFIRMACAO e um TRECHO copiado de um documento.\n"
    "O trecho sustenta a afirmacao? Responda uma palavra: SIM ou NAO.\n"
    "Responda NAO se o trecho falar de outra pessoa, de outro papel, de outro "
    "valor, ou se for preciso supor alguma coisa para a afirmacao valer."
)

SISTEMA = (
    "Voce confere se um trecho sustenta uma afirmacao. Nao explica, nao completa, "
    "nao da opiniao. Responde SIM ou NAO."
)


def frase_do_item(item: Item, secao: str) -> str:
    """A afirmacao em portugues, do jeito que ela seria dita na resposta."""
    if secao == "parties":
        papel = item.dados.get("role_br") or item.dados.get("role") or "parte"
        return f"{item.dados.get('name', '')} é {papel} neste documento."
    if secao == "dates":
        return f"A data {item.dados.get('date', '')} é a data de {item.dados.get('kind') or 'referência'}."
    if secao == "amounts":
        return f"O valor {item.dados.get('value_text', '')} é {item.dados.get('kind') or 'um valor do documento'}."
    return f"{item.valor} consta deste documento."


def conferir_item(client, item: Item, secao: str) -> tuple[bool, str]:
    """
    Pergunta ao conferidor. Devolve (aceito, motivo).

    Sem cliente, sem trecho ou com erro do modelo, o item passa como estava -
    a conferencia e uma peneira a mais, e peneira que nao roda nao pode
    reprovar o que ja tinha sido aceito pela verificacao de span.
    """
    if client is None or not item.quote:
        return True, "conferidor nao rodou"

    pedido = (f"{INSTRUCAO}\n\nAFIRMACAO: {frase_do_item(item, secao)}\n\n"
              f"TRECHO: {item.quote[:600]}")
    try:
        resposta = limpar(client.ask(pedido, "", sistema=SISTEMA)).upper()
    except Exception as exc:
        return True, f"conferidor falhou ({type(exc).__name__})"

    if resposta.startswith("NAO") or resposta.startswith("NÃO") or resposta.startswith("NO"):
        return False, "o trecho citado não sustenta a afirmação"
    return True, "conferido"


def conferir_todos(client, itens: list[Item], secao: str) -> int:
    """
    Passa a lista pelo conferidor. Devolve quantos foram rebaixados.

    So itens JA verificados por span entram: gastar uma chamada de modelo com
    o que a aritmetica ja reprovou seria pagar caro para confirmar o obvio.
    """
    rebaixados = 0
    for item in itens:
        if not item.verified:
            continue
        aceito, motivo = conferir_item(client, item, secao)
        if not aceito:
            item.verified = False
            item.certainty = "uncertain"
            item.dados["verification_note"] = motivo
            rebaixados += 1
    return rebaixados
