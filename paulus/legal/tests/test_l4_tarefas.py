"""
L4 - tarefas de vários passos com ponto de restauração (src/passos.py, js/66-passos.js).

  - o ponto de restauração: apaga o que a tarefa criou, volta o arquivo
    alterado, e não apaga nem volta o que alguém mudou depois (diz isso);
  - revisar contra o padrão: cláusulas achadas, alinhadas mesmo fora de
    ordem, e comparadas - igual, alterada (o que saiu e o que entrou),
    faltando, a mais; sem cláusula numerada, falha com o motivo; o modelo
    só explica quando pedido, e a frase vem marcada;
  - contratos vencendo: só as datas conferidas, no período, só contratos;
    o relatório no editor; propor na Agenda vira pedidos em Aprovações;
  - desfazer: relatório e pedidos saem; o pedido já aprovado fica, e a
    tarefa diz "desfeita em parte";
  - no Edge: a seção na tela Agentes, rodar, ver os passos, desfazer.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l4_tarefas.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []

PADRAO = """CONTRATO PADRÃO DE LOCAÇÃO

CLÁUSULA 1ª - DO OBJETO
O locador cede ao locatário o uso do imóvel descrito no quadro resumo, para fins residenciais.

CLÁUSULA 2ª - DO ALUGUEL
O aluguel mensal é o do quadro resumo, pago até o dia cinco de cada mês, por boleto.

CLÁUSULA 3ª - DA MULTA
O atraso no pagamento sujeita o locatário à multa de dois por cento sobre o valor devido, mais juros de mora.

CLÁUSULA 4ª - DA VISTORIA
O imóvel é entregue vistoriado, e a vistoria de saída segue o mesmo laudo.
"""

CONTRATO = """CONTRATO DE LOCAÇÃO - CLÍNICA

CLÁUSULA 1ª - DO OBJETO
O locador cede ao locatário o uso do imóvel descrito no quadro resumo, para fins residenciais.

CLÁUSULA 2ª - DA MULTA
O atraso no pagamento sujeita o locatário à multa de dez por cento sobre o valor devido, mais juros de mora e correção.

CLÁUSULA 3ª - DO ALUGUEL
O aluguel mensal é o do quadro resumo, pago até o dia cinco de cada mês, por boleto.

