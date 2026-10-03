"""
F1 - a fila do modelo à vista, a pergunta que espera na conversa e o
Ctrl+Enter (src/fila_modelo.py, src/fila_de_todos.py, js/58-fila.js).

O modelo é o cliente de verdade (src/llama_client.py) com a rede trocada por
um Ollama de mentira em que o teste segura e solta cada chamada: assim a
fila de todas as telas passa pelo mesmo caminho do programa.

  - a ordem: pergunta na frente do segundo plano; "propria" troca só entre
    as perguntas da mesma pessoa; "geral" passa na frente de quem espera,
    nunca de quem já começou; duas por pessoa;
  - a segunda pergunta na mesma conversa vira "na fila", fica guardada (vale
    depois de recarregar), edita, cancela e vai sozinha na vez;
  - a terceira: mensagem clara, nada guardado;
  - Ctrl+Enter sem liberação: só na frente das próprias; com liberação:
    na frente de outra pessoa, com limite por hora, na auditoria, sem
    interromper quem está sendo atendido; quem foi passado vê o motivo;
  - o e-mail (outra tela) entra na mesma fila, com a origem, e a posição
    bate com a ordem real;
  - ninguém vê o texto da pergunta de outra pessoa; a fila inteira só na
    janela do escritório;
  - na tela (Edge): a bolha "na fila", depois de recarregar, e a dica do
    Ctrl+Enter.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_f1_fila.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-f1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import fila_modelo  # noqa: E402
from fila_modelo import FilaCheia, FilaDoModelo  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS") or (TMP / "capturas"))
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, segundos: float = 20.0) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.05)
    return False


# ------------------------------------------------------------------ a ordem

def test_ordem() -> None:
    print("\na ordem da fila")
    f = FilaDoModelo()
    a1 = f.entrar("local", origem="conversa", nome="Ana")
    f.esperar(a1, timeout=0)                     # Ana começou
    fundo = f.entrar("segundo plano", fundo=True, origem="segundo plano", nome="segundo plano")
    r1 = f.entrar("conta:2", origem="conversa", nome="Rui")
    checar(f._fila == [a1, r1, fundo], "pergunta passa na frente do segundo plano que espera")
    h1 = f.entrar("conta:3", origem="conversa", nome="Helena")
    r2 = f.entrar("conta:2", origem="editor", nome="Rui", prioridade="propria")
    checar(f._fila == [a1, r2, h1, r1, fundo], "“propria” troca só entre as do Rui: a Helena continua em 2º",
           [v.nome + v.origem for v in f._fila])
    try:
        f.entrar("conta:2", nome="Rui")
        checar(False, "a 3ª do Rui é recusada")
    except FilaCheia as exc:
        checar("duas perguntas" in str(exc), "a 3ª do Rui é recusada, com a razão", str(exc))
    h2 = f.entrar("conta:3", origem="conversa", nome="Helena", prioridade="geral")
    checar(f._fila[0] is a1 and f._fila[1] is h2, "“geral” vai logo depois de quem já começou — não interrompe a Ana")
    checar(r2.passado_por == "Helena" and r1.passado_por == "Helena" and not h1.passado_por,
           "quem foi passado sabe por quem (e a própria Helena não)")
    ev = f.para_evento(r1)
    checar(ev["motivo"] == "pergunta prioritária de Helena" and [x["nome"] for x in ev["na_frente"]] ==
           ["Ana", "Helena", "Rui", "Helena"], "o evento diz quem está na frente e o motivo", ev)
    checar(all(set(x) == {"nome", "origem", "respondendo"} for x in ev["na_frente"]),
           "na frente: só nome, origem e se está respondendo — nada de texto")
    checar(all("rotulo" not in x for x in f.foto()), "a foto da fila não leva rótulo nem texto")
    f.sair(a1)
    checar(f.esperar(h2, timeout=0) and fila_modelo.VEZ.get() is h2, "a vez chega e fica marcada na thread")
    f.sair(h2)
    checar(fila_modelo.VEZ.get() is None, "sair tira a marca")

    print("\na vez do cliente do modelo")
    fila_modelo.instalar(f, lambda: False)
    with fila_modelo.vez_para_o_modelo() as vez:
        checar(vez is None, "chave desligada: nem entra na fila")
    fila_modelo.instalar(f, lambda: True)
    for v in list(f._fila):
        f.sair(v)
    with fila_modelo.vez_para_o_modelo() as vez:
        checar(vez is not None and vez.fundo, "sem requisição: segundo plano")
        with fila_modelo.vez_para_o_modelo() as dentro:
            checar(dentro is None and len(f._fila) == 1, "quem já tem a vez não entra de novo")
    outro = f.entrar("conta:9", nome="Zé")
    f.esperar(outro, timeout=0)
    fila_modelo.VEZ.set(None)        # a vez do Zé é de outra thread
    try:
        with fila_modelo.vez_para_o_modelo(parar=lambda: True):
            checar(False, "parar enquanto espera")
    except fila_modelo.Parado:
        checar(len(f._fila) == 1, "parar enquanto espera tira da fila")
    f.sair(outro)
    fila_modelo.instalar(None, lambda: False)


# ----------------------------------------------------- o Ollama de mentira

class Chamada:
    def __init__(self, dados: dict) -> None:
        self.soltar = threading.Event()
        self.pedido = dict(fila_modelo.PEDIDO.get() or {})
        self.dados = dados
        self.texto = "Resposta de teste."


class Resposta:
    def __init__(self, chamada: Chamada, stream: bool) -> None:
        self.chamada, self.stream, self.status_code = chamada, stream, 200

    def raise_for_status(self) -> None:
        pass

    def _esperar(self) -> None:
        self.chamada.soltar.wait(60)

    def json(self) -> dict:
        self._esperar()
        return {"message": {"content": self.chamada.texto}, "prompt_eval_count": 10, "eval_count": 5, "done": True}

    def iter_lines(self, decode_unicode=True):
        self._esperar()
        yield json.dumps({"message": {"content": self.chamada.texto}})
        yield json.dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5})

    def close(self) -> None:
        pass


class OllamaDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[Chamada] = []
        self._trava = threading.Lock()

    def post(self, url, json=None, stream=False, timeout=None, **k):
        c = Chamada(json or {})
        with self._trava:
            self.chamadas.append(c)
        return Resposta(c, stream)

    def get(self, url, **k):
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": []})

    def soltar_todas(self) -> None:
        for c in list(self.chamadas):
            c.soltar.set()


def _eventos(linhas: list[str], tipo: str) -> list[dict]:
    saida, atual = [], ""
    for linha in linhas:
        if linha.startswith("event: "):
            atual = linha[7:].strip()
        elif linha.startswith("data: ") and atual == tipo:
            saida.append(json.loads(linha[6:]))
    return saida


# -------------------------------------------------------------- pela API

def test_api():
    print("\npela API")
    import requests

    import api
    import llama_client
    import segredos
    from fastapi.testclient import TestClient

    ollama = OllamaDeMentira()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.client = cliente
    api.estado.cliente_para = lambda tarefa, **k: cliente
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.check_ollama = lambda modelo: (True, "")
    api.estado.prefs.dados.setdefault("aparelho", {})["fila"] = True
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "locacao.txt").write_text("CONTRATO DE LOCAÇÃO. O aluguel é de R$ 6.200,00. O reajuste é pelo IGP-M.",
                                       encoding="utf-8")
    api.estado.recarregar()
    local = TestClient(api.app, headers=api.cabecalho_local())

    def em_thread(cli, tid, texto, prioridade=False):
        caixa = {"linhas": [], "status": 0}

        def rodar():
            with cli.stream("POST", f"/api/trabalhos/{tid}/perguntar",
                            json={"pergunta": texto, "prioridade": prioridade, "tudo": True}) as r:
                caixa["status"] = r.status_code
                for linha in r.iter_lines():
                    caixa["linhas"].append(linha)
        caixa["thread"] = threading.Thread(target=rodar, daemon=True)
        caixa["thread"].start()
        return caixa

    def chamadas(n):
        return esperar(lambda: len(ollama.chamadas) >= n)

    fila = api.estado.fila_modelo

    # ------------------------------------------------ a pergunta que espera
    print("  a segunda pergunta na mesma conversa")
    tid = local.post("/api/trabalhos", json={"pedido": "fila"}).json()["id"]
    q1 = em_thread(local, tid, "qual o valor do aluguel?")
    checar(chamadas(1) and ollama.chamadas[0].pedido.get("origem") == "conversa",
           "a primeira está sendo respondida (origem conversa)", [c.pedido for c in ollama.chamadas])
    r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "e o reajuste?", "tudo": True})
    checar(r.status_code == 202 and r.json()["pendente"]["texto"] == "e o reajuste?" and r.json()["pendente"]["posicao"] >= 1,
           "a segunda vira “na fila”, com a posição", r.text[:300])
    pid = r.json()["pendente"]["id"]
    t = local.get(f"/api/trabalhos/{tid}").json()
    checar([m["texto"] for m in t["mensagens"] if m["autor"] == "pessoa"] == ["qual o valor do aluguel?"]
           and "pendentes" not in (t.get("contexto") or {}), "ela não entra no histórico antes da vez, nem sai no trabalho")
    disco = json.loads(next((Path(os.environ["PAULUS_DADOS"]) / "trabalhos").glob(f"{tid}*.json")).read_text(encoding="utf-8"))
    checar([p["texto"] for p in disco["contexto"]["pendentes"]] == ["e o reajuste?"], "fica guardada no servidor, na conversa")
    recarregado = TestClient(api.app, headers=api.cabecalho_local())
    lista = recarregado.get(f"/api/trabalhos/{tid}/pendentes").json()["pendentes"]
    checar(len(lista) == 1 and lista[0]["estado"] == "na_fila", "depois de recarregar, continua lá", lista)
    r = local.put(f"/api/trabalhos/{tid}/pendentes/{pid}", json={"texto": "e o índice de reajuste?"})
    checar(r.status_code == 200 and r.json()["pendente"]["texto"] == "e o índice de reajuste?", "editar troca o texto na fila")
    antes = len(local.get(f"/api/trabalhos/{tid}").json()["mensagens"])
    r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "e a multa?", "tudo": True})
    checar(r.status_code == 429 and "duas perguntas" in r.json()["detail"], "a terceira: 429 com a razão", r.text[:200])
    checar(len(local.get(f"/api/trabalhos/{tid}/pendentes").json()["pendentes"]) == 1
           and len(local.get(f"/api/trabalhos/{tid}").json()["mensagens"]) == antes, "e nada foi guardado")

    ollama.chamadas[0].soltar.set()
    q1["thread"].join(20)
    checar(chamadas(2), "a primeira termina e a da fila vai sozinha")
    ollama.chamadas[1].soltar.set()
    checar(esperar(lambda: any(m["texto"] == "e o índice de reajuste?" for m in local.get(f"/api/trabalhos/{tid}").json()["mensagens"])
                   and not api.estado.respondendo.get(tid)),
           "a pergunta editada entrou na conversa e foi respondida")
    msgs = local.get(f"/api/trabalhos/{tid}").json()["mensagens"]
    checar(msgs[-1]["autor"] == "paulus" and "Resposta de teste" in msgs[-1]["texto"], "com a resposta dela", msgs[-1]["texto"][:80])
    checar(not local.get(f"/api/trabalhos/{tid}/pendentes").json()["pendentes"] and not fila.foto(), "a fila ficou vazia")

    print("  cancelar")
    q = em_thread(local, tid, "qual o prazo?")
    chamadas(3)
    r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "e a garantia?", "tudo": True})
    pid = r.json()["pendente"]["id"]
    checar(len(fila.foto()) == 2, "a pendente tem lugar de verdade na fila")
    checar(local.delete(f"/api/trabalhos/{tid}/pendentes/{pid}").status_code == 200
           and not local.get(f"/api/trabalhos/{tid}/pendentes").json()["pendentes"] and len(fila.foto()) == 1,
           "cancelar tira da conversa e da fila")
    ollama.chamadas[2].soltar.set()
    q["thread"].join(20)
    time.sleep(0.5)
    checar(len(ollama.chamadas) == 3, "a cancelada não foi ao modelo")

    # ------------------------------------------------------------ prioridade
    if not segredos.disponivel():
        print("  pulado: sem DPAPI, sem contas de fora")
        return
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False

    def entrar(nome, email, papel, niveis=None):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30)))
        if niveis:
            local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": niveis})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f, c["conta"]["id"]

    try:
        entrar("Mateus", "mateus@x.com", "titular")
        helena, hid = entrar("Helena Duarte", "helena@x.com", "colaborador", {"prioridade": "faz", "acervo": "ver"})
        rui, rid = entrar("Rui", "rui@x.com", "colaborador", {"acervo": "ver"})
        print("  Ctrl+Enter")
        n0 = len(ollama.chamadas)
        t_l = local.post("/api/trabalhos", json={"pedido": "l"}).json()["id"]
        t_h1 = helena.post("/api/trabalhos", json={"pedido": "h1"}).json()["id"]
        t_h2 = helena.post("/api/trabalhos", json={"pedido": "h2"}).json()["id"]
        t_r1 = rui.post("/api/trabalhos", json={"pedido": "r1"}).json()["id"]
        t_r2 = rui.post("/api/trabalhos", json={"pedido": "r2"}).json()["id"]
        L = em_thread(local, t_l, "pergunta do escritório")
        chamadas(n0 + 1)
        H1 = em_thread(helena, t_h1, "pergunta sigilosa da Helena")
        esperar(lambda: len(fila.foto()) == 2)
        R1 = em_thread(rui, t_r1, "pergunta do Rui")
        esperar(lambda: len(fila.foto()) == 3)
        R2 = em_thread(rui, t_r2, "pergunta urgente do Rui", prioridade=True)
        esperar(lambda: len(fila.foto()) == 4)
        ordem = [(v["nome"], v["prioridade"]) for v in fila.foto()]
        checar(ordem == [("Escritório", ""), ("Helena", ""), ("Rui", "propria"), ("Rui", "")],
               "sem liberação: o Rui passa só na frente da própria; a Helena continua em 2º", ordem)
        # A Helena já tem uma esperando: a segunda, com Ctrl+Enter e a liberação do titular.
        H2 = em_thread(helena, t_h2, "outra da Helena", prioridade=True)
        esperar(lambda: len(fila.foto()) == 5)
        ordem = [(v["nome"], v["prioridade"]) for v in fila.foto()]
        checar(ordem[0] == ("Escritório", "") and fila.foto()[0]["respondendo"] and ordem[1] == ("Helena", "geral"),
               "com liberação: a Helena passa na frente dos outros, e quem está sendo atendido continua", ordem)
        checar(rui.get(f"/api/trabalhos/{t_h1}/pendentes").status_code == 200, "(o Rui pede as pendentes da conversa da Helena)")
        checar(rui.get("/api/fila").status_code == 403, "a fila inteira não abre de fora")
        foto = local.get("/api/fila").json()["fila"]
        checar(len(foto) == 5 and all(set(v) >= {"nome", "origem"} and "texto" not in v for v in foto),
               "a janela do escritório vê a fila inteira, sem texto", foto[:2])
        acessos = [json.loads(l) for l in (Path(os.environ["PAULUS_DADOS"]) / "acesso" / "acessos.jsonl").read_text(encoding="utf-8").splitlines()]
        prios = [(a["pessoa"], a["alvo"]) for a in acessos if a["acao"] == "prioridade"]
        checar(any(p[0].startswith("Helena") and "da fila" in p[1] for p in prios)
               and any(p[0] == "Rui" and "próprias" in p[1] for p in prios), "toda prioridade vai para a auditoria", prios)

        pedido_helena = SimpleNamespace(scope={"state": {"paulus_pessoa": {"conta_id": hid, "nome": "Helena Duarte",
                                                                           "permissoes": {"prioridade": "faz"}}}})
        import fila_de_todos

        tipos = [fila_de_todos.decidir_prioridade(api.estado, pedido_helena, f"conta:{hid}", True)["tipo"] for _ in range(3)]
        checar(tipos == ["geral", "geral", "propria"], "o limite por hora: a 4ª da hora vai só entre as próprias", tipos)

        print("  o e-mail entra na mesma fila")
        caixa = {}
        r3 = helena.post("/api/email/reescrever", json={"pedido": "mais formal", "corpo": "Oi"})
        checar(r3.status_code == 429 and "duas perguntas" in r3.json()["detail"],
               "a Helena, com duas na fila, não manda a 3ª nem pelo e-mail: o limite vale em todas as telas", r3.text[:160])
        th = threading.Thread(target=lambda: caixa.update(r=local.post("/api/email/reescrever",
                                                                         json={"pedido": "mais formal", "corpo": "Oi"})), daemon=True)
        th.start()
        esperar(lambda: len(fila.foto()) == 6)
        foto = fila.foto()
        checar(foto[-1]["nome"] == "Escritório" and foto[-1]["origem"] == "e-mail",
               "o pedido do e-mail está na fila, com a origem, no fim", [(v["nome"], v["origem"]) for v in foto])

        print("  a ordem em que o modelo atendeu")
        todas = [L, H1, H2, R1, R2]
        fim = time.time() + 90
        while time.time() < fim and (any(x["thread"].is_alive() for x in todas) or th.is_alive()):
            ollama.soltar_todas()
            time.sleep(0.2)
        atendidos = [(c.pedido.get("nome"), c.pedido.get("origem")) for c in ollama.chamadas[n0:]]
        checar(atendidos == [("Escritório", "conversa"), ("Helena", "conversa"), ("Helena", "conversa"), ("Rui", "conversa"),
                             ("Rui", "conversa"), ("Escritório", "e-mail")],
               "a ordem real bate com a fila mostrada: escritório, Helena (prioridade), Helena, Rui (própria), Rui, e-mail",
               atendidos)
        # Os eventos chegam inteiros no fim (o cliente de teste junta o stream).
        avisos = [e.get("aviso") for e in _eventos(R2["linhas"], "fila") if e.get("aviso")]
        checar(avisos and "depende do titular" in avisos[0], "o Rui lê por que foi só entre as dele, numa linha", avisos[:1])
        checar(any(e.get("motivo") == "pergunta prioritária de Helena" for e in _eventos(R1["linhas"], "fila")),
               "o Rui vê a posição mudar, com o motivo")
        vistos = " ".join(R1["linhas"] + R2["linhas"])
        checar(_eventos(R1["linhas"], "fila") and "sigilosa" not in vistos and "outra da Helena" not in vistos
               and "pergunta do escritório" not in vistos, "nos eventos do Rui, nenhum texto das perguntas dos outros")
        ultima_h2 = helena.get(f"/api/trabalhos/{t_h2}").json()["mensagens"]
        checar(ultima_h2 and ultima_h2[-1]["autor"] == "paulus", "e todas terminaram com resposta")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
        ollama.soltar_todas()
    return ollama


# ------------------------------------------------------------ na tela

def test_tela(ollama) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    CAPTURAS.mkdir(parents=True, exist_ok=True)
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        ctx.set_default_timeout(30000)
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof enfileirarNaConversa === 'function' && typeof acessoDeFora !== 'undefined'")
        pag.wait_for_timeout(1500)
        checar(pag.evaluate("() => filaLigada()"), "a tela sabe que a fila está ligada")
        n0 = len(ollama.chamadas)
        pag.fill("#pedido", "qual o valor do aluguel?")
        pag.press("#pedido", "Enter")
        esperar(lambda: len(ollama.chamadas) > n0, 20)
        pag.wait_for_timeout(600)
        checar(pag.evaluate("() => !document.getElementById('dica-prioridade').hidden"),
               "com uma resposta andando, a dica do Ctrl+Enter aparece")
        pag.fill("#pedido", "e o reajuste?")
        pag.press("#pedido", "Enter")
        pag.wait_for_selector(".fila-pendente .bolha-pessoa.na-fila", timeout=10000)
        linha = pag.inner_text(".fila-pendente-linha small")
        checar("na fila" in linha and pag.input_value("#pedido") == "", "a segunda vira a bolha “na fila”, e o campo esvazia", linha)
        pag.screenshot(path=str(CAPTURAS / "f1-na-fila.png"))
        tid = pag.evaluate("() => estado.trabalhoId")
        pag.reload(wait_until="load")
        pag.wait_for_function("() => typeof abrirTrabalho === 'function'")
        pag.wait_for_timeout(1200)
        pag.evaluate(f"() => abrirTrabalho({tid!r})")
        pag.wait_for_selector(".fila-pendente .bolha-pessoa.na-fila", timeout=10000)
        checar("e o reajuste?" in pag.inner_text(".fila-pendente"), "depois de recarregar, a bolha continua")
        ollama.soltar_todas()
        esperar(lambda: len(ollama.chamadas) >= n0 + 2, 20)
        ollama.soltar_todas()
        ok = False
        try:
            pag.wait_for_function("() => !document.querySelector('.fila-pendente') && "
                                  "[...document.querySelectorAll('.bolha-pessoa')].some(b => b.textContent === 'e o reajuste?')",
                                  timeout=20000)
            ok = True
        except Exception:  # noqa: BLE001
            pass
        checar(ok, "ela vai sozinha e entra na conversa")
        pag.screenshot(path=str(CAPTURAS / "f1-depois.png"))
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  F1 — a fila do modelo à vista")
    print("=" * 55)
    test_ordem()
    ollama = test_api()
    if ollama is not None:
        test_tela(ollama)
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
