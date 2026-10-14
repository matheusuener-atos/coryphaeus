"""
PAULUS - O documento em blocos com identidade (docs/PLANO-EDITOR.md, E2 e E3).

O editor escreve HTML num campo editável, e até aqui o HTML era o documento
inteiro: nenhum parágrafo tinha nome. O assistente achava o lugar de uma
mudança pelo texto - e trocava em todas as ocorrências - ou desistia e
escrevia no fim do documento.

Aqui o documento vira uma lista de blocos (título, parágrafo, item, citação,
quadro), cada um com um `data-b` que não muda enquanto ele existir. Com isso:

- o assistente aponta o lugar ("b12"), e o programa confere que ele existe;
- a mudança vira sugestão marcada DENTRO do bloco - o que entra num <ins>, o
  que sai num <del>, como o controlar alterações do Word -, e cada uma se
  aceita ou recusa sozinha, sem levar o resto do documento junto;
- a tela recebe só os blocos que mudaram (`remendos`), e o que a pessoa
  digitou em outro parágrafo enquanto o modelo escrevia fica onde está.

O HTML continua sendo o que vai para o banco: é o que o campo editável sabe
mostrar. Mas ele passa por aqui na ida e na volta, e o que não é documento
(estilo colado de outra página, script, classe da tela) não fica.

A sugestão no HTML:
  <ins data-s="s1a2b3" data-r="2">texto que entra</ins>
  <del data-s="s1a2b3" data-r="2">texto que sai</del>
  <p data-b="b7k2" data-s="s1a2b3" data-sug="ins" data-r="2">bloco inteiro que entra</p>
`data-s` é a sugestão (aceitar e recusar andam por ela), `data-r` a rodada do
assistente que a escreveu ("desfazer esta resposta" recusa a rodada inteira).
"""

from __future__ import annotations

import copy
import difflib
import html as html_mod
import re
import secrets
import unicodedata
from dataclasses import dataclass, field

# ------------------------------------------------------------------ modelo

MARCAS_ORDEM = ("b", "i", "u", "s", "sup", "sub")
_MARCA_DA_TAG = {"b": "b", "strong": "b", "i": "i", "em": "i", "u": "u",
                 "s": "s", "strike": "s", "sup": "sup", "sub": "sub"}
_BLOCO_DA_TAG = {"p": "p", "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4", "h5": "h4", "h6": "h4",
                 "blockquote": "blockquote", "pre": "p"}
# Embrulhos: viram parágrafo quando só têm texto, e somem quando têm blocos.
_EMBRULHOS = {"div", "section", "article", "header", "footer", "main", "center", "aside", "nav", "form",
              "figure", "figcaption", "address", "body", "html"}
_IGNORAR = {"script", "style", "template", "head", "title", "meta", "link", "noscript", "button",
            "input", "select", "textarea", "svg", "canvas", "iframe", "object", "img", "video", "audio"}
TIPOS = ("p", "h1", "h2", "h3", "h4", "blockquote", "li", "table")
ALINHAMENTOS = ("center", "right", "justify")

# Espaço que o HTML junta num só. A quebra (<br>) é "\n" e fica.
_ESPACOS = re.compile(r"[ \t\r\n\f\v      　]+")


@dataclass
class Corrida:
    """Um pedaço de texto com a mesma marcação do começo ao fim."""

    texto: str = ""
    marcas: tuple = ()      # em MARCAS_ORDEM
    sug: str = ""           # "", "ins" ou "del"
    sid: str = ""
    rodada: int = 0

    def mesma_marcacao(self, outra: "Corrida") -> bool:
        return (self.marcas, self.sug, self.sid, self.rodada) == (outra.marcas, outra.sug, outra.sid, outra.rodada)


@dataclass
class Bloco:
    """Um parágrafo, título, item, citação ou quadro - com nome."""

    id: str
    tipo: str = "p"
    corridas: list = field(default_factory=list)
    alinhar: str = ""                       # "", "center", "right", "justify"
    lista: str = ""                         # "ul" ou "ol", nos itens
    nivel: int = 0                          # item de lista dentro de outro
    linhas: list = field(default_factory=list)   # quadro: [[[cabeca, texto], ...], ...]
    sug: str = ""                           # o bloco inteiro: "", "ins" ou "del"
    sid: str = ""
    rodada: int = 0
    docx: str = ""                          # o parágrafo do .docx de onde veio (E1)
    num: str = ""                           # a numeração automática do Word ("1.1", "a)")

    @property
    def texto(self) -> str:
        """O texto que se vê agora: o que entra conta, o que sai não."""
        if self.tipo == "table":
            return "\n".join(" | ".join(c[1] for c in linha) for linha in self.linhas)
        return normalizar_espacos("".join(c.texto for c in self.corridas if c.sug != "del"))

    def texto_original(self) -> str:
        """O texto de antes das sugestões pendentes: o que sai conta, o que entra não."""
        if self.tipo == "table":
            return self.texto
        return normalizar_espacos("".join(c.texto for c in self.corridas if c.sug != "ins"))

    def texto_aceito(self) -> str:
        return self.texto

    def tem_sugestao(self) -> bool:
        return bool(self.sug) or any(c.sug for c in self.corridas)


def normalizar_espacos(texto: str) -> str:
    """O espaço como o HTML mostra: um só, sem sobra nas pontas nem em volta da quebra."""
    t = _ESPACOS.sub(" ", texto.replace("\n", "\x00")).replace("\x00", "\n")
    t = re.sub(r" *\n *", "\n", t)
    return t.strip(" ")


# ------------------------------------------------------------- identidade

