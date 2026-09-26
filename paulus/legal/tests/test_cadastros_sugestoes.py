"""
Testes das rotas da sugestao de cadastro: ignorar, desfazer e o
levantamento (ler os documentos do Acervo que ainda nao foram lidos).

Tudo em pasta temporaria: a base, o cache da classificacao e a lista de
ignorados sao trocados por copias ficticias antes de chamar as rotas, e a
leitura com o modelo e um duble. Nada toca os cadastros de verdade.

    python tests/test_cadastros_sugestoes.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from base import Base  # noqa: E402
from cadastros import Cadastros  # noqa: E402
from classify import VERSAO_CLASSIFICADOR  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


class _Doc:
    def __init__(self, caminho: Path, sha1: str) -> None:
        self.path = str(caminho)
        self.sha1 = sha1
        self.name = caminho.name


class _Buscador:
    def __init__(self, documentos: list[_Doc]) -> None:
        self.documents = documentos
        self.chunks: list = []


class _Leitura:
    """Duble da habilidade classificar: grava no cache o que 'leu'."""

    executavel = True
    precisa: list[str] = []

    def __init__(self, cache: Path, partes: dict[str, list[str]]) -> None:
        self.cache = cache
        self.partes = partes
        self.lidos: list[str] = []

    def executar(self, _ctx, caminhos=None):
        bruto = json.loads(self.cache.read_text(encoding="utf-8"))
        documentos = []
        for i, caminho in enumerate(caminhos or [], start=1):
            nome = Path(caminho).name
            sha = "sha-" + nome
            self.lidos.append(nome)
            bruto["itens"][sha] = {"nome": nome, "sha1": sha, "partes": self.partes.get(nome, []), "documentos": []}
            documentos.append({"arquivo": caminho, "nome": nome, "sha1": sha})
            yield "progresso", {"indice": i, "total": len(caminhos), "nome": nome, "cache": False}
        self.cache.write_text(json.dumps(bruto, ensure_ascii=False), encoding="utf-8")
        yield "resultados", {"documentos": documentos, "parado": False}


class _Registro:
    def __init__(self, leitura) -> None:
        self.leitura = leitura

    def obter(self, id_: str):
        return self.leitura if id_ == "classificar" else None


def _eventos(resposta) -> list[tuple[str, dict]]:
    async def ler():
        return [c async for c in resposta.body_iterator]

    saida = []
    for pedaco in asyncio.run(ler()):
        texto = pedaco.decode("utf-8") if isinstance(pedaco, bytes) else pedaco
        for bloco in texto.strip().split("\n\n"):
            linhas = dict(l.split(": ", 1) for l in bloco.splitlines() if ": " in l)
            if "event" in linhas:
                saida.append((linhas["event"], json.loads(linhas["data"])))
    return saida


def test_rotas(tmp: Path) -> None:
    print("\nrotas da sugestao de cadastro")
    import api
    from fastapi import HTTPException

    cache = tmp / "classificacao.json"
    cache.write_text(json.dumps({
        "versao": VERSAO_CLASSIFICADOR,
        "itens": {
            "a": {"nome": "contrato-a.pdf", "sha1": "a", "partes": ["Empresa Ficticia Alfa Ltda", "Pessoa Ficticia Beta"],
                  "documentos": ["00.000.000/0001-00"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    for nome in ("contrato-a.pdf", "contrato-novo.pdf"):
        (tmp / nome).write_text("x", encoding="utf-8")

    base = Base(tmp / "p.db")
    guardadas = (api.CLASSIFICACAO_PATH, api.estado.cadastros, api.estado.searcher, api.estado.registro)
    try:
        api.CLASSIFICACAO_PATH = cache
        api.estado.cadastros = Cadastros(base, tmp / "ignorados.json")
        api.estado.searcher = _Buscador([_Doc(tmp / "contrato-a.pdf", "a")])

        d = api.cadastros_sugestoes()
        checar(d["total"] == 2 and len(d["sugestoes"]) == 2, f"duas sugestoes lidas do cache ({d['total']})")
        checar(d["levantamento"] == {"documentos": 1, "faltam": 0}, f"o documento do Acervo ja foi lido ({d['levantamento']})")

        r = api.cadastros_sugestao_ignorar(api.NomeSugerido(nome="Pessoa Ficticia Beta"))
        checar(r["ignorados"] == 1, "ignorar responde quantos estao ignorados")
        d = api.cadastros_sugestoes()
        checar([x["nome"] for x in d["sugestoes"]] == ["Empresa Ficticia Alfa Ltda"], "o ignorado sai da lista")
        checar(d["ignorados"] == 1, "e a conta de ignorados vem junto")
        checar((tmp / "ignorados.json").exists(), "o ignorado fica guardado em arquivo")

        r = api.cadastros_sugestao_desfazer(api.NomeSugerido(nome="Pessoa Ficticia Beta"))
        checar(r["voltou"] is True, "desfazer devolve o nome")
        checar(api.cadastros_sugestoes()["total"] == 2, "e ele volta a ser sugerido")

        try:
            api.cadastros_sugestao_ignorar(api.NomeSugerido(nome="   "))
            checar(False, "ignorar sem nome e recusado")
        except HTTPException as exc:
            checar(exc.status_code == 400, "ignorar sem nome e recusado")

        # Levantamento sem documento novo: nao le nada, nem pede o modelo.
        api.estado.registro = _Registro(None)
        ev = _eventos(api.cadastros_levantamento())
        tipos = [t for t, _ in ev]
        checar(tipos == ["inicio", "fim"], f"sem documento novo, so inicio e fim ({tipos})")
        checar(ev[0][1]["novos"] == 0 and ev[-1][1]["lidos"] == 0, "e diz que nao havia o que ler")
        checar(ev[-1][1]["sugestoes"] == 2 and ev[-1][1]["novas"] == 0, "com a conta de sugestoes de agora")

        # Com documento novo: le so ele, e o nome achado entra na lista.
        api.estado.searcher = _Buscador([_Doc(tmp / "contrato-a.pdf", "a"), _Doc(tmp / "contrato-novo.pdf", "sha-contrato-novo.pdf")])
        checar(api.cadastros_sugestoes()["levantamento"]["faltam"] == 1, "um documento ainda por ler")
        leitura = _Leitura(cache, {"contrato-novo.pdf": ["Cooperativa Ficticia Gama"]})
        api.estado.registro = _Registro(leitura)
        ev = _eventos(api.cadastros_levantamento())
        tipos = [t for t, _ in ev]
        checar(tipos == ["inicio", "progresso", "fim"], f"andamento documento a documento ({tipos})")
        checar(leitura.lidos == ["contrato-novo.pdf"], f"le so o que faltava ({leitura.lidos})")
        fim = ev[-1][1]
        checar(fim["lidos"] == 1 and fim["novas"] == 1 and fim["sugestoes"] == 3, f"o nome novo aparece no fim ({fim})")
        nomes = [x["nome"] for x in api.cadastros_sugestoes()["sugestoes"]]
        checar("Cooperativa Ficticia Gama" in nomes, "e entra nas sugestoes")
        checar(api.cadastros_sugestoes()["levantamento"]["faltam"] == 0, "depois do levantamento, nada por ler")

        # Documento por ler e leitura que nao carregou: erro claro, antes de ler.
        api.estado.searcher = _Buscador([_Doc(tmp / "contrato-novo.pdf", "sha-outro")])
        api.estado.registro = _Registro(None)
        try:
            api.cadastros_levantamento()
            checar(False, "sem a leitura carregada, o levantamento recusa")
        except HTTPException as exc:
            checar(exc.status_code == 503, "sem a leitura carregada, o levantamento recusa")
    finally:
        api.CLASSIFICACAO_PATH, api.estado.cadastros, api.estado.searcher, api.estado.registro = guardadas
        base.fechar()


def main() -> int:
    print("=" * 55)
    print("  PAULUS - sugestao de cadastro (rotas)")
    print("=" * 55)
    with tempfile.TemporaryDirectory() as tmp:
        test_rotas(Path(tmp))
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
