"""
Testes do editor e da planilha.

Duas famílias de erro guiam o que está aqui.

No documento: PDF e DOCX saindo diferentes um do outro. Num contrato, "a versão
em Word está diferente da versão em PDF" não é detalhe de formatação — por isso
os dois nascem da mesma leitura, e o teste confere que o texto sobrevive aos
dois caminhos.

Na planilha: número lido errado. "12.000,00" é doze mil, não doze. Ler isso
errado num campo de honorários troca o valor por mil vezes menos, e ninguém
confere planilha somando de cabeça.

E, nos dois: fórmula vinda de arquivo de terceiro nunca pode executar nada.

    python tests/test_escrita.py
"""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import documento as D  # noqa: E402
import planilha as P  # noqa: E402
from base import Base  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


CONTRATO = (
    "<h1>CONTRATO DE PRESTAÇÃO DE SERVIÇOS</h1>"
    "<h2>1. DAS PARTES</h2>"
    "<p style='text-align:justify'>De um lado a\n"
    "<b>COOPERATIVA BRASILEIRA</b>, CNPJ 11.222.333/0001-81, doravante\n"
    "<b>CONTRATANTE</b>.</p>"
    "<h2>2. DO OBJETO</h2>"
    "<p>Reuniões com <u>48 (quarenta e oito) horas</u> de antecedência.<br>Segunda linha.</p>"
    "<ul><li>análise de contratos</li><li>acompanhamento de prazos</li></ul>"
    "<ol><li>primeiro</li><li>segundo</li></ol>"
    "<p style='text-align:center'><i>Goiânia, 10 de setembro de 2026.</i></p>"
)


# ------------------------------------------------------------- documento


def test_ler_html() -> None:
    print("\nleitura do que o editor escreve")
    blocos = D.ler_html(CONTRATO)
    tipos = [b.tipo for b in blocos]

    checar(len(blocos) == 10, f"dez blocos, sem paragrafo fantasma (achou {len(blocos)})", str(tipos))
    checar(tipos[0] == "titulo1" and tipos[1] == "titulo2", "reconhece os titulos")
    checar(tipos.count("item") == 2 and tipos.count("numerado") == 2,
           "separa lista com marcador de lista numerada")
    checar(blocos[2].alinhamento == "justificado", f"le o alinhamento ({blocos[2].alinhamento})")
    checar(blocos[-1].alinhamento == "centro", "le o centralizado")
    checar(any(t.negrito for b in blocos for t in b.trechos), "guarda o negrito")
    checar(any(t.sublinhado for b in blocos for t in b.trechos), "guarda o sublinhado")
    checar(any(t.italico for b in blocos for t in b.trechos), "guarda o italico")

    # A quebra de linha do fonte HTML e espaco; so o <br> quebra.
    paragrafo = blocos[2].texto
    checar("\n" not in paragrafo,
           "quebra de linha do fonte NAO vira quebra no documento", repr(paragrafo[:60]))
    checar("\n" in blocos[4].texto, "mas o <br> vira quebra de verdade")
    checar("de um lado a COOPERATIVA" in paragrafo.replace("De", "de"),
           f"as palavras nao grudam nem somem ({paragrafo[:52]!r})")

    # Marcacao desconhecida nao pode engolir texto de contrato.
    estranho = D.ler_html("<p>antes <coisa-nova>importante</coisa-nova> depois</p>")
    checar("importante" in D.para_texto(estranho), "tag desconhecida nao faz o texto sumir")
    checar(D.ler_html("") == [], "HTML vazio nao quebra")


def test_pdf_e_docx() -> None:
    """Os dois formatos saem da mesma leitura, entao dizem a mesma coisa."""
    print("\nPDF e DOCX")
    blocos = D.ler_html(CONTRATO)

    pdf = D.para_pdf(blocos, "Contrato", "Uener Advogados")
    checar(pdf.startswith(b"%PDF"), "sai um PDF de verdade")
    checar(D.paginas_de(pdf) >= 1, "e da para contar as paginas")

    docx = D.para_docx(blocos, "Contrato")
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        xml = z.read("word/document.xml").decode("utf-8")

    for pedaco in ("11.222.333/0001-81", "CONTRATO DE PRESTA", "acompanhamento de prazos"):
        checar(pedaco in xml, f"o DOCX guarda “{pedaco[:26]}”")
    checar("<w:b/>" in xml, "o DOCX guarda o negrito")
    checar("<w:u " in xml or "<w:u/>" in xml, "o DOCX guarda o sublinhado")

    # Nenhum dos dois pode perder texto pelo caminho.
    texto = D.para_texto(blocos)
    perdidas = [p for p in ("CONTRATANTE", "Goiânia", "primeiro") if p not in texto]
    checar(not perdidas, f"nada some do texto ({perdidas})")

    png = D.pagina_png(pdf, 1, 400)
    checar(png[:4] == b"\x89PNG", "e a pagina desenha como PNG para a pre-visualizacao")

    vazio = D.para_pdf([], "Vazio")
    checar(vazio.startswith(b"%PDF"), "documento vazio nao derruba o gerador")