def novo_id(existentes: set | None = None, prefixo: str = "b") -> str:
    """Um nome curto que ainda não existe no documento."""
    existentes = existentes if existentes is not None else set()
    while True:
        candidato = prefixo + secrets.token_hex(3)
        if candidato not in existentes:
            existentes.add(candidato)
            return candidato


def nova_sugestao() -> str:
    return "s" + secrets.token_hex(3)


_ID_VALIDO = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$")


# ------------------------------------------------------------------ leitura

def ler(html: str) -> list[Bloco]:
    """
    O HTML do editor virando blocos com nome.

    Marcação desconhecida vira texto, nunca some: perder texto de contrato por
    causa de uma tag inesperada seria o pior resultado possível. Bloco sem
    nome ganha um; nome repetido (o Enter do navegador copia o parágrafo
    inteiro, atributos junto) fica com o primeiro, e o segundo ganha outro.
    """
    import lxml.html

    fonte = (html or "").strip()
    if not fonte:
        return []
    try:
        raiz = lxml.html.fragment_fromstring(fonte, create_parent="div")
    except Exception:  # noqa: BLE001 - HTML que nem o lxml lê vira texto
        raiz = None
    if raiz is None:
        texto = re.sub(r"<[^>]+>", " ", fonte)
        return _dar_nomes([Bloco(id="", corridas=[Corrida(texto=html_mod.unescape(texto))])])

    leitor = _Leitor()
    leitor.conteudo(raiz)
    leitor.fechar_solto()
    return _dar_nomes([b for b in leitor.blocos if _vale(b)])


def _vale(b: Bloco) -> bool:
    if b.tipo == "table":
        return any(any(str(c[1]).strip() for c in linha) for linha in b.linhas) or bool(b.linhas)
    return True


def _dar_nomes(blocos: list[Bloco]) -> list[Bloco]:
    vistos: set = set()
    for b in blocos:
        if not b.id or not _ID_VALIDO.match(b.id) or b.id in vistos:
            b.id = novo_id(vistos)
        else:
            vistos.add(b.id)
    docx_vistos: set = set()
    for b in blocos:
        # O parágrafo do .docx partido em dois (Enter): o primeiro é o original.
        if b.docx:
            if b.docx in docx_vistos:
                b.docx = ""
                b.num = ""
            else:
                docx_vistos.add(b.docx)
    for b in blocos:
        _limpar_corridas(b)
    return blocos


class _Leitor:
    def __init__(self) -> None:
        self.blocos: list[Bloco] = []
        self.solto: Bloco | None = None   # texto fora de bloco, junto num parágrafo

    # O texto que não está em bloco nenhum (o campo editável deixa assim a
    # primeira linha às vezes) vira um parágrafo.
    def _solto(self) -> Bloco:
        if self.solto is None:
            self.solto = Bloco(id="")
            self.blocos.append(self.solto)
        return self.solto

    def fechar_solto(self) -> None:
        if self.solto is not None and not "".join(c.texto for c in self.solto.corridas).strip():
            self.blocos.remove(self.solto)
        self.solto = None

    def conteudo(self, el, alinhar: str = "") -> None:
        """Os filhos de um embrulho: blocos viram blocos; texto solto, parágrafo."""
        if el.text:
            self._solto().corridas.append(Corrida(texto=el.text))
        for filho in el:
            tag = _tag(filho)
            if tag in _IGNORAR or not isinstance(tag, str):
                if filho.tail:
                    self._solto().corridas.append(Corrida(texto=filho.tail))
                continue
            if _e_bloco(filho):
                self.fechar_solto()
                self.bloco(filho, alinhar)
            else:
                alvo = self._solto()
                _corridas(filho, alvo.corridas, ())
            if filho.tail:
                if _e_bloco(filho):
                    self._solto().corridas.append(Corrida(texto=filho.tail))
                else:
                    self._solto().corridas.append(Corrida(texto=filho.tail))
        if self.solto is not None and not self.solto.alinhar:
            self.solto.alinhar = alinhar

    def bloco(self, el, alinhar: str = "", nivel: int = 0, lista: str = "") -> None:
        tag = _tag(el)
        meu_alinhar = _alinhamento(el) or alinhar
        if tag in ("ul", "ol"):
            for filho in el:
                if _tag(filho) == "li":
                    self.item(filho, tag, nivel, meu_alinhar)
                elif _e_bloco(filho):
                    self.bloco(filho, meu_alinhar, nivel + 1 if _tag(filho) in ("ul", "ol") else nivel, tag)
                elif _tag(filho) not in _IGNORAR and isinstance(_tag(filho), str):
                    b = self._novo("li", el=filho, alinhar=meu_alinhar)
                    b.lista, b.nivel = tag, nivel
                    _corridas(filho, b.corridas, ())
            return
        if tag == "li":
            self.item(el, lista or "ul", nivel, meu_alinhar)
            return
        if tag == "table":
            b = self._novo("table", el=el)
            b.linhas = _linhas_do_quadro(el)
            return
        if tag in _EMBRULHOS or (tag == "blockquote" and _tem_bloco(el)):
            if _tem_bloco(el):
                # Embrulho com blocos dentro: some, e os blocos ficam (o
                # recuo do navegador põe parágrafos dentro de <blockquote>).
                antes = len(self.blocos)
                self.fechar_solto()
                self.conteudo(el, meu_alinhar)
                self.fechar_solto()
                if tag == "blockquote":
                    for b in self.blocos[antes:]:
                        if b.tipo == "p":
                            b.tipo = "blockquote"
                return
            b = self._novo("p", el=el, alinhar=meu_alinhar)
            _corridas_de_dentro(el, b.corridas, ())
            return
        tipo = _BLOCO_DA_TAG.get(tag, "p")
        b = self._novo(tipo, el=el, alinhar=meu_alinhar)
        if _tem_bloco(el):
            # <p> com bloco dentro (HTML colado torto): o texto de antes fica
            # neste bloco, e os blocos de dentro viram blocos.
            if el.text:
                b.corridas.append(Corrida(texto=el.text))
            for filho in el:
                if _e_bloco(filho):
                    self.bloco(filho, meu_alinhar)
                    if filho.tail and filho.tail.strip():
                        extra = self._novo(tipo, alinhar=meu_alinhar)
                        extra.corridas.append(Corrida(texto=filho.tail))
                elif _tag(filho) not in _IGNORAR:
                    _corridas(filho, b.corridas, ())
            return
        _corridas_de_dentro(el, b.corridas, ())

    def item(self, el, lista: str, nivel: int, alinhar: str) -> None:
        b = self._novo("li", el=el, alinhar=_alinhamento(el) or alinhar)
        b.lista, b.nivel = lista, nivel
        if el.text:
            b.corridas.append(Corrida(texto=el.text))
        for filho in el:
            tag = _tag(filho)
            if tag in ("ul", "ol"):
                self.bloco(filho, alinhar, nivel + 1)
                if filho.tail and filho.tail.strip():
                    resto = self._novo("li", alinhar=alinhar)
                    resto.lista, resto.nivel = lista, nivel
                    resto.corridas.append(Corrida(texto=filho.tail))
                continue
            if tag in _IGNORAR or not isinstance(tag, str):
                if filho.tail:
                    b.corridas.append(Corrida(texto=filho.tail))
                continue
            if _e_bloco(filho):
                # <li><p>texto</p></li>: o parágrafo é o próprio item.
                if b.corridas and "".join(c.texto for c in b.corridas).strip():
                    b.corridas.append(Corrida(texto=" "))
                _corridas_de_dentro(filho, b.corridas, ())
            else:
                _corridas(filho, b.corridas, ())
            if filho.tail:
                b.corridas.append(Corrida(texto=filho.tail))

    def _novo(self, tipo: str, el=None, alinhar: str = "") -> Bloco:
        self.fechar_solto()
        b = Bloco(id="", tipo=tipo, alinhar=alinhar)
        if el is not None:
            b.id = str(el.get("data-b") or "")
            b.docx = str(el.get("data-docx") or "")[:20]
            b.num = " ".join(str(el.get("data-num") or "").split())[:20]
            sug = str(el.get("data-sug") or "")
            sid = str(el.get("data-s") or "")
            if sug in ("ins", "del") and sid:
                b.sug, b.sid, b.rodada = sug, sid[:20], _inteiro(el.get("data-r"))
        self.blocos.append(b)
        return b


