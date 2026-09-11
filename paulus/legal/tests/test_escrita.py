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
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import documento as D  # noqa: E402
import planilha as P  # noqa: E402
from base import Base  # noqa: E402
from extract import index_all_contracts  # noqa: E402

CONTRATOS = RAIZ / "data" / "test_contracts"

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


def test_duas_paginas_ao_mesmo_tempo() -> None:
    """
    Duas páginas desenhadas no mesmo instante.

    O PDFium é uma biblioteca em C e não é segura para duas threads ao mesmo
    tempo; o FastAPI atende rota `def` num pool de threads. Enquanto a tela
    pedia uma página de cada vez, ninguém viu nada. A comparação de versões
    passou a mostrar as duas folhas lado a lado, dois `<img>` saíram juntos e o
    processo morreu com "access violation reading 0x2C" — sem traceback da
    aplicação, só dois 500 na tela.

    Não dá para testar isso dentro do próprio processo: se voltar, ele não
    falha, ele morre e leva a suíte inteira junto. Então o desenho simultâneo
    acontece num processo à parte, e o que se mede é ele ter sobrevivido.
    """
    print("\nduas páginas desenhadas ao mesmo tempo")

    receita = "\n".join([
        f"import sys; sys.path.insert(0, {str(RAIZ / 'src')!r})",
        "from concurrent.futures import ThreadPoolExecutor",
        "import documento",
        "blocos = documento.ler_html('<p>' + 'texto de contrato ' * 400 + '</p>')",
        "pdf = documento.para_pdf(blocos, 'Teste', 'Teste')",
        "desenhar = lambda n: len(documento.pagina_png(pdf, 1, 900))",
        "with ThreadPoolExecutor(max_workers=4) as pool:",
        "    tamanhos = list(pool.map(desenhar, range(12)))",
        "print(min(tamanhos))",
    ])

    fim = subprocess.run([sys.executable, "-c", receita],
                         capture_output=True, text=True, timeout=180)

    checar(fim.returncode == 0,
           f"12 desenhos simultâneos, o processo sobrevive (saída {fim.returncode})",
           (fim.stderr or fim.stdout).strip()[-200:])
    menor = fim.stdout.strip()
    checar(menor.isdigit() and int(menor) > 1000,
           f"e todo PNG sai inteiro (o menor tem {menor or '?'} bytes)")


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


QUADRO = (
    "<h1>CONTRATO DE HONORÁRIOS</h1>"
    "<p>As partes ajustam o pagamento conforme o quadro abaixo:</p>"
    "<table><tr><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>"
    "<tr><td>1ª</td><td>10/10/2026</td><td>R$ 3.000,00</td></tr>"
    "<tr><td></td><td></td><td></td></tr>"
    "<tr><td>2ª</td><td>10/11/2026</td><td>R$ 4.000,00 — saldo, com uma descrição "
    "longa o bastante para quebrar em mais de uma linha dentro da célula</td></tr>"
    "</table>"
    "<p>O atraso implica multa de 2%.</p>"
)


