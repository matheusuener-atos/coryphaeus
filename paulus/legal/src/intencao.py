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

# "abra a procuracao ABC" nao e pergunta sobre o conteudo: e pedido para
# abrir um arquivo. Ia parar na busca, que respondia "nao encontrei essa
# informacao" - sobre um arquivo que esta ali, com esse nome.
VERBOS_ABRIR = ("abra", "abrir", "abre", "mostre", "mostrar", "mostra",
                "exiba", "exibir", "ver", "veja", "reexiba", "reexibir", "reexibe",
                "reabra", "reabrir", "reabre")

# Palavras que dizem o TIPO da coisa e nao aparecem no nome do arquivo. "o
# contrato XYZ" nomeia um arquivo chamado "COMPRA E VENDA - XYZ".
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

    tipo: str                       # agenda | tarefa | sobre | abrir | servico | cadastro | nota | documentos
    titulo: str = ""
    campos: dict = field(default_factory=dict)
    resumo: str = ""
    porque: str = ""                # o que na frase levou a esta leitura
    falta: str = ""                 # o que impede de fazer, quando impede
    # A ação é certa, mas um campo obrigatório não saiu por regra e a frase
    # tem com o que preencher: vale chamar o modelo para completar.
    precisa_modelo: bool = False


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


# "abra um serviço para a Cooperativa: renovação do contrato" - a pasta de
# trabalho de Serviços nasce da conversa (docs/ui, A15). "Abra" é o mesmo
# verbo de abrir arquivo; o que decide é a palavra "serviço", que nenhum
# arquivo tem no nome.
VERBOS_SERVICO = ("abra", "abrir", "abre", "crie", "criar", "cria", "monte", "montar",
                  "monta", "inicie", "iniciar", "inicia", "comece", "comecar", "comeca",
                  "registre", "registrar", "registra", "cadastre", "cadastrar", "cadastra")
COISAS_SERVICO = ("servico", "pasta de trabalho", "novo caso", "nova pasta")
RE_PEDIDO_SERVICO = re.compile(
    r"\b(" + "|".join(VERBOS_SERVICO) + r")\b"
    r"(?:\s+(?:um|uma|o|a|novo|nova|outro|outra|mais|esse|essa|este|esta|ai|aqui|la|pra mim|para mim))*"
    r"\s+(servico|pasta de trabalho|novo caso|nova pasta)\b")
RE_COISA_SERVICO = re.compile(r"(servi[çc]o|pasta de trabalho|novo caso|nova pasta)\s*(?:novo|nova)?\s*(.*)$", re.I | re.S)
CONECTORES = ("para o cliente", "para a cliente", "do cliente", "da cliente", "chamado", "chamada",
              "para", "com", "de", "do", "da", "o", "a", "um", "uma")
# No fim do nome só caem preposições: "Fornecedor A" termina em "A" e é nome.
CONECTORES_NO_FIM = ("para o cliente", "para a cliente", "do cliente", "da cliente",
                     "chamado", "chamada", "para", "com", "de", "do", "da")


def _cliente_citado(plano: str, cadastros) -> str:
    """O cadastro cujo nome inteiro aparece na frase - o mais longo, se mais de um."""
    melhor = ""
    for nome in cadastros or []:
        n = _plano(str(nome)).strip()
        if len(n) >= 3 and re.search(r"\b" + re.escape(n) + r"\b", plano) and len(n) > len(melhor):
            melhor = str(nome)
    return melhor


def _sem_conectores(texto: str) -> str:
    """Tira "para", "de", "chamado"... do começo e do fim do que sobrou como nome."""
    t = texto.strip(" .:;,-–—")
    mudou = True
    while mudou and t:
        mudou = False
        for c in CONECTORES:
            if re.match(r"^" + re.escape(c) + r"\b", t, re.I):
                t = t[len(c):].strip(" .:;,-–—")
                mudou = True
            if c in CONECTORES_NO_FIM and re.search(r"\b" + re.escape(c) + r"$", t, re.I):
                t = t[: len(t) - len(c)].strip(" .:;,-–—")
                mudou = True
    return t


