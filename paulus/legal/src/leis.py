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
    # Os da Biblioteca (docs/PROGRESSO-BIBLIOTECA.md, M2). O endereco de cada
    # um foi conferido no Planalto em 30/09/2026.
    "cdc": {
        "nome": "Código de Defesa do Consumidor",
        "lei": "Lei nº 8.078, de 11 de setembro de 1990",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
        "pistas": ("8078", "defesa do consumidor", "cdc-"),
    },
    "cf": {
        "nome": "Constituição Federal",
        "lei": "Constituição da República Federativa do Brasil de 1988",
        "fonte": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm",
        "pistas": ("constituicaocompilado", "constituicao federal", "cf-"),
    },
    "ctn": {
        "nome": "Código Tributário Nacional",
        "lei": "Lei nº 5.172, de 25 de outubro de 1966",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
        "pistas": ("5172", "tributario nacional", "ctn-"),
    },
    "eca": {
        "nome": "Estatuto da Criança e do Adolescente",
        "lei": "Lei nº 8.069, de 13 de julho de 1990",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8069compilado.htm",
        "pistas": ("8069", "crianca e do adolescente", "eca-"),
    },
    "inquilinato": {
        "nome": "Lei do Inquilinato",
        "lei": "Lei nº 8.245, de 18 de outubro de 1991",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8245compilado.htm",
        "pistas": ("8245", "inquilinato", "inquilinato-"),
    },
    # Os que a camada de citacoes ja reconhecia ("art. 312 do CPP") e nao
    # tinham o texto guardado. Enderecos conferidos no Planalto em 30/09/2026.
    "cpp": {
        "nome": "Código de Processo Penal",
        "lei": "Decreto-Lei nº 3.689, de 3 de outubro de 1941",
        "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm",
        "pistas": ("3689", "processo penal", "cpp-"),
    },
    "ctb": {
        "nome": "Código de Trânsito Brasileiro",
        "lei": "Lei nº 9.503, de 23 de setembro de 1997",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm",
        "pistas": ("9503", "transito brasileiro", "ctb-"),
    },
    # O acervo de 25/10/2026: as leis que o escritorio usa fora dos codigos
    # (familia, imoveis, rural no Para, processo, o proprio advogado).
    # Enderecos conferidos no Planalto em 25/10/2026; texto compilado onde ha
    # (Improbidade com a reforma de 2021, Estatuto da Terra, ACP). Estas nao
    # sao "gerais": a busca por assunto so vai a elas quando a frase as nomeia
    # (CODIGO_NA_FRASE) - medido em tools/medir_leis.py.
    "oab": {
        "nome": "Estatuto da Advocacia e da OAB",
        "lei": "Lei nº 8.906, de 4 de julho de 1994",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8906.htm",
        "pistas": ("8906", "estatuto da advocacia", "oab-"),
    },
    "lgpd": {
        "nome": "Lei Geral de Proteção de Dados Pessoais",
        "lei": "Lei nº 13.709, de 14 de agosto de 2018",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm",
        "pistas": ("13709", "protecao de dados pessoais", "lgpd-"),
    },
    "lindb": {
        "nome": "Lei de Introdução às Normas do Direito Brasileiro",
        "lei": "Decreto-Lei nº 4.657, de 4 de setembro de 1942",
        "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm",
        "pistas": ("4657", "introducao as normas", "lindb-"),
    },
    "alimentos": {
        "nome": "Lei de Alimentos",
        "lei": "Lei nº 5.478, de 25 de julho de 1968",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l5478.htm",
        "pistas": ("5478", "acao de alimentos", "alimentos-"),
    },
    "bem_de_familia": {
        "nome": "Lei do Bem de Família",
        "lei": "Lei nº 8.009, de 29 de março de 1990",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8009.htm",
        "pistas": ("8009", "impenhorabilidade do bem de familia", "bem_de_familia-"),
        "minimo": 6,
    },
    "registros": {
        "nome": "Lei de Registros Públicos",
        "lei": "Lei nº 6.015, de 31 de dezembro de 1973",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l6015compilada.htm",
        "pistas": ("6015", "registros publicos", "registros-"),
    },
    "terra": {
        "nome": "Estatuto da Terra",
        "lei": "Lei nº 4.504, de 30 de novembro de 1964",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l4504compilada.htm",
        "pistas": ("4504", "estatuto da terra", "terra-"),
    },
    "florestal": {
        "nome": "Código Florestal",
        "lei": "Lei nº 12.651, de 25 de maio de 2012",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651compilado.htm",
        "pistas": ("12651", "protecao da vegetacao nativa", "florestal-"),
    },
    "ambientais": {
        "nome": "Lei de Crimes Ambientais",
        "lei": "Lei nº 9.605, de 12 de fevereiro de 1998",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        "pistas": ("9605", "lesivas ao meio ambiente", "ambientais-"),
    },
    "juizados": {
        "nome": "Lei dos Juizados Especiais",
        "lei": "Lei nº 9.099, de 26 de setembro de 1995",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l9099.htm",
        "pistas": ("9099", "juizados especiais civeis e criminais", "juizados-"),
    },
    "ms": {
        "nome": "Lei do Mandado de Segurança",
        "lei": "Lei nº 12.016, de 7 de agosto de 2009",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/lei/l12016.htm",
        "pistas": ("12016", "mandado de seguranca individual e coletivo", "ms-"),
    },
    "acp": {
        "nome": "Lei da Ação Civil Pública",
        "lei": "Lei nº 7.347, de 24 de julho de 1985",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l7347compilada.htm",
        "pistas": ("7347", "acao civil publica", "acp-"),
    },
    "arbitragem": {
        "nome": "Lei de Arbitragem",
        "lei": "Lei nº 9.307, de 23 de setembro de 1996",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l9307.htm",
        "pistas": ("9307", "dispoe sobre a arbitragem", "arbitragem-"),
    },
    "mediacao": {
        "nome": "Lei de Mediação",
        "lei": "Lei nº 13.140, de 26 de junho de 2015",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13140.htm",
        "pistas": ("13140", "mediacao entre particulares", "mediacao-"),
    },
    "custeio": {
        "nome": "Lei de Custeio da Seguridade Social",
        "lei": "Lei nº 8.212, de 24 de julho de 1991",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8212cons.htm",
        "pistas": ("8212", "plano de custeio", "custeio-"),
    },
    "beneficios": {
        "nome": "Lei de Benefícios da Previdência Social",
        "lei": "Lei nº 8.213, de 24 de julho de 1991",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm",
        "pistas": ("8213", "planos de beneficios", "beneficios-"),
    },
    "falencia": {
        "nome": "Lei de Recuperação Judicial e Falência",
        "lei": "Lei nº 11.101, de 9 de fevereiro de 2005",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101.htm",
        "pistas": ("11101", "recuperacao judicial", "falencia-"),
    },
    "idoso": {
        "nome": "Estatuto da Pessoa Idosa",
        "lei": "Lei nº 10.741, de 1º de outubro de 2003",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/2003/l10.741.htm",
        "pistas": ("10741", "estatuto da pessoa idosa", "idoso-"),
    },
    "maria_da_penha": {
        "nome": "Lei Maria da Penha",
        "lei": "Lei nº 11.340, de 7 de agosto de 2006",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
        "pistas": ("11340", "violencia domestica e familiar contra a mulher", "maria_da_penha-"),
    },
    "licitacoes": {
        "nome": "Lei de Licitações e Contratos Administrativos",
        "lei": "Lei nº 14.133, de 1º de abril de 2021",
        "fonte": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
        "pistas": ("14133", "licitacoes e contratos administrativos", "licitacoes-"),
    },
    "improbidade": {
        "nome": "Lei de Improbidade Administrativa",
        "lei": "Lei nº 8.429, de 2 de junho de 1992",
        "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l8429compilada.htm",
        "pistas": ("8429", "improbidade administrativa", "improbidade-"),
    },
}

