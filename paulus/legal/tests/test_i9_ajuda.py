"""
Portao da I9 - a IA ajuda sem ser perguntada (src/ajuda.py, src/rotas_ajuda.py).

  - o cartao do documento so mostra fato conferido;
  - corrigir um fato grava a correcao como `manual` e acrescenta uma linha ao
    conjunto real de medicao;
  - as perguntas sugeridas respondem sem chamar o modelo;
  - o prazo achado vira pedido na fila de Aprovacoes, e nao tarefa gravada -
    uma vez so; o sim e que anota a tarefa.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i9_ajuda.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-i9-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PETICAO = """EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 2ª VARA CÍVEL DA COMARCA DE BELÉM - TJPA

Processo nº 0801234-50.2024.8.14.0301

MARIA DA SILVA vem propor AÇÃO DE COBRANÇA em face de JOSÉ PEREIRA.

DO DIREITO
Aplica-se o art. 389 da Lei 10.406/2002 e o art. 300 do CPC.

DOS PEDIDOS
Requer a condenação do réu ao pagamento do valor emprestado.

Dá-se à causa o valor de R$ 15.000,00 (quinze mil reais).

O prazo para cumprimento do acordo vence em 10 de dezembro de 2099.

Belém/PA, assinado em 10 de março de 2024.
"""


class Falha:
    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"

    def __init__(self) -> None:
        self.chamadas = 0

    def ask(self, *a, **k):
        self.chamadas += 1
        raise AssertionError("o modelo foi chamado")

    def digest(self, model=""):
        return ""


def main() -> int:
    print("=" * 55)
    print("  I9 - a IA ajuda sem ser perguntada")
    print("=" * 55)
    try:
        return _rodar()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def _rodar() -> int:
    from fastapi.testclient import TestClient

    import api
    from inteligencia import portas
    from inteligencia.esquema import Item

    falha = Falha()
    api.estado.client = falha
    api.estado.cliente_para = lambda tarefa: falha
    api.estado.saber.ligada = False
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "peticao.txt").write_text(PETICAO, encoding="utf-8")
    api.estado.recarregar()
    doc = api.estado.searcher.documents[0]
    analise = portas.analisar_documento(api.estado.saber.biblioteca, api.estado.catalogo, doc.path, texto=doc.text,
                                        paginas=doc.pages, sha1=doc.sha1, titulo=doc.name)
    meta = analise.metadata
    # Um valor achado mas NAO conferido: nao pode aparecer no cartao.
    valores = meta.colecao("amounts")
    valores.append(Item(id="amt_nao_conferido", dados={"kind": "fee", "value_text": "R$ 99.999,00"},
                        quote="R$ 99.999,00", certainty="inferred", verified=False, produced_by="teste"))
    meta.guardar("amounts", valores)
    api.estado.saber.biblioteca.gravar(meta, nota="teste")
    api.estado.saber.ligada = True
    c = TestClient(api.app, headers=api.cabecalho_local())

    print("\no cartão")
    d = c.get("/api/ajuda/documento", params={"nome": doc.name}).json()
    itens = (d.get("cartao") or {}).get("itens") or []
    valores = [i["valor"] for i in itens]
    checar(any("15.000,00" in v for v in valores) and any("0801234-50" in v for v in valores),
           "o cartão traz o valor da causa e o processo", valores)
    checar(not any("99.999" in v for v in valores), "o que não foi conferido não aparece", valores)

    print("\ncorrigir")
    alvo = next(i for i in itens if "15.000,00" in i["valor"])
    r = c.post("/api/ajuda/corrigir", json={"nome": doc.name, "secao": alvo["secao"], "id": alvo["id"],
                                            "valor": "R$ 16.000,00"})
    checar(r.status_code == 200, "a correção é aceita", r.text[:200])
    meta2, _ = api.estado.saber.metadados_de([doc])
    item = next((i for i in meta2[0].colecao("amounts") if i.id == alvo["id"]), None)
    checar(item is not None and item.produced_by == "manual" and item.valor == "R$ 16.000,00",
           "gravada no metadata como manual", item and (item.produced_by, item.valor))
    conjunto = api.DADOS_DIR / "medicao" / "conjunto-real.jsonl"
    linhas = [json.loads(l) for l in conjunto.read_text(encoding="utf-8").splitlines()] if conjunto.exists() else []
    checar(linhas and linhas[-1]["alguma"] == ["R$ 16.000,00"] and linhas[-1]["documentos"] == [doc.name],
           "e uma pergunta nova no conjunto real", linhas[-1:] if linhas else None)

    print("\nas perguntas sugeridas")
    d = c.get("/api/ajuda/documento", params={"nome": doc.name}).json()
    sugestoes = d.get("sugestoes") or []
    checar(len(sugestoes) >= 2, "há perguntas sugeridas para a petição", sugestoes)
    for pergunta in sugestoes:
        id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
        resposta = c.post(f"/api/trabalhos/{id_}/perguntar",
                          json={"pergunta": pergunta, "apenas": [doc.name], "documentos": True}).text
        texto = "".join(json.loads(b.split("data: ", 1)[1]).get("t", "") for b in resposta.split("\n\n")
                        if b.startswith("event: token"))
        checar(texto.strip(), f"“{pergunta}” responde na hora: {texto[:60]!r}")
    checar(falha.chamadas == 0, "sem chamar o modelo nenhuma vez", falha.chamadas)

    print("\nos prazos")
    tarefas_antes = len(api.estado.tarefas.listar("todas"))
    r = c.post("/api/ajuda/prazos", json={"nome": doc.name}).json()
    pedidos = [p for p in api.estado.fila._itens.values() if p.acao == "ajuda.prazo"]
    checar(r.get("propostos") == 1 and len(pedidos) == 1 and "10/12/2099" in pedidos[0].titulo,
           "o vencimento vira pedido em Aprovações", (r, [p.titulo for p in pedidos]))
    tarefas_depois = len(api.estado.tarefas.listar("todas"))
    checar(tarefas_antes == tarefas_depois, "e nenhuma tarefa é gravada sozinha", (tarefas_antes, tarefas_depois))
    r = c.post("/api/ajuda/prazos", json={"nome": doc.name}).json()
    checar(r.get("propostos") == 0, "propor de novo não duplica")
    resultado = api.EXECUTORES["ajuda.prazo"](pedidos[0])
    tarefas_fim = len(api.estado.tarefas.listar("todas"))
    checar("10/12/2099" in resultado and tarefas_fim == (tarefas_antes or 0) + 1,
           "o sim anota a tarefa com o prazo", (resultado, tarefas_fim))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