CLÁUSULA 4ª - DA RENOVAÇÃO AUTOMÁTICA
Findo o prazo, o contrato se renova por igual período, salvo aviso com noventa dias.
"""


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def meta_falsa(tipo: str, datas: list[tuple[str, str]]):
    itens = [SimpleNamespace(id=f"d{i}", dados={"kind": k, "date": d}, source=SimpleNamespace(page=i + 1), quote=f"vigora até {d}")
             for i, (k, d) in enumerate(datas)]
    return SimpleNamespace(fatos=lambda secao: itens if secao == "dates" else [],
                           por_secao=lambda secao: {"document_type": tipo} if secao == "classification" else {})


def esperar_tarefa(local, id_, segundos=30):
    fim = time.time() + segundos
    while time.time() < fim:
        t = local.get(f"/api/passos/{id_}").json()
        if t["estado"] != "andando":
            return t
        time.sleep(0.1)
    return local.get(f"/api/passos/{id_}").json()


def main() -> int:
    print("=" * 55)
    print("  L4 — tarefas de vários passos")
    print("=" * 55)
    import passos

    print("\no ponto de restauração")
    r = passos.Restauracao(TMP / "restauracao-teste")
    criado = TMP / "criado.txt"
    criado.write_text("novo", encoding="utf-8")
    r.arquivo_criado(criado)
    mexido = TMP / "mexido.txt"
    mexido.write_text("original", encoding="utf-8")
    r.antes_de_alterar(mexido)
    mexido.write_text("alterado pela tarefa", encoding="utf-8")
    r.depois_de_alterar(mexido)
    outro = TMP / "outro.txt"
    outro.write_text("da tarefa", encoding="utf-8")
    r.arquivo_criado(outro)
    outro.write_text("alguém escreveu aqui depois", encoding="utf-8")
    feito = passos.Restauracao(TMP / "restauracao-teste").desfazer(SimpleNamespace())
    checar(not criado.exists() and mexido.read_text(encoding="utf-8") == "original",
           "desfazer apaga o criado e volta o alterado")
    checar(outro.exists() and any(not x["ok"] and "mudou o arquivo depois" in x["como"] for x in feito),
           "o arquivo que alguém mudou depois fica, e é dito", feito)

    print("\nrevisar contra o padrão")
    cp, cc = passos.clausulas_de(PADRAO), passos.clausulas_de(CONTRATO)
    checar(len(cp) == 4 and len(cc) == 4 and cp[2]["titulo"].startswith("CLÁUSULA 3ª"), "as cláusulas dos dois", [c["titulo"] for c in cp])
    comps = [passos.comparar(par) for par in passos.alinhar(cp, cc)]
    por = {(c["padrao"] or c["contrato"])["titulo"].split(" - ")[1]: c for c in comps}
    checar(por["DO OBJETO"]["situacao"] == "igual", "igual ao padrão")
    checar(por["DO ALUGUEL"]["situacao"] == "igual" and por["DO ALUGUEL"]["contrato"]["numero"] == 3,
           "a mesma cláusula em outra posição é achada", por["DO ALUGUEL"].get("contrato"))
    multa = por["DA MULTA"]
    checar(multa["situacao"] == "alterada" and any("dois" in s for s in multa["saiu"]) and any("dez" in s for s in multa["entrou"]),
           "alterada: o que saiu e o que entrou", multa)
    checar(por["DA VISTORIA"]["situacao"] == "faltando" and por["DA RENOVAÇÃO AUTOMÁTICA"]["situacao"] == "a mais",
           "falta no contrato e a mais no contrato")

    import api
    from fastapi.testclient import TestClient

    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "padrao-locacao.txt").write_text(PADRAO, encoding="utf-8")
    (pasta / "contrato-clinica.txt").write_text(CONTRATO, encoding="utf-8")
    (pasta / "parecer.txt").write_text("Parecer sem cláusula nenhuma, só texto corrido.", encoding="utf-8")
    hoje = date.today()
    (pasta / "locacao-sala.txt").write_text("Contrato da sala.", encoding="utf-8")
    (pasta / "procuracao.txt").write_text("Procuração.", encoding="utf-8")
    api.estado.recarregar()
    metas = {
        "locacao-sala.txt": meta_falsa("contrato de locação", [("term", (hoje + timedelta(days=40)).isoformat()),
                                                               ("deadline", (hoje + timedelta(days=200)).isoformat())]),
        "contrato-clinica.txt": meta_falsa("contrato", [("deadline", (hoje + timedelta(days=10)).isoformat()),
                                                         ("deadline", (hoje - timedelta(days=5)).isoformat())]),
        "procuracao.txt": meta_falsa("procuração", [("term", (hoje + timedelta(days=20)).isoformat())]),
    }
    api.estado.saber.metadados_de = lambda docs: ([metas[d.name] for d in docs if d.name in metas], {})
    local = TestClient(api.app, headers=api.cabecalho_local())

    print("\npela API: revisar")
    checar(local.post("/api/passos", json={"tipo": "revisar", "params": {"documento": "contrato-clinica.txt"}}).status_code == 400,
           "revisar sem o padrão: recusa")
    t = local.post("/api/passos", json={"tipo": "revisar", "params": {"documento": "contrato-clinica.txt", "padrao": "padrao-locacao.txt"}}).json()
    t = esperar_tarefa(local, t["id"])
    doc = api.estado.documentos.obter(t["resultado"]["documento_id"]) if t.get("resultado") else {}
    checar(t["estado"] == "feita" and all(p["estado"] == "feito" for p in t["passos"]) and t["resultado"]["conta"] ==
           {"igual": 2, "alterada": 1, "faltando": 1, "a mais": 1}, "a tarefa roda os passos e conta", (t["estado"], t.get("resultado", {}).get("conta")))
    checar("DA MULTA — alterada" in (doc.get("corpo") or "") and "Saiu do padrão" in (doc.get("corpo") or ""),
           "o relatório vai para o editor")
    t = esperar_tarefa(local, local.post("/api/passos", json={"tipo": "revisar", "params": {"documento": "parecer.txt", "padrao": "padrao-locacao.txt"}}).json()["id"])
    checar(t["estado"] == "falhou" and "cláusulas numeradas" in t["erro"], "sem cláusula numerada: falha com o motivo", t.get("erro"))
    perguntas = []
    api.estado.cliente_para = lambda tarefa, **k: SimpleNamespace(ask=lambda p, c: perguntas.append(c) or "A multa subiu de 2% para 10%, pior para o locatário.")
    t = esperar_tarefa(local, local.post("/api/passos", json={"tipo": "revisar", "params": {"documento": "contrato-clinica.txt",
                                                                                               "padrao": "padrao-locacao.txt", "explicar": True}}).json()["id"])
    corpo = api.estado.documentos.obter(t["resultado"]["documento_id"])["corpo"]
    checar(len(perguntas) == 1 and "O assistente (confira): A multa subiu" in corpo and len(t["passos"]) == 5,
           "explicar: o modelo só nas alteradas, e a frase vem marcada", len(perguntas))

    print("\npela API: contratos vencendo")
    t = esperar_tarefa(local, local.post("/api/passos", json={"tipo": "vencimentos", "params": {"dias": 90, "propor": True}}).json()["id"])
    itens = t["resultado"]["itens"]
    checar(t["estado"] == "feita" and [i["documento"] for i in itens] == ["contrato-clinica.txt", "locacao-sala.txt"],
           "só as datas conferidas no período, só contratos, em ordem", itens)
    pedidos = [p for p in api.estado.fila.pendentes if p.pedido_por == "Tarefa: contratos vencendo"]
    doc_id = t["resultado"]["documento_id"]
    checar(len(pedidos) == 2 and api.estado.documentos.obter(doc_id), "o relatório no editor e os pedidos em Aprovações")
    d = local.post(f"/api/passos/{t['id']}/desfazer").json()
    checar(d["estado"] == "desfeita" and not api.estado.documentos.obter(doc_id)
           and not [p for p in api.estado.fila.pendentes if p.pedido_por == "Tarefa: contratos vencendo"],
           "desfazer: o relatório e os pedidos saem", d["desfeita"])
    t = esperar_tarefa(local, local.post("/api/passos", json={"tipo": "vencimentos", "params": {"dias": 90, "propor": True}}).json()["id"])
    pedidos = [p for p in api.estado.fila.pendentes if p.pedido_por == "Tarefa: contratos vencendo"]
    local.post("/api/aprovacoes/decidir", json={"ids": [pedidos[0].id], "aprovar": True})
    d = local.post(f"/api/passos/{t['id']}/desfazer").json()
    checar(d["estado"] == "desfeita em parte" and any("já tinha sido decidido" in x["como"] for x in d["desfeita"]),
           "o pedido já aprovado fica, e a tarefa diz: desfeita em parte", d["desfeita"])
    checar(local.get("/api/passos/xyz").status_code == 404, "tarefa que não existe: 404")

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
                pag.wait_for_function("() => typeof mostrarAgentes === 'function' && typeof carregarTarefasDePassos === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarAgentes()")
                pag.wait_for_selector("[data-pas-nova='vencimentos']", timeout=15000)
                antes = pag.locator(".pas-tarefa").count()
                pag.click("[data-pas-nova='vencimentos']")
                pag.wait_for_selector("[data-pas-p='dias']", timeout=10000)
                pag.fill("[data-pas-p='dias']", "30")
                pag.get_by_role("button", name="Rodar").click()
                pag.wait_for_function(f"() => document.querySelectorAll('.pas-tarefa').length > {antes}", timeout=15000)
                pag.wait_for_selector(".pas-tarefa [data-pas-abrir]", timeout=20000)
                texto = pag.inner_text(".pas-tarefa")
                checar("Separar o que vence em 30 dias" in texto and "feito" in texto, "a tarefa aparece com os passos (30 dias)", texto[:200])
                pag.screenshot(path=str(TMP / "l4-tarefas.png"))
                pag.click(".pas-tarefa [data-pas-desfazer]")
                pag.get_by_role("button", name="Desfazer").last.click()
                pag.wait_for_function("() => /desfeita/.test(document.querySelector('.pas-tarefa').textContent)", timeout=15000)
                checar("relatório apagado do editor" in pag.inner_text(".pas-tarefa"), "desfazer pela tela, com o que foi desfeito")
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (foto em {TMP})")
                nav.close()

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