# Os codigos de sempre: a busca por assunto sem lei nomeada fica neles, como
# antes do acervo de 25/10 - com 32 leis, "prazo para contestar" achava a lei
# de outro procedimento antes do CPC.
GERAIS = ("cc", "cpc", "cp", "clt", "cdc", "cf", "ctn", "eca", "inquilinato", "cpp", "ctb")


def minimo_de_artigos(codigo: str) -> int:
    """Abaixo disto o arquivo nao e a lei inteira (a pagina mudou, ou e outro texto)."""
    return int(CODIGOS.get(codigo, {}).get("minimo", 20))

# O identificador de cada codigo na camada de inteligencia
# (src/inteligencia/extratores/regras_leis.py): e por ele que uma citacao
# achada num livro ("art. 18 do CDC") chega ao artigo guardado aqui.
INSTRUMENTO = {
    "cc": "lei_10406_2002", "cpc": "lei_13105_2015", "cp": "decreto_lei_2848_1940", "clt": "decreto_lei_5452_1943",
    "cdc": "lei_8078_1990", "cf": "constituicao_1988", "ctn": "lei_5172_1966", "eca": "lei_8069_1990",
    "inquilinato": "lei_8245_1991", "cpp": "decreto_lei_3689_1941", "ctb": "lei_9503_1997",
    "oab": "lei_8906_1994", "lgpd": "lei_13709_2018", "lindb": "decreto_lei_4657_1942", "alimentos": "lei_5478_1968",
    "bem_de_familia": "lei_8009_1990", "registros": "lei_6015_1973", "terra": "lei_4504_1964",
    "florestal": "lei_12651_2012", "ambientais": "lei_9605_1998", "juizados": "lei_9099_1995", "ms": "lei_12016_2009",
    "acp": "lei_7347_1985", "arbitragem": "lei_9307_1996", "mediacao": "lei_13140_2015", "custeio": "lei_8212_1991",
    "beneficios": "lei_8213_1991", "falencia": "lei_11101_2005", "idoso": "lei_10741_2003",
    "maria_da_penha": "lei_11340_2006", "licitacoes": "lei_14133_2021", "improbidade": "lei_8429_1992",
}
CODIGO_DO_INSTRUMENTO = {v: k for k, v in INSTRUMENTO.items()}

