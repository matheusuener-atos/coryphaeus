"""
N14 - o agente que faz sozinho (src/agentes.py `autonomia`, src/agente_na_conversa.py, js/74-autonomia.js).

  - o AGENTE.md ganha `autonomia:`, só com ferramentas que o agente já tem;
  - desligada a chave "Agentes fazem sozinhos" (de fábrica), o cartão e a
    fila, como sempre;
  - ligada: o compromisso entra na agenda sem o cartão, e o Histórico de
    Aprovações guarda "feito sozinho", com o resultado; nenhum aviso de
    pedido novo; desfazer apaga o compromisso (e não desfaz duas vezes);
  - o agente sem a ferramenta na autonomia, o pedido sem a data, e o limite do
    dia voltam ao cartão (o limite, dito);
  - o que não tem como desfazer (mostrar documento) diz isso;
  - de fora, desfazer é da janela do escritório;
  - no Edge: o cartão "feito sozinho" na conversa, desfazer por ele, e o
    "Desfazer" no Histórico de Aprovações.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n14_autonomia.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n14-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def agente_md(nome, ferramentas, autonomia, palavra):
    return f"""---
nome: {nome}
descricao: Anota compromissos do escritório.
quando_usar:
  exemplos:
    - anote uma {palavra}
  palavras: [{palavra}]
capacidades: [perguntar]
ferramentas: [{", ".join(ferramentas)}]
autonomia: [{", ".join(autonomia)}]
fontes:
  acervo: acervo
saida:
  formato: texto
modelo: conversa
testes:
  - pergunta: anote uma {palavra} amanhã
    deve_conter: [{palavra}]
versao: 1
---

