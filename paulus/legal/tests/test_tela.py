"""
Teste de tela: abre o programa num navegador de verdade.

Existe por causa de dois erros que as outras nove suites nao pegaram, porque
nenhuma delas pinta a pagina:

  - a lista de conversas ficava com DOZE pixels de altura numa tela de 900 px.
    As conversas sumiam da barra lateral e o cabecalho do grupo aparecia
    cortado ao meio. O CSS era valido, o HTML era valido, a rota respondia 200
  - o padding das celulas da planilha era anulado por um seletor mais
    especifico, e o valor de uma coluna encostava no texto da coluna vizinha
  - o campo de pergunta da conversa aparecia no rodape das vinte telas,
    inclusive numa de Financeiro, onde nao tinha o que fazer

Os dois so aparecem depois que o navegador calcula o layout. Este arquivo faz
isso: sobe o servidor, abre cada destino do menu e mede.

Precisa do playwright e do Edge. Sem eles, o teste diz que pulou em vez de
falhar - nao e razoavel exigir navegador para rodar a suite inteira.

    python tests/test_tela.py
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def test_ponte_so_tem_metodos() -> None:
    """
    O objeto exposto ao JavaScript da janela não pode ter atributo nenhum.

    O pywebview monta `window.pywebview.api` percorrendo `dir()` do objeto e
    recursando em todo atributo que não seja função. A Ponte guardava a janela
    — `self.janela` — e o passeio entrava no controle nativo do WebView2:

        janela.native.AccessibilityObject.Bounds.Empty.Empty.Empty.Empty...

    até estourar a pilha. A proteção de ciclo do pywebview é por id do objeto e
    não pega este caso: `Rectangle.Empty` devolve um objeto novo a cada acesso.

    O estrago não parava no erro: cada passo lia uma propriedade COM do
    WebView2 de fora da thread da interface, e a janela travava. Medido numa
    janela real — o passeio ficou 4 minutos em "Não Respondendo" e não
    terminou. O usuário via isso em quase toda abertura.

    A checagem é estática de propósito: abrir a janela pra testar é sorteio,
    porque a falha depende de o controle nativo já existir na hora do passeio.
    """
    print("\na ponte do JavaScript só tem métodos")
    import inspect

    import desktop

    ponte = desktop.Ponte()
    publicos = [n for n in dir(ponte) if not n.startswith("_")]
    atributos = [
        n for n in publicos
        if not (inspect.ismethod(getattr(ponte, n)) or inspect.isfunction(getattr(ponte, n)))
    ]

    checar(bool(publicos), f"a ponte expõe alguma coisa ({publicos})")
    checar(not atributos,
           "e nenhum atributo — só o que o pywebview pode chamar",
           f"{atributos} — o pywebview vai percorrer isso e travar a janela")

    # A janela existe, mas fora da ponte.
    checar(hasattr(desktop, "_JANELA"),
           "a janela mora no módulo, onde o passeio do pywebview não chega")


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _subir_servidor(porta: int):
    import uvicorn

    import api

    api.estado.porta = porta
    servidor = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=porta, log_level="error")
    )
    threading.Thread(target=servidor.run, daemon=True).start()

    limite = time.time() + 40
    while time.time() < limite:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return servidor
        time.sleep(0.3)
    raise RuntimeError("o servidor nao subiu")


def _fim() -> int:
    """
    O resumo.

    Existe porque há três saídas do main, e todas têm que passar por aqui: uma
    checagem que falhou não pode sumir porque faltou navegador na máquina.
    """
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


def main() -> int:
    print("=" * 55)
    print("PAULUS - teste de tela")
    print("=" * 55)

    # Esta nao precisa de navegador: e leitura do codigo da janela.
    test_ponte_so_tem_metodos()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n  pulado: playwright nao instalado (pip install playwright)")
        return _fim()

    porta = _porta_livre()
    servidor = _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"

    try:
        with sync_playwright() as p:
            try:
                navegador = p.chromium.launch(channel="msedge")
            except Exception as exc:
                print(f"\n  pulado: nao achei o Edge ({str(exc)[:60]})")
                return _fim()

            pagina = navegador.new_page(viewport={"width": 1440, "height": 900})
            erros: list[str] = []
            pagina.on("pageerror", lambda e: erros.append(f"{e}"))
            pagina.on(
                "console",
                lambda m: erros.append(m.text) if m.type == "error" else None,
            )

            pagina.goto(base, wait_until="networkidle")
            pagina.wait_for_timeout(2500)

            print("\nabertura")
            checar(not erros, f"nenhum erro de JavaScript ao abrir", "; ".join(erros[:3]))
            checar(
                pagina.evaluate("() => !!document.querySelector('link[rel=icon]')"),
                "a pagina declara um icone - sem isso todo carregamento pede /favicon.ico e leva 404",
            )
            checar(
                pagina.evaluate("() => document.documentElement.dataset.tema") == "escuro",
                "abre no tema escuro, que e o desenho do produto",
            )

            print("\nbarra lateral em tela de 900 px")
            lateral = pagina.evaluate("""() => {
              const a = document.querySelector('.trabalhos');
              const lst = document.getElementById('lista-trabalhos');
              const mq = document.querySelector('.maquina');
              return {
                vaza: a.scrollHeight > a.clientHeight + 1,
                lista: Math.round(lst.getBoundingClientRect().height),
                itens: document.querySelectorAll('.item').length,
                maquina_dentro: mq.getBoundingClientRect().bottom <= window.innerHeight + 1,
                menu_itens: document.querySelectorAll('[data-destino]').length,
              };
            }""")
            checar(not lateral["vaza"], "a coluna nao transborda em silencio")
            checar(lateral["maquina_dentro"], "o painel do computador cabe na tela")
            checar(lateral["menu_itens"] == 20, f"os 20 destinos estao no menu (achou {lateral['menu_itens']})")
            if lateral["itens"]:
                checar(
                    lateral["lista"] >= 60,
                    f"a lista de conversas tem altura util ({lateral['lista']} px para "
                    f"{lateral['itens']} conversa(s))",
                )
            else:
                checar(True, "sem conversas gravadas - nada a medir na lista")

            print("\ncada destino do menu")
            ver_compositor = """() => {
              const e = document.getElementById('compositor');
              return !!e && !e.hidden && e.getBoundingClientRect().height > 0;
            }"""
            destinos = pagina.evaluate("() => DESTINOS.map(d => ({id: d.id, nome: d.nome}))")
            com_compositor = []
            for d in destinos:
                erros.clear()
                pagina.evaluate("(id) => abrirDestino(id)", d["id"])
                pagina.wait_for_timeout(900)
                conteudo = pagina.evaluate(
                    "() => document.getElementById('centro').innerText.trim().length"
                )
                vazio = conteudo == 0 and d["id"] != "conversa"
                checar(
                    not erros and not vazio,
                    f"{d['nome']} abre sem erro e com conteudo",
                    ("; ".join(erros[:2]) if erros else "a tela ficou em branco"),
                )
                if d["id"] != "conversa" and pagina.evaluate(ver_compositor):
                    com_compositor.append(d["nome"])

            print("\no campo de pergunta")
            # O compositor e da conversa. Nas outras vinte telas ele so ocupava
            # o rodape sem ter o que fazer ali.
            checar(not com_compositor, "some fora da conversa", ", ".join(com_compositor))
            pagina.evaluate("() => abrirDestino('conversa')")
            pagina.wait_for_timeout(900)
            checar(pagina.evaluate(ver_compositor), "e volta ao abrir a conversa")

            print("\nas tres telas de tres colunas")
            for destino, seletor, nome in (
                ("tarefas", ".colunas-3", "Tarefas"),
                ("calendario", ".colunas-2", "Calendário"),
                ("agendamento", ".colunas-2", "Agendamento"),
            ):
                pagina.evaluate("(id) => abrirDestino(id)", destino)
                pagina.wait_for_timeout(1400)
                colunas = pagina.evaluate(
                    "(sel) => { const g = document.querySelector(sel);"
                    " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }",
                    seletor,
                )
                checar(colunas >= 2, f"{nome} abre em colunas (achou {colunas})")

            # Uma regra `.hoje { margin-top: 22px }` da tela de Aprovacoes vazava
            # para qualquer elemento marcado como "hoje": a celula de hoje do
            # calendario ficava 22 px abaixo das vizinhas, e o cabecalho da
            # semana quebrava em duas linhas. Classe generica com layout dentro
            # e a forma mais silenciosa de uma tela estragar outra.
            print("\ncolisao de classe generica")
            pagina.evaluate("() => abrirDestino('calendario')")
            pagina.wait_for_timeout(1400)
            desvio = pagina.evaluate("""() => {
              const h = document.querySelector('.cel.hoje');
              const o = document.querySelector('.cel:not(.hoje):not(.fora)');
              if (!h || !o) return null;
              return {hoje: getComputedStyle(h).marginTop, outra: getComputedStyle(o).marginTop};
            }""")
            checar(
                desvio is None or desvio["hoje"] == desvio["outra"],
                "a celula de hoje nao anda por causa de regra de outra tela",
                str(desvio),
            )

            pagina.evaluate("""() => { const b = document.querySelector('[data-vista=semana]');
              if (b) b.click(); }""")
            pagina.wait_for_timeout(1200)
            alturas = pagina.evaluate(
                "() => [...document.querySelectorAll('.semana-cabeca')]"
                ".map(e => Math.round(e.getBoundingClientRect().height))"
            )
            checar(
                len(set(alturas)) <= 1,
                f"os cabecalhos da semana tem a mesma altura ({sorted(set(alturas))})",
            )

            print("\ncelulas da planilha")
            id_planilha = pagina.evaluate("""async () => {
              const r = await fetch('/api/documentos', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({titulo: 'teste de tela', tipo: 'planilha'})});
              const d = await r.json();
              await fetch('/api/planilha/' + d.id + '/celula', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({aba: 0, ref: 'B2', dados: {valor: '12.000,00', formato: 'moeda'}})});
              await fetch('/api/planilha/' + d.id + '/celula', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({aba: 0, ref: 'C2', dados: {valor: 'pago'}})});
              return d.id;
            }""")
            pagina.evaluate("(id) => abrirPlanilha(id)", id_planilha)
            pagina.wait_for_timeout(1500)

            folga = pagina.evaluate("""() => {
              const b = document.querySelector('[data-ref="B2"]');
              const c = document.querySelector('[data-ref="C2"]');
              if (!b || !c) return null;
              const pb = parseFloat(getComputedStyle(b).paddingRight);
              const pc = parseFloat(getComputedStyle(c).paddingLeft);
              return {direita: pb, esquerda: pc};
            }""")
            checar(
                folga is not None and folga["direita"] >= 4 and folga["esquerda"] >= 4,
                "o valor de uma coluna nao encosta no texto da coluna vizinha",
                str(folga),
            )
            pagina.evaluate(
                "(id) => fetch('/api/documentos/' + id, {method: 'DELETE'})", id_planilha
            )

            navegador.close()
    finally:
        servidor.should_exit = True

    return _fim()


if __name__ == "__main__":
    raise SystemExit(main())