def test_conferir() -> None:
    print("\nconferir antes de sair")
    checar(D.cpf_valido("529.982.247-25"), "aceita CPF com digito certo")
    checar(not D.cpf_valido("529.982.247-26"), "recusa CPF com digito errado")
    checar(not D.cpf_valido("111.111.111-11"), "recusa CPF de digito repetido")
    checar(D.cnpj_valido("11.222.333/0001-81"), "aceita CNPJ com digito certo")
    checar(not D.cnpj_valido("00.000.000/0001-00"), "recusa CNPJ com digito errado")

    ruim = D.ler_html(
        "<p>Honorários de R$ mensais para a COOPERATIVA BRASILEIRA, "
        "CNPJ 00.000.000/0001-00, CPF 529.982.247-26.</p><p>Prazo de _____ dias.</p>"
    )
    avisos = D.conferir(ruim, [{"nome": "COOPERATIVA BRASILEIRA", "documento": "11.222.333/0001-81"}])
    titulos = {a["titulo"] for a in avisos}

    checar("Falta preencher" in titulos, "acha a lacuna do modelo")
    checar("Valor sem número" in titulos, "acha o R$ sem numero")
    checar("CNPJ não confere" in titulos, "acha o CNPJ invalido")
    checar("CPF não confere" in titulos, "acha o CPF invalido")
    checar("Documento diferente do cadastro" in titulos,
           "cruza o texto com a ficha do cadastro")
    checar(all(a["detalhe"] for a in avisos), "todo aviso explica o que fazer")

    bom = D.ler_html("<p>Honorários de R$ 12.000,00 para a parte, CNPJ 11.222.333/0001-81.</p>")
    checar(D.conferir(bom, []) == [], "documento sem problema nao inventa aviso")


def test_versoes(tmp: Path) -> None:
    print("\nversoes e comparacao")
    base = Base(tmp / "escrita.db")
    docs = D.Documentos(base)

    id_ = docs.criar("Contrato de honorários", "texto", "<h1>CONTRATO</h1><p>Prazo de 48 horas.</p>")
    checar(docs.ultima_versao(id_) == 1, "criar ja grava a v1")

    docs.salvar(id_, "<h1>CONTRATO</h1><p>Prazo de 72 horas.</p>", nota="prazo revisado")
    checar(docs.ultima_versao(id_) == 2, "gravar com mudanca cria versao")

    antes = docs.ultima_versao(id_)
    docs.salvar(id_, "<h1>CONTRATO</h1><p>Prazo de 72 horas.</p>")
    checar(docs.ultima_versao(id_) == antes,
           "gravar SEM mudanca nao cria versao - o historico nao vira ruido")

    docs.salvar(id_, "<h1>CONTRATO</h1><p>Prazo de 72 horas.</p><p>Vigência de 12 meses.</p>",
                nota="vigência inserida")
    mudancas = D.comparar(docs.corpo_da_versao(id_, 1), docs.corpo_da_versao(id_, 3))
    tipos = [m["tipo"] for m in mudancas]
    checar("mudou" in tipos, f"percebe o paragrafo alterado ({tipos})")
    checar("entrou" in tipos, "percebe o paragrafo novo")
    checar(any("48" in m["antes"] and "72" in m["depois"] for m in mudancas if m["tipo"] == "mudou"),
           "e mostra o antes e o depois")

    # Trocar so a marcacao nao e alteracao de contrato.
    so_marcacao = D.comparar("<p><b>Prazo</b> de 72 horas.</p>", "<p><strong>Prazo</strong> de 72 horas.</p>")
    checar(so_marcacao == [], "trocar <b> por <strong> NAO conta como mudanca")

    restaurada = docs.restaurar(id_, 1)
    checar(restaurada["versao"] == 4, f"restaurar cria versao nova (v{restaurada['versao']})")
    checar(len(docs.versoes(id_)) == 4, "e o historico inteiro continua la")
    checar(docs.obter(id_)["corpo"] == docs.corpo_da_versao(id_, 1), "com o conteudo da versao pedida")

    try:
        docs.restaurar(id_, 99)
        checar(False, "versao que nao existe vira erro")
    except ValueError:
        checar(True, "versao que nao existe vira erro")

    # No Windows a pasta temporaria so some depois que o SQLite solta o arquivo.
    base.fechar()


