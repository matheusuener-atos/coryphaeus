"""
PAULUS - Documento de texto.

Guarda o documento, conta versoes, e transforma o que o editor produz em PDF e
em DOCX.

O editor da tela escreve HTML, porque e o que um campo editavel do navegador
sabe produzir sem biblioteca nenhuma. Mas HTML nao e o documento: e a forma de
digitar. O documento de verdade e a lista de blocos que sai daqui - paragrafo,
alinhamento, trechos em negrito - e e dela que saem tanto o PDF quanto o DOCX.

Isso importa porque um caminho separado para cada formato produz dois
documentos diferentes com o mesmo nome. Num contrato, "a versao em PDF esta
diferente da versao em Word" nao e detalhe de formatacao.

O PDF e o formato canonico: e o que a tela de pre-visualizacao mostra, e o que
vai para a assinatura. O DOCX existe para quem precisa continuar editando no
Word, e a tela diz isso.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import leitor_pdf

# A4 com margens de 2,5 cm, como o wireframe pede.
MARGEM_CM = 2.5
CORPO_PT = 12

# ------------------------------------------------------ o formato da folha
#
# So o que muda de documento para documento. A4 e margem de 2,5 cm ficam
# iguais para todos: sao as medidas da peca juridica brasileira, e escolher
# outra coisa seria oferecer um jeito de errar.
#
# A fonte vem em par - a do PDF e a do DOCX - porque o mesmo documento sai nos
# dois. Antes o PDF saia em Times e o DOCX em Georgia, e ninguem tinha decidido
# isso: era o padrao de cada biblioteca aparecendo por baixo.
FONTES = {
    "serifada": {"pdf": "Times-Roman", "pdf_negrito": "Times-Bold",
                 "docx": "Times New Roman", "nome": "Times (serifada)"},
    "sem-serifa": {"pdf": "Helvetica", "pdf_negrito": "Helvetica-Bold",
                   "docx": "Arial", "nome": "Arial (sem serifa)"},
}
CORPOS = (11, 12, 13)
# 0 = sem recuo; 1,25 cm e a tabulacao herdada do Word; 2 cm e o que a maior
# parte dos manuais de peticao pede.
RECUOS_CM = (0.0, 1.25, 2.0)
ENTRELINHAS = (1.0, 1.5, 2.0)

FORMATO_PADRAO = {
    "fonte": "serifada",
    "corpo": CORPO_PT,
    "recuo_cm": 0.0,
    "entrelinhas": 1.5,
}

# Ainda usado pelo DOCX quando nenhum formato e passado.
FONTE_PADRAO = FONTES[FORMATO_PADRAO["fonte"]]["docx"]


def _uma_das(valor, opcoes: tuple, padrao):
    """O valor, se for um dos que o PDF sabe produzir. Senao, o padrao."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return padrao
    for o in opcoes:
        if abs(n - o) < 0.001:
            return o
    return padrao


def normalizar_formato(bruto) -> dict:
    """
    O formato pedido, reduzido ao que o PDF sabe produzir.

    Aceitar corpo 7,5 pt ou uma fonte que o reportlab nao tem daria um PDF
    diferente do que a tela mostrou - e a tela promete ser o arquivo. Fora da
    lista, volta para o padrao em vez de tentar o mais parecido: "quase o que
    voce pediu" e a resposta que ninguem consegue conferir.
    """
    import json

    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto or "{}")
        except json.JSONDecodeError:
            bruto = {}
    if not isinstance(bruto, dict):
        bruto = {}

    fonte = bruto.get("fonte")
    return {
        "fonte": fonte if fonte in FONTES else FORMATO_PADRAO["fonte"],
        "corpo": int(_uma_das(bruto.get("corpo"), CORPOS, FORMATO_PADRAO["corpo"])),
        "recuo_cm": _uma_das(bruto.get("recuo_cm"), RECUOS_CM, FORMATO_PADRAO["recuo_cm"]),
        "entrelinhas": _uma_das(bruto.get("entrelinhas"), ENTRELINHAS,
                                FORMATO_PADRAO["entrelinhas"]),
        "folha": normalizar_folha(bruto.get("folha")),
    }


# ------------------------------------------------- a folha: timbre e rodape
#
# O que se desenha em volta do texto, em toda pagina: o cabecalho (o papel
# timbrado), o rodape e o numero da pagina. E do documento, e nao do
# escritorio inteiro: a peca protocolada sai timbrada, a minuta interna nao.
#
# "padrao" segue a chave de Configuracoes, como era antes de a folha existir:
# documento que ninguem mexeu continua saindo igual.
CABECALHOS = ("padrao", "escritorio", "proprio", "nenhum")
RODAPES = ("titulo", "proprio", "nenhum")
NUMERACOES = ("pagina", "pagina_de", "numero", "nenhuma")
LADOS = ("esquerda", "centro", "direita")
LINHAS_DO_CABECALHO = 4

FOLHA_PADRAO = {
    "cabecalho": "padrao",
    "linhas": [],
    "logo": True,
    "alinhar": "centro",
    "fio": True,
    "rodape": "titulo",
    "rodape_texto": "",
    "numeracao": "pagina",
    "numeracao_onde": "direita",
}
FORMATO_PADRAO["folha"] = FOLHA_PADRAO


def normalizar_folha(bruto) -> dict:
    """A folha pedida, reduzida ao que o PDF desenha. Fora da lista, o padrao."""
    if not isinstance(bruto, dict):
        bruto = {}

    def uma(chave, opcoes):
        valor = bruto.get(chave)
        return valor if valor in opcoes else FOLHA_PADRAO[chave]

    linhas = bruto.get("linhas")
    if not isinstance(linhas, list):
        linhas = []
    linhas = [" ".join(str(x).split())[:130] for x in linhas][:LINHAS_DO_CABECALHO]
    # Linha vazia no fim nao e linha: e o campo que a pessoa deixou em branco.
    while linhas and not linhas[-1]:
        linhas.pop()

    return {
        "cabecalho": uma("cabecalho", CABECALHOS),
        "linhas": linhas,
        "logo": bool(bruto.get("logo", FOLHA_PADRAO["logo"])),
        "alinhar": uma("alinhar", LADOS),
        "fio": bool(bruto.get("fio", FOLHA_PADRAO["fio"])),
        "rodape": uma("rodape", RODAPES),
        "rodape_texto": " ".join(str(bruto.get("rodape_texto") or "").split())[:110],
        "numeracao": uma("numeracao", NUMERACOES),
        "numeracao_onde": uma("numeracao_onde", LADOS),
    }


# O que a regra resolve sem modelo: e o grosso dos pedidos ("pagina 1 de 3",
# "sem logo", "centralizado"), e responde na hora.
_REGRAS_DA_FOLHA = (
    (r"\bde\s+(y|n|total)\b|p[aá]gina\s*\w*\s*de\s*\w+|x\s*de\s*y", {"numeracao": "pagina_de"}),
    (r"sem\s+numera|sem\s+n[uú]mero", {"numeracao": "nenhuma"}),
    (r"s[oó]\s+o\s+n[uú]mero", {"numeracao": "numero"}),
    (r"sem\s+(cabe[cç]alho|timbre)", {"cabecalho": "nenhum"}),
    (r"sem\s+logo", {"logo": False}),
    (r"com\s+(a\s+)?logo", {"logo": True}),
    (r"sem\s+(o\s+)?(fio|linha|tra[cç]o)", {"fio": False}),
    (r"sem\s+rodap[eé]", {"rodape": "nenhum"}),
    # O lado do cabecalho so quando a frase fala do cabecalho: "numeracao no
    # centro" nao pode centralizar o timbre. A virgula separa os assuntos.
    (r"(timbre|cabe[cç]alho|logo)\s+[^.,]*\b(centraliz\w*|centrad\w*|no\s+centro)", {"alinhar": "centro"}),
    (r"(timbre|cabe[cç]alho|logo)\s+[^.,]*\besquerda", {"alinhar": "esquerda"}),
    (r"(timbre|cabe[cç]alho|logo)\s+[^.,]*\bdireita", {"alinhar": "direita"}),
    (r"n[uú]mer\w*\s+[^.]*\b(no\s+)?centro", {"numeracao_onde": "centro"}),
    (r"n[uú]mer\w*\s+[^.]*\besquerda", {"numeracao_onde": "esquerda"}),
)