def test_quadro() -> None:
    """
    Quadro de parcelas dentro do contrato.

    É o que fazia o contrato sair do Word: aqui não havia como montar um. O
    teste persegue o que dói — texto de célula sumindo entre o editor e o
    arquivo, e o quadro virando parágrafos soltos.
    """
    print("\nquadro dentro do documento")
    blocos = D.ler_html(QUADRO)
    tipos = [b.tipo for b in blocos]
    checar(tipos == ["titulo1", "paragrafo", "tabela", "paragrafo"],
           f"o quadro é UM bloco, não dezoito parágrafos soltos ({tipos})")

    quadro = blocos[2]
    checar(len(quadro.linhas) == 4, f"quatro linhas, com a em branco ({len(quadro.linhas)})")
    checar(all(len(l) == 3 for l in quadro.linhas),
           f"toda linha com o mesmo número de colunas ({[len(l) for l in quadro.linhas]})")
    checar(quadro.linhas[0] == ["Parcela", "Vencimento", "Valor"], "o cabeçalho é a 1ª linha")
    # A linha em branco existe no editor; some no PDF quebraria a promessa de
    # que a pré-visualização é o arquivo.
    checar(quadro.linhas[2] == ["", "", ""], "a linha em branco fica")

    texto = D.para_texto(blocos)
    for pedaco in ("Vencimento", "10/11/2026", "R$ 3.000,00", "multa de 2%"):
        checar(pedaco in texto, f"o texto do documento guarda “{pedaco}”")

    # O que importa mesmo: chegar ao arquivo.
    import leitor_pdf

    pdf = D.para_pdf(blocos, "Honorários", "Honorários")
    with leitor_pdf.abrir(pdf) as doc:
        na_folha = " ".join(doc[0].get_textpage().get_text_range().split())
    faltando = [p for p in ("Parcela", "Vencimento", "10/11/2026", "4.000,00", "multa de 2%")
                if p not in na_folha]
    checar(not faltando, f"e o PDF mostra tudo ({faltando} faltando)")

    with zipfile.ZipFile(io.BytesIO(D.para_docx(blocos, "Honorários"))) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    checar("<w:tbl>" in xml, "o DOCX sai com tabela de verdade, não com texto colado")
    checar("10/11/2026" in xml and "Vencimento" in xml, "e com o conteúdo das células")

    # O quadro conta como um bloco no mapa de páginas, como no PDF.
    mapa = D.mapa_de_paginas(blocos)
    checar(len(mapa["de_bloco"]) == len(blocos),
           f"o mapa de páginas conta o quadro como um bloco ({len(mapa['de_bloco'])})")

    # Bordas do que chega torto.
    checar(D.ler_html("<table></table>") == [], "quadro sem nada não vira bloco")
    checar(D.ler_html("<table><tr><td></td></tr></table>") == [],
           "quadro só de células vazias também não")
    aberto = D.ler_html("<table><tr><td>a</td><td>b</td></tr>")
    checar(len(aberto) == 1 and aberto[0].tipo == "tabela",
           "</table> faltando não faz o quadro sumir")
    tortas = D.ler_html("<table><tr><td>a</td></tr><tr><td>b</td><td>c</td></tr></table>")
    checar([len(l) for l in tortas[0].linhas] == [2, 2],
           f"linha com menos células é completada ({[len(l) for l in tortas[0].linhas]})")
    negrito = D.ler_html("<table><tr><td>um <b>valor</b> alto</td></tr></table>")
    checar(negrito[0].linhas[0][0] == "um valor alto",
           f"negrito dentro da célula não engole o texto ({negrito[0].linhas[0]})")


def _contrato_real() -> list:
    """O maior contrato desta máquina, em blocos. Vazio se a pasta não existe."""
    if not CONTRATOS.exists():
        return []
    docs = index_all_contracts(CONTRATOS, verbose=False)
    if not docs:
        return []
    d = max(docs, key=lambda x: len(x.text))
    return D.ler_html("".join("<p>" + p.strip() + "</p>"
                              for p in d.text.split("\n") if p.strip()))


def test_pagina_medida() -> None:
    """
    A página que a tela mostra é a página do arquivo.

    O editor dizia "páginas ~4": palavras dividido por 450. Erra em todo
    documento com título, lista ou parágrafo curto — e erra mais quanto maior
    o documento, que é justamente quando a pessoa precisa saber.

    O teste que importa não é "o número parece certo", é: a página em que o
    mapa diz que um parágrafo começa é a página do PDF em que ele está. Isso
    se abre e se lê, e é o que este teste faz.
    """
    print("\na página é medida, não estimada")
    blocos = _contrato_real()
    if not blocos:
        print("  pulado: sem contratos nesta máquina")
        return

    mapa = D.mapa_de_paginas(blocos)
    pdf = D.para_pdf(blocos, "Contrato", "Contrato")
    checar(mapa["paginas"] == D.paginas_de(pdf),
           f"o total bate com o PDF de verdade ({mapa['paginas']})")
    checar(len(mapa["de_bloco"]) == len(blocos),
           f"todo bloco tem uma página ({len(mapa['de_bloco'])} de {len(blocos)})")
    checar(all(a <= b for a, b in zip(mapa["de_bloco"], mapa["de_bloco"][1:])),
           "e a numeração nunca anda para trás")
    checar(max(mapa["de_bloco"]) <= mapa["paginas"], "nem passa do total")

    # O que a linha de quebra promete: a página N do arquivo começa aqui.
    #
    # Compara só letras e números: um "▪" do Word sai do PDF como "■", porque
    # o Times não tem aquele glifo e o reportlab troca pelo parecido. Isso é o
    # gerador fazendo o certo, e não tem a ver com a página em que o parágrafo
    # caiu, que é o que este teste mede.
    import leitor_pdf

    so_letras = lambda t: re.sub(r"[^0-9a-zà-ÿ]+", " ", t.lower()).strip()

    erradas = []
    with leitor_pdf.abrir(pdf) as doc:
        for pagina in range(2, mapa["paginas"] + 1):
            primeiro = next(i for i, p in enumerate(mapa["de_bloco"]) if p == pagina)
            comeco = so_letras(blocos[primeiro].texto)[:40]
            na_folha = so_letras(doc[pagina - 1].get_textpage().get_text_range())
            if comeco not in na_folha[:len(comeco) + 70]:
                erradas.append(f"p{pagina}: {comeco[:30]}")
    checar(not erradas,
           f"cada página do PDF começa onde o mapa diz ({mapa['paginas'] - 1} quebras)",
           "; ".join(erradas[:2]))

    vazio = D.mapa_de_paginas([])
    checar(vazio["paginas"] == 1 and vazio["de_bloco"] == [],
           "documento vazio não quebra o mapa")


