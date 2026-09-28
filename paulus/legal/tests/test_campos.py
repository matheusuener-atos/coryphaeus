"""
Testes dos campos de CPF, CNPJ e telefone (frontend/js/39-campos.js).

O JavaScript roda no Node e e comparado com uma conta de referencia feita
aqui, em Python, a parte: os digitos verificadores do CPF e do CNPJ (o
numerico e o alfanumerico da Receita, IN RFB 2.229/2024), em documentos
gerados com os verificadores certos e com um deles trocado. E confere a
formatacao enquanto se digita.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_campos.py
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
JS = RAIZ / "frontend" / "js" / "39-campos.js"
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


# ----------------------------------------------------- a conta de referencia

def dv_cpf(nove: str) -> str:
    d = [int(c) for c in nove]
    for n in (9, 10):
        soma = sum(d[i] * (n + 1 - i) for i in range(n))
        d.append((soma * 10) % 11 % 10)
    return "".join(map(str, d[9:]))


def dv_cnpj(doze: str) -> str:
    v = [ord(c) - 48 for c in doze]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(a * b for a, b in zip(v, pesos)) % 11
        v.append(0 if resto < 2 else 11 - resto)
    return "".join(str(x) for x in v[12:])


def rodar_js(chamadas: list[list]) -> list:
    """Cada chamada e [funcao, argumento]; devolve o resultado de cada uma."""
    codigo = JS.read_text(encoding="utf-8") + "\n;const __c = " + json.dumps(chamadas) + ";\n" \
        "process.stdout.write(JSON.stringify(__c.map(([f, a]) => eval(f)(a))));"
    r = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def test_verificadores() -> None:
    print("\nos digitos verificadores, contra a conta de referencia")
    sorte = random.Random(27)
    casos, esperado = [], []
    for _ in range(40):
        nove = "".join(sorte.choice("0123456789") for _ in range(9))
        certo = nove + dv_cpf(nove)
        errado = certo[:10] + str((int(certo[10]) + 1) % 10)
        casos += [["cpfValido", certo], ["cpfValido", errado]]
        esperado += [len(set(certo)) > 1, False]
    for alfabeto in ("0123456789", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        for _ in range(40):
            doze = "".join(sorte.choice(alfabeto) for _ in range(12))
            certo = doze + dv_cnpj(doze)
            errado = certo[:13] + str((int(certo[13]) + 1) % 10)
            casos += [["cnpjValido", certo], ["cnpjValido", errado]]
            esperado += [len(set(certo)) > 1, False]
    obtido = rodar_js(casos)
    erros = [(c, o, e) for c, o, e in zip(casos, obtido, esperado) if o != e]
    checar(not erros, f"{len(casos)} CPFs e CNPJs (numericos e alfanumericos) batem com a referencia", erros[:3])
    checar(rodar_js([["cpfValido", "111.111.111-11"], ["cnpjValido", "00.000.000/0000-00"]]) == [False, False],
           "sequencia repetida nao passa, mesmo com a conta fechando")
    exemplo = "12ABC34501DE"
    checar(rodar_js([["cnpjValido", exemplo + dv_cnpj(exemplo)]]) == [True] and dv_cnpj(exemplo) == "35",
           "o exemplo da Receita (12.ABC.345/01DE-35) fecha")


def test_formatacao() -> None:
    print("\na formatacao enquanto se digita")
    casos = [
        ("formatarCpf", "52998224725", "529.982.247-25"),
        ("formatarCpf", "5299", "529.9"),
        ("formatarCpf", "529.982.247-2599", "529.982.247-25"),
        ("formatarCnpj", "11222333000181", "11.222.333/0001-81"),
        ("formatarCnpj", "12abc34501de35", "12.ABC.345/01DE-35"),
        ("formatarCpfOuCnpj", "52998224725", "529.982.247-25"),
        ("formatarCpfOuCnpj", "112223330001", "11.222.333/0001"),
        ("formatarCpfOuCnpj", "12ABC", "12.ABC"),
        ("formatarTelefone", "62999998888", "(62) 99999-8888"),
        ("formatarTelefone", "6232221111", "(62) 3222-1111"),
        ("formatarTelefone", "+55 62 99999-8888", "(62) 99999-8888"),
        ("formatarTelefone", "629999", "(62) 9999"),
        ("formatarTelefone", "08007271234", "0800 727 1234"),
        ("formatarTelefone", "+1 415 555 0100", "+1 415 555 0100"),
    ]
    obtido = rodar_js([[f, a] for f, a, _ in casos])
    for (f, a, e), o in zip(casos, obtido):
        checar(o == e, f"{f}({a!r}) = {e!r}", o)


def test_problemas() -> None:
    print("\no aviso de cada campo")
    casos = [
        (["cpf", ""], ""),
        (["cpf", "529.982.247-25"], ""),
        (["cpf", "529.982.247-26"], "CPF inválido: confira os números"),
        (["cpf", "529.982"], "CPF incompleto: são 11 números"),
        (["cnpj", "11.222.333/0001-81"], ""),
        (["cpf-cnpj", "11.222.333/0001-80"], "CNPJ inválido: confira os caracteres"),
        (["telefone", "(62) 99999-8888"], ""),
        (["telefone", "(62) 3222-1111"], ""),
        (["telefone", "(62) 8999-88888"], "telefone incompleto: DDD e número, como (62) 99999-8888"),
        (["telefone", "(62) 9999"], "telefone incompleto: DDD e número, como (62) 99999-8888"),
    ]
    codigo_chamadas = [["(a) => problemaDoCampo(a[0], a[1])", c] for c, _ in casos]
    obtido = rodar_js(codigo_chamadas)
    for (c, e), o in zip(casos, obtido):
        checar(o == e, f"{c[0]} {c[1]!r} -> {e or 'certo'}", o)


def main() -> int:
    print("=" * 55)
    print("  CPF, CNPJ e telefone")
    print("=" * 55)
    if not shutil.which("node"):
        print("\n  pulado: Node nao instalado")
        return 0
    test_verificadores()
    test_formatacao()
    test_problemas()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
