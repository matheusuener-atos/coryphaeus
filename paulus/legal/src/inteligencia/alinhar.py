"""
A conferencia da citacao contra o texto - a barreira desta camada.

Esta e a peca que separa o programa de um chute bem formatado. A regra e de
uma linha: **todo item que se diz explicito carrega uma citacao que casa com o
texto do documento. O que nao casa nao e fato.**

Sem isso, um modelo pode devolver "o autor e Joao da Silva, conforme fls. 3" e
o programa repetiria a frase inteira, inclusive a folha, sem que nada disso
exista no documento. Com isso, a afirmacao sem lastro e reprovada por
aritmetica, nao por bom senso: ou a frase esta la, ou nao esta.

Por que nao basta comparar strings direto: o modelo quase nunca devolve os
mesmos bytes. Ele junta espacos, troca aspas curvas por retas, desfaz a quebra
de linha, corta o hifen da palavra partida no fim da linha e as vezes muda uma
preposicao. Reprovar tudo isso seria reprovar citacoes corretas - e citacao
reprovada e um fato verdadeiro que a camada deixa de usar. Dai a sequencia:

    1. normaliza os dois lados (texto.py), guardando o caminho de volta
    2. procura a citacao inteira - o caso comum, e barato
    3. nao achando, procura aproximado em volta de uma ancora distintiva
    4. achando, devolve o span no ORIGINAL e a pagina
    5. nao achando, o item fica `verified: false`, cai para `inferred` e
       **nao pode ser apresentado como fato**

O limiar de 92% nao e arbitrario: abaixo disso, o que passa deixa de ser "a
mesma frase escrita diferente" e passa a ser "uma frase parecida", que e
justamente o que nao se quer confirmar.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .esquema import Fonte, Item
from .texto import Normalizado, Pagina, normalizar, pagina_de

# Quanto a citacao pode diferir do texto e ainda ser a mesma citacao.
LIMIAR = 0.92

# Citacao curta demais nao prova nada: "o autor" casa com qualquer documento.
MINIMO = 12

# Ate onde procurar aproximado. Comparar a citacao com o documento inteiro,
# janela a janela, seria caro num processo de 400 paginas; a ancora resolve
# quase sempre, e o que ela nao resolve fica sem verificacao - o que e a
# resposta certa para uma citacao que o documento nao tem.
CANDIDATOS_MAX = 40


@dataclass
class Conferencia:
    """O que a conferencia achou - e por que aceitou ou nao."""

    achou: bool = False
    char_start: int = 0
    char_end: int = 0
    pagina: int | None = None
    semelhanca: float = 0.0
    trecho: str = ""         # o texto do documento naquele span
    motivo: str = ""

    def to_dict(self) -> dict:
        return {"achou": self.achou, "char_start": self.char_start, "char_end": self.char_end,
                "pagina": self.pagina, "semelhanca": round(self.semelhanca, 3),
                "motivo": self.motivo}


def conferir(texto: str, citacao: str, paginas: list[Pagina] | None = None,
             normalizado: Normalizado | None = None) -> Conferencia:
    """
    A citacao esta no texto? Onde?

    `normalizado` pode ser passado pronto quando se vai conferir varias
    citacoes do mesmo documento - normalizar um processo de 400 paginas uma
    vez por item seria pagar o mesmo preco dez vezes.
    """
    citacao = (citacao or "").strip()
    if not citacao:
        return Conferencia(motivo="sem citação")
    if len(citacao) < MINIMO:
        return Conferencia(motivo="citação curta demais para provar alguma coisa")
    if not (texto or "").strip():
        return Conferencia(motivo="documento sem texto")

    doc = normalizado or normalizar(texto)
    alvo = normalizar(citacao).plano
    if not alvo:
        return Conferencia(motivo="citação vazia depois de normalizar")

    # 1. Igual, que e o caso comum.
    posicao = doc.plano.find(alvo)
    if posicao >= 0:
        return _resultado(doc, paginas, posicao, posicao + len(alvo), 1.0, texto, "casou exatamente")

    # 2. Sem caixa: modelo as vezes devolve o titulo em maiuscula.
    posicao = doc.plano.lower().find(alvo.lower())
    if posicao >= 0:
        return _resultado(doc, paginas, posicao, posicao + len(alvo), 0.99, texto,
                          "casou fora a caixa das letras")

    # 3. Sem acento: quem digita com pressa e quem copia de PDF perdem o
    # acento, e o modelo repete o que recebeu. A diferenca nao muda o que esta
    # escrito - e o span devolvido continua sendo o do documento, com acento.
    plano_sem = sem_acento(doc.plano.lower())
    alvo_sem = sem_acento(alvo.lower())
    posicao = plano_sem.find(alvo_sem)
    if posicao >= 0:
        return _resultado(doc, paginas, posicao, posicao + len(alvo_sem), 0.98, texto,
                          "casou sem contar os acentos")

    # 4. Aproximado, ancorado num pedaco distintivo da citacao.
    melhor, onde = 0.0, -1
    por_numero = False
    largura = len(alvo)
    numeros_do_alvo = _digitos(alvo)
    escritos_do_alvo = _numeros_escritos(alvo_sem)
    for inicio in _candidatos(plano_sem, alvo_sem):
        fim = min(len(doc.plano), inicio + largura)
        janela = plano_sem[inicio:fim]
        razao = SequenceMatcher(None, alvo_sem, janela).ratio()
        if razao < melhor:
            continue
        # Numero trocado NAO e a mesma citacao. "R$ 150.000,00" difere de
        # "R$ 15.000,00" em um caractere - 98% de semelhanca - e em um zero
        # que muda a resposta por dez. Num documento juridico o que se
        # pergunta e quase sempre justamente o numero: valor, data, artigo,
        # CPF. Entao a semelhanca aproxima o texto, e o digito decide.
        if _digitos(janela) != numeros_do_alvo or not _cabem(escritos_do_alvo, janela):
            por_numero = por_numero or razao >= LIMIAR
            continue
        melhor, onde = razao, inicio

    if onde >= 0 and melhor >= LIMIAR:
        return _resultado(doc, paginas, onde, min(len(doc.plano), onde + largura), melhor, texto,
                          "casou aproximado")
    if por_numero:
        return Conferencia(achou=False, semelhanca=melhor,
                           motivo="o texto bate, mas os números da citação não são os do documento")
    return Conferencia(achou=False, semelhanca=melhor,
                       motivo="a citação não está no documento" if melhor < 0.6
                       else f"parecida demais para ignorar e diferente demais para aceitar ({melhor:.0%})")


def _digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


# Em documento juridico o numero tantas vezes esta por extenso quanto em
# algarismo - "doze parcelas", "noventa dias", "clausula sexta" -, e trocar
# uma dessas palavras muda o fato exatamente como trocar um digito muda.
NUMEROS_POR_EXTENSO = {
    "zero", "um", "uma", "dois", "duas", "tres", "quatro", "cinco", "seis", "sete",
    "oito", "nove", "dez", "onze", "doze", "treze", "quatorze", "catorze", "quinze",
    "dezesseis", "dezessete", "dezoito", "dezenove", "vinte", "trinta", "quarenta",
    "cinquenta", "sessenta", "setenta", "oitenta", "noventa", "cem", "cento",
    "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
    "oitocentos", "novecentos", "mil", "milhao", "milhoes", "bilhao", "bilhoes",
    "primeiro", "primeira", "segundo", "segunda", "terceiro", "terceira", "quarto",
    "quarta", "quinto", "quinta", "sexto", "sexta", "setimo", "setima", "oitavo",
    "oitava", "nono", "nona", "decimo", "decima", "meio", "meia", "metade", "dobro",
}


def _numeros_escritos(texto: str) -> list[str]:
    import re as _re

    return [p for p in _re.findall(r"[a-z]+", texto.lower()) if p in NUMEROS_POR_EXTENSO]


def _cabem(escritos: list[str], janela: str) -> bool:
    """Todo numero por extenso da citacao aparece na janela do documento?"""
    if not escritos:
        return True
    tem = _numeros_escritos(janela)
    for palavra in escritos:
        if palavra in tem:
            tem.remove(palavra)
        else:
            return False
    return True


def sem_acento(texto: str) -> str:
    """
    Sem acento, com o MESMO tamanho - cada letra acentuada vira a base dela.

    Manter o tamanho e o que permite usar a posicao achada aqui como posicao
    no texto normalizado: se a conversao encolhesse a string, o span voltaria
    deslocado e a citacao sairia comecando no meio da palavra anterior.
    """
    import unicodedata

    return "".join(
        (unicodedata.normalize("NFD", c)[0] if unicodedata.category(c) != "Mn" else c)
        for c in texto
    )


def _candidatos(plano: str, alvo: str) -> list[int]:
    """
    Onde no documento vale a pena comparar.

    A ancora e o pedaco mais distintivo da citacao - as primeiras palavras
    longas dela. Procurar por ela e barato; comparar so nas posicoes onde ela
    aparece transforma uma busca quadratica numa busca pontual.
    """
    palavras = [p for p in alvo.split() if len(p) >= 5][:4]
    ancoras = [" ".join(palavras[:3]), " ".join(palavras[:2])] if palavras else []
    ancoras += [p for p in palavras[:2]]
    ancoras = [a for a in dict.fromkeys(ancoras) if len(a) >= 6]

    posicoes: list[int] = []
    for ancora in ancoras:
        # A ancora quase nunca comeca a citacao: a janela precisa recuar o
        # tanto que a ancora esta adiantada dentro dela, senao a comparacao
        # sai deslocada e uma citacao correta e reprovada.
        recuo = max(0, alvo.find(ancora))
        comeco = 0
        while len(posicoes) < CANDIDATOS_MAX:
            achou = plano.find(ancora, comeco)
            if achou < 0:
                break
            posicoes.append(max(0, achou - recuo))
            comeco = achou + 1
        if posicoes:
            break
    return posicoes


def _resultado(doc: Normalizado, paginas, inicio: int, fim: int, razao: float,
               texto: str, motivo: str) -> Conferencia:
    comeco, acabou = doc.original(inicio, fim)
    return Conferencia(
        achou=True, char_start=comeco, char_end=acabou,
        pagina=pagina_de(paginas or [], comeco) if paginas else None,
        semelhanca=razao, trecho=texto[comeco:acabou], motivo=motivo,
    )


def verificar_item(item: Item, texto: str, version_id: str,
                   paginas: list[Pagina] | None = None,
                   normalizado: Normalizado | None = None) -> Item:
    """
    Confere um item e devolve ele com o veredito escrito.

    Nao levanta excecao e nao descarta nada: item reprovado continua existindo,
    marcado. Descartar esconderia do log que o extrator alucinou - e e
    justamente essa contagem que diz se um extrator novo pode entrar em
    producao (taxa de alucinacao por secao).
    """
    resultado = conferir(texto, item.quote, paginas, normalizado)
    if resultado.achou:
        item.verified = True
        item.source = Fonte(version_id=version_id, kind="text", page=resultado.pagina,
                            char_start=resultado.char_start, char_end=resultado.char_end,
                            chunk_id=item.source.chunk_id)
        # A citacao gravada passa a ser a do DOCUMENTO, e nao a que o modelo
        # escreveu: e ela que a pessoa vai conferir, e ela tem de ser a que
        # esta no papel.
        item.quote = resultado.trecho.strip()
        # A conferencia nunca PROMOVE. Achar a citacao prova que a frase existe
        # no documento - nao prova que a afirmacao construida em cima dela esta
        # certa. Quem marcou um item como deduzido (o extrator viu que o papel
        # da parte nao esta escrito, por exemplo) sabia de alguma coisa que
        # esta comparacao nao sabe, e subir a certeza aqui apagaria isso.
    else:
        item.verified = False
        if item.certainty == "explicit":
            item.certainty = "inferred"
        item.dados["verification_note"] = resultado.motivo
    return item


def verificar_todos(itens: list[Item], texto: str, version_id: str,
                    paginas: list[Pagina] | None = None) -> tuple[list[Item], int]:
    """Confere uma lista inteira normalizando o documento uma vez so."""
    if not itens:
        return [], 0
    doc = normalizar(texto)
    conferidos = [verificar_item(item, texto, version_id, paginas, doc) for item in itens]
    return conferidos, len([i for i in conferidos if not i.verified])