# -------------------------------------------------------------- planilha


def test_numeros() -> None:
    """
    "12.000,00" e doze mil. Ler como doze troca o honorario por mil vezes
    menos, e planilha ninguem confere somando de cabeca.
    """
    print("\nnumero como brasileiro escreve")
    casos = [
        ("12.000,00", 12000.0), ("1.234", 1234.0), ("0,5", 0.5),
        ("1,5", 1.5), ("R$ 8.500,00", 8500.0), ("10%", 10.0),
        ("-1.200,50", -1200.5), ("(300,00)", -300.0), ("1234.56", 1234.56),
    ]
    for texto, esperado in casos:
        lido = P.numero(texto)
        checar(lido == esperado, f"{texto!r} vira {esperado}", f"achou {lido}")

    checar(P.numero("pago") is None, "texto nao vira numero")
    checar(P.numero("") is None, "vazio nao vira zero por engano")

    checar(P.formatar(12000.0, "moeda") == "R$ 12.000,00", "formata moeda no padrao brasileiro")
    checar(P.formatar(29100.5, "numero") == "29.100,50", "formata numero com milhar")


def test_formulas() -> None:
    print("\nformulas em portugues")
    aba = P.Aba()
    dados = [
        ("A1", "Cooperativa"), ("B1", "12.000,00"), ("C1", "pago"),
        ("A2", "Fornecedor A"), ("B2", "8.500,00"), ("C2", "em aberto"),
        ("A3", "Condomínio"), ("B3", "3.200,00"), ("C3", "pago"),
        ("A4", "Seguradora"), ("B4", "5.400,00"), ("C4", "em aberto"),
    ]
    for ref, v in dados:
        aba.gravar(ref, {"valor": v})
    for l in (1, 2, 3, 4):
        aba.gravar(f"D{l}", {"valor": f'=SE(C{l}="pago";0;B{l}*0,1)', "formato": "moeda"})
    aba.gravar("B5", {"valor": "=SOMA(B1:B4)", "formato": "moeda"})
    aba.gravar("C5", {"valor": '=CONT.SE(C1:C4;"em aberto")'})
    aba.gravar("D5", {"valor": "=SOMA(D1:D4)", "formato": "moeda"})
    aba.gravar("E5", {"valor": '=SOMASE(C1:C4;"em aberto";B1:B4)', "formato": "moeda"})

    c = P.calcular_aba(aba)
    checar(c["B5"]["texto"] == "R$ 29.100,00", f"SOMA de faixa ({c['B5']['texto']})")
    checar(c["C5"]["bruto"] == 2, f"CONT.SE conta o criterio ({c['C5']['bruto']})")
    checar(c["D1"]["texto"] == "R$ 0,00", "SE devolve o ramo verdadeiro")
    checar(c["D2"]["texto"] == "R$ 850,00", f"SE devolve o ramo falso com conta ({c['D2']['texto']})")
    checar(c["D5"]["texto"] == "R$ 1.390,00", f"soma das multas ({c['D5']['texto']})")
    checar(c["E5"]["texto"] == "R$ 13.900,00", f"SOMASE com faixa de soma ({c['E5']['texto']})")

    # Celula digitada e sem formato volta como foi digitada.
    checar(c["B1"]["texto"] == "12.000,00", f"o que foi digitado aparece igual ({c['B1']['texto']})")
    checar(c["B1"]["bruto"] == 12000.0, "mas a conta usa o numero")


