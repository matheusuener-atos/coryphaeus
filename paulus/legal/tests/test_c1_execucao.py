"""
C1 - a resposta roda sem depender da janela (src/execucoes.py).

Com um modelo simulado que escreve devagar (a habilidade de perguntar e
trocada por uma que manda 24 pedacos de texto, um a cada 0,12 s):

  - desconectar o inscrito no meio -> a execucao termina e a resposta
    completa fica na conversa;
  - inscrever de novo com desde=n -> exatamente os eventos depois de n, sem
    repetir nem pular;
  - dois inscritos na mesma execucao recebem a mesma sequencia;
  - "matar" o processo no meio (simulado: um registro sem evento de fim em
    disco) -> ao abrir, a conversa tem o texto parcial marcado como
    interrompido, e a recuperacao nao se repete;
  - todo evento leva execucao_id e conversa_id;
  - parar interrompe so a propria execucao;
  - com a chave desligada, tudo como antes (o gerador preso a conexao).

A parte da tela (evento de outra conversa nao mexe na conversa aberta) esta
em tests/test_tela.py, com o navegador.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_c1_execucao.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import execucoes as execucoes_mod  # noqa: E402

_falhas: list[str] = []
PEDACOS = [f"palavra{i} " for i in range(24)]


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def executar_devagar(ctx, pergunta: str = "", top: int = 6, apenas=None):
    """A habilidade de perguntar, simulada: fontes, leitura e 24 pedacos devagar."""
    yield "fontes", {"consultados": ["Contrato A.docx"], "ignorados": [], "total_contratos": 1, "apenas": [],
                     "trechos": [{"documento": "Contrato A.docx", "trecho": 1, "score": 1.0, "texto": "cláusula 1"}]}
    yield "lendo", {"caracteres": 1200, "trechos": 1, "documentos": 1, "caminho": "busca", "previsao": {"sabe": False}}
    yield "escrevendo", {"lendo_segundos": 0.1}
    for p in PEDACOS:
        if ctx.parar and ctx.parar():
            return
        time.sleep(0.12)
        yield "token", {"t": p}
    yield "fim", {}


# ------------------------------------------------------------- o modulo

def test_modulo(pasta: Path) -> None:
    print("\no registro da execução")
    ex = execucoes_mod.Execucoes(pasta)
    e = ex.criar(conversa_id="c1", dono="local")

    def eventos():
        for i in range(10):
            time.sleep(0.03)
            yield "token", {"t": f"p{i} "}
        yield "fim", {}

    a, b = [], []
    ta = threading.Thread(target=lambda: a.extend(execucoes_mod.do_sse(s) for s in ex.inscrever(e, 0)))
    ta.start()
    ex.rodar(e, eventos())
    tb = threading.Thread(target=lambda: b.extend(execucoes_mod.do_sse(s) for s in ex.inscrever(e, 0)))
    time.sleep(0.1)
    tb.start()
    ta.join(5)
    tb.join(5)
    checar(a and a == b, "dois inscritos recebem a mesma sequência", (len(a), len(b)))
    checar([d["seq"] for _, d in a] == list(range(1, 12)), "a sequência não repete nem pula", [d["seq"] for _, d in a])
    checar(all(d.get("execucao_id") == e.id and d.get("conversa_id") == "c1" for _, d in a),
           "todo evento leva execucao_id e conversa_id")
    depois = [execucoes_mod.do_sse(s) for s in ex.inscrever(e, 4)]
    checar([d["seq"] for _, d in depois] == list(range(5, 12)), "desde=4 entrega do 5 em diante", [d["seq"] for _, d in depois])
    linhas = e.arquivo.read_text(encoding="utf-8").splitlines()
    checar(len(linhas) == 11 and json.loads(linhas[-1])["tipo"] == "fim", "cada evento foi para o disco na hora")
    checar(e.estado == "concluida" and e.texto_parcial().startswith("p0 p1"), "a execução termina concluída, com o texto")


def test_interrompida(pasta: Path) -> None:
    print("\no programa fechou no meio (simulado)")
    from jobs import Trabalhos

    trabalhos = Trabalhos(pasta / "trabalhos")
    t = trabalhos.criar("Teste de interrupção")
    t.dizer("pessoa", "qual a multa?")
    t.estado = "executando"
    trabalhos.salvar(t)
    ex = execucoes_mod.Execucoes(pasta / "execucoes")
    e = ex.criar(conversa_id=t.id)
    e.acrescentar("execucao", {"conversa_id": t.id})
    e.acrescentar("fontes", {"trechos": [{"documento": "Contrato A.docx", "trecho": 1, "texto": "multa de 10%"}]})
    for p in ("A multa ", "é de ", "10%"):
        e.acrescentar("token", {"t": p})
    # "matar": uma instância nova, que só conhece o disco
    novo = execucoes_mod.Execucoes(pasta / "execucoes")

    def pausar(tr):
        tr.estado = "pausado"

    checar(novo.recuperar_interrompidas(trabalhos, pausar) == 1, "o registro sem fim é achado ao abrir")
    t2 = trabalhos.obter(t.id)
    ultima = t2.mensagens[-1]
    checar(ultima.autor == "paulus" and ultima.texto == "A multa é de 10%" and ultima.interrompida,
           "a conversa tem o texto parcial, marcado como interrompido", (ultima.autor, ultima.texto, ultima.interrompida))
    checar(ultima.fontes and ultima.fontes[0]["documento"] == "Contrato A.docx", "com as fontes que já tinham chegado")
    checar(t2.estado == "pausado", "e a conversa fica parada")
    de_novo = execucoes_mod.Execucoes(pasta / "execucoes")
    checar(de_novo.recuperar_interrompidas(trabalhos, pausar) == 0 and len(trabalhos.obter(t.id).mensagens) == 2,
           "abrir de novo não recupera outra vez")


# --------------------------------------------------------------- pela API

def _ler_eventos(resposta, ate: int | None = None) -> list[tuple[str, dict]]:
    eventos, bloco = [], []
    for linha in resposta:
        linha = linha.decode("utf-8").rstrip("\n")
        if linha:
            bloco.append(linha)
            continue
        if bloco:
            eventos.append(execucoes_mod.do_sse("\n".join(bloco)))
            bloco = []
            if ate is not None and len(eventos) >= ate:
                break
    return eventos


def _pedir(base: str, metodo: str, caminho: str, dados=None, cabecalhos=None, stream=False):
    import api

    req = urllib.request.Request(base + caminho, method=metodo,
                                 data=json.dumps(dados).encode() if dados is not None else None,
                                 headers={"Content-Type": "application/json", **api.cabecalho_local(), **(cabecalhos or {})})
    r = urllib.request.urlopen(req, timeout=60)
    return r if stream else json.loads(r.read() or b"{}")


def _esperar(condicao, segundos: float = 15) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        if condicao():
            return True
        time.sleep(0.1)
    return False


def test_api() -> None:
    print("\npela API, com o modelo simulado")
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    habilidade.executar = executar_devagar
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    criados = []
    try:
        t = _pedir(base, "POST", "/api/trabalhos", {"pedido": "teste C1"})
        criados.append(t["id"])
        r = _pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": "qual a multa do contrato A?",
                                                                          "apenas": ["Contrato A.docx"]}, stream=True)
        primeiros = _ler_eventos(r, ate=8)
        r.close()   # a janela fechou
        tipos = [tp for tp, _ in primeiros]
        checar(tipos and tipos[0] == "execucao", "o primeiro evento diz o id da execução", tipos[:3])
        exec_id = primeiros[0][1].get("execucao_id", "")
        n = primeiros[-1][1].get("seq", 0)
        checar(all(d.get("conversa_id") == t["id"] for _, d in primeiros), "os eventos dizem de que conversa são")
        feito = _esperar(lambda: (_pedir(base, "GET", f"/api/trabalhos/{t['id']}").get("estado") == "concluido"), 20)
        conversa = _pedir(base, "GET", f"/api/trabalhos/{t['id']}")
        texto = (conversa["mensagens"][-1] if conversa["mensagens"] else {}).get("texto", "")
        checar(feito and texto == "".join(PEDACOS).strip(),
               "janela fechada no meio: a resposta termina e fica inteira na conversa", (conversa.get("estado"), texto[:60]))
        r = _pedir(base, "GET", f"/api/execucoes/{exec_id}/eventos?desde={n}", stream=True)
        resto = _ler_eventos(r)
        r.close()
        seqs = [d["seq"] for _, d in resto]
        checar(seqs and seqs[0] == n + 1 and seqs == list(range(n + 1, n + 1 + len(seqs))) and resto[-1][0] in ("fim", "oferta"),
               f"reinscrever com desde={n}: do {n + 1} ao fim, sem repetir nem pular", seqs[:5])
        texto_reinscrito = "".join(tp_d[1].get("t", "") for tp_d in primeiros + resto if tp_d[0] == "token")
        checar(texto_reinscrito == "".join(PEDACOS), "o que chegou antes e depois forma o texto inteiro")
        situ = _pedir(base, "GET", f"/api/trabalhos/{t['id']}/execucao")
        checar((situ.get("execucao") or {}).get("id") == exec_id and situ["execucao"]["estado"] == "concluida",
               "a conversa sabe qual foi a execução dela")

        # parar interrompe só a própria
        a = _pedir(base, "POST", "/api/trabalhos", {"pedido": "A"})
        b = _pedir(base, "POST", "/api/trabalhos", {"pedido": "B"})
        criados += [a["id"], b["id"]]
        ra = _pedir(base, "POST", f"/api/trabalhos/{a['id']}/perguntar", {"pergunta": "qual a multa do contrato A?",
                                                                           "apenas": ["Contrato A.docx"]}, stream=True)
        rb = _pedir(base, "POST", f"/api/trabalhos/{b['id']}/perguntar", {"pergunta": "qual a multa do contrato A?",
                                                                           "apenas": ["Contrato A.docx"]}, stream=True)
        _ler_eventos(ra, ate=6)
        ra.close()
        rb.close()
        _pedir(base, "POST", f"/api/trabalhos/{a['id']}/parar", {})
        _esperar(lambda: _pedir(base, "GET", f"/api/trabalhos/{b['id']}").get("estado") == "concluido", 30)
        ca = _pedir(base, "GET", f"/api/trabalhos/{a['id']}")
        cb = _pedir(base, "GET", f"/api/trabalhos/{b['id']}")
        checar(ca["estado"] == "pausado" and cb["estado"] == "concluido"
               and cb["mensagens"][-1]["texto"] == "".join(PEDACOS).strip(),
               "parar a A para só a A; a B termina inteira", (ca["estado"], cb["estado"]))

        # chave desligada: o caminho de antes
        api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": False}
        c = _pedir(base, "POST", "/api/trabalhos", {"pedido": "sem chave"})
        criados.append(c["id"])
        r = _pedir(base, "POST", f"/api/trabalhos/{c['id']}/perguntar", {"pergunta": "qual a multa do contrato A?",
                                                                          "apenas": ["Contrato A.docx"]}, stream=True)
        evs = _ler_eventos(r)
        r.close()
        checar(evs and evs[0][0] != "execucao" and "execucao_id" not in evs[0][1] and evs[-1][0] in ("fim", "oferta"),
               "com a chave desligada, o gerador de antes", [e[0] for e in evs[:2]])
        api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True}
        test_tela(base, criados)
    finally:
        habilidade.executar = antes_exec
        api.estado.prefs.dados["conversa"] = antes_prefs
        for id_ in criados:
            try:
                _pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass


def test_tela(base: str, criados: list) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api

    a = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Conversa A do teste"})
    b = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Conversa B do teste"})
    criados += [a["id"], b["id"]]
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
        pag.wait_for_timeout(1500)
        texto_de = "() => [...document.querySelectorAll('#centro .resposta .texto')].map(e => e.textContent).join(' | ')"
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_timeout(500)
        pag.evaluate("() => { enviar({ texto: 'qual a multa do contrato A?', apenas: ['Contrato A.docx'] }); }")
        pag.wait_for_function("() => (document.querySelector('#centro .resposta .texto') || {}).textContent?.includes('palavra3')",
                              timeout=15000)
        pag.evaluate(f"() => abrirTrabalho('{b['id']}')")
        pag.wait_for_timeout(1500)
        titulo_b = pag.evaluate("() => document.getElementById('conversa-titulo').textContent")
        checar(titulo_b == b["titulo"], "com a A respondendo, a B aberta mantém o título dela", titulo_b)
        checar("palavra" not in pag.evaluate(texto_de), "e nenhum texto da A aparece na B")
        checar("Contrato A.docx" not in pag.evaluate("() => (document.getElementById('lat-trechos') || {}).textContent || ''"),
               "nem os trechos da A no painel da B")
        pag.wait_for_timeout(600)
        checar(pag.evaluate("() => document.getElementById('conversa-titulo').textContent") == b["titulo"],
               "o fim da A não troca o título da B")
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_function("() => document.querySelector('#centro .resposta .texto')?.textContent.includes('palavra23')",
                              timeout=20000)
        checar("palavra0" in pag.evaluate(texto_de) and "palavra23" in pag.evaluate(texto_de),
               "voltar à A mostra a resposta inteira (o que saiu antes e depois)")
        # recarregar no meio de outra resposta
        pag.evaluate("() => { enviar({ texto: 'e o foro?', apenas: ['Contrato A.docx'] }); }")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .resposta .texto')].pop()?.textContent.includes('palavra2')",
                              timeout=15000)
        pag.reload(wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .resposta .texto')].length >= 2 && "
                              "[...document.querySelectorAll('#centro .resposta .texto')].pop().textContent.includes('palavra23')",
                              timeout=20000)
        ultimo = pag.evaluate("() => [...document.querySelectorAll('#centro .resposta .texto')].pop().textContent")
        checar(ultimo.strip().startswith("palavra0") and "palavra23" in ultimo,
               "recarregar no meio: ao abrir, a resposta aparece do começo e termina ao vivo", ultimo[:60])
        pag.wait_for_timeout(1500)
        conv = _pedir(base, "GET", f"/api/trabalhos/{a['id']}")
        respostas = [m for m in conv["mensagens"] if m["autor"] == "paulus"]
        checar(len(respostas) == 2 and all(m["texto"] == "".join(PEDACOS).strip() for m in respostas),
               "as duas respostas ficaram inteiras na conversa", [m["texto"][:20] for m in respostas])
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  C1 — a resposta roda sem depender da janela")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-c1-{i}-")) for i in range(2)]
    try:
        test_modulo(pastas[0])
        test_interrompida(pastas[1])
        test_api()
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
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