def sugerir_folha(pedido: str, atual: dict, escritorio: list[str], titulo: str,
                   perguntar=None) -> dict:
    """
    A folha que o pedido descreve, partindo da atual. Nao grava: a tela mostra
    e a pessoa aplica.

    A regra resolve o que e escolha (numeracao, alinhamento, logo). O modelo
    so escreve texto - as linhas do cabecalho e o rodape - e so com os dados
    que o escritorio ja cadastrou: linha com numero que nao esta nos dados nem
    no pedido e descartada, porque OAB e telefone inventados num timbre sao
    piores que timbre nenhum.
    """
    import re as _re

    folha = dict(normalizar_folha(atual))
    baixo = pedido.lower()
    feitas = []
    for padrao, mudanca in _REGRAS_DA_FOLHA:
        if _re.search(padrao, baixo):
            folha.update(mudanca)
            feitas.append(mudanca)

    quer_texto = _re.search(r"cabe[cç]alho|timbr|rodap[eé]|escrev|slogan|frase|nome|endere|contato|site|telefone|e-?mail|oab", baixo)
    nota = ""
    if quer_texto and perguntar:
        dados = "\n".join(escritorio) or "(nenhum dado profissional cadastrado)"
        sistema = ("Você monta o papel timbrado de documentos de um escritório de advocacia brasileiro. "
                   "Use SOMENTE os dados fornecidos; nunca invente número de OAB, CPF, telefone, endereço ou e-mail.")
        instrucao = (f"Dados do escritório:\n{dados}\n\nTítulo do documento: {titulo}\n\n"
                     f"Pedido: {pedido}\n\nEscreva o cabeçalho (até 4 linhas curtas; a primeira é o nome, em destaque) "
                     "e, se o pedido falar de rodapé, um texto curto para o rodapé.")
        esquema = '{"linhas": ["linha 1", "linha 2"], "rodape_texto": ""}'
        try:
            r = perguntar(instrucao, sistema, esquema)
        except Exception:
            r = None
        if isinstance(r, dict):
            fonte = (dados + " " + pedido).replace(" ", "")
            linhas = []
            for linha in r.get("linhas") or []:
                linha = " ".join(str(linha).split())
                numeros = _re.findall(r"\d[\d.\-/]{2,}", linha)
                if linha and all(n.replace(" ", "") in fonte for n in numeros):
                    linhas.append(linha)
            if linhas:
                folha["cabecalho"] = "proprio"
                folha["linhas"] = linhas[:LINHAS_DO_CABECALHO]
            rodape = " ".join(str(r.get("rodape_texto") or "").split())
            if rodape and _re.search(r"rodap[eé]", baixo) and "sem rodap" not in baixo:
                folha["rodape"] = "proprio"
                folha["rodape_texto"] = rodape
        else:
            nota = "o modelo não respondeu; apliquei só o que a regra entende"
    elif quer_texto and not folha["linhas"] and escritorio:
        folha["cabecalho"] = "proprio"
        folha["linhas"] = escritorio[:LINHAS_DO_CABECALHO]

    return {"folha": normalizar_folha(folha), "regras": len(feitas), "nota": nota}


def texto_do_rodape(folha: dict, titulo: str) -> str:
    """O texto do rodape desta folha: o titulo, o que a pessoa escreveu ou nada."""
    folha = normalizar_folha(folha)
    if folha["rodape"] == "nenhum":
        return ""
    if folha["rodape"] == "proprio":
        return folha["rodape_texto"]
    return titulo or ""


def numero_da_pagina(numeracao: str, pagina: int, total: int = 0) -> str:
    """Como o numero aparece: 'página 2', 'página 2 de 5', '2' ou nada."""
    if numeracao == "nenhuma":
        return ""
    if numeracao == "numero":
        return str(pagina)
    if numeracao == "pagina_de" and total:
        return f"página {pagina} de {total}"
    return f"página {pagina}"


def desenho_da_folha(timbre: dict | None, formato, titulo: str = "") -> dict:
    """
    O que o editor desenha em volta do texto em cada pagina da tela: as linhas
    do cabecalho ja resolvidas, se ha logo, o rodape e as medidas. E a mesma
    conta do PDF, para a folha na tela ser a folha impressa.
    """
    folha = normalizar_formato(formato)["folha"]
    linhas = _linhas_do_timbre(timbre) if timbre else []
    return {
        "linhas": linhas,
        "logo": bool(linhas and timbre and _logo_do_timbre(timbre)),
        "logo_cm": LOGO_ALTURA_CM,
        "alinhar": folha["alinhar"],
        "fio": folha["fio"],
        "rodape": texto_do_rodape(folha, titulo),
        "numeracao": folha["numeracao"],
        "numeracao_onde": folha["numeracao_onde"],
        **medidas_da_folha(timbre if linhas else None),
    }


def medidas_da_folha(timbre: dict | None) -> dict:
    """
    Onde o texto comeca e termina na folha, em centimetros - o que o editor
    precisa para desenhar as paginas na tela no mesmo lugar que o PDF.
    """
    from reportlab.lib.units import cm

    alto = _altura_do_timbre(timbre) / cm if timbre else 0
    return {"largura_cm": 21.0, "altura_cm": 29.7, "margem_cm": MARGEM_CM,
            "topo_cm": round(MARGEM_CM + alto, 3), "base_cm": MARGEM_CM}


ALINHAMENTOS = {
    "esquerda": "Alinhado à esquerda",
    "centro": "Centralizado",
    "direita": "Alinhado à direita",
    "justificado": "Justificado",
}


@dataclass
class Trecho:
    """Um pedaco de texto com a mesma formatacao do inicio ao fim."""

    texto: str = ""
    negrito: bool = False
    italico: bool = False
    sublinhado: bool = False
    riscado: bool = False


@dataclass
class Bloco:
    """Um paragrafo, titulo ou item de lista."""

    tipo: str = "paragrafo"   # paragrafo | titulo1..3 | item | numerado | tabela
    alinhamento: str = "esquerda"
    trechos: list[Trecho] = field(default_factory=list)
    # Quadro de parcelas, de honorarios, de bens. As celulas sao texto puro:
    # negrito dentro de celula de quadro nao aparece em contrato, e o que
    # importa aqui e que o texto sobreviva inteiro ao PDF e ao DOCX.
    linhas: list[list[str]] = field(default_factory=list)

    @property
    def texto(self) -> str:
        if self.tipo == "tabela":
            return "\n".join(" · ".join(c for c in linha if c) for linha in self.linhas)
        return "".join(t.texto for t in self.trechos)

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "alinhamento": self.alinhamento,
            "texto": self.texto,
            "trechos": [t.__dict__ for t in self.trechos],
            "linhas": self.linhas,
        }


# ------------------------------------------------------------ ler o HTML


BLOCOS = {
    "p": "paragrafo", "div": "paragrafo",
    "h1": "titulo1", "h2": "titulo2", "h3": "titulo3",
    "li": "item",
}
MARCAS = {
    "b": "negrito", "strong": "negrito",
    "i": "italico", "em": "italico",
    "u": "sublinhado",
    "s": "riscado", "strike": "riscado", "del": "riscado",
}