def _tag(el) -> str:
    t = el.tag
    return t.lower() if isinstance(t, str) else t


def _e_bloco(el) -> bool:
    tag = _tag(el)
    return isinstance(tag, str) and (tag in _BLOCO_DA_TAG or tag in _EMBRULHOS or tag in ("ul", "ol", "li", "table"))


def _tem_bloco(el) -> bool:
    return any(_e_bloco(f) for f in el)


def _inteiro(valor) -> int:
    try:
        return max(0, int(str(valor or "0")))
    except ValueError:
        return 0


def _alinhamento(el) -> str:
    estilo = str(el.get("style") or "").lower()
    m = re.search(r"text-align\s*:\s*(center|right|justify|left|start|end)", estilo)
    valor = m.group(1) if m else str(el.get("align") or "").lower()
    if _tag(el) == "center":
        valor = "center"
    return {"end": "right", "left": "", "start": ""}.get(valor, valor) if valor in ("center", "right", "justify", "left",
                                                                                     "start", "end") else ""


def _marcas_do_estilo(el) -> set:
    estilo = str(el.get("style") or "").lower().replace(" ", "")
    marcas = set()
    if re.search(r"font-weight:(bold|bolder|[6-9]00)", estilo):
        marcas.add("b")
    if "font-style:italic" in estilo or "font-style:oblique" in estilo:
        marcas.add("i")
    if "underline" in estilo:
        marcas.add("u")
    if "line-through" in estilo:
        marcas.add("s")
    if "vertical-align:super" in estilo:
        marcas.add("sup")
    if "vertical-align:sub" in estilo:
        marcas.add("sub")
    return marcas


def _corridas_de_dentro(el, saida: list, marcas: tuple, sug=("", "", 0)) -> None:
    if el.text:
        saida.append(Corrida(texto=el.text, marcas=marcas, sug=sug[0], sid=sug[1], rodada=sug[2]))
    for filho in el:
        _corridas(filho, saida, marcas, sug)
        if filho.tail:
            saida.append(Corrida(texto=filho.tail, marcas=marcas, sug=sug[0], sid=sug[1], rodada=sug[2]))


def _corridas(el, saida: list, marcas: tuple, sug=("", "", 0)) -> None:
    """O conteúdo de um elemento de dentro do parágrafo, com a marcação acumulada."""
    tag = _tag(el)
    if not isinstance(tag, str) or tag in _IGNORAR:
        return
    if tag == "br":
        saida.append(Corrida(texto="\n", marcas=marcas, sug=sug[0], sid=sug[1], rodada=sug[2]))
        return
    novas = set(marcas)
    novo_sug = sug
    if tag in _MARCA_DA_TAG:
        novas.add(_MARCA_DA_TAG[tag])
    elif tag in ("ins", "del"):
        sid = str(el.get("data-s") or "")
        if sid and not sug[0]:
            novo_sug = (tag, sid[:20], _inteiro(el.get("data-r")))
        elif tag == "del":
            novas.add("s")        # tachado de verdade, não sugestão
        else:
            novas.add("u")
    elif tag == "mark" and "ed-novo" in str(el.get("class") or ""):
        # A marca do editor de antes de 13/10/2026 (o texto escrito pelo
        # assistente esperando "manter"): vira sugestão de verdade, para
        # aceitar ou recusar como as outras.
        if not sug[0]:
            novo_sug = ("ins", "s-legado", 0)
    novas |= _marcas_do_estilo(el)
    ordenadas = tuple(m for m in MARCAS_ORDEM if m in novas)
    _corridas_de_dentro(el, saida, ordenadas, novo_sug)


