"""
O e-mail pela conversa (pacote de telas: `Conversa - E-mail` e `Conversa -
Escrever e-mail`; src/email_pela_conversa.py, js/85-email-na-conversa.js).

  - a frase vira pedido de abrir ou de responder, com quem e o que pedir;
    "responda em português" e "responda que sim" nao viram
  - o codigo de verificacao, o prazo e o remetente de nao-responder saem
    por regra, e a frase da conversa diz so o que achou
  - as conferencias: os valores do texto estao no e-mail ou no Acervo (o
    total que e soma dos outros conta), "até sexta" pede para confirmar a
    data, e o envio diz se passa por Aprovacoes
  - na tela: abrir o e-mail mostra o codigo, a mensagem no quadro isolado e
    a barra "No e-mail / Na conversa"; responder poe o envelope na conversa
    e o texto no lugar da caixa; enviar pede o sim e vira pedido em
    Aprovacoes, e o resultado entra na conversa

IMAP e modelo sao dubles: nada toca a rede.

    python tests/test_email_conversa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-emc-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import email_pela_conversa as emc  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


# ------------------------------------------------------------- a regra


def test_pedido() -> None:
    print("\no pedido na frase")
    casos = {
        "abra o último e-mail do Mercado Pago": ("abrir", "Mercado Pago", ""),
        "Abre a última mensagem da Priscila Almeida": ("abrir", "Priscila Almeida", ""),
        "mostre o e-mail da Priscila sobre a parcela": ("abrir", "Priscila", ""),
        "responda a Priscila confirmando o acordo da parcela de setembro": ("responder", "Priscila", "confirmando o acordo da parcela de setembro"),
        "Responda o e-mail da Cooperativa Rio Fresco": ("responder", "Cooperativa Rio Fresco", ""),
        "Por favor, responda ao Carlos dizendo que recebi": ("responder", "Carlos", "dizendo que recebi"),
    }
    for frase, (acao, quem, pedido) in casos.items():
        d = emc.ler_pedido(frase) or {}
        checar((d.get("acao"), d.get("quem"), d.get("pedido")) == (acao, quem, pedido), f"“{frase}”", d)
    for frase in ("responda em português", "responda que sim", "abra o contrato de honorários", "qual a multa do contrato?"):
        checar(emc.ler_pedido(frase) is None, f"“{frase}” não é pedido de e-mail")
    # o e-mail novo
    d = emc.ler_pedido("escreva um e-mail para a Priscila dizendo que a audiência foi remarcada para quinta") or {}
    checar((d.get("acao"), d.get("quem"), d.get("pedido")) == ("escrever", "Priscila", "dizendo que a audiência foi remarcada para quinta"), "o e-mail novo", d)
    d = emc.ler_pedido("manda um email pra contato@riofresco.coop.br pedindo o comprovante") or {}
    checar(d.get("acao") == "escrever" and d.get("email") == "contato@riofresco.coop.br" and d.get("pedido") == "pedindo o comprovante", "para um endereço", d)
    d = emc.ler_pedido("escreva um e-mail para Wagner Antônio dizendo: Olá, Wagner. A audiência foi remarcada.") or {}
    checar(d.get("acao") == "escrever" and d.get("quem") == "Wagner Antônio", "o “Mandar por e-mail” do WhatsApp", d)

    class _Novo:
        def ask(self, pergunta, contexto=""):
            return "Assunto: Audiência remarcada\n\nOlá, Priscila,\n\nA audiência foi remarcada para quinta.\n\nAtenciosamente,\nFulano de Tal"
    assunto, texto, _aviso = emc.escrever_novo(_Novo(), "Priscila Almeida", "dizendo que a audiência foi remarcada para quinta")
    checar(assunto == "Audiência remarcada" and texto.startswith("Olá, Priscila,") and texto.endswith("Atenciosamente,"),
           "o assunto sai da primeira linha e a assinatura inventada sai", (assunto, texto))


def test_mensagem() -> None:
    print("\no que a mensagem tem, por regra")
    checar(emc.codigo_de_verificacao("Seu código de verificação chegou", "Use este código 417112 agora") == "417112", "o código de verificação")
    checar(emc.codigo_de_verificacao("Reunião", "nos vemos em 2026 às 15h") == "", "sem gatilho, sem código")
    checar(emc.sem_resposta("nao-responder") and emc.sem_resposta("no-reply") and not emc.sem_resposta("priscila.almeida"),
           "o remetente de não-responder")
    m = {"de_nome": "Mercado Pago", "de_email": "nao-responder@mercadopago.com", "quando": "2026-09-26T04:10:00", "assunto": "Código"}
    frase = emc.frase_da_mensagem(m, "417112")
    checar(frase == "Abri aqui. É um código de verificação de 26 de setembro — não achei prazo, e o remetente não recebe resposta.", "a frase de abrir", frase)
    m2 = {"de_nome": "Priscila", "de_email": "p@x.br", "quando": "2026-09-30T10:00:00", "assunto": "Prazo",
          "prazo": "2026-10-05", "prazo_trecho": "até o dia 05/10", "anexos": [{"nome": "a.pdf"}]}
    frase = emc.frase_da_mensagem(m2, "")
    checar("achei um prazo, 05/10" in frase and "Tem 1 anexo." in frase and "não recebe" not in frase, "com prazo e anexo, sem prometer resposta", frase)


def test_conferir() -> None:
    print("\nas conferências")
    corpo = ("valor da parcela: R$ 6.000,00; juros de R$ 36,00, desde que o pagamento saia até sexta-feira, 02/10. "
             "O total fica em R$ 6.036,00.")
    itens = emc.conferir(corpo, "a parcela de R$ 6.000,00", [("CONTRATO DE HONORÁRIOS.pdf", "juros de R$ 36,00 ao mês")], date(2026, 10, 1), True)
    textos = [i["texto"] for i in itens]
    checar(itens[0]["ok"] and "CONTRATO DE HONORÁRIOS.pdf" in textos[0] and "R$ 6.036,00 é a soma" in textos[0], "os valores batem, e o total é a soma", textos[0])
    checar(textos[1] == "“até sexta-feira” — confirme se é 02/10", "“até sexta” pede para confirmar a data", textos[1])
    checar(textos[-1] == "passa por Aprovações antes de sair", "e diz que passa por Aprovações", textos[-1])
    itens = emc.conferir("O valor é R$ 999,00 até sexta, 09/10.", "", [], date(2026, 10, 1), False)
    checar(not itens[0]["ok"] and "R$ 999,00 não aparece" in itens[0]["texto"], "o valor que não está em lugar nenhum pede conferência", itens[0])
    checar("seria 02/10" in itens[1]["texto"] and "09/10" in itens[1]["texto"], "a data que não bate com o dia da semana", itens[1])
    checar("Enviar" in itens[-1]["texto"], "sem Aprovações, diz que sai no clique", itens[-1])


# --------------------------------------------------------------- a tela

HTML_MP = ("<div style='background:#fff;padding:24px;font-family:Arial'><p>Use este código</p>"
           "<p style='font-size:28px;letter-spacing:8px'>417112</p><p>Por segurança, não compartilhe seu código com ninguém.</p>"
           "<img src='https://exemplo.invalid/logo.png'></div>")
CORPO_PRISCILA = ("Olá, Matheus! Conforme conversamos hoje, a parcela de setembro (2/10) do contrato de honorários, de R$ 6.000,00, "
                  "venceu em 12/09. Podemos pagar até sexta, com os juros de R$ 36,00 e sem a multa? Obrigada, Priscila.")
RASCUNHO = ("Olá, Priscila,\n\nObrigado pela conversa de hoje. Confirmo o que combinamos sobre a parcela 2/10 do contrato de honorários, "
            "vencida em 12/09: o valor da parcela é de R$ 6.000,00, a multa de 2% fica dispensada desde que o pagamento saia até "
            "sexta-feira, e os juros proporcionais são de R$ 36,00.\n\nO total fica em R$ 6.036,00.\n\nAtenciosamente,\nMatheus Uener")


class _Modelo:
    model = "duble"

    def __init__(self):
        self.chamadas = []

    def ask(self, pergunta, contexto="", **_):
        self.chamadas.append((pergunta, contexto))
        if "O que o advogado pediu para a resposta" in pergunta:
            return RASCUNHO
        if "e-mail NOVO" in pergunta:
            return "Assunto: Comprovante da parcela\n\nOlá, Priscila,\n\nPode me mandar o comprovante da parcela de setembro?\n\nAtenciosamente,"
        if "Responda a\npergunta dele" in pergunta or "pergunta dele sobre o e-mail" in pergunta:
            return "É o código 417112, do Mercado Pago, de 26 de setembro."
        return "A dispensa da multa vale só para esta parcela."

    def __getattr__(self, nome):
        raise AttributeError(nome)


def _dubles(api):
    import correio

    msgs = [
        correio.Mensagem(uid="301", de_nome="Mercado Pago", de_email="nao-responder@mercadopago.com", para="pix@paulus.ia.br",
                         assunto="Seu código de verificação chegou", quando="2026-09-26T04:10:00", quando_curto="26 set",
                         corpo="Use este código\n417112\nPor segurança, não compartilhe seu código com ninguém.", html=HTML_MP, imagens_remotas=1),
        correio.Mensagem(uid="302", de_nome="Priscila Almeida", de_email="priscila.almeida@riofresco.coop.br", para="advogado@escritorio.adv.br",
                         assunto="Parcela de setembro · contrato de honorários", quando="2026-09-30T16:20:00", quando_curto="ontem",
                         corpo=CORPO_PRISCILA),
    ]

    def listar(conta, senha, *, filtro="tudo", busca="", limite=25, antes_de="", clientes=None):
        b = (busca or "").lower()
        achadas = [m for m in msgs if not b or b in (m.de_nome + " " + m.de_email + " " + m.assunto).lower()]
        if filtro == "nao_lidos":
            achadas = [m for m in achadas if not m.lido]
        return {"mensagens": [dict(m.to_dict(), corpo="", html="") for m in achadas[:limite]], "total": len(achadas),
                "mostrando": len(achadas[:limite]), "nao_lidos": 0, "sem_resposta": 0, "ultimo_uid": "", "tem_mais": False}

    def abrir(conta, senha, uid, *, marcar_lido=True):
        m = next(x for x in msgs if x.uid == uid)
        if marcar_lido:
            m.lido = True
        return correio.Mensagem(**m.to_dict())

    correio.listar = listar
    correio.abrir = abrir
    modelo = _Modelo()
    api.estado.cliente_para = lambda *_a, **_k: modelo
    api.check_ollama = lambda *_a, **_k: (True, "ok")
    return modelo


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    import correio_contas
    from test_gravacoes import _porta_livre, _subir_servidor

    api.estado.contas = correio_contas.Contas(TMP / "contas.json")
    conta = api.estado.contas.salvar_conta({"email": "advogado@escritorio.adv.br", "nome": "Matheus Uener",
                                            "imap_host": "imap.x", "smtp_host": "smtp.x"}, "senha")
    api.estado.contas.lembrar(conta.id, "senha")
    _dubles(api)
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1984, "height": 1064})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)

        # abrir
        pag.fill("#pedido", "abra o último e-mail do Mercado Pago")
        pag.click("#enviar")
        pag.wait_for_selector(".emc-msg", timeout=20000)
        pag.wait_for_timeout(1200)
        frase = pag.evaluate("() => [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop()")
        checar(frase and frase.startswith("Abri aqui. É um código de verificação de 26 de setembro"), "a conversa diz o que a mensagem é", frase)
        codigo = pag.evaluate("() => (document.querySelector('.emc-achado .emc-codigo') || {}).textContent")
        checar(codigo == "417112", "o “Achei na mensagem” traz o código", codigo)
        quadro = pag.evaluate("""() => { const q = document.querySelector('.emc-msg iframe.ex-html-quadro');
          return q ? {sandbox: q.getAttribute('sandbox'), csp: /img-src data:;/.test(q.srcdoc), altura: q.getBoundingClientRect().height} : null; }""")
        checar(quadro and "allow-scripts" not in quadro["sandbox"] and quadro["csp"], "a mensagem no quadro isolado, sem script e sem imagem de fora", quadro)
        pe = pag.evaluate("() => document.querySelector('.emc-msg-pe').textContent")
        checar("imagens bloqueadas até você permitir" in pe and "ver só o texto" in pe and "Próxima que pede resposta" in pe, "o pé da mensagem", pe)
        modos = pag.evaluate("() => ({barra: !document.getElementById('emc-modos').hidden, ph: document.getElementById('pedido').placeholder})")
        checar(modos["barra"] and modos["ph"].startswith("Pergunte sobre o e-mail"), "a caixa de pedido ganha “No e-mail / Na conversa”", modos)
        pag.screenshot(path=str(CAPTURAS / "t3-email.png"))

        # pergunta "No e-mail"
        pag.fill("#pedido", "de quando é esse código?")
        pag.click("#enviar")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .resposta .texto')].some(t => t.textContent.includes('417112, do Mercado Pago'))", timeout=15000)
        checar(True, "“No e-mail”, a pergunta é sobre a mensagem")
        id_conversa = pag.evaluate("() => estado.trabalhoId")
        falas = [m.texto for m in api.estado.trabalhos.obter(id_conversa).mensagens]
        checar("de quando é esse código?" in falas, "a pergunta e a resposta entram na conversa", falas[-2:])

        # a próxima que pede resposta fica na conversa
        pag.click("[data-emc-proxima]")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .resposta .texto')].some(t => t.textContent.startsWith('A próxima que pede resposta: Priscila Almeida'))", timeout=15000)
        guardada = api.estado.trabalhos.obter(id_conversa).mensagens[-1]
        checar(guardada.texto.startswith("A próxima que pede resposta: Priscila Almeida") and (guardada.proposta or {}).get("campos", {}).get("uid") == "302",
               "a próxima que pede resposta fica guardada na conversa, com o cartão", guardada.texto[:80])
        pag.reload(wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.evaluate(f"() => abrirTrabalho('{id_conversa}')")
        pag.wait_for_selector(".emc-msg", timeout=15000)
        checar("A próxima que pede resposta" in pag.evaluate("() => document.getElementById('centro').textContent"), "e volta ao reabrir")

        # responder, numa conversa nova
        pag.click("#nova")
        pag.wait_for_timeout(600)
        pag.fill("#pedido", "responda a Priscila confirmando o acordo da parcela de setembro")
        pag.click("#enviar")
        pag.wait_for_selector(".emc-env", timeout=20000)
        pag.wait_for_function("() => !document.querySelector('#emc-editor').hidden && document.getElementById('emc-texto').textContent.includes('R$ 6.036,00')", timeout=20000)
        pag.wait_for_timeout(600)
        env = pag.evaluate("""() => ({para: document.querySelector('.emc-env .emc-chip b').textContent,
          assunto: document.getElementById('emc-assunto').value,
          confere: [...document.querySelectorAll('.emc-confere-item')].map(x => x.textContent),
          caixa: document.getElementById('cartao-campo').hidden,
          frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          autoria: document.getElementById('emc-autoria').textContent})""")
        checar(env["para"] == "Priscila Almeida" and env["assunto"] == "Re: Parcela de setembro · contrato de honorários", "o envelope com quem e o assunto", env)
        checar(env["caixa"], "o texto entra no lugar da caixa de pedido")
        checar(any("batem com o e-mail recebido" in c for c in env["confere"]) and any("confirme se é" in c for c in env["confere"])
               and any("Aprovações" in c for c in env["confere"]), "as conferências por regra", env["confere"])
        checar(env["frase"].startswith("Preparei a resposta.") and env["autoria"].startswith("escrito pelo assistente"), "a frase e a autoria", env)

        # o trecho selecionado
        pag.evaluate("""() => { const t = document.getElementById('emc-texto'); const r = document.createRange();
          const n = [...t.querySelectorAll('div')].find(d => d.textContent.includes('O total')); r.selectNodeContents(n);
          const s = getSelection(); s.removeAllRanges(); s.addRange(r); abrirTrechoDoEmail(); }""")
        pag.wait_for_selector("#emc-trecho:not([hidden]) #emc-trecho-pedido", timeout=5000)
        atalhos = pag.evaluate("() => [...document.querySelectorAll('#emc-trecho .emc-atalho')].map(b => b.textContent)")
        checar(atalhos == ["Deixar mais formal", "Encurtar", "Conferir os valores"], "selecionar abre o pedido sobre o trecho", atalhos)
        pag.fill("#emc-trecho-pedido", "diga que a dispensa vale só para esta parcela")
        pag.keyboard.press("Enter")
        pag.wait_for_selector("#emc-texto .emc-mudou", timeout=8000)
        checar("vale só para esta parcela" in pag.evaluate("() => document.querySelector('#emc-texto .emc-mudou').textContent"),
               "o trecho volta reescrito e sublinhado")
        pag.wait_for_timeout(3200)
        guardado = api.estado.trabalhos.obter(pag.evaluate("() => estado.trabalhoId")).contexto.get("email_rascunhos", {}).get("302", {})
        checar("vale só para esta parcela" in guardado.get("corpo", ""), "o rascunho fica guardado na conversa", guardado.get("corpo", "")[:80])
        pag.screenshot(path=str(CAPTURAS / "t3-escrever-email.png"))

        # enviar: pede o sim e vira pedido em Aprovações
        pag.click("#emc-enviar")
        pag.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
        pergunta = pag.evaluate("() => document.getElementById('veu-dialogo').textContent")
        checar("Vai para Aprovações" in pergunta, "enviar pede o sim e diz que vai para Aprovações", pergunta[:120])
        pag.click("#veu-dialogo [data-dialogo='confirmar']")
        try:
            pag.wait_for_selector(".nota-feito", timeout=8000)
        except Exception:  # noqa: BLE001
            print("  DEPURA", erros[:3], pag.evaluate("() => [...document.querySelectorAll('.cert, .aviso-cert, [role=status]')].map(x => x.textContent).join(' | ')"))
            raise
        nota = pag.evaluate("() => [...document.querySelectorAll('.nota-feito')].pop().textContent")
        pendentes = [x for x in api.estado.fila.pendentes if x.categoria == "email"]
        checar("Aprovações" in nota and pendentes, "o pedido fica em Aprovações e a conversa diz", (nota, len(pendentes)))
        checar(pag.evaluate("() => !document.getElementById('cartao-campo').hidden && document.getElementById('emc-editor').hidden"),
               "a caixa de pedido volta")

        # o e-mail novo, com quem recebe achado na ficha
        api.estado.cadastros.salvar({"tipo": "cliente", "nome": "Priscila Almeida", "email": "priscila.almeida@riofresco.coop.br"})
        pag.click("#nova")
        pag.wait_for_timeout(600)
        pag.fill("#pedido", "escreva um e-mail para a Priscila pedindo o comprovante da parcela de setembro")
        pag.click("#enviar")
        pag.wait_for_selector(".emc-env", timeout=20000)
        pag.wait_for_function("() => !document.querySelector('#emc-editor').hidden && document.getElementById('emc-texto').textContent.includes('comprovante')", timeout=20000)
        pag.wait_for_timeout(600)
        novo = pag.evaluate("""() => ({cabeca: document.querySelector('.emc-env-cabeca').textContent,
          para: (document.querySelector('.emc-env .emc-chip small') || {}).textContent || '',
          assunto: document.getElementById('emc-assunto').value,
          frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop()})""")
        checar("Novo e-mailpara Priscila Almeida" in novo["cabeca"] and "priscila.almeida@riofresco.coop.br" in novo["para"], "o envelope do e-mail novo, com a ficha", novo)
        checar(novo["assunto"] == "Comprovante da parcela" and novo["frase"].startswith("Preparei o e-mail."), "o assunto e a frase", novo)
        pag.screenshot(path=str(CAPTURAS / "faltas-email-novo.png"))
        pag.click("#emc-enviar")
        pag.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
        checar("Enviar o e-mail?" in pag.evaluate("() => document.getElementById('veu-dialogo').textContent"), "enviar o e-mail novo pede o sim")
        pag.click("#veu-dialogo [data-dialogo='confirmar']")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.includes('Comprovante da parcela'))", timeout=8000)
        pendentes = [x for x in api.estado.fila.pendentes if x.categoria == "email"]
        checar(any("Comprovante da parcela" in str(x.dados) for x in pendentes), "o e-mail novo fica em Aprovações", len(pendentes))

        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(500)
        largura = pag.evaluate("() => document.documentElement.scrollWidth")
        checar(largura <= 392, "sem rolagem horizontal em 390 px", largura)
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_pedido()
    test_mensagem()
    test_conferir()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
