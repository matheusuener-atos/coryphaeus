"""
O Google Drive pela internet, no Acervo (src/drive_online.py), com um Drive de
mentira:

  - a pasta escolhida vira copia em "Acervo/Google Drive/<nome>", com as
    subpastas; so desce o que o Acervo le; Docs saem .docx;
  - de novo, sem mudanca: nada desce; mudou la, desce so aquele;
  - renomeado la: a copia com o nome antigo sai; apagado la: sai da copia;
    arquivo posto a mao na copia fica;
  - dois arquivos com o mesmo nome na mesma pasta: o segundo ganha " (2)";
  - nome que o Windows nao aceita e ajeitado;
  - erro do Google fica na pasta, sem derrubar as outras;
  - tirar sem apagar deixa a copia; apagando, so a copia sai;
  - as rotas: sem a leitura autorizada, "autorizar"; com ela, as raizes, as
    pastas, e a copia comeca; de fora, 403.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_drive_online.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-drive-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PASTA = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"


class DriveDeMentira:
    def __init__(self) -> None:
        self.itens: dict[str, dict] = {}
        self.baixados: list[str] = []
        self.quebrar = set()

    def por(self, id_, nome, pai, mime="application/pdf", conteudo=b"%PDF-1.4 x", versao="1"):
        self.itens[id_] = {"id": id_, "name": nome, "mimeType": mime, "pai": pai, "md5Checksum": versao,
                           "size": str(len(conteudo)), "conteudo": conteudo}

    def drive_listar(self, pasta_id):
        from google_servicos import ErroGoogle

        if pasta_id in self.quebrar:
            raise ErroGoogle("o Google respondeu 500: quebrado", status=500)
        return [{k: v for k, v in x.items() if k not in ("pai", "conteudo")} for x in self.itens.values() if x["pai"] == pasta_id]

    def drive_baixar(self, arquivo, destino):
        self.baixados.append(arquivo["id"])
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(self.itens[arquivo["id"]]["conteudo"])


class Prefs:
    def __init__(self) -> None:
        self.dados = {}

    def atualizar(self, _):
        pass


def test_espelho() -> None:
    print("\na copia das pastas do Drive")
    import drive_online

    acervo = TMP / "acervo"
    d = DriveDeMentira()
    mudou = []
    e = drive_online.EspelhoDoDrive(d, lambda: acervo, Prefs(), ao_mudar=lambda: mudou.append(1))
    d.por("f1", "Clientes", "raiz-x", PASTA)
    d.por("a1", "contrato.pdf", "f1")
    d.por("a2", "Parecer", "f1", DOC, b"PK docx")
    d.por("a3", "foto.jpg", "f1", "image/jpeg", b"jpg")
    d.por("f2", "Moura: 2026?", "f1", PASTA)
    d.por("a4", "peticao.docx", "f2", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK")
    d.por("a5", "contrato.pdf", "f1", conteudo=b"%PDF outro", versao="9")

    p = e.incluir("f1", "Clientes")
    try:
        e.incluir("f1", "Clientes")
        checar(False, "a mesma pasta duas vezes: recusa")
    except ValueError:
        checar(True, "a mesma pasta duas vezes: recusa")
    r = e.sincronizar()
    copia = acervo / "Google Drive" / "Clientes"
    checar(r and r[0]["baixados"] == 4 and r[0]["ignorados"] == 1, "desce o que o Acervo le; a foto fica", r)
    checar((copia / "contrato.pdf").is_file() and (copia / "Parecer.docx").is_file(), "o Doc chega como .docx")
    checar((copia / "Moura_ 2026_" / "peticao.docx").is_file(), "subpasta, com o nome que o Windows aceita",
           [str(x.relative_to(copia)) for x in copia.rglob("*")])
    checar((copia / "contrato (2).pdf").read_bytes() == b"%PDF outro", "nome repetido: o segundo ganha (2)")
    checar(bool(mudou), "o Acervo e avisado para reler")

    d.baixados.clear()
    r = e.sincronizar()
    checar(r[0]["baixados"] == 0 and not d.baixados, "de novo, sem mudanca: nada desce", r)
    d.itens["a1"]["conteudo"] = b"%PDF nova"
    d.itens["a1"]["md5Checksum"] = "2"
    r = e.sincronizar()
    checar(d.baixados == ["a1"] and (copia / "contrato.pdf").read_bytes() == b"%PDF nova", "mudou la: desce so aquele", d.baixados)

    (copia / "minha-nota.txt").write_text("posta a mao", encoding="utf-8")
    d.itens["a4"]["name"] = "peticao inicial.docx"
    del d.itens["a2"]
    r = e.sincronizar()
    checar((copia / "Moura_ 2026_" / "peticao inicial.docx").is_file() and not (copia / "Moura_ 2026_" / "peticao.docx").exists(),
           "renomeado la: a copia com o nome antigo sai")
    checar(not (copia / "Parecer.docx").exists() and r[0]["removidos"] == 1, "apagado la: sai da copia", r)
    checar((copia / "minha-nota.txt").is_file(), "o que foi posto a mao na copia fica")

    d.por("f9", "Outra", "raiz-x", PASTA)
    e.incluir("f9", "Clientes")
    d.quebrar.add("f9")
    r = e.sincronizar()
    pastas = {x["id"]: x for x in e.pastas()}
    checar(pastas["f9"]["erro"].startswith("o Google respondeu 500") and not pastas["f1"]["erro"],
           "o erro fica na pasta, sem derrubar as outras", pastas)
    checar(pastas["f9"]["local"] == "Clientes (2)", "dois nomes iguais escolhidos: pastas locais diferentes", pastas["f9"]["local"])

    e.tirar("f1")
    checar(copia.is_dir() and "f1" not in {x["id"] for x in e.pastas()}, "tirar sem apagar: a copia fica")
    e.incluir("f1", "Clientes 3")
    e.tirar("f1", apagar_copia=True)
    checar(copia.is_dir(), "apagar a copia de outro nome nao toca na antiga")
    x = e.incluir("f1", "Clientes")
    e.sincronizar("f1")
    e.tirar("f1", apagar_copia=True)
    checar(not (acervo / "Google Drive" / x["local"]).exists() and acervo.is_dir(), "apagando: so a copia sai")
    try:
        e.incluir("../../etc", "x")
        checar(False, "id estranho: recusa")
    except ValueError:
        checar(True, "id estranho: recusa")


def test_baixar() -> None:
    print("\no download pelo Google")
    import requests

    import google_servicos

    pedidos = []

    class Resposta:
        def __init__(self, status, pedacos):
            self.status_code, self.pedacos = status, pedacos

        def iter_content(self, _):
            for p in self.pedacos:
                if isinstance(p, Exception):
                    raise p
                yield p

        def json(self):
            return {"error": {"message": "x", "errors": [{"reason": "insufficientPermissions"}]}}

    class Sessao:
        resposta = None

        def get(self, url, params=None, headers=None, timeout=None, stream=False):
            pedidos.append((url, params, headers.get("Authorization")))
            return self.resposta

    s = Sessao()
    g = google_servicos.Google(lambda: "tok", sessao=s)
    destino = TMP / "baixar" / "a.docx"
    s.resposta = Resposta(200, [b"PK", b"docx"])
    g.drive_baixar({"id": "d1", "mimeType": "application/vnd.google-apps.document"}, destino)
    checar(pedidos[-1][0].endswith("/files/d1/export") and "wordprocessingml" in pedidos[-1][1]["mimeType"]
           and pedidos[-1][2] == "Bearer tok", "Doc do Google: exportado como .docx", pedidos[-1])
    checar(destino.read_bytes() == b"PKdocx", "os bytes chegam inteiros")
    g.drive_baixar({"id": "p1", "mimeType": "application/pdf"}, TMP / "baixar" / "b.pdf")
    checar(pedidos[-1][0].endswith("/files/p1") and pedidos[-1][1]["alt"] == "media", "PDF: alt=media", pedidos[-1])
    s.resposta = Resposta(200, [b"meio", requests.ConnectionError("caiu")])
    try:
        g.drive_baixar({"id": "p2", "mimeType": "application/pdf"}, TMP / "baixar" / "c.pdf")
        checar(False, "caiu no meio: erro")
    except google_servicos.ErroGoogle:
        checar(not (TMP / "baixar" / "c.pdf").exists() and not (TMP / "baixar" / "c.pdf.parcial").exists(),
               "caiu no meio: nem o arquivo nem o .parcial ficam")
    s.resposta = Resposta(403, [])
    try:
        g.drive_baixar({"id": "p3", "mimeType": "application/pdf"}, TMP / "baixar" / "d.pdf")
    except google_servicos.ErroGoogle as exc:
        checar(exc.autorizar == "drive_leitura", "sem a permissao: pede para autorizar a leitura", exc.autorizar)


def test_rotas() -> None:
    print("\nas rotas")
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    tem = {"drive_leitura": False}
    api.estado.google_tem = lambda s: tem.get(s, False)
    api.estado.conta_google = lambda: type("C", (), {"email": "escritorio@x.com", "precisa_entrar": False})()
    d = DriveDeMentira()
    d.drive_compartilhados = lambda: [{"id": "0AB", "name": "Equipe"}]
    d.por("f1", "Clientes", "root", PASTA)
    d.por("a1", "contrato.pdf", "f1")
    api.estado.drive_online.google = d
    api.estado.google.drive_listar = d.drive_listar
    api.estado.google.drive_compartilhados = d.drive_compartilhados
    r = local.get("/api/google/drive/navegar").json()
    checar(r["autorizar"] is True and r["conta"] == "escritorio@x.com", "sem a leitura: pede para autorizar", r)
    checar(local.post("/api/google/drive/copias", json={"id": "f1", "nome": "Clientes"}).status_code == 403,
           "copiar sem a leitura: 403")
    tem["drive_leitura"] = True
    r = local.get("/api/google/drive/navegar").json()
    checar([x["nome"] for x in r["itens"]] == ["Meu Drive", "Compartilhados comigo", "Equipe"], "as raizes", r)
    r = local.get("/api/google/drive/navegar", params={"pasta": "root"}).json()
    checar(r["itens"] == [{"id": "f1", "nome": "Clientes", "pasta": True, "le": False}], "as pastas do Meu Drive", r)
    r = local.post("/api/google/drive/copias", json={"id": "f1", "nome": "Clientes"})
    checar(r.status_code == 200 and r.json()["pasta"]["local"] == "Clientes", "copiar: a pasta entra", r.text[:200])
    for _ in range(50):
        if (api.estado.pasta / "Google Drive" / "Clientes" / "contrato.pdf").is_file() and not api.estado.drive_online.andando:
            break
        time.sleep(0.1)
    checar((api.estado.pasta / "Google Drive" / "Clientes" / "contrato.pdf").is_file(), "e a primeira descida comeca ja")
    g = local.get("/api/google").json()
    checar(g["drive_online"]["pastas"][0]["arquivos"] == 1, "Conexoes mostra as copias", g.get("drive_online"))
    checar(local.post("/api/google/drive/copias", json={"id": "compartilhados", "nome": "x"}).status_code == 400,
           "“Compartilhados comigo” inteiro nao se copia")
    fora = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.9.9.9"})
    checar(fora.get("/api/google/drive/navegar").status_code in (401, 403), "de fora: fechado")
    r = local.post("/api/google/drive/copias/tirar", json={"id": "f1", "apagar_copia": True})
    checar(r.status_code == 200 and not (api.estado.pasta / "Google Drive" / "Clientes").exists(), "tirar e apagar a copia")


def main() -> int:
    print("=" * 55)
    print("  O Google Drive pela internet, no Acervo")
    print("=" * 55)
    try:
        test_espelho()
        test_baixar()
        test_rotas()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