def test_paragrafo_que_atravessa_a_quebra() -> None:
    """
    Um parágrafo longo é partido em dois pelo reportlab, e os pedaços novos não
    herdam nada. Sem repassar a marca na divisão, exatamente o parágrafo sobre
    o qual "em que página isso cai?" é interessante sumia do mapa.
    """
    print("\nparágrafo que atravessa a quebra")
    blocos = D.ler_html(
        "<p>curto antes</p>"
        "<p>" + ("palavra que enche a página " * 900) + "</p>"
        "<p>curto depois</p>")

    mapa = D.mapa_de_paginas(blocos)
    checar(mapa["paginas"] > 2, f"o do meio ocupa várias páginas ({mapa['paginas']})")
    checar(mapa["de_bloco"][1] == 1, "e sua página é onde ele COMEÇA, não onde termina")
    checar(mapa["de_bloco"][2] == mapa["paginas"],
           f"o de depois cai na última ({mapa['de_bloco'][2]})")


def test_formato_da_folha() -> None:
    """Fonte, corpo, recuo e entrelinhas — e o que acontece com o que não existe."""
    print("\no formato da folha")

    padrao = D.normalizar_formato(None)
    checar(padrao == D.FORMATO_PADRAO, f"sem pedido, o padrão ({padrao})")
    checar(D.normalizar_formato("") == D.FORMATO_PADRAO, "documento antigo, sem formato gravado")
    checar(D.normalizar_formato('{"corpo": 11}')["corpo"] == 11, "aceita o JSON do banco")

    torto = D.normalizar_formato({"fonte": "Comic Sans", "corpo": 7.5,
                                  "recuo_cm": 9, "entrelinhas": 0})
    checar(torto == D.FORMATO_PADRAO,
           "o que o PDF não sabe produzir volta ao padrão, não ao mais parecido")
    checar(D.normalizar_formato({"corpo": 12.4})["corpo"] == 12,
           "12,4 não vira 12 por arredondamento — vira o padrão, que por acaso é 12")

    bom = D.normalizar_formato({"fonte": "sem-serifa", "corpo": 13,
                                "recuo_cm": 1.25, "entrelinhas": 2.0})
    checar(bom["fonte"] == "sem-serifa" and bom["corpo"] == 13
           and bom["recuo_cm"] == 1.25 and bom["entrelinhas"] == 2.0,
           f"e o que existe passa inteiro ({bom})")

    # O formato tem que chegar ao arquivo, senão é enfeite de tela.
    blocos = _contrato_real() or D.ler_html(CONTRATO)
    simples = D.para_pdf(blocos, "x", "x")
    duplo = D.para_pdf(blocos, "x", "x", formato={"entrelinhas": 2.0})
    checar(D.paginas_de(duplo) > D.paginas_de(simples),
           f"entrelinhas duplo rende mais páginas ({D.paginas_de(simples)} → {D.paginas_de(duplo)})")
    checar(D.para_pdf(blocos, "x", "x", formato={"recuo_cm": 2.0}) != simples,
           "e o recuo muda o arquivo")

    docx = D.para_docx(blocos, "x", formato={"fonte": "sem-serifa", "corpo": 13,
                                             "recuo_cm": 2.0})
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        estilos = z.read("word/styles.xml").decode("utf-8")
        corpo_xml = z.read("word/document.xml").decode("utf-8")
    checar("Arial" in estilos, "o DOCX sai na fonte escolhida")
    checar('w:firstLine="1134"' in corpo_xml or "firstLine" in corpo_xml,
           "e com o recuo de primeira linha")

    # O que estava gravado antes desta coluna existir continua saindo igual.
    checar(D.paginas_de(D.para_pdf(blocos, "x", "x", formato="")) == D.paginas_de(simples),
           "documento sem formato gravado sai como sempre saiu")


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


