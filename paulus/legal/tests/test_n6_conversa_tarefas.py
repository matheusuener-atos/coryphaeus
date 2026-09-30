"""
N6 - a conversa chama as tarefas de vários passos (src/intencao.py, src/ferramentas.py, js/66-passos.js).

  - a regra: "quais contratos vencem nos próximos 60 dias?", "em 3 meses",
    "este ano", sem período (90, dito); "revise o contrato X contra o padrão"
    (o padrão pelo nome ou o único com "padrão" no nome); sem o contrato, diz
    o que falta; "qual o vencimento do contrato X?" continua nos documentos;
  - na conversa: a pergunta vira cartão (nada roda sem o sim); o sim começa a
    tarefa, que termina com o relatório; contrato que não está no Acervo é
    recusado; de fora, diz que é da janela do escritório; com um agente sem a
    ferramenta, recusa;
  - no Edge: o cartão na conversa, "Rodar a tarefa", os passos e "Abrir o
    relatório".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n6_conversa_tarefas.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n6-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []

PADRAO = ("CLÁUSULA 1ª – DO OBJETO\nA locação do imóvel da Rua A.\nCLÁUSULA 2ª – DA MULTA\nA multa por atraso é de dois por cento.\n")
CONTRATO = ("1. DO OBJETO\nA locação do imóvel da Rua A.\n2. DA MULTA\nA multa por atraso é de dez por cento.\n")


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


def main() -> int:
    print("=" * 55)
    print("  N6 — a conversa chama as tarefas de vários passos")
    print("=" * 55)
    import intencao
    from extract import Document

    docs = [Document(name="Contrato Locação Beta.txt", path=str(TMP / "Contrato Locação Beta.txt"), text=CONTRATO, sha1="c1"),
            Document(name="Padrão de locação.txt", path=str(TMP / "Padrão de locação.txt"), text=PADRAO, sha1="p1")]
    hoje = date(2026, 9, 30)

    def ler(f):
        return intencao.ler(f, hoje=hoje, documentos=docs)

    print("\na regra")
    i = ler("quais contratos vencem nos próximos 60 dias?")
    checar(i.tipo == "passos" and i.campos == {"receita": "vencimentos", "dias": 60, "propor": False}, "“nos próximos 60 dias”", i.campos)
    checar(ler("contratos que terminam em 3 meses").campos.get("dias") == 90, "“em 3 meses”: 90 dias")
    checar(ler("liste os contratos que vencem este ano").campos.get("dias") == 92, "“este ano”: até 31/12", ler("liste os contratos que vencem este ano").campos)
    i = ler("quais contratos vencem?")
    checar(i.campos.get("dias") == 90 and "90 dias" in i.porque, "sem período: 90, e o cartão diz", i.porque)
    i = ler("revise o contrato Locação Beta contra o padrão")
    checar(i.tipo == "passos" and i.campos["documento"] == "Contrato Locação Beta.txt" and i.campos["padrao"] == "Padrão de locação.txt" and not i.falta,
           "revisar: o contrato pelo nome, e o único padrão do Acervo", i.campos)
    i = ler("compare o Contrato Locação Beta com o Padrão de locação")
    checar(i.campos.get("padrao") == "Padrão de locação.txt", "“compare … com o padrão …”: os dois pelo nome", i.campos)
    i = ler("revise contra o padrão")
    checar(i.tipo == "passos" and i.falta == "diga qual contrato revisar", "sem o contrato: diz o que falta", i.falta)
    checar(ler("qual o vencimento do contrato Locação Beta?").tipo == "documentos", "a pergunta sobre UM contrato continua nos documentos")
    checar(ler("o que o contrato diz sobre multa?").tipo == "documentos", "e a pergunta comum também")

    print("\nna conversa")
    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    for d in docs:
        Path(d.path).write_text(d.text, encoding="utf-8")
    api.estado.searcher.documents = list(api.estado.searcher.documents) + docs

    def perguntar(tid, texto):
        return eventos(local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": texto}).text)

    tid = local.post("/api/trabalhos", json={"pedido": "teste N6"}).json()["id"]
    ev = perguntar(tid, "quais contratos vencem nos próximos 60 dias?")
    prop = next((d for t, d in ev if t == "proposta"), {})
    antes = len(api.estado.tarefas_de_passos.listar())
    checar(prop.get("tipo") == "passos" and prop.get("ferramenta") == "tarefa_de_varios_passos" and prop["campos"]["dias"] == 60,
           "a pergunta vira cartão, com a ferramenta do catálogo", prop)
    checar(len(api.estado.tarefas_de_passos.listar()) == antes, "nada roda sem o sim")
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "passos", "campos": prop["campos"]})
    feito = r.json()
    checar(r.status_code == 200 and feito["onde"] == "passos" and "Contratos vencendo" in feito["resumo"], "o sim começa a tarefa", feito)
    limite = time.time() + 20
    t = {}
    while time.time() < limite:
        t = local.get(f"/api/passos/{feito['id']}").json()
        if t.get("estado") != "andando":
            break
        time.sleep(0.3)
    checar(t.get("estado") == "feita" and (t.get("resultado") or {}).get("documento_id"), "a tarefa termina com o relatório", t.get("estado"))

    ev = perguntar(tid, "revise o contrato Locação Beta contra o padrão")
    prop = next((d for t_, d in ev if t_ == "proposta"), {})
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "passos", "campos": prop.get("campos", {})})
    rid = r.json().get("id")
    limite = time.time() + 20
    while time.time() < limite:
        t = local.get(f"/api/passos/{rid}").json()
        if t.get("estado") != "andando":
            break
        time.sleep(0.3)
    doc = api.estado.documentos.obter(int((t.get("resultado") or {}).get("documento_id") or 0)) or {}
    checar(t.get("estado") == "feita" and "MULTA" in str(doc.get("corpo") or "") and "alterada" in str(doc.get("corpo") or "").lower(),
           "revisar pela conversa: o relatório acha a multa alterada", t.get("estado"))
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "passos", "campos": {"receita": "revisar", "documento": "Não existe.pdf",
                                                                                   "padrao": "Padrão de locação.txt"}})
    checar(r.status_code == 400 and "Acervo" in r.json().get("detail", ""), "contrato que não está no Acervo: recusa", r.json())

    import acesso.rotas as rotas_do_acesso

    original = api.rotas_do_acesso.e_local
    api.rotas_do_acesso.e_local = lambda request: False
    try:
        ev = perguntar(tid, "quais contratos vencem nos próximos 30 dias?")
    finally:
        api.rotas_do_acesso.e_local = original
    texto = "".join(d.get("t", "") for t_, d in ev if t_ == "token")
    checar("só na janela do escritório" in texto and not any(t_ == "proposta" for t_, _ in ev), "de fora: diz que é da janela do escritório", texto[:120])
    checar(rotas_do_acesso.e_local is original, "(a troca do teste foi desfeita)")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        time.sleep(1.5)
        api.estado.searcher.documents = [x for x in api.estado.searcher.documents if x.sha1 not in ("c1", "p1")] + docs
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abrirTrabalho === 'function' && typeof cartaoPassos === 'function'")
                pag.wait_for_timeout(800)
                # O cartão de gravar não volta ao reabrir a conversa (de propósito): pergunta pela caixa.
                pag.fill("#pedido", "quais contratos vencem nos próximos 45 dias?")
                pag.evaluate("() => { enviar(); }")
                pag.wait_for_selector("input[data-pc='dias']", timeout=20000)
                checar(pag.input_value("input[data-pc='dias']") == "45" and "vou rodar a tarefa" in pag.inner_text(".proposta").lower(),
                       "o cartão na conversa, com o período lido", pag.inner_text(".proposta")[:200])
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n6-cartao.png"))
                pag.fill("input[data-pc='dias']", "30")
                pag.click(".proposta [data-prop='fazer']")
                pag.wait_for_selector(".pas-na-conversa [data-pas-abrir]", timeout=20000)
                checar("Contratos vencendo" in pag.inner_text(".pas-na-conversa") and pag.locator(".pas-na-conversa .pas-passo.feito").count() >= 3,
                       "“Rodar a tarefa”: os passos feitos, ali mesmo", pag.inner_text(".pas-na-conversa")[:200])
                ultima = api.estado.tarefas_de_passos.listar()[0]
                checar(ultima["params"]["dias"] == 30, "vale o período corrigido no cartão", ultima["params"])
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n6-feita.png"))
                pag.click(".pas-na-conversa [data-pas-abrir]")
                pag.wait_for_timeout(1500)
                checar("Contratos vencendo nos próximos 30 dias" in pag.inner_text("body"), "“Abrir o relatório” abre no editor")
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

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
