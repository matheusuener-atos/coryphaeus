"""
O extrato do banco: ler o arquivo e conferir contra o que foi lancado.

Os dois lados sao testados separados, porque erram por motivos diferentes. A
leitura erra no formato - banco manda OFX sem fechar etiqueta, CSV com virgula
decimal, valor com o sinal depois do numero, texto em Latin-1. A conciliacao
erra no julgamento - casar dois honorarios iguais com a mesma linha do banco,
ou casar um pagamento com um lancamento de tres meses atras.

Rodar: venv\\Scripts\\python.exe tests\\test_extrato.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import extrato as E  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260910120000[-03:EST]
<TRNAMT>1200.00
<FITID>2026091001
<MEMO>PIX RECEBIDO COOPERATIVA BRASILEIRA
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260912
<TRNAMT>-350.90
<FITID>2026091202
<MEMO>PAGTO ALUGUEL SALA 402
</STMTTRN>
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""

CSV_BR = """Data;Histórico;Valor;Saldo
10/09/2026;PIX RECEBIDO COOPERATIVA BRASILEIRA;1.200,00;9.999,99
12/09/2026;PAGTO ALUGUEL SALA 402;-350,90;9.649,09
13/09/2026;TARIFA MENSALIDADE;-39,90;9.609,19
"""

CSV_SEM_CABECALHO = """13/09/2026,Recebimento de honorarios,800.50
14/09/2026,Compra material,-120.00
"""


def test_ler_ofx() -> None:
    print("\nler o OFX do banco")
    movimentos = E.ler(OFX.encode("utf-8"), "extrato.ofx")
    checar(len(movimentos) == 2, f"as duas linhas foram lidas ({len(movimentos)})")
    primeiro = movimentos[0]
    checar(primeiro.data == "2026-09-10" and primeiro.centavos == 120000,
           "data e valor de entrada", primeiro.to_dict())
    checar("COOPERATIVA" in primeiro.descricao and primeiro.documento == "2026091001",
           "o texto e o numero do banco vem junto", primeiro.to_dict())
    saida = movimentos[1]
    checar(saida.centavos == -35090 and saida.to_dict()["tipo"] == "despesa",
           "e o que saiu vem negativo", saida.to_dict())
    # Etiqueta sem fechar e o normal no OFX dos bancos: nao pode comer a linha.
    checar("[-03:EST]" not in primeiro.data, "o fuso do DTPOSTED nao entra na data")


def test_ler_csv() -> None:
    print("\nler o CSV, do jeito que cada banco exporta")
    movimentos = E.ler(CSV_BR.encode("cp1252"), "extrato.csv")
    checar(len(movimentos) == 3, f"tres linhas ({len(movimentos)})")
    checar(movimentos[0].centavos == 120000 and movimentos[1].centavos == -35090,
           "virgula decimal e ponto de milhar entendidos",
           [m.centavos for m in movimentos])
    checar("Histórico" not in " ".join(m.descricao for m in movimentos),
           "o cabecalho nao virou lancamento")
    checar(all(abs(m.centavos) != 999999 for m in movimentos),
           "e a coluna Saldo nao foi confundida com o valor",
           [m.to_dict() for m in movimentos])

    sem_cabeca = E.ler(CSV_SEM_CABECALHO.encode("utf-8"), "extrato.csv")
    checar(len(sem_cabeca) == 2 and sem_cabeca[0].centavos == 80050,
           "arquivo sem cabecalho tambem e lido", [m.to_dict() for m in sem_cabeca])
    checar(sem_cabeca[0].descricao.startswith("Recebimento"),
           "e a descricao e a coluna de texto", sem_cabeca[0].descricao)

    for dados, nome, pedaco in ((b"nada aqui", "extrato.csv", "lançamento nenhum"),
                                (b"qualquer coisa", "extrato.pdf", "OFX ou CSV")):
        try:
            E.ler(dados, nome)
            checar(False, f"recusa o arquivo que nao serve ({pedaco})")
        except ValueError as exc:
            checar(pedaco in str(exc), f"recusa dizendo o motivo: {exc}")


def _lancamento(id_, tipo, centavos, vencimento, descricao, cliente="", liquidado=""):
    return {"id": id_, "tipo": tipo, "centavos": centavos, "vencimento": vencimento,
            "descricao": descricao, "cadastro_nome": cliente, "liquidado_em": liquidado}


def test_conciliar() -> None:
    print("\nconferir o extrato contra os lancamentos")
    movimentos = E.ler(OFX.encode("utf-8"), "extrato.ofx")
    lancamentos = [
        _lancamento(1, "recebimento", 120000, "2026-09-10", "Honorários de setembro", "Cooperativa Brasileira"),
        _lancamento(2, "despesa", 35090, "2026-09-05", "Aluguel da sala"),
        _lancamento(3, "recebimento", 120000, "2026-09-10", "Honorários de outro cliente", "Fornecedor A"),
        _lancamento(4, "recebimento", 120000, "2026-09-10", "Já recebido", "Outro", liquidado="2026-09-09"),
    ]
    pares = E.conciliar(movimentos, lancamentos)
    checar(len(pares) == 2, "um par por linha do extrato")
    entrada = pares[0]
    checar(entrada.lancamento and entrada.lancamento["id"] == 1,
           "o nome no texto do banco desempata entre dois valores iguais",
           entrada.to_dict())
    checar("nome parecido" in " ".join(entrada.motivos), "e o motivo diz por que", entrada.motivos)
    saida = pares[1]
    checar(saida.lancamento and saida.lancamento["id"] == 2,
           "a despesa casa com a despesa, dentro da janela de dias", saida.to_dict())
    checar(all((p.lancamento or {}).get("id") != 4 for p in pares),
           "lancamento ja liquidado nao entra na conferencia")

    # Sem candidato: a linha volta sozinha, e nao casada a forca.
    sozinho = E.conciliar(E.ler(CSV_BR.encode("cp1252"), "e.csv"), [])
    checar(all(p.lancamento is None for p in sozinho), "sem lancamento, nada e casado")
    checar("sem lançamento parecido" in sozinho[0].to_dict()["porque"], "e a tela sabe dizer isso")

    # Cada lancamento vale uma vez: dois PIX iguais nao dao baixa no mesmo.
    dois_iguais = E.conciliar(
        [E.Movimento(data="2026-09-10", descricao="PIX COOPERATIVA", centavos=120000),
         E.Movimento(data="2026-09-10", descricao="PIX COOPERATIVA", centavos=120000)],
        [lancamentos[0]])
    checar(dois_iguais[0].lancamento and dois_iguais[1].lancamento is None,
           "o segundo movimento igual fica sem par, em vez de repetir a baixa")

    # Longe demais no tempo nao e o mesmo pagamento.
    velho = E.conciliar([E.Movimento(data="2026-09-10", descricao="PIX", centavos=120000)],
                        [_lancamento(9, "recebimento", 120000, "2026-05-10", "Honorários de maio")])
    checar(velho[0].lancamento is None, "vencimento de quatro meses atras nao casa")


def test_resumo_e_meses() -> None:
    print("\no que a tela mostra em cima da lista")
    pares = E.conciliar(E.ler(CSV_BR.encode("cp1252"), "e.csv"),
                        [_lancamento(1, "recebimento", 120000, "2026-09-10", "Honorários", "Cooperativa")])
    r = E.resumo(pares)
    checar(r["movimentos"] == 3 and r["conciliados"] == 1 and r["sozinhos"] == 2,
           "quantos entraram, quantos casaram", r)
    checar(r["entradas"] == 120000 and r["saidas"] == 39080, "entradas e saidas somadas", r)
    checar(r["de"] == "2026-09-10" and r["ate"] == "2026-09-13", "e o periodo do arquivo", r)

    meses = E.meses_do_extrato(E.ler(CSV_BR.encode("cp1252"), "e.csv"))
    checar(meses == ["2026-08", "2026-09"],
           "o mes anterior entra na busca: boleto vence num mes e cai no outro", meses)


def main() -> int:
    print("=" * 55)
    print("  PAULUS - o extrato do banco")
    print("=" * 55)
    test_ler_ofx()
    test_ler_csv()
    test_conciliar()
    test_resumo_e_meses()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