# Como cada lei se apresenta no alto do proprio texto: "LEI Nº 8.078, DE 11
# DE SETEMBRO DE 1990". Reconhecer pelo numero, e pelo que aparece PRIMEIRO,
# porque o CDC cita a Constituicao no art. 1o e a Lei do Inquilinato cita o
# Codigo Civil - quem procura "codigo civil" no comeco do texto erra de lei.
# ("nº" tem o "º", que para a expressão regular é letra: daí o \S{0,2}.)
TITULOS = {
    "cc": r"lei n\S{0,2}\s*10\.?406",
    "cpc": r"lei n\S{0,2}\s*13\.?105",
    "cp": r"decreto-lei n\S{0,2}\s*2\.?848",
    "clt": r"decreto-lei n\S{0,2}\s*5\.?452",
    "cdc": r"lei n\S{0,2}\s*8\.?078",
    "cf": r"constituicao da republica federativa do brasil",
    "ctn": r"lei n\S{0,2}\s*5\.?172",
    "eca": r"lei n\S{0,2}\s*8\.?069",
    "inquilinato": r"lei n\S{0,2}\s*8\.?245",
    "cpp": r"decreto-lei n\S{0,2}\s*3\.?689",
    "ctb": r"lei n\S{0,2}\s*9\.?503",
    "oab": r"lei n\S{0,2}\s*8\.?906",
    "lgpd": r"lei n\S{0,2}\s*13\.?709",
    "lindb": r"decreto-lei n\S{0,2}\s*4\.?657",
    "alimentos": r"lei n\S{0,2}\s*5\.?478",
    "bem_de_familia": r"lei n\S{0,2}\s*8\.?009",
    "registros": r"lei n\S{0,2}\s*6\.?015",
    "terra": r"lei n\S{0,2}\s*4\.?504",
    "florestal": r"lei n\S{0,2}\s*12\.?651",
    "ambientais": r"lei n\S{0,2}\s*9\.?605",
    "juizados": r"lei n\S{0,2}\s*9\.?099",
    "ms": r"lei n\S{0,2}\s*12\.?016",
    "acp": r"lei n\S{0,2}\s*7\.?347",
    "arbitragem": r"lei n\S{0,2}\s*9\.?307",
    "mediacao": r"lei n\S{0,2}\s*13\.?140",
    "custeio": r"lei n\S{0,2}\s*8\.?212",
    "beneficios": r"lei n\S{0,2}\s*8\.?213",
    "falencia": r"lei n\S{0,2}\s*11\.?101",
    "idoso": r"lei n\S{0,2}\s*10\.?741",
    "maria_da_penha": r"lei n\S{0,2}\s*11\.?340",
    "licitacoes": r"lei n\S{0,2}\s*14\.?133",
    "improbidade": r"lei n\S{0,2}\s*8\.?429",
}

