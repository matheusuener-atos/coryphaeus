"""
PAULUS - Planilha.

Grade com formulas, no formato que um escritorio brasileiro digita: ponto e
virgula separa argumento, virgula e decimal, e as funcoes tem nome em portugues
- =SE(C4="pago";0;B4*0,1) e o que a pessoa escreve no Excel dela.

Escrever um interpretador de formula da trabalho e por isso a tentacao e usar
`eval`. Nao da: formula vem de arquivo que veio de fora - uma planilha que o
cliente mandou - e `eval` num texto de terceiro executa o que estiver la. Aqui
ha um analisador de verdade, que so conhece numeros, textos, referencias e as
funcoes desta lista. O que ele nao conhece vira erro na celula, nunca acao.

Referencia circular tambem e erro visivel, nao travamento: A1 que soma A1
devolve #CIRCULAR e a planilha continua respondendo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

LINHAS_PADRAO = 40
COLUNAS_PADRAO = 8
MAX_LINHAS = 2000
MAX_COLUNAS = 40

FORMATOS = {
    "": "Texto",
    "numero": "Número",
    "moeda": "R$",
    "porcento": "%",
    "data": "Data",
}

ERRO_CIRCULAR = "#CIRCULAR"
ERRO_NOME = "#NOME?"
ERRO_VALOR = "#VALOR!"
ERRO_DIV = "#DIV/0!"
ERRO_REF = "#REF!"

RE_CELULA = re.compile(r"^([A-Z]{1,2})(\d{1,4})$")


# ------------------------------------------------------------- a grade


@dataclass
class Celula:
    valor: str = ""            # o que a pessoa digitou, inclusive a formula
    formato: str = ""
    negrito: bool = False
    italico: bool = False

    @property
    def e_formula(self) -> bool:
        return self.valor.startswith("=")

    def to_dict(self) -> dict:
        return {
            "valor": self.valor, "formato": self.formato,
            "negrito": self.negrito, "italico": self.italico,
        }


@dataclass
class Aba:
    nome: str = "Página 1"
    celulas: dict[str, Celula] = field(default_factory=dict)
    linhas: int = LINHAS_PADRAO
    colunas: int = COLUNAS_PADRAO
    congelar_cabecalho: bool = False

    def obter(self, ref: str) -> Celula | None:
        return self.celulas.get(ref.upper())

    def gravar(self, ref: str, dados: dict) -> Celula:
        ref = ref.upper()
        celula = self.celulas.get(ref) or Celula()
        if "valor" in dados:
            celula.valor = str(dados["valor"])
        for campo in ("formato", "negrito", "italico"):
            if campo in dados:
                setattr(celula, campo, dados[campo] if campo == "formato" else bool(dados[campo]))

        if not celula.valor and not celula.formato and not celula.negrito and not celula.italico:
            self.celulas.pop(ref, None)
            return celula

        self.celulas[ref] = celula
        linha, coluna = _posicao(ref)
        self.linhas = max(self.linhas, min(linha + 4, MAX_LINHAS))
        self.colunas = max(self.colunas, min(coluna + 2, MAX_COLUNAS))
        return celula

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "linhas": self.linhas,
            "colunas": self.colunas,
            "congelar_cabecalho": self.congelar_cabecalho,
            "celulas": {k: c.to_dict() for k, c in self.celulas.items()},
        }


def letra_da_coluna(indice: int) -> str:
    """0 vira A, 25 vira Z, 26 vira AA."""
    nome = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        nome = chr(65 + resto) + nome
    return nome


def indice_da_coluna(letras: str) -> int:
    total = 0
    for c in letras.upper():
        total = total * 26 + (ord(c) - 64)
    return total - 1


def _posicao(ref: str) -> tuple[int, int]:
    achado = RE_CELULA.match(ref.upper())
    if not achado:
        return 0, 0
    return int(achado.group(2)) - 1, indice_da_coluna(achado.group(1))


# ------------------------------------------------------ numeros e texto


def numero(texto) -> float | None:
    """
    Le numero como um brasileiro escreve.

    "12.000,00" e doze mil, nao doze. Ler isso errado num campo de honorarios
    troca o valor por mil vezes menos, e ninguem confere planilha somando de
    cabeca.
    """
    if isinstance(texto, (int, float)) and not isinstance(texto, bool):
        return float(texto)
    bruto = str(texto or "").strip().replace("R$", "").replace("%", "").strip()
    if not bruto:
        return None

    negativo = bruto.startswith("-") or (bruto.startswith("(") and bruto.endswith(")"))
    bruto = bruto.strip("()-").strip()

    if "," in bruto:
        # Virgula e o decimal; ponto, se houver, e separador de milhar.
        limpo = bruto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", bruto):
        limpo = bruto.replace(".", "")
    else:
        limpo = bruto

    try:
        valor = float(limpo)
    except ValueError:
        return None
    return -valor if negativo else valor


def formatar(valor, formato: str) -> str:
    """O valor como ele aparece na celula."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, str):
        return valor

    if formato == "porcento":
        return _br(valor * 100 if abs(valor) <= 1 else valor, 2).rstrip("0").rstrip(",") + "%"
    if formato == "moeda":
        return "R$ " + _br(valor, 2)
    if formato == "data":
        try:
            return (date(1899, 12, 30).toordinal() + int(valor)) and \
                date.fromordinal(date(1899, 12, 30).toordinal() + int(valor)).strftime("%d/%m/%Y")
        except (ValueError, OverflowError):
            return _br(valor, 0)
    if formato == "numero":
        return _br(valor, 2)

    if float(valor).is_integer():
        return _br(valor, 0)
    return _br(valor, 2)


