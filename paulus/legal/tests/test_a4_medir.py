"""
A4 - medir os agentes (src/agentes_medida.py, tools/medir.py --agentes).

Com dados de mentira e a habilidade de perguntar simulada (ela acerta ou
erra conforme o teste manda):

  - um teste de agente que falha tira o agente da escolha automatica: os
    exemplos e as palavras nao o escolhem mais, a barra diz por que, e a
    ficha e a tela mostram "precisa de revisão" com o que faltou;
  - a escolha manual continua possivel: pelo seletor (agente=slug) e por
    "@Nome", na conversa;
  - revisar tira o aviso: rodar os testes de novo e passar, ou salvar uma
    versao nova (o resultado da versao antiga deixa de valer);
  - as contas do painel: vezes usado (a pergunta que sai com o agente),
    vezes "nao usar" (so quando havia sugestao) e "sem avaliação" no lugar
    das respostas ruins - o programa nao avalia resposta;
  - tools/medir.py --agentes roda os testes de cada agente ativo pela rota
    de testar e grava o resultado como o ultimo do agente.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_a4_medir.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-a4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ / "tools"))

import agente_na_conversa as escolha_mod  # noqa: E402
import agentes as agentes_mod  # noqa: E402
import agentes_medida  # noqa: E402

CAPTURAS = Path(os.environ.get("A3_CAPTURAS") or (TMP / "capturas"))
_falhas: list[str] = []
PASSAR = {"sim": False}

CONFERENTE = """---
nome: Conferente de locação
descricao: Responde sobre os contratos de locação do Acervo.
quando_usar:
  exemplos:
    - qual o índice de reajuste do aluguel?
  palavras: [aluguel]
capacidades: [perguntar]
ferramentas: []
fontes:
  acervo: acervo
saida:
  formato: texto
modelo: conversa
testes:
  - pergunta: qual índice reajusta o aluguel da Clínica?
    deve_conter: [IGP-M]
  - pergunta: em que dia vence o aluguel da Clínica?
    deve_conter: [dia 5]
versao: 1
---