def _sem_conectores_no_fim(texto: str) -> str:
    """Tira do fim tudo que só liga ao que vinha depois - inclusive artigos."""
    t = texto.strip(" .:;,-–—")
    mudou = True
    while mudou and t:
        mudou = False
        for c in CONECTORES:
            if re.search(r"(?:^|\s)" + re.escape(c) + r"$", t, re.I):
                t = t[: len(t) - len(c)].strip(" .:;,-–—")
                mudou = True
    return t


def ler_servico(texto: str, plano: str, cadastros=None) -> Intencao | None:
    """
    "abra um serviço para X: Y" vira a proposta de uma pasta de trabalho.

    O nome é o que vem depois de "serviço", sem o cliente (quando a frase cita
    um cadastro) e sem os conectores; o que vem depois de ":" ou "sobre" é a
    descrição. Sem nome nenhum, a proposta diz o que falta.
    """
    # "serviço" tem de ser a coisa pedida, logo depois do verbo: "abra um
    # serviço", "crie serviço", "monte uma nova pasta de trabalho". Em "abra o
    # contrato de serviço" a coisa é o contrato, e o arquivo é que abre.
    m_pedido = RE_PEDIDO_SERVICO.search(plano)
    if not m_pedido:
        return None
    antes = re.findall(r"[a-z0-9]+", plano[: m_pedido.start()])
    if not all(palavra in ENFEITE for palavra in antes):
        return None
    verbo, coisa = m_pedido.group(1), m_pedido.group(2)
    cliente = _cliente_citado(plano, cadastros)
    m = RE_COISA_SERVICO.search(texto)
    resto = m.group(2).strip() if m else ""
    descricao = ""
    if ":" in resto:
        resto, descricao = resto.split(":", 1)
    elif re.search(r"\bsobre\b", resto, re.I):
        resto, descricao = re.split(r"\bsobre\b", resto, maxsplit=1, flags=re.I)
    nome = resto
    if cliente:
        onde = _plano(nome).find(_plano(cliente))
        if onde >= 0:
            # O que colava no cliente ("com a", "para o cliente") cai junto.
            antes_do_cliente = _sem_conectores_no_fim(nome[:onde])
            depois_do_cliente = _sem_conectores(nome[onde + len(cliente):])
            nome = antes_do_cliente + " " + depois_do_cliente
    nome = " ".join(_sem_conectores(nome).split())
    descricao = " ".join(descricao.split()).strip(" .")
    if not nome and descricao:
        nome, descricao = _sem_conectores(descricao)[:80], ""
    if nome:
        nome = nome[0].upper() + nome[1:]
    return Intencao(
        tipo="servico", titulo=nome or (cliente or ""),
        campos={"nome": nome, "cliente": cliente, "descricao": descricao},
        porque=_porque(verbo, coisa),
        falta="" if nome else "não achei o nome do serviço nessa frase",
    )


# "cadastre o cliente João Souza, CPF 123..." e "emita uma NFS-e para a
# Cooperativa de R$ 1.500": as ferramentas de ferramentas.py. A regra acha a
# ação e tira dela o que é inequívoco — CPF, e-mail, telefone, valor, data.
# Quando a ação é certa mas um campo obrigatório não sai por regra, a leitura
# marca `precisa_modelo`, e o modelo é chamado só para completar.
VERBOS_CADASTRO = ("cadastre", "cadastrar", "cadastra", "registre", "registrar", "registra",
                   "adicione", "adicionar", "adiciona", "inclua", "incluir", "inclui",
                   "crie", "criar", "cria", "salve", "salvar", "salva")
RE_PEDIDO_CADASTRO = re.compile(
    r"\b(" + "|".join(VERBOS_CADASTRO) + r")\b"
    r"(?:\s+(?:um|uma|o|a|novo|nova|outro|outra|mais|esse|essa|este|esta|ai|aqui|pra mim|para mim|como))*"
    r"\s+(cliente|cadastro|contato|ficha)\b(?:\s+(?:novo|nova)\b)?")
# "cadastre o João Souza": o verbo sozinho já diz a coisa.
RE_SO_CADASTRE = re.compile(r"\b(cadastre|cadastrar|cadastra)\b")
RE_NOVO_CLIENTE = re.compile(r"^\s*(?:(?:um|uma)\s+)?(novo|nova)\s+(cliente|cadastro|contato)\b")

