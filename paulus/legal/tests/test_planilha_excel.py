"""
Testes da planilha no jeito do Excel: inserir e excluir linha e coluna,
largura e altura guardadas, ocultar, comentario e gravar em lote.

O erro que guia estes testes: estrutura que muda e formula que nao acompanha.
Inserir uma linha no meio de uma tabela e ver =SOMA(B2:B10) continuar somando
B2:B10 - deixando a linha nova de fora - e um total errado com cara de certo.

    python tests/test_planilha_excel.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import planilha as P  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _tabela() -> P.Aba:
    aba = P.Aba()
    for i, v in enumerate([100, 200, 300, 400], start=2):
        aba.gravar(f"B{i}", {"valor": str(v)})
        aba.gravar(f"C{i}", {"valor": f"=B{i}*$E$1"})
    aba.gravar("E1", {"valor": "2"})
    aba.gravar("B6", {"valor": "=SOMA(B2:B5)"})
    return aba


def test_formula_acompanha() -> None:
    print("\nformula acompanha a estrutura")
    ajustar = P.ajustar_formula
    checar(ajustar("=SOMA(B2:B10)", "linhas", 5, 1, True) == "=SOMA(B2:B11)",
           "inserir no meio da faixa estica a faixa")
    checar(ajustar("=SOMA(B2:B10)", "linhas", 1, 2, True) == "=SOMA(B4:B12)",
           "inserir acima empurra a faixa inteira")
    checar(ajustar("=B7*$E$5+$E$1", "linhas", 3, 1, True) == "=B8*$E$6+$E$1",
           "o $ nao prende na mudanca de estrutura: a celula mudou de lugar")
    checar(ajustar("=SOMA(B2:B10)", "linhas", 9, 4, False) == "=SOMA(B2:B8)",
           "excluir o fim da faixa encolhe a faixa")
    checar(ajustar("=B5+1", "linhas", 5, 1, False) == "=#REF!+1",
           "referencia a celula excluida vira #REF!")
    checar(ajustar('=SE(A1="B5";1;0)', "linhas", 1, 3, True) == '=SE(A4="B5";1;0)',
           "o que esta entre aspas e texto, nao referencia")
    checar(ajustar("=SOMA(A1:C1)", "colunas", 1, 1, True) == "=SOMA(A1:D1)",
           "coluna inserida no meio estica a faixa")
    checar(ajustar("=D2*2", "colunas", 1, 2, False) == "=B2*2",
           "excluir colunas antes puxa a referencia para a esquerda")
    checar(ajustar("=SOMA(B2:B5)", "linhas", 2, 4, False) == "=SOMA(#REF!)",
           "faixa inteira excluida vira #REF!")
    checar(ajustar("=soma(b2:b5)", "linhas", 3, 1, True) == "=soma(B2:B6)",
           "minuscula tambem e referencia")


def test_inserir_e_excluir_linhas() -> None:
    print("\ninserir e excluir linhas")
    aba = _tabela()
    aba.medir(alturas={"4": 50})
    aba.ocultar(linhas=[5])
    feito = P.reestruturar(aba, "linhas", "inserir", 3, 2)
    c = P.calcular_aba(aba)
    checar(aba.obter("B5").valor == "200", "a linha 3 foi para a 5")
    checar(aba.obter("C5").valor == "=B5*$E$1", "e a formula dela acompanhou", aba.obter("C5").valor)
    checar(aba.obter("B8").valor == "=SOMA(B2:B7)", "o total estica e pega as linhas novas", aba.obter("B8").valor)
    checar(c["B8"]["bruto"] == 1000, f"e continua somando certo ({c['B8']['bruto']})")
    checar(aba.alturas == {"6": 50}, "a altura anda com a linha", str(aba.alturas))
    checar(aba.linhas_ocultas == [7], "o que estava oculto continua oculto", str(aba.linhas_ocultas))
    checar(feito["formulas"] >= 3, f"conta as formulas ajustadas ({feito['formulas']})")

    P.reestruturar(aba, "linhas", "excluir", 3, 2)
    checar(aba.obter("B3").valor == "200" and aba.obter("B6").valor == "=SOMA(B2:B5)",
           "excluir as linhas vazias volta ao que era")
    P.reestruturar(aba, "linhas", "excluir", 2, 1)
    c = P.calcular_aba(aba)
    checar(aba.obter("B5").valor == "=SOMA(B2:B4)" and c["B5"]["bruto"] == 900,
           "excluir uma linha de dados encolhe o total", aba.obter("B5").valor)

    aba = P.Aba()
    aba.gravar("A2", {"valor": "=A1*2"})
    aba.gravar("A1", {"valor": "3"})
    P.reestruturar(aba, "linhas", "excluir", 1, 1)
    c = P.calcular_aba(aba)
    checar(c["A1"]["texto"] == P.ERRO_REF, f"formula sem a celula mostra #REF! ({c['A1']['texto']})")


def test_colunas() -> None:
    print("\ninserir e excluir colunas")
    aba = _tabela()
    aba.medir(larguras={"C": 200})
    aba.gravar("A8", {"valor": "título", "juntar": 3})
    P.reestruturar(aba, "colunas", "inserir", 1, 1)
    checar(aba.obter("C2").valor == "100", "B foi para C")
    checar(aba.obter("D2").valor == "=C2*$F$1", "a formula segue, inclusive a absoluta", aba.obter("D2").valor)
    checar(aba.larguras == {"D": 200}, "a largura anda com a coluna", str(aba.larguras))
    checar(aba.obter("A8").juntar == 4, "coluna inserida dentro da juncao estica a juncao")

    P.reestruturar(aba, "colunas", "excluir", 1, 1)
    checar(aba.obter("B2").valor == "100" and aba.obter("C2").valor == "=B2*$E$1",
           "excluir a coluna vazia volta ao que era", aba.obter("C2").valor)

    cheia = P.Aba()
    cheia.gravar(f"{P.letra_da_coluna(P.MAX_COLUNAS - 1)}1", {"valor": "fim"})
    try:
        P.reestruturar(cheia, "colunas", "inserir", 0, 1)
        checar(False, "inserir que empurraria para fora da grade e recusado")
    except ValueError:
        checar(True, "inserir que empurraria para fora da grade e recusado")


def test_medidas_e_comentario() -> None:
    print("\nlargura, altura, ocultar e comentario ficam no documento")
    aba = P.Aba()
    aba.medir({"b": 5000, "C": 90}, {"2": 3, "9": 40})
    checar(aba.larguras == {"B": P.LARGURA_MAX, "C": 90}, "largura presa no limite", str(aba.larguras))
    checar(aba.alturas == {"2": P.ALTURA_MIN, "9": 40}, "altura presa no limite", str(aba.alturas))
    aba.medir({"C": None})
    checar("C" not in aba.larguras, "None volta ao padrao")
    aba.ocultar(colunas=["d", "B"], linhas=[3])
    checar(aba.colunas_ocultas == ["B", "D"] and aba.linhas_ocultas == [3], "ocultar guarda em ordem")
    aba.gravar("A1", {"comentario": "conferir com o cliente"})
    checar("A1" in aba.celulas, "celula so com comentario nao some")

    volta = P.de_dict(json.loads(P.para_json([aba])))[0]
    checar(volta.larguras == aba.larguras and volta.alturas == aba.alturas, "medidas voltam do JSON")
    checar(volta.colunas_ocultas == ["B", "D"] and volta.linhas_ocultas == [3], "ocultas voltam do JSON")
    checar(volta.obter("A1").comentario == "conferir com o cliente", "comentario volta do JSON")

    antigo = P.de_dict({"abas": [{"nome": "x", "celulas": {"A1": {"valor": "1"}}}]})[0]
    checar(antigo.larguras == {} and antigo.colunas_ocultas == [], "planilha antiga abre com tudo no padrao")

    aba.gravar("A1", {"comentario": ""})
    checar("A1" not in aba.celulas, "tirar o comentario da celula vazia apaga a celula")

    import io

    from openpyxl import load_workbook

    aba.gravar("B2", {"valor": "x", "comentario": "nota"})
    livro = load_workbook(io.BytesIO(P.para_xlsx([aba], [P.calcular_aba(aba)])))
    folha = livro.worksheets[0]
    checar(folha.column_dimensions["B"].width > 100, "a largura vai para o XLSX")
    checar(folha.column_dimensions["D"].hidden, "a coluna oculta vai oculta")
    checar(folha["B2"].comment is not None and folha["B2"].comment.text == "nota", "o comentario vai junto")


def test_lote() -> None:
    print("\ngravar em lote")
    aba = P.Aba()
    feitas = P.gravar_lote(aba, [
        {"ref": "A1", "dados": {"valor": "1", "formato": "moeda"}},
        {"ref": "a2", "dados": {"valor": "=A1+1", "juntar": 9}},
        {"ref": "ZZZ9", "dados": {"valor": "x"}},
        {"ref": "A3", "dados": "lixo"},
    ])
    checar(feitas == 2, f"so as validas entram ({feitas})")
    checar(aba.obter("A2").juntar == 1, "o lote nao junta celula por tabela")
    P.gravar_lote(aba, [{"ref": "A1", "dados": {"valor": "", "formato": ""}}])
    checar("A1" not in aba.celulas, "limpar pelo lote apaga a celula")


def test_rotas() -> None:
    print("\nas rotas da planilha")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    r = c.post("/api/documentos", json={"titulo": "Teste de planilha estrutura", "tipo": "planilha"})
    checar(r.status_code == 200, "planilha de teste criada")
    id_ = r.json()["id"]
    try:
        r = c.post(f"/api/planilha/{id_}/lote", json={"aba": 0, "nota": "colou", "itens": [
            {"ref": "A1", "dados": {"valor": "10"}}, {"ref": "A2", "dados": {"valor": "20"}},
            {"ref": "A3", "dados": {"valor": "=SOMA(A1:A2)"}}]})
        d = r.json()
        checar(r.status_code == 200 and d["calculado"][0]["A3"]["bruto"] == 30, "lote grava e calcula")
        checar(d.get("limites", {}).get("colunas") == P.MAX_COLUNAS, "a resposta diz ate onde a grade cresce")

        r = c.post(f"/api/planilha/{id_}/estrutura", json={"aba": 0, "eixo": "linhas", "acao": "inserir", "em": 2, "quantas": 1})
        d = r.json()
        checar(r.status_code == 200 and d["abas"][0]["celulas"]["A4"]["valor"] == "=SOMA(A1:A3)",
               "inserir linha pela rota ajusta a formula")
        r = c.post(f"/api/planilha/{id_}/estrutura", json={"aba": 0, "eixo": "colunas", "acao": "inserir", "em": "A", "quantas": 1})
        checar(r.status_code == 200 and "B4" in r.json()["abas"][0]["celulas"], "coluna pela letra")
        r = c.post(f"/api/planilha/{id_}/estrutura", json={"aba": 0, "eixo": "colunas", "acao": "sumir", "em": 0})
        checar(r.status_code == 400, "operacao desconhecida vira 400")

        r = c.post(f"/api/planilha/{id_}/layout", json={"aba": 0, "larguras": {"B": 190}, "alturas": {"4": 44},
                                                         "ocultar": {"colunas": ["C"]}})
        aba = r.json()["abas"][0]
        checar(r.status_code == 200 and aba["larguras"] == {"B": 190} and aba["alturas"] == {"4": 44},
               "largura e altura gravadas")
        checar(aba["colunas_ocultas"] == ["C"], "coluna oculta gravada")
        r = c.post(f"/api/planilha/{id_}/layout", json={"aba": 0, "reexibir": {"colunas": ["C"]}, "larguras": {"B": None}})
        aba = r.json()["abas"][0]
        checar(aba["colunas_ocultas"] == [] and aba["larguras"] == {}, "reexibir e voltar ao padrao")
        aba_de_novo = c.get(f"/api/planilha/{id_}").json()["abas"][0]
        checar(aba_de_novo["alturas"] == {"4": 44}, "a medida sobrevive a abrir de novo")

        r = c.post(f"/api/planilha/{id_}/celula", json={"aba": 0, "ref": "D9", "dados": {"comentario": "ver"}})
        checar(r.json()["abas"][0]["celulas"]["D9"]["comentario"] == "ver", "comentario pela rota da celula")
    finally:
        r = c.delete(f"/api/documentos/{id_}")
        try:
            lixo = r.json().get("lixeira")
        except ValueError:
            lixo = None
        if lixo:
            c.delete(f"/api/lixeira/{lixo}")


def main() -> int:
    print("=" * 55)
    print("PAULUS - planilha no jeito do Excel")
    print("=" * 55)
    test_formula_acompanha()
    test_inserir_e_excluir_linhas()
    test_colunas()
    test_medidas_e_comentario()
    test_lote()
    test_rotas()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s)")
        return 1
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
