"""
Sugestoes de resposta durante uma gravacao (pacote de telas de 01/10/2026,
`Conversa - Gravando`, docs/PLANO-TELAS-ASSISTENTE.md, T2).

Enquanto a reuniao e transcrita, cada fala que chega pode cruzar com os
documentos do caso: "a parcela de setembro nao esta atrasada, o contrato fala
em vencimento no fim do mes" contra a clausula que diz "dia 12". Quando cruza,
a conversa mostra, logo abaixo da fala, o que o advogado pode responder -
citando a clausula e o documento.

Como no resto do programa, a regra vem antes do modelo:

  - so olha a fala que tem numero, data, percentual ou uma palavra de
    contrato (multa, juros, vencimento, prazo, parcela, clausula...);
  - so olha os documentos do caso (os do Servico do cliente, ou os que tem o
    nome do cliente), e so chama o modelo quando a busca acha trecho;
  - o modelo responde em JSON (tipo, base, resposta, trecho), e a resposta so
    passa se for ancorada no trecho: um numero da resposta tem de estar no
    trecho, ou a resposta e descartada. Modelo de 3 bilhoes inventa clausula.

O modelo entra pela fila de sempre (src/fila_modelo.py): uma sugestao espera
a vez como qualquer pergunta, e a pessoa ve a fala antes da sugestao.
"""

from __future__ import annotations

import re
import unicodedata

GATILHOS = (
    "multa", "juro", "vencimento", "vence", "venceu", "vencid", "prazo", "parcela", "clausula", "contrato",
    "atras", "valor", "pagament", "pagar", "pago", "paguei", "rescis", "acordo", "desconto", "reajuste",
    "indeniza", "honorari", "notifica", "cobranc", "por cento", "porcento", "aditivo", "suspens", "entrega",
)
RE_NUMERO = re.compile(r"\d")
RE_NUMEROS = re.compile(r"\d+(?:[.,]\d+)*")
GENERICOS = {"ltda", "eireli", "me", "sa", "s/a", "cooperativa", "associacao", "empresa", "escritorio", "de", "da", "do",
             "dos", "das", "e", "cliente", "sociedade", "grupo", "comercio", "servicos", "industria"}
TIPOS = {"refutacao": "refutação", "sugestao": "sugestão"}

SISTEMA = (
    "Você acompanha uma reunião de um escritório de advocacia brasileiro. Recebe uma fala dita na reunião e trechos "
    "dos documentos do caso, numerados [T1], [T2]... Responda só com JSON.\n"
    "- Se a fala afirma algo que os trechos contradizem (data, valor, percentual, prazo, cláusula), tipo = \"refutacao\".\n"
    "- Se a fala abre espaço para um acordo ou um pedido que os trechos permitem, tipo = \"sugestao\".\n"
    "- Se os trechos não dizem nada sobre a fala, tipo = \"nada\".\n"
    "Em \"resposta\", escreva em primeira pessoa a frase que o advogado pode dizer, curta, citando a cláusula, o valor "
    "ou a data exatamente como estão no trecho. Não invente nada que não esteja nos trechos. Em \"base\", três a cinco "
    "palavras que dizem por quê (por exemplo: \"contradiz o contrato\", \"valor diferente do contrato\", \"margem para acordo\"). "
    "Em \"trecho\", o número do trecho que sustenta a resposta."
)
ESQUEMA = '{"tipo": "refutacao | sugestao | nada", "base": "...", "resposta": "...", "trecho": 1}'


def _plano(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem.lower()).strip()


def vale_olhar(texto: str) -> bool:
    """A fala diz alguma coisa que da para conferir num documento?"""
    p = _plano(texto)
    if len(p.split()) < 5:
        return False
    return bool(RE_NUMERO.search(p)) or any(g in p for g in GATILHOS)


