"""
Mostrar o trecho citado dentro do documento, na página em que ele está.

A conversa já dizia de onde tirou cada informação — mas dizia em texto, num
bloco de "fontes" que a pessoa lê e acredita. Conferir de verdade exigia abrir
o PDF por fora, achar a página e procurar o parágrafo com o olho.

Este módulo fecha essa distância: dado um trecho que o assistente leu, ele diz
em que página do arquivo aquilo está e onde exatamente, para a tela marcar. A
página é o PDF de verdade rasterizado — não uma aproximação em HTML. O que
aparece é o documento.

Duas decisões:

**Procurar no PDF, não confiar no índice.** Os trechos que o assistente lê vêm
do texto extraído, com marcas de página que a extração escreveu. Usar aquele
número seria confiar numa conta feita antes; procurar a frase dentro do
arquivo devolve a página que ela realmente ocupa hoje.

**Dizer por que aquele trecho entrou.** O painel ao lado não é um resumo
escrito por modelo: são as palavras da pergunta que aparecem naquele pedaço.
Quem confere quer saber o que ligou um ao outro, e isso é contável.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import leitor_pdf

# Quanto do trecho usar para procurar. Frase inteira falha por um espaço a
# mais na extração; um pedaço do meio, sem as bordas, casa com folga.
LETRAS_DA_BUSCA = 60

# Acima disto o trecho não é "o parágrafo citado", é meia página — e marcar
# meia página não ajuda ninguém a conferir nada.
MAXIMO_MARCADO = 1200


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def frases_de_busca(trecho: str) -> list[str]:
    """
    Vários pedaços do trecho para usar de agulha, do melhor para o pior.

    Um pedaço só não basta. A busca do pdfium é literal, e o texto extraído
    diverge do texto interno do PDF em detalhes bobos — um espaço antes da
    vírgula, uma linha de assinatura em underscores, uma ligadura. Medido: com
    um pedaço só, 12 de 14 trechos eram localizados; o que falhava era sempre
    um azar de onde o corte caiu, não um trecho impossível.

    Então tenta em quatro pontos do trecho e em dois tamanhos. Basta um casar.
    """
    sem_marca = re.sub(r"\[p[áa]gina \d+\]", " ", trecho or "", flags=re.IGNORECASE)

    # A agulha não atravessa quebra de linha NEM vão de coluna.
    #
    # O texto extraído respeita a ordem de leitura da página, e o que está
    # lado a lado na folha pode estar longe no fluxo interno do PDF. Duas
    # formas disso, e as duas quebravam a marca do trecho no visor:
    #
    #   - linhas vizinhas: "11/09/2026" e "Despesas de Viagem", cantos opostos
    #     do cabeçalho, viravam a agulha "11/09/2026 Despesas de Viagem"
    #   - células de uma tabela, que a extração alinha com corridas de espaço:
    #     "Apuração das receitas em:        11/09/2026        Dados RTA" virava
    #     uma agulha só, e essa sequência não existe no arquivo
    #
    # Espaço duplo é vão de coluna; espaço simples é espaço de palavra. Cada
    # pedaço entre vãos é texto contíguo de verdade, e é nele que se procura.
    linhas = [p.strip() for l in sem_marca.splitlines()
              for p in re.split(r"\s{2,}", l)]
    linhas = [re.sub(r"\s+", " ", l) for l in linhas if l.strip()]

    inteiro = re.sub(r"\s+", " ", sem_marca).strip()
    if not inteiro:
        return []
    if len(inteiro) <= LETRAS_DA_BUSCA and len(linhas) <= 1:
        return [inteiro]

    candidatas: list[str] = []

    def juntar(pedaco: str) -> None:
        # Não começar no meio de uma palavra: o pdfium procura literal.
        corte = pedaco.find(" ")
        if 0 <= corte < 20:
            pedaco = pedaco[corte + 1:]
        pedaco = pedaco.strip()
        if len(pedaco) >= 20 and pedaco not in candidatas:
            candidatas.append(pedaco)

    # As linhas mais longas primeiro: "Total" e "Resumo" aparecem em qualquer
    # página e não identificam trecho nenhum.
    for linha in sorted(linhas, key=len, reverse=True)[:6]:
        for tamanho in (LETRAS_DA_BUSCA, 34):
            juntar(linha[:tamanho])
            if len(linha) > tamanho + 20:
                juntar(linha[len(linha) // 3:][:tamanho])

    # Documento de uma linha só — prosa corrida sem quebra — continua sendo
    # fatiado ao longo do texto, como antes.
    if len(linhas) <= 1:
        for tamanho in (LETRAS_DA_BUSCA, 34):
            for parte in (1, 2, 3, 4):
                inicio = (len(inteiro) * parte) // 5
                juntar(inteiro[inicio:inicio + tamanho])

    # Trecho curto de formulário: nenhuma linha chega a vinte letras, e o piso
    # de vinte — que existe para não marcar uma palavra genérica — deixava o
    # trecho sem agulha nenhuma. Quando é isso, a linha mais longa é o trecho.
    if not candidatas:
        maior = max(linhas, key=len, default="")
        if len(maior) >= 10:
            candidatas.append(maior)

    return candidatas


def onde_esta(caminho: Path | str, trecho: str) -> dict:
    """
    Em que página do PDF este trecho está, e onde marcar.

    Devolve `achou=False` quando o texto não é encontrado — pode ser PDF
    escaneado, extração diferente ou o arquivo ter mudado. A tela mostra a
    página mesmo assim, sem marca: melhor a página certa sem destaque do que
    um destaque no lugar errado.
    """
    alvo = Path(caminho)
    vazio = {"achou": False, "pagina": 1, "total": 0, "marcas": [],
             "largura": 0, "altura": 0}
    if not alvo.exists() or alvo.suffix.lower() != ".pdf":
        return vazio

    agulhas = frases_de_busca(trecho)
    if not agulhas:
        return vazio

    with leitor_pdf.abrir(alvo) as pdf:
        total = len(pdf)
        achado = _achar(pdf, agulhas)
        if not achado:
            return {**vazio, "total": total}
        numero, marcas, largura, altura = achado
        return {"achou": True, "pagina": numero, "total": total,
                "marcas": marcas, "largura": largura, "altura": altura}


def _marcas(pagina, texto, inicio: int, quantos: int) -> list[dict]:
    """Os retangulos de um achado, em fracao da pagina e com o eixo da tela."""
    largura, altura = pagina.get_size()
    marcas = []
    for i in range(texto.count_rects(inicio, quantos)):
        x0, y0, x1, y1 = texto.get_rect(i)
        # Texto que o PDF desenha um pouco fora da folha (a coluna
        # vertical na margem de um extrato de banco) dava marca com y
        # negativo. Presa na pagina: a marca mostra o que se ve.
        x0, x1 = max(0.0, x0), min(largura, x1)
        y0, y1 = max(0.0, y0), min(altura, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        # O PDF conta do rodape para cima; a tela conta do topo para
        # baixo. Sem virar o eixo, a marca sai espelhada na vertical.
        marcas.append({
            "x": round(x0 / largura, 5),
            "y": round((altura - y1) / altura, 5),
            "w": round((x1 - x0) / largura, 5),
            "h": round((y1 - y0) / altura, 5),
        })
    return marcas


def _ate_a_palavra(texto, inicio: int, quantos: int, folga: int = 40) -> tuple[int, int]:
    """
    A agulha e um pedaco do trecho e pode comecar ou acabar no meio de uma
    palavra ("...parcelas mensais e suc"): a marca vai ate o fim da palavra
    dos dois lados, para nao cortar o que a pessoa le.
    """
    total = texto.count_chars()
    fim = inicio + quantos
    antes = texto.get_text_range(max(0, inicio - folga), min(folga, inicio))
    corte = len(antes)
    while corte > 0 and antes[corte - 1].isalnum():
        corte -= 1
    novo_inicio = inicio - (len(antes) - corte)
    depois = texto.get_text_range(fim, min(folga, max(0, total - fim)))
    k = 0
    while k < len(depois) and depois[k].isalnum():
        k += 1
    return novo_inicio, fim + k - novo_inicio


def _achar(pdf, agulhas: list[str], inteira: bool = False):
    """A primeira pagina em que uma das agulhas casa: (numero, marcas, largura, altura)."""
    for numero in range(len(pdf)):
        pagina = pdf[numero]
        texto = pagina.get_textpage()
        achado = None
        for agulha in agulhas:
            achado = texto.search(agulha, match_case=False).get_next()
            if achado:
                break
        if not achado:
            continue
        if inteira:
            try:
                achado = _ate_a_palavra(texto, *achado)
            except Exception:  # noqa: BLE001 - sem alargar, a marca e a da agulha
                pass
        largura, altura = pagina.get_size()
        return numero + 1, _marcas(pagina, texto, *achado), largura, altura
    return None


def marcas_dos_trechos(origem: Path | str | bytes, trechos: list[str], limite: int = 12) -> list[dict]:
    """
    Cada trecho citado, com a pagina e as marcas, para o visor da conversa
    (pacote de telas, `Conversa - Documento`/`PDF`). `origem` e o PDF - o
    arquivo, ou os bytes que o gerador do editor monta para o Word. O trecho
    que nao se acha fica de fora: melhor sem marca do que marca no lugar errado.
    """
    saida: list[dict] = []
    if not trechos:
        return saida
    with leitor_pdf.abrir(origem) as pdf:
        for indice, trecho in enumerate(trechos[:limite]):
            # O trecho inteiro primeiro: quando a extracao bate com o arquivo,
            # a marca cobre a frase toda, e nao so o pedaco que serviu de agulha.
            inteiro = re.sub(r"\s+", " ", re.sub(r"\[p[áa]gina \d+\]", " ", trecho or "", flags=re.IGNORECASE)).strip()
            agulhas = ([inteiro] if 20 <= len(inteiro) <= MAXIMO_MARCADO else []) + frases_de_busca(trecho)
            achado = _achar(pdf, agulhas, inteira=True) if agulhas else None
            if achado:
                saida.append({"indice": indice, "pagina": achado[0], "marcas": achado[1]})
    return saida


def ocorrencias(origem: Path | str | bytes, termo: str, limite: int = 60) -> list[dict]:
    """Onde o termo aparece no documento, pagina a pagina (a lupa do visor)."""
    termo = re.sub(r"\s+", " ", termo or "").strip()
    if len(termo) < 2:
        return []
    saida: list[dict] = []
    with leitor_pdf.abrir(origem) as pdf:
        for numero in range(len(pdf)):
            pagina = pdf[numero]
            texto = pagina.get_textpage()
            busca = texto.search(termo, match_case=False)
            while len(saida) < limite:
                achado = busca.get_next()
                if not achado:
                    break
                saida.append({"pagina": numero + 1, "marcas": _marcas(pagina, texto, *achado)})
            if len(saida) >= limite:
                break
    return saida


def paginas_de(caminho: Path | str) -> int:
    alvo = Path(caminho)
    if not alvo.exists() or alvo.suffix.lower() != ".pdf":
        return 0
    with leitor_pdf.abrir(alvo) as pdf:
        return len(pdf)


def por_que_este_trecho(pergunta: str, trecho: str, limite: int = 6) -> dict:
    """
    O que da pergunta aparece neste trecho.

    Não é um resumo escrito por modelo: são as palavras que a pessoa digitou e
    que estão ali dentro, contadas. Quem abre o documento para conferir quer
    saber o que ligou um ao outro — e essa é a resposta que dá para provar.
    """
    plano_trecho = _sem_acento(trecho)
    palavras = [p for p in re.findall(r"[0-9a-zà-ÿ]{3,}", _sem_acento(pergunta))
                if p not in PARADAS]

    achadas, vistas = [], set()
    for p in palavras:
        raiz = p[:-1] if len(p) > 4 and p.endswith("s") else p
        if raiz in vistas:
            continue
        vistas.add(raiz)
        if raiz in plano_trecho:
            achadas.append(p)

    return {
        "termos": achadas[:limite],
        "quantos": len(achadas),
        "de": len(vistas),
    }


# Palavras que aparecem em qualquer texto e não explicam nada.
PARADAS = {
    "que", "com", "dos", "das", "por", "para", "pelo", "pela", "uma", "uns",
    "nos", "nas", "seu", "sua", "seus", "suas", "este", "esta", "esse", "essa",
    "qual", "quais", "quando", "onde", "como", "sobre", "entre", "meu", "minha",
    "aqui", "tem", "ter", "sao", "foi", "era", "nao", "sim", "mais", "menos",
    "todos", "todas", "algum", "alguma", "cada", "ate", "ele", "ela", "eles",
}
