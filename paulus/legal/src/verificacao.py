"""
Verificação por regra, antes e depois do modelo, nas perguntas sobre documentos.

O banco de provas (tools/demo/roteiro.py --dificil, 27/09/2026) achou dois
erros que instrução nenhuma corrigiu no llama3.2:3b:

- **Papel trocado.** "Quem é o advogado da Rio Fresco?" voltava "Helena
  Moura" - a advogada da Cooperativa, a outra parte. O modelo junta o nome
  que aparece na procuração com a parte que aparece no mesmo texto.
- **Consequência pela metade.** "O que acontece se a Rio Fresco não
  regularizar?" voltava a multa e esquecia a rescisão; "quanto custa
  rescindir sem motivo?" voltava os 10% e esquecia o aviso de 30 dias.

As duas regras seguem o padrão de sempre - o código acha a evidência, o
modelo não inventa:

1. `papel_sem_prova`: ANTES do modelo. Se a parte aparece nos documentos mas
   em nenhum ponto ligada a advogado ou procurador (outorgante, "representada
   por", "por seu advogado"...), a resposta é essa, sem modelo.
2. `trecho_decisivo`: DEPOIS do modelo. Em pergunta de consequência ou
   condição, acha a frase do documento que decide e, se ela traz algo que a
   resposta deixou de fora (multa, rescisão, prazo, número), copia a frase
   literal embaixo - nunca reescreve a resposta.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------ 1. papel

RE_PAPEL = re.compile(
    r"\b(?:quem (?:e|sao|seria|representa)|qual (?:e )?o nome d[oa])\b.{0,24}?"
    r"\b(?P<papel>advogad[oa]s?|procurador(?:a|es|as)?|representante(?:s)?|patron[oa])\s+"
    r"(?:d[aoe]s?|que representa)\s+(?P<parte>[^?.,;]{3,80})")

# O que diz que alguém representa a parte - pela ESTRUTURA, nao pela
# proximidade: "OUTORGANTE: fulano" (o marcador logo antes do nome) ou
# "fulano, representada por" (logo depois). Proximidade sozinha errou: na
# procuracao da Cooperativa, "...com a Transportes Rio Fresco Ltda. Nao estao
# incluidos os poderes ... da OUTORGANTE" achava "outorgante" a 60 letras e
# ligava a Rio Fresco a advogada da outra parte.
ANTES_DO_NOME = re.compile(r"(outorgante|constituinte|mandante)s?\s*:?\s*$")
# Num contrato de honorarios advocaticios, o contratante e o cliente.
ANTES_NO_HONORARIO = re.compile(r"(contratante|cliente)s?\s*:?\s*$")
DEPOIS_DO_NOME = re.compile(
    # 60 letras, passando por ponto: "Gama Comércio Ltda., representada por".
    r"^[^;:]{0,60}?\b(representad[oa]s? (?:por|neste)|por (?:seu|sua|seus|suas|intermedio de seu) "
    r"(?:advogad|procurador|patron)|neste ato representad)")

ARTIGOS = {"a", "o", "as", "os", "empresa", "cliente", "parte", "senhor", "senhora", "sr", "sra", "dr", "dra"}


def papel_sem_prova(pergunta: str, documentos) -> str:
    """
    "Quem é o advogado de X?" quando nenhum documento liga advogado a X: a
    resposta, pronta. Vazio quando há ligação (o modelo lê) ou quando X nem
    aparece (o caminho de sempre diz que não achou).
    """
    achado = RE_PAPEL.search(_plano(pergunta))
    if not achado:
        return ""
    palavras = [p for p in re.findall(r"[a-z0-9]+", achado.group("parte")) if p not in ARTIGOS]
    if not palavras:
        return ""
    # A frase inteira, e senão as duas últimas palavras ("rio fresco").
    alvos = [" ".join(palavras)] + ([" ".join(palavras[-2:])] if len(palavras) > 2 else [])
    onde = []
    for d in documentos or []:
        texto = re.sub(r"\s+", " ", _plano(getattr(d, "text", "")))
        for alvo in alvos:
            posicoes = [m.start() for m in re.finditer(r"\b" + re.escape(alvo) + r"\b", texto)]
            if not posicoes:
                continue
            onde.append(d.name)
            honorarios = "honorarios advocat" in texto
            for i in posicoes:
                antes = texto[max(0, i - 60): i]
                depois = texto[i + len(alvo): i + len(alvo) + 120]
                if (ANTES_DO_NOME.search(antes) or (honorarios and ANTES_NO_HONORARIO.search(antes))
                        or DEPOIS_DO_NOME.search(depois)):
                    return ""
            break
    if not onde:
        return ""
    papel = achado.group("papel")
    # O nome como a pessoa escreveu, com acento e maiúscula.
    original = re.search(r"(?i)\b(?:advogad|procurador|representante|patron)\w*\s+(?:d[aoe]s?|que representa)\s+([^?.,;]{3,80})",
                         pergunta)
    nome_parte = original.group(1).strip() if original else achado.group("parte").strip()
    docs = ", ".join(Path(n).stem for n in dict.fromkeys(onde))
    return (f"Nenhum documento do Acervo diz quem é o {papel} de {nome_parte}. "
            f"{nome_parte} aparece em {docs}, mas em nenhum ponto como parte representada por advogado "
            "ou procurador - quem aparece representando alguém ali representa outra parte.")


# ------------------------------------------------- 2. trecho decisivo

RE_CONSEQUENCIA = re.compile(
    r"\b(o que acontece|acontece se|consequenc\w*|sob pena|rescind\w*|rescis\w*|descumpr\w*|caso (?:a|o|nao)|"
    r"se (?:a|o) \w+ nao|se nao|penalidade)\b")

# O que, numa frase de contrato, costuma ser a parte que decide.
DECISIVOS = ("multa", "rescis", "aviso", "juros", "prazo", "dias", "sob pena", "mora", "indeniza", "perda")

VAZIAS = {"qual", "quais", "quanto", "quantos", "como", "onde", "quando", "sobre", "para", "pelo", "pela",
          "com", "sem", "que", "acontece", "custa", "contrato", "documento", "este", "esse", "isso", "caso",
          "nao", "entre", "das", "dos", "uma", "um"}


def _raizes(texto: str) -> set[str]:
    return {p[:5] for p in re.findall(r"[a-z0-9]{4,}", _plano(texto)) if p not in VAZIAS}


def trecho_decisivo(pergunta: str, resposta: str, hits) -> str:
    """
    A frase do documento que decide a pergunta de consequência, literal,
    quando ela traz o que a resposta não trouxe. Vazio no resto.
    """
    if not RE_CONSEQUENCIA.search(_plano(pergunta)) or not hits:
        return ""
    chaves = _raizes(pergunta)
    melhor, melhor_nota, doc = "", 0.0, ""
    for h in hits:
        # O documento de que a pergunta fala ("do contrato de transporte",
        # "a Rio Fresco") pesa: a frase certa costuma morar nele.
        do_doc = 1.5 * len(chaves & _raizes(Path(h.doc_name).stem))
        for frase in re.split(r"(?<=[.;])\s+", h.chunk.text):
            frase = frase.strip()
            if len(frase) < 30 or len(frase) > 500:
                continue
            plano = _plano(frase)
            comum = len(chaves & _raizes(frase))
            if comum < 1:
                continue
            nota = 2 * comum + do_doc + 0.5 * sum(1 for d in DECISIVOS if d in plano)
            if nota > melhor_nota:
                melhor, melhor_nota, doc = frase, nota, h.doc_name
    if melhor_nota < 4:
        return ""
    r = _plano(resposta)
    f = _plano(melhor)
    faltam = [d for d in DECISIVOS if d in f and d not in r] + \
             [n for n in re.findall(r"\d+(?:[.,]\d+)?%?", f) if n not in r]
    if not faltam:
        return ""
    return f"\n\nNo documento ({Path(doc).stem}): «{' '.join(melhor.split())}»"