def test_paragrafo_trocado_nao_e_paragrafo_editado() -> None:
    """
    Apagar uma cláusula e escrever outra no lugar não é "esta cláusula mudou".

    O difflib chama os dois de `replace`, e a tela dizia "a cláusula do foro
    virou a cláusula da multa". Quem lê isso para decidir o que aceitar é
    enganado — e é exatamente a hora em que a comparação precisa ser exata.

    O corte é por palavra e não por letra, e o número saiu de medir parágrafos
    de contrato deste escritório: edição de verdade entre 0,60 e 0,83, e
    parágrafo trocado por outro entre 0,00 e 0,33.
    """
    print("\nparágrafo trocado não é parágrafo editado")

    edicoes = [
        ("2ª CLAUSULA – Do preço, que é de R$ 3.000,00.",
         "2ª CLAUSULA – Do preço, que é de R$ 4.500,00."),
        ("O prazo é de trinta dias.", "O prazo é de sessenta dias."),
        ("CLÁUSULA 9ª – Do foro de São Félix do Xingu.", "CLÁUSULA 9ª – Do foro de Goiânia."),
        ("As partes elegem o foro da comarca de Goiânia.",
         "Fica eleito o foro da comarca de Goiânia, Estado de Goiás."),
    ]
    outros = [
        ("4ª CLAUSULA – Do foro da comarca.", "5ª CLAUSULA – Da multa por atraso."),
        # Por letra estes dois dão 0,74 — o que eles têm em comum é o
        # sublinhado. Por palavra, zero.
        ("Nome: ________", "CPF: ________"),
        ("VENDEDOR: MATHEUS UENER SILVA", "COMPRADOR: CAROLINE WAGNER DOS SANTOS"),
        ("1ª CLAUSULA – Do objeto.",
         "7ª CLAUSULA – Da rescisão antecipada por qualquer das partes."),
    ]

    for a, b in edicoes:
        checar(D._parecidos(a, b), f"edição: “{a[:34]}…”")
    for a, b in outros:
        checar(not D._parecidos(a, b), f"outro parágrafo: “{a[:34]}…”")

    antes = ("<p>1ª CLAUSULA – Do objeto do contrato.</p>"
             "<p>2ª CLAUSULA – Do preço, que é de R$ 3.000,00.</p>"
             "<p>4ª CLAUSULA – Do foro da comarca.</p>")
    depois = ("<p>1ª CLAUSULA – Do objeto do contrato.</p>"
              "<p>2ª CLAUSULA – Do preço, que é de R$ 4.500,00.</p>"
              "<p>5ª CLAUSULA – Da multa por atraso.</p>")
    tipos = [m["tipo"] for m in D.comparar(antes, depois)]
    checar(tipos == ["mudou", "saiu", "entrou"],
           f"o preço mudou; o foro saiu e a multa entrou ({tipos})")


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


def _parcelas() -> "P.Aba":
    """A tabela que este escritório digita: cliente, valor, honorário calculado."""
    aba = P.Aba(nome="Parcelas")
    aba.gravar("A1", {"valor": "Cliente"})
    aba.gravar("B1", {"valor": "Valor"})
    aba.gravar("C1", {"valor": "Honorário"})
    for i, (nome, valor) in enumerate(
            [("Carol", 3000), ("Ana", 1200), ("Bruno", 9000), ("Davi", 500)], start=2):
        aba.gravar(f"A{i}", {"valor": nome})
        aba.gravar(f"B{i}", {"valor": str(valor)})
        aba.gravar(f"C{i}", {"valor": f"=B{i}*0,1"})
    aba.gravar("B7", {"valor": "=SOMA(B2:B5)"})
    return aba


