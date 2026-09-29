"""
A saude do PAULUS e o diagnostico (src/saude.py, docs/PLANO-PRODUTO.md P2).

  - /api/saude lista memoria, disco, modelo, backup, acesso de fora, versao e
    erros, cada um com estado e, quando nao esta ok, o que fazer;
  - um erro inesperado numa rota vira 500 com frase (e nao resposta vazia) e
    fica anotado - sem a mensagem, que pode trazer nome de cliente;
  - o diagnostico e um texto para baixar, com o estado e os erros, sem nome
    de cliente nem conteudo;
  - de fora, as rotas nao existem.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_saude.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-saude-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_saude() -> None:
    print("\na saude do PAULUS")
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local(), raise_server_exceptions=False)
    r = local.get("/api/saude")
    d = r.json()
    chaves = {i["chave"] for i in d["itens"]}
    checar(r.status_code == 200 and {"memoria", "disco", "modelo", "backup", "acesso", "versao", "erros"} <= chaves,
           "memoria, disco, modelo, backup, acesso, versao e erros", chaves)
    b = next(i for i in d["itens"] if i["chave"] == "backup")
    checar(b["estado"] == "aviso" and "Configurações › Backup" in b["dica"], "sem backup: aviso, com o que fazer", b)
    checar(d["geral"] in ("ok", "aviso", "erro"), "e um estado geral")

    print("  um erro inesperado")

    @api.app.get("/api/teste-erro-saude/{id_}")
    def _quebra(id_: int) -> dict:
        raise RuntimeError("Contrato da Cliente Maria Secreta.pdf")

    api.estado.acesso_de_fora.portao.rotas = api.app.router
    from acesso import politicas

    politicas.REGISTRO[("GET", "/api/teste-erro-saude/{id_}")] = politicas.PERMITIDO
    r = local.get("/api/teste-erro-saude/42")
    checar(r.status_code == 500 and "diagnóstico" in r.json().get("detail", ""), "vira 500 com frase", r.text[:160])
    erros = next(i for i in local.get("/api/saude").json()["itens"] if i["chave"] == "erros")
    checar(erros["valor"] == "1" and erros["estado"] == "aviso", "e a Saude conta o erro", erros)

    print("  o diagnostico")
    r = local.get("/api/saude/diagnostico")
    texto = r.text
    checar(r.status_code == 200 and "attachment" in r.headers.get("content-disposition", ""), "baixa como arquivo")
    checar("GET /api/teste-erro-saude/{id_}" in texto and "RuntimeError" in texto, "com a rota (molde) e o tipo do erro")
    checar("Maria Secreta" not in texto and "/42" not in texto, "sem a mensagem nem o endereco de verdade (dado de cliente)")
    checar("Saúde:" in texto and "Windows:" in texto, "com o estado e o sistema")

    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    try:
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
        checar(fora.get("/api/saude").status_code in (401, 403) and fora.get("/api/saude/diagnostico").status_code in (401, 403),
               "de fora: nao existe")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False


def main() -> int:
    test_saude()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
