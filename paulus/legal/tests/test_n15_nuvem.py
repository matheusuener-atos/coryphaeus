"""
N15 - a nuvem com a chave do escritório (src/nuvem.py, src/rotas_nuvem.py,
habilidades/perguntar.py `_escrever_na_nuvem`, js/75-nuvem.js).

O provedor é de mentira (`nuvem.PEDIR`): nada sai desta máquina no teste.

  - mascarar: CPF e CNPJ válidos, processo, e-mail e telefone viram
    marcadores; o CPF inválido fica; o marcador partido entre dois pedaços da
    resposta volta inteiro;
  - Anthropic e OpenAI: as mensagens no formato de cada um, a resposta aos
    pedaços e os tokens contados;
  - desligada de fábrica; ligar sem chave é recusado; a chave fica cifrada
    (o arquivo não tem a chave) e o teste escolhe o modelo;
  - a pergunta marcada "Nuvem": o pedido em Aprovações com o texto exato
    (mascarado, sem o CPF), o sim manda, a resposta volta com o CPF, o modelo
    local não escreve, o registro de envios e a auditoria;
  - recusar: o computador escreve, e diz por quê;
  - a conversa liberada e a regra de alçada vão sem pedir;
  - o anexo do e-mail e o caso só no escritório nunca vão; de fora não há
    nuvem (nem as rotas); a chave recusada pelo provedor volta para o
    computador;
  - no Edge: o cartão em Modelos, a pílula "Nuvem" e o cartão na conversa com
    "Mandar".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n15_nuvem.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-n15-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
CHAVE = "sk-ant-api03-teste-de-mentira-0123456789abcdef"
CPF = "529.982.247-25"


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
    """O modelo local de mentira: anota cada chamada."""

    def __init__(self) -> None:
        self.pedidos: list[list[dict]] = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        self.pedidos.append((json or {}).get("messages") or [])
        texto = "Escrita no escritório."

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


class Provedor:
    """A Anthropic e a OpenAI de mentira. `status` força o erro; `pedacos` é a resposta."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.status = 200
        self.pedacos = ["A multa é de 10%. O devedor, CPF [CP", "F 1], foi avisado."]

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": cabecalhos, "corpo": corpo})
        status, pedacos = self.status, list(self.pedacos)

        class R:
            status_code = status

            def json(self):
                if status >= 400:
                    return {"error": {"message": "invalid x-api-key"}}
                if "openai" in url:
                    return {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.5-mini"}, {"id": "whisper-1"}]}
                return {"data": [{"id": "claude-sonnet-5-5"}, {"id": "claude-haiku-4-5-20251001"}]}

            def iter_lines(self, decode_unicode=True):
                if "openai" in url:
                    for p in pedacos:
                        yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                    yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 30}})
                    yield "data: [DONE]"
                    return
                yield "event: message_start"
                yield "data: " + json.dumps({"type": "message_start", "message": {"usage": {"input_tokens": 321}}})
                for p in pedacos:
                    yield "data: " + json.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": p}})
                yield "data: " + json.dumps({"type": "message_delta", "usage": {"output_tokens": 42}})
                yield "data: " + json.dumps({"type": "message_stop"})

            def close(self):
                pass
        return R()


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
    print("  N15 — a nuvem com a chave do escritório")
    print("=" * 55)
    import requests

    import api
    import config
    import llama_client
    import nuvem
    import segredos
    from acesso import politicas
    from fastapi.testclient import TestClient

    print("\nmascarar")
    m = nuvem.Mascara()
    t = m.aplicar(f"O cliente, CPF {CPF} (e não 111.222.333-44), da empresa 11.222.333/0001-81, no processo "
                  "0001234-56.2024.8.26.0100, e-mail joao@clinica.com.br, telefone (11) 98765-4321. De novo: " + CPF)
    checar("[CPF 1]" in t and "[CNPJ 1]" in t and "[PROCESSO 1]" in t and "[E-MAIL 1]" in t and "[TELEFONE 1]" in t and CPF not in t,
           "CPF, CNPJ, processo, e-mail e telefone viram marcadores", t)
    checar("111.222.333-44" in t and t.count("[CPF 1]") == 2 and "[CPF 2]" not in t, "o CPF inválido fica; o mesmo CPF é o mesmo marcador")
    d = nuvem.Desmascarador(m)
    junto = d.entrar("O CPF é [CP") + d.entrar("F 1] e o processo [PROCESSO 1].") + d.fim()
    checar(junto == f"O CPF é {CPF} e o processo 0001234-56.2024.8.26.0100.", "o marcador partido entre dois pedaços volta inteiro", junto)

    print("\nAnthropic e OpenAI")
    prov = Provedor()
    nuvem.PEDIR["fn"] = prov
    msgs = llama_client.montar_mensagens("qual a multa?", "[T1] A multa é de 10%.", ensinado="cite [T1]")
    pedacos: list[str] = []
    uso = nuvem.chamar("anthropic", "claude-sonnet-5-5", CHAVE, msgs, pedacos.append)
    c = prov.chamadas[-1]
    checar(c["url"].endswith("/v1/messages") and c["cabecalhos"]["x-api-key"] == CHAVE and c["corpo"]["system"] and
           [x["role"] for x in c["corpo"]["messages"]] == ["user"] and c["corpo"]["stream"] is True,
           "Anthropic: o sistema à parte, as mensagens, o stream", c["corpo"].keys())
    checar("".join(pedacos).startswith("A multa é de 10%") and uso == {"tokens_entrada": 321, "tokens_saida": 42}, "Anthropic: os pedaços e os tokens", uso)
    pedacos.clear()
    uso = nuvem.chamar("openai", "gpt-5.5", "sk-openai-de-mentira-0123456789", msgs, pedacos.append)
    c = prov.chamadas[-1]
    checar(c["url"].endswith("/chat/completions") and c["cabecalhos"]["Authorization"].startswith("Bearer ") and
           c["corpo"]["messages"][0]["role"] == "system" and uso == {"tokens_entrada": 120, "tokens_saida": 30},
           "OpenAI: o sistema como mensagem, os pedaços e os tokens", uso)

    print("\ndesligada de fábrica, e a chave")
    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "trechos", "denso": False})
    api.estado.client = cliente
    api.estado.cliente_para = lambda tarefa: cliente
    local = TestClient(api.app, headers=api.cabecalho_local())
    regra = next(a for a in config.AUTONOMIA if a["chave"] == "modelo_nuvem")
    checar(not regra["travada"] and regra["padrao"] is False and "sem pedir" in regra["titulo"], "a regra de alçada: desligada, e não mais travada", regra["titulo"])
    e = local.get("/api/nuvem").json()
    checar(e["ligado"] is False and e["ligada"] is False and e["mascarar"] is True and not any(p["tem_chave"] for p in e["provedores"]),
           "desligada de fábrica, mascarar ligado, sem chave", e)
    r = local.post("/api/nuvem/configurar", json={"ligado": True})
    checar(r.status_code == 400 and local.get("/api/nuvem").json()["ligado"] is False, "ligar sem chave é recusado", r.json())
    if not segredos.disponivel():
        print("  pulado o resto: sem DPAPI")
        return 0
    prov.status = 401
    r = local.post("/api/nuvem/chave", json={"provedor": "anthropic", "chave": CHAVE})
    checar(r.status_code == 400 and "recusou a chave" in r.json()["detail"] and not nuvem.chave(api.estado, "anthropic"),
           "a chave recusada pelo provedor não fica guardada", r.json())
    prov.status = 200
    r = local.post("/api/nuvem/chave", json={"provedor": "anthropic", "chave": CHAVE}).json()
    arq = Path(os.environ["PAULUS_DADOS"]) / "nuvem" / "chave-anthropic.dpapi"
    checar(r["modelos"] == ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"] and r["modelo"] == "claude-sonnet-5-5"
           and arq.exists() and CHAVE not in arq.read_text(encoding="utf-8") and CHAVE not in json.dumps(api.estado.prefs.dados),
           "guardada cifrada (nem no arquivo nem nas preferências), testada, e o modelo escolhido", r.get("modelos"))
    r = local.post("/api/nuvem/configurar", json={"ligado": True}).json()
    checar(r["ligada"] is True, "ligada")

    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "contrato-clinica.txt").write_text(
        "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\nCláusula 1. O locatário, CPF " + CPF + ", paga o aluguel até o dia 5.\n\n"
        "Cláusula 2. A multa por atraso no aluguel é de 10% sobre o valor devido.", encoding="utf-8")
    api.estado.recarregar()
    execs = Path(os.environ["PAULUS_DADOS"]) / "execucoes"

    def perguntar(pergunta, cliente_http=None, nuvem_marcada=True, decidir=None, tid=None):
        """Pergunta; `decidir(pedido)` age no pedido da nuvem, se houver. Devolve (eventos, mensagem final, chamadas ao local, tid)."""
        h = cliente_http or local
        tid = tid or h.post("/api/trabalhos", json={"pedido": "n15"}).json()["id"]
        n0 = len(ollama.pedidos)
        saida = {}
        th = threading.Thread(target=lambda: saida.update(r=h.post(f"/api/trabalhos/{tid}/perguntar",
                                                                     json={"pergunta": pergunta, "nuvem": nuvem_marcada})), daemon=True)
        th.start()
        if decidir is not None:
            if esperar(lambda: any(p.categoria == "nuvem" for p in api.estado.fila.pendentes), 30):
                decidir(next(p for p in api.estado.fila.pendentes if p.categoria == "nuvem"))
        th.join(90)
        esperar(lambda: not api.estado.respondendo.get(tid))
        evs = eventos(saida["r"].text) if "r" in saida else []
        m = h.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
        return evs, m, len(ollama.pedidos) - n0, tid

    print("\na pergunta marcada “Nuvem”")
    visto = {}

    def aprovar(p):
        visto["pedido"] = p
        visto["decidir"] = local.post("/api/aprovacoes/decidir", json={"ids": [p.id], "aprovar": True}).json()

    n_chamadas = len(prov.chamadas)
    evs, m, locais, tid = perguntar("qual a multa por atraso no aluguel?", decidir=aprovar)
    p = visto.get("pedido")
    exato = (p.dados or {}).get("texto_exato", "") if p else ""
    checar(p is not None and p.acao == "nuvem.enviar" and not p.reversivel and (p.dados or {}).get("sai_daqui") and "multa por atraso" in exato,
           "o pedido em Aprovações, com o texto exato que vai sair", p and p.titulo)
    checar(CPF not in exato and "[CPF 1]" in exato and "Mascarados: 1 CPF" in (p.resumo if p else ""), "o texto que sai vai mascarado (o CPF não sai)", p and p.resumo)
    checar(any(t == "nuvem_pedido" and d.get("precisa_aprovar") for t, d in evs) and any(t == "nuvem_mandando" for t, d in evs),
           "a tela recebe o pedido e o envio", [t for t, _ in evs if t.startswith("nuvem")])
    enviado = json.dumps(prov.chamadas[-1]["corpo"], ensure_ascii=False) if len(prov.chamadas) > n_chamadas else ""
    checar(enviado and CPF not in enviado and "[CPF 1]" in enviado, "ao provedor foi o texto mascarado")
    texto = m.get("texto") or ""
    checar("A multa é de 10%" in texto and CPF in texto and "[CPF" not in texto, "a resposta volta com o CPF de volta no lugar", texto[:160])
    checar(locais == 0, "o modelo local não escreveu", locais)
    como = (m.get("cobertura") or {}).get("como") or {}
    checar((como.get("nuvem") or {}).get("onde") == "nuvem" and "claude-sonnet-5-5" in como.get("modelo", "") and como["nuvem"].get("tokens_saida") == 42,
           "a resposta diz que foi escrita pela nuvem, o modelo e os tokens", como.get("nuvem"))
    lista = local.get("/api/nuvem/envios").json()["envios"]
    checar(lista and lista[0]["modelo"] == "claude-sonnet-5-5" and lista[0]["como"] == "aprovado em Aprovações" and lista[0]["tokens_entrada"] == 321,
           "o registro de envios", lista[:1])
    saiu = local.get(f"/api/nuvem/envios/{lista[0]['envio']}").json()["texto"] if lista else ""
    checar("[CPF 1]" in saiu and CPF not in saiu, "o texto exato que saiu fica guardado ao lado")
    checar(any(ev.get("acao") == "nuvem" for ev in api.estado.acesso_de_fora.eventos), "e na auditoria")

    print("\nrecusar")
    evs, m, locais, _ = perguntar("qual a multa por atraso no aluguel?",
                                  decidir=lambda p: local.post("/api/aprovacoes/decidir", json={"ids": [p.id], "aprovar": False}))
    fim = next((d for t, d in evs if t == "nuvem_fim"), {})
    checar(fim.get("onde") == "computador" and "responder neste computador" in fim.get("motivo", ""), "recusado: o computador escreve, e diz por quê", fim)
    checar(locais >= 1 and "Escrita no escritório" in (m.get("texto") or ""), "a resposta é a do modelo local", (locais, (m.get("texto") or "")[:60]))

    print("\nsem pedir")
    r = local.post(f"/api/trabalhos/{tid}/nuvem", json={"liberada": True})
    n_pend = len(api.estado.fila.pendentes)
    evs, m, locais, _ = perguntar("e qual o dia do aluguel?", tid=tid)
    checar(r.status_code == 200 and len(api.estado.fila.pendentes) == n_pend and locais == 0 and
           next((d for t, d in evs if t == "nuvem_mandando"), {}).get("como") == "conversa liberada", "a conversa liberada vai sem pedir")
    api.estado.prefs.atualizar({"autonomia": {"modelo_nuvem": True}})
    evs, m, locais, _ = perguntar("qual a multa por atraso no aluguel?")
    checar(len(api.estado.fila.pendentes) == n_pend and next((d for t, d in evs if t == "nuvem_mandando"), {}).get("como") == "regra de alçada (sem pedir)",
           "a regra de alçada ligada vai sem pedir")
    evs, m, locais, _ = perguntar("qual a multa por atraso no aluguel?", nuvem_marcada=False)
    checar(not any(t.startswith("nuvem") for t, _ in evs) and locais >= 1, "sem marcar “Nuvem”, nada vai (nem com a regra ligada)")

    print("\no que nunca vai")
    # Com poucos documentos, a pergunta lê todos: o anexo entra em qualquer uma.
    (pasta / "anexo-do-email.txt").write_text("PROPOSTA RECEBIDA POR E-MAIL.\n\nO prazo da proposta recebida é de 15 dias corridos.", encoding="utf-8")
    nuvem.marcar_do_email(api.estado, pasta / "anexo-do-email.txt")
    api.estado.recarregar()
    n_chamadas = len(prov.chamadas)
    evs, m, locais, _ = perguntar("qual o prazo da proposta recebida por e-mail?")
    fim = next((d for t, d in evs if t == "nuvem_fim"), {})
    checar(fim.get("onde") == "computador" and "e-mail" in fim.get("motivo", "") and len(prov.chamadas) == n_chamadas, "o anexo do e-mail fica", fim)
    import aparelho

    (pasta / "anexo-do-email.txt").unlink()
    (pasta / "sigilo").mkdir(exist_ok=True)
    (pasta / "sigilo" / "acordo-sigiloso.txt").write_text("ACORDO SIGILOSO.\n\nA indenização do acordo sigiloso é de 50 mil reais.", encoding="utf-8")
    api.estado.recarregar()
    aparelho.so_no_escritorio().guardar([{"tipo": "pasta", "valor": "sigilo"}])
    evs, m, locais, _ = perguntar("qual a indenização do acordo sigiloso?")
    fim = next((d for t, d in evs if t == "nuvem_fim"), {})
    checar(fim.get("onde") == "computador" and "só no escritório" in fim.get("motivo", "") and len(prov.chamadas) == n_chamadas, "o caso só no escritório fica", fim)
    aparelho.so_no_escritorio().guardar([])
    (pasta / "sigilo" / "acordo-sigiloso.txt").unlink()
    api.estado.recarregar()
    prov.status = 401
    evs, m, locais, _ = perguntar("qual a multa por atraso no aluguel?")
    fim = next((d for t, d in evs if t == "nuvem_fim"), {})
    checar(fim.get("onde") == "computador" and "recusou a chave" in fim.get("motivo", "") and "Escrita no escritório" in (m.get("texto") or ""),
           "o provedor recusou: o computador escreve", fim)
    prov.status = 200
    rotas = ["GET /api/nuvem", "POST /api/nuvem/chave", "POST /api/nuvem/configurar", "POST /api/trabalhos/{id_}/nuvem", "GET /api/nuvem/envios"]
    checar(all(politicas.de(*x.split(" ", 1)) == politicas.BLOQUEADO for x in rotas) and "nuvem.enviar" in politicas.ACOES_SO_NO_ESCRITORIO,
           "de fora: as rotas e o sim do pedido são da janela do escritório")
    copia = api.estado.drive_online.raiz() / "Clientes" / "parecer.pdf"
    hit = SimpleNamespace(chunk=SimpleNamespace(doc_path=str(copia)), doc_name="parecer.pdf")
    envio = nuvem.Envio(api.estado, SimpleNamespace(id="x", titulo="x", contexto={}))
    checar(envio.preparar("p", "c", "", [hit]) is None and "Google Drive" in envio.motivo, "a cópia do Drive feita pelo PAULUS (API do Google) fica", envio.motivo)
    envio = nuvem.Envio(api.estado, SimpleNamespace(id="x", titulo="x", contexto={}), pessoa={"conta_id": 1})
    checar(envio.preparar("p", "c", "", []) is None and "de fora" in envio.motivo, "de fora, a pergunta não vai à nuvem", envio.motivo)
    api.estado.prefs.atualizar({"autonomia": {"modelo_nuvem": False}})

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
                pag.wait_for_function("() => typeof cartaoNuvem === 'function' && typeof enviar === 'function'")
                pag.wait_for_selector("#pilula-nuvem", timeout=10000)
                checar(pag.locator("#pilula-nuvem").count() == 1, "a pílula “Nuvem” na caixa da pergunta (nuvem ligada, janela do escritório)")
                pag.evaluate("() => { mostrarConfig('modelos'); }")
                pag.wait_for_function("() => /Nuvem \\(chave do escritório\\)/.test((document.getElementById('cfg-tela') || {}).innerText || '')", timeout=15000)
                tela = pag.inner_text("#cfg-tela")
                checar("assinatura de consumidor" in tela and "Mascarar antes de sair" in tela and "registro de envios" in tela.lower(),
                       "o cartão em Modelos: o que sai, mascarar e o registro")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n15-modelos.png"), full_page=True)
                pag.evaluate("() => { voltarAoAssistente(); }")
                pag.wait_for_timeout(500)
                pag.click("#pilula-nuvem")
                checar(pag.get_attribute("#pilula-nuvem", "aria-pressed") == "true", "a pílula marca a próxima pergunta")
                pag.fill("#pedido", "qual a multa por atraso no aluguel?")
                pag.evaluate("() => { enviar(); }")
                pag.wait_for_selector(".nuvem-pedido [data-nuvem-mandar]", timeout=30000)
                checar("Mandar à" in pag.inner_text(".nuvem-pedido") and "Mascarados: 1 CPF" in pag.inner_text(".nuvem-pedido"),
                       "o cartão na conversa: para onde vai e o que foi mascarado")
                checar(pag.get_attribute("#pilula-nuvem", "aria-pressed") == "false", "a marca vale para uma pergunta só")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n15-pedido.png"))
                pag.click(".nuvem-pedido [data-nuvem-mandar]")
                pag.wait_for_function("() => /O devedor, CPF 529\\.982\\.247-25/.test(document.body.innerText)", timeout=30000)
                pag.wait_for_timeout(800)
                checar(pag.locator(".nuvem-pedido").count() == 0 and "nuvem" in pag.inner_text(".assinatura >> nth=-1"),
                       "Mandar: a resposta da nuvem chega e assina com o modelo dela", pag.inner_text(".assinatura >> nth=-1"))
                pag.screenshot(path=str(TMP / "n15-resposta.png"))
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