RE_CNPJ = re.compile(r"(?<![\d/])\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?![\d/])")
RE_CPF = re.compile(r"(?<![\d/])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d/])")
RE_TELEFONE = re.compile(r"(?<![\d/.-])(?:\+?55\s*)?\(?\d{2}\)?\s*9?\s?\d{4}[-\s.]?\d{4}(?![\d/-])")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_ROTULO = re.compile(
    r"(?i)\b(?:com\s+(?:o\s+|a\s+)?)?(?:cpf|cnpj|documento|doc|telefone|tel|fone|celular|cel|"
    r"whatsapp|whats|zap|e-?mail)\b\s*(?:n[ºo°.]\s*|n[uú]mero\s*|:\s*|é\s*|e\s+)?$")
RE_CORTA_NOME = re.compile(
    r"(?i)[,;|:\n\d]|\s[-–—]\s|\b(?:com\s+(?:o\s+|a\s+)?)?(?:cpf|cnpj|documento|telefone|tel|fone|celular|"
    r"whatsapp|whats|e-?mail|endere[cç]o|mora|morador|residente|que|para|pra|no|na|nos|nas)\b")
RE_ENDERECO = re.compile(
    r"(?i)\b(?:endere[cç]o|residente(?:\s+e\s+domiciliad[oa])?(?:\s+(?:na|no|em))?|mora(?:dor[a]?)?\s+(?:na|no|em))"
    r"\s*:?\s*(.+?)\s*(?=[;|]|(?:[,.]\s*|\s+e\s+|\s+com\s+)(?:cpf|cnpj|tel|telefone|fone|celular|whats\w*|e-?mail)\b|$)")
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}
PALAVRAS_NUMERO = ("mil", "cem", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos")


def _nfc(texto: str) -> str:
    """Letra acentuada num caractere só: é o que mantém texto e plano do mesmo tamanho."""
    return unicodedata.normalize("NFC", texto or "")


def _nome_proprio(nome: str) -> str:
    """ "joão da silva" -> "João da Silva". Quem digitou com maiúscula fica como digitou."""
    nome = " ".join(nome.split()).strip(" .,;:-–—")
    if not nome or nome != nome.lower():
        return nome
    return " ".join(p if p in PARTICULAS and i else p[:1].upper() + p[1:]
                    for i, p in enumerate(nome.split()))


def _nome_valido(nome: str) -> bool:
    palavras = nome.split()
    return (bool(re.search(r"[A-Za-zÀ-ÿ]{2}", nome)) and len(palavras) <= 10 and len(nome) <= 90
            and _plano(palavras[0]) not in ENFEITE | {"o", "a", "um", "uma", "cliente", "cadastro"})


def ler_cadastro(texto: str, plano: str) -> Intencao | None:
    """
    "cadastre o cliente João Souza, CPF 529.982.247-25, joao@x.com" vira a
    proposta de uma ficha em Cadastros.

    CPF/CNPJ, e-mail e telefone saem por padrão — números e arroba não são
    ambíguos. O nome é o que vem depois do pedido até a primeira vírgula ou
    rótulo. Sem nome, a proposta diz o que falta; e, se sobrou texto que a
    regra não soube ler, pede ajuda ao modelo.
    """
    texto = _nfc(texto)
    m = RE_PEDIDO_CADASTRO.search(plano) or RE_NOVO_CLIENTE.search(plano)
    so_verbo = False
    if not m:
        m = RE_SO_CADASTRE.search(plano)
        so_verbo = True
    if not m:
        return None
    antes = re.findall(r"[a-z0-9]+", plano[: m.start()])
    if not all(palavra in ENFEITE for palavra in antes):
        return None
    # "cadastre uma reunião", "crie o cadastro do serviço": outra coisa.
    if _tem(plano, COISAS_AGENDA + COISAS_TAREFA + COISAS_PRAZO) or re.search(r"\bservicos?\b", plano):
        return None
    if so_verbo and re.search(r"\b(documento|arquivo|nota|lancamento|processo|prazo)\b", plano):
        return None

    verbo = m.group(1)
    coisa = "cliente" if so_verbo else m.group(2)
    campos = {"nome": "", "documento": "", "telefone": "", "email": "", "endereco": "", "observacao": ""}
    problema = ""

    # Tira as peças inequívocas do texto, deixando uma marca "|" no lugar:
    # a marca corta o nome, e o rótulo que vinha antes ("CPF", "tel") sai junto.
    marcado = texto
    for chave, padrao in (("email", RE_EMAIL), ("documento", RE_CNPJ), ("documento", RE_CPF),
                          ("telefone", RE_TELEFONE)):
        achado = padrao.search(marcado)
        if not achado or campos[chave]:
            continue
        bruto = achado.group(0).strip()
        try:
            import ferramentas

            campos[chave] = {"email": ferramentas.email, "documento": ferramentas.cpf_ou_cnpj,
                             "telefone": ferramentas.telefone}[chave](bruto)
        except ValueError as exc:
            campos[chave] = bruto
            problema = problema or str(exc)
        inicio = achado.start()
        rotulo = RE_ROTULO.search(marcado[:inicio])
        if rotulo:
            inicio = rotulo.start()
        marcado = marcado[:inicio] + " | " + marcado[achado.end():]

    endereco = RE_ENDERECO.search(marcado)
    if endereco:
        campos["endereco"] = " ".join(endereco.group(1).split()).strip(" .,;")
        marcado = marcado[: endereco.start()] + " | " + marcado[endereco.end():]

    # O nome: depois do pedido, até o primeiro corte.
    m_texto = (RE_PEDIDO_CADASTRO if not so_verbo else RE_SO_CADASTRE).search(_plano(marcado)) \
        or RE_NOVO_CLIENTE.search(_plano(marcado))
    resto = marcado[m_texto.end():] if m_texto else ""
    resto = re.sub(r"(?i)^[\s:,-]*(?:(?:um|uma|o|a)\s+)?(?:(?:novo|nova)\s+)?"
                   r"(?:(?:cliente|cadastro|contato|ficha)\s+)?(?:(?:novo|nova)\s+)?"
                   r"(?:(?:chamad[oa]|de nome|com o nome de|com nome|que se chama)\s+)?[:\s]*", "", resto)
    corte = RE_CORTA_NOME.search(resto)
    nome = _sem_conectores_no_fim(resto[: corte.start()] if corte else resto)
    nome = _nome_proprio(nome)
    if not _nome_valido(nome):
        nome = ""
    campos["nome"] = nome

    sobra = re.sub(r"[|,;:.\s]+", " ", _plano(resto)).strip()
    falta = "" if nome else "não achei o nome do cliente nessa frase"
    return Intencao(
        tipo="cadastro", titulo=nome, campos=campos,
        porque=_porque(verbo, coisa),
        falta=falta or problema,
        precisa_modelo=not nome and bool(re.search(r"[a-z]{3,}", sobra)),
    )


VERBOS_NOTA = ("emita", "emitir", "emite", "gere", "gerar", "gera", "faca", "fazer", "faz",
               "tire", "tirar", "tira", "crie", "criar", "cria", "prepare", "preparar", "prepara")
RE_PEDIDO_NOTA = re.compile(
    r"\b(" + "|".join(VERBOS_NOTA) + r")\b"
    r"(?:\s+(?:um|uma|a|nova|outra|mais|essa|esta|ai|aqui|pra mim|para mim))*"
    r"\s+(nfs-?e|nf-?e|nota fiscal(?: de servicos?| eletronica)?|nota)\b")
# O que diz o valor sai inteiro — "no valor de", "de R$", "reais" —, para não
# sobrar "no reais" colado no nome do cliente.
RE_VALOR = re.compile(
    r"(?:\b(?:no\s+)?valor(?:\s+de)?\s*(?:r\$)?\s*|\b(?:de\s+)?r\$\s*|\bde\s+(?=\d[\d.,]*\s*(?:mil\s*)?(?:reais|real)\b))"
    r"(\d[\d.,]*(?:\s*mil\b)?)(?:\s*(?:reais|real)\b)?"
    r"|(\d[\d.,]*(?:\s*mil)?)\s*(?:reais|real)\b")
RE_DESCRICAO_NOTA = re.compile(
    r"(?i)\b(?:referente\s+(?:a|ao|aos|as|à|às)|pel[oa]s?|sobre)\s+(.+?)\s*"
    r"(?=[,;]|\bno valor\b|\bde\s+R\$|R\$|\bvalor\b|\bpara\b|\bpra\b|\.\s|\.?$)")
PARA_QUEM = re.compile(r"(?i)\b(?:para|pra|pro)\s+(?:(?:o|a)\s+)?(?:(?:cliente|tomador|tomadora)\s+)?")
CORTA_CLIENTE = re.compile(
    r"(?i)[,;:\d]|\.(?:\s|$)|R\$|\b(?:no valor|valor|de\s+R\$|referente|pel[oa]s?|sobre|por|hoje|amanh\w*|"
    r"dia|em|com|data|emitida|emitir|de\s+(?=\d))\b")
NAO_E_CLIENTE = {"o", "a", "dia", "hoje", "amanha", "mes", "semana", "referente", "valor", "mim"}


def ler_nota(texto: str, plano: str, cadastros=None, hoje: date | None = None) -> Intencao | None:
    """
    "emita uma NFS-e para a Cooperativa de R$ 1.500,00 referente à consultoria"
    vira a proposta de uma nota fiscal de serviço.

    "nota" sozinha só conta quando a frase tem valor em dinheiro: "crie uma
    nota sobre a reunião" é anotação, não nota fiscal. A emissão em si ainda
    não existe — a proposta confere os dados e diz isso.
    """
    texto = _nfc(texto)
    m = RE_PEDIDO_NOTA.search(plano)
    if not m:
        return None
    antes = re.findall(r"[a-z0-9]+", plano[: m.start()])
    if not all(palavra in ENFEITE for palavra in antes):
        return None

    import ferramentas

    centavos = 0
    sem_valor = texto
    achado = RE_VALOR.search(plano)
    if achado:
        bruto = next(g for g in achado.groups() if g).rstrip(".,")
        try:
            centavos = ferramentas.centavos_de(bruto)
        except ValueError:
            centavos = 0
        sem_valor = texto[: achado.start()] + " " + texto[achado.end():]
    if m.group(2) == "nota" and not achado:
        return None

    cliente = _cliente_citado(plano, cadastros)
    if not cliente:
        for para in PARA_QUEM.finditer(sem_valor):
            depois = sem_valor[para.end():]
            corte = CORTA_CLIENTE.search(depois)
            candidato = _sem_conectores_no_fim(depois[: corte.start()] if corte else depois)
            candidato = _nome_proprio(candidato)
            if candidato and _plano(candidato.split()[0]) not in NAO_E_CLIENTE and _nome_valido(candidato):
                cliente = candidato
                break

    descricao = ""
    d = RE_DESCRICAO_NOTA.search(sem_valor)
    if d:
        descricao = " ".join(d.group(1).split()).strip(" .")
    elif ":" in sem_valor:
        descricao = " ".join(sem_valor.split(":", 1)[1].split()).strip(" .")
    data, _ = ler_data(sem_valor, hoje)

    campos = {"cliente": cliente, "valor": centavos, "descricao": descricao, "data": data}
    falta = ferramentas.o_que_falta("emitir_nfse", campos)
    resto = _plano(sem_valor[m.end():] if len(sem_valor) >= m.end() else "")
    precisa = bool(
        (not cliente and re.search(r"\b(para|pra|pro)\s+\w{3,}", resto))
        or (not centavos and (re.search(r"\d", resto)
                              or any(re.search(r"\b" + p + r"\b", resto) for p in PALAVRAS_NUMERO))))
    return Intencao(
        tipo="nota", titulo=cliente or "NFS-e", campos=campos,
        porque=_porque(m.group(1), "nota fiscal" if m.group(2).startswith("nota") else "NFS-e"),
        falta=falta, precisa_modelo=precisa,
    )


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

    # Segunda tentativa sem as palavras de tipo: "mostre o contrato ABC"
    # nomeia um arquivo que não tem "contrato" no nome. A primeira passada vem
    # antes de propósito — "procuração XYZ" acha pelo conjunto inteiro, e
    # só por "xyz" acharia duas.
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
           tudo: bool = False, herdar_foco: bool = True) -> tuple[list[str], list[str]]:
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

    `herdar_foco=False` é a pessoa que tirou o anexo da caixa: a regra 5 não
    vale, porque ela acabou de dizer que não quer só aquele. Tirar o anexo
    também não é pedir o acervo inteiro — quem decide isso é a conversa,
    perguntando. "o documento" continua apontando o que estava em foco.

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
    if not pelo_nome and len(em_foco) == 1 and (fala_do_documento_em_foco(texto)
                                                 or pede_so_o_documento(texto)):
        por_anafora = em_foco[0]
    explicito = [n for n in (pelo_nome or por_anafora,) if n]

    escolhidos = explicito
    if not escolhidos:
        escolhidos = [n for n in (pedidos or []) if n in nomes]
    if not escolhidos and herdar_foco:
        escolhidos = em_foco
    return escolhidos, explicito