# Os artigos do ADCT recomecam do 1o dentro do texto da Constituicao. Ficam no
# mesmo codigo, com a ordem depois de todos os artigos do corpo e o numero
# "ADCT 1º": sem isso, o ADCT inteiro era lido como citacao e ia parar dentro
# do art. 250.
ADCT_BASE = 10 ** 11
RE_ADCT = re.compile(r"^ATO DAS DISPOSI[ÇC][ÕO]ES CONSTITUCIONAIS TRANSIT[ÓO]RIAS\.?$")

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
    r"|COMPLEMENTAR|Complementar"
    # O CTN numera por extenso: "LIVRO PRIMEIRO", "LIVRO SEGUNDO".
    r"|PRIMEIR[OA]|Primeir[oa]|SEGUND[OA]|Segund[oa]|TERCEIR[OA]|Terceir[oa]|QUART[OA]|Quart[oa]"
    r"|QUINT[OA]|Quint[oa]|SEXT[OA]|Sext[oa])"
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

# As notas que mudam a redacao do artigo, em qualquer parte dele (caput,
# paragrafo, inciso): "(Redacao dada pela Lei n 12.741, de 2012)",
# "(Incluido pela Lei n 14.181, de 2021)", "(Revogado pela Lei n 13.146, de
# 2015)". Conferido nos textos do Planalto em 30/09/2026 (CDC, CC, CPC): sao
# essas, e o ano e o ultimo da nota ("de 21.3.1995" tambem).
RE_NOTA_DE_REDACAO = re.compile(
    r"\((?:Reda[çc][ãa]o dada|Inclu[íi]d[oa]s?|Revogad[oa]s?|Acrescid[oa]s?|Renumerad[oa][^()]{0,40}?)"
    r"\s+pel[oa]s?\s+([^()]{0,160}?)\)", re.IGNORECASE)
RE_ANO = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def ano_da_alteracao(texto: str) -> int:
    """
    O ano mais recente em que o artigo (ou um paragrafo, inciso ou alinea
    dele) teve a redacao mudada; 0 quando o texto nao traz nota nenhuma. E o
    que a Biblioteca compara com o ano da obra (M6) - nao e o motor de
    vigencia: nao diz qual era a redacao numa data passada.
    """
    anos = [int(a) for m in RE_NOTA_DE_REDACAO.finditer(texto or "") for a in RE_ANO.findall(m.group(1))]
    return max(anos) if anos else 0

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


SIGLAS = {"cc": "CC", "cpc": "CPC", "cp": "CP", "clt": "CLT", "cdc": "CDC", "cf": "CF", "ctn": "CTN", "eca": "ECA",
          "inquilinato": "Lei 8.245/1991", "cpp": "CPP", "ctb": "CTB",
          "oab": "EAOAB", "lgpd": "LGPD", "lindb": "LINDB", "alimentos": "Lei 5.478/1968",
          "bem_de_familia": "Lei 8.009/1990", "registros": "Lei 6.015/1973", "terra": "Estatuto da Terra",
          "florestal": "Código Florestal", "ambientais": "Lei 9.605/1998", "juizados": "Lei 9.099/1995",
          "ms": "Lei 12.016/2009", "acp": "Lei 7.347/1985", "arbitragem": "Lei 9.307/1996",
          "mediacao": "Lei 13.140/2015", "custeio": "Lei 8.212/1991", "beneficios": "Lei 8.213/1991",
          "falencia": "Lei 11.101/2005", "idoso": "Estatuto da Pessoa Idosa", "maria_da_penha": "Lei 11.340/2006",
          "licitacoes": "Lei 14.133/2021", "improbidade": "Lei 8.429/1992"}


def citar(codigo: str, numero: str) -> str:
    """A forma como um advogado escreve a citação no texto."""
    sigla = SIGLAS.get(codigo, codigo.upper())
    if str(numero).startswith("ADCT "):
        return f"{sigla}, ADCT, art. {numero[5:]}"
    return f"{sigla}, art. {numero}"


# ------------------------------------------------------------- ler o HTML