def _linhas_do_quadro(el) -> list:
    linhas = []
    for tr in el.iter("tr"):
        linha = []
        for c in tr:
            if _tag(c) in ("td", "th"):
                partes = []
                for x in c.iter():
                    if _tag(x) == "br":
                        partes.append(" ")
                    if x.text and _tag(x) not in _IGNORAR:
                        partes.append(x.text)
                    if x is not c and x.tail:
                        partes.append(x.tail)
                linha.append([_tag(c) == "th", " ".join("".join(partes).split())])
        if linha:
            linhas.append(linha)
    largura = max((len(l) for l in linhas), default=0)
    return [l + [[False, ""]] * (largura - len(l)) for l in linhas]


def _limpar_corridas(b: Bloco) -> None:
    """Espaço como o HTML mostra, corridas iguais juntas, nada vazio."""
    if b.tipo == "table":
        return
    juntas: list[Corrida] = []
    for c in b.corridas:
        texto = c.texto
        if texto != "\n":
            texto = _ESPACOS.sub(" ", texto)
        if not texto:
            continue
        if juntas and juntas[-1].mesma_marcacao(c) and juntas[-1].texto != "\n" and texto != "\n":
            # Juntar pode emendar dois espaços (o de uma corrida e o da outra).
            juntas[-1].texto = _ESPACOS.sub(" ", juntas[-1].texto + texto)
        else:
            juntas.append(Corrida(texto, c.marcas, c.sug, c.sid, c.rodada))
    # Espaço repetido na emenda de duas corridas, e nas pontas do bloco.
    for i in range(1, len(juntas)):
        anterior, atual = juntas[i - 1], juntas[i]
        if atual.texto.startswith(" ") and (anterior.texto.endswith(" ") or anterior.texto == "\n"):
            if anterior.sug != "del" and atual.sug != "del":
                atual.texto = atual.texto[1:]
    visiveis = [c for c in juntas if c.sug != "del"]
    if visiveis:
        visiveis[0].texto = visiveis[0].texto.lstrip(" ")
        visiveis[-1].texto = visiveis[-1].texto.rstrip(" ")
    b.corridas = [c for c in juntas if c.texto]


# ------------------------------------------------------------------ escrita

def html(blocos: list[Bloco]) -> str:
    """Os blocos de volta em HTML - o que o banco guarda e a tela mostra."""
    partes: list[str] = []
    pilha: list[tuple[str, int]] = []     # listas abertas: (tipo, nivel)
    item_aberto: list[bool] = []

    def fechar_ate(nivel: int) -> None:
        while pilha and pilha[-1][1] > nivel:
            if item_aberto[-1]:
                partes.append("</li>")
            partes.append(f"</{pilha[-1][0]}>")
            pilha.pop()
            item_aberto.pop()

    for b in blocos:
        if b.tipo != "li":
            fechar_ate(-1)
            partes.append(_bloco_html(b))
            continue
        nivel = max(0, b.nivel)
        if pilha:
            nivel = min(nivel, pilha[-1][1] + 1)
        else:
            nivel = 0
        fechar_ate(nivel)
        if pilha and pilha[-1][1] == nivel and pilha[-1][0] != (b.lista or "ul"):
            fechar_ate(nivel - 1)
        if not pilha or pilha[-1][1] < nivel:
            partes.append(f"<{b.lista or 'ul'}>")
            pilha.append((b.lista or "ul", nivel))
            item_aberto.append(False)
        elif item_aberto[-1]:
            partes.append("</li>")
        partes.append(f"<li{_atributos(b)}>{_corridas_html(b.corridas)}")
        item_aberto[-1] = True
    fechar_ate(-1)
    return "".join(partes)


def _atributos(b: Bloco) -> str:
    attrs = [f' data-b="{b.id}"']
    if b.sug and b.sid:
        attrs.append(f' data-s="{_attr(b.sid)}" data-sug="{b.sug}" data-r="{b.rodada}"')
    if b.docx:
        attrs.append(f' data-docx="{_attr(b.docx)}"')
    if b.num:
        attrs.append(f' data-num="{_attr(b.num)}"')
    if b.alinhar in ALINHAMENTOS:
        attrs.append(f' style="text-align: {b.alinhar};"')
    return "".join(attrs)


def _attr(valor: str) -> str:
    return html_mod.escape(str(valor), quote=True)


def _bloco_html(b: Bloco) -> str:
    if b.tipo == "table":
        corpo = "".join(
            "<tr>" + "".join(f"<{'th' if c[0] else 'td'}>{html_mod.escape(c[1], quote=False) or '<br>'}"
                             f"</{'th' if c[0] else 'td'}>" for c in linha) + "</tr>"
            for linha in b.linhas)
        return f"<table{_atributos(b)}><tbody>{corpo}</tbody></table>"
    tag = b.tipo if b.tipo in ("p", "h1", "h2", "h3", "h4", "blockquote") else "p"
    return f"<{tag}{_atributos(b)}>{_corridas_html(b.corridas)}</{tag}>"