def test_criterio_com_numero() -> None:
    """
    ">1000" tem que comparar número com número.

    O critério chega sempre como texto, e a comparação caía no ramo de texto:
    letra a letra, "500" > "1000" é verdadeiro, porque "5" vem depois de "1".
    Com isso =SOMASE(B1:B4;">1000") somava a coluna inteira — 13.700 onde o
    certo era 13.200 — e =SOMASE(B1:B4;"<1000") devolvia zero.

    A célula mostrava um número plausível, que é a pior forma de errar valor:
    ninguém confere planilha somando de cabeça.
    """
    print("\ncritério com número")
    aba = P.Aba()
    for i, v in enumerate(["9000", "3000", "1200", "500", "pago"], start=1):
        aba.gravar(f"B{i}", {"valor": v})
    for ref, formula in [("D1", '=SOMASE(B1:B5;">1000")'), ("D2", '=CONT.SE(B1:B5;">1000")'),
                         ("D3", '=SOMASE(B1:B5;"<1000")'), ("D4", '=SOMASE(B1:B5;">=1200")'),
                         ("D5", '=CONT.SE(B1:B5;"pago")'), ("D6", "=CONT.SE(B1:B5;3000)")]:
        aba.gravar(ref, {"valor": formula})

    c = P.calcular_aba(aba)
    esperado = {"D1": "13.200", "D2": "3", "D3": "500", "D4": "13.200", "D5": "1", "D6": "1"}
    for ref, certo in esperado.items():
        checar(c[ref]["texto"] == certo,
               f"{aba.celulas[ref].valor} = {certo}", f"saiu {c[ref]['texto']}")

    # Texto não é maior nem menor que mil; só "diferente de" vale sobre ele.
    aba.gravar("D7", {"valor": '=CONT.SE(B1:B5;"<99999")'})
    c = P.calcular_aba(aba)
    checar(c["D7"]["texto"] == "4",
           "célula de texto não satisfaz uma comparação numérica",
           f"saiu {c['D7']['texto']} em vez de 4")


def test_ordenar_a_tabela() -> None:
    """
    Ordenar move a linha inteira, e a fórmula vai com a linha dela.

    Ordenar só a coluna escolhida embaralha a tabela — o valor da linha 7 passa
    a valer para o cliente da linha 3 — e o estrago não aparece olhando: cada
    célula continua com um número plausível.
    """
    print("\nordenar a tabela")
    aba = _parcelas()
    antes = P.calcular_aba(aba)
    total_antes = antes["B7"]["texto"]

    feito = P.ordenar(aba, antes, "A1:C5", "B", crescente=False, com_cabecalho=True)
    depois = P.calcular_aba(aba)

    nomes = [aba.celulas[f"A{l}"].valor for l in range(2, 6)]
    checar(nomes == ["Bruno", "Carol", "Ana", "Davi"],
           f"as linhas ficam na ordem do valor ({nomes})")
    checar(aba.celulas["A1"].valor == "Cliente", "o cabeçalho não entra na ordenação")
    checar(feito["linhas"] == 4, f"e diz quantas linhas moveu ({feito['linhas']})")

    # O que importa: cada honorário continua sendo 10% do valor da SUA linha.
    certo = all(abs(depois[f"C{l}"]["bruto"] - depois[f"B{l}"]["bruto"] * 0.1) < 0.01
                for l in range(2, 6))
    checar(certo, f"cada fórmula acompanhou a linha dela ({feito['formulas']} ajustadas)",
           str([aba.celulas[f"C{l}"].valor for l in range(2, 6)]))
    checar(depois["B7"]["texto"] == total_antes,
           f"o total fora da faixa não se mexe ({total_antes})")

    # Aspas não são referência.
    checar(P._trocar_linha('=SE(A1="A1";B1;0)', 1, 9) == '=SE(A9="A1";B9;0)',
           "texto entre aspas não é renumerado")

    crescente = _parcelas()
    P.ordenar(crescente, P.calcular_aba(crescente), "A1:C5", "B", com_cabecalho=True)
    checar([crescente.celulas[f"A{l}"].valor for l in range(2, 6)] ==
           ["Davi", "Ana", "Carol", "Bruno"], "e ordena para os dois lados")

    vazias = _parcelas()
    vazias.celulas.pop("B3")
    P.ordenar(vazias, P.calcular_aba(vazias), "A1:C5", "B", crescente=False, com_cabecalho=True)
    checar(vazias.celulas["A5"].valor == "Ana",
           f"linha sem valor vai para o fim, nos dois sentidos ({vazias.celulas['A5'].valor})")

    try:
        P.ordenar(aba, depois, "A1:C5", "Z")
        checar(False, "coluna fora da faixa vira erro")
    except ValueError:
        checar(True, "coluna fora da faixa vira erro, não ordenação torta")


