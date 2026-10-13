"""
"Abra o contrato aqui no editor" (caso real de 13/10/2026, conversa
"Contrato Obedi Lourenço"). O PAVLVS já tinha redigido o contrato; o dono
pediu, em três mensagens, para abri-lo no editor - e recebeu uma resposta
sobre o item 3 do PDF em foco, depois "Peça: abra o contrato no editor de
texto." e "Peça: crie um novo documento...", no modo criativo.

  - as três frases, numa conversa com trabalho redigido (cartão "levar ao
    editor"): abrem o MESMO rascunho que o botão abre, sem modelo, sem nuvem,
    sem cópia nova ao pedir de novo - com o PDF anexado e com o modo criativo;
  - o /fazer "levar_ao_editor" continua devolvendo o mesmo rascunho;
  - a frase que NOMEIA um arquivo ("o contrato de locação no editor") abre esse;
  - sem trabalho, o documento anexado abre no editor (e de novo, o mesmo);
  - sem trabalho e sem documento: diz que não há o que levar e oferece redigir;
  - "abra o contrato de locação" (sem "editor") segue o abrir de hoje;
  - o eco "Peça: <pedido>" do modelo nunca fica como resposta (instrucao_nuvem).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_abrir_no_editor.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-abrir-editor-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

import instrucao_nuvem  # noqa: E402
import intencao  # noqa: E402

_falhas: list[str] = []

FRASES = ("Abra o contrato aqui no editor",
          "Abre o contrato que fizemos juntos nessa conversa aqui no editor",
          "abra o contrato no editor de texto")
CONTRATO = ("CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO\n\nQUALIFICAÇÃO DAS PARTES\n\nVendedor: OBEDI LOURENÇO SANTOS.\n\n"
            "CLÁUSULA 1ª – DO OBJETO\n\nO imóvel urbano descrito no item 3.\n\nCLÁUSULA 2ª – DO PREÇO\n\nR$ 30.000,00.")
LOCACAO = "Contrato de locação.txt"
PDF = "Partilha consensual.txt"


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
    """A nuvem de mentira: responde o eco "Peça: ..." - o que o modelo fez no caso real."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.resposta = "Peça: abra o contrato no editor de texto."

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"url": url, "corpo": corpo})
        pedacos = [self.resposta[:10], self.resposta[10:]]

        class R:
            status_code = 200

            def json(self):
                return {}

            def iter_lines(self, decode_unicode=True):
                for p in pedacos:
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
                yield "data: [DONE]"

            def close(self):
                pass
        return R()


class Ollama:
    """O modelo deste computador não pode ser chamado: nenhum desses pedidos lê documento."""

    def __init__(self) -> None:
        self.pedidos = 0

    def post(self, *a, **k):
        self.pedidos += 1
        raise RuntimeError("o modelo local não devia ser chamado")

    def get(self, *a, **k):
        return SimpleNamespace(status_code=200, json=lambda: {"models": [{"name": "falso:1b"}]}, raise_for_status=lambda: None)


# ------------------------------------------------------------ sem servidor

