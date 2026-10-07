"""
O que o PAULUS sabe de si mesmo - e a camada que decide antes do modelo.

A conversa tinha dois caminhos: as ações que a regra reconhece (anotar,
criar tarefa, cadastrar...) e, para todo o resto, a busca nos documentos.
"Quanto recebi este mês?", "abra o financeiro", "como assino um PDF?" iam
todas para dentro dos contratos, e voltavam com "não encontrei essa
informação nos trechos" - resposta certa para a pergunta errada. Medido em
26/09/2026: de 18 perguntas sobre o programa, 17 caíam na busca.

Esta camada responde três coisas, todas sem escrever com o modelo:

- **consulta** - o que o escritório gravou: compromissos de um dia, tarefas
  atrasadas, o mês do Financeiro, a fila de Aprovações, quantos cadastros.
  Quem conta é o banco, não o modelo.
- **ir** - "abra o financeiro": um botão que abre a tela.
- **como** - "como assino um PDF?": os passos, com os rótulos da tela, tirados
  do mapa em `programa_mapa.json`. O mapa foi montado lendo o código de cada
  tela, e o teste confere que os rótulos citados existem no arquivo indicado.

**O código é dono do fluxo** (o padrão do Jev, da TypeSafe). A regra monta os
candidatos; quando ela sozinha decide, o modelo nem é chamado. O modelo entra
só na dúvida, e só para ESCOLHER entre os candidatos que o código montou -
uma letra, com a probabilidade de cada uma (`juizo.py`). Nunca para escrever
a resposta.

**Na dúvida, o caminho de antes.** Sem modelo, com o modelo fora do ar ou com
a escolha abaixo do limiar, a pergunta segue para os documentos, como sempre
seguiu. A camada só acrescenta; o que funcionava continua funcionando.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

import destinos

MAPA_PATH = Path(__file__).with_name("programa_mapa.json")

# Acima disto o julgamento do modelo tira a pergunta dos documentos; abaixo,
# ela segue para lá. Medido em 26/09/2026 com tests/medir_juiz.py (llama3.2:3b,
# com a ordem das opções trocada): perguntas de documento ficaram entre 0,27 e
# 0,47; as do programa que a regra não resolvia, entre 0,42 e 0,61. O 3B
# separa pouco - por isso o limiar é conservador e quem decide quase tudo é a
# regra. Errar para o lado dos documentos é o comportamento de antes.
LIMIAR = 0.55

# As telas que o menu tem e o registro do servidor não lista (moram no
# frontend, em NOVOS_DESTINOS).
TELAS_EXTRAS = {
    "servicos": "Serviços",
    "gravacoes": "Gravações",
}

# C4 (chave `conversa.roteamento`): lugares do programa que não são destino do
# menu, mas que a pessoa chama pelo nome. Medido em 30/09/2026: "Pra que serve
# a busca no DJE?" caía na busca de documentos porque nenhum nome de tela
# casava. Cada um abre pelo frontend (abrirTelaDaConversa, js/08-destinos.js):
#   publicacoes - Agenda › To-do, filtro Publicações (js/48-publicacoes.js)
#   busca       - a caixa do Ctrl+K (js/50-busca.js + GET /api/busca)
#   leis        - Configurações › Assistente e modelo › Códigos de lei
#   acesso      - Configurações › Acesso externo (js/42-acesso.js)
# A tela "Agentes" ainda não existe: entra quando existir, não antes.
TELAS_C4 = {
    "publicacoes": ("Publicações",
                    "As comunicações do Diário de Justiça Eletrônico Nacional (DJEN) para as OABs do escritório, "
                    "com o prazo virando tarefa. Fica em Agenda › To-do."),
    "busca": ("Buscar em tudo",
              "Uma caixa, aberta com Ctrl+K, que procura em tudo: telas, ações e os dados do escritório."),
    "leis": ("Códigos de lei",
             "Os códigos instalados nesta máquina, do texto compilado do Planalto, para citar o artigo com o "
             "texto certo. Ficam em Configurações › Assistente e modelo."),
    "acesso": ("Acesso externo",
               "Usar o Paulus de casa ou do celular por um endereço paulus.ia.br, com o computador do escritório "
               "ligado. Fica em Configurações › Acesso externo."),
}

# Com a chave, o nome que a tela tem hoje: a seção de Configurações que o
# destino "habilidades" abre se chama Biblioteca desde a Biblioteca do
# escritório (M0-M7); "Aprendizado" não aparece mais em lugar nenhum da tela.
NOMES_C4 = {"habilidades": "Biblioteca"}
RESOLVE_C4 = {
    "habilidades": "O que o Paulus consulta para responder: livros, manuais e leis, com a fonte de cada um, e o "
                   "que o escritório ensinou com as próprias palavras, a Constituição, os códigos e as súmulas do STJ que vêm "
                   "com o Paulus, e o processo pelo número no DataJud. Fica na Biblioteca, no menu.",
}

# Pedido de 02/10/2026: "garanta que exista chamada para chegarmos em cada
# tela". As telas e seções que não eram destino do servidor: cada uma com o
# nome que a pessoa lê, o que faz e os outros nomes pelos quais é chamada.
# Valem sempre (não dependem da chave C4). O frontend abre cada uma em
# abrirTelaDaConversa (js/08-destinos.js); "config_<secao>" abre a seção de
# Configurações de mesmo nome. tests/test_navegacao.py confere que toda tela
# daqui tem quem a abra lá.
TELAS_NAVEGAVEIS = {
    "consumo": ("Plano e consumo",
                "Quanto o escritório usa da IA no ciclo, quem da equipe usa, os limites de uso, o plano e a recarga de "
                "tokens.",
                ("plano e consumo", "consumo", "consumo de tokens", "consumo da ia", "tokens", "meus tokens",
                 "meu plano", "limites de uso", "limite de tokens", "recarga de tokens", "upgrade do plano")),
    "notas": ("Notas fiscais",
              "As NFS-e do escritório: as emitidas para os clientes (com PDF, XML, cancelar e substituir) e as "
              "recebidas do PAVLVS pela assinatura.",
              ("notas fiscais", "nota fiscal", "notas emitidas", "notas recebidas", "nfs-e", "nfse",
               "minhas notas fiscais", "lista de notas fiscais")),
    "agentes": ("Agentes",
                "Os agentes do escritório - assistentes com instruções, fontes e ferramentas próprias - e as tarefas "
                "de vários passos.",
                ("agentes", "agente", "meus agentes", "tarefas de varios passos")),
    "avisos": ("Avisos",
               "Os avisos do dia: prazos, contas, compromissos e conversas que ficaram pela metade, com o histórico "
               "do que já foi visto.",
               ("avisos", "aviso", "meus avisos", "notificacoes", "central de avisos", "lembretes do dia")),
    "mais": ("Mais",
             "O menu do perfil e das Configurações. No celular, é o ☰ da barra de baixo.",
             ("menu", "menu mais", "mais", "menu de configuracoes", "menu do perfil")),
    "config_perfil": ("Meus dados", "Seus dados e os do escritório, que entram nos documentos que o Paulus gera.",
                      ("meus dados", "meu perfil", "perfil", "dados pessoais", "meu cadastro")),
    "config_vinculos": ("Escritório e equipe", "O escritório, a equipe e o que cada pessoa pode fazer.",
                        ("escritorio", "equipe", "escritorio e equipe", "minha equipe", "usuarios")),
    "config_assistente": ("Assistente e modelo", "Como o assistente responde e o modelo que ele usa.",
                          ("assistente e modelo", "configuracoes do assistente", "ajustes do assistente")),
    "config_modelos": ("Modelos", "Os modelos de linguagem desta máquina: baixar, trocar e medir.",
                       ("modelos", "modelos de linguagem", "modelos de ia", "modelo de ia")),
    "config_backup": ("Backup", "A cópia de segurança de tudo o que o escritório guarda neste computador.",
                      ("backup", "copia de seguranca", "backups")),
    "config_lixeira": ("Lixeira", "O que foi apagado fica aqui por 30 dias, com o caminho para voltar.",
                       ("lixeira", "itens apagados", "apagados", "arquivos apagados")),
    "config_aparencia": ("Aparência", "Tema, avisos do Windows e animações.",
                         ("aparencia", "tema", "aparencia e avisos", "modo escuro", "modo claro")),
    "config_menu": ("Módulos", "O que aparece no menu desta máquina.",
                    ("modulos", "modulo", "modulos do menu")),
    "config_plano": ("Versão", "A versão instalada, as atualizações e a licença.",
                     ("versao", "atualizacoes", "atualizacao", "sobre o paulus", "sobre")),
    "config_word": ("Word", "O PAVLVS dentro do Word: o painel que confere citações e insere trechos.",
                    ("word", "suplemento do word", "paulus no word", "complemento do word")),
    "config_feedback": ("Feedback", "Mandar uma sugestão ou um problema para quem faz o Paulus.",
                        ("feedback", "enviar feedback", "sugestao", "reportar problema")),
}

# Outros nomes de telas que já existiam, ditos do jeito que se fala.
APELIDOS_EXTRAS = {
    "conversa": ("inicio", "tela inicial", "pagina inicial", "assistente", "chat", "conversa"),
    "editor": ("editor de documentos", "editor de texto", "editor"),
    "calendario": ("agenda", "calendario", "minha agenda"),
    "biblioteca": ("acervo", "meus documentos", "documentos do escritorio"),
    "caixa": ("email", "e mail", "emails", "caixa de entrada", "meus emails"),
    "gravacoes": ("gravacoes", "gravacao", "minhas gravacoes", "reunioes gravadas"),
    "assinar": ("assinatura", "assinar", "assinaturas", "assinar documento"),
    "config": ("configuracoes", "configuracao", "ajustes", "preferencias"),
}

# Palavras que acompanham o nome da tela sem fazer parte dele: "a seção de
# Backup", "a lixeira do PAULUS".
SOBRA_DA_NAVEGACAO = {"paulus", "pavlvs", "sistema", "programa", "secao", "sessao", "area", "parte", "de",
                      "do", "da", "dos", "das", "e", "nas", "nos", "ele", "ela", "isso", "logo"}

NAO_E_TELA = ("busca e apreensao", "mandado de busca", "busca pessoal", "busca domiciliar", "busca de bens")

# A tela que mora dentro de outra: com as duas na frase ("as Publicações da
# Agenda"), vale a de dentro - é a mais específica.
DENTRO_DE = {"publicacoes": "calendario", "tarefas": "calendario", "agendamento": "calendario",
             "leis": "config", "acesso": "config", "habilidades": "config", "desempenho": "config",
             "conexoes": "config", "certificado": "assinar", "relatorios": "financeiro", "organizar": "biblioteca"}


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _palavras(plano: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", plano.replace("e-mail", "email"))


# O nome que a pessoa lê no menu. O registro de destinos ainda tem os nomes do
# manual ("Calendário", "Biblioteca", "Caixa de entrada"); o menu redesenhado
# diz "Agenda", "Acervo", "E-mail". Resposta que manda abrir "Biblioteca" manda
# procurar um botão que não existe.
NOMES_NO_MENU = {
    "conversa": "Assistente", "calendario": "Agenda", "agendamento": "Agenda",
    "biblioteca": "Acervo", "editor": "Editor de documentos", "assinar": "Assinatura",
    "caixa": "E-mail", "certificado": "Certificado digital", "habilidades": "Aprendizado",
}


def nome_da_tela(id_: str, ampliado: bool = False) -> str:
    if ampliado and id_ in NOMES_C4:
        return NOMES_C4[id_]
    if ampliado and id_ in TELAS_C4:
        return TELAS_C4[id_][0]
    if id_ in NOMES_NO_MENU:
        return NOMES_NO_MENU[id_]
    if id_ in TELAS_NAVEGAVEIS:
        return TELAS_NAVEGAVEIS[id_][0]
    d = destinos.obter(id_)
    return d.nome if d else TELAS_EXTRAS.get(id_, id_)


def telas_conhecidas(ampliado: bool = True) -> list[str]:
    """
    Na ordem do menu: com dois nomes iguais ("Agenda"), vence o primeiro.
    Sem `ampliado` (a chave `conversa.roteamento` desligada), só as de antes.
    """
    return ([d.id for d in destinos.DESTINOS] + list(TELAS_EXTRAS) + (list(TELAS_C4) if ampliado else [])
            + list(TELAS_NAVEGAVEIS))


# ----------------------------------------------------------------- sinais

# O que faz uma frase ser sobre um DOCUMENTO. Com uma destas, uma palavra de
# tela sozinha não basta para desviar a pergunta: "quanto vou receber de
# honorários no contrato?" é sobre o contrato.
ANCORAS_DE_DOCUMENTO = (
    "contrato", "contratos", "clausula", "clausulas", "procuracao", "peticao",
    "processo", "sentenca", "acordao", "aditivo", "vigencia", "rescisao",
    "contratante", "contratada", "contratado", "outorgante", "outorgado",
    "reu", "re", "autor", "autora", "reclamante", "reclamada", "multa",
    "documento", "documentos", "arquivo", "pdf", "notificacao", "escritura",
    "laudo", "parecer", "ata", "estatuto", "minuta", "anexo", "trecho",
    "segundo o", "de acordo com", "no texto", "foro", "testemunha",
    # Verbos de texto: quem pergunta onde algo "diz" ou "consta" está lendo.
    "onde diz", "diz que", "dizem que", "consta", "constam", "preve", "estabelece",
    "menciona", "esta escrito", "fala sobre",
)

# Dentro das âncoras, as que dizem "isto está escrito no documento". Com uma
# delas, nem a primeira pessoa tira a pergunta dos documentos: "o que tenho a
# receber segundo o contrato?" é leitura do contrato.
ANCORAS_DE_TEXTO = (
    "clausula", "clausulas", "trecho", "segundo o", "segundo a", "de acordo com",
    "no texto", "onde diz", "diz que", "dizem que", "consta", "constam", "preve",
    "estabelece", "menciona", "esta escrito", "fala sobre", "aponta", "determina",
)

# Quem fala de si fala dos próprios registros: "tenho reunião com o autor do
# processo?" é a agenda dele, não o processo. Medido: o 3B dava 0,47 para esta
# frase - do lado errado do limiar. Regra que sabe não pergunta ao modelo.
PRIMEIRA_PESSOA = (
    "tenho", "tive", "recebi", "recebemos", "paguei", "pagamos", "gastei", "gastamos",
    "marquei", "agendei", "anotei", "faturei", "faturamos", "minha agenda", "na minha agenda",
    "minhas tarefas", "meu dia", "meu caixa", "meu financeiro",
)

# Nomes que só existem no programa: nenhum contrato fala da "fila de
# aprovação" do escritório.
INEQUIVOCOS = {
    "agenda": ("na agenda", "minha agenda", "no calendario"),
    "tarefas": ("minhas tarefas", "meu dia", "lista de tarefas"),
    "financeiro": ("no financeiro", "meu caixa", "meu financeiro"),
    "aprovacoes": ("aprovacao pendente", "aprovacoes pendentes", "para eu aprovar", "pra eu aprovar",
                   "fila de aprovacao", "esperando minha decisao"),
}

INTERROGATIVAS = (
    "quais", "qual", "quanto", "quanta", "quantos", "quantas", "tenho", "tem",
    "ha", "existe", "existem", "estou", "o que", "me diga", "me fala",
    "liste", "listar", "lista", "mostre", "mostra", "me mostra", "me mostre",
    "ver", "veja", "resumo", "resuma", "como esta", "como estao", "como ficou",
)

# Verbos de ir a uma tela. "abra"/"mostre" também abrem documento: por isso
# a navegação só vale quando o que sobra da frase é o nome de uma tela.
VERBOS_IR = (
    "abra", "abre", "abrir", "va", "vai", "ir", "leve", "leva", "entre",
    "entrar", "acesse", "acessar", "mostre", "mostra", "mostrar", "exiba",
    "exibe", "exibir", "quero", "abrir", "me", "volte", "voltar", "volta", "veja", "ver", "vamos", "bora",
    "navegue", "navegar", "levar", "leve", "ir",
)
PREENCHIMENTO = {
    "o", "a", "os", "as", "de", "do", "da", "dos", "das", "para", "pra", "pro",
    "no", "na", "em", "tela", "pagina", "aba", "me", "meu", "minha", "meus",
    "minhas", "por", "favor", "pf", "voce", "pode", "poderia", "consegue",
    "ai", "ali", "aqui", "agora", "ver", "um", "uma", "ao", "aos", "ate",
}

_ABERTURA = (r"^(?:(?:e|mas|entao|ok|oi|ola|bom dia|boa tarde|boa noite|por favor)[, ]+)?"
             r"(?:(?:voce )?(?:sabe|pode me dizer|pode me explicar|me explica|me ensina|me diga|"
             r"quero saber|queria saber|gostaria de saber) )?")

# "como assino", "como faço para lançar", "tem como", "dá para": pedido de
# caminho. O verbo depois do "como" é o da pessoa - primeira pessoa ou
# infinitivo. "como está o prazo do contrato?" e "como isso funciona no
# contrato?" não são: terceira pessoa e pronome ficam de fora.
RE_COMO_FAZER = re.compile(
    _ABERTURA +
    r"(?:(?:como|de que jeito|qual o jeito de|qual o caminho para)\s+"
    r"(?:eu\s+|a gente\s+|que eu\s+|se\s+|faco\s+(?:para|pra)\s+|faz\s+(?:para|pra)\s+|"
    r"posso\s+|consigo\s+|devo\s+|fazer\s+(?:para|pra)\s+|da\s+(?:para|pra)\s+)?"
    r"(?!isso\b|isto\b|aquilo\b|esta\b|estao\b|fica\b|ficou\b|e\b|foi\b|sera\b|seria\b|era\b)"
    r"[a-z]{2,}(?:ar|er|ir|o)\b"
    r"|(?:tem como|da para|da pra|e possivel|eu consigo|consigo|posso|onde eu posso)\b)"
)

# "mude o tema para escuro": ordem de ajuste que o programa não executa pela
# conversa - mas sabe dizer onde se faz.
RE_ORDEM_DE_AJUSTE = re.compile(
    _ABERTURA + r"(?:mude|mudar|troque|trocar|ative|ativar|ligue|ligar|desligue|desligar|"
    r"configure|configurar|altere|alterar|deixe|deixar|coloque|colocar|ponha|habilite|desabilite)\b"
)

RE_ONDE = re.compile(_ABERTURA + r"(?:onde|aonde|em que lugar|em que tela|qual tela)\b")

# "o que é a tela de aprovações?", "para que serve o Acervo?"
RE_O_QUE_E = re.compile(
    _ABERTURA + r"(?:o que e|o que sao|o que faz|para que serve|pra que serve|para que servem|"
    r"pra que servem|qual a funcao)\b"
)

# Com a chave, "como funciona o acesso de fora?" também pede a explicação da
# tela. Sem tela citada a frase continua indo para o "o que eu faço" de
# intencao.SOBRE, como antes.
RE_O_QUE_E_C4 = re.compile(
    _ABERTURA + r"(?:o que e|o que sao|o que faz|o que fazem|para que serve|pra que serve|para que servem|"
    r"pra que servem|qual a funcao|qual a utilidade|como funciona|como funcionam|serve para que|serve pra que)\b"
)


def _tem_palavra(plano: str, termos) -> str:
    for t in termos:
        if " " in t:
            if t in plano:
                return t
        elif re.search(r"\b" + re.escape(t) + r"\b", plano):
            return t
    return ""


def ancora_de_documento(plano: str) -> str:
    return _tem_palavra(plano, ANCORAS_DE_DOCUMENTO)


def _pergunta_ou_lista(plano: str) -> bool:
    return plano.rstrip().endswith("?") or bool(_tem_palavra(plano, INTERROGATIVAS))


# -------------------------------------------------------------- consultas

# Cada consulta: as palavras que a chamam, a tela onde o dado mora e a função
# que conta. `forte` é o que decide sozinho; `fraco` precisa de mais contexto
# (uma interrogativa, e nenhuma âncora de documento).
CONSULTAS = {
    "agenda": {
        "tela": "calendario",
        "descricao": "os compromissos gravados na Agenda do programa num dia ou período",
        "forte": ("compromisso", "compromissos", "reuniao", "reunioes", "audiencia", "audiencias",
                  "na agenda", "minha agenda", "agendado", "agendada", "agendados", "marcado", "marcada",
                  "marcados", "estou livre", "tenho livre", "horario livre"),
        "fraco": ("o que tenho", "tenho algo", "tenho alguma coisa", "agenda"),
    },
    "tarefas": {
        "tela": "tarefas",
        "descricao": "as tarefas gravadas no programa (atrasadas, de hoje ou em aberto)",
        "forte": ("tarefa", "tarefas", "pendencia", "pendencias", "a fazer", "para fazer",
                  "pra fazer", "meu dia"),
        "fraco": ("atrasada", "atrasadas", "atrasado", "atrasados", "vencendo", "vencidas"),
    },
    "financeiro": {
        "tela": "financeiro",
        "descricao": "os lançamentos do Financeiro do programa: o que entrou e saiu no mês e o que está em aberto",
        "forte": ("recebi", "recebemos", "faturei", "faturamos", "faturamento", "paguei", "pagamos",
                  "gastei", "gastamos", "gastos", "contas a pagar", "contas a receber", "a receber",
                  "a pagar", "saldo", "entrou", "entraram", "saiu", "sairam", "financeiro",
                  "fluxo de caixa", "despesas", "receitas", "inadimplente", "inadimplentes",
                  "pagamento atrasado", "pagamentos atrasados", "recebimento atrasado", "recebimentos atrasados",
                  "honorarios atrasados", "cobranca atrasada", "cobrancas atrasadas", "em atraso", "devendo",
                  "quem me deve", "quem esta devendo"),
        "fraco": ("honorarios", "despesa", "receita", "pagamento", "pagamentos", "receber", "pagar",
                  "dinheiro", "caixa"),
    },
    "aprovacoes": {
        "tela": "aprovacoes",
        "descricao": "a fila de Aprovações: pedidos que esperam a decisão da pessoa",
        "forte": ("aprovacao", "aprovacoes", "aprovar", "para eu aprovar", "pra eu aprovar",
                  "esperando minha decisao", "para eu decidir", "pra eu decidir"),
        "fraco": (),
    },
    # "O que tenho para hoje?": compromissos E tarefas do dia, juntos. Medido
    # no banco de provas (27/09/2026): "o que tenho" era palavra fraca da
    # agenda sozinha, e a pergunta ia procurar nos contratos.
    "dia": {
        "tela": "calendario",
        "descricao": "o que está marcado e o que vence num dia: compromissos e tarefas",
        "forte": ("o que tenho para hoje", "o que tenho pra hoje", "o que tenho hoje", "o que tenho para amanha",
                  "o que tenho pra amanha", "o que tenho amanha", "o que tem para hoje", "o que tem pra hoje",
                  "como esta meu dia", "como esta o meu dia", "minha agenda de hoje", "minha agenda hoje",
                  "o que vence hoje", "o que vence amanha", "resumo do dia", "resumo de hoje", "meu dia de hoje",
                  "o que tenho para fazer hoje", "o que tenho pra fazer hoje", "o que fazer hoje"),
        "fraco": (),
    },
    "servicos": {
        "tela": "servicos",
        "descricao": "os serviços (pastas de trabalho) em andamento e em que pé estão",
        "forte": ("servicos em andamento", "meus servicos", "quais servicos", "servicos abertos", "servicos ativos",
                  "casos em andamento", "como estao os servicos", "andamento dos servicos", "servicos do escritorio"),
        "fraco": ("servicos",),
    },
    "certificado": {
        "tela": "certificado",
        "descricao": "o certificado digital cadastrado: de quem é e até quando vale",
        "forte": ("meu certificado", "certificado vence", "vence o meu certificado", "vence o certificado",
                  "validade do certificado", "certificado esta vencido", "certificado venceu", "certificado valido",
                  "o certificado ainda vale", "certificado digital vence"),
        "fraco": (),
    },
    "cadastros": {
        "tela": "cadastros",
        "descricao": "quantas fichas há em Cadastros (clientes, colaboradores, sócios)",
        "forte": ("quantos clientes", "quantas clientes", "clientes cadastrados", "quantos cadastros",
                  "quantas fichas", "lista de clientes", "meus clientes", "nossos clientes",
                  "quantos colaboradores"),
        "fraco": ("clientes", "cadastros", "cadastrados"),
    },
}

# "caixa de entrada" é o e-mail, não o caixa do escritório.
NAO_E_FINANCEIRO = ("caixa de entrada",)


def _hoje(hoje: date | None) -> date:
    return hoje or date.today()


def _dia_curto(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    semana = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")[d.weekday()]
    return f"{semana}, {d.day:02d}/{d.month:02d}"


def periodo(plano: str, hoje: date | None = None) -> tuple[str, str, str]:
    """
    O período da pergunta: (de, até, como dizer). Sem período escrito, os
    próximos sete dias - "quais compromissos tenho?" quer o que vem.
    """
    import intencao

    h = _hoje(hoje)
    if re.search(r"\b(proxima semana|semana que vem)\b", plano):
        inicio = h + timedelta(days=7 - h.weekday())
        return inicio.isoformat(), (inicio + timedelta(days=6)).isoformat(), "na semana que vem"
    if re.search(r"\b(essa|esta|nesta|nessa) semana\b", plano) or re.search(r"\bda semana\b", plano):
        fim = h + timedelta(days=6 - h.weekday())
        return h.isoformat(), fim.isoformat(), "até o fim desta semana"
    if re.search(r"\b(esse|este|neste|nesse) mes\b", plano):
        prox = (h.replace(day=28) + timedelta(days=4)).replace(day=1)
        return h.isoformat(), (prox - timedelta(days=1)).isoformat(), "até o fim do mês"
    dia, bruto = intencao.ler_data(plano, h)
    if dia:
        rotulo = {"hoje": "hoje", "amanhã": "amanhã", "depois de amanhã": "depois de amanhã"}.get(bruto, "")
        return dia, dia, (rotulo + " (" + _dia_curto(dia) + ")") if rotulo else "em " + _dia_curto(dia)
    return h.isoformat(), (h + timedelta(days=6)).isoformat(), "nos próximos 7 dias"


def _mes(plano: str, hoje: date | None = None) -> str:
    import intencao

    h = _hoje(hoje)
    if re.search(r"\bmes passado\b", plano):
        anterior = h.replace(day=1) - timedelta(days=1)
        return anterior.strftime("%Y-%m")
    for nome, numero in intencao.MESES.items():
        if re.search(r"\b(em|de|no mes de) " + nome + r"\b", plano):
            ano = h.year if numero <= h.month else h.year - 1
            return f"{ano}-{numero:02d}"
    return h.strftime("%Y-%m")


def _consultar_agenda(dados, plano: str, hoje: date | None) -> str:
    de, ate, dito = periodo(plano, hoje)
    itens = dados.agenda.listar(de, ate)
    if not itens:
        return f"Nada marcado na Agenda {dito}."
    linhas = [f"{len(itens)} compromisso{'s' if len(itens) > 1 else ''} {dito}:"]
    for c in itens[:12]:
        onde = c.get("onde_rotulo") or ""
        quem = c.get("cadastro_nome") or ""
        extra = " · ".join(x for x in (quem, onde if onde != "Sem local" else "") if x)
        dia = "" if de == ate else _dia_curto(c["data"]) + " "
        linhas.append(f"  {dia}{c['hora']}–{c['fim']}  {c['titulo']}" + (f" · {extra}" if extra else ""))
    if len(itens) > 12:
        linhas.append(f"  e mais {len(itens) - 12} na Agenda.")
    return "\n".join(linhas)


def _consultar_tarefas(dados, plano: str, hoje: date | None) -> str:
    h = _hoje(hoje).isoformat()
    abertas = dados.tarefas.listar("todas")
    if re.search(r"\b(atrasad[ao]s?|vencid[ao]s?|passou|passaram)\b", plano):
        itens = [t for t in abertas if t.get("prazo") and t["prazo"] < h]
        dito = "atrasada"
    elif re.search(r"\b(hoje|meu dia)\b", plano):
        itens = dados.tarefas.listar("meu_dia")
        dito = "para hoje (Meu dia, com o que vence hoje ou já venceu)"
    else:
        itens = abertas
        dito = "em aberto"
    if not itens:
        return f"Nenhuma tarefa {dito.split(' (')[0]}."
    plural = "s" if len(itens) > 1 else ""
    if dito == "atrasada":
        cabeca = f"{len(itens)} tarefa{plural} atrasada{plural}:"
    else:
        cabeca = f"{len(itens)} tarefa{plural} {dito}:"
    linhas = [cabeca]
    for t in itens[:10]:
        quem = f" · {t['cadastro_nome']}" if t.get("cadastro_nome") else ""
        linhas.append(f"  {t['titulo']} — {t.get('situacao', '')}{quem}")
    if len(itens) > 10:
        linhas.append(f"  e mais {len(itens) - 10} em Tarefas.")
    return "\n".join(linhas)


RE_ATRASO = re.compile(r"\b(atrasad\w*|em atraso|devendo|inadimplen\w*|me deve|vencid\w*)\b")


def _consultar_atrasados(dados, hoje: date | None) -> str:
    """Quem está devendo: os recebimentos vencidos e ainda em aberto, com o cliente."""
    itens = [l for l in dados.financeiro.listar(tipo="recebimento") if l.get("atrasado")]
    if not itens:
        return "Nenhum recebimento atrasado no Financeiro."
    itens.sort(key=lambda l: -int(l.get("dias_atraso") or 0))
    total = sum(int(l.get("centavos") or 0) for l in itens)
    import financeiro as fin_mod

    linhas = [f"{len(itens)} recebimento{'s' if len(itens) > 1 else ''} atrasado{'s' if len(itens) > 1 else ''}, "
              f"{fin_mod.em_reais(total)} no total:"]
    for l in itens[:10]:
        quem = l.get("cadastro_nome") or "sem cliente"
        linhas.append(f"  {quem} — {l['descricao']} · {l['valor']} · {l.get('situacao', '')}")
    if len(itens) > 10:
        linhas.append(f"  e mais {len(itens) - 10} no Financeiro.")
    return "\n".join(linhas)


def _consultar_financeiro(dados, plano: str, hoje: date | None) -> str:
    if RE_ATRASO.search(plano):
        return _consultar_atrasados(dados, hoje)
    mes = _mes(plano, hoje)
    p = dados.financeiro.painel(mes)
    if not p.get("tem_dado"):
        return "O Financeiro ainda não tem lançamentos."
    linhas = [
        f"Em {p['mes_rotulo']}: entrou {p['entradas_mes_texto']} e saiu {p['saidas_mes_texto']} "
        f"(resultado {p['resultado_mes_texto']}).",
        f"Em aberto, somando todos os meses: a receber {p['a_receber_texto']} "
        f"({p['a_receber_quantos']} lançamento{'s' if p['a_receber_quantos'] != 1 else ''}), "
        f"a pagar {p['a_pagar_texto']} ({p['a_pagar_quantos']}).",
    ]
    if p.get("atrasado_quantos"):
        linhas.append(f"Recebimentos atrasados: {p['atrasado_texto']} ({p['atrasado_quantos']}).")
    linhas.append(f"Saldo em caixa (o que já entrou menos o que já saiu): {p['saldo_texto']}.")
    return "\n".join(linhas)


def _consultar_aprovacoes(dados, plano: str, hoje: date | None) -> str:
    pendentes = dados.fila.pendentes
    if not pendentes:
        return "Nada esperando a sua decisão em Aprovações."
    linhas = [f"{len(pendentes)} pedido{'s' if len(pendentes) > 1 else ''} esperando a sua decisão:"]
    for p in pendentes[:8]:
        prazo = " · prazo hoje" if p.vence_hoje else ""
        linhas.append(f"  {p.titulo} ({p.categoria_rotulo}){prazo}")
    if len(pendentes) > 8:
        linhas.append(f"  e mais {len(pendentes) - 8} em Aprovações.")
    return "\n".join(linhas)


def _consultar_cadastros(dados, plano: str, hoje: date | None) -> str:
    import cadastros as mod

    conta = dados.cadastros.contagem()
    partes = [f"{conta[t]} em {rotulo}" for t, rotulo in mod.TIPOS.items() if conta.get(t)]
    total = sum(conta.values())
    if not total:
        return "Cadastros ainda não tem nenhuma ficha."
    return f"{total} ficha{'s' if total != 1 else ''} em Cadastros: " + ", ".join(partes) + "."


def _consultar_dia(dados, plano: str, hoje: date | None) -> str:
    """Compromissos e tarefas do dia, numa resposta só."""
    h = _hoje(hoje)
    de, ate, dito = periodo(plano, hoje)
    compromissos = dados.agenda.listar(de, ate)
    abertas = dados.tarefas.listar("todas")
    if de == ate == h.isoformat():
        # Hoje é o "Meu dia" da tela: o que vence hoje, o que já venceu e o
        # que a pessoa trouxe para o dia.
        tarefas = dados.tarefas.listar("meu_dia")
    else:
        tarefas = [t for t in abertas if t.get("prazo") and de <= t["prazo"] <= ate]
    if not compromissos and not tarefas:
        return f"Nada marcado nem vencendo {dito}."
    linhas = [dito[0].upper() + dito[1:] + ":"]
    if compromissos:
        linhas.append("Compromissos")
        for c in compromissos[:10]:
            dia = "" if de == ate else _dia_curto(c["data"]) + " "
            linhas.append(f"  {dia}{c['hora']}–{c['fim']}  {c['titulo']}")
    if tarefas:
        linhas.append("Tarefas")
        for t in tarefas[:10]:
            linhas.append(f"  {t['titulo']} — {t.get('situacao', '')}")
    return "\n".join(linhas)


def _consultar_servicos(dados, plano: str, hoje: date | None) -> str:
    itens = dados.servicos.listar("andamento")
    if not itens:
        return "Nenhum serviço em andamento."
    linhas = [f"{len(itens)} serviço{'s' if len(itens) > 1 else ''} em andamento:"]
    for s in itens[:10]:
        partes = [s.get("cliente_nome") or "sem cliente", s.get("status_rotulo", "")]
        etapas = s.get("etapas") or []
        if etapas:
            partes.append(f"{s.get('etapas_feitas', 0)} de {len(etapas)} etapas")
            proxima = next((e for e in etapas if not e.get("feita")), None)
            if proxima:
                quando = f" ({_dia_curto(proxima['quando'])})" if proxima.get("quando") else ""
                partes.append("próxima: " + str(proxima.get("titulo", "")) + quando)
        linhas.append(f"  {s['nome']} — " + " · ".join(p for p in partes if p))
    if len(itens) > 10:
        linhas.append(f"  e mais {len(itens) - 10} em Serviços.")
    return "\n".join(linhas)


def _consultar_certificado(dados, plano: str, hoje: date | None) -> str:
    cert = dados.cofre.certificado() if getattr(dados.cofre, "instalado", False) else None
    if not cert:
        return "Nenhum certificado digital cadastrado. Ele entra em Assinatura › Certificado digital."
    if getattr(cert, "erro", ""):
        return "Há um certificado cadastrado, mas " + cert.erro + "."
    dias = cert.dias_restantes
    quanto = ""
    if dias is not None:
        quanto = f" — venceu há {-dias} dia(s)" if dias < 0 else f" — faltam {dias} dia(s)"
    return (f"Certificado de {cert.titular or 'titular não identificado'}, emitido por {cert.emissor or '—'}, "
            f"válido até {cert.valido_ate or '—'}{quanto}.")


EXECUTORES = {
    "dia": _consultar_dia,
    "servicos": _consultar_servicos,
    "certificado": _consultar_certificado,
    "agenda": _consultar_agenda,
    "tarefas": _consultar_tarefas,
    "financeiro": _consultar_financeiro,
    "aprovacoes": _consultar_aprovacoes,
    "cadastros": _consultar_cadastros,
}


# ------------------------------------------------------------------- mapa


@dataclass
class TarefaDoMapa:
    destino: str
    pergunta: str
    palavras: list[str]
    passos: list[str]
    evidencia: str = ""
    c4: bool = False           # só com a chave conversa.roteamento


@dataclass
class TelaDoMapa:
    destino: str
    apelidos: list[str] = field(default_factory=list)
    faz: list[str] = field(default_factory=list)
    nao_faz: list[str] = field(default_factory=list)
    tarefas: list[TarefaDoMapa] = field(default_factory=list)
    c4: bool = False           # a tela inteira só existe no mapa com a chave
    apelidos_c4: list[str] = field(default_factory=list)       # entram com a chave
    apelidos_fora_c4: list[str] = field(default_factory=list)  # saem com a chave


_MAPA: dict[str, TelaDoMapa] | None = None
_MAPAS: dict[bool, dict[str, TelaDoMapa]] = {}

# Linhas do mapa que dependem do estado do programa: "{nfse:emite} ..." só vale
# quando a NFS-e está ligada e o município emite pelo nacional; "{nfse:nao_emite}
# ..." só no contrário (src/nfse, N9). Quem sabe o estado pendura a função aqui
# (src/rotas_nfse.py); sem ninguém, a emissão conta como desligada.
CONDICOES: dict = {}


def _condicao(marca: str) -> bool:
    if marca == "nfse:emite":
        f = CONDICOES.get("nfse:emite")
        try:
            return bool(f()) if f else False
        except Exception:  # noqa: BLE001 - estado que falha não derruba o mapa
            return False
    if marca == "nfse:nao_emite":
        return not _condicao("nfse:emite")
    return True


def linhas_que_valem(linhas: list[str]) -> list[str]:
    """As linhas do mapa que valem agora, sem a marca da condição."""
    saida = []
    for l in linhas:
        if l.startswith("{") and "}" in l:
            marca, _, texto = l[1:].partition("}")
            if not _condicao(marca):
                continue
            l = texto.strip()
        saida.append(l)
    return saida


def mapa(caminho: Path | None = None) -> dict[str, TelaDoMapa]:
    """
    O mapa das telas inteiro, lido uma vez - com o que só vale com a chave
    `conversa.roteamento` marcado (`c4`). Quem responde usa `mapa_para`.
    Sem o arquivo, o mapa é vazio e o "como" não responde.
    """
    global _MAPA
    if _MAPA is not None and caminho is None:
        return _MAPA
    alvo = caminho or MAPA_PATH
    telas: dict[str, TelaDoMapa] = {}
    if alvo.exists():
        bruto = json.loads(alvo.read_text(encoding="utf-8"))
        for t in bruto.get("telas", []):
            tela = TelaDoMapa(
                destino=t["destino"], apelidos=t.get("apelidos", []), faz=t.get("faz", []),
                nao_faz=t.get("nao_faz", []),
                tarefas=[TarefaDoMapa(destino=t["destino"], pergunta=x["pergunta"],
                                      palavras=x.get("palavras", []), passos=x.get("passos", []),
                                      evidencia=x.get("evidencia", ""), c4=bool(x.get("c4")))
                         for x in t.get("tarefas", [])],
                c4=bool(t.get("c4")), apelidos_c4=t.get("apelidos_c4", []),
                apelidos_fora_c4=t.get("apelidos_fora_c4", []),
            )
            telas[tela.destino] = tela
    if caminho is None:
        _MAPA = telas
    return telas


def mapa_para(ampliado: bool) -> dict[str, TelaDoMapa]:
    """
    O mapa que responde. Sem a chave, exatamente o de antes da C4: sem as
    telas, as perguntas e os apelidos que ela trouxe. Com a chave, tudo, e o
    Acervo deixa de atender por "biblioteca" (a Biblioteca agora é outra).
    """
    if ampliado in _MAPAS and _MAPAS[ampliado] and _MAPA is not None:
        return _com_condicoes(_MAPAS[ampliado])
    saida: dict[str, TelaDoMapa] = {}
    for id_, tela in mapa().items():
        if tela.c4 and not ampliado:
            continue
        apelidos = list(tela.apelidos)
        if ampliado:
            apelidos = [a for a in apelidos if a not in tela.apelidos_fora_c4] + list(tela.apelidos_c4)
        saida[id_] = TelaDoMapa(
            destino=tela.destino, apelidos=apelidos, faz=tela.faz, nao_faz=tela.nao_faz,
            tarefas=[t for t in tela.tarefas if ampliado or not t.c4], c4=tela.c4,
        )
    _MAPAS[ampliado] = saida
    return _com_condicoes(saida)


def _com_condicoes(telas: dict[str, TelaDoMapa]) -> dict[str, TelaDoMapa]:
    """O mapa com as linhas condicionais resolvidas agora (o estado muda em uso)."""
    return {k: TelaDoMapa(destino=t.destino, apelidos=t.apelidos, faz=linhas_que_valem(t.faz),
                          nao_faz=linhas_que_valem(t.nao_faz), tarefas=t.tarefas, c4=t.c4,
                          apelidos_c4=t.apelidos_c4, apelidos_fora_c4=t.apelidos_fora_c4)
            for k, t in telas.items()}


SUFIXOS = ("amentos", "imentos", "amento", "imento", "atura", "acoes", "icoes", "acao", "icao",
           "coes", "cao", "mente", "ando", "endo", "indo", "ados", "adas", "idos", "idas", "ado",
           "ada", "ido", "ida", "amos", "emos", "imos", "aram", "eram", "iram", "oes", "ao",
           "ar", "er", "ir", "ei", "ou", "eu", "iu", "as", "es", "os", "a", "e", "o", "s")


def _raiz(p: str) -> str:
    """
    Raiz grosseira do português: 'assino', 'assinar', 'assinatura' -> 'assin';
    'gravo', 'gravar', 'gravação' -> 'grav'. Nunca abaixo de 4 letras: 'conta'
    e 'contrato' não podem virar a mesma coisa.
    """
    for s in SUFIXOS:
        if p.endswith(s) and len(p) - len(s) >= 4:
            return p[: -len(s)]
    return p


VAZIAS = PREENCHIMENTO | {"como", "onde", "eu", "que", "e", "se", "faco", "faz", "fazer", "posso",
                          "consigo", "devo", "la", "isso", "isto", "algum", "alguma", "tem", "ter",
                          "com", "sem", "ao", "aos", "qual", "quais", "vejo", "fica", "ficam",
                          "esta", "estao", "encontro", "acho", "programa", "paulus", "sistema"}


def _pontos(frase_raizes: set[str], plano: str, termos: list[str]) -> float:
    """
    Quanto a frase casa com os termos. Termo de uma palavra vale 1; de várias,
    1,5 quando todas as raízes estão na frase ("lançar despesa" casa com
    "como lanço uma despesa"). Cada raiz da frase conta uma vez só.
    """
    pontos = 0.0
    usadas: set[str] = set()
    for termo in sorted(termos, key=lambda x: -len(x.split())):
        if termo.startswith("="):
            # Termo que só vale escrito assim, junto (C4): "=paulus de casa"
            # não casa com "como uso a casa como garantia?", que tem as
            # mesmas raízes em outra ordem.
            exato = _plano(termo[1:]).strip()
            if exato and re.search(r"(?<![a-z0-9])" + re.escape(exato) + r"(?![a-z0-9])", plano):
                raizes = [_raiz(p) for p in _palavras(exato) if p not in VAZIAS]
                if not all(r in usadas for r in raizes):
                    pontos += 1.5
                    usadas.update(raizes)
            continue
        raizes = [_raiz(p) for p in _palavras(_plano(termo).replace("-", "")) if p not in VAZIAS]
        if not raizes:
            continue
        if len(raizes) > 1:
            if all(r in frase_raizes for r in raizes) and not all(r in usadas for r in raizes):
                pontos += 1.5
                usadas.update(raizes)
        elif raizes[0] in frase_raizes and raizes[0] not in usadas:
            pontos += 1.0
            usadas.add(raizes[0])
    return pontos


RE_VERBO_DO_COMO = re.compile(
    r"\bcomo\s+(?:eu\s+|a gente\s+|que eu\s+|se\s+|faco\s+(?:para|pra)\s+|"
    r"faz\s+(?:para|pra)\s+|posso\s+|consigo\s+|devo\s+|fazer\s+(?:para|pra)\s+)?"
    r"([a-z]{2,}(?:ar|er|ir|o))\b"
)


def _verbo_do_como(plano: str) -> str:
    """O verbo da pessoa em "como faço para imprimir", "como assino": a raiz."""
    m = RE_VERBO_DO_COMO.search(plano)
    if not m or m.group(1) in ("faco", "fazer", "posso", "consigo", "devo"):
        return ""
    return _raiz(m.group(1))


def _candidatos_como(plano: str, telas: dict[str, TelaDoMapa]) -> list[tuple[float, TarefaDoMapa, bool]]:
    raizes = {_raiz(p) for p in _palavras(plano) if p not in VAZIAS}
    verbo = _verbo_do_como(plano)
    achados = []
    for tela in telas.values():
        bonus = 0.5 if _pontos(raizes, plano, tela.apelidos) else 0.0
        for tarefa in tela.tarefas:
            pts = _pontos(raizes, plano, tarefa.palavras)
            if pts:
                da_tarefa = {_raiz(p) for termo in tarefa.palavras for p in _palavras(_plano(termo))}
                achados.append((pts + bonus, tarefa, bool(verbo) and verbo in da_tarefa))
    achados.sort(key=lambda x: -x[0])
    return achados


def _tela_citada(plano: str, telas: dict[str, TelaDoMapa], ampliado: bool = False) -> str:
    """A tela cujo nome ou apelido a frase escreve - só quando é uma."""
    if ampliado:
        return _tela_citada_c4(plano, telas)
    achadas: dict[str, None] = {}
    for id_ in telas_conhecidas(False):
        nomes = [nome_da_tela(id_)] + (telas[id_].apelidos if id_ in telas else [])
        for n in nomes:
            n = _plano(n)
            if n and re.search(r"\b" + re.escape(n) + r"\b", plano):
                achadas.setdefault(id_)
    # "Agenda" é o nome de duas visões; conta como uma tela só.
    unicas = list(dict.fromkeys(NOMES_NO_MENU.get(a, a) for a in achadas))
    return next(iter(achadas)) if len(unicas) == 1 else ""


def _tela_citada_c4(plano: str, telas: dict[str, TelaDoMapa]) -> str:
    """
    Com a chave, duas regras a mais para quando a frase escreve mais de uma:

    - o nome de dentro de outro não conta: em "a busca no DJE", "busca" é
      parte de "busca no DJE" (Publicações), e não a caixa do Ctrl+K;
    - tela dentro de tela vale a de dentro: "as Publicações da Agenda" é
      Publicações.
    """
    achados: list[tuple[str, int, int]] = []
    # Termo jurídico que contém um nome de tela não é a tela: "busca e
    # apreensão" cobre o "busca" de dentro, e o que sobra não cita nada.
    for termo in NAO_E_TELA:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(termo) + r"(?![a-z0-9])", plano):
            achados.append(("", m.start(), m.end()))
    for id_ in telas_conhecidas(True):
        nomes = [nome_da_tela(id_, True)] + (telas[id_].apelidos if id_ in telas else [])
        for n in nomes:
            n = _plano(n)
            if not n:
                continue
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", plano):
                achados.append((id_, m.start(), m.end()))
    inteiros = [a for a in achados
                if not any(b[0] != a[0] and b[1] <= a[1] and a[2] <= b[2] and (b[2] - b[1]) > (a[2] - a[1])
                           for b in achados)]
    ids = list(dict.fromkeys(a[0] for a in inteiros if a[0]))
    # "Agenda" é o nome de duas visões; conta como uma tela só.
    unicas = list(dict.fromkeys(NOMES_NO_MENU.get(a, a) if a in ("calendario", "agendamento") else a for a in ids))
    if len(unicas) > 1:
        de_dentro = [a for a in ids if DENTRO_DE.get(a) in ids]
        if len(de_dentro) == 1:
            return de_dentro[0]
        return ""
    return ids[0] if ids else ""


def texto_do_como(tarefa: TarefaDoMapa) -> str:
    linhas = [tarefa.pergunta.rstrip("?") + ":"]
    linhas += [f"  {i}. {p}" for i, p in enumerate(tarefa.passos, 1)]
    return "\n".join(linhas)


def texto_da_tela(id_: str, telas: dict[str, TelaDoMapa], ampliado: bool = False) -> str:
    d = destinos.obter(id_)
    nome = nome_da_tela(id_, ampliado)
    resolve = (RESOLVE_C4.get(id_) or (TELAS_C4.get(id_) or ("", ""))[1]) if ampliado else ""
    resolve = resolve or (d.resolve if d else "") or (TELAS_NAVEGAVEIS.get(id_) or ("", ""))[1]
    linhas = [f"{nome}: {resolve}" if resolve else nome + "."]
    tela = telas.get(id_)
    if tela and tela.faz:
        linhas += ["", "O que dá para fazer lá:"] + [f"  · {f}" for f in tela.faz[:6]]
    if tela and tela.tarefas:
        linhas += ["", "Pergunte, por exemplo: " + " · ".join(f"“{t.pergunta}”" for t in tela.tarefas[:3])]
    return "\n".join(linhas)


# ---------------------------------------------------------------- leitura


@dataclass
class Leitura:
    tipo: str                  # "consulta" | "ir" | "como"
    destino: str               # id da tela
    texto: str = ""            # a resposta pronta (vazia no "ir")
    porque: str = ""           # de onde veio a decisão, em português
    por_modelo: bool = False
    julgamento: dict = field(default_factory=dict)
    chave: str = ""            # id da consulta ou pergunta da tarefa
    ampliado: bool = False     # respondida com a chave conversa.roteamento

    @property
    def nome_tela(self) -> str:
        return nome_da_tela(self.destino, self.ampliado)

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados["nome_tela"] = self.nome_tela
        return dados


@dataclass
class Candidato:
    tipo: str
    destino: str
    chave: str
    descricao: str             # o que o modelo lê
    forte: bool = False
    pontos: float = 0.0
    tarefa: TarefaDoMapa | None = None
    dono: bool = False         # consulta sobre os registros de quem pergunta
    verbo: bool = False        # "como" cujo verbo é a ação da tarefa


def _ler_ir(plano: str, telas, ampliado: bool = False) -> Candidato | None:
    """'abra o financeiro': verbo de ir, e o resto da frase é o nome de uma tela."""
    palavras = _palavras(plano)
    # A gentileza que vem antes do verbo: "pode abrir a agenda?", "por favor,
    # me leve ao financeiro".
    while palavras and palavras[0] in GENTILEZA_ANTES_DO_VERBO and palavras[0] not in VERBOS_IR:
        palavras = palavras[1:]
    if not palavras or palavras[0] not in VERBOS_IR:
        return None
    resto = [p for p in palavras if p not in VERBOS_IR and p not in PREENCHIMENTO]
    if not resto or len(resto) > 5:
        return None
    # "a seção de Backup do PAULUS": tentar também sem o que só acompanha o
    # nome. Sem nada sobrando ("abra o sistema"), não é tela.
    enxuto = [p for p in resto if p not in SOBRA_DA_NAVEGACAO]
    alvos = {" ".join(resto)} | ({" ".join(enxuto)} if enxuto else set())
    for id_ in telas_conhecidas(ampliado):
        if any(n in alvos for n in _nomes_da_tela(id_, telas, ampliado)):
            return Candidato("ir", id_, id_, f"abrir a tela {nome_da_tela(id_, ampliado)}", forte=True)
    return None


# Antes do verbo de ir, o que é só gentileza: "pode abrir", "você pode me levar".
GENTILEZA_ANTES_DO_VERBO = {"pode", "poderia", "consegue", "voce", "por", "favor", "ok", "entao", "e", "agora",
                            "oi", "ola", "preciso", "gostaria", "queria"}


def _nomes_da_tela(id_: str, telas, ampliado: bool) -> set[str]:
    """Todos os jeitos de chamar a tela, já sem acento e sem as palavras de enchimento."""
    apelidos = list(telas[id_].apelidos if id_ in telas else [])
    apelidos += list((TELAS_NAVEGAVEIS.get(id_) or ("", "", ()))[2]) + list(APELIDOS_EXTRAS.get(id_, ()))
    nomes = set()
    for n in [nome_da_tela(id_, ampliado)] + apelidos:
        ps = [p for p in _palavras(_plano(n)) if p not in PREENCHIMENTO]
        if ps:
            nomes.add(" ".join(ps))
            enxuto = [p for p in ps if p not in SOBRA_DA_NAVEGACAO]
            if enxuto:
                nomes.add(" ".join(enxuto))
    return nomes


def navegar(frase: str, ampliado: bool = True) -> "Leitura | None":
    """
    Só a navegação, só por regra: "abra a agenda", "vá para Agentes", "pode
    abrir a lixeira?". Vale mesmo com um documento em foco - a frase inteira
    é o nome de uma tela, então não é pergunta sobre o documento. Antes, com
    um anexo na caixa, "abra a agenda" ia ler o anexo (pedido de 02/10).
    """
    plano = _plano(frase).strip()
    c = _ler_ir(plano, mapa_para(ampliado), ampliado) if plano else None
    if not c:
        return None
    leitura = Leitura("ir", c.destino, chave=c.chave, ampliado=ampliado)
    leitura.porque = f"você pediu para abrir {nome_da_tela(c.destino, ampliado)}"
    return leitura


def _ler_consultas(plano: str) -> list[Candidato]:
    achados = []
    de_si = bool(_tem_palavra(plano, PRIMEIRA_PESSOA))
    for id_, c in CONSULTAS.items():
        if id_ == "financeiro" and _tem_palavra(plano, NAO_E_FINANCEIRO):
            continue
        forte = _tem_palavra(plano, c["forte"])
        fraco = "" if forte else _tem_palavra(plano, c["fraco"])
        if forte or fraco:
            # "Dono": a frase fala dos registros de quem pergunta. Cadastros
            # fica de fora - "meus clientes têm contrato vencendo?" é sobre os
            # contratos deles.
            dono = bool(forte) and id_ != "cadastros" and (
                de_si or bool(_tem_palavra(plano, INEQUIVOCOS.get(id_, ()))))
            achados.append(Candidato("consulta", c["tela"], id_, c["descricao"], forte=bool(forte),
                                     pontos=3.0 if dono else 2.0 if forte else 1.0, dono=dono))
    achados.sort(key=lambda x: -x.pontos)
    return achados


def candidatos(frase: str, telas: dict[str, TelaDoMapa] | None = None,
               ampliado: bool = False) -> tuple[list[Candidato], dict]:
    """
    Tudo o que a regra enxerga na frase, e os sinais que ela usou.

    Não decide nada: devolve os candidatos com a força de cada um. Quem
    decide é `ler`. `ampliado` é a chave `conversa.roteamento` (C4).
    """
    telas = mapa_para(ampliado) if telas is None else telas
    plano = _plano(frase).strip()
    sinais = {
        "ancora": ancora_de_documento(plano),
        "ancora_de_texto": _tem_palavra(plano, ANCORAS_DE_TEXTO),
        "pergunta": _pergunta_ou_lista(plano),
        "como_fazer": bool(RE_COMO_FAZER.search(plano) or RE_ORDEM_DE_AJUSTE.search(plano)),
        "onde": bool(RE_ONDE.search(plano)),
        "o_que_e": bool((RE_O_QUE_E_C4 if ampliado else RE_O_QUE_E).search(plano)),
        "tela": _tela_citada(plano, telas, ampliado),
        "ampliado": ampliado,
    }
    lista: list[Candidato] = []

    ir = _ler_ir(plano, telas, ampliado)
    if ir:
        lista.append(ir)

    if sinais["o_que_e"] and sinais["tela"]:
        tela = sinais["tela"]
        lista.append(Candidato("como", tela, "", f"explicar para que serve a tela {nome_da_tela(tela, ampliado)}",
                               forte=True, pontos=1.0))

    if sinais["como_fazer"] or sinais["onde"]:
        for pts, tarefa, verbo in _candidatos_como(plano, telas)[:6]:
            lista.append(Candidato("como", tarefa.destino, tarefa.pergunta,
                                   f"explicar como usar o programa: {tarefa.pergunta}",
                                   pontos=pts, tarefa=tarefa, verbo=verbo))
        tela = sinais["tela"]
        if tela and not any(c.tipo == "como" for c in lista):
            lista.append(Candidato("como", tela, "", f"explicar para que serve a tela {nome_da_tela(tela, ampliado)}",
                                   pontos=1.0))

    if sinais["pergunta"] and not ir:
        lista += _ler_consultas(plano)

    return lista, sinais


def _por_regra(lista: list[Candidato], sinais: dict) -> Candidato | None:
    """
    O que a regra decide sozinha, nesta ordem:

    1. navegação: verbo de ir e o resto é o nome de uma tela;
    2. "o que é a tela X?": a tela;
    3. "como faço X?": a tarefa do mapa claramente à frente das outras - e
       aqui consulta não compete: quem pergunta "como gravo uma reunião?" quer
       o caminho, não a lista de reuniões;
    4. consulta com UMA palavra forte, pergunta, e nenhuma âncora de documento;
    5. "onde vejo X?": a tarefa do mapa, se claramente à frente.

    Fora disso, None: a dúvida vai ao juiz, ou aos documentos.
    """
    ir = [c for c in lista if c.tipo == "ir"]
    if ir:
        return ir[0]

    tela = [c for c in lista if c.tipo == "como" and c.forte]
    if tela:
        return tela[0]

    # Com a chave (C4), no empate de pontos vem primeiro a tarefa cujo verbo é
    # o da frase: em "como desligo o acesso de fora?", as três tarefas do
    # Acesso de fora somavam 2,0 e a regra desistia; "desligar" desempata.
    if sinais.get("ampliado"):
        como = sorted((c for c in lista if c.tipo == "como"), key=lambda c: (-c.pontos, not c.verbo))
    else:
        como = sorted((c for c in lista if c.tipo == "como"), key=lambda c: -c.pontos)

    def clara() -> Candidato | None:
        if not como:
            return None
        primeiro = como[0]
        segundo = como[1].pontos if len(como) > 1 else 0.0
        if primeiro.pontos >= 2.0 and primeiro.pontos >= segundo + 1.0:
            return primeiro
        if not sinais["ancora"] and primeiro.pontos >= 1.0 and primeiro.pontos >= segundo + 0.5:
            return primeiro
        # "como faço para imprimir o contrato?": o verbo É a ação da tarefa, e
        # o contrato é só o objeto. Nunca com âncora de texto ("como a
        # cláusula define o reajuste?").
        empate = len(como) > 1 and como[1].verbo and como[1].pontos == primeiro.pontos
        if primeiro.verbo and not sinais["ancora_de_texto"] and not empate:
            return primeiro
        return None

    if sinais["como_fazer"]:
        return clara()

    consultas = [c for c in lista if c.tipo == "consulta"]
    fortes = [c for c in consultas if c.forte]
    if len(fortes) == 1 and not sinais["ancora"]:
        return fortes[0]
    # Com âncora de documento, só a consulta sobre os próprios registros
    # ("tenho reunião com o autor do processo?"), e nunca com verbo de texto.
    donos = [c for c in consultas if c.dono]
    if len(donos) == 1 and not sinais["ancora_de_texto"]:
        return donos[0]

    if sinais["onde"]:
        return clara()
    return None


def _responder(c: Candidato, dados, plano: str, hoje: date | None, telas, ampliado: bool = False) -> Leitura | None:
    if c.tipo == "ir":
        return Leitura("ir", c.destino, chave=c.chave, ampliado=ampliado)
    if c.tipo == "como":
        texto = texto_do_como(c.tarefa) if c.tarefa else texto_da_tela(c.destino, telas, ampliado)
        return Leitura("como", c.destino, texto=texto, chave=c.chave, ampliado=ampliado)
    if c.tipo == "consulta":
        if dados is None:
            return None
        try:
            texto = EXECUTORES[c.chave](dados, plano, hoje)
        except Exception:
            # Um dado que não se deixou ler não vira resposta pela metade.
            return None
        return Leitura("consulta", c.destino, texto=texto, chave=c.chave)
    return None


PERGUNTA_DO_JUIZ = (
    "Um advogado escreveu a ENTRADA na conversa do PAULUS. O PAULUS guarda duas coisas "
    "diferentes: (1) os DOCUMENTOS do escritório - contratos, procurações, petições, "
    "processos -, cujo texto ele lê; (2) os REGISTROS que o próprio escritório faz no "
    "programa - compromissos anotados na agenda, tarefas, lançamentos do Financeiro, "
    "pedidos de Aprovação, cadastros - e as telas onde se faz cada coisa. "
    "Onde está a resposta para a ENTRADA?\n"
    "Exemplos:\n"
    "- \"o contrato prevê reunião mensal?\" -> no texto de um documento\n"
    "- \"tenho reunião amanhã com o cliente do processo?\" -> nos registros do programa\n"
    "- \"qual o valor da multa do contrato?\" -> no texto de um documento\n"
    "- \"quais tarefas tenho para o caso da Maria?\" -> nos registros do programa\n"
    "- \"o réu pagou as custas?\" -> no texto de um documento\n"
    "- \"quanto entrou no caixa com o contrato X este mês?\" -> nos registros do programa\n"
    "- \"como exporto o contrato em PDF?\" -> nas telas do programa\n"
    "- \"como o contrato define o reajuste?\" -> no texto de um documento"
)

DOCUMENTOS = "no texto de um documento (contrato, procuração, processo, petição)"


def _principal(lista: list[Candidato]) -> Candidato:
    """O candidato do programa que vai a julgamento: o forte, ou o de mais pontos."""
    return sorted(lista, key=lambda c: (not c.forte, -c.pontos))[0]


def _descricao_para_o_juiz(c: Candidato) -> str:
    if c.tipo == "consulta":
        return f"nos registros do programa: {c.descricao}"
    if c.tipo == "como":
        alvo = c.tarefa.pergunta if c.tarefa else f"a tela {nome_da_tela(c.destino)}"
        return f"nas telas do programa: {alvo}"
    return f"nas telas do programa: abrir {nome_da_tela(c.destino)}"


def julgar(frase: str, lista: list[Candidato], juiz, em_foco: list[str] | None = None):
    """
    Documentos ou programa? Uma pergunta de duas opções, com a ordem trocada
    e a média das duas (`trocar_ordem`): o 3B tem viés pela letra A, e sem a
    troca a "decisão" era só a posição. Devolve (candidato, Escolha) ou None.
    """
    alvo = _principal(lista)
    estado = {"documento_em_foco": (em_foco or [])[:2]} if em_foco else None
    escolha = juiz.escolher(
        PERGUNTA_DO_JUIZ,
        [("documentos", DOCUMENTOS), ("programa", _descricao_para_o_juiz(alvo))],
        estado=estado, entrada=frase, trocar_ordem=True,
    )
    if escolha is None:
        return None
    return alvo, escolha


def ler(frase: str, *, dados=None, juiz=None, hoje: date | None = None, em_foco: list[str] | None = None,
        telas: dict[str, TelaDoMapa] | None = None, ampliado: bool = False) -> Leitura | None:
    """
    O que a frase pede ao programa - ou None, e ela segue para os documentos.

    `dados` é quem guarda agenda, tarefas, financeiro, fila e cadastros (o
    Estado da API). `juiz` é um `juizo.Juiz`; sem ele, só a regra decide.
    `ampliado` é a chave `conversa.roteamento` (C4): as telas e as perguntas
    que ela trouxe. Desligada, tudo como antes.
    """
    telas = mapa_para(ampliado) if telas is None else telas
    plano = _plano(frase).strip()
    if not plano:
        return None
    lista, sinais = candidatos(frase, telas, ampliado)
    if not lista:
        return None

    decidido = _por_regra(lista, sinais)
    if decidido:
        leitura = _responder(decidido, dados, plano, hoje, telas, ampliado)
        if leitura:
            leitura.porque = _porque_da_regra(decidido, sinais, ampliado)
        return leitura

    if juiz is None:
        return None
    # Palavra fraca sozinha ("pagamento", "receber") não justifica os segundos
    # do modelo numa pergunta que, quase sempre, é sobre o documento.
    if not any(c.forte or (c.tipo == "como" and c.pontos >= 1.0) for c in lista):
        return None

    julgado = julgar(frase, lista, juiz, em_foco)
    if julgado is None:
        return None
    alvo, escolha = julgado
    p = escolha.probabilidades.get("programa", 0.0)
    if p < LIMIAR:
        return None
    leitura = _responder(alvo, dados, plano, hoje, telas, ampliado)
    if leitura:
        leitura.por_modelo = True
        leitura.julgamento = {**escolha.to_dict(), "p": round(p, 3)}
        leitura.porque = f"o modelo local julgou que a resposta está no programa ({round(p * 100)}%)"
    return leitura



def _porque_da_regra(c: Candidato, sinais: dict, ampliado: bool = False) -> str:
    if c.tipo == "ir":
        return f"você pediu para abrir {nome_da_tela(c.destino, ampliado)}"
    if c.tipo == "como":
        return "pergunta de como usar o programa"
    return f"pergunta sobre {c.descricao}"
