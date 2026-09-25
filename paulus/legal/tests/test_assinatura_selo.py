"""
Testes do selo posto a mao: posicao e tamanho vindos da tela.

A tela de assinar deixa a pessoa adicionar o selo, arrastar e redimensionar
(sempre na mesma proporcao). O que ela ve precisa ser o que o PDF recebe:

  - sem tamanho, tudo continua como antes (o canto escolhido, 228 x 62 pt)
  - com tamanho, a proporcao se mantem e o selo nao sai da pagina
  - a posicao vem com origem no canto de cima e vira a do PDF (embaixo)
  - o campo da assinatura no PDF assinado tem a largura pedida
  - a rota leva o tamanho ate o assinador
  - depois do sim na fila, a resposta traz o desfecho para a tela abrir

Nada aqui toca a fila, o cofre ou o acervo de verdade: cada teste troca
essas pecas por copias temporarias e devolve no fim.

    python tests/test_assinatura_selo.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import assinatura  # noqa: E402
import certificado  # noqa: E402

SENHA = "senha-de-teste-123"

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _pdf_de_teste(pasta: Path) -> Path | None:
    for origem in sorted((RAIZ / "data" / "test_contracts").glob("*.pdf")):
        if assinatura.ler(origem).assinaturas == 0:
            return Path(shutil.copy(origem, pasta / "documento.pdf"))
    return None


def test_medidas() -> None:
    print("\nmedidas do selo")
    checar(assinatura.medidas_do_selo(None) == (228.0, 62.0), "sem tamanho, o de sempre")
    w, h = assinatura.medidas_do_selo(342)
    checar(w == 342 and abs(h - 93) < 0.01, f"com tamanho, mantem a proporcao ({w} x {h})")
    w, _ = assinatura.medidas_do_selo(10)
    checar(w == assinatura.SELO_MIN, "pequeno demais fica no minimo legivel")
    w, _ = assinatura.medidas_do_selo(5000, 595)
    checar(w <= 595, "grande demais nao passa da largura da pagina")


def test_caixa() -> None:
    print("\ncaixa do selo na pagina")
    L, A = 595.0, 842.0
    checar(assinatura.caixa_na_pagina("rodape_direita", None, L, A) == assinatura.caixa("rodape_direita", L, A),
           "sem ponto e sem tamanho, igual ao canto de antes")

    # Ponto da tela: 100 pt da esquerda, 50 pt do topo.
    x1, y1, x2, y2 = assinatura.caixa_na_pagina("rodape_direita", (100, 50), L, A, 342)
    checar(x1 == 100, f"x vem direto da tela ({x1})")
    checar(abs(y2 - (A - 50)) <= 1, f"y de cima vira y de baixo ({y2})")
    checar(abs((x2 - x1) - 342) <= 1 and abs((y2 - y1) - 93) <= 1, f"a caixa tem o tamanho pedido ({x2 - x1} x {y2 - y1})")

    # Ponto fora da pagina e puxado para dentro.
    x1, y1, x2, y2 = assinatura.caixa_na_pagina("rodape_direita", (590, 840), L, A, 300)
    checar(x1 >= 0 and y1 >= 0 and x2 <= L + 1 and y2 <= A + 1, "ponto fora da pagina volta para dentro")

    # Sem ponto, com tamanho: o selo cresce a partir do canto.
    x1, y1, x2, _ = assinatura.caixa_na_pagina("rodape_direita", None, L, A, 300)
    _, _, cx2, _ = assinatura.caixa("rodape_direita", L, A)
    checar(x2 == cx2 and y1 == assinatura.MARGEM, "sem ponto, fica preso ao canto escolhido")


def test_assinar_com_tamanho(tmp: Path) -> None:
    print("\nassinar com o selo redimensionado")
    pdf = _pdf_de_teste(tmp)
    if pdf is None:
        checar(False, "havia um PDF de exemplo para assinar")
        return
    pfx = certificado.gerar_de_teste(tmp / "teste.pfx", SENHA, "PESSOA DE TESTE")
    destino = tmp / "grande.pdf"
    r = assinatura.assinar(pdf, destino, arquivo_pfx=pfx, senha=SENHA, selo=dict(certificado.PADRAO_SELO),
                           escolha_paginas="todas", ponto=(60, 80), tamanho=342)
    checar(not r.erro, "assina com ponto e tamanho", r.erro)
    if r.erro:
        return

    from pyhanko.pdf_utils.reader import PdfFileReader

    with destino.open("rb") as f:
        leitor = PdfFileReader(f)
        assinaturas = leitor.embedded_signatures
        checar(len(assinaturas) == 1, "selo em varias paginas continua UMA assinatura")
        ret = [float(v) for v in assinaturas[0].sig_field["/Rect"]]
        largura = ret[2] - ret[0]
        altura = ret[3] - ret[1]
        checar(abs(largura - 342) <= 1.5, f"o campo da assinatura tem a largura pedida ({largura})")
        checar(abs(altura - 93) <= 1.5, f"e a altura na mesma proporcao ({altura})")
        checar(abs(ret[0] - 60) <= 1, f"e esta onde a tela mostrou ({ret[0]})")

    conferido = assinatura.verificar(destino)
    checar(bool(conferido) and conferido[0].get("intacta") is True, "a assinatura confere")


def test_rota_leva_o_tamanho(tmp: Path) -> None:
    print("\na rota leva posicao e tamanho ate o assinador")
    import api

    pedido = api.PedidoAssinatura(arquivo="x.pdf", x=10, y=20, tamanho=300)
    checar(pedido.tamanho == 300, "o pedido aceita o tamanho")
    checar(api.PedidoAssinatura(arquivo="x.pdf").tamanho is None, "sem tamanho, fica vazio (compativel)")

    class CofreFalso:
        origem = "arquivo"
        arquivo = tmp / "nao-usado.pfx"
        dados = {"selo": {}}
        windows = None

        def caminho_do_selo(self, _campo):
            return None

    pegos: dict = {}

    def assinar_falso(origem, destino, **kw):
        pegos.update(kw)
        return assinatura.Resultado(erro="parado no teste")

    guardados = (api.estado.cofre, api.assinatura.assinar)
    try:
        api.estado.cofre = CofreFalso()
        api.assinatura.assinar = assinar_falso
        dados = {**pedido.model_dump(exclude={"senha_certificado"}), "guardar_biblioteca": False}
        dados["arquivo"] = str(tmp / "x.pdf")
        api._assinar_de_fato(dados, "senha")
        checar(pegos.get("tamanho") == 300.0, f"o tamanho chega ao assinador ({pegos.get('tamanho')})")
        checar(pegos.get("ponto") == (10.0, 20.0), f"e o ponto tambem ({pegos.get('ponto')})")

        pegos.clear()
        dados.pop("tamanho")
        api._assinar_de_fato(dados, "senha")
        checar(pegos.get("tamanho") is None, "pedido antigo, sem tamanho, segue sem tamanho")
    finally:
        api.estado.cofre, api.assinatura.assinar = guardados


def test_desfecho_depois_do_sim(tmp: Path) -> None:
    print("\ndepois do sim, a resposta diz para onde ir")
    import api
    import aprovacoes

    class CofreFalso:
        def senha_agora(self):
            return "senha"

    feito_de_mentira = assinatura.Resultado(destino=str(tmp / "doc - assinado.pdf"), codigo="ABC123",
                                            paginas=[2], titular="PESSOA DE TESTE", icp_brasil=False)
    guardados = (api.estado.fila, api.estado.cofre, api._assinar_de_fato)
    try:
        api.estado.fila = aprovacoes.Fila(tmp / "fila.json")
        api.estado.cofre = CofreFalso()
        api._assinar_de_fato = lambda dados, senha: feito_de_mentira

        p = api.estado.fila.pedir("Assinar doc.pdf", "assinatura", acao="assinatura.assinar",
                                  dados={"arquivo": str(tmp / "doc.pdf")}, reversivel=False)
        r = api.aprovacoes_decidir(api.Decisao(ids=[p.id], aprovar=True))
        checar(not r["falhas"], f"aprova sem falha ({r['falhas']})")
        feito = r["feitos"][0]
        checar(feito.get("categoria") == "assinatura", "o feito diz a categoria")
        checar("ABC123" in feito.get("resultado", ""), f"o historico continua com a frase ({feito.get('resultado')})")
        d = feito.get("desfecho") or {}
        checar(d.get("tipo") == "assinatura", "o desfecho diz o tipo")
        checar(d.get("destino", "").endswith("assinado.pdf"), "e traz o documento assinado")
        checar(d.get("origem", "").endswith("doc.pdf"), "e o original")
        registrado = api.estado.fila.obter(p.id)
        checar(registrado is None or isinstance(getattr(registrado, "resultado", ""), str),
               "a fila guarda texto, nao o dicionario")

        # Um executor que devolve so a frase continua valendo.
        api.EXECUTORES["teste.frase"] = lambda pedido: "feito a moda antiga"
        p2 = api.estado.fila.pedir("Outra coisa", "arquivo", acao="teste.frase")
        r2 = api.aprovacoes_decidir(api.Decisao(ids=[p2.id], aprovar=True))
        f2 = r2["feitos"][0]
        checar(f2.get("resultado") == "feito a moda antiga" and "desfecho" not in f2,
               "executor antigo, sem desfecho, segue igual")
    finally:
        api.EXECUTORES.pop("teste.frase", None)
        api.estado.fila, api.estado.cofre, api._assinar_de_fato = guardados


def main() -> int:
    print("=" * 55)
    print("PAULUS - selo posto a mao")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_medidas()
        test_caixa()
        test_assinar_com_tamanho(tmp)
        test_rota_leva_o_tamanho(tmp)
        test_desfecho_depois_do_sim(tmp)

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
