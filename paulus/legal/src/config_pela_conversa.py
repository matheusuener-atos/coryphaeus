"""
As Configurações pela conversa (pacote de telas de 01/10/2026, T5: `Conversa -
Meus dados`, `- Assistente e modelo`, `- Modelos`, `- Desempenho`, `- Teste`,
`- Conexoes`, `- Word`, `- Acesso de fora`, `- Escritorio`, `- Backup`,
`- Biblioteca`, `- Aparencia`, `- Modulos`, `- Versao`, `- Lixeira`).

  "troquei de número, agora é (94) 99123-4567. e já liga o papel timbrado"
        -> Meus dados ao lado, com as duas mudanças marcadas "novo"
  "para de me avisar de pausa toda hora, e coloca o tema claro durante o dia"
        -> Aparência e avisos, com o bem-estar desligado e o tema no Windows
  "tira gravações e assinatura do menu, a gente não usa"
        -> Módulos, com os dois desligados

A frase vira, por regra, a seção e as mudanças propostas (`ler`). A
conversa diz o que muda, de quanto para quanto, e o que precisa de atenção
(`proposta`). NADA é gravado aqui: a coluna mostra a seção com as mudanças
marcadas, e só o clique em "Salvar alterações" grava, pelo caminho de sempre
de Configurações. Assinar sem revisar, enviar sem confirmar e mandar à nuvem
sem pedir nunca são ligados pela conversa - continuam pedindo o sim, e quem
quiser liga com a própria mão, ao lado.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

import campos_br

# id da seção (o de js/05-configuracoes.js) -> (título da coluna, linha curta)
SECOES = {
    "perfil": ("Meus dados", "ficam nesta máquina"),
    "assistente": ("Assistente e modelo", "tudo roda nesta máquina"),
    "modelos": ("Modelos", "o motor é o Ollama, aqui mesmo"),
    "desempenho": ("Desempenho", "o gráfico mostra o último minuto"),
    "conexoes": ("Conexões", "nada sai sem a sua aprovação"),
    "word": ("Word", "desligado de fábrica"),
    "acesso": ("Acesso externo", "desligado de fábrica"),
    "vinculos": ("Escritório e equipe", "a equipe entra por convite"),
    "backup": ("Backup", "arquivo cifrado, todo dia"),
    "aprendizado": ("Biblioteca", "nada sai desta máquina"),
    "aparencia": ("Aparência e avisos", "tema, avisos e atalhos"),
    "menu": ("Módulos", "desligar só tira do menu"),
    "plano": ("Versão", "atualização e novidades"),
    "lixeira": ("Lixeira", "30 dias para voltar"),
}

# As chaves de Limites da IA que a conversa nunca liga (o LEIA-ME do pacote:
# assinar, enviar e-mail e nuvem seguem pedindo o sim).
SENSIVEIS = {"assinar": "Assinar documentos sem revisar", "enviar_mensagem": "Enviar e-mail e mensagem sem confirmar",
             "modelo_nuvem": "Mandar à nuvem sem pedir a cada pergunta"}

AUTONOMIA_ROTULO = {
    "ler_pastas": "Ler as pastas incluídas", "organizar_mover": "Mover arquivos sem pedir",
    "agentes_sozinhos": "Agentes fazem sozinhos o que o AGENTE.md permite", **SENSIVEIS,
}
AUTONOMIA_COM_ISSO = {
    ("organizar_mover", True): "Com isso, o plano de organização é aplicado direto, sem esperar na fila de Aprovações. "
                               "Cada movimento continua no Histórico, com desfazer.",
    ("organizar_mover", False): "Com isso, cada plano de organização volta a esperar o seu sim na fila de Aprovações.",
    ("ler_pastas", True): "Com isso, as pastas que você incluiu são abertas e indexadas; nenhum arquivo é alterado.",
    ("ler_pastas", False): "Com isso, as pastas incluídas deixam de ser lidas até você ligar de novo.",
    ("agentes_sozinhos", True): "Com isso, cada agente faz sem perguntar só o que o AGENTE.md dele lista em “autonomia:”, "
                                "até 20 por dia, tudo no Histórico. E-mail, assinatura e pagamento continuam fora.",
    ("agentes_sozinhos", False): "Com isso, os agentes voltam a pedir o seu sim antes de cada ação.",
}

AVISOS_ROTULO = {"bem_estar": "Bem-estar e foco", "resposta": "Resposta pronta", "aprovacao": "Aprovação pendente",
                 "gravacao": "Transcrição pronta", "agenda": "Compromisso chegando", "acesso": "Acesso externo"}

MODULOS = [
    ("servicos", "Serviços", r"servicos?"), ("gravacoes", "Gravações", r"gravac(?:ao|oes)"),
    ("agenda", "Agenda", r"agenda"), ("acervo", "Acervo", r"acervo"), ("documentos", "Documentos", r"documentos"),
    ("assinatura", "Assinatura", r"assinaturas?"), ("email", "E-mail", r"e-?mails?"),
    ("financeiro", "Financeiro", r"financeiro"), ("cadastros", "Cadastros", r"cadastros"),
    ("aprovacoes", "Aprovações", r"aprovac(?:ao|oes)"), ("foco", "Foco e bem-estar", r"foco(?: e bem-estar)?|bem-estar"),
]

TEMAS = {"claro": "Claro", "escuro": "Escuro", "auto": "Seguir o Windows"}

TAREFAS = {"conversa": "Perguntas sobre documentos", "juiz": "Julgamentos rápidos", "email": "E-mail",
           "redacao": "Redação", "resumos": "Resumos", "leitura": "Leitura do Acervo"}

NUMEROS = {1: "a", 2: "as duas", 3: "as três", 4: "as quatro", 5: "as cinco"}


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _nfc(texto: str) -> str:
    return unicodedata.normalize("NFC", texto or "")


def _mudanca(chave: str, valor) -> dict:
    return {"chave": chave, "valor": valor}


# ================================================================ ler a frase

RE_TELEFONE = re.compile(r"\(?\b(\d{2})\)?\s*(9?\s?\d{4})[\s.-]?(\d{4})\b")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_EU = re.compile(r"\b(meu|minha|troquei|mudei|meus dados|agora (?:e|eh)|atualiza(?:r)? (?:o )?meu)\b")
RE_LIGA = r"(?:liga|ligar|ligue|ativa|ativar|ative|poe|por|ponha|coloca|colocar|coloque|bota|botar|usa|usar|use|quero|deixa)"
RE_DESLIGA = r"(?:desliga|desligar|desligue|desativa|desativar|tira|tirar|tire|remove|remover|para|parar|pare|chega|nao quero|esconde|esconder|some)"


def _telefone(texto: str) -> str:
    m = RE_TELEFONE.search(texto)
    if not m:
        return ""
    digitos = campos_br.so_digitos(m.group(0))
    return campos_br.mascara_telefone(digitos) if len(digitos) in (10, 11) else ""


def _ler_perfil(texto: str, plano: str) -> dict | None:
    mudancas = []
    eu = bool(RE_EU.search(plano))
    if eu and re.search(r"\b(telefone|numero|celular|whats\w*|zap)\b", plano):
        tel = _telefone(texto)
        if tel:
            mudancas.append(_mudanca("pessoa.telefone", tel))
    if eu and re.search(r"\b(meu|minha) (?:novo |nova )?e-?mail\b", plano):
        m = RE_EMAIL.search(texto)
        if m:
            mudancas.append(_mudanca("pessoa.email", m.group(0)))
    m = re.search(r"\bminha (?:inscricao (?:na )?)?oab\b\D{0,12}([a-z]{2})?\s*(\d[\d.]{2,8})", plano)
    if m:
        uf = (m.group(1) or "").upper()
        mudancas.append(_mudanca("pessoa.oab", ((uf + " ") if uf and uf not in ("E ", "EH") else "") + m.group(2).replace(".", "")))
    m = re.search(r"\bmeu cpf\b\D{0,10}(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", plano)
    if m:
        mudancas.append(_mudanca("pessoa.cpf", campos_br.mascara_cpf(m.group(1))))
    m = re.search(r"\bmeu endereco(?: profissional| do escritorio)?\s+(?:agora\s+)?(?:e|eh|fica|passou a ser|mudou para|:)\s*", plano)
    if m:
        resto = _nfc(texto)[m.end():].strip()
        resto = re.split(r"[.;]\s|\s+e\s+(?:liga|ativa|poe|coloca|ja)\b", resto)[0].strip(" .,;")
        if resto:
            mudancas.append(_mudanca("pessoa.endereco", resto))
    m = re.search(r"\b(?:o )?nome do (?:meu )?escritorio\s+(?:e|eh|fica|passa a ser|:)\s*", plano)
    if m:
        resto = re.split(r"[.;]\s|,\s", _nfc(texto)[m.end():].strip())[0].strip(" .,;\"“”")
        if resto:
            mudancas.append(_mudanca("escritorio.nome", resto))
    m = re.search(r"\bcnpj do (?:meu )?escritorio\b\D{0,10}(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", plano)
    if m:
        mudancas.append(_mudanca("escritorio.cnpj", campos_br.mascara_cnpj(m.group(1))))
    if re.search(r"\bpapel timbrado\b|\btimbre\b", plano):
        if re.search(r"\b" + RE_DESLIGA + r"\b[^.]{0,30}(papel timbrado|timbre)", plano):
            mudancas.append(_mudanca("timbre_no_pdf", False))
        elif re.search(r"\b" + RE_LIGA + r"\b[^.]{0,30}(papel timbrado|timbre)", plano):
            mudancas.append(_mudanca("timbre_no_pdf", True))
    if not mudancas:
        return None
    return {"secao": "perfil", "mudancas": mudancas}


def _ler_aparencia(texto: str, plano: str) -> dict | None:
    mudancas = []
    if re.search(r"\btema\b|\bmodo (claro|escuro|noturno)\b|\bfundo (claro|escuro)\b", plano):
        if re.search(r"\b(durante o dia|de dia|seguir o windows|igual ao windows|do windows|automatico)\b", plano):
            mudancas.append(_mudanca("tema", "auto"))
        elif re.search(r"\b(escuro|noturno|dark)\b", plano):
            mudancas.append(_mudanca("tema", "escuro"))
        elif re.search(r"\bclaro\b", plano):
            mudancas.append(_mudanca("tema", "claro"))
    if re.search(r"\banimac(ao|oes)\b", plano):
        if re.search(r"\b(reduz\w*|" + RE_DESLIGA + r"|menos|sem)\b[^.]{0,20}animac", plano):
            mudancas.append(_mudanca("animacoes_reduzidas", True))
        elif re.search(r"\b(volta\w*|" + RE_LIGA + r")\b[^.]{0,20}animac", plano):
            mudancas.append(_mudanca("animacoes_reduzidas", False))
    tipos = {
        "bem_estar": r"pausa|bem-estar|bem estar|foco|descanso|levantar",
        "resposta": r"resposta pronta|quando (?:a )?resposta",
        "aprovacao": r"aprovac(?:ao|oes)",
        "gravacao": r"transcric(?:ao|oes)|gravac(?:ao|oes)",
        "agenda": r"compromissos?|reunio(?:es)?|audiencias?",
        "acesso": r"acesso (?:de fora|externo)|bloque\w+",
    }
    # "me avisa da audiência amanhã" é agenda: aqui só o substantivo ("os
    # avisos", "notificação") ou o "para de me avisar".
    if re.search(r"\bavisos?\b|\bnotificac\w*|\blembretes? de pausa|\b(?:para|pare|parar|chega) de (?:me )?avisar\b|\bvolt\w* a (?:me )?avisar\b", plano):
        if re.search(r"\b(todos os avisos|nenhum aviso|avisos do windows|notificac(?:ao|oes) do windows)\b", plano):
            ligar = not re.search(r"\b" + RE_DESLIGA + r"\b|\bnenhum\b", plano)
            mudancas.append(_mudanca("avisos_windows", ligar))
        else:
            for chave, padrao in tipos.items():
                m = re.search(r"\b(?:" + padrao + r")\b", plano)
                if not m:
                    continue
                antes = plano[max(0, m.start() - 45):m.start()]
                if re.search(r"\b(" + RE_DESLIGA + r"|sem)\b", antes):
                    mudancas.append(_mudanca("avisos_tipos." + chave, False))
                elif re.search(r"\b(volta\w*|" + RE_LIGA + r"|me avis\w*)\b", antes):
                    mudancas.append(_mudanca("avisos_tipos." + chave, True))
    if not mudancas:
        return None
    return {"secao": "aparencia", "mudancas": mudancas}


def _ler_menu(texto: str, plano: str) -> dict | None:
    m = re.search(r"\b(?:do|no|ao|pro|para o) menu\b|\bdo trilho\b|\bda barra\b", plano)
    if not m:
        return None
    desligar = bool(re.search(r"\b(" + RE_DESLIGA + r")\b", plano)) and not re.search(r"\b(volta\w*|poe de volta|traz\w* de volta)\b", plano)
    ligar = bool(re.search(r"\b(volta\w*|poe|coloca|traz\w*|mostra\w*|liga\w*)\b", plano))
    if not (desligar or ligar):
        return None
    mudancas = []
    for chave, _rotulo, padrao in MODULOS:
        if re.search(r"\b(?:" + padrao + r")\b", plano):
            mudancas.append(_mudanca("modulos." + chave, not desligar))
    if not mudancas:
        return None
    return {"secao": "menu", "mudancas": mudancas}


def _ler_assistente(texto: str, plano: str) -> dict | None:
    mudancas, recusadas = [], []
    sozinho = r"(sozinh\w*|sem (?:me )?(?:pedir|perguntar|confirmar|revisar)|sem ficar (?:me )?pedindo|direto)"
    voltar = r"(volta\w* a (?:me )?(?:pedir|perguntar)|pede (?:o )?(?:meu )?sim|pergunta antes|com (?:o meu )?sim)"
    regras = [
        ("organizar_mover", r"(organiz\w*|mover|mova|move)\b[^.]{0,40}(pastas?|arquivos?)|(pastas?|arquivos?)\b[^.]{0,20}organiz\w*"),
        ("assinar", r"\bassin\w*"),
        ("enviar_mensagem", r"\b(envi\w*|mand\w*) (?:os? )?(e-?mails?|mensage\w*)"),
        ("modelo_nuvem", r"\bnuvem\b"),
        ("agentes_sozinhos", r"\bagentes?\b"),
    ]
    for chave, padrao in regras:
        if not re.search(padrao, plano):
            continue
        if re.search(voltar, plano):
            mudancas.append(_mudanca("autonomia." + chave, False))
        elif re.search(sozinho, plano):
            if chave in SENSIVEIS:
                recusadas.append(chave)
            else:
                mudancas.append(_mudanca("autonomia." + chave, True))
    if re.search(r"\b(para|pare|nao) (?:de )?ler (?:as )?pastas\b", plano):
        mudancas.append(_mudanca("autonomia.ler_pastas", False))
    if re.search(r"\bir devagar\b|\bmodo devagar\b|\bdevagar quando eu usar\b", plano):
        mudancas.append(_mudanca("devagar", not re.search(r"\b" + RE_DESLIGA + r"\b", plano)))
    m = re.search(r"\b(?:troca|troque|trocar|muda|mude|mudar|usa|use|usar|passa|passe)\b[^.]{0,30}\bmodelo(?: de linguagem| padrao| da conversa)?\b[^.]{0,12}?"
                  r"\b(?:para|pro|por|pelo|o)\s+([a-z0-9][\w.:/-]*\d[\w.:/-]*)", plano)
    if m:
        mudancas.append(_mudanca("modelo", m.group(1).strip(".,")))
    if not mudancas and not recusadas:
        return None
    return {"secao": "assistente", "mudancas": mudancas, "recusadas": recusadas}


def _ler_modelos(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(teste|testa|testar|medir|mede|compara\w*)\b[^.]{0,40}\bmodelos\b|\bqual modelo\b[^.]{0,30}(vale|melhor|roda)", plano):
        return {"secao": "desempenho", "mudancas": [], "teste": True}
    m = re.search(r"\b(?:usa|use|usar|coloca|poe|passa|passe|deixa)\s+(?:o\s+)?([a-z0-9][\w.:/-]*\d[\w.:/-]*)\s+(?:para|pras?|pros?|nos?|nas?)\s+(?:os |as |a |o )?"
                  r"(perguntas?|julgamentos?|juiz|e-?mails?|redac\w*|resumos?|leitura)", plano)
    if m:
        alvo = m.group(2)
        tarefa = ("conversa" if alvo.startswith("pergunta") else "juiz" if alvo.startswith(("julgamento", "juiz"))
                  else "email" if "mail" in alvo else "redacao" if alvo.startswith("redac") else
                  "resumos" if alvo.startswith("resumo") else "leitura")
        return {"secao": "modelos", "mudancas": [_mudanca("tarefas_modelo." + tarefa, m.group(1).strip(".,"))]}
    if re.search(r"\b(respostas?|paulus|conversa|ia|assistente)\b[^.]{0,30}\b(demor\w*|lent\w*|devagar)\b|\bmais rapid\w*\b[^.]{0,20}\b(respost\w*|paulus)?", plano) \
            and re.search(r"\b(respost\w*|demor\w*|rapid\w*)\b", plano) and not re.search(r"\b(computador|pc|maquina) (?:ta|esta)\b", plano):
        return {"secao": "modelos", "mudancas": [], "mais_rapido": True}
    return None


def _ler_desempenho(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(computador|pc|maquina|notebook|windows)\b[^.]{0,30}\b(travand\w*|lent\w*|pesad\w*|engasga\w*|trava\w*)\b"
                 r"|\b(travand\w*|lent\w*)\b[^.]{0,30}\b(e o paulus|culpa do paulus)\b", plano):
        return {"secao": "desempenho", "mudancas": []}
    return None


def _ler_versao(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(paulus|programa|sistema)?\s*(?:ta|esta|estou)\s+atualizad\w*|\b(tem|saiu|existe)\s+(?:uma\s+)?(versao|atualizac\w*)\s+nova"
                 r"|\bqual (?:e )?a (?:minha )?versao\b|\bversao (?:do paulus|mais nova|nova)\b", plano):
        return {"secao": "plano", "mudancas": []}
    return None


def _ler_lixeira(texto: str, plano: str) -> dict | None:
    m = re.search(r"\b(?:apaguei|deletei|exclui|joguei fora|removi)\b(?:\s+sem querer)?\s+(?:o |a |os |as )?(.+?)(?:,|\?|$| da pra| tem como| como (?:eu )?(?:volto|recupero))", plano)
    if not m:
        m = re.search(r"\b(?:recuperar|recupera|restaurar|restaura|desfazer|voltar)\b\s+(?:o |a )?(.+?)\s+que (?:eu )?apaguei", plano)
    if not m:
        return None
    busca = re.sub(r"\bsem querer\b", "", m.group(1)).strip(" .,")
    return {"secao": "lixeira", "mudancas": [], "busca": busca}


def _ler_backup(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(computador|pc|maquina|hd|notebook)\b[^.]{0,25}\b(estragar|quebrar|pifar|queimar|for roubad\w*|der defeito)\b"
                 r"|\bperco tudo\b|\bperder tudo\b|\bbackup\b|\bcopia de seguranca\b", plano):
        return {"secao": "backup", "mudancas": []}
    return None


def _ler_word(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(paulus|pavlvs|assistente)\b[^.]{0,25}\b(dentro do|no|pelo) word\b|\bword\b[^.]{0,25}\b(paulus|pavlvs)\b", plano):
        return {"secao": "word", "mudancas": []}
    return None


def _ler_acesso(texto: str, plano: str) -> dict | None:
    if re.search(r"\b(usar|uso|abrir|acessar|entrar no)\b[^.]{0,25}\b(paulus|sistema)\b[^.]{0,25}\b(do|no|pelo) (celular|telefone|tablet|ipad)\b"
                 r"|\b(do|no|pelo) (celular|tablet)\b[^.]{0,30}\b(paulus)\b|\bacesso (?:de fora|externo)\b[^.]{0,20}\b(liga\w*|quero|configur\w*)\b"
                 r"|\b(de casa|fora do escritorio|no forum)\b[^.]{0,30}\bpaulus\b|\bpaulus\b[^.]{0,30}\b(de casa|fora do escritorio|no forum)\b", plano):
        return {"secao": "acesso", "mudancas": []}
    return None


def _ler_convite(texto: str, plano: str) -> dict | None:
    m = re.search(r"\b(?:convid\w*|chama\w*)\s+(?:o |a )?(.+?)\s+(?:pra|para|pro|na|a) (?:a )?equipe\b", plano)
    if not m:
        return None
    # O nome como a pessoa escreveu (com maiúsculas), no mesmo lugar da frase.
    trecho = texto[m.start(1):m.end(1)] if len(texto) == len(plano) else m.group(1)
    nome = " ".join(p if p.lower() in ("da", "de", "do", "das", "dos") else p[:1].upper() + p[1:] for p in trecho.split())
    email = (RE_EMAIL.search(texto) or [""])[0] if RE_EMAIL.search(texto) else ""
    return {"secao": "vinculos", "mudancas": [], "nome": nome.strip(" ,."), "email": email}


def _ler_lembrete(texto: str, plano: str) -> dict | None:
    m = re.match(r"^\s*(?:paulus,?\s*)?(?:lembra|lembre|lembre-se|guarda|guarde|anota|anote|aprende|aprenda|grava|grave)\s+(?:de\s+)?que\s+", plano)
    if not m:
        return None
    # "lembra que amanhã tenho audiência" é agenda, não regra da casa.
    if re.search(r"\b(amanha|hoje|depois de amanha|segunda|terca|quarta|quinta|sexta|sabado|domingo|dia \d|\d{1,2}h|\d{1,2}/\d{1,2}|semana que vem)\b", plano):
        return None
    if not re.search(r"\b(escritorio|a gente|nos|sempre|nunca|todo|toda|todos|todas|regra|padrao|costum\w*|clientes?)\b", plano):
        return None
    return {"secao": "aprendizado", "mudancas": [], "resto": texto[m.end():], "lembrete": lembrete_da_frase(texto[m.end():])}


# "a gente sempre pede" -> "pedir": a regra da casa escrita como instrução.
INFINITIVOS = {"pede": "pedir", "pedimos": "pedir", "faz": "fazer", "fazemos": "fazer", "coloca": "colocar", "colocamos": "colocar",
               "usa": "usar", "usamos": "usar", "manda": "mandar", "mandamos": "mandar", "junta": "juntar", "juntamos": "juntar",
               "cita": "citar", "citamos": "citar", "inclui": "incluir", "incluimos": "incluir", "cobra": "cobrar", "cobramos": "cobrar",
               "poe": "pôr", "pomos": "pôr", "envia": "enviar", "enviamos": "enviar", "evita": "evitar", "evitamos": "evitar",
               "confere": "conferir", "conferimos": "conferir", "escreve": "escrever", "escrevemos": "escrever"}


def lembrete_da_frase(resto: str, nomes: list[str] | None = None) -> str:
    """
    "aqui no escritório a gente sempre pede justiça gratuita pros clientes da
    cooperativa" -> "Para os clientes da Cooperativa Rio Fresco, pedir justiça
    gratuita." `nomes` são as fichas de Cadastros: "a cooperativa" vira o nome
    da ficha quando só uma combina.
    """
    t = " ".join(_nfc(resto).split()).strip(" .")
    t = re.sub(r"^(?:aqui\s+)?(?:no|neste|nesse)\s+escrit[óo]rio\s*,?\s*", "", t, flags=re.I)
    t = re.sub(r"^(?:a gente|nós|nos|a equipe)\s+(?:sempre\s+)?", "", t, flags=re.I)
    troca = [(r"\bpros\b", "para os"), (r"\bpras\b", "para as"), (r"\bpro\b", "para o"), (r"\bpra\b", "para"),
             (r"\btá\b", "está"), (r"\bvc\b", "você")]
    for a, b in troca:
        t = re.sub(a, b, t, flags=re.I)
    if not t:
        return ""
    primeira, _, resto_t = t.partition(" ")
    verbo = INFINITIVOS.get(_plano(primeira))
    if verbo:
        m = re.search(r"\s+(para (?:os|as|o|a) clientes?\b.*|nos? (?:processos?|casos?|pe[çc]as?)\b.*)$", resto_t, flags=re.I)
        if m:
            quem = m.group(1)
            for nome in nomes or []:
                cabeca = (_plano(nome).split() or [""])[0]
                unico = sum(1 for n in nomes if (_plano(n).split() or [""])[0] == cabeca) == 1
                if cabeca and unico and re.search(r"\b(?:da|do|de)\s+" + re.escape(cabeca) + r"\b", _plano(quem)):
                    quem = re.sub(r"\b(da|do|de)\s+" + re.escape(cabeca) + r"\w*", lambda x, n=nome: x.group(1) + " " + n, quem, flags=re.I)
                    break
            t = quem[:1].upper() + quem[1:] + ", " + verbo + " " + resto_t[:m.start()].strip()
        else:
            t = verbo + " " + resto_t
    return t[:1].upper() + t[1:] + "."


def _ler_whatsapp(texto: str, plano: str) -> dict | None:
    m = re.search(r"\b(?:manda|mande|mandar|envia|envie|enviar|avisa|avise|escreve|escreva)\b[^.]{0,20}\b(?:no |pelo |por )?(?:whats\w*|zap)\b"
                  r"\s*(?:d[oa]s?|pr[oa]|para o|para a|ao|a)?\s*(.+?)\s+(?:que|dizendo que|falando que|avisando que)\s+(.+)$", plano)
    if not m:
        m = re.search(r"\b(?:avisa|avise|manda|mande)\s+(?:o |a )?(.+?)\s+(?:pelo|no|por) (?:whats\w*|zap)\s+(?:que|dizendo que)\s+(.+)$", plano)
    if not m:
        return None
    mesmo = len(texto) == len(plano)
    quem = texto[m.start(1):m.end(1)] if mesmo else m.group(1)
    recado = texto[m.start(2):m.end(2)] if mesmo else m.group(2)
    return {"secao": "conexoes", "mudancas": [], "whatsapp": {"quem": quem.strip(" ,."), "recado": recado.strip(" .")}}


LEITORES = (_ler_whatsapp, _ler_lixeira, _ler_lembrete, _ler_convite, _ler_menu, _ler_perfil, _ler_aparencia,
            _ler_modelos, _ler_assistente, _ler_desempenho, _ler_versao, _ler_word, _ler_acesso, _ler_backup)


def ler(texto: str) -> dict | None:
    """O pedido de configuração na frase: a seção, as mudanças propostas e o que mais a seção precisa. None quando não é."""
    texto = _nfc(texto or "").strip()
    plano = _plano(texto)
    if not plano or len(plano) > 400:
        return None
    # "abra as configurações" é a tela, não um pedido de mudança.
    if re.fullmatch(r"\s*(abr\w*|mostr\w*|ir para|va para)\s+(as\s+)?configurac\w*\s*\.?", plano):
        return None
    for leitor in LEITORES:
        achado = leitor(texto, plano)
        if achado:
            return achado
    return None


# ============================================================ montar a proposta

def _sim_nao(v) -> str:
    return "ligado" if v else "desligado"


def _valor_de(prefs: dict, chave: str):
    alvo = prefs
    for parte in chave.split("."):
        alvo = (alvo or {}).get(parte) if isinstance(alvo, dict) else None
    return alvo


ROTULOS = {
    "pessoa.telefone": "Telefone", "pessoa.email": "E-mail", "pessoa.oab": "OAB", "pessoa.cpf": "CPF",
    "pessoa.endereco": "Endereço profissional", "pessoa.nome": "Nome", "escritorio.nome": "Nome do escritório",
    "escritorio.cnpj": "CNPJ do escritório", "timbre_no_pdf": "Papel timbrado nos PDFs", "tema": "Tema",
    "animacoes_reduzidas": "Animações reduzidas", "avisos_windows": "Avisar no Windows", "devagar": "Ir devagar quando eu usar o PC",
    "modelo": "Modelo de linguagem",
}


def rotulo(chave: str) -> str:
    if chave in ROTULOS:
        return ROTULOS[chave]
    secao, _, fim = chave.partition(".")
    if secao == "autonomia":
        return AUTONOMIA_ROTULO.get(fim, fim)
    if secao == "avisos_tipos":
        return "Avisos de " + AVISOS_ROTULO.get(fim, fim)[:1].lower() + AVISOS_ROTULO.get(fim, fim)[1:]
    if secao == "modulos":
        return next((r for c, r, _ in MODULOS if c == fim), fim)
    if secao == "tarefas_modelo":
        return TAREFAS.get(fim, fim)
    return chave


def _mostrar(chave: str, valor, dados: dict) -> str:
    if chave.startswith("modulos."):
        return "no menu" if valor else "fora do menu"
    if chave == "tema":
        return TEMAS.get(valor or "", "")
    if chave.startswith("tarefas_modelo."):
        return valor or ("Padrão (" + (dados.get("padrao") or "o modelo padrão") + ")")
    if isinstance(valor, bool) or valor is None and chave in ("timbre_no_pdf", "devagar", "animacoes_reduzidas"):
        return _sim_nao(valor)
    if chave.startswith(("autonomia.", "avisos_tipos.")) or chave == "avisos_windows":
        return _sim_nao(valor)
    if chave == "pessoa.telefone":
        return campos_br.mascara_telefone(valor or "") or (valor or "vazio")
    return str(valor) if valor not in (None, "") else "vazio"


def _linhas(mudancas: list[dict], prefs: dict, dados: dict) -> list[dict]:
    linhas = []
    for m in mudancas:
        antes = _valor_de(prefs, m["chave"])
        if m["chave"].startswith("avisos_tipos.") and antes is None:
            antes = True
        if m["chave"].startswith("modulos.") and antes is None:
            antes = True
        linhas.append({"chave": m["chave"], "campo": rotulo(m["chave"]), "antes": _mostrar(m["chave"], antes, dados) if m["chave"] != "tema" else "",
                       "depois": _mostrar(m["chave"], m["valor"], dados), "tom": "ok", "riscar": m["chave"].startswith("pessoa.")})
    return linhas


def _oab_falta(oab: str) -> bool:
    so = re.sub(r"\D", "", oab or "")
    return not so or set(so) == {"0"}


def _quantas(n: int) -> str:
    return NUMEROS.get(n, str(n))


def _titulo_da_conversa(secao: str, mudancas: list[dict]) -> str:
    chaves = [m["chave"] for m in mudancas]
    if secao == "perfil":
        if "pessoa.telefone" in chaves:
            return "Troque meu telefone"
        return "Atualize meus dados"
    if secao == "aparencia":
        if any(c == "avisos_tipos.bem_estar" for c in chaves):
            return "Menos avisos de pausa"
        if chaves == ["tema"]:
            return "Troque o tema"
        return "Ajuste a aparência e os avisos"
    if secao == "menu":
        nomes = [rotulo(c) for c in chaves]
        fora = all(not m["valor"] for m in mudancas)
        return ("Tire " if fora else "Volte ") + " e ".join([", ".join(nomes[:-1]), nomes[-1]] if len(nomes) > 1 else nomes) + (" do menu" if fora else " ao menu")
    if secao == "assistente":
        if "autonomia.organizar_mover" in chaves:
            return "Organize as pastas sem pedir"
        return "Ajuste o assistente"
    return SECOES.get(secao, ("Configurações", ""))[0]


def proposta(pedido: dict, dados: dict) -> tuple[str, dict]:
    """
    A frase da conversa e a proposta do cartão. `dados` é o que a API leu
    agora para a seção (prefs, modelos, saúde, backup...): a frase sai dele,
    não de suposição.
    """
    secao = pedido["secao"]
    prefs = dados.get("prefs") or {}
    mudancas = [dict(m) for m in pedido.get("mudancas") or []]
    linhas: list[dict] = []
    acoes: list[dict] = []
    nota = ""
    extra: dict = {}
    titulo = _titulo_da_conversa(secao, mudancas)
    frase = ""

    if secao == "perfil":
        # Só o que muda de verdade.
        mudancas = [m for m in mudancas if _valor_de(prefs, m["chave"]) != m["valor"]
                    or (m["chave"] == "pessoa.telefone" and campos_br.so_digitos(_valor_de(prefs, m["chave"]) or "") != campos_br.so_digitos(m["valor"]))]
        linhas = _linhas(mudancas, prefs, dados)
        timbre = next((m["valor"] for m in mudancas if m["chave"] == "timbre_no_pdf"), prefs.get("timbre_no_pdf"))
        pessoa = {**(prefs.get("pessoa") or {}), **{m["chave"].split(".", 1)[1]: m["valor"] for m in mudancas if m["chave"].startswith("pessoa.")}}
        n = len(mudancas)
        if not n:
            frase = "Abri Meus dados ao lado: o que você pediu já está assim, nada para mudar."
        else:
            frase = "Abri Meus dados ao lado com " + ("a mudança marcada." if n == 1 else _quantas(n) + " mudanças marcadas.")
        falta = []
        if timbre:
            if _oab_falta(pessoa.get("oab")):
                falta.append(("pessoa.oab", "OAB", pessoa.get("oab") or ""))
            if not (pessoa.get("endereco") or "").strip():
                falta.append(("pessoa.endereco", "Endereço profissional", ""))
            if not (pessoa.get("nome") or "").strip():
                falta.append(("pessoa.nome", "Nome", ""))
        if falta:
            chave, campo, valor = falta[0]
            if chave == "pessoa.oab" and valor:
                frase += (" Antes de salvar, um ponto: o papel timbrado usa nome, OAB, endereço e contato, e a sua OAB ainda está como `"
                          + valor + "`. Se salvar assim, esse número sai no alto de todo PDF.")
            else:
                frase += (" Antes de salvar, um ponto: o papel timbrado usa nome, OAB, endereço e contato, e " +
                          ("a sua OAB" if chave == "pessoa.oab" else "o " + campo.lower()) + " ainda está vazi" +
                          ("a" if chave == "pessoa.oab" else "o") + ". Se salvar assim, o alto do PDF sai sem " + ("ela." if chave == "pessoa.oab" else "ele."))
            for chave_f, campo_f, _v in falta:
                linhas.append({"chave": chave_f, "campo": campo_f, "antes": "", "depois": "falta preencher para o timbre", "tom": "aviso"})
            acoes.append({"rotulo": "Vou informar a " + ("OAB" if chave == "pessoa.oab" else campo.lower()), "faz": "focar", "chave": chave})
            outras = [m for m in mudancas if m["chave"] != "timbre_no_pdf"]
            if outras and any(m["chave"] == "timbre_no_pdf" for m in mudancas):
                acoes.append({"rotulo": "Salvar só o " + rotulo(outras[0]["chave"]).lower() if len(outras) == 1 else "Salvar sem o timbre",
                              "faz": "salvar_so", "chaves": [m["chave"] for m in outras]})
            extra["atencao"] = [f[0] for f in falta]

    elif secao == "aparencia":
        linhas = _linhas(mudancas, prefs, dados)
        partes = []
        bem = next((m for m in mudancas if m["chave"] == "avisos_tipos.bem_estar"), None)
        outros = [m for m in mudancas if m["chave"].startswith("avisos_tipos.") and m is not bem]
        if bem is not None:
            partes.append("Desliguei os avisos de bem-estar e foco no Windows; os lembretes continuam na coluna de Foco, só não piscam mais na tela."
                          if not bem["valor"] else "Liguei de novo os avisos de bem-estar e foco no Windows.")
            if not bem["valor"]:
                nota = "O alerta de 90 minutos sem pausa também para. Se quiser só esse de volta, é ligar de novo ao lado."
        for m in outros:
            partes.append(("Desliguei" if not m["valor"] else "Liguei") + " o aviso de " + AVISOS_ROTULO[m["chave"].split(".")[1]].lower() + " no Windows.")
        w = next((m for m in mudancas if m["chave"] == "avisos_windows"), None)
        if w is not None:
            partes.append("Desliguei os avisos do Windows: nada mais aparece no canto da tela." if not w["valor"] else "Liguei os avisos do Windows.")
        t = next((m for m in mudancas if m["chave"] == "tema"), None)
        if t is not None:
            partes.append({"auto": "Para o tema, escolhi \"Seguir o Windows\": ele fica claro de dia e escuro à noite, se o Windows estiver configurado assim.",
                           "claro": "Para o tema, marquei o Claro.", "escuro": "Para o tema, marquei o Escuro."}[t["valor"]])
        a = next((m for m in mudancas if m["chave"] == "animacoes_reduzidas"), None)
        if a is not None:
            partes.append("Marquei Animações reduzidas: sem deslizes nem pulsos, a tela troca direto." if a["valor"] else "Desmarquei Animações reduzidas: as transições voltam.")
        frase = " ".join(partes) + " Nada muda até você salvar ao lado."

    elif secao == "menu":
        mudancas = [m for m in mudancas if (_valor_de(prefs, m["chave"]) is not False) != m["valor"]]
        linhas = _linhas(mudancas, prefs, dados)
        nomes = [rotulo(m["chave"]) for m in mudancas]
        if not mudancas:
            frase = "Abri Módulos ao lado: o menu já está como você pediu."
        elif all(not m["valor"] for m in mudancas):
            frase = ("Desliguei " + ("os dois" if len(nomes) == 2 else "o " + nomes[0] if len(nomes) == 1 else "os " + str(len(nomes))) +
                     " ao lado. Desligar só tira do menu desta máquina: nada é apagado, e ligar de novo traz tudo de volta como estava.")
            nota = "Ainda dá para pedir " + " ou ".join(n.lower() for n in nomes) + " aqui na conversa; o Paulus só não mostra o atalho no menu."
        else:
            frase = "Liguei de novo ao lado: " + ", ".join(nomes) + " volta" + ("m" if len(nomes) > 1 else "") + " ao menu como estava" + ("m" if len(nomes) > 1 else "") + "."

    elif secao == "assistente":
        modelos = dados.get("modelos") or []
        validas = []
        for m in mudancas:
            if m["chave"] == "modelo" and modelos and m["valor"] not in modelos:
                parecido = next((x for x in modelos if x.startswith(m["valor"])), "")
                if parecido:
                    m["valor"] = parecido
                else:
                    extra.setdefault("fora", []).append(m["valor"])
                    continue
            validas.append(m)
        mudancas = [m for m in validas if _valor_de(prefs, m["chave"]) != m["valor"] or m["chave"] == "modelo" and dados.get("padrao") != m["valor"]]
        linhas = _linhas(mudancas, prefs, dados)
        partes = []
        for m in mudancas:
            if m["chave"].startswith("autonomia."):
                k = m["chave"].split(".")[1]
                partes.append(("Liguei" if m["valor"] else "Desliguei") + " \"" + AUTONOMIA_ROTULO[k] + "\" ao lado. " + AUTONOMIA_COM_ISSO.get((k, m["valor"]), ""))
            elif m["chave"] == "modelo":
                partes.append("Marquei o " + m["valor"] + " ao lado: ele passa a responder a partir da próxima pergunta, depois de salvar.")
            elif m["chave"] == "devagar":
                partes.append(("Liguei" if m["valor"] else "Desliguei") + " \"Ir devagar quando eu usar o PC\" ao lado: " +
                              ("a leitura de documentos espera a máquina desafogar." if m["valor"] else "a leitura não espera mais a máquina desafogar."))
        for nome in extra.get("fora", []):
            partes.append("O " + nome + " não está nesta máquina: dá para baixar em Modelos.")
        recusadas = pedido.get("recusadas") or []
        if recusadas:
            nomes = [SENSIVEIS[k] for k in recusadas]
            partes.append(("\"" + nomes[0] + "\" eu não ligo pela conversa" if len(nomes) == 1 else "Esses eu não ligo pela conversa") +
                          ": é ação que tem valor jurídico ou sai do escritório, e continua pedindo o seu sim. Se quiser mesmo, ligue você ao lado.")
            for k in recusadas:
                linhas.append({"chave": "autonomia." + k, "campo": SENSIVEIS[k], "antes": "", "depois": "fica com você, ao lado", "tom": "aviso"})
            extra["destacar"] = ["autonomia." + k for k in recusadas]
        elif any(m["chave"].startswith("autonomia.") and m["valor"] for m in mudancas):
            a = prefs.get("autonomia") or {}
            if not a.get("assinar") and not a.get("enviar_mensagem"):
                linhas.append({"chave": "", "campo": "Assinar e enviar e-mail", "antes": "", "depois": "continuam pedindo o seu sim", "tom": "aviso"})
                nota = "Assinatura tem valor jurídico e o e-mail sai do escritório, por isso deixei os dois como estavam."
        frase = " ".join(partes) or "Abri Assistente e modelo ao lado: já está como você pediu."

    elif secao == "modelos":
        frase, linhas, acoes, nota, mudancas, extra = _proposta_modelos(pedido, dados, mudancas)
        titulo = "Deixe as respostas mais rápidas" if pedido.get("mais_rapido") else "Quem faz cada tarefa"

    elif secao == "desempenho" and pedido.get("teste"):
        frase, extra = _proposta_teste(dados)
        titulo = "Teste os modelos desta máquina"
        nota = "Pode continuar usando o Paulus; o teste pausa quando você manda uma pergunta."

    elif secao == "desempenho":
        frase, linhas, acoes, depois = _proposta_desempenho(dados)
        extra = {"depois": depois}
        titulo = "O computador está travando"

    elif secao == "plano":
        frase, linhas, acoes = _proposta_versao(dados)
        titulo = "O Paulus está atualizado?"

    elif secao == "lixeira":
        frase, extra, nota = _proposta_lixeira(pedido, dados)
        achado = (extra.get("achados") or [{}])[0]
        titulo = ("Recupere " + achado["titulo"]) if achado.get("titulo") else "Recupere da Lixeira"

    elif secao == "backup":
        frase, linhas, extra = _proposta_backup(dados)
        titulo = "Proteja os dados do escritório"

    elif secao == "aprendizado":
        texto = pedido.get("lembrete") or ""
        frase = ("Escrevi como lembrete do escritório. Ele entra em toda pergunta da conversa, junto com os trechos dos documentos. "
                 "Confira o texto ao lado antes de guardar.")
        extra = {"lembrete": texto}
        nota = "Na resposta, a regra da casa aparece separada da lei e da doutrina."
        titulo = "Lembre: " + texto[:40].rstrip(" .,") + ("…" if len(texto) > 40 else "")

    elif secao == "word":
        frase, linhas, extra = _proposta_word(dados)
        titulo = "Use o Paulus dentro do Word"

    elif secao == "acesso":
        frase, linhas, extra = _proposta_acesso(dados)
        titulo = "Use o Paulus do celular"

    elif secao == "vinculos":
        frase, linhas, acoes, extra = _proposta_convite(pedido, dados)
        titulo = "Convide " + (pedido.get("nome") or "alguém").split()[0] + " para a equipe"

    elif secao == "conexoes":
        frase, extra, acoes = _proposta_whatsapp(pedido, dados)
        quem = (extra.get("contato") or {}).get("nome") or (pedido.get("whatsapp") or {}).get("quem") or ""
        titulo = "Avise " + (quem.split()[0] if quem else "pelo WhatsApp") + (" pelo WhatsApp" if quem else "")

    rotulo_secao, sub = SECOES.get(secao, ("Configurações", ""))
    return frase, {
        "tipo": "config", "titulo": rotulo_secao, "secao": secao, "sub": sub, "titulo_conversa": titulo,
        "mudancas": [{"chave": m["chave"], "valor": m["valor"]} for m in mudancas],
        "linhas": linhas, "acoes": acoes, "nota": nota, "extra": extra,
    }


# ---------------------------------------------------------------- por seção

def _s(seg) -> str:
    return ("~" + str(int(round(seg))) + " s") if seg else ""


def _proposta_modelos(pedido: dict, dados: dict, mudancas: list[dict]):
    instalados = dados.get("instalados") or []
    padrao = dados.get("padrao") or ""
    tarefas = {t["id"]: t for t in dados.get("tarefas") or []}
    nomes = [m["nome"] for m in instalados]
    linhas, acoes, extra = [], [], {}
    nota = ""

    def nota_de(m):
        q = m.get("qualidade") or {}
        return (str(q.get("certas")) + " de " + str(q.get("total"))) if q.get("total") else ""

    def primeira(m):
        e = m.get("estimativa") or {}
        med = m.get("medida") or {}
        return e.get("primeira_s") or e.get("segundos") or med.get("total_s")

    if mudancas:
        validas = []
        for m in mudancas:
            nome = m["valor"]
            if nome not in nomes:
                parecido = next((x for x in nomes if x.startswith(nome)), "")
                if not parecido:
                    extra.setdefault("fora", []).append(nome)
                    continue
                m["valor"] = parecido
            validas.append(m)
        mudancas = validas
        partes = []
        for m in mudancas:
            t = m["chave"].split(".")[1]
            antes = (tarefas.get(t) or {}).get("modelo") or ""
            linhas.append({"chave": m["chave"], "campo": TAREFAS.get(t, t), "antes": antes or padrao, "depois": m["valor"], "tom": "ok"})
            partes.append("Marquei o " + m["valor"] + " para " + TAREFAS.get(t, t).lower() + " ao lado; vale na hora em que você salvar.")
        for nome in extra.get("fora", []):
            partes.append("O " + nome + " não está nesta máquina: dá para baixar ao lado, em Modelos.")
        return " ".join(partes), linhas, acoes, nota, mudancas, extra

    # "As respostas estão demorando": o juiz para o modelo mais leve que
    # tenha nota, sem trocar o modelo das respostas.
    atual = next((m for m in instalados if m["nome"] == padrao), None)
    leves = sorted([m for m in instalados if m["nome"] != padrao and (m.get("gb") or 99) < ((atual or {}).get("gb") or 0)],
                   key=lambda m: m.get("gb") or 99)
    juiz_atual = (tarefas.get("juiz") or {}).get("modelo") or padrao
    leve = leves[0] if leves else None
    t_atual = primeira(atual or {})
    partes = []
    if t_atual:
        partes.append("Nesta máquina, a primeira pergunta sobre um documento leva uns " + str(int(round(t_atual))) + " s com o " + padrao + ".")
    if leve and juiz_atual != leve["nome"]:
        n = nota_de(leve)
        partes.append("Dá para ganhar tempo sem trocar o modelo das respostas: passar os julgamentos rápidos para o " + leve["nome"] +
                      (", que acertou " + n + " no nosso teste mas só decide uma palavra" if n else ", que só decide uma palavra") +
                      ", e ligar \"Ir devagar quando eu usar o PC\" só se a máquina estiver travando. Deixei a sugestão marcada ao lado.")
        mudancas = [_mudanca("tarefas_modelo.juiz", leve["nome"])]
        linhas.append({"chave": "tarefas_modelo.juiz", "campo": "Julgamentos rápidos", "antes": juiz_atual, "depois": leve["nome"], "tom": "ok", "icone": "speed"})
        if atual:
            n_atual = nota_de(atual)
            linhas.append({"chave": "", "campo": "Perguntas sobre documentos continuam no " + padrao + (", que acertou " + n_atual + "." if n_atual else "."),
                           "antes": "", "depois": "", "tom": "info"})
        if not (leve.get("medida") or {}).get("total_s"):
            acoes.append({"rotulo": "Medir antes", "faz": "medir", "nome": leve["nome"]})
    else:
        partes.append("Nesta máquina não há modelo mais leve que o " + (padrao or "padrão") + " instalado. Um menor responde mais rápido e acerta menos; "
                      "dá para baixar ao lado, em Modelos, e medir antes de usar.")
    acoes.append({"rotulo": "Ver outros modelos para baixar", "faz": "rolar", "alvo": "catalogo"})
    return " ".join(partes), linhas, acoes, nota, mudancas, extra


def _proposta_teste(dados: dict):
    instalados = dados.get("instalados") or []
    livre = dados.get("memoria_total_gb") or 0
    cabem, fora = [], []
    for m in instalados:
        (fora if livre and (m.get("gb") or 0) > livre * 0.9 else cabem).append(m)
    frase = ("Estou medindo um por vez com a mesma resposta curta e fixa. Os acertos vêm do banco de provas do Paulus, que já foi "
             "rodado: a qualidade não depende da máquina, a velocidade sim.")
    for m in fora:
        frase += " O " + m["nome"] + " fica de fora: com " + str(m.get("gb")).replace(".", ",") + " GB, não cabe na memória desta máquina."
    if not cabem:
        frase = "Não há modelo instalado que caiba nesta máquina para medir. Dá para baixar um em Configurações › Modelos."
    return frase, {"teste": [{"nome": m["nome"], "gb": m.get("gb"), "qualidade": m.get("qualidade"),
                              "medida": m.get("medida")} for m in cabem],
                   "fora": [m["nome"] for m in fora]}


def _proposta_desempenho(dados: dict):
    rec = dados.get("recursos") or {}
    itens = dados.get("saude") or []
    cpu = round((rec.get("processador") or {}).get("percentual") or 0)
    mem = rec.get("memoria") or {}
    total = mem.get("total_gb") or 0
    livre = round(total - (mem.get("usado_gb") or 0), 1) if total else 0
    gb = lambda x: str(x).replace(".", ",")  # noqa: E731
    apertado = total and livre < 3
    partes = []
    if cpu >= 85:
        partes.append(f"Sim, em boa parte: o processador está em {cpu}%.")
    elif apertado:
        partes.append(f"Em parte. O processador está em {cpu}%, o que é tranquilo, mas a memória está quase cheia: sobram {gb(livre)} GB de {gb(total)} GB.")
    else:
        partes.append(f"Agora não parece ser o Paulus: o processador está em {cpu}% e sobram {gb(livre)} GB de memória de {gb(total)} GB.")
    if apertado or cpu >= 85:
        partes.append("O modelo de IA ocupa uns " + gb(dados.get("modelo_gb") or 2) + " GB e a transcrição pede outros 2 GB, então quando os dois "
                      "rodam juntos com o navegador aberto, o Windows começa a usar o disco e tudo fica lento.")
    linhas, ok_juntos = [], []
    for i in itens:
        if i["estado"] in ("erro", "aviso"):
            valor = i["valor"] + (" · feche abas e programas pesados" if i["chave"] == "memoria" else "")
            linhas.append({"chave": "", "campo": i["rotulo"], "antes": "", "depois": valor, "tom": "erro"})
        elif i["estado"] == "ok":
            ok_juntos.append(i["rotulo"].split()[0].lower() if i["chave"] != "erros" else "erros")
    if ok_juntos:
        nomes = {"espaco": "disco", "modelo": "modelo", "versao": "versão", "erros": "erros", "memoria": "memória"}
        juntos = [nomes.get(x, x) for x in ok_juntos]
        linhas.append({"chave": "", "campo": (", ".join(juntos[:-1]) + " e " + juntos[-1] if len(juntos) > 1 else juntos[0]).capitalize(),
                       "antes": "", "depois": "em dia", "tom": "ok"})
    acoes = []
    if not rec.get("devagar") and not (dados.get("prefs") or {}).get("devagar"):
        partes_fim = "Posso ligar \"Ir devagar quando eu usar o PC\": a leitura de documentos espera a máquina desafogar e o computador continua seu."
        acoes.append({"rotulo": "Ligar “Ir devagar”", "faz": "marcar", "chave": "devagar", "valor": True, "primario": True})
    else:
        partes_fim = "\"Ir devagar quando eu usar o PC\" já está ligado: a leitura de documentos espera a máquina desafogar."
    acoes.append({"rotulo": "Gerar diagnóstico", "faz": "clicar", "seletor": "[data-cfg-diagnostico]"})
    return " ".join(partes), linhas, acoes, partes_fim


def _quando(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso.replace("Z", ""))
    except (ValueError, AttributeError):
        return ""
    hoje = date.today()
    dia = "hoje" if d.date() == hoje else "ontem" if d.date() == hoje - timedelta(days=1) else d.strftime("%d/%m")
    return dia + " às " + d.strftime("%H:%M")


def _proposta_versao(dados: dict):
    a = dados.get("atualizacao") or {}
    atual = a.get("atual") or ""
    anuncio = a.get("anuncio") or {}
    quando = _quando(a.get("ultima_consulta") or "")
    if anuncio.get("nova"):
        frase = (f"Ainda não. Você usa a versão {atual}, e a {anuncio.get('versao')} já saiu. "
                 + ("Ela já está baixada: instala quando você fechar o Paulus, ou agora ao lado." if a.get("pronto") else "Dá para baixar ao lado; nada seu vai junto."))
        linhas = [{"chave": "", "campo": "Versão nova disponível", "antes": atual, "depois": anuncio.get("versao") or "", "tom": "aviso", "mono": True}]
    elif not a.get("ultima_consulta"):
        frase = f"Você usa a versão {atual}. Ainda não conferi se há uma mais nova nesta máquina: dá para verificar agora ao lado."
        linhas = [{"chave": "", "campo": "Versão", "antes": "", "depois": atual, "tom": "info", "mono": True}]
    else:
        frase = (f"Está. Você usa a versão {atual}, a mais nova, e a última verificação foi {quando}. "
                 "O Paulus confere uma vez por dia lendo um arquivo público; nada seu vai junto.")
        linhas = [{"chave": "", "campo": "Na versão mais nova", "antes": "", "depois": atual, "tom": "ok", "mono": True}]
    if quando:
        linhas.append({"chave": "", "campo": "Última verificação", "antes": "", "depois": quando.replace("hoje às", date.today().strftime("%d/%m") + " às"), "tom": "neutro"})
    if a.get("erro"):
        linhas.append({"chave": "", "campo": "A última verificação falhou", "antes": "", "depois": a["erro"][:60], "tom": "aviso"})
    acoes = [{"rotulo": "Novidades da versão", "faz": "clicar", "seletor": "[data-cfg-novidades]"}]
    return frase, linhas, acoes


def _palavras(texto: str) -> list[str]:
    vazias = {"o", "a", "os", "as", "do", "da", "de", "dos", "das", "no", "na", "um", "uma", "e", "que", "pra", "para", "meu", "minha"}
    return [p for p in re.findall(r"[a-z0-9]+", _plano(texto)) if p not in vazias]


def _proposta_lixeira(pedido: dict, dados: dict):
    itens = dados.get("lixeira") or []
    busca = _palavras(pedido.get("busca") or "")
    pontuados = []
    for e in itens:
        alvo = set(_palavras(e.get("titulo", "") + " " + e.get("tipo_rotulo", "")))
        acerto = sum(1 for p in busca if p in alvo)
        if acerto:
            pontuados.append((acerto, e))
    pontuados.sort(key=lambda x: -x[0])
    if not pontuados:
        return ("Não achei nada parecido na Lixeira: o que você apaga fica lá por 30 dias. Abri a Lixeira ao lado para você procurar pelo nome.",
                {"achados": [], "busca": pedido.get("busca") or ""}, "")
    melhor = pontuados[0][0]
    achados = [e for p, e in pontuados if p == melhor][:3]
    e = achados[0]
    quando = _quando(e.get("apagado_em") or "")
    frase = (f"Dá. Ele está na Lixeira desde {quando} e só some em " + (f"{e.get('dias_restantes')} dias" if e.get("dias_restantes") != 1 else "1 dia") +
             ". Restaurar devolve " + ("o documento" if e.get("tipo") == "documento" else "o item") + ", as ligações e os arquivos ao lugar de onde saíram.")
    nota = ""
    # O que saiu no mesmo minuto, com o nome parecido (o documento A do mesmo teste).
    minuto = (e.get("apagado_em") or "")[:16]
    vizinhos = [x for x in itens if x is not e and (x.get("apagado_em") or "")[:16] == minuto and x.get("tipo") == e.get("tipo")]
    if vizinhos:
        v = vizinhos[0]
        nota = "“" + v["titulo"] + "” também foi apagado no mesmo minuto. Quer voltar com ele também?"
    termo = " ".join(w for w in (pedido.get("busca") or "").split() if len(w) > 1)
    return frase, {"achados": [{"id": x["id"], "titulo": x["titulo"], "tipo": x.get("tipo"), "tipo_rotulo": x.get("tipo_rotulo"),
                                "detalhe": x.get("detalhe") or "", "apagado_em": x.get("apagado_em")} for x in achados],
                   "vizinhos": [{"id": v["id"], "titulo": v["titulo"]} for v in vizinhos[:1]],
                   "busca": _busca_curta(e.get("titulo") or termo)}, nota


def _busca_curta(titulo: str) -> str:
    """ "Teste C5 — documento B" -> "Teste C5": o começo que junta os parecidos."""
    return re.split(r"\s+[—–-]\s+", titulo or "")[0].strip()


def _proposta_backup(dados: dict):
    b = dados.get("backup") or {}
    sugerida = ""
    if not b.get("pasta"):
        drives = dados.get("drives") or []
        sugerida = (drives[0].rstrip("\\") + "\\PAULUS Backup") if drives else ""
    linhas = []
    if b.get("ultimo_erro"):
        frase = "O último backup falhou: " + b["ultimo_erro"] + ". Abri o Backup ao lado para conferir a pasta e a senha."
    elif b.get("ultimo") and b.get("pasta") and b.get("tem_senha"):
        frase = ("Não: o backup está ligado e o último foi " + _quando(b["ultimo"]) + ", em " + b["pasta"] +
                 ". Se este computador estragar, é instalar o Paulus em outro e restaurar de lá com a sua senha.")
    else:
        frase = ("Hoje, sim: tudo do escritório mora neste computador e o backup nunca foi feito. O backup é um arquivo cifrado com uma senha sua, "
                 "numa pasta que você escolhe, uma vez por dia.")
        if sugerida:
            frase += " Já deixei a pasta sugerida ao lado; falta só a senha."
        elif not b.get("pasta"):
            frase += " Falta escolher a pasta e a senha, ao lado."
        elif not b.get("tem_senha"):
            frase += " A pasta já está escolhida; falta só a senha, ao lado."
    linhas.append({"chave": "", "campo": "Último backup", "antes": "", "depois": _quando(b["ultimo"]) if b.get("ultimo") else "nunca",
                   "tom": "ok" if b.get("ultimo") and not b.get("ultimo_erro") else "erro"})
    pasta = b.get("pasta") or sugerida
    linhas.append({"chave": "", "campo": "Pasta", "antes": "", "depois": _pasta_curta(pasta) if pasta else "falta escolher", "tom": "ok" if pasta else "aviso"})
    linhas.append({"chave": "", "campo": "Senha", "antes": "", "depois": "definida" if b.get("tem_senha") else "falta definir", "tom": "ok" if b.get("tem_senha") else "pendente"})
    return frase, linhas, {"pasta_sugerida": sugerida, "depois": "Guarde a senha fora deste computador: sem ela, ninguém abre o backup, nem você. "
                                                                "Uma pasta sincronizada protege até contra perder o computador."}


def _pasta_curta(pasta: str) -> str:
    """ "G:\\Meu Drive\\PAULUS Backup" -> "Google Drive › PAULUS Backup"."""
    m = re.match(r"^[A-Za-z]:\\(?:Meu Drive|My Drive)\\?(.*)$", pasta or "")
    if m:
        return "Google Drive" + (" › " + m.group(1).replace("\\", " › ") if m.group(1) else "")
    return pasta


def _proposta_word(dados: dict):
    w = dados.get("word") or {}
    ligado = bool(w.get("ligado"))
    inst = w.get("instalacao") or {}
    instalado = bool(inst.get("instalado"))
    carregado = bool(inst.get("carregado"))
    if not inst.get("word_no_computador", True):
        frase = "Não achei o Word neste computador. O PAVLVS funciona dentro do Word para Windows (2016 ou mais novo) ou do Word no navegador, pelo acesso externo."
    elif not ligado:
        frase = "O PAVLVS vem desligado de fábrica. São três passos e nenhum pede administrador. Abri a página Word ao lado."
    elif not instalado:
        frase = "O PAVLVS já está ligado, mas ainda não foi instalado no Word deste computador. São três passos e nenhum pede administrador. Abri a página Word ao lado."
    elif not carregado:
        frase = "O PAVLVS está ligado e instalado; falta abrir um documento no Word: o painel aparece sozinho na aba PAVLVS."
    else:
        frase = "O PAVLVS já está funcionando no Word deste computador. Abra o documento no Word e use \"Conferir citações\" na aba PAVLVS."
    passo = 1 if not ligado else 2 if not instalado else 3 if not carregado else 4
    passos = [
        {"titulo": "Ligar o PAVLVS", "sub": "o texto do documento vai só para este Paulus", "feito": ligado},
        {"titulo": "Instalar no Word", "sub": "o Windows vai perguntar se confia no certificado: clique em Sim", "feito": instalado},
        {"titulo": "Abrir o documento no Word", "sub": "o painel aparece sozinho, com \"Conferir citações\"", "feito": carregado},
    ]
    return frase, [], {"passos": passos, "passo": passo}


def _proposta_acesso(dados: dict):
    a = dados.get("acesso") or {}
    ligado = bool(a.get("ligado"))
    if ligado and a.get("contas"):
        frase = ("Consegue: o acesso externo já está ligado" + (f" em {a['hostname']}" if a.get("hostname") else "") +
                 ". Entre pelo navegador do celular com a sua conta e o código do Google Authenticator.")
    else:
        frase = "Consegue, pelo acesso externo. Ele vem desligado e só se liga daqui. Antes de ligar, o que muda:"
    pontos = [
        {"icone": "settings", "texto": "Este computador precisa ficar ligado e com o Paulus aberto enquanto você estiver fora."},
        {"icone": "verified", "texto": "Os documentos e o modelo de IA não saem daqui. Pela internet passa só a tela e o que você digita."},
        {"icone": "history", "texto": "Toda entrada fica registrada aqui: quem entrou, quando, o que abriu e o que baixou."},
    ]
    depois = "" if ligado and a.get("contas") else "Abri o Acesso externo ao lado com a sua conta de titular. Nada é criado antes de você confirmar."
    return frase, [], {"pontos": pontos, "depois": depois}


def _proposta_convite(pedido: dict, dados: dict):
    nome = pedido.get("nome") or ""
    email = pedido.get("email") or ""
    vinculado = bool(dados.get("vinculado"))
    primeiro = nome.split()[0] if nome else "A pessoa"
    frase = (f"{'A' if not primeiro.endswith('o') else 'O'} {primeiro} não precisa instalar nada: recebe o convite, entra com a conta Google "
             f"{'dela' if not primeiro.endswith('o') else 'dele'} e liga o Google Authenticator no celular.")
    linhas = []
    if not vinculado:
        frase += " Para mandar o convite, este Paulus precisa estar vinculado à sua conta Google, e ainda não está."
        linhas.append({"chave": "", "campo": "Conta Google deste Paulus", "antes": "", "depois": "não vinculada", "tom": "aviso"})
    linhas.append({"chave": "", "campo": nome or "A pessoa", "antes": "", "depois": "convite pronto · colaborador" + ("a" if not primeiro.endswith("o") else ""), "tom": "ok"})
    if not email:
        linhas.append({"chave": "", "campo": "E-mail Google", "antes": "", "depois": "falta informar", "tom": "aviso"})
    linhas.append({"chave": "", "campo": "O que " + ("ela" if not primeiro.endswith("o") else "ele") + " vê e faz", "antes": "", "depois": "escolhido em Permissões", "tom": "pendente"})
    acoes = [{"rotulo": "Abrir Cadastros › Equipe", "faz": "clicar", "seletor": "[data-cfg-equipe]"}]
    depois = ("Depois de vincular, o Paulus passa a abrir travado e pede o Google a cada abertura. Dá para manter aberto neste computador."
              if not vinculado else "O convite sai pelo botão ao lado; nada é enviado antes disso.")
    return frase, linhas, acoes, {"convite": {"nome": nome, "email": email}, "vinculado": vinculado, "depois": depois}


DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
DIAS_CURTOS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def recado_do_whatsapp(nome: str, recado: str, hoje: date | None = None) -> str:
    """ "a audiência foi remarcada pra quinta, 14h" -> "Olá, Wagner. A audiência foi remarcada para quinta-feira, 08/10, às 14h." """
    hoje = hoje or date.today()
    t = " ".join(_nfc(recado).split()).strip(" .")
    for a, b in ((r"\bpros\b", "para os"), (r"\bpras\b", "para as"), (r"\bpro\b", "para o"), (r"\bpra\b", "para"), (r"\btá\b", "está"),
                 (r"\bvc\b", "você"), (r"\bq\b", "que")):
        t = re.sub(a, b, t, flags=re.I)

    def dia(m):
        alvo = DIAS_CURTOS[_plano(m.group(1))]
        dias = (alvo - hoje.weekday()) % 7 or 7
        quando = hoje + timedelta(days=dias)
        return DIAS[alvo] + ", " + quando.strftime("%d/%m")

    t = re.sub(r"\b(segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)(?:-feira)?\b", dia, t, flags=re.I)
    t = re.sub(r",?\s*(?:às|as)?\s*\b(\d{1,2})\s*h(?:oras?)?\b(\s*\d{2})?", lambda m: ", às " + m.group(1) + "h" + (m.group(2) or "").strip(), t)
    t = re.sub(r"\bseu\b", "seu", t)
    corpo = t[:1].upper() + t[1:]
    primeiro = (nome or "").split()[0] if nome else ""
    return ("Olá, " + primeiro + ". " if primeiro else "Olá. ") + corpo + ". Qualquer dúvida, estou à disposição."


def _proposta_whatsapp(pedido: dict, dados: dict):
    w = pedido.get("whatsapp") or {}
    contato = dados.get("contato") or {}
    sessao = dados.get("sessao") or {}
    nome = contato.get("nome") or w.get("quem") or ""
    texto = recado_do_whatsapp(nome, w.get("recado") or "")
    partes = []
    if not contato:
        partes.append(f"Não achei \"{w.get('quem')}\" com telefone em Cadastros: o número você põe ao abrir a conversa.")
    if not sessao.get("existe"):
        partes.append("O WhatsApp Web ainda não está conectado nesta máquina. Abri Conexões ao lado: é só ler o QR com o celular uma vez, "
                      "e a sessão fica aqui. Enquanto isso, deixei a mensagem pronta; enviar continua sendo com você.")
    else:
        partes.append("Deixei a mensagem pronta. Abrir o WhatsApp Web, ao lado, já leva o texto escrito; enviar continua sendo com você.")
    acoes = [{"rotulo": "Copiar mensagem", "faz": "copiar", "icone": "content_copy"}]
    if contato.get("email"):
        acoes.append({"rotulo": "Mandar por e-mail", "faz": "pedir", "pedido": f"escreva um e-mail para {contato['nome']} dizendo: {texto}"})
    return " ".join(partes), {"mensagem": texto, "contato": contato, "conectado": bool(sessao.get("existe"))}, acoes
