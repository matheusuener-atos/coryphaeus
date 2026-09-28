"""
O contrato de resposta com fonte: cada afirmacao termina na marca do trecho
que a sustenta, `[T1]`, `[T2]`... (I8).

O modelo recebe os trechos numerados - `[T3] (Contrato ACME.pdf, p. 12)` e o
texto - e a instrucao de terminar cada frase com a marca de onde ela saiu.
Antes de a resposta ficar na conversa, tres conferencias, em codigo:

1. **Frase sem marca** fica, com o rotulo "sem fonte": quem le sabe que
   aquela frase nao aponta para lugar nenhum.
2. **Marca que nao existe** (`[T9]` com seis trechos): a resposta e refeita
   uma vez, com menos trechos - o modelo pequeno se perde em contexto longo.
3. **Lei, artigo, sumula ou numero de processo que nao esta em nenhum
   trecho** sai da resposta, e fica registrado. Os achadores sao os mesmos da
   camada de inteligencia (regras_leis, regras_processo): o que conta como
   citacao ali conta aqui.

O que NAO se faz: dar ao modelo uma frase pronta de fuga ("se nao achar,
diga 'nao encontrei'"). Medido em llama_client.py: com a frase pronta, o
modelo de 3B desiste cedo demais. A instrucao so pede a marca.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

RE_MARCA = re.compile(r"\[T(\d{1,3})\]")
SEM_FONTE = "[sem fonte]"

REGRA = (
    "Os trechos abaixo vem numerados: [T1], [T2] e assim por diante. Termine cada frase "
    "da resposta com a marca do trecho de onde ela saiu, por exemplo: \"A multa e de 2% [T3].\" "
    "Use so as marcas que aparecem nos trechos. Cada trecho pertence ao documento cujo nome esta "
    "acima dele: nao use o trecho de um documento para responder sobre outro."
)

# Frases que nao afirmam nada sobre o documento: nao pedem marca.
RE_NAO_AFIRMA = re.compile(
    r"^\s*(?:[-•*]\s*)?(?:sim|nao|não|ok|segue|veja|conforme abaixo|resumindo|em resumo)[\s.,:!]*$",
    re.IGNORECASE)


def numerar(hits, max_chars: int = 0) -> tuple[str, dict[int, object]]:
    """
    O contexto com os trechos numerados, e o mapa numero -> trecho.

    Nao cabendo tudo em `max_chars`, cada trecho cede o mesmo tanto - como no
    `format_context` de sempre -, e nenhum some calado.
    """
    AVISO = " […]"
    # Agrupados por documento, com o nome do arquivo em cima, como no
    # contexto de sempre: soltos, o modelo de 3B misturava documentos -
    # medido no roteiro, a multa de 2% do contrato de transporte saiu como a
    # multa do aluguel da Clinica. A numeracao continua a da ordem dos
    # trechos, que e a das fontes na tela.
    blocos = []
    for i, hit in enumerate(hits, start=1):
        chunk = getattr(hit, "chunk", hit)
        pagina = getattr(chunk, "pagina_inicio", None)
        blocos.append((chunk.doc_name, f"[T{i}]" + (f" (p. {pagina})" if pagina else ""), chunk.text))
    total = sum(len(c) + len(t) + 2 for _, c, t in blocos)
    if max_chars and total > max_chars and blocos:
        fatia = max(120, (max_chars - sum(len(c) + len(d) + 10 for d, c, _ in blocos)) // len(blocos))
        blocos = [(d, c, t if len(t) <= fatia else t[:max(0, fatia - len(AVISO))] + AVISO) for d, c, t in blocos]
    por_documento: dict[str, list[str]] = {}
    for documento, cabeca, texto in blocos:
        por_documento.setdefault(documento, []).append(f"{cabeca}\n{texto}")
    mapa = {i: hit for i, hit in enumerate(hits, start=1)}
    return "\n\n".join(f"--- {d} ---\n" + "\n\n".join(partes) for d, partes in por_documento.items()), mapa


def atribuir(resposta: str, trechos: list[str]) -> str:
    """
    As marcas [Tn] postas em codigo, frase a frase, sem pedir nada ao modelo.

    Medido no roteiro (28/09/2026): pedir as marcas ao llama3.2:3b derrubou o
    banco de provas de 40/41 para 38/41 - a instrucao a mais deixou as
    respostas secas ("Nao achou.") e fez o modelo misturar documentos. Aqui
    o modelo responde como sempre respondeu, e cada frase ganha a marca do
    trecho que a sustenta: o que tem TODOS os numeros dela e mais palavras
    em comum. Frase sem trecho assim fica sem marca - e a conferencia a
    rotula "sem fonte".
    """
    from inteligencia import molde
    from lexico import normalizar

    base = [(set(normalizar(t).split()), molde.numeros_de(t)) for t in trechos]
    saida = []
    for frase in _frases(resposta):
        corpo = frase.strip()
        if not corpo or RE_MARCA.search(corpo) or len(corpo.split()) < 3:
            saida.append(frase)
            continue
        palavras = {p for p in normalizar(corpo).split() if not p.isdigit() and len(p) > 2}
        numeros = molde.numeros_de(corpo)
        melhor, pontos = 0, 0
        for i, (termos, nums) in enumerate(base, start=1):
            if numeros and not numeros <= nums:
                continue
            comuns = len(palavras & termos) + 2 * len(numeros)
            if comuns > pontos:
                melhor, pontos = i, comuns
        if melhor and pontos >= 3:
            fim = len(frase.rstrip())
            corte = fim - 1 if fim and frase[fim - 1] in ".!?" else fim
            frase = frase[:corte].rstrip() + f" [T{melhor}]" + frase[corte:]
        saida.append(frase)
    return "".join(saida)


def _frases(texto: str) -> list[str]:
    """As frases da resposta, com a pontuacao e a quebra de linha que tinham."""
    partes = re.split(r"(?<=[.!?])(\s+)|(\n+)", texto or "")
    frases, atual = [], ""
    for p in partes:
        if p is None:
            continue
        atual += p
        if p.strip() == "" and atual.strip():
            frases.append(atual)
            atual = ""
    if atual:
        frases.append(atual)
    # "art. 412", "p. 3", "n. 5", "Dra. Helena": o ponto da abreviatura nao
    # fecha a frase - junta de volta com a seguinte.
    juntas: list[str] = []
    for frase in frases:
        if juntas and _RE_ABREVIATURA.search(juntas[-1]):
            juntas[-1] += frase
        else:
            juntas.append(frase)
    return juntas


_RE_CONECTIVO = re.compile(
    r"(?:[,;]?\s*\b(?:nos termos|na forma|com base|com fundamento|conforme|segundo|de acordo com|previst[oa]s?|"
    r"como (?:diz|preve|prevê|dispoe|dispõe)|a teor)\b)?(?:\s+\b(?:d[oa]s?|n[oa]s?|em|o|a|os|as)\b)?\s*$",
    re.IGNORECASE)

_RE_ABREVIATURA = re.compile(
    r"\b(?:art|arts|n|nº|no|p|pp|fls?|inc|al|dr|dra|sr|sra|s|cf|ex|sec|cap|par|tit|lei|c|v)\.\s*$",
    re.IGNORECASE)


def _citacoes_em(texto: str) -> list[dict]:
    """Leis, artigos, sumulas e numeros de processo citados, com a posicao."""
    from inteligencia.extratores import regras_leis, regras_processo

    achados = []
    for a in regras_leis.achar(texto):
        d = a["dados"]
        achados.append({"inicio": a["inicio"], "fim": a["fim"], "tipo": d.get("kind"),
                        "chave": (d.get("kind"), d.get("article", ""), d.get("instrument_id", ""),
                                  d.get("number", ""), d.get("court", ""))})
    for a in regras_processo.achar(texto):
        achados.append({"inicio": a["inicio"], "fim": a["fim"], "tipo": "case", "chave": ("case", a["numero"])})
    return achados


def _existe_nos_trechos(citacao: dict, nos_trechos: list[dict]) -> bool:
    chave = citacao["chave"]
    for outra in nos_trechos:
        o = outra["chave"]
        if chave[0] != o[0]:
            continue
        if chave[0] == "case":
            if chave[1] == o[1]:
                return True
            continue
        tipo, artigo, instrumento, numero, tribunal = chave
        _, artigo2, instrumento2, numero2, tribunal2 = o
        if tipo == "article" and artigo == artigo2 and (not instrumento or not instrumento2 or instrumento == instrumento2):
            return True
        if tipo == "law" and instrumento == instrumento2:
            return True
        if tipo == "precedent" and numero == numero2 and (not tribunal or not tribunal2 or tribunal == tribunal2):
            return True
    return False


@dataclass
class Revisao:
    texto: str
    marcas_validas: int = 0
    marcas_invalidas: list[int] = field(default_factory=list)
    sem_fonte: int = 0
    removidas: list[str] = field(default_factory=list)
    frases: int = 0

    @property
    def refazer(self) -> bool:
        """Regra 2: marca que nao existe no contexto."""
        return bool(self.marcas_invalidas)

    @property
    def sem_fundamento(self) -> bool:
        """Nenhuma frase aponta para trecho nenhum: a resposta nao se sustenta."""
        return self.frases > 0 and self.marcas_validas == 0


def revisar(resposta: str, trechos: list[str]) -> Revisao:
    """
    As tres conferencias sobre a resposta, contra os textos dos trechos que o
    modelo recebeu (na ordem das marcas: `trechos[0]` e o [T1]).
    """
    n = len(trechos)
    citados_nos_trechos = [c for t in trechos for c in _citacoes_em(t)]
    saida: list[str] = []
    rev = Revisao(texto="")
    for frase in _frases(resposta):
        corpo = frase.strip()
        if not corpo:
            saida.append(frase)
            continue
        marcas = [int(m) for m in RE_MARCA.findall(corpo)]
        invalidas = [m for m in marcas if m < 1 or m > n]
        rev.marcas_invalidas += invalidas
        validas = [m for m in marcas if 1 <= m <= n]
        rev.marcas_validas += len(validas)
        # Regra 3: a citacao que nao existe em trecho nenhum sai da frase.
        for citacao in sorted(_citacoes_em(frase), key=lambda c: -c["inicio"]):
            if not _existe_nos_trechos(citacao, citados_nos_trechos):
                trecho = frase[citacao["inicio"]:citacao["fim"]]
                rev.removidas.append(RE_MARCA.sub("", trecho).strip())
                # A marca que o achador engoliu junto ("Codigo Civil [T1]")
                # fica; o conectivo que sobraria pendurado ("nos termos do"),
                # nao.
                marcas_dentro = " ".join(RE_MARCA.findall(trecho) and [m.group(0) for m in RE_MARCA.finditer(trecho)])
                antes = _RE_CONECTIVO.sub("", frase[:citacao["inicio"]]).rstrip(" ,;(")
                frase = antes + (" " + marcas_dentro if marcas_dentro else "") + frase[citacao["fim"]:]
                # A citacao que abria a frase ("Conforme o art. 999, cabe...")
                # nao pode deixar a virgula e a minuscula no comeco.
                frase = re.sub(r"^(\s*)[,;]\s*(\w)", lambda m: m.group(1) + m.group(2).upper(), frase)
        afirma = len(re.sub(RE_MARCA, "", corpo).split()) >= 3 and not RE_NAO_AFIRMA.match(corpo)
        rev.frases += 1 if afirma else 0
        # Regra 1: frase que afirma sem marca ganha o rotulo.
        if afirma and not validas:
            fim = len(frase.rstrip())
            frase = frase[:fim] + " " + SEM_FONTE + frase[fim:]
            rev.sem_fonte += 1
        saida.append(frase)
    rev.texto = "".join(saida)
    return rev