Cite a cláusula e a página.
"""


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def responder(pergunta: str) -> str:
    """Acerta tudo com PASSAR ligado; desligado, esquece o índice (o que um modelo trocado faria)."""
    if PASSAR["sim"]:
        return "O aluguel é reajustado pelo IGP-M e vence no dia 5 de cada mês."
    return "O aluguel vence no dia 5 de cada mês; o reajuste é anual."


def executar_simulado(ctx, pergunta: str = "", top: int = 6, apenas=None):
    yield "fontes", {"consultados": [], "ignorados": [], "total_contratos": 1, "apenas": [], "trechos": []}
    yield "lendo", {"caracteres": 100, "trechos": 1, "documentos": 1, "caminho": "busca", "modelo": "simulado",
                    "previsao": {"sabe": False}}
    yield "escrevendo", {"lendo_segundos": 0.1}
    yield "token", {"t": responder(pergunta)}
    yield "fim", {}


def test_modulo() -> None:
    print("\nescolha e medida (módulo)")
    pasta = TMP / "modulo"
    ag = agentes_mod.Agentes(pasta, capacidades=["perguntar"], perfis=["conversa"], areas=["civil"], leis={"cc": "CC"},
                             medidas=agentes_medida.Medidas(pasta))
    a = ag.criar(CONFERENTE)
    ag.ativar(a.slug)
    exemplo = "qual o índice de reajuste do aluguel?"
    checar(escolha_mod.escolher(exemplo, ag.ativos()).agente.slug == a.slug, "antes de medir, o exemplo escolhe o agente")

    PASSAR["sim"] = False
    r = agentes_mod.rodar_testes(ag.obter(a.slug), lambda p, _a: responder(p))
    ag.medidas.registrar_teste(a.slug, r)
    x = ag.obter(a.slug)
    checar(r["passaram"] == 1 and x.precisa_revisao and "faltou IGP-M" in x.revisao_motivo,
           "um teste que falha: \"precisa de revisão\", com o que faltou", x.revisao_motivo)
    e = escolha_mod.escolher(exemplo, ag.ativos())
    checar(e.agente is None and [y.slug for y in e.em_revisao] == [a.slug],
           "e ele sai da escolha automática (exemplo e palavras), dizendo por quê", (e.agente, e.em_revisao))
    checar(escolha_mod.escolher("quando vence o aluguel?", ag.ativos()).agente is None, "nem pelas palavras")
    checar(escolha_mod.escolher(exemplo, ag.ativos(), pedido=a.slug).agente.slug == a.slug,
           "a escolha manual (o seletor) continua possível")
    e = escolha_mod.escolher("@Conferente " + exemplo, ag.ativos())
    checar(e.agente is not None and e.como == "arroba", "e \"@Nome\" também")

    PASSAR["sim"] = True
    ag.medidas.registrar_teste(a.slug, agentes_mod.rodar_testes(ag.obter(a.slug), lambda p, _a: responder(p)))
    checar(not ag.obter(a.slug).precisa_revisao and escolha_mod.escolher(exemplo, ag.ativos()).agente is not None,
           "testar de novo e passar: volta à escolha automática")

    PASSAR["sim"] = False
    ag.medidas.registrar_teste(a.slug, agentes_mod.rodar_testes(ag.obter(a.slug), lambda p, _a: responder(p)))
    checar(ag.obter(a.slug).precisa_revisao, "falhou de novo: precisa de revisão")
    ag.salvar(a.slug, CONFERENTE.replace("Cite a cláusula e a página.", "Cite a cláusula, a página e o índice."))
    x = ag.obter(a.slug)
    checar(not x.precisa_revisao and x.medida["testes"]["da_versao_atual"] is False,
           "salvar uma versão nova também revisa: o resultado era da versão anterior", x.medida["testes"])

    ag.medidas.contar(a.slug, "usado")
    ag.medidas.contar(a.slug, "usado")
    ag.medidas.contar(a.slug, "nao_usar")
    m = ag.obter(a.slug).medida
    checar(m["usado"] == 2 and m["nao_usar"] == 1 and m["ruins"] is None and "sem avaliação" in m["ruins_aviso"],
           "as contas do painel: usado, \"não usar\" e sem avaliação (não zero)", m)
    checar(ag.medidas.contar("nao-existe", "usado") == 0 and not (pasta / "nao-existe").exists(),
           "contar para um agente que não existe não cria pasta")


def test_conversa_e_medir() -> None:
    print("\npela API, na conversa e no tools/medir.py")
    from test_c1_execucao import _ler_eventos, _pedir
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    habilidade.executar = executar_simulado
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "agentes": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    try:
        a = _pedir(base, "POST", "/api/agentes", {"markdown": CONFERENTE})
        slug = a["slug"]
        _pedir(base, "POST", f"/api/agentes/{slug}/ativar", {})
        exemplo = "qual o índice de reajuste do aluguel?"

        def perguntar(t_id, texto, **extra):
            r = _pedir(base, "POST", f"/api/trabalhos/{t_id}/perguntar", {"pergunta": texto, **extra}, stream=True)
            ev = _ler_eventos(r)
            r.close()
            como = ((_pedir(base, "GET", f"/api/trabalhos/{t_id}")["mensagens"][-1].get("cobertura") or {}).get("como") or {})
            return ev, como

        t = _pedir(base, "POST", "/api/trabalhos", {"pedido": "teste A4"})
        _, como = perguntar(t["id"], exemplo)
        checar(como.get("agente_slug") == slug and como.get("agente_como") == "exemplo", "antes de medir, o exemplo usa o agente", como)

        PASSAR["sim"] = False
        r = _pedir(base, "POST", f"/api/agentes/{slug}/testar")
        checar(r["passaram"] == 1 and r["total"] == 2 and r["precisa_revisao"] and "faltou IGP-M" in r["revisao_motivo"],
               "testar e falhar: a rota diz que precisa de revisão, com o motivo", r.get("revisao_motivo"))
        lista = _pedir(base, "GET", "/api/agentes")
        ficha = next(x for x in lista["agentes"] if x["slug"] == slug)
        checar(ficha["precisa_revisao"] and lista["contagem"]["precisa_revisao"] == 1 and ficha["medida"]["testes"]["passaram"] == 1,
               "a lista mostra o aviso e o acerto", ficha["medida"])
        s = _pedir(base, "GET", "/api/agentes/sugerir?texto=" + "qual%20o%20%C3%ADndice%20de%20reajuste%20do%20aluguel%3F")
        checar(s.get("agente") is None and [x["slug"] for x in s.get("em_revisao") or []] == [slug]
               and any(x["slug"] == slug and x["precisa_revisao"] for x in s.get("ativos") or []),
               "a barra não o sugere, diz por quê, e ele continua no seletor", s)
        _, como = perguntar(t["id"], exemplo)
        checar(not como.get("agente"), "na conversa, o exemplo não o escolhe mais sozinho", como.get("agente_como"))
        _, como = perguntar(t["id"], exemplo, agente=slug)
        checar(como.get("agente_slug") == slug and como.get("agente_como") == "pedido", "escolhido no seletor, ele responde", como)
        _, como = perguntar(t["id"], "@Conferente " + exemplo)
        checar(como.get("agente_slug") == slug and como.get("agente_como") == "arroba", "e por \"@Nome\" também", como)
        usado = api.estado.agentes.obter(slug).medida["usado"]
        checar(usado == 3, "vezes usado: as três perguntas que saíram com ele", usado)
        perguntar(t["id"], exemplo, sem_agente=True)
        checar(api.estado.agentes.obter(slug).medida["nao_usar"] == 0,
               "\"sem agente\" sem sugestão (ele estava em revisão) não conta como \"não usar\"")

        tela_da_revisao(base, api, slug)

        # tools/medir.py --agentes: pela rota, e o resultado fica guardado
        import medir

        PASSAR["sim"] = True
        medidos = medir.medir_agentes(base)
        m = api.estado.agentes.obter(slug)
        checar([x["slug"] for x in medidos] == [slug] and medidos[0]["passaram"] == 2 and not m.precisa_revisao
               and m.medida["testes"]["origem"] == "medir", "tools/medir.py --agentes: roda os ativos e grava o último resultado",
               medidos)
        s = _pedir(base, "GET", "/api/agentes/sugerir?texto=" + "qual%20o%20%C3%ADndice%20de%20reajuste%20do%20aluguel%3F")
        checar((s.get("agente") or {}).get("slug") == slug, "passou de novo: volta a ser sugerido")
        perguntar(t["id"], exemplo, sem_agente=True)
        checar(api.estado.agentes.obter(slug).medida["nao_usar"] == 1, "\"sem agente\" com a sugestão: conta como \"não usar\"")
        _pedir(base, "DELETE", f"/api/trabalhos/{t['id']}")
    finally:
        habilidade.executar = antes_exec
        api.estado.prefs.dados["conversa"] = antes_prefs


def tela_da_revisao(base: str, api, slug: str) -> None:
    """O aviso na tela: a etiqueta na lista e o motivo na ficha do agente."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado (tela): playwright não instalado")
        return
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado (tela): não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.set_default_timeout(60000)
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof mostrarAgentes === 'function' && typeof acessoDeFora !== 'undefined'")
        pag.evaluate("() => acessoDeFora.pronto")
        pag.evaluate("() => mostrarAgentes()")
        pag.wait_for_selector(f'[data-agt-linha="{slug}"] [data-agt-revisao]')
        checar(True, "a lista mostra \"precisa de revisão\"")
        pag.click(f'[data-agt-abrir="{slug}"]')
        pag.wait_for_selector("[data-agt-aviso-revisao]")
        aviso = pag.inner_text("[data-agt-aviso-revisao]")
        checar("faltou IGP-M" in aviso and "não é escolhido sozinho" in aviso, "a ficha diz o que faltou e o que fazer", aviso)
        medida = pag.inner_text(".agt-medida")
        checar("1 de 2" in medida and "sem avaliação" in medida and "Vezes usado" in medida,
               "o painel do agente: acerto, usado, “não usar” e sem avaliação", medida)
        pag.screenshot(path=str(CAPTURAS / "a4-revisao.png"))
        # a barra acima do campo: ele fica no seletor, marcado, e a barra diz
        # por que nao foi escolhido
        t = api.estado.trabalhos.criar("barra A4") if hasattr(api.estado.trabalhos, "criar") else None
        if t is not None:
            pag.evaluate(f"() => abrirTrabalho('{t.id}')")
            pag.wait_for_timeout(500)
            pag.fill("#pedido", "qual o índice de reajuste do aluguel?")
            pag.wait_for_selector("[data-barra-revisao]", timeout=8000)
            opcoes = pag.inner_text("[data-barra-agente]")
            checar("precisa de revisão" in opcoes, "a barra: no seletor, marcado; e diz que não o escolheu sozinho", opcoes)
        checar(not erros, "sem erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  A4 — medir os agentes")
    print("=" * 55)
    test_modulo()
    test_conversa_e_medir()
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
