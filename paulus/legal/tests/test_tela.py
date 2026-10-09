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

import json
import socket
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
# O servidor sobe sobre os dados reais: sem retomar as transcricoes paradas
# deles (carregar o Whisper ali derrubava o teste por falta de memoria).
# Para nao tocar nos dados reais, rode com PAULUS_DADOS numa COPIA de
# data/demo (o escritorio de demonstracao tem documentos; as conversas, que
# ele nao tem, o teste supre). Numa pasta vazia, as partes do acervo falham.
import os  # noqa: E402

os.environ.setdefault("PAULUS_SEM_VOZ", "1")

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
    # Os dados reais podem estar vinculados a uma conta Google sem "manter
    # aberto": o servidor sobe travado e toda rota responde 423 ate entrar com
    # o Google. A trava tem teste proprio (test_e5_vinculo); aqui ela fica
    # aberta so neste processo - nada e gravado nos dados.
    if getattr(api.estado, "vinculo", None) is not None:
        api.estado.vinculo.destravado = True
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


def test_celular(navegador, base: str) -> None:
    """
    As quatro telas do acesso de fora num celular de 390 px (R9): a tela de
    entrar, a conversa, o documento aberto com o trecho citado e Aprovacoes.
    O Cloudflare Access e simulado (o JWT e conferido de verdade em
    tests/test_r6_tunel.py); o resto e o caminho real de quem chega de fora.

    Usavel quer dizer: nada passa da largura da tela (sem rolagem de lado), o
    que se aperta tem 44 px, e a barra de destinos fica embaixo.
    """
    print("\ncelular (390 px), pelo acesso de fora")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI, o acesso de fora nao existe nesta maquina")
        return
    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    antes_chave = prefs.get("turnstile_sitekey", "")
    # A regra de antes volta no fim (desde 07/10/2026 o padrao e desligado): este teste roda
    # tambem sobre os dados de verdade, e nao pode deixar o escritorio so com o Google.
    antes_so_google = bool(prefs.get("so_google", False))
    email = "celular-tela@escritorio.com"
    conta = None
    pedido = None
    try:
        conta = servico.contas.criar("Teste de Tela", email, "titular", "senha-do-celular-12")
        servico.contas.confirmar_totp(conta["conta"]["id"], codigo_totp(conta["segredo"], int(time.time() // 30) - 1))
        prefs["ligado"] = True
        prefs["so_google"] = False  # o celular entra por senha aqui; a regra "so Google" e de test_e3_google
        servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
        prefs["turnstile_sitekey"] = "chave-de-teste"
        pedido = api.estado.fila.pedir("Teste de tela: enviar e-mail", "email", acao="correio.enviar",
                                       resumo="Pedido criado pelo teste de tela")
        ctx = navegador.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        # O Turnstile de mentira: o widget da Cloudflare nao carrega no teste,
        # e o token que ele daria e o que o servidor simulado aceita.
        ctx.route("https://challenges.cloudflare.com/**", lambda rota: rota.fulfill(
            content_type="application/javascript",
            body="window.turnstile = {render: () => 1, getResponse: () => 'ok', reset: () => {}};"))
        pag = ctx.new_page()
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        largura = "() => document.documentElement.scrollWidth"

        pag.goto(base + "/", wait_until="networkidle")
        # Com o Google configurado (dados de verdade), ele vem primeiro e o
        # e-mail e a senha ficam no "Entrar com e-mail e senha".
        if pag.locator("#usar-senha").is_visible():
            pag.click("#usar-senha")
        checar(pag.evaluate(largura) <= 390 and pag.locator("#email").is_visible(), "a tela de entrar cabe em 390 px",
               pag.evaluate(largura))
        pag.fill("#email", email)
        pag.fill("#senha", "senha-do-celular-12")
        pag.click("#form-senha button[type=submit]")
        pag.wait_for_selector("#codigo", state="visible", timeout=10000)
        pag.fill("#codigo", codigo_totp(conta["segredo"], int(time.time() // 30)))
        pag.click("#form-codigo button[type=submit]")
        pag.wait_for_load_state("networkidle")
        # A pagina recarrega depois do codigo e so marca "remoto" quando
        # /api/acesso/eu responde: espera a marca, e nao um tempo fixo (com a
        # maquina carregada, 2,5 s nao bastavam).
        try:
            pag.wait_for_function("() => document.documentElement.classList.contains('remoto')", timeout=15000)
        except Exception:  # noqa: BLE001 - o checar abaixo diz
            pass
        pag.wait_for_timeout(500)
        checar(pag.evaluate("() => document.documentElement.classList.contains('remoto')"), "entrou de fora")
        checar(pag.evaluate(largura) <= 390, "a conversa cabe em 390 px", pag.evaluate(largura))
        # Pacote "PAULUS - Telas Mobile" (02/10/2026): no celular o trilho sai
        # e a navegacao e a barra de baixo de cinco icones (#barra-celular).
        trilho = pag.evaluate("() => { const r = document.getElementById('barra-celular').getBoundingClientRect(); return {topo: r.top, altura: r.height}; }")
        checar(trilho["topo"] > 700, "a barra de destinos fica embaixo", trilho)
        alvos = pag.evaluate("() => [...document.querySelectorAll('#barra-celular button')].filter(b => b.offsetParent).map(b => Math.min(b.getBoundingClientRect().height, b.getBoundingClientRect().width))")
        checar(len(alvos) == 5 and min(alvos) >= 44, "cada destino tem 44 px de toque", alvos)

        nome = api.estado.searcher.documents[0].name if api.estado.searcher.documents else ""
        if nome:
            pag.evaluate("(n) => { const c = document.createElement('div'); c.className = 'visor-caixa'; document.body.appendChild(c); abrirCitacao(n, '', '', c); }", nome)
            pag.wait_for_timeout(2500)
            checar(pag.evaluate(largura) <= 390 and pag.locator(".visor").count() > 0, "o documento com o trecho cabe em 390 px",
                   pag.evaluate(largura))
            checar(not pag.locator('[data-vs="fora"]').first.is_visible(), "de fora, 'Abrir fora' nao aparece")
        pag.evaluate("() => abrirDestino('aprovacoes')")
        pag.wait_for_timeout(1800)
        checar(pag.evaluate(largura) <= 390, "Aprovacoes cabe em 390 px", pag.evaluate(largura))
        botoes = pag.evaluate("() => [...document.querySelectorAll('#centro .tabela-linha button')].filter(b => b.offsetParent).map(b => { const r = b.getBoundingClientRect(); return [r.right, r.height]; })")
        checar(botoes and all(d <= 390 and h >= 44 for d, h in botoes), "Aprovar e Recusar inteiros na tela, com 44 px", botoes[:3])
        ctx.close()
    finally:
        prefs["ligado"] = False
        prefs["so_google"] = antes_so_google
        servico.__dict__.pop("conferir_turnstile", None)
        prefs["turnstile_sitekey"] = antes_chave
        if pedido:
            api.estado.fila.esquecer(pedido.id)
        if conta:
            # A conta do teste sai sempre - mesmo sendo a unica de titular,
            # que pela tela nao sairia: este teste roda tambem nos dados de
            # verdade (sem PAULUS_DADOS), e conta de teste nao pode sobrar la.
            servico.contas.encerrar_sessoes(conta["conta"]["id"])
            with servico.contas._db() as c:
                c.execute("DELETE FROM contas WHERE id = ?", (conta["conta"]["id"],))
                c.execute("DELETE FROM tentativas WHERE email = ?", (email,))


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

    # A Agenda confere a lista do dia e a ficha de uma tarefa. Sem tarefa
    # nenhuma na máquina o teste parava ali e não chegava ao resto das telas:
    # ele traz a sua, com prazo hoje, e a tira no fim, passe ou falhe.
    import api
    from datetime import date

    tarefa_do_teste = api.estado.tarefas.salvar(
        {"titulo": "Teste de tela · tarefa do dia", "prazo": date.today().isoformat()})

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

            # Como a janela do programa: entra uma vez pelo /entrar-local, que
            # troca a chave desta execucao pelo cookie da sessao local (R1).
            pagina.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
            pagina.wait_for_timeout(2500)

            print("\nabertura")
            checar(pagina.url.rstrip("/") == base, "o /entrar-local segue para a pagina", pagina.url)
            checar(not erros, f"nenhum erro de JavaScript ao abrir", "; ".join(erros[:3]))
            checar(
                pagina.evaluate("() => !!document.querySelector('link[rel=icon]')"),
                "a pagina declara um icone - sem isso todo carregamento pede /favicon.ico e leva 404",
            )
            checar(
                pagina.evaluate("() => document.documentElement.dataset.tema") == "escuro",
                "abre no tema escuro, o padrao (pedido do dono, 29/09/2026)",
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
                // Fechado e a faixa na largura do trilho e o menu sem receber
                // clique: ela fica montada o tempo todo e abre crescendo, com o
                // menu de largura fixa dentro, para nao refazer o layout dos
                // itens a cada quadro nem deixar a conversa aparecer atraves.
                fechado: getComputedStyle(m.querySelector('.menu-faixa')).width === '64px'
                  && getComputedStyle(m).pointerEvents === 'none',
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

            # Ctrl+K abre a busca de tudo (js/50-busca.js), com o campo focado; Esc fecha.
            pagina.keyboard.press("Control+K")
            pagina.wait_for_timeout(200)
            checar(
                pagina.evaluate("() => document.activeElement && document.activeElement.id") == "bsc-campo",
                "Ctrl+K abre a busca de tudo, com o campo focado",
            )
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(150)
            checar(pagina.evaluate("() => !document.getElementById('bsc-veu')"), "Esc fecha a busca")

            print("\nprimeira abertura")
            # A ordem do assistente novo (07/10/2026, js/23-boas-vindas.js):
            # Boas-vindas, Sua conta, Assinatura, Seus dados, Conexoes,
            # Acesso a distancia e Atualizacoes. A assinatura e a do site
            # (src/rotas_boas_vindas.py): aqui ela e de mentira, para o passeio
            # nao depender da conta da nuvem - primeiro sem assinatura (o passo
            # segura), depois ativa (o passo some sozinho). E nada do passeio
            # grava nas preferencias: o que o assistente mandaria fica anotado.
            import rotas_boas_vindas

            assinatura_antes = rotas_boas_vindas.assinatura
            sem_assinatura = {"ativa": False, "situacao": "nenhuma", "email": "teste@exemplo.com.br", "pessoa": {}, "escritorio": "",
                              "plano": "", "renova_em": ""}
            situacao = {"a": sem_assinatura}
            rotas_boas_vindas.assinatura = lambda estado: situacao["a"]
            gravados: list[str] = []

            def sem_gravar(rota):
                if rota.request.method == "POST":
                    gravados.append(rota.request.post_data or "")
                    rota.fulfill(status=200, content_type="application/json", body="{}")
                else:
                    rota.continue_()

            pagina.route("**/api/preferencias", sem_gravar)
            etapa = "() => (document.querySelector('.bv-etapa.atual') || {}).textContent"
            try:
                # Com uma query nova: so trocar o hash nao recarrega a pagina, e o
                # passeio e decidido na abertura.
                pagina.goto(base + "/?passeio=1#boasvindas", wait_until="networkidle")
                pagina.wait_for_timeout(1500)
                checar(
                    pagina.evaluate("() => !document.getElementById('boas-vindas').hidden"),
                    "#boasvindas abre o passeio de boas-vindas",
                )
                etapas = "() => [...document.querySelectorAll('.bv-etapa')].map(e => e.textContent).join('|')"
                checar(
                    pagina.evaluate(etapas) == "Boas-vindas|Sua conta|Assinatura|Seus dados|Conexões|Acesso à distância|Atualizações",
                    "as etapas na ordem nova, so com o nome",
                    pagina.evaluate(etapas),
                )
                pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
                pagina.wait_for_timeout(600)
                # Entrar e obrigatorio (08/10/2026): o passo Sua conta tem o login e nao tem
                # "Pular por agora" nem Continuar enquanto a conta nao esta vinculada.
                checar(
                    pagina.evaluate(etapa) == "Sua conta"
                    and pagina.evaluate("() => !!document.querySelector('[data-bv-google], [data-bv-atos]')")
                    and pagina.evaluate("() => !document.querySelector('[data-bv=pular]') && !document.querySelector('[data-bv=continuar]')"),
                    "Comecar leva ao passo Sua conta: o login, sem pular e sem Continuar antes de entrar",
                    pagina.evaluate(etapa),
                )
                # Entrou (como o formulario deixa), ainda sem assinatura: o Continuar aparece.
                pagina.evaluate("""async () => {
                  vinc.estado = {vinculado: true, por: 'senha', email: 'teste@exemplo.com.br', nome: 'Helena Teste', manter_aberto: false, google: false, fase: ''};
                  await aoVincularBv(); desenharBoasVindas();
                }""")
                pagina.wait_for_timeout(400)
                checar(
                    pagina.evaluate(etapa) == "Sua conta" and pagina.evaluate("() => !!document.querySelector('[data-bv=continuar]')"),
                    "com a conta vinculada, o passo Sua conta mostra o Continuar",
                    pagina.evaluate(etapa),
                )
                pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
                pagina.wait_for_timeout(400)
                # Sem assinatura, o passo segura: nao ha Continuar, so assinar no site.
                checar(
                    pagina.evaluate(etapa) == "Assinatura"
                    and pagina.evaluate("() => !document.querySelector('[data-bv=continuar]') && !!document.querySelector('[data-bv=assinar]')")
                    and pagina.evaluate("() => !!document.querySelector('[data-bv=outra-conta]')"),
                    "sem assinatura, o passo Assinatura segura: so 'Assinar no site' e a troca de conta",
                    pagina.evaluate(etapa),
                )
                # O site confirmou durante a espera: quem assinou agora acabou de preencher tudo la, entao
                # "Seus dados" nao aparece; os dados do cadastro sao gravados sem a tela.
                pagina.evaluate("() => { bv.pessoa = {}; bv.escritorio = ''; }")
                situacao["a"] = {"ativa": True, "situacao": "ativa", "email": "teste@exemplo.com.br", "escritorio": "Escritório da Tela",
                                 "plano": "Escritório", "renova_em": "2026-11-07", "valor": 1290, "periodo": "mensal", "pago_ate": "",
                                 "pessoa": {"nome": "Helena Teste", "oab": "PA 12345", "cpf": "11.222.333/0001-81",
                                            "telefone": "(91) 98888-7777", "endereco": "Rua A, 1 - Centro, Belém - PA, CEP 66010-000"}}
                pagina.evaluate("async () => { bv.assinaturaEsperando = true; await lerAssinatura(); desenharBoasVindas(); }")
                pagina.wait_for_timeout(800)
                checar(
                    pagina.evaluate(etapa) == "Conexões"
                    and pagina.evaluate(etapas) == "Boas-vindas|Sua conta|Conexões|Acesso à distância|Atualizações",
                    "assinou durante o assistente: Assinatura e Seus dados saem, e o assistente segue para Conexoes",
                    pagina.evaluate(etapas),
                )
                salvo = json.loads(gravados[-1]) if gravados else {}
                checar(
                    (salvo.get("escritorio") or {}).get("nome") == "Escritório da Tela"
                    and (salvo.get("escritorio") or {}).get("cnpj") == "11.222.333/0001-81"
                    and "cpf" not in (salvo.get("pessoa") or {}),
                    "os dados da assinatura sao gravados: o nome do escritorio, e o CNPJ vai para o escritorio, nao para o CPF",
                    salvo,
                )
                # Quem entrou ja com assinatura ativa confere em "Seus dados": o cadastro so para ler e o plano.
                pagina.evaluate("() => { bv.semConferirDados = false; bv.passo = ordemBv().indexOf('dados'); desenharBoasVindas(); }")
                pagina.wait_for_timeout(400)
                checar(
                    pagina.evaluate(etapa) == "Seus dados"
                    and pagina.evaluate("() => document.querySelectorAll('.bv-dados-grade .bv-dado').length") == 7
                    and "Escritório da Tela" in pagina.evaluate("() => document.querySelector('.bv-dados-grade').textContent")
                    and "mensal" in pagina.evaluate("() => document.querySelector('.bv-secao-plano').textContent")
                    and "R$ 1.290" in pagina.evaluate("() => document.querySelector('.bv-secao-plano').textContent"),
                    "Seus dados mostra o cadastro da assinatura, so para ler, com o plano, o periodo e o valor",
                    pagina.evaluate("() => (document.querySelector('.bv-entrada') || {}).textContent"),
                )
                pagina.evaluate("() => document.querySelector('[data-bv=continuar]').click()")
                pagina.wait_for_timeout(500)
                checar(
                    pagina.evaluate(etapa) == "Conexões"
                    and pagina.evaluate("() => document.querySelectorAll('.cartao-permissoes .lb-escopo').length") == 5
                    and pagina.evaluate("() => !!document.querySelector('[data-bv=pular]')"),
                    "depois de Seus dados, Conexoes: os cinco servicos e 'Pular por agora'",
                    pagina.evaluate(etapa),
                )
                # Entrou com e-mail e senha, sem conta Google: o cartao diz que os servicos pedem uma.
                checar(
                    "Precisa de uma conta Google" in pagina.evaluate("() => document.querySelector('#boas-vindas .bv-entrada').textContent"),
                    "sem conta Google, Conexoes avisa que os servicos pedem uma conta Google",
                )
                # A Agenda usa a autorizacao do Gmail: marcar a Agenda marca o Gmail junto.
                pagina.evaluate("() => document.querySelector('[data-bv-servico=agenda]').click()")
                pagina.wait_for_timeout(300)
                checar(
                    pagina.evaluate("() => Boolean(bv.servicos.agenda && bv.servicos.gmail)")
                    and "Autorizar no Google" in pagina.evaluate("() => document.querySelector('[data-bv=continuar]').textContent"),
                    "marcar a Agenda marca o Gmail junto, e o botao vira 'Autorizar no Google'",
                    pagina.evaluate("() => JSON.stringify(bv.servicos)"),
                )
                pagina.evaluate("() => document.querySelector('[data-bv-servico=gmail]').click()")
                pagina.wait_for_timeout(300)
                checar(
                    pagina.evaluate("() => !bv.servicos.agenda && !bv.servicos.gmail"),
                    "desmarcar o Gmail desmarca a Agenda",
                    pagina.evaluate("() => JSON.stringify(bv.servicos)"),
                )
                pagina.evaluate("() => document.querySelector('[data-bv=pular]').click()")
                pagina.wait_for_timeout(700)
                checar(
                    pagina.evaluate(etapa) == "Acesso à distância"
                    and pagina.evaluate("() => !document.querySelector('[data-bv=pular]')"),
                    "depois de Conexoes, 'Acesso a distancia', sem 'Pular por agora'",
                    pagina.evaluate(etapa),
                )
                # O acesso vem ligado (o caminho normal); o interruptor e o do
                # proprio acesso ("Ligado"/"Desligado"): aria-checked = acesso.
                ja_tem = bool((api.estado.prefs.dados.get("acesso_remoto") or {}).get("hostname"))
                recusado = bool((api.estado.prefs.dados.get("acesso_remoto") or {}).get("recusado"))
                checar(
                    pagina.evaluate("() => document.querySelector('[data-bv-acesso]').getAttribute('aria-checked')") == str(not recusado).lower(),
                    "o interruptor do acesso vem como os dados dizem (de fabrica, ligado)",
                )
                # Ligado, com o Worker de mentira: so a disponibilidade.
                from types import SimpleNamespace

                conexao = api.estado.acesso_de_fora.conexao
                provisao_antes = conexao.provisao
                conexao.provisao = SimpleNamespace(disponivel=lambda nome, inst, token="": {"disponivel": True, "motivo": "", "sugestao": ""})
                try:
                    # Com um endereco ja gravado, so o endereco aparece; recusado, nada a preencher.
                    if not ja_tem and not recusado:
                        pagina.wait_for_selector("#cx-slug", timeout=5000)
                        pagina.fill("#cx-slug", "escritorio-da-tela")
                        pagina.wait_for_timeout(1200)
                        # No assistente, o desenho novo nao escreve "disponivel": o campo fica
                        # verde (data-tom "ok") e o final do endereco fica no proprio campo.
                        checar(
                            pagina.evaluate("() => document.getElementById('cx-final').textContent") == "escritorio-da-tela.paulus.ia.br"
                            and pagina.evaluate("() => document.getElementById('cx-disp').dataset.tom") == "ok"
                            and pagina.evaluate("() => document.querySelector('#boas-vindas .acesso-slug').dataset.tom") == "ok",
                            "ligado: o endereco, conferido enquanto digita (disponivel: o campo fica verde)",
                            pagina.evaluate("() => [document.getElementById('cx-final').textContent, document.getElementById('cx-disp').dataset.tom, document.getElementById('cx-disp').textContent]"),
                        )
                        checar(
                            pagina.evaluate("() => document.querySelectorAll('#boas-vindas .acesso-etapa').length") == 3,
                            "as tres etapas: endereco, conta do titular, confirmar no navegador",
                        )
                        # So o passo da vez fica aberto: "Usar este endereco" encolhe o 1 (com o endereco) e abre o 2.
                        checar(
                            pagina.evaluate("() => document.querySelectorAll('#boas-vindas .acesso-etapa.fechada').length") == 2,
                            "no comeco, so o passo do endereco fica aberto; os outros dois, apagados",
                        )
                        pagina.evaluate("() => document.querySelector('[data-cx-usar-endereco]').click()")
                        pagina.wait_for_timeout(500)
                        checar(
                            pagina.evaluate("() => (document.querySelector('#boas-vindas .acesso-etapa.feita .acesso-resumo') || {}).textContent") == "escritorio-da-tela.paulus.ia.br"
                            and not pagina.evaluate("() => !!document.getElementById('cx-slug')")
                            and pagina.evaluate("() => document.querySelectorAll('#boas-vindas .acesso-etapa.fechada').length") == 1,
                            "'Usar este endereco' encolhe o passo 1 com o endereco e abre o passo 2",
                            pagina.evaluate("() => [...document.querySelectorAll('#boas-vindas .acesso-etapa')].map(e => e.className).join(' | ')"),
                        )
                        checar(
                            pagina.evaluate("() => !document.querySelector('[data-bv=continuar]') && !!document.querySelector('.bv-rodape-nota')"),
                            "sem o tunel conectado ate o fim, nao ha Continuar: o rodape diz o que falta",
                        )
                        pagina.evaluate("() => document.querySelector('[data-bv-acesso]').click()")
                        pagina.wait_for_timeout(400)
                        checar(
                            pagina.evaluate("() => document.querySelector('[data-bv-acesso]').getAttribute('aria-checked')") == "false"
                            and not pagina.evaluate("() => !!document.getElementById('cx-slug')")
                            and any('"recusado": true' in g or '"recusado":true' in g for g in gravados),
                            "desligar tira o endereco da tela e grava a recusa",
                        )
                        checar(
                            pagina.evaluate("() => !!document.querySelector('[data-bv=continuar]')"),
                            "recusado, o Continuar aparece",
                        )
                        pagina.evaluate("() => document.querySelector('[data-bv-acesso]').click()")
                        pagina.wait_for_timeout(300)
                finally:
                    conexao.provisao = provisao_antes
                pagina.evaluate("() => concluirBoasVindas(true)")
                pagina.wait_for_timeout(600)
                checar(
                    pagina.evaluate("() => document.getElementById('boas-vindas').hidden"),
                    "concluir fecha o passeio e devolve o programa",
                )
            finally:
                rotas_boas_vindas.assinatura = assinatura_antes
                pagina.unroute("**/api/preferencias")

            print("\ncada destino do menu")
            ver_compositor = """() => {
              const e = document.getElementById('compositor');
              return !!e && !e.hidden && e.getBoundingClientRect().height > 0;
            }"""
            # A coluna de toda tela e a do Financeiro: 1080 px (--fio), centrada
            # na pagina de 1280. So o cabecalho usa os 1280. Com painel ao lado
            # (Organizar, um documento aberto), coluna e painel somam a pagina.
            fora_da_coluna = """() => {
              const c = document.getElementById('centro');
              const fio = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fio'));
              const painel = c.querySelector('.acervo-painel');
              if (painel && painel.getBoundingClientRect().width > 0) return [];
              const largos = [];
              c.querySelectorAll('*').forEach((e) => {
                const b = e.getBoundingClientRect();
                if (b.height < 120 || b.width <= fio + 2) return;
                const cs = getComputedStyle(e);
                if (cs.display === 'none' || cs.visibility === 'hidden') return;
                // so o mais fundo: quem embrulha outro bloco largo nao conta
                const largoDentro = [...e.children].some((f) => {
                  const r = f.getBoundingClientRect();
                  return r.width > fio + 2 && r.height >= 120;
                });
                if (largoDentro) return;
                // a moldura da pagina tem 1280 e centra a coluna: vale ate
                // onde os filhos chegam, nao a largura dela
                let esq = Infinity, dir = -Infinity;
                for (const f of e.children) {
                  const r = f.getBoundingClientRect();
                  if (r.width === 0 || getComputedStyle(f).position === 'fixed') continue;
                  esq = Math.min(esq, r.left); dir = Math.max(dir, r.right);
                }
                const ocupado = dir > esq ? dir - esq : b.width;
                if (ocupado > fio + 2) largos.push(String(e.className || e.tagName).slice(0, 40) + ' ' + Math.round(ocupado));
              });
              return largos;
            }"""
            destinos = pagina.evaluate("() => DESTINOS.map(d => ({id: d.id, nome: d.nome}))")
            # Servicos e Gravacoes sao so da casca, sem par no servidor.
            do_servidor = {d["id"] for d in destinos}
            destinos += [{"id": i, "nome": i} for i in casca["destinos"] if i not in do_servidor]
            com_compositor = []
            largas = []
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
                fora = pagina.evaluate(fora_da_coluna)
                if fora:
                    largas.append(f"{d['nome']} ({fora[0]})")
            checar(not largas, "toda tela sem painel cabe na coluna do Financeiro", "; ".join(largas))

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
                pagina.evaluate("async () => { if (document.querySelector('#agenda .acervo-painel')) return false; document.querySelector('.ag-cel:not(.ag-fora)').click(); await new Promise(r => setTimeout(r, 900)); const ok = !!document.querySelector('.dialogo-dia #ag-dia-pop [data-ag-marcar]'); if (dialogoAberto) dialogoAberto.fechar(null); return ok; }"),
                "o mes nao tem coluna e o dia abre num pop-up com o adicionar",
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
            checar(colunas == 8, f"a semana tem a faixa de horas e os sete dias, como o mes (achou {colunas})")
            alturas = pagina.evaluate(
                "() => [...document.querySelectorAll('.ag-semana-dias span')]"
                ".map(e => Math.round(e.getBoundingClientRect().height))"
            )
            checar(
                len(set(alturas)) <= 1,
                f"os cabecalhos da semana tem a mesma altura ({sorted(set(alturas))})",
            )
            checar(
                pagina.evaluate("() => !document.querySelector('#agenda .acervo-painel') && document.getElementById('agenda').classList.contains('sem-painel')"),
                "a semana tambem nao tem coluna, como o mes",
            )

            pagina.evaluate("() => document.querySelector('[data-visao=tarefas]').click()")
            pagina.wait_for_timeout(1400)
            checar(
                pagina.evaluate(
                    "() => !!document.querySelector('.ag-tarefas .ag-listas')"
                    " && !!document.querySelector('.ag-linha[data-ag-tarefa]')"
                    " && !document.querySelector('[data-ag-nova]')"
                ),
                "as tarefas abrem com as listas e a lista do dia, sem caixa de adicionar",
            )
            # A linha se abre no lugar da coluna: a ficha vem debaixo dela.
            checar(
                pagina.evaluate(
                    "async () => { document.querySelector('.ag-linha[data-ag-tarefa]').click();"
                    " await new Promise(r => setTimeout(r, 900));"
                    " const ok = !!document.querySelector('.ag-linha.aberta')"
                    " && !!document.querySelector('.ag-linha-ficha .painel-chaves')"
                    " && !document.querySelector('#agenda .acervo-painel');"
                    # Fecha de novo: a ficha aberta empurra as linhas para baixo
                    # da janela, e as checagens seguintes clicam nelas.
                    " document.querySelector('.ag-linha.aberta').click();"
                    " await new Promise(r => setTimeout(r, 600));"
                    " return ok; }"
                ),
                "clicar na tarefa abre a ficha na propria linha, sem coluna",
            )
            pagina.evaluate("() => abrirDestino('tarefas')")
            pagina.wait_for_timeout(1200)
            checar(
                pagina.evaluate("() => ag.visao === 'tarefas' && ag.tar.filtro === 'meu_dia' && document.getElementById('conversa-meta').textContent.startsWith('Meu dia')"),
                "o destino antigo Tarefas abre a Agenda em Meu dia",
            )

            print("\no Financeiro: visao geral, lancamentos e relatorios")
            # Financeiro e Relatorios viraram as tres visoes de uma tela so
            # (docs/ui/03-telas-desktop.md, A9). O destino antigo Relatorios
            # continua abrindo, na visao que o substituiu.
            pagina.evaluate("() => abrirDestino('financeiro')")
            pagina.wait_for_timeout(1800)
            numeros = pagina.evaluate("() => document.querySelectorAll('#financeiro .fin-ficha .sv-ficha-item').length")
            checar(numeros == 5, f"a visao geral abre com os cinco numeros na ficha (achou {numeros})")
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.fin-fluxo-grade');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 6, f"o fluxo de caixa tem seis meses (achou {colunas})")
            # Desde 26/09/2026 a tela e uma coluna so: sem painel ao lado, e os
            # cadastros abrem em pop-up.
            checar(
                pagina.evaluate("() => !document.querySelector('#financeiro .acervo-painel') && !!document.querySelector('#financeiro .sv-medida')"),
                "a visao geral e uma coluna so, sem painel ao lado",
            )
            pagina.evaluate("() => document.querySelector('[data-fin-novo]').click()")
            pagina.wait_for_timeout(600)
            checar(
                pagina.evaluate("() => !!document.querySelector('.veu-dialogo #fin-form-pop')"),
                "Novo lancamento abre o cadastro num pop-up",
            )
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(500)
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

            print("\nconferir o extrato do banco com os lancamentos (A9)")
            # O arquivo do banco vira uma lista de propostas: cada linha com o
            # lancamento que parece ser ela. Nada e gravado antes do sim.
            criado = pagina.evaluate("""async () => {
              const r = await fetch('/api/financeiro/lancamentos', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: null, dados: {tipo: 'recebimento', descricao: 'Teste — extrato de tela',
                  centavos: '1.234,56', categoria: 'honorarios', cadastro_id: null,
                  vencimento: '2026-09-10', liquidado_em: '', observacao: ''}})});
              return r.ok ? await r.json() : {erro: r.status};
            }""")
            id_lancamento = criado.get("id")
            checar(bool(id_lancamento), "lancamento de teste criado para conferir", criado)
            try:
                lido = pagina.evaluate("""async () => {
                  const ofx = ['OFXHEADER:100', '<OFX><BANKTRANLIST>', '<STMTTRN>', '<TRNTYPE>CREDIT',
                    '<DTPOSTED>20260910', '<TRNAMT>1234.56', '<FITID>teste-1',
                    '<MEMO>PIX RECEBIDO TESTE EXTRATO', '</STMTTRN>', '<STMTTRN>', '<TRNTYPE>DEBIT',
                    '<DTPOSTED>20260911', '<TRNAMT>-77.00', '<FITID>teste-2',
                    '<MEMO>TARIFA DE TESTE</MEMO>', '</STMTTRN>', '</BANKTRANLIST></OFX>'].join('\\n');
                  const fd = new FormData();
                  fd.append('arquivo', new Blob([ofx], {type: 'text/plain'}), 'extrato-teste.ofx');
                  const r = await fetch('/api/financeiro/banco', {method: 'POST', body: fd});
                  return r.ok ? await r.json() : {erro: r.status, detalhe: await r.text()};
                }""")
                checar(lido.get("resumo", {}).get("movimentos") == 2, "o extrato do banco e lido pela rota da tela", lido)
                achou = [p for p in lido.get("pares", []) if p.get("lancamento_id") == id_lancamento]
                checar(len(achou) == 1 and "valor igual" in achou[0]["porque"],
                       "e o lancamento de teste aparece como par, com o motivo", achou)
                checar(
                    pagina.evaluate("async () => { const d = await (await fetch('/api/financeiro/lancamentos?mes=2026-09')).json();"
                                    f" const l = (d.lancamentos || []).find((x) => x.id === {id_lancamento});"
                                    " return l && !l.liquidado_em; }"),
                    "ler o extrato nao da baixa em nada sozinho",
                )
                pagina.evaluate("(d) => { fin.visao = 'lancamentos'; fin.extrato = d;"
                                " fin.baixas = new Set(d.pares.map((p, i) => (p.lancamento_id ? i : -1)).filter((i) => i >= 0));"
                                " fin.novos = new Set(); desenharFinanceiro(); }", lido)
                pagina.wait_for_timeout(800)
                checar(
                    pagina.evaluate("() => document.querySelectorAll('#financeiro .fin-conc').length === 2 && document.querySelectorAll('#financeiro .fin-conc.marcada').length === 1"),
                    "o painel mostra as duas linhas, com so a que tem par marcada",
                )
                checar(
                    pagina.evaluate("() => document.querySelector('[data-fin-conc-aplicar]').textContent.includes('1 linha')"),
                    "e o botao diz quantas linhas serao conferidas",
                )
                aplicou = pagina.evaluate(f"""async () => {{
                  const r = await fetch('/api/financeiro/banco/aplicar', {{method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{baixas: [{{lancamento_id: {id_lancamento}, data: '2026-09-10'}}], novos: []}})}});
                  return r.ok ? await r.json() : {{erro: r.status}};
                }}""")
                checar(aplicou.get("baixados") == 1, "confirmar da a baixa no lancamento certo", aplicou)
                checar(
                    pagina.evaluate("async () => { const d = await (await fetch('/api/financeiro/lancamentos?mes=2026-09')).json();"
                                    f" const l = (d.lancamentos || []).find((x) => x.id === {id_lancamento});"
                                    " return l && l.liquidado_em === '2026-09-10'; }"),
                    "e a data da baixa e a do banco, nao a de hoje",
                )
            finally:
                if id_lancamento:
                    pagina.evaluate(f"""async () => {{
                      const r = await (await fetch('/api/financeiro/lancamentos/{id_lancamento}', {{method: 'DELETE'}})).json();
                      if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{method: 'DELETE'}});
                    }}""")
                    pagina.evaluate("() => { fin.extrato = null; fin.baixas = new Set(); fin.novos = new Set(); }")
                    pagina.wait_for_timeout(400)

            print("\nos Cadastros: clientes, equipe e despesas fixas")
            # Tres tabelas; desde fd0f1b0 (padrao editorial) sem coluna ao
            # lado, e a ficha nova abre no pop-up do sistema.
            pagina.evaluate("() => abrirDestino('cadastros')")
            pagina.wait_for_timeout(1800)
            colunas = pagina.evaluate(
                "() => { const g = document.querySelector('.tabela-cabecalho.colunas-clientes');"
                " return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; }"
            )
            checar(colunas == 5, f"a tabela de clientes tem cinco colunas (achou {colunas})")
            checar(
                pagina.evaluate("() => !document.querySelector('#cad-tela .acervo-painel')"),
                "a lista ocupa a largura, sem coluna ao lado",
            )
            pagina.evaluate("() => document.querySelector('[data-cad-nova]').click()")
            pagina.wait_for_timeout(500)
            checar(
                pagina.evaluate("() => { const d = document.querySelector('.veu-dialogo');"
                                " return !!d && (d.querySelector('h2') || {}).textContent === 'Novo cliente'"
                                " && !!d.querySelector('[data-cc=nome]') && !d.querySelector('[data-cc=nome]').value; }"),
                "Novo cliente abre a ficha em branco num pop-up",
            )
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(400)
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
            checar(secoes == 16, f"o menu tem dezesseis secoes, Modelos, Modulos, Nota fiscal (N1), Word (W1), Acesso de fora, Backup e a Lixeira incluidas (achou {secoes})")
            # Desde fd658f7 (padrao editorial) os cartoes vem um embaixo do
            # outro, numa coluna so: Voce e Escritorio.
            checar(
                pagina.evaluate("() => { const c = [...document.querySelectorAll('#cfg-tela .cfg-cartao')]"
                                ".map(e => e.getBoundingClientRect());"
                                " return c.length === 2 && Math.abs(c[0].left - c[1].left) < 2 && c[1].top > c[0].bottom - 1; }"),
                "Meus dados abre em dois cartoes, um embaixo do outro",
            )
            # A foto do perfil e a logo do escritorio: escolher um arquivo no
            # computador nao da para automatizar, entao o teste manda a imagem
            # pela mesma rota que a tela usa e confere o que aparece depois.
            enviou = pagina.evaluate("""async () => {
              const lona = document.createElement('canvas');
              lona.width = 120; lona.height = 60;
              const t = lona.getContext('2d');
              t.fillStyle = '#7a1f2b'; t.fillRect(0, 0, 120, 60);
              const bin = await new Promise((ok) => lona.toBlob(ok, 'image/png'));
              const saida = {};
              for (const tipo of ['foto', 'logo']) {
                const fd = new FormData();
                fd.append('arquivo', bin, tipo + '.png');
                const r = await fetch('/api/marca/' + tipo, {method: 'POST', body: fd});
                saida[tipo] = r.ok ? await r.json() : {erro: r.status};
              }
              return saida;
            }""")
            checar(enviou["foto"].get("tem") and enviou["logo"].get("tem"), "a foto e a logo sobem pela rota da tela", enviou)
            checar(enviou["foto"].get("largura") == enviou["foto"].get("altura"),
                   "a foto chega quadrada para caber no circulo", enviou["foto"])
            try:
                pagina.evaluate("async () => { cfg.recarregar = true; await mostrarConfig('perfil'); await carregarUsuario(); }")
                pagina.wait_for_timeout(1800)
                checar(
                    pagina.evaluate("() => !!document.querySelector('#cfg-tela .cfg-foto .cad-avatar img') && !!document.querySelector('#cfg-tela .cfg-logo-propria img')"),
                    "Meus dados mostra a foto no avatar e a logo do escritorio",
                )
                redondo = pagina.evaluate("""() => {
                  const i = document.querySelector('#cfg-tela .cfg-foto .cad-avatar img');
                  const c = getComputedStyle(i);
                  const r = i.getBoundingClientRect();
                  return {corte: c.objectFit, largura: Math.round(r.width), altura: Math.round(r.height)};
                }""")
                checar(redondo["corte"] == "cover" and redondo["largura"] == redondo["altura"],
                       "a foto preenche o circulo sem deformar", redondo)
            finally:
                pagina.evaluate("""async () => {
                  for (const tipo of ['foto', 'logo']) await fetch('/api/marca/' + tipo, {method: 'DELETE'});
                  cfg.recarregar = true; await mostrarConfig('perfil'); await carregarUsuario();
                }""")
                pagina.wait_for_timeout(1200)
            checar(pagina.evaluate("() => !document.querySelector('#cfg-tela .cfg-foto .cad-avatar img') && !document.querySelector('#cfg-tela .cfg-logo-propria')"),
                   "remover devolve as iniciais e a marca do programa")

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

            print("\no que ja foi lido (camada de inteligencia)")
            # A camada tem de aparecer na tela: quanto do acervo ja foi
            # entendido, quanto isso economiza, e a chave para desligar tudo.
            pagina.evaluate("() => { cfg.recarregar = true; return mostrarConfig('assistente'); }")
            pagina.wait_for_timeout(2600)
            lido = pagina.evaluate("""() => {
              const chaves = [...document.querySelectorAll('#cfg-tela .chave-valor')]
                .map((c) => c.textContent);
              return {
                tem: chaves.some((t) => t.includes('Documentos entendidos')),
                datas: chaves.some((t) => t.includes('Datas')),
                chave: !!document.querySelector('[data-cfg-liga="inteligencia"]'),
                ligada: !!document.querySelector('[data-cfg-liga="inteligencia"].on'),
              };
            }""")
            checar(lido["tem"] and lido["datas"],
                   "Configuracoes mostra quanto do acervo ja foi entendido", lido)
            checar(lido["chave"] and lido["ligada"],
                   "com a chave de ligar e desligar, ligada por padrao", lido)

            situacao = pagina.evaluate("async () => await (await fetch('/api/inteligencia')).json()")
            checar(situacao["documentos"] >= 1 and not situacao["catalogo"]["problemas"],
                   "o servidor confirma o que a tela mostra, e o catalogo esta coerente",
                   {k: situacao[k] for k in ("documentos", "no_acervo", "ligada")})
            checar(all(e["nivel"] == 0 for e in situacao["catalogo"]["extratores"]
                       if e["secao"] in ("case", "dates", "amounts", "legal_references")),
                   "as secoes de regra estao declaradas no nivel 0",
                   situacao["catalogo"]["extratores"])

            # A etiqueta que a spec exige: resposta que veio do resumo e
            # leitura do assistente, e a tela precisa dizer isso.
            etiqueta = pagina.evaluate("""() => {
              const alvo = document.createElement('div');
              alvo.innerHTML = etiquetaDeLeitura();
              return alvo.textContent;
            }""")
            checar("leitura do assistente" in etiqueta,
                   "e o que vem do resumo e rotulado como leitura, nao como trecho", etiqueta)

            print("\nos tres atalhos novos e as novidades da versao")
            # Ctrl+Shift+F liga o ciclo de foco de qualquer tela; Ctrl+Enter so
            # vale com a fila aberta (aprovar sem ver seria decidir no escuro).
            estado_foco = pagina.evaluate("""async () => {
              const antes = (await (await fetch('/api/bemestar')).json()).ciclo.estado;
              return antes;
            }""")
            pagina.keyboard.press("Control+Shift+F")
            pagina.wait_for_timeout(2500)
            depois = pagina.evaluate("async () => (await (await fetch('/api/bemestar')).json()).ciclo.estado")
            checar(depois != estado_foco or depois == "foco", f"Ctrl+Shift+F mexe no ciclo de foco ({estado_foco} -> {depois})")
            checar(pagina.evaluate("() => !!document.querySelector('.be-anel')"), "e abre a tela do Foco para ver o relogio")
            pagina.evaluate("() => fetch('/api/bemestar/parar', {method: 'POST'})")
            pagina.wait_for_timeout(600)

            pagina.evaluate("() => abrirDestino('aprovacoes')")
            pagina.wait_for_timeout(1600)
            checar(pagina.evaluate("() => typeof aprovarMarcados === 'function' && !!document.getElementById('ap-fila')"),
                   "a fila de Aprovacoes responde ao Ctrl+Enter")

            # "Novidades da versao" mora em Configuracoes > Versao desde fd658f7.
            pagina.evaluate("() => { cfg.recarregar = true; return mostrarConfig('plano'); }")
            pagina.wait_for_timeout(1800)
            pagina.evaluate("() => document.querySelector('[data-cfg-novidades]').click()")
            pagina.wait_for_timeout(1200)
            novidades = pagina.evaluate("""() => {
              const d = document.getElementById('veu-dialogo');
              if (!d) return null;
              return {blocos: d.querySelectorAll('.cfg-novidade').length,
                      itens: d.querySelectorAll('.cfg-novidade li').length,
                      titulo: (d.querySelector('h2, .dialogo-titulo') || {}).textContent || ''};
            }""")
            checar(novidades and novidades["blocos"] >= 3 and novidades["itens"] >= 8,
                   "Novidades da versao abre com a lista lida do proprio programa", novidades)
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(400)
            checar(pagina.evaluate("() => !document.getElementById('veu-dialogo')"), "e Esc fecha")

            print("\nlimpar o cache e animacoes reduzidas (A13)")
            # Limpar cache pergunta antes, e o que custa caro para refazer (a
            # classificacao pelo modelo) so sai quando a pessoa marca.
            pagina.evaluate("() => { cfg.recarregar = true; return mostrarConfig('assistente'); }")
            pagina.wait_for_timeout(2500)
            checar(pagina.evaluate("() => !!document.querySelector('[data-cfg-cache]')"),
                   "o botao Limpar cache deixou de ser um aviso de em breve")
            pagina.evaluate("() => document.querySelector('[data-cfg-cache]').click()")
            pagina.wait_for_timeout(700)
            checar(
                pagina.evaluate("() => !!document.getElementById('veu-dialogo') && !!document.getElementById('dialogo-marcar') && !document.getElementById('dialogo-marcar').checked"),
                "o dialogo abre e a classificacao vem desmarcada",
            )
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(400)
            checar(pagina.evaluate("() => !document.getElementById('veu-dialogo')"), "Esc fecha sem apagar nada")
            limpou = pagina.evaluate("""async () => {
              const r = await fetch('/api/cache/limpar', {method: 'POST',
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify({classificacao: false})});
              return r.ok ? await r.json() : {erro: r.status};
            }""")
            checar("aviso" in limpou and "classifica" not in " ".join(limpou.get("apagados", [])),
                   "limpar sem marcar mexe so no cache de extracao", limpou)
            # O cache que o teste apagou volta agora: a maquina de quem roda o
            # teste nao pode ficar mais lenta por causa dele.
            refez = pagina.evaluate("""async () => {
              const r = await fetch('/api/reindex', {method: 'POST'});
              return r.ok ? await r.json() : {erro: r.status};
            }""")
            checar(refez.get("contratos", 0) >= 0 and "erro" not in refez, "e o Reindexar reconstroi o que foi apagado", refez)

            pagina.evaluate("() => aplicarAnimacoes(true)")
            pagina.wait_for_timeout(300)
            parado = pagina.evaluate("""() => {
              const el = document.querySelector('.trilho-item');
              return {classe: document.documentElement.classList.contains('sem-animacao'),
                      transicao: getComputedStyle(el).transitionDuration,
                      guardado: localStorage.getItem('paulus.animacoes')};
            }""")
            checar(parado["classe"] and parado["guardado"] == "reduzidas" and parado["transicao"].startswith("0.001"),
                   "animacoes reduzidas param a tela e ficam guardadas", parado)
            pagina.evaluate("() => aplicarAnimacoes(false)")
            pagina.wait_for_timeout(200)
            checar(pagina.evaluate("() => !document.documentElement.classList.contains('sem-animacao')"),
                   "e desligar devolve o movimento")

            print("\nAprendizado: ensinar o assistente com as proprias palavras")
            # O que o escritorio ensina entra em toda pergunta (A13). Desde
            # fd658f7 escrever e alterar acontecem no pop-up do sistema, e a
            # faixa de numeros diz quanto daquilo vai a cada pergunta.
            pagina.evaluate("() => { cfg.recarregar = true; return mostrarConfig('aprendizado'); }")
            pagina.wait_for_timeout(1800)
            id_lembrete = None
            try:
                pagina.evaluate("() => document.querySelector('[data-cfg-ensinar-novo]').click()")
                pagina.wait_for_timeout(500)
                checar(pagina.evaluate("() => !!document.querySelector('.veu-dialogo #cfg-ensinar-titulo')"),
                       "Escrever lembrete abre o pop-up com o formulario")
                pagina.evaluate("""() => {
                  document.getElementById('cfg-ensinar-titulo').value = 'Teste — prazo de aviso';
                  document.getElementById('cfg-ensinar-texto').value = 'Teste de tela: o aviso de nao renovacao e de 90 dias.';
                  document.querySelector('.veu-dialogo [data-dialogo="confirmar"]').click();
                }""")
                pagina.wait_for_timeout(1500)
                id_lembrete = pagina.evaluate("() => ((cfg.ctx || {}).contextos || []).map((x) => x.id)[0] || null")
                checar(id_lembrete is not None, "Guardar grava o lembrete e a secao ja mostra")
                checar(
                    pagina.evaluate("() => !!Array.from(document.querySelectorAll('#cfg-tela .cfg-lembrete b')).find((b) => b.textContent.startsWith('Teste — prazo'))"),
                    "o lembrete aparece na lista com o titulo que foi escrito",
                )
                checar(
                    pagina.evaluate("() => /\\d+ de \\d+ caracteres/.test(document.getElementById('cfg-tela').textContent)"),
                    "e a faixa de numeros diz quanto disso vai em cada pergunta",
                )
                checar(
                    pagina.evaluate("async () => { const d = await (await fetch('/api/contextos')).json(); return d.caracteres > 0; }"),
                    "o servidor confirma que ha texto para o assistente",
                )
                # Ensinar por arquivo: o programa le, propoe e enche o
                # formulario - guardar continua sendo um clique da pessoa.
                # Com o modelo ligado isso leva o tempo de uma resposta dele.
                # O modelo local leva ate um minuto para responder nesta
                # maquina; a espera padrao do Playwright e de 30 s.
                pagina.set_default_timeout(240000)
                lido = pagina.evaluate("""async () => {
                  const bin = new Blob(["Regra da casa: o aviso de nao renovacao deste escritorio e sempre de 90 dias, contados da data de assinatura. O nome da cliente se escreve Cooperativa Brasileira, por extenso."],
                    {type: 'text/plain'});
                  const fd = new FormData();
                  fd.append('arquivo', bin, 'regras-da-casa.txt');
                  const r = await fetch('/api/contextos/ler', {method: 'POST', body: fd});
                  return r.ok ? await r.json() : {erro: r.status, texto: await r.text()};
                }""")
                checar(lido.get("titulo") == "Regras da casa" and len(lido.get("texto", "")) > 20,
                       "ler um arquivo propoe titulo e texto sem guardar nada", lido)
                checar("aviso" in lido and ("confira" in lido["aviso"] or "resumir" in lido["aviso"]),
                       "e o aviso diz para conferir antes", lido.get("aviso"))
                checar(
                    pagina.evaluate("async () => { const d = await (await fetch('/api/contextos')).json(); return (d.contextos || []).filter((x) => x.titulo === 'Regras da casa').length === 0; }"),
                    "ler nao guarda: a proposta so vai para o formulario",
                )
                recusou = pagina.evaluate("""async () => {
                  const fd = new FormData();
                  fd.append('arquivo', new Blob([new Uint8Array([1, 2, 3])], {type: 'image/png'}), 'foto.png');
                  const r = await fetch('/api/contextos/ler', {method: 'POST', body: fd});
                  return {status: r.status, detalhe: (await r.json()).detail || ''};
                }""")
                checar(recusou["status"] == 400 and "imagem" in recusou["detalhe"],
                       "formato que nao da para ler e recusado dizendo por que", recusou)

                pagina.set_default_timeout(30000)
                pagina.evaluate("() => document.querySelector('[data-cfg-ensinar-editar]').click()")
                pagina.wait_for_timeout(600)
                checar(
                    pagina.evaluate("() => (document.getElementById('cfg-ensinar-titulo') || {value: ''}).value.startsWith('Teste — prazo')"
                                    " && !!document.querySelector('.veu-dialogo .dialogo-cancelar')"),
                    "Alterar abre o lembrete no pop-up",
                )
                pagina.evaluate("() => document.querySelector('.veu-dialogo .dialogo-cancelar').click()")
                pagina.wait_for_timeout(500)
                checar(pagina.evaluate("() => !document.getElementById('cfg-ensinar-titulo')"
                                       " && !!Array.from(document.querySelectorAll('#cfg-tela .cfg-lembrete b')).find((b) => b.textContent.startsWith('Teste — prazo'))"),
                       "e Cancelar fecha sem mexer no que esta guardado")
            finally:
                if id_lembrete is not None:
                    pagina.evaluate(f"""async () => {{
                      const r = await (await fetch('/api/contextos/{id_lembrete}', {{method: 'DELETE'}})).json();
                      if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{method: 'DELETE'}});
                      cfg.ctx = await (await fetch('/api/contextos')).json();
                    }}""")
                    pagina.wait_for_timeout(600)

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
            # O grafico da semana sao sete barras deitadas, uma por dia; desde
            # 907a158 fica no cartao "Foco na semana", ao lado dos habitos.
            barras = pagina.evaluate("() => document.querySelectorAll('.be-semana .be-barra').length")
            checar(barras == 7, f"a semana tem sete dias, um por barra (achou {barras})")
            checar(
                pagina.evaluate("() => { const g = document.querySelector('.be-semana'); const c = g && g.closest('.fin-cartao');"
                                " return !!c && c.querySelector('.fin-cartao-cabeca').textContent.startsWith('Foco na semana'); }"),
                "o grafico da semana fica no cartao Foco na semana",
            )
            checar(
                pagina.evaluate("() => !!document.querySelector('#be-tela .be-habito') && !!document.querySelector('#be-tela .fin-parecer')"),
                "a semana traz os habitos e o parecer",
            )

            print("\no apoio saiu do PAULUS (02/10/2026)")
            checar(
                pagina.evaluate("() => !document.querySelector('[data-destino=apoiar]') && typeof mostrarApoiar === 'undefined'"),
                "nem o coracao no menu nem a tela Apoiar",
            )

            print("\no escritorio e um so: a equipe entra por convite (E4)")
            # O "entrar num escritorio existente" (o vinculo por codigo) saiu:
            # o passo Escritorio so pede o nome, e um pedido antigo guardado no
            # navegador nao prende mais a casca.
            pagina.evaluate("() => localStorage.setItem('paulus.vinculo', JSON.stringify({estado: 'aguardando', meuCodigo: 'ABC123'}))")
            pagina.reload(wait_until="networkidle")
            pagina.wait_for_timeout(1500)
            checar(
                pagina.evaluate("() => localStorage.getItem('paulus.vinculo') === null && !document.body.classList.contains('vinculo-pendente')"),
                "um vinculo antigo guardado no navegador e esquecido",
            )
            pagina.evaluate("() => { location.hash = '#boasvindas'; verificarPrimeiraAbertura(); }")
            pagina.wait_for_selector("[data-bv=continuar]", timeout=40000)
            pagina.wait_for_timeout(300)
            # O assistente novo nao tem o passo Escritorio (o nome vem da
            # assinatura) nem o caminho de quem entra num escritorio existente
            # (os Codigos): so o de quem cria.
            checar(
                pagina.evaluate("() => !document.querySelector('[data-caminho]') && typeof passoCodigos === 'undefined' && typeof passoIA === 'undefined'")
                and not any(n in pagina.evaluate("() => [...document.querySelectorAll('.bv-etapa')].map(e => e.textContent)")
                            for n in ("Escritório", "Códigos")),
                "o assistente e so o de quem cria o escritorio, sem 'entrar num existente'",
                pagina.evaluate("() => [...document.querySelectorAll('.bv-etapa')].map(e => e.textContent).join('|')"),
            )
            pagina.evaluate("() => concluirBoasVindas(true)")
            pagina.wait_for_timeout(600)

            print("\nServicos: pastas e visao de trabalho (A15)")
            # A grade de pastas em tres colunas e, dentro da pasta, o desenho
            # do modelo: no centro ficha, equipe, status, historico e arquivos;
            # no painel, prazos, anotacoes e resumo. O teste abre uma pasta de
            # verdade e apaga no fim.
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
                pagina.wait_for_selector("#sv-tela .sv-status", timeout=20000)
                checar(
                    pagina.evaluate("() => [...document.querySelectorAll('[data-sv-aba]')].map(b => b.textContent).join('|') === 'Visão geral|Arquivos|Processos|Trilha|Cliente' && document.querySelector('[data-sv-aba=geral]').classList.contains('ativa') && !document.querySelector('#sv-tela .sv-historico')"),
                    "a pasta abre na Visao geral, com as abas Arquivos, Processos (L2), Trilha e Cliente no cabecalho",
                )
                checar(
                    pagina.evaluate("() => !!document.querySelector('.sv-medida .sv-ficha') && !!document.querySelector('.sv-medida .sv-equipe') && document.querySelectorAll('#sv-tela .sv-duas .sv-secao').length === 2 && !document.querySelector('#sv-tela .acervo-painel')"),
                    "sem barra ao lado: ficha, equipe, e prazos e anotacoes lado a lado na pagina",
                )
                checar(
                    pagina.evaluate("() => document.querySelectorAll('.sv-status .sv-linha-etapa').length === 1 && !!document.querySelector('.sv-abertura > .sv-resumo-topo + .sv-ficha')"),
                    "a etapa no status e o resumo da IA no topo, antes da ficha",
                )
                pagina.evaluate("() => document.querySelector('[data-sv-aba=trilha]').click()")
                pagina.wait_for_selector("#sv-tela .sv-historico", timeout=5000)
                checar(
                    pagina.evaluate("() => document.querySelectorAll('.sv-historico .sv-ev').length >= 2 && !!document.querySelector('.sv-historico [data-sv-conversa]') && document.querySelectorAll('.sv-comando').length >= 2 && !document.querySelector('.sv-status')"),
                    "a Trilha traz o historico com os comandos e a caixa de pedido, sozinho",
                )
                pagina.evaluate("() => document.querySelector('[data-sv-aba=arquivos]').click()")
                pagina.wait_for_selector("#sv-tela .sv-arquivos", timeout=5000)
                checar(pagina.evaluate("() => !document.querySelector('.sv-historico')"), "a aba Arquivos traz so os arquivos")
                pagina.evaluate("() => document.querySelector('[data-sv-voltar]').click()")
                pagina.wait_for_selector("#sv-tela .sv-grade", timeout=20000)
                checar(pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Serviços", "a seta volta para as pastas")
            finally:
                pagina.evaluate(f"async () => {{ const r = await (await fetch('/api/servicos/{id_servico}', {{ method: 'DELETE' }})).json(); if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{ method: 'DELETE' }}); }}")
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
                    pagina.evaluate(f"() => !!document.querySelector('[data-gv-expandir=\"{id_gravacao}\"] .gv-avatares .cad-avatar')"),
                    "a linha mostra os participantes",
                )
                pagina.evaluate("() => document.querySelector('#acoes-tela [data-gv-nova]').click()")
                pagina.wait_for_selector("[data-gv-comecar]", timeout=20000)
                checar(
                    pagina.evaluate("() => !!document.querySelector('.gv-forma') && !!document.querySelector('.gv-adiante') && document.querySelectorAll('#gv-tela .gv-painel .painel-bloco').length === 3"),
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
                # Faltou memoria para o modelo de voz: a frase oferece o mais
                # leve "clicando aqui" (sem clicar: este teste roda tambem nos
                # dados de verdade, e o clique troca o modelo).
                pagina.evaluate("() => { gv.aberta.transcricao_estado = 'erro'; gv.aberta.transcricao_sem_memoria = true;"
                                " gv.aberta.transcricao_erro = 'memória livre insuficiente para o modelo de voz agora (0,9 GB livres, precisa de uns 1,9 GB). Troque para o Whisper small, mais leve (0,5 GB), ou feche programas pesados e mande transcrever de novo';"
                                " gv.voz = Object.assign({}, gv.voz, { mais_leve: { nome: 'small', rotulo: 'Whisper small', mb: 480, instalado: true } }); gv.aba = 'transcricao'; redesenharConteudoGv(); }")
                pagina.wait_for_timeout(300)
                checar(
                    pagina.evaluate("() => { const b = document.querySelector('#gv-conteudo [data-gv-mais-leve]'); const t = document.querySelector('#gv-conteudo .gv-adiante').textContent;"
                                    " return !!b && b.textContent === 'clicando aqui' && t.includes('Whisper small') && (t.match(/Whisper small/g) || []).length === 1; }"),
                    "sem memoria para o modelo de voz, a tela sugere o mais leve 'clicando aqui', uma vez so",
                )
                # Com a transcricao pronta a aba oferece corrigir nomes, exportar
                # .docx e compartilhar; as pendencias do resumo viram tarefas.
                pagina.evaluate("() => { gv.aberta.transcricao_estado = 'pronta'; gv.aberta.trechos = [{ inicio: 0, fim: 2, texto: 'Bom dia, Priscilla.' }]; gv.aberta.palavras = 3; gv.aba = 'transcricao'; redesenharConteudoGv(); }")
                pagina.wait_for_timeout(300)
                checar(
                    pagina.evaluate("() => !!document.querySelector('[data-gv-corrigir]') && !!document.querySelector('[data-gv-exportar]') && document.querySelectorAll('.gv-trecho').length === 1"),
                    "a transcricao pronta oferece Corrigir nomes e Exportar .docx",
                )
                checar(
                    pagina.evaluate("() => { const p = pendenciasDoResumo('Resumo:\\nx\\nPendências:\\n- Conferir a procuração até 15/09\\n- Enviar o aditivo até sexta\\n'); return p.length === 2 && p[0].prazo.endsWith('-09-15') && p[1].prazo.length === 10; }"),
                    "as pendencias do resumo viram itens com prazo",
                )
                pagina.evaluate("() => document.querySelector('[data-gv-voltar]').click()")
                pagina.wait_for_selector("#gv-tela .gv-lista", timeout=20000)
                checar(pagina.evaluate("() => document.getElementById('conversa-titulo').textContent") == "Gravações", "a seta volta para a lista")
            finally:
                pagina.evaluate(f"async () => {{ const r = await (await fetch('/api/gravacoes/{id_gravacao}', {{ method: 'DELETE' }})).json(); if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{ method: 'DELETE' }}); }}")
                pagina.wait_for_timeout(300)

            print("\ndialogos do sistema (P - Popups)")
            # confirm() e prompt() do navegador viraram dialogos do desenho:
            # titulo em Garamond, contexto, acao destrutiva em vinho, Enter
            # confirma, Esc fecha, foco no campo e devolvido ao fechar.
            pagina.evaluate("() => { window.__d = confirmar({ titulo: 'Apagar isto?', contexto: 'Teste de tela', texto: 'Some de vez.', confirmar: 'Apagar', perigo: true }); }")
            pagina.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
            checar(
                pagina.evaluate("() => document.querySelector('#veu-dialogo h2').textContent === 'Apagar isto?'"
                                # Desde o padrao visual (docs/ui/07) o destrutivo e o .perigo
                                # do sistema, sem o .primario junto.
                                " && !!document.querySelector('#veu-dialogo .dialogo-pe .perigo[data-dialogo=confirmar]')"
                                " && document.activeElement === document.querySelector('#veu-dialogo [data-dialogo=confirmar]')"),
                "o dialogo de confirmacao abre com o titulo, a acao em vinho e o foco nela",
            )
            pagina.keyboard.press("Escape")
            checar(pagina.evaluate("async () => (await window.__d) === false && !document.getElementById('veu-dialogo')"), "Esc fecha e devolve nao")
            pagina.evaluate("() => { window.__p = perguntar({ titulo: 'Renomear', contexto: 'Teste de tela', campo: { rotulo: 'Nome', valor: 'antigo', sufixo: '.pdf' }, confirmar: 'Renomear' }); }")
            pagina.wait_for_selector("#dialogo-campo", timeout=5000)
            checar(
                pagina.evaluate("() => document.activeElement === document.getElementById('dialogo-campo') && !document.querySelector('.dialogo-teclas')"),
                "o dialogo com campo abre com o foco no campo, sem a dica de teclas no rodape",
            )
            pagina.keyboard.type("novo nome")
            pagina.keyboard.press("Enter")
            checar(pagina.evaluate("async () => (await window.__p) === 'novo nome' && !document.getElementById('veu-dialogo')"), "Enter confirma e devolve o texto digitado")
            pagina.evaluate("() => avisoCert('teste de aviso', { acao: { rotulo: 'Desfazer', fazer: () => { window.__desfez = true; } } })")
            pagina.wait_for_timeout(200)
            pagina.evaluate("() => document.querySelector('#faixa-janela button').click()")
            checar(pagina.evaluate("() => window.__desfez === true"), "o aviso com Desfazer chama a acao")

            print("\nlixeira (doc 05): apagar guarda 30 dias, o aviso desfaz, Configuracoes restaura")
            id_tarefa = pagina.evaluate("""async () => {
                const r = await fetch('/api/tarefas', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: null, dados: { titulo: 'Teste de tela — vai e volta', prazo: '', cadastro_id: null, anotacao: '' } }) });
                return (await r.json()).id;
            }""")
            try:
                lixo = pagina.evaluate(f"async () => {{ const r = await fetch('/api/tarefas/{id_tarefa}', {{ method: 'DELETE' }}); avisarLixeira(r.clone(), null); return await r.json(); }}")
                pagina.wait_for_timeout(300)
                checar(
                    bool(lixo.get("lixeira")) and pagina.evaluate("() => document.querySelector('#faixa-janela.visivel button') && document.querySelector('#faixa-janela.visivel button').textContent === 'Desfazer'"),
                    "apagar avisa com Desfazer",
                )
                pagina.evaluate("() => mostrarConfig('lixeira')")
                pagina.wait_for_selector("[data-cfg-lixo-restaurar]", timeout=40000)
                checar(
                    pagina.evaluate(f"() => !!document.querySelector('[data-cfg-lixo-restaurar=\"{lixo['lixeira']}\"]') && document.body.textContent.includes('Teste de tela — vai e volta')"),
                    "Configuracoes > Lixeira lista a tarefa apagada",
                )
                pagina.evaluate(f"() => document.querySelector('[data-cfg-lixo-restaurar=\"{lixo['lixeira']}\"]').click()")
                pagina.wait_for_timeout(1500)
                checar(
                    pagina.evaluate(f"async () => ((await (await fetch('/api/tarefas?filtro=abertas')).json()).tarefas || []).some((t) => t.id === {id_tarefa})"),
                    "Restaurar traz a tarefa de volta",
                )
            finally:
                pagina.evaluate(f"async () => {{ const r = await (await fetch('/api/tarefas/{id_tarefa}', {{ method: 'DELETE' }})).json(); if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{ method: 'DELETE' }}); }}")
                pagina.wait_for_timeout(300)

            print("\nselecao multipla: segurar marca, a barra age em lote")
            # Segurar o botao numa linha por meio segundo entra no modo de
            # selecao; dai o clique marca, Shift marca o intervalo, Esc limpa
            # e a barra da lista age sobre todas. Aqui: a lista de conversas
            # (Ver mais) e as tarefas, com Concluir em lote.
            ids_tarefas = pagina.evaluate("""async () => {
                const ids = [];
                for (const n of [1, 2]) {
                    const r = await fetch('/api/tarefas', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id: null, dados: { titulo: 'Teste de tela — selecao ' + n, prazo: '', cadastro_id: null, anotacao: '' } }) });
                    ids.push((await r.json()).id);
                }
                return ids;
            }""")
            conversas_de_mentira = not pagina.evaluate("() => (estado.recentes || []).length")
            if conversas_de_mentira:
                from datetime import datetime, timezone

                agora = datetime.now(timezone.utc).isoformat()

                def com_duas_conversas(rota):
                    resposta = rota.fetch()
                    d = resposta.json()
                    d["grupos"] = [{"nome": "", "trabalhos": [
                        {"id": f"teste-tela-{n}", "titulo": f"Teste de tela — conversa {n}", "atualizado_em": agora, "estado": "concluido", "grupo": ""}
                        for n in (1, 2)]}]
                    rota.fulfill(response=resposta, json=d)

                pagina.route("**/api/trabalhos", com_duas_conversas)
                pagina.evaluate("() => carregarTrabalhos()")
            try:
                pagina.evaluate("() => { $('nova').click(); alternarListaDeConversas(true); }")
                pagina.wait_for_selector("#lista-conversas .lc-linha[data-sel]", timeout=20000)
                # A lista se redesenha logo depois de abrir (a animacao e a recarga): mede so quando parou.
                caixa = None
                for _ in range(20):
                    pagina.wait_for_timeout(150)
                    caixa = pagina.locator("#lista-conversas .lc-linha[data-sel]").first.bounding_box()
                    if caixa:
                        break
                pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
                pagina.mouse.down()
                pagina.wait_for_timeout(650)
                pagina.mouse.up()
                pagina.wait_for_timeout(300)
                checar(
                    pagina.evaluate("() => lcSel.escolhidos.size === 1 && !!document.querySelector('#lista-conversas .lc-linha.escolhida')"
                                    " && document.querySelector('#lista-conversas .lc-barra .selecao').textContent.includes('1 selecionada')"),
                    "segurar numa conversa marca e a barra mostra a selecao",
                )
                pagina.keyboard.press("Escape")
                pagina.wait_for_timeout(300)
                checar(pagina.evaluate("() => lcSel.escolhidos.size === 0"), "Esc limpa a selecao")

                pagina.evaluate("() => { ag.tar.filtro = 'abertas'; mostrarAgenda('tarefas'); }")
                pagina.wait_for_selector(f".ag-linha[data-sel='{ids_tarefas[0]}']", timeout=20000)
                caixa = pagina.locator(f".ag-linha[data-sel='{ids_tarefas[0]}']").bounding_box()
                pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
                pagina.mouse.down()
                pagina.wait_for_timeout(650)
                pagina.mouse.up()
                pagina.wait_for_timeout(300)
                pagina.locator(f".ag-linha[data-sel='{ids_tarefas[1]}']").click()
                pagina.wait_for_timeout(300)
                checar(pagina.evaluate("() => ag.tar.escolhidas.size === 2 && !!document.querySelector('[data-ag-sel-concluir]')"), "duas tarefas marcadas, com a barra")
                pagina.evaluate("() => document.querySelector('[data-ag-sel-concluir]').click()")
                pagina.wait_for_timeout(2000)
                checar(
                    pagina.evaluate(f"async () => {{ const t = (await (await fetch('/api/tarefas?filtro=concluidas')).json()).tarefas || []; return t.filter((x) => [{ids_tarefas[0]}, {ids_tarefas[1]}].includes(x.id)).length === 2; }}"),
                    "Concluir em lote concluiu as duas",
                )
            finally:
                if conversas_de_mentira:
                    pagina.unroute("**/api/trabalhos")
                    pagina.evaluate("() => { lcSel.escolhidos.clear(); return carregarTrabalhos(); }")
                for tid in ids_tarefas:
                    pagina.evaluate(f"async () => {{ const r = await (await fetch('/api/tarefas/{tid}', {{ method: 'DELETE' }})).json(); if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {{ method: 'DELETE' }}); }}")
                pagina.wait_for_timeout(300)

            print("\nestados de erro e carregando (doc 05)")
            # O cartao do motor diz em linguagem comum o que falta e oferece a
            # acao: Ligar agora, Baixar agora, o caminho do Ollama. O esqueleto
            # de carregando tem a forma da lista, sem giro.
            pagina.evaluate("() => { $('nova').click(); desenharAvisoDoMotor({ ollama: false, motor: { instalado: true, rodando: false, modelo_presente: false, mensagem: 'sem servidor' } }); }")
            pagina.wait_for_timeout(300)
            checar(
                pagina.evaluate("() => !document.getElementById('aviso-motor').hidden && document.querySelector('#aviso-motor .cartao-erro b').textContent === 'O assistente está desligado' && !!document.querySelector('[data-motor-ligar]')"),
                "o cartao 'O assistente esta desligado' traz Ligar agora",
            )
            pagina.evaluate("() => desenharAvisoDoMotor({ ollama: false, motor: { instalado: true, rodando: true, modelo_presente: false, tamanho: '2,0 GB' } })")
            checar(
                pagina.evaluate("() => document.querySelector('#aviso-motor p').textContent.includes('2,0 GB') && !!document.querySelector('[data-motor-puxar]')"),
                "o cartao 'Falta baixar o modelo' diz o tamanho e traz Baixar agora",
            )
            pagina.evaluate("() => carregarStatus()")
            pagina.wait_for_timeout(1500)
            checar(pagina.evaluate("() => document.querySelectorAll('.esqueleto').length === 0 && typeof esqueleto('lista') === 'string' && esqueleto('lista').includes('esq-fila')"), "o esqueleto existe para as listas que abrem")

            print("\na proposta de abrir um servico (A15)")
            # "abra um servico para X: Y" volta da conversa como proposta com
            # os tres campos a vista. Entender nao e fazer: a pasta so nasce
            # no clique, e por isso os campos sao editaveis antes do sim.
            pagina.evaluate("""() => {
              const d = {tipo: 'servico', titulo: 'Renovação do contrato',
                campos: {nome: 'Renovação do contrato', cliente: 'Cooperativa Brasileira', descricao: 'Aviso e aditivo'},
                porque: '“abra” e “serviço”', falta: ''};
              $('centro').innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal" id="teste-proposta">' + cartaoProposta(d) + '</div></div>';
            }""")
            pagina.wait_for_timeout(200)
            campos_prop = pagina.evaluate(
                "() => Array.from(document.querySelectorAll('#teste-proposta [data-pc]')).map((e) => e.dataset.pc + '=' + e.value)")
            checar(campos_prop == ["nome=Renovação do contrato", "cliente=Cooperativa Brasileira", "descricao=Aviso e aditivo"],
                   "os tres campos do servico vem preenchidos e editaveis", campos_prop)
            checar(
                pagina.evaluate("() => document.querySelector('#teste-proposta [data-prop=\\\"fazer\\\"]').textContent === 'Abrir o serviço' && !!document.querySelector('#teste-proposta [data-prop=\\\"nao\\\"]')"),
                "o botao diz o que vai acontecer, e da para recusar",
            )
            largura_prop = pagina.evaluate("""() => {
              const p = document.querySelector('#teste-proposta .proposta');
              const i = document.querySelector('#teste-proposta [data-pc=\\\"nome\\\"]');
              return {cartao: p.getBoundingClientRect().width, campo: i.getBoundingClientRect().width};
            }""")
            checar(largura_prop["campo"] > 80 and largura_prop["campo"] <= largura_prop["cartao"],
                   "o campo do nome cabe no cartao", largura_prop)
            pagina.evaluate("""() => {
              const d = {tipo: 'servico', titulo: '', campos: {nome: '', cliente: '', descricao: ''},
                porque: '“abra” e “serviço”', falta: 'não achei o nome do serviço nessa frase'};
              $('teste-proposta').innerHTML = cartaoProposta(d);
            }""")
            checar(
                pagina.evaluate("() => document.querySelector('#teste-proposta .etiqueta.atencao').textContent === 'falta um dado' && document.querySelector('#teste-proposta .explica').textContent.includes('não achei o nome')"),
                "sem nome, o cartao diz o que falta em vez de inventar",
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
                "async (id) => { const r = await (await fetch('/api/documentos/' + id, {method: 'DELETE'})).json(); if (r.lixeira) await fetch('/api/lixeira/' + r.lixeira, {method: 'DELETE'}); }", id_planilha
            )

            test_celular(navegador, base)
            navegador.close()
    finally:
        api.estado.tarefas.apagar(tarefa_do_teste)
        servidor.should_exit = True

    return _fim()


if __name__ == "__main__":
    raise SystemExit(main())
