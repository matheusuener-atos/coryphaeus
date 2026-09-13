"""
CPF, CNPJ e o nome que vem antes deles - o que pessoas e organizacoes
compartilham.

Este modulo nao e um extrator: e o que os dois usam. E ele existe por uma
razao que vale enunciar, porque e a mesma que fez o numero do processo ser a
primeira secao de regra da camada inteira: **estes numeros trazem o proprio
conferidor.**

Um CPF e um CNPJ tem digito verificador. Isso quer dizer que, ao contrario de
um nome, de uma data ou de uma clausula, da para saber se o que foi lido esta
certo sem consultar coisa nenhuma - so com aritmetica. Num acervo de verdade
isso aparece: entre as procuracoes deste escritorio ha um documento em que o
CNPJ da outorgante aparece duas vezes, com um digito diferente entre elas.
Uma das duas esta errada, e ate hoje ninguem notou. A camada nota, e sem
inventar nada: guarda a que fecha e marca a que nao fecha.

A outra metade do problema e o nome. Numa qualificacao brasileira ele vem
antes do documento, separado dele por uma lista de adjetivos:

    JOAO DA SILVA, brasileiro, casado, portador do CPF n. 111.444.777-35

Entao a busca e de tras para a frente: quebra-se o texto anterior nos
separadores, e pega-se o ultimo pedaco que termina com uma sequencia de
palavras com cara de nome. "CNPJ/MF" tem cara de nome - e maiuscula - e por
isso existe uma lista de palavras que a qualificacao usa e que nome nenhum e.
"""

from __future__ import annotations

import re

from . import frases

# A forma pontuada, que e como aparece em peca e em contrato. A forma crua
# (so digitos) fica de fora: onze digitos seguidos sao telefone com DDD tantas
# vezes quantas sao CPF, e um telefone com digito verificador valido por acaso
# viraria uma pessoa.
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_OAB = re.compile(r"\bOAB[\s/-]{0,3}([A-Z]{2})[\s/n.º°-]{0,5}(\d{1,6})\b", re.IGNORECASE)

# O que a qualificacao escreve em maiuscula e nao e nome de ninguem. Comparado
# sem acento e sem ponto, para pegar "C.P.F." junto com "CPF".
#
# "Brasileiro" ficou de fora de proposito: em minuscula ele ja nao passa (nome
# comeca em maiuscula), e em maiuscula ele e parte de nome de empresa -
# "COOPERATIVA BRASILEIRA LTDA." perderia duas palavras das tres.
NAO_E_NOME = {
    "cpf", "cnpj", "mf", "rg", "oab", "ie", "cep", "uf", "nº", "no", "n",
    "inscricao", "estadual", "municipal", "identidade", "portador", "portadora",
    "sob", "numero", "cnpjmf", "cpfmf", "rgssp", "ctps", "pis", "nit", "nire",
    "endereco", "residente", "domiciliado", "inscrito", "inscrita", "cliente",
}

# Um nome tem mais de uma palavra - de pessoa e de empresa. A regra derruba de
# uma vez a maior parte do lixo que gruda em documento: "PC/PA" e "SSP/GO" sao
# orgaos expedidores de RG, "N.I.R.E." e registro de junta comercial, e todos
# eles aparecem a poucos caracteres de um CPF.
PALAVRAS_MINIMAS = 2
LETRAS_MINIMAS = 6

# Palavras que ficam DENTRO de um nome sem quebra-lo.
LIGAM_NOME = {"da", "de", "do", "das", "dos", "e", "-", "&", "em", "y"}

SEPARADORES = ",;:()[]\n"

# Ate onde se procura o nome. Passou disso, a qualificacao ja acabou e o que
# vem antes fala de outra pessoa.
RECUO = 220


# O papel que a qualificacao escreve antes do nome. E uma tabela diferente da
# que as alegacoes usam: la a pergunta e quem esta falando, aqui e o que a
# pessoa e no documento.
PAPEIS = {
    "grantor": ("outorgante", "mandante", "constituinte"),
    "grantee": ("outorgado", "mandatario", "procurador"),
    "seller": ("vendedor", "vendedora", "promitente vendedor", "alienante"),
    "buyer": ("comprador", "compradora", "promitente comprador", "adquirente"),
    "lessor": ("locador", "locadora"),
    "lessee": ("locatario", "locataria", "inquilino"),
    "contractor": ("contratante",),
    "contracted": ("contratado", "contratada", "prestador"),
    "plaintiff": ("autor", "autora", "requerente", "exequente", "reclamante"),
    "defendant": ("reu", "re", "requerido", "requerida", "executado", "reclamada"),
    "lawyer": ("advogado", "advogada", "patrono", "oab"),
    "witness": ("testemunha",),
    "guarantor": ("fiador", "fiadora", "avalista"),
}

# A busca do papel e por palavra inteira, e nao por pedaco de palavra. Sem
# isso a pista "re" de reu casa dentro de "RG", de "residente" e de "REIS", e
# o acervo inteiro sai com todo mundo marcado como reu - foi o que aconteceu
# na primeira medicao desta colecao.
_REGEX_DOS_PAPEIS = {
    papel: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in pistas) + r")\b")
    for papel, pistas in PAPEIS.items()
}