def _texto_do_html(bruto: bytes) -> str:
    """
    HTML do Planalto virando texto, um bloco por linha.

    A codificação vem declarada como windows-1252 e é isso mesmo: decodificar
    como UTF-8 falha no primeiro acento. Algumas páginas antigas do FrontPage
    vêm em UTF-16, com a marca no começo (a Lei Maria da Penha): lidas como
    windows-1252, eram um zero no meio de cada letra e nenhum artigo.
    """
    if bruto[:2] in (b"\xff\xfe", b"\xfe\xff"):
        texto = bruto.decode("utf-16", errors="replace")
    else:
        achado = re.search(rb'charset=["\']?([\w-]+)', bruto[:4000], re.IGNORECASE)
        codificacao = (achado.group(1).decode("ascii", "ignore") if achado else "cp1252").lower()
        if codificacao in ("iso-8859-1", "latin-1", "windows-1252", "cp1252"):
            codificacao = "cp1252"
        try:
            texto = bruto.decode(codificacao, errors="replace")
        except LookupError:
            texto = bruto.decode("cp1252", errors="replace")

    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", texto, flags=re.S | re.I)
    # A quebra de linha do codigo-fonte e espaco, como no navegador. O
    # Planalto quebra o paragrafo no meio ("Art." numa linha, "10." na
    # outra): lida como linha, o artigo nao comecava, e o texto dele ia
    # parar no artigo anterior. Medido em 30/09/2026: o Codigo Penal perdia
    # 44 artigos (o 147-A inclusive), a CLT 28, o CTN mais da metade.
    texto = re.sub(r"[\r\n]+", " ", texto)
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
    return ler_linhas(_texto_do_html(alvo.read_bytes()).split("\n"), codigo)


# Uma linha de dispositivo: paragrafo, inciso, alinea. Nunca e nome de
# Titulo ou Capitulo, mesmo curta.
RE_A_SEGUIR = re.compile(r"(seguinte reda[çc][ãa]o|passa(?:m)? a vigorar[^:]*):\s*$", re.IGNORECASE)
RE_DISPOSITIVO = re.compile(r"^(?:§|Par[áa]grafo|[IVXLCDM]{1,7}\s*[-–—]|[a-z]\)|\(Revogad|\(Vetad|\(Inclu)")