def _corridas_html(corridas: list) -> str:
    if not corridas or not "".join(c.texto for c in corridas).strip("\n "):
        if not any(c.texto == "\n" for c in corridas):
            return "<br>"
    partes: list[str] = []
    i = 0
    while i < len(corridas):
        c = corridas[i]
        if c.sug:
            grupo = [c]
            while i + 1 < len(corridas) and (corridas[i + 1].sug, corridas[i + 1].sid, corridas[i + 1].rodada) == \
                    (c.sug, c.sid, c.rodada):
                i += 1
                grupo.append(corridas[i])
            dentro = "".join(_marcado(x) for x in grupo)
            partes.append(f'<{c.sug} data-s="{_attr(c.sid)}" data-r="{c.rodada}">{dentro}</{c.sug}>')
        else:
            partes.append(_marcado(c))
        i += 1
    saida = "".join(partes)
    # Um <br> no fim do bloco não aparece no navegador: precisa de outro.
    if corridas and corridas[-1].texto == "\n" and corridas[-1].sug != "del":
        saida += "<br>"
    return saida


def _marcado(c: Corrida) -> str:
    if c.texto == "\n":
        return "<br>"
    texto = html_mod.escape(c.texto, quote=False)
    for m in reversed(c.marcas):
        texto = f"<{m}>{texto}</{m}>"
    return texto


def normalizar(html_entrada: str) -> str:
    """O HTML do jeito que o banco guarda: com nomes, sem o que não é documento."""
    return html(ler(html_entrada))


# --------------------------------------------------------------- consultas

def por_id(blocos: list[Bloco]) -> dict[str, Bloco]:
    return {b.id: b for b in blocos}


def indice(blocos: list[Bloco], id_: str) -> int:
    for i, b in enumerate(blocos):
        if b.id == id_:
            return i
    return -1


def tem_sugestoes(blocos: list[Bloco]) -> bool:
    return any(b.tem_sugestao() for b in blocos)


def sugestoes(blocos: list[Bloco]) -> list[dict]:
    """As sugestões pendentes, na ordem em que aparecem, com o que entra e o que sai."""
    vistas: dict[str, dict] = {}
    for b in blocos:
        if b.sug and b.sid:
            s = vistas.setdefault(b.sid, {"sid": b.sid, "rodada": b.rodada, "blocos": [], "entra": [], "sai": []})
            if b.id not in s["blocos"]:
                s["blocos"].append(b.id)
            (s["entra"] if b.sug == "ins" else s["sai"]).append(b.texto if b.sug == "ins" else b.texto_original())
        for c in b.corridas:
            if c.sug and c.sid and not b.sug:
                s = vistas.setdefault(c.sid, {"sid": c.sid, "rodada": c.rodada, "blocos": [], "entra": [], "sai": []})
                if b.id not in s["blocos"]:
                    s["blocos"].append(b.id)
                (s["entra"] if c.sug == "ins" else s["sai"]).append(c.texto)
    saida = []
    for s in vistas.values():
        saida.append({**s, "entra": normalizar_espacos(" ".join(s["entra"])),
                      "sai": normalizar_espacos(" ".join(s["sai"]))})
    return saida


# ------------------------------------------------------ aceitar e recusar

def decidir(blocos: list[Bloco], aceitar: bool, sids: set | None = None, rodada: int | None = None) -> list[Bloco]:
    """
    Aceita (ou recusa) as sugestões pedidas - por nome, por rodada, ou todas.

    Aceitar: o que entra fica como texto, o que sai some. Recusar: o
    contrário. Bloco que fica sem texto nenhum some junto (a sugestão que
    apagava o parágrafo inteiro).
    """
    def alvo(sid: str, r: int) -> bool:
        if sids is not None and sid not in sids:
            return False
        if rodada is not None and r != rodada:
            return False
        return True

    saida: list[Bloco] = []
    for b in blocos:
        b = copy.deepcopy(b)
        if b.sug and alvo(b.sid, b.rodada):
            fica = (b.sug == "ins") == aceitar
            if not fica:
                continue
            b.sug, b.sid, b.rodada = "", "", 0
        corridas = []
        mexeu = False
        for c in b.corridas:
            if c.sug and alvo(c.sid, c.rodada):
                mexeu = True
                if (c.sug == "ins") == aceitar:
                    corridas.append(Corrida(c.texto, c.marcas))
                continue
            corridas.append(c)
        b.corridas = corridas
        if mexeu:
            _limpar_corridas(b)
            if b.tipo != "table" and not b.corridas and not b.sug:
                continue
        saida.append(b)
    return saida


def aceito(blocos: list[Bloco]) -> list[Bloco]:
    return decidir(blocos, True)


def recusado(blocos: list[Bloco]) -> list[Bloco]:
    return decidir(blocos, False)


# ------------------------------------------------------- achar um trecho

_ASPAS = str.maketrans({"“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
                        "‘": "'", "’": "'", "‚": "'", "‛": "'", "´": "'", "`": "'",
                        "–": "-", "—": "-", "‒": "-", "―": "-", "−": "-",
                        " ": " ", " ": " ", " ": " "})


def _plano(texto: str) -> str:
    """Para comparar: aspas e travessões de um tipo só, espaço único."""
    return _ESPACOS.sub(" ", texto.translate(_ASPAS))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def achar(texto: str, trecho: str, depois_de: int = 0) -> tuple[int, int] | None:
    """
    Onde `trecho` está em `texto` (o texto visível do bloco), tolerando o que o
    modelo costuma trocar ao copiar: aspas curvas por retas, travessão por
    hífen, espaço duplo, caixa. Devolve (início, fim) no texto de verdade, ou
    None - e None é a resposta certa quando o trecho não está lá: aplicar no
    lugar parecido é como se escreve no lugar errado.
    """
    if not trecho or not texto:
        return None
    i = texto.find(trecho, depois_de)
    if i >= 0:
        return i, i + len(trecho)
    # O mesmo texto com aspas, travessão e espaço de um tipo só. Os dois têm o
    # mesmo tamanho depois de _plano só se o espaço não mudou; por isso o mapa.
    for transformar in (_plano, lambda t: _plano(t).lower(), lambda t: _sem_acento(_plano(t).lower())):
        plano, mapa = _com_mapa(texto, transformar)
        alvo = transformar(trecho).strip()
        if not alvo:
            continue
        inicio_plano = 0
        while mapa and inicio_plano < len(mapa) and mapa[inicio_plano] < depois_de:
            inicio_plano += 1
        j = plano.find(alvo, inicio_plano)
        if j >= 0:
            return mapa[j], mapa[j + len(alvo) - 1] + 1
    return None


