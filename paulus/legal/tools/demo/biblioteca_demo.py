"""
A biblioteca da demonstração: o escritório fictício de criar_demo.py com uma
biblioteca jurídica - duas obras de doutrina, o CDC e o manual interno -, e o
conjunto de perguntas que mede a Biblioteca (tools/medir.py --conjunto
biblioteca).

**As duas obras são fictícias.** Autor, editora, ISBN e ficha catalográfica
foram escritos aqui, para a demonstração; o conteúdo segue a lei de verdade,
mas não é doutrina publicada e não deve ser citado como tal. A primeira página
de cada uma diz isso. O dono do PAULUS preferiu seguir com a demonstração a
esperar obras reais (docs/PROGRESSO-BIBLIOTECA.md, M0): é a limitação desta
medição, e ela fica registrada.

O CDC é o texto oficial compilado do Planalto (público: Lei 9.610, art. 8º,
IV), lido de data/leis/l8078compilado.htm e posto num PDF como os que
circulam por aí - um dispositivo por linha, com as notas de alteração. É o
"PDF do CDC" que alguém entrega como material.

Por que as obras são escritas assim:

- **sinônimo de propósito.** A obra diz "adimplemento substancial" e a
  pergunta diz "inadimplemento mínimo"; a obra diz "comerciante" e
  "fabricante", a pergunta diz "loja" e "fábrica". É o caso em que a busca por
  palavra falha e a por sentido tem de acertar;
- **o que um livro tem e um contrato não:** sumário com número de página,
  cabeçalho e rodapé repetidos em toda página, nota de rodapé, ficha
  catalográfica (CIP) com ISBN, edição e ano;
- **citação com e sem instrumento:** "art. 18 do CDC" liga a obra ao artigo;
  "como visto no art. 18", sozinho, não pode ligar;
- **o tempo:** a obra A é de 2015 e comenta os arts. 4º e 6º do CDC, que a Lei
  14.181/2021 alterou; a obra B é de 2022 e comenta o art. 421 do Código
  Civil, alterado em 2019 - antes dela.

    venv\\Scripts\\python.exe tools\\demo\\biblioteca_demo.py          (monta data/demo-biblioteca)
    venv\\Scripts\\python.exe tools\\demo\\biblioteca_demo.py --refazer
"""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PASTA = RAIZ / "data" / "demo-biblioteca"
LEIS = RAIZ / "data" / "leis"
CONJUNTO = RAIZ / "data" / "medicao" / "conjunto-biblioteca.jsonl"
EXEMPLO = Path(__file__).resolve().parent / "conjunto-biblioteca-exemplo.jsonl"

FONTES_PLANALTO = {
    "l8078compilado.htm": "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
    "l10406compilada.htm": "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
}

AVISO_FICTICIA = ("OBRA FICTÍCIA, escrita para a demonstração do PAULUS. O autor, a editora, o ISBN e a ficha "
                  "catalográfica não existem; não cite esta obra.")

# ------------------------------------------------------------ as obras
# Cada página é uma lista de blocos: ("h1", capítulo), ("h2", seção),
# ("p", parágrafo) e ("nota", nota de rodapé). A página impressa é a do PDF:
# folha de rosto é a 1, ficha catalográfica a 2, sumário a 3.

