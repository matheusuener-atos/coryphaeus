"""
PAULUS - As operações de edição (docs/PLANO-EDITOR.md, E3).

O modelo propõe; o programa confere e aplica. O que volta do modelo é uma
lista de operações com nome de bloco ("troque X por Y no b12", "insira este
parágrafo depois do b20", "apague o b31") - nunca o documento reescrito, nunca
"acrescente no fim". Aqui cada operação é conferida (o bloco existe? o trecho
está nele, letra por letra? está dentro do trecho que a pessoa selecionou?) e
aplicada como SUGESTÃO marcada (src/blocos.py), com um nome próprio para
aceitar ou recusar.

O que não passa na conferência não é aplicado em lugar parecido: volta em
`falhas`, com o motivo, e a resposta diz o que não deu. Escrever no lugar
errado é pior que não escrever.

A descrição de cada mudança ("Cláusula 3ª: “30” → “60”") sai daqui, do que foi
aplicado de fato - e não do que o modelo disse que fez.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

import blocos as B
import esboco as E

TIPOS_DE_OPERACAO = ("substituir", "substituir_em_tudo", "reescrever", "inserir", "apagar", "apagar_trecho",
                     "mover", "comentar", "renumerar")


@dataclass
class Resultado:
    blocos: list
    aplicadas: list = field(default_factory=list)    # {"op", "tipo", "sids", "ids", "rotulo", "resumo"}
    falhas: list = field(default_factory=list)       # {"op", "tipo", "motivo"}
    comentarios: list = field(default_factory=list)  # {"bloco", "trecho", "texto", "rotulo"}

    @property
    def sids(self) -> list[str]:
        return [s for a in self.aplicadas for s in a["sids"]]


@dataclass
class _Ctx:
    rotulos: dict           # o rótulo de cada bloco ANTES desta rodada ("Cláusula 4ª")
    original: list          # o documento como o modelo leu: o nome por rótulo vale para ele
    rodada: int
    existentes: set
    permitido: set | None
    selecao: dict | None
    em_tudo: bool

    def rotulo(self, bid: str) -> str:
        return self.rotulos.get(bid, bid)


class _Falhou(Exception):
    pass


# A operação pede o que o texto já diz ("RIBEIRO" → "RIBEIRO ALVES" onde já
# está "RIBEIRO ALVES"): nada a fazer, e não é falha - não vira correção.
_JA_ESTAVA = object()


def _fora_do_que_ja_trocou(texto: str, lugares: list, de: str, para: str) -> list:
    """
    As ocorrências de `de` que ainda não estão como `para`. "RIBEIRO" dentro de
    "RIBEIRO ALVES" (a mesma troca pedida duas vezes, ou já feita) não é
    trocado de novo: daria "RIBEIRO ALVES ALVES".
    """
    k = para.lower().find(de.lower())
    if k < 0 or len(para) <= len(de):
        return lugares
    return [(ini, fim) for ini, fim in lugares
            if ini - k < 0 or texto[ini - k:ini - k + len(para)].lower() != para.lower()]


def de_rotulo(rotulo: str) -> str:
    """"da Cláusula 4ª", "do preâmbulo", "das Assinaturas" - a preposição com o artigo certo."""
    r = str(rotulo or "").strip()
    primeira = r.split(" ")[0].lower() if r else ""
    if primeira in ("cláusula", "clausula", "seção", "alínea"):
        return "da " + r
    if primeira in ("assinaturas",):
        return "das " + r
    if re.match(r"^b[0-9a-f]{4,8}$", r):
        return "de " + r
    if r.isupper():
        return "da seção " + r
    if primeira in ("local", "fecho", "título", "preâmbulo", "endereçamento"):
        return "do " + r[0].lower() + r[1:]
    return "do " + r


def _curto(texto: str, n: int = 60) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def aplicar(blocos_entrada: list, operacoes: list, *, rodada: int, escopo: list | None = None,
            selecao: dict | None = None, em_tudo: bool = False, original: list | None = None) -> Resultado:
    """
    As operações sobre uma cópia do documento.

    `escopo`: os blocos onde mexer é permitido (o trecho selecionado, a
    cláusula que o pedido nomeou). `selecao`: {"bloco", "texto"} quando a
    seleção é um pedaço de um bloco só - a troca tem de cair dentro dela.
    `em_tudo`: o pedido falou em "todo o documento"; sem isso, a troca em
    todas as ocorrências só vale para nome e termo em maiúsculas (o que
    costuma mesmo aparecer em vários lugares).
    """
    blocos = copy.deepcopy(blocos_entrada)
    res = Resultado(blocos=blocos)
    # `original`: o documento como o modelo leu (as operações de uma rodada
    # chegam uma a uma, e o rótulo "Cláusula 4ª" é o de antes delas).
    lido = original if original is not None else copy.deepcopy(blocos)
    ctx = _Ctx(rotulos=E.rotulos(lido), original=lido, rodada=rodada,
               existentes={b.id for b in blocos} | {b.id for b in lido}, permitido=set(escopo) if escopo else None,
               selecao=selecao, em_tudo=em_tudo)

    for i, op in enumerate(operacoes or []):
        if not isinstance(op, dict):
            res.falhas.append({"op": i, "tipo": "?", "motivo": "operação ilegível"})
            continue
        tipo = str(op.get("op") or op.get("tipo") or "").strip().lower()
        if tipo not in TIPOS_DE_OPERACAO:
            res.falhas.append({"op": i, "tipo": tipo or "?", "motivo": f"operação desconhecida “{tipo}”"})
            continue
        try:
            feito = _UMA[tipo](blocos, op, ctx)
        except _Falhou as exc:
            res.falhas.append({"op": i, "tipo": tipo, "motivo": str(exc)})
            continue
        if feito is _JA_ESTAVA:
            continue
        if feito is None:
            res.falhas.append({"op": i, "tipo": tipo, "motivo": "não mudou nada (o texto novo é igual ao de antes)"})
            continue
        if tipo == "comentar":
            res.comentarios.append(feito.pop("comentario"))
        feito.update(op=i, tipo=tipo)
        res.aplicadas.append(feito)
    res.blocos = blocos
    return res


# ------------------------------------------------------------ conferir

def _id_do_bloco(valor, blocos: list, ctx: _Ctx) -> str:
    """
    O nome do bloco como o modelo escreveu: "b12", "[b12 · Cláusula 4ª]" ou,
    às vezes, só o rótulo ("Cláusula 4ª"). O rótulo é resolvido no documento
    como o modelo o leu (antes desta rodada): "a cláusula 4ª" logo depois de
    inserir uma cláusula 4ª nova continua sendo a antiga.
    """
    vivos = {b.id for b in blocos}
    t = str(valor or "").strip().strip("[]").strip()
    if not t:
        return ""
    primeiro = re.split(r"[\s·|,]+", t)[0]
    if primeiro in vivos:
        return primeiro
    achado = re.search(r"\bb[0-9a-f]{4,8}\b", t)
    if achado and achado.group(0) in vivos:
        return achado.group(0)
    ids = [i for i in (E.localizar(ctx.original, t).get("ids") or []) if i in vivos]
    return ids[0] if ids else ""


def _ids_da_referencia(valor, blocos: list, ctx: _Ctx) -> list[str]:
    """
    Os blocos de uma referência: o nome de um bloco é ele só; um rótulo
    ("Cláusula 4ª") é a cláusula inteira - cabeça e corpo -, no documento
    como o modelo o leu.
    """
    vivos = {b.id for b in blocos}
    t = str(valor or "").strip().strip("[]").strip()
    primeiro = re.split(r"[\s·|,]+", t)[0] if t else ""
    if primeiro in vivos or re.search(r"\bb[0-9a-f]{4,8}\b", t):
        bid = _id_do_bloco(valor, blocos, ctx)
        return [bid] if bid else []
    return [i for i in (E.localizar(ctx.original, t).get("ids") or []) if i in vivos]


def _exigir_bloco(valor, blocos: list, ctx: _Ctx) -> B.Bloco:
    bid = _id_do_bloco(valor, blocos, ctx)
    if not bid:
        raise _Falhou(f"o bloco “{_curto(valor, 30)}” não existe no documento")
    if ctx.permitido is not None and bid not in ctx.permitido:
        raise _Falhou(f"{bid} está fora do trecho em que o pedido manda mexer")
    b = B.por_id(blocos)[bid]
    if b.sug == "del":
        raise _Falhou(f"{bid} já está marcado para sair")
    return b


def _achar_no_bloco(b: B.Bloco, de: str, selecao: dict | None) -> list[tuple[int, int]]:
    texto = b.texto
    if selecao and selecao.get("bloco") == b.id and selecao.get("texto"):
        lugar_sel = B.achar(texto, selecao["texto"])
        if lugar_sel:
            dentro = B.achar(texto[lugar_sel[0]:lugar_sel[1]], de)
            if dentro:
                return [(lugar_sel[0] + dentro[0], lugar_sel[0] + dentro[1])]
            return []
    exatas = B.ocorrencias(texto, de, palavra_inteira=True)
    if exatas:
        return exatas
    um = B.achar(texto, de)
    return [um] if um else []


def _paragrafos(texto) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", str(texto or "").strip()) if p.strip()]


# ---------------------------------------------------------- operações

def _substituir(blocos, op, ctx):
    de = str(op.get("de") or "")
    para = str(op.get("para") if op.get("para") is not None else "")
    if not de.strip():
        raise _Falhou("faltou o trecho a trocar")
    varios = _ids_da_referencia(op.get("bloco"), blocos, ctx)
    if len(varios) > 1:
        # "na Cláusula 2ª": o trecho está num dos blocos dela.
        mapa = B.por_id(blocos)
        com = [i for i in varios if mapa[i].sug != "del" and _achar_no_bloco(mapa[i], de, None)]
        op = {**op, "bloco": com[0] if com else varios[0]}
    b = _exigir_bloco(op.get("bloco"), blocos, ctx)
    lugares = _achar_no_bloco(b, de, ctx.selecao)
    nota = ""
    if not lugares:
        # O modelo errou o bloco mas copiou o trecho certo: se o trecho está
        # em UM bloco só (e permitido), é lá. Em dois ou mais, não adivinha.
        candidatos = [x for x in blocos if x.id != b.id and x.sug != "del" and x.tipo != "table"
                      and (ctx.permitido is None or x.id in ctx.permitido) and _achar_no_bloco(x, de, None)]
        if len(candidatos) == 1:
            nota = f" (o trecho estava em {candidatos[0].id}, não em {b.id})"
            b = candidatos[0]
            lugares = _achar_no_bloco(b, de, None)
        else:
            raise _Falhou(f"não achei “{_curto(de, 50)}” em {b.id}" +
                          (f" (aparece em {len(candidatos)} blocos)" if candidatos else ""))
    if b.tipo == "table":
        return _trocar_no_quadro(blocos, b, de, para, ctx)
    lugares = _fora_do_que_ja_trocou(b.texto, lugares, de, para)
    if not lugares:
        return _JA_ESTAVA
    novo = b.texto
    for ini, fim in sorted(lugares, reverse=True):
        novo = novo[:ini] + para + novo[fim:]
    sid = B.nova_sugestao()
    if not B.reescrever(b, novo, sid, ctx.rodada):
        return None
    rotulo = ctx.rotulo(b.id)
    vezes = f" ({len(lugares)} vezes)" if len(lugares) > 1 else ""
    de_curto, para_curto = _o_que_mudou(de, para)
    resumo = (f"{rotulo}: “{de_curto}” → “{para_curto}”{vezes}" if para.strip()
              else f"{rotulo}: tirei “{_curto(de, 60)}”{vezes}")
    return {"sids": [sid], "ids": [b.id], "rotulo": rotulo, "resumo": resumo + nota}


def _o_que_mudou(de: str, para: str, n: int = 50) -> tuple[str, str]:
    """
    O pedaço que muda de fato, para o resumo: "a contar do recebimento desta,
    por depósito na conta" → "...por PIX" vira “por depósito na conta” → “por
    PIX”, e não dois textos cortados iguais no começo.
    """
    a, b = " ".join(de.split()), " ".join(para.split())
    if len(a) <= n and len(b) <= n:
        return a, b
    pa, pb = a.split(" "), b.split(" ")
    ini = 0
    while ini < min(len(pa), len(pb)) - 1 and pa[ini] == pb[ini]:
        ini += 1
    fim = 0
    while fim < min(len(pa), len(pb)) - ini - 1 and pa[-1 - fim] == pb[-1 - fim]:
        fim += 1
    trecho_a = " ".join(pa[ini:len(pa) - fim]) or a
    trecho_b = " ".join(pb[ini:len(pb) - fim]) or b
    antes = "…" if ini else ""
    depois = "…" if fim else ""
    return antes + _curto(trecho_a, n) + depois, antes + _curto(trecho_b, n) + depois


def _trocar_no_quadro(blocos, b, de, para, ctx):
    """No quadro a célula é texto puro: o quadro velho sai e o novo entra, na mesma sugestão."""
    novo = copy.deepcopy(b)
    novo.id = B.novo_id(ctx.existentes)
    mudou = False
    for linha in novo.linhas:
        for c in linha:
            lugar = B.achar(c[1], de)
            if lugar:
                c[1] = c[1][:lugar[0]] + para + c[1][lugar[1]:]
                mudou = True
    if not mudou:
        raise _Falhou(f"não achei “{_curto(de, 50)}” no quadro")
    sid = B.nova_sugestao()
    B.marcar_bloco(b, "del", sid, ctx.rodada)
    B.marcar_bloco(novo, "ins", sid, ctx.rodada)
    blocos.insert(B.indice(blocos, b.id) + 1, novo)
    rotulo = ctx.rotulo(b.id)
    return {"sids": [sid], "ids": [b.id, novo.id], "rotulo": rotulo,
            "resumo": f"{rotulo} (quadro): “{_curto(de, 40)}” → “{_curto(para, 40)}”"}


def _substituir_em_tudo(blocos, op, ctx):
    de = " ".join(str(op.get("de") or "").split())
    para = str(op.get("para") if op.get("para") is not None else "")
    if not de:
        raise _Falhou("faltou o trecho a trocar")
    termo = bool(re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ.\- ]{0,60}$", de)) and (
        de.isupper() or de.istitle() or len(de.split()) >= 2)
    if not ctx.em_tudo and not termo:
        raise _Falhou(f"trocar “{_curto(de, 40)}” em todo o documento não foi pedido; diga onde, ou peça "
                      "“em todo o documento”")
    sids, ids, total, ja = [], [], 0, 0
    for b in blocos:
        if b.sug == "del" or b.tipo == "table" or (ctx.permitido is not None and b.id not in ctx.permitido):
            continue
        achados = B.ocorrencias(b.texto, de)
        lugares = _fora_do_que_ja_trocou(b.texto, achados, de, para)
        ja += len(achados) - len(lugares)
        if not lugares:
            continue
        novo = b.texto
        for ini, fim in sorted(lugares, reverse=True):
            novo = novo[:ini] + para + novo[fim:]
        sid = B.nova_sugestao()
        if B.reescrever(b, novo, sid, ctx.rodada):
            sids.append(sid)
            ids.append(b.id)
            total += len(lugares)
    if not sids and ja:
        return _JA_ESTAVA
    if not sids:
        raise _Falhou(f"não achei “{_curto(de, 50)}” no documento")
    return {"sids": sids, "ids": ids, "rotulo": ctx.rotulo(ids[0]) if len(ids) == 1 else "o documento",
            "resumo": f"“{_curto(de, 40)}” → “{_curto(para, 40)}” em {total} lugar{'es' if total > 1 else ''} "
                      f"({len(ids)} bloco{'s' if len(ids) > 1 else ''})"}


def _reescrever(blocos, op, ctx):
    b = _exigir_bloco(op.get("bloco"), blocos, ctx)
    if b.tipo == "table":
        raise _Falhou("quadro não se reescreve por texto: troque a célula")
    partes = _paragrafos(op.get("texto"))
    if not partes:
        raise _Falhou(f"o texto novo de {b.id} veio vazio (para tirar o bloco, a operação é apagar)")
    sid = B.nova_sugestao()
    rotulo = ctx.rotulo(b.id)
    sel = ctx.selecao
    if sel and sel.get("bloco") == b.id and sel.get("texto") and len(partes) == 1:
        # Seleção de um pedaço do bloco: o texto novo entra no lugar do pedaço.
        lugar = B.achar(b.texto, sel["texto"])
        if lugar and (lugar[1] - lugar[0]) < len(b.texto) * 0.9:
            atual = b.texto
            if not B.reescrever(b, atual[:lugar[0]] + partes[0] + atual[lugar[1]:], sid, ctx.rodada):
                return None
            return {"sids": [sid], "ids": [b.id], "rotulo": rotulo, "resumo": f"{rotulo}: reescrevi o trecho selecionado"}
    mudou = B.reescrever(b, partes[0], sid, ctx.rodada)
    ids = [b.id]
    i = B.indice(blocos, b.id)
    for k, extra in enumerate(partes[1:], start=1):
        novo = B.bloco_novo(b.tipo, extra, ctx.existentes, sid, ctx.rodada, lista=b.lista, nivel=b.nivel,
                            alinhar=b.alinhar)
        blocos.insert(i + k, novo)
        ids.append(novo.id)
        mudou = True
    if not mudou:
        return None
    return {"sids": [sid], "ids": ids, "rotulo": rotulo,
            "resumo": f"Reescrevi {rotulo}" + (f" (agora em {len(partes)} parágrafos)" if len(partes) > 1 else "")}


def _molde(blocos: list, texto: str, perto: int) -> dict:
    """
    Como o bloco novo deve parecer: a cabeça de cláusula nova copia a cara das
    cabeças que o documento já tem (negrito, alinhamento, título ou
    parágrafo); o corpo, a do corpo vizinho.
    """
    cabeca = bool(E._numero_da_clausula(texto)[0]) or bool(E.RE_TITULO_NUMERADO.match(texto))
    partes = E.esboco(blocos)
    candidatos = [(abs(i - perto), b) for i, (b, p) in enumerate(zip(blocos, partes))
                  if b.sug != "del" and b.tipo != "table" and ((p.tipo == "clausula") == cabeca)
                  and (cabeca or p.tipo in ("corpo", "paragrafo", "inciso", "alinea", "subitem", "preambulo"))]
    if not candidatos:
        return {"tipo": "p", "alinhar": "", "marcas": ()}
    _, ref = min(candidatos, key=lambda x: x[0])
    visiveis = [c for c in ref.corridas if c.sug != "del" and c.texto.strip()]
    # Negrito no bloco inteiro (cabeça de cláusula em negrito) passa adiante;
    # negrito numa palavra do vizinho, não.
    marcas = visiveis[0].marcas if visiveis and all(c.marcas == visiveis[0].marcas for c in visiveis) else ()
    return {"tipo": ref.tipo if ref.tipo != "li" else "p", "alinhar": ref.alinhar, "marcas": marcas}


def _fim_da_clausula(blocos: list, i: int) -> int:
    """
    "Depois da cláusula 4ª" apontando para a CABEÇA dela: o lugar é depois do
    último bloco da cláusula (até a próxima cabeça, o fecho ou a data), e não
    entre a cabeça e o corpo.
    """
    partes = E.esboco(blocos)
    if partes[i].tipo != "clausula":
        return i
    j = i
    while j + 1 < len(blocos) and partes[j + 1].tipo not in ("clausula", "fecho", "data", "assinatura", "titulo",
                                                              "secao") and (partes[j + 1].clausula or
                                                                            partes[j + 1].tipo == "saindo"):
        j += 1
    return j


def _inserir(blocos, op, ctx):
    chave = "depois_de" if op.get("depois_de") else ("antes_de" if op.get("antes_de") else "")
    if not chave:
        raise _Falhou("faltou dizer onde inserir (depois_de ou antes_de um bloco)")
    ancora_id = _id_do_bloco(op.get(chave), blocos, ctx)
    if not ancora_id:
        raise _Falhou(f"o bloco “{_curto(op.get(chave), 30)}” não existe no documento")
    if ctx.permitido is not None and ancora_id not in ctx.permitido:
        raise _Falhou(f"{ancora_id} está fora do trecho em que o pedido manda mexer")
    definidos = op.get("blocos")
    if isinstance(definidos, (str, dict)):
        definidos = [definidos]
    if not definidos and op.get("texto"):
        definidos = [{"tipo": "p", "texto": t} for t in _paragrafos(op.get("texto"))]
    textos: list[tuple[str, str]] = []
    for d in definidos or []:
        if isinstance(d, str):
            textos += [("", t) for t in _paragrafos(d)]
        elif isinstance(d, dict):
            textos += [(str(d.get("tipo") or ""), t) for t in _paragrafos(d.get("texto"))]
    if not textos:
        raise _Falhou("o texto a inserir veio vazio")
    i = B.indice(blocos, ancora_id)
    ancora = blocos[i]
    pos = _fim_da_clausula(blocos, i) + 1 if chave == "depois_de" else i
    sid = B.nova_sugestao()
    ids = []
    for k, (tipo, texto) in enumerate(textos):
        molde = _molde(blocos, texto, pos)
        tipo_final = tipo if tipo in ("h1", "h2", "h3", "h4", "blockquote", "li") else molde["tipo"]
        lista = (ancora.lista or "ul") if tipo_final == "li" else ""
        novo = B.bloco_novo(tipo_final, texto, ctx.existentes, sid, ctx.rodada, lista=lista,
                            nivel=ancora.nivel if tipo_final == "li" else 0, alinhar=molde["alinhar"],
                            marcas=molde["marcas"] if tipo_final == molde["tipo"] else ())
        blocos.insert(pos + k, novo)
        ids.append(novo.id)
    primeiro = textos[0][1]
    if E._numero_da_clausula(primeiro)[0] or E.RE_TITULO_NUMERADO.match(primeiro):
        o_que = f"a cláusula “{_curto(primeiro, 50)}”"
    else:
        o_que = f"{len(textos)} parágrafo{'s' if len(textos) > 1 else ''}"
    onde = ("depois " if chave == "depois_de" else "antes ") + de_rotulo(ctx.rotulo(ancora_id))
    return {"sids": [sid], "ids": ids, "rotulo": ctx.rotulo(ancora_id), "resumo": f"Inseri {o_que} {onde}"}


def _alvos(op: dict, blocos: list, ctx: _Ctx) -> list[str]:
    """Os blocos de apagar e mover: a lista dada, ou a referência inteira (a cláusula toda)."""
    pedidos = op.get("blocos") if isinstance(op.get("blocos"), list) else [op.get("bloco")]
    ids: list[str] = []
    for p in pedidos:
        achados = _ids_da_referencia(p, blocos, ctx)
        if not achados:
            raise _Falhou(f"o bloco “{_curto(p, 30)}” não existe no documento")
        ids += [i for i in achados if i not in ids]
    return ids


def _apagar(blocos, op, ctx):
    alvos = _alvos(op, blocos, ctx)
    sid = B.nova_sugestao()
    ids, rotulos = [], []
    for alvo in alvos:
        b = _exigir_bloco(alvo, blocos, ctx)
        if b.sug == "ins":
            blocos.remove(b)        # entrava numa sugestão pendente: some de vez
        else:
            B.marcar_bloco(b, "del", sid, ctx.rodada)
        ids.append(b.id)
        r = ctx.rotulo(b.id)
        if r not in rotulos:
            rotulos.append(r)
    return {"sids": [sid], "ids": ids, "rotulo": rotulos[0],
            "resumo": "Apaguei " + (rotulos[0] if len(rotulos) == 1 else ", ".join(rotulos[:3]))
                      + (f" ({len(ids)} blocos)" if len(ids) > 1 else "")}


def _apagar_trecho(blocos, op, ctx):
    return _substituir(blocos, {**op, "para": ""}, ctx)


def _mover(blocos, op, ctx):
    alvos = _alvos(op, blocos, ctx)
    chave = "depois_de" if op.get("depois_de") else ("antes_de" if op.get("antes_de") else "")
    if not chave:
        raise _Falhou("faltou dizer para onde mover")
    destino_id = _id_do_bloco(op.get(chave), blocos, ctx)
    if not destino_id:
        raise _Falhou(f"o bloco “{_curto(op.get(chave), 30)}” não existe no documento")
    movidos = [_exigir_bloco(a, blocos, ctx) for a in alvos]
    if any(m.id == destino_id for m in movidos):
        raise _Falhou("o bloco não pode ir para perto dele mesmo")
    sid = B.nova_sugestao()
    copias = []
    for m in movidos:
        copia = copy.deepcopy(m)
        copia.id = B.novo_id(ctx.existentes)
        copia.corridas = [B.Corrida(c.texto, c.marcas) for c in copia.corridas if c.sug != "del"]
        B.marcar_bloco(copia, "ins", sid, ctx.rodada)
        B.marcar_bloco(m, "del", sid, ctx.rodada)
        copias.append(copia)
    i = B.indice(blocos, destino_id)
    pos = _fim_da_clausula(blocos, i) + 1 if chave == "depois_de" else i
    for k, c in enumerate(copias):
        blocos.insert(pos + k, c)
    rotulo = ctx.rotulo(movidos[0].id)
    return {"sids": [sid], "ids": [m.id for m in movidos] + [c.id for c in copias], "rotulo": rotulo,
            "resumo": f"Movi {rotulo} para " + ("depois " if chave == "depois_de" else "antes ")
                      + de_rotulo(ctx.rotulo(destino_id))}


def _comentar(blocos, op, ctx):
    b = _exigir_bloco(op.get("bloco"), blocos, ctx)
    texto = " ".join(str(op.get("texto") or "").split())
    if not texto:
        raise _Falhou("o comentário veio vazio")
    trecho = str(op.get("de") or "").strip()
    if trecho and not B.achar(b.texto, trecho):
        trecho = ""
    rotulo = ctx.rotulo(b.id)
    return {"sids": [], "ids": [b.id], "rotulo": rotulo, "resumo": f"Comentei {rotulo}",
            "comentario": {"bloco": b.id, "trecho": trecho or b.texto[:600], "texto": texto[:1500], "rotulo": rotulo}}


def _renumerar(blocos, op, ctx):
    return renumerar(blocos, ctx.rodada)


RE_LETRA_NA_CLAUSULA = re.compile(r"^(\s*cl[áa]usula\s+\d{1,3}\s*[ªaº°]?)\s*-\s*[A-Z]\b", re.I)


def renumerar(blocos: list, rodada: int) -> dict | None:
    """
    As cláusulas em sequência e as referências cruzadas junto (redacao.renumerar),
    como UMA sugestão: a pessoa aceita ou recusa a renumeração inteira.
    """
    import redacao

    vivos = [b for b in blocos if b.sug != "del" and b.tipo != "table"]
    textos = [b.texto.replace("\n", " ") for b in vivos]
    # "CLÁUSULA 2ª-A": a cláusula enfiada sem renumerar. Renumerando, a letra sai.
    textos = [RE_LETRA_NA_CLAUSULA.sub(r"\1", t) for t in textos]
    resultado = redacao.renumerar("\n".join(textos))
    if not resultado["trocas"]:
        return None
    novos = resultado["texto"].split("\n")
    if len(novos) != len(vivos):
        return None
    sid = B.nova_sugestao()
    ids = []
    for b, novo in zip(vivos, novos):
        novo = novo.replace(" ", "\n")
        if novo != b.texto and B.reescrever(b, novo, sid, rodada):
            ids.append(b.id)
    if not ids:
        return None
    clausulas = sum(1 for t in resultado["trocas"] if t["tipo"] == "clausula")
    refs = len(resultado["referencias"])
    resumo = f"Renumerei {clausulas} cláusula{'s' if clausulas != 1 else ''}" + (
        f" e {refs} referência{'s' if refs != 1 else ''} cruzada{'s' if refs != 1 else ''}" if refs else "")
    return {"sids": [sid], "ids": ids, "rotulo": "Numeração", "resumo": resumo, "tipo": "renumerar"}


_UMA = {
    "substituir": _substituir, "substituir_em_tudo": _substituir_em_tudo, "reescrever": _reescrever,
    "inserir": _inserir, "apagar": _apagar, "apagar_trecho": _apagar_trecho, "mover": _mover,
    "comentar": _comentar, "renumerar": _renumerar,
}


def precisa_renumerar(blocos: list) -> bool:
    """As cabeças de cláusula vivas estão fora de sequência (1, 2, 4... ou 1, 2, 2)?"""
    vivos = [b for b in blocos if b.sug != "del"]
    numeros = [int(re.sub(r"\D", "", p.rotulo) or 0) for p in E.esboco(vivos) if p.tipo == "clausula"]
    return bool(numeros) and numeros != list(range(numeros[0], numeros[0] + len(numeros)))