def ler_linhas(linhas: list[str], codigo: str) -> tuple[list[Artigo], dict]:
    """
    O mesmo `ler_codigo`, sobre linhas de texto: as do HTML do Planalto ou as
    de um PDF da lei (a triagem da Biblioteca, src/biblioteca/triagem.py).

    Três coisas a mais do que o Código Civil precisava:

    - **o nome do Titulo** ("DAS PESSOAS NATURAIS", na linha de baixo do
      "TÍTULO I") não é texto do artigo anterior. Antes ele ia parar no fim
      do último artigo do capítulo que acabou;
    - **o ADCT da Constituição** recomeça do art. 1º: vira "ADCT 1º", com a
      ordem depois do corpo (ver ADCT_BASE);
    - **só a CLT tem decreto com artigos antes do primeiro Titulo.** O CTN
      tem o art. 1º numa "Disposição preliminar", antes do Livro Primeiro:
      jogar fora tudo o que vinha antes do primeiro cabeçalho perdia o art.
      1º do CTN.
    """
    artigos: list[Artigo] = []
    # Os artigos antes do primeiro cabeçalho ficam em suspenso: se a
    # numeração recomeça depois dele (a CLT volta ao art. 1º), eram do
    # decreto que aprova o código, e saem; se continua (o CTN vai ao art. 2º),
    # eram do código.
    pendentes: list[Artigo] | None = None
    maior_pendente = 0
    atual: Artigo | None = None
    corpo: list[str] = []
    estrutura: list[str] = []
    no_preambulo = True
    maior = 0
    base_ordem = 0          # ADCT_BASE depois do "ATO DAS DISPOSIÇÕES..."
    apos_cabecalho = False  # a linha seguinte a um cabeçalho pode ser o nome dele
    fora = {"preambulo": 0, "citados": 0, "adct": 0}

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

    entre_aspas = False
    linha_anterior = ""
    for linha in linhas:
        linha = (linha or "").strip()
        if not linha or re.fullmatch(r"\[pagina \d+\]", linha):
            continue
        anterior_redacao = bool(RE_A_SEGUIR.search(linha_anterior))
        linha_anterior = linha

        # A lei que muda outra cita o texto novo entre aspas, e a citação pode
        # abrir antes do "Art.": o art. 178 da Lei 14.133 traz “CAPÍTULO II-B
        # ... Art. 337-E ... Art. 337-P ...” para o Código Penal. Lido como
        # artigo, o 337-P virava o maior número da lei, e do 179 ao 194 tudo
        # passava por citação e sumia. Entre a aspa que abre e a que fecha,
        # tudo é corpo do artigo que está citando.
        if entre_aspas or linha.startswith("“"):
            if RE_ARTIGO.match(linha.lstrip("“ ")):
                fora["citados"] += 1
            if atual is not None:
                corpo.append(linha)
            abre, fecha = linha.rfind("“"), linha.rfind("”")
            if abre != fecha:   # sem aspa nenhuma na linha (-1 e -1), a citação continua como estava
                entre_aspas = abre > fecha
            continue

        if codigo == "cf" and not no_preambulo and not base_ordem and RE_ADCT.match(linha):
            # Acabou o corpo da Constituicao: o ADCT recomeca a numeracao.
            fechar()
            atual, corpo = None, []
            base_ordem, maior = ADCT_BASE, 0
            estrutura = ["ADCT"]
            apos_cabecalho = True
            continue

        if RE_ESTRUTURA.match(linha) and len(linha) < 96:
            if no_preambulo:
                # Começou o código. O que veio antes fica em suspenso (ver
                # `pendentes`), e o contador volta a zero: sem isso, os dois
                # primeiros artigos da CLT seriam lidos como citação do
                # decreto que ficou para trás.
                fechar()
                pendentes, maior_pendente = artigos, maior
                artigos = []
                atual, corpo = None, []
                maior = 0
                no_preambulo = False
            nivel = _nivel(linha)
            estrutura = [x for x in estrutura if _nivel(x) < nivel]
            estrutura.append(linha)
            estrutura = estrutura[-4:] if estrutura[0] != "ADCT" else (["ADCT"] + estrutura[1:])[-5:]
            apos_cabecalho = True
            continue

        achado = RE_ARTIGO.match(linha)
        if achado:
            apos_cabecalho = False
            cadeia = achado.group(3) or ""
            ordem = base_ordem + _ordem(achado.group(1), cadeia)

            if pendentes is not None:
                if pendentes and ordem <= maior_pendente:
                    fora["preambulo"] = len(pendentes)   # a numeração recomeçou
                else:
                    artigos = pendentes + artigos
                    maior = max(maior, maior_pendente)
                pendentes = None

            # Sem aspas, a lei antiga diz "o artigo 921 do Código de Processo
            # Civil ... passa a vigorar com a seguinte redação:" e o artigo vem
            # na linha de baixo (Lei de Alimentos, de 1968). Logo depois dessa
            # fórmula, um número muito à frente é o artigo da outra lei.
            citado_sem_aspas = bool(anterior_redacao and maior and ordem > maior + 50 * 1_000_000)
            if (not no_preambulo and ordem <= maior) or citado_sem_aspas:
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
            if base_ordem:
                numero = "ADCT " + numero
                fora["adct"] += 1

            atual = Artigo(codigo=codigo, numero=numero, ordem=ordem,
                           contexto=" · ".join(estrutura))
            corpo = [linha[achado.end():].strip()]
            maior = max(maior, ordem)
            continue

        # O nome do cabeçalho, na linha de baixo dele: curto, sem cara de
        # dispositivo. Não é texto do artigo que ficou para trás.
        if apos_cabecalho and len(linha) < 160 and not RE_DISPOSITIVO.match(linha):
            continue
        apos_cabecalho = False
        if atual is not None:
            corpo.append(linha)

    fechar()
    if pendentes:
        artigos = pendentes + artigos
    if no_preambulo:
        # Texto sem cabeçalho de estrutura nenhum: tudo o que há são artigos.
        fora["preambulo"] = 0
    # A página que não é compilada (Lei de Alimentos, do Mandado de Segurança)
    # traz a redação antiga riscada e, logo depois, a de agora "(Redação dada
    # pela Lei ...)": o mesmo artigo duas vezes. Fica a última, a vigente - e
    # a base, que tem um artigo por número, deixa de recusar a lei inteira.
    ultima = {a.ordem: i for i, a in enumerate(artigos)}
    if len(ultima) < len(artigos):
        fora["redacao_antiga"] = len(artigos) - len(ultima)
        artigos = [a for i, a in enumerate(artigos) if ultima[a.ordem] == i]
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
        return reconhecer_texto(_texto_do_html(alvo.read_bytes()))
    except OSError:
        return ""