OBRA_A = {
    "arquivo": "Brandão - Vícios do produto e do serviço (2ª ed., 2015).pdf",
    "titulo": "Vícios do Produto e do Serviço",
    "cabecalho": "HEITOR VALADARES BRANDÃO · VÍCIOS DO PRODUTO E DO SERVIÇO",
    "rosto": ["Heitor Valadares Brandão", "VÍCIOS DO PRODUTO E DO SERVIÇO",
              "Comentários ao Código de Defesa do Consumidor", "2ª edição", "Editora Exemplo Jurídico",
              "São Paulo", "2015", AVISO_FICTICIA],
    "ficha": ["Dados Internacionais de Catalogação na Publicação (CIP)",
              "(Câmara Brasileira do Livro, SP, Brasil)",
              "Brandão, Heitor Valadares",
              "Vícios do produto e do serviço : comentários ao Código de Defesa do Consumidor / "
              "Heitor Valadares Brandão. – 2. ed. – São Paulo : Editora Exemplo Jurídico, 2015.",
              "ISBN 978-85-99999-01-1",
              "1. Defesa do consumidor – Brasil 2. Responsabilidade do fornecedor I. Título.",
              "15-01234 CDU-347.451.031(81)",
              "Índices para catálogo sistemático: 1. Brasil : Direito do consumidor 347.451.031(81)",
              "© 2015 by Heitor Valadares Brandão",
              "Todos os direitos desta edição reservados à Editora Exemplo Jurídico."],
    "paginas": [
        [("h1", "CAPÍTULO 1 — A RELAÇÃO DE CONSUMO"),
         ("h2", "1.1 Consumidor e fornecedor"),
         ("p", "O Código de Defesa do Consumidor define consumidor como toda pessoa física ou jurídica que adquire "
               "ou utiliza produto ou serviço como destinatário final (art. 2º do CDC). Fornecedor, por sua vez, é "
               "quem desenvolve atividade de produção, montagem, criação, construção, transformação, importação, "
               "exportação, distribuição ou comercialização de produtos ou prestação de serviços (art. 3º do CDC)."),
         ("p", "A expressão destinatário final é o ponto mais disputado do conceito. Para a corrente finalista, só é "
               "consumidor quem retira o bem do mercado para uso próprio, sem reempregá-lo na atividade econômica. "
               "A jurisprudência, contudo, admite o finalismo mitigado: a pequena empresa que compra fora da sua "
               "especialidade e se mostra vulnerável recebe a proteção do Código.")],
        [("h2", "1.2 A vulnerabilidade do consumidor"),
         ("p", "A vulnerabilidade é presumida em toda relação de consumo (art. 4º, I, do CDC) e se apresenta em três "
               "formas. A vulnerabilidade técnica é a falta de conhecimento específico sobre o produto ou o "
               "serviço: quem compra um automóvel não sabe avaliar o sistema de freios. A vulnerabilidade jurídica "
               "é a falta de conhecimento sobre direito, contabilidade ou economia. A vulnerabilidade fática, ou "
               "socioeconômica, é a desproporção de forças entre quem vende e quem compra."),
         ("p", "Vulnerabilidade não se confunde com hipossuficiência. A primeira é qualidade de todo consumidor; a "
               "segunda é condição de alguns, verificada no processo, e é ela que autoriza a inversão do ônus da "
               "prova.")],
        [("h1", "CAPÍTULO 2 — OS DIREITOS BÁSICOS DO CONSUMIDOR"),
         ("h2", "2.1 O rol do art. 6º"),
         ("p", "O art. 6º do CDC enumera os direitos básicos do consumidor: a proteção da vida e da saúde, a educação "
               "para o consumo, a informação adequada e clara, a proteção contra a publicidade enganosa, a revisão "
               "de cláusulas desproporcionais, a prevenção e reparação de danos e o acesso aos órgãos judiciários e "
               "administrativos. O rol não é taxativo: outros direitos decorrem de tratados, de leis e dos "
               "princípios gerais."),
         ("h2", "2.2 A inversão do ônus da prova"),
         ("p", "A facilitação da defesa do consumidor inclui a inversão do ônus da prova, a critério do juiz, quando "
               "for verossímil a alegação ou quando o consumidor for hipossuficiente (art. 6º, VIII, do CDC). Não é "
               "automática: depende de decisão fundamentada, e o momento adequado para ela é o saneamento do "
               "processo, para que o fornecedor saiba a tempo o que terá de provar.")],
        [("h1", "CAPÍTULO 3 — O VÍCIO DO PRODUTO"),
         ("h2", "3.1 A responsabilidade solidária dos fornecedores"),
         ("p", "Pelo art. 18 do CDC, os fornecedores de produtos de consumo duráveis ou não duráveis respondem "
               "solidariamente pelos vícios de qualidade ou quantidade. Isso quer dizer que o consumidor pode "
               "escolher contra quem reclamar: o comerciante que vendeu, o fabricante ou o importador. Ao "
               "comerciante que pagar resta o regresso contra os demais."),
         ("p", "Vício é a inadequação do produto ao fim a que se destina, ou a diminuição do seu valor. Não se "
               "confunde com o defeito, que é o vício que causa acidente de consumo e atinge a segurança do "
               "consumidor, tratado no art. 12 do CDC como fato do produto¹."),
         ("nota", "¹ Sobre o fato do produto e a responsabilidade do comerciante, ver o art. 13 do CDC.")],
        [("h2", "3.2 O prazo de trinta dias para sanar o vício"),
         ("p", "O fornecedor tem o prazo máximo de trinta dias para sanar o vício (art. 18, § 1º, do CDC). Vencido o "
               "prazo sem conserto, o consumidor escolhe, à sua vontade, entre três alternativas: a substituição do "
               "produto por outro da mesma espécie, a restituição imediata da quantia paga, atualizada, ou o "
               "abatimento proporcional do preço."),
         ("p", "As partes podem convencionar prazo diferente, nunca inferior a sete nem superior a cento e oitenta "
               "dias. Quando o vício atinge parte essencial do produto, o consumidor não precisa esperar os trinta "
               "dias: pode exigir de imediato uma das três alternativas."),
         ("h2", "3.3 O vício do serviço"),
         ("p", "O mesmo regime vale para o serviço viciado (art. 20 do CDC): o consumidor pode exigir a reexecução "
               "do serviço, a restituição do que pagou ou o abatimento do preço. Como visto no art. 18, a escolha "
               "é do consumidor, e não do fornecedor.")],
        [("h1", "CAPÍTULO 4 — DECADÊNCIA E PRESCRIÇÃO"),
         ("h2", "4.1 Os prazos para reclamar"),
         ("p", "O direito de reclamar pelos vícios aparentes ou de fácil constatação caduca em trinta dias para "
               "produtos não duráveis e em noventa dias para produtos duráveis (art. 26 do CDC). A contagem começa "
               "na entrega efetiva do produto ou no término do serviço."),
         ("p", "A reclamação comprovada feita ao fornecedor obsta a decadência até a resposta negativa, que deve ser "
               "transmitida de forma inequívoca."),
         ("h2", "4.2 O vício oculto"),
         ("p", "Tratando-se de vício oculto, o prazo decadencial só começa quando o defeito fica evidenciado (art. "
               "26, § 3º, do CDC). É a regra que protege o comprador do eletrodoméstico que para de funcionar um ano "
               "depois: o prazo de noventa dias corre a partir do momento em que o problema aparece, e não da "
               "compra.")],
        [("h2", "4.3 A prescrição da pretensão de reparação"),
         ("p", "A pretensão à reparação pelos danos causados por fato do produto ou do serviço prescreve em cinco "
               "anos, contados do conhecimento do dano e de sua autoria (art. 27 do CDC). Decadência é para "
               "reclamar do vício; prescrição é para cobrar a indenização do acidente de consumo."),
         ("h1", "CAPÍTULO 5 — O DIREITO DE ARREPENDIMENTO"),
         ("h2", "5.1 A contratação fora do estabelecimento"),
         ("p", "O consumidor pode desistir do contrato no prazo de sete dias, contados da assinatura ou do "
               "recebimento do produto, sempre que a contratação ocorrer fora do estabelecimento comercial (art. 49 "
               "do CDC). O fundamento é a compra por impulso e a impossibilidade de examinar o produto antes."),
         ("p", "O prazo de reflexão não depende de motivo. Exercido o arrependimento, os valores pagos são devolvidos "
               "de imediato e atualizados, inclusive o frete.")],
        [("h2", "5.2 O comércio eletrônico"),
         ("p", "A compra pela internet é a contratação fora do estabelecimento por excelência, e a ela se aplica o "
               "art. 49 do CDC. O fornecedor que dificulta a desistência, exigindo justificativa ou cobrando multa, "
               "pratica conduta abusiva.")],
    ],
}