# A que distancia o papel ainda qualifica o nome. Alem disso ja e outra
# pessoa da mesma qualificacao.
ALCANCE_DO_PAPEL = 90


def papel_perto(texto: str, posicao: int) -> str:
    """
    O papel escrito COLADO no nome - e nada, quando nao ha nenhum.

    A regra vem de uma medicao antiga desta camada: o modelo local escreveu
    "COOBRAMEX - reu" numa procuracao em que a palavra "reu" nao aparece. Papel
    que nao esta escrito nao e papel, nem aqui nem la.

    Mas "escrito perto" nao basta, e a primeira medicao desta colecao mostrou
    por que: em "vem, por seu advogado, propor acao em face de JOAO DA SILVA",
    a palavra "advogado" esta a menos de noventa caracteres do nome do REU.
    Entao a janela nao e de tamanho: e de estrutura. Ela vai ate o separador
    anterior ao anterior, o que aceita o rotulo colado ("OUTORGANTE: FULANO",
    "VENDEDOR: FULANO") e recusa o que ficou para tras de uma virgula a mais.
    """
    piso = max(0, posicao - ALCANCE_DO_PAPEL)
    separadores = [i for i in range(piso, posicao) if texto[i] in SEPARADORES]
    if len(separadores) >= 2:
        piso = separadores[-2] + 1
    janela = frases.sem_acento(texto[piso:posicao])
    melhor, mais_perto = "", len(janela) + 1
    for papel, regex in _REGEX_DOS_PAPEIS.items():
        for encontro in regex.finditer(janela):
            distancia = len(janela) - encontro.start()
            if distancia < mais_perto:
                melhor, mais_perto = papel, distancia
    return melhor


def _digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


def cpf_valido(bruto: str) -> bool:
    """Modulo 11, os dois digitos - a conta que a Receita usa desde 1965."""
    numero = _digitos(bruto)
    if len(numero) != 11 or numero == numero[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(numero[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(numero[tamanho]):
            return False
    return True


def cnpj_valido(bruto: str) -> bool:
    """Modulo 11 com pesos ciclicos de 2 a 9 - a mesma ideia, outra tabela."""
    numero = _digitos(bruto)
    if len(numero) != 14 or numero == numero[0] * 14:
        return False
    for tamanho, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
                           (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        soma = sum(int(numero[i]) * pesos[i] for i in range(tamanho))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(numero[tamanho]):
            return False
    return True


def _parece_nome(palavra: str) -> bool:
    limpa = palavra.strip(".,:;()[]").strip()
    if not limpa or any(c.isdigit() for c in limpa):
        return False
    if frases.sem_acento(limpa).replace(".", "").replace("/", "") in NAO_E_NOME:
        return False
    return limpa[:1].isupper()


def nome_antes(texto: str, posicao: int) -> tuple[str, int]:
    """
    O nome que vem antes do documento, e onde ele comeca.

    Procura de tras para a frente, pedaco a pedaco, o ultimo trecho que
    termina numa sequencia de palavras com cara de nome - porque a
    qualificacao poe o nome primeiro e o documento por ultimo, com os
    adjetivos no meio.
    """
    piso = max(0, posicao - RECUO)
    janela = texto[piso:posicao]
    corte = piso
    partes: list[tuple[int, str]] = []
    inicio = 0
    for i, caractere in enumerate(janela):
        if caractere in SEPARADORES:
            partes.append((inicio, janela[inicio:i]))
            inicio = i + 1
    partes.append((inicio, janela[inicio:]))

    for deslocamento, pedaco in reversed(partes):
        palavras = [(m.start(), m.group()) for m in re.finditer(r"\S+", pedaco)]
        fim = len(palavras)
        while fim > 0 and not _parece_nome(palavras[fim - 1][1]):
            fim -= 1
        if fim == 0:
            continue
        comeco = fim
        while comeco > 0:
            palavra = palavras[comeco - 1][1]
            if _parece_nome(palavra) or frases.sem_acento(palavra.strip(".,")) in LIGAM_NOME:
                comeco -= 1
            else:
                break
        while comeco < fim and frases.sem_acento(
                palavras[comeco][1].strip(".,")) in LIGAM_NOME:
            comeco += 1          # nome nao comeca em "de"
        if comeco >= fim:
            continue
        trecho = pedaco[palavras[comeco][0]: palavras[fim - 1][0] + len(palavras[fim - 1][1])]
        palavras_do_nome = [p for p in trecho.split() if len(p.strip(".,-")) > 1]
        if (len(palavras_do_nome) < PALAVRAS_MINIMAS
                or len(frases.chave(trecho)) < LETRAS_MINIMAS):
            continue
        corte = piso + deslocamento + palavras[comeco][0]
        return frases.limpo(trecho).strip(" -,;"), corte
    return "", corte