def _com_mapa(texto: str, transformar) -> tuple[str, list[int]]:
    """O texto transformado letra a letra, com a posição de cada letra no original."""
    saida: list[str] = []
    mapa: list[int] = []
    anterior_espaco = False
    for i, ch in enumerate(texto):
        t = transformar(ch)
        if t == " " or ch.isspace():
            if anterior_espaco:
                continue
            anterior_espaco = True
            saida.append(" ")
            mapa.append(i)
            continue
        anterior_espaco = False
        for x in t:
            saida.append(x)
            mapa.append(i)
    return "".join(saida), mapa


def ocorrencias(texto: str, trecho: str, palavra_inteira: bool = True) -> list[tuple[int, int]]:
    """Todas as vezes que o trecho aparece no texto, como palavra inteira."""
    alvo = " ".join((trecho or "").split())
    if not alvo or not texto:
        return []
    padrao = (r"(?<![\w])" if palavra_inteira and alvo[0].isalnum() else "") + \
        r"\s+".join(map(re.escape, alvo.split())) + \
        (r"(?![\w])" if palavra_inteira and alvo[-1].isalnum() else "")
    return [(m.start(), m.end()) for m in re.finditer(padrao, texto)]


# ------------------------------------------------- mudar um bloco, marcado

_TOKEN = re.compile(r"\n|[^\W_]+(?:[.,/-][^\W_]+)*|\s+|.", re.UNICODE)


def _tokens(texto: str) -> list[str]:
    return _TOKEN.findall(texto)


def _letras(b: Bloco) -> list[tuple]:
    """
    O bloco letra a letra: (letra, marcas, sug, sid, rodada). As letras que
    já saem (sugestão de apagar pendente) ficam com sug "del" - elas não
    aparecem no texto visível, mas não podem sumir do HTML.
    """
    saida = []
    for c in b.corridas:
        for ch in c.texto:
            saida.append((ch, c.marcas, c.sug, c.sid, c.rodada))
    return saida


def reescrever(b: Bloco, novo: str, sid: str, rodada: int, marcas_novas: tuple | None = None) -> bool:
    """
    Muda o texto visível do bloco para `novo`, marcando a diferença palavra
    por palavra: o que ficou igual fica como estava (com o negrito de antes),
    o que saiu vira <del>, o que entrou vira <ins>. Devolve False quando nada
    mudou.

    Sobre uma sugestão ainda pendente: o texto que ela fazia entrar e agora
    sai some de vez (nunca foi aceito), e o que ela fazia sair, no mesmo
    lugar, passa para a sugestão nova - "30 → 60" seguido de "60 → 90" é,
    para quem decide, "30 → 90". Sem isso, recusar uma e aceitar a outra
    deixaria "30 90" no contrato.
    """
    novo = normalizar_espacos(novo)
    letras = _letras(b)

    # As letras visíveis com o espaço normalizado, e de que letra original
    # cada uma veio. As que já saem (del pendente) ficam fora: o modelo não as vê.
    chars: list[str] = []
    origem: list[int] = []
    for i, l in enumerate(letras):
        if l[2] == "del":
            continue
        ch = l[0]
        if ch != "\n" and _ESPACOS.fullmatch(ch):
            ch = " "
        if ch == " " and (not chars or chars[-1] in (" ", "\n")):
            continue
        if ch == "\n" and chars and chars[-1] == " ":
            chars.pop()
            origem.pop()
        chars.append(ch)
        origem.append(i)
    while chars and chars[-1] == " ":
        chars.pop()
        origem.pop()
    antigo = "".join(chars)
    if antigo == novo:
        return False

    a_tokens = _tokens(antigo)
    b_tokens = _tokens(novo)
    inicio_tok = []
    pos = 0
    for t in a_tokens:
        inicio_tok.append(pos)
        pos += len(t)
    inicio_tok.append(pos)

    opcodes = _limpar_opcodes(difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False).get_opcodes(),
                              a_tokens, b_tokens)

    saida: list[tuple] = []        # (letra, marcas, sug, sid, rodada)
    ultimo = -1                    # a última letra original já posta (de um trecho igual)
    ultima_marca: tuple = ()

    for n, (op, i1, i2, j1, j2) in enumerate(opcodes):
        p1, p2 = inicio_tok[i1], inicio_tok[i2]
        if op == "equal":
            for k in range(p1, p2):
                oi = origem[k]
                # O que já saía entre a letra anterior e esta fica onde está.
                for g in range(ultimo + 1, oi):
                    if letras[g][2] == "del":
                        saida.append(letras[g])
                saida.append(letras[oi])
                ultimo = oi
                ultima_marca = letras[oi][1]
            continue

        # A região da mudança: da letra igual anterior até a próxima letra igual.
        proxima_igual = len(letras)
        for op2, a1, a2, _b1, _b2 in opcodes[n + 1:]:
            if op2 == "equal" and a1 < a2:
                proxima_igual = origem[inicio_tok[a1]]
                break
        trocadas = set(origem[p1:p2])
        sids_retirados = {letras[oi][3] for oi in trocadas if letras[oi][2] == "ins"}
        primeira_marca = None
        for g in range(ultimo + 1, proxima_igual):
            l = letras[g]
            if l[2] == "del":
                saida.append((l[0], l[1], "del", sid, rodada) if l[3] in sids_retirados else l)
            elif g in trocadas:
                if primeira_marca is None:
                    primeira_marca = l[1]
                if l[2] == "ins":
                    continue        # entrou numa sugestão pendente: some, nunca foi aceito
                saida.append((l[0], l[1], "del", sid, rodada))
            # (o espaço que a normalização tirou não volta)
        if j1 < j2:
            if marcas_novas is not None:
                marcas = marcas_novas
            elif primeira_marca is not None:
                marcas = primeira_marca
            elif ultimo >= 0:
                marcas = ultima_marca
            elif proxima_igual < len(letras):
                marcas = letras[proxima_igual][1]
            else:
                marcas = ()
            for ch in "".join(b_tokens[j1:j2]):
                saida.append((ch, tuple(marcas), "ins", sid, rodada))
        ultimo = max(ultimo, proxima_igual - 1)
    for g in range(ultimo + 1, len(letras)):
        if letras[g][2] == "del":
            saida.append(letras[g])

    corridas: list[Corrida] = []
    for ch, marcas, sug, s, r in saida:
        if corridas and (corridas[-1].marcas, corridas[-1].sug, corridas[-1].sid, corridas[-1].rodada) == \
                (marcas, sug, s, r) and ch != "\n" and corridas[-1].texto != "\n":
            corridas[-1].texto += ch
        else:
            corridas.append(Corrida(ch, marcas, sug, s, r))
    b.corridas = corridas
    _limpar_corridas(b)
    if b.sug == "ins":
        # O bloco inteiro ainda é sugestão de entrar (a cláusula nova, a movida):
        # mexer nele muda o que vai entrar, como no Word. Riscar "12ª" dentro do
        # que nem entrou era ruído ("CLÁUSULA 12ª13ª", 13/10/2026).
        b.corridas = decidir([b], True, sids={sid})[0].corridas
    return True


