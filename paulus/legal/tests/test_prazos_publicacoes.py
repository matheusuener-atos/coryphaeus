"""
Prazos em dias uteis e publicacoes do DJEN (src/prazos.py, src/publicacoes.py,
docs/PLANO-PRODUTO.md P3).

  - a Pascoa e os feriados moveis; o recesso de 20/12 a 20/01;
  - disponibilizacao -> publicacao -> inicio -> vencimento (Lei 11.419 e CPC);
  - dias corridos com vencimento prorrogado; feriado do escritorio;
  - a OAB escrita de varios jeitos;
  - a consulta ao DJEN (de mentira) com paginas, o HTML virando texto e a
    mesma comunicacao guardada uma vez so;
  - pela API: a publicacao vira tarefa de prazo com a conta na anotacao; de
    fora, as rotas nao existem.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_prazos_publicacoes.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-prazos-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_prazos() -> None:
    print("\nprazos em dias uteis")
    import prazos as p

    checar([p.pascoa(a) for a in (2025, 2026, 2027)] == [date(2025, 4, 20), date(2026, 4, 5), date(2027, 3, 28)], "a Pascoa")
    f = p.feriados(2026)
    checar(f.get(date(2026, 2, 16)) and f.get(date(2026, 2, 17)) and f.get(date(2026, 4, 3)) and f.get(date(2026, 6, 4)),
           "Carnaval, Sexta-feira Santa e Corpus Christi de 2026")
    checar(f.get(date(2026, 11, 20)) == "Consciência Negra", "20 de novembro (Lei 14.759/2023)")
    checar(p.em_recesso(date(2026, 12, 20)) and p.em_recesso(date(2027, 1, 20)) and not p.em_recesso(date(2027, 1, 21)),
           "recesso de 20/12 a 20/01, inclusive")
    r = p.calcular(date(2026, 9, 25), 15, origem="disponibilizacao")
    checar(r["publicacao"] == "2026-09-28" and r["inicio"] == "2026-09-29" and r["vencimento"] == "2026-10-20",
           "disponibilizado na sexta: publica na segunda, comeca na terca, 15 uteis pulando 12/10", r)
    r = p.calcular(date(2026, 12, 15), 5)
    checar(r["vencimento"] == "2027-01-22", "o recesso suspende a contagem", r["vencimento"])
    r = p.calcular(date(2026, 10, 1), 2, uteis=False)
    checar(r["vencimento"] == "2026-10-05", "corridos: vence no sabado, passa para segunda (art. 224, par. 1o)", r["vencimento"])
    extras = p.extras_das_preferencias([{"data": "2026-10-06", "nome": "Aniversário da cidade"}, {"data": "ruim"}])
    r = p.calcular(date(2026, 10, 2), 2, extras=extras)
    checar(r["vencimento"] == "2026-10-07" and any("Aniversário da cidade" in x for x in r["passos"]),
           "o feriado do escritorio conta e aparece na conta", r)
    try:
        p.calcular(date(2026, 10, 1), 0)
        recusou = False
    except ValueError:
        recusou = True
    checar(recusou, "prazo de 0 dias: recusado")


def test_publicacoes() -> None:
    print("\npublicacoes do DJEN")
    import publicacoes as pub

    checar(pub.ler_oab("GO 12345") == {"numero": "12345", "uf": "GO"} and pub.ler_oab("12.345/SP") == {"numero": "12345", "uf": "SP"}
           and pub.ler_oab("OAB/MG 098765") == {"numero": "98765", "uf": "MG"} and pub.ler_oab("123") is None,
           "a OAB escrita de varios jeitos")
    paginas = {1: [{"id": i, "data_disponibilizacao": "2026-09-25", "siglaTribunal": "TJGO", "tipoComunicacao": "Intimação",
                    "nomeOrgao": "1ª Vara", "numeroprocessocommascara": f"000{i}-00.2026.8.09.0001",
                    "texto": "<html><body><p>Fica a parte <b>intimada</b>&nbsp;para manifestar.</p></body></html>"}
                   for i in range(100)],
               2: [{"id": 100, "data_disponibilizacao": "2026-09-25", "siglaTribunal": "TJGO", "texto": "<p>última</p>"}]}
    pedidos = []

    def abrir(pedido, timeout=0):
        pedidos.append(pedido.full_url)
        n = int(pedido.full_url.split("pagina=")[1].split("&")[0])
        return io.BytesIO(json.dumps({"status": "success", "items": paginas.get(n, [])}).encode("utf-8"))

    itens = pub.consultar({"numero": "12345", "uf": "GO"}, date(2026, 9, 20), date(2026, 9, 29), abrir=abrir)
    checar(len(itens) == 101 and len(pedidos) == 2 and "numeroOab=12345" in pedidos[0] and "ufOab=GO" in pedidos[0],
           "pagina a pagina, so com a OAB e o periodo", pedidos[:1])
    n = pub.normalizar(itens[0], {"numero": "12345", "uf": "GO"})
    checar(n["texto"] == "Fica a parte intimada para manifestar." and n["processo"].startswith("0000-") and n["oab"] == "GO 12345",
           "o HTML vira texto", n["texto"])
    de, ate = pub.periodo_para_consultar("2026-09-20", hoje=date(2026, 9, 29))
    checar(de == date(2026, 9, 18) and ate == date(2026, 9, 29), "consulta de dois dias antes da ultima ate hoje")
    de, _ = pub.periodo_para_consultar("", hoje=date(2026, 9, 29))
    checar(de == date(2026, 9, 22), "a primeira vez, a ultima semana")

    print("  pela API")
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    r = local.post("/api/publicacoes/consultar")
    checar(r.status_code == 400 and "OAB" in r.json().get("detail", ""), "sem OAB: pede antes", r.text[:160])
    r = local.post("/api/publicacoes/configurar", json={"oabs": ["GO 12345", "sem numero"]})
    checar(r.status_code == 400, "OAB que nao entende: recusada")
    api.estado.prefs.dados["pessoa"]["oab"] = "GO 12345"
    local.post("/api/publicacoes/configurar", json={"oabs": ["12.345/GO", "SP 555"], "ligado": True})
    checar(local.get("/api/publicacoes").json()["oabs"] == ["GO 12345", "SP 555"], "as OABs sem repetir (a de Meus dados primeiro)")
    antes = pub.consultar
    pub.consultar = lambda o, de, ate, abrir=None: antes(o, de, ate, abrir=abrir_so_go) if o["uf"] == "GO" else []

    def abrir_so_go(pedido, timeout=0):
        return abrir(pedido, timeout)

    try:
        r = local.post("/api/publicacoes/consultar")
        checar(r.status_code == 200 and r.json()["encontradas"] == 101, "a consulta guarda as novas", r.text[:160])
        r = local.post("/api/publicacoes/consultar")
        checar(r.status_code == 200 and r.json()["encontradas"] == 0, "consultar de novo nao repete", r.text[:160])
    finally:
        pub.consultar = antes
    lista = local.get("/api/publicacoes").json()["publicacoes"]
    alvo = next(p for p in lista if p["processo"] == "0007-00.2026.8.09.0001")
    r = local.post(f"/api/publicacoes/{alvo['id']}/prazo", json={"dias": 15})
    tarefa = api.estado.tarefas.obter(r.json()["tarefa_id"])
    checar(r.status_code == 200 and tarefa["prazo"] == "2026-10-20" and tarefa["lista"] == "Prazos" and "Lei 11.419" in tarefa["anotacao"],
           "a publicacao vira tarefa de prazo, com a conta na anotacao", tarefa)
    checar(local.get("/api/publicacoes").json()["novas"] == 100, "e sai das novas")
    r = local.post("/api/prazos/calcular", json={"data": "2026-09-25", "dias": 15, "origem": "disponibilizacao"})
    checar(r.status_code == 200 and r.json()["vencimento"] == "2026-10-20", "calcular um prazo solto")
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    try:
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
        checar(fora.get("/api/publicacoes").status_code in (401, 403), "de fora: nao existe (por ora)")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False


def main() -> int:
    test_prazos()
    test_publicacoes()
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
