"""
PAULUS - Os códigos em casa.

Le o texto oficial compilado do Planalto e guarda artigo por artigo numa base
local. A partir daí, citar um artigo é consulta a um índice — não palpite de
modelo.

Esta é a razão de o módulo existir. Antes, citar o Código Civil dependia de o
assistente lembrar o número certo, e um modelo de 3 bilhões de parâmetros
devolve número plausível e errado dentro de um contrato. Com o texto no disco,
o programa mostra o artigo junto da citação, e quem lê confere.

Texto de lei é público: a Lei 9.610, art. 8º, IV, diz que leis não são obra
protegida. O que se guarda aqui é o texto oficial, com a data em que foi
capturado e o endereço de onde veio, para dar para conferir depois.

**Artigo revogado é marcado como revogado.** O texto compilado do Planalto
mantém os revogados no corpo, com "(Revogado pela Lei ...)" ao lado. Citar um
artigo revogado como se estivesse em vigor é o erro mais caro que esta tela
pode cometer, e por isso ele fica visível em toda parte.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# O que o programa sabe reconhecer, e onde o texto oficial mora.
CODIGOS = {
    "cc": {
        "nome": "Código Civil",
        "lei": "Lei nº 10.406, de 10 de janeiro de 2002",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        "pistas": ("10406", "codigo civil", "cc-"),
    },
    "cpc": {
        "nome": "Código de Processo Civil",
        "lei": "Lei nº 13.105, de 16 de março de 2015",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
        "pistas": ("13105", "processo civil", "cpc-"),
    },
    "cp": {
        "nome": "Código Penal",
        "lei": "Decreto-Lei nº 2.848, de 7 de dezembro de 1940",
        "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
        "pistas": ("2848", "codigo penal", "cp-"),
    },
    "clt": {
        "nome": "Consolidação das Leis do Trabalho",
        "lei": "Decreto-Lei nº 5.452, de 1º de maio de 1943",
        "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm",
        "pistas": ("5452", "consolidacao das leis", "clt-"),
    },
}

# Cabeçalhos que dão o lugar do artigo dentro do código.
#
# Não basta a linha começar com a palavra: o texto da lei também começa frases
# com ela. A CLT diz «...o Título "Do Processo de Multas Administrativas", no
# que lhe for aplicável...» e o Código Civil, «...parte em relação a cada uma
# das que falecerem...». Lidas como cabeçalho, essas frases viravam o lugar do
# artigo mostrado ao lado da citação — mandando o leitor conferir num trecho do
# código que não tem nada a ver com o artigo.
#
# O que separa o cabeçalho da frase é o que vem depois: algarismo romano,
# "único", ou o nome da parte. O romano é lido em caixa alta de propósito: com
# maiúscula e minúscula valendo o mesmo, "Parte civil" casaria, porque C, I, V,
# I e L são todos algarismos.
#
# E o cabeçalho traz o nome na mesma linha — "LIVRO I DAS PESSOAS" —, então não
# dá para exigir que a linha acabe no número. O que decide é a maiúscula: nome
# de cabeçalho começa com ela, e continuação de frase começa com "da", "do".
# É assim que "Livro II da Parte Especial deste Código." fica de fora.
RE_ESTRUTURA = re.compile(
    r"^(?i:LIVRO|PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+"
    r"(?:[IVXLCDM]{1,8}(?:-[A-Z])?"
    r"|[ÚU]NIC[OA]|[ÚU]nic[oa]"
    r"|PRELIMINAR|Preliminar|GERAL|Geral|ESPECIAL|Especial"
    r"|COMPLEMENTAR|Complementar)"
    r"(?![A-Za-zÀ-ÿ])\s*(?:[A-ZÀ-Ý][^\n]{0,78})?$"
)

# "Art. 1º", "Art. 1.228", "Art. 5º-A", "Art. 15-A"
#
# O hifen do Planalto nem sempre e o ASCII: vem tambem como travessao e como
# hifen sem quebra. Aceitar so o "-" fazia "Art. 401-A" virar o artigo 401 com
# o texto comecando em "A." - e o 401-A sumia, colidindo com o 401.
#
# E o hifen do sufixo tem que estar COLADO. A CLT e o Codigo Penal, dos anos
# 40, separam o numero do texto com " - ": "Art. 58 - A duracao normal do
# trabalho". Com espaco permitido, esse "A" virava sufixo, e o artigo 58
# desaparecia dentro de um "58-A" com o texto comecando em "duracao normal".
HIFENS = "-‐‑‒–—"
RE_ARTIGO = re.compile(
    r"^Art\.?\s*(\d{1,4}(?:\.\d{3})?)\s*"
    r"([ºo°]?)\s*"
    r"((?:[" + HIFENS + r"][A-Z]{1,2}(?![a-zà-ÿ]))*)"
    r"\s*[\.‐-—-]?\s*",
)

RE_REVOGADO = re.compile(r"^\s*\(?\s*Revogad[oa]s?\b", re.IGNORECASE)

# Onde o caput termina e comecam os paragrafos.
RE_PARAGRAFO = re.compile(r"§|Par[áa]grafo\s+[úu]nico", re.IGNORECASE)

RE_ALTERADO = re.compile(
    r"\(\s*((?:Reda[çc][ãa]o dada|Inclu[íi]d[oa]|Vide|Renumerado)[^)]{0,120})\)",
    re.IGNORECASE,
)

# A hierarquia, do maior para o menor. Um cabeçalho fecha todos os que estão
# abaixo dele: quando começa o LIVRO V do CPC, a SEÇÃO do livro anterior acabou.
# Sem isso o art. 294 aparecia em "SEÇÃO II · CAPÍTULO IV", que é de outro lugar
# do código — o contexto ao lado da citação apontava para o capítulo errado.
NIVEIS = ("parte", "livro", "titulo", "capitulo", "secao", "subsecao")


def _nivel(linha: str) -> int:
    primeira = _sem_acento(linha.split()[0]) if linha.split() else ""
    return NIVEIS.index(primeira) if primeira in NIVEIS else len(NIVEIS)

# Tags que separam bloco. O resto é texto corrido: o Planalto exporta do Word,
# e <sup>o</sup> no meio de "Art. 1º" viraria uma linha própria se cada tag
# quebrasse — o número do artigo se descolaria do texto.
RE_BLOCO = re.compile(r"</\s*(p|div|tr|li|h[1-6]|table)\s*>|<\s*br\s*/?>", re.IGNORECASE)
RE_TAG = re.compile(r"<[^>]+>")
RE_ESPACO = re.compile(r"[ \t\xa0]+")


@dataclass
class Artigo:
    codigo: str = ""
    numero: str = ""            # "1º", "1.228", "5º-A"
    ordem: int = 0              # para ordenar e para achar por número
    texto: str = ""
    contexto: str = ""          # "LIVRO I · TÍTULO I · CAPÍTULO I"
    revogado: bool = False
    alterado_por: str = ""

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "codigo_nome": CODIGOS.get(self.codigo, {}).get("nome", self.codigo),
            "numero": self.numero,
            "ordem": self.ordem,
            "texto": self.texto,
            "contexto": self.contexto,
            "revogado": self.revogado,
            "alterado_por": self.alterado_por,
            "citacao": citar(self.codigo, self.numero),
        }


def citar(codigo: str, numero: str) -> str:
    """A forma como um advogado escreve a citação no texto."""
    sigla = {"cc": "CC", "cpc": "CPC", "cp": "CP", "clt": "CLT"}.get(codigo, codigo.upper())
    return f"{sigla}, art. {numero}"


# ------------------------------------------------------------- ler o HTML


def _texto_do_html(bruto: bytes) -> str:
    """
    HTML do Planalto virando texto, um bloco por linha.

    A codificação vem declarada como windows-1252 e é isso mesmo: decodificar
    como UTF-8 falha no primeiro acento.
    """
    achado = re.search(rb'charset=["\']?([\w-]+)', bruto[:4000], re.IGNORECASE)
    codificacao = (achado.group(1).decode("ascii", "ignore") if achado else "cp1252").lower()
    if codificacao in ("iso-8859-1", "latin-1", "windows-1252", "cp1252"):
        codificacao = "cp1252"
    try:
        texto = bruto.decode(codificacao, errors="replace")
    except LookupError:
        texto = bruto.decode("cp1252", errors="replace")

    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", texto, flags=re.S | re.I)
    texto = RE_BLOCO.sub("\n", texto)
    texto = RE_TAG.sub("", texto)
    texto = _html.unescape(texto)
    texto = RE_ESPACO.sub(" ", texto)
    return "\n".join(l.strip() for l in texto.split("\n"))


def _ordem(numero: str, sufixo: str = "") -> int:
    """
    Número do artigo virando inteiro ordenável.

    O sufixo entra em escalas decrescentes porque ele pode ter mais de um
    degrau: o Código Penal tem o 359-M-A, que fica entre o 359-M e o 359-N.
    Com um degrau só, o 359-M-A cairia depois do 359-N.
    """
    base = int(re.sub(r"\D", "", numero) or 0)
    valor = base * 1_000_000
    escala = 10_000
    for parte in re.findall(r"[A-Za-z]{1,2}", sufixo or "")[:3]:
        n = 0
        for c in parte.upper():
            n = n * 26 + (ord(c) - 64)
        valor += min(n, 99) * escala
        escala //= 100
    return valor


def ler_codigo(caminho: Path | str, codigo: str) -> tuple[list[Artigo], dict]:
    """
    Quebra o texto oficial em artigos, e diz o que deixou de fora.

    Cada artigo leva junto tudo o que vem depois dele até o próximo —
    parágrafos, incisos e alíneas fazem parte do artigo, e separá-los quebraria
    a citação.

    Duas coisas no arquivo NÃO são artigos do código, e tratá-las como se
    fossem produziria citação errada:

    O decreto que aprova a consolidação tem artigos próprios. A CLT começa com
    "Art. 1º Fica aprovada a Consolidação..." — que é artigo do decreto-lei,
    não da CLT. Eles vêm antes do primeiro título, e é por aí que se separa.

    As disposições finais citam artigos de outras leis. O CPC, ao alterar a
    Lei dos Juizados, escreve "Art. 48. Caberão embargos..." dentro do seu
    art. 1.064. Guardar isso como "CPC, art. 48" seria inventar um artigo que
    não existe — e é exatamente o erro que este módulo existe para não cometer.
    Dentro de um código o número só cresce; um número que anda para trás é
    citação, e o texto dela pertence ao artigo que está citando.
    """
    alvo = Path(caminho)
    linhas = _texto_do_html(alvo.read_bytes()).split("\n")

    artigos: list[Artigo] = []
    atual: Artigo | None = None
    corpo: list[str] = []
    estrutura: list[str] = []
    no_preambulo = True
    maior = 0
    fora = {"preambulo": 0, "citados": 0}

    def fechar() -> None:
        if atual is None:
            return
        junto = RE_ESPACO.sub(" ", " ".join(x for x in corpo if x)).strip()

        # O "o" sobrescrito de "Art. 1o" as vezes cai num bloco proprio no HTML
        # do Planalto, e chega aqui como primeira letra do texto. Sem colar de
        # volta, o artigo vira "1" com o texto comecando em "o Toda pessoa".
        solto = re.match(r"^([ºo°])\s+(?=[A-ZÀ-Ý])", junto)
        if solto and atual.numero.isdigit() and len(atual.numero) == 1:
            atual.numero += "º"
            junto = junto[solto.end():]

        # Revogado vale para o ARTIGO, nao para um inciso dele. O art. 3o do
        # Codigo Civil esta em vigor e teve os incisos revogados pela Lei
        # 13.146; procurar "Revogado" em qualquer lugar do texto marcava o
        # artigo inteiro como inexistente - que e o pior erro que esta tela
        # pode cometer. Artigo revogado no todo comeca com "(Revogado".
        atual.revogado = bool(RE_REVOGADO.match(junto))
        # A nota de alteração só vale se estiver no caput. O art. 121 do Código
        # Penal é de 1940; foi o § 2º-A que a Lei 13.104/2015 incluiu. Ler a
        # primeira nota do artigo inteiro fazia a tela dizer "art. 121 incluído
        # pela Lei de 2015" ao lado da citação — informação errada sobre a lei.
        caput = RE_PARAGRAFO.split(junto, maxsplit=1)[0]
        alterado = RE_ALTERADO.findall(caput)
        atual.alterado_por = alterado[0] if alterado else ""
        atual.texto = junto
        if junto:
            artigos.append(atual)

    for linha in linhas:
        if not linha:
            continue

        if RE_ESTRUTURA.match(linha) and len(linha) < 96:
            if no_preambulo:
                # Começou o código: o que veio antes era do decreto que o aprova.
                fechar()
                fora["preambulo"] = len(artigos)
                artigos = []
                atual, corpo = None, []
                # O contador volta a zero junto: o corpo recomeca no art. 1o, e
                # sem zerar aqui os dois primeiros artigos da CLT seriam lidos
                # como citacao do decreto que ficou para tras.
                maior = 0
                no_preambulo = False
            nivel = _nivel(linha)
            estrutura = [x for x in estrutura if _nivel(x) < nivel]
            estrutura.append(linha)
            estrutura = estrutura[-4:]
            continue

        achado = RE_ARTIGO.match(linha)
        if achado:
            cadeia = achado.group(3) or ""
            ordem = _ordem(achado.group(1), cadeia)

            if not no_preambulo and ordem <= maior:
                # Artigo de outra lei, citado aqui dentro: o texto é do artigo
                # que está citando, e não de um artigo novo deste código.
                fora["citados"] += 1
                if atual is not None:
                    corpo.append(linha)
                continue

            fechar()
            partes = re.findall(r"[A-Za-z]{1,2}", cadeia)
            numero = achado.group(1) + (achado.group(2) or "").replace("o", "º").replace("°", "º")
            if partes:
                numero += "-" + "-".join(p.upper() for p in partes)

            atual = Artigo(codigo=codigo, numero=numero, ordem=ordem,
                           contexto=" · ".join(estrutura))
            corpo = [linha[achado.end():].strip()]
            maior = max(maior, ordem)
            continue

        if atual is not None:
            corpo.append(linha)

    fechar()
    if no_preambulo:
        # Texto sem cabeçalho de estrutura nenhum: tudo o que há são artigos.
        fora["preambulo"] = 0
    return artigos, fora


def reconhecer(caminho: Path | str) -> str:
    """
    De qual código é este arquivo.

    Pelo nome e, se não bastar, pelo conteúdo: o nome do arquivo baixado varia
    conforme quem baixou, e errar isso guardaria o Código Penal como Civil.
    """
    alvo = Path(caminho)
    nome = _sem_acento(alvo.name)
    for chave, dados in CODIGOS.items():
        if any(p in nome for p in dados["pistas"]):
            return chave

    try:
        inicio = _sem_acento(_texto_do_html(alvo.read_bytes())[:6000])
    except OSError:
        return ""
    for chave, dados in CODIGOS.items():
        if any(p in inicio for p in dados["pistas"]):
            return chave
    return ""


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


# ---------------------------------------------------------- a base local


class Leis:
    """Os códigos guardados, e a busca por artigo e por palavra."""

    def __init__(self, base) -> None:
        self.base = base

    # ------------------------------------------------------------ importar

    def importar(self, caminho: Path | str, codigo: str = "") -> dict:
        alvo = Path(caminho)
        if not alvo.exists():
            raise ValueError("não achei esse arquivo")

        codigo = codigo or reconhecer(alvo)
        if codigo not in CODIGOS:
            raise ValueError(
                "não reconheci de qual código é este arquivo. Baixe a versão compilada "
                "do Planalto, ou escolha o código na lista."
            )

        artigos, fora = ler_codigo(alvo, codigo)
        if len(artigos) < 20:
            raise ValueError(
                f"só achei {len(artigos)} artigo(s) neste arquivo. Ele parece não ser o "
                "texto compilado da lei — salve a página do Planalto como HTML completo."
            )

        self.base.escrever("DELETE FROM artigos WHERE codigo = ?", (codigo,))
        for a in artigos:
            self.base.escrever(
                "INSERT INTO artigos (codigo, numero, ordem, texto, contexto, revogado, alterado_por) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (a.codigo, a.numero, a.ordem, a.texto, a.contexto,
                 1 if a.revogado else 0, a.alterado_por),
            )

        dados = CODIGOS[codigo]
        self.base.escrever(
            "INSERT INTO leis (codigo, nome, lei, fonte, arquivo, artigos, importado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime')) "
            "ON CONFLICT(codigo) DO UPDATE SET nome = excluded.nome, lei = excluded.lei, "
            "fonte = excluded.fonte, arquivo = excluded.arquivo, artigos = excluded.artigos, "
            "importado_em = excluded.importado_em",
            (codigo, dados["nome"], dados["lei"], dados["fonte"], str(alvo), len(artigos)),
        )
        self._reindexar(codigo)

        revogados = sum(1 for a in artigos if a.revogado)
        return {
            "codigo": codigo,
            "nome": dados["nome"],
            "artigos": len(artigos),
            "revogados": revogados,
            "primeiro": artigos[0].numero if artigos else "",
            "ultimo": artigos[-1].numero if artigos else "",
            "fora_do_corpo": fora,
        }

    def _reindexar(self, codigo: str) -> None:
        """Refaz o índice de busca por palavra deste código."""
        self.base.escrever("DELETE FROM artigos_busca WHERE codigo = ?", (codigo,))
        for a in self.base.buscar(
            "SELECT id, codigo, numero, texto FROM artigos WHERE codigo = ?", (codigo,)
        ):
            self.base.escrever(
                "INSERT INTO artigos_busca (rowid, codigo, numero, texto) VALUES (?, ?, ?, ?)",
                (a["id"], a["codigo"], a["numero"], a["texto"]),
            )

    def apagar(self, codigo: str) -> bool:
        self.base.escrever("DELETE FROM artigos_busca WHERE codigo = ?", (codigo,))
        self.base.escrever("DELETE FROM artigos WHERE codigo = ?", (codigo,))
        return self.base.escrever("DELETE FROM leis WHERE codigo = ?", (codigo,)) > 0

    # --------------------------------------------------------------- ler

    def instalados(self) -> list[dict]:
        """O que está no disco, e o que falta."""
        linhas = {l["codigo"]: l for l in self.base.buscar("SELECT * FROM leis")}
        saida = []
        for chave, dados in CODIGOS.items():
            l = linhas.get(chave)
            saida.append({
                "codigo": chave,
                "nome": dados["nome"],
                "lei": dados["lei"],
                "fonte": dados["fonte"],
                "instalado": l is not None,
                "artigos": l["artigos"] if l else 0,
                "importado_em": l["importado_em"] if l else "",
                "arquivo": l["arquivo"] if l else "",
            })
        return saida

    def artigo(self, codigo: str, numero: str) -> dict | None:
        """
        Um artigo pelo número.

        Aceita "421", "421º", "5-A" e "1.228": é como a pessoa digita, e exigir
        a forma exata faria a busca falhar no uso normal.
        """
        limpo = str(numero or "").strip().replace("°", "º")
        # A cadeia inteira de sufixos, nao so o ultimo degrau: procurar
        # "359-M-A" pegando so o "-A" cairia no artigo 359-A, que e outro.
        cadeia = "".join(re.findall(r"[" + HIFENS + r"][A-Za-z]{1,2}", limpo))
        alvo = _ordem(limpo, cadeia)
        if not alvo:
            return None

        linha = self.base.um(
            "SELECT * FROM artigos WHERE codigo = ? AND ordem = ?", (codigo, alvo)
        )
        return self._enfeitar(linha) if linha else None

    def procurar(self, termo: str, codigo: str = "", limite: int = 20) -> list[dict]:
        """
        Busca por palavra no texto dos artigos.

        Quando o termo é um número, a busca por número vem primeiro: quem digita
        "421" quer o artigo 421, não os artigos que citam 421.
        """
        termo = (termo or "").strip()
        if not termo:
            return []

        achados: list[dict] = []
        if re.fullmatch(r"\d{1,4}(?:\.\d{3})?(?:\s*[ºo°])?(?:-[A-Za-z])?", termo):
            for chave in ([codigo] if codigo else list(CODIGOS)):
                a = self.artigo(chave, termo)
                if a:
                    achados.append(a)

        onde = "artigos_busca MATCH ?"
        parametros: list = [_consulta_fts(termo)]
        if codigo:
            onde += " AND codigo = ?"
            parametros.append(codigo)

        try:
            linhas = self.base.buscar(
                f"SELECT a.* FROM artigos_busca b JOIN artigos a ON a.id = b.rowid "
                f"WHERE {onde} ORDER BY rank LIMIT ?",
                tuple(parametros) + (limite,),
            )
        except Exception:
            # FTS não gosta de tudo que a pessoa digita; cair para o modo simples
            # é melhor que devolver erro por causa de um caractere.
            like = f"%{termo}%"
            sql = "SELECT * FROM artigos WHERE texto LIKE ?"
            p2: list = [like]
            if codigo:
                sql += " AND codigo = ?"
                p2.append(codigo)
            linhas = self.base.buscar(sql + " ORDER BY ordem LIMIT ?", tuple(p2) + (limite,))

        vistos = {(a["codigo"], a["numero"]) for a in achados}
        for l in linhas:
            if (l["codigo"], l["numero"]) not in vistos:
                achados.append(self._enfeitar(l))
        return achados[:limite]

    def vizinhos(self, codigo: str, ordem: int, quantos: int = 3) -> list[dict]:
        """Os artigos ao redor — ler o anterior costuma resolver a dúvida."""
        linhas = self.base.buscar(
            "SELECT * FROM artigos WHERE codigo = ? AND ordem > ? ORDER BY ordem LIMIT ?",
            (codigo, ordem, quantos),
        )
        return [self._enfeitar(l) for l in linhas]

    @staticmethod
    def _enfeitar(linha: dict) -> dict:
        dados = dict(linha)
        dados["revogado"] = bool(dados.get("revogado"))
        dados["codigo_nome"] = CODIGOS.get(dados["codigo"], {}).get("nome", dados["codigo"])
        dados["citacao"] = citar(dados["codigo"], dados["numero"])
        dados["resumo"] = _resumir(dados.get("texto", ""))
        return dados

    def contagem(self) -> dict:
        total = self.base.contar("artigos")
        return {
            "artigos": total,
            "codigos": self.base.contar("leis"),
            "faltam": len(CODIGOS) - self.base.contar("leis"),
        }


def _consulta_fts(termo: str) -> str:
    """
    O que a pessoa digitou virando consulta que o FTS aceita.

    Aspas, hífens e parênteses são sintaxe para o FTS e erro de digitação para
    quem procura "boa-fé". Cada palavra vira um termo entre aspas.
    """
    palavras = re.findall(r"[0-9A-Za-zÀ-ÿ]+", termo)
    return " ".join(f'"{p}"' for p in palavras if len(p) > 1) or f'"{termo}"'


def _resumir(texto: str, limite: int = 190) -> str:
    limpo = RE_ESPACO.sub(" ", texto).strip()
    if len(limpo) <= limite:
        return limpo
    corte = limpo[:limite]
    espaco = corte.rfind(" ")
    return corte[: espaco if espaco > 60 else limite] + "…"
