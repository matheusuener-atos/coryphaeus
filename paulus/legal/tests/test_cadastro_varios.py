"""
Várias fichas de uma vez pela conversa (casos reais de 13/10/2026):

  - "Isso mesmo, eu quero que você cadastre os seguintes qualificados:
    Vendedores: OBEDI ..., e seu conjuge SWEDY ...; Comprador: HUGO ..., e seu
    conjuge ANA ..." -> 4 pessoas, CPFs com máscara, o endereço de "ambos
    residentes" para as duas do grupo, RG/estado civil/profissão/cônjuge/papel
    na observação (fichas_pela_conversa.ler_qualificacoes)
  - a abertura "isso mesmo, eu quero que você" não derruba o pedido
  - só a qualificação colada, sem verbo, vira a mesma proposta
  - "Cadastre as partes Vendedores e Compradores" com o contrato aberto no
    editor lê a qualificação DO DOCUMENTO; "os vendedores" traz só eles;
    "Vendedores e Compradores" nunca é nome de pessoa
  - "crie um contato em que os qualificados... são vendedores" (contato por
    contrato) não é cadastro, e vai para a redação
  - uma pessoa só segue o cadastro de sempre; frase que não é cadastro não vira
  - o /fazer "cadastros" grava as 4 sem duplicar o CPF que já tem ficha
    (completa só o vazio), e nada é gravado antes do sim

    python tests/test_cadastro_varios.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-cdv-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import fichas_pela_conversa as fpc  # noqa: E402
import intencao  # noqa: E402

_falhas: list[str] = []


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


QUALIFICACAO = (
    "Vendedores: OBEDI LOURENÇO SANTOS, portador do RG nº 4091179 PC/PA e CPF nº 752.043.042-15, e seu conjuge "
    "SWEDY PEREIRA SANTOS, portador(a) do RG nº 772.753 SSP/TO e CPF nº 962.136.202-49, ambos residentes e "
    "domiciliados à Avenida Araguaia, S/n, Setor Jardim Vitória, São Félix do Xingu, Pará, 68380-000, doravante "
    "denominados em conjunto como VENDEDORES;\n\n"
    "Comprador: HUGO MAGALHÃES SILVA, brasileiro, casado, pecuarista, portador do RG de nº 8653510 PC/PA, inscrito no "
    "CPF de nº 016.708.042-32, e seu conjuge ANA LUIZA MACEDO DA SILVA, brasileira, casada, do lar, portador do RG de "
    "nº 8207289 PC/PA, inscrito no CPF de nº 051.601.932-51, ambos residentes e domiciliados à Rua América, 639, "
    "Setor Vitória, São Félix do Xingu/PA, doravante denominados em conjunto como COMPRADORES e/ou ADQUIRENTES;"
)
PEDIDO = "Isso mesmo, eu quero que você cadastre os seguintes qualificados:\n\n" + QUALIFICACAO
CONTRATO_HTML = (
    "<h1>CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO</h1><h2>QUALIFICAÇÃO DAS PARTES</h2>" +
    "".join("<p>" + p + "</p>" for p in QUALIFICACAO.split("\n\n")) +
    "<h2>CLÁUSULA PRIMEIRA - DO OBJETO</h2><p>O imóvel descrito no item 3 é vendido pelos VENDEDORES aos COMPRADORES.</p>"
    "<p>São Félix do Xingu, 13 de outubro de 2026.</p><p>VENDEDOR: OBEDI LOURENÇO SANTOS</p>"
)
CONTATO = ("Preciso que você crie um contato em que os qualificados deste instrumento são ambos vendedores do imóvel "
           "descrito no item 3")


def test_leitura() -> None:
    print("\na qualificação, lida por regra")
    pessoas = fpc.ler_qualificacoes(PEDIDO)
    nomes = [p["nome"] for p in pessoas]
    checar(nomes == ["Obedi Lourenço Santos", "Swedy Pereira Santos", "Hugo Magalhães Silva", "Ana Luiza Macedo da Silva"],
           "as 4 pessoas, com o nome em forma própria", nomes)
    checar([p["documento"] for p in pessoas] == ["752.043.042-15", "962.136.202-49", "016.708.042-32", "051.601.932-51"],
           "os CPFs certos, com a máscara", [p["documento"] for p in pessoas])
    checar(all(p["tipo"] == "cliente" and p["pessoa"] == "fisica" and not p["aviso"] for p in pessoas),
           "fichas de cliente, pessoa física, sem aviso", [(p["tipo"], p["pessoa"], p["aviso"]) for p in pessoas])
    if len(pessoas) != 4:
        return
    obedi, swedy, hugo, ana = pessoas
    araguaia = "Avenida Araguaia, S/n, Setor Jardim Vitória, São Félix do Xingu, Pará, 68380-000"
    checar(obedi["endereco"] == swedy["endereco"] == araguaia and obedi["end_cep"] == swedy["end_cep"] == "68380000",
           "“ambos residentes”: o endereço e o CEP valem para os dois vendedores", (obedi["endereco"], swedy["end_cep"]))
    checar(hugo["endereco"] == ana["endereco"] == "Rua América, 639, Setor Vitória, São Félix do Xingu/PA" and not hugo["end_cep"],
           "o endereço dos compradores, sem CEP inventado", (hugo["endereco"], hugo["end_cep"]))
    checar(obedi["observacao"] == "vendedor(a) · RG 4091179 PC/PA · cônjuge de Swedy Pereira Santos",
           "observação do vendedor: papel, RG e cônjuge", obedi["observacao"])
    checar(swedy["observacao"] == "vendedor(a) · RG 772.753 SSP/TO · cônjuge de Obedi Lourenço Santos",
           "o cônjuge dos dois lados (“portador(a)”, “conjuge” sem acento)", swedy["observacao"])
    checar(hugo["observacao"] == "comprador(a) · brasileiro · casado · pecuarista · RG 8653510 PC/PA · cônjuge de Ana Luiza Macedo da Silva",
           "nacionalidade, estado civil e profissão (“do RG de nº”, “inscrito no CPF de nº”)", hugo["observacao"])
    checar(ana["observacao"] == "comprador(a) · brasileira · casada · do lar · RG 8207289 PC/PA · cônjuge de Hugo Magalhães Silva",
           "profissão de duas palavras (“do lar”)", ana["observacao"])
    pj = fpc.ler_qualificacoes("Locador: AGROPECUÁRIA XINGU LTDA, inscrita no CNPJ 11.222.333/0001-81, com sede na Rua A, 10; "
                               "Locatário: JOÃO DA SILVA, brasileiro, solteiro, CPF 529.982.247-25;")
    checar([(p["nome"], p["pessoa"], p["papel"]) for p in pj] ==
           [("Agropecuária Xingu Ltda", "juridica", "locador(a)"), ("João da Silva", "fisica", "locatário(a)")],
           "pessoa jurídica pelo CNPJ, e outros papéis", [(p["nome"], p["pessoa"], p["papel"]) for p in pj])
    import documento

    no_contrato = fpc.ler_qualificacoes(documento.para_texto(documento.ler_html(CONTRATO_HTML)))
    checar([p["nome"] for p in no_contrato] == nomes, "no contrato inteiro: as 4, e a assinatura não repete a pessoa",
           [p["nome"] for p in no_contrato])


def test_intencao() -> None:
    print("\na intenção")
    lido = intencao.ler(PEDIDO)
    checar(lido.tipo == "cadastros" and len(lido.campos["pessoas"]) == 4,
           "“Isso mesmo, eu quero que você cadastre…” com 4 pessoas vira “cadastros”", (lido.tipo, lido.titulo))
    lido = intencao.ler(QUALIFICACAO)
    checar(lido.tipo == "cadastros" and len(lido.campos["pessoas"]) == 4, "só a qualificação colada, sem verbo, também",
           (lido.tipo, lido.titulo))
    lido = intencao.ler("Cadastre as partes Vendedores e Compradores")
    checar(lido.tipo == "cadastros" and lido.campos.get("do_documento") and not lido.campos["pessoas"],
           "“cadastre as partes …” lê do documento, e não procura uma pessoa chamada assim", (lido.tipo, lido.campos))
    lido = intencao.ler("cadastre os vendedores")
    checar(lido.tipo == "cadastros" and lido.campos.get("papeis") == ["vendedor(a)"], "“os vendedores”: só eles", lido.campos)
    lido = intencao.ler(CONTATO)
    checar(lido.tipo == "documentos", "“crie um contato em que os qualificados…” não é cadastro", (lido.tipo, lido.titulo))
    import entrevista

    checar(entrevista.e_trabalho(CONTATO), "… e vai para a redação (contato por contrato)")
    checar(not entrevista.e_trabalho("crie um contato em que eu possa falar"), "sem papel de contrato, “contato” fica contato")
    lido = intencao.ler("crie um contato em que eu possa falar com a cliente")
    checar(lido.tipo != "cadastro", "nome nunca começa por conector (a ficha de “Em”)", (lido.tipo, lido.titulo))
    lido = intencao.ler("cadastre o cliente João Souza, CPF 529.982.247-25")
    checar(lido.tipo == "cadastro" and lido.campos["nome"] == "João Souza" and lido.campos["documento"] == "529.982.247-25",
           "uma pessoa só: o cadastro de sempre", (lido.tipo, lido.campos))
    lido = intencao.ler("isso mesmo, eu quero que você cadastre o cliente João Souza, CPF 529.982.247-25")
    checar(lido.tipo == "cadastro" and lido.campos["nome"] == "João Souza", "a abertura relaxada vale para uma pessoa", (lido.tipo, lido.campos))
    lido = intencao.ler("cadastre o cliente Vendedores e Compradores")
    checar(not (lido.tipo == "cadastro" and lido.campos.get("nome")), "papel de contrato não é nome", (lido.tipo, lido.campos))
    for frase in ("qual o CPF do vendedor no contrato?", "eu cadastrei o João ontem?", "isso mesmo, qual o valor do contrato?",
                  "o comprador já pagou a segunda parcela?", "ok, e a multa?"):
        lido = intencao.ler(frase)
        checar(lido.tipo not in ("cadastro", "cadastros"), f"não é cadastro: “{frase}”", (lido.tipo, lido.titulo))
    checar(intencao.ler("cadastra o aluguel como despesa fixa").tipo == "ficha", "a despesa fixa segue o caminho dela")


def _eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


def test_conversa() -> None:
    print("\npela conversa e pelo /fazer")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    e = api.estado
    # Hugo já tem ficha, com o CPF e sem endereço: não ganha outra.
    hugo_id = e.cadastros.salvar({"tipo": "cliente", "nome": "Hugo M. Silva", "documento": "016.708.042-32"})
    antes = len(e.cadastros.listar())

    def perguntar(frase: str, **extra) -> tuple[str, dict]:
        t = c.post("/api/trabalhos", json={"pedido": frase}).json()
        r = c.post(f"/api/trabalhos/{t['id']}/perguntar", json={"pergunta": frase, **extra})
        ev = _eventos(r.text)
        return t["id"], {"texto": "".join(d.get("t", "") for k, d in ev if k == "token"),
                         "proposta": next((d for k, d in ev if k == "proposta"), {})}

    tid, r = perguntar(PEDIDO)
    p = r["proposta"]
    pessoas = (p.get("campos") or {}).get("pessoas") or []
    checar(p.get("tipo") == "cadastros" and len(pessoas) == 4, "a proposta lista as 4 pessoas", (p.get("tipo"), r["texto"][:120]))
    checar(r["texto"].startswith("Achei 4 pessoas para cadastrar") and "1 já está em Cadastros" in r["texto"],
           "a frase curta diz quantas e quem já existe", r["texto"])
    checar(len(e.cadastros.listar()) == antes, "nada gravado antes do sim")
    checar([bool(x.get("ja_existe")) for x in pessoas] == [False, False, True, False], "o cartão marca quem já tem ficha",
           [x.get("ja_existe") for x in pessoas])

    r = c.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "cadastros", "campos": {"pessoas": pessoas}})
    feito = r.json()
    checar(r.status_code == 200 and feito.get("onde") == "cadastros", "o sim grava", r.text[:200])
    fichas = e.cadastros.listar()
    checar(len(fichas) == antes + 3, "3 fichas novas: o CPF que já existia não duplica", len(fichas) - antes)
    hugo = e.cadastros.obter(hugo_id)
    checar(hugo["nome"] == "Hugo M. Silva" and hugo["endereco"].startswith("Rua América, 639")
           and hugo["observacao"].startswith("comprador(a)"), "a ficha antiga só ganhou o que estava vazio", hugo)
    checar(feito.get("resumo", "").startswith("Cadastrei 3 pessoas em Cadastros; completei a ficha de Hugo M. Silva"),
           "o retorno diz quantas foram criadas e qual foi completada", feito.get("resumo"))
    obedi = next((f for f in fichas if f["nome"] == "Obedi Lourenço Santos"), {})
    checar(obedi.get("documento") == "752.043.042-15" and obedi.get("tipo") == "cliente"
           and (e.cadastros.obter(obedi["id"]) or {}).get("end_cep") == "68380000",
           "a ficha nova com CPF, endereço e CEP", obedi)
    r = c.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "cadastros", "campos": {"pessoas": pessoas}})
    checar(len(e.cadastros.listar()) == antes + 3 and "já estava" in r.json().get("resumo", ""),
           "confirmar de novo não duplica ninguém", r.json().get("resumo"))
    ruim = dict(pessoas[0], nome="Fulano Errado", documento="111.111.111-12")
    r = c.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "cadastros", "campos": {"pessoas": [ruim]}})
    checar(r.status_code == 400 and "Fulano Errado" in r.text, "CPF que não confere volta como erro, sem gravar", r.text[:160])

    print("\n“cadastre as partes” com o contrato aberto no editor")
    doc_id = e.documentos.criar("CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO", "texto", CONTRATO_HTML, None)
    _, r = perguntar("Cadastre as partes Vendedores e Compradores", editor=doc_id)
    p = r["proposta"]
    nomes = [x["nome"] for x in (p.get("campos") or {}).get("pessoas") or []]
    checar(p.get("tipo") == "cadastros" and len(nomes) == 4 and "Vendedores e Compradores" not in r["texto"],
           "as 4 pessoas lidas do documento, e não uma ficha chamada “Vendedores e Compradores”", (nomes, r["texto"][:160]))
    checar("CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO" in r["texto"], "a frase diz de qual documento leu", r["texto"])
    _, r = perguntar("cadastre os vendedores", editor=doc_id)
    nomes = [x["nome"] for x in (r["proposta"].get("campos") or {}).get("pessoas") or []]
    checar(nomes == ["Obedi Lourenço Santos", "Swedy Pereira Santos"], "“os vendedores”: só os dois", nomes)
    _, r = perguntar("Cadastre as partes Vendedores e Compradores")
    checar(not r["proposta"] and r["texto"].startswith("Não achei a qualificação das partes"),
           "sem documento aberto, diz o que fazer em vez de abrir uma ficha", r["texto"])


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    antes = len(e.cadastros.listar())
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
        texto = QUALIFICACAO.replace("OBEDI", "OSIAS").replace("752.043.042-15", "529.982.247-25") \
            .replace("SWEDY", "SUELI").replace("962.136.202-49", "111.444.777-35") \
            .replace("HUGO", "HÉLIO").replace("016.708.042-32", "390.533.447-05") \
            .replace("ANA LUIZA", "ANA PAULA").replace("051.601.932-51", "714.602.380-01")
        pag.fill("#pedido", texto)
        pag.click("#enviar")
        pag.wait_for_selector("[data-cdv-cartao]", timeout=20000)
        tela = pag.evaluate("""() => ({linhas: [...document.querySelectorAll('.fcn-cdv b')].map(b => b.textContent),
          botao: document.querySelector('[data-cdv-fazer]').textContent})""")
        checar(len(tela["linhas"]) == 4 and tela["botao"] == "Cadastrar as 4", "o cartão com as 4 pessoas e o botão", tela)
        pag.click("[data-cdv='1']")
        checar(pag.evaluate("() => document.querySelector('[data-cdv-fazer]').textContent") == "Cadastrar as 3",
               "desmarcar alguém muda o botão")
        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(300)
        checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "sem rolagem horizontal em 390 px")
        pag.set_viewport_size({"width": 1600, "height": 1000})
        pag.click("[data-cdv-fazer]")
        pag.wait_for_selector("[data-cdv-abrir]", timeout=10000)
        feito = pag.evaluate("""() => ({rotulo: document.querySelector('.proposta .rotulo').textContent,
          abrir: document.querySelectorAll('[data-cdv-abrir]').length})""")
        checar(feito == {"rotulo": "feito", "abrir": 3} and len(e.cadastros.listar()) == antes + 3,
               "o cartão vira “feito”, com “Abrir em Cadastros” para cada ficha", (feito, len(e.cadastros.listar()) - antes))
        pag.click("[data-cdv-abrir]")
        pag.wait_for_selector(".cad-dialogo", timeout=8000)
        checar(pag.evaluate("() => document.querySelector('.cad-dialogo').textContent.includes('Osias Lourenço Santos')"),
               "“Abrir em Cadastros” abre a ficha")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_leitura()
    test_intencao()
    test_conversa()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"{len(_falhas)} falha(s):")
        for f in _falhas:
            print("  -", f)
        sys.exit(1)
    print("todos os testes passaram")
