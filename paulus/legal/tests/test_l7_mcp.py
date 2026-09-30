"""
L7 - o servidor MCP além das leis (src/mcp_leis.py, js/69-mcp.js).

  - a conexão com ferramenta do escritório exige escopo e o "entendi que
    sai"; sem isso, recusa;
  - só a pasta liberada: a busca e a lista não devolvem documento de fora
    do escopo, nem de caso "só no escritório" (nem com o Acervo inteiro);
  - o escopo por Serviço; o cartão só de documento liberado;
  - súmulas e temas do STJ, e a posição da casa;
  - tudo na auditoria, e a criação diz o que é do escritório e o escopo;
  - só leitura: nenhuma ferramenta nova escreve (a lista delas é conferida).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l7_mcp.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l7-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  L7 — MCP além das leis")
    print("=" * 55)
    import api
    import aparelho
    import mcp_leis
    from fastapi.testclient import TestClient

    auditoria = []
    api.estado.mcp.registrar = lambda **e: auditoria.append(e)
    api.estado.prefs.dados.setdefault("umbrel", {})["mcp"] = True
    janela = TestClient(api.app, headers=api.cabecalho_local(), client=("127.0.0.1", 50124))
    local = TestClient(api.app, client=("127.0.0.1", 50123))

    pasta = Path(api.estado.pasta)
    (pasta / "Clientes" / "Alfa").mkdir(parents=True, exist_ok=True)
    (pasta / "Clientes" / "Beta").mkdir(parents=True, exist_ok=True)
    (pasta / "Clientes" / "Alfa" / "contrato-alfa.txt").write_text("Contrato da Alfa. A multa zebrina é de dez por cento.", encoding="utf-8")
    (pasta / "Clientes" / "Beta" / "contrato-beta.txt").write_text("Contrato da Beta. A multa zebrina é de vinte por cento.", encoding="utf-8")
    s1 = janela.post("/api/servicos", json={"id": None, "dados": {"nome": "Caso Gama"}}).json()["id"]
    (api.estado.servicos.pasta_de(s1, criar=True) / "peticao-gama.txt").write_text("Petição do caso Gama. A multa zebrina foi paga.", encoding="utf-8")
    api.estado.recarregar()

    def rpc(metodo, params=None, token="", id_=1):
        return local.post("/mcp", headers={"Authorization": f"Bearer {token}"},
                          content=json.dumps({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}})).json()

    def chamar(token, nome, args=None):
        r = rpc("tools/call", {"name": nome, "arguments": args or {}}, token=token)
        return r.get("result", {}).get("content", [{}])[0].get("text", "") if "result" in r else json.dumps(r)

    print("\ncriar a conexão")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Sem escopo", "ferramentas": ["acervo_procurar"], "entendi": True})
    checar(r.status_code == 400 and "escopo" in r.json()["detail"], "ferramenta do escritório sem escopo: recusa")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Sem entendi", "ferramentas": ["acervo_procurar"], "escopo": {"tudo": True}})
    checar(r.status_code == 400 and "entendeu" in r.json()["detail"], "sem o “entendi que sai”: recusa")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Só Alfa", "ferramentas": ["acervo_procurar", "acervo_documentos", "acervo_cartao",
                                                                                "sumulas_stj", "temas_stj", "posicao_da_casa"],
                                              "escopo": {"pastas": ["Clientes\\Alfa"]}, "entendi": True})
    checar(r.status_code == 200 and r.json()["conexao"]["escopo"]["pastas"] == ["Clientes\\Alfa"], "com pasta e “entendi”: cria", r.text[:200])
    t_alfa = r.json()["token"]
    ferramentas = {f["id"]: f for f in r.json()["ferramentas"]}
    checar(ferramentas["sumulas_stj"]["publica"] and not ferramentas["acervo_procurar"]["publica"], "a tela sabe o que é público e o que é do escritório")
    criada = [e for e in auditoria if e.get("acao") == "mcp-conexao"][-1]["alvo"]
    checar("do escritório" in criada and "Clientes" in criada, "a auditoria diz o que é do escritório e o escopo", criada)
    t_publica = janela.post("/api/mcp/conexoes", json={"nome": "Públicas", "ferramentas": ["temas_stj", "citar_artigo"]}).json()["token"]

    print("\no escopo")
    texto = chamar(t_alfa, "acervo_procurar", {"termo": "multa zebrina"})
    checar("contrato-alfa.txt" in texto and "beta" not in texto.lower() and "gama" not in texto.lower(),
           "a busca só traz a pasta liberada", texto[:300])
    lista = chamar(t_alfa, "acervo_documentos")
    checar("contrato-alfa.txt" in lista and "contrato-beta.txt" not in lista, "a lista também", lista)
    checar("não está entre os liberados" in chamar(t_alfa, "acervo_cartao", {"documento": "contrato-beta.txt"}),
           "o cartão de documento de fora do escopo: recusa")
    r = rpc("tools/call", {"name": "acervo_procurar", "arguments": {"termo": "multa"}}, token=t_publica)
    checar("error" in r and "não está liberada" in r["error"]["message"], "a conexão pública não usa ferramenta do escritório")
    t_servico = janela.post("/api/mcp/conexoes", json={"nome": "Gama", "ferramentas": ["acervo_procurar"], "escopo": {"servicos": [s1]},
                                                       "entendi": True}).json()["token"]
    texto = chamar(t_servico, "acervo_procurar", {"termo": "multa zebrina"})
    checar("peticao-gama.txt" in texto and "alfa" not in texto.lower(), "o escopo por Serviço", texto[:200])
    t_tudo = janela.post("/api/mcp/conexoes", json={"nome": "Tudo", "ferramentas": ["acervo_procurar", "acervo_documentos"],
                                                    "escopo": {"tudo": True}, "entendi": True}).json()["token"]
    aparelho.so_no_escritorio().guardar([{"tipo": "pasta", "valor": "Clientes\\Beta"}])
    texto = chamar(t_tudo, "acervo_procurar", {"termo": "multa zebrina"})
    checar("contrato-alfa.txt" in texto and "contrato-beta.txt" not in texto and "contrato-beta.txt" not in chamar(t_tudo, "acervo_documentos"),
           "o caso só no escritório nunca sai, nem com o Acervo inteiro", texto[:300])
    aparelho.so_no_escritorio().guardar([])

    print("\no que é público e a posição da casa")
    import threading

    for th in threading.enumerate():
        if th.name == "temas-stj":
            th.join(60)
    texto = chamar(t_publica, "temas_stj", {"numero": "1016"})
    checar("Tema Repetitivo 1016/STJ" in texto and "Questão" in texto, "os temas do STJ", texto[:160])
    api.estado.posicoes.gravar("cdc", "51", "Multa acima de 2% é abusiva.")
    checar(chamar(t_alfa, "posicao_da_casa", {"codigo": "cdc", "numero": "51"}) == "Multa acima de 2% é abusiva.", "a posição da casa")
    checar("súmula" in chamar(t_alfa, "sumulas_stj", {"termo": "zebrina"}).lower(), "súmulas: responde sem quebrar (nenhuma aqui)")
    chamadas = [e for e in auditoria if e.get("acao") == "mcp"]
    checar(any("acervo_procurar" in e["alvo"] and e["pessoa"] == "Só Alfa" for e in chamadas), "toda chamada na auditoria")

    print("\nsó leitura")
    escreve = ("salvar", "gravar", "apagar", "mover", "enviar", "criar", "editar")
    checar(not any(p in n for n in mcp_leis.FERRAMENTAS_DO_ESCRITORIO for p in escreve),
           "nenhuma ferramenta nova é de escrever", list(mcp_leis.FERRAMENTAS_DO_ESCRITORIO))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
