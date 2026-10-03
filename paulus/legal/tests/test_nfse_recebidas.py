"""
As NFS-e que o PAVLVS emitiu para este escritório (src/nfse_recebidas.py,
src/rotas_nfse_recebidas.py e o aviso em src/central_avisos.py).

O Worker de paulus.ia.br é de mentira (`nuvem.PEDIR`); o de verdade tem o
próprio teste: node worker/teste-nfse-casa.mjs.

  - sem a conta da nuvem: lista vazia, sem aviso e sem erro;
  - com a conta: a lista vem do Worker, com o segredo da instalação, e fica
    em memória (30 min); sem rede, fica a última lista boa;
  - o aviso "Sua NFS-e de outubro/2026 chegou", com "nº 43 · R$ 300,00 ·
    ambiente de testes" e duas ações de baixar (Download = PDF, XML);
    a nota cancelada e a de mais de 45 dias não avisam;
  - o download: o PDF e o XML com Content-Disposition attachment
    "NFS-e 43.pdf"/".xml"; nota que não existe, 404;
  - as rotas são só da janela do escritório (como Plano e consumo).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_nfse_recebidas.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-nfse-recebidas-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ.setdefault("PAULUS_NFSE_SEM_FILA", "1")
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
SEGREDO = "pia_" + "a1" * 12 + "_" + "b2" * 32
PDF = b"%PDF-1.4 a nota do PAVLVS"
XML = b"<NFSe><nNFSe>43</nNFSe></NFSe>"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Worker:
    """O /api/ia/nfse de mentira."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.fora = False
        hoje = date.today()
        self.notas = [
            {"id": "n-1", "numero": "43", "competencia": "2026-10", "valor": 300, "descricao": "Licença do PAVLVS",
             "emitida_em": hoje.isoformat() + "T12:00:00Z", "ambiente": "producao_restrita", "cancelada": False},
            {"id": "n-0", "numero": "40", "competencia": "2026-09", "valor": 1234.5, "descricao": "Licença",
             "emitida_em": (hoje - timedelta(days=5)).isoformat() + "T12:00:00Z", "ambiente": "producao", "cancelada": True},
            {"id": "n-velha", "numero": "12", "competencia": "2026-06", "valor": 300, "descricao": "Licença",
             "emitida_em": (hoje - timedelta(days=60)).isoformat() + "T12:00:00Z", "ambiente": "producao", "cancelada": False},
        ]

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": dict(cabecalhos or {})})
        if self.fora:
            raise ConnectionError("sem internet")
        status, dados, conteudo, ctype = 200, {}, b"", "application/json"
        if url.endswith("/api/ia/nfse"):
            dados = {"notas": self.notas}
        elif url.endswith("/api/ia/nfse/n-1/pdf"):
            conteudo, ctype = PDF, "application/pdf"
        elif url.endswith("/api/ia/nfse/n-1/xml"):
            conteudo, ctype = XML, "application/xml"
        else:
            status, dados = 404, {"erro": "essa nota não existe"}

        class R:
            status_code = status
            content = conteudo
            headers = {"content-type": ctype}

            def json(self):
                return dados
        return R()

    def ultimas(self, trecho: str) -> list[dict]:
        return [c for c in self.chamadas if trecho in c["url"]]


