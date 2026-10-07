"""
A3 - a tela de agentes (frontend/js/56-agentes.js e src/agentes_tela.py).

Com dados de mentira (uma pasta temporaria) e a habilidade de perguntar
simulada - ela responde com os trechos dos documentos da demonstracao
(tools/demo/criar_demo.py) que mais parecem com a pergunta, como a busca
faria -, este portao confere:

  - criar pelo formulario gera um AGENTE.md valido, e o erro de validacao
    aparece em portugues antes de salvar;
  - criar a partir da conversa preenche os campos (as perguntas viram
    exemplos, as palavras mais repetidas viram palavras, o titulo vira o
    nome) e NAO salva sem a pessoa confirmar;
  - os dois agentes de exemplo vem com o produto, desativados, com 3 testes
    cada, e os testes passam; cada palavra de `deve_conter` esta no texto da
    demonstracao (a resposta certa pode te-la);
  - editar mostra a versao anterior (a lista de versoes e a leitura de uma);
  - na tela (Edge pelo Playwright): a lista, o formulario, o markdown com
    erro, o resultado do teste e o celular de fora - a lista e o teste
    funcionam, criar e editar nao aparecem. As capturas vao para a pasta de
    rascunho da sessao (A3_CAPTURAS, ou a temporaria).

A medida com o modelo de verdade e a parte: tools/medir.py --so-agentes
--agente <slug> com a demonstracao (docs/PROGRESSO-CONVERSA.md, A3).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_a3_tela.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-a3-"))
# A API desta rodada grava em dados de mentira: os agentes do teste nao
# aparecem no escritorio de verdade.
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import agentes as agentes_mod  # noqa: E402
import agentes_tela  # noqa: E402

CAPTURAS = Path(os.environ.get("A3_CAPTURAS") or (TMP / "capturas"))
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _plano(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")


# ------------------------------------------- a demonstracao, como a busca a veria

def _trechos_da_demo() -> list[str]:
    import criar_demo

    trechos = [texto for blocos in criar_demo.DOCUMENTOS.values() for tipo, texto in blocos if tipo == "p"]
    trechos += [p for _, paragrafos in criar_demo.MANUAL for p in paragrafos]
    return trechos


TRECHOS = _trechos_da_demo()


def _palavras(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _plano(t)) if len(w) >= 4}


def resposta_simulada(pergunta: str, quantos: int = 3) -> str:
    """
    Os trechos da demonstracao que mais dividem palavras raras com a
    pergunta (peso 1/numero de trechos com a palavra), como a busca poria no
    contexto. Nao ha modelo: a "resposta" e o que ele leria.
    """
    import math

    em_quantos: dict[str, int] = {}
    for t in TRECHOS:
        for w in _palavras(t):
            em_quantos[w] = em_quantos.get(w, 0) + 1
    p = _palavras(pergunta)
    notas = sorted(((sum(1 / math.log(1 + em_quantos[w]) for w in p & _palavras(t) if w in em_quantos), t) for t in TRECHOS),
                   key=lambda x: -x[0])
    return " ".join(t for n, t in notas[:quantos] if n > 0)


def executar_demo(ctx, pergunta: str = "", top: int = 6, apenas=None):
    texto = resposta_simulada(pergunta)
    yield "fontes", {"consultados": [], "ignorados": [], "total_contratos": 6, "apenas": [], "trechos": []}
    yield "token", {"t": texto}
    yield "fim", {}


def _ag(pasta: Path) -> agentes_mod.Agentes:
    return agentes_mod.Agentes(pasta, capacidades=["perguntar", "buscar"], perfis=["conversa", "juiz"],
                               areas=["civil", "consumidor"], leis={"cc": "Código Civil", "cdc": "Código de Defesa do Consumidor"})


# ------------------------------------------------------------------ modulo

def test_formulario() -> None:
    print("\no formulário grava um AGENTE.md válido")
    ag = _ag(TMP / "form")
    campos = {
        "nome": "Conferente de prazos", "descricao": "Confere os prazos de um contrato: vigência, aviso e vencimentos.",
        "exemplos": "quais os prazos deste contrato?\nquando vence o contrato: aviso prévio?", "palavras": "prazo, vigência; aviso",
        "acervo": "pastas", "pastas": "Cooperativa Vale Verde\nClínica Bem Viver", "formato": "tabela",
        "ferramentas": [], "instrucoes": "## Como trabalhar\nListe cada prazo com a cláusula e a página.",
        "testes": [{"pergunta": "qual o aviso para não renovar?", "deve_conter": "60, sessenta"}], "versao": 1,
    }
    md = agentes_tela.markdown_do_formulario(campos)
    v = agentes_tela.conferir(ag, md)
    checar(v["valido"], "os campos viram um AGENTE.md que a validação da A1 aceita", v.get("erro"))
    a = ag.criar(md)
    checar(not a.problema and a.nome == "Conferente de prazos" and a.fontes["acervo"] == {"pastas": ["Cooperativa Vale Verde", "Clínica Bem Viver"]}
           and a.quando_usar["palavras"] == ["prazo", "vigência", "aviso"] and a.testes[0]["deve_conter"] == ["60", "sessenta"]
           and a.saida["formato"] == "tabela", "gravado, ele carrega com os mesmos campos", a.ficha())
    checar("quando vence o contrato: aviso prévio?" in a.quando_usar["exemplos"], "dois-pontos num exemplo não quebra o YAML")
    checar(Path(a.arquivo).read_text(encoding="utf-8").startswith("---\nnome: Conferente de prazos\n"),
           "o arquivo é o formato do §2.6, campo por campo")
    ruim = agentes_tela.conferir(ag, agentes_tela.markdown_do_formulario({**campos, "ferramentas": ["apagar_arquivos"], "nome": ""}))
    checar(not ruim["valido"] and "falta o nome" in ruim["erro"] and "a ferramenta 'apagar_arquivos' não existe" in ruim["erro"],
           "sem nome e com ferramenta desconhecida: o erro em português, sem gravar", ruim.get("erro"))
    checar(len(ag.listar()) == 1, "e nada foi gravado pela conferência")
    # biblioteca e leis nao estao no formulario: editar por ele as preserva
    md2 = agentes_tela.markdown_do_formulario({**campos, "biblioteca": ["civil"], "leis": ["cc"]})
    checar(ag.validar(md2).fontes["leis"] == ["cc"], "o que o formulário não mostra (leis, biblioteca) volta como veio")


def test_da_conversa() -> None:
    print("\ncriar a partir da conversa: por regra, sem salvar")
    from jobs import Trabalho

    t = Trabalho(id="c1", titulo="Revisão do contrato de transporte")
    for texto in ("qual a multa do contrato de transporte?", "@Revisor e a multa por rescisão do contrato de transporte?",
                  "obrigado", "qual o foro do contrato de transporte?", "qual a multa do contrato de transporte?"):
        t.dizer("pessoa", texto)
        t.dizer("paulus", "resposta")
    campos = agentes_tela.rascunho_da_conversa(t)
    checar(campos["nome"] == "Revisão do contrato de transporte", "o título da conversa vira o nome", campos["nome"])
    checar(campos["exemplos"] == ["qual a multa do contrato de transporte?", "e a multa por rescisão do contrato de transporte?",
                                  "qual o foro do contrato de transporte?"],
           "as perguntas viram os exemplos, sem repetir, sem o @ e sem as de uma palavra", campos["exemplos"])
    checar(campos["palavras"][:3] == ["contrato", "transporte", "multa"] and "qual" not in campos["palavras"],
           "as palavras que mais se repetem viram as palavras (sem as de toda pergunta)", campos["palavras"])
    checar("Revisão do contrato de transporte" in campos["instrucoes"] and "qual o foro" in campos["instrucoes"],
           "as instruções dizem de onde veio e os pedidos que atende")
    ag = _ag(TMP / "conversa")
    checar(agentes_tela.conferir(ag, agentes_tela.markdown_do_formulario(campos))["valido"], "o rascunho já é um agente válido")
    checar(ag.listar() == [], "e nada foi salvo")


def test_exemplos() -> None:
    print("\nos agentes de exemplo do produto")
    ag = _ag(TMP / "exemplos")
    copiados = agentes_tela.semear_exemplos(ag)
    checar(sorted(copiados) == ["exemplo-revisor-de-contratos", "exemplo-triagem-de-consumidor"], "os dois vêm na primeira abertura", copiados)
    lista = {a.slug: a for a in ag.listar()}
    checar(all(not a.problema and not a.ativo and a.origem == "produto" for a in lista.values()),
           "desativados, válidos, com origem \"produto\"", {s: (a.problema, a.ativo, a.origem) for s, a in lista.items()})
    checar({a.nome for a in lista.values()} == {"Revisor de contratos", "Triagem de consumidor"}, "Revisor de contratos e Triagem de consumidor")
    checar(all(len(a.testes) == 3 for a in lista.values()), "cada um com 3 testes")
    todo = _plano(" ".join(TRECHOS))
    faltam = [(a.slug, x) for a in lista.values() for t in a.testes for x in t["deve_conter"] if _plano(x) not in todo]
    checar(not faltam, "cada palavra de deve_conter está no texto da demonstração", faltam)
    for a in lista.values():
        r = agentes_mod.rodar_testes(a, lambda pergunta, _a: resposta_simulada(pergunta))
        checar(r["passaram"] == 3, f"os testes de \"{a.nome}\" passam (perguntar simulado sobre a demonstração)",
               [(x["pergunta"], x["faltou"]) for x in r["resultados"] if not x["passou"]])
    # o escritorio editou um, e apagou o outro: nenhum volta como era
    rev = lista["exemplo-revisor-de-contratos"]
    ag.salvar(rev.slug, rev.markdown.replace("o foro.", "o foro e a arbitragem."))
    shutil.rmtree(ag.pasta / "exemplo-triagem-de-consumidor")
    checar(agentes_tela.semear_exemplos(ag) == [], "abrir de novo não copia nada")
    checar("arbitragem" in ag.obter(rev.slug).instrucoes and ag.obter("exemplo-triagem-de-consumidor") is None,
           "o editado fica como o escritório deixou, e o apagado não volta")


# ------------------------------------------------------------------ API

def test_api(base: str, api) -> dict:
    print("\npela API")
    from test_c1_execucao import _pedir

    lista = _pedir(base, "GET", "/api/agentes")
    slugs = {a["slug"]: a for a in lista["agentes"]}
    checar({"exemplo-revisor-de-contratos", "exemplo-triagem-de-consumidor"} <= set(slugs)
           and not any(a["ativo"] for a in slugs.values()), "os exemplos estão na pasta de dados, desativados")
    r = _pedir(base, "POST", "/api/agentes/formulario", {"campos": {"nome": "", "descricao": "x", "instrucoes": "y"}})
    checar(r["valido"] is False and "falta o nome" in r["erro"], "formulário sem nome: o erro, antes de salvar", r.get("erro"))
    r = _pedir(base, "POST", "/api/agentes/validar", {"markdown": "---\nnome: [quebrado\n---\n\ncorpo"})
    checar(r["valido"] is False and "erro de YAML" in r["erro"], "markdown quebrado: o erro em português", r.get("erro"))

    t = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Prazos da Clínica Bem Viver"})
    trab = api.estado.trabalhos.obter(t["id"])
    trab.titulo = "Prazos da Clínica Bem Viver"
    for texto in ("em que dia vence o aluguel da Clínica Bem Viver?", "até quando vai a locação da Clínica Bem Viver?"):
        trab.dizer("pessoa", texto)
        trab.dizer("paulus", "resposta")
    api.estado.trabalhos.salvar(trab)
    antes = len(_pedir(base, "GET", "/api/agentes")["agentes"])
    d = _pedir(base, "GET", f"/api/agentes/da-conversa/{t['id']}")
    checar(d["campos"]["nome"] == "Prazos da Clínica Bem Viver" and len(d["campos"]["exemplos"]) == 2 and d["valido"],
           "da conversa: o rascunho preenchido e válido", d.get("campos"))
    checar(len(_pedir(base, "GET", "/api/agentes")["agentes"]) == antes, "e nada foi salvo")
    return {"conversa": t["id"]}


# ------------------------------------------------------------------ tela

def test_tela(base: str, api, conversa: str) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    ag = api.estado.agentes
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        # Sem "networkidle": com a maquina ocupada (o modelo rodando ao lado),
        # a pagina do inicio segue pedindo coisas e a espera estourava. Pronto
        # e quando a tela de agentes ja carregou e o "sou local?" respondeu.
        ctx.set_default_timeout(60000)
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof mostrarAgentes === 'function' && typeof acessoDeFora !== 'undefined'")
        pag.evaluate("() => acessoDeFora.pronto")
        pag.wait_for_selector('.trilho [data-destino="agentes"]')
        pag.wait_for_timeout(1200)

        # a lista, pelo trilho
        pag.click('.trilho [data-destino="agentes"]')
        pag.wait_for_selector("[data-agt-linha]", timeout=10000)
        linhas = pag.evaluate("() => [...document.querySelectorAll('[data-agt-linha]')].map(l => l.textContent)")
        checar(any("Revisor de contratos" in x and "desativado" in x and "exemplo do Paulus" in x for x in linhas)
               and any("Triagem de consumidor" in x for x in linhas), "a lista mostra os exemplos: desativados, versão, origem", linhas)
        checar(all("usado 0×" in x for x in linhas), "e a medida de cada um no cartão (A4): usado N×")
        # A22: a equipe em cartões, o nível, os pontos de teste e os passos
        checar(pag.inner_text(".agt-equipe .est-titulo h1") == "Monte a sua equipe", "A22: o título do mock")
        nivel = pag.inner_text(".agt-equipe .est-nivel")
        checar("Sem equipe" in nivel and pag.inner_text(".agt-equipe .est-anel") == "0",
               "nenhum agente pronto (os exemplos vêm desativados): “Sem equipe”", nivel)
        pontos = pag.evaluate("() => [...document.querySelectorAll('[data-agt-linha]')].map(c => c.querySelectorAll('.agt-pontos i.nao').length)")
        checar(pontos and all(n == 3 for n in pontos), "um ponto por teste, vazio enquanto não rodou", pontos)
        checar(pag.is_visible(".agt-cartao-novo[data-agt-novo]"), "o último cartão é “Chamar mais um”")
        passos = pag.evaluate("() => [...document.querySelectorAll('.agt-equipe .est-passo b')].map(b => b.textContent)")
        checar(any(x.startswith("Teste e ative ") for x in passos) and len(passos) <= 4, "os passos saem dos dados: “Teste e ative”", passos)
        checar("@" in pag.inner_text(".agt-equipe .agt-chamar"), "e o cartão “Chamar pelo nome”")
        pag.click('[data-agt-linha="exemplo-revisor-de-contratos"]')
        pag.wait_for_selector(".agt-faixa", timeout=5000)
        faixa = pag.inner_text(".agt-faixa")
        checar("Entra quando alguém pede algo como" in faixa and "sem avaliação" in faixa and pag.query_selector(".agt-faixa [data-agt-abrir]"),
               "clicar no cartão abre a faixa: exemplos, ferramentas, “sem avaliação” (A4), Testar e Editar", faixa[:200])
        pag.screenshot(path=str(CAPTURAS / "a3-lista.png"))
        pag.click("[data-agt-fechar]")

        # criar pelo formulario
        pag.click("[data-agt-novo]")
        pag.wait_for_selector("#agt-nome")
        pag.fill("#agt-nome", "Conferente de locação")
        pag.fill("#agt-descricao", "Responde sobre os contratos de locação do Acervo.")
        pag.fill("#agt-exemplos", "qual o índice de reajuste do aluguel?\nquando vence o aluguel?")
        pag.fill("#agt-palavras", "aluguel, locação")
        pag.fill("#agt-instrucoes", "## Como trabalhar\nCite a cláusula e a página de cada resposta.")
        pag.click("[data-agt-teste-mais]")
        pag.fill('[data-agt-teste-pergunta="0"]', "qual índice reajusta o aluguel da Clínica?")
        pag.fill('[data-agt-teste-deve="0"]', "IGP-M")
        # A conferencia roda 350 ms depois da ultima tecla: espera a que ja
        # conhece o teste (antes dele, ela avisa "sem testes").
        pag.wait_for_function("() => { const v = document.querySelector('[data-agt-valido]'); "
                              "return v && !v.textContent.toLowerCase().includes('sem testes'); }", timeout=8000)
        checar(pag.is_enabled("[data-agt-salvar]"), "formulário preenchido: pronto para salvar")
        texto_ferr = pag.inner_text(".agt-form")
        checar("pedindo a sua confirmação" in texto_ferr, "as ferramentas dizem que cada uma pede confirmação")
        pag.evaluate("() => { document.querySelector('#agt-tela .sv-principal').scrollTop = 0; }")
        pag.screenshot(path=str(CAPTURAS / "a3-formulario.png"))
        pag.evaluate("() => { const e = document.querySelector('#agt-tela .sv-principal'); e.scrollTop = e.scrollHeight; }")
        pag.screenshot(path=str(CAPTURAS / "a3-formulario-fim.png"))
        pag.click('[data-agt-modo="markdown"]')
        pag.wait_for_selector("#agt-md")
        md = pag.input_value("#agt-md")
        checar(md.startswith("---\nnome: Conferente de locação"), "a visão do markdown traz o AGENTE.md do formulário", md[:60])
        pag.fill("#agt-md", md.replace("capacidades:\n- perguntar", "capacidades:\n- perguntar\nferramenta:\n- apagar_tudo"))
        pag.wait_for_selector("[data-agt-erro]", timeout=8000)
        erro = pag.inner_text("[data-agt-erro]")
        checar("não faz parte do formato" in erro and "ferramentas" in erro and not pag.is_enabled("[data-agt-salvar]"),
               "markdown com erro: o motivo em português, e Salvar travado", erro[:160])
        pag.screenshot(path=str(CAPTURAS / "a3-markdown-erro.png"))
        pag.fill("#agt-md", md)
        pag.wait_for_selector("[data-agt-valido]", timeout=8000)
        pag.click("[data-agt-salvar]")
        pag.wait_for_selector("[data-agt-testar]", timeout=8000)
        criado = ag.obter("conferente-de-locacao")
        checar(criado is not None and not criado.problema and not criado.ativo and criado.testes[0]["deve_conter"] == ["IGP-M"],
               "criar pelo formulário gera um AGENTE.md válido, desativado", criado.ficha() if criado else None)

        # testar (perguntar simulado sobre a demonstracao)
        pag.click("[data-agt-testar]")
        pag.wait_for_selector(".agt-testes .etiqueta.ok", timeout=15000)
        checar("1 de 1 passaram" in pag.inner_text(".agt-testes"), "Testar mostra passou, com a contagem")
        checar(ag.obter("conferente-de-locacao").medida["testes"]["passaram"] == 1, "e o resultado fica na medida do agente")

        # editar mostra a versao anterior
        pag.click("[data-agt-editar]")
        pag.wait_for_selector("#agt-instrucoes")
        pag.fill("#agt-instrucoes", "## Como trabalhar\nCite a cláusula, a página e o índice.")
        pag.wait_for_selector("[data-agt-valido]", timeout=8000)
        checar("Salvar versão 2" in pag.inner_text("[data-agt-salvar]"), "editar diz qual versão vai gravar")
        pag.click("[data-agt-salvar]")
        pag.wait_for_selector('[data-agt-versao="1"]', timeout=8000)
        pag.click('[data-agt-versao="1"]')
        pag.wait_for_selector("[data-agt-leitura]")
        antiga = pag.inner_text("[data-agt-leitura]")
        checar("Cite a cláusula e a página de cada resposta." in antiga and "versao: 1" in antiga,
               "a versão anterior aparece em Versões e é legível", antiga[-120:])
        pag.keyboard.press("Escape")

        # a partir da conversa: preenche e nao salva
        antes = len(ag.listar())
        pag.evaluate(f"() => mostrarAgentes({{ conversa: '{conversa}' }})")
        pag.wait_for_selector("[data-agt-sugerido]", timeout=8000)
        checar(pag.input_value("#agt-nome") == "Prazos da Clínica Bem Viver"
               and "em que dia vence o aluguel" in pag.input_value("#agt-exemplos")
               and "clínica" in pag.input_value("#agt-palavras").lower(), "da conversa: o formulário vem preenchido",
               [pag.input_value("#agt-nome"), pag.input_value("#agt-palavras")])
        checar(len(ag.listar()) == antes, "e nada foi salvo antes de confirmar")
        pag.click("[data-agt-cancelar] >> nth=0")
        pag.wait_for_selector("[data-agt-linha]")
        checar(len(ag.listar()) == antes, "cancelar não salva")
        checar(not erros, "sem erro de JavaScript", erros[:3])

        # o menu da conversa oferece "Criar agente desta conversa" (a linha
        # da lista de conversas, montada aqui com o que o menu le dela)
        pag.evaluate("() => { voltarAoAssistente(); }")
        pag.wait_for_timeout(600)
        pag.evaluate("(id) => { window.PAULUS_CONVERSA = Object.assign({}, window.PAULUS_CONVERSA, { agentes: true });"
                     " const l = document.createElement('div'); l.dataset.id = id; l.dataset.titulo = 'x'; l.dataset.grupo = '';"
                     " l.id = 'linha-teste-a3'; document.getElementById('centro').appendChild(l); abrirMenu(l); }", conversa)
        checar(pag.is_visible('#linha-teste-a3 [data-a="agente"]'), "o menu da conversa oferece \"Criar agente desta conversa\"")
        pag.click('#linha-teste-a3 [data-a="agente"]')
        pag.wait_for_selector("[data-agt-sugerido]", timeout=8000)
        checar(pag.input_value("#agt-nome") == "Prazos da Clínica Bem Viver" and len(ag.listar()) == antes,
               "e abre o formulário preenchido, sem salvar")
        pag.click("[data-agt-cancelar] >> nth=0")
        pag.wait_for_selector("[data-agt-linha]")

        # o celular, de fora: a lista e o teste; criar e editar nao
        cel = ctx.new_page()
        cel.set_viewport_size({"width": 390, "height": 800})
        cel.goto(base + "/", wait_until="load")
        cel.wait_for_function("() => typeof mostrarAgentes === 'function' && typeof acessoDeFora !== 'undefined'")
        cel.evaluate("() => acessoDeFora.pronto")
        cel.wait_for_timeout(800)
        # A janela local faz de conta que e o acesso de fora: a tela decide
        # pelo mesmo `acessoDeFora.local` que o 00-acesso.js preenche.
        cel.evaluate("() => { acessoDeFora.local = false; document.documentElement.classList.add('remoto'); mostrarAgentes(); }")
        cel.wait_for_selector("[data-agt-linha]", timeout=10000)
        checar(cel.is_visible("[data-agt-so-leitura]") and not cel.query_selector("[data-agt-novo]"),
               "no celular de fora: a lista, sem Novo agente, com o motivo")
        largura = cel.evaluate("() => document.documentElement.scrollWidth")
        checar(largura <= 392, "cabe em 390 px, sem rolar para o lado", largura)
        cel.screenshot(path=str(CAPTURAS / "a3-celular.png"))
        cel.click('[data-agt-linha="exemplo-revisor-de-contratos"]')
        cel.wait_for_selector(".agt-faixa [data-agt-abrir]", timeout=5000)
        cel.click('.agt-faixa [data-agt-abrir="exemplo-revisor-de-contratos"]')
        cel.wait_for_selector("[data-agt-testar]")
        checar(not cel.query_selector("[data-agt-editar]") and not cel.query_selector("[data-agt-ativar]"),
               "o agente abre com Testar, sem Editar nem Ativar")
        cel.click("[data-agt-testar]")
        cel.wait_for_selector(".agt-testes .etiqueta.ok", timeout=20000)
        checar("3 de 3 passaram" in cel.inner_text(".agt-testes"), "e o teste roda do celular: 3 de 3 no exemplo")
        cel.locator(".agt-testes").scroll_into_view_if_needed()
        cel.screenshot(path=str(CAPTURAS / "a3-celular-teste.png"))

        # a captura do resultado do teste na janela do escritorio
        pag.evaluate("() => mostrarAgentes({ slug: 'exemplo-triagem-de-consumidor' })")
        pag.wait_for_selector("[data-agt-testar]")
        pag.click("[data-agt-testar]")
        pag.wait_for_selector(".agt-testes .etiqueta.ok", timeout=20000)
        checar("3 de 3 passaram" in pag.inner_text(".agt-testes"), "Triagem de consumidor: 3 de 3 na tela")
        pag.locator(".agt-testes").scroll_into_view_if_needed()
        pag.screenshot(path=str(CAPTURAS / "a3-teste.png"))
        checar(not erros, "sem erro de JavaScript no fim", erros[:3])
        nav.close()
    print(f"  capturas em {CAPTURAS}")


def main() -> int:
    print("=" * 55)
    print("  A3 — a tela de agentes")
    print("=" * 55)
    test_formulario()
    test_da_conversa()
    test_exemplos()

    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    habilidade.executar = executar_demo
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "agentes": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    try:
        d = test_api(base, api)
        test_tela(base, api, d["conversa"])
    finally:
        habilidade.executar = antes_exec
        api.estado.prefs.dados["conversa"] = antes_prefs
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