class _Leitor(HTMLParser):
    """
    Le o HTML do editor e devolve blocos.

    Nao pretende entender HTML em geral: entende o que um campo editavel
    produz. Marcacao desconhecida vira texto, nunca some - perder texto de um
    contrato por causa de uma tag inesperada seria o pior resultado possivel.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocos: list[Bloco] = []
        self._atual: Bloco | None = None
        self._marcas: list[str] = []
        self._lista: list[str] = []       # pilha de ul/ol
        self._ignorar = 0
        self._quadro: list[list[str]] | None = None
        self._linha: list[str] | None = None
        self._celula: str | None = None

    # ---------------------------------------------------------- estrutura

    def _abrir(self, tipo: str, alinhamento: str = "") -> None:
        self._fechar()
        self._atual = Bloco(tipo=tipo, alinhamento=alinhamento or "esquerda")

    def _fechar(self) -> None:
        if self._atual and self._atual.trechos:
            self.blocos.append(self._atual)
        self._atual = None

    # -------------------------------------------------------------- quadro
    #
    # Quadro de parcelas, de honorarios, de bens. Dentro dele o texto vai para
    # a celula, e nao vira paragrafo: sem isso, um quadro de seis linhas saia
    # do PDF como dezoito paragrafos soltos.

    def _abrir_quadro(self) -> None:
        self._fechar()
        self._quadro = []
        self._linha = None
        self._celula = None

    def _fechar_quadro(self) -> None:
        self._fechar_linha()
        linhas = list(self._quadro or [])
        self._quadro = None
        # Linha em branco no meio do quadro fica: a pre-visualizacao promete
        # ser o arquivo, e uma linha que aparece no editor e some do PDF quebra
        # essa promessa. Quadro inteiro em branco e que nao vira nada.
        if not any(c.strip() for l in linhas for c in l):
            return
        # Toda linha com o mesmo numero de colunas: uma celula a menos numa
        # linha desalinha o quadro inteiro na folha.
        largura = max(len(l) for l in linhas)
        self.blocos.append(Bloco(
            tipo="tabela",
            linhas=[l + [""] * (largura - len(l)) for l in linhas],
        ))

    def _fechar_linha(self) -> None:
        self._fechar_celula()
        if self._linha is not None and self._quadro is not None:
            self._quadro.append(self._linha)
        self._linha = None

    def _fechar_celula(self) -> None:
        if self._celula is None:
            return
        if self._linha is None:
            self._linha = []
        self._linha.append(" ".join(self._celula.split()))
        self._celula = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorar += 1
            return

        atributos = dict(attrs)
        if tag == "table":
            self._abrir_quadro()
            return
        if self._quadro is not None:
            if tag == "tr":
                self._fechar_linha()
                self._linha = []
                return
            if tag in ("td", "th"):
                self._fechar_celula()
                self._celula = ""
                return
            if tag == "br" and self._celula is not None:
                self._celula += " "
                return
            if tag in MARCAS:
                # A marca e ignorada dentro do quadro, mas o texto dela nao.
                self._marcas.append(MARCAS[tag])
                return
            if tag in BLOCOS:
                return
        if tag == "br":
            self._quebra()
            return
        if tag in ("ul", "ol"):
            self._lista.append(tag)
            return
        if tag in BLOCOS:
            tipo = BLOCOS[tag]
            if tag == "li":
                tipo = "numerado" if (self._lista and self._lista[-1] == "ol") else "item"
            self._abrir(tipo, _alinhamento(atributos))
            return
        if tag in MARCAS:
            self._marcas.append(MARCAS[tag])
            return
        # span com estilo: negrito e italico tambem chegam assim.
        if tag == "span":
            estilo = (atributos.get("style") or "").lower()
            if "bold" in estilo or "font-weight: 7" in estilo:
                self._marcas.append("negrito")
            elif "italic" in estilo:
                self._marcas.append("italico")
            elif "underline" in estilo:
                self._marcas.append("sublinhado")
            else:
                self._marcas.append("")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._ignorar = max(0, self._ignorar - 1)
            return
        if tag == "table":
            self._fechar_quadro()
            return
        if self._quadro is not None:
            if tag == "tr":
                self._fechar_linha()
            elif tag in ("td", "th"):
                self._fechar_celula()
            elif tag in MARCAS and self._marcas:
                self._marcas.pop()
            return
        if tag in ("ul", "ol"):
            if self._lista:
                self._lista.pop()
            return
        if tag in BLOCOS:
            self._fechar()
            return
        if tag in MARCAS or tag == "span":
            if self._marcas:
                self._marcas.pop()

    def handle_data(self, dados):
        if self._ignorar:
            return
        self._texto(dados)

    def _quebra(self) -> None:
        """<br> e quebra de verdade, dentro do paragrafo."""
        if self._atual is None:
            self._atual = Bloco()
        if self._atual.trechos:
            self._atual.trechos[-1].texto += "\n"
        else:
            self._atual.trechos.append(Trecho(texto="\n"))

    def _texto(self, bruto: str) -> None:
        texto = bruto.replace("\xa0", " ")

        # Dentro do quadro o texto e da celula. Fora de celula, entre <tr> e
        # <td>, e so a indentacao do HTML e nao e conteudo de nada.
        if self._quadro is not None:
            if self._celula is not None:
                self._celula += texto
            return

        # Espaco e quebra de linha ENTRE tags sao formatacao do HTML, nao
        # conteudo. Tratar isso como texto criava um paragrafo vazio a cada
        # linha do fonte - um documento de nove blocos virava dezessete, e o
        # PDF saia com o dobro de espaco entre as clausulas.
        if not texto.strip():
            if self._atual and self._atual.trechos:
                if not self._atual.trechos[-1].texto.endswith((" ", "\n")):
                    self._atual.trechos[-1].texto += " "
            return

        # Quebra de linha DENTRO do texto e espaco, na regra do HTML. Só o <br>
        # quebra. Sem isto, um paragrafo escrito em tres linhas no fonte saia
        # do PDF quebrado em tres linhas no meio da frase.
        texto = re.sub(r"\s+", " ", texto)

        if self._atual is None:
            self._atual = Bloco()

        marcas = set(self._marcas)
        self._atual.trechos.append(Trecho(
            texto=texto,
            negrito="negrito" in marcas,
            italico="italico" in marcas,
            sublinhado="sublinhado" in marcas,
            riscado="riscado" in marcas,
        ))

    def resultado(self) -> list[Bloco]:
        # HTML colado de fora as vezes chega com o </table> faltando. Fechar
        # aqui e a diferenca entre o quadro sair no PDF e o quadro sumir.
        if self._quadro is not None:
            self._fechar_quadro()
        self._fechar()
        return self.blocos


def _alinhamento(atributos: dict) -> str:
    estilo = (atributos.get("style") or "").lower()
    for chave, valor in (("center", "centro"), ("right", "direita"), ("justify", "justificado")):
        if f"text-align: {chave}" in estilo or f"text-align:{chave}" in estilo:
            return valor
    return (atributos.get("align") or "").lower().replace("center", "centro") or "esquerda"


def ler_html(html: str) -> list[Bloco]:
    """O HTML do editor virando documento."""
    leitor = _Leitor()
    leitor.feed(html or "")
    leitor.close()
    return leitor.resultado()


def para_texto(blocos: list[Bloco]) -> str:
    """O documento em texto puro - para busca, contagem e para o assistente."""
    return "\n".join(b.texto for b in blocos).strip()


def contar(blocos: list[Bloco]) -> dict:
    """
    Palavras, caracteres e uma estimativa de paginas.

    Paginas so o gerador de PDF sabe de verdade; aqui e estimativa para a
    barra de status, e a tela de pre-visualizacao mostra o numero real.
    """
    texto = para_texto(blocos)
    palavras = len([p for p in re.split(r"\s+", texto) if p])
    return {
        "palavras": palavras,
        "caracteres": len(texto),
        "blocos": len(blocos),
    }


# ------------------------------------------------------------------ PDF


class _Paragrafo:
    """
    Um paragrafo que lembra de que bloco do editor veio, mesmo partido.

    Quando um paragrafo nao cabe no que sobra da pagina, o reportlab o divide
    em dois paragrafos novos - e os novos nao herdam nada que eu tenha
    pendurado no original. Sem repassar a marca na divisao, todo paragrafo que
    atravessa uma quebra sumiria do mapa de paginas, que e exatamente o
    paragrafo sobre o qual a pergunta "em que pagina isso cai?" e interessante.

    E uma classe montada na hora porque o reportlab so entra na funcao: manter
    o import no topo do modulo custaria o carregamento do reportlab em toda
    importacao de `documento`, e quase tudo aqui nao gera PDF nenhum.
    """

    _classe = None

    def __new__(cls, *args, **kwargs):
        if cls._classe is None:
            from reportlab.platypus import Paragraph

            class Paragrafo(Paragraph):
                blocos: list[int] = []

                def split(self, largura, altura):
                    partes = Paragraph.split(self, largura, altura)
                    for parte in partes:
                        parte.blocos = self.blocos
                    return partes

            cls._classe = Paragrafo
        return cls._classe(*args, **kwargs)


def _estilos(formato: dict) -> dict:
    """Os estilos do PDF para este formato. Titulo nao leva recuo."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm

    fonte = FONTES[formato["fonte"]]
    normal, negrito = fonte["pdf"], fonte["pdf_negrito"]
    corpo, entre = formato["corpo"], formato["entrelinhas"]

    return {
        "paragrafo": ParagraphStyle(
            "corpo", fontName=normal, fontSize=corpo, leading=corpo * entre,
            spaceAfter=8, firstLineIndent=formato["recuo_cm"] * cm),
        # Recuo de primeira linha e coisa de paragrafo: um titulo recuado fica
        # torto no meio da folha.
        "titulo1": ParagraphStyle("t1", fontName=negrito, fontSize=corpo + 4,
                                  leading=(corpo + 4) * 1.25, spaceBefore=12, spaceAfter=10),
        "titulo2": ParagraphStyle("t2", fontName=negrito, fontSize=corpo + 1.5,
                                  leading=(corpo + 1.5) * 1.32, spaceBefore=10, spaceAfter=8),
        "titulo3": ParagraphStyle("t3", fontName=negrito, fontSize=corpo,
                                  leading=corpo * 1.34, spaceBefore=8, spaceAfter=6),
        # Item de lista ja e recuado pela propria lista.
        "item": ParagraphStyle("item", fontName=normal, fontSize=corpo,
                               leading=corpo * entre, spaceAfter=8),
    }