def reconhecer_texto(texto: str) -> str:
    """
    De qual código é este texto - pelo título que a lei tem no alto
    ("LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990"), o que aparecer primeiro.
    Serve para o HTML do Planalto e para o PDF que alguém entregou como
    material. Sem título reconhecido, as pistas de antes.
    """
    inicio = _sem_acento(texto[:6000])
    achados = []
    for chave, padrao in TITULOS.items():
        m = re.search(padrao, inicio)
        if m:
            achados.append((m.start(), chave))
    if achados:
        return min(achados)[1]
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
        return self._gravar(codigo, artigos, fora, str(alvo), CODIGOS[codigo]["fonte"])

    def importar_texto(self, texto: str, codigo: str, arquivo: str = "") -> dict:
        """
        A lei vinda de um PDF ou TXT, e não do HTML do Planalto: alguém entregou
        o CDC como material (src/biblioteca/triagem.py). O texto passa pelo
        mesmo leitor, artigo por artigo; a fonte guardada diz que veio de um
        arquivo, e não do Planalto.
        """
        if codigo not in CODIGOS:
            raise ValueError("não reconheci de qual código é este texto")
        artigos, fora = ler_linhas((texto or "").split("\n"), codigo)
        return self._gravar(codigo, artigos, fora, arquivo, "arquivo entregue: " + Path(arquivo or "").name)

    def _gravar(self, codigo: str, artigos: list[Artigo], fora: dict, arquivo: str, fonte: str) -> dict:
        if len(artigos) < minimo_de_artigos(codigo):
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
            (codigo, dados["nome"], dados["lei"], fonte, arquivo, len(artigos)),
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
        # "ADCT 2", "ADCT, art. 2º": o ADCT tem a numeracao dele (ADCT_BASE).
        base_ordem = 0
        if re.match(r"(?i)adct\b", limpo):
            base_ordem = ADCT_BASE
            limpo = re.sub(r"(?i)^adct[\s,]*(?:art\.?\s*)?", "", limpo)
        # A cadeia inteira de sufixos, nao so o ultimo degrau: procurar
        # "359-M-A" pegando so o "-A" cairia no artigo 359-A, que e outro.
        cadeia = "".join(re.findall(r"[" + HIFENS + r"][A-Za-z]{1,2}", limpo))
        alvo = _ordem(limpo, cadeia)
        if not alvo:
            return None
        alvo += base_ordem

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

    def procurar_assunto(self, pergunta: str, limite: int = 3) -> list[dict]:
        """
        Os artigos que mais têm o assunto da pergunta, por radical ("contestar"
        acha "contestação") e no código que a frase nomeia, quando nomeia.

        É a reserva da triagem (src/triagem.py), não o caminho principal:
        medido em 02/10/2026 nas dez perguntas de lei da bateria, a busca por
        palavra acerta o artigo vizinho mais do que o certo ("prazo para
        contestar" trouxe o art. 679 antes do 335). Por isso só os primeiros.
        """
        # O mapa de assuntos (src/mapa_de_assuntos.py) vem primeiro: o assunto
        # que ele conhece aponta o artigo; a busca por palavra completa.
        import mapa_de_assuntos

        do_mapa: list[dict] = []
        for codigo, numero, _rotulo in mapa_de_assuntos.artigos_do_assunto(pergunta):
            a = self.artigo(codigo, numero)
            if a and not a["revogado"] and a not in do_mapa:
                do_mapa.append(a)
        if len(do_mapa) >= limite:
            return do_mapa[:limite]
        plano = _plano(pergunta)
        codigos = [c for c, padrao in CODIGO_NA_FRASE if re.search(padrao, plano)]
        radicais: list[str] = []
        for palavra in re.findall(r"[a-z]{4,}", plano):
            if palavra in PALAVRAS_DE_PERGUNTA:
                continue
            radical = palavra[:6]
            if radical not in radicais:
                radicais.append(radical)
        if not radicais:
            return do_mapa
        # Sem lei nomeada, so os codigos de sempre (GERAIS): as leis de 25/10
        # entram quando a frase as nomeia. Medido em tools/medir_leis.py.
        codigos = codigos or list(GERAIS)
        onde = "artigos_busca MATCH ?"
        parametros: list = [" OR ".join(f'"{r}"*' for r in radicais)]
        if codigos:
            onde += " AND a.codigo IN (" + ",".join("?" * len(codigos)) + ")"
            parametros += codigos
        try:
            linhas = self.base.buscar(
                f"SELECT a.* FROM artigos_busca b JOIN artigos a ON a.id = b.rowid WHERE {onde} "
                f"ORDER BY bm25(artigos_busca) LIMIT ?", tuple(parametros) + (limite,))
        except Exception:  # noqa: BLE001 - FTS recusou a consulta: sem reserva
            return do_mapa
        vistos = {(a["codigo"], a["numero"]) for a in do_mapa}
        por_palavra = [self._enfeitar(l) for l in linhas if (l["codigo"], l["numero"]) not in vistos]
        return (do_mapa + por_palavra)[:limite]

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
        # M6 da Biblioteca: tirado do texto guardado, e nao de uma coluna -
        # vale tambem para o codigo importado antes de existir a regra.
        dados["alterado_em"] = ano_da_alteracao(dados.get("texto", ""))
        return dados

    def contagem(self) -> dict:
        total = self.base.contar("artigos")
        return {
            "artigos": total,
            "codigos": self.base.contar("leis"),
            "faltam": len(CODIGOS) - self.base.contar("leis"),
        }


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


