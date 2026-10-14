"""
As tarefas do banco de provas do editor (docs/PLANO-EDITOR.md, E0).

Cada tarefa é um pedido de verdade sobre um documento do corpus, com:

  - `gabarito`: as operações que um bom profissional faria (src/edicao.py) - o
    adaptador "gabarito" aplica isto e tem de tirar 100%;
  - `mudam`: os blocos que TÊM de mudar; `podem`: os que podem mudar junto
    (a renumeração, a assinatura com o nome novo). Qualquer outro bloco que
    mude é dano colateral;
  - `contem` / `nao_contem`: o que o documento aceito tem de ter (e não ter);
  - `ordem`: (bloco-com-este-texto, depois-deste-bloco, antes-deste-bloco);
  - `numeracao`: as cláusulas em sequência e nenhuma referência para o nada;
  - `pergunta` / `cita`: pedido que é pergunta - o documento não muda, e a
    resposta aponta o bloco.

Os blocos têm nome fixo no corpus (b0a0005 = compra e venda, bloco 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tarefa:
    id: str
    doc: str
    pedido: str
    categoria: str
    gabarito: list = field(default_factory=list)
    mudam: list = field(default_factory=list)
    podem: list = field(default_factory=list)
    contem: list = field(default_factory=list)
    nao_contem: list = field(default_factory=list)
    ordem: tuple | None = None
    numeracao: bool = False
    renumera: bool = False         # a numeração pode mudar (cabeças e referências)
    pergunta: bool = False
    cita: list = field(default_factory=list)
    selecao: dict | None = None    # {"bloco", "texto"}
    em_tudo: bool = False


CATEGORIAS = {
    "troca_local": "troca num lugar só",
    "troca_valor": "valor em número e por extenso",
    "nome_em_tudo": "nome ou termo em todo o documento",
    "reescrever": "reescrever um parágrafo",
    "selecao": "pedido sobre o trecho selecionado",
    "inserir_clausula": "inserir cláusula no lugar certo",
    "inserir_paragrafo": "inserir parágrafo ou item",
    "apagar": "apagar",
    "mover": "mover",
    "estilo": "estilo (formal, curto, claro)",
    "varios": "vários pontos de uma vez",
    "pergunta": "pergunta sobre o documento",
    "parafrase": "pedido com outras palavras ou com erro de digitação",
}

T = Tarefa

TAREFAS: list[Tarefa] = [
    # ------------------------------------------------------------ locação
    T("loc-01", "locacao", "Mude o prazo da locação para 24 meses.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses, com início em 1º de novembro de 2026 e término em 30 de abril de 2029",
                 "para": "24 (vinte e quatro) meses, com início em 1º de novembro de 2026 e término em 31 de outubro de 2028"}],
      mudam=["b0b0008"], contem=["24 (vinte e quatro) meses"], nao_contem=["30 (trinta) meses"]),
    T("loc-02", "locacao", "O aluguel passa a ser de R$ 2.600,00.", "troca_valor",
      gabarito=[{"op": "substituir", "bloco": "b0b0011", "de": "R$ 2.400,00 (dois mil e quatrocentos reais)",
                 "para": "R$ 2.600,00 (dois mil e seiscentos reais)"}],
      mudam=["b0b0011"], podem=["b0b0019"], contem=["R$ 2.600,00 (dois mil e seiscentos reais)"],
      nao_contem=["dois mil e quatrocentos"]),
    T("loc-03", "locacao", "Troque o índice de reajuste do IGP-M pelo IPCA em todo o contrato.", "nome_em_tudo",
      gabarito=[{"op": "substituir_em_tudo", "de": "IGP-M/FGV", "para": "IPCA/IBGE"}],
      mudam=["b0b0012", "b0b0017"], contem=["IPCA"], nao_contem=["IGP-M"], em_tudo=True),
    T("loc-04", "locacao", "A locatária se chama Mariana Costa Ribeiro Alves, corrija o nome dela.", "nome_em_tudo",
      gabarito=[{"op": "substituir_em_tudo", "de": "MARIANA COSTA RIBEIRO", "para": "MARIANA COSTA RIBEIRO ALVES"}],
      mudam=["b0b0003", "b0b0030"], contem=["MARIANA COSTA RIBEIRO ALVES, brasileira"]),
    T("loc-05", "locacao", "Inclua uma cláusula de multa por rescisão antecipada logo depois da cláusula do prazo, "
      "com multa proporcional de 3 aluguéis.", "inserir_clausula",
      gabarito=[{"op": "inserir", "depois_de": "b0b0007", "blocos": [
          {"texto": "CLÁUSULA 3ª – DA RESCISÃO ANTECIPADA"},
          {"texto": "Se a LOCATÁRIA devolver o imóvel antes do término do prazo, pagará multa equivalente a 3 (três) "
                    "aluguéis vigentes, reduzida proporcionalmente ao tempo de contrato cumprido, nos termos do art. 4º "
                    "da Lei nº 8.245/1991."}]}],
      mudam=[], renumera=True, numeracao=True, contem=["rescisão antecipada"],
      ordem=("rescisão antecipada", "b0b0009", "b0b0010")),
    T("loc-06", "locacao", "Acrescente na cláusula da garantia um parágrafo dizendo que a caução será devolvida "
      "corrigida pela poupança ao fim da locação.", "inserir_paragrafo",
      gabarito=[{"op": "inserir", "depois_de": "b0b0019", "blocos": [
          {"texto": "Parágrafo único. Finda a locação e quitadas as obrigações da LOCATÁRIA, a caução será devolvida "
                    "corrigida pelos índices da caderneta de poupança, nos termos do art. 38, § 2º, da Lei nº 8.245/1991."}]}],
      contem=["poupança"], ordem=("poupança", "b0b0019", "b0b0020")),
    T("loc-07", "locacao", "Remova o inciso III do § 3º da cláusula 3ª.", "apagar",
      gabarito=[{"op": "apagar", "bloco": "b0b0017"}], mudam=["b0b0017"], nao_contem=["III – correção monetária"]),
    T("loc-08", "locacao", "Reescreva o parágrafo único da cláusula 2ª de forma mais clara.", "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0b0009", "texto": "Parágrafo único. Terminado o prazo, se a LOCATÁRIA "
                 "permanecer no imóvel por mais de 30 (trinta) dias sem oposição do LOCADOR, a locação passa a vigorar "
                 "por prazo indeterminado."}],
      mudam=["b0b0009"], contem=["Parágrafo único."]),
    T("loc-09", "locacao", "Passe a cláusula do foro para antes da cláusula de rescisão.", "mover",
      gabarito=[{"op": "mover", "blocos": ["b0b0025", "b0b0026"], "antes_de": "b0b0023"}],
      mudam=[], renumera=True, numeracao=True, ordem=("DO FORO", "b0b0022", "b0b0023")),
    T("loc-10", "locacao", "Qual é o prazo da locação?", "pergunta", pergunta=True, cita=["b0b0008"]),
    T("loc-11", "locacao", "Deixe a cláusula das benfeitorias mais formal.", "estilo",
      gabarito=[{"op": "reescrever", "bloco": "b0b0022", "texto": "Parágrafo único. É vedada a realização de "
                 "benfeitorias sem prévia e expressa autorização, por escrito, do LOCADOR; as que forem realizadas "
                 "incorporar-se-ão ao imóvel, sem direito a retenção ou indenização."}],
      mudam=["b0b0022"], podem=["b0b0021", "b0b0020"]),
    T("loc-12", "locacao", "Faça estes ajustes: 1) prazo de 36 meses; 2) vencimento do aluguel no dia 10; "
      "3) caução de 2 aluguéis.", "varios",
      gabarito=[{"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses, com início em 1º de novembro de 2026 e término em 30 de abril de 2029",
                 "para": "36 (trinta e seis) meses, com início em 1º de novembro de 2026 e término em 31 de outubro de 2029"},
                {"op": "substituir", "bloco": "b0b0011", "de": "dia 5 (cinco)", "para": "dia 10 (dez)"},
                {"op": "substituir", "bloco": "b0b0019", "de": "R$ 7.200,00 (sete mil e duzentos reais), equivalente a 3 (três) aluguéis",
                 "para": "R$ 4.800,00 (quatro mil e oitocentos reais), equivalente a 2 (dois) aluguéis"}],
      mudam=["b0b0008", "b0b0011", "b0b0019"], contem=["36 (trinta e seis) meses", "dia 10 (dez)", "2 (dois) aluguéis"],
      nao_contem=["dia 5 (cinco)"]),
    T("loc-13", "locacao", "Reescreva isto de forma mais técnica.", "selecao",
      selecao={"bloco": "b0b0021", "texto": "obrigando-se a devolvê-lo no mesmo estado, ressalvado o desgaste natural do uso"},
      gabarito=[{"op": "substituir", "bloco": "b0b0021", "de": "obrigando-se a devolvê-lo no mesmo estado, ressalvado o desgaste natural do uso",
                 "para": "obrigando-se a restituí-lo nas mesmas condições, ressalvadas as deteriorações decorrentes do uso normal (art. 23, III, da Lei nº 8.245/1991)"}],
      mudam=["b0b0021"], contem=["A LOCATÁRIA declara receber o imóvel em perfeito estado de conservação"]),

    # ---------------------------------------------------------- compra e venda
    T("cv-01", "compra_venda", "O apartamento tem área privativa de 102,30 m², corrija.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0a0006", "de": "98,50 m² (noventa e oito metros e cinquenta decímetros quadrados)",
                 "para": "102,30 m² (cento e dois metros e trinta decímetros quadrados)"}],
      mudam=["b0a0006"], contem=["102,30 m²"], nao_contem=["98,50"]),
    T("cv-02", "compra_venda", "Mude o preço para R$ 900.000,00, com sinal de R$ 180.000,00 e o resto financiado.",
      "troca_valor",
      gabarito=[{"op": "substituir", "bloco": "b0a0009", "de": "R$ 850.000,00 (oitocentos e cinquenta mil reais)",
                 "para": "R$ 900.000,00 (novecentos mil reais)"},
                {"op": "substituir", "bloco": "b0a0010", "de": "R$ 170.000,00 (cento e setenta mil reais)",
                 "para": "R$ 180.000,00 (cento e oitenta mil reais)"},
                {"op": "substituir", "bloco": "b0a0011", "de": "R$ 680.000,00 (seiscentos e oitenta mil reais)",
                 "para": "R$ 720.000,00 (setecentos e vinte mil reais)"}],
      mudam=["b0a0009", "b0a0010", "b0a0011"], contem=["R$ 900.000,00", "R$ 180.000,00", "R$ 720.000,00"],
      nao_contem=["850.000", "170.000", "680.000"]),
    T("cv-03", "compra_venda", "O prazo para aprovar o financiamento deve ser de 120 dias.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0a0012", "de": "90 (noventa) dias", "para": "120 (cento e vinte) dias"}],
      mudam=["b0a0012"], contem=["120 (cento e vinte) dias"]),
    T("cv-04", "compra_venda", "Inclua uma cláusula sobre a entrega de documentos depois da cláusula das obrigações "
      "dos vendedores.", "inserir_clausula",
      gabarito=[{"op": "inserir", "depois_de": "b0a0017", "blocos": [
          {"texto": "CLÁUSULA QUINTA – DA DOCUMENTAÇÃO"},
          {"texto": "Os VENDEDORES entregarão ao COMPRADOR, em até 15 (quinze) dias da assinatura deste instrumento, a "
                    "certidão de ônus reais, as certidões negativas de débitos de IPTU e de condomínio e as certidões "
                    "pessoais exigidas para a lavratura da escritura."}]}],
      renumera=True, numeracao=True, contem=["document"], ordem=("document", "b0a0017", "b0a0018")),
    T("cv-05", "compra_venda", "Tire o parágrafo único da cláusula primeira.", "apagar",
      gabarito=[{"op": "apagar", "bloco": "b0a0007"}], mudam=["b0a0007"], nao_contem=["vagas de garagem"]),
    T("cv-06", "compra_venda", "A multa por atraso deve ser de 10%, não de 2%.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0a0013", "de": "2% (dois por cento)", "para": "10% (dez por cento)"}],
      mudam=["b0a0013"], contem=["multa de 10% (dez por cento)"], nao_contem=["2% (dois por cento)"]),
    T("cv-07", "compra_venda", "Reescreva a cláusula da posse para a posse ser entregue na assinatura deste contrato.",
      "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0a0015", "texto": "A posse do imóvel será transmitida ao COMPRADOR na "
                 "data da assinatura deste instrumento, livre de pessoas e coisas, com a entrega das chaves no mesmo ato."}],
      mudam=["b0a0015"], contem=["assinatura deste instrumento"], nao_contem=["na data da lavratura da escritura pública, livre"]),
    T("cv-08", "compra_venda", "Acrescente um inciso III prevendo que o ITBI e as despesas de escritura ficam por conta "
      "do comprador.", "inserir_paragrafo",
      gabarito=[{"op": "substituir", "bloco": "b0a0011", "de": "pelo COMPRADOR.", "para": "pelo COMPRADOR;"},
                {"op": "inserir", "depois_de": "b0a0011", "blocos": [
                    {"texto": "III – o Imposto de Transmissão de Bens Imóveis (ITBI), os emolumentos da escritura e as "
                              "despesas de registro correrão por conta do COMPRADOR."}]}],
      mudam=[], podem=["b0a0011"], contem=["III", "ITBI"], ordem=("ITBI", "b0a0011", "b0a0012")),
    T("cv-09", "compra_venda", "Quais são as vagas de garagem incluídas na venda?", "pergunta", pergunta=True,
      cita=["b0a0007"]),
    T("cv-10", "compra_venda", "O comprador é casado sob comunhão parcial com Juliana Torres Pereira, ajuste a "
      "qualificação dele.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0a0003", "de": "brasileiro, solteiro, analista de sistemas",
                 "para": "brasileiro, casado sob o regime da comunhão parcial de bens com JULIANA TORRES PEREIRA, analista de sistemas"}],
      mudam=["b0a0003"], contem=["JULIANA TORRES PEREIRA"], nao_contem=["brasileiro, solteiro"]),
    T("cv-11", "compra_venda", "Troque “Belo Horizonte/MG” por “Belo Horizonte – MG” só na cláusula do foro.",
      "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0a0021", "de": "Belo Horizonte/MG", "para": "Belo Horizonte – MG"}],
      mudam=["b0a0021"], contem=["Comarca de Belo Horizonte – MG"]),
    T("cv-12", "compra_venda", "Deixe o fecho mais curto.", "estilo",
      gabarito=[{"op": "reescrever", "bloco": "b0a0022", "texto": "E, por estarem de acordo, as partes assinam este "
                 "instrumento em 2 (duas) vias, com as testemunhas abaixo."}],
      mudam=["b0a0022"]),
    T("cv-13", "compra_venda", "Coloque a cláusula da rescisão antes da cláusula da posse.", "mover",
      gabarito=[{"op": "mover", "blocos": ["b0a0018", "b0a0019"], "antes_de": "b0a0014"}],
      renumera=True, numeracao=True, ordem=("DA RESCISÃO", "b0a0013", "b0a0014")),

    # ------------------------------------------------------------ procuração
    T("pr-01", "procuracao", "A procuração deve valer por 2 anos.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0c0008", "de": "1 (um) ano", "para": "2 (dois) anos"}],
      mudam=["b0c0008"], contem=["2 (dois) anos"], nao_contem=["1 (um) ano"]),
    T("pr-02", "procuracao", "Não permita substabelecimento.", "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0c0007", "texto": "SUBSTABELECIMENTO: é vedado o substabelecimento."}],
      mudam=["b0c0007"], contem=["substabelecimento"],
      nao_contem=["é permitido o substabelecimento, com ou sem reserva de poderes"]),
    T("pr-03", "procuracao", "Retire os poderes para confessar e para renunciar ao direito.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0c0005", "de": "receber citação, confessar, reconhecer a procedência do pedido, transigir, desistir, renunciar ao direito sobre o qual se funda a ação, receber",
                 "para": "receber citação, reconhecer a procedência do pedido, transigir, desistir, receber"}],
      mudam=["b0c0005"], nao_contem=["confessar", "renunciar ao direito"]),
    T("pr-04", "procuracao", "A outorgada mudou de escritório: agora é na Rua da Bahia, nº 1.148, sala 805, Centro.",
      "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0c0003", "de": "Avenida Afonso Pena, nº 1.500, sala 1.201, Centro",
                 "para": "Rua da Bahia, nº 1.148, sala 805, Centro"}],
      mudam=["b0c0003"], contem=["Rua da Bahia, nº 1.148, sala 805"], nao_contem=["Afonso Pena"]),
    T("pr-05", "procuracao", "Inclua também poderes para representar a empresa no Procon e em audiências de "
      "conciliação.", "inserir_paragrafo",
      gabarito=[{"op": "inserir", "depois_de": "b0c0005", "blocos": [
          {"texto": "Confere, também, poderes para representar a OUTORGANTE perante o Procon e demais órgãos de defesa do "
                    "consumidor, e em audiências de conciliação e mediação, judiciais ou extrajudiciais."}]}],
      podem=["b0c0004", "b0c0005"], contem=["Procon"], ordem=("Procon", "b0c0003", "b0c0006")),
    T("pr-06", "procuracao", "Quem é a outorgada?", "pergunta", pergunta=True, cita=["b0c0003"]),
    T("pr-07", "procuracao", "Corrija o CNPJ da ré para 13.216.988/0001-72.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0c0006", "de": "99.524.328/0001-74", "para": "13.216.988/0001-72"}],
      mudam=["b0c0006"], contem=["13.216.988/0001-72"], nao_contem=["99.524.328/0001-74"]),
    T("pr-08", "procuracao", "Deixe a finalidade mais genérica, para qualquer cobrança contra a ré.", "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0c0006", "texto": "FINALIDADE: especialmente para representar a "
                 "OUTORGANTE em quaisquer medidas de cobrança, judiciais ou extrajudiciais, em face de DISTRIBUIDORA "
                 "MONTES CLAROS LTDA., inscrita no CNPJ sob o nº 99.524.328/0001-74."}],
      mudam=["b0c0006"], contem=["cobrança"], nao_contem=["na ação de cobrança a ser ajuizada"]),
    T("pr-09", "procuracao", "Apague a validade.", "apagar",
      gabarito=[{"op": "apagar", "bloco": "b0c0008"}], mudam=["b0c0008"], nao_contem=["VALIDADE:"]),

    # ---------------------------------------------------------------- petição
    T("pe-01", "peticao", "O valor devido é R$ 52.300,00, corrija em toda a petição.", "troca_valor",
      gabarito=[{"op": "substituir_em_tudo", "de": "R$ 48.600,00 (quarenta e oito mil e seiscentos reais)",
                 "para": "R$ 52.300,00 (cinquenta e dois mil e trezentos reais)"}],
      mudam=["b0d0006", "b0d0015", "b0d0018"], contem=["R$ 52.300,00"], nao_contem=["48.600"], em_tudo=True),
    T("pe-02", "peticao", "Inclua nos pedidos a concessão de tutela de urgência para protesto das duplicatas.",
      "inserir_paragrafo",
      gabarito=[{"op": "substituir", "bloco": "b0d0016", "de": "honorários advocatícios.", "para": "honorários advocatícios;"},
                {"op": "inserir", "depois_de": "b0d0016", "blocos": [
                    {"texto": "d) a concessão de tutela de urgência para autorizar o protesto das duplicatas vencidas, "
                              "nos termos do art. 300 do Código de Processo Civil."}]}],
      mudam=[], podem=["b0d0013", "b0d0014", "b0d0015", "b0d0016"], contem=["tutela de urgência"],
      ordem=("tutela de urgência", "b0d0012", "b0d0017")),
    T("pe-03", "peticao", "Reescreva o primeiro parágrafo dos fatos com mais detalhes da relação comercial.",
      "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0d0006", "texto": "A autora mantém relação comercial com a ré desde "
                 "2024, fornecendo-lhe gêneros alimentícios para revenda. Entre março e junho de 2026, forneceu "
                 "mercadorias no valor total de R$ 48.600,00 (quarenta e oito mil e seiscentos reais), conforme as notas "
                 "fiscais nº 1.021, 1.044, 1.078 e 1.102, todas recebidas pela ré sem qualquer ressalva."}],
      mudam=["b0d0006"], contem=["R$ 48.600,00", "1.021, 1.044, 1.078 e 1.102"]),
    T("pe-04", "peticao", "Acrescente na parte do direito um parágrafo sobre os juros de mora desde o vencimento "
      "(art. 397 do Código Civil).", "inserir_paragrafo",
      gabarito=[{"op": "inserir", "depois_de": "b0d0010", "blocos": [
          {"texto": "Tratando-se de obrigação positiva e líquida, com termo certo, o inadimplemento constitui de pleno "
                    "direito o devedor em mora, nos termos do art. 397 do Código Civil, sendo devidos os juros desde o "
                    "vencimento de cada duplicata."}]}],
      contem=["art. 397"], ordem=("art. 397", "b0d0009", "b0d0012")),
    T("pe-05", "peticao", "Tire a parte que fala da notificação extrajudicial.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0d0007", "de": " e não foram pagas, apesar de a ré ter sido notificada extrajudicialmente em 15 de agosto de 2026.",
                 "para": " e não foram pagas."}],
      mudam=["b0d0007"], nao_contem=["notificada extrajudicialmente"]),
    T("pe-06", "peticao", "Qual o valor da causa?", "pergunta", pergunta=True, cita=["b0d0018"]),
    T("pe-07", "peticao", "Mude o endereçamento para a 3ª Vara Cível.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0d0001", "de": "DA ___ VARA CÍVEL", "para": "DA 3ª VARA CÍVEL"}],
      mudam=["b0d0001"], contem=["3ª VARA CÍVEL"]),
    T("pe-08", "peticao", "Deixe o pedido de custas e honorários mais completo, com honorários de 20%.", "estilo",
      gabarito=[{"op": "reescrever", "bloco": "b0d0016", "texto": "c) a condenação da ré ao pagamento das custas "
                 "processuais e dos honorários advocatícios, fixados em 20% (vinte por cento) sobre o valor da "
                 "condenação, nos termos do art. 85, § 2º, do Código de Processo Civil."}],
      mudam=["b0d0016"], contem=["20% (vinte por cento)"]),
    T("pe-09", "peticao", "Troque “ré” por “requerida” em toda a petição.", "nome_em_tudo",
      gabarito=[{"op": "substituir_em_tudo", "de": "ré", "para": "requerida"}],
      mudam=["b0d0006", "b0d0007", "b0d0008", "b0d0014", "b0d0015", "b0d0016"], em_tudo=True,
      nao_contem=[" ré ", " ré,"], contem=["a requerida não efetuou"]),
    T("pe-10", "peticao", "Mova o parágrafo da prova escrita para o fim dos fatos.", "mover",
      gabarito=[{"op": "mover", "bloco": "b0d0011", "depois_de": "b0d0008"}],
      ordem=("A prova escrita da dívida", "b0d0008", "b0d0009")),

    # --------------------------------------------------------------- partilha
    T("pa-01", "partilha", "O apartamento foi avaliado em R$ 760.000,00.", "troca_valor",
      gabarito=[{"op": "substituir", "bloco": "b0e0007", "de": "R$ 720.000,00 (setecentos e vinte mil reais)",
                 "para": "R$ 760.000,00 (setecentos e sessenta mil reais)"}],
      mudam=["b0e0007"], podem=["b0e0013"], contem=["R$ 760.000,00 (setecentos e sessenta mil reais)"]),
    T("pa-02", "partilha", "A torna deve ser paga em 12 parcelas.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0e0013", "de": "10 (dez) parcelas", "para": "12 (doze) parcelas"}],
      mudam=["b0e0013"], contem=["12 (doze) parcelas"], nao_contem=["10 (dez) parcelas"]),
    T("pa-03", "partilha", "Inclua um item sobre a guarda do cachorro Thor, que fica com a segunda cônjuge.",
      "inserir_clausula",
      gabarito=[{"op": "inserir", "depois_de": "b0e0017", "blocos": [
          {"texto": "5. DO ANIMAL DE ESTIMAÇÃO"},
          {"texto": "O cão de estimação do casal, de nome Thor, ficará sob a guarda da SEGUNDA CÔNJUGE, que arcará com "
                    "as despesas de sua manutenção."}]}],
      renumera=True, numeracao=True, contem=["Thor"], ordem=("Thor", "b0e0009", "b0e0018")),
    T("pa-04", "partilha", "A segunda cônjuge vai manter o nome de casada.", "reescrever",
      gabarito=[{"op": "reescrever", "bloco": "b0e0017", "texto": "A SEGUNDA CÔNJUGE continuará a usar o nome de "
                 "casada, PATRÍCIA ROCHA LOPES."}],
      mudam=["b0e0017"], nao_contem=["voltará a usar o nome de solteira"]),
    T("pa-05", "partilha", "Apague a cláusula dos alimentos.", "apagar",
      gabarito=[{"op": "apagar", "blocos": ["b0e0014", "b0e0015"]}], renumera=True, numeracao=True,
      mudam=["b0e0014", "b0e0015"], nao_contem=["DOS ALIMENTOS"]),
    T("pa-06", "partilha", "Qual é o valor da torna?", "pergunta", pergunta=True, cita=["b0e0013"]),
    T("pa-07", "partilha", "O carro é um Honda Civic 2022, placa RTA-4B21.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0e0008", "de": "Toyota Corolla, ano 2023", "para": "Honda Civic, ano 2022"}],
      mudam=["b0e0008"], contem=["Honda Civic, ano 2022"], nao_contem=["Corolla"]),
    T("pa-08", "partilha", "Faça: 1) casamento em 12 de maio de 2012; 2) aplicações no Itaú; 3) quitação também quanto "
      "a dívidas.", "varios",
      gabarito=[{"op": "substituir", "bloco": "b0e0004", "de": "10 de maio de 2012", "para": "12 de maio de 2012"},
                {"op": "substituir", "bloco": "b0e0009", "de": "no Banco do Brasil", "para": "no Itaú Unibanco"},
                {"op": "substituir", "bloco": "b0e0019", "de": "quitação quanto à partilha", "para": "quitação quanto à partilha e às dívidas do casal"}],
      mudam=["b0e0004", "b0e0009", "b0e0019"], contem=["12 de maio de 2012", "Itaú", "dívidas"],
      nao_contem=["Banco do Brasil"]),
    T("pa-09", "partilha", "Mude o regime de bens para comunhão universal.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0e0004", "de": "comunhão parcial de bens", "para": "comunhão universal de bens"}],
      mudam=["b0e0004"], contem=["comunhão universal de bens"]),

    # ------------------------------------------------------------ notificação
    T("no-01", "notificacao", "O prazo para pagar deve ser de 5 dias úteis.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0f0006", "de": "10 (dez) dias", "para": "5 (cinco) dias úteis"}],
      mudam=["b0f0006"], contem=["5 (cinco) dias úteis"], nao_contem=["10 (dez) dias"]),
    T("no-02", "notificacao", "Deixe a notificação mais firme no parágrafo das consequências, mencionando a "
      "negativação no Serasa.", "estilo",
      gabarito=[{"op": "reescrever", "bloco": "b0f0007", "texto": "Decorrido o prazo sem o pagamento, a NOTIFICANTE "
                 "promoverá, independentemente de novo aviso, o protesto dos títulos, a inscrição do débito nos cadastros "
                 "de proteção ao crédito, inclusive o Serasa, e o ajuizamento de ação de cobrança, com a condenação da "
                 "NOTIFICADA nas custas e honorários advocatícios."}],
      mudam=["b0f0007"], contem=["Serasa"]),
    T("no-03", "notificacao", "Inclua os dados bancários para pagamento: Banco Inter, agência 0001, conta 123456-7.",
      "inserir_paragrafo",
      gabarito=[{"op": "inserir", "depois_de": "b0f0006", "blocos": [
          {"texto": "Dados para pagamento: Banco Inter, agência 0001, conta corrente nº 123456-7, de titularidade da "
                    "NOTIFICANTE."}]}],
      podem=["b0f0006"], contem=["Banco Inter"], ordem=("Banco Inter", "b0f0005", "b0f0007")),
    T("no-04", "notificacao", "Tire o e-mail de contato.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0f0008", "de": " ou pelo e-mail financeiro@serraverde.com.br", "para": ""}],
      mudam=["b0f0008"], nao_contem=["financeiro@serraverde.com.br"]),
    T("no-05", "notificacao", "Até quando a notificada tem para pagar?", "pergunta", pergunta=True, cita=["b0f0006"]),
    T("no-06", "notificacao", "A data da notificação é 20 de agosto de 2026.", "troca_local",
      gabarito=[{"op": "substituir", "bloco": "b0f0010", "de": "15 de agosto de 2026", "para": "20 de agosto de 2026"}],
      mudam=["b0f0010"], contem=["20 de agosto de 2026"]),
    T("no-07", "notificacao", "Reescreva isto em linguagem mais simples.", "selecao",
      selecao={"bloco": "b0f0006", "texto": "Fica a NOTIFICADA constituída em mora e intimada a efetuar o pagamento do débito, devidamente atualizado"},
      gabarito=[{"op": "substituir", "bloco": "b0f0006", "de": "Fica a NOTIFICADA constituída em mora e intimada a efetuar o pagamento do débito, devidamente atualizado",
                 "para": "A NOTIFICADA está em atraso e deve pagar a dívida, com correção"}],
      mudam=["b0f0006"], contem=["no prazo de 10 (dez) dias a contar do recebimento desta"]),
    T("no-08", "notificacao", "Coloque o parágrafo do contato antes das consequências.", "mover",
      gabarito=[{"op": "mover", "bloco": "b0f0008", "antes_de": "b0f0007"}],
      ordem=("Para tratar do assunto", "b0f0006", "b0f0007")),

    # --------------------------- o pedido com outras palavras (a ata, 14/10/2026)
    # O advogado resume o texto, escreve com erro de digitação e diz o que NÃO quer.
    T("par-01", "locacao", "Não precisa dizer que a locatária recebe o imovel em perfeito estado de conservassão, ela "
      "recebe em bom estado", "parafrase",
      gabarito=[{"op": "substituir", "bloco": "b0b0021", "de": "em perfeito estado de conservação",
                 "para": "em bom estado de conservação"}],
      mudam=["b0b0021"], contem=["bom estado"], nao_contem=["perfeito estado"]),
    T("par-02", "locacao", "Nao precisa citar o laudo de vistoria, a locatária recebe conforme a vistoria fotográfica "
      "anexa", "parafrase",
      gabarito=[{"op": "substituir", "bloco": "b0b0021", "de": "o laudo de vistoria anexo",
                 "para": "a vistoria fotográfica anexa"}],
      mudam=["b0b0021"], contem=["vistoria fotográfica anexa"], nao_contem=["laudo de vistoria", "o vistoria"]),
    T("par-03", "notificacao", "o prazo de dez dias tá curto, poe quinze", "parafrase",
      gabarito=[{"op": "substituir", "bloco": "b0f0006", "de": "10 (dez) dias", "para": "15 (quinze) dias"}],
      mudam=["b0f0006"], contem=["15 (quinze) dias"], nao_contem=["10 (dez) dias"]),
]


def por_id(id_: str) -> Tarefa:
    return next(t for t in TAREFAS if t.id == id_)