def _limpar_opcodes(opcodes, a, b):
    """
    Junta mudanças separadas só por um espaço ou uma palavra curta: "a b c" →
    "x y z" vira um trecho que sai e um que entra, e não seis marcas
    alternadas que ninguém consegue ler.
    """
    saida = [list(op) for op in opcodes]
    # Igual curto entre duas mudanças: vira parte da mudança.
    i = 1
    while i < len(saida) - 1:
        tag, i1, i2, j1, j2 = saida[i]
        if tag == "equal" and saida[i - 1][0] != "equal" and saida[i + 1][0] != "equal":
            pedaco = "".join(a[i1:i2])
            if len(pedaco.strip()) <= 3 or len(pedaco) <= 4:
                ant, prox = saida[i - 1], saida[i + 1]
                saida[i - 1] = ["replace", ant[1], prox[2], ant[3], prox[4]]
                del saida[i:i + 2]
                continue
        i += 1
    return [tuple(x) for x in saida]


def inserir_texto(b: Bloco, posicao: int, texto: str, sid: str, rodada: int) -> bool:
    """Texto novo dentro do bloco, na posição do texto visível."""
    atual = b.texto
    posicao = max(0, min(len(atual), posicao))
    return reescrever(b, atual[:posicao] + texto + atual[posicao:], sid, rodada)


def substituir_trecho(b: Bloco, inicio: int, fim: int, novo: str, sid: str, rodada: int) -> bool:
    atual = b.texto
    return reescrever(b, atual[:inicio] + novo + atual[fim:], sid, rodada)


def marcar_bloco(b: Bloco, sug: str, sid: str, rodada: int) -> None:
    b.sug, b.sid, b.rodada = sug, sid, rodada


def bloco_novo(tipo: str, texto: str, existentes: set, sid: str = "", rodada: int = 0, *, lista: str = "",
               nivel: int = 0, alinhar: str = "", marcas: tuple = ()) -> Bloco:
    """Um bloco que entra inteiro, marcado como sugestão."""
    b = Bloco(id=novo_id(existentes), tipo=tipo if tipo in TIPOS and tipo != "table" else "p", alinhar=alinhar,
              lista=lista, nivel=nivel)
    partes = normalizar_espacos(texto).split("\n")
    for i, parte in enumerate(partes):
        if i:
            b.corridas.append(Corrida("\n", marcas))
        if parte:
            b.corridas.append(Corrida(parte, marcas))
    if sid:
        b.sug, b.sid, b.rodada = "ins", sid, rodada
    return b


# ------------------------------------------------------------------ remendos

def unidades(blocos: list[Bloco]) -> list[list[Bloco]]:
    """
    Os pedaços de primeiro nível da folha: cada bloco sozinho, e os itens de
    uma lista juntos (na tela eles moram dentro do mesmo <ul>/<ol>).
    """
    saida: list[list[Bloco]] = []
    for b in blocos:
        if b.tipo == "li" and saida and saida[-1][-1].tipo == "li":
            saida[-1].append(b)
        else:
            saida.append([b])
    return saida


