"""
Trechos pela estrutura do documento, e nao por tamanho fixo (I5).

A busca quebrava o texto em blocos de 1.200 caracteres. O bloco cortava onde
o tamanho mandava: a clausula 9 comecava num trecho e terminava no outro, e
quem achava o trecho achava meia clausula - com a multa num pedaco e a
condicao dela no outro. Documento juridico ja vem dividido pelo autor, em
clausulas, secoes e artigos; a divisao dele e a unidade de sentido.

Dois regimes:

- **B - pecas e contratos:** quebra no cabecalho (CLAUSULA, DOS FATOS, DO
  DIREITO, DOS PEDIDOS, DISPOSITIVO, VOTO, EMENTA, numeracao romana e
  decimal). Secao acima de ~1000 tokens vira janelas de ~700 com 96 de
  sobreposicao, sem sair dela; secao abaixo de 80 tokens se junta a vizinha
  inteira.
- **A - leis:** a unidade e o artigo, com os paragrafos e incisos dele.

O que nao se faz nunca: um trecho que termina no meio de uma clausula e
continua na seguinte. Juntar duas secoes pequenas inteiras pode; cortar uma
e emendar na outra, nao.

Cada trecho sabe onde esta: `char_start`/`char_end` no texto extraido, as
paginas (do mapa de layout, src/inteligencia/texto.py), e um `chunk_id`
estavel - o mesmo documento da sempre os mesmos ids, e reindexar do zero
tambem. `text_embed` leva o caminho na frente ("Contrato ACME > CLAUSULA
9a"), para a busca achar a clausula pelo nome do documento.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CHARS_POR_TOKEN = 3
MAXIMO_TOKENS = 1000
JANELA_TOKENS = 700
SOBREPOSICAO_TOKENS = 96
MINIMO_TOKENS = 80

REGIME_PECA = "B"
REGIME_LEI = "A"
# O regime C, das obras de consulta (livro de doutrina, curso, comentario):
# so a Biblioteca usa. Ver `fatiar_obra`, no fim do arquivo.
REGIME_OBRA = "C"

# Um cabecalho de peca ou contrato: no comeco da linha, curto, e de um dos
# jeitos que o direito brasileiro escreve secao.
RE_CABECALHO = re.compile(
    r"^[ \t]*(?:"
    # A clausula abre linha mesmo quando o texto dela vem na mesma linha
    # ("CLAUSULA 3a - DO ATRASO. A multa e de..."): comum em contrato.
    r"CL[ÁA]USULA\b[^\n]*"
    r"|Cl[áa]usula\s+(?:\d+|[A-Za-zçãéêíóôú]+)[ªºa-z]*\b[^\n]*"
    r"|D[OA]S?\s+(?:FATOS?|DIREITO|PEDIDOS?|FUNDAMENTOS?|PRELIMINAR(?:ES)?|M[ÉE]RITO|PROVAS?|REQUERIMENTOS?|"
    r"TUTELA[^\n]{0,60}|VALOR DA CAUSA|HONOR[ÁA]RIOS[^\n]{0,40}|OBJETO|PRE[ÇC]O|PRAZO|FORO|"
    r"OBRIGA[ÇC][ÕO]ES[^\n]{0,60}|RESCIS[ÃA]O|DISPOSI[ÇC][ÕO]ES[^\n]{0,60}|PARTES)\b[^\n]{0,80}"
    r"|DISPOSITIVO\b|VOTO\b|EMENTA\b|AC[ÓO]RD[ÃA]O\b|RELAT[ÓO]RIO\b|SENTEN[ÇC]A\b|DECIS[ÃA]O\b"
    r"|[IVXLC]{1,6}\s*[-–—.)]\s+[A-ZÀ-Ý][^\n]{0,120}"
    r"|\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+[A-ZÀ-Ý][A-ZÀ-Ý ,;/()-]{3,}[^\n]{0,80}"
    r")[ \t]*$",
    re.M,
)

# Um artigo de lei: "Art. 1º", "Art. 12.", "Artigo 5" no comeco da linha.
RE_ARTIGO = re.compile(r"^[ \t]*(?:Art\.?|Artigo)\s*\d+[ºo°]?[\s.:-]", re.M)


@dataclass
class Fatia:
    """Um pedaco pronto: onde comeca e acaba no texto, e o caminho ate ele."""

    char_start: int
    char_end: int
    caminho: str
    regime: str


def versao_de(sha1: str, texto: str, nome: str = "") -> str:
    """
    A versao do documento, para o `chunk_id`: o sha1 do arquivo (sem ele, o
    do texto) junto com o nome. O mesmo arquivo da o mesmo id em qualquer
    reindexacao; arquivo mudado, id novo - e o trecho antigo nao passa pelo
    novo. O nome entra porque "contrato.pdf" e "contrato (1).pdf" com o mesmo
    conteudo sao dois documentos no Acervo, e um id nao pode apontar para os
    dois.
    """
    base = sha1 or hashlib.sha1((texto or "").encode("utf-8")).hexdigest()
    return hashlib.sha1(f"{base}\0{nome}".encode("utf-8")).hexdigest()[:12]


def chunk_id(versao: str, char_start: int) -> str:
    return f"chunk_{versao}_{char_start:08d}"


def regime_de(texto: str) -> str:
    """Lei (artigos no comeco da linha, e mais deles que clausulas) ou peca/contrato."""
    artigos = len(RE_ARTIGO.findall(texto or ""))
    clausulas = len(re.findall(r"^[ \t]*CL[ÁA]USULA\b|^[ \t]*Cl[áa]usula\s", texto or "", re.M))
    return REGIME_LEI if artigos >= 3 and artigos > clausulas else REGIME_PECA


def _secoes(texto: str, regime: str) -> list[tuple[int, int, str]]:
    """(inicio, fim, titulo) de cada secao; o que vem antes do 1o cabecalho e o preambulo."""
    padrao = RE_ARTIGO if regime == REGIME_LEI else RE_CABECALHO
    marcas = [m for m in padrao.finditer(texto)]
    inicios = [m.start() for m in marcas]
    titulos = [" ".join(texto[m.start():texto.find("\n", m.start()) if texto.find("\n", m.start()) != -1
                              else len(texto)].split())[:80] for m in marcas]
    secoes: list[tuple[int, int, str]] = []
    if not inicios or inicios[0] > 0:
        secoes.append((0, inicios[0] if inicios else len(texto), ""))
    for i, inicio in enumerate(inicios):
        fim = inicios[i + 1] if i + 1 < len(inicios) else len(texto)
        titulo = titulos[i]
        if regime == REGIME_LEI:
            titulo = re.match(r"(?:Art\.?|Artigo)\s*\d+[ºo°]?", titulo.strip()).group(0) if re.match(
                r"(?:Art\.?|Artigo)\s*\d+[ºo°]?", titulo.strip()) else titulo
        secoes.append((inicio, fim, titulo))
    return [(a, b, t) for a, b, t in secoes if texto[a:b].strip()]


def _ajustar(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    """Sem espaco nas pontas: o trecho comeca e termina em texto."""
    while inicio < fim and texto[inicio].isspace():
        inicio += 1
    while fim > inicio and texto[fim - 1].isspace():
        fim -= 1
    return inicio, fim


def _janelas(texto: str, inicio: int, fim: int) -> list[tuple[int, int]]:
    """
    Janelas de ~700 tokens com 96 de sobreposicao, dentro de [inicio, fim) e
    cortando em fim de frase ou de linha - nunca no meio de palavra.
    """
    tamanho = JANELA_TOKENS * CHARS_POR_TOKEN
    sobra = SOBREPOSICAO_TOKENS * CHARS_POR_TOKEN
    saida: list[tuple[int, int]] = []
    atual = inicio
    while atual < fim:
        limite = min(fim, atual + tamanho)
        if limite < fim:
            pedaco = texto[atual:limite]
            corte = max(pedaco.rfind(". "), pedaco.rfind(".\n"), pedaco.rfind(";\n"), pedaco.rfind("\n"))
            if corte < len(pedaco) // 2:
                corte = pedaco.rfind(" ")
            if corte > len(pedaco) // 2:
                limite = atual + corte + 1
        saida.append((atual, limite))
        if limite >= fim:
            break
        proximo = max(atual + 1, limite - sobra)
        # O comeco da janela seguinte tambem cai em palavra inteira.
        espaco = texto.find(" ", proximo, limite)
        atual = espaco + 1 if espaco != -1 else proximo
    return saida


def fatiar(texto: str, titulo: str = "", regime: str = "") -> list[Fatia]:
    """
    As fatias do documento, em ordem.

    Secao grande vira janelas dentro dela; secoes pequenas vizinhas se juntam
    inteiras ate passarem do minimo (ou do maximo, o que vier antes).

    `regime` vazio e o de sempre: a lei ou a peca, pelo texto. A Biblioteca
    diz o regime por fora (a ficha do material), e o "C" - obra de consulta -
    so existe por ela (`fatiar_obra`).
    """
    texto = texto or ""
    if not texto.strip():
        return []
    if regime == REGIME_OBRA:
        return fatiar_obra(texto, titulo)
    regime = regime or regime_de(texto)
    secoes = _secoes(texto, regime)
    minimo = MINIMO_TOKENS * CHARS_POR_TOKEN
    maximo = MAXIMO_TOKENS * CHARS_POR_TOKEN

    # Juntar as pequenas: o grupo cresce so enquanto estiver abaixo do minimo
    # (e o proximo couber inteiro no maximo). Crescer ate o maximo juntaria
    # seis clausulas curtas num trecho so, e a busca devolveria as seis para
    # quem perguntou de uma.
    grupos: list[list[tuple[int, int, str]]] = []
    for secao in secoes:
        # Na lei a unidade e o artigo: juntar artigos seria devolver o art. 4
        # para quem procurou o art. 5. So o preambulo (sem titulo) se junta.
        if regime == REGIME_LEI and grupos and secao[2]:
            grupos.append([secao])
            continue
        if grupos:
            ultimo = grupos[-1]
            tamanho = ultimo[-1][1] - ultimo[0][0]
            if tamanho < minimo and tamanho + (secao[1] - secao[0]) <= maximo:
                ultimo.append(secao)
                continue
        grupos.append([secao])
    # A ultima, se ficou pequena, volta para a anterior.
    if len(grupos) > 1 and regime != REGIME_LEI:
        ultimo = grupos[-1]
        if ultimo[-1][1] - ultimo[0][0] < minimo and ultimo[-1][1] - grupos[-2][0][0] <= maximo:
            grupos[-2].extend(grupos.pop())

    fatias: list[Fatia] = []
    for grupo in grupos:
        inicio, fim = grupo[0][0], grupo[-1][1]
        nomes = [t for _, _, t in grupo if t]
        caminho = " > ".join(p for p in (titulo, " + ".join(nomes[:3]) + (" …" if len(nomes) > 3 else "")) if p)
        if fim - inicio <= maximo:
            a, b = _ajustar(texto, inicio, fim)
            if b > a:
                fatias.append(Fatia(a, b, caminho, regime))
            continue
        # Grupo grande e sempre uma secao so (as grandes nao se juntam).
        for a, b in _janelas(texto, inicio, fim):
            a, b = _ajustar(texto, a, b)
            if b > a:
                fatias.append(Fatia(a, b, caminho, regime))
    return fatias


# ------------------------------------------------ C - obras de consulta
#
# Livro nao e contrato. Tem o que contrato nao tem, e que atrapalha a busca:
#
# - o **sumario**: "3.2 Adimplemento substancial ........ 45" casa com
#   qualquer pergunta sobre adimplemento, e nao responde nenhuma;
# - **cabecalho e rodape** repetidos em toda pagina ("BRANDAO - VICIOS DO
#   PRODUTO", o numero da pagina): o mesmo texto em cem trechos;
# - a divisao em **Parte, Titulo, Capitulo e secao decimal** (3.2.1), e o
#   titulo do capitulo em caixa alta numa linha so.
#
# O sumario e o cabecalho/rodape nao sao cortados do texto: sao trocados por
# espacos do mesmo tamanho. Assim cada posicao continua a mesma do texto
# guardado - a pagina de cada trecho sai do mapa de sempre, e o `chunk_id`
# continua sendo a versao + a posicao.
#
# O capitulo e a fronteira: trecho nenhum atravessa capitulo. Dentro dele,
# as secoes pequenas se juntam, as grandes viram janelas - e a janela prefere
# terminar na virada de pagina, para a citacao dizer a pagina certa.

RE_MARCA_PAGINA_OBRA = re.compile(r"^\[pagina (\d+)\][ \t]*$", re.M)

# Parte, Livro, Titulo, Capitulo, Secao: a palavra, o numero (romano,
# arabico ou por extenso) e, na mesma linha, o nome.
RE_CAPITULO_OBRA = re.compile(
    r"^[ \t]*(?P<chave>PARTE|Parte|LIVRO|Livro|T[ÍI]TULO|T[íi]tulo|CAP[ÍI]TULO|Cap[íi]tulo|SE[ÇC][ÃA]O|Se[çc][ãa]o)"
    r"\s+(?P<numero>[IVXLCDM]{1,7}|\d{1,3}|[ÚU]NIC[OA]|[ÚU]nic[oa]|PRIMEIR[OA]|Primeir[oa]|SEGUND[OA]|Segund[oa]|"
    r"TERCEIR[OA]|Terceir[oa])\b(?P<nome>[^\n]{0,110})$", re.M)
# A secao decimal: "3.2 Adimplemento substancial", "3.2.1. Requisitos".
RE_SECAO_OBRA = re.compile(r"^[ \t]*(?P<numero>\d{1,2}(?:\.\d{1,2}){1,3})\.?[ \t]+(?P<nome>[A-ZÀ-Ý][^\n]{2,110})$", re.M)
# Titulo em caixa alta, sozinho na linha ("INTRODUCAO", "O VICIO DO PRODUTO").
RE_CAIXA_ALTA = re.compile(r"^[ \t]*(?P<nome>[A-ZÀ-Ý][A-ZÀ-Ý0-9 ,;:()ºª°—–\-]{3,100})[ \t]*$", re.M)
# Linha de sumario: termina no numero da pagina, quase sempre depois de pontos.
RE_LINHA_SUMARIO = re.compile(r"^[ \t]*\S[^\n]{2,150}?(?:\s*\.{2,}\s*|\s*…+\s*|\t+|\s{3,}|\s+)(\d{1,4})[ \t]*$")
RE_TITULO_SUMARIO = re.compile(r"^[ \t]*(?:SUM[ÁA]RIO|Sum[áa]rio|[ÍI]NDICE(?: GERAL)?|[ÍI]ndice(?: geral)?)[ \t]*$")

ABREVIADO = {"capitulo": "Cap.", "titulo": "Tít.", "secao": "Seção", "parte": "Parte", "livro": "Livro"}


def _plano_curto(texto: str) -> str:
    import unicodedata

    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _apagar(texto: list[str], inicio: int, fim: int) -> None:
    """Troca [inicio, fim) por espacos, sem mexer nas quebras de linha: a posicao de tudo fica a mesma."""
    for i in range(inicio, fim):
        if texto[i] != "\n":
            texto[i] = " "


def _linhas_com_posicao(texto: str, inicio: int = 0, fim: int | None = None) -> list[tuple[int, int, str]]:
    fim = len(texto) if fim is None else fim
    saida, pos = [], inicio
    while pos < fim:
        quebra = texto.find("\n", pos, fim)
        final = fim if quebra == -1 else quebra
        saida.append((pos, final, texto[pos:final]))
        pos = final + 1
    return saida


def limpar_obra(texto: str) -> str:
    """
    O texto da obra sem o que nao e conteudo: cabecalho e rodape repetidos, e
    o sumario. Do mesmo tamanho do original (ver o comentario acima).
    """
    texto = texto or ""
    saida = list(texto)
    marcas = list(RE_MARCA_PAGINA_OBRA.finditer(texto))
    paginas = [(m.end(), marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)) for i, m in enumerate(marcas)]

    # Cabecalho e rodape: as linhas das pontas de cada pagina que se repetem
    # (com o numero trocado por #) em pelo menos metade das paginas - e em
    # tres, no minimo. Uma linha igual em duas paginas e coincidencia.
    if len(paginas) >= 3:
        pontas: list[list[tuple[int, int, str]]] = []
        contagem: dict[str, int] = {}
        for a, b in paginas:
            linhas = [x for x in _linhas_com_posicao(texto, a, b) if x[2].strip()]
            nesta = linhas[:2] + linhas[-2:] if len(linhas) > 4 else linhas
            pontas.append(nesta)
            for chave in {re.sub(r"\d+", "#", " ".join(l.split()).lower()) for _, _, l in nesta}:
                contagem[chave] = contagem.get(chave, 0) + 1
        repetidas = {c for c, n in contagem.items() if n >= max(3, len(paginas) // 2)}
        for nesta in pontas:
            for a, b, linha in nesta:
                if re.sub(r"\d+", "#", " ".join(linha.split()).lower()) in repetidas:
                    _apagar(saida, a, b)

    # Sumario: tres ou mais linhas seguidas terminando em numero de pagina que
    # so cresce, com pontos na maioria - ou o titulo "Sumario" em cima.
    linhas = _linhas_com_posicao("".join(saida))
    i = 0
    while i < len(linhas):
        j, numeros, pontos = i, [], 0
        while j < len(linhas):
            _, _, linha = linhas[j]
            if not linha.strip() or RE_MARCA_PAGINA_OBRA.match(linha):
                j += 1
                continue
            achado = RE_LINHA_SUMARIO.match(linha)
            if not achado or (numeros and int(achado.group(1)) < numeros[-1]):
                break
            numeros.append(int(achado.group(1)))
            pontos += 1 if re.search(r"\.{2,}|…", linha) else 0
            j += 1
        titulo = any(RE_TITULO_SUMARIO.match(linhas[k][2]) for k in range(max(0, i - 3), i))
        if len(numeros) >= 3 and (pontos * 2 >= len(numeros) or (titulo and len(numeros) >= 3)):
            for a, b, linha in linhas[i:j]:
                if not RE_MARCA_PAGINA_OBRA.match(linha):
                    _apagar(saida, a, b)
            for k in range(max(0, i - 3), i):
                if RE_TITULO_SUMARIO.match(linhas[k][2]):
                    _apagar(saida, linhas[k][0], linhas[k][1])
            i = j
        else:
            i += 1
    return "".join(saida)


def _cabecalhos_obra(texto: str) -> list[tuple[int, str, str]]:
    """
    (posicao, nivel, rotulo) de cada cabecalho. Nivel: 'superior' (Parte,
    Livro, Titulo), 'capitulo' (Capitulo, Secao por extenso, titulo em caixa
    alta) ou 'secao' (a numeracao decimal).
    """
    achados: dict[int, tuple[str, str, str]] = {}   # posicao -> nivel, rotulo, de onde veio
    for m in RE_CAPITULO_OBRA.finditer(texto):
        chave = _plano_curto(m.group("chave"))
        nome = " ".join(m.group("nome").split()).strip(" —–-:.")
        rotulo = f"{ABREVIADO.get(chave, m.group('chave'))} {m.group('numero')}" + (f" — {nome}" if nome else "")
        achados[m.start()] = ("superior" if chave in ("parte", "livro", "titulo") else "capitulo", rotulo[:90], "chave")
    for m in RE_SECAO_OBRA.finditer(texto):
        if m.start() not in achados and not m.group("nome").rstrip().endswith((".", ",", ";")):
            achados[m.start()] = ("secao", f"{m.group('numero')} {' '.join(m.group('nome').split())}"[:90], "decimal")
    for m in RE_CAIXA_ALTA.finditer(texto):
        nome = " ".join(m.group("nome").split())
        letras = [c for c in nome if c.isalpha()]
        # "ISBN 978-85-..." tambem e caixa alta: titulo e feito de letras.
        if (m.start() not in achados and len(letras) >= 4 and sum(1 for c in letras if c.isupper()) == len(letras)
                and len(letras) >= 0.6 * len(nome.replace(" ", "")) and not nome.endswith((".", ","))):
            achados[m.start()] = ("capitulo", nome[:90], "caixa")
    ordem = sorted((p, n, r, f) for p, (n, r, f) in achados.items())

    # O titulo do capitulo que nao coube numa linha ("CAPITULO 2 - OS
    # DIREITOS BASICOS DO" e, embaixo, "CONSUMIDOR"): a linha de baixo, so
    # em caixa alta e colada no cabecalho, e o resto do nome - nao um
    # capitulo novo.
    juntos: list[list] = []
    for pos, nivel, rotulo, fonte in ordem:
        if juntos and fonte == "caixa":
            anterior = juntos[-1]
            quebra = texto.find("\n", anterior[0])
            entre = texto[quebra + 1:pos] if quebra != -1 and quebra < pos else "x"
            if not entre.strip() and anterior[1] in ("capitulo", "superior"):
                anterior[2] = (anterior[2] + " " + rotulo)[:90]
                continue
        juntos.append([pos, nivel, rotulo, fonte])

    # Antes do primeiro Capitulo, Parte ou secao decimal e folha de rosto,
    # ficha catalografica e dedicatoria - mesmo em caixa alta.
    firmes = [i for i, x in enumerate(juntos) if x[3] != "caixa"]
    if firmes:
        juntos = juntos[firmes[0]:]
    return [(p, n, r) for p, n, r, _ in juntos]


def parece_obra(texto: str) -> bool:
    """Tem cara de livro: capitulo e secoes que o regime C sabe ler."""
    cabecalhos = _cabecalhos_obra(limpar_obra(texto))
    capitulos = sum(1 for _, n, _ in cabecalhos if n in ("capitulo", "superior"))
    secoes = sum(1 for _, n, _ in cabecalhos if n == "secao")
    return capitulos >= 2 and capitulos + secoes >= 4


def _janelas_de_pagina(texto: str, inicio: int, fim: int) -> list[tuple[int, int]]:
    """
    As janelas de sempre, mas terminando na virada de pagina quando ela cai
    na segunda metade da janela: a citacao diz a pagina do trecho inteiro.
    """
    tamanho = JANELA_TOKENS * CHARS_POR_TOKEN
    saida: list[tuple[int, int]] = []
    atual = inicio
    while atual < fim:
        if fim - atual <= MAXIMO_TOKENS * CHARS_POR_TOKEN:
            saida.append((atual, fim))
            break
        limite = min(fim, atual + tamanho)
        viradas = [m.start() for m in RE_MARCA_PAGINA_OBRA.finditer(texto, atual + tamanho // 2, limite)]
        if viradas:
            saida.append((atual, viradas[-1]))
            atual = viradas[-1]
            continue
        pedacos = _janelas(texto, atual, fim)
        a, b = pedacos[0]
        saida.append((a, b))
        if len(pedacos) == 1:
            break
        atual = pedacos[1][0]
    return saida


def fatiar_obra(texto: str, titulo: str = "") -> list[Fatia]:
    """
    As fatias de uma obra de consulta (regime C), com o caminho
    "<Obra> > Cap. 3 > 3.2 Adimplemento substancial".

    O que vem antes do primeiro cabecalho - folha de rosto, ficha
    catalografica - nao vira trecho: nao responde pergunta e casaria com o
    assunto da obra inteira. A ficha e lida a parte (src/biblioteca/ficha.py).

    As posicoes valem no texto guardado; o TEXTO do trecho sai de
    `limpar_obra(texto)[a:b]`, sem o cabecalho e o rodape repetidos.
    """
    limpo = limpar_obra(texto or "")
    cabecalhos = _cabecalhos_obra(limpo)
    if not cabecalhos:
        return []
    minimo = MINIMO_TOKENS * CHARS_POR_TOKEN
    maximo = MAXIMO_TOKENS * CHARS_POR_TOKEN

    # As secoes, cada uma com o capitulo a que pertence. O capitulo e a
    # fronteira; Parte e Titulo so entram no caminho.
    secoes: list[list] = []   # inicio, fim, capitulo (caminho), secao, so o titulo
    superior = capitulo = ""
    for i, (pos, nivel, rotulo) in enumerate(cabecalhos):
        fim = cabecalhos[i + 1][0] if i + 1 < len(cabecalhos) else len(limpo)
        secao = ""
        if nivel == "superior":
            superior, capitulo = rotulo, ""
        elif nivel == "capitulo":
            capitulo = rotulo
        else:
            secao = rotulo
        corpo = RE_MARCA_PAGINA_OBRA.sub("", limpo[pos:fim]).strip()
        if corpo:
            secoes.append([pos, fim, " > ".join(p for p in (superior, capitulo) if p), secao, "\n" not in corpo])

    # O cabecalho que so abre outro ("PARTE II" e logo "CAPITULO 2") nao e
    # secao: o texto dele (a linha do titulo) vai junto com a seguinte.
    juntas: list[list] = []
    for s in secoes:
        if juntas and juntas[-1][4] and juntas[-1][2] != s[2]:
            s = [juntas.pop()[0], s[1], s[2], s[3], s[4]]
        juntas.append(s)

    # Juntar as pequenas do mesmo capitulo; nunca atravessar capitulo.
    grupos: list[list] = []
    for s in juntas:
        if grupos:
            ultimo = grupos[-1]
            tamanho = ultimo[-1][1] - ultimo[0][0]
            if (ultimo[-1][2] == s[2] and tamanho < minimo and tamanho + (s[1] - s[0]) <= maximo):
                ultimo.append(s)
                continue
        grupos.append([s])
    if len(grupos) > 1:
        ultimo = grupos[-1]
        if (ultimo[-1][1] - ultimo[0][0] < minimo and grupos[-2][-1][2] == ultimo[0][2]
                and ultimo[-1][1] - grupos[-2][0][0] <= maximo):
            grupos[-2].extend(grupos.pop())

    fatias: list[Fatia] = []
    for grupo in grupos:
        inicio, fim = grupo[0][0], grupo[-1][1]
        capitulo = grupo[0][2]
        nomes = [s[3] for s in grupo if s[3]]
        partes = [titulo, capitulo, " + ".join(nomes[:3]) + (" …" if len(nomes) > 3 else "")]
        caminho = " > ".join(p for p in partes if p)
        pedacos = [(inicio, fim)] if fim - inicio <= maximo else _janelas_de_pagina(limpo, inicio, fim)
        for a, b in pedacos:
            a, b = _ajustar(limpo, a, b)
            if b > a and RE_MARCA_PAGINA_OBRA.sub("", limpo[a:b]).strip():
                fatias.append(Fatia(a, b, caminho, REGIME_OBRA))
    return fatias
