"""
Paulus autônomo para decidir o que fazer, onde procurar e como pensar
(regra do dono, 13/10/2026; src/caminho_da_pergunta.py).

  - a caixa de pergunta não tem mais a pílula de escopo ("Modo criativo",
    "Acervo", "pergunto onde procurar") nem a linha "A próxima pergunta…";
    o chip do anexo fica, com o x (no HTML/JS montado e na tela, no Edge);
  - a rota do "modo de escopo" saiu do servidor;
  - o caminho sai da frase, com e sem anexo:
      "explique a usucapião" com um PDF anexado -> conhecimento (não lê o PDF);
      "qual o valor do imóvel?" com o PDF -> documento (lê o PDF);
      "cadastre os vendedores" com o PDF -> o cartão de cadastro;
      "escreva um e-mail de boas-vindas" -> conhecimento, sem Biblioteca;
      depois de uma resposta de conhecimento, "resuma isso" continua nele;
      sem a nuvem, o conhecimento vai ao modelo daqui, sem ler o Acervo;
  - "Como respondi" guarda a decisão (caminho e porquê);
  - a memória não emenda pedido de ação nem frase completa na pergunta
    anterior (caso real: "qual Abre o contrato que fizemos juntos no
    contrato aqui no editor conversa aqui no editor?"), e continua
    completando "e o prazo?" e "e dele?";
  - o modelo daqui não diz mais "não presta consultoria jurídica"; o trabalho
    em etapas tira a ressalva de leigo.

Sem rede: a nuvem e o modelo local são de mentira.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_paulus_autonomo.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-autonomo-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import caminho_da_pergunta as cp  # noqa: E402
import memoria  # noqa: E402

_falhas: list[str] = []

PDF = "COMPRA E VENDA - LOTE SETOR ATLANTA.txt"
CONTRATO = """CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO

Vendedores: OBEDI LOURENÇO SANTOS, portador do RG nº 4091179 PC/PA e CPF nº 752.043.042-15, e seu conjuge \
SWEDY PEREIRA SANTOS, portador(a) do RG nº 772.753 SSP/TO e CPF nº 962.136.202-49, ambos residentes e \
domiciliados à Avenida Araguaia, S/n, Setor Jardim Vitória, São Félix do Xingu, Pará, 68380-000, doravante \
denominados em conjunto como VENDEDORES;

Comprador: HUGO MAGALHÃES SILVA, brasileiro, casado, pecuarista, portador do RG de nº 8653510 PC/PA, inscrito no \
CPF de nº 016.708.042-32, residente à Rua América, 639, Setor Vitória, São Félix do Xingu/PA, doravante \
denominado COMPRADOR;

CLÁUSULA 1ª – DO OBJETO
A venda do imóvel urbano medindo 360 m², no Setor Atlanta, São Félix do Xingu.

CLÁUSULA 2ª – DO PREÇO
O valor do imóvel é de R$ 30.000,00 (trinta mil reais), pago em 2 parcelas de R$ 15.000,00.
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


