"""
Quem sao as partes - a secao que justifica existir um modelo.

Esta e a pergunta que mais se faz sobre um documento juridico e a que menos se
resolve por regra. O nome esta sempre no mesmo lugar - no primeiro paragrafo,
na qualificacao -, mas quem e AUTOR e quem e REU depende de ler a frase:
"COOPERATIVA BRASILEIRA LTDA., doravante CONTRATANTE, contrata JOAO DA SILVA,
CONTRATADO" nao se separa por expressao regular sem escrever um analisador de
portugues.

O desenho aqui e o que a spec pede e vale repetir: **o modelo aponta, a
verificacao confirma.** O modelo devolve nome, papel e a frase do documento
onde aquilo esta escrito; a camada de verificacao procura a frase no texto e
so aceita o item se ela existir. O que ele inventar fica marcado como nao
conferido, sobrevive no metadata para ser contado, e nao responde nada.

Por isso o prompt pede a citacao junto - e nao por educacao. Sem ela nao ha o
que conferir, e sem conferencia um nome extraido e s um nome que apareceu na
tela do programa.
"""

from __future__ import annotations

import re

from .base import LEITURA_PADRAO, Pedido, Resultado, limpar
from ..esquema import Item

ID = "party-extractor/v2"
SECAO = "parties"
NIVEL = 2
PROMPT_VERSAO = "parties/v2"

# Os papeis que interessam, em portugues e ja mapeados. Lista fechada: papel
# em texto livre viraria "contratante", "CONTRATANTE" e "parte contratante"
# como tres coisas diferentes na hora de consultar.
PAPEIS = {
    "autor": "plaintiff", "autora": "plaintiff", "requerente": "plaintiff",
    "exequente": "plaintiff", "reclamante": "plaintiff",
    "reu": "defendant", "ré": "defendant", "re": "defendant",
    "requerido": "defendant", "requerida": "defendant", "executado": "defendant",
    "reclamado": "defendant", "reclamada": "defendant",
    "contratante": "contracting_party", "contratada": "contractor",
    "contratado": "contractor", "locador": "lessor", "locadora": "lessor",
    "locatario": "lessee", "locataria": "lessee",
    "vendedor": "seller", "vendedora": "seller", "comprador": "buyer",
    "compradora": "buyer", "outorgante": "grantor", "outorgada": "grantee",
    "outorgado": "grantee", "cedente": "assignor", "cessionario": "assignee",
    "credor": "creditor", "devedor": "debtor", "fiador": "guarantor",
    "advogado": "lawyer", "advogada": "lawyer", "testemunha": "witness",
}

INSTRUCAO = (
    "Liste as PARTES do documento abaixo: quem contrata, quem e contratado, quem "
    "processa, quem e processado, quem outorga, quem recebe. Para cada uma devolva:\n"
    "  nome  - o nome como esta escrito no documento\n"
    "  papel - uma palavra: autor, reu, contratante, contratado, locador, locatario, "
    "vendedor, comprador, outorgante, outorgado, credor, devedor, fiador, advogado\n"
    "  tipo  - pessoa ou empresa\n"
    "  trecho - a frase do documento, COPIADA LETRA POR LETRA, onde o nome aparece\n\n"
    "Nao invente parte que nao esteja no texto. Se nao houver nenhuma, devolva lista vazia. "
    "O trecho tem de existir no documento exatamente como voce escrever."
)

FORMA = '[{"nome": "...", "papel": "...", "tipo": "pessoa", "trecho": "..."}]'


def _familia(papel_br: str) -> tuple[str, ...]:
    """As palavras que dizem o mesmo papel - "reu", "requerido", "executado"."""
    canonico = PAPEIS.get(papel_br)
    if not canonico:
        return (papel_br,) if papel_br else ()
    return tuple(p for p, c in PAPEIS.items() if c == canonico)


def papel_esta_escrito(texto_plano: str, nome: str, papel_br: str, alcance: int = 260) -> bool:
    """
    O documento diz, perto do nome, que aquela parte tem aquele papel?

    Esta e uma peneira deterministica que o conferidor de modelo nao substitui,
    e a medicao mostrou por que: com o modelo pequeno desta maquina, uma
    procuracao saiu com "EMPRESA X - reu". O trecho citado era real, o nome era
    real, e o conferidor disse SIM. So que a palavra "reu" nao aparece em
    lugar nenhum daquele documento.

    Em documento juridico o papel e SEMPRE escrito - "doravante denominada
    CONTRATANTE", "OUTORGANTE", "REQUERIDO" -, e quase sempre a poucas
    palavras do nome. Nao estando escrito ali, o papel nao e explicito: pode
    ate estar certo, mas e deducao, e deducao nao responde nivel 0.
    """
    familia = _familia(_plano(papel_br))
    if not familia:
        return False
    alvo = _plano(nome)[:60]
    if not alvo:
        return False
    posicao = texto_plano.find(alvo)
    while posicao >= 0:
        janela = texto_plano[max(0, posicao - alcance): posicao + len(alvo) + alcance]
        if any(re.search(r"\b" + re.escape(palavra) + r"[as]?\b", janela) for palavra in familia):
            return True
        posicao = texto_plano.find(alvo, posicao + 1)
    return False


def extrair(pedido: Pedido) -> Resultado:
    if pedido.client is None:
        return Resultado(status="skipped", erro="sem assistente ligado")

    # A qualificacao esta no comeco. Mandar o processo inteiro nao caberia na
    # janela e traria toda pessoa citada no meio da fundamentacao como parte.
    trecho = pedido.texto[: min(pedido.limite or LEITURA_PADRAO, 5000)]
    try:
        bruto = pedido.client.ask_json(INSTRUCAO, trecho, FORMA)
    except Exception as exc:
        return Resultado(status="failed", erro=str(exc)[:160])

    linhas = bruto if isinstance(bruto, list) else (bruto or {}).get("partes", [])
    if not isinstance(linhas, list):
        return Resultado(status="failed", erro="o modelo nao devolveu uma lista")

    plano = _plano(pedido.texto)
    itens: list[Item] = []
    vistos: set[str] = set()
    for i, linha in enumerate(linhas[:12], start=1):
        if not isinstance(linha, dict):
            continue
        nome = limpar(str(linha.get("nome") or linha.get("name") or ""))[:120]
        if not nome or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        papel = limpar(str(linha.get("papel") or linha.get("role") or "")).lower()
        tipo = limpar(str(linha.get("tipo") or linha.get("entity_type") or "")).lower()
        escrito = papel_esta_escrito(plano, nome, papel)
        dados = {
            "name": nome,
            "role": PAPEIS.get(_plano(papel), papel or "party"),
            "role_br": papel,
            "entity_type": "organization" if tipo.startswith("emp") else "person",
        }
        if not escrito:
            dados["role_note"] = "o papel não está escrito perto do nome no documento"
        itens.append(Item(
            id=f"party_{i:03d}",
            dados=dados,
            quote=limpar(str(linha.get("trecho") or linha.get("quote") or "")),
            # Nasce dizendo-se explicito so quando o documento escreve o papel.
            # O resto e deducao do modelo, e deducao nao vira fato: quem decide
            # o veredito final ainda e a verificacao de span, que roda depois.
            certainty="explicit" if escrito else "inferred",
            verified=False,
            produced_by=ID,
        ))
    return Resultado(itens=itens, modelo=getattr(pedido.client, "model", ""))


def _plano(texto: str) -> str:
    import unicodedata

    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())