def main() -> int:
    print("=" * 55)
    print("  NFS-e recebidas do PAVLVS")
    print("=" * 55)
    import api
    import nfse_recebidas
    import nuvem
    import segredos
    from acesso import politicas
    from fastapi.testclient import TestClient

    worker = Worker()
    nuvem.PEDIR["fn"] = worker
    local = TestClient(api.app, headers=api.cabecalho_local())
    e = api.estado
    e.prefs.dados["conversa"] = {**(e.prefs.dados.get("conversa") or {}), "avisos": True}
    hoje = date.today()

    def avisos_nfse() -> list[dict]:
        return [a for a in e.central_avisos.coletar(hoje=hoje) if a["id"].startswith("nfse-recebida:")]

    print("\nsem a conta da nuvem")
    checar(local.get("/api/nfse-recebidas").json() == {"notas": []}, "lista vazia, sem erro")
    checar(not avisos_nfse(), "e nenhum aviso")
    checar(not worker.chamadas, "nem pergunta ao Worker")

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return 0
    nuvem.guardar_chave(e, "paulus", SEGREDO)
    nfse_recebidas.esquecer()

    print("\ncom a conta")
    notas = local.get("/api/nfse-recebidas").json()["notas"]
    chamada = worker.ultimas("/api/ia/nfse")[-1]
    checar(len(notas) == 3 and notas[0]["numero"] == "43" and chamada["cabecalhos"].get("Authorization") == "Bearer " + SEGREDO,
           "a lista vem do Worker com o segredo da instalação", notas)
    n = len(worker.chamadas)
    local.get("/api/nfse-recebidas")
    avisos_nfse()
    checar(len(worker.chamadas) == n, "e fica em memória (a Central não pergunta de novo)")

    print("\no aviso")
    av = avisos_nfse()
    checar(len(av) == 1, "só a nota não cancelada dos últimos 45 dias avisa", [a["id"] for a in av])
    a = av[0] if av else {}
    checar(a.get("id") == "nfse-recebida:n-1" and a.get("tipo") == "nota_fiscal", "id estável e tipo nota_fiscal", a.get("id"))
    checar(a.get("titulo") == "Sua NFS-e de outubro/2026 chegou", "título com a competência por extenso", a.get("titulo"))
    checar(a.get("detalhe") == "nº 43 · R$ 300,00 · ambiente de testes", "detalhe: número, valor e o ambiente de testes", a.get("detalhe"))
    acoes = a.get("acoes") or []
    checar([x.get("rotulo") for x in acoes] == ["Download", "XML"] and all(x.get("tipo") == "baixar" for x in acoes),
           "duas ações de baixar: Download e XML", acoes)
    checar([x.get("url") for x in acoes] == ["/api/nfse-recebidas/n-1/pdf", "/api/nfse-recebidas/n-1/xml"],
           "Download aponta para o PDF e XML para o XML", acoes)
    hoje_api = local.get("/api/central-avisos/hoje").json()
    checar(any(x["id"] == "nfse-recebida:n-1" and len(x["acoes"]) == 2 for x in hoje_api.get("avisos") or []),
           "o aviso chega no carrossel da janela", [x["id"] for x in hoje_api.get("avisos") or []])
    checar(nfse_recebidas.reais(1234.5) == "R$ 1.234,50" and nfse_recebidas.mes_por_extenso("2026-03") == "março/2026",
           "valor e mês em português")

    print("\no download")
    r = local.get("/api/nfse-recebidas/n-1/pdf")
    checar(r.status_code == 200 and r.content == PDF and r.headers["content-type"].startswith("application/pdf")
           and 'attachment; filename="NFS-e 43.pdf"' in r.headers.get("content-disposition", ""),
           "o PDF baixa como anexo NFS-e 43.pdf", (r.status_code, r.headers.get("content-disposition")))
    r = local.get("/api/nfse-recebidas/n-1/xml")
    checar(r.status_code == 200 and r.content == XML and r.headers["content-type"].startswith("application/xml")
           and 'filename="NFS-e 43.xml"' in r.headers.get("content-disposition", ""), "e o XML como NFS-e 43.xml")
    checar(worker.ultimas("/api/ia/nfse/n-1/pdf")[-1]["cabecalhos"].get("Authorization") == "Bearer " + SEGREDO,
           "o arquivo vem com o mesmo segredo")
    r = local.get("/api/nfse-recebidas/nao-tem/pdf")
    checar(r.status_code == 404, "nota que não existe: 404", r.status_code)

    print("\nPDF ainda não gerado na nuvem: o PAULUS desenha do XML")
    from nfse import danfse

    original = danfse.gerar
    danfse.gerar = lambda xml: b"%PDF-desenhado:" + xml
    try:
        worker_antes = worker.__class__.__call__

        def so_xml(self, metodo, url, cabecalhos, corpo, stream):
            if url.endswith("/api/ia/nfse/n-1/pdf"):
                url = url.replace("/n-1/pdf", "/sem-pdf")
            return worker_antes(self, metodo, url, cabecalhos, corpo, stream)

        worker.__class__.__call__ = so_xml
        r = local.get("/api/nfse-recebidas/n-1/pdf")
        checar(r.status_code == 200 and r.content == b"%PDF-desenhado:" + XML, "sem PDF na nuvem, o PDF sai do XML",
               (r.status_code, r.content[:40]))
    finally:
        worker.__class__.__call__ = worker_antes
        danfse.gerar = original

    print("\nsem rede")
    worker.fora = True
    nfse_recebidas._cache["quando"] = 0.0
    checar(len(nfse_recebidas.listar(e)) == 3, "fica a última lista boa, sem erro")
    nfse_recebidas.esquecer()
    checar(nfse_recebidas.listar(e) == [], "sem lista anterior: vazia, sem erro")
    r = local.get("/api/nfse-recebidas/n-1/pdf")
    checar(r.status_code == 502, "baixar sem rede diz que não falou com paulus.ia.br", r.status_code)
    worker.fora = False

    print("\nde fora")
    for rota in ("GET /api/nfse-recebidas", "GET /api/nfse-recebidas/{id_}/pdf", "GET /api/nfse-recebidas/{id_}/xml"):
        metodo, caminho = rota.split(" ")
        checar(politicas.de(metodo, caminho) == politicas.de("GET", "/api/consumo") == politicas.BLOQUEADO,
               rota + ": só na janela do escritório, como Plano e consumo")
    nfse_recebidas.esquecer()
    checar(not [a for a in e.central_avisos.coletar(hoje=hoje, politica=lambda m, r: None) if a["id"].startswith("nfse-recebida:")],
           "quem não pode a rota não recebe o aviso")

    nuvem.apagar_chave(e, "paulus")
    nfse_recebidas.esquecer()
    print()
    if _falhas:
        print(f"  {len(_falhas)} falha(s): " + "; ".join(_falhas))
        return 1
    print("  NFS-e recebidas: todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
