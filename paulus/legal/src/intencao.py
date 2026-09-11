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


def ler(texto: str, hoje: date | None = None) -> Intencao:
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