def _montar_fluxo(blocos: list[Bloco], estilos: dict, formato: dict) -> list:
    """
    Os blocos do editor viram os elementos que o reportlab empilha na folha.

    Cada elemento leva consigo de que bloco veio - e o que permite dizer
    depois em que pagina cada paragrafo caiu, sem estimar nada.
    """
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import ListFlowable, ListItem, Spacer

    alinha = {
        "esquerda": TA_LEFT, "centro": TA_CENTER,
        "direita": TA_RIGHT, "justificado": TA_JUSTIFY,
    }
    fluxo: list = []
    itens: list = []
    de_itens: list[int] = []
    ordenada = False

    def despejar_lista():
        nonlocal itens, ordenada, de_itens
        if not itens:
            return
        lista = ListFlowable(
            itens, bulletType="1" if ordenada else "bullet",
            leftIndent=18, bulletFontName=FONTES[formato["fonte"]]["pdf"],
        )
        lista.blocos = list(de_itens)
        fluxo.append(lista)
        fluxo.append(Spacer(1, 6))
        itens, de_itens = [], []

    for numero, bloco in enumerate(blocos):
        # O quadro vem antes da checagem de texto: as celulas dele nao passam
        # por _para_marcacao, e o teste de vazio jogaria fora a tabela inteira.
        if bloco.tipo == "tabela":
            despejar_lista()
            quadro = _quadro_pdf(bloco, estilos, formato)
            if quadro is not None:
                quadro.blocos = [numero]
                fluxo.append(quadro)
                fluxo.append(Spacer(1, 8))
            continue

        marcado = _para_marcacao(bloco)
        if not marcado.strip():
            continue

        if bloco.tipo in ("item", "numerado"):
            if itens and ordenada != (bloco.tipo == "numerado"):
                despejar_lista()
            ordenada = bloco.tipo == "numerado"
            itens.append(ListItem(_Paragrafo(marcado, estilos["item"])))
            de_itens.append(numero)
            continue

        despejar_lista()
        estilo = estilos.get(bloco.tipo, estilos["paragrafo"])
        if bloco.tipo == "paragrafo":
            estilo = ParagraphStyle(
                "p", parent=estilos["paragrafo"],
                alignment=alinha.get(bloco.alinhamento, TA_LEFT),
            )
        paragrafo = _Paragrafo(marcado, estilo)
        paragrafo.blocos = [numero]
        fluxo.append(paragrafo)

    despejar_lista()
    if not fluxo:
        fluxo.append(_Paragrafo("(documento vazio)", estilos["paragrafo"]))
    return fluxo


def _quadro_pdf(bloco: Bloco, estilos: dict, formato: dict):
    """
    O quadro desenhado na folha: primeira linha em negrito, fio fino, e as
    colunas repartindo a largura util igualmente.

    A celula e um Paragraph e nao texto solto de proposito: assim uma
    descricao longa quebra em varias linhas dentro da celula em vez de
    atravessar o quadro e sumir na margem.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle

    # A linha em branco fica: ela existe no editor, e a folha tem que ser o
    # que o editor mostra.
    linhas = [l for l in bloco.linhas if l]
    if not linhas:
        return None

    corpo = formato["corpo"] - 1
    fonte = FONTES[formato["fonte"]]
    dentro = ParagraphStyle("quadro", fontName=fonte["pdf"], fontSize=corpo,
                            leading=corpo * 1.3)
    cabeca = ParagraphStyle("quadro-cabeca", parent=dentro, fontName=fonte["pdf_negrito"])

    colunas = max(len(l) for l in linhas)
    util = A4[0] - 2 * MARGEM_CM * cm
    grade = [[_celula_pdf(str(c), cabeca if i == 0 else dentro)
              for c in (list(l) + [""] * (colunas - len(l)))]
             for i, l in enumerate(linhas)]

    quadro = Table(grade, colWidths=[util / colunas] * colunas, repeatRows=1)
    quadro.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.55, 0.55, 0.55)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.94, 0.94, 0.93)),
    ]))
    return quadro


def _celula_pdf(texto: str, estilo):
    """O conteudo de uma celula. Celula vazia leva um espaco: sem nada dentro o
    reportlab encolhe a linha e o quadro sai torto."""
    from xml.sax.saxutils import escape

    from reportlab.platypus import Paragraph

    return Paragraph(escape(texto) or "&nbsp;", estilo)


def _construir(classe, blocos, titulo, rodape, timbre, formato, total=0):
    """A folha montada uma vez so, para quem quiser os bytes ou as paginas."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    formato = normalizar_formato(formato)
    estilos = _estilos(formato)

    # O timbre ocupa o alto da pagina: sem abrir espaco, o texto passa por
    # cima dele. A margem de cima cresce so quando ha timbre.
    alto = _altura_do_timbre(timbre) if timbre else 0

    saida = io.BytesIO()
    doc = classe(
        saida, pagesize=A4,
        leftMargin=MARGEM_CM * cm, rightMargin=MARGEM_CM * cm,
        topMargin=MARGEM_CM * cm + alto, bottomMargin=MARGEM_CM * cm,
        title=titulo or "Documento", author="PAULUS",
    )
    desenhar = _decorar(rodape, timbre, formato, total)
    doc.build(_montar_fluxo(blocos, estilos, formato),
              onFirstPage=desenhar, onLaterPages=desenhar)
    return saida, doc


def para_pdf(blocos: list[Bloco], titulo: str = "", rodape: str = "",
             timbre: dict | None = None, formato: dict | None = None) -> bytes:
    """
    O documento em PDF, no formato que sai para o cliente.

    Este e o formato canonico: e o que a pre-visualizacao mostra e o que vai
    para a assinatura. A pre-visualizacao desenha este mesmo PDF, entao o que
    aparece na tela e o arquivo, nao uma aproximacao em CSS.
    """
    from reportlab.platypus import SimpleDocTemplate

    total = 0
    if normalizar_formato(formato)["folha"]["numeracao"] == "pagina_de":
        # "pagina 2 de 5" precisa do 5 antes de desenhar a pagina 1: monta uma
        # vez para contar. O rodape nao muda a altura util, entao a conta vale.
        _, rascunho = _construir(SimpleDocTemplate, blocos, titulo, rodape, timbre, formato)
        total = rascunho.page
    saida, _ = _construir(SimpleDocTemplate, blocos, titulo, rodape, timbre, formato, total)
    return saida.getvalue()


