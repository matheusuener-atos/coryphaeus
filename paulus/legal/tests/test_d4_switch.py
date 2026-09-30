"""
D4 - o switch e a tela (src/aparelho.py, js/61-aparelho-tela.js).

  - a conta do Automático: com a fila do escritório vazia e o aparelho lento,
    o escritório; com a fila cheia e o aparelho rápido, o aparelho; sem
    medida, o escritório; o limite da janela de sugestão (30 s ou 2 na frente);
  - pela API: conta sem liberação não tem sugestão; acima do limite, sugere;
    abaixo, não; caso "só no escritório" nunca sugere; a pergunta que vai ao
    aparelho não entra na fila do escritório (a fila cheia não a segura); a
    resposta diz onde foi escrita e por quê, inclusive a escolha da pessoa;
  - no Edge, entrando como conta de fora, com o motor falso: conta sem
    liberação não vê o seletor; o teste de capacidade faz o seletor
    aparecer; o Automático decide pela fila de agora; a janela de sugestão
    aparece acima do limite, não abaixo, nunca no caso só no escritório, e
    "não sugerir hoje" some até o dia seguinte; "Usar este aparelho" mostra o
    aviso da primeira vez, escreve no aparelho sem passar pela fila e a
    resposta diz onde foi escrita; nada da conversa fica no navegador;
    "apagar o modelo" tira os pesos e o seletor.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d4_switch.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-d4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
OLLAMA = TMP / "ollama"
os.environ["OLLAMA_MODELS"] = str(OLLAMA)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import fila_modelo  # noqa: E402

_falhas: list[str] = []
PESO = b"GGUF-falso-do-teste-d4-" * 512
PERGUNTA = "qual o prazo de aviso ao locador na cláusula de obrigações?"


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


class Resposta:
    status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"message": {"content": "Escrita no escritório."}, "done": True}

    def iter_lines(self, decode_unicode=True):
        yield json.dumps({"message": {"content": "Escrita no escritório."}})
        yield json.dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5})

    def close(self) -> None:
        pass


class Ollama:
    def __init__(self) -> None:
        self.chamadas: list[dict] = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        self.chamadas.append(json or {})
        return Resposta()

    def get(self, url, **k):
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": []})


def ollama_falso() -> str:
    sha = hashlib.sha256(PESO).hexdigest()
    (OLLAMA / "blobs").mkdir(parents=True, exist_ok=True)
    (OLLAMA / "blobs" / f"sha256-{sha}").write_bytes(PESO)
    man = OLLAMA / "manifests" / "registry.ollama.ai" / "library" / "teste" / "1b"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:" + sha}]}),
                   encoding="utf-8")
    return sha


def _cortar(arquivo, destino):
    destino.mkdir(parents=True, exist_ok=True)
    dados = Path(arquivo).read_bytes()
    metade = len(dados) // 2
    saida = []
    for i, pedaco in enumerate((dados[:metade], dados[metade:]), 1):
        alvo = destino / f"modelo-0000{i}-of-00002.gguf"
        alvo.write_bytes(pedaco)
        saida.append(alvo)
    return saida


# ------------------------------------------------------------ a conta

def test_conta() -> None:
    print("\na conta do Automático e o limite")
    import aparelho

    vazia = {"na_frente": 0, "espera_s": 0, "resposta_s": 60}
    cheia = {"na_frente": 3, "espera_s": 170, "resposta_s": 60}
    lento = aparelho.tempo_no_aparelho({"tokens_por_segundo": 3.5, "leitura_tps": 35}, carregado=True, baixado=True, bytes_do_modelo=0)
    rapido = aparelho.tempo_no_aparelho({"tokens_por_segundo": 40, "leitura_tps": 400}, carregado=True, baixado=True, bytes_do_modelo=0)
    checar(aparelho.decidir(vazia, lento) == "escritorio", f"fila vazia, aparelho lento (~{lento} s): o escritório")
    checar(aparelho.decidir(cheia, rapido) == "aparelho", f"fila cheia, aparelho rápido (~{rapido} s): o aparelho")
    checar(aparelho.decidir(cheia, None) == "escritorio", "sem a medida do aparelho: o escritório")
    frio = aparelho.tempo_no_aparelho({"tokens_por_segundo": 40, "leitura_tps": 400, "carregou_s": 20}, carregado=False,
                                      baixado=False, bytes_do_modelo=2 * 1024 ** 3)
    checar(frio > rapido + 200, "modelo por carregar e por baixar entra na conta", (rapido, frio))
    checar(aparelho.acima_do_limite({"na_frente": 1, "espera_s": 31}) and aparelho.acima_do_limite({"na_frente": 2, "espera_s": 0})
           and not aparelho.acima_do_limite({"na_frente": 1, "espera_s": 20}), "o limite: mais de 30 s, ou 2 na frente")
    f = fila_modelo.FilaDoModelo(segundos_por_resposta=lambda: 60)
    checar(f.espera_de_quem_chega() == (0, 0), "fila vazia: ninguém na frente, sem espera")
    a = f.entrar("conta:1", nome="Ana")
    f.esperar(a, timeout=0.1)
    f.entrar("conta:2", nome="Rui")
    n, s = f.espera_de_quem_chega()
    checar(n == 2 and 60 <= s <= 120, "com uma respondendo e uma esperando: 2 na frente, ~2 respostas", (n, s))


# ------------------------------------------------------------ pela API

class Montagem:
    pass


def montar(api) -> Montagem | None:
    import requests

    import aparelho_motor
    import llama_client
    import segredos
    from fastapi.testclient import TestClient

    if not segredos.disponivel():
        print("  pulado: sem DPAPI, sem contas de fora")
        return None
    from acesso.contas import codigo_totp

    m = Montagem()
    m.ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=m.ollama.post, get=m.ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.estado.prefs.dados.setdefault("ia", {}).update({"denso": False})
    api.estado.prefs.dados.setdefault("aparelho", {}).update({"ligado": True, "modelo": "teste:1b"})
    m.sha = ollama_falso()
    aparelho_motor.dividir = _cortar
    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    m.local = TestClient(api.app, headers=api.cabecalho_local())

    def entrar(nome, email, papel, niveis=None):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30)))
        if niveis:
            m.local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": niveis})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2",
                                                                            "User-Agent": "Teste/" + nome})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    def cad(nome, email, tipo="colaborador"):
        return m.local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "email": email}}).json()["id"]

    entrar("Mateus", "mateus@x.com", "titular")
    m.helena = entrar("Helena", "helena@x.com", "colaborador", {"aparelho": "faz", "servicos": "faz", "acervo": "ver"})
    m.rui = entrar("Rui", "rui@x.com", "colaborador", {"servicos": "faz", "acervo": "ver"})
    api.estado.client = cliente
    api.estado.cliente_para = lambda tarefa: cliente
    api.check_ollama = lambda modelo: (True, "")
    mateus, h, r_ = cad("Mateus", "mateus@x.com", "socio"), cad("Helena", "helena@x.com"), cad("Rui", "rui@x.com")
    m.servico = m.local.post("/api/servicos", json={"id": None, "dados": {"nome": "Locação da Clínica",
                                                                         "equipe": [mateus, h, r_]}}).json()["id"]
    clausulas = "\n\n".join(f"Cláusula de obrigações {i}. O locatário cumpre a obrigação do contrato de locação e dá aviso "
                            "por escrito ao locador, no prazo combinado entre as partes." for i in range(1, 120))
    (api.estado.servicos.pasta_de(m.servico, criar=True) / "contrato-clinica.txt").write_text(
        "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\n" + clausulas, encoding="utf-8")
    api.estado.recarregar()
    return m


def _encher_fila(api, n=3) -> list:
    vezes = [api.estado.fila_modelo.entrar(f"conta:{900 + i}", origem="conversa", nome=f"Pessoa{i}") for i in range(n)]
    api.estado.fila_modelo.esperar(vezes[0], timeout=0.1)
    return vezes


def _esvaziar(api, vezes) -> None:
    for v in vezes:
        api.estado.fila_modelo.sair(v)


def test_api(api, m: Montagem) -> None:
    print("\npela API, com contas de fora")
    import aparelho

    execs = Path(os.environ["PAULUS_DADOS"]) / "execucoes"
    rapido = {"tokens_por_segundo": 40, "leitura_tps": 400, "carregou_s": 1, "carregado": True, "baixado": True}
    s = m.rui.post("/api/aparelho/sugestao", json=rapido).json()
    checar(not s["pode"] and not s["sugerir"] and "não liberou" in s["motivo"], "conta sem liberação: sem sugestão", s)
    s = m.helena.post("/api/aparelho/sugestao", json=rapido).json()
    checar(s["pode"] and not s["sugerir"] and s["escritorio"]["na_frente"] == 0, "fila vazia: não sugere", s)
    checar(m.helena.post("/api/aparelho/sugestao", json={"navegador": "Edge"}).status_code == 422,
           "a sugestão aceita só o escopo e números")
    vezes = _encher_fila(api)
    try:
        s = m.helena.post("/api/aparelho/sugestao", json=rapido).json()
        checar(s["sugerir"] and s["escritorio"]["na_frente"] == 3 and s["automatico"] == "aparelho",
               "fila acima do limite: sugere, e o Automático escolhe o aparelho rápido", s)
        lento = dict(rapido, tokens_por_segundo=1.0, leitura_tps=5)
        checar(m.helena.post("/api/aparelho/sugestao", json=lento).json()["automatico"] == "escritorio",
               "com a fila cheia e o aparelho muito lento: o escritório")
        aparelho.so_no_escritorio().guardar([{"tipo": "servico", "valor": m.servico}])
        s = m.helena.post("/api/aparelho/sugestao", json=dict(rapido, apenas=["contrato-clinica.txt"])).json()
        checar(not s["sugerir"] and not s["vai_ao_aparelho"] and "só no escritório" in s["motivo_do_escritorio"],
               "conversa num caso só no escritório: nunca sugere", s)
        aparelho.so_no_escritorio().guardar([])

        print("  a pergunta que vai ao aparelho não entra na fila do escritório")
        tid = m.helena.post("/api/trabalhos", json={"pedido": "d4"}).json()["id"]
        caixa = {}
        t = threading.Thread(target=lambda: caixa.update(r=m.helena.post(f"/api/trabalhos/{tid}/perguntar",
                                                                         json={"pergunta": PERGUNTA, "aparelho": True})),
                             daemon=True)
        t.start()
        chegou = esperar(lambda: _evento(execs, tid, "aparelho") is not None, 30)
        checar(chegou and not any(v["nome"] == "Helena" for v in api.estado.fila_modelo.foto()),
               "com 3 na fila, o pacote sai sem esperar a vez, e a Helena nunca aparece na fila")
        if chegou:
            ev = _evento(execs, tid, "aparelho")
            m.helena.get(f"/api/aparelho/pacote/{ev['pacote']}", params={"assinatura": ev["assinatura"]})
            m.helena.post(f"/api/aparelho/pacote/{ev['pacote']}/devolver",
                          json={"assinatura": ev["assinatura"], "texto": "O aviso ao locador é por escrito [T1]."})
        t.join(30)
        esperar(lambda: not api.estado.respondendo.get(tid), 30)
        msg = m.helena.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
        esc = msg.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(esc.get("onde") == "aparelho" and esc.get("conferida") and esc.get("modelo") == "teste:1b"
               and "aviso ao locador" in msg["texto"], "a resposta diz: escrita no aparelho, o modelo, conferida", esc)
    finally:
        _esvaziar(api, vezes)

    print("  a escolha da pessoa fica dita")
    tid = m.helena.post("/api/trabalhos", json={"pedido": "d4"}).json()["id"]
    m.helena.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": PERGUNTA, "escolha": "fila"})
    esperar(lambda: not api.estado.respondendo.get(tid), 30)
    msg = m.helena.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
    esc = msg.get("cobertura", {}).get("como", {}).get("escrita", {})
    checar(esc.get("onde") == "escritorio" and esc.get("motivo") == "você escolheu esperar na fila", "“esperar na fila”", esc)
    tid = m.helena.post("/api/trabalhos", json={"pedido": "d4"}).json()["id"]
    m.helena.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": PERGUNTA})
    esperar(lambda: not api.estado.respondendo.get(tid), 30)
    msg = m.helena.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
    checar("escrita" not in msg.get("cobertura", {}).get("como", {}), "sem o seletor, a resposta não fala de aparelho")


def _evento(execs: Path, conversa: str, tipo: str) -> dict | None:
    for f in execs.glob("*.jsonl"):
        linhas = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        if linhas and linhas[0].get("conversa_id") == conversa:
            for x in linhas:
                if x["tipo"] == tipo:
                    return x["dados"]
    return None


# ------------------------------------------------------------ no navegador

def test_navegador(api, m: Montagem) -> None:
    print("\nno Edge, como conta de fora, com o motor falso")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import aparelho
    from test_gravacoes import _porta_livre, _subir_servidor

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"

    def contexto(nav, cli):
        ctx = nav.new_context(viewport={"width": 1280, "height": 860})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        ctx.add_cookies([{"name": "paulus_sessao", "value": cli.cookies.get("paulus_sessao"), "url": base}])
        pag = ctx.new_page()
        erros = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/", wait_until="load")
        pag.wait_for_function("() => typeof aparelhoTela === 'object' && aparelhoTela.estado !== null", timeout=20000)
        return ctx, pag, erros

    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return

        print("  conta sem liberação")
        ctx, pag, erros = contexto(nav, m.rui)
        pag.evaluate("() => { guardarPrefsDoAparelho({ teste: { passou: true, tokens_por_segundo: 40 } }); desenharSeletorDoAparelho(); }")
        checar(pag.evaluate("() => { const s = document.getElementById('aparelho-onde'); return !s || s.hidden; }"),
               "conta sem liberação não vê o seletor (nem com um teste guardado)")
        checar(not erros, "nenhum erro de JavaScript (Rui)", erros[:3])
        ctx.close()

        ctx, pag, erros = contexto(nav, m.helena)
        checar(pag.evaluate("() => aparelhoTela.estado.pode === true && !aparelhoDisponivel()"),
               "conta liberada, sem o teste neste aparelho: o seletor ainda não aparece")
        t = pag.evaluate("async () => { motorAparelho.falso = true; motorAparelho.falsoTps = 3.5; return await fazerTesteDoAparelho(); }")
        checar(t.get("passou") and t.get("tokens_por_segundo") == 3.5 and t.get("sha") == m.sha, "o teste de capacidade passa", t)
        checar(pag.is_visible("#aparelho-onde"), "depois do teste, o seletor aparece na caixa da pergunta")
        devagar = pag.evaluate("async () => { motorAparelho.falsoTps = 1; const t = await fazerTesteDoAparelho(); motorAparelho.falsoTps = 3.5;"
                               " return [t, document.getElementById('aparelho-onde').hidden]; }")
        checar(not devagar[0]["passou"] and "devagar" in devagar[0]["motivo"] and devagar[1],
               "aparelho devagar demais: não passa, com o motivo, e o seletor some", devagar[0])
        pag.evaluate("async () => { await fazerTesteDoAparelho(); }")

        print("  Automático")
        pag.evaluate("() => guardarPrefsDoAparelho({ modo: 'automatico', entendi: true })")
        r = pag.evaluate("async () => await ondeEscrever({}, { apenas: [] })")
        checar(r == {"escolha": "automatico"}, "fila vazia e aparelho lento: o escritório", r)
        vezes = _encher_fila(api)
        try:
            pag.evaluate("() => guardarPrefsDoAparelho({ teste: Object.assign(prefsDoAparelho().teste, { tokens_por_segundo: 40, leitura_tps: 400 }) })")
            r = pag.evaluate("async () => await ondeEscrever({}, { apenas: [] })")
            checar(r == {"aparelho": True, "escolha": "automatico"}, "fila cheia e aparelho rápido: o aparelho", r)

            print("  a janela de sugestão")
            pag.evaluate("() => guardarPrefsDoAparelho({ modo: 'escritorio' })")
            pag.evaluate("() => { window._r = null; ondeEscrever({}, { apenas: [] }).then((r) => { window._r = r; }); }")
            pag.wait_for_selector("#aparelho-sugestao", timeout=10000)
            texto = pag.inner_text("#aparelho-sugestao")
            checar("3 na sua frente" in texto and "Usar este aparelho" in texto and "Esperar na fila" in texto
                   and "Não sugerir de novo hoje" in texto, "acima do limite, a janela aparece, com os três botões", texto)
            pag.click("[data-sugestao='hoje']")
            pag.wait_for_function("() => window._r !== null")
            checar(pag.evaluate("() => window._r") == {"escolha": "fila"} and not pag.is_visible("#aparelho-sugestao"),
                   "“não sugerir hoje”: a pergunta vai para a fila e a janela fecha")
            r = pag.evaluate("async () => await ondeEscrever({}, { apenas: [] })")
            checar(r == {"escolha": "escritorio"} and not pag.is_visible("#aparelho-sugestao"), "no mesmo dia, não sugere de novo", r)
            pag.evaluate("() => guardarPrefsDoAparelho({ semSugestaoAte: '2000-01-01' })")
            pag.evaluate("() => { window._r = null; ondeEscrever({}, { apenas: [] }).then((r) => { window._r = r; }); }")
            pag.wait_for_selector("#aparelho-sugestao", timeout=10000)
            pag.click("[data-sugestao='fila']")
            pag.wait_for_function("() => window._r !== null")
            checar(pag.evaluate("() => window._r") == {"escolha": "fila"}, "no dia seguinte, sugere de novo; “esperar na fila”")
            aparelho.so_no_escritorio().guardar([{"tipo": "servico", "valor": m.servico}])
            r = pag.evaluate("async () => await ondeEscrever({}, { apenas: ['contrato-clinica.txt'] })")
            checar(r == {"escolha": "caso"} and not pag.is_visible("#aparelho-sugestao"),
                   "conversa num caso só no escritório: nenhuma janela", r)
            aparelho.so_no_escritorio().guardar([])

            print("  “Usar este aparelho”, pela caixa da pergunta")
            pag.evaluate("() => guardarPrefsDoAparelho({ entendi: false })")
            n0 = len(m.ollama.chamadas)
            pag.fill("#pedido", PERGUNTA)
            pag.press("#pedido", "Enter")
            pag.wait_for_selector("#aparelho-sugestao", timeout=15000)
            pag.screenshot(path=str(TMP / "d4-sugestao.png"))
            pag.click("[data-sugestao='aparelho']")
            pag.wait_for_selector("text=O que não dá para garantir", timeout=10000)
            aviso = pag.inner_text(".aparelho-aviso")
            checar("só o modelo" in aviso and "vírus" in aviso and "não o elimina" in aviso,
                   "primeira vez: o aviso diz o que fica aqui e o que não dá para garantir")
            pag.get_by_role("button", name="Entendi").click()
            pag.wait_for_selector(".resposta .assinatura", timeout=40000)
            assinatura = pag.inner_text(".resposta .assinatura")
            resposta = pag.inner_text(".resposta .texto")
            checar("Texto escrito pelo motor falso." in resposta and "neste aparelho" in assinatura,
                   "a resposta foi escrita aqui, e a assinatura diz", (resposta[:80], assinatura))
            checar(len(m.ollama.chamadas) == n0, "o modelo do escritório não foi chamado, com a fila cheia")
            checar(pag.evaluate("() => prefsDoAparelho().entendi === true"), "o “entendi” fica guardado")
            pag.wait_for_function("() => document.getElementById('lat-como-lista') && /Escrita/.test(document.getElementById('lat-como-lista').textContent)",
                                  timeout=15000)
            painel = pag.inner_text("#lat-como-lista")
            pag.screenshot(path=str(TMP / "d4-resposta.png"))
            pag.set_viewport_size({"width": 400, "height": 820})
            pag.wait_for_timeout(300)
            pag.screenshot(path=str(TMP / "d4-celular.png"))
            checar(pag.evaluate("() => document.documentElement.scrollWidth <= 400"), "na largura de celular, nada passa da tela")
            pag.set_viewport_size({"width": 1280, "height": 860})
            print(f"  (fotos em {TMP})")
            checar("escrita neste aparelho · teste:1b · conferida no escritório" in painel,
                   "o painel “Sobre esta resposta” diz onde, com qual modelo e que foi conferida", painel)
        finally:
            _esvaziar(api, vezes)

        guardado = pag.evaluate("""async () => {
          const t = [];
          for (const k of Object.keys(localStorage)) t.push(k + '=' + localStorage.getItem(k));
          for (const k of Object.keys(sessionStorage)) t.push(k + '=' + sessionStorage.getItem(k));
          const bancos = indexedDB.databases ? (await indexedDB.databases()).map((b) => b.name) : [];
          return { texto: t.join('\\n'), bancos: bancos };
        }""")
        checar("locador" not in guardado["texto"] and "motor falso" not in guardado["texto"] and not guardado["bancos"],
               "nada da pergunta nem da resposta no armazenamento do navegador")

        print("  Minha conta › Este aparelho")
        pag.evaluate("() => { configuracoesDoAparelho(); }")
        pag.wait_for_selector("[data-aparelho-acao='apagar']", timeout=10000)
        painel = pag.inner_text(".aparelho-config")
        checar("passou" in painel and "teste:1b" in painel, "o painel mostra o teste e o modelo guardado", painel)
        pag.click("[data-aparelho-acao='apagar']")
        pag.wait_for_selector("text=Apaguei o modelo deste aparelho", timeout=10000)
        fim = pag.evaluate("async () => [(await caches.keys()).length, aparelhoDisponivel(), document.getElementById('aparelho-onde').hidden]")
        checar(fim == [0, False, True], "“apagar o modelo” tira os pesos, e o seletor some até o próximo teste", fim)
        checar(not erros, "nenhum erro de JavaScript (Helena)", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  D4 — o switch e a tela")
    print("=" * 55)
    test_conta()
    import api

    m = montar(api)
    if m is not None:
        test_api(api, m)
        test_navegador(api, m)
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
