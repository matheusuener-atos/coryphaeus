"""
O caminho da pergunta, decidido pelo Paulus (13/10/2026).

Regra do dono: "Paulus autônomo para decidir o que fazer, onde procurar e
como pensar." Até aqui a caixa de pergunta tinha a pílula de escopo (o
documento da conversa, o Acervo, "pergunto onde procurar" e o "Modo
criativo"): quem escolhia o caminho era a pessoa, antes de escrever. A pílula
saiu; o caminho sai da frase e do contexto, a cada pergunta.

Os caminhos, na ordem em que a conversa (src/api.py) os confere:

1. pedido de ação (cadastro, agenda, abrir no editor, redigir, e-mail...): os
   leitores de intenção que já existiam (src/intencao.py, src/entrevista.py);
2. continuação do que acabou de ser dito: a resposta anterior como objeto
   (src/conversa_continua.py, src/memoria.py);
3. **conhecimento**: explicar, definir, opinar ou escrever sem relação com
   documento ("explique a usucapião", "o que é ITBI", "escreva um e-mail de
   boas-vindas"). Não lê o Acervo; pode ler a Biblioteca (as leis). É o que
   este módulo decide;
4. documento: o resto - o anexo, o documento que a frase nomeia, o da
   conversa, ou o Acervo (com a triagem da nuvem, quando ligada).

Só regra, sem modelo: é instantâneo, repetível e testável. A regra só diz
"conhecimento" quando a frase tem a forma de pedido de conhecimento E não
aponta documento nenhum (nome de arquivo, "este contrato", "a cláusula",
"o anexo"...). Na dúvida, não decide - e a pergunta segue o caminho de
documento de sempre, onde a triagem da nuvem (src/triagem.py, uma chamada
curta que já existia) separa lei de documento quando nada na conversa diz qual
documento.

O anexo é indício forte, não prisão: "explique a usucapião" com um PDF
anexado é conhecimento (a frase não fala dele); "qual o valor do imóvel?" com
o PDF é documento (a frase não tem forma de conhecimento, e ambígua com anexo
é sobre o anexo).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", str(texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


@dataclass
class Decisao:
    caminho: str            # "conhecimento" | "documento"
    tipo: str = ""          # conhecimento: "explicar" | "escrever" | "opinar" | "continuar"
    porque: str = ""        # a frase que "Como respondi" mostra
    anexos: list = field(default_factory=list)

    def como(self) -> dict:
        return {"caminho": self.caminho, "tipo": self.tipo, "porque": self.porque}


# A forma do pedido de conhecimento: explicar, definir, comparar, requisitos.
RE_EXPLICAR = re.compile(
    r"\b(?:expli(?:que|ca|car|caria|cacao)|me (?:ensine|ensina)|esclare(?:ca|ce)|"
    r"o que (?:e|sao|significa|significam|seria|quer dizer|vem a ser|diz a lei)|"
    r"(?:qual|quais) (?:e |sao )?(?:a |o |as |os )?(?:diferencas?|conceitos?|definicao|significado|natureza juridica|"
    r"requisitos|pressupostos|especies|modalidades|hipoteses|principios|efeitos|teses|fundamentos|"
    r"tipos de|elementos)\b|"
    r"como funciona(?:m)?|em que consiste|defina|definir|conceitue|conceituar|"
    r"para que serve(?:m)?|pra que serve(?:m)?)\b")

# Escrever sem documento: um e-mail, uma mensagem, ideias. Peça (contrato,
# petição, procuração...) é pedido de TRABALHO (src/entrevista.py), não daqui.
RE_ESCREVER = re.compile(
    r"\b(?:escreva|escrever|escreve|redija|redigir|elabore|crie|cria|faca|faz|monte|prepare|sugira|sugere|"
    r"me de|me da|liste|gere)\s+(?:para mim |pra mim |me )?"
    r"(?:um|uma|uns|umas|algumas|alguns|\d+|tres|cinco|dez)\s+"
    r"(?:(?:breve|curto|curta|pequeno|pequena|bom|boa|novo|nova)\s+)?"
    r"(?:e-?mails?|mensage(?:m|ns)|textos?|cartas?|posts?|publicac\w+|artigos?|discursos?|roteiros?|"
    r"apresentac\w+|listas?|ideias?|sugestoes|frases?|paragrafos?|comunicados?|convites?|agradecimentos?|"
    r"bios?|slogans?|titulos?|exemplos?|perguntas para|dicas?|resposta para)\b")
RE_IDEIAS = re.compile(r"\b(?:me (?:de|da) ideias|ideias? (?:de|para|pra)|sugestoes? de|exemplos? de)\b")

# Opinião em tese: "o que você acha de cláusula de não concorrência?". Sobre
# a resposta anterior ou o documento, é continuação ou documento.
# Precisa de objeto: "o que você acha?" sozinho é sobre o que acabou de ser dito.
RE_OPINAR = re.compile(r"\b(?:o que (?:voce|vc|tu) (?:acha|pensa)|na sua opiniao|qual (?:a )?sua opiniao)\s+"
                       r"(?:de|da|do|das|dos|sobre|a respeito de|acerca de|quanto a)\s+\w")

# O que aponta documento: a frase fala de UM documento do escritório.
_DOC = (r"(?:documentos?|contratos?|arquivos?|pdf|docx|procurac\w+|petic\w+|minutas?|escrituras?|aditivos?|laudos?|"
        r"certid\w+|pareceres?|parecer|planilhas?|anexos?|acordos?|termos?|recibos?|notificac\w+|sentenc\w+|"
        r"decis\w+|processos?|autos|matriculas?|imovel|imoveis|textos?|e-?mails?|mensage(?:m|ns)|clausulas?)")
RE_APONTA_DOCUMENTO = re.compile(
    r"\b(?:est[ea]s?|ess[ea]s?|dest[ea]s?|dess[ea]s?|nest[ea]s?|ness[ea]s?|aquel[ea]s?|naquel[ea]s?|daquel[ea]s?|"
    r"meu|minha|meus|minhas|nosso|nossa|nossos|nossas|seu|sua)\s+" + _DOC + r"\b"
    r"|\b(?:o|a|os|as|do|da|dos|das|no|na|nos|nas|ao|pelo|pela)\s+" + _DOC + r"\b"
    r"|\banex\w*|\breferid[oa]s?\b|\b(?:clausula|paragrafo|inciso|item) (?:\d|[ivx]+\b|primeir|segund|terceir|quart|quint|sext|setim|oitav|non|decim|unico)"
    r"|\bacervo\b|\bque (?:te )?(?:mandei|enviei|anexei|subi|passei)\b|\bque fizemos\b"
    # O pronome que aponta o que está na conversa: "o que você acha dele?".
    r"|\b(?:dele|dela|deles|delas|nele|nela|neles|nelas|disso|disto|nisso|nisto|ele|ela)\b")

# O que trabalha sobre a resposta que acabou de sair: "resuma isso", "mais
# curto", "em tópicos". Só vale depois de uma resposta de conhecimento.
RE_SOBRE_A_RESPOSTA = re.compile(
    r"\b(?:isso|isto|essa resposta|sua resposta|o que (?:voce|vc) (?:disse|escreveu|explicou)|mais (?:curt[oa]|long[oa]|"
    r"simples|formal|informal|detalhad[oa])|resum\w*|reescrev\w*|traduz\w*|em (?:\w+ )?(?:linhas|topicos|paragrafos))\b")

# Palavras do programa: "como funciona o acesso de fora?" é a camada do
# programa (src/programa.py), não conhecimento.
PROGRAMA = {
    "programa", "paulus", "pavlvs", "sistema", "app", "aplicativo", "voce", "vc", "isso", "isto", "aqui", "tela",
    "telas", "acesso", "acervo", "agenda", "biblioteca", "conversa", "assistente", "nuvem", "editor", "backup", "busca",
    "fila", "agente", "agentes", "modelo", "modelos", "aprovacoes", "financeiro", "cadastro", "cadastros", "servidor",
    "equipe", "painel", "plano", "assinatura", "whatsapp", "drive", "google", "botao", "menu", "configuracoes",
    "gravacoes", "gravacao", "certificado", "portal", "lixeira", "tarefas", "tarefa", "atos", "conta", "pilula",
    "area do cliente", "minha conta", "atalho", "atalhos", "ditado", "organizar",
}


def _fala_do_programa(plano: str) -> bool:
    depois = re.search(r"\b(?:como funciona(?:m)?|o que (?:e|sao)|para que serve(?:m)?|pra que serve(?:m)?|"
                       r"expli(?:que|ca|car)(?: como funciona)?)\s+(?:o |a |os |as |um |uma |esse |essa |este |esta )?"
                       r"([a-z-]+(?: [a-z-]+)?)", plano)
    if not depois:
        return False
    objeto = depois.group(1)
    primeira = objeto.split()[0]
    return primeira in PROGRAMA or objeto in PROGRAMA or not objeto.strip() or primeira in ("de", "do", "da")


def aponta_documento(texto: str, explicito=None) -> bool:
    """A frase fala de um documento: o nome dele, "este contrato", "a cláusula", "o anexo"."""
    return bool(explicito) or bool(RE_APONTA_DOCUMENTO.search(_plano(texto)))


def forma_de_conhecimento(texto: str) -> str:
    """'explicar' | 'escrever' | 'opinar' | '' - a forma da frase, sem olhar o contexto."""
    plano = _plano(texto)
    if not plano:
        return ""
    if RE_ESCREVER.search(plano) or RE_IDEIAS.search(plano):
        return "escrever"
    if RE_EXPLICAR.search(plano):
        return "" if _fala_do_programa(plano) else "explicar"
    if RE_OPINAR.search(plano):
        return "opinar"
    return ""


PORQUE = {
    "explicar": "pedido de explicação sem relação com documento: respondi pelo que sei, sem ler o Acervo",
    "escrever": "pedido de texto sem relação com documento: escrevi pelo que sei, sem ler o Acervo",
    "opinar": "pedido de opinião em tese: respondi pelo que sei, sem ler o Acervo",
    "continuar": "continuação da resposta anterior, que também não lia documento",
}


def decidir(pergunta: str, *, anexos=None, explicito=None, anterior: str = "", continua: bool = False) -> Decisao | None:
    """
    O caminho que a frase pede, ou None (o caminho de documento de sempre).

    - `anexos`: os documentos que a tela mandou com a pergunta (o anexo, ou o
      documento aberto ao lado da conversa);
    - `explicito`: o documento que a frase nomeia (src/intencao.py, `escopo`);
    - `anterior`: o caminho da resposta anterior ("conhecimento", "lei"...);
    - `continua`: a frase continua a anterior (memória ou "esses pontos").
    """
    anexos = [a for a in (anexos or []) if a]
    if aponta_documento(pergunta, explicito):
        if anexos:
            return Decisao("documento", porque="a pergunta fala do documento anexado", anexos=anexos)
        return None
    forma = forma_de_conhecimento(pergunta)
    if forma:
        return Decisao("conhecimento", tipo=forma, porque=PORQUE[forma])
    # "Resuma isso", "mais curto", "e quais os requisitos?", depois de uma
    # resposta que não lia documento: a continuação fica no mesmo caminho.
    # Com anexo novo, não.
    continua = continua or bool(RE_SOBRE_A_RESPOSTA.search(_plano(pergunta)))
    if continua and anterior in ("conhecimento", "criativo") and not anexos:
        return Decisao("conhecimento", tipo="continuar", porque=PORQUE["continuar"])
    if anexos:
        return Decisao("documento", porque="com documento anexado, a pergunta vai a ele", anexos=anexos)
    return None


def caminho_anterior(mensagens) -> str:
    """O caminho da última resposta do Paulus nesta conversa ('' sem nenhuma)."""
    for m in reversed(list(mensagens or [])):
        if getattr(m, "autor", "") == "paulus":
            como = ((getattr(m, "cobertura", None) or {}).get("como") or {})
            return str(como.get("caminho") or "")
    return ""