def test_leitura() -> None:
    print("\na frase, lida por regra")
    for frase in FRASES + ("leva isso pro editor", "pode abrir a minuta no editor?", "manda pro editor, por favor",
                           "Isso mesmo, quero que você abra o contrato no editor", "abra o que fizemos no editor"):
        lido = intencao.ler(frase)
        checar(lido.tipo == "levar_ao_editor", f"“{frase}” é levar ao editor", lido.tipo)
    checar(intencao.pede_no_editor(FRASES[0])["coisa"] == "o contrato", "o que levar: “o contrato”")
    checar(intencao.pede_no_editor(FRASES[1])["proprias"] == [], "“que fizemos juntos nessa conversa” não nomeia arquivo",
           intencao.pede_no_editor(FRASES[1]))
    for frase in ("abra o editor", "abra a agenda no editor", "coloque a cláusula de multa no editor",
                  "resuma a procuração e salve no editor", "crie um documento no editor",
                  "abra o contrato e corrija o valor no editor", "qual o item 3 do contrato?"):
        checar(intencao.pede_no_editor(frase) is None, f"não é levar ao editor: “{frase}”")
    docs = [{"nome": LOCACAO}, {"nome": PDF}]
    pedido = intencao.pede_no_editor("abra o contrato de locação no editor")
    checar(intencao.documento_no_editor(pedido, docs) == LOCACAO, "“o contrato de locação no editor” nomeia o arquivo")
    checar(intencao.documento_no_editor(intencao.pede_no_editor(FRASES[0]), docs) == "", "“o contrato” sozinho não escolhe arquivo")
    lido = intencao.ler("abra o contrato de locação", documentos=docs)
    checar(lido.tipo == "abrir" and lido.campos.get("nome") == LOCACAO, "“abra o contrato de locação” (sem editor) segue o abrir",
           (lido.tipo, lido.campos))

    print("\no eco “Peça: ...” do modelo")
    checar(instrucao_nuvem.eco_de_pedido("Peça: abra o contrato no editor de texto."), "“Peça: abra o contrato...” é eco")
    checar(instrucao_nuvem.eco_de_pedido("**Peça:** crie um novo documento no editor de texto para redigir o contrato."),
           "com negrito, também")
    checar(not instrucao_nuvem.eco_de_pedido("Peça, por exemplo: “crie uma tarefa”. Eu mostro o cartão."),
           "“Peça, por exemplo” numa resposta não é eco")
    checar(not instrucao_nuvem.eco_de_pedido("O prazo é de 15 dias.\nPeça: crie uma tarefa."), "resposta com mais linhas não é eco")
    checar("Nunca responda só repetindo" in instrucao_nuvem.instrucao(), "a instrução da nuvem pede frase completa")


# ------------------------------------------------------------ na tela