OBRA_B = {
    "arquivo": "Teles - Teoria geral dos contratos (2022).pdf",
    "titulo": "Teoria Geral dos Contratos",
    "cabecalho": "MARINA ALBUQUERQUE TELES — TEORIA GERAL DOS CONTRATOS",
    "rosto": ["Marina Albuquerque Teles", "TEORIA GERAL DOS CONTRATOS", "1ª edição", "Editora Exemplo Jurídico",
              "Belo Horizonte", "2022", AVISO_FICTICIA],
    "ficha": ["Dados Internacionais de Catalogação na Publicação (CIP)",
              "T269t Teles, Marina Albuquerque",
              "Teoria geral dos contratos / Marina Albuquerque Teles. – Belo Horizonte : Editora Exemplo "
              "Jurídico, 2022.",
              "212 p. ; 23 cm.",
              "ISBN 978-65-99999-02-4",
              "1. Contratos. 2. Direito civil. 3. Direito do consumidor. I. Título.",
              "CDD 346.02",
              "Ficha catalográfica elaborada por bibliotecária fictícia – CRB-6/0000",
              "Copyright © 2022 Marina Albuquerque Teles"],
    "paginas": [
        [("h1", "PARTE I — OS PRINCÍPIOS"),
         ("h1", "CAPÍTULO 1 — PRINCÍPIOS CONTRATUAIS"),
         ("h2", "1.1 A função social do contrato"),
         ("p", "A liberdade contratual será exercida nos limites da função social do contrato (art. 421 do Código "
               "Civil). Desde a Lei 13.874/2019, o parágrafo único do mesmo artigo afirma a intervenção mínima e a "
               "excepcionalidade da revisão contratual nas relações privadas."),
         ("h2", "1.2 A boa-fé objetiva"),
         ("p", "Os contratantes são obrigados a guardar, assim na conclusão do contrato como em sua execução, os "
               "princípios de probidade e boa-fé (art. 422 do Código Civil). A boa-fé objetiva é regra de conduta: "
               "impõe deveres anexos de lealdade, informação e cooperação, que existem ainda que o contrato não os "
               "escreva.")],
        [("p", "Da boa-fé objetiva nascem figuras como a supressio, a perda de um direito pelo seu não exercício "
               "prolongado, que cria na outra parte a confiança de que ele não será mais exercido, e a vedação ao "
               "comportamento contraditório (venire contra factum proprium)."),
         ("h1", "PARTE II — A EXTINÇÃO DO CONTRATO"),
         ("h1", "CAPÍTULO 2 — A RESOLUÇÃO POR INADIMPLEMENTO"),
         ("h2", "2.1 A cláusula resolutiva"),
         ("p", "A parte lesada pelo inadimplemento pode pedir a resolução do contrato, se não preferir exigir-lhe o "
               "cumprimento, cabendo em qualquer dos casos indenização por perdas e danos (art. 475 do Código "
               "Civil). A cláusula resolutiva expressa opera de pleno direito; a tácita depende de interpelação "
               "judicial (art. 474 do Código Civil).")],
        [("h2", "2.2 O adimplemento substancial"),
         ("p", "A teoria do adimplemento substancial limita o direito de resolver o contrato. Quando o devedor "
               "cumpriu parte tão expressiva da obrigação que o descumprimento restante é de pouca importância, a "
               "resolução é desproporcional: ao credor resta cobrar o saldo, com os encargos, mas não desfazer o "
               "negócio."),
         ("p", "A doutrina aponta três requisitos: a proximidade entre o que foi pago e o que era devido, a boa-fé do "
               "devedor e a utilidade do que foi cumprido para o credor. A teoria decorre da boa-fé objetiva e da "
               "função social, e não de artigo específico do Código Civil."),
         ("h2", "2.3 A exceção do contrato não cumprido"),
         ("p", "Nos contratos bilaterais, nenhum dos contratantes, antes de cumprida a sua obrigação, pode exigir o "
               "implemento da do outro (art. 476 do Código Civil). É a defesa de quem é cobrado sem que o credor "
               "tenha cumprido a parte dele.")],
        [("h1", "CAPÍTULO 3 — A REVISÃO POR ONEROSIDADE EXCESSIVA"),
         ("h2", "3.1 A teoria da imprevisão"),
         ("p", "Nos contratos de execução continuada ou diferida, se a prestação de uma das partes se tornar "
               "excessivamente onerosa, com extrema vantagem para a outra, em virtude de acontecimentos "
               "extraordinários e imprevisíveis, o devedor poderá pedir a resolução do contrato (art. 478 do Código "
               "Civil). O art. 479 permite evitar a resolução se o réu se oferecer a modificar equitativamente as "
               "condições."),
         ("p", "No Código de Defesa do Consumidor a exigência é menor: basta o fato superveniente que torne a "
               "prestação excessivamente onerosa, sem necessidade de imprevisibilidade (art. 6º, V, do CDC).")],
        [("h1", "PARTE III — OS CONTRATOS DE CONSUMO"),
         ("h1", "CAPÍTULO 4 — VÍCIOS E SUPERENDIVIDAMENTO"),
         ("h2", "4.1 O art. 18 do CDC na prática contratual"),
         ("p", "Nos contratos de consumo, o art. 18 do CDC afasta a lógica dos vícios redibitórios do Código Civil. "
               "Em vez de só redibir o contrato ou pedir abatimento, o consumidor tem, depois dos trinta dias sem "
               "conserto, a escolha entre substituição, restituição e abatimento, contra qualquer fornecedor da "
               "cadeia. Para esta autora, a cláusula que limita a garantia ao fabricante é nula (art. 51, I, do "
               "CDC).")],
        [("h2", "4.2 O superendividamento"),
         ("p", "A Lei 14.181/2021 incluiu no CDC o capítulo da prevenção e do tratamento do superendividamento. "
               "Entende-se por superendividamento a impossibilidade manifesta de o consumidor pessoa natural, de "
               "boa-fé, pagar a totalidade de suas dívidas de consumo sem comprometer seu mínimo existencial (art. "
               "54-A, § 1º, do CDC)."),
         ("p", "O consumidor superendividado pode pedir a repactuação das dívidas em audiência de conciliação com "
               "todos os credores, apresentando plano de pagamento de até cinco anos (art. 104-A do CDC).")],
    ],
}

