"""
A IA ajudando sem ser perguntada (I9) - tudo a partir do que a camada de
inteligencia ja conferiu, sem modelo.

1. **O cartao do documento:** tipo, partes, valores, numero do processo,
   datas e pedidos, cada um com a pagina. So fatos conferidos: o que o modelo
   achou e nao se confirmou no texto nao aparece - um cartao com um valor
   errado ensina a pessoa a desconfiar do cartao inteiro.
2. **Corrigir um fato** grava a correcao como `manual` no metadata e
   acrescenta uma pergunta ao conjunto real de medicao
   (data/medicao/conjunto-real.jsonl, docs/medicao.md): cada correcao e um
   caso que o programa errou, e vira regua para a proxima versao.
3. **Perguntas sugeridas** pelo tipo do documento - mas so as que tem
   resposta de nivel 0, montada na hora pelos fatos conferidos. Sugerir uma
   pergunta que leva um minuto para responder nao e ajuda.
4. **Prazos e vencimentos** conferidos viram PROPOSTA na fila de Aprovacoes
   ("Vencimento do Contrato ACME em 12/11 - anotar?"). Nada e gravado na
   Agenda sem o sim de alguem.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from inteligencia import molde, roteador

SECOES = ("parties", "amounts", "dates", "requests")
ROTULO_DA_SECAO = {"classification": "tipo", "case": "processo", "parties": "parte", "amounts": "valor",
                   "dates": "data", "requests": "pedido"}

# Os tipos de documento que a camada conhece, na linguagem da tela.
TIPOS_BR = {"contrato": "contrato", "peticao": "petição", "procuracao": "procuração", "sentenca": "sentença",
            "notificacao": "notificação", "decisao": "decisão", "acordo": "acordo"}

# As perguntas que valem para cada tipo; so as que tem resposta de nivel 0
# chegam a tela.
SUGESTOES = {
    "contrato": ["qual o valor do contrato?", "quem são as partes?", "quando o contrato foi assinado?",
                 "quais leis são citadas?", "qual a vigência?", "qual a multa?", "qual o foro?"],
    "peticao": ["quais os pedidos?", "qual o valor da causa?", "quais leis são citadas?",
                "qual o número do processo?", "qual o tribunal?", "quem são as partes?"],
    "": ["quem são as partes?", "qual o valor?", "quando foi assinado?", "quais leis são citadas?",
         "qual o número do processo?"],
}


def _tipo(meta) -> str:
    objeto = meta.por_secao("classification") or {}
    bruto = str(objeto.get("document_type") or "")
    for chave in TIPOS_BR:
        if chave in bruto:
            return chave
    return ""


def _item(secao: str, id_: str, rotulo: str, valor: str, pagina, quote: str = "") -> dict:
    return {"secao": secao, "id": id_, "rotulo": rotulo, "valor": valor, "pagina": pagina, "quote": quote,
            "secao_rotulo": ROTULO_DA_SECAO.get(secao, secao)}


def cartao(meta, nome: str) -> dict:
    """O cartao do documento: so o que esta conferido no texto, com a pagina."""
    itens: list[dict] = []
    classificacao = meta.por_secao("classification") or {}
    if classificacao.get("document_type") and classificacao.get("verified"):
        bruto = str(classificacao["document_type"])
        itens.append(_item("classification", "document_type", "tipo",
                           str(classificacao.get("document_type_br") or TIPOS_BR.get(bruto, bruto)),
                           (classificacao.get("source") or {}).get("page")))
    processo = meta.por_secao("case") or {}
    if processo.get("case_number") and processo.get("verified"):
        itens.append(_item("case", "case_number", "número do processo", str(processo["case_number"]),
                           (processo.get("source") or {}).get("page"), processo.get("quote", "")))
    for secao in SECOES:
        for item in meta.fatos(secao):
            fato = roteador._fato_do_item(meta, item, nome, secao)
            valor = molde._data_br(fato.valor) if secao == "dates" else fato.valor
            itens.append(_item(secao, item.id, fato.rotulo, valor, fato.pagina, fato.quote))
    return {"documento": nome, "tipo": _tipo(meta), "itens": itens,
            "manual": [i["id"] for i in itens if _manual(meta, i)]}


def _manual(meta, item: dict) -> bool:
    if item["secao"] == "case":
        return (meta.por_secao("case") or {}).get("produced_by") == "manual"
    if item["secao"] == "classification":
        return (meta.por_secao("classification") or {}).get("produced_by") == "manual"
    return any(i.id == item["id"] and i.produced_by == "manual" for i in meta.colecao(item["secao"]))


def _chave_do_valor(secao: str, item) -> str:
    if secao == "amounts":
        return "value_text"
    if secao == "dates":
        return "date"
    for chave in ("name", "text", "value_text", "number", "value", "title"):
        if item.dados.get(chave):
            return chave
    return "text"


def corrigir(biblioteca, meta, nome: str, secao: str, id_: str, novo: str, conjunto: Path | str) -> dict:
    """
    Grava o valor certo como `manual` e acrescenta a pergunta ao conjunto real.
    Devolve o item corrigido e a linha acrescentada.
    """
    novo = " ".join(str(novo or "").split())
    if not novo:
        raise ValueError("escreva o valor certo")
    if secao == "dates":
        # A tela mostra dd/mm/aaaa; o metadata guarda AAAA-MM-DD.
        import re

        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", novo)
        if m:
            novo = f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        try:
            date.fromisoformat(novo)
        except ValueError as exc:
            raise ValueError("escreva a data como dd/mm/aaaa") from exc
    quote, rotulo, pagina = "", "", None
    if secao in ("case", "classification"):
        objeto = dict(meta.por_secao(secao) or {})
        if not objeto:
            raise ValueError("esse dado não existe neste documento")
        objeto[id_] = novo
        objeto.update(produced_by="manual", verified=True)
        setattr(meta, secao, objeto)
        quote, pagina = objeto.get("quote", ""), (objeto.get("source") or {}).get("page")
        rotulo = "número do processo" if secao == "case" else "tipo"
    else:
        itens = meta.colecao(secao)
        alvo = next((i for i in itens if i.id == id_), None)
        if alvo is None:
            raise ValueError("esse dado não existe neste documento")
        alvo.dados[_chave_do_valor(secao, alvo)] = novo
        alvo.produced_by = "manual"
        alvo.verified = True
        alvo.certainty = "explicit"
        meta.guardar(secao, itens)
        fato = roteador._fato_do_item(meta, alvo, nome, secao)
        quote, rotulo, pagina = alvo.quote, fato.rotulo, fato.pagina
    biblioteca.gravar(meta, nota=f"correcao manual: {secao}/{id_}")
    linha = _linha_do_conjunto(nome, secao, rotulo, novo, quote)
    caminho = Path(conjunto)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as saida:
        saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return {"item": _item(secao, id_, rotulo, novo, pagina, quote), "linha": linha}


def _linha_do_conjunto(nome: str, secao: str, rotulo: str, valor: str, quote: str) -> dict:
    titulo = Path(nome).stem
    pergunta = {
        "case": f"qual o número do processo de {titulo}?",
        "classification": f"que tipo de documento é {titulo}?",
        "parties": f"quem é o {rotulo or 'parte'} em {titulo}?",
        "amounts": f"qual o {rotulo or 'valor'} de {titulo}?",
        "dates": f"qual a data de {rotulo or 'referência'} de {titulo}?",
        "requests": f"quais os pedidos de {titulo}?",
    }.get(secao, f"qual o {rotulo} de {titulo}?")
    return {"pergunta": pergunta, "caminho": "documentos", "tipo": "lista" if secao == "requests" else "fato",
            "alguma": [valor], "todas": [], "nunca": [], "documentos": [nome],
            "trechos_esperados": [quote] if quote else [],
            "origem": "correção manual", "quando": datetime.now().isoformat(timespec="seconds")}


def sugestoes(saber, doc, limite: int = 4) -> list[str]:
    """As perguntas do tipo do documento que respondem na hora, pelo molde."""
    metas, nomes = saber.metadados_de([doc])
    if not metas:
        return []
    saida = []
    for pergunta in SUGESTOES.get(_tipo(metas[0]), SUGESTOES[""]):
        pacote = roteador.resolver(pergunta, metas, nomes=nomes, em_foco=True)
        if pacote.responde_sozinho and (molde.montar(pacote, pergunta) or molde.lista(pacote)):
            saida.append(pergunta)
        if len(saida) >= limite:
            break
    return saida


def prazos(meta, nome: str, hoje: date | None = None) -> list[dict]:
    """Os prazos e vencimentos conferidos que ainda nao passaram."""
    hoje = hoje or date.today()
    saida = []
    for item in meta.fatos("dates"):
        tipo = item.dados.get("kind")
        if tipo not in ("deadline", "term"):
            continue
        try:
            quando = date.fromisoformat(str(item.dados.get("date") or "")[:10])
        except ValueError:
            continue
        if quando < hoje:
            continue
        titulo = Path(nome).stem
        rotulo = "Vencimento" if tipo == "deadline" else "Fim da vigência"
        saida.append({"titulo": f"{rotulo} de {titulo} em {quando:%d/%m/%Y}", "data": quando.isoformat(),
                      "documento": nome, "pagina": item.source.page, "quote": item.quote, "item": item.id})
    return saida
