"""
C5 - as outras superficies de IA.

  - o bug do documento errado: pedir uma sugestao no documento A, trocar para
    o B antes de a resposta chegar -> o B nao muda; a sugestao espera o A e
    aparece marcada nele quando ele abre (Edge);
  - o parecer do Financeiro e o resumo da gravacao como execucao
    (src/ia_em_fundo.py): com uma conversa respondendo, a chamada de outra
    tela entra na fila do modelo e diz a posicao; depois, o resultado;
  - o resultado sobrevive a reabrir o programa (a execucao sai da memoria e
    volta do registro em disco) e a tela o mostra ao voltar (Edge: o parecer
    guardado aparece no Financeiro);
  - parar funciona; com a chave desligada, a rota recusa;
  - um leitor de SSE so no codigo da tela.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_c5_superficies.py
"""

from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from test_c1_execucao import _ler_eventos, _pedir, executar_devagar  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class ClienteLento:
    """O modelo simulado das outras telas: espera `segundos` e devolve o texto."""

    def __init__(self, texto: str, segundos: float = 1.5) -> None:
        self.texto, self.segundos, self.model = texto, segundos, "simulado"

    def ask(self, *a, **k):
        time.sleep(self.segundos)
        return self.texto


def test_leitor_unico() -> None:
    print("\num leitor de SSE só")
    js = RAIZ / "frontend" / "js"
    achados = [(p.name, n) for p in sorted(js.glob("*.js")) for n in [len(re.findall(r"getReader\(", p.read_text(encoding="utf-8")))] if n]
    checar(achados == [("16-dialogos.js", 1)], "o único getReader() da tela é o de eventosSSE", achados)


def test_api() -> None:
    print("\npela API: fila, resultado, reabrir, parar")
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    antes_cliente = api.estado.cliente_para
    habilidade.executar = executar_devagar
    api.estado.cliente_para = lambda tarefa, **k: ClienteLento("Parecer de teste: o mês fechou no azul.")
    antes_ollama = api.check_ollama
    api.check_ollama = lambda modelo: (True, "")
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "superficies": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    criados = []
    try:
        t = _pedir(base, "POST", "/api/trabalhos", {"pedido": "teste C5"})
        criados.append(t["id"])
        r = _pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": "qual a multa do contrato A?",
                                                                          "apenas": ["Contrato A.docx"]}, stream=True)
        _ler_eventos(r, ate=4)   # a conversa pegou a vez e esta escrevendo
        r.close()
        e = _pedir(base, "POST", "/api/ia/parecer", {"dados": {"quando": ""}})
        r = _pedir(base, "GET", f"/api/execucoes/{e['execucao_id']}/eventos?desde=0", stream=True)
        ev = _ler_eventos(r)
        r.close()
        tipos = [tp for tp, _ in ev]
        fila = next((d for tp, d in ev if tp == "fila"), {})
        res = next((d for tp, d in ev if tp == "resultado"), {})
        checar(fila.get("posicao", 0) >= 1 and tipos.index("fila") < tipos.index("trabalhando") < tipos.index("resultado"),
               "com a conversa respondendo, o parecer entra na fila e diz a posição", tipos)
        checar(res.get("parecer", "").startswith("Parecer de teste"), "e depois vem o resultado, o JSON de antes", res)
        # "reabrir o programa": a execucao sai da memoria e volta do disco
        api.estado.execucoes._itens.pop(e["execucao_id"], None)
        r = _pedir(base, "GET", f"/api/execucoes/{e['execucao_id']}/eventos?desde=0", stream=True)
        de_novo = _ler_eventos(r)
        r.close()
        checar(any(tp == "resultado" and d.get("parecer") == res.get("parecer") for tp, d in de_novo),
               "depois de reabrir, o resultado volta do registro em disco")
        # parar
        api.estado.cliente_para = lambda tarefa, **k: ClienteLento("não devia chegar", 3)
        e2 = _pedir(base, "POST", "/api/ia/parecer", {"dados": {"quando": ""}})
        time.sleep(0.8)
        _pedir(base, "POST", f"/api/execucoes/{e2['execucao_id']}/parar", {})
        r = _pedir(base, "GET", f"/api/execucoes/{e2['execucao_id']}/eventos?desde=0", stream=True)
        ev2 = _ler_eventos(r)
        r.close()
        checar(ev2 and ev2[-1][0] == "parado" and not any(tp == "resultado" for tp, _ in ev2), "parar funciona",
               [tp for tp, _ in ev2])
        api.estado.prefs.dados["conversa"] = {**antes_prefs, "superficies": False}
        try:
            _pedir(base, "POST", "/api/ia/parecer", {"dados": {}})
            checar(False, "com a chave desligada, a rota recusa")
        except Exception as exc:  # noqa: BLE001
            checar("409" in str(exc), "com a chave desligada, a rota recusa", str(exc))
        api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "superficies": True}
        api.estado.cliente_para = lambda tarefa, **k: ClienteLento("Cláusula nova escrita pelo assistente de teste.", 2.5)
        test_tela(base, api, res)
    finally:
        habilidade.executar = antes_exec
        api.estado.cliente_para = antes_cliente
        api.check_ollama = antes_ollama
        api.estado.prefs.dados["conversa"] = antes_prefs
        for id_ in criados:
            try:
                _pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass


def test_tela(base: str, api, parecer: dict) -> None:
    print("\nna tela (Edge)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    a = _pedir(base, "POST", "/api/documentos", {"titulo": "Teste C5 — documento A", "tipo": "texto", "corpo": "<p>Texto do A.</p>"})
    b = _pedir(base, "POST", "/api/documentos", {"titulo": "Teste C5 — documento B", "tipo": "texto", "corpo": "<p>Texto do B.</p>"})
    try:
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
                return
            pag = nav.new_page(viewport={"width": 1440, "height": 900})
            pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
            erros: list[str] = []
            pag.on("pageerror", lambda e: erros.append(str(e)))
            pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
            pag.wait_for_timeout(1200)
            pag.evaluate(f"() => abrirDocumento({a['id']})")
            pag.wait_for_selector("#ed-folha", timeout=10000)
            pag.evaluate("() => { pedirNoEditor('acrescente uma cláusula de foro'); }")
            pag.wait_for_timeout(600)
            pag.evaluate(f"() => abrirDocumento({b['id']})")
            pag.wait_for_timeout(3500)
            b_depois = pag.evaluate("() => document.getElementById('ed-folha').innerText")
            checar("Cláusula nova" not in b_depois and escr_id(pag) == b["id"],
                   "trocar de documento durante a sugestão: o B não muda", b_depois[:60])
            pag.wait_for_timeout(1500)
            b_servidor = _pedir(base, "GET", f"/api/documentos/{b['id']}")
            checar("Cláusula nova" not in b_servidor.get("corpo", ""), "nem no servidor")
            pag.evaluate(f"() => abrirDocumento({a['id']})")
            pag.wait_for_selector("#ed-folha .ed-novo", timeout=10000)
            checar("Cláusula nova" in pag.evaluate("() => document.querySelector('#ed-folha .ed-novo').textContent"),
                   "ao abrir o A, a sugestão aparece marcada nele, com Manter e Descartar")
            # o parecer guardado volta ao abrir o Financeiro
            ex = parecer and api.estado.execucoes  # o id do primeiro parecer foi para o disco
            ids = [x.stem for x in api.estado.execucoes.pasta.glob("*.jsonl")]
            alvo = next((i for i in ids if any("Parecer de teste" in l for l in (api.estado.execucoes.pasta / (i + ".jsonl")).read_text(encoding="utf-8").splitlines())), "")
            pag.evaluate("(id) => localStorage.setItem('paulus.ia.parecer.', JSON.stringify({ id: id, tipo: 'parecer', em: Date.now() }))", alvo)
            pag.evaluate("() => { fin.parecer = null; mostrarRelatorios(); }")
            pag.wait_for_function("() => (document.querySelector('.fin-parecer') || {}).textContent?.includes('Parecer de teste')",
                                  timeout=10000)
            checar(bool(ex), "voltar ao Financeiro (ou recarregar) mostra o parecer que ficou pronto")
            checar(not erros, "nenhum erro de JavaScript", erros[:3])
            nav.close()
    finally:
        for d in (a, b):
            try:
                _pedir(base, "DELETE", f"/api/documentos/{d['id']}")
            except Exception:  # noqa: BLE001
                pass


def escr_id(pag) -> int:
    return pag.evaluate("() => (escr.doc || {}).id")


def main() -> int:
    print("=" * 55)
    print("  C5 — as outras superfícies de IA")
    print("=" * 55)
    test_leitor_unico()
    test_api()
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