Anote o que pedirem.
"""


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
    print("  N14 — o agente que faz sozinho")
    print("=" * 55)
    import agente_na_conversa as agm
    import agentes
    import api
    from acesso import politicas
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    ag = api.estado.agentes
    api.estado.prefs.dados.setdefault("conversa", {})["agentes"] = True

    print("\no AGENTE.md")
    try:
        ag.validar(agente_md("Errado", ["criar_compromisso"], ["cadastrar_cliente"], "visita"))
        checar(False, "autonomia fora das ferramentas: recusa")
    except agentes.ErroDeAgente as exc:
        checar("não está entre as ferramentas" in str(exc), "autonomia fora das ferramentas: recusa", str(exc))
    a = ag.criar(agente_md("Secretária", ["criar_compromisso", "exibir_documento"], ["criar_compromisso", "exibir_documento"], "reunião"))
    slug = a.slug if hasattr(a, "slug") else a["slug"]
    ag.ativar(slug, vi_o_conteudo=True, por="teste")
    b = ag.criar(agente_md("Agenda sem autonomia", ["criar_compromisso"], [], "audiência"))
    slug_b = b.slug if hasattr(b, "slug") else b["slug"]
    ag.ativar(slug_b, vi_o_conteudo=True, por="teste")
    checar(ag.obter(slug).autonomia == ["criar_compromisso", "exibir_documento"] if hasattr(ag, "obter") else True, "a autonomia fica no agente")

    def perguntar(texto):
        tid = local.post("/api/trabalhos", json={"pedido": "n14"}).json()["id"]
        return tid, eventos(local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": texto}).text)

    print("\ndesligada (de fábrica)")
    checar(not api.estado.prefs.pode("agentes_sozinhos"), "a chave vem desligada")
    antes = api.estado.base.contar("compromissos")
    tid, ev = perguntar("@Secretária anote uma reunião amanhã às 10h com a Clínica Bem Viver")
    prop = next((d for t, d in ev if t == "proposta"), {})
    checar(prop.get("tipo") == "agenda" and prop.get("pedido_id") and api.estado.base.contar("compromissos") == antes,
           "o cartão e o pedido na fila, como sempre", prop.get("tipo"))
    api.estado.fila.esquecer(prop.get("pedido_id", ""))

    print("\nligada")
    avisos = []
    api.estado.fila.ao_pedir = lambda pedido: avisos.append(pedido.titulo)
    api.estado.prefs.atualizar({"autonomia": {"agentes_sozinhos": True}})
    tid, ev = perguntar("@Secretária anote uma reunião amanhã às 10h com a Clínica Bem Viver")
    prop = next((d for t, d in ev if t == "proposta"), {})
    pedido = api.estado.fila.obter(prop.get("pedido_id", ""))
    comp = api.estado.base.um("SELECT * FROM compromissos ORDER BY id DESC LIMIT 1") or {}
    checar(prop.get("tipo") == "sozinho" and api.estado.base.contar("compromissos") == antes + 1 and comp.get("hora") == "10:00",
           "o compromisso entra sem o cartão", (prop.get("tipo"), dict(comp)))
    checar(pedido and pedido.estado == "aprovado" and pedido.acao == "agente.sozinho" and "feito sozinho" in pedido.resultado
           and not any(p.acao == "agente.sozinho" for p in api.estado.fila.pendentes), "o Histórico guarda “feito sozinho”, nada esperando", pedido and pedido.resultado)
    checar(not avisos, "nenhum aviso de pedido novo para o que já foi feito", avisos)
    texto = "".join(d.get("t", "") for t, d in ev if t == "token")
    checar("feito sozinho pelo agente “Secretária”" in texto, "a conversa diz que foi sozinho", texto)
    r = local.post(f"/api/aprovacoes/{pedido.id}/desfazer")
    checar(r.status_code == 200 and "apagado" in r.json()["desfeito"] and api.estado.base.contar("compromissos") == antes,
           "desfazer apaga o compromisso", r.json())
    checar(local.post(f"/api/aprovacoes/{pedido.id}/desfazer").status_code == 400, "não desfaz duas vezes")

    print("\no que volta ao cartão")
    tid, ev = perguntar("@Agenda sem autonomia anote uma audiência amanhã às 14h")
    checar(next((d for t, d in ev if t == "proposta"), {}).get("tipo") == "agenda", "o agente sem a ferramenta na autonomia: cartão")
    tid, ev = perguntar("@Secretária anote uma reunião com a Clínica")
    checar(next((d for t, d in ev if t == "proposta"), {}).get("tipo") == "agenda", "sem a data: cartão (falta um dado)")
    limite = agm.LIMITE_SOZINHO_POR_DIA
    agm.LIMITE_SOZINHO_POR_DIA = 0
    try:
        tid, ev = perguntar("@Secretária anote uma reunião amanhã às 16h")
        prop = next((d for t, d in ev if t == "proposta"), {})
        checar(prop.get("tipo") == "agenda" and "sozinho hoje" in prop.get("porque", ""), "passado o limite do dia: cartão, dito", prop.get("porque"))
    finally:
        agm.LIMITE_SOZINHO_POR_DIA = limite
    for p in list(api.estado.fila.pendentes):
        api.estado.fila.esquecer(p.id)
    falso = api.estado.fila.pedir("x", "conversa", avisar=False, acao="agente.sozinho", dados={"ferramenta": "exibir_documento", "feito_id": 0})
    api.estado.fila.decidir(falso.id, True)
    r = local.post(f"/api/aprovacoes/{falso.id}/desfazer")
    checar(r.status_code == 400 and "não há o que desfazer" in r.json()["detail"], "mostrar documento: não há o que desfazer, dito", r.json())
    checar(politicas.de("POST", "/api/aprovacoes/{id_}/desfazer") == politicas.BLOQUEADO, "de fora, desfazer é da janela do escritório")

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
        with sync_playwright() as pw:
            try:
                nav = pw.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof cartaoSozinho === 'function' && typeof enviar === 'function'")
                pag.wait_for_timeout(800)
                pag.fill("#pedido", "@Secretária anote uma reunião amanhã às 11h")
                pag.evaluate("() => { enviar(); }")
                pag.wait_for_selector(".proposta.sozinho", timeout=20000)
                checar("FEITO SOZINHO" in pag.inner_text(".proposta.sozinho").upper() and pag.locator("[data-sozinho-desfazer]").count() == 1,
                       "o cartão “feito sozinho” na conversa, com Desfazer")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n14-conversa.png"))
                antes = api.estado.base.contar("compromissos")
                pag.click("[data-sozinho-desfazer]")
                pag.wait_for_function("() => /desfeito/i.test(document.querySelector('.proposta.sozinho').innerText)", timeout=10000)
                checar(api.estado.base.contar("compromissos") == antes - 1, "desfazer pelo cartão apaga o compromisso")
                pag.fill("#pedido", "@Secretária anote uma reunião amanhã às 15h")
                pag.evaluate("() => { enviar(); }")
                pag.wait_for_function("() => document.querySelectorAll('.proposta.sozinho [data-sozinho-desfazer]').length >= 1", timeout=20000)
                pag.wait_for_timeout(500)
                pag.evaluate("() => { mostrarAprovacoes(); }")
                pag.wait_for_selector("[data-decidido]", timeout=15000)
                ultimo = next(p for p in sorted(api.estado.fila.decididos_hoje(), key=lambda x: x.decidido_em, reverse=True) if p.acao == "agente.sozinho"
                              and not (p.dados or {}).get("desfeito") and "15:00" in (p.resultado or "") + (p.titulo or ""))
                pag.click(f"[data-decidido='{ultimo.id}']")
                pag.wait_for_selector("#ap-dlg-desfazer", timeout=10000)
                checar("feito sozinho pelo agente" in pag.inner_text("#veu-dialogo"), "o Histórico diz “feito sozinho pelo agente”")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n14-historico.png"))
                antes = api.estado.base.contar("compromissos")
                pag.click("#ap-dlg-desfazer")
                pag.wait_for_timeout(1500)
                checar(api.estado.base.contar("compromissos") == antes - 1, "desfazer pelo Histórico")
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