def _palavras_do_nome(nome: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", _plano(nome)) if len(w) > 2 and w not in GENERICOS]


def documentos_do_caso(estado, cliente: str = "", cadastro_id=None, limite: int = 6) -> list[str]:
    """
    Os documentos do caso: os vinculados aos Servicos do cliente e, depois,
    os do Acervo que trazem o nome dele no nome do arquivo. So os que estao
    abertos (a busca so le esses).
    """
    abertos = [d.name for d in estado.searcher.documents]
    conjunto = set(abertos)
    nomes: list[str] = []
    if cadastro_id:
        try:
            for s in estado.servicos.listar():
                if s.get("cadastro_id") == cadastro_id:
                    nomes += [a["nome"] for a in estado.servicos.arquivos_de(s["id"])]
        except Exception:  # noqa: BLE001 - sem Servicos, segue pelo nome
            pass
    palavras = _palavras_do_nome(cliente)
    if palavras:
        for nome in abertos:
            plano = _plano(nome)
            if all(p in plano for p in palavras) or (len(palavras) > 1 and sum(p in plano for p in palavras) >= len(palavras) - 1
                                                    and len(palavras[0]) > 4 and palavras[0] in plano):
                nomes.append(nome)
    vistos, saida = set(), []
    for n in nomes:
        if n in conjunto and n not in vistos:
            vistos.add(n)
            saida.append(n)
    return saida[:limite]


def _ancorada(resposta: str, trecho: str) -> bool:
    """Um numero da resposta tem de estar no trecho (ou a resposta nao traz numero nenhum)."""
    numeros = [n.replace(".", "").replace(",", "") for n in RE_NUMEROS.findall(resposta)]
    if not numeros:
        return True
    do_trecho = {n.replace(".", "").replace(",", "") for n in RE_NUMEROS.findall(trecho)}
    return any(n in do_trecho for n in numeros)


def sugerir(texto: str, documentos: list[str], searcher, perguntar_json, anteriores: str = "") -> dict | None:
    """
    A sugestao para uma fala, ou None. `perguntar_json(instrucao, contexto,
    esquema, sistema)` e o cliente do modelo (ask_json).
    """
    if not vale_olhar(texto) or not documentos:
        return None
    hits = [h for h in searcher.search(texto, top_k=4, per_doc_limit=2, documentos=documentos) if h.score > 0]
    if not hits:
        return None
    contexto = "\n\n".join(f"[T{i}] {h.doc_name}\n{h.chunk.text[:900]}" for i, h in enumerate(hits, 1))
    pedido = f'Fala na reunião: "{texto.strip()}"'
    if anteriores:
        pedido += f"\nO que foi dito logo antes: {anteriores.strip()[:600]}"
    pedido += "\n\nO que o advogado pode responder?"
    try:
        r = perguntar_json(pedido, contexto, ESQUEMA, SISTEMA)
    except Exception:  # noqa: BLE001 - sem modelo agora: sem sugestao, a fala continua
        return None
    if not isinstance(r, dict):
        return None
    tipo = _plano(r.get("tipo", "")).replace("ç", "c")
    tipo = "refutacao" if tipo.startswith("refut") else ("sugestao" if tipo.startswith("suge") else "")
    resposta = " ".join(str(r.get("resposta") or "").split()).strip().strip('"“”')
    if not tipo or len(resposta) < 20:
        return None
    try:
        indice = int(r.get("trecho") or 1)
    except (TypeError, ValueError):
        indice = 1
    hit = hits[indice - 1] if 1 <= indice <= len(hits) else hits[0]
    if not _ancorada(resposta, hit.chunk.text):
        return None
    pagina = hit.chunk.pagina_inicio
    return {
        "tipo": tipo,
        "rotulo": TIPOS[tipo],
        "base": " ".join(str(r.get("base") or "").split())[:60] or ("contradiz o documento" if tipo == "refutacao" else "margem para acordo"),
        "texto": resposta[:600],
        "fonte": {"documento": hit.doc_name, "pagina": pagina, "trecho": hit.chunk.text[:400]},
    }


PONTOS_SISTEMA = (
    "Você resume, para um advogado que vai entrar numa reunião, os pontos de um caso a partir dos trechos dos documentos. "
    "Escreva UMA frase curta, com os números exatamente como estão nos trechos: valores, datas, percentuais, prazos e "
    "cláusulas. Separe os pontos por \" · \". Não invente nada. Responda só com JSON."
)


def pontos_do_caso(documentos: list[str], searcher, perguntar_json) -> str:
    """Os pontos do caso numa frase (valores, datas, multa, prazos), so dos trechos."""
    if not documentos:
        return ""
    hits = [h for h in searcher.search("valor parcela vencimento multa juros prazo clausula atraso pagamento",
                                       top_k=5, per_doc_limit=2, documentos=documentos) if h.score > 0]
    if not hits:
        return ""
    contexto = "\n\n".join(f"[T{i}] {h.doc_name}\n{h.chunk.text[:700]}" for i, h in enumerate(hits, 1))
    try:
        r = perguntar_json("Quais são os pontos do caso?", contexto, '{"pontos": "..."}', PONTOS_SISTEMA)
    except Exception:  # noqa: BLE001
        return ""
    bruto = (r or {}).get("pontos") if isinstance(r, dict) else ""
    # O modelo pequeno as vezes devolve os pontos como objeto ou lista, e nao
    # como a frase pedida: vira a frase, "chave: valor · chave: valor".
    if isinstance(bruto, dict):
        bruto = " · ".join(f"{k}: {v}" for k, v in bruto.items())
    elif isinstance(bruto, list):
        bruto = " · ".join(str(x) for x in bruto)
    texto = " ".join(str(bruto or "").split())
    if not texto or not _ancorada(texto, " ".join(h.chunk.text for h in hits)):
        return ""
    return texto[:320]
