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
            # A primeira abertura (boas-vindas) cobre a tela enquanto nao ha
            # nome cadastrado. O teste e da casca: marca como vista, e testa
            # o passeio a parte, por #boasvindas.
            pagina.add_init_script(
                "try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}"
            )
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
                pagina.evaluate("() => document.documentElement.dataset.tema") == "claro",
                "abre no tema claro, que e o padrao do desenho",
            )

            # A casca do desenho (docs/ui/01-shell.md): trilho de 64 px que
            # cabe em 900 px de altura, e um menu que abre por passagem do
            # mouse POR CIMA do conteudo - a coluna nao pode se mexer.
            print("\ncasca em tela de 900 px")
            casca = pagina.evaluate("""() => {
              const t = document.querySelector('.trilho');
              const m = document.getElementById('menu-flutuante');
              const ids = [...document.querySelectorAll('[data-destino]')].map(e => e.dataset.destino);
              return {
                largura: Math.round(t.getBoundingClientRect().width),
                vaza: t.scrollHeight > t.clientHeight + 1,
                fechado: getComputedStyle(m).opacity === '0',
                coluna: Math.round(document.getElementById('conversa-col').getBoundingClientRect().left),
                destinos: [...new Set(ids)],
              };
            }""")
            checar(casca["largura"] == 64, f"o trilho tem 64 px (achou {casca['largura']})")
            checar(not casca["vaza"], "o trilho cabe na tela sem transbordar")
            checar(casca["fechado"], "o menu comeca fechado")
            checar(casca["coluna"] == 64, "a coluna de conteudo comeca onde o trilho termina")

            # mouse.move, e nao hover(): o menu aberto cobre o trilho, e o
            # hover() do Playwright espera o ponteiro alcancar o alvo.
            pagina.mouse.move(32, 450)
            pagina.wait_for_timeout(450)
            aberto = pagina.evaluate("""() => ({
              opacidade: getComputedStyle(document.getElementById('menu-flutuante')).opacity,
              coluna: Math.round(document.getElementById('conversa-col').getBoundingClientRect().left),
            })""")
            checar(aberto["opacidade"] == "1", "passar o mouse no trilho abre o menu")
            checar(aberto["coluna"] == casca["coluna"], "e o conteudo nao se desloca")
            pagina.mouse.move(760, 460)
            pagina.wait_for_timeout(450)

            destinos = pagina.evaluate("() => DESTINOS.map(d => ({id: d.id, nome: d.nome}))")
            # Destino absorvido por uma tela nova (Organizar virou visao do
            # Acervo) nao tem botao proprio: abre pela tela que o absorveu.
            absorvidos = set(pagina.evaluate("() => [...ABSORVIDOS]"))
            faltando = [
                d["nome"] for d in destinos
                if d["id"] not in casca["destinos"] and d["id"] not in absorvidos
            ]
            checar(
                not faltando,
                f"os {len(destinos)} destinos do servidor estao alcancaveis pela casca",
                ", ".join(faltando),
            )

            # Aceite da fase 0 do desenho: Ctrl+K leva ao campo de pedido.
            pagina.keyboard.press("Control+K")
            pagina.wait_for_timeout(200)
            checar(
                pagina.evaluate("() => document.activeElement && document.activeElement.id") == "pedido",
                "Ctrl+K foca a caixa de pedido",
            )

            print("\nprimeira abertura")
            # Com uma query nova: so trocar o hash nao recarrega a pagina, e o
            # passeio e decidido na abertura.
            pagina.goto(base + "/?passeio=1#boasvindas", wait_until="networkidle")
            pagina.wait_for_timeout(1500)
            checar(
                pagina.evaluate("() => !document.getElementById('boas-vindas').hidden"),
                "#boasvindas abre o passeio de boas-vindas",
            )
            pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
            pagina.wait_for_timeout(400)
            checar(
                pagina.evaluate("() => (document.querySelector('.bv-passo.atual') || {}).textContent") == "2Escritório",
                "Comecar leva ao passo Escritorio",
            )
            pagina.evaluate("() => concluirBoasVindas(true)")
            pagina.wait_for_timeout(600)
            checar(
                pagina.evaluate("() => document.getElementById('boas-vindas').hidden"),
                "concluir fecha o passeio e devolve o programa",
            )

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

            print("\na Agenda: mes, semana e tarefas")
            # Calendario, Agendamento e Tarefas viraram as tres visoes da Agenda
            # (docs/ui/03-telas-desktop.md, A4). Os destinos antigos continuam
            # abrindo, cada um na visao que o substituiu.
            pagina.evaluate("() => abrirDestino('calendario')")
            pagina.wait_for_timeout(1600)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.ag-mes');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 7, f"o mes abre em sete colunas (achou {colunas})")
            checar(
                pagina.evaluate("() => !!document.querySelector('#agenda .acervo-painel .painel-cabeca')"),
                "o painel do dia abre junto do mes",
            )

            # Uma regra `.hoje { margin-top: 22px }` de outra tela ja fez a
            # celula de hoje descer 22 px. As classes da Agenda tem prefixo
            # proprio, e esta checagem garante que continua assim.
            desvio = pagina.evaluate("""() => {
              const h = document.querySelector('.ag-cel.ag-hoje');
              const o = document.querySelector('.ag-cel:not(.ag-hoje):not(.ag-fora)');
              if (!h || !o) return null;
              return {hoje: getComputedStyle(h).marginTop, outra: getComputedStyle(o).marginTop};
            }""")
            checar(
                desvio is None or desvio["hoje"] == desvio["outra"],
                "a celula de hoje nao anda por causa de regra de outra tela",
                str(desvio),
            )

            pagina.evaluate("() => document.querySelector('[data-visao=semana]').click()")
            pagina.wait_for_timeout(1400)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.ag-semana');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 6, f"a semana tem a faixa de horas e cinco dias (achou {colunas})")
            alturas = pagina.evaluate(
                "() => [...document.querySelectorAll('.ag-semana-dias span')]"
                ".map(e => Math.round(e.getBoundingClientRect().height))"
            )
            checar(
                len(set(alturas)) <= 1,
                f"os cabecalhos da semana tem a mesma altura ({sorted(set(alturas))})",
            )
            checar(
                pagina.evaluate("() => !!document.querySelector('#agenda .ag-form')"),
                "a semana abre com o formulario de novo compromisso no painel",
            )

            pagina.evaluate("() => document.querySelector('[data-visao=tarefas]').click()")
            pagina.wait_for_timeout(1400)
            checar(
                pagina.evaluate(
                    "() => !!document.querySelector('.ag-tarefas .ag-listas')"
                    " && !!document.querySelector('[data-ag-nova]')"
                ),
                "as tarefas abrem com as listas e a caixa de adicionar",
            )
            pagina.evaluate("() => abrirDestino('tarefas')")
            pagina.wait_for_timeout(1200)
            checar(
                pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Meu dia",
                "o destino antigo Tarefas abre a Agenda em Meu dia",
            )

            print("\no Financeiro: visao geral, lancamentos e relatorios")
            # Financeiro e Relatorios viraram as tres visoes de uma tela so
            # (docs/ui/03-telas-desktop.md, A9). O destino antigo Relatorios
            # continua abrindo, na visao que o substituiu.
            pagina.evaluate("() => abrirDestino('financeiro')")
            pagina.wait_for_timeout(1800)
            numeros = pagina.evaluate("() => document.querySelectorAll('#financeiro .fin-numero').length")
            checar(numeros == 4, f"a visao geral abre com os quatro numeros (achou {numeros})")
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.fin-fluxo-grade');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 6, f"o fluxo de caixa tem seis meses (achou {colunas})")
            checar(
                pagina.evaluate("() => !!document.querySelector('#financeiro .acervo-painel .painel-cabeca')"),
                "o painel Precisa de voce abre junto",
            )
            pagina.evaluate("() => document.querySelector('[data-fin-visao=lancamentos]').click()")
            pagina.wait_for_timeout(1600)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.tabela-cabecalho.colunas-lancamentos');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 6, f"a tabela de lancamentos tem seis colunas (achou {colunas})")
            pagina.evaluate("() => document.querySelector('[data-fin-visao=relatorios]').click()")
            pagina.wait_for_timeout(1600)
            abas = pagina.evaluate("() => document.querySelectorAll('#financeiro .fin-rel-abas button').length")
            checar(abas == 3, f"os relatorios abrem com as tres abas (achou {abas})")
            pagina.evaluate("() => abrirDestino('relatorios')")
            pagina.wait_for_timeout(1600)
            checar(
                pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Relatórios",
                "o destino antigo Relatorios abre o Financeiro em Relatorios",
            )

            print("\nos Cadastros: clientes, equipe e despesas fixas")
            # Tres tabelas com a ficha editavel no painel
            # (docs/ui/03-telas-desktop.md, A10).
            pagina.evaluate("() => abrirDestino('cadastros')")
            pagina.wait_for_timeout(1800)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.tabela-cabecalho.colunas-clientes');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 5, f"a tabela de clientes tem cinco colunas (achou {colunas})")
            checar(
                pagina.evaluate("() => !!document.querySelector('#cad-tela .acervo-painel .painel-vazio')"),
                "o painel abre vazio, esperando uma ficha",
            )
            pagina.evaluate("() => document.querySelector('[data-cad-nova]').click()")
            pagina.wait_for_timeout(500)
            checar(
                pagina.evaluate("() => !!document.querySelector('#cad-tela .cad-campos [data-cc=nome]')"),
                "Novo cliente abre a ficha em branco no painel",
            )
            pagina.evaluate("() => document.querySelector('[data-cad-visao=equipe]').click()")
            pagina.wait_for_timeout(600)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.tabela-cabecalho.colunas-equipe');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 5, f"a tabela da equipe tem cinco colunas (achou {colunas})")
            pagina.evaluate("() => document.querySelector('[data-cad-visao=despesas]').click()")
            pagina.wait_for_timeout(600)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.tabela-cabecalho.colunas-despesas');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 6, f"a tabela de despesas tem seis colunas (achou {colunas})")

            print("\nas Configuracoes: menu interno e nove secoes")
            # Habilidades, Desempenho e Conexoes viraram secoes de Configuracoes
            # (docs/ui/03-telas-desktop.md, A13); os destinos antigos continuam
            # abrindo, cada um na sua secao.
            pagina.evaluate("() => abrirDestino('config')")
            pagina.wait_for_timeout(1800)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.cfg-corpo');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 2, f"o menu interno e a secao ficam lado a lado (achou {colunas})")
            secoes = pagina.evaluate("() => document.querySelectorAll('#cfg-tela [data-cfg-secao]').length")
            checar(secoes == 9, f"o menu tem nove secoes (achou {secoes})")
            checar(
                pagina.evaluate("() => document.querySelectorAll('#cfg-tela .cfg-grade > .cfg-cartao').length") == 2,
                "Meus dados abre em dois cartoes lado a lado",
            )
            pagina.evaluate("() => abrirDestino('desempenho')")
            pagina.wait_for_timeout(3200)
            checar(
                pagina.evaluate("() => cfg.secao === 'desempenho' && cfg.historico.length >= 1"),
                "o destino antigo Desempenho abre a secao e mede ao vivo",
            )
            pagina.evaluate("() => abrirDestino('habilidades')")
            pagina.wait_for_timeout(1600)
            checar(pagina.evaluate("() => cfg.secao === 'aprendizado' && cfg.relogio === null"),
                   "o destino antigo Aprendizado abre a secao e para a medicao")
            pagina.evaluate("() => abrirDestino('conexoes')")
            pagina.wait_for_timeout(1600)
            checar(pagina.evaluate("() => cfg.secao === 'conexoes'"), "o destino antigo Conexoes abre a secao")

            print("\nFoco e bem-estar: hoje e semana")
            # O ciclo no anel, os lembretes e o ritmo por hora no painel
            # (docs/ui/03-telas-desktop.md, A12).
            pagina.evaluate("() => abrirDestino('foco')")
            pagina.wait_for_timeout(2000)
            checar(
                pagina.evaluate("() => !!document.querySelector('#be-tela .be-anel') && !!document.querySelector('#be-tela .be-lembretes')"),
                "Hoje abre com o anel do ciclo e os lembretes",
            )
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.be-horas');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 11, f"o ritmo por hora tem onze colunas (achou {colunas})")
            pagina.evaluate("() => document.querySelector('[data-be-visao=semana]').click()")
            pagina.wait_for_timeout(2200)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.be-semana-grade');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 7, f"a semana tem sete dias (achou {colunas})")
            checar(
                pagina.evaluate("() => !!document.querySelector('#be-tela .be-habito') && !!document.querySelector('#be-tela .fin-parecer')"),
                "a semana traz os habitos e o parecer",
            )

            print("\nApoiar o projeto: contribuir e quem ja apoia")
            # O coracao do trilho abre a tela do desenho (A14); o pagamento nao
            # existe e a tela diz isso, em vez do aviso generico de antes.
            pagina.evaluate("() => abrirDestino('apoiar')")
            pagina.wait_for_timeout(900)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('#apoio-tela .cfg-valores');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 4, f"os valores ficam em quatro colunas (achou {colunas})")
            checar(
                pagina.evaluate("() => !!document.querySelector('#apoio-tela .apoio-previa')"),
                "a previa da lista de apoiadores aparece",
            )
            pagina.evaluate("() => document.querySelector('[data-apoio-visao=lista]').click()")
            pagina.wait_for_timeout(600)
            checar(
                pagina.evaluate("() => document.querySelectorAll('#apoio-tela .apoio-secao').length") == 3,
                "Quem ja apoia abre com as tres secoes",
            )

            print("\nentrar no escritorio por codigo (A0b)")
            # O ramo "existente" das boas-vindas encurta o passeio para quatro
            # passos e termina nos dois codigos; concluir abre o PAULUS em modo
            # limitado ate o responsavel validar. O teste desfaz no fim.
            pagina.evaluate("() => { localStorage.removeItem('paulus.vinculo'); location.hash = '#boasvindas'; verificarPrimeiraAbertura(); }")
            # Abrir o passeio le preferencias e status; com o Ollama desligado,
            # cada leitura espera ate 5 s.
            pagina.wait_for_selector("[data-bv=continuar]", timeout=40000)
            pagina.wait_for_timeout(300)
            pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
            pagina.wait_for_timeout(300)
            pagina.evaluate("() => document.querySelector('[data-escritorio=existente]').click()")
            pagina.wait_for_timeout(300)
            checar(
                pagina.evaluate("() => document.querySelectorAll('#boas-vindas .bv-passo').length") == 4,
                "entrar em um escritorio existente deixa quatro passos",
            )
            pagina.evaluate("() => { bv.passo = 3; desenharBoasVindas(); }")
            pagina.wait_for_timeout(400)
            checar(
                pagina.evaluate("() => document.querySelectorAll('#boas-vindas .bv-casas').length === 2 && bv.vinculo.meuCodigo.length === 6"),
                "o passo dos codigos mostra as duas caixas e gera o seu codigo",
            )
            pagina.evaluate("() => { const el = document.getElementById('bv-codigo'); el.value = 'TESTE1'; el.dispatchEvent(new Event('input')); }")
            pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
            pagina.wait_for_timeout(2500)
            checar(
                pagina.evaluate("() => document.body.classList.contains('vinculo-pendente')"
                                " && getComputedStyle(document.querySelector('.trilho-item[data-destino=financeiro]')).pointerEvents === 'none'"),
                "concluir abre em modo limitado, com o Financeiro apagado",
            )
            pagina.evaluate("() => { localStorage.removeItem('paulus.vinculo'); aplicarModoLimitado(); carregarAgora(); }")
            pagina.wait_for_timeout(400)
            checar(
                pagina.evaluate("() => !document.body.classList.contains('vinculo-pendente')"),
                "desfazer o pedido libera a casca",
            )

            print("\nServicos: pastas e visao de trabalho (A15)")
            # A grade de pastas em tres colunas e, dentro da pasta, resumo,
            # etapas e arquivos com o painel de equipe, prazos, anotacoes e
            # trilha. O teste abre uma pasta de verdade e apaga no fim.
            id_servico = pagina.evaluate("""async () => {
                const r = await fetch('/api/servicos', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: null, dados: { nome: 'Teste de tela — pasta', descricao: 'Pasta aberta pelo teste de tela.' } }) });
                const s = await r.json();
                await fetch('/api/servicos/' + s.id + '/etapas', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ titulo: 'Primeira etapa' }) });
                return s.id;
            }""")
            try:
                pagina.evaluate("() => abrirDestino('servicos')")
                pagina.wait_for_selector("#sv-tela .sv-pasta", timeout=20000)
                colunas = pagina.evaluate("() => getComputedStyle(document.querySelector('.sv-grade')).gridTemplateColumns.split(' ').length")
                checar(colunas == 3, f"as pastas ficam em tres colunas (achou {colunas})")
                checar(
                    pagina.evaluate("() => !!document.querySelector('.sv-novo') && document.getElementById('conversa-meta').textContent.includes('em andamento')"),
                    "o cartao tracejado e a contagem do cabecalho aparecem",
                )
                pagina.evaluate(f"() => abrirServico({id_servico})")
                pagina.wait_for_selector("#sv-tela .sv-trabalho", timeout=20000)
                colunas = pagina.evaluate("() => getComputedStyle(document.querySelector('.sv-trabalho')).gridTemplateColumns.split(' ').length")
                checar(colunas == 2, f"resumo e etapas lado a lado (achou {colunas})")
                checar(
                    pagina.evaluate("() => document.querySelectorAll('#sv-tela .sv-painel .painel-bloco').length") == 4,
                    "o painel traz equipe, prazos, anotacoes e trilha",
                )
                checar(
                    pagina.evaluate("() => document.querySelectorAll('.sv-etapa').length === 1 && !!document.querySelector('.sv-arquivos')"),
                    "a etapa e a tabela de arquivos estao na visao geral",
                )
                pagina.evaluate("() => document.querySelector('[data-sv-voltar]').click()")
                pagina.wait_for_selector("#sv-tela .sv-grade", timeout=20000)
                checar(pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Serviços", "a seta volta para as pastas")
            finally:
                pagina.evaluate(f"() => fetch('/api/servicos/{id_servico}', {{ method: 'DELETE' }})")
                pagina.wait_for_timeout(300)

            print("\nGravacoes: lista, gravador e gravacao arquivada (A16)")
            # A lista em seis colunas, o gravador com o tempo e os botoes
            # redondos, e a gravacao arquivada com o tocador. O audio de teste
            # e um WAV curto gerado na hora; a transcricao diz que falta o
            # modelo de voz em vez de fingir. Apaga no fim.
            id_gravacao = pagina.evaluate("""async () => {
                const taxa = 8000, segundos = 2, n = taxa * segundos;
                const buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
                const escreve = (p, s) => { for (let i = 0; i < s.length; i++) v.setUint8(p + i, s.charCodeAt(i)); };
                escreve(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); escreve(8, 'WAVE'); escreve(12, 'fmt ');
                v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, taxa, true);
                v.setUint32(28, taxa * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); escreve(36, 'data'); v.setUint32(40, n * 2, true);
                for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.round(8000 * Math.sin(2 * Math.PI * 440 * i / taxa)), true);
                const fd = new FormData();
                fd.append('arquivo', new Blob([buf], { type: 'audio/wav' }), 'teste-de-tela.wav');
                fd.append('titulo', 'Teste de tela — gravação'); fd.append('tipo', 'reuniao'); fd.append('participantes', 'Ana Lima, Bruno Souza');
                fd.append('duracao_s', '2'); fd.append('origem', 'importada'); fd.append('marcadores', '[{"t":1,"texto":"meio"}]');
                const r = await fetch('/api/gravacoes', { method: 'POST', body: fd });
                return (await r.json()).id;
            }""")
            try:
                pagina.evaluate("() => abrirDestino('gravacoes')")
                pagina.wait_for_selector("#gv-tela .gv-lista", timeout=20000)
                colunas = pagina.evaluate("() => getComputedStyle(document.querySelector('.tabela-cabecalho.colunas-gravacoes')).gridTemplateColumns.split(' ').length")
                checar(colunas == 6, f"a lista de gravacoes tem seis colunas (achou {colunas})")
                checar(
                    pagina.evaluate(f"() => !!document.querySelector('[data-gv-abrir=\"{id_gravacao}\"] .gv-avatares .cad-avatar')"),
                    "a linha mostra os participantes",
                )
                pagina.evaluate("() => document.querySelector('.tabela-barra [data-gv-nova]').click()")
                pagina.wait_for_selector("[data-gv-comecar]", timeout=20000)
                checar(
                    pagina.evaluate("() => !!document.querySelector('.gv-forma') && !!document.querySelector('.gv-adiante') && document.querySelectorAll('#gv-tela .gv-painel .painel-bloco').length === 4"),
                    "o gravador abre com o formulario, a transcricao honesta e o painel de contexto",
                )
                # Com o modelo de voz baixado, o cartao diz que a transcricao ao
                # vivo comeca junto com a gravacao; sem ele, que falta baixar.
                checar(
                    pagina.evaluate("() => { const t = document.querySelector('.gv-transcricao .gv-adiante').textContent;"
                                    " return gv.voz && gv.voz.disponivel ? t.includes('Começa junto com a gravação') : t.includes('sem modelo de voz'); }"),
                    "o cartao da transcricao ao vivo sabe se o modelo esta nesta maquina",
                )
                pagina.evaluate(f"() => abrirGravacao({id_gravacao})")
                pagina.wait_for_selector("#gv-tela .gv-player", timeout=20000)
                checar(
                    pagina.evaluate("() => !!document.getElementById('gv-audio') && document.querySelectorAll('.gv-barra u').length === 1"),
                    "a gravacao arquivada abre com o tocador e o marcador na barra",
                )
                pagina.evaluate("() => document.querySelector('[data-gv-aba=\"marcadores\"]').click()")
                pagina.wait_for_timeout(400)
                checar(
                    pagina.evaluate("() => document.querySelectorAll('.gv-conteudo .gv-marcador').length") == 1,
                    "a aba Marcadores lista o marcador",
                )
                # A transcricao roda nesta maquina com o Whisper: a aba oferece
                # transcrever quando o modelo esta baixado, ou baixar quando nao
                # esta. O teste nao transcreve (leva meio minuto por minuto de
                # audio); so confere que a tela sabe em que pe esta.
                pagina.evaluate("() => document.querySelector('[data-gv-aba=\"transcricao\"]').click()")
                pagina.wait_for_timeout(400)
                checar(
                    pagina.evaluate("() => !!gv.voz && !!document.querySelector('#gv-conteudo [data-gv-transcrever], #gv-conteudo [data-gv-baixar-voz], #gv-conteudo #gv-progresso, #gv-conteudo .gv-trecho')"),
                    "a aba Transcricao sabe se o modelo de voz esta nesta maquina",
                )
                pagina.evaluate("() => document.querySelector('[data-gv-voltar]').click()")
                pagina.wait_for_selector("#gv-tela .gv-lista", timeout=20000)
                checar(pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Gravações", "a seta volta para a lista")
            finally:
                pagina.evaluate(f"() => fetch('/api/gravacoes/{id_gravacao}', {{ method: 'DELETE' }})")
                pagina.wait_for_timeout(300)

            print("\ndialogos do sistema (P - Popups)")
            # confirm() e prompt() do navegador viraram dialogos do desenho:
            # titulo em Garamond, contexto, acao destrutiva em vinho, Enter
            # confirma, Esc fecha, foco no campo e devolvido ao fechar.
            pagina.evaluate("() => { window.__d = confirmar({ titulo: 'Apagar isto?', contexto: 'Teste de tela', texto: 'Some de vez.', confirmar: 'Apagar', perigo: true }); }")
            pagina.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
            checar(
                pagina.evaluate("() => document.querySelector('#veu-dialogo h2').textContent === 'Apagar isto?'"
                                " && !!document.querySelector('#veu-dialogo .dialogo-pe .primario.perigo')"
                                " && document.activeElement === document.querySelector('#veu-dialogo .dialogo-pe .primario')"),
                "o dialogo de confirmacao abre com o titulo, a acao em vinho e o foco nela",
            )
            pagina.keyboard.press("Escape")
            checar(pagina.evaluate("async () => (await window.__d) === false && !document.getElementById('veu-dialogo')"), "Esc fecha e devolve nao")
            pagina.evaluate("() => { window.__p = perguntar({ titulo: 'Renomear', contexto: 'Teste de tela', campo: { rotulo: 'Nome', valor: 'antigo', sufixo: '.pdf' }, confirmar: 'Renomear' }); }")
            pagina.wait_for_selector("#dialogo-campo", timeout=5000)
            checar(
                pagina.evaluate("() => document.activeElement === document.getElementById('dialogo-campo') && !!document.querySelector('.dialogo-teclas')"),
                "o dialogo com campo abre com o foco no campo e a dica de teclas",
            )
            pagina.keyboard.type("novo nome")
            pagina.keyboard.press("Enter")
            checar(pagina.evaluate("async () => (await window.__p) === 'novo nome' && !document.getElementById('veu-dialogo')"), "Enter confirma e devolve o texto digitado")
            pagina.evaluate("() => avisoCert('teste de aviso', { acao: { rotulo: 'Desfazer', fazer: () => { window.__desfez = true; } } })")
            pagina.wait_for_timeout(200)
            pagina.evaluate("() => document.querySelector('#aviso-toast button').click()")
            checar(pagina.evaluate("() => window.__desfez === true"), "o aviso com Desfazer chama a acao")

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
