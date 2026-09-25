"""
Testes da assinatura em lote e do .zip dos assinados.

A tela "Assinar documento" deixa marcar varios PDFs, por o selo em cada um
e assinar os prontos com uma senha so. Depois, pergunta se a pessoa quer
salvar um a um ou num .zip. O que precisa valer:

  - o lote assina cada documento com o SEU selo (posicao de cada um)
  - um documento que nao abre nao derruba os outros: volta com o motivo
  - lote vazio, repetido ou com a senha errada e recusado antes de assinar
  - com a alcada pedindo aprovacao, o lote vira UM pedido, e nada e
    assinado antes do sim; o sim assina todos e devolve o desfecho do lote
  - o Acervo e relido uma vez so no fim do lote, e nao a cada documento
  - o .zip so aceita arquivos assinados por aqui, nao repete nome e nao
    perde conteudo; gravado pelo "Salvar como" ganha .zip no fim
  - copiar um a um para uma pasta nunca passa por cima do que ja esta la

Nada aqui toca a fila, o cofre, o registro ou o acervo de verdade: cada
teste troca essas pecas por copias temporarias e devolve no fim. O
certificado e um de teste, criado na hora numa pasta temporaria.

    python tests/test_assinatura_lote.py
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import aprovacoes  # noqa: E402
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


def _pdf_de_exemplo() -> Path | None:
    for origem in sorted((RAIZ / "data" / "test_contracts").glob("*.pdf")):
        if assinatura.ler(origem).assinaturas == 0:
            return origem
    return None


class PrefsFalsas:
    def __init__(self, sozinho: bool) -> None:
        self.sozinho = sozinho

    def pode(self, chave: str) -> bool:
        return self.sozinho if chave == "assinar" else False


class Ambiente:
    """Troca as pecas do servidor por copias temporarias, e devolve no fim."""

    PECAS = ("cofre", "fila", "prefs", "assinaturas", "pasta", "recarregar")

    def __init__(self, tmp: Path, sozinho: bool = True) -> None:
        import api

        self.api = api
        self.tmp = tmp
        self.sozinho = sozinho
        self.recargas = 0

    def __enter__(self):
        e = self.api.estado
        self.guardado = {p: getattr(e, p) for p in self.PECAS}
        pasta_cert = self.tmp / "cert"
        pasta_cert.mkdir(exist_ok=True)
        pfx = certificado.gerar_de_teste(pasta_cert / "teste.pfx", SENHA, "PESSOA DE TESTE")
        cofre = certificado.Cofre(self.tmp / "cofre.json", pasta_cert)
        cofre.dados["arquivo"] = str(pfx)
        cofre.dados["minutos"] = 15
        e.cofre = cofre
        e.fila = aprovacoes.Fila(self.tmp / "fila.json")
        e.prefs = PrefsFalsas(self.sozinho)
        e.assinaturas = assinatura.Registro(self.tmp / "registro.json")
        e.pasta = self.tmp / "acervo"
        e.pasta.mkdir(exist_ok=True)

        def contar(force: bool = False) -> None:
            self.recargas += 1

        e.recarregar = contar
        return self

    def __exit__(self, *_):
        for peca, valor in self.guardado.items():
            setattr(self.api.estado, peca, valor)


def _tres_documentos(tmp: Path) -> list[Path] | None:
    exemplo = _pdf_de_exemplo()
    if exemplo is None:
        return None
    pasta = tmp / "originais"
    pasta.mkdir(exist_ok=True)
    a = Path(shutil.copy(exemplo, pasta / "contrato A.pdf"))
    b = Path(shutil.copy(exemplo, pasta / "contrato B.pdf"))
    ruim = pasta / "quebrado.pdf"
    ruim.write_bytes(b"isto nao e um PDF")
    return [a, b, ruim]


def _retangulo(pdf: Path) -> list[float]:
    from pyhanko.pdf_utils.reader import PdfFileReader

    with pdf.open("rb") as f:
        assinaturas = PdfFileReader(f).embedded_signatures
        return [float(v) for v in assinaturas[0].sig_field["/Rect"]] if assinaturas else []


def test_lote_direto(tmp: Path) -> None:
    print("\nlote assinado direto, com uma senha so")
    docs = _tres_documentos(tmp)
    if docs is None:
        checar(False, "havia um PDF de exemplo para assinar")
        return
    a, b, ruim = docs
    with Ambiente(tmp, sozinho=True) as amb:
        api = amb.api
        pedido = api.PedidoLote(
            itens=[
                api.ItemDoLote(arquivo=str(a), paginas="todas", x=40, y=60, tamanho=300),
                api.ItemDoLote(arquivo=str(b), paginas="ultima", x=200, y=500),
                api.ItemDoLote(arquivo=str(ruim)),
            ],
            guardar_biblioteca=True,
            senha_certificado=SENHA,
        )
        r = api.assinar_lote(pedido)
        checar(r["aguardando_aprovacao"] is False, "com a alcada livre, assina na hora")
        feitos = r["feitos"]
        checar(len(feitos) == 2, f"os dois PDFs bons foram assinados ({len(feitos)})")
        checar(len(r["falhas"]) == 1 and r["falhas"][0]["nome"] == "quebrado.pdf" and r["falhas"][0]["motivo"],
               f"o que nao abre volta com o motivo ({r['falhas']})")
        origens = {f["origem"] for f in feitos}
        checar(origens == {str(a), str(b)}, "cada feito diz de qual original veio")
        codigos = {f["codigo"] for f in feitos}
        checar(len(codigos) == 2 and all(codigos), "cada documento tem a sua assinatura (codigos diferentes)")
        destinos = [Path(f["destino"]) for f in feitos]
        checar(all(d.exists() and d.parent == amb.api.estado.pasta for d in destinos), "os assinados estao no Acervo (temporario)")
        checar(a.exists() and b.exists(), "os originais continuam onde estavam")
        checar(amb.recargas == 1, f"o Acervo foi relido uma vez so ({amb.recargas})")

        por_origem = {f["origem"]: Path(f["destino"]) for f in feitos}
        ret_a, ret_b = _retangulo(por_origem[str(a)]), _retangulo(por_origem[str(b)])
        checar(bool(ret_a) and abs(ret_a[0] - 40) <= 1 and abs((ret_a[2] - ret_a[0]) - 300) <= 1.5,
               f"o selo de A esta onde a tela pos, no tamanho pedido ({ret_a[:3]})")
        checar(bool(ret_b) and abs(ret_b[0] - 200) <= 1 and abs((ret_b[2] - ret_b[0]) - 228) <= 1.5,
               f"o de B, no lugar dele e no tamanho de sempre ({ret_b[:3]})")
        conferidos = [assinatura.verificar(d) for d in destinos]
        checar(all(c and c[0].get("intacta") is True for c in conferidos), "as duas assinaturas conferem")
        checar(len(api.estado.assinaturas.itens) == 2, "o registro anotou as duas")


def test_lote_recusado(tmp: Path) -> None:
    print("\nlote recusado antes de assinar")
    from fastapi import HTTPException

    docs = _tres_documentos(tmp)
    if docs is None:
        checar(False, "havia um PDF de exemplo para assinar")
        return
    a, b, ruim = docs
    with Ambiente(tmp, sozinho=True) as amb:
        api = amb.api

        def recusa(pedido) -> str:
            try:
                api.assinar_lote(pedido)
            except HTTPException as exc:
                return str(exc.detail)
            return ""

        checar(bool(recusa(api.PedidoLote(itens=[], senha_certificado=SENHA))), "lote vazio")
        repetido = recusa(api.PedidoLote(itens=[api.ItemDoLote(arquivo=str(a)), api.ItemDoLote(arquivo=str(a))], senha_certificado=SENHA))
        checar("duas vezes" in repetido, f"o mesmo documento duas vezes ({repetido})")
        errada = recusa(api.PedidoLote(itens=[api.ItemDoLote(arquivo=str(a))], senha_certificado="errada"))
        checar(bool(errada), f"senha errada ({errada})")
        nenhum = recusa(api.PedidoLote(itens=[api.ItemDoLote(arquivo=str(ruim))], senha_certificado=SENHA))
        checar("nenhum documento" in nenhum, f"nenhum que de para assinar ({nenhum})")
        sem_pagina = recusa(api.PedidoLote(itens=[api.ItemDoLote(arquivo=str(a), paginas="intervalo", intervalo="900")], senha_certificado=SENHA))
        checar("nenhuma página" in sem_pagina, f"intervalo sem pagina do documento ({sem_pagina})")
        checar(not list(api.estado.pasta.glob("*.pdf")), "nada foi assinado")


def test_lote_na_fila(tmp: Path) -> None:
    print("\nlote com a alcada pedindo aprovacao")
    docs = _tres_documentos(tmp)
    if docs is None:
        checar(False, "havia um PDF de exemplo para assinar")
        return
    a, b, ruim = docs
    with Ambiente(tmp, sozinho=False) as amb:
        api = amb.api
        r = api.assinar_lote(api.PedidoLote(
            itens=[api.ItemDoLote(arquivo=str(a), x=40, y=60), api.ItemDoLote(arquivo=str(b)), api.ItemDoLote(arquivo=str(ruim))],
            guardar_biblioteca=False, senha_certificado=SENHA,
        ))
        checar(r["aguardando_aprovacao"] is True, "nao assina: vai para a fila")
        pedido = r["pedido"]
        checar(pedido["acao"] == "assinatura.lote" and pedido["categoria"] == "assinatura", "um pedido so, de lote, na categoria assinatura")
        checar(len(api.estado.fila.para_tela()["pendentes"]) == 1, "a fila (temporaria) tem um pedido so")
        checar(sorted(pedido["dados"]["arquivos"]) == sorted([str(a), str(b)]), "o pedido lista os arquivos que vao sair")
        checar("2 documentos" in pedido["resumo"] and "contrato A.pdf" in pedido["resumo"], f"o resumo diz quantos e quais ({pedido['resumo'][:80]})")
        checar(len(r["falhas"]) == 1, "o que nao abre ja volta de fora")
        checar(not list((tmp / "originais").glob("* - assinado*.pdf")), "nada foi assinado antes do sim")

        d = api.aprovacoes_decidir(api.Decisao(ids=[pedido["id"]], aprovar=True))
        checar(not d["falhas"], f"o sim executa sem falha ({d['falhas']})")
        feito = d["feitos"][0] if d["feitos"] else {}
        desfecho = feito.get("desfecho") or {}
        checar(desfecho.get("tipo") == "assinatura_lote", "o desfecho e de lote, para a tela voltar ao lote")
        checar(len(desfecho.get("feitos", [])) == 2, "o sim assinou os dois")
        checar(all(Path(f["destino"]).exists() for f in desfecho.get("feitos", [])), "os assinados existem, ao lado dos originais")
        checar("2 de 2" in feito.get("resultado", ""), f"o historico conta os assinados ({feito.get('resultado')})")

        # Sem a senha na memoria, o sim falha dizendo por que - e nao assina.
        r2 = api.assinar_lote(api.PedidoLote(itens=[api.ItemDoLote(arquivo=str(a))], guardar_biblioteca=False, senha_certificado=SENHA))
        api.estado.cofre.esquecer_senha()
        d2 = api.aprovacoes_decidir(api.Decisao(ids=[r2["pedido"]["id"]], aprovar=True))
        checar(bool(d2["falhas"]) and "senha" in d2["falhas"][0]["motivo"], f"sem senha na memoria, o sim diz o motivo ({d2['falhas']})")


def _dois_assinados_com_o_mesmo_nome(tmp: Path, registro: assinatura.Registro) -> list[Path]:
    exemplo = _pdf_de_exemplo()
    um = tmp / "um"
    outro = tmp / "outro"
    um.mkdir(exist_ok=True)
    outro.mkdir(exist_ok=True)
    x = Path(shutil.copy(exemplo, um / "acordo - assinado.pdf"))
    y = outro / "acordo - assinado.pdf"
    y.write_bytes(x.read_bytes() + b"\n% outro\n")
    for n, alvo in enumerate((x, y)):
        registro.anotar(assinatura.Resultado(destino=str(alvo), codigo=f"C{n}", quando="agora"), alvo)
    return [x, y]


def test_zip(tmp: Path) -> None:
    print("\no .zip dos assinados")
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    with Ambiente(tmp) as amb:
        api = amb.api
        x, y = _dois_assinados_com_o_mesmo_nome(tmp, api.estado.assinaturas)
        cliente = TestClient(api.app)

        r = cliente.get("/api/assinar/zip", params=[("arquivo", str(x)), ("arquivo", str(y))])
        checar(r.status_code == 200, f"a rota entrega o .zip ({r.status_code})")
        checar(r.headers.get("content-type", "").startswith("application/zip"), "como application/zip")
        checar("attachment" in r.headers.get("content-disposition", "") and ".zip" in r.headers.get("content-disposition", ""),
               "com nome de arquivo para baixar")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nomes = z.namelist()
            checar(nomes == ["acordo - assinado.pdf", "acordo - assinado (2).pdf"], f"nomes sem colisao ({nomes})")
            checar(z.read(nomes[0]) == x.read_bytes() and z.read(nomes[1]) == y.read_bytes(), "o conteudo e o dos assinados, byte a byte")

        repetido = cliente.get("/api/assinar/zip", params=[("arquivo", str(x)), ("arquivo", str(x))])
        with zipfile.ZipFile(io.BytesIO(repetido.content)) as z:
            checar(len(z.namelist()) == 1, "o mesmo arquivo pedido duas vezes entra uma vez")

        estranho = tmp / "qualquer.pdf"
        estranho.write_bytes(x.read_bytes())
        r = cliente.get("/api/assinar/zip", params=[("arquivo", str(x)), ("arquivo", str(estranho))])
        checar(r.status_code == 403, f"arquivo que nao foi assinado aqui e recusado ({r.status_code})")
        checar(cliente.get("/api/assinar/zip").status_code == 400, "sem arquivo, recusa")
        sumido = tmp / "sumido - assinado.pdf"
        api.estado.assinaturas.anotar(assinatura.Resultado(destino=str(sumido), codigo="C9"), sumido)
        checar(cliente.get("/api/assinar/zip", params={"arquivo": str(sumido)}).status_code == 404, "assinado que saiu do disco da 404")

        # Pelo "Salvar como" da janela: grava onde a pessoa escolheu.
        alvo = tmp / "saida" / "meus assinados"
        g = api.assinar_zip_gravar(api.AssinadosParaSalvar(arquivos=[str(x), str(y)], caminho=str(alvo)))
        gravado = Path(g["caminho"])
        checar(gravado.suffix == ".zip" and gravado.exists(), f"sem extensao, ganha .zip ({gravado.name})")
        checar(g["quantos"] == 2, "e diz quantos entraram")
        with zipfile.ZipFile(gravado) as z:
            checar(len(z.namelist()) == 2, "o .zip gravado tem os dois")
        try:
            api.assinar_zip_gravar(api.AssinadosParaSalvar(arquivos=[str(x)], caminho=""))
            checar(False, "sem caminho, recusa")
        except HTTPException:
            checar(True, "sem caminho, recusa")


def test_copiar_um_a_um(tmp: Path) -> None:
    print("\nsalvar um a um numa pasta")
    from fastapi import HTTPException

    with Ambiente(tmp) as amb:
        api = amb.api
        x, y = _dois_assinados_com_o_mesmo_nome(tmp, api.estado.assinaturas)
        pasta = tmp / "destino"
        pasta.mkdir()
        ja = pasta / "acordo - assinado.pdf"
        ja.write_bytes(b"o que ja estava la")
        r = api.assinar_copiar(api.AssinadosParaSalvar(arquivos=[str(x), str(y)], pasta=str(pasta)))
        checar(ja.read_bytes() == b"o que ja estava la", "o arquivo que ja estava na pasta nao foi substituido")
        checar(len(r["copiados"]) == 2 and len(set(r["copiados"])) == 2, f"os dois entraram com nomes diferentes ({r['copiados']})")
        checar(all((pasta / n).exists() for n in r["copiados"]), "e estao na pasta")
        try:
            api.assinar_copiar(api.AssinadosParaSalvar(arquivos=[str(x)], pasta=str(tmp / "nao-existe")))
            checar(False, "pasta que nao existe e recusada")
        except HTTPException:
            checar(True, "pasta que nao existe e recusada")


def main() -> int:
    print("=" * 55)
    print("PAULUS - assinatura em lote e .zip")
    print("=" * 55)

    for teste in (test_lote_direto, test_lote_recusado, test_lote_na_fila, test_zip, test_copiar_um_a_um):
        with tempfile.TemporaryDirectory() as bruto:
            teste(Path(bruto))

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