def proteger_com_senha(pdf: bytes, senha: str) -> bytes:
    """
    O mesmo PDF, agora pedindo senha para abrir.

    Quem manda uma minuta com o CPF do cliente por e-mail nao controla a caixa
    de entrada de quem recebe. A senha nao e sigilo forte - e a diferenca
    entre o documento abrir sozinho na previa do e-mail e nao abrir.

    A senha e a mesma para abrir e para editar: duas senhas diferentes num
    documento que o escritorio manda pronto so dariam a chance de a pessoa
    guardar a errada. Cifrar reescreve o arquivo inteiro, entao isto vem
    sempre ANTES de qualquer assinatura - depois, quebraria a assinatura.
    """
    import io as _io

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import copy_into_new_writer

    if not senha:
        raise ValueError("escreva a senha que vai abrir o PDF")

    leitor = PdfFileReader(_io.BytesIO(pdf))
    escritor = copy_into_new_writer(leitor)
    escritor.encrypt(senha, senha)
    saida = _io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def mapa_de_paginas(blocos: list[Bloco], timbre: dict | None = None,
                    formato: dict | None = None) -> dict:
    """
    Em que pagina cai cada paragrafo, e quantas paginas o documento tem.

    O editor mostrava "paginas ~4": caracteres divididos por uma media. Erra
    sempre que ha titulo, lista ou paragrafo curto, e erra mais quanto maior o
    documento - justamente quando a pessoa precisa saber.

    Aqui a conta e o proprio PDF sendo montado, o mesmo que a tela desenha.
    Parece caro e nao e: 53 ms num contrato de seis paginas, medido nos
    contratos deste escritorio.

    A pagina de um paragrafo e onde ele COMECA. Paragrafo que atravessa a
    quebra e partido pelo reportlab em pedacos, e cada pedaco lembra de que
    bloco veio - por isso o primeiro pedaco e que manda.
    """
    from reportlab.platypus import SimpleDocTemplate

    onde: dict[int, int] = {}

    class Marcador(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            for numero in getattr(flowable, "blocos", ()):
                onde.setdefault(numero, self.page)

    _, doc = _construir(Marcador, blocos, "", "", timbre, formato)

    # Bloco vazio nao vira elemento nenhum na folha, entao nao tem pagina
    # propria: fica na pagina do paragrafo anterior, que e onde ele esta.
    paginas, ultima = [], 1
    for numero in range(len(blocos)):
        ultima = onde.get(numero, ultima)
        paginas.append(ultima)

    return {"paginas": doc.page, "de_bloco": paginas}


# Quanto o timbre ocupa, em centimetros, por linha que ele tem.
LINHA_TIMBRE_CM = 0.42


# A logo do escritorio, quando existe, ocupa esta altura no alto do papel. A
# largura sai da proporcao da imagem; e a altura que precisa ser constante,
# porque e ela que empurra o texto para baixo.
LOGO_ALTURA_CM = 1.3
LOGO_FOLGA_CM = 0.3


def _logo_do_timbre(timbre: dict):
    """O caminho da logo, se o escritorio enviou uma e ela ainda esta la."""
    caminho = str(timbre.get("logo") or "").strip()
    if not caminho:
        return None
    alvo = Path(caminho)
    return alvo if alvo.exists() else None


def _altura_do_timbre(timbre: dict) -> float:
    from reportlab.lib.units import cm

    linhas = _linhas_do_timbre(timbre)
    if not linhas:
        return 0
    alto_logo = (LOGO_ALTURA_CM + LOGO_FOLGA_CM) if _logo_do_timbre(timbre) else 0
    # O nome vai maior que o resto, e depois vem um fio separando do texto.
    return (alto_logo + 0.62 + LINHA_TIMBRE_CM * (len(linhas) - 1) + 0.55) * cm


def _linhas_do_timbre(timbre: dict) -> list[str]:
    """
    O que entra no timbre, na ordem, pulando o que o escritorio nao preencheu.

    Nada de rotulo vazio: um timbre com "OAB:" e nada depois e pior que um
    timbre sem OAB.

    Timbre com "linhas" e o que a pessoa escreveu na folha do documento: vai
    como esta, a primeira linha em destaque.
    """
    if isinstance(timbre.get("linhas"), list):
        return [str(x).strip() for x in timbre["linhas"] if str(x).strip()][:LINHAS_DO_CABECALHO]

    nome = str(timbre.get("nome", "")).strip()
    if not nome:
        return []

    segunda = " · ".join(x for x in (
        ("OAB " + str(timbre.get("oab", "")).strip()) if timbre.get("oab") else "",
        str(timbre.get("cpf", "")).strip(),
    ) if x)
    terceira = " · ".join(x for x in (
        str(timbre.get("endereco", "")).strip(),
        str(timbre.get("telefone", "")).strip(),
        str(timbre.get("email", "")).strip(),
    ) if x)

    return [x for x in (nome, segunda, terceira) if x]


def _escrever_alinhado(canvas, lado: str, y: float, texto: str) -> None:
    """Uma linha na largura util, do lado pedido."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    if lado == "esquerda":
        canvas.drawString(MARGEM_CM * cm, y, texto)
    elif lado == "direita":
        canvas.drawRightString(A4[0] - MARGEM_CM * cm, y, texto)
    else:
        canvas.drawCentredString(A4[0] / 2, y, texto)


def _decorar(rodape: str, timbre: dict | None, formato: dict | None = None, total: int = 0):
    """Numero de pagina no rodape, e o timbre no alto quando ha um."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    formato = normalizar_formato(formato)
    folha = formato["folha"]
    fonte = FONTES[formato["fonte"]]
    linhas = _linhas_do_timbre(timbre) if timbre else []
    numerar = _numerar(rodape, fonte["pdf"], folha, total)
    lado = folha["alinhar"]

    logo = _logo_do_timbre(timbre) if timbre else None

    def desenhar(canvas, doc):
        if linhas:
            canvas.saveState()
            topo = A4[1] - MARGEM_CM * cm
            if logo:
                topo = _desenhar_logo(canvas, logo, topo, lado)
            canvas.setFillGray(0.1)
            canvas.setFont(fonte["pdf_negrito"], 12)
            _escrever_alinhado(canvas, lado, topo - 0.3 * cm, linhas[0][:90])

            canvas.setFont(fonte["pdf"], 8.5)
            canvas.setFillGray(0.35)
            for i, linha in enumerate(linhas[1:], start=1):
                _escrever_alinhado(
                    canvas, lado, topo - 0.3 * cm - (0.62 + LINHA_TIMBRE_CM * (i - 1)) * cm,
                    linha[:130])

            if folha["fio"]:
                fio = topo - _altura_do_timbre(timbre) + 0.3 * cm
                if logo:
                    fio += (LOGO_ALTURA_CM + LOGO_FOLGA_CM) * cm
                canvas.setStrokeGray(0.75)
                canvas.setLineWidth(0.6)
                canvas.line(MARGEM_CM * cm, fio, A4[0] - MARGEM_CM * cm, fio)
            canvas.restoreState()
        numerar(canvas, doc)

    return desenhar


def _desenhar_logo(canvas, caminho, topo: float, lado: str = "centro") -> float:
    """
    A logo centrada no alto, e o novo topo para o texto do timbre.

    Se a imagem nao abrir - trocada por outro arquivo, disco removido -, o
    timbre sai so com o texto. Um PDF sem logo e melhor que um PDF que nao sai.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader

    try:
        imagem = ImageReader(str(caminho))
        largura_px, altura_px = imagem.getSize()
    except Exception:
        return topo

    altura = LOGO_ALTURA_CM * cm
    largura = altura * (largura_px / altura_px if altura_px else 1)
    # Logo muito larga (uma assinatura deitada, por exemplo) nao pode invadir
    # as margens: ela encolhe ate caber entre elas.
    limite = A4[0] - 2 * MARGEM_CM * cm
    if largura > limite:
        altura *= limite / largura
        largura = limite
    if lado == "esquerda":
        x = MARGEM_CM * cm
    elif lado == "direita":
        x = A4[0] - MARGEM_CM * cm - largura
    else:
        x = (A4[0] - largura) / 2
    canvas.drawImage(imagem, x, topo - altura, width=largura,
                     height=altura, mask="auto")
    return topo - altura - LOGO_FOLGA_CM * cm


def _numerar(rodape: str, fonte: str = "Times-Roman", folha: dict | None = None,
             total: int = 0):
    """
    Numero de pagina no rodape, como todo documento juridico tem.

    O texto do rodape fica a esquerda; se o numero pedir a esquerda, o texto
    passa para a direita - os dois no mesmo canto se atropelariam.
    """
    from reportlab.lib.units import cm

    folha = normalizar_folha(folha)
    onde = folha["numeracao_onde"]
    lado_do_texto = "direita" if onde == "esquerda" else "esquerda"

    def desenhar(canvas, doc):
        canvas.saveState()
        canvas.setFont(fonte, 8.5)
        canvas.setFillGray(0.4)
        if rodape:
            _escrever_alinhado(canvas, lado_do_texto, 1.4 * cm, rodape[:110])
        numero = numero_da_pagina(folha["numeracao"], doc.page, total)
        if numero:
            _escrever_alinhado(canvas, onde, 1.4 * cm, numero)
        canvas.restoreState()

    return desenhar


def _para_marcacao(bloco: Bloco) -> str:
    """Os trechos do bloco na marcacao curta que o reportlab entende."""
    from xml.sax.saxutils import escape

    partes = []
    for t in bloco.trechos:
        texto = escape(t.texto).replace("\n", "<br/>")
        if not texto:
            continue
        if t.negrito:
            texto = f"<b>{texto}</b>"
        if t.italico:
            texto = f"<i>{texto}</i>"
        if t.sublinhado:
            texto = f"<u>{texto}</u>"
        if t.riscado:
            texto = f"<strike>{texto}</strike>"
        partes.append(texto)
    return "".join(partes)


# ----------------------------------------------------------------- DOCX


def para_docx(blocos: list[Bloco], titulo: str = "",
              formato: dict | None = None) -> bytes:
    """
    O documento em DOCX, para continuar no Word.

    Sai da mesma lista de blocos que gerou o PDF, no mesmo formato - fonte,
    corpo, recuo e entrelinhas. O desenho da pagina ainda nao e identico, que
    Word e reportlab quebram linha de jeitos diferentes, e a tela diz isso: o
    PDF e o que vale para assinar e enviar.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    formato = normalizar_formato(formato)

    alinha = {
        "esquerda": WD_ALIGN_PARAGRAPH.LEFT,
        "centro": WD_ALIGN_PARAGRAPH.CENTER,
        "direita": WD_ALIGN_PARAGRAPH.RIGHT,
        "justificado": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    estilos = {
        "titulo1": "Heading 1", "titulo2": "Heading 2", "titulo3": "Heading 3",
        "item": "List Bullet", "numerado": "List Number",
    }

    doc = Document()
    for secao in doc.sections:
        secao.left_margin = secao.right_margin = Cm(MARGEM_CM)
        secao.top_margin = secao.bottom_margin = Cm(MARGEM_CM)

    normal = doc.styles["Normal"]
    normal.font.name = FONTES[formato["fonte"]]["docx"]
    normal.font.size = Pt(formato["corpo"])
    normal.paragraph_format.line_spacing = formato["entrelinhas"]

    for bloco in blocos:
        if not bloco.texto.strip():
            continue

        if bloco.tipo == "tabela":
            linhas = [l for l in bloco.linhas if l]
            if not linhas:
                continue
            colunas = max(len(l) for l in linhas)
            quadro = doc.add_table(rows=0, cols=colunas)
            # "Table Grid" e o unico estilo de tabela que todo Word tem e que
            # desenha os fios. Sem ele o quadro chega ao Word invisivel - as
            # celulas estao la, mas ninguem ve que e um quadro.
            try:
                quadro.style = "Table Grid"
            except KeyError:
                pass
            for i, linha in enumerate(linhas):
                celulas = quadro.add_row().cells
                for j in range(colunas):
                    texto = str(linha[j]) if j < len(linha) else ""
                    corrida = celulas[j].paragraphs[0].add_run(texto)
                    corrida.bold = i == 0
            doc.add_paragraph()
            continue

        paragrafo = doc.add_paragraph(style=estilos.get(bloco.tipo))
        if bloco.tipo == "paragrafo":
            paragrafo.alignment = alinha.get(bloco.alinhamento)
            # O item de lista ja e recuado pela lista; o titulo recuado fica
            # torto. O recuo de primeira linha e do corpo do texto.
            paragrafo.paragraph_format.first_line_indent = Cm(formato["recuo_cm"])

        for t in bloco.trechos:
            if not t.texto:
                continue
            corrida = paragrafo.add_run(t.texto)
            corrida.bold = t.negrito
            corrida.italic = t.italico
            corrida.underline = t.sublinhado
            if t.riscado:
                corrida.font.strike = True

    saida = io.BytesIO()
    doc.save(saida)
    return saida.getvalue()


def pagina_png(pdf: bytes, numero: int = 1, largura: int = 900) -> bytes:
    """Uma pagina do PDF desenhada, para a pre-visualizacao."""
    buffer = io.BytesIO()
    with leitor_pdf.abrir(pdf) as doc:
        indice = max(0, min(int(numero) - 1, len(doc) - 1))
        pagina = doc[indice]
        escala = max(min(largura / max(pagina.get_width(), 1), 4.0), 0.2)
        # Gravar o PNG aqui dentro, e nao depois de fechar: a imagem do Pillow
        # aponta para a memoria do PDFium, que some junto com o documento.
        pagina.render(scale=escala).to_pil().save(buffer, format="PNG")
    return buffer.getvalue()


def paginas_de(pdf: bytes) -> int:
    with leitor_pdf.abrir(pdf) as doc:
        return len(doc)


# ------------------------------------------------ conferir antes de sair


# Vestigios de modelo que ninguem preencheu. Sair com "R$ ______" num contrato
# de honorarios e o tipo de erro que se descobre depois de enviado.
RE_LACUNA = re.compile(r"_{3,}|\.{4,}|\[\s*\]|\{\{[^}]*\}\}|\bXXX+\b|<<[^>]*>>")
RE_CPF_TXT = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ_TXT = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
# O \s* fora do lookahead volta atras e casa com zero espaco, entao
# "R$ 12.000,00" era apontado como valor sem numero. O espaco tem que
# estar DENTRO do lookahead.
RE_VALOR_VAZIO = re.compile(r"R\$(?!\s*[\d_])", re.IGNORECASE)


def _digitos(texto: str) -> list[int]:
    return [int(c) for c in re.sub(r"\D", "", texto)]


def cpf_valido(texto: str) -> bool:
    """Digito verificador do CPF. Objetivo: ou fecha, ou nao fecha."""
    d = _digitos(texto)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for corte in (9, 10):
        soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
        resto = (soma * 10) % 11 % 10
        if resto != d[corte]:
            return False
    return True


def cnpj_valido(texto: str) -> bool:
    """Digito verificador do CNPJ."""
    d = _digitos(texto)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        corte = len(pesos)
        soma = sum(d[i] * pesos[i] for i in range(corte))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != d[corte]:
            return False
    return True


def conferir(blocos: list[Bloco], fichas: list[dict] | None = None) -> list[dict]:
    """
    O que conferir antes de o documento sair.

    Tudo aqui e regra, nao modelo: roda em milissegundos e a resposta e sempre
    a mesma. Um aviso que muda de opiniao a cada leitura nao serve para conferir
    contrato.

    Nao aponta estilo nem sugere redacao - so o que da para afirmar: lacuna de
    modelo que ficou, documento com digito verificador errado, valor com o
    cifrao e sem numero, e nome que aparece no texto sem bater com a ficha.
    """
    avisos: list[dict] = []
    fichas = fichas or []

    for numero, bloco in enumerate(blocos, start=1):
        texto = bloco.texto
        if not texto.strip():
            continue

        for achado in RE_LACUNA.findall(texto):
            avisos.append({
                "grau": "impede",
                "bloco": numero,
                "titulo": "Falta preencher",
                "detalhe": f"Ficou “{achado.strip()}” no texto: {_recorte(texto, achado)}",
            })

        if RE_VALOR_VAZIO.search(texto):
            avisos.append({
                "grau": "impede",
                "bloco": numero,
                "titulo": "Valor sem número",
                "detalhe": f"Tem “R$” sem valor: {_recorte(texto, 'R$')}",
            })

        for cpf in RE_CPF_TXT.findall(texto):
            if not cpf_valido(cpf):
                avisos.append({
                    "grau": "impede",
                    "bloco": numero,
                    "titulo": "CPF não confere",
                    "detalhe": f"{cpf} não fecha no dígito verificador.",
                })
        for cnpj in RE_CNPJ_TXT.findall(texto):
            if not cnpj_valido(cnpj):
                avisos.append({
                    "grau": "impede",
                    "bloco": numero,
                    "titulo": "CNPJ não confere",
                    "detalhe": f"{cnpj} não fecha no dígito verificador.",
                })

    avisos += _conferir_fichas(blocos, fichas)
    return avisos


def _conferir_fichas(blocos: list[Bloco], fichas: list[dict]) -> list[dict]:
    """
    Cruza os documentos citados no texto com os Cadastros.

    Quando a ficha do cliente existe e o CNPJ do contrato e outro, o mais
    provavel e que alguem copiou de um contrato antigo - e esse e exatamente o
    erro que ninguem percebe relendo.
    """
    if not fichas:
        return []

    texto = para_texto(blocos)
    achados = set(RE_CPF_TXT.findall(texto)) | set(RE_CNPJ_TXT.findall(texto))
    avisos = []

    for ficha in fichas:
        nome = (ficha.get("nome") or "").strip()
        doc = (ficha.get("documento") or "").strip()
        if not nome or not doc or len(nome) < 6:
            continue
        if nome.lower() not in texto.lower():
            continue
        if doc in achados:
            continue
        # Em que paragrafo o nome aparece. Sem isto o aviso vinha com bloco 0 e
        # a tela so podia dizer "em algum lugar do documento" - para conferir,
        # a pessoa tinha que procurar o nome com o olho.
        onde = next((n for n, b in enumerate(blocos, start=1)
                     if nome.lower() in b.texto.lower()), 0)
        avisos.append({
            "grau": "confira",
            "bloco": onde,
            "titulo": "Documento diferente do cadastro",
            "detalhe": (
                f"O texto cita {nome}, mas não traz o {('CNPJ' if len(_digitos(doc)) == 14 else 'CPF')} "
                f"{doc} que está no cadastro."
            ),
        })
    return avisos


def _recorte(texto: str, alvo: str, folga: int = 34) -> str:
    onde = texto.find(alvo)
    if onde < 0:
        return " ".join(texto.split())[:80]
    inicio = max(0, onde - folga)
    fim = min(len(texto), onde + len(alvo) + folga)
    pedaco = " ".join(texto[inicio:fim].split())
    return ("…" if inicio else "") + pedaco + ("…" if fim < len(texto) else "")


# ----------------------------------------------------------- o arquivo


class Documentos:
    """
    Documentos e planilhas, com historico.

    Versao nova so quando o conteudo muda de verdade. Gravar a cada tecla
    encheria o historico de ruido e enterraria a versao que interessa - a
    tela promete "v6: clausula de vigencia inserida", nao "v418".
    """

    def __init__(self, base) -> None:
        self.base = base

    def listar(self, tipo: str = "") -> list[dict]:
        sql = (
            "SELECT d.id, d.titulo, d.tipo, d.cadastro_id, d.criado_em, d.atualizado_em,"
            " k.nome AS cadastro_nome, LENGTH(d.corpo) AS tamanho,"
            " (SELECT MAX(numero) FROM versoes v WHERE v.documento_id = d.id) AS versao"
            " FROM documentos d LEFT JOIN cadastros k ON k.id = d.cadastro_id"
        )
        parametros: tuple = ()
        if tipo:
            sql += " WHERE d.tipo = ?"
            parametros = (tipo,)
        sql += " ORDER BY d.atualizado_em DESC"
        itens = self.base.buscar(sql, parametros)
        for i in itens:
            i["versao"] = i["versao"] or 1
        return itens

    def obter(self, id_: int) -> dict | None:
        item = self.base.um(
            "SELECT d.*, k.nome AS cadastro_nome FROM documentos d "
            "LEFT JOIN cadastros k ON k.id = d.cadastro_id WHERE d.id = ?",
            (id_,),
        )
        if item:
            item["versao"] = self.ultima_versao(id_)
        return item

    def criar(self, titulo: str, tipo: str = "texto", corpo: str = "",
              cadastro_id: int | None = None) -> int:
        titulo = " ".join(str(titulo or "").split()) or "Documento sem título"
        id_ = self.base.escrever(
            "INSERT INTO documentos (titulo, tipo, corpo, cadastro_id, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (titulo, tipo if tipo in ("texto", "planilha") else "texto", corpo, cadastro_id),
        )
        self._gravar_versao(id_, corpo, "criado")
        return id_

    def salvar(self, id_: int, corpo: str, titulo: str = "", nota: str = "") -> dict:
        atual = self.base.um("SELECT corpo, titulo FROM documentos WHERE id = ?", (id_,))
        if not atual:
            raise ValueError("documento nao encontrado")

        mudou = atual["corpo"] != corpo
        novo_titulo = " ".join(str(titulo).split()) if titulo else atual["titulo"]

        self.base.escrever(
            "UPDATE documentos SET corpo = ?, titulo = ?, "
            "atualizado_em = datetime('now','localtime') WHERE id = ?",
            (corpo, novo_titulo, id_),
        )
        if mudou:
            self._gravar_versao(id_, corpo, nota)
        return {"id": id_, "versao": self.ultima_versao(id_), "nova_versao": mudou}

    def _gravar_versao(self, id_: int, corpo: str, nota: str) -> int:
        numero = self.ultima_versao(id_) + 1
        self.base.escrever(
            "INSERT INTO versoes (documento_id, numero, corpo, nota, criada_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
            (id_, numero, corpo, nota[:120]),
        )
        return numero

    def formato(self, id_: int) -> dict:
        linha = self.base.um("SELECT formato FROM documentos WHERE id = ?", (id_,))
        return normalizar_formato(linha["formato"] if linha else None)

    def formatar(self, id_: int, pedido) -> dict:
        """
        Troca a fonte, o corpo, o recuo ou as entrelinhas da folha.

        Nao cria versao: nao mudou o que o documento diz, mudou como ele e
        impresso. Uma linha "v7: trocou a fonte" no historico enterraria a
        versao em que a clausula mudou, que e a que alguem vai procurar.
        """
        import json

        # Quem troca so a fonte (a barra, o painel antigo de Folha) nao manda a
        # folha: sem isto, trocar o corpo apagaria o timbre do documento.
        if isinstance(pedido, dict) and "folha" not in pedido:
            pedido = {**pedido, "folha": self.formato(id_)["folha"]}
        limpo = normalizar_formato(pedido)
        mexeu = self.base.escrever(
            "UPDATE documentos SET formato = ?, "
            "atualizado_em = datetime('now','localtime') WHERE id = ?",
            (json.dumps(limpo, ensure_ascii=False), id_),
        )
        if not mexeu:
            raise ValueError("documento nao encontrado")
        return limpo

    def ultima_versao(self, id_: int) -> int:
        linha = self.base.um(
            "SELECT MAX(numero) AS n FROM versoes WHERE documento_id = ?", (id_,)
        )
        return int(linha["n"] or 0) if linha else 0

    def versoes(self, id_: int, limite: int = 30) -> list[dict]:
        return self.base.buscar(
            "SELECT id, numero, nota, criada_em, LENGTH(corpo) AS tamanho "
            "FROM versoes WHERE documento_id = ? ORDER BY numero DESC LIMIT ?",
            (id_, limite),
        )

    def corpo_da_versao(self, id_: int, numero: int) -> str | None:
        linha = self.base.um(
            "SELECT corpo FROM versoes WHERE documento_id = ? AND numero = ?",
            (id_, numero),
        )
        return linha["corpo"] if linha else None

    def restaurar(self, id_: int, numero: int) -> dict:
        """
        Volta para uma versao antiga sem apagar o caminho de volta.

        A versao antiga vira uma versao nova. Sobrescrever o historico faria
        do "restaurar" uma operacao sem desfazer - e restaurar por engano e
        exatamente o tipo de coisa que acontece.
        """
        corpo = self.corpo_da_versao(id_, numero)
        if corpo is None:
            raise ValueError("essa versao nao existe")
        return self.salvar(id_, corpo, nota=f"voltou para a v{numero}")

    def apagar(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM documentos WHERE id = ?", (id_,)) > 0

    def contagem(self) -> dict:
        return {
            "texto": self.base.contar("documentos", "tipo = 'texto'"),
            "planilha": self.base.contar("documentos", "tipo = 'planilha'"),
        }


# Quanto dois paragrafos precisam ter em comum para serem o MESMO paragrafo
# editado. Medido em paragrafos de contrato deste escritorio: edicao de
# verdade fica entre 0,60 e 0,83, e paragrafo trocado por outro entre 0,00 e
# 0,33 - a folga entre os dois grupos e larga, e 0,45 fica no meio dela.
#
# A conta e por PALAVRA e nao por letra: por letra, "Nome: ______" e
# "CPF: ______" dao 0,74, porque o que eles tem em comum e o sublinhado.
PARECIDOS_MINIMO = 0.45


def _parecidos(a: str, b: str) -> bool:
    import difflib

    palavras_a = re.findall(r"[0-9a-zà-ÿ]+", a.lower())
    palavras_b = re.findall(r"[0-9a-zà-ÿ]+", b.lower())
    if not palavras_a or not palavras_b:
        return False
    return difflib.SequenceMatcher(None, palavras_a, palavras_b).ratio() >= PARECIDOS_MINIMO


class Comentarios:
    """
    Observacao presa a um trecho do documento.

    A ancora e o TEXTO do paragrafo, e nao o numero dele: numero muda toda vez
    que alguem insere uma linha acima, e o comentario passaria a apontar para o
    paragrafo errado - calado, que e pior do que nao ter comentario. Pelo
    texto, ou acha o paragrafo certo, ou diz que o trecho nao existe mais.
    """

    def __init__(self, base) -> None:
        self.base = base

    def listar(self, documento_id: int, incluir_resolvidos: bool = False) -> list[dict]:
        sql = "SELECT * FROM comentarios WHERE documento_id = ?"
        if not incluir_resolvidos:
            sql += " AND resolvido = 0"
        return self.base.buscar(sql + " ORDER BY id", (documento_id,))

    def criar(self, documento_id: int, trecho: str, texto: str,
              origem: str = "assistente") -> int:
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("comentário sem texto")
        return self.base.escrever(
            "INSERT INTO comentarios (documento_id, trecho, texto, origem, criado_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
            (documento_id, " ".join(str(trecho or "").split())[:600], texto, origem),
        )

    def resolver(self, id_: int, resolvido: bool = True) -> bool:
        return self.base.escrever(
            "UPDATE comentarios SET resolvido = ? WHERE id = ?",
            (1 if resolvido else 0, id_),
        ) > 0

    def apagar(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM comentarios WHERE id = ?", (id_,)) > 0

    def ancorar(self, documento_id: int, blocos: list[Bloco],
                incluir_resolvidos: bool = False) -> list[dict]:
        """
        Em que bloco cada comentario cai no texto de agora.

        `bloco` -1 quer dizer que o trecho nao esta mais no documento. A tela
        mostra esses numa lista a parte, em vez de pendurar num paragrafo
        qualquer.
        """
        textos = [" ".join(b.texto.split()) for b in blocos]
        saida = []
        for item in self.listar(documento_id, incluir_resolvidos):
            alvo = " ".join(str(item["trecho"]).split())
            onde = -1
            if alvo:
                for numero, texto in enumerate(textos):
                    if alvo == texto or (len(alvo) > 12 and alvo in texto):
                        onde = numero
                        break
            saida.append({**item, "bloco": onde})
        return saida


def comparar(antes: str, depois: str) -> list[dict]:
    """
    O que mudou entre duas versoes, por paragrafo.

    Compara o texto, nao o HTML: trocar o editor de <b> para <strong> nao e
    alteracao de contrato, e listar isso como mudanca faria a comparacao
    perder a utilidade justamente no dia em que ela importa.
    """
    import difflib

    a = [b.texto.strip() for b in ler_html(antes) if b.texto.strip()]
    b = [x.texto.strip() for x in ler_html(depois) if x.texto.strip()]

    saida: list[dict] = []
    for marca, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if marca == "equal":
            continue
        if marca == "replace":
            for antes_txt, depois_txt in zip(a[i1:i2], b[j1:j2]):
                # Paragrafo apagado com outro escrito no lugar nao e "este
                # paragrafo mudou": chamar de mudanca faz a tela dizer que a
                # clausula do foro virou a clausula da multa, e quem le isso
                # para decidir e enganado.
                if _parecidos(antes_txt, depois_txt):
                    saida.append({"tipo": "mudou", "antes": antes_txt, "depois": depois_txt})
                else:
                    saida.append({"tipo": "saiu", "antes": antes_txt, "depois": ""})
                    saida.append({"tipo": "entrou", "antes": "", "depois": depois_txt})
            for extra in b[j1 + (i2 - i1):j2]:
                saida.append({"tipo": "entrou", "antes": "", "depois": extra})
            for extra in a[i1 + (j2 - j1):i2]:
                saida.append({"tipo": "saiu", "antes": extra, "depois": ""})
        elif marca == "insert":
            for texto in b[j1:j2]:
                saida.append({"tipo": "entrou", "antes": "", "depois": texto})
        elif marca == "delete":
            for texto in a[i1:i2]:
                saida.append({"tipo": "saiu", "antes": texto, "depois": ""})
    return saida


class Clausulas:
    """
    As clausulas que o escritorio guarda para reaproveitar.

    Conteudo do escritorio, escrito pelo escritorio. E de proposito que aqui
    nao entra texto de lei: o programa nao carrega o Codigo Civil, e pedir o
    artigo ao modelo produziria numero plausivel e errado dentro de um
    contrato. Modelo de clausula que a pessoa mesma escreveu nao tem esse risco.
    """

    def __init__(self, caminho: Path) -> None:
        import json

        self.caminho = Path(caminho)
        self.itens: list[dict] = []
        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                self.itens = bruto.get("clausulas", []) if isinstance(bruto, dict) else []
            except (json.JSONDecodeError, OSError):
                self.itens = []

    def listar(self) -> list[dict]:
        return sorted(self.itens, key=lambda c: c.get("titulo", "").lower())

    def gravar(self, titulo: str, texto: str, id_: str = "") -> dict:
        import uuid

        titulo = " ".join(str(titulo or "").split())
        if not titulo:
            raise ValueError("a cláusula precisa de um título")
        if not str(texto or "").strip():
            raise ValueError("a cláusula precisa de um texto")

        item = next((c for c in self.itens if c.get("id") == id_), None)
        if item is None:
            item = {"id": uuid.uuid4().hex[:10]}
            self.itens.append(item)
        item["titulo"] = titulo
        item["texto"] = str(texto)
        item["atualizada_em"] = datetime.now().isoformat(timespec="seconds")
        self.salvar()
        return item

    def apagar(self, id_: str) -> bool:
        antes = len(self.itens)
        self.itens = [c for c in self.itens if c.get("id") != id_]
        self.salvar()
        return len(self.itens) < antes

    def salvar(self) -> None:
        import json

        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps({"versao": 1, "clausulas": self.itens}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