def test_filtrar_e_so_olhar() -> None:
    """Filtro é jeito de olhar: devolve o que esconder, e não grava nada."""
    print("\nfiltrar")
    aba = _parcelas()
    c = P.calcular_aba(aba)
    antes = {k: v.valor for k, v in aba.celulas.items()}

    r = P.filtrar(aba, c, "A1:C5", "B", ">1000")
    checar(r["mostrando"] == 3 and r["de"] == 4, f"mostra 3 de 4 ({r})")
    checar(r["esconder"] == [5], f"esconde a linha do valor menor ({r['esconder']})")
    checar({k: v.valor for k, v in aba.celulas.items()} == antes,
           "e a planilha não muda: filtro não é alteração do documento")

    texto = P.filtrar(aba, c, "A1:C5", "A", "ana")
    checar(texto["mostrando"] == 1, f"filtra por texto sem ligar para maiúscula ({texto})")


def test_resumo_da_selecao() -> None:
    print("\nresumo da seleção")
    aba = _parcelas()
    c = P.calcular_aba(aba)

    checar(P.refs_da_faixa("B2:C3") == ["B2", "C2", "B3", "C3"],
           f"a faixa vira células em ordem de leitura ({P.refs_da_faixa('B2:C3')})")
    checar(P.refs_da_faixa("D9:B2") == P.refs_da_faixa("B2:D9"),
           "e as pontas podem vir ao contrário")
    checar(P.refs_da_faixa("B4") == ["B4"], "uma célula só é ela mesma")
    checar(P.refs_da_faixa("") == [], "faixa vazia não vira nada")

    r = P.resumo_selecao(aba, c, P.refs_da_faixa("B2:B5"))
    checar(r["soma"] == 13700 and r["media"] == 3425, f"soma e média ({r['soma']}, {r['media']})")
    checar(r["minimo"] == 500 and r["maximo"] == 9000, "mínimo e máximo")
    checar(r["com_numero"] == 4 and r["vazias"] == 0, "conta o que é número e o que está vazio")

    # Uma vazia no meio muda a média e não muda a soma - e isso não se vê.
    aba.celulas.pop("B3")
    r2 = P.resumo_selecao(aba, P.calcular_aba(aba), P.refs_da_faixa("B2:B5"))
    checar(r2["vazias"] == 1 and r2["com_numero"] == 3,
           f"a célula vazia aparece na contagem ({r2['vazias']} vazia)")
    checar(r2["soma"] == 12500 and round(r2["media"]) == 4167,
           f"e a média muda com ela ({r2['media']})")

    com_texto = P.resumo_selecao(aba, P.calcular_aba(aba), P.refs_da_faixa("A1:A5"))
    checar(com_texto["com_texto"] == 5 and com_texto["soma"] == 0,
           f"coluna de texto não inventa soma ({com_texto})")


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
    test_duas_paginas_ao_mesmo_tempo()
    test_quadro()
    test_pagina_medida()
    test_paragrafo_que_atravessa_a_quebra()
    test_formato_da_folha()
    test_conferir()
    test_numeros()
    test_formulas()
    test_criterio_com_numero()
    test_ordenar_a_tabela()
    test_filtrar_e_so_olhar()
    test_resumo_da_selecao()
    test_formula_erra_sem_derrubar()
    test_formula_nao_executa_nada()
    test_entrar_e_sair()
    test_grade()
    test_paragrafo_trocado_nao_e_paragrafo_editado()

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