def _br(valor: float, casas: int) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").upper()


# --------------------------------------------------------- as formulas


class ErroFormula(Exception):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


TOKEN = re.compile(r"""
    (?P<numero>\d+(?:,\d+)?|\,\d+)
  | (?P<texto>"[^"]*")
  | (?P<faixa>\$?[A-Za-z]{1,2}\$?\d{1,4}\s*:\s*\$?[A-Za-z]{1,2}\$?\d{1,4})
  | (?P<celula>\$?[A-Za-z]{1,2}\$?\d{1,4})
  | (?P<funcao>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._]*)
  | (?P<op><=|>=|<>|[-+*/^()=<>;%&])
  | (?P<espaco>\s+)
""", re.VERBOSE)


def _tokenizar(formula: str) -> list[tuple[str, str]]:
    saida, pos = [], 0
    while pos < len(formula):
        achado = TOKEN.match(formula, pos)
        if not achado:
            raise ErroFormula(ERRO_VALOR)
        pos = achado.end()
        tipo = achado.lastgroup
        if tipo != "espaco":
            saida.append((tipo, achado.group()))
    return saida


class _Analisador:
    """
    Analisador descendente recursivo.

    Escrito a mao de proposito: a alternativa seria `eval`, e formula chega de
    planilha que veio de fora. Aqui o pior que uma formula estranha faz e
    devolver #NOME? numa celula.
    """

    def __init__(self, tokens: list[tuple[str, str]], resolver) -> None:
        self.tokens = tokens
        self.i = 0
        self.resolver = resolver          # (ref) -> valor da celula

    def _olhar(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _comer(self, texto: str | None = None) -> tuple[str, str]:
        atual = self._olhar()
        if atual is None or (texto and atual[1].upper() != texto.upper()):
            raise ErroFormula(ERRO_VALOR)
        self.i += 1
        return atual

    # -------------------------------------------------------- gramatica

    def expressao(self):
        """Comparacoes: o nivel mais frouxo."""
        esquerda = self.soma()
        while (atual := self._olhar()) and atual[1] in ("=", "<>", "<", ">", "<=", ">="):
            self._comer()
            direita = self.soma()
            esquerda = _comparar(atual[1], esquerda, direita)
        return esquerda

    def soma(self):
        valor = self.produto()
        while (atual := self._olhar()) and atual[1] in ("+", "-", "&"):
            self._comer()
            outro = self.produto()
            if atual[1] == "&":
                valor = _como_texto(valor) + _como_texto(outro)
            else:
                a, b = _como_numero(valor), _como_numero(outro)
                valor = a + b if atual[1] == "+" else a - b
        return valor

    def produto(self):
        valor = self.potencia()
        while (atual := self._olhar()) and atual[1] in ("*", "/"):
            self._comer()
            outro = _como_numero(self.potencia())
            if atual[1] == "*":
                valor = _como_numero(valor) * outro
            else:
                if outro == 0:
                    raise ErroFormula(ERRO_DIV)
                valor = _como_numero(valor) / outro
        return valor

    def potencia(self):
        valor = self.unario()
        if (atual := self._olhar()) and atual[1] == "^":
            self._comer()
            return _como_numero(valor) ** _como_numero(self.potencia())
        return valor

    def unario(self):
        atual = self._olhar()
        if atual and atual[1] == "-":
            self._comer()
            return -_como_numero(self.unario())
        if atual and atual[1] == "+":
            self._comer()
            return self.unario()
        return self.posfixo()

    def posfixo(self):
        valor = self.primario()
        if (atual := self._olhar()) and atual[1] == "%":
            self._comer()
            return _como_numero(valor) / 100
        return valor

    def primario(self):
        atual = self._olhar()
        if atual is None:
            raise ErroFormula(ERRO_VALOR)
        tipo, texto = atual

        if tipo == "numero":
            self._comer()
            return float(texto.replace(",", "."))
        if tipo == "texto":
            self._comer()
            return texto[1:-1]
        if tipo == "faixa":
            self._comer()
            return _Faixa(texto.replace("$", "").replace(" ", ""))
        if tipo == "celula":
            self._comer()
            return self.resolver(texto.replace("$", "").upper())
        if texto == "(":
            self._comer()
            valor = self.expressao()
            self._comer(")")
            return valor
        if tipo == "funcao":
            return self.funcao()
        raise ErroFormula(ERRO_VALOR)

    def funcao(self):
        _, nome = self._comer()
        chave = _sem_acento(nome).replace(".", "")
        if not (self._olhar() and self._olhar()[1] == "("):
            # VERDADEIRO e FALSO sao constantes, nao funcoes.
            if chave == "VERDADEIRO":
                return True
            if chave == "FALSO":
                return False
            raise ErroFormula(ERRO_NOME)

        self._comer("(")
        argumentos = []
        if self._olhar() and self._olhar()[1] != ")":
            argumentos.append(self.expressao())
            while self._olhar() and self._olhar()[1] == ";":
                self._comer(";")
                argumentos.append(self.expressao())
        self._comer(")")

        funcao = FUNCOES.get(chave)
        if funcao is None:
            raise ErroFormula(ERRO_NOME)
        return funcao(argumentos)


@dataclass
class _Faixa:
    """A1:B5 ainda sem resolver - quem resolve e a planilha."""

    texto: str
    valores: list = field(default_factory=list)


def _como_numero(valor) -> float:
    if isinstance(valor, _Faixa):
        valor = valor.valores[0] if valor.valores else 0
    if isinstance(valor, bool):
        return 1.0 if valor else 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if valor in (None, ""):
        return 0.0
    convertido = numero(valor)
    if convertido is None:
        raise ErroFormula(ERRO_VALOR)
    return convertido


def _como_texto(valor) -> str:
    if isinstance(valor, bool):
        return "VERDADEIRO" if valor else "FALSO"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return "" if valor is None else str(valor)


def _comparar(operador: str, a, b) -> bool:
    if isinstance(a, str) or isinstance(b, str):
        x, y = _como_texto(a).strip().lower(), _como_texto(b).strip().lower()
    else:
        x, y = _como_numero(a), _como_numero(b)
    return {
        "=": x == y, "<>": x != y,
        "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y,
    }[operador]


def _achatar(argumentos) -> list:
    saida = []
    for a in argumentos:
        if isinstance(a, _Faixa):
            saida.extend(a.valores)
        else:
            saida.append(a)
    return saida


def _numeros(argumentos) -> list[float]:
    achados = []
    for v in _achatar(argumentos):
        if isinstance(v, bool) or v in (None, ""):
            continue
        if isinstance(v, (int, float)):
            achados.append(float(v))
            continue
        convertido = numero(v)
        if convertido is not None:
            achados.append(convertido)
    return achados


def _criterio(valores: list, criterio) -> list[bool]:
    """
    O criterio de SOMASE e CONT.SE: ">100", "pago", "<>0".

    Texto compara sem diferenciar maiuscula, que e como o Excel faz e como a
    pessoa espera - "Pago" e "pago" sao o mesmo na planilha do escritorio.
    """
    bruto = _como_texto(criterio).strip()
    achado = re.match(r"^(<=|>=|<>|<|>|=)\s*(.*)$", bruto)
    operador, alvo = (achado.group(1), achado.group(2)) if achado else ("=", bruto)

    saida = []
    for v in valores:
        try:
            saida.append(_comparar(operador, v, alvo))
        except ErroFormula:
            saida.append(False)
    return saida


def _se(args):
    if len(args) < 2:
        raise ErroFormula(ERRO_VALOR)
    condicao = args[0]
    verdade = bool(condicao) if isinstance(condicao, bool) else _como_numero(condicao) != 0
    if verdade:
        return args[1]
    return args[2] if len(args) > 2 else False


def _somase(args):
    if len(args) < 2:
        raise ErroFormula(ERRO_VALOR)
    faixa = args[0].valores if isinstance(args[0], _Faixa) else [args[0]]
    soma_faixa = args[2].valores if len(args) > 2 and isinstance(args[2], _Faixa) else faixa
    marcas = _criterio(faixa, args[1])
    total = 0.0
    for i, marca in enumerate(marcas):
        if marca and i < len(soma_faixa):
            total += _numeros([soma_faixa[i]])[0] if _numeros([soma_faixa[i]]) else 0.0
    return total


def _contse(args):
    if len(args) < 2:
        raise ErroFormula(ERRO_VALOR)
    faixa = args[0].valores if isinstance(args[0], _Faixa) else [args[0]]
    return float(sum(1 for m in _criterio(faixa, args[1]) if m))


def _media(args):
    valores = _numeros(args)
    if not valores:
        raise ErroFormula(ERRO_DIV)
    return sum(valores) / len(valores)


def _se_erro(args):
    """SE.ERRO ja recebe o valor pronto; o erro vira excecao antes de chegar."""
    if not args:
        raise ErroFormula(ERRO_VALOR)
    return args[0]


def _hoje(args):
    hoje = date.today()
    return float(hoje.toordinal() - date(1899, 12, 30).toordinal())


FUNCOES = {
    "SOMA": lambda a: sum(_numeros(a)),
    "MEDIA": _media,
    "MAXIMO": lambda a: max(_numeros(a)) if _numeros(a) else 0.0,
    "MINIMO": lambda a: min(_numeros(a)) if _numeros(a) else 0.0,
    "CONT": lambda a: float(len([v for v in _achatar(a) if v not in (None, "")])),
    "CONTNUM": lambda a: float(len(_numeros(a))),
    "CONTSE": _contse,
    "SOMASE": _somase,
    "SE": _se,
    "SEERRO": _se_erro,
    "ARRED": lambda a: round(_como_numero(a[0]), int(_como_numero(a[1])) if len(a) > 1 else 0),
    "ABS": lambda a: abs(_como_numero(a[0])),
    "INT": lambda a: float(int(_como_numero(a[0]))),
    "HOJE": _hoje,
    "CONCATENAR": lambda a: "".join(_como_texto(v) for v in _achatar(a)),
    "MAIUSCULA": lambda a: _como_texto(a[0]).upper(),
    "MINUSCULA": lambda a: _como_texto(a[0]).lower(),
    "E": lambda a: all(bool(v) if isinstance(v, bool) else _como_numero(v) != 0 for v in _achatar(a)),
    "OU": lambda a: any(bool(v) if isinstance(v, bool) else _como_numero(v) != 0 for v in _achatar(a)),
    "NAO": lambda a: not (bool(a[0]) if isinstance(a[0], bool) else _como_numero(a[0]) != 0),
}

# O que a tela mostra no menu "Fórmulas", com a explicacao em portugues.
AJUDA_FUNCOES = [
    ("SOMA", "=SOMA(B1:B5)", "Soma os números da faixa."),
    ("MÉDIA", "=MÉDIA(B1:B5)", "Média dos números da faixa."),
    ("SE", '=SE(C4="pago";0;B4*0,1)', "Um valor se a condição for verdadeira, outro se não."),
    ("SOMASE", '=SOMASE(C1:C5;"em aberto";B1:B5)', "Soma só as linhas que atendem ao critério."),
    ("CONT.SE", '=CONT.SE(C1:C5;"em aberto")', "Conta quantas linhas atendem ao critério."),
    ("MÁXIMO", "=MÁXIMO(B1:B5)", "O maior número da faixa."),
    ("MÍNIMO", "=MÍNIMO(B1:B5)", "O menor número da faixa."),
    ("ARRED", "=ARRED(B4*0,1;2)", "Arredonda com o número de casas que você pedir."),
    ("HOJE", "=HOJE()", "A data de hoje."),
    ("CONCATENAR", '=CONCATENAR(A1;" - ";B1)', "Junta textos."),
]


# ------------------------------------------------------------ calcular


def calcular_aba(aba: Aba) -> dict:
    """
    Resolve a aba inteira e devolve o valor de cada celula.

    Formula que depende de formula e resolvida por recursao com memoria; a
    pilha de visitados pega referencia circular e devolve #CIRCULAR na celula,
    em vez de estourar a pilha do programa.
    """
    prontos: dict[str, object] = {}
    visitando: set[str] = set()

    def valor_de(ref: str):
        ref = ref.upper()
        if ref in prontos:
            return prontos[ref]
        if ref in visitando:
            raise ErroFormula(ERRO_CIRCULAR)
        if not RE_CELULA.match(ref):
            raise ErroFormula(ERRO_REF)

        celula = aba.celulas.get(ref)
        if celula is None or not celula.valor:
            prontos[ref] = ""
            return ""

        if not celula.e_formula:
            convertido = numero(celula.valor)
            resultado = convertido if convertido is not None else celula.valor
            prontos[ref] = resultado
            return resultado

        visitando.add(ref)
        try:
            resultado = _avaliar(celula.valor[1:], valor_de)
        except ErroFormula as exc:
            resultado = exc.codigo
        except RecursionError:
            resultado = ERRO_CIRCULAR
        except Exception:
            resultado = ERRO_VALOR
        finally:
            visitando.discard(ref)

        prontos[ref] = resultado
        return resultado

    saida = {}
    for ref in list(aba.celulas):
        bruto = valor_de(ref)
        celula = aba.celulas[ref]
        # Celula digitada e sem formato aparece exatamente como foi digitada.
        # Quem escreve "12.000,00" nao espera ver "12.000" de volta - a conta
        # usa o numero, mas a tela devolve o que a pessoa pôs ali.
        if not celula.e_formula and not celula.formato:
            texto = celula.valor
        else:
            texto = bruto if isinstance(bruto, str) else formatar(bruto, celula.formato)

        saida[ref] = {
            "bruto": bruto if not isinstance(bruto, float) else round(bruto, 10),
            "texto": texto,
            "erro": isinstance(bruto, str) and bruto.startswith("#"),
            "formula": celula.valor if celula.e_formula else "",
        }
    return saida


def _avaliar(formula: str, valor_de):
    def resolver(ref: str):
        return valor_de(ref)

    def faixa_resolvida(alvo: _Faixa) -> _Faixa:
        inicio, fim = alvo.texto.split(":")
        l1, c1 = _posicao(inicio)
        l2, c2 = _posicao(fim)
        if (l1, c1) > (l2, c2):
            l1, l2, c1, c2 = l2, l1, c2, c1
        valores = []
        for linha in range(min(l1, l2), max(l1, l2) + 1):
            for coluna in range(min(c1, c2), max(c1, c2) + 1):
                valores.append(valor_de(f"{letra_da_coluna(coluna)}{linha + 1}"))
        alvo.valores = valores
        return alvo

    tokens = _tokenizar(formula)
    analisador = _Analisador(tokens, resolver)
    # As faixas so sabem seus valores depois de resolvidas; o analisador as
    # devolve cruas e este envelope preenche na hora de usar.
    original = analisador.primario

    def primario():
        valor = original()
        return faixa_resolvida(valor) if isinstance(valor, _Faixa) else valor

    analisador.primario = primario
    resultado = analisador.expressao()
    if analisador.i < len(analisador.tokens):
        raise ErroFormula(ERRO_VALOR)
    if isinstance(resultado, _Faixa):
        return resultado.valores[0] if resultado.valores else ""
    return resultado


def resumo(aba: Aba, calculado: dict) -> dict:
    """Os numeros que a barra de status e o painel lateral mostram."""
    numeros = [
        v["bruto"] for v in calculado.values()
        if isinstance(v["bruto"], (int, float)) and not isinstance(v["bruto"], bool)
    ]
    return {
        "celulas": len(aba.celulas),
        "formulas": sum(1 for c in aba.celulas.values() if c.e_formula),
        "erros": sum(1 for v in calculado.values() if v["erro"]),
        "soma": round(sum(numeros), 2) if numeros else 0,
        "media": round(sum(numeros) / len(numeros), 2) if numeros else 0,
        "maximo": round(max(numeros), 2) if numeros else 0,
        "minimo": round(min(numeros), 2) if numeros else 0,
    }


def resumo_selecao(aba: Aba, calculado: dict, refs: list[str]) -> dict:
    numeros = []
    for ref in refs:
        valor = (calculado.get(ref.upper()) or {}).get("bruto")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            numeros.append(valor)
    return {
        "quantas": len(refs),
        "com_numero": len(numeros),
        "soma": round(sum(numeros), 2) if numeros else 0,
        "media": round(sum(numeros) / len(numeros), 2) if numeros else 0,
    }


# --------------------------------------------------------- entrar e sair


def de_csv(texto: str, nome: str = "Importado") -> Aba:
    """
    Le CSV, adivinhando o separador.

    Planilha exportada no Brasil quase sempre usa ponto e virgula, porque a
    virgula ja e o decimal. Adivinhar errado joga a linha inteira numa celula.
    """
    import csv
    import io

    amostra = texto[:4000]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t")
        separador = dialeto.delimiter
    except csv.Error:
        separador = ";" if amostra.count(";") >= amostra.count(",") else ","

    aba = Aba(nome=nome)
    leitor = csv.reader(io.StringIO(texto), delimiter=separador)
    for l, linha in enumerate(leitor):
        if l >= MAX_LINHAS:
            break
        for c, valor in enumerate(linha):
            if c >= MAX_COLUNAS:
                break
            if str(valor).strip():
                aba.gravar(f"{letra_da_coluna(c)}{l + 1}", {"valor": str(valor).strip()})
    return aba


def para_csv(aba: Aba, calculado: dict) -> str:
    """Sai com os valores calculados, nao com as formulas."""
    import csv
    import io

    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    for linha in range(aba.linhas):
        fila = []
        for coluna in range(aba.colunas):
            ref = f"{letra_da_coluna(coluna)}{linha + 1}"
            fila.append((calculado.get(ref) or {}).get("texto", ""))
        while fila and not fila[-1]:
            fila.pop()
        escritor.writerow(fila)
    return saida.getvalue()


def de_xlsx(dados: bytes) -> list[Aba]:
    import io

    from openpyxl import load_workbook

    livro = load_workbook(io.BytesIO(dados), data_only=False)
    abas = []
    for folha in livro.worksheets[:6]:
        aba = Aba(nome=str(folha.title)[:24])
        for linha in folha.iter_rows(max_row=min(folha.max_row or 1, MAX_LINHAS),
                                     max_col=min(folha.max_column or 1, MAX_COLUNAS)):
            for celula in linha:
                if celula.value is None:
                    continue
                valor = celula.value
                if isinstance(valor, datetime):
                    valor = valor.strftime("%d/%m/%Y")
                aba.gravar(celula.coordinate, {"valor": str(valor)})
        abas.append(aba)
    return abas or [Aba()]


def para_xlsx(abas: list[Aba], calculados: list[dict]) -> bytes:
    """
    Exporta com formula, nao so com o resultado.

    Quem abre no Excel espera continuar calculando. Mandar so o numero
    entregaria uma foto da planilha em vez da planilha.
    """
    import io

    from openpyxl import Workbook

    livro = Workbook()
    livro.remove(livro.active)

    for aba, calculado in zip(abas, calculados):
        folha = livro.create_sheet(title=aba.nome[:31] or "Página")
        for ref, celula in aba.celulas.items():
            if celula.e_formula:
                folha[ref] = celula.valor
            else:
                convertido = numero(celula.valor)
                folha[ref] = convertido if convertido is not None else celula.valor
            if celula.formato == "moeda":
                folha[ref].number_format = 'R$ #,##0.00'
            elif celula.formato == "porcento":
                folha[ref].number_format = "0.0%"
            elif celula.formato == "numero":
                folha[ref].number_format = "#,##0.00"
            if celula.negrito or celula.italico:
                from openpyxl.styles import Font

                folha[ref].font = Font(bold=celula.negrito, italic=celula.italico)
        if aba.congelar_cabecalho:
            folha.freeze_panes = "A2"

    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def de_dict(bruto: dict) -> list[Aba]:
    abas = []
    for item in bruto.get("abas", []):
        aba = Aba(
            nome=item.get("nome", "Página"),
            linhas=int(item.get("linhas", LINHAS_PADRAO)),
            colunas=int(item.get("colunas", COLUNAS_PADRAO)),
            congelar_cabecalho=bool(item.get("congelar_cabecalho")),
        )
        for ref, dados in (item.get("celulas") or {}).items():
            if isinstance(dados, dict):
                aba.celulas[ref.upper()] = Celula(
                    valor=str(dados.get("valor", "")),
                    formato=str(dados.get("formato", "")),
                    negrito=bool(dados.get("negrito")),
                    italico=bool(dados.get("italico")),
                )
        abas.append(aba)
    return abas or [Aba()]


def para_json(abas: list[Aba]) -> str:
    return json.dumps({"versao": 1, "abas": [a.to_dict() for a in abas]}, ensure_ascii=False)
