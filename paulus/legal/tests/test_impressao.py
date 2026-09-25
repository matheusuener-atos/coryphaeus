"""
Imprimir direto, sem o dialogo do navegador.

A impressao de verdade vai para a "Microsoft Print to PDF" com arquivo de
saida - o caminho inteiro (listar, abrir o driver, desenhar a pagina, fechar
o trabalho) sem papel e sem janela. Se essa impressora nao estiver instalada,
essa parte e pulada e o resto ainda roda.

Rodar: venv\\Scripts\\python.exe tests\\test_impressao.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import documento as D  # noqa: E402
import impressao  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


def test_paginas() -> None:
    print("\nquais páginas")
    checar(impressao.paginas_pedidas("todas", 3) == [1, 2, 3], "todas")
    checar(impressao.paginas_pedidas("1-2, 5", 6) == [1, 2, 5], "intervalo e avulsa")
    checar(impressao.paginas_pedidas("2", 3) == [2], "uma só")
    for torto in ("9", "0", "3-1", "abc"):
        try:
            impressao.paginas_pedidas(torto, 5)
            checar(False, f"'{torto}' é recusado")
        except impressao.ErroDeImpressao:
            checar(True, f"'{torto}' é recusado, com frase")


def test_listar_e_imprimir() -> None:
    print("\nimpressoras")
    if not impressao.disponivel():
        print("  (fora do Windows - pulado)")
        return
    lista = impressao.listar()
    checar(isinstance(lista, list), "lista as impressoras", lista)
    if lista:
        checar(sum(1 for i in lista if i["padrao"]) <= 1, "no máximo uma padrão")
        checar(lista[0]["padrao"] or not any(i["padrao"] for i in lista), "a padrão vem primeiro")

    pdf_virtual = next((i["nome"] for i in lista if i["nome"] == "Microsoft Print to PDF"), None)
    if not pdf_virtual:
        print("  (sem 'Microsoft Print to PDF' - impressão de verdade pulada)")
        return
    blocos = D.ler_html("".join(f"<p>Parágrafo {i} de teste para encher a folha.</p>" for i in range(90)))
    pdf = D.para_pdf(blocos, "Teste de impressão", "rodapé")
    with tempfile.TemporaryDirectory() as pasta:
        saida = str(Path(pasta) / "impresso.pdf")
        r = impressao.imprimir(pdf, pdf_virtual, "Teste de impressão", paginas="1-2", saida=saida)
        checar(r["folhas"] == 2, "duas páginas foram ao spooler", r)
        for _ in range(40):
            if Path(saida).exists() and Path(saida).stat().st_size > 0:
                break
            time.sleep(0.25)
        existe = Path(saida).exists() and Path(saida).stat().st_size > 0
        checar(existe, "o arquivo impresso saiu")
        if existe:
            from pypdf import PdfReader
            checar(len(PdfReader(saida).pages) == 2, "com as duas páginas pedidas")

    try:
        impressao.imprimir(pdf, "Impressora que não existe", paginas="1")
        checar(False, "impressora sumida é recusada")
    except impressao.ErroDeImpressao:
        checar(True, "impressora sumida é recusada, com frase")


if __name__ == "__main__":
    test_paginas()
    test_listar_e_imprimir()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    print("  todos os testes passaram")
