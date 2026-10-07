"""
V1-V7 - a nuvem vendida (docs/PLANO-NUVEM.md): o PAULUS (nuvem) pelo Worker,
o DeepInfra com a chave do escritório, o sim do titular, resumos e redação,
o plano e a recarga.

Tudo de mentira: o Worker de paulus.ia.br, o DeepInfra e o Ollama são
funções aqui (`nuvem.PEDIR`, `llama_client.requests`). Nada sai da máquina.
O Worker de verdade tem o próprio teste: node worker/teste-ia.mjs.

  - o termo: o que vai, para onde, a política do DeepInfra, o que nunca vai,
    "não anonimiza"; o sim com a versão errada é recusado; trocar de
    provedor pede outro sim; retirar desliga;
  - DeepInfra com chave própria: só os modelos de texto, o formato OpenAI com
    max_tokens;
  - o PAULUS (nuvem): ativar sem o Google recente pede o Google; ativar
    guarda o segredo cifrado; o sim vai ao Worker; a conversa vai sem pedir,
    com o sim do titular; a cota acabou volta ao computador e diz por quê;
    o plano, a assinatura e a recarga pela janela;
  - de fora: com o sim, a pergunta vai; com "pedir a cada envio", fica;
  - resumos e redação: o resumo do serviço vai à nuvem mascarado e volta com
    o CPF; o serviço só no escritório fica; a reescrita de e-mail e o parecer
    do Financeiro nunca vão; a funcionalidade desligada fica; a nuvem com
    erro volta ao local; o JSON pede o modo JSON;
  - as rotas novas: todas da janela, menos a situação da pílula.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_v_nuvem.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-v-nuvem-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
CPF = "529.982.247-25"
SEGREDO = "pia_" + "a1" * 12 + "_" + "b2" * 32


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, segundos: float = 30.0) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.05)
    return False


class Ollama:
    def __init__(self) -> None:
        self.pedidos: list[list[dict]] = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        self.pedidos.append((json or {}).get("messages") or [])
        texto = '{"ok": "local"}' if (json or {}).get("format") == "json" else "Escrita no escritório."

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": texto}, "done": True}

            def iter_lines(self, decode_unicode=True):
                yield __import__("json").dumps({"message": {"content": texto}})
                yield __import__("json").dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5})

            def close(self):
                pass
        return R()

    def get(self, url, **k):
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": []})


class Nuvem:
    """O Worker de paulus.ia.br e o DeepInfra de mentira."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.modo = "ok"  # "ok", "cota", "fora"
        self.consentimento = None
        self.pedacos = ["O resumo: o herdeiro, CPF [CP", "F 1], assinou."]

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": dict(cabecalhos or {}), "corpo": corpo})
        eu = self
        status, dados = 200, {}
        if self.modo == "fora":
            raise ConnectionError("sem internet")
        if url.endswith("/api/ia/ativar"):
            dados = {"segredo": SEGREDO, "conta": {"email": "dono@escritorio.com.br"}}
        elif url.endswith("/api/ia/consentimento"):
            self.consentimento = corpo
            dados = {"ok": True}
        elif url.endswith("/api/ia/conta"):
            dados = {"ok": True, "email": "dono@escritorio.com.br", "plano_vigente": True, "cortesia": False,
                     "assinatura": {"id": "pre1", "situacao": "authorized"}, "plano": {"valor": 300, "tokens": 30000000},
                     "recarga": {"valor": 50, "tokens": 10000000},
                     "ciclo": {"inicio": "2026-10-01T12:00:00Z", "fim": "2026-11-01T12:00:00Z", "tokens": 30000000, "usados": 1200},
                     "tokens": {"do_ciclo": 29998800, "da_recarga": 0, "reservados": 0, "restantes": 29998800, "hoje": 1200}}
        elif url.endswith("/api/ia/modelos"):
            dados = {"modelos": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"]}
        elif url.endswith("/api/ia/assinar"):
            dados = {"link": "https://paulus.ia.br/cadastro/pagamento/?plano=escritorio&periodo=mensal", "periodo": "mensal"}
        elif url.endswith("/api/ia/recarga"):
            dados = {"id": "ORD1", "valor": "50.00", "tokens": 10000000, "qr_code": "000201pix", "qr_code_base64": "", "vence_em_minutos": 30}
        elif "/api/ia/recarga/" in url:
            dados = {"id": "ORD1", "pago": True}
        elif url.endswith("/api/ia/sair"):
            dados = {"ok": True}
        elif url.endswith("/v1/openai/models"):
            dados = {"data": [{"id": "meta-llama/Llama-3.3-70B-Instruct"}, {"id": "Qwen/Qwen2.5-72B-Instruct"},
                              {"id": "black-forest-labs/FLUX-1-schnell"}, {"id": "BAAI/bge-m3"}]}
        elif url.endswith("/chat/completions"):
            if self.modo == "cota" and "paulus" in url:
                status, dados = 402, {"erro": "os tokens deste ciclo acabaram", "motivo": "cota"}
        pedacos = list(self.pedacos) if not (corpo or {}).get("response_format") else ['{"campo": "CPF [CPF 1]"}']

        class R:
            status_code = status

            def json(self):
                return dados

            def iter_lines(self, decode_unicode=True):
                for p in pedacos:
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 200}})
                yield "data: [DONE]"

            def close(self):
                pass
        del eu
        return R()

    def ultimas(self, trecho: str) -> list[dict]:
        return [c for c in self.chamadas if trecho in c["url"]]


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
    print("  V1-V7 — a nuvem vendida (PAULUS na nuvem)")
    print("=" * 55)
    import requests

    import api
    import aparelho
    import llama_client
    import nuvem
    import segredos
    from acesso import politicas
    from acesso import rotas as rotas_do_acesso
    from fastapi.testclient import TestClient

    fake = Nuvem()
    nuvem.PEDIR["fn"] = fake
    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "trechos", "denso": False})
    api.estado.client = cliente
    api.estado.modelo_para = lambda tarefa: "falso:1b"
    api.check_ollama = lambda *a, **k: (True, "")
    local = TestClient(api.app, headers=api.cabecalho_local())
    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return 0

    print("\no termo e o sim")
    e = local.get("/api/nuvem").json()
    checar(e["provedor"] == "paulus" and e["provedores"][0]["id"] == "paulus" and not e["consentido"] and not e["ligada"],
           "de fábrica: o PAULUS (nuvem) primeiro, sem o sim, desligada", {k: e[k] for k in ("provedor", "consentido", "ligada")})
    termo = local.get("/api/nuvem/termo?provedor=paulus").json()
    texto = " ".join(termo["texto"])
    checar(all(x in texto for x in ("O que vai", "DeepInfra", "Mistral AI", "França", "Anthropic", "30 dias", "Estados Unidos", "art. 33", "não grava em disco", "não isolamento técnico",
                                    "Nunca vai", "e-mail", "Drive", "só no escritório", "não anonimiza", "retirado")),
           "o termo diz o que vai, para onde, a política do provedor, o que nunca vai e como retirar")
    checar("créditos do plano" in texto and "não guarda o texto" in texto, "e que o portão só anota os créditos")
    outro = " ".join(local.get("/api/nuvem/termo?provedor=deepinfra").json()["texto"])
    checar("chave de API do escritório" in outro and "contrato é do escritório" in outro, "o termo da chave própria diz que o contrato é do escritório")
    r = local.post("/api/nuvem/consentimento", json={"aceito": True, "versao": "1999-01-01"})
    checar(r.status_code == 409, "o sim de uma versão antiga do termo é recusado", r.status_code)
    r = local.post("/api/nuvem/configurar", json={"ligado": True})
    checar(r.status_code == 400 and "sim" in r.json()["detail"], "sem o sim, não liga", r.json())

    print("\nDeepInfra com a chave do escritório")
    r = local.post("/api/nuvem/chave", json={"provedor": "deepinfra", "chave": "di-chave-de-mentira-0123456789abcdef"}).json()
    checar(r["modelos"] == ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"] and r["modelo"] == "meta-llama/Llama-3.3-70B-Instruct",
           "a lista só com os modelos de texto, e o Llama 3.3 70B escolhido", r.get("modelos"))
    local.post("/api/nuvem/consentimento", json={"aceito": True, "versao": termo["versao"]})
    checar(local.get("/api/nuvem").json()["consentido"], "o sim para o DeepInfra")
    pedacos: list[str] = []
    msgs = llama_client.montar_mensagens("qual a multa?", "[T1] A multa é de 10%.")
    uso = nuvem.chamar("deepinfra", "meta-llama/Llama-3.3-70B-Instruct", "di-chave", msgs, pedacos.append)
    c = fake.chamadas[-1]
    checar(c["url"] == "https://api.deepinfra.com/v1/openai/chat/completions" and c["corpo"]["max_tokens"] == nuvem.MAX_TOKENS and
           c["cabecalhos"]["Authorization"] == "Bearer di-chave" and uso == {"tokens_entrada": 1000, "tokens_saida": 200},
           "o formato OpenAI do DeepInfra, com o teto de saída e os tokens", c["corpo"].keys())
    checar("X-PAULUS-Versao" not in c["cabecalhos"], "a versão do PAULUS não vai a provedor de fora", c["cabecalhos"].keys())
    r = local.post("/api/nuvem/configurar", json={"provedor": "paulus"}).json()
    checar(not r["consentido"], "trocar de provedor pede outro sim (o termo diz para onde vai)")

    print("\no PAULUS (nuvem): ativar")
    api.estado.vinculo.id_token_valido = lambda margem=120: ""
    r = local.post("/api/nuvem/paulus/ativar")
    checar(r.status_code == 401 and "Google" in r.json()["detail"], "sem o login Google recente, pede o Google", r.json())
    api.estado.vinculo.id_token_valido = lambda margem=120: "id-token-de-mentira"
    r = local.post("/api/nuvem/paulus/ativar").json()
    ativar = fake.ultimas("/api/ia/ativar")[-1]
    arq = Path(os.environ["PAULUS_DADOS"]) / "nuvem" / "chave-paulus.dpapi"
    checar(ativar["corpo"]["id_token"] == "id-token-de-mentira" and "Authorization" not in ativar["cabecalhos"] and ativar["corpo"]["instalacao_id"],
           "ativar manda o id_token e o id da instalação, sem segredo", ativar["corpo"])
    checar(arq.exists() and SEGREDO not in arq.read_text(encoding="utf-8") and nuvem.chave(api.estado, "paulus") == SEGREDO,
           "o segredo da instalação fica cifrado (DPAPI)")
    checar(r["conta"]["tokens"]["restantes"] == 29998800 and r["provedor"] == "paulus", "a conta e o plano chegam na tela", r.get("conta", {}).get("tokens"))
    local.post("/api/nuvem/consentimento", json={"aceito": True, "versao": termo["versao"]})
    checar((fake.consentimento or {}).get("aceito") is True and fake.consentimento.get("versao") == termo["versao"],
           "o sim do titular também vai ao Worker", fake.consentimento)
    r = local.post("/api/nuvem/configurar", json={"ligado": True}).json()
    checar(r["ligada"] and not r["pedir_cada_envio"], "ligada, sem pedir a cada envio")
    situacao = local.get("/api/nuvem/situacao").json()
    niveis = situacao.pop("profundidade", {}).get("niveis") or []
    checar(situacao == {"ligada": True, "provedor": "paulus", "nome": "Paulus (nuvem)",
                        "modelo": "meta-llama/Llama-3.3-70B-Instruct", "pedir_cada_envio": False} and len(niveis) == 5,
           "a situação da pílula: só o necessário (e os níveis de profundidade)")

    print("\na conversa")
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "contrato-clinica.txt").write_text(
        "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\nCláusula 1. O locatário, CPF " + CPF + ", paga o aluguel até o dia 5.\n\n"
        "Cláusula 2. A multa por atraso no aluguel é de 10% sobre o valor devido.", encoding="utf-8")
    api.estado.recarregar()

    def perguntar(pergunta, h=None, marcar=True):
        h = h or local
        tid = h.post("/api/trabalhos", json={"pedido": "v"}).json()["id"]
        n0 = len(ollama.pedidos)
        saida = {}
        th = threading.Thread(target=lambda: saida.update(r=h.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": pergunta, "nuvem": marcar})), daemon=True)
        th.start()
        th.join(90)
        esperar(lambda: not api.estado.respondendo.get(tid))
        evs = eventos(saida["r"].text) if "r" in saida else []
        m = h.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
        return evs, m, len(ollama.pedidos) - n0

    n_pend = len(api.estado.fila.pendentes)
    n0 = len(fake.ultimas("/api/ia/v1/chat/completions"))
    evs, m, locais = perguntar("qual a multa por atraso no aluguel?")
    mandando = next((d for t, d in evs if t == "nuvem_mandando"), {})
    ida = fake.ultimas("/api/ia/v1/chat/completions")
    # Duas idas: a triagem da pergunta (src/triagem.py) e a resposta.
    checar(len(ida) == n0 + 2 and all(x["cabecalhos"]["Authorization"] == "Bearer " + SEGREDO and
                                      x["corpo"]["model"] == "meta-llama/Llama-3.3-70B-Instruct" for x in ida[n0:]),
           "a pergunta vai ao portão de paulus.ia.br com o segredo da instalação", len(ida) - n0)
    from versao import VERSAO
    checar(all(x["cabecalhos"].get("X-PAULUS-Versao") == VERSAO for x in ida[n0:]), "e com a versão do PAULUS (a lista de instalações da Minha conta)", ida[-1]["cabecalhos"].keys())
    checar(len(api.estado.fila.pendentes) == n_pend and "com o sim do titular" in mandando.get("como", ""), "sem pedido em Aprovações: vai com o sim do titular", mandando)
    enviado = json.dumps(ida[-1]["corpo"], ensure_ascii=False)
    checar(CPF not in enviado and "[CPF 1]" in enviado, "mascarado: o CPF não sai")
    checar(locais == 0 and CPF in (m.get("texto") or ""), "a resposta é da nuvem, com o CPF de volta", (m.get("texto") or "")[:120])
    lista = local.get("/api/nuvem/envios").json()["envios"]
    checar(lista and lista[0]["tarefa"] == "conversa" and lista[0]["tokens_entrada"] == 1000, "o registro anota a tarefa e os tokens", lista[:1])
    fake.modo = "cota"
    evs, m, locais = perguntar("qual a multa por atraso no aluguel?")
    fim = next((d for t, d in evs if t == "nuvem_fim"), {})
    checar(fim.get("onde") == "computador" and "tokens deste ciclo" in fim.get("motivo", "") and "recarga" in fim.get("motivo", "") and locais >= 1,
           "a cota acabou: o computador escreve, e diz por quê e onde recarregar", fim)
    fake.modo = "ok"

    print("\nde fora")
    p = {"conta_id": 7, "nome": "Colaboradora", "papel": "colaborador"}
    envio = nuvem.Envio(api.estado, SimpleNamespace(id="x", titulo="x", contexto={}), pessoa=p)
    hit = SimpleNamespace(chunk=SimpleNamespace(doc_path=str(pasta / "contrato-clinica.txt")), doc_name="contrato-clinica.txt")
    pacote = envio.preparar("qual a multa?", "[T1] A multa é de 10%.", "", [hit])
    checar(pacote is not None and not pacote["precisa_aprovar"], "de fora, com o sim do titular, a pergunta vai", envio.motivo)
    local.post("/api/nuvem/configurar", json={"pedir_cada_envio": True})
    envio = nuvem.Envio(api.estado, SimpleNamespace(id="x", titulo="x", contexto={}), pessoa=p)
    checar(envio.preparar("qual a multa?", "c", "", [hit]) is None and "computador do escritório" in envio.motivo,
           "de fora, pedindo o sim a cada envio, fica (o sim é da janela)", envio.motivo)
    local.post("/api/nuvem/configurar", json={"pedir_cada_envio": False})
    del rotas_do_acesso

    print("\nresumos e redação")
    sid = local.post("/api/servicos", json={"dados": {"nome": "Inventário Silva", "descricao": "Herdeiro CPF " + CPF}}).json().get("id")
    n0 = len(fake.ultimas("/api/ia/v1/chat/completions"))
    c = api.estado.cliente_para("resumos", servico=sid)
    checar(isinstance(c, nuvem.ClienteNuvem), "o resumo do serviço usa o cliente da nuvem", type(c).__name__)
    texto = c.ask("Resuma.", "Serviço: Inventário Silva. Herdeiro CPF " + CPF)
    ida = fake.ultimas("/api/ia/v1/chat/completions")
    checar(len(ida) == n0 + 1 and CPF not in json.dumps(ida[-1]["corpo"], ensure_ascii=False) and CPF in texto,
           "vai mascarado e volta com o CPF", texto)
    checar(local.get("/api/nuvem/envios").json()["envios"][0]["tarefa"] == "resumos", "o registro diz que foi um resumo")
    r = local.post(f"/api/servicos/{sid}/resumo")
    checar(r.status_code == 200 and len(fake.ultimas("/api/ia/v1/chat/completions")) == n0 + 2, "a rota do resumo do serviço passa pela nuvem", r.status_code)
    aparelho.so_no_escritorio().guardar([{"tipo": "servico", "valor": sid}])
    n1, l1 = len(fake.ultimas("/api/ia/v1/chat/completions")), len(ollama.pedidos)
    c = api.estado.cliente_para("resumos", servico=sid)
    c.ask("Resuma.", "Serviço sigiloso")
    checar(len(fake.ultimas("/api/ia/v1/chat/completions")) == n1 and len(ollama.pedidos) == l1 + 1 and "só no escritório" in c.ultima["nuvem"]["motivo"],
           "o serviço só no escritório é resumido neste computador", c.ultima)
    aparelho.so_no_escritorio().guardar([])
    checar(not isinstance(api.estado.cliente_para("redacao", local=True), nuvem.ClienteNuvem) and
           not isinstance(api.estado.cliente_para("email"), nuvem.ClienteNuvem) and not isinstance(api.estado.cliente_para("juiz"), nuvem.ClienteNuvem),
           "a reescrita de e-mail, o e-mail e o juiz nunca vão")
    fonte = (RAIZ / "src" / "api.py").read_text(encoding="utf-8")
    checar('correio.reescrever_email(estado.cliente_para("redacao", local=True)' in fonte and
           'estado.cliente_para("resumos", local=True).ask(relatorios.INSTRUCAO_PARECER' in fonte,
           "no código: a reescrita de e-mail e o parecer do Financeiro pedem o local")
    local.post("/api/nuvem/configurar", json={"tarefas": {"redacao": False}})
    checar(not isinstance(api.estado.cliente_para("redacao"), nuvem.ClienteNuvem) and isinstance(api.estado.cliente_para("resumos"), nuvem.ClienteNuvem),
           "a funcionalidade desligada fica aqui; as outras continuam")
    local.post("/api/nuvem/configurar", json={"tarefas": {"redacao": True}})
    c = api.estado.cliente_para("redacao")
    j = c.ask_json("Extraia.", "CPF " + CPF, schema_hint='{"campo": "..."}')
    ida = fake.ultimas("/api/ia/v1/chat/completions")[-1]
    checar(ida["corpo"].get("response_format") == {"type": "json_object"} and j == {"campo": "CPF " + CPF}, "o JSON pede o modo JSON e volta desmascarado", j)
    fake.modo = "fora"
    l1 = len(ollama.pedidos)
    c = api.estado.cliente_para("redacao")
    t = c.ask("Reescreva.", "texto")
    checar(t == "Escrita no escritório." and len(ollama.pedidos) == l1 + 1 and "internet" in c.ultima["nuvem"]["motivo"],
           "sem internet, o modelo daqui escreve", c.ultima)
    fake.modo = "ok"

    print("\no plano, a assinatura e a recarga (V7)")
    r = local.get("/api/nuvem/paulus/conta?forcar=true").json()
    checar(r["conta"]["plano_vigente"] and r["conta"]["tokens"]["hoje"] == 1200, "a tela lê o plano do Worker", r)
    r = local.post("/api/nuvem/paulus/assinar", json={}).json()
    checar(r["link"].startswith("https://paulus.ia.br/cadastro/pagamento/"), "assinar devolve a página de pagamento do site (o cartão vai no bloco do Mercado Pago)", r)
    r = local.post("/api/nuvem/paulus/recarga", json={}).json()
    checar(r["qr_code"] == "000201pix" and r["tokens"] == 10000000, "a recarga devolve o Pix", r)
    r = local.get("/api/nuvem/paulus/recarga/ORD1").json()
    checar(r["pago"] is True, "e diz quando foi pago")

    print("\nno Edge: o sim e a tela de consumo")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        # O titular começa sem o sim: a tela pede o termo antes de ligar.
        local.post("/api/nuvem/consentimento", json={"aceito": False})
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
                pag.wait_for_function("() => typeof cartaoNuvem === 'function' && typeof mostrarConfig === 'function'")
                checar(pag.locator("#pilula-nuvem").count() == 0, "sem o sim, não há pílula “Nuvem”")
                pag.evaluate("() => { mostrarConfig('modelos'); }")
                pag.wait_for_function("() => /créditos livres agora/.test((document.getElementById('cfg-tela') || {}).innerText || '')", timeout=15000)
                tela = pag.inner_text("#cfg-tela")
                checar("30 milhões" in tela and "Renova em" in tela and "01/11/2026" in tela and "Recarregar" in tela and "assinatura ativa" in tela,
                       "o plano: tokens restantes, a renovação, a recarga", tela[tela.find("tokens restantes") - 40:][:400])
                checar("Antes de ligar: o termo" in tela and pag.locator("#nuvem-ligado").is_disabled(), "sem o sim, o termo vem antes e ligar fica travado")
                checar("gráfico" not in tela.lower() and "tokens" in tela, "sem gráfico; a medida é em tokens")
                pag.screenshot(path=str(TMP / "v-plano.png"), full_page=True)
                pag.click("[data-nuvem-termo]")
                pag.wait_for_selector(".nuvem-termo", timeout=10000)
                checar("Nunca vai" in pag.inner_text(".nuvem-termo") and "DeepInfra" in pag.inner_text(".nuvem-termo"), "o termo na tela")
                pag.screenshot(path=str(TMP / "v-termo.png"))
                pag.click('[data-dialogo="confirmar"]')
                pag.wait_for_timeout(400)
                checar(not local.get("/api/nuvem").json()["consentido"], "sem marcar que leu, o sim não vale")
                pag.click("[data-nuvem-termo]")
                pag.wait_for_selector("#dialogo-marcar", timeout=10000)
                pag.check("#dialogo-marcar")
                pag.click('[data-dialogo="confirmar"]')
                pag.wait_for_function("() => /O sim do titular/.test((document.getElementById('cfg-tela') || {}).innerText || '')", timeout=15000)
                checar(local.get("/api/nuvem").json()["consentido"], "marcado e confirmado: o sim fica registrado")
                pag.click("#nuvem-ligado")
                pag.wait_for_function("() => document.getElementById('pilula-nuvem')", timeout=10000)
                checar(local.get("/api/nuvem").json()["ligada"] and pag.get_attribute("#pilula-nuvem", "aria-pressed") == "true",
                       "ligada, a pílula aparece já na nuvem")
                pag.click("[data-nuvem-recarga]")
                pag.wait_for_selector(".nuvem-pix", timeout=10000)
                checar("50,00" in pag.inner_text(".nuvem-pix") and pag.input_value(".nuvem-copia") == "000201pix", "a recarga: o Pix de R$ 50 com o copia e cola")
                pag.wait_for_function("() => /Pago\\. Os créditos entraram/.test(document.body.innerText)", timeout=15000)
                checar(True, "o pagamento é visto sozinho, sem fechar a janela")
                pag.screenshot(path=str(TMP / "v-recarga.png"))
                pag.click('[data-dialogo="confirmar"]')
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

    print("\nretirar o sim e sair")
    r = local.post("/api/nuvem/consentimento", json={"aceito": False}).json()
    checar(not r["consentido"] and not r["ligado"] and fake.consentimento.get("aceito") is False, "retirar desliga aqui e no Worker", r)
    checar(not isinstance(api.estado.cliente_para("resumos"), nuvem.ClienteNuvem), "sem o sim, o resumo é local")
    hist = (Path(os.environ["PAULUS_DADOS"]) / "nuvem" / "consentimentos.jsonl").read_text(encoding="utf-8").splitlines()
    checar([json.loads(x)["acao"] for x in hist][-1] == "retirado" and "sim" in [json.loads(x)["acao"] for x in hist], "o histórico do sim e do não fica guardado")
    local.delete("/api/nuvem/chave/paulus")
    checar(not nuvem.chave(api.estado, "paulus") and fake.ultimas("/api/ia/sair"), "desligar a instalação apaga o segredo daqui e de lá")

    print("\nas rotas")
    janela = ["GET /api/nuvem/termo", "POST /api/nuvem/consentimento", "POST /api/nuvem/paulus/ativar", "GET /api/nuvem/paulus/conta",
              "POST /api/nuvem/paulus/assinar", "POST /api/nuvem/paulus/recarga", "POST /api/nuvem/paulus/cancelar"]
    checar(all(politicas.de(*x.split(" ", 1)) == politicas.BLOQUEADO for x in janela), "o sim, a conta e o pagamento são da janela do escritório")
    checar(politicas.de("GET", "/api/nuvem/situacao") == politicas.PERMITIDO, "a situação da pílula passa de fora")

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
