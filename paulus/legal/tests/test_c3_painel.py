"""
C3 - o painel "Sobre esta resposta", a barra de escopo e o que e de cada conversa.

Com a habilidade de perguntar simulada (respostas com marcas [Tn]) e as
chaves `conversa.execucao`, `pensando` e `painel` ligadas:

  - "ver fontes" numa resposta antiga mostra as fontes DAQUELA resposta: as
    citadas pelas marcas, e as outras em "Também lidas";
  - a contagem de trechos aparece em no máximo um lugar por resposta, além do
    painel;
  - o rascunho da A não aparece na B, e volta ao reabrir a A;
  - o escopo "perguntar" escolhido na A continua na A depois de ir à B e
    voltar (e fica no servidor);
  - em 390 px o painel começa fechado;
  - uma conversa concluída não mostra "Progresso";
  - a segunda pergunta com outra respondendo diz por quê e oferece esperar,
    e vai sozinha quando a primeira termina;
  - uma linha de registro não sobe a conversa na lista; a busca de conversas
    acha pelo texto das mensagens.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_c3_painel.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from test_c1_execucao import _ler_eventos, _pedir  # noqa: E402

_falhas: list[str] = []
RESPOSTAS = {
    "primeira": ([("Contrato A.docx", "multa de 10%"), ("Contrato B.docx", "foro de Belém"), ("Contrato C.docx", "prazo de 30 dias")],
                 "A multa é de 10% [T1] e o prazo é de 30 dias [T3]."),
    "segunda": ([("Contrato D.docx", "reajuste pelo IGP-M"), ("Contrato E.docx", "vigência de 36 meses")],
                "A vigência é de 36 meses [T2]."),
}


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def executar_simulado(ctx, pergunta: str = "", top: int = 6, apenas=None):
    chave = "segunda" if "vigência" in pergunta else "primeira"
    fontes, texto = RESPOSTAS[chave]
    yield "fontes", {"consultados": sorted({d for d, _ in fontes}), "ignorados": [], "total_contratos": 5, "apenas": [],
                     "trechos": [{"documento": d, "trecho": 1, "score": 1.0, "texto": x, "onde": "página 1"} for d, x in fontes]}
    yield "lendo", {"caracteres": 1200, "trechos": len(fontes), "documentos": len(fontes), "caminho": "busca",
                    "modelo": "simulado", "previsao": {"sabe": False}}
    yield "escrevendo", {"lendo_segundos": 0.2}
    for palavra in texto.split(" "):
        if ctx.parar and ctx.parar():
            return
        time.sleep(0.12 if "devagar" not in pergunta else 0.3)
        yield "token", {"t": palavra + " "}
    yield "fim", {}


def test_modulo() -> None:
    print("\no registro e a busca")
    from jobs import Trabalho

    import rotas_conversa

    t = Trabalho(id="x", titulo="Teste")
    antes = t.atualizado_em = "2026-01-01T00:00:00"
    t.registrar("uma linha qualquer", mexer_na_ordem=False)
    checar(t.atualizado_em == antes and t.atividade[0].texto == "uma linha qualquer",
           "uma linha de registro não sobe a conversa na lista")
    t.registrar("outra")
    checar(t.atualizado_em != antes, "sem a chave, como antes")

    class Lista:
        def __init__(self, itens):
            self._itens = {i.id: i for i in itens}

    a = Trabalho(id="a", titulo="Reunião de terça")
    a.dizer("pessoa", "qual o índice de reajuste do aluguel?")
    b = Trabalho(id="b", titulo="Outra coisa")
    achadas = rotas_conversa.buscar(Lista([a, b]), "indice de reajuste")
    checar([x["id"] for x in achadas] == ["a"] and achadas[0]["onde"] == "mensagem",
           "a busca acha pelo texto da mensagem, sem acento", achadas)


def test_api_e_tela() -> None:
    print("\npela API e na tela")
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    habilidade.executar = executar_simulado
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "pensando": True, "painel": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    criados = []
    try:
        a = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Conversa A do painel"})
        b = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Conversa B do painel"})
        criados += [a["id"], b["id"]]
        for pergunta in ("qual a multa e o prazo?", "qual a vigência?"):
            r = _pedir(base, "POST", f"/api/trabalhos/{a['id']}/perguntar", {"pergunta": pergunta, "apenas": ["Contrato A.docx"]},
                       stream=True)
            _ler_eventos(r)
            r.close()
        conv = _pedir(base, "GET", f"/api/trabalhos/{a['id']}")
        como = (conv["mensagens"][-1].get("cobertura") or {}).get("como") or {}
        checar(como.get("modelo") == "simulado" and "escopo" in como and "continuacao" in como,
               "a resposta guarda o modelo, o escopo e se foi continuação", como)
        achadas = _pedir(base, "GET", "/api/conversas/buscar?termo=vigencia")
        checar(a["id"] in [x["id"] for x in achadas["conversas"]], "a busca pela API acha a conversa pelo texto")
        test_tela(base, a, b)
    finally:
        habilidade.executar = antes_exec
        api.estado.prefs.dados["conversa"] = antes_prefs
        for id_ in criados:
            try:
                _pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass


def test_tela(base: str, a: dict, b: dict) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api

    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); localStorage.setItem('paulus.lateral', '1'); } catch (e) {}")
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(1500)
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_timeout(900)

        # "ver fontes" na resposta antiga
        pag.evaluate("() => document.querySelector('#centro .resposta[data-msg=\"1\"] [data-ver-trechos]').click()")
        pag.wait_for_timeout(500)
        painel = pag.evaluate("""() => ({
          titulo: document.getElementById('lat-trechos-titulo').textContent,
          citadas: document.getElementById('lat-trechos-lista').textContent,
          lidas: document.getElementById('lat-lidas').hidden ? '' : document.getElementById('lat-lidas-lista').textContent,
          como: document.getElementById('lat-como').hidden ? '' : document.getElementById('lat-como-lista').textContent,
          onde: document.getElementById('lat-onde-texto').textContent,
          progresso: document.getElementById('lat-progresso').hidden,
          props: document.getElementById('lat-propriedades').hidden,
        })""")
        checar(painel["titulo"] == "Fontes citadas" and "Contrato A.docx" in painel["citadas"] and "Contrato C.docx" in painel["citadas"]
               and "Contrato D.docx" not in painel["citadas"],
               "\"ver fontes\" na resposta antiga mostra as fontes citadas DAQUELA resposta", painel["citadas"][:80])
        checar("Contrato B.docx" in painel["lidas"] and "Contrato A.docx" not in painel["lidas"],
               "o trecho lido e não citado vai para \"Também lidas\"", painel["lidas"][:80])
        checar("simulado" in painel["como"] and "Achei trecho em 3 documentos" in painel["onde"],
               "\"Como respondi\" e \"Onde procurei\" daquela resposta (3 documentos dela, não 2 da última)",
               (painel["como"][:60], painel["onde"]))
        checar(painel["progresso"], "uma conversa concluída não mostra \"Progresso\"")
        checar(painel["props"], "motor e trechos indexados só no modo de diagnóstico")
        contas = pag.evaluate(r"""() => [...document.querySelectorAll('#centro .resposta')].map(r => (r.innerText.match(/\d+ trechos?\b/g) || []).length)""")
        checar(contas and max(contas) <= 1, "a contagem de trechos em no máximo um lugar por resposta", contas)
        barra = pag.evaluate("() => document.getElementById('registro-agora').textContent")
        checar(barra.startswith(("A próxima pergunta", "Na próxima pergunta")) and "trecho" not in barra,
               "a barra acima do campo diz onde a próxima pergunta procura, sem contagem de trechos", barra)

        # rascunho e escopo por conversa
        pag.fill("#pedido", "rascunho que é da A")
        pag.wait_for_timeout(400)
        pag.evaluate("() => { let n = 0; while (modoDoEscopo() !== 'perguntar' && n++ < 4) alternarModoDoEscopo(); }")
        pag.wait_for_timeout(400)
        pag.evaluate(f"() => abrirTrabalho('{b['id']}')")
        pag.wait_for_timeout(800)
        na_b = pag.evaluate("() => ({ pedido: document.getElementById('pedido').value, modo: modoDoEscopo() })")
        checar(na_b["pedido"] == "", "o rascunho da A não aparece na B", na_b)
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_timeout(800)
        de_volta = pag.evaluate("() => ({ pedido: document.getElementById('pedido').value, modo: modoDoEscopo() })")
        checar(de_volta["pedido"] == "rascunho que é da A", "e volta ao reabrir a A", de_volta)
        checar(de_volta["modo"] == "perguntar" and na_b["modo"] != "perguntar",
               "o escopo \"perguntar\" da A continua na A depois de ir à B", (na_b["modo"], de_volta["modo"]))
        conv = _pedir(base, "GET", f"/api/trabalhos/{a['id']}")
        checar((conv.get("contexto") or {}).get("modo_escopo") == "perguntar", "e o modo ficou no servidor")

        # duas perguntas ao mesmo tempo (de volta ao Acervo inteiro: no modo
        # "perguntar", a pergunta sem documento volta com o cartão de onde)
        pag.evaluate("() => { let n = 0; while (modoDoEscopo() !== 'acervo' && n++ < 4) alternarModoDoEscopo(); }")
        pag.fill("#pedido", "")
        pag.evaluate("() => { enviar({ texto: 'qual a multa, devagar?', apenas: ['Contrato A.docx'] }); }")
        pag.wait_for_function("() => estado.ocupado", timeout=5000)
        pag.wait_for_timeout(300)
        pag.evaluate("() => { enviar({ texto: 'e a vigência?' }); }")
        pag.wait_for_timeout(300)
        aviso = pag.evaluate("() => (document.getElementById('faixa-janela') || {}).textContent || ''")
        checar("ainda está respondendo" in aviso and "Esperar na fila" in aviso,
               "a segunda pergunta diz por que não foi e oferece esperar", aviso[:120])
        pag.evaluate("() => { const b = [...document.querySelectorAll('#faixa-janela button')].find(x => /Esperar na fila/.test(x.textContent)); if (b) b.click(); }")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .bolha-pessoa')].some(x => x.textContent === 'e a vigência?')",
                              timeout=20000)
        pag.wait_for_function("() => !estado.ocupado && [...document.querySelectorAll('#centro .resposta .texto')].pop().textContent.includes('36 meses')",
                              timeout=20000)
        checar(True, "e ela vai sozinha quando a primeira termina")

        # celular
        cel = ctx.new_page()
        cel.set_viewport_size({"width": 390, "height": 800})
        cel.goto(base + "/", wait_until="networkidle")
        cel.wait_for_timeout(1500)
        cel.evaluate(f"() => abrirTrabalho('{a['id']}')")
        cel.wait_for_timeout(900)
        checar(cel.evaluate("() => document.getElementById('lateral').hidden"), "em 390 px o painel começa fechado")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  C3 — sobre esta resposta, barra de escopo, estado por conversa")
    print("=" * 55)
    test_modulo()
    test_api_e_tela()
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