def remendos(antes: list[Bloco], depois: list[Bloco]) -> list[dict]:
    """
    O que a tela precisa trocar para sair de `antes` e chegar em `depois`, um
    pedaço por vez: "troque os blocos [b3, b4] por este HTML". Cada remendo
    leva o texto que cada bloco tinha (`antes`) - se a pessoa mexeu num deles
    enquanto o modelo escrevia, a tela não passa por cima (conflito).

    A unidade é o pedaço de primeiro nível da folha (o bloco, ou a lista
    inteira). Inserção pura vai ancorada no pedaço anterior (troca [b3] por
    b3 + novo); no começo do documento, no seguinte.
    """
    u_velhas = unidades(antes)
    u_novas = unidades(depois)
    h_velhas = [html(u) for u in u_velhas]
    h_novas = [html(u) for u in u_novas]
    saida: list[dict] = []

    def ids_de(us) -> list[str]:
        return [b.id for u in us for b in u]

    def remendo(velhas, novas) -> dict:
        ids = ids_de(velhas)
        mapa = {b.id: b for u in velhas for b in u}
        return {"ids": ids, "antes": {i: mapa[i].texto for i in ids},
                "html": "".join(html(u) for u in novas), "blocos": ids_de(novas)}

    casar = difflib.SequenceMatcher(None, h_velhas, h_novas, autojunk=False)
    for op, i1, i2, j1, j2 in casar.get_opcodes():
        if op == "equal":
            continue
        if op in ("replace", "delete"):
            saida.append(remendo(u_velhas[i1:i2], u_novas[j1:j2]))
            continue
        # insert: ancora no pedaço anterior, que não mudou.
        if i1 > 0:
            saida.append(remendo(u_velhas[i1 - 1:i1], u_velhas[i1 - 1:i1] + u_novas[j1:j2]))
        elif i1 < len(u_velhas):
            saida.append(remendo(u_velhas[i1:i1 + 1], u_novas[j1:j2] + u_velhas[i1:i1 + 1]))
        else:
            saida.append({"ids": [], "antes": {}, "html": "".join(html(u) for u in u_novas[j1:j2]),
                          "blocos": ids_de(u_novas[j1:j2])})
    # Dois remendos ancorados no mesmo pedaço (inserção logo depois de uma
    # troca) viram um só: a tela troca o intervalo uma vez.
    return _juntar_remendos(saida, antes)


def _juntar_remendos(lista: list[dict], antes: list[Bloco]) -> list[dict]:
    ordem = {b.id: i for i, b in enumerate(antes)}
    juntos: list[dict] = []
    for r in lista:
        if juntos and r["ids"] and juntos[-1]["ids"] and set(r["ids"]) & set(juntos[-1]["ids"]):
            anterior = juntos[-1]
            ids = sorted(set(anterior["ids"]) | set(r["ids"]), key=lambda i: ordem.get(i, 0))
            # O bloco âncora aparece nos dois HTMLs: fica o do primeiro.
            blocos_novos = ler(anterior["html"]) + [b for b in ler(r["html"]) if b.id not in set(anterior["blocos"])]
            juntos[-1] = {"ids": ids, "antes": {**anterior["antes"], **r["antes"]}, "html": html(blocos_novos),
                          "blocos": [b.id for b in blocos_novos]}
        else:
            juntos.append(r)
    return juntos


def aplicar_remendos(blocos: list[Bloco], lista: list[dict]) -> tuple[list[Bloco], list[dict]]:
    """
    Os remendos sobre um documento que pode ter mudado desde que foram feitos.
    O remendo cujo bloco mudou de texto (ou sumiu) não entra: volta em
    `conflitos`, para a resposta dizer o que não deu.
    """
    atual = list(blocos)
    conflitos: list[dict] = []
    for r in lista:
        ids = r.get("ids") or []
        novos = ler(r.get("html") or "") if r.get("html") else []
        if not ids:
            if atual:
                conflitos.append(r)
            else:
                atual = novos
            continue
        mapa = {b.id: b for b in atual}
        # A tela já gravou o documento com este remendo (ele foi aplicado ao
        # vivo): não é conflito, e aplicar de novo duplicaria o que entrou.
        ja = [mapa.get(b.id) for b in novos]
        saem = [i for i in ids if i not in {b.id for b in novos}]
        if all(ja) and not any(i in mapa for i in saem) and (not novos or html(ja) == html(novos)):
            continue
        if any(i not in mapa for i in ids) or any(normalizar_espacos(mapa[i].texto) !=
                                                    normalizar_espacos(r.get("antes", {}).get(i, mapa[i].texto))
                                                    for i in ids):
            conflitos.append(r)
            continue
        posicoes = sorted(indice(atual, i) for i in ids)
        if posicoes != list(range(posicoes[0], posicoes[0] + len(posicoes))):
            conflitos.append(r)
            continue
        atual = atual[:posicoes[0]] + novos + atual[posicoes[-1] + 1:]
    return _dar_nomes(atual), conflitos


# ------------------------------------------------------------------- texto

def para_modelo(blocos: list[Bloco], ids: list[str] | None = None, rotulos: dict | None = None,
                limite: int = 0) -> str:
    """
    O documento como o modelo lê: uma linha por bloco, com o nome na frente.
    `[b12 · Cláusula 4ª] O LOCATÁRIO pagará...` - é por esse nome que ele
    aponta o lugar da mudança.
    """
    linhas = []
    total = 0
    alvo = set(ids) if ids else None
    for b in blocos:
        if alvo is not None and b.id not in alvo:
            continue
        rotulo = (rotulos or {}).get(b.id, "")
        cabeca = b.id + (f" · {rotulo}" if rotulo else "")
        if b.tipo in ("h1", "h2", "h3", "h4"):
            cabeca += " · título"
        elif b.tipo == "li":
            cabeca += " · item"
        elif b.tipo == "table":
            cabeca += " · quadro"
        texto = (b.num + " " if b.num else "") + b.texto.replace("\n", " / ")
        linha = f"[{cabeca}] {texto}"
        total += len(linha)
        if limite and total > limite:
            linhas.append("[…o documento continua…]")
            break
        linhas.append(linha)
    return "\n".join(linhas)


def texto_puro(blocos: list[Bloco]) -> str:
    return "\n".join(((b.num + " ") if b.num else "") + b.texto for b in blocos).strip()
