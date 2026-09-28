"""
PAULUS - CPF, CNPJ e telefone.

O espelho, no servidor, de frontend/js/39-campos.js: as mesmas contas, as
mesmas mascaras e os mesmos avisos. A tela confere enquanto a pessoa digita;
aqui confere de novo antes de gravar - o que chega por outro caminho (a
conversa, um arquivo antigo, a API) passa pela mesma regra. Duas regras
diferentes para o mesmo CPF era o jeito de um lado aceitar o que o outro
recusa.

O CNPJ aceita o formato alfanumerico da Receita (IN RFB 2.229/2024): as 12
primeiras posicoes podem ter letras; os dois verificadores continuam
numeros, e a conta usa o codigo de cada caractere menos 48 - o mesmo calculo
de sempre para quem e so numero.

Tres familias de funcao:
  - mascara_*: formata enquanto se digita, sem conferir (como na tela);
  - formatar_*: formata o que fecha e recusa o que nao fecha (ValueError com
    o aviso que a tela mostraria); vazio continua vazio;
  - exibir_*: para mostrar - formata o que fecha e devolve o resto como veio,
    sem nunca recusar.
E normalizado() / so_digitos() para comparar sem depender da mascara.
"""

from __future__ import annotations

import re

ROTULO = {"cpf": "CPF", "cnpj": "CNPJ", "cpf-cnpj": "CPF ou CNPJ", "telefone": "Telefone"}

# \d do Python casa com digito de qualquer alfabeto; o \d do JavaScript, so
# com 0-9. Aqui tudo e explicito para as duas pontas darem o mesmo.
_NAO_DIGITO = re.compile(r"[^0-9]")
_NAO_DOCUMENTO = re.compile(r"[^0-9A-Z]")
_FORA_DO_BRASIL = re.compile(r"^\+(?!55)")

PESOS_CNPJ_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_CNPJ_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

# CPF e CNPJ como aparecem num texto: com a mascara. O CNPJ pode ter letras
# nas 12 primeiras posicoes (maiusculas, como a Receita emite).
RE_CPF_TEXTO = re.compile(r"(?<![0-9])[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}(?![0-9])")
RE_CNPJ_TEXTO = re.compile(
    r"(?<![0-9A-Za-z])[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-[0-9]{2}(?![0-9])")


def so_digitos(valor) -> str:
    return _NAO_DIGITO.sub("", str(valor or ""))


def normalizado(valor) -> str:
    """O que sobra de um CPF/CNPJ: numeros e, para o CNPJ novo, letras."""
    return _NAO_DOCUMENTO.sub("", str(valor or "").upper())


# ------------------------------------------------------------- mascaras


def mascara_cpf(valor) -> str:
    d = so_digitos(valor)[:11]
    if len(d) <= 3:
        return d
    if len(d) <= 6:
        return d[:3] + "." + d[3:]
    if len(d) <= 9:
        return d[:3] + "." + d[3:6] + "." + d[6:]
    return d[:3] + "." + d[3:6] + "." + d[6:9] + "-" + d[9:]


def mascara_cnpj(valor) -> str:
    # Letras so nas 12 primeiras posicoes; os verificadores sao numeros.
    bruto = normalizado(valor)
    c = (bruto[:12] + so_digitos(bruto[12:]))[:14]
    if len(c) <= 2:
        return c
    if len(c) <= 5:
        return c[:2] + "." + c[2:]
    if len(c) <= 8:
        return c[:2] + "." + c[2:5] + "." + c[5:]
    if len(c) <= 12:
        return c[:2] + "." + c[2:5] + "." + c[5:8] + "/" + c[8:]
    return c[:2] + "." + c[2:5] + "." + c[5:8] + "/" + c[8:12] + "-" + c[12:]


def _e_lado_cnpj(limpo: str) -> bool:
    """Ate 11 numeros e CPF; passou disso, ou tem letra, e CNPJ."""
    return len(limpo) > 11 or bool(re.search(r"[A-Z]", limpo))


def mascara_cpf_ou_cnpj(valor) -> str:
    c = normalizado(valor)
    return mascara_cnpj(c) if _e_lado_cnpj(c) else mascara_cpf(c)


def mascara_telefone(valor) -> str:
    bruto = str(valor or "").strip()
    # Numero de fora do Brasil (+ que nao e 55): fica como a pessoa escreveu.
    if _FORA_DO_BRASIL.match(bruto):
        return re.sub(r"[^0-9+ ()\-]", "", bruto)
    d = so_digitos(bruto)
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]
    if d.startswith("0800") or d.startswith("0300"):
        d = d[:11]
        if len(d) <= 4:
            return d
        return d[:4] + " " + d[4:7] + (" " + d[7:] if len(d) > 7 else "")
    d = d[:11]
    if not d:
        return ""
    if len(d) <= 2:
        return "(" + d
    ddd = "(" + d[:2] + ") "
    resto = d[2:]
    # Celular tem 9 digitos depois do DDD (comeca com 9); fixo, 8.
    corte = 5 if len(resto) > 8 or (resto[:1] == "9" and len(resto) >= 5) else 4
    return ddd + resto if len(resto) <= corte else ddd + resto[:corte] + "-" + resto[corte:]


