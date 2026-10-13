"""
O banco de provas do editor (docs/PLANO-EDITOR.md, E0): as checagens.

Para cada tarefa, o que um sistema de edição devolveu (o documento, com as
sugestões que ele marcou, e a frase da resposta) é conferido sem modelo:

  lugar      os blocos que tinham de mudar mudaram, e o conteúdo pedido está lá
  ordem      o texto novo entrou entre os blocos certos
  sem_dano   nenhum outro bloco mudou (a renumeração é tolerada quando a
             tarefa mexe na numeração)
  numeracao  as cláusulas em sequência e nenhuma referência para o nada
  marcado    recusar todas as sugestões devolve o documento original - ou
             seja, toda mudança está marcada e é reversível uma a uma
  honesto    o que a resposta diz que fez bate com o que mudou
  aponta     (pergunta) o documento não mudou e a resposta cita o bloco certo

`acerto` é lugar + ordem + sem_dano (+ numeracao, quando a tarefa pede). As
outras são propriedades do sistema e entram no resumo à parte.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

LEGAL = Path(__file__).resolve().parents[2]
if str(LEGAL / "src") not in sys.path:
    sys.path.insert(0, str(LEGAL / "src"))

import blocos as B  # noqa: E402
import esboco as E  # noqa: E402
import redacao  # noqa: E402

CORPUS = Path(__file__).parent / "corpus"


def documento(nome: str) -> list:
    return B.ler((CORPUS / f"{nome}.html").read_text(encoding="utf-8"))


@dataclass
class Saida:
    html: str = ""                 # o documento como o sistema deixou (com as sugestões)
    resposta: str = ""             # o que a conversa disse
    mudou: bool | None = None      # o que a resposta afirma (None: não afirma)
    cita: list = field(default_factory=list)   # os blocos que a resposta aponta
    segundos: float = 0.0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    erro: str = ""
    detalhe: dict = field(default_factory=dict)


def _n(texto: str) -> str:
    """Para comparar conteúdo: espaço único, aspas e travessões de um tipo só."""
    t = (texto or "").replace(" ", " ")
    t = t.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}))
    return " ".join(t.split())


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


_ORDINAL = "|".join(sorted(redacao._FORMAS_EXTENSO, key=len, reverse=True))
_NUMERACAO = [
    re.compile(r"(cl[áa]usula)\s+(?:\d{1,3}\s*[ªaº°]?|" + _ORDINAL + r")\b", re.I),
    re.compile(r"^\s*\d{1,3}\s*(?=[.)\-–—]\s)"),
    re.compile(r"(\d{1,3})\s*[ªaº°]\s+(cl[áa]usula)", re.I),
]


def _so_numeracao(a: str, b: str) -> bool:
    """A diferença entre os dois textos é só o número de cláusula (renumeração)?"""
    def tirar(t: str) -> str:
        t = _n(t)
        for padrao in _NUMERACAO:
            t = padrao.sub(lambda m: "§N§", t)
        return t
    return tirar(a) == tirar(b)


def _posicao(blocos_aceitos: list, alvo: str, original: dict) -> int:
    """O índice do bloco `alvo` no documento aceito: pelo nome, ou pelo texto original (bloco movido)."""
    for i, b in enumerate(blocos_aceitos):
        if b.id == alvo:
            return i
    texto = original.get(alvo, "")
    for i, b in enumerate(blocos_aceitos):
        if texto and (_n(b.texto) == _n(texto) or _so_numeracao(b.texto, texto)):
            return i
    return -1


def avaliar(t, saida: Saida) -> dict:
    original = documento(t.doc)
    o = {b.id: b.texto for b in original}
    feito = B.ler(saida.html) if saida.html else original
    aceito = B.aceito(feito)
    recusado = B.recusado(feito)
    a = {b.id: b.texto for b in aceito}
    texto_aceito = _n("\n".join(b.texto for b in aceito))
    texto_original = _n("\n".join(b.texto for b in original))
    mexeu = texto_aceito != texto_original

    res = {"id": t.id, "categoria": t.categoria, "erro": saida.erro, "segundos": round(saida.segundos, 1),
           "tokens": saida.tokens_entrada + saida.tokens_saida, "resposta": saida.resposta[:400]}

    res["marcado"] = _n("\n".join(b.texto for b in recusado)) == texto_original
    if saida.mudou is None:
        res["honesto"] = None
    else:
        res["honesto"] = bool(saida.mudou) == mexeu

    if t.pergunta:
        res["intacto"] = not mexeu
        res["aponta"] = bool(set(saida.cita or []) & set(t.cita))
        res["acerto"] = res["intacto"] and res["aponta"]
        res["sem_dano"] = res["intacto"]
        return res

    # lugar: os blocos que tinham de mudar mudaram (ou saíram). O conteúdo é
    # conferido sem caixa e sem acento: "Da Rescisão Antecipada" vale.
    nao_mudaram = [i for i in t.mudam if i in a and _n(a[i]) == _n(o.get(i, ""))]
    plano_aceito = _sem_acento(texto_aceito).lower()
    faltando = [c for c in t.contem if _sem_acento(_n(c)).lower() not in plano_aceito]
    sobrando = [c for c in t.nao_contem if _n(c) in texto_aceito]
    res["lugar"] = not nao_mudaram and not faltando and not sobrando and mexeu
    res["por_que"] = {k: v for k, v in (("nao_mudaram", nao_mudaram), ("faltando", faltando), ("sobrando", sobrando))
                      if v}
    if not mexeu:
        res["por_que"]["nada_mudou"] = True

    # ordem
    res["ordem"] = True
    if t.ordem:
        texto, depois, antes = t.ordem
        alvo = _sem_acento(_n(texto)).lower()
        onde = next((i for i, b in enumerate(aceito) if alvo in _sem_acento(_n(b.texto)).lower()), -1)
        i_depois = _posicao(aceito, depois, o)
        i_antes = _posicao(aceito, antes, o)
        res["ordem"] = onde >= 0 and i_depois >= 0 and i_antes >= 0 and i_depois < onde < i_antes
        if not res["ordem"]:
            res["por_que"]["ordem"] = {"onde": onde, "depois": i_depois, "antes": i_antes}

    # dano colateral
    livres = set(t.mudam) | set(t.podem)
    danos = []
    for b in original:
        if b.id in livres:
            continue
        if b.id not in a:
            # Saiu daqui mas o mesmo texto está em outro lugar: foi movido.
            movido = any(_n(x.texto) == _n(b.texto) or (t.renumera and _so_numeracao(x.texto, b.texto))
                         for x in aceito if x.id not in o)
            if not (movido and t.categoria == "mover"):
                danos.append(b.id)
            continue
        if _n(a[b.id]) != _n(b.texto) and not (t.renumera and _so_numeracao(a[b.id], b.texto)):
            danos.append(b.id)
    res["sem_dano"] = not danos
    if danos:
        res["por_que"]["danos"] = danos

    # numeração
    res["numeracao"] = True
    if t.numeracao:
        numeros = [c["numero"] for c in E.clausulas(aceito)]
        sequencia = bool(numeros) and numeros == list(range(1, len(numeros) + 1))
        quebradas = redacao.referencias_quebradas("\n".join(b.texto for b in aceito))
        res["numeracao"] = sequencia and not quebradas
        if not res["numeracao"]:
            res["por_que"]["numeracao"] = {"numeros": numeros, "quebradas": [q["texto"] for q in quebradas]}

    res["acerto"] = bool(res["lugar"] and res["ordem"] and res["sem_dano"] and res["numeracao"] and not saida.erro)
    return res


def resumo(resultados: list[dict]) -> dict:
    """Os números do banco: acerto por categoria e as propriedades do sistema."""
    def pct(itens, chave):
        valores = [r[chave] for r in itens if r.get(chave) is not None]
        return round(100 * sum(1 for v in valores if v) / len(valores), 1) if valores else None

    cats: dict[str, list] = {}
    for r in resultados:
        cats.setdefault(r["categoria"], []).append(r)
    edicao = [r for r in resultados if r["categoria"] != "pergunta"]
    unicas = [r for r in edicao if r["categoria"] not in ("varios", "nome_em_tudo")]
    return {
        "tarefas": len(resultados),
        "acerto": pct(resultados, "acerto"),
        "acerto_edicao": pct(edicao, "acerto"),
        "lugar_unico": pct(unicas, "acerto"),
        "varios": pct([r for r in edicao if r["categoria"] == "varios"], "acerto"),
        "sem_dano": pct(edicao, "sem_dano"),
        "marcado": pct(resultados, "marcado"),
        "honesto": pct(resultados, "honesto"),
        "numeracao": pct([r for r in edicao if r["categoria"] in ("inserir_clausula", "mover", "apagar")], "numeracao"),
        "erros": sum(1 for r in resultados if r.get("erro")),
        "segundos_medio": round(sum(r["segundos"] for r in resultados) / max(1, len(resultados)), 1),
        "tokens": sum(r["tokens"] for r in resultados),
        "por_categoria": {c: {"n": len(v), "acerto": pct(v, "acerto")} for c, v in sorted(cats.items())},
    }