# O código que a frase nomeia ("no CPC", "segundo o Código Civil").
CODIGO_NA_FRASE = (
    # As leis de 25/10 vem antes: quem pega o primeiro achado (citacoes.py)
    # nao pode cair no Codigo Civil quando a frase nomeia a Lei do Bem de
    # Familia. Assunto que tambem esta num codigo (alimentos e bem de familia
    # no CC, mediacao no CPC) so conta com o nome da lei ou o numero.
    ("oab", r"estatuto da (advocacia|oab)|\beaoab\b|\b8\.?906\b"),
    ("lgpd", r"\blgpd\b|protecao de dados|\b13\.?709\b"),
    ("lindb", r"\blindb\b|introducao as normas|\b4\.?657\b"),
    ("alimentos", r"lei de alimentos|\b5\.?478\b"),
    ("bem_de_familia", r"lei do bem de familia|\b8\.?009\b"),
    ("registros", r"registros? publicos|registro de imoveis|\b6\.?015\b"),
    ("terra", r"estatuto da terra|arrendamento rural|parceria rural|\b4\.?504\b"),
    ("florestal", r"codigo florestal|reserva legal|preservacao permanente|\b12\.?651\b"),
    ("ambientais", r"crimes? ambienta|\b9\.?605\b"),
    ("juizados", r"juizados? especia|\b9\.?099\b"),
    ("ms", r"mandado de seguranca|\b12\.?016\b"),
    ("acp", r"acao civil publica|\b7\.?347\b"),
    ("arbitragem", r"arbitragem|sentenca arbitral|\b9\.?307\b"),
    ("mediacao", r"lei de mediacao|\b13\.?140\b"),
    ("custeio", r"lei de custeio|contribuic\w* previdenciari|\b8\.?212\b"),
    ("beneficios", r"lei de beneficios|aposentadoria|auxilio[- ]doenca|auxilio por incapacidade|pensao por morte"
                   r"|salario[- ]maternidade|beneficio previdenciario|\binss\b|\b8\.?213\b"),
    ("falencia", r"falencia|recuperacao (judicial|extrajudicial)|\b11\.?101\b"),
    ("idoso", r"estatuto d[ao] (pessoa )?idos|\b10\.?741\b"),
    ("maria_da_penha", r"maria da penha|violencia domestica|medidas? protetivas?|\b11\.?340\b"),
    ("licitacoes", r"licitac|\bpregao\b|\b14\.?133\b"),
    ("improbidade", r"improbidade|\b8\.?429\b"),
    ("cpc", r"\bcpc\b|processo civil"), ("cc", r"\bcc\b|codigo civil"), ("cf", r"\bcf\b|constituicao"),
    ("clt", r"\bclt\b|trabalhist"), ("cdc", r"\bcdc\b|defesa do consumidor"), ("cpp", r"\bcpp\b|processo penal"),
    ("cp", r"\bcp\b|codigo penal"), ("ctn", r"\bctn\b|tributario nacional"), ("eca", r"\beca\b|crianca e do adolescente"),
    ("ctb", r"\bctb\b|codigo de transito"), ("inquilinato", r"inquilinato"),
)
# O que toda pergunta de lei tem e não diz o assunto.
PALAVRAS_DE_PERGUNTA = set("""qual quais quanto quanta quando onde como porque para pelo pela pelos pelas com sem
sobre entre que uma umas uns dos das nos nas aos art artigo artigos codigo lei leis segundo conforme prazo prazos
precisa precisam constar forma tempo geral diferenciado cabimento estao esta sao ser ter tem hipoteses garante
pretensao contado contados dias corridos uteis deve devem pode podem existe isso este esta essa esse""".split())


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
