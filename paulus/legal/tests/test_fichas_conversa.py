"""
Os cadastros pela conversa (pacote de telas: `Conversa - Cadastro`, `-
Equipe`, `- Despesa fixa`; src/fichas_pela_conversa.py, js/86-fichas-na-
conversa.js).

  - a frase vira a pessoa da equipe (nome, função, salário, e-mail, início,
    convite) ou a despesa fixa; "cadastra X como cliente" corta o nome
  - o contrato anexo, lido por regra: valor, dia, reajuste, quem recebe
  - o nome procurado no Acervo traz o CPF/CNPJ e o endereço que estão perto
    dele, e diz em quantos documentos
  - a despesa fixa com "lançar todo mês" entra no Financeiro uma vez por mês
  - na tela: a ficha abre na coluna com o que foi lido; a correção escrita
    marca o campo com "novo"; salvar grava, liga os documentos e a conversa
    diz o que foi feito

    python tests/test_fichas_conversa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-fcn-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import fichas_pela_conversa as fpc  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


CONTRATO = ("CONTRATO DE LOCAÇÃO NÃO RESIDENCIAL — SALA 204. LOCADORA: Imobiliária Xingu Ltda., inscrita no CNPJ 11.222.333/0001-81, "
            "e-mail financeiro@imobxingu.com.br. O aluguel mensal é de R$ 4.500,00, pago até o dia 10 de cada mês. "
            "O valor será reajustado anualmente pelo IGP-M no mês de março. Vigência até 31/03/2028.")


def test_regras() -> None:
    print("\nas regras")
    p = fpc.ler_equipe("a Larissa Costa começa segunda como estagiária, salário de 1.800. coloca ela na equipe e convida pro PAULUS "
                       "— o e-mail é larissa.costa@gmail.com", date(2026, 10, 1))
    checar(p and (p["nome"], p["funcao"], p["salario"], p["email"], p["inicio"], p["convidar"], p["vinculo"]) ==
           ("Larissa Costa", "Estagiária", "R$ 1.800,00", "larissa.costa@gmail.com", "2026-10-05", True, "estagio"), "a pessoa da equipe", p)
    checar(fpc.ler_equipe("marque uma reunião com a equipe amanhã") is None, "reunião com a equipe não é pessoa nova")
    d = fpc.ler_despesa_fixa("cadastra o aluguel como despesa fixa, o contrato tá anexo")
    checar(d and d["nome"] == "Aluguel", "a despesa fixa", d)
    d = fpc.ler_despesa_fixa("cadastra a internet como despesa fixa, R$ 129,90 todo dia 15")
    checar(d and (d["valor"], d["dia"]) == ("R$ 129,90", 15), "com valor e dia na frase", d)
    c = fpc.ler_contrato(CONTRATO)
    checar((c.get("valor"), c.get("dia"), c.get("fornecedor"), c.get("reajuste"), c.get("ate")) ==
           ("R$ 4.500,00", 10, "Imobiliária Xingu Ltda", "Reajuste anual pelo IGP-M em março", "03/2028"), "o contrato, por regra", c)
    import intencao
    lido = intencao.ler("cadastra a congregação cristã como cliente, ela aparece em vários adiantamentos")
    checar(lido.tipo == "cadastro" and lido.campos["nome"] == "Congregação Cristã", "“como cliente” corta o nome", lido.campos)
    checar(fpc.corrigir("o CPF certo é 529.982.247-25") == {"documento": "529.982.247-25"}, "a correção escrita")
    checar(fpc.aviso_do_documento("298.077.192-91", "juridica") == "confira: é um CPF, não um CNPJ", "o CPF numa pessoa jurídica")


class _Doc:
    def __init__(self, nome, texto, sha1):
        self.name, self.path, self.text, self.sha1 = nome, "", texto, sha1
        self.pages, self.ocr = 1, 0

    @property
    def chars(self):
        return len(self.text)


def _acervo():
    return [
        _Doc("ADIANTAMENTO VIAGEM 410 - WERMESSON.PDF", "Recebi da CONGREGAÇÃO CRISTÃ NO BRASIL, CPF 298.077.192-91, a quantia de R$ 800,00, em 14/08/2026.", "a1"),
        _Doc("ENVELOPE 409 - VALDIVINO.pdf", "Remetente: Congregação Cristã no Brasil, Av. Paulo São, 1193 - São Félix do Xingu/PA. Postado em 02/09/2026.", "a2"),
        _Doc("Recibo coletivo setembro.docx", "valores repassados à Congregação Cristã no Brasil em 30/09/2026", "a3"),
        _Doc("Contrato de locação - sala 204.pdf", CONTRATO, "a4"),
    ]


def test_lancar_fixas() -> None:
    print("\nlançar a despesa fixa todo mês")
    import api

    e = api.estado
    fid = e.cadastros.salvar({"tipo": "despesa", "nome": "Internet", "honorario": "R$ 129,90", "dia_vencimento": 31, "lancar_mensal": 1})
    criados = e.financeiro.lancar_fixas(e.cadastros.listar(tipo="despesa"), "2026-02")
    de_novo = e.financeiro.lancar_fixas(e.cadastros.listar(tipo="despesa"), "2026-02")
    lanc = [x for x in e.financeiro.listar(tipo="despesa", mes="2026-02") if x["cadastro_id"] == fid]
    checar(len(criados) == 1 and not de_novo and lanc and lanc[0]["vencimento"] == "2026-02-28" and lanc[0]["centavos"] == 12990,
           "entra uma vez, no último dia do mês quando o dia passa dele", lanc)
    e.cadastros.apagar(fid)


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
    e.cadastros.salvar({"tipo": "socio", "nome": "Valter Uener da Silva", "observacao": "Advogado"})
    e.cadastros.salvar({"tipo": "despesa", "nome": "Contabilidade", "honorario": "R$ 1.200,00", "dia_vencimento": 5, "fornecedor": "Contábil Rio Fresco"})
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
        pag.goto(base + "/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)
        # Depois de subir: a subida carrega o Acervo de novo.
        e.searcher.documents.extend(_acervo())

        # o cliente
        pag.fill("#pedido", "cadastra a congregação cristã como cliente, ela aparece em vários adiantamentos")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='ficha']", timeout=20000)
        pag.wait_for_timeout(800)
        tela = pag.evaluate("""() => ({
          frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          docs: [...document.querySelectorAll('.fcn-doc b')].map(b => b.textContent),
          nome: document.querySelector('#lado-ferramenta [data-fcn=nome]').value,
          doc: document.querySelector('#lado-ferramenta [data-fcn=documento]').value,
          end: document.querySelector('#lado-ferramenta [data-fcn=endereco]').value,
          notas: [...document.querySelectorAll('#lado-ferramenta .fcn-rotulo em')].map(x => x.textContent),
          largura: document.getElementById('lateral').getBoundingClientRect().width})""")
        checar(tela["frase"].startswith("Achei Congregação Cristã no Brasil em 3 documentos") and "ligada a 2 documentos" in tela["frase"],
               "a conversa diz onde achou, e quantos entram na ficha (os que têm dado)", tela["frase"])
        checar(len(tela["docs"]) == 3 and tela["nome"] == "CONGREGAÇÃO CRISTÃ NO BRASIL", "onde aparece, e o nome como está nos documentos", tela)
        checar(tela["doc"] == "298.077.192-91" and tela["end"].startswith("Av. Paulo São, 1193"), "o CPF e o endereço lidos perto do nome", tela)
        checar("lido em 3 documentos" in tela["notas"] and "confira: é um CPF, não um CNPJ" in tela["notas"], "de onde veio, e o que conferir", tela["notas"])
        checar(410 <= tela["largura"] <= 430, "a ficha na coluna de 420", tela["largura"])
        caixa = pag.evaluate("""() => ({ph: document.getElementById('pedido').placeholder,
          fora: [...document.querySelectorAll('#lado-ferramenta input, #lado-ferramenta .escolha-botao')].filter(x => x.getBoundingClientRect().right > document.getElementById('lateral').getBoundingClientRect().right - 8).length,
          aberta: fichaAbertaNoLado(), papel: papelDoLado()})""")
        checar(caixa["ph"] == "Corrija um dado ou cadastre outra pessoa…", "a caixa de pedido diz que corrige a ficha", caixa)
        checar(caixa["fora"] == 0, "nenhum campo passa da coluna", caixa)
        pag.screenshot(path=str(CAPTURAS / "t4-cadastro.png"))
        pag.fill("#pedido", "o telefone é (94) 3435-1200")
        pag.click("#enviar")
        pag.wait_for_function("() => document.querySelector('#lado-ferramenta [data-fcn=telefone]').value.includes('3435')", timeout=8000)
        novo = pag.evaluate("() => document.querySelector('#lado-ferramenta [data-fcn=telefone]').closest('.fcn-campo').querySelector('.fcn-novo') !== null")
        checar(novo, "a correção escrita muda o campo e marca “novo”")
        pag.click("#lado-ferramenta [data-fcn-salvar]")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.startsWith('Cadastrei'))", timeout=8000)
        ficha = next((f for f in e.cadastros.listar(tipo="cliente") if f["nome"] == "CONGREGAÇÃO CRISTÃ NO BRASIL"), None)
        ligados = e.cadastros.documentos_de(ficha["id"]) if ficha else []
        checar(ficha and ficha["telefone"] and len(ligados) == 2, "salvar grava a ficha e liga os documentos marcados", (ficha, ligados))
        nota = pag.evaluate("() => [...document.querySelectorAll('.nota-feito')].pop().textContent")
        checar("como cliente, ligado a 2 documentos" in nota, "a conversa diz o que foi feito", nota)

        # a despesa fixa, com o contrato anexo
        pag.click("#nova")
        pag.wait_for_timeout(500)
        pag.evaluate("() => { estado.escopo = ['Contrato de locação - sala 204.pdf']; }")
        pag.fill("#pedido", "cadastra o aluguel como despesa fixa, o contrato tá anexo")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='ficha'] [data-fcn=fornecedor]", timeout=20000)
        pag.wait_for_timeout(800)
        desp = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          valor: document.querySelector('#lado-ferramenta [data-fcn=valor]').value,
          forn: document.querySelector('#lado-ferramenta [data-fcn=fornecedor]').value,
          linhas: [...document.querySelectorAll('.fcn-desp:not(.fcn-titulos) b')].map(b => b.textContent),
          liga: document.querySelector('#lado-ferramenta [data-fcn-liga=lancar_mensal]').classList.contains('on')})""")
        checar(desp["frase"].startswith("Li “Contrato de locação - sala 204.pdf” e preenchi a despesa ao lado: R$ 4.500,00, todo dia 10"),
               "a conversa diz o que leu no contrato", desp["frase"])
        checar(desp["valor"] == "R$ 4.500,00" and desp["forn"] == "Imobiliária Xingu Ltda" and desp["liga"], "a despesa preenchida, lançando todo mês", desp)
        checar(desp["linhas"][:2] == ["Aluguel", "Contabilidade"], "a tabela com a nova marcada e as que já existem", desp["linhas"])
        pag.screenshot(path=str(CAPTURAS / "t4-despesa-fixa.png"))
        pag.click("#lado-ferramenta [data-fcn-salvar]")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.startsWith('Cadastrei a despesa'))", timeout=8000)
        aluguel = next((f for f in e.cadastros.listar(tipo="despesa") if f["nome"] == "Aluguel"), {})
        checar(aluguel.get("fornecedor") == "Imobiliária Xingu Ltda" and aluguel.get("lancar_mensal") == 1 and aluguel.get("dia_vencimento") == 10,
               "salvar grava fornecedor e “lançar todo mês”", aluguel)

        # a equipe
        pag.click("#nova")
        pag.wait_for_timeout(500)
        pag.fill("#pedido", "a Larissa Costa começa segunda como estagiária, salário de 1.800. coloca ela na equipe e convida pro PAULUS — o e-mail é larissa.costa@gmail.com")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='ficha'] [data-fcn=funcao]", timeout=20000)
        pag.wait_for_timeout(800)
        eq = pag.evaluate("""() => ({funcao: document.querySelector('#lado-ferramenta [data-fcn=funcao]').value,
          salario: document.querySelector('#lado-ferramenta [data-fcn=salario]').value,
          linhas: [...document.querySelectorAll('.fcn-eq:not(.fcn-titulos) b')].map(b => b.textContent),
          pode: [...document.querySelectorAll('#lado-ferramenta .fcn-pode li')].map(l => l.textContent),
          botao: document.querySelector('#lado-ferramenta [data-fcn-salvar]').textContent})""")
        checar(eq["funcao"] == "Estagiária" and eq["salario"] == "R$ 1.800,00", "a pessoa preenchida", eq)
        checar("Larissa Costa" in eq["linhas"] and "Valter Uener da Silva" in eq["linhas"], "a equipe com a nova pessoa", eq["linhas"])
        checar(eq["pode"] and any("Financeiro" in x for x in eq["pode"]) and eq["botao"].strip().endswith("Salvar e convidar"),
               "o que o papel pode sai das permissões de verdade", eq)
        pag.screenshot(path=str(CAPTURAS / "t4-equipe.png"))
        pag.click("#lado-ferramenta [data-fcn-salvar]")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.startsWith('Pus'))", timeout=10000)
        larissa = next((f for f in e.cadastros.listar(tipo="colaborador") if f["nome"] == "Larissa Costa"), {})
        checar(larissa.get("salario_centavos") == 180000 and larissa.get("vinculo") == "estagio" and larissa.get("observacao") == "Estagiária",
               "salvar grava a pessoa na folha, com a função", larissa)

        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(500)
        checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "sem rolagem horizontal em 390 px")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_regras()
    test_lancar_fixas()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
