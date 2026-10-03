"""
Plano e consumo (src/consumo.py, js/91-plano-consumo.js), sem rede:

  - o consumo do ciclo dividido por pessoa, com a porcentagem de cada uma;
  - linha antiga, sem `pessoa`, conta para a janela do escritório (ou "de
    fora", se veio de fora);
  - o histórico de uma pessoa junta a triagem e a resposta da mesma pergunta;
  - os limites: gravar, apagar o de uma pessoa (sem a fusão das preferências
    trazê-lo de volta), e o envio à nuvem que para no limite e diz por quê.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_consumo.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-consumo-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _linhas(estado, linhas: list[dict]) -> None:
    import nuvem

    pasta = nuvem._pasta(estado)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "envios.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in linhas), encoding="utf-8")


def main() -> int:
    print("=" * 55)
    print("  Plano e consumo")
    print("=" * 55)
    try:
        import api
        import consumo
        import nuvem

        e = api.estado
        agora = datetime.now()
        h = lambda **k: (agora - timedelta(**k)).isoformat(timespec="seconds")  # noqa: E731
        _linhas(e, [
            {"quando": h(minutes=30), "tarefa": "conversa", "titulo": "Triagem da pergunta", "trabalho_id": "t1",
             "pessoa": {"conta_id": 2, "nome": "João"}, "pergunta": "Elabore uma contestação", "tokens_entrada": 1800, "tokens_saida": 42},
            {"quando": h(minutes=29), "tarefa": "conversa", "titulo": "Contestação", "trabalho_id": "t1",
             "pessoa": {"conta_id": 2, "nome": "João"}, "pergunta": "Elabore uma contestação", "tokens_entrada": 3000, "tokens_saida": 1000},
            {"quando": h(minutes=10), "tarefa": "conversa", "titulo": "Contrato", "trabalho_id": "t2",
             "pessoa": {"conta_id": 3, "nome": "Maria"}, "pergunta": "Analise este contrato", "tokens_entrada": 1500, "tokens_saida": 500},
            {"quando": h(days=1), "tarefa": "conversa", "titulo": "Processo antigo", "trabalho_id": "t3", "de_fora": False,
             "tokens_entrada": 900, "tokens_saida": 100},
        ])

        print("\no consumo por pessoa")
        p = consumo.painel(e)
        por = {x["conta_id"]: x for x in p["pessoas"]}
        checar(por[2]["tokens"] == 5842 and por[3]["tokens"] == 2000, "João e Maria com os tokens do ciclo", {k: v["tokens"] for k, v in por.items()})
        checar(por[0]["tokens"] == 1000 and por[0]["hoje"] == 0, "a linha antiga, sem pessoa, é da janela do escritório (ontem)", por[0])
        checar(p["total"] == 8842 and abs(sum(x["porcento"] for x in p["pessoas"]) - 100) < 0.5, "as porcentagens somam 100", p["total"])
        checar(p["pessoas"][0]["conta_id"] == 2, "quem gasta mais vem primeiro")

        print("\no histórico de uma pessoa")
        hist = consumo.historico(e, 2)
        checar(len(hist) == 1 and hist[0]["rotulo"] == "Hoje" and len(hist[0]["itens"]) == 1, "triagem e resposta da mesma pergunta viram uma só", hist)
        item = hist[0]["itens"][0]
        checar(item["tokens"] == 5842 and item["pergunta"] == "Elabore uma contestação" and item["trabalho_id"] == "t1",
               "com o começo da pergunta, os tokens somados e a conversa para abrir", item)
        checar(consumo.historico(e, 0)[0]["rotulo"] == "Ontem" and consumo.historico(e, 0)[0]["itens"][0]["pergunta"] == "Processo antigo",
               "a linha antiga mostra o título da conversa, no dia de ontem")

        print("\nos limites")
        lim = consumo.guardar_limites(e, {"diario": "", "mensal": "1.000.000", "pessoas": {"2": {"diario": "5000", "mensal": ""}, "3": {"diario": "0"}}})
        checar(lim == {"diario": 0, "mensal": 1000000, "pessoas": {"2": {"diario": 5000, "mensal": 0}}}, "grava; vazio e zero são sem limite", lim)
        p = consumo.painel(e)
        joao = next(x for x in p["pessoas"] if x["conta_id"] == 2)
        checar("atingiu o limite diário" in joao["alerta"], "João passou do limite diário: o alerta aparece", joao)
        checar("limite diário" in consumo.motivo_do_limite(e, 2) and consumo.motivo_do_limite(e, 3) == "",
               "o João para no limite; a Maria, sem limite próprio, segue")
        lim = consumo.guardar_limites(e, {"diario": 0, "mensal": 0, "pessoas": {}})
        checar(lim["pessoas"] == {} and consumo.limites(e)["pessoas"] == {} and consumo.motivo_do_limite(e, 2) == "",
               "tirar o limite do João tira de vez (a fusão das preferências não o traz de volta)")

        print("\no envio à nuvem para no limite")
        consumo.guardar_limites(e, {"diario": max(1, consumo.painel(e)["hoje"]), "mensal": 0, "pessoas": {}})
        original_ligada, original_usa = nuvem.ligada, nuvem.usa
        nuvem.ligada = lambda estado: True
        nuvem.usa = lambda estado, tarefa: True
        try:
            trabalho = e.trabalhos.criar("teste do limite") if hasattr(e.trabalhos, "criar") else None
            if trabalho is None:
                from jobs import Trabalho
                trabalho = Trabalho(id="x1", pedido="teste")
            envio = nuvem.Envio(e, trabalho, pessoa={"conta_id": 3, "nome": "Maria"})
            pacote = envio.preparar("Qual o valor?", "texto", "", [])
            checar(pacote is None and "limite diário de tokens do escritório" in envio.motivo,
                   "o escritório passou do limite diário: a pergunta fica no computador, e diz por quê", envio.motivo)
        finally:
            nuvem.ligada, nuvem.usa = original_ligada, original_usa
            consumo.guardar_limites(e, {"diario": 0, "mensal": 0, "pessoas": {}})

        print("\no extrato")
        _linhas(e, [
            {"quando": h(minutes=30), "tarefa": "conversa", "trabalho_id": "t1", "pessoa": {"conta_id": 2, "nome": "João"},
             "pergunta": "Elabore", "tokens_entrada": 6000, "tokens_saida": 0},
            {"quando": h(minutes=20), "tarefa": "resumos", "pessoa": {"conta_id": 3, "nome": "Maria"},
             "pergunta": "Resumos", "tokens_entrada": 3000, "tokens_saida": 1000},
        ])
        areas = {a["tarefa"]: a for a in consumo.painel(e)["areas"]}
        checar(areas["conversa"]["tokens"] == 6000 and areas["resumos"]["tokens"] == 4000 and areas["conversa"]["porcento"] == 60.0,
               "o consumo do ciclo por área (tarefa do registro)", areas)
        checar(areas["resumos"]["nome"] == nuvem.TAREFAS["resumos"], "a área tem o nome da tarefa", areas["resumos"])
        cache = dict(nuvem._CONTA_CACHE)
        nuvem._CONTA_CACHE["dados"] = {"plano": {"nome": "Escritório", "valor": 300, "tokens": 30_000_000}}
        try:
            ex = consumo.extrato(e)
            checar(ex["total"] == 10000 and ex["por_milhao"] == 10.0 and ex["custo"] == 0.1 and ex["plano"] == "Escritório",
                   "o custo pela conta do plano: R$ 300 / 30 mi = R$ 10 por milhão", ex)
            checar([p["nome"] for p in ex["pessoas"]] == ["João", "Maria"], "por pessoa, só quem gastou, de quem gasta mais", ex["pessoas"])
            nuvem._CONTA_CACHE["dados"] = {"cortesia": True, "plano": {"nome": "Escritório", "valor": 300, "tokens": 30_000_000}}
            checar(consumo.extrato(e)["custo"] is None, "na cortesia, sem custo")
            import html as _html
            arq = consumo.gravar_pdf_do_extrato(e, _html.escape)
            checar(arq.is_file() and arq.read_bytes()[:4] == b"%PDF" and arq.parent.name == "Consumo da IA",
                   "o PDF do extrato vai para o Acervo, em Relatórios › Consumo da IA", str(arq))
            texto = consumo.html_do_extrato(ex, _html.escape)
            checar("não uma cobrança à parte" in texto and "6.000 tokens" in texto, "o texto do extrato diz o que o custo é", texto[:200])
        finally:
            nuvem._CONTA_CACHE.clear()
            nuvem._CONTA_CACHE.update(cache)

        print("\nas rotas")
        rotas = {f"{m} {r.path}" for r in api.app.routes for m in getattr(r, "methods", [])}
        checar({"GET /api/consumo", "GET /api/consumo/pessoa/{conta_id}", "POST /api/consumo/limites", "GET /api/consumo/extrato",
                "POST /api/consumo/extrato/pdf", "GET /api/consumo/extrato/arquivo"} <= rotas, "a tela tem as seis rotas")
        from fastapi.testclient import TestClient
        cli = TestClient(api.app, headers=api.cabecalho_local())
        r = cli.post("/api/consumo/extrato/pdf")
        checar(r.status_code == 200 and r.json()["nome"].startswith("extrato-consumo-"), "a rota grava o PDF", r.text[:200])
        if r.status_code == 200:
            b = cli.get("/api/consumo/extrato/arquivo", params={"nome": r.json()["nome"]})
            checar(b.status_code == 200 and b.content[:4] == b"%PDF", "e o PDF se baixa", b.status_code)
        checar(cli.get("/api/consumo/extrato/arquivo", params={"nome": "../preferencias.json"}).status_code == 404,
               "baixar só da pasta do extrato")
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
