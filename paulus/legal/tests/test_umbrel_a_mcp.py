"""
Ideia A do umbrelOS (docs/DECISAO-UMBREL.md): o servidor MCP das leis
(src/mcp_leis.py).

  - desligado de fábrica: o /mcp responde 404;
  - sem token 401; token errado 401; token revogado 401; e o token não fica
    guardado, só o resumo;
  - só deste computador: pedido de outro endereço, ou com os cabeçalhos da
    Cloudflare (o túnel do acesso de fora), 403;
  - initialize, tools/list (só as ferramentas da conexão) e tools/call;
  - ferramenta fora da lista da conexão: negada;
  - nenhuma ferramenta devolve texto do Acervo, da biblioteca ou de cadastro:
    o catálogo só tem leis;
  - as rotas que criam e revogam conexão são bloqueadas de fora;
  - toda chamada vai para a auditoria.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_umbrel_a_mcp.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import leis as leis_mod  # noqa: E402
import mcp_leis  # noqa: E402
from base import Base  # noqa: E402

LEIS = RAIZ / "data" / "leis"
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  Umbrel A — o servidor MCP das leis")
    print("=" * 55)
    from fastapi.testclient import TestClient

    import api
    import acesso.politicas as pol

    pasta = Path(tempfile.mkdtemp(prefix="paulus-mcp-"))
    base = Base(pasta / "b.db")
    L = leis_mod.Leis(base)
    if (LEIS / "l8078compilado.htm").exists():
        L.importar(LEIS / "l8078compilado.htm", "cdc")
    auditoria: list[dict] = []
    original, prefs = api.estado.mcp, dict(api.estado.prefs.dados.get("umbrel") or {})
    api.estado.mcp = mcp_leis.ServidorMCP(leis=L, conexoes=mcp_leis.Conexoes(pasta), ligado=lambda: ligado[0],
                                          registrar=lambda **e: auditoria.append(e), versao="teste")
    ligado = [False]
    local = TestClient(api.app, client=("127.0.0.1", 50123))
    janela = TestClient(api.app, headers=api.cabecalho_local(), client=("127.0.0.1", 50124))

    def rpc(metodo, params=None, token="", cliente=None, cab=None, id_=1):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        h.update(cab or {})
        return (cliente or local).post("/mcp", headers=h, content=json.dumps(
            {"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}}))

    try:
        print("\ndesligado e travas")
        checar(rpc("initialize").status_code == 404, "desligado de fábrica: 404")
        ligado[0] = True
        api.estado.prefs.dados["umbrel"] = {**prefs, "mcp": True}
        r = janela.post("/api/mcp/conexoes", json={"nome": "Claude Desktop", "ferramentas": ["citar_artigo",
                                                                                            "leis_instaladas"]})
        checar(r.status_code == 200 and r.json()["token"].startswith("paulus_mcp_"), "a janela cria a conexão", r.text[:200])
        token = r.json()["token"]
        id_conexao = r.json()["conexao"]["id"]
        guardado = (pasta / "mcp" / "conexoes.json").read_text(encoding="utf-8")
        checar(token not in guardado and "resumo" in guardado, "o token não fica guardado, só o resumo")
        checar(rpc("initialize").status_code == 401, "sem token: 401")
        checar(rpc("initialize", token="paulus_mcp_errado").status_code == 401, "token errado: 401")
        de_fora = TestClient(api.app, client=("192.168.0.20", 50000))
        checar(rpc("initialize", token=token, cliente=de_fora).status_code == 403, "de outro endereço: 403")
        checar(rpc("initialize", token=token, cab={"CF-Connecting-IP": "200.1.1.1", "CF-Ray": "x"}).status_code == 403,
               "pelo túnel da Cloudflare (que chega pelo 127.0.0.1): 403")

        print("\no protocolo")
        r = rpc("initialize", {"protocolVersion": mcp_leis.PROTOCOLO}, token=token)
        checar(r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "paulus", "initialize", r.text[:200])
        r = local.post("/mcp", headers={"Authorization": f"Bearer {token}"},
                       content=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        checar(r.status_code == 202, "notificação: 202 sem corpo", r.status_code)
        nomes = [t["name"] for t in rpc("tools/list", token=token).json()["result"]["tools"]]
        checar(sorted(nomes) == ["citar_artigo", "leis_instaladas"], "tools/list só com as ferramentas da conexão", nomes)
        r = rpc("tools/call", {"name": "procurar_na_lei", "arguments": {"termo": "vício"}}, token=token).json()
        checar("error" in r and "não está liberada" in r["error"]["message"], "ferramenta fora da lista: negada", r)
        if L.contagem()["codigos"]:
            r = rpc("tools/call", {"name": "citar_artigo", "arguments": {"codigo": "cdc", "numero": "18"}},
                    token=token).json()["result"]
            texto = r["content"][0]["text"]
            checar(not r["isError"] and texto.startswith("CDC, art. 18") and "respondem solidariamente" in texto
                   and "Planalto" in texto, "citar_artigo devolve o texto oficial, com a fonte", texto[:120])
            r = rpc("tools/call", {"name": "citar_artigo", "arguments": {"codigo": "cdc", "numero": "6"}},
                    token=token).json()["result"]
            checar("Última alteração da redação" in r["content"][0]["text"] and "2021" in r["content"][0]["text"],
                   "o artigo alterado diz o ano da última alteração")
            r = rpc("tools/call", {"name": "citar_artigo", "arguments": {"codigo": "cdc", "numero": "999"}},
                    token=token).json()["result"]
            checar(r["isError"] and "Não achei" in r["content"][0]["text"], "artigo que não existe: diz que não achou")
        else:
            print("  pulado: sem o CDC do Planalto em data/leis")
        r = rpc("tools/call", {"name": "citar_artigo", "arguments": {"codigo": "cp", "numero": "121"}}, token=token)
        checar(r.json()["result"]["isError"], "código não guardado: diz que não dá para conferir")

        print("\no que não sai")
        checar(set(mcp_leis.FERRAMENTAS) == {"leis_instaladas", "citar_artigo", "procurar_na_lei"},
               "o catálogo só tem leis: nada do Acervo, da biblioteca ou de cadastro")
        for rota in ("GET /api/mcp", "POST /api/mcp/conexoes", "DELETE /api/mcp/conexoes/{id_}"):
            metodo, caminho = rota.split(" ")
            checar(pol.de(metodo, caminho) == pol.BLOQUEADO, f"{rota}: bloqueada de fora")
        checar(any(e.get("acao") == "mcp" and "citar_artigo" in e.get("alvo", "") for e in auditoria),
               "a chamada foi para a auditoria", [e.get("acao") for e in auditoria])
        checar(any(e.get("acao") == "mcp-negado" for e in auditoria), "a negada também")

        print("\nrevogar")
        checar(janela.delete(f"/api/mcp/conexoes/{id_conexao}").status_code == 200, "a janela revoga a conexão")
        checar(rpc("tools/list", token=token).status_code == 401, "token revogado: 401")
    finally:
        api.estado.mcp = original
        api.estado.prefs.dados["umbrel"] = prefs
        base.con.close()
        shutil.rmtree(pasta, ignore_errors=True)
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