class Nuvem:
    """A nuvem de mentira: guarda o que recebeu e responde a triagem ou um texto."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"url": url, "corpo": corpo})
        sistema = " ".join(m["content"] for m in (corpo or {}).get("messages") or [] if m["role"] == "system")
        if "Você faz a triagem" in sistema:
            texto = '{"assunto": "documentos", "documentos": [], "em_tese": "", "dispositivos": []}'
        elif "CONHECIMENTO" in sistema:
            texto = "Resposta pelo que sei."
        else:
            texto = "O valor do imóvel é de R$ 30.000,00."

        class R:
            status_code = 200

            def json(self):
                return {}

            def iter_lines(self, decode_unicode=True):
                yield "data: " + json.dumps({"choices": [{"delta": {"content": texto}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
                yield "data: [DONE]"

            def close(self):
                pass
        return R()

    def respostas(self, desde: int = 0) -> list[dict]:
        return [c for c in self.chamadas[desde:]
                if "Você faz a triagem" not in " ".join(m["content"] for m in c["corpo"]["messages"] if m["role"] == "system")]


class Ollama:
    """O modelo daqui, de mentira: responde e guarda as mensagens."""

    def __init__(self) -> None:
        self.pedidos: list = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        self.pedidos.append((json or {}).get("messages") or [])
        texto = '{"ok": "local"}' if (json or {}).get("format") == "json" else "Resposta escrita aqui."

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
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": [{"name": "falso:1b"}]})


# ------------------------------------------------------------ as regras

def test_regras() -> None:
    print("\no caminho, pela frase (sem servidor)")
    casos = [
        ("explique a usucapião", [PDF], "conhecimento"),
        ("o que é ITBI?", [PDF], "conhecimento"),
        ("me explique como funciona a usucapião extrajudicial", [], "conhecimento"),
        ("quais os requisitos da usucapião?", [PDF], "conhecimento"),
        ("escreva um e-mail de boas-vindas para um cliente novo", [], "conhecimento"),
        ("qual a diferença entre posse e propriedade?", [PDF], "conhecimento"),
        ("qual o valor do imóvel?", [PDF], "documento"),
        ("explique a cláusula 2ª", [PDF], "documento"),
        ("explique este contrato", [PDF], "documento"),
        ("O que você acha dele? Está bom assim?", [PDF], "documento"),
        ("qual o valor do imóvel?", [], None),
        ("como funciona o acesso de fora?", [], None),
        ("o que é o Acervo?", [], None),
        ("Pra que serve a busca no DJE?", [], None),
        ("qual o prazo para contestar?", [], None),
    ]
    for frase, anexos, esperado in casos:
        d = cp.decidir(frase, anexos=anexos)
        obtido = d.caminho if d else None
        checar(obtido == esperado, f"“{frase}”{' com anexo' if anexos else ''} → {esperado or 'caminho de sempre'}",
               (obtido, d.porque if d else ""))
    d = cp.decidir("escreva um e-mail de boas-vindas", anexos=[])
    checar(d.tipo == "escrever" and d.porque, "a escrita livre tem tipo e porquê", d)
    d = cp.decidir("resuma isso em três linhas", anexos=[], anterior="conhecimento")
    checar(d is not None and d.caminho == "conhecimento" and d.tipo == "continuar",
           "“resuma isso” depois de uma resposta de conhecimento continua nele", d)
    checar(cp.decidir("resuma isso em três linhas", anexos=[PDF], anterior="conhecimento").caminho == "documento",
           "com anexo novo, vai ao anexo")
    checar(cp.decidir("resuma isso em três linhas", anexos=[], anterior="busca") is None,
           "depois de uma resposta de documento, o caminho de sempre")

    print("\na memória não emenda pedido de ação")
    real = "Abre o contrato que fizemos juntos nesta conversa aqui no editor"
    ctx = {"ultima_pergunta": "abra o contrato aqui no editor", "assunto": ["contrato aqui no editor", "m"]}
    efetiva, _, continuou = memoria.preparar([], ctx, real)
    checar(efetiva == real and not continuou, "o caso real fica como a pessoa escreveu", efetiva)
    checar(memoria.pede_acao(real) and memoria.pede_acao("por favor, cadastre os vendedores")
           and not memoria.pede_acao("e a multa?"), "o verbo de comando na frente é pedido")
    ctx = {}
    memoria.preparar([], ctx, "abra o contrato aqui no editor")
    checar("assunto" not in ctx, "o pedido de ação não vira o assunto da conversa", ctx)
    for frase in ("Cadastre os vendedores dele", "qual a cláusula de reajuste prevista neste contrato de locação?",
                  "Mande isso por e-mail para ela"):
        checar(memoria.reescrever(frase, "qual o prazo do contrato ACME?") == frase, f"“{frase}” fica intacta")
    checar(memoria.reescrever("e o prazo?", "qual o valor do contrato ACME?") == "qual o prazo do contrato ACME?",
           "“e o prazo?” continua herdando o sujeito")
    checar(memoria.reescrever("e dele?", "qual o valor do contrato ACME?") != "e dele?", "“e dele?” também")
    checar(memoria.reescrever("qual o valor dele?", "qual o prazo do contrato ACME?") == "qual o valor do contrato ACME?",
           "“qual o valor dele?” também")

    print("\nquem pergunta é advogado")
    import llama_client

    plano = cp._plano(llama_client.SYSTEM_PROMPT)
    checar("consultoria" not in plano and "colega" in plano and "garantia" in plano,
           "o modelo daqui fala como colega, sem “não presta consultoria”, sem garantia")
    fonte = (RAIZ / "src" / "api.py").read_text(encoding="utf-8")
    trecho = fonte[fonte.index("def _responder_trabalho"):fonte.index("INSTRUCAO_CONHECIMENTO = ")]
    checar("sem_ressalva_de_leigo" in trecho, "o trabalho em etapas tira a ressalva de leigo")


# ------------------------------------------------------------ a tela, no código

def test_tela_no_codigo() -> None:
    print("\na caixa, no HTML/JS montado")
    front = RAIZ / "frontend"
    js = "\n".join(p.read_text(encoding="utf-8") for p in sorted((front / "js").glob("*.js")))
    html = (front / "index.html").read_text(encoding="utf-8")
    codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    codigo = "\n".join(l for l in codigo.splitlines() if not l.strip().startswith("//"))
    for marca in ("Modo criativo", "escopo-modo", "escopo-livre", "A próxima pergunta lê", "A próxima pergunta procura",
                  "Pergunto onde procurar", "modoDoEscopo", "alternarModoDoEscopo", "guardarModoNoServidor", "modoEscopo",
                  "textoDoProximo", "/escopo\"", "criativo:"):
        checar(marca not in codigo and marca not in html, f"sem “{marca}” no frontend")
    checar('class="escopo-pilula"' in codigo and "data-tirar" in codigo, "o chip do anexo, com o x, continua")
    checar('foco: (estado.foco || []).slice()' in codigo, "o documento da conversa vai como indício (`foco`), não como anexo")


# ------------------------------------------------------------ pela conversa

def main() -> int:
    print("=" * 60)
    print("  Paulus autônomo: o caminho decidido pela frase")
    print("=" * 60)
    test_regras()
    test_tela_no_codigo()

    import requests

    import api
    import llama_client
    import nuvem
    from fastapi.testclient import TestClient

    fake = Nuvem()
    nuvem.PEDIR["fn"] = fake
    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    api.estado.client = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.check_ollama = lambda *a, **k: (True, "")
    api.plano_mod.liberada = lambda estado: True
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "tudo", "denso": False})
    api.estado.modelo_para = lambda tarefa: "falso:1b"
    nuvem.chave = lambda estado, provedor: "di-chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    local = TestClient(api.app, headers=api.cabecalho_local())
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / PDF).write_text(CONTRATO, encoding="utf-8")
    api.estado.recarregar()

    def nova() -> str:
        return local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]

    def perguntar(tid: str, frase: str, **extra) -> dict:
        corpo = {"pergunta": frase, "nuvem": True, **extra}
        r = local.post(f"/api/trabalhos/{tid}/perguntar", json=corpo)
        ev = eventos(r.text)
        t = local.get(f"/api/trabalhos/{tid}").json()
        ultima = t["mensagens"][-1]
        return {"status": r.status_code, "eventos": ev, "proposta": next((d for k, d in ev if k == "proposta"), {}),
                "salvo": ultima, "como": (ultima.get("cobertura") or {}).get("como") or {}, "trabalho": t}

    def enviado(chamadas) -> str:
        return json.dumps([c["corpo"] for c in chamadas], ensure_ascii=False)

    print("\nas quatro rotas, com o PDF anexado")
    r = local.post("/api/trabalhos/x/escopo", json={"modo": "criativo"})
    checar(r.status_code in (404, 405), "a rota do modo de escopo saiu", r.status_code)

    n0 = len(fake.chamadas)
    tid = nova()
    r = perguntar(tid, "explique a usucapião", apenas=[PDF])
    feitas = fake.respostas(n0)
    checar(r["status"] == 200 and len(feitas) == 1 and "CONHECIMENTO" in enviado(feitas),
           "“explique a usucapião” com o PDF: uma chamada, com a instrução de conhecimento", (r["status"], len(feitas)))
    checar("30.000" not in enviado(fake.chamadas[n0:]) and "OBEDI" not in enviado(fake.chamadas[n0:]),
           "e o PDF não foi lido")
    checar(r["como"].get("caminho") == "conhecimento" and (r["como"].get("decisao") or {}).get("caminho") == "conhecimento"
           and (r["como"].get("decisao") or {}).get("porque"), "“Como respondi” guarda o caminho e o porquê", r["como"])

    n0 = len(fake.chamadas)
    r = perguntar(tid, "qual o valor do imóvel?", apenas=[PDF])
    feitas = fake.respostas(n0)
    checar(r["status"] == 200 and feitas and "30.000" in enviado(feitas) and "CONHECIMENTO" not in enviado(feitas),
           "“qual o valor do imóvel?” com o PDF: lê o PDF", (r["status"], len(feitas)))
    checar(r["como"].get("caminho") != "conhecimento" and (r["como"].get("decisao") or {}).get("caminho") == "documento"
           and PDF in ((r["como"].get("escopo") or {}).get("apenas") or []), "caminho de documento, só no anexo", r["como"])

    n0 = len(fake.chamadas)
    ollama.pedidos.clear()
    r = perguntar(nova(), "cadastre os vendedores", apenas=[PDF])
    nomes = [p["nome"] for p in (r["proposta"].get("campos") or {}).get("pessoas") or []]
    checar(r["proposta"].get("tipo") == "cadastros" and nomes == ["Obedi Lourenço Santos", "Swedy Pereira Santos"],
           "“cadastre os vendedores” com o PDF: o cartão com os dois vendedores", (r["proposta"].get("tipo"), nomes))
    checar(not fake.chamadas[n0:] and not ollama.pedidos, "sem modelo")

    print("\nsem anexo")
    n0 = len(fake.chamadas)
    r = perguntar(nova(), "escreva um e-mail de boas-vindas para um cliente novo")
    feitas = fake.respostas(n0)
    checar(len(fake.chamadas[n0:]) == 1 and "CONHECIMENTO" in enviado(feitas) and "LEI —" not in enviado(feitas),
           "“escreva um e-mail de boas-vindas”: conhecimento, sem triagem e sem Biblioteca", len(fake.chamadas[n0:]))
    checar((r["como"].get("decisao") or {}).get("tipo") == "escrever", "decidido como escrita", r["como"].get("decisao"))
    tid2 = r["trabalho"]["id"]
    n0 = len(fake.chamadas)
    r = perguntar(tid2, "resuma isso em três linhas")
    checar(r["como"].get("caminho") == "conhecimento" and "CONHECIMENTO" in enviado(fake.respostas(n0)),
           "“resuma isso” continua no caminho de conhecimento", r["como"])

    print("\no documento da conversa é indício, não prisão")
    tid3 = nova()
    perguntar(tid3, "qual o valor do imóvel?", apenas=[PDF])
    n0 = len(fake.chamadas)
    r = perguntar(tid3, "o que é ITBI?", foco=[PDF])
    # O par anterior (o valor) vai no histórico; o texto do PDF, não.
    checar(r["como"].get("caminho") == "conhecimento" and "OBEDI" not in enviado(fake.chamadas[n0:])
           and "Setor Atlanta" not in enviado(fake.chamadas[n0:]),
           "“o que é ITBI?” com o PDF em foco: conhecimento, sem ler o PDF", r["como"])
    n0 = len(fake.chamadas)
    r = perguntar(tid3, "e quem é o comprador?", foco=[PDF])
    checar("30.000" in enviado(fake.respostas(n0)) and r["como"].get("caminho") != "conhecimento",
           "a pergunta seguinte, sobre o documento, volta a ele", r["como"].get("caminho"))

    print("\nsem a nuvem")
    # O resumo da conversa longa (src/memoria.py) das conversas de cima roda em
    # segundo plano, e elas podiam ir à nuvem: espera ele acabar, ou a chamada
    # dele cai na conta desta pergunta, que não pode ir.
    import time

    fim = time.time() + 60
    while api._resumindo and time.time() < fim:
        time.sleep(0.2)
    n0 = len(fake.chamadas)
    ollama.pedidos.clear()
    r = perguntar(nova(), "explique a usucapião", apenas=[PDF], nuvem=False)
    lido_aqui = json.dumps(ollama.pedidos, ensure_ascii=False)
    checar(not fake.chamadas[n0:] and ollama.pedidos and "NAO E SOBRE DOCUMENTO" in lido_aqui and "30.000" not in lido_aqui,
           "o modelo daqui responde, sem ler o PDF", (len(fake.chamadas[n0:]), len(ollama.pedidos)))
    checar(r["como"].get("caminho") == "conhecimento" and "Resposta escrita aqui" in r["salvo"]["texto"],
           "marcada como conhecimento", r["como"].get("caminho"))

    test_na_tela(api)

    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s):")
        for f in _falhas:
            print("  - " + f)
        return 1
    print("todos os testes passaram")
    return 0


def test_na_tela(api) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: sem o Playwright")
        return
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    t = e.trabalhos.criar("Sobre o lote")
    t.dizer("pessoa", "qual o valor do imóvel?")
    t.dizer("paulus", "O valor do imóvel é de R$ 30.000,00.")
    t.contexto["documento_em_foco"] = [PDF]
    e.trabalhos.salvar(t)
    porta = _porta_livre()
    _subir_servidor(porta)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1600, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        for largura, nome in ((1600, "computador"), (390, "celular")):
            pag = ctx.new_page()
            pag.set_viewport_size({"width": largura, "height": 900})
            erros: list[str] = []
            pag.on("pageerror", lambda x: erros.append(str(x)))
            # A janela de fora entra pela chave uma vez; a do celular já tem a sessão.
            destino = ("/entrar-local?chave=" + e.acesso.chave) if largura > 400 else "/"
            pag.goto(f"http://127.0.0.1:{porta}" + destino, wait_until="networkidle")
            pag.wait_for_function("() => typeof abrirTrabalho === 'function'", timeout=20000)
            pag.wait_for_timeout(800)
            pag.evaluate(f"() => abrirTrabalho('{t.id}')")
            pag.wait_for_timeout(800)
            caixa = pag.evaluate("""() => ({
              registro: document.getElementById('registro').hidden,
              escopo: document.getElementById('escopo').hidden,
              pilula: !!document.querySelector('#escopo-modo, .escopo-livre, .escopo-acervo'),
              texto: document.getElementById('conversa-rodape').innerText,
              envio: escopoDoEnvio(),
            })""")
            checar(caixa["registro"] and caixa["escopo"] and not caixa["pilula"]
                   and "Modo criativo" not in caixa["texto"] and "próxima pergunta" not in caixa["texto"].lower(),
                   f"{nome}: sem pílula de escopo e sem a linha “A próxima pergunta”", caixa)
            checar(caixa["envio"].get("foco") == [PDF] and not caixa["envio"].get("apenas"),
                   f"{nome}: o documento da conversa vai como indício", caixa["envio"])
            pag.evaluate("(n) => definirEscopo([n])", PDF)
            chip = pag.evaluate("""() => ({ visivel: !document.getElementById('escopo').hidden,
              texto: (document.querySelector('#escopo .escopo-pilula') || {}).textContent || '',
              envio: escopoDoEnvio() })""")
            checar(chip["visivel"] and PDF in chip["texto"] and chip["envio"].get("apenas") == [PDF],
                   f"{nome}: o chip do anexo aparece e o anexo vai com a pergunta", chip)
            pag.click("#escopo [data-tirar]")
            checar(pag.evaluate("() => document.getElementById('escopo').hidden && !estado.escopo.length"),
                   f"{nome}: o x tira o anexo")
            checar(not erros, f"{nome}: nenhum erro de JavaScript", erros[:3])
            pag.close()
        nav.close()


if __name__ == "__main__":
    sys.exit(main())