# O que pode acompanhar "abra" sem virar pergunta sobre o conteúdo: "abra o
# documento", "reexiba ele aqui", "mostre esse arquivo de novo pra mim".
SO_O_DOCUMENTO = {
    "o", "a", "os", "as", "um", "este", "esse", "esta", "essa", "estes", "esses", "aquele",
    "documento", "documentos", "arquivo", "arquivos", "anexo", "anexos", "ele", "ela", "eles",
    "elas", "isso", "isto", "pdf", "docx", "word", "de", "novo", "novamente", "outra", "vez",
    "aqui", "ai", "la", "pra", "para", "mim", "me", "no", "na", "chat", "conversa", "tela",
    "referido", "mesmo", "citado", "acima", "anexado", "anexados", "que", "eu", "anexei",
    "por", "favor", "agora", "entao", "so",
}


def pede_so_o_documento(texto: str) -> bool:
    """
    "Quero que você abra o documento", "reexiba o arquivo": o pedido é o
    arquivo, e não o que está escrito nele.

    Depois do verbo de abrir só pode vir referência ao documento. Com qualquer
    outra palavra — "mostre o VALOR do adiantamento", "exiba o CONTEÚDO aqui"
    — é pergunta, e segue para a leitura: é o "a não ser que seja pedido".
    """
    palavras = re.findall(r"[a-z0-9]+", _plano(texto))
    for posicao, palavra in enumerate(palavras[:6]):
        if palavra in VERBOS_ABRIR:
            if not all(anterior in ENFEITE for anterior in palavras[:posicao]):
                return False
            return all(p in SO_O_DOCUMENTO for p in palavras[posicao + 1:])
    return False


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