def test_tela(texto_do_contrato: str) -> None:
    """Na tela, o pedido abre o editor ao lado, no rascunho do contrato."""
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    sys.path.insert(0, str(RAIZ / "tests"))
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    t = e.trabalhos.criar("Contrato na tela") if hasattr(e.trabalhos, "criar") else None
    if t is None:
        print("  pulado: sem como criar a conversa")
        return
    t.dizer("pessoa", "Vamos criar um contrato de compra e venda de imóvel urbano")
    t.dizer("paulus", texto_do_contrato, proposta={"tipo": "levar_ao_editor", "titulo": "CONTRATO DE COMPRA E VENDA",
                                                   "campos": {}, "pergunta": "Vamos criar um contrato"})
    e.trabalhos.salvar(t)
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1600, "height": 1000})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(base + "/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.evaluate(f"() => abrirTrabalho('{t.id}')")
        pag.wait_for_timeout(800)
        pag.fill("#pedido", "abra o contrato no editor de texto")
        pag.click("#enviar")
        try:
            pag.wait_for_selector("#editor-lado #dp-folha", timeout=15000)
            aberto = pag.evaluate("() => document.querySelector('#dp-folha').textContent")
        except Exception as exc:  # noqa: BLE001
            aberto = "não abriu: " + str(exc)[:80]
        checar("OBEDI LOURENÇO SANTOS" in aberto, "o editor abre sozinho, ao lado, com o contrato", aberto[:120])
        rotulo = pag.evaluate("() => [...document.querySelectorAll('.proposta .rotulo')].map(x => x.textContent).pop() || ''")
        checar(rotulo == "no editor", "o cartão diz “no editor”", rotulo)
        resposta = pag.evaluate("() => [...document.querySelectorAll('.resposta .texto')].map(x => x.textContent).pop() || ''")
        checar("Abri o contrato no editor." in resposta and "Peça" not in resposta, "a resposta curta na conversa", resposta[:120])
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


# ------------------------------------------------------------ pela conversa

def main() -> int:
    print("=" * 60)
    print("  Abrir no editor o que a conversa redigiu")
    print("=" * 60)
    test_leitura()

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
    nuvem.chave = lambda estado, provedor: "di-chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    local = TestClient(api.app, headers=api.cabecalho_local())

    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / LOCACAO).write_text("CONTRATO DE LOCAÇÃO RESIDENCIAL\nLocador: Fulano. Aluguel de R$ 2.000,00.", encoding="utf-8")
    (pasta / PDF).write_text("INSTRUMENTO PARTICULAR DE PARTILHA\nITEM 3: 01 lote urbano medindo 360 m².", encoding="utf-8")
    api.estado.recarregar()

    def n_documentos() -> int:
        return int((api.estado.base.um("SELECT COUNT(*) AS n FROM documentos") or {}).get("n") or 0)

    def nova() -> str:
        return local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]

    def perguntar(tid: str, frase: str, **extra) -> dict:
        r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": frase, **extra})
        ev = eventos(r.text)
        substituido = next((d["texto"] for k, d in ev if k == "substituir"), None)
        return {"status": r.status_code, "texto": substituido if substituido is not None
                else "".join(d.get("t", "") for k, d in ev if k == "token"),
                "proposta": next((d for k, d in ev if k == "proposta"), {}), "eventos": [k for k, _ in ev],
                "salvo": local.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]}

    print("\nconversa com o contrato redigido (o caso real)")
    tid = nova()
    t = api.estado.trabalhos.obter(tid)
    t.titulo = "Contrato Obedi Lourenço"
    t.dizer("pessoa", "Vamos criar um contrato de compra e venda de imóvel urbano")
    t.dizer("paulus", CONTRATO, proposta={"tipo": "levar_ao_editor", "titulo": "CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO",
                                          "campos": {}, "pergunta": "Vamos criar um contrato de compra e venda de imóvel urbano"})
    t.dizer("pessoa", "Desculpe eu errei, extraia o item 3")
    t.dizer("paulus", "O item 3 está no documento “" + PDF + "”: 01 lote urbano.",
            proposta={"tipo": "exibir", "titulo": PDF, "campos": {"nome": PDF}})
    t.contexto["documento_em_foco"] = [PDF]
    api.estado.trabalhos.salvar(t)
    antes = n_documentos()

    ids = []
    for i, frase in enumerate(FRASES):
        # A 1ª com o PDF anexado; a 3ª no modo criativo e com a nuvem - como no caso real.
        extra = {"apenas": [PDF]} if i == 0 else ({"criativo": True, "nuvem": True} if i == 2 else {})
        r = perguntar(tid, frase, **extra)
        p = r["proposta"]
        ids.append((p.get("campos") or {}).get("id"))
        checar(r["status"] == 200 and p.get("tipo") == "editor_criado" and p.get("reaberto"),
               f"“{frase}”: o cartão que abre o editor", (r["status"], p, r["texto"]))
        checar(r["texto"] == "Abri o contrato no editor.", "resposta curta", r["texto"])
        checar("item 3" not in r["texto"] and "Peça" not in r["texto"], "nada sobre o anexo, nada de “Peça:”")
    checar(len(set(ids)) == 1 and ids[0], "as três abrem o mesmo rascunho", ids)
    checar(n_documentos() == antes + 1, "uma cópia só no editor", n_documentos() - antes)
    doc = api.estado.documentos.obter(ids[0]) or {}
    conteudo = json.dumps(doc, ensure_ascii=False, default=str)
    checar("OBEDI LOURENÇO SANTOS" in conteudo and "CLÁUSULA 2ª" in conteudo, "com o texto do contrato redigido")
    checar((doc.get("titulo") or "").lower().startswith("contrato de compra e venda"), "e o título do trabalho", doc.get("titulo"))
    checar(not fake.chamadas and not ollama.pedidos, "sem modelo: nem a nuvem nem o local",
           (len(fake.chamadas), ollama.pedidos))
    t = local.get(f"/api/trabalhos/{tid}").json()
    original = next(m for m in t["mensagens"] if (m.get("proposta") or {}).get("tipo") == "levar_ao_editor")
    checar((original.get("feito") or {}).get("id") == ids[0], "o trabalho fica marcado como levado (o botão sabe)")
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "levar_ao_editor", "campos": {}})
    checar(r.status_code == 200 and r.json()["proposta"]["campos"]["id"] == ids[0], "o botão “levar ao editor” abre o mesmo",
           r.text[:200])
    checar(n_documentos() == antes + 1, "e não duplica")

    print("\napagado do editor, o pedido cria de novo")
    api.estado.documentos.apagar(ids[0])
    r = perguntar(tid, FRASES[2])
    novo = (r["proposta"].get("campos") or {}).get("id")
    checar(novo and novo != ids[0] and "OBEDI" in json.dumps(api.estado.documentos.obter(novo) or {}, ensure_ascii=False),
           "um rascunho novo, com o texto do trabalho", novo)
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "levar_ao_editor", "campos": {}})
    checar(r.status_code == 200 and r.json()["proposta"]["campos"]["id"] == novo, "e o botão passa a abrir o novo")

    print("\na frase que nomeia um arquivo abre ele, e não o trabalho")
    r = perguntar(tid, "abra o contrato de locação no editor")
    p = r["proposta"]
    loc = api.estado.documentos.obter((p.get("campos") or {}).get("id") or 0) or {}
    checar(p.get("tipo") == "editor_criado" and "LOCAÇÃO RESIDENCIAL" in json.dumps(loc, ensure_ascii=False),
           "o contrato de locação, como rascunho", (p, r["texto"]))
    checar(LOCACAO in r["texto"] and "original" in r["texto"], "a resposta diz qual e que o original não muda", r["texto"])

    print("\nsem trabalho, com o documento anexado")
    tid2 = nova()
    antes = n_documentos()
    r = perguntar(tid2, "abra o contrato no editor", apenas=[LOCACAO])
    p = r["proposta"]
    checar(p.get("tipo") == "editor_criado" and LOCACAO in r["texto"], "o anexado abre no editor", (p, r["texto"]))
    r2 = perguntar(tid2, "abra o contrato no editor", apenas=[LOCACAO])
    checar((r2["proposta"].get("campos") or {}).get("id") == (p.get("campos") or {}).get("id") and n_documentos() == antes + 1,
           "de novo, o mesmo rascunho", (r2["proposta"], n_documentos() - antes))
    checar(not fake.chamadas and not ollama.pedidos, "sem modelo")

    print("\nsem trabalho e sem documento")
    tid3 = nova()
    antes = n_documentos()
    r = perguntar(tid3, "abra o contrato no editor de texto", criativo=True, nuvem=True)
    checar(not r["proposta"] and "ainda não há nenhum contrato redigido" in r["texto"] and "redija" in r["texto"],
           "diz que não há contrato redigido e oferece redigir", r["texto"])
    checar("Peça:" not in r["texto"] and n_documentos() == antes and not fake.chamadas, "sem inventar nada, sem modelo")
    r = perguntar(tid3, "pode abrir a minuta no editor?")
    checar("nenhuma minuta redigida" in r["texto"], "no feminino para a minuta", r["texto"])

    print("\n“abra o contrato de locação” (sem editor) segue o abrir de hoje")
    tid4 = nova()
    r = perguntar(tid4, "abra o contrato de locação")
    checar(r["proposta"].get("tipo") == "abrir" and (r["proposta"].get("campos") or {}).get("nome") == LOCACAO,
           "o cartão de abrir o arquivo", (r["proposta"].get("tipo"), r["texto"][:120]))

    print("\no eco “Peça: ...” no modo criativo")
    tid5 = nova()
    r = perguntar(tid5, "converta o contrato em PDF e mande pelo WhatsApp", criativo=True, nuvem=True)
    checar(len(fake.chamadas) == 1, "foi à nuvem", len(fake.chamadas))
    checar("substituir" in r["eventos"] and r["texto"] == instrucao_nuvem.FRASE_ECO_DE_PEDIDO,
           "a tela troca o eco pela frase honesta", r["texto"])
    checar(r["salvo"]["texto"] == instrucao_nuvem.FRASE_ECO_DE_PEDIDO, "e a conversa guarda a frase, não o eco", r["salvo"]["texto"])
    fake.resposta = "Para converter, abra o documento no editor e use Exportar."
    r = perguntar(tid5, "como converto um contrato em PDF?", criativo=True, nuvem=True)
    checar(r["salvo"]["texto"] == fake.resposta and "substituir" not in r["eventos"], "resposta de verdade fica como está",
           r["salvo"]["texto"])

    test_tela(CONTRATO)

    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s):")
        for f in _falhas:
            print("  - " + f)
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
