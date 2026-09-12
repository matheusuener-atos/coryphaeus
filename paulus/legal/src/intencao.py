"""
O que a pessoa está pedindo — antes de sair procurando.

A conversa tinha um caminho só: toda mensagem virava busca nos documentos.
Pedir "anote uma reunião no calendário dia 11/09 às 13:40" fazia o programa
procurar a palavra "reunião" dentro dos contratos e responder "não encontrei
essa informação nos trechos fornecidos" — uma resposta correta para a pergunta
errada. O escritório tem agenda, tarefas, financeiro e códigos de lei; a
conversa não alcançava nada disso.

Este módulo lê a frase e diz o que ela é. Três decisões:

**Por regra, não por modelo.** Reconhecer "anote", "marque", "agende" seguido
de uma data é instantâneo e repetível. Perguntar a um modelo de 3 bilhões de
parâmetros o que a pessoa quis dizer custaria um minuto e erraria de formas
imprevisíveis. O modelo continua sendo para o que é de verdade ambíguo: ler
documento e redigir.

**A dúvida não vira palpite.** Sem verbo de ação reconhecido, ou sem data
quando a ação precisa de data, o pedido volta para o caminho de sempre — os
documentos. Um programa que adivinha errado o que fazer com o dia de alguém é
pior que um que só procura.

**Entender não é fazer.** O que sai daqui é uma proposta com os campos à
vista: o que entendi, a data que li, a hora, o aviso. Quem confirma é a
pessoa. Nada é gravado por interpretação de frase.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------- palavras

# Os verbos que pedem uma coisa no tempo. "Anote" aparece primeiro porque foi
# a palavra que o programa não entendeu.
VERBOS_AGENDA = (
    "anota", "anote", "anotar", "marca", "marque", "marcar", "agenda",
    "agende", "agendar", "coloca", "coloque", "colocar", "poe", "ponha",
    "por na agenda", "adiciona", "adicione", "adicionar", "cria", "crie",
    "criar", "registra", "registre", "registrar", "guarda", "guarde",
)

# O que a coisa é. Sem isto, "crie um documento" viraria compromisso.
COISAS_AGENDA = ("reuniao", "compromisso", "audiencia", "consulta", "encontro",
                 "visita", "call", "videoconferencia", "sessao", "julgamento",
                 "pericia", "na agenda", "no calendario")

COISAS_TAREFA = ("tarefa", "lembrete", "pendencia", "a fazer", "todo",
                 "na lista", "nas tarefas")
COISAS_PRAZO = ("prazo", "vencimento")

# "abra a procuracao Matheus" nao e pergunta sobre o conteudo: e pedido para
# abrir um arquivo. Ia parar na busca, que respondia "nao encontrei essa
# informacao" - sobre um arquivo que esta ali, com esse nome.
VERBOS_ABRIR = ("abra", "abrir", "abre", "mostre", "mostrar", "mostra",
                "exiba", "exibir", "ver", "veja")

# Palavras que dizem o TIPO da coisa e nao aparecem no nome do arquivo. "o
# contrato Wanderson" nomeia um arquivo chamado "COMPRA E VENDA - WANDERSON".
GENERICAS = {"contrato", "documento", "arquivo", "pdf", "docx", "papel",
             "peca", "minuta"}

# A busca é feita sem acento, porque é assim que se digita com pressa. Mas o
# que aparece na tela leva o acento: "li isso de reuniao" tem cara de erro.
COM_ACENTO = {
    "reuniao": "reunião", "audiencia": "audiência", "sessao": "sessão",
    "pericia": "perícia", "videoconferencia": "videoconferência",
    "no calendario": "no calendário", "pendencia": "pendência",
}

# Perguntas sobre o próprio programa. Procurar "o que você sabe fazer" dentro
# dos contratos do escritório é o mesmo erro, de outro jeito.
SOBRE = (
    "o que voce faz", "o que voce sabe fazer", "o que voce consegue",
    "voce consegue", "voce sabe fazer", "quais suas funcoes", "o que da para fazer",
    "como funciona", "o que voce e", "quem e voce", "me ajuda com o que",
    "no que voce ajuda", "para que voce serve", "suas habilidades",
    "o que este programa faz", "o que o paulus faz",
)

DIAS_SEMANA = {
    "segunda": 0, "segunda-feira": 0, "terca": 1, "terca-feira": 1,
    "quarta": 2, "quarta-feira": 2, "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4, "sabado": 5, "domingo": 6,
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}


def _plano(texto: str) -> str:
    """Sem acento e em minúscula: é como a pessoa digita, com pressa."""
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------------ datas

RE_DATA_BARRA = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b")
RE_DIA_MES = re.compile(r"\bdia\s+(\d{1,2})\s+de\s+([a-z]+)\b")
RE_DE_MES = re.compile(r"\b(\d{1,2})\s+de\s+([a-z]+)\b")
RE_SO_DIA = re.compile(r"\bdia\s+(\d{1,2})\b")

# "às 13:40", "as 13h40", "13h", "14 horas". O "às" some quando se digita
# rápido, então não pode ser obrigatório.
RE_HORA = re.compile(
    r"\b(?:as|às|a)?\s*(\d{1,2})\s*(?::|h|hs|horas?)\s*(\d{2})?\b(?!\s*(?:dias?|minutos?|meses))"
)

# "com lembrete 10 minutos antes", "avisar 1 hora antes", "me lembre 30 min antes"
RE_AVISO = re.compile(
    r"(?:lembrete|lembrar|lembre|avisar|aviso|avise|alerta)\D{0,24}?"
    r"(\d{1,3})\s*(min|minutos?|h|horas?|dias?)\s*antes"
)


def _ano_provavel(dia: int, mes: int, hoje: date) -> int:
    """
    Sem ano escrito, o ano é o que faz a data não ser passado.

    Quem digita "dia 3 de janeiro" em dezembro quer o janeiro que vem, não o
    que passou. Marcar no passado é o erro mais irritante de uma agenda.
    """
    try:
        neste_ano = date(hoje.year, mes, dia)
    except ValueError:
        return hoje.year
    return hoje.year if neste_ano >= hoje else hoje.year + 1


def ler_data(texto: str, hoje: date | None = None) -> tuple[str, str]:
    """
    A data que a frase contém, em ISO — e o trecho que a produziu.

    Devolve ("", "") quando não há data. Não inventar é a regra: "marque uma
    reunião com o cliente" sem data nenhuma não vira uma reunião hoje.
    """
    hoje = hoje or date.today()
    plano = _plano(texto)

    # "depois de amanhã" vem antes de "amanhã": a segunda regra casaria dentro
    # da primeira e devolveria o dia errado.
    if re.search(r"\bdepois de amanha\b", plano):
        return (hoje + timedelta(days=2)).isoformat(), "depois de amanhã"
    if re.search(r"\bhoje\b", plano):
        return hoje.isoformat(), "hoje"
    if re.search(r"\bamanha\b", plano):
        return (hoje + timedelta(days=1)).isoformat(), "amanhã"

    achado = RE_DATA_BARRA.search(plano)
    if achado:
        dia, mes = int(achado.group(1)), int(achado.group(2))
        bruto = achado.group(3)
        if bruto:
            ano = int(bruto)
            ano += 2000 if ano < 100 else 0
        else:
            ano = _ano_provavel(dia, mes, hoje)
        try:
            return date(ano, mes, dia).isoformat(), achado.group(0)
        except ValueError:
            return "", ""

    for padrao in (RE_DIA_MES, RE_DE_MES):
        achado = padrao.search(plano)
        if achado and achado.group(2) in MESES:
            dia, mes = int(achado.group(1)), MESES[achado.group(2)]
            try:
                return date(_ano_provavel(dia, mes, hoje), mes, dia).isoformat(), achado.group(0)
            except ValueError:
                return "", ""

    # "na segunda", "sexta-feira": o próximo dia com esse nome, nunca hoje —
    # quem diz "na segunda" numa segunda quer a semana que vem.
    for nome, indice in DIAS_SEMANA.items():
        if re.search(r"\b" + nome + r"\b", plano):
            adiante = (indice - hoje.weekday()) % 7 or 7
            return (hoje + timedelta(days=adiante)).isoformat(), nome

    achado = RE_SO_DIA.search(plano)
    if achado:
        dia = int(achado.group(1))
        mes, ano = hoje.month, hoje.year
        if dia < hoje.day:
            mes, ano = (1, ano + 1) if mes == 12 else (mes + 1, ano)
        try:
            return date(ano, mes, dia).isoformat(), achado.group(0)
        except ValueError:
            return "", ""

    return "", ""


def ler_hora(texto: str) -> str:
    """A hora que a frase contém, em HH:MM. Sem hora, devolve ""."""
    plano = _plano(texto)
    # Tirar a data antes: "11/09/2026" tem "09" que parece hora.
    plano = RE_DATA_BARRA.sub(" ", plano)
    achado = RE_HORA.search(plano)
    if not achado:
        return ""
    hora = int(achado.group(1))
    minuto = int(achado.group(2) or 0)
    if hora > 23 or minuto > 59:
        return ""
    return f"{hora:02d}:{minuto:02d}"


def ler_aviso(texto: str) -> int:
    """Quantos minutos antes avisar. Zero quando a frase não pede aviso."""
    achado = RE_AVISO.search(_plano(texto))
    if not achado:
        return 0
    quanto, unidade = int(achado.group(1)), achado.group(2)
    if unidade.startswith("h"):
        return quanto * 60
    if unidade.startswith("d"):
        return quanto * 1440
    return quanto


# --------------------------------------------------------------- intenção


@dataclass
class Intencao:
    """O que a frase pede, com os campos já lidos."""

    tipo: str                       # agenda | tarefa | sobre | documentos
    titulo: str = ""
    campos: dict = field(default_factory=dict)
    resumo: str = ""
    porque: str = ""                # o que na frase levou a esta leitura
    falta: str = ""                 # o que impede de fazer, quando impede


def _porque(verbo: str, coisa: str) -> str:
    """A explicação que vai para a tela, com os acentos de volta."""
    return f"“{COM_ACENTO.get(verbo, verbo)}” e “{COM_ACENTO.get(coisa, coisa)}”"


def _tem(plano: str, palavras) -> str:
    """
    A palavra inteira, nunca um pedaço de outra.

    Por substring, "tem alguma reunião **marcada** nos documentos?" virava um
    pedido para marcar reunião — "marcada" contém "marca". É o erro caro deste
    módulo: mexer na agenda de alguém por causa de uma pergunta.
    """
    for p in palavras:
        if re.search(r"\b" + re.escape(p) + r"\b", plano):
            return p
    return ""


# O que pode vir antes do comando sem deixar de ser comando: gentileza e
# muleta de fala.
ENFEITE = {
    "por", "favor", "pfv", "pls", "pode", "podes", "poderia", "me", "voce",
    "vc", "que", "preciso", "quero", "gostaria", "de", "e", "ai", "entao",
    "so", "ja", "hoje", "olha", "escuta", "faz", "favorzinho",
}


def _verbo_de_comando(plano: str) -> str:
    """
    O verbo de ação, e só quando está no começo da frase.

    "o contrato **marca** reunião de diretoria?" e "a procuração **registra**
    algum compromisso?" têm o verbo, mas na terceira pessoa e depois do
    sujeito — são perguntas sobre o documento, não ordens. Num comando o verbo
    vem na frente; o que pode preceder é gentileza ("por favor anote") ou
    muleta ("aí, marca uma reunião").
    """
    palavras = re.findall(r"[a-z0-9]+", plano)
    for posicao, palavra in enumerate(palavras[:6]):
        if palavra in VERBOS_AGENDA:
            if all(anterior in ENFEITE for anterior in palavras[:posicao]):
                return palavra
            return ""
    # "por na agenda" é o único de duas palavras da lista.
    if plano.startswith("por na agenda"):
        return "por na agenda"
    return ""


def _titulo_do_pedido(texto: str, data_bruta: str) -> str:
    """
    O texto vira título, tirando o que era comando e o que era data.

    "Anote uma reunião no calendário 11/09 às 13:40 com lembrete 10 min antes"
    tem que virar "Reunião" — o resto já está nos campos, e repetir a frase
    inteira no título da agenda deixa a grade ilegível.
    """
    limpo = texto.strip().rstrip("?!")
    limpo = re.sub(r"(?i)\b(por favor|pfv|pls)\b", " ", limpo)

    # A gentileza e a muleta de fala que abrem o pedido — "pode", "aí", "me" —
    # não fazem parte do assunto. Saem por onde entraram: pela frente.
    for _ in range(4):
        antes = limpo
        limpo = re.sub(r"(?i)^\s*(" + "|".join(sorted(ENFEITE, key=len, reverse=True)) +
                       r"|a[ií])\b[\s,]*", " ", limpo).lstrip()
        if limpo == antes:
            break

    limpo = re.sub(r"(?i)^\s*(" + "|".join(VERBOS_AGENDA) + r")\b", " ", limpo)
    # "pode marcar": o verbo de comando pode vir no infinitivo depois do "pode".
    limpo = re.sub(r"(?i)^\s*(anotar|marcar|agendar|colocar|adicionar|criar|registrar)\b",
                   " ", limpo)
    limpo = re.sub(r"(?i)^\s*\b(a[ií])\b[\s,]*", " ", limpo)
    # "na agenda", "no calendário", "nas tarefas" dizem ONDE guardar, e não o
    # que a coisa é. No título, viram ruído.
    limpo = re.sub(r"(?i)\b(um|uma|o|a|no|na|nos|nas|em|para|pra)\s+(o\s+|a\s+)?"
                   r"(calendario|calendário|agenda|lista de tarefas|lista|tarefas)\b",
                   " ", limpo)
    limpo = re.sub(r"(?i)^\s*[:,-]+\s*", " ", limpo)

    if data_bruta:
        limpo = re.sub(re.escape(data_bruta), " ", limpo, flags=re.IGNORECASE)
    # O "com" de "com lembrete 10 minutos antes" fica órfão quando o aviso sai.
    limpo = re.sub(r"(?i)\b(com|e)\s+(?=lembrete|lembrar|avisar|aviso|alerta)", " ", limpo)
    limpo = RE_AVISO.sub(" ", limpo)
    limpo = RE_HORA.sub(" ", limpo)

    # "crie uma tarefa para revisar o contrato" tem por título "revisar o
    # contrato": "tarefa" é o tipo da coisa, não o assunto dela.
    limpo = re.sub(r"(?i)^\s*(um|uma|o|a)?\s*(tarefa|lembrete|pendencia|pendência|prazo)"
                   r"\s*(para|de|:)?\s*", " ", limpo)

    # Só o espaço colapsa. Colapsar ponto também transformava "Dr. Silva" em
    # "Dr Silva" — abreviação não é pontuação sobrando.
    limpo = re.sub(r"\s+", " ", limpo).strip(" ,;:-")
    limpo = re.sub(r"[\s.]+$", "", limpo)
    limpo = re.sub(r"(?i)^(um|uma|o|a)\s+", "", limpo)
    # Preposição solta no fim é sobra do que saiu: "Reunião com" era "Reunião
    # com lembrete 10 minutos antes".
    for _ in range(3):
        limpo = re.sub(r"(?i)\s+\b(com|de|da|do|em|na|no|para|pra|as|às|a|e|que|dia|até)\s*$",
                       "", limpo).strip(" ,.;:-")
    if not limpo:
        return ""
    return limpo[0].upper() + limpo[1:]


def _documento_pedido(plano: str, documentos) -> str:
    """
    Qual documento do acervo a frase está nomeando.

    Só responde quando existe um arquivo com esse nome — e só um. Duas
    salvaguardas de propósito: "mostre a cláusula de multa" não nomeia
    arquivo nenhum e continua sendo pergunta; e "abra a procuração", com
    quatro procurações no acervo, é ambíguo demais para escolher sozinho.
    """
    palavras = [p for p in re.findall(r"[a-z0-9]{3,}", plano)
                if p not in ENFEITE and p not in VERBOS_ABRIR]
    if not palavras:
        return ""

    def casam(quais: list[str]) -> list[str]:
        # Todas as palavras têm que estar no nome do arquivo. Uma só bastaria
        # para "procuracao" casar com as quatro procurações.
        achados = []
        for doc in documentos or []:
            bruto = getattr(doc, "name", "") or (doc.get("nome", "") if isinstance(doc, dict) else "")
            nome = _plano(bruto)
            if nome and quais and all(p in nome for p in quais):
                achados.append(bruto)
        return achados

    exatos = casam(palavras)
    if len(exatos) == 1:
        return exatos[0]

    # Segunda tentativa sem as palavras de tipo: "mostre o contrato Wanderson"
    # nomeia um arquivo que não tem "contrato" no nome. A primeira passada vem
    # antes de propósito — "procuração Matheus" acha pelo conjunto inteiro, e
    # só por "matheus" acharia duas.
    sem_tipo = [p for p in palavras if p not in GENERICAS]
    if sem_tipo and sem_tipo != palavras:
        soltos = casam(sem_tipo)
        if len(soltos) == 1:
            return soltos[0]
    return ""


# Jeitos de dizer "aquele documento de que estávamos falando". Não nomeiam
# arquivo nenhum — quem sabe qual é a conversa.
ANAFORA = (
    "referido documento", "referido arquivo", "documento referido",
    "este documento", "esse documento", "deste documento", "desse documento",
    "neste documento", "nesse documento", "o documento acima", "mesmo documento",
    "este arquivo", "esse arquivo", "neste arquivo", "nesse arquivo",
    "o documento aqui", "o documento em questao", "documento citado",
)


def fala_do_documento_em_foco(texto: str) -> bool:
    """
    A frase fala de "o referido documento" sem dizer qual.

    Quem sabe qual é a conversa, e não a frase: sem isso, "Exiba o referido
    documento aqui" não nomeia arquivo nenhum, cai na busca e é respondida
    pelo acervo inteiro.
    """
    return any(a in _plano(texto) for a in ANAFORA)


def _nome_de(doc) -> str:
    """
    O nome do arquivo, venha ele como for.

    A lista de documentos chega de tres jeitos conforme quem chama: objeto
    Document, dicionario da tela, ou o nome puro. Aceitar so o primeiro fazia
    a funcao devolver vazio calada - e "vazio" aqui quer dizer "nenhum
    documento nomeado", que e uma resposta plausivel e errada.
    """
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        return doc.get("nome") or doc.get("name") or ""
    return getattr(doc, "name", "") or ""


# Pedir para varrer o acervo inteiro, com todas as letras. Enquanto ler tudo
# era o padrao, isso nao precisava existir; agora que o padrao e o documento em
# foco, e preciso ter como dizer "sai desse documento e olha o resto".
TODO_O_ACERVO = (
    "em todos os documentos", "em todos os contratos", "em todos os arquivos",
    "todos os documentos", "todos os contratos", "todos os arquivos",
    "em todo o acervo", "no acervo inteiro", "em todo acervo",
    "na biblioteca inteira", "em toda a biblioteca", "na biblioteca toda",
    "em qualquer documento", "em qualquer contrato", "em qualquer arquivo",
    "procure em tudo", "procura em tudo", "busque em tudo", "olhe em tudo",
    "em tudo que", "no acervo todo", "todos os meus documentos",
)


def quer_todo_o_acervo(texto: str) -> bool:
    """
    A frase pede, com todas as letras, para olhar o acervo inteiro.

    É a saída do foco. Sem ela, quem começou a conversa sobre um documento
    ficaria preso nele — e "compare com os outros contratos" nunca sairia
    daquele arquivo.
    """
    return any(p in _plano(texto) for p in TODO_O_ACERVO)


def escopo(texto: str, abertos=None, em_foco=None, pedidos=None,
           tudo: bool = False) -> tuple[list[str], list[str]]:
    """
    Sobre quais documentos é esta pergunta. Lista vazia = o acervo inteiro.

    Devolve dois: o que ler, e o que a frase referiu **explicitamente**. A
    diferença importa — só o explícito pode virar ação de abrir o arquivo.
    Com o foco herdado, "mostre o valor do adiantamento" abriria o PDF em vez
    de responder, porque "mostre" é verbo de abrir e havia documento em foco.

    A ordem é esta, e cada degrau tem um motivo:

    1. "em todos os documentos", com todas as letras — ou o botão que diz o
       mesmo. Sai do foco: a pessoa mandou olhar o resto.
    2. O que a tela diz estar em foco (`pedidos`): as pílulas do compositor,
       postas pelo "/", por anexar um arquivo, ou por ter perguntado sobre ele.
       É o que a pessoa está VENDO, então ganha do palpite sobre o texto.
    3. O nome escrito na frase.
    4. "o referido documento", quando há um só em foco.
    5. O foco, sem mais nada. É o padrão: quem abriu uma conversa sobre um
       documento continua nele até dizer o contrário.
    6. Nada: o acervo inteiro.

    A regra 5 só é honesta porque a tela mostra as pílulas o tempo todo.
    Escopo silencioso seria tão ruim quanto ler tudo calado: a pessoa leria
    "não achei" sem saber que a busca não saiu de um arquivo.
    """
    if tudo or quer_todo_o_acervo(texto):
        return [], []

    nomes = {n for n in (_nome_de(d) for d in abertos or []) if n}
    em_foco = [n for n in (em_foco or []) if n in nomes]

    pelo_nome = documento_citado(texto, abertos)
    por_anafora = ""
    if not pelo_nome and len(em_foco) == 1 and fala_do_documento_em_foco(texto):
        por_anafora = em_foco[0]
    explicito = [n for n in (pelo_nome or por_anafora,) if n]

    escolhidos = explicito
    if not escolhidos:
        escolhidos = [n for n in (pedidos or []) if n in nomes]
    if not escolhidos:
        escolhidos = em_foco
    return escolhidos, explicito


def quer_abrir(texto: str) -> bool:
    """A frase começa com um verbo de abrir — "exiba", "mostre", "abra"."""
    palavras = re.findall(r"[a-z0-9]+", _plano(texto))
    for posicao, palavra in enumerate(palavras[:4]):
        if palavra in VERBOS_ABRIR:
            return all(anterior in ENFEITE for anterior in palavras[:posicao])
    return False


def documento_citado(texto: str, documentos=None) -> str:
    """
    Qual documento do acervo esta frase MENCIONA. Vazio quando nenhum ou vários.

    É outra pergunta que `ler` não faz: `ler` decide o que fazer com a frase,
    esta decide sobre o quê. Perguntar nomeando um documento e ler os nove
    fazia o documento citado virar 3,4% do contexto - medido - e a resposta
    saía sobre os outros 96,6%.

    Conservadora de propósito: na dúvida devolve vazio e a busca segue como
    antes. Estreitar a leitura para o documento errado é pior do que não
    estreitar.
    """
    plano = _plano(texto)
    if not plano:
        return ""

    nomes = [n for n in (_nome_de(d) for d in documentos or []) if n]

    # Primeira passada: o nome do arquivo aparece inteiro na frase. É o caso
    # do "Sobre “X”:" que a tela escreve, e não tem como dar falso positivo.
    inteiros = [n for n in nomes if _plano(Path(n).stem) in plano]
    if inteiros:
        # Com "contrato.pdf" e "contrato (1).pdf", os dois casam: fica o mais
        # específico, que é o nome mais longo.
        maior = max(len(Path(n).stem) for n in inteiros)
        finalistas = [n for n in inteiros if len(Path(n).stem) == maior]
        if len(finalistas) == 1:
            return finalistas[0]
        return ""

    # Segunda: todas as palavras próprias do nome aparecem na frase. Pega
    # "qual o valor da viagem 000434?" sem pegar "quanto custou a viagem?".
    achados = []
    for nome in nomes:
        proprias = [p for p in re.findall(r"[a-z0-9]{3,}", _plano(Path(nome).stem))
                    if p not in GENERICAS and p not in ENFEITE]
        if proprias and all(p in plano for p in proprias):
            achados.append(nome)
    return achados[0] if len(achados) == 1 else ""


def ler(texto: str, hoje: date | None = None, documentos=None) -> Intencao:
    """
    O que a frase pede.

    Devolve sempre alguma coisa: quando nada é reconhecido, o tipo é
    "documentos" e a conversa segue pelo caminho de antes.
    """
    texto = (texto or "").strip()
    plano = _plano(texto)
    if not plano:
        return Intencao(tipo="documentos")

    if any(p in plano for p in SOBRE):
        return Intencao(tipo="sobre", porque="pergunta sobre o próprio programa")

    # Abrir um arquivo pelo nome. Só vira ação quando o arquivo existe: sem
    # isso, "mostre o que diz sobre multa" viraria tentativa de abrir nada.
    palavras = re.findall(r"[a-z0-9]+", plano)
    if palavras and palavras[0] in VERBOS_ABRIR:
        qual = _documento_pedido(plano, documentos)
        if qual:
            return Intencao(
                tipo="abrir", titulo=qual,
                campos={"nome": qual},
                porque=f"“{palavras[0]}” e um documento com esse nome no acervo",
            )

    verbo = _verbo_de_comando(plano)
    coisa_agenda = _tem(plano, COISAS_AGENDA)
    coisa_tarefa = _tem(plano, COISAS_TAREFA)
    coisa_prazo = _tem(plano, COISAS_PRAZO)

    if not verbo or not (coisa_agenda or coisa_tarefa or coisa_prazo):
        return Intencao(tipo="documentos")

    data, bruto = ler_data(texto, hoje)
    hora = ler_hora(texto)
    aviso = ler_aviso(texto)
    titulo = _titulo_do_pedido(texto, bruto)

    if coisa_agenda:
        # Compromisso sem data não é compromisso. Em vez de marcar hoje por
        # conta própria, o pedido diz o que falta.
        if not data:
            return Intencao(
                tipo="agenda", titulo=titulo,
                campos={"titulo": titulo, "hora": hora, "avisar_min": aviso},
                porque=_porque(verbo, coisa_agenda),
                falta="não achei a data nessa frase",
            )
        return Intencao(
            tipo="agenda",
            titulo=titulo,
            campos={
                "titulo": titulo or "Compromisso",
                "tipo": "compromisso",
                "data": data,
                "hora": hora or "09:00",
                "duracao": 60,
                "avisar_min": aviso,
            },
            porque=_porque(verbo, coisa_agenda),
        )

    # Tarefa e prazo: data é opcional — tarefa sem prazo é tarefa.
    alvo = "prazo_interno" if coisa_prazo else "tarefa"
    return Intencao(
        tipo="tarefa",
        titulo=titulo,
        campos={
            "titulo": titulo or "Tarefa",
            "prazo": data,
            "lembrar_em": f"{data} {hora}" if data and hora else "",
            "importante": bool(coisa_prazo),
        },
        porque=_porque(verbo, coisa_tarefa or coisa_prazo),
        resumo=alvo,
    )
