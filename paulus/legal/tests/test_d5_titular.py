"""
D5 - o que o titular controla (src/aparelho.py, js/62-aparelho-titular.js).

  - ninguém liga o recurso de fora: nem o colaborador para si mesmo (a
    permissão, a chave, as marcas e o relatório), nem o titular pelo acesso
    de fora - tudo isso é da janela do escritório;
  - "só no escritório" por cliente, Serviço e pasta, conferido na hora de
    marcar e respeitado na montagem do pacote: a pergunta sobre um caso
    marcado vai ao escritório, com o motivo, mesmo com o switch ligado;
    marcar e tirar ficam na auditoria;
  - desligar no meio de uma resposta (para o escritório ou só para a conta)
    faz ela terminar no escritório, com o motivo, e o pacote não vale mais;
  - o relatório: por pessoa, quantas no aparelho, quantas refeitas pela
    conferência, quantas o escritório terminou;
  - na janela do escritório, o cartão "Escrever no aparelho" em Acesso de
    fora: o estado, as marcas (marcar e tirar) e o relatório.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d5_titular.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-d5-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["OLLAMA_MODELS"] = str(TMP / "ollama")
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
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


def _evento(execs: Path, conversa: str, tipo: str) -> dict | None:
    for f in execs.glob("*.jsonl"):
        linhas = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        if linhas and linhas[0].get("conversa_id") == conversa:
            for x in linhas:
                if x["tipo"] == tipo:
                    return x["dados"]
    return None


def main() -> int:
    print("=" * 55)
    print("  D5 — o que o titular controla")
    print("=" * 55)
    import requests

    import api
    import llama_client
    import segredos
    from fastapi.testclient import TestClient

    if not segredos.disponivel():
        print("  pulado: sem DPAPI, sem contas de fora")
        print("  todos os testes passaram")
        return 0
    from acesso.contas import codigo_totp

    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.estado.prefs.dados.setdefault("ia", {}).update({"denso": False})
    api.estado.prefs.dados.setdefault("aparelho", {}).update({"ligado": True})
    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())
    ids: dict[str, int] = {}

    def entrar(nome, email, papel, niveis=None):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        ids[nome] = c["conta"]["id"]
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30)))
        if niveis:
            local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": niveis})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2",
                                                                            "User-Agent": "Teste/" + nome})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    def cad(nome, email, tipo="colaborador"):
        return local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "email": email}}).json()["id"]

    niveis_helena = {"aparelho": "faz", "servicos": "faz", "acervo": "ver"}
    mateus = entrar("Mateus", "mateus@x.com", "titular")
    helena = entrar("Helena", "helena@x.com", "colaborador", niveis_helena)
    rui = entrar("Rui", "rui@x.com", "colaborador", {"servicos": "faz", "acervo": "ver"})
    api.estado.client = cliente
    api.estado.cliente_para = lambda tarefa: cliente
    api.check_ollama = lambda modelo: (True, "")
    m_, h, r_ = cad("Mateus", "mateus@x.com", "socio"), cad("Helena", "helena@x.com"), cad("Rui", "rui@x.com")
    clinica = cad("Clínica Boa Saúde", "clinica@x.com", "cliente")
    s1 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Locação da Clínica", "cadastro_id": clinica,
                                                                 "equipe": [m_, h, r_]}}).json()["id"]
    clausulas = "\n\n".join(f"Cláusula de obrigações {i}. O locatário cumpre a obrigação do contrato de locação e dá aviso "
                            "por escrito ao locador, no prazo combinado entre as partes." for i in range(1, 120))
    (api.estado.servicos.pasta_de(s1, criar=True) / "contrato-clinica.txt").write_text(
        "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\n" + clausulas, encoding="utf-8")
    api.estado.recarregar()
    execs = Path(os.environ["PAULUS_DADOS"]) / "execucoes"
    import aparelho

    # ---------------------------------------------------- ninguém de fora
    print("\nninguém liga de fora")
    marca = {"marcas": [{"tipo": "servico", "valor": s1}]}
    for quem, cli in (("o colaborador", rui), ("o titular de fora", mateus)):
        checar(cli.put(f"/api/acesso/contas/{ids['Rui']}/permissoes", json={"niveis": {"aparelho": "faz"}}).status_code == 403,
               f"{quem} não muda a permissão “aparelho”")
        checar(cli.post("/api/chaves", json={"bloco": "aparelho", "chave": "ligado", "ligada": True}).status_code == 403,
               f"{quem} não mexe na chave do escritório")
        checar(cli.put("/api/aparelho/so-no-escritorio", json=marca).status_code == 403
               and cli.get("/api/aparelho/so-no-escritorio").status_code == 403, f"{quem} não vê nem muda as marcas")
        checar(cli.get("/api/aparelho/relatorio").status_code == 403, f"{quem} não vê o relatório")
    checar(servico.contas.obter(ids["Rui"])["permissoes"].get("aparelho") == "nao", "e o Rui continua sem a liberação")

    # ---------------------------------------------------- só no escritório
    print("\nsó no escritório")
    checar(local.put("/api/aparelho/so-no-escritorio", json={"marcas": [{"tipo": "caso", "valor": 1}]}).status_code == 400,
           "tipo desconhecido: recusa")
    checar(local.put("/api/aparelho/so-no-escritorio", json={"marcas": [{"tipo": "servico", "valor": 9999}]}).status_code == 400,
           "Serviço que não existe: recusa")
    checar(local.put("/api/aparelho/so-no-escritorio", json={"marcas": [{"tipo": "pasta", "valor": "não-existe"}]}).status_code == 400,
           "pasta que não existe: recusa")
    r = local.put("/api/aparelho/so-no-escritorio", json={"marcas": [{"tipo": "cliente", "valor": clinica}]})
    checar(r.status_code == 200 and r.json()["marcas"] == [{"tipo": "cliente", "valor": clinica, "rotulo": "Clínica Boa Saúde"}],
           "marcar o cliente", r.json())
    g = local.get("/api/aparelho/so-no-escritorio").json()
    checar(any(c["nome"] == "Clínica Boa Saúde" for c in g["clientes"]) and any(s["nome"] == "Locação da Clínica" for s in g["servicos"]),
           "a janela do escritório lista clientes e Serviços para marcar")

    def perguntar(cli):
        tid = cli.post("/api/trabalhos", json={"pedido": "d5"}).json()["id"]
        caixa = {"tid": tid}
        caixa["t"] = threading.Thread(target=lambda: caixa.update(r=cli.post(f"/api/trabalhos/{tid}/perguntar",
                                                                             json={"pergunta": PERGUNTA, "aparelho": True})),
                                      daemon=True)
        caixa["t"].start()
        return caixa

    def fim(caixa, cli):
        caixa["t"].join(40)
        esperar(lambda: not api.estado.respondendo.get(caixa["tid"]), 40)
        m = cli.get(f"/api/trabalhos/{caixa['tid']}").json()["mensagens"]
        return (m[-1].get("cobertura") or {}).get("como", {}).get("escrita", {}) if m else {}

    c = perguntar(helena)
    esc = fim(c, helena)
    checar(_evento(execs, c["tid"], "aparelho") is None and esc.get("onde") == "escritorio"
           and "só no escritório" in esc.get("motivo", ""),
           "cliente marcado: o Serviço dele não sai - sem pacote, escrita no escritório, com o motivo", esc)
    local.put("/api/aparelho/so-no-escritorio", json={"marcas": [{"tipo": "servico", "valor": s1}]})
    c = perguntar(helena)
    esc = fim(c, helena)
    checar(_evento(execs, c["tid"], "aparelho") is None and "só no escritório" in esc.get("motivo", ""),
           "Serviço marcado: o mesmo", esc)
    local.put("/api/aparelho/so-no-escritorio", json={"marcas": []})

    def ate_o_pacote(cli):
        c = perguntar(cli)
        if not esperar(lambda: _evento(execs, c["tid"], "aparelho") is not None, 30):
            return c, None
        ev = _evento(execs, c["tid"], "aparelho")
        cli.get(f"/api/aparelho/pacote/{ev['pacote']}", params={"assinatura": ev["assinatura"]})
        return c, ev

    c, ev = ate_o_pacote(helena)
    checar(ev is not None, "sem marca: o pacote sai")
    if ev:
        helena.post(f"/api/aparelho/pacote/{ev['pacote']}/devolver", json={"assinatura": ev["assinatura"], "texto": "O aviso é por escrito."})
    checar(fim(c, helena).get("onde") == "aparelho", "e a resposta é escrita no aparelho")
    c, ev = ate_o_pacote(helena)
    if ev:
        helena.post(f"/api/aparelho/pacote/{ev['pacote']}/devolver", json={"assinatura": ev["assinatura"], "texto": "O prazo é de 99 dias."})
    checar(fim(c, helena).get("motivo") == "conferência reprovou", "número inventado: refeita no escritório")

    # ---------------------------------------------------- desligar no meio
    print("\ndesligar no meio de uma resposta")
    c, ev = ate_o_pacote(helena)
    if ev:
        helena.post(f"/api/aparelho/pacote/{ev['pacote']}/pedaco", json={"assinatura": ev["assinatura"], "texto": "O aviso"})
        local.post("/api/chaves", json={"bloco": "aparelho", "chave": "ligado", "ligada": False})
        esc = fim(c, helena)
        depois = helena.post(f"/api/aparelho/pacote/{ev['pacote']}/pedaco", json={"assinatura": ev["assinatura"], "texto": "O aviso é"})
        checar(esc.get("onde") == "escritorio" and esc.get("motivo") == "o escritório desligou a escrita no aparelho",
               "desligar para o escritório: a resposta termina aqui, com o motivo", esc)
        checar(depois.status_code == 410, "e o pacote não vale mais", depois.status_code)
    else:
        checar(False, "o pacote saiu para desligar no meio")
    local.post("/api/chaves", json={"bloco": "aparelho", "chave": "ligado", "ligada": True})
    c, ev = ate_o_pacote(helena)
    if ev:
        local.put(f"/api/acesso/contas/{ids['Helena']}/permissoes", json={"niveis": dict(niveis_helena, aparelho="nao")})
        r = helena.post(f"/api/aparelho/pacote/{ev['pacote']}/devolver", json={"assinatura": ev["assinatura"], "texto": "O aviso é por escrito."})
        esc = fim(c, helena)
        checar(r.status_code == 410 and esc.get("onde") == "escritorio"
               and esc.get("motivo") == "o titular desligou a escrita no aparelho para a sua conta",
               "tirar a liberação da conta no meio: devolver é recusado e a resposta termina aqui", (r.status_code, esc))
        local.put(f"/api/acesso/contas/{ids['Helena']}/permissoes", json={"niveis": niveis_helena})
    else:
        checar(False, "o pacote saiu para tirar a liberação no meio")

    # ---------------------------------------------------- relatório
    print("\no relatório")
    rel = local.get("/api/aparelho/relatorio").json()
    hel = next((p for p in rel["pessoas"] if p["pessoa"] == "Helena"), {})
    checar(hel.get("no_aparelho") == 1 and hel.get("refeitas") == 1 and hel.get("no_escritorio") == 2,
           "por pessoa: 1 no aparelho, 1 refeita, 2 terminadas no escritório", hel)
    acessos = [json.loads(x) for x in (Path(os.environ["PAULUS_DADOS"]) / "acesso" / "acessos.jsonl").read_text(encoding="utf-8").splitlines()]
    alvos = [a["alvo"] for a in acessos if a["acao"] == "aparelho"]
    checar(any(a.startswith("marcou só no escritório: Clínica Boa Saúde") for a in alvos)
           and any(a.startswith("tirou a marca só no escritório") for a in alvos), "marcar e tirar ficam na auditoria")

    # ---------------------------------------------------- a tela
    print("\na janela do escritório")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        sync_playwright = None
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        base = f"http://127.0.0.1:{porta}"
        pasta = Path(api.estado.pasta) / "Clientes" / "Fusão"
        pasta.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                ctx = nav.new_context(viewport={"width": 1280, "height": 900})
                ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag = ctx.new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarConfig === 'function' && typeof cartaoAparelhoTitular === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarConfig('acesso')")
                pag.wait_for_selector("#apt", timeout=15000)
                texto = pag.inner_text("#apt")
                checar("Para o escritório: ligado" in texto and "Liberadas: Helena" in texto and "Helena" in pag.inner_text(".apt-relatorio"),
                       "o cartão mostra o estado, quem está liberado e o relatório", texto[:200])
                pag.fill("#apt-pasta", "Clientes\\Fusão")
                pag.click("[data-apt-pasta]")
                pag.wait_for_selector(".apt-marca", timeout=10000)
                checar("Clientes\\Fusão" in pag.inner_text(".apt-marcas") and
                       any(m["tipo"] == "pasta" for m in aparelho.so_no_escritorio().marcas()), "marcar uma pasta pela tela")
                pag.locator("#apt").scroll_into_view_if_needed()
                pag.screenshot(path=str(TMP / "d5-cartao.png"))
                pag.click("[data-apt-tirar='0']")
                pag.wait_for_function("() => !document.querySelector('.apt-marca')", timeout=10000)
                checar(not aparelho.so_no_escritorio().marcas(), "tirar a marca pela tela")
                pag.click("[data-apt-ligar='0']")
                pag.wait_for_function("() => /Para o escritório: desligado/.test(document.getElementById('apt').textContent)", timeout=10000)
                checar(not api.estado.prefs.dados["aparelho"]["ligado"], "desligar pela tela desliga a chave")
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
