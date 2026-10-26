"""
A jurisprudência do TST que vem com o PAULUS (tools/jurisprudencia_pacote.py) e
o material que é só do trabalho (src/material.py, _da_area).

  - o RTF vira texto: acento em \\'e9 e em \\u233?, parágrafo, destino que não é texto;
  - do livro do TST entra o que vale hoje: o cancelado e o histórico ficam fora,
    a tese do IRR vai junto do verbete, o código separado por espaço (Súmula
    443) e com espaço na frente (Súmula 72) entram, o índice remissivo não;
  - o texto sai no formato que a Biblioteca divide um verbete por trecho;
  - o material só do trabalho não entra na pergunta que não é do trabalho
    (o Precedente Normativo 72, multa por atraso de salário, na pergunta da
    multa por atraso no aluguel), e entra na que é.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_acervo_tst.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))
TMP = Path(tempfile.mkdtemp(prefix="paulus-tst-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")

import jurisprudencia_pacote as jp  # noqa: E402
import rtf_em_texto  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_rtf() -> None:
    print("\no RTF vira texto")
    rtf = (rb"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0 Times New Roman;}}{\colortbl;\red0\green0\blue0;}"
           rb"{\*\generator Word;}\pard Prescri\'e7\'e3o\par Per\u237?odo de f\u233?rias\tab fim\par"
           rb"{\pict 89504e47}{\header Cabe\'e7alho}texto ap\'f3s}")
    t = rtf_em_texto.converter(rtf)
    checar("Prescrição\n" in t and "Período de férias\tfim" in t and "texto após" in t,
           "acentos dos dois jeitos, parágrafo e tabulação", t)
    checar("Times New Roman" not in t and "Word" not in t and "89504e47" not in t and "Cabeçalho" not in t,
           "fonte, gerador, figura e cabeçalho de página ficam fora", t)


LIVRO = "\n".join(["capa"] * 3 + [
    "SUM-8\tJUNTADA DE DOCUMENTO (mantida - Res. 121/2003, DJ 19, 20 e 21.11.2003). - Entendimento reafirmado no IRR nº 286.",
    "A juntada de documentos na fase recursal só se justifica quando provado o justo impedimento.",
    "IRR-286\tJUNTADA DE DOCUMENTO NA FASE RECURSAL. (RR-0010013-87.2024.5.03.0073, Tribunal Pleno)",
    "A juntada na fase recursal só se justifica com justo impedimento.",
    "Histórico:",
    "Redação original - RA 28/1969",
    "Nº 8 A juntada de documentos na fase recursal só se justifica (redação velha).",
    "SUM-11\tHONORÁRIOS DE ADVOGADO (cancelada) - Res. 121/2003, DJ 19, 20 e 21.11.2003",
    "É inaplicável na Justiça do Trabalho o disposto no art. 64 do CPC.",
    "Histórico:",
    "  SUM-72\tAPOSENTADORIA (nova redação) - Res. 121/2003",
    "O prêmio-aposentadoria instituído por norma regulamentar não está condicionado à lei.",
    "SUM-437 INTERVALO INTRAJORNADA (cancelada por perda de eficácia a partir de 11.11.2017, pela Lei 13.467/2017) – Res. 225/2025",
    "I - Após a edição da Lei nº 8.923/94, a não-concessão do intervalo implica pagamento total.",
    "SUM-443 DISPENSA DISCRIMINATÓRIA. PRESUNÇÃO (Res. 185/2012, DEJT divulgado em 25.09.2012)",
    "Presume-se discriminatória a despedida de empregado portador de doença grave.",
    "OJ-SDI1-394\tREPOUSO SEMANAL REMUNERADO. INTEGRAÇÃO DAS HORAS EXTRAS. (nova redação - IncJulgRREmbRep)",
    "I - A majoração do repouso semanal remunerado deve repercutir no cálculo das demais parcelas.",
    "\tHistórico:",
    "Nº 394. REPOUSO SEMANAL REMUNERADO. NÃO REPERCUSSÃO (a de antes)",
    "PN-72\t\tMULTA. ATRASO NO PAGAMENTO DE SALÁRIO (positivo)",
    "Estabelece-se multa de 10% sobre o saldo salarial, na hipótese de atraso no pagamento de salário.",
    "PN-1\t\tANTECIPAÇÃO SALARIAL TRIMESTRAL (negativo) – (cancelado pela SDC em sessão de 14.09.1998)",
    "Não se concede antecipação salarial trimestral.",
] + ["enchimento"] * 1000 + [
    "Índice Remissivo",
    "SUM-999\tVerbete que só existe no índice",
    "Texto do índice.",
])


def test_livro_do_tst() -> None:
    print("\no livro do TST")
    saida, contas = jp.verbetes_do_tst(LIVRO)
    sumulas = {n: (t, e) for n, t, e in saida["SUM"]}
    checar(set(sumulas) == {"8", "72", "443"}, "vigentes entram; canceladas (11, 437) e o índice (999) não", sorted(sumulas))
    checar(sumulas["8"][0] == "JUNTADA DE DOCUMENTO" and "Res." not in sumulas["8"][0],
           "o título sem a situação nem a resolução", sumulas["8"][0])
    checar("[Reafirmado no IRR nº 286, tese vinculante:" in sumulas["8"][1] and "redação velha" not in sumulas["8"][1],
           "a tese do IRR vai junto, o histórico não", sumulas["8"][1])
    checar("prêmio-aposentadoria" in sumulas["72"][1] and "doença grave" in sumulas["443"][1],
           "o código com espaço na frente (72) e separado por espaço (443)")
    ojs = {n: e for n, t, e in saida["OJ-SDI1"]}
    checar("394" in ojs and "a de antes" not in ojs["394"], "OJ: o histórico com tabulação na frente também fica fora", ojs)
    pns = {n for n, t, e in saida["PN"]}
    checar(pns == {"72"}, "precedente normativo cancelado pela SDC fica fora", pns)
    checar(contas["canceladas_fora"] == 3 and contas["irr_juntos"] == 1, "as contas", contas)
    texto, n = jp.texto_do_pacote(saida, ("SUM",))
    checar(texto.startswith("Súmula 8 do TST\nJUNTADA DE DOCUMENTO. A juntada") and n == 3 and "Súmula 72 do TST" in texto,
           "o texto sai como 'Súmula N do TST', em ordem", texto[:80])
    from biblioteca import sumulas as fatiador

    fatias = fatiador.fatiar(texto + "Precedente Normativo 72 do TST\nMULTA. Estabelece-se multa.\n", "TST")
    checar(len(fatias) == 4 and fatias[-1].caminho.endswith("Precedente Normativo 72"),
           "a Biblioteca divide um verbete por trecho, também o precedente normativo", [f.caminho for f in fatias])


def test_so_do_trabalho() -> None:
    print("\no material só do trabalho")
    import material as material_mod
    from biblioteca import nativo

    m = material_mod.Material(TMP / "material")
    m.absorver_texto("Precedentes Normativos do TST",
                     "Precedente Normativo 72 do TST\nMULTA. ATRASO NO PAGAMENTO DE SALÁRIO. Estabelece-se multa de "
                     "10% sobre o saldo salarial, na hipótese de atraso no pagamento de salário até 20 dias.\n\n"
                     "Precedente Normativo 73 do TST\nMULTA. OBRIGAÇÃO DE FAZER. Impõe-se multa por descumprimento.\n\n"
                     "Precedente Normativo 74 do TST\nDESCONTO ASSISTENCIAL. Subordina-se o desconto à não oposição.\n\n"
                     "Precedente Normativo 75 do TST\nCONTRATO DE EXPERIÊNCIA. Readmissão.\n\n"
                     "Precedente Normativo 76 do TST\nAVISO PRÉVIO. Redução da jornada.\n",
                     nativo.ficha_das_sumulas("Precedentes Normativos do TST"))
    ficha = nativo.ficha_das_sumulas("Súmulas do TST")
    checar(ficha["autor"] == "Tribunal Superior do Trabalho" and set(ficha["areas"]) == {"trabalho", "processo do trabalho"},
           "a ficha do TST diz o tribunal e as áreas do trabalho", ficha)
    civil = m.consultar("qual a multa por atraso no pagamento do aluguel?")
    checar(civil == [], "pergunta que não é do trabalho: o TST não entra", [h.doc_name for h in civil])
    trabalho = m.consultar("qual a multa por atraso no pagamento do salário do empregado?")
    checar(trabalho and trabalho[0].doc_name == "Precedentes Normativos do TST",
           "pergunta do trabalho: entra", [h.doc_name for h in trabalho])


def main() -> int:
    print("=" * 55)
    print("  a jurisprudência do TST no acervo")
    print("=" * 55)
    try:
        test_rtf()
        test_livro_do_tst()
        test_so_do_trabalho()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