def test_formula_erra_sem_derrubar() -> None:
    """Erro de formula vira erro na celula, nunca acao e nunca travamento."""
    print("\nformula com problema")
    aba = P.Aba()
    casos = [
        ("A1", "=1/0", P.ERRO_DIV),
        ("A2", "=NAOEXISTE(1)", P.ERRO_NOME),
        ("A3", "=A3+1", P.ERRO_CIRCULAR),
        ("A4", "=((", P.ERRO_VALOR),
        ("A5", '=SOMA("texto")', None),
    ]
    for ref, formula, _ in casos:
        aba.gravar(ref, {"valor": formula})
    aba.gravar("A6", {"valor": "=A7+1"})     # celula vazia conta como zero
    aba.gravar("B1", {"valor": "=B2"})       # referencia em cadeia
    aba.gravar("B2", {"valor": "=B3"})
    aba.gravar("B3", {"valor": "=B1"})       # fecha o circulo

    c = P.calcular_aba(aba)
    for ref, formula, esperado in casos:
        if esperado:
            checar(c[ref]["texto"] == esperado, f"{formula} vira {esperado}", f"achou {c[ref]['texto']}")
    checar(c["A6"]["bruto"] == 1, "celula vazia vale zero na conta")
    checar(c["B1"]["erro"], "referencia circular indireta tambem e pega")
    checar(all(not v["erro"] or v["texto"].startswith("#") for v in c.values()),
           "todo erro aparece com codigo, nao em branco")


def test_formula_nao_executa_nada() -> None:
    """
    Formula chega de planilha que veio de fora. O pior que uma formula
    estranha pode fazer e devolver erro numa celula.
    """
    print("\nformula de terceiro nao executa nada")
    aba = P.Aba()
    perigosas = [
        "=__import__('os').system('echo x')",
        "=open('/etc/passwd').read()",
        "=eval('1+1')",
        "=exec('x=1')",
        "=[].__class__.__mro__",
    ]
    for i, formula in enumerate(perigosas, start=1):
        aba.gravar(f"A{i}", {"valor": formula})

    c = P.calcular_aba(aba)
    for i, formula in enumerate(perigosas, start=1):
        resultado = c[f"A{i}"]["texto"]
        checar(str(resultado).startswith("#"),
               f"recusa {formula[:30]}", f"devolveu {resultado!r}")


def test_entrar_e_sair() -> None:
    print("\nimportar e exportar")
    csv = "Cliente;Honorários;Situação\nCooperativa;12.000,00;pago\nFornecedor;8.500,00;em aberto\n"
    aba = P.de_csv(csv, "Importado")
    c = P.calcular_aba(aba)
    checar(len(aba.celulas) == 9, f"le as nove celulas do CSV (achou {len(aba.celulas)})")
    checar(c["B2"]["texto"] == "12.000,00", "com ponto e virgula, que e o padrao brasileiro")
    checar(c["C3"]["texto"] == "em aberto", "e o acento sobrevive")

    virgula = P.de_csv("a,b,c\n1,2,3\n", "Virgula")
    checar(len(virgula.celulas) == 6, "CSV com virgula tambem e lido")

    aba.gravar("D2", {"valor": "=B2*2", "formato": "moeda"})
    xlsx = P.para_xlsx([aba], [P.calcular_aba(aba)])
    checar(xlsx[:2] == b"PK", "exporta XLSX de verdade")

    volta = P.de_xlsx(xlsx)[0]
    checar(volta.celulas["D2"].valor == "=B2*2",
           "a formula vai no XLSX, nao so o resultado - quem abre no Excel continua calculando")

    saida = P.para_csv(aba, P.calcular_aba(aba))
    checar("Cooperativa" in saida and ";" in saida, "exporta CSV com ponto e virgula")
    checar("=B2*2" not in saida, "o CSV leva o valor calculado, nao a formula")


def test_grade() -> None:
    print("\nreferencia de celula")
    checar(P.letra_da_coluna(0) == "A" and P.letra_da_coluna(25) == "Z", "coluna vira letra")
    checar(P.letra_da_coluna(26) == "AA", "e passa de Z para AA")
    checar(P.indice_da_coluna("AA") == 26, "e volta de letra para numero")

    aba = P.Aba()
    aba.gravar("C10", {"valor": "x"})
    checar(aba.linhas >= 10 and aba.colunas >= 3, "a grade cresce para caber o que foi escrito")

    aba.gravar("C10", {"valor": ""})
    checar("C10" not in aba.celulas, "celula esvaziada some, em vez de virar lixo guardado")


def main() -> int:
    print("=" * 55)
    print("PAULUS - editor de texto e planilha")
    print("=" * 55)

    test_ler_html()
    test_pdf_e_docx()
    test_conferir()
    test_numeros()
    test_formulas()
    test_formula_erra_sem_derrubar()
    test_formula_nao_executa_nada()
    test_entrar_e_sair()
    test_grade()

    with tempfile.TemporaryDirectory() as bruto:
        test_versoes(Path(bruto))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
