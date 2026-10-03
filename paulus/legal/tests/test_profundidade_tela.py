"""
A profundidade e o módulo de perguntas na tela (js/92-entrevista.js), no
Edge, pelo Playwright, com a nuvem de mentira (sem rede):

  - a pílula do nível aparece com a nuvem ligada, no padrão Advogado; o menu
    traz os cinco níveis na ordem, com o técnico discreto e o consumo; a
    escolha fica guardada e vai com a pergunta;
  - o pedido de trabalho abre o módulo de perguntas que o modelo montou: a
    pergunta, o porquê, as opções, "Não sei", "Decida por mim", "Depois" e as
    ações do cartão;
  - responder envia as respostas legíveis na conversa e, com o que basta, o
    trabalho chega com o cartão "trabalho pronto" e o nível na assinatura;
  - o cartão respondido não se oferece de novo ao reabrir a conversa;
  - sem erro de página, no claro, no escuro e no celular (390 px).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_profundidade_tela.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-prof-tela-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
CAPTURAS = Path(os.environ.get("PROF_CAPTURAS") or (TMP / "capturas"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


ENTREVISTA = {
    "decisao": "perguntar", "trabalho": "contrato de arrendamento rural", "entendimento": "Um contrato de arrendamento rural.",
    "abertura": "Claro. Antes de redigir, há alguns pontos que mudam bastante a estrutura desse contrato. Vamos defini-los.",
    "titulo": "Vamos definir esse contrato",
    "perguntas": [
        {"id": "objeto", "pergunta": "Qual é o objeto do arrendamento?", "porque": "Muda as obrigações de uso e conservação.",
         "tipo": "escolha", "opcoes": ["Área rural", "Maquinário", "Área e maquinário"], "sugestao": "Área rural"},
        {"id": "situacoes", "pergunta": "Que situações especiais devemos prever?", "porque": "Cada uma vira uma cláusula própria.",
         "tipo": "multipla", "opcoes": ["Benfeitorias", "Subarrendamento", "Garantia", "Rescisão antecipada"]},
        {"id": "prazo", "pergunta": "Prazo pretendido", "porque": "O Estatuto da Terra fixa prazos mínimos por atividade.",
         "tipo": "texto"},
        {"id": "preco", "pergunta": "Valor anual", "porque": "O preço tem teto legal no arrendamento.", "tipo": "valor"}],
    "premissas": ["foro da comarca do imóvel"]}


def main() -> int:
    print("=" * 60)
    print("  Profundidade e módulo de perguntas — a tela")
    print("=" * 60)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return 0
    from test_gravacoes import _porta_livre, _subir_servidor

    import api
    import llama_client
    import nuvem
    import requests

    antes = dict(os.environ)
    import test_profundidade as tp
    os.environ.clear()
    os.environ.update(antes)

    fake = tp.Nuvem()
    nuvem.PEDIR["fn"] = fake
    ollama = tp.Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    api.plano_mod.liberada = lambda estado: True
    nuvem.chave = lambda estado, provedor: "di-chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    porta = _porta_livre()
    _subir_servidor(porta)
    api.plano_mod.liberada = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    base = f"http://127.0.0.1:{porta}"
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return 0
        ctx = nav.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        ctx.set_default_timeout(60000)
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof profundidadeDoEnvio === 'function' && typeof acessoDeFora !== 'undefined'")
        pag.evaluate("() => acessoDeFora.pronto")

        print("\na pílula e o menu")
        pag.wait_for_selector("#pilula-profundidade", timeout=20000)
        checar(pag.inner_text("#pilula-profundidade").strip().endswith("Advogado"), "a pílula, no padrão Advogado",
               pag.inner_text("#pilula-profundidade"))
        pag.click("#pilula-profundidade")
        pag.wait_for_selector("#menu-profundidade")
        nomes = pag.evaluate("() => [...document.querySelectorAll('.mp-nivel .mp-texto > b')].map(x => x.childNodes[0].textContent.trim())")
        checar(nomes == ["Estagiário", "Bacharel", "Advogado", "Juiz", "Ministro"], "os cinco níveis, na ordem", nomes)
        tecnico = pag.inner_text("#menu-profundidade")
        checar("da franquia" in tecnico and "revisa" in tecnico and "Entender antes de trabalhar" in tecnico,
               "o técnico discreto, o consumo e o 'entender antes'")
        pag.screenshot(path=str(CAPTURAS / "menu-profundidade.png"))
        pag.click('[data-prof-nivel="juiz"]')
        checar(pag.inner_text("#pilula-profundidade").strip().endswith("Juiz"), "escolhido o Juiz")
        checar(pag.evaluate("() => localStorage.getItem('paulus.profundidade')") == "juiz", "a escolha fica guardada")
        checar(pag.evaluate("() => profundidadeDoEnvio().profundidade") == "juiz", "e vai com a pergunta")

        print("\no módulo de perguntas")
        fake.entrevistas = [dict(ENTREVISTA), {"decisao": "executar", "abertura": "Perfeito. Já tenho o necessário."}]
        fake.revisao = {"problemas": [{"gravidade": "media", "onde": "cláusula 4", "o_que": "falta o prazo de aviso",
                                       "correcao": "incluir 6 meses"}], "refazer": True}
        pag.fill("#pedido", "Preciso fazer um contrato de arrendamento rural")
        pag.click("#enviar")
        pag.wait_for_selector(".proposta.entrevista .ent-q", timeout=30000)
        qs = pag.evaluate("() => [...document.querySelectorAll('.ent-q .ent-titulo')].map(x => x.textContent)")
        checar(qs == [q["pergunta"] for q in ENTREVISTA["perguntas"]], "as perguntas que o modelo montou para este pedido", qs)
        checar(pag.locator(".ent-porque").count() == 4, "cada pergunta com o porquê")
        checar(pag.locator(".ent-q").first.locator(".ent-op").count() == 3 and pag.locator(".ent-sug").count() == 1,
               "as opções, com a sugerida marcada")
        modos = pag.evaluate("() => [...document.querySelectorAll('.ent-q')[0].querySelectorAll('.ent-modo')].map(x => x.textContent)")
        checar(modos == ["Não sei", "Decida por mim", "Depois"], "em toda pergunta: Não sei, Decida por mim, Depois", modos)
        acoes = pag.evaluate("() => [...document.querySelectorAll('.ent-acoes button')].map(x => x.textContent)")
        checar(acoes == ["Enviar respostas", "Continuar com o que temos", "Decida por mim", "Quero explicar com minhas palavras",
                         "Responder depois"], "as saídas do cartão", acoes)
        checar("Claro. Antes de redigir" in pag.inner_text("#centro"), "a abertura natural, antes do cartão")
        checar("foro da comarca" in pag.inner_text(".ent-premissas"), "o que vai assumir, à vista")
        for tema in ("claro", "escuro"):
            pag.evaluate("() => aplicarTema('" + tema + "')")
            pag.wait_for_timeout(300)
            pag.locator(".proposta.entrevista").screenshot(path=str(CAPTURAS / f"entrevista-{tema}.png"))
        pag.evaluate("() => aplicarTema('claro')")

        print("\nresponder e receber o trabalho")
        pag.click('.ent-q >> nth=0 >> .ent-op >> text="Área rural"')
        pag.click('.ent-q >> nth=1 >> .ent-op >> text="Benfeitorias"')
        pag.click('.ent-q >> nth=1 >> .ent-op >> text="Garantia"')
        pag.fill('.ent-q >> nth=2 >> input', "5 anos")
        pag.click('.ent-q >> nth=3 >> .ent-modo >> text="Decida por mim"')
        pag.click('[data-ent-acao="explicar"]')
        pag.fill(".ent-explicar textarea", "O arrendatário vai plantar soja.")
        pag.click('[data-ent-acao="responder"]')
        pag.wait_for_selector(".proposta.trabalho-pronto", timeout=60000)
        pag.wait_for_timeout(500)
        texto = pag.inner_text("#centro")
        checar("Qual é o objeto do arrendamento? — Área rural" in texto and "Benfeitorias, Garantia" in texto
               and "decida por mim" in texto and "plantar soja" in texto, "as respostas, legíveis na conversa")
        checar("CONTRATO REVISTO" in texto and "Perfeito. Já tenho o necessário." in texto, "o trabalho, na versão revista")
        corpo = [c["corpo"] for c in fake.chamadas if c["etapa"] == "entrevista"][-1]
        enviado = corpo["messages"][-1]["content"]
        checar("Área rural" in enviado and "5 anos" in enviado and "decida por mim" in enviado and "soja" in enviado,
               "a segunda análise recebeu as respostas e a explicação")
        checar([c["etapa"] for c in fake.chamadas][-4:] == ["plano", "redacao", "revisao", "reescrita"], "o Juiz planejou, redigiu, revisou e reescreveu",
               [c["etapa"] for c in fake.chamadas][-5:])
        assinatura = pag.locator(".resposta .ass-meta").last.inner_text()
        checar(assinatura.find("Juiz") >= 0, "a assinatura diz o nível", assinatura)
        checar("revisão apontou" in pag.inner_text(".proposta.trabalho-pronto"), "o cartão diz o que a revisão apontou")
        checar(pag.locator(".proposta.entrevista button:enabled").count() == 0, "o cartão respondido trava")
        pag.screenshot(path=str(CAPTURAS / "trabalho-pronto.png"), full_page=True)

        print("\nao reabrir a conversa")
        tid = pag.evaluate("() => estado.trabalhoId")
        pag.reload(wait_until="load")
        pag.wait_for_function("() => typeof abrirTrabalho === 'function' || typeof mostrarTrabalho === 'function'")
        pag.evaluate("(id) => (typeof abrirTrabalho === 'function' ? abrirTrabalho(id) : mostrarTrabalho(id))", tid)
        pag.wait_for_selector(".proposta.entrevista", timeout=20000)
        checar(pag.locator(".proposta.entrevista.respondida").count() == 1 and pag.locator(".proposta.entrevista .ent-acoes").count() == 0,
               "o cartão respondido volta como resumo, sem ações")
        checar(pag.locator(".proposta.trabalho-pronto [data-levar-editor]").count() == 1, "o cartão de levar ao editor volta")
        checar(not erros, "sem erro na página", erros)

        print("\nno celular")
        pc = ctx.new_page()
        pc.set_viewport_size({"width": 390, "height": 844})
        erros_cel: list[str] = []
        pc.on("pageerror", lambda e: erros_cel.append(str(e)))
        pc.goto(base + "/", wait_until="load")
        pc.wait_for_function("() => typeof profundidadeDoEnvio === 'function' && typeof acessoDeFora !== 'undefined'")
        pc.evaluate("() => acessoDeFora.pronto")
        fake.entrevistas = [dict(ENTREVISTA)]
        pc.wait_for_selector("#pilula-profundidade", timeout=20000)
        pc.fill("#pedido", "Preciso fazer um contrato de arrendamento rural")
        pc.click("#enviar")
        pc.wait_for_selector(".proposta.entrevista .ent-q", timeout=30000)
        pc.wait_for_timeout(400)
        largura = pc.evaluate("() => document.documentElement.scrollWidth")
        checar(largura <= 390, "sem rolagem para o lado em 390 px", largura)
        pc.screenshot(path=str(CAPTURAS / "entrevista-celular.png"), full_page=True)
        pc.click("#pilula-profundidade")
        pc.wait_for_selector("#menu-profundidade")
        caixa = pc.evaluate("() => { const r = document.getElementById('menu-profundidade').getBoundingClientRect(); return [r.left, r.right]; }")
        checar(caixa[0] >= 0 and caixa[1] <= 390, "o menu cabe na tela do celular", caixa)
        checar(not erros_cel, "sem erro na página (celular)", erros_cel)
        nav.close()
    print(f"\ncapturas em {CAPTURAS}")
    print()
    if _falhas:
        print(f"FALHARAM {len(_falhas)}: " + "; ".join(_falhas))
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
