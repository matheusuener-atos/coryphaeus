"""
N5 - a cláusula no estilo "1. DO OBJETO" (src/redacao.py, src/passos.py).

  - achada no texto puro e no HTML do editor, com o título; as subcláusulas
    ("1.1") e a lista numerada em minúsculas não entram;
  - só com duas ou mais, numeração andando: "1. DOS FATOS" solto não vira
    contrato; e só quando o documento não tem cláusula com a palavra;
  - renumerar troca só o número (e o separador fica como está), e leva a
    referência "cláusula 3" junto;
  - revisar contra o padrão (L4): o padrão com "CLÁUSULA 1ª – DO OBJETO" e o
    contrato com "1. DO OBJETO" se alinham pelo título, e a alterada é achada.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n5_clausulas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


CONTRATO = """CONTRATO DE LOCAÇÃO
1. DO OBJETO
O presente contrato tem por objeto a locação do imóvel da Rua A, 10.
1.1 O imóvel se destina a uso residencial.
3. DO PRAZO
O prazo é de 12 meses, renovável nos termos da cláusula 4.
4 – DAS OBRIGAÇÕES DA LOCATÁRIA
Pagar o aluguel até o dia 5 de cada mês.
5) DA MULTA
A multa por atraso é de dez por cento do valor do aluguel.
"""

PADRAO = """CLÁUSULA 1ª – DO OBJETO
O presente contrato tem por objeto a locação do imóvel da Rua A, 10.
CLÁUSULA 2ª – DO PRAZO
O prazo é de 12 meses, renovável nos termos da cláusula 3.
CLÁUSULA 3ª – DAS OBRIGAÇÕES DA LOCATÁRIA
Pagar o aluguel até o dia 5 de cada mês.
CLÁUSULA 4ª – DA MULTA
A multa por atraso é de dois por cento do valor do aluguel.
"""


def main() -> int:
    print("=" * 55)
    print("  N5 — a cláusula “1. DO OBJETO”")
    print("=" * 55)
    import passos
    import redacao

    print("\nachar")
    a = redacao.achar_clausulas(CONTRATO)
    checar([(x["estilo"], x["numero"], x["titulo"]) for x in a] ==
           [("titulo", 1, "DO OBJETO"), ("titulo", 3, "DO PRAZO"), ("titulo", 4, "DAS OBRIGAÇÕES DA LOCATÁRIA"), ("titulo", 5, "DA MULTA")],
           "as quatro, com o título; o “1.1” não entra", [(x["numero"], x.get("titulo")) for x in a])
    html = "<h2>CONTRATO</h2><p>1. DO OBJETO</p><p>Texto.</p><p>2. DO PRAZO</p><p>Doze meses.</p>"
    checar([x["numero"] for x in redacao.achar_clausulas(html)] == [1, 2], "no HTML do editor")
    checar(redacao.achar_clausulas("1. DOS FATOS\nO autor comprou.\n") == [], "um título solto não vira contrato")
    checar(redacao.achar_clausulas("1. o locatário pagará\n2. o locador entregará\n") == [], "lista numerada em minúsculas não entra")
    checar(redacao.achar_clausulas("7. DOS FATOS\nx\n2. DO DIREITO\ny\n9. DOS PEDIDOS\nz\n") == [], "números que não andam não entram")
    mistura = "CLÁUSULA 1ª – DO OBJETO\nTexto.\n2. DO PRAZO\nx\n3. DA MULTA\ny\n"
    checar([x["estilo"] for x in redacao.achar_clausulas(mistura)] == ["depois"], "com a palavra “cláusula” no documento, vale só ela")
    checar(redacao.estilo_do_documento(CONTRATO) == "titulo", "o estilo do documento é “titulo”")

    print("\nrenumerar")
    r = redacao.renumerar(CONTRATO)
    t = r["texto"]
    checar("2. DO PRAZO" in t and "3 – DAS OBRIGAÇÕES" in t and "4) DA MULTA" in t and "1.1 O imóvel" in t,
           "troca só o número; o separador fica como está", t)
    checar("nos termos da cláusula 3." in t and r["referencias"], "a referência vai junto", r["referencias"])
    checar(all(x["de"][0].isdigit() for x in r["trocas"] if x["tipo"] == "clausula"), "as trocas mostram só a marca (número e separador)", r["trocas"])
    checar(redacao.renumerar(t)["trocas"] == [], "renumerar de novo não muda nada")

    print("\nrevisar contra o padrão (L4)")
    cp, cc = passos.clausulas_de(PADRAO), passos.clausulas_de(CONTRATO)
    comps = [passos.comparar(par) for par in passos.alinhar(cp, cc)]
    sit = {(c["padrao"] or c["contrato"])["titulo"].split("–")[-1].split(".")[-1].split(")")[-1].strip(): c["situacao"] for c in comps}
    checar(len(cc) == 4 and all(c["padrao"] and c["contrato"] for c in comps) and sit.get("DAS OBRIGAÇÕES DA LOCATÁRIA") == "igual",
           "“CLÁUSULA 3ª – DAS OBRIGAÇÕES” e “4 – DAS OBRIGAÇÕES” se alinham pelo título; as quatro têm par", sit)
    objeto = next(c for c in comps if "OBJETO" in c["padrao"]["titulo"])
    checar(objeto["situacao"] == "alterada" and any("residencial" in s for s in objeto["entrou"]),
           "o subitem 1.1, que o padrão não tem, aparece como o que entrou", objeto.get("entrou"))
    multa = next(c for c in comps if "MULTA" in (c["padrao"] or c["contrato"])["titulo"])
    checar(multa["situacao"] == "alterada" and any("dez" in s for s in multa["entrou"]), "a alterada é achada, com o que entrou", multa.get("entrou"))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