def ler(texto: str, hoje: date | None = None, documentos=None, cadastros=None) -> Intencao:
    """
    O que a frase pede.

    Devolve sempre alguma coisa: quando nada é reconhecido, o tipo é
    "documentos" e a conversa segue pelo caminho de antes. `cadastros` são
    os nomes das fichas, para "abra um serviço para a Cooperativa" ligar a
    pasta ao cliente certo.
    """
    texto = (texto or "").strip()
    plano = _plano(texto)
    if not plano:
        return Intencao(tipo="documentos")

    if any(p in plano for p in SOBRE):
        return Intencao(tipo="sobre", porque="pergunta sobre o próprio programa")

    # Antes de "abrir arquivo": "abra um serviço" tem o mesmo verbo.
    servico = ler_servico(texto, plano, cadastros)
    if servico:
        return servico

    cadastro = ler_cadastro(texto, plano)
    if cadastro:
        return cadastro

    nota = ler_nota(texto, plano, cadastros, hoje)
    if nota:
        return nota

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
            import ferramentas

            return Intencao(
                tipo="agenda", titulo=titulo,
                campos={"titulo": titulo, "hora": hora, "avisar_min": aviso},
                porque=_porque(verbo, coisa_agenda),
                falta="não achei a data nessa frase",
                # "na terça que vem", "daqui a duas semanas": a regra não lê,
                # e o modelo pode. Sem indício de data nenhum, nem pergunta.
                precisa_modelo=ferramentas.tem_indicio_de_data(texto),
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