OBRAS = [OBRA_A, OBRA_B]


def _sumario(obra: dict) -> list[str]:
    """As linhas do sumário, com a página de cada capítulo e seção - como no livro."""
    linhas = []
    for n, pagina in enumerate(obra["paginas"], start=4):
        for tipo, texto in pagina:
            if tipo in ("h1", "h2"):
                linhas.append(f"{texto} {'.' * 12} {n}")
    return linhas


def obra_em_pdf(obra: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    estilos = getSampleStyleSheet()
    nota = ParagraphStyle("nota", parent=estilos["BodyText"], fontSize=8, leading=10)
    centro = ParagraphStyle("centro", parent=estilos["BodyText"], alignment=1, fontSize=12, leading=16)

    def moldura(canvas, doc) -> None:
        # Cabeçalho e rodapé repetidos, a partir do corpo do livro: é o que a
        # leitura tem de reconhecer e tirar antes de cortar.
        if doc.page <= 3:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(A4[0] / 2, A4[1] - 40, obra["cabecalho"])
        canvas.drawCentredString(A4[0] / 2, 30, str(doc.page))
        canvas.restoreState()

    partes: list = [Paragraph(x, centro) for x in obra["rosto"]]
    partes.append(PageBreak())
    partes += [Paragraph(x, estilos["BodyText"]) for x in obra["ficha"]]
    partes.append(PageBreak())
    partes.append(Paragraph("SUMÁRIO", estilos["Heading1"]))
    partes += [Paragraph(x, estilos["BodyText"]) for x in _sumario(obra)]
    for pagina in obra["paginas"]:
        partes.append(PageBreak())
        for tipo, texto in pagina:
            estilo = {"h1": estilos["Heading1"], "h2": estilos["Heading2"], "nota": nota}.get(tipo, estilos["BodyText"])
            partes += [Paragraph(texto, estilo), Spacer(1, 4)]
    saida = io.BytesIO()
    SimpleDocTemplate(saida, pagesize=A4, title=obra["titulo"]).build(partes, onFirstPage=moldura, onLaterPages=moldura)
    return saida.getvalue()


def texto_do_planalto(nome: str) -> Path:
    """O HTML compilado do Planalto em data/leis; baixado uma vez, se faltar (texto público)."""
    alvo = LEIS / nome
    if not alvo.exists():
        import urllib.request

        LEIS.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(FONTES_PLANALTO[nome], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            alvo.write_bytes(r.read())
    return alvo


def cdc_em_pdf() -> bytes:
    """O CDC como PDF comum: título, estrutura e um dispositivo por linha, com as notas do Planalto."""
    import leis
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from xml.sax.saxutils import escape

    artigos, _ = leis.ler_codigo(texto_do_planalto("l8078compilado.htm"), "cdc")
    estilos = getSampleStyleSheet()
    partes = [Paragraph("LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990", estilos["Heading2"]),
              Paragraph("Dispõe sobre a proteção do consumidor e dá outras providências.", estilos["BodyText"])]
    estrutura_antes: list[str] = []
    for a in artigos:
        estrutura = [x for x in a.contexto.split(" · ") if x]
        for nivel in estrutura:
            if nivel not in estrutura_antes:
                partes.append(Paragraph(escape(nivel), estilos["Heading3"]))
        estrutura_antes = estrutura
        dispositivos = re.split(r"\s(?=§\s*\d|Parágrafo único|[IVXLC]{1,6}\s*-\s)", f"Art. {a.numero} {a.texto}")
        partes += [Paragraph(escape(d.strip()), estilos["BodyText"]) for d in dispositivos if d.strip()]
    saida = io.BytesIO()
    SimpleDocTemplate(saida, pagesize=A4, title="Código de Defesa do Consumidor").build(partes)
    return saida.getvalue()


CDC_ARQUIVO = "Lei 8.078-1990 - Código de Defesa do Consumidor.pdf"


# ------------------------------------------------------------ o conjunto
# Formato do tools/medir.py (alguma/todas/nunca, trechos_esperados), mais o
# que é da Biblioteca:
#   tipo: sinonimo | dispositivo | lei | manual | sem_material | fora | temporal
#   material: a biblioteca deve trazer algo (True) ou nada (False)
#   area: a área que a pergunta tem, por regra (M7), ou ""
#   cobertura: "fora" quando a biblioteca não tem nada da área
#   defasagem: True quando a resposta deve avisar que a obra é anterior à
#     redação atual do artigo; False quando não pode avisar; None, não se aplica


def Q(pergunta, tipo, esperados=(), alguma=(), todas=(), nunca=(), material=True, area="", cobertura="",
      defasagem=None):
    return {"pergunta": pergunta, "caminho": "documentos", "tipo": tipo, "trechos_esperados": list(esperados),
            "alguma": list(alguma), "todas": [list(x) for x in todas], "nunca": list(nunca), "material": material,
            "area": area, "cobertura": cobertura, "defasagem": defasagem}


CONJUNTO_BIBLIOTECA = [
    # --- conceitual com sinônimo: a pergunta usa outra palavra que a obra
    Q("o que é a teoria do inadimplemento mínimo?", "sinonimo",
      ["A teoria do adimplemento substancial limita o direito de resolver o contrato"],
      alguma=["adimplemento substancial", "parte tão expressiva", "pouca importância"], area="civil"),
    Q("o que é a fragilidade técnica de quem compra um produto?", "sinonimo",
      ["A vulnerabilidade técnica é a falta de conhecimento específico sobre o produto"],
      alguma=["vulnerabilidade técnica", "conhecimento específico"], area="consumidor"),
    Q("quem responde quando a mercadoria vem com problema, a loja ou a fábrica?", "sinonimo",
      ["o consumidor pode escolher contra quem reclamar"],
      alguma=["solidari", "comerciante", "fabricante", "qualquer"], area="consumidor"),
    Q("quando um acontecimento imprevisto deixa o contrato caro demais, dá para desfazer?", "sinonimo",
      ["em virtude de acontecimentos extraordinários e imprevisíveis"],
      alguma=["onerosidade excessiva", "excessivamente onerosa", "imprevisão", "resolução"], area="civil"),
    Q("o que é perder um direito por deixar de usá-lo por muito tempo?", "sinonimo",
      ["a perda de um direito pelo seu não exercício prolongado"],
      alguma=["supressio", "não exercício"], area="civil"),
    Q("existe regra que proíbe a parte de agir contra o que ela mesma fez antes?", "sinonimo",
      ["vedação ao comportamento contraditório"],
      alguma=["venire", "comportamento contraditório"], area="civil"),
    Q("o cliente que comprou on-line pode desistir sem explicar o porquê?", "sinonimo",
      ["O prazo de reflexão não depende de motivo"],
      alguma=["sete dias", "7 dias", "arrependimento"], area="consumidor"),

    # --- por dispositivo: a pergunta cita o artigo com o instrumento
    Q("o que a doutrina diz do art. 18 do CDC?", "dispositivo",
      ["respondem solidariamente pelos vícios de qualidade ou quantidade", "afasta a lógica dos vícios redibitórios"],
      alguma=["solidari", "trinta dias", "substituição"], area="consumidor"),
    Q("o que a biblioteca tem sobre o art. 26, § 3º, do CDC?", "dispositivo",
      ["Tratando-se de vício oculto, o prazo decadencial só começa quando o defeito fica evidenciado"],
      alguma=["vício oculto", "evidenciado"], area="consumidor"),
    Q("o que os autores dizem do art. 475 do Código Civil?", "dispositivo",
      ["A parte lesada pelo inadimplemento pode pedir a resolução do contrato"],
      alguma=["resolução", "perdas e danos"], area="civil"),
    Q("como a doutrina comenta o art. 49 do CDC?", "dispositivo",
      ["sempre que a contratação ocorrer fora do estabelecimento comercial"],
      alguma=["sete dias", "7 dias", "fora do estabelecimento"], area="consumidor"),
    Q("o que a doutrina diz sobre o art. 27 do CDC?", "dispositivo",
      ["prescreve em cinco anos, contados do conhecimento do dano e de sua autoria"],
      alguma=["cinco anos", "5 anos"], area="consumidor"),
    Q("o que se diz na biblioteca sobre o art. 422 do Código Civil?", "dispositivo",
      ["impõe deveres anexos de lealdade, informação e cooperação"],
      alguma=["boa-fé", "deveres anexos", "lealdade"], area="civil"),

    # --- lei pura: a resposta está no texto da lei
    Q("qual o prazo para o consumidor desistir de uma compra feita fora da loja, segundo o CDC?", "lei",
      ["O consumidor pode desistir do contrato, no prazo de 7 dias"],
      alguma=["7 dias", "sete dias"], area="consumidor"),
    Q("o que diz o art. 26 do CDC sobre produtos duráveis?", "lei",
      ["noventa dias, tratando-se de fornecimento de serviço e de produtos duráveis"],
      alguma=["noventa dias", "90 dias"], area="consumidor"),
    Q("quais as alternativas do consumidor se o vício não for sanado em trinta dias, pelo art. 18, § 1º, do CDC?", "lei",
      ["a substituição do produto por outro da mesma espécie"],
      todas=[["substituição"], ["restituição"], ["abatimento"]], area="consumidor"),
    Q("o que diz o art. 54-A do CDC?", "lei",
      ["Este Capítulo dispõe sobre a prevenção do superendividamento da pessoa natural"],
      alguma=["superendividamento"], area="consumidor"),
    Q("em quanto tempo prescreve a reparação por fato do produto, pelo art. 27 do CDC?", "lei",
      ["Prescreve em cinco anos a pretensão à reparação pelos danos causados por fato do produto"],
      alguma=["cinco anos", "5 anos"], area="consumidor"),
    Q("como o art. 2º do CDC define consumidor?", "lei",
      ["Consumidor é toda pessoa física ou jurídica que adquire ou utiliza produto ou serviço como destinatário final"],
      alguma=["destinatário final"], area="consumidor"),

    # --- manual interno: a regra da casa
    Q("com quantos dias de antecedência devo protocolar uma contestação?", "manual",
      ["três dias úteis de antecedência do prazo final"], alguma=["três dias úteis", "3 dias úteis"]),
    Q("quanto o escritório cobra por uma consulta avulsa?", "manual",
      ["Consulta avulsa: R$ 450,00"], alguma=["450"]),
    Q("por quanto tempo guardamos as pastas de clientes encerradas?", "manual",
      ["fica arquivada por cinco anos"], alguma=["cinco anos", "5 anos"]),
    Q("em quanto tempo devemos responder o e-mail de um cliente?", "manual",
      ["E-mail de cliente é respondido em até um dia útil"], alguma=["um dia útil", "1 dia útil"]),
    Q("o percentual de êxito do contrato do João Batista está dentro da tabela do escritório?", "manual",
      ["honorários de êxito entre 20% e 30%"], todas=[["20%", "vinte por cento"], ["30%", "trinta por cento"]]),
    Q("quanto o escritório cobra para acompanhar uma audiência avulsa?", "manual",
      ["Acompanhamento avulso de audiência: R$ 900,00"], alguma=["900"]),
    Q("o que o cliente novo precisa assinar antes do primeiro protocolo?", "manual",
      ["Cliente novo assina o contrato de honorários antes do primeiro protocolo"],
      alguma=["contrato de honorários"]),

    # --- não deve trazer material: pergunta de documento de cliente. Os
    # dois primeiros são os casos registrados em src/material.py.
    Q("qual o percentual de êxito no contrato do João Batista?", "sem_material", alguma=["20%", "vinte por cento"],
      nunca=["30%"], material=False),
    Q("quais poderes especiais a procuração dá à Dra. Helena?", "sem_material",
      todas=[["transigir"], ["quitação", "quitacao"], ["acordo"]], material=False),
    Q("qual a multa por atraso no pagamento do contrato de transporte?", "sem_material",
      alguma=["2%", "dois por cento"], material=False),
    Q("quanto custa rescindir o contrato de transporte sem motivo?", "sem_material",
      todas=[["10%", "dez por cento"], ["30 dias", "trinta dias", "30 (trinta)"]], material=False),
    Q("qual o foro do contrato de transporte?", "sem_material", alguma=["Santarém"], material=False),
    Q("em que dia vence o aluguel da Clínica Bem Viver?", "sem_material",
      alguma=["dia 5", "dia 05", "5 (cinco)", "dia cinco"], material=False),
    Q("quem é o locador da sala 402?", "sem_material", alguma=["Marcos Antônio Lemos", "Marcos Antonio Lemos"],
      material=False),
    Q("qual índice reajusta o aluguel da Clínica?", "sem_material", alguma=["IGP-M", "IGPM"], material=False),

    # --- fora da cobertura: a biblioteca não tem nada da área
    Q("qual o prazo de decadência para o fisco lançar o tributo?", "fora", material=False, area="tributário",
      cobertura="fora"),
    Q("qual a pena do crime de furto qualificado?", "fora", material=False, area="penal", cobertura="fora"),
    Q("quantos dias de férias o empregado tem por ano, pela CLT?", "fora", material=False, area="trabalho",
      cobertura="fora"),
    Q("como se calcula a aposentadoria por idade no INSS?", "fora", material=False, area="previdenciário",
      cobertura="fora"),
    Q("qual o regime de bens quando o casal não faz pacto antenupcial?", "fora", material=False,
      area="família e sucessões", cobertura="fora"),

    # --- temporal: a obra é anterior (ou posterior) à redação atual do artigo
    Q("o que a doutrina diz sobre os direitos básicos do art. 6º do CDC?", "temporal",
      ["O art. 6º do CDC enumera os direitos básicos do consumidor"],
      alguma=["direitos básicos", "informação"], area="consumidor", defasagem=True),
    Q("como a biblioteca explica a vulnerabilidade do art. 4º, I, do CDC?", "temporal",
      ["A vulnerabilidade é presumida em toda relação de consumo"],
      alguma=["vulnerabilidade"], area="consumidor", defasagem=True),
    Q("o que a doutrina diz da inversão do ônus da prova do art. 6º, VIII, do CDC?", "temporal",
      ["depende de decisão fundamentada"],
      alguma=["verossímil", "hipossuficiente", "saneamento"], area="consumidor", defasagem=True),
    Q("o que a doutrina diz do art. 421 do Código Civil?", "temporal",
      ["nos limites da função social do contrato"],
      alguma=["função social"], area="civil", defasagem=False),
    Q("o que a doutrina diz do superendividamento no art. 54-A do CDC?", "temporal",
      ["Entende-se por superendividamento a impossibilidade manifesta"],
      alguma=["superendividamento", "mínimo existencial"], area="consumidor", defasagem=False),
]


def escrever_conjunto(caminho: Path = CONJUNTO) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    cabeca = ("// Conjunto da Biblioteca (tools/medir.py --conjunto biblioteca), gerado por "
              "tools/demo/biblioteca_demo.py.\n// Obras FICTÍCIAS + CDC do Planalto + manual da demonstração. "
              "Como anotar um conjunto real: docs/medicao.md.\n")
    caminho.write_text(cabeca + "\n".join(json.dumps(q, ensure_ascii=False) for q in CONJUNTO_BIBLIOTECA) + "\n",
                       encoding="utf-8")
    return caminho


def escrever_exemplo() -> Path:
    """Uma pergunta de cada tipo, no git: mostra o formato."""
    vistos, linhas = set(), []
    for q in CONJUNTO_BIBLIOTECA:
        if q["tipo"] not in vistos:
            vistos.add(q["tipo"])
            linhas.append(json.dumps(q, ensure_ascii=False))
    EXEMPLO.write_text("// Exemplo do formato do conjunto da Biblioteca: uma pergunta de cada tipo.\n"
                       "// O conjunto inteiro sai de tools/demo/biblioteca_demo.py e fica em "
                       "data/medicao/conjunto-biblioteca.jsonl, fora do git.\n" + "\n".join(linhas) + "\n",
                       encoding="utf-8")
    return EXEMPLO


# ------------------------------------------------------------ montar

def montar(dados: Path = PASTA, refazer: bool = False) -> dict:
    """O escritório da demonstração com a biblioteca inteira, em `dados`."""
    import criar_demo
    from config import Preferencias

    if dados.exists() and any(dados.iterdir()):
        if not refazer:
            return {"pasta": str(dados), "ja_existia": True}
        if dados.name != "demo-biblioteca":
            raise SystemExit("por segurança, --refazer só apaga uma pasta chamada 'demo-biblioteca'")
        shutil.rmtree(dados)
    acervo = dados / "test_contracts"
    acervo.mkdir(parents=True, exist_ok=True)
    criar_demo.escrever_documentos(acervo)
    criar_demo.semear(dados, acervo, date.today())
    criar_demo.ensinar_manual(dados)
    Preferencias(dados / "preferencias.json").atualizar({
        "pessoa": {"nome": criar_demo.ADVOGADA, "oab": criar_demo.OAB},
        "escritorio": {"nome": criar_demo.ESCRITORIO},
    })
    entrou = entrar_na_biblioteca(dados)
    (dados / "criada-em.txt").write_text(date.today().isoformat(), encoding="utf-8")
    return {"pasta": str(dados), **entrou}


def entrar_na_biblioteca(dados: Path) -> dict:
    """
    As obras e o CDC entram pelo mesmo caminho que um escritório usaria: o
    arquivo entregue como material. Quem decide o que é lei, doutrina ou
    manual é a entrada da Biblioteca, não esta função.
    """
    import leis as leis_mod
    import material as material_mod
    from base import Base

    m = material_mod.Material(dados / "aprendizado")
    saida = {}
    if "--sem-triagem" in sys.argv:
        # A linha de base da M0: tudo como material, o CDC cortado em blocos.
        for obra in OBRAS:
            saida[obra["arquivo"]] = m.absorver(obra["arquivo"], obra_em_pdf(obra))
        saida[CDC_ARQUIVO] = m.absorver(CDC_ARQUIVO, cdc_em_pdf())
        return saida
    from biblioteca import ficha as ficha_mod
    from biblioteca import triagem

    base = Base(dados / "paulus.db")
    try:
        leis = leis_mod.Leis(base)
        # O Código Civil do Planalto, como um escritório instalaria em
        # Configurações › Códigos de lei: a obra B comenta artigos dele.
        saida["Código Civil"] = leis.importar(texto_do_planalto("l10406compilada.htm"), "cc")["artigos"]
        for obra in OBRAS:
            saida[obra["arquivo"]] = triagem.entregar(m, leis, obra["arquivo"], obra_em_pdf(obra), dados / "leis")["destino"]
        saida[CDC_ARQUIVO] = triagem.entregar(m, leis, CDC_ARQUIVO, cdc_em_pdf(), dados / "leis")["mensagem"]
        # O manual entrou por criar_demo, sem triagem: ganha a ficha aqui.
        for item in m.itens:
            if not item.get("ficha"):
                t = triagem.triar(item["nome"], m.texto_de(item["id"]))
                m.definir_ficha(item["id"], {**ficha_mod.ler_ficha(m.texto_de(item["id"]), t["tipo"]), "confirmada": True,
                                             "autor": criar_demo_escritorio()})
    finally:
        base.con.close()
    return saida


def criar_demo_escritorio() -> str:
    import criar_demo

    return criar_demo.ESCRITORIO


def main() -> int:
    r = montar(PASTA, refazer="--refazer" in sys.argv)
    escrever_conjunto()
    escrever_exemplo()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str)[:3000])
    print(f"conjunto: {CONJUNTO} ({len(CONJUNTO_BIBLIOTECA)} perguntas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