def mascara(tipo: str, valor) -> str:
    if tipo == "cpf":
        return mascara_cpf(valor)
    if tipo == "cnpj":
        return mascara_cnpj(valor)
    if tipo == "cpf-cnpj":
        return mascara_cpf_ou_cnpj(valor)
    if tipo == "telefone":
        return mascara_telefone(valor)
    return str(valor or "")


# ------------------------------------------------------------- conferir


def cpf_valido(valor) -> bool:
    d = so_digitos(valor)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def cnpj_valido(valor) -> bool:
    c = normalizado(valor)
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", c) or c == c[0] * 14:
        return False
    for n, pesos in ((12, PESOS_CNPJ_1), (13, PESOS_CNPJ_2)):
        soma = sum((ord(c[i]) - 48) * pesos[i] for i in range(n))
        resto = soma % 11
        if (0 if resto < 2 else 11 - resto) != int(c[n]):
            return False
    return True


def telefone_valido(valor) -> bool:
    bruto = str(valor or "").strip()
    if _FORA_DO_BRASIL.match(bruto):
        return len(so_digitos(bruto)) >= 8
    d = so_digitos(bruto)
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]
    if d.startswith("0800") or d.startswith("0300"):
        return len(d) == 11
    if len(d) not in (10, 11):
        return False
    if d[0] == "0" or d[1] == "0":          # DDD nao comeca nem termina em 0
        return False
    return len(d) == 10 or d[2] == "9"      # 11 digitos: celular, comeca com 9


def problema(tipo: str, valor) -> str:
    """O que esta errado no valor, ou "" se esta certo (vazio e certo)."""
    v = str(valor or "").strip()
    if not v:
        return ""
    if tipo == "cpf":
        if len(so_digitos(v)) < 11:
            return "CPF incompleto: são 11 números"
        return "" if cpf_valido(v) else "CPF inválido: confira os números"
    if tipo == "cnpj":
        if len(normalizado(v)) < 14:
            return "CNPJ incompleto: são 14 caracteres"
        return "" if cnpj_valido(v) else "CNPJ inválido: confira os caracteres"
    if tipo == "cpf-cnpj":
        return problema("cnpj" if _e_lado_cnpj(normalizado(v)) else "cpf", v)
    if tipo == "telefone":
        return "" if telefone_valido(v) else "telefone incompleto: DDD e número, como (62) 99999-8888"
    return ""


# --------------------------------------------------- formatar para gravar


def formatar(tipo: str, valor) -> str:
    """
    O valor com a mascara, pronto para gravar. Vazio continua vazio; o que
    nao fecha levanta ValueError com o mesmo aviso que a tela mostra.
    """
    v = str(valor or "").strip()
    if not v:
        return ""
    erro = problema(tipo, v)
    if erro:
        raise ValueError(erro)
    return mascara(tipo, v)


def formatar_documento(valor, tipo: str = "cpf-cnpj") -> str:
    return formatar(tipo, valor)


def formatar_telefone(valor) -> str:
    return formatar("telefone", valor)


# ------------------------------------------------------- para mostrar


def exibir(tipo: str, valor) -> str:
    """Formatado se fecha; se nao, como veio. Nunca recusa."""
    v = str(valor or "").strip()
    if not v or problema(tipo, v):
        return v
    return mascara(tipo, v)


def exibir_documento(valor) -> str:
    return exibir("cpf-cnpj", valor)


def exibir_telefone(valor) -> str:
    return exibir("telefone", valor)


def e_cnpj(valor) -> bool:
    """
    O documento e de pessoa juridica? 14 numeros (o CNPJ de sempre) ou um
    CNPJ alfanumerico que fecha. Letra solta ("CPF 123...") nao faz CNPJ.
    """
    v = str(valor or "").strip()
    if len(so_digitos(v)) == 14:
        return True
    return bool(re.fullmatch(r"[0-9A-Za-z./\- ]+", v)) and cnpj_valido(v)


def rotulo_do_documento(valor) -> str:
    """"CNPJ", "CPF" ou "documento", pelo tamanho do que sobra."""
    if e_cnpj(valor):
        return "CNPJ"
    return "CPF" if len(so_digitos(valor)) == 11 else "documento"
