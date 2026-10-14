"""
PAULUS - O esboço do documento (docs/PLANO-EDITOR.md, E2 e E5).

O que cada bloco é - título, preâmbulo, Cláusula 4ª, § 1º da Cláusula 4ª,
inciso II, fecho, local e data, assinaturas; numa petição, a seção ("DOS
FATOS") -, tudo por regra, a partir do texto que está escrito.

É o mapa que o assistente usa para achar "a cláusula quinta" sem perguntar ao
modelo, e o nome que a tela mostra ao lado de cada mudança ("Cláusula 4ª, §
1º"). Regra e não modelo de propósito: o rótulo de um parágrafo tem de ser o
mesmo toda vez que se olha para ele.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import redacao

ORDINAIS = {p: i for i, p in enumerate(redacao._POR_EXTENSO_PLANO, start=1)}
_ORDINAIS_MASC = ["primeiro", "segundo", "terceiro", "quarto", "quinto", "sexto", "setimo", "oitavo", "nono",
                  "decimo", "decimo primeiro", "decimo segundo", "decimo terceiro", "decimo quarto", "decimo quinto"]
ORDINAIS_MASC = {p: i for i, p in enumerate(_ORDINAIS_MASC, start=1)}
_ROMANOS = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def plano(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def romano(texto: str) -> int:
    t = (texto or "").lower()
    if not t or any(c not in _ROMANOS for c in t):
        return 0
    total = 0
    for i, c in enumerate(t):
        v = _ROMANOS[c]
        total += -v if i + 1 < len(t) and _ROMANOS[t[i + 1]] > v else v
    return total


def para_romano(n: int) -> str:
    pares = ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    saida = ""
    for valor, letra in pares:
        while n >= valor:
            saida += letra
            n -= valor
    return saida


# ------------------------------------------------------------ reconhecer

_EXTENSO = "|".join(sorted({re.escape(p) for p in redacao._POR_EXTENSO_PLANO}, key=len, reverse=True))
RE_CLAUSULA_DEPOIS = re.compile(r"^\s*cl[aá]usula\s+(\d{1,3})\s*(?:[ªaº°o])?(?![\d.])", re.I)
RE_CLAUSULA_ANTES = re.compile(r"^\s*(\d{1,3})\s*[ªaº°]?\s+cl[aá]usula\b", re.I)
RE_CLAUSULA_EXTENSO = re.compile(r"^\s*clausula\s+(" + _EXTENSO + r")\b")
RE_TITULO_NUMERADO = re.compile(r"^\s*(\d{1,3})\s*(?:[.)\-–—:]\s+|\s+[\-–—]\s+)([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{2,}(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ/,\-]+)*)")
RE_ARTIGO = re.compile(r"^\s*art(?:igo)?\.?\s*(\d{1,4})\s*[ºo°]?", re.I)
RE_SUBITEM = re.compile(r"^\s*(\d{1,3})\.(\d{1,3})(?:\.(\d{1,3}))?\s*[.)\-–—]?\s+\S")
RE_PARAGRAFO_NUM = re.compile(r"^\s*§\s*(\d{1,3})\s*[ºo°]?", re.I)
RE_PARAGRAFO_UNICO = re.compile(r"^\s*par[aá]grafo\s+[uú]nico", re.I)
# "Parágrafo 1º:", "Parágrafo primeiro -": o "º" colado no número não é fim de
# palavra para o \b, e era assim que o estilo mais comum ficava sem nome.
RE_PARAGRAFO_EXTENSO = re.compile(r"^\s*paragrafo\s+(" + "|".join(sorted(ORDINAIS_MASC, key=len, reverse=True))
                                  + r"|\d{1,3})(?:\s*[ºo°ª])?(?=[\s:.,;\-–—)]|$)")
RE_INCISO = re.compile(r"^\s*([IVXLC]{1,7})\s*[-–—.)]\s+\S")
RE_ALINEA = re.compile(r"^\s*([a-z])\)\s+\S")
RE_FECHO = re.compile(r"^\s*(?:e,?\s+)?(?:por\s+)?(?:estarem|estando)\s+(?:assim\s+)?(?:justos|justas|de\s+acordo|"
                      r"cientes)|justas\s+e\s+contratadas|justos\s+e\s+contratados|"
                      r"^\s*e,?\s+por\s+estarem|^\s*nestes\s+termos|^\s*termos\s+em\s+que|"
                      r"^\s*assinad[oa]s?\s+(?:em|neste|nesta|aos?)\b|"
                      r"\bem\s+(?:duas|tr[eê]s|quatro|\d)\s+(?:\(\w+\)\s+)?vias\s+de\s+igual\s+teor", re.I)
# A linha da assinatura sem traço: o nome em maiúsculas, sozinho ("HUGO MAGALHÃES SILVA").
RE_NOME_DE_ASSINATURA = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÀÇ][A-ZÁÉÍÓÚÂÊÔÃÕÀÇ'.\- ]{3,70}$")
RE_DATA = re.compile(r"^[^\n]{0,60},\s*(?:\d{1,2}|\[[^\]]*\])\s+de\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|"
                     r"agosto|setembro|outubro|novembro|dezembro|\[[^\]]*\])\s+de\s+(?:\d{4}|\[[^\]]*\])", re.I)
RE_ASSINATURA = re.compile(r"_{5,}|^\s*testemunhas?\s*:?\s*$|^\s*assinatura", re.I)
RE_ENDERECAMENTO = re.compile(r"^\s*(?:excelent[ií]ssim[oa]|ao\s+ju[ií]zo|exmo|ilustr[ií]ssim[oa]|ao\s+senhor|"
                              r"a\s+senhora|ao\s+cart[oó]rio|ao\s+tribunal)", re.I)


@dataclass
class Parte:
    id: str
    rotulo: str = ""          # "Cláusula 4ª, § 1º"
    tipo: str = "corpo"       # titulo, preambulo, clausula, corpo, paragrafo, inciso, alinea, subitem, secao,
    #                           fecho, data, assinatura, enderecamento
    clausula: int = 0         # o número da cláusula em que o bloco está (0: nenhuma)
    clausula_rotulo: str = ""
    paragrafo: str = ""       # "1", "unico"
    inciso: int = 0
    alinea: str = ""
    subitem: str = ""         # "5.2"
    secao: str = ""


def _numero_da_clausula(texto: str) -> tuple[int, str]:
    """(número, estilo) quando o texto ABRE com a cabeça de uma cláusula."""
    m = RE_CLAUSULA_DEPOIS.match(texto)
    if m:
        return int(m.group(1)), "clausula"
    m = RE_CLAUSULA_ANTES.match(texto)
    if m:
        return int(m.group(1)), "clausula"
    m = RE_CLAUSULA_EXTENSO.match(plano(texto[:60]))
    if m:
        return ORDINAIS.get(m.group(1), 0), "clausula"
    m = RE_ARTIGO.match(texto)
    if m:
        return int(m.group(1)), "artigo"
    return 0, ""


RE_SECAO = re.compile(r"^\s*(?:[IVXLC]{1,6}|\d{1,2})?\s*[-–—.)]?\s*(?:d[oa]s?\s|preliminar|pedido|requerimento|fatos|"
                      r"fundament|m[eé]rito|s[ií]ntese|conclus|tutela|valor\s+da\s+causa|provas?\b|justi[cç]a\s+gratuita|"
                      r"gratuidade|cabimento|tempestividade|raz[oõ]es|introdu)", re.I)


def _e_titulo_de_secao(b, texto: str, qualquer: bool = False) -> bool:
    """
    Linha curta em maiúsculas que abre uma parte da peça: "DOS FATOS", "II -
    DO DIREITO", "DOS PEDIDOS", "PRELIMINARMENTE". O nome da ação no
    preâmbulo ("AÇÃO DE COBRANÇA") não é seção. `qualquer`: no documento sem
    cláusula que não é petição (ata, parecer), qualquer linha assim é seção
    ("OBJETIVO DA REUNIÃO", "PROVIDÊNCIAS") - menos o nome em maiúsculas da
    assinatura, que é da cauda.
    """
    if not texto or len(texto) > 90:
        return False
    letras = [c for c in texto if c.isalpha()]
    if len(letras) < 4:
        return False
    if not RE_SECAO.match(texto) and not (qualquer and len(texto) <= 60 and not texto.rstrip().endswith((".", ":"))):
        return False
    if b.tipo in ("h1", "h2", "h3", "h4"):
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > 0.85 and not texto.rstrip().endswith((",", ";"))


# O nome do documento na primeira linha da ata, do parecer, do termo: é o título, não seção.
RE_NOME_DO_DOCUMENTO = re.compile(r"(?i)^\s*(?:ata|parecer|relat[oó]rio|termo|contrato|declara[cç][aã]o|procura[cç][aã]o|"
                                  r"notifica[cç][aã]o|requerimento|estatuto|regimento|memorando|laudo|certid[aã]o|"
                                  r"of[ií]cio|edital|convoca[cç][aã]o|recibo|acordo|distrato|aditivo|minuta)\b")
RE_ROTULO_DE_PARTE = re.compile(r"^\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ ]{2,30})\s*:")


def _sem_estrutura(partes: list, blocos: list) -> None:
    """
    Documento sem cláusula e sem seção (procuração, notificação, carta): o
    corpo não é "preâmbulo" de nada. Cada parágrafo ganha o nome que o próprio
    texto dá ("OUTORGANTE:", "PODERES:") ou a posição ("Parágrafo 3").
    """
    if any(p.tipo in ("clausula", "secao") for p in partes):
        return
    n = 0
    for b, p in zip(blocos, partes):
        if p.tipo != "preambulo":
            continue
        n += 1
        p.tipo = "corpo"
        m = RE_ROTULO_DE_PARTE.match(b.texto)
        p.rotulo = m.group(1).strip().capitalize() if m else f"Parágrafo {n}"


def _inicio_da_cauda(blocos: list) -> int:
    """
    Onde começa a cauda do documento: os blocos curtos do fim, sem cabeça de
    cláusula (nomes, cargos, CPF, testemunhas). Só nela um nome em maiúsculas
    sozinho conta como assinatura.
    """
    i = len(blocos)
    while i > 0:
        b = blocos[i - 1]
        texto = (b.texto or "").strip() if getattr(b, "tipo", "") != "table" else ""
        if getattr(b, "sug", "") == "del" or not texto:
            i -= 1
            continue
        if len(texto) >= 90 or _numero_da_clausula(texto)[0]:
            break
        # Uma frase de verdade ("A cooperativa está comprometida em...") é corpo, não
        # cauda - a não ser o fecho e a data. Sem isso, na ata de parágrafos curtos,
        # "OBJETIVO DA REUNIÃO" virava nome de quem assina (14/10/2026).
        if sum(1 for w in texto.split() if w.isalpha() and w.islower()) >= 3 and not RE_DATA.match(texto) \
                and not RE_FECHO.search(texto):
            break
        i -= 1
    return i


def rotulo_da_clausula(n: int, estilo: str) -> str:
    if estilo == "artigo":
        return f"Art. {n}º" if n < 10 else f"Art. {n}"
    return f"Cláusula {n}ª"


def esboco(blocos: list) -> list[Parte]:
    """O que cada bloco é, na ordem do documento."""
    partes: list[Parte] = []
    clausula, clausula_rot, estilo = 0, "", ""
    paragrafo, inciso, alinea, subitem = "", 0, "", ""
    secao = ""
    titulo_visto = False
    houve_clausula = False
    titulos_numerados = _titulos_numerados(blocos)
    # Documento sem cláusula e que não é petição (ata, parecer, relatório): toda
    # linha curta em maiúsculas é seção ("OBJETIVO DA REUNIÃO", "PROVIDÊNCIAS"),
    # e cada parágrafo tem número dentro dela. Antes, a ata inteira era
    # "Preâmbulo" e a resposta dizia "Reescrevi o preâmbulo" quatro vezes.
    textos_ = [(x.texto or "").strip() for x in blocos if getattr(x, "tipo", "") != "table"]
    generico = (not any(_numero_da_clausula(x)[0] for x in textos_)
                and not any(RE_ENDERECAMENTO.match(x) for x in textos_[:3]) and not titulos_numerados)
    no_corpo = 0             # o número do parágrafo, na seção (ou fora dela) do documento genérico
    na_lista = 0             # e o do item de lista, contado à parte
    fim = False             # depois do fecho/data: assinaturas
    cauda = _inicio_da_cauda(blocos)

    for i, b in enumerate(blocos):
        # O bloco marcado para sair (sugestão pendente) não conta no esboço:
        # o mapa é o do documento como fica.
        if getattr(b, "sug", "") == "del":
            partes.append(Parte(id=b.id, tipo="saindo", rotulo="(saindo)"))
            continue
        texto = b.texto.strip() if b.tipo != "table" else ""
        # A numeração automática do Word ("5.2", "a)") conta para o esboço como
        # se estivesse escrita (src/docx_ida_e_volta.py).
        if getattr(b, "num", "") and texto:
            texto = b.num + " " + texto
        p = Parte(id=b.id)
        n, est = _numero_da_clausula(texto)
        if not n and b.id in titulos_numerados:
            n, est = titulos_numerados[b.id], "clausula"
        if fim and texto and not n:
            if RE_DATA.match(texto) and len(texto) < 120:
                p.tipo, p.rotulo = "data", "Local e data"
            else:
                p.tipo, p.rotulo = "assinatura", "Assinaturas"
            partes.append(p)
            continue
        if n:
            # Cláusula depois do fecho: o documento está fora de ordem (a revisão
            # aponta), mas cláusula é cláusula - e o que vem depois é dela.
            fim = False
            clausula, estilo = n, est
            clausula_rot = rotulo_da_clausula(n, est)
            paragrafo, inciso, alinea, subitem = "", 0, "", ""
            houve_clausula = True
            p.tipo, p.rotulo = "clausula", clausula_rot
        elif RE_FECHO.search(texto[:160]) and (houve_clausula or i > 2):
            p.tipo, p.rotulo = "fecho", "Fecho"
            clausula, clausula_rot = 0, ""
            fim = True
        elif RE_DATA.match(texto) and len(texto) < 120:
            p.tipo, p.rotulo = "data", "Local e data"
            clausula, clausula_rot = 0, ""
            fim = True
        elif texto and RE_ASSINATURA.search(texto) and len(texto) < 160 and (houve_clausula or i > 2):
            p.tipo, p.rotulo = "assinatura", "Assinaturas"
            fim = True
        elif (texto and (houve_clausula or generico) and i >= cauda and RE_NOME_DE_ASSINATURA.match(texto)
              and len(texto.split()) >= 2):
            # Os nomes em maiúsculas no fim, sem traço nem fecho: são as assinaturas,
            # não o corpo da última cláusula.
            p.tipo, p.rotulo = "assinatura", "Assinaturas"
            clausula, clausula_rot = 0, ""
            fim = True
        elif not titulo_visto and not houve_clausula and i <= 1 and texto and (
                b.tipo in ("h1", "h2") or _e_titulo_de_secao(b, texto)
                or (generico and RE_NOME_DO_DOCUMENTO.match(texto) and _e_titulo_de_secao(b, texto, qualquer=True))) \
                and not RE_ENDERECAMENTO.match(texto) and not (generico and RE_SECAO.match(texto)):
            p.tipo, p.rotulo = "titulo", "Título"
            titulo_visto = True
        elif texto and RE_ENDERECAMENTO.match(texto) and i <= 2 and not houve_clausula:
            p.tipo, p.rotulo = "enderecamento", "Endereçamento"
        elif not houve_clausula and _e_titulo_de_secao(b, texto, qualquer=generico) and (i > 0 or generico):
            secao = " ".join(texto.split())[:60]
            p.tipo, p.rotulo, p.secao = "secao", secao, secao
            no_corpo = na_lista = 0
        elif clausula:
            p.clausula, p.clausula_rotulo = clausula, clausula_rot
            m_sub = RE_SUBITEM.match(texto)
            m_par = RE_PARAGRAFO_NUM.match(texto)
            m_inc = RE_INCISO.match(texto)
            m_ali = RE_ALINEA.match(texto)
            if RE_PARAGRAFO_UNICO.match(texto):
                paragrafo, inciso, alinea = "unico", 0, ""
                p.tipo = "paragrafo"
            elif m_par:
                paragrafo, inciso, alinea = m_par.group(1), 0, ""
                p.tipo = "paragrafo"
            elif RE_PARAGRAFO_EXTENSO.match(plano(texto[:40])):
                valor = RE_PARAGRAFO_EXTENSO.match(plano(texto[:40])).group(1)
                paragrafo = str(ORDINAIS_MASC.get(valor, valor))
                inciso, alinea = 0, ""
                p.tipo = "paragrafo"
            elif m_sub and int(m_sub.group(1)) == clausula:
                subitem = m_sub.group(0).split()[0].rstrip(".)-–—")
                p.tipo = "subitem"
            elif m_inc and romano(m_inc.group(1)):
                inciso, alinea = romano(m_inc.group(1)), ""
                p.tipo = "inciso"
            elif m_ali and inciso:
                alinea = m_ali.group(1)
                p.tipo = "alinea"
            p.paragrafo, p.inciso, p.alinea, p.subitem = paragrafo, inciso, alinea, subitem
            p.rotulo = _rotulo(clausula_rot, paragrafo, inciso, alinea, subitem, p.tipo)
        elif secao:
            p.secao = secao
            p.rotulo = secao
            # Dentro da seção da peça, o item dos pedidos ("c) a condenação...")
            # e o inciso têm nome próprio: é para onde o pedido novo vai.
            m_inc = RE_INCISO.match(texto)
            m_ali = RE_ALINEA.match(texto)
            if m_inc and romano(m_inc.group(1)):
                p.tipo = "inciso"
                p.rotulo = f"{secao}, inciso {m_inc.group(1)}"
            elif m_ali:
                p.tipo = "alinea"
                p.rotulo = f"{secao}, alínea {m_ali.group(1)}"
            elif generico and texto and b.tipo == "li":
                na_lista += 1
                p.rotulo = f"{secao}, {na_lista}º item"
            elif generico and texto:
                no_corpo += 1
                p.rotulo = f"{secao}, {no_corpo}º parágrafo"
        elif generico and not houve_clausula and texto and (titulo_visto or i > 0):
            no_corpo += 1
            # O nome que o próprio texto dá ("OUTORGANTE:", "PODERES:"), ou a posição.
            m_parte = RE_ROTULO_DE_PARTE.match(b.texto)
            p.tipo = "corpo"
            p.rotulo = m_parte.group(1).strip().capitalize() if m_parte else f"Parágrafo {no_corpo}"
        elif not houve_clausula and texto:
            p.tipo, p.rotulo = "preambulo", "Preâmbulo"
        if not p.rotulo:
            p.rotulo = f"Parágrafo {i + 1}"
        partes.append(p)
    _sem_estrutura(partes, blocos)
    return partes


def _rotulo(clausula: str, paragrafo: str, inciso: int, alinea: str, subitem: str, tipo: str) -> str:
    partes = [clausula]
    if subitem and tipo in ("subitem",):
        return f"{clausula.split(' ')[0]} {subitem}"
    if paragrafo:
        partes.append("parágrafo único" if paragrafo == "unico" else f"§ {paragrafo}º")
    if inciso:
        partes.append(f"inciso {para_romano(inciso)}")
    if alinea:
        partes.append(f"alínea {alinea}")
    return ", ".join(partes)


def _titulos_numerados(blocos: list) -> dict[str, int]:
    """
    "1. DO OBJETO", "2 – DO PREÇO": cláusula sem a palavra. Só quando há pelo
    menos duas e a numeração anda (a mesma regra de redacao._titulos_numerados).
    """
    achados = []
    for b in blocos:
        if b.tipo == "table":
            continue
        m = RE_TITULO_NUMERADO.match(b.texto)
        if m and len(m.group(2).replace(" ", "")) >= 4 and len(b.texto) < 140:
            achados.append((b.id, int(m.group(1))))
    if len(achados) < 2:
        return {}
    andam = sum(1 for a, c in zip(achados, achados[1:]) if c[1] == a[1] + 1)
    if andam < (len(achados) - 1) / 2:
        return {}
    return dict(achados)


def rotulos(blocos: list) -> dict[str, str]:
    return {p.id: p.rotulo for p in esboco(blocos)}


def clausulas(blocos: list) -> list[dict]:
    """As cláusulas: número, rótulo, o bloco da cabeça e todos os blocos dela."""
    saida: list[dict] = []
    for b, p in zip(blocos, esboco(blocos)):
        if p.tipo == "clausula":
            saida.append({"numero": int(re.sub(r"\D", "", p.rotulo) or 0), "rotulo": p.rotulo, "cabeca": b.id,
                          "titulo": " ".join(b.texto.split())[:90], "blocos": [b.id]})
        elif p.clausula and saida and saida[-1]["rotulo"] == p.clausula_rotulo:
            saida[-1]["blocos"].append(b.id)
    return saida


def resumo(blocos: list, limite: int = 6000) -> str:
    """
    O esboço curto que vai ao modelo junto do pedido: uma linha por parte
    grande (título, preâmbulo, cada cláusula com a cabeça e os blocos dela,
    fecho) - "- Cláusula 4ª: CLÁUSULA QUARTA – DO PRAZO · b9…b12 (4 blocos)".
    """
    grupos: list[dict] = []
    for b, p in zip(blocos, esboco(blocos)):
        chave = p.rotulo if p.tipo == "clausula" else (p.clausula_rotulo if p.clausula else p.rotulo)
        if grupos and grupos[-1]["chave"] == chave and p.tipo != "clausula":
            grupos[-1]["ids"].append(b.id)
            continue
        nome = chave
        if p.tipo == "clausula":
            nome = f"{p.rotulo}: {' '.join(b.texto.split())[:70]}"
        grupos.append({"chave": chave, "nome": nome, "ids": [b.id]})
    linhas = []
    for g in grupos:
        ids = g["ids"]
        faixa = ids[0] if len(ids) == 1 else f"{ids[0]}…{ids[-1]} ({len(ids)} blocos)"
        linhas.append(f"- {g['nome']} · {faixa}")
    texto = "\n".join(linhas)
    if len(texto) > limite:
        texto = texto[:limite].rsplit("\n", 1)[0] + "\n- …"
    return texto


# --------------------------------------------------------- localizar

_REF_CLAUSULA = re.compile(r"cl[aá]usula\s+(\d{1,3}|" + _EXTENSO + r")(?:\s*[ªaº°])?(?:\.(\d{1,3}))?", re.I)
_REF_CLAUSULA_ANTES = re.compile(r"(\d{1,3})\s*[ªaº°]\s+cl[aá]usula", re.I)
_REF_ORDINAL_CLAUSULA = re.compile(r"\b(" + _EXTENSO + r")\s+cl[aá]usula", re.I)
_REF_PARAGRAFO = re.compile(r"(?:§\s*(\d{1,3})\s*[ºo°]?|par[aá]grafo\s+([uú]nico|\d{1,3}\s*[ºo°]?|"
                            + "|".join(_ORDINAIS_MASC) + r"))", re.I)
_REF_INCISO = re.compile(r"inciso\s+([IVXLC]{1,7}|\d{1,3})\b", re.I)
_REF_ALINEA = re.compile(r"al[ií]nea\s+[\"“']?([a-z])\b", re.I)
_REF_SUBITEM = re.compile(r"\b(?:item|subcl[aá]usula|subitem)\s+(\d{1,3})\.(\d{1,3})", re.I)
_REF_ARTIGO = re.compile(r"\bart(?:igo)?\.?\s*(\d{1,4})\s*[ºo°]?(?!\s*(?:do|da)\s+(?:c[oó]digo|lei|cc|cpc|clt|cf|"
                         r"constitui))", re.I)
_REF_POSICAO = re.compile(r"\b(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|[uú]ltim[oa]|pen[uú]ltim[oa])\s+"
                          r"(par[aá]grafo|bloco|linha|item|t[oó]pico)", re.I)
_POSICOES = {"primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5, "ultimo": -1, "penultimo": -2}
# Só a primeira palavra forte, sem consumir o resto da frase: "a cláusula do
# foro para antes da cláusula de rescisão" tem dois nomes.
_REF_CLAUSULA_POR_NOME = re.compile(r"cl[aá]usula\s+(?:d[oa]s?|de|sobre\s+(?:o|a|os|as)?)\s+(?=([a-z]{4,}))")
_VAZIAS = {"para", "pelo", "pela", "como", "sobre", "mais", "menos", "esta", "este", "essa", "esse", "isso", "aqui",
           "logo", "depois", "antes", "contrato", "documento", "clausula"}


def numero_da_referencia(valor: str) -> int:
    v = plano(valor).strip()
    if v.isdigit():
        return int(v)
    return ORDINAIS.get(v, 0)


def localizar(blocos: list, frase: str) -> dict:
    """
    O lugar que a frase aponta, por regra: {"ids": [...], "rotulo": "...",
    "como": "..."} - ou {"ids": []} quando a frase não aponta lugar nenhum.

    "a cláusula quinta", "o § 2º da cláusula 3ª", "o parágrafo único",
    "o inciso II da cláusula 4", "o item 5.2", "o preâmbulo", "o título",
    "o fecho", "as assinaturas", "o último parágrafo", "nos pedidos".
    """
    partes = esboco(blocos)
    baixo = plano(frase or "")

    numero = 0
    m = _REF_CLAUSULA.search(baixo)
    if m:
        numero = numero_da_referencia(m.group(1))
        sub = m.group(2)
        if sub and numero:
            achados = [p for p in partes if p.clausula == numero and p.subitem == f"{numero}.{sub}"]
            if achados:
                return {"ids": [p.id for p in achados], "rotulo": f"Cláusula {numero}.{sub}", "como": "item"}
    else:
        m2 = _REF_CLAUSULA_ANTES.search(baixo) or _REF_ORDINAL_CLAUSULA.search(baixo)
        if m2:
            numero = numero_da_referencia(m2.group(1))
    m_sub = _REF_SUBITEM.search(baixo)
    if m_sub:
        n1, n2 = int(m_sub.group(1)), int(m_sub.group(2))
        achados = [p for p in partes if p.clausula == n1 and p.subitem == f"{n1}.{n2}"]
        if achados:
            return {"ids": [p.id for p in achados], "rotulo": f"Cláusula {n1}.{n2}", "como": "item"}
    if not numero:
        m_art = _REF_ARTIGO.search(baixo)
        if m_art and any(p.tipo == "clausula" and p.rotulo.startswith("Art.") for p in partes):
            numero = int(m_art.group(1))

    m_par = _REF_PARAGRAFO.search(baixo)
    m_inc = _REF_INCISO.search(baixo)
    m_ali = _REF_ALINEA.search(baixo)
    paragrafo = ""
    if m_par:
        if m_par.group(1):
            paragrafo = m_par.group(1)
        else:
            v = re.sub(r"\s*[ºo°]$", "", m_par.group(2).strip()) if re.match(r"^\d", m_par.group(2)) else \
                m_par.group(2).strip()
            paragrafo = "unico" if v.startswith("unico") else str(ORDINAIS_MASC.get(v, v))
    inciso = 0
    if m_inc:
        valor = m_inc.group(1)
        inciso = int(valor) if valor.isdigit() else romano(valor)
    alinea = m_ali.group(1).lower() if m_ali else ""

    if numero:
        da_clausula = [p for p in partes if p.clausula == numero or (p.tipo == "clausula" and _num(p.rotulo) == numero)]
        if not da_clausula:
            return {"ids": [], "rotulo": f"Cláusula {numero}ª", "como": "nao_existe"}
        escolhidos = da_clausula
        if paragrafo:
            escolhidos = [p for p in da_clausula if p.paragrafo == paragrafo]
        if inciso:
            escolhidos = [p for p in escolhidos if p.inciso == inciso]
        if alinea:
            escolhidos = [p for p in escolhidos if p.alinea == alinea]
        if not escolhidos:
            return {"ids": [], "rotulo": _rotulo(da_clausula[0].clausula_rotulo or da_clausula[0].rotulo, paragrafo,
                                                     inciso, alinea, "", ""), "como": "nao_existe"}
        # Só o parágrafo (ou o inciso) pedido, e não o que vem embaixo dele.
        if paragrafo and not inciso and not alinea:
            escolhidos = [p for p in escolhidos if p.inciso == 0 and not p.alinea] or escolhidos
        if inciso and not alinea:
            escolhidos = [p for p in escolhidos if not p.alinea] or escolhidos
        rotulo = escolhidos[0].rotulo if (paragrafo or inciso or alinea) else (
            escolhidos[0].clausula_rotulo or escolhidos[0].rotulo)
        return {"ids": [p.id for p in escolhidos], "rotulo": rotulo, "como": "clausula"}

    if paragrafo == "unico" or (paragrafo and not numero):
        achados = [p for p in partes if p.paragrafo == paragrafo and p.inciso == 0 and not p.alinea]
        donos = {p.clausula for p in achados}
        if len(donos) == 1 and achados:
            return {"ids": [p.id for p in achados], "rotulo": achados[0].rotulo, "como": "paragrafo"}
        if len(donos) > 1:
            return {"ids": [], "rotulo": "", "como": "ambiguo",
                    "opcoes": sorted({p.clausula_rotulo for p in achados})}

    # "a cláusula do prazo", "a cláusula das benfeitorias": a cláusula pelo
    # nome que a cabeça dela tem ("CLÁUSULA 2ª – DO PRAZO").
    for m_nome in _REF_CLAUSULA_POR_NOME.finditer(baixo):
        achado = _clausula_pelo_nome(blocos, partes, m_nome.group(1))
        if achado:
            return achado

    for chave, tipo in (("preambulo", "preambulo"), ("qualificac", "preambulo"), ("titulo", "titulo"),
                        ("fecho", "fecho"), ("encerramento", "fecho"), ("assinatura", "assinatura"),
                        ("local e data", "data"), ("enderecamento", "enderecamento")):
        if re.search(r"\b" + chave, baixo):
            achados = [p for p in partes if p.tipo == tipo]
            if achados:
                return {"ids": [p.id for p in achados], "rotulo": achados[0].rotulo, "como": tipo}

    for p in partes:
        if p.tipo == "secao":
            nome = plano(p.secao)
            nucleo = re.sub(r"^[ivxlc\d]+\s*[-–—.)]?\s*", "", nome)
            nucleo = re.sub(r"^d[oa]s?\s+", "", nucleo).strip()
            if nucleo and len(nucleo) > 3 and re.search(r"\b" + re.escape(nucleo) + r"\b", baixo):
                ids = [q.id for q in partes if q.secao == p.secao]
                return {"ids": ids, "rotulo": p.secao, "como": "secao"}

    m_pos = _REF_POSICAO.search(baixo)
    if m_pos:
        chave = re.sub(r"[ao]$", "o", plano(m_pos.group(1)))
        pos = _POSICOES.get(chave, 0)
        # "O último parágrafo" é o do texto, não a linha da assinatura.
        fora = {p.id for p in partes if p.tipo in ("assinatura", "data", "titulo")}
        corpo = [b for b in blocos if b.tipo != "table" and b.texto.strip() and b.id not in fora]
        if pos and corpo and abs(pos) <= len(corpo):
            b = corpo[pos - 1] if pos > 0 else corpo[pos]
            rot = next((p.rotulo for p in partes if p.id == b.id), "")
            return {"ids": [b.id], "rotulo": rot, "como": "posicao"}
    return {"ids": [], "rotulo": "", "como": ""}


def _clausula_pelo_nome(blocos: list, partes: list, nome: str) -> dict | None:
    """A cláusula cuja cabeça tem a primeira palavra forte do nome ("do prazo" → "DO PRAZO")."""
    palavras = [p for p in re.findall(r"[a-z]{4,}", nome) if p not in _VAZIAS][:3]
    if not palavras:
        return None
    cabecas = [(b, p) for b, p in zip(blocos, partes) if p.tipo == "clausula"
               and re.search(r"\b" + palavras[0], plano(b.texto))]
    if len(cabecas) != 1:
        return None
    rot = cabecas[0][1].rotulo
    ids = [p.id for p in partes if p.rotulo == rot or p.clausula_rotulo == rot]
    return {"ids": ids, "rotulo": rot, "como": "clausula_por_nome"}


def localizar_todos(blocos: list, frase: str) -> list[dict]:
    """
    Todos os lugares que a frase aponta ("mova a cláusula do foro para antes
    da cláusula de rescisão": as duas), na ordem em que aparecem nela.
    """
    partes = esboco(blocos)
    baixo = plano(frase or "")
    achados: list[dict] = []
    vistos: set = set()
    candidatos = [(m.start(), m.end()) for m in _REF_CLAUSULA.finditer(baixo)]
    candidatos += [(m.start(), m.end()) for m in _REF_CLAUSULA_ANTES.finditer(baixo)]
    candidatos += [(m.start(), m.end()) for m in _REF_ORDINAL_CLAUSULA.finditer(baixo)]
    candidatos.sort()
    if len(candidatos) <= 1:
        # Uma cláusula só: a frase inteira diz o §, o inciso e a alínea dela,
        # venham antes ou depois ("o inciso III do § 3º da cláusula 3ª").
        lugar = localizar(blocos, frase)
        if lugar.get("ids"):
            vistos.add(tuple(lugar["ids"]))
            achados.append(lugar)
    else:
        fim_anterior = 0
        for inicio, fim in candidatos:
            # Cada referência com o pedaço da frase entre ela e a anterior.
            lugar = localizar(blocos, baixo[fim_anterior:fim + 25])
            fim_anterior = fim
            chave = tuple(lugar.get("ids") or [])
            if chave and chave not in vistos:
                vistos.add(chave)
                achados.append(lugar)
    for m in _REF_CLAUSULA_POR_NOME.finditer(baixo):
        lugar = _clausula_pelo_nome(blocos, partes, m.group(1))
        if lugar and tuple(lugar["ids"]) not in vistos:
            vistos.add(tuple(lugar["ids"]))
            achados.append(lugar)
    if not achados:
        lugar = localizar(blocos, frase)
        if lugar.get("ids"):
            achados.append(lugar)
    return achados


def _num(rotulo: str) -> int:
    m = re.search(r"\d+", rotulo or "")
    return int(m.group(0)) if m else 0
