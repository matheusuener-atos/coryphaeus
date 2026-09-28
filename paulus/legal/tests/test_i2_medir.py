"""
Portao da I2 - as contas de tools/medir.py e o conjunto de exemplo.

  - Recall@k, MRR@k e percentil dao o numero certo em casos feitos a mao;
  - a frase esperada e achada mesmo com quebra de linha e sem acento;
  - o conjunto da demonstracao le, tem os seis tipos e de 8 a 10 perguntas
    de continuacao, e toda frase esperada existe num documento da demo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i2_medir.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  I2 - medicao")
    print("=" * 55)
    import medir

    print("\nas contas")
    textos = ["nada aqui", "a multa de 2% (dois\npor cento) sobre o valor", "foro da Comarca de Santarém"]
    esperados = ["multa de 2% (dois por cento)", "foro da comarca de santarem"]
    checar(medir.recall_em(textos, esperados, 1) == 0.0, "Recall@1: nenhuma no primeiro")
    checar(medir.recall_em(textos, esperados, 2) == 0.5, "Recall@2: uma de duas, com quebra de linha")
    checar(medir.recall_em(textos, esperados, 3) == 1.0, "Recall@3: as duas, sem acento e sem maiúscula")
    checar(medir.rr_em(textos, esperados, 6) == 0.5, "MRR: a primeira achada está na posição 2")
    checar(medir.rr_em(textos, ["não existe"], 6) == 0.0, "MRR: nenhuma achada, zero")
    checar(medir.percentil([1, 2, 3, 4, 100], 50) == 3 and medir.percentil([1, 2, 3, 4, 100], 95) == 100,
           "p50 e p95")
    p = {"alguma": ["não há", "não prevê"], "todas": [], "nunca": ["2%"], "minimo": None}
    checar(medir.conferir(p, "O contrato não prevê multa.")[0], "conferência: acha a ausência")
    checar(not medir.conferir(p, "Não há multa, mas há juros de 2%.")[0], "conferência: o `nunca` derruba")

    print("\no conjunto da demonstração")
    conjunto = medir.ler_conjunto(medir.CONJUNTO_DEMO)
    tipos = {p.get("tipo") for p in conjunto}
    checar(set(medir.TIPOS) <= tipos, "tem os seis tipos", sorted(tipos))
    continuacoes = [p for p in conjunto if p.get("continua")]
    checar(8 <= len(continuacoes) <= 10, f"de 8 a 10 continuações ({len(continuacoes)})")
    checar(all(p.get("trechos_esperados") for p in conjunto), "toda pergunta tem trechos esperados")
    from criar_demo import DOCUMENTOS

    texto = medir._compacto(" ".join(t for blocos in DOCUMENTOS.values() for _, t in blocos))
    faltam = [f for p in conjunto for f in p["trechos_esperados"] if medir._compacto(f) not in texto]
    checar(not faltam, "toda frase esperada existe num documento da demo", faltam)

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
