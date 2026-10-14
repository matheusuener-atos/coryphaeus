"""
O editor inteligente na tela (docs/PLANO-EDITOR.md, E1-E5 e E8), no Edge.

Com a nuvem de mentira respondendo operações de verdade:

  - o documento da conversa abre ao lado com os blocos nomeados, a linha
    "rascunho desta conversa" e o botão Concluir;
  - o pedido na caixa vira mudança MARCADA no lugar (sublinhado o que entra,
    riscado o que sai), a resposta da conversa leva ao lugar, e o contador de
    alterações sobe;
  - clicar na mudança abre o cartãozinho: Aceitar tira a marca e deixa o texto;
  - a cláusula nova entra depois da cláusula certa; "Desfazer esta resposta"
    tira só ela;
  - o trecho selecionado fica marcado, a barrinha aparece, e "Mais formal" vai
    ao Paulus com o trecho;
  - a pergunta é respondida com o bloco citado, que leva ao lugar;
  - concluir grava o arquivo, e o editor fica só leitura, com "Reabrir";
  - sair da conversa e voltar reabre o documento ao lado;
  - o PDF: pela conversa, o cartão oferece a versão editável, e o sim abre o
    editor com o texto;
  - nenhum erro de JavaScript.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_tela.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-editor-tela-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


RESPOSTAS: list[str] = []
RECEBIDO: list[dict] = []


def nuvem_falsa(metodo, url, cabecalhos, corpo, stream):
    RECEBIDO.append(corpo)
    texto = RESPOSTAS.pop(0) if RESPOSTAS else '{"operacoes": []}'
    pedacos = [texto[i:i + 19] for i in range(0, len(texto), 19)]

    class R:
        status_code = 200
        headers = {"x-paulus-modelo": "meta-llama/Llama-3.3-70B-Instruct"}

        def iter_lines(self, decode_unicode=True):
            import time

            for p in pedacos:
                time.sleep(0.01)
                yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
            yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 50}})
            yield "data: [DONE]"

        def close(self):
            pass
    return R()


def main() -> int:
    print("=" * 60)
    print("  O editor inteligente na tela")
    print("=" * 60)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return 0
    import requests

    import api
    import bancada
    import documento as D
    import llama_client
    import nuvem
    from test_gravacoes import _porta_livre, _subir_servidor

    nuvem.PEDIR["fn"] = nuvem_falsa
    llama_client.requests = SimpleNamespace(post=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sem modelo local")),
                                           get=lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"models": []},
                                                                              raise_for_status=lambda: None),
                                           exceptions=requests.exceptions)
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.check_ollama = lambda *a, **k: (True, "")
    api.plano_mod.liberada = lambda estado: True
    nuvem.chave = lambda estado, provedor: "chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"provedor": "paulus", "modelo": "meta-llama/Llama-3.3-70B-Instruct", "mascarar": True,
                                       "tarefas": {"conversa": True}}

    e = api.estado
    pasta = Path(e.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    blocos = D.ler_html("<h1>NOTIFICAÇÃO BETA</h1>" + "".join(
        f"<p>Parágrafo {i} da notificação sobre o débito de número {i * 13}, com texto comprido o bastante para a linha "
        f"quebrar na folha do PDF.</p>" for i in range(1, 6)))
    (pasta / "Notificação Beta.pdf").write_bytes(D.para_pdf(blocos, "Notificação Beta"))
    e.recarregar()

    t = e.trabalhos.criar("Locação na tela")
    t.dizer("pessoa", "abra a locação")
    e.trabalhos.salvar(t)
    corpo = (bancada.CORPUS / "locacao.html").read_text(encoding="utf-8")
    did = e.documentos.criar("Contrato de locação", "texto", corpo, None, trabalho_id=t.id, situacao="conversa")

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return 0
        pag = nav.new_page(viewport={"width": 1600, "height": 1000})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(base + "/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.evaluate(f"() => abrirTrabalho('{t.id}')")
        pag.wait_for_timeout(600)
        pag.evaluate(f"() => mostrarDupla({did})")
        pag.wait_for_selector("#editor-lado #dp-folha", timeout=10000)
        pag.wait_for_timeout(500)

        print("\no documento da conversa ao lado")
        info = pag.evaluate("""() => ({linha: document.querySelector('#dp-linha').textContent,
            guardar: document.querySelector('#dp-guardar').textContent,
            nomes: document.querySelectorAll('#dp-folha [data-b]').length,
            unicos: new Set([...document.querySelectorAll('#dp-folha [data-b]')].map(x => x.dataset.b)).size})""")
        checar(info["linha"].startswith("rascunho desta conversa"), "a linha diz que é rascunho desta conversa", info["linha"])
        checar(info["guardar"] == "Concluir", "o botão é Concluir", info["guardar"])
        checar(info["nomes"] == 30 and info["unicos"] == 30, "todo bloco com nome único", info)

        print("\no pedido vira mudança marcada, no lugar")
        RESPOSTAS.append(json.dumps({"entendi": "mudar o prazo", "operacoes": [
            {"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "24 (vinte e quatro) meses"}],
            "nao_fiz": [], "sugestoes": ["a caução da Cláusula 4ª equivale a 3 aluguéis"], "lacunas": []}, ensure_ascii=False))
        pag.fill("#pedido", "Mude o prazo da locação para 24 meses.")
        pag.click("#enviar")
        try:
            pag.wait_for_selector("#dp-folha [data-b='b0b0008'] ins[data-s]", timeout=15000)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        checar(ok, "a mudança entra marcada no bloco certo")
        pag.wait_for_timeout(600)
        estado_m = pag.evaluate("""() => ({ins: (document.querySelector("#dp-folha [data-b='b0b0008'] ins[data-s]") || {}).textContent,
            del: (document.querySelector("#dp-folha [data-b='b0b0008'] del[data-s]") || {}).textContent,
            outro: document.querySelector("#dp-folha [data-b='b0b0009']").textContent,
            conta: document.querySelector('#dp-alteracoes-n').textContent,
            linha: [...document.querySelectorAll('.ei-cartao .ei-c-mud .ei-c-onde')].map(x => x.textContent).pop() || '',
            botoes: document.querySelectorAll('.ei-cartao .ei-c-mud [data-ei-c]').length,
            resposta: [...document.querySelectorAll('.ei-cartao')].map(x => x.textContent).pop() || ''})""")
        checar("24 (vinte e quatro" in (estado_m["ins"] or "") and "30 (trinta" in (estado_m["del"] or ""),
               "o que entra sublinhado, o que sai riscado (palavra por palavra)", estado_m)
        checar("30 (trinta) dias" in estado_m["outro"], "o parágrafo vizinho não mudou")
        checar(estado_m["conta"] == "1", "o contador de alterações sobe", estado_m["conta"])
        checar("Cláusula 2ª" in estado_m["linha"], "o cartão da resposta: a mudança com o lugar (Cláusula 2ª)",
               estado_m["linha"])
        checar(estado_m["botoes"] == 2, "e aceitar e recusar só aquela", estado_m["botoes"])
        checar("caução" in estado_m["resposta"] and "Vale olhar também" in estado_m["resposta"],
               "e diz o que talvez devesse mudar", estado_m["resposta"][-200:])

        print("\naceitar pelo cartãozinho")
        pag.click("#dp-folha [data-b='b0b0008'] ins[data-s]")
        pag.wait_for_selector("#ei-popover", timeout=3000)
        pag.click("#ei-popover [data-ei-dec='aceitar']")
        pag.wait_for_timeout(400)
        bloco = pag.evaluate("""() => ({html: document.querySelector("#dp-folha [data-b='b0b0008']").innerHTML,
            conta: document.querySelector('#dp-alteracoes-n').textContent})""")
        checar("<ins" not in bloco["html"] and "<del" not in bloco["html"] and "24 (vinte e quatro) meses" in bloco["html"],
               "aceito: o texto novo fica, sem marca", bloco["html"][:200])
        checar(bloco["conta"] == "0", "o contador volta a zero")
        estado_linha = pag.evaluate("() => [...document.querySelectorAll('.ei-cartao .ei-c-mud .ei-c-estado')].map(x => x.textContent).pop()")
        checar(estado_linha == "aceita", "o cartão da conversa diz que a mudança foi aceita", estado_linha)
        pag.wait_for_timeout(2200)
        gravado = e.documentos.obter(did)["corpo"]
        checar("24 (vinte e quatro) meses" in gravado and "data-s=" not in gravado, "e o aceite foi gravado")

        print("\na cláusula nova no lugar certo, e desfazer a resposta")
        RESPOSTAS.append(json.dumps({"operacoes": [{"op": "inserir", "depois_de": "b0b0007", "blocos": [
            {"texto": "CLÁUSULA 3ª – DA RESCISÃO ANTECIPADA"}, {"texto": "Multa de 3 aluguéis, proporcional."}]}]},
            ensure_ascii=False))
        pag.fill("#pedido", "Inclua uma cláusula de rescisão antecipada depois da cláusula do prazo")
        pag.click("#enviar")
        try:
            pag.wait_for_selector("#dp-folha [data-sug='ins']", timeout=15000)
            pag.wait_for_selector(".ei-cartao [data-ed-acao='recusar']", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        ordem = pag.evaluate("""() => [...document.querySelectorAll('#dp-folha > *')].map(x => (x.textContent || '').slice(0, 60))""")
        i = next((k for k, x in enumerate(ordem) if "DA RESCISÃO ANTECIPADA" in x), -1)
        checar(i > 0 and ordem[i - 1].startswith("Parágrafo único. Findo o"), "depois do último bloco da cláusula do prazo",
               ordem[max(0, i - 1):i + 2])
        renum = pag.evaluate("() => (document.querySelector(\"#dp-folha [data-b='b0b0010'] ins[data-s]\") || {}).textContent || ''")
        checar("4" in renum, "a cláusula seguinte renumerada (sugestão)", renum)
        # A resposta desta rodada é a última da conversa.
        pag.locator(".ei-cartao [data-ed-acao='recusar']").last.click()
        pag.wait_for_timeout(500)
        depois = pag.evaluate("""() => ({nova: !!document.querySelector("#dp-folha [data-sug='ins']"),
            texto: document.querySelector("#dp-folha [data-b='b0b0010']").textContent,
            marcas: document.querySelectorAll('#dp-folha [data-s]').length})""")
        checar(not depois["nova"] and depois["texto"].startswith("CLÁUSULA 3ª") and depois["marcas"] == 0,
               "desfazer a resposta tira a cláusula e a renumeração", depois)

        print("\no trecho selecionado e a barrinha")
        pag.evaluate("""() => {
            const el = document.querySelector("#dp-folha [data-b='b0b0021']");
            el.scrollIntoView({block: 'center'});
            const no = el.firstChild;
            const r = document.createRange();
            r.setStart(no, 0); r.setEnd(no, 40);
            const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
            el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        }""")
        pag.wait_for_timeout(300)
        barra = pag.evaluate("() => ({chip: (document.querySelector('#ei-chip-selecao') || {}).textContent || '', "
                             "barra: !!document.querySelector('#ei-barrinha')})")
        checar("trecho selecionado" in barra["chip"] and barra["barra"], "o chip do trecho e a barrinha aparecem", barra)
        RESPOSTAS.append(json.dumps({"operacoes": [{"op": "substituir", "bloco": "b0b0021", "de": "A LOCATÁRIA declara receber",
                                                    "para": "A LOCATÁRIA declara ter recebido"}]}, ensure_ascii=False))
        antes_n = len(RECEBIDO)
        pag.click("#ei-barrinha >> text=Mais formal")
        try:
            pag.wait_for_selector("#dp-folha [data-b='b0b0021'] ins[data-s]", timeout=15000)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        lido = json.dumps(RECEBIDO[antes_n:], ensure_ascii=False)
        checar(ok and "TRECHO SELECIONADO" in lido and "Deixe este trecho mais formal" in lido,
               "“Mais formal” vai ao Paulus com o trecho, e a mudança cai nele")
        pag.evaluate("() => decidirNaFolha(document.querySelector('#dp-folha'), true)")

        print("\na pergunta, com o bloco citado")
        RESPOSTAS.append("O aluguel é de R$ 2.400,00 [b0b0011 · Cláusula 3ª], com vencimento no dia 5 [b0b0011].")
        pag.fill("#pedido", "Qual é o valor do aluguel?")
        pag.click("#enviar")
        try:
            pag.wait_for_selector(".ei-citado", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        citado = pag.evaluate("() => [...document.querySelectorAll('.ei-citado')].map(x => x.textContent)")
        checar(citado and citado[0] == "Cláusula 3ª", "a resposta cita o bloco pelo nome dele", citado)

        print("\nconcluir")
        pag.wait_for_timeout(1800)
        pag.click("#dp-guardar")
        pag.wait_for_selector(".dialogo-concluir", timeout=5000)
        pag.click('#veu-dialogo [data-dialogo="confirmar"]')
        pag.wait_for_timeout(1500)
        final = pag.evaluate("""() => ({linha: document.querySelector('#dp-linha').textContent,
            edita: document.querySelector('#dp-folha').contentEditable, botao: document.querySelector('#dp-guardar').textContent})""")
        checar(final["linha"].startswith("concluído") and final["edita"] == "false" and final["botao"] == "Reabrir",
               "concluído: só leitura, com Reabrir", final)
        doc = e.documentos.obter(did)
        checar(doc["situacao"] == "concluido" and Path(doc["arquivo"]).exists(), "o arquivo foi gravado no Acervo", doc["arquivo"])

        print("\nsair da conversa e voltar reabre o documento")
        pag.evaluate("() => document.querySelector('#nova').click()")
        pag.wait_for_timeout(600)
        pag.evaluate(f"() => abrirTrabalho('{t.id}')")
        try:
            pag.wait_for_selector("#editor-lado #dp-folha", timeout=8000)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        checar(ok, "o editor volta ao lado com a conversa")

        print("\no PDF continua PDF")
        pag.evaluate("() => fecharEditorNaConversa({ pelaPessoa: true })")
        pag.wait_for_timeout(400)
        pag.fill("#pedido", "abra a Notificação Beta no editor")
        pag.evaluate("() => definirEscopo(['Notificação Beta.pdf'])")
        pag.click("#enviar")
        try:
            pag.wait_for_selector("[data-prop='editavel']", timeout=15000)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        checar(ok, "o cartão oferece a versão editável, sem converter sozinho")
        if ok:
            pag.click("[data-prop='editavel']")
            try:
                pag.wait_for_selector("#editor-lado #dp-folha", timeout=10000)
                texto = pag.evaluate("() => document.querySelector('#dp-folha').textContent")
            except Exception:  # noqa: BLE001
                texto = ""
            checar("Parágrafo 3 da notificação" in texto and "[pagina" not in texto, "o sim abre a versão editável, texto limpo",
                   texto[:120])
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
