"""
As colecoes de extensao (spec, passo 7): pedidos, decisoes, eventos, provas,
alegacoes, relacoes e as entidades com documento valido.

O nucleo da camada extrai COISAS - um numero, uma data, um valor. Estas
colecoes extraem FRASES: o que a parte pediu, o que o juiz decidiu, o que
alguem alegou. Muda o risco junto: uma data extraida errada e uma data
errada; uma frase extraida errada e uma afirmacao que o documento nao faz.

Por isso o que se testa aqui e quase todo negativo - o que NAO pode entrar:

  - "confere poderes para requerer" nao e um pedido (e uma procuracao, e o
    acervo deste escritorio e cheio delas)
  - "pede deferimento" nao e um pedido (e a formula de encerramento de toda
    peca do pais)
  - "sustentacao oral" nao e uma alegacao (e um ato processual)
  - "indefiro" nao e "defiro" com uma letra a mais
  - CNPJ com digito verificador errado nao vira entidade

E uma regra que atravessa tudo: toda frase guardada tem de existir no
documento, literalmente, na posicao anotada.

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia_extensao.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as base_mod  # noqa: E402
from extract import index_all_contracts  # noqa: E402
from inteligencia import esquema, portas  # noqa: E402
from inteligencia.catalogo import Catalogo  # noqa: E402
from inteligencia.extratores import frases, regras_pedidos  # noqa: E402
from inteligencia.extratores.base import Pedido  # noqa: E402
from inteligencia.guarda import Biblioteca  # noqa: E402

ACERVO = RAIZ / "data" / "test_contracts"
CACHE = RAIZ / "data" / "extractions" / "index.json"

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


# Uma inicial como elas sao: qualificacao, fundamento, pedido enumerado e a
# formula de encerramento. As quebras de linha no meio de frase estao ai de
# proposito - e assim que texto sai de PDF.
INICIAL = (
    "[pagina 1]\n"
    "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL DA COMARCA DE SÃO PAULO\n"
    "Processo nº 1001234-55.2025.8.26.0100\n"
    "EMPRESA EXEMPLO LTDA., pessoa jurídica de direito privado, inscrita no CNPJ/MF sob o\n"
    "nº 31.984.284/0001-21, vem, por seu advogado, propor AÇÃO DE COBRANÇA em face de\n"
    "JOÃO DA SILVA, brasileiro, portador do CPF nº 111.444.777-35.\n\n"
    "[pagina 2]\n"
    "DOS FATOS\n"
    "O autor alega que celebrou com o réu contrato de prestação de serviços em 12/03/2024,\n"
    "no valor de R$ 15.000,00, e que o réu deixou de pagar as três últimas parcelas.\n"
    "Sustenta que houve inadimplemento absoluto, nos termos do art. 389 do Código Civil.\n"
    "O réu, por sua vez, aduz que o serviço não foi prestado a contento.\n"
    "Junta-se o contrato assinado (doc. 01), as notas fiscais (docs. 02/04) e o\n"
    "comprovante de notificação extrajudicial (doc. 05).\n\n"
    "[pagina 3]\n"
    "DOS PEDIDOS\n"
    "Ante o exposto, requer:\n"
    "a) a concessão da tutela de urgência para inscrição do réu nos cadastros de inadimplentes;\n"
    "b) a citação do réu, na pessoa de seu representante legal;\n"
    "c) a condenação do réu ao pagamento de R$ 15.000,00, devidamente corrigidos;\n"
    "d) a produção de prova documental, testemunhal e pericial contábil;\n"
    "e) a concessão dos benefícios da justiça gratuita.\n"
    "Requer, ainda, a designação de audiência de conciliação.\n"
    "Dá-se à causa o valor de R$ 15.000,00.\n"
    "Nestes termos, pede deferimento.\n"
    "São Paulo, 14 de abril de 2025.\n"
)

# Uma sentenca com o dispositivo inteiro, incluindo as duas armadilhas: o
# indeferimento no meio do texto e as formulas de encerramento no fim.
SENTENCA = (
    "[pagina 1]\n"
    "SENTENÇA\n"
    "Processo nº 1001234-55.2025.8.26.0100\n"
    "Vistos.\n"
    "Trata-se de ação de cobrança ajuizada por EMPRESA EXEMPLO LTDA. em face de\n"
    "JOÃO DA SILVA.\n"
    "Na decisão de fls. 45, INDEFIRO a tutela de urgência pleiteada, por ausência de\n"
    "perigo de dano.\n"
    "Ante o exposto, JULGO PARCIALMENTE PROCEDENTE o pedido, para condenar o réu ao\n"
    "pagamento de R$ 10.000,00, corrigidos desde o vencimento.\n"
    "CONDENO o réu ao pagamento das custas e honorários advocatícios.\n"
    "DEFIRO ao autor os benefícios da justiça gratuita.\n"
    "HOMOLOGO o acordo parcial celebrado quanto às parcelas vencidas.\n"
    "Julgo extinto o processo, com resolução do mérito, nos termos do art. 487, I, do CPC.\n"
    "Publique-se. Registre-se. Intime-se.\n"
    "São Paulo, 20 de agosto de 2025.\n"
)

# Uma procuracao de verdade do acervo, reduzida: a lista de poderes tem
# "requerer" no infinitivo, e nao pede nada.
PROCURACAO = (
    "[pagina 1]\n"
    "INSTRUMENTO PARTICULAR DE PROCURAÇÃO\n"
    "OUTORGANTE: COOPERATIVA BRASILEIRA LTDA., CNPJ/MF 31.984.284/0001-21.\n"
    "Através do presente instrumento particular de mandato, o OUTORGANTE confere poderes\n"
    "de representação perante as repartições Públicas Federais, podendo para tanto\n"
    "apresentar e cumprir exigências, requerer e/ou efetivar toda documentação necessária,\n"
    "atender notificação, protocolar documentos, requerer e assinar todos os atos\n"
    "necessários ao fiel desempenho deste mandato, sendo vedado o substabelecimento.\n"
    "São Félix do Xingu - PA, 06 de outubro de 2021.\n"
)


def pedido_de(texto: str) -> Pedido:
    from inteligencia.texto import mapa_de_paginas

    return Pedido(texto=texto, version_id="ver_teste", paginas=mapa_de_paginas(texto))


def ancorados(itens, texto: str) -> bool:
    """Todo item aponta para um trecho que existe mesmo, naquela posicao."""
    for item in itens:
        inicio, fim = item.source.char_start, item.source.char_end
        if inicio is None or fim is None:
            return False
        if texto[inicio:fim].strip() != item.quote.strip():
            return False
    return True


# ------------------------------------------------------------------ pedidos


def test_pedidos() -> None:
    print("\nos pedidos da peça")
    resultado = regras_pedidos.extrair(pedido_de(INICIAL))
    itens = resultado.itens
    tipos = [i.dados["kind"] for i in itens]
    textos = [i.dados["text"] for i in itens]

    checar(len(itens) == 6, "a enumeração virou seis pedidos, e não um só", textos)
    checar(tipos[:5] == ["injunction", "citation", "condemnation",
                         "evidence_production", "free_justice"],
           "cada alínea saiu com o próprio rótulo", tipos)
    checar(any("audiência de conciliação" in t for t in textos),
           "o pedido escrito fora da lista também entra", textos)
    checar(not any("deferimento" in t for t in textos),
           "'pede deferimento' não é pedido - é a formula de encerramento", textos)
    checar(not any("Ante o exposto" in t for t in textos),
           "o anúncio da lista não vira pedido", textos)
    checar(all(i.pode_virar_fato for i in itens),
           "todo pedido nasce conferido, porque a citação é o próprio texto")
    checar(ancorados(itens, INICIAL), "e cada um aponta para onde está no documento")
    checar([i.source.page for i in itens] == [3] * 6,
           "todos na página 3, que é onde está o capítulo dos pedidos",
           [i.source.page for i in itens])


def test_procuracao_nao_pede_nada() -> None:
    """
    A armadilha que o acervo deste escritório tem de verdade.

    Metade dos documentos de teste são procurações, e todas dizem "requerer"
    numa lista de poderes. Se o infinitivo contasse, cada procuração viraria
    duas linhas de pedido - e "quais os pedidos?" responderia com poderes.
    """
    print("\na procuração não pede nada")
    resultado = regras_pedidos.extrair(pedido_de(PROCURACAO))
    checar(resultado.itens == [], "poder no infinitivo não é pedido",
           [i.dados.get("text") for i in resultado.itens])

    docs = index_all_contracts(ACERVO, CACHE, verbose=False)
    comeco = time.time()
    total = sum(len(regras_pedidos.extrair(Pedido(texto=d.text)).itens) for d in docs)
    print(f"       {len(docs)} documentos reais varridos em "
          f"{round(time.time() - comeco, 3)} s")
    checar(total == 0, f"e no acervo real (sem petição) não achou pedido nenhum: {total}")


# ------------------------------------------------------------------ esquema


def test_colecao_nova_nao_migra_nada() -> None:
    """
    A promessa da spec: acrescentar uma coleção não mexe no que já está gravado.

    O metadata de um documento analisado ANTES do passo 7 continua sendo lido
    sem erro, sem chave nova e sem perder nada - e a coleção que ele não tem
    é tratada como seção ausente, que é o que o roteador já sabe escalar.
    """
    print("\numa coleção nova não migra o acervo")
    antigo = {
        "schema": esquema.ESQUEMA,
        "document": {"id": "doc_1", "title": "velho.pdf"},
        "version": {"id": "ver_1", "sha256": "abc"},
        "dates": [], "amounts": [], "parties": [], "legal_references": [],
        "analysis": {"sections": {"dates": {"extractor": "date-parser/v1", "status": "ok"}}},
    }
    meta = esquema.Metadata.from_dict(antigo)
    checar(meta.colecao("requests") == [], "coleção que não existe lê como vazia")
    checar(meta.secao("requests").status == "missing",
           "e a seção dela fica 'missing', que é o que faz o roteador escalar")
    checar("requests" not in meta.to_dict(),
           "gravar de novo não inventa a chave que ninguém extraiu",
           sorted(meta.to_dict().keys()))
    checar(not esquema.problemas(meta.to_dict()), "o metadata antigo continua válido")

    meta.guardar("requests", [])
    checar(meta.to_dict().get("requests") == [],
           "depois de analisar, a lista vazia aparece - analisado e não achou "
           "é diferente de ninguém procurou")


def test_analise_guarda_as_colecoes() -> None:
    """Ponta a ponta: o HOOK 1 grava a coleção nova e a lê de volta igual."""
    print("\na análise guarda e relê as coleções")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        bd = base_mod.Base(pasta / "teste.db")
        bd.migrar()
        biblioteca = Biblioteca(pasta / "conhecimento", bd)
        catalogo = Catalogo.carregar()
        checar(not catalogo.problemas(), "o catálogo continua coerente", catalogo.problemas())

        arquivo = pasta / "inicial.txt"
        arquivo.write_text(INICIAL, encoding="utf-8")
        analise = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=INICIAL,
                                            paginas=3, sha1="sha-inicial", titulo="inicial.txt")
        checar("requests" in analise.rodadas, "a seção nova rodou na ingestão", analise.rodadas)
        checar(not analise.falhas, "sem falha", analise.falhas)

        relido = biblioteca.ler_por_sha1("sha-inicial")
        checar(len(relido.fatos("requests")) == 6,
               "e voltou do disco com os seis pedidos conferidos",
               [i.valor for i in relido.colecao("requests")])
        checar(not esquema.problemas(relido.to_dict()), "o metadata gravado é válido",
               esquema.problemas(relido.to_dict()))
        bd.fechar()


# ----------------------------------------------------------------- decisões


def test_decisoes() -> None:
    """
    O dispositivo, e a palavra que contém a palavra contrária.

    "Indefiro" contém "defiro"; "improcedente" contém "procedente". Um
    classificador que procurasse a primeira pista da lista responderia
    "deferido" para "INDEFIRO" - e esse é o erro mais caro possível aqui,
    porque tem exatamente a cara de uma resposta certa.
    """
    print("\no dispositivo da sentença")
    from inteligencia.extratores import regras_decisoes

    itens = regras_decisoes.extrair(pedido_de(SENTENCA)).itens
    desfechos = [i.dados["kind"] for i in itens]
    textos = [i.dados["text"] for i in itens]

    checar(desfechos == ["denied", "partial", "conviction", "granted",
                         "homologated", "extinguished"],
           "cada decisão saiu com o próprio desfecho", list(zip(desfechos, textos)))
    checar(desfechos[0] == "denied", "'INDEFIRO' é indeferimento, não deferimento")
    checar(desfechos[1] == "partial",
           "'PARCIALMENTE PROCEDENTE' é parcial, não procedente")
    checar(not any("Publique-se" == t for t in textos),
           "'Publique-se. Registre-se.' não decide nada - é formula de encerramento",
           textos)
    checar(ancorados(itens, SENTENCA), "e cada uma aponta para onde está no documento")

    docs = index_all_contracts(ACERVO, CACHE, verbose=False)
    total = sum(len(regras_decisoes.extrair(Pedido(texto=d.text)).itens) for d in docs)
    checar(total == 0,
           f"e nos {len(docs)} documentos reais (sem sentença) não achou decisão: {total}")


def test_roteador_lista_decisoes() -> None:
    print("\no roteador responde o que foi decidido")
    from inteligencia import roteador

    with tempfile.TemporaryDirectory() as tmp:
        bd, meta = biblioteca_com(SENTENCA, Path(tmp), sha1="sha-sentenca")
        pacote = decidir(meta, "qual foi a decisão?")
        checar(pacote.nivel == roteador.METADATA and pacote.enumera,
               "'qual foi a decisão?' responde do que já foi lido", pacote.trace)
        rotulos = [f.rotulo for f in pacote.fatos]
        checar("indeferido" in rotulos and "parcial" in rotulos,
               "e o rótulo de cada uma chega em português", rotulos)

        checar(decidir(meta, "por que o juiz decidiu assim?").fallback,
               "'por que' pede leitura e continua escalando")
        bd.fechar()


# ----------------------------------------------------------------- roteador


def biblioteca_com(texto: str, tmp: Path, paginas: int = 3, sha1: str = "sha-teste"):
    bd = base_mod.Base(tmp / "roteador.db")
    bd.migrar()
    biblioteca = Biblioteca(tmp / "conhecimento", bd)
    catalogo = Catalogo.carregar()
    arquivo = tmp / "peca.txt"
    arquivo.write_text(texto, encoding="utf-8")
    portas.analisar_documento(biblioteca, catalogo, arquivo, texto=texto, paginas=paginas,
                              sha1=sha1, titulo="peca.txt")
    return bd, biblioteca.ler_por_sha1(sha1)


def decidir(meta, pergunta: str, em_foco: bool = True):
    from inteligencia import roteador

    return roteador.resolver(pergunta, [meta], nomes={meta.version_id: "peca.txt"},
                             em_foco=em_foco)


def test_roteador_lista_pedidos() -> None:
    """
    A pergunta de lista, e as três travas que a impedem de virar meia resposta.
    """
    print("\no roteador responde a lista de pedidos")
    from inteligencia import roteador

    with tempfile.TemporaryDirectory() as tmp:
        bd, meta = biblioteca_com(INICIAL, Path(tmp))

        pacote = decidir(meta, "quais os pedidos?")
        checar(pacote.nivel == roteador.METADATA and pacote.enumera and not pacote.fallback,
               "'quais os pedidos?' responde do que já foi lido", pacote.trace)
        checar(len(pacote.fatos) == 6, "com os seis pedidos", len(pacote.fatos))
        checar(all(f.quote and f.pagina == 3 for f in pacote.fatos),
               "cada um com o trecho literal e a página")

        prompt = pacote.prompt("quais os pedidos?")
        checar("EXPRESSAMENTE" in prompt,
               "o prompt diz que a lista é do que está escrito, não do que se deduziu")
        checar("ESCALAR" in prompt, "e mantém a saída de emergência")

        fora = decidir(meta, "quais os pedidos?", em_foco=False)
        checar(fora.fallback and fora.nivel == roteador.BUSCADOR,
               "sem documento em foco, escala - listar pedidos de vários é juntar peças",
               fora.trace)

        recortada = decidir(meta, "quais os pedidos sobre a tutela de urgência?")
        checar(recortada.fallback,
               "pergunta com recorte pede leitura, e a lista inteira não responde",
               recortada.trace)

        # Um documento que ainda nao foi analisado para pedidos nao responde
        # "nenhum": ele pode ter dez escritos.
        from inteligencia.esquema import Metadata

        virgem = Metadata(document={"id": "d"}, version={"id": "v"})
        vazio = roteador.resolver("quais os pedidos?", [virgem], em_foco=True)
        checar(vazio.fallback, "documento não analisado escala, não responde 'nenhum'",
               vazio.trace)
        bd.fechar()


def test_lista_longa_demais_escala() -> None:
    """
    A trava que mais protege: lista cortada tem cara de lista completa.

    Quem lê uma resposta com oito pedidos não tem como saber que havia
    quinze. Então, quando a lista não cabe, a pergunta volta a ler o
    documento - que é exatamente o que acontecia antes desta camada.
    """
    print("\nlista que não cabe na resposta escala")
    from inteligencia import roteador

    longa = INICIAL + "\n".join(
        f"Requer, ainda, a expedição de ofício ao órgão número {n}." for n in range(1, 15))
    with tempfile.TemporaryDirectory() as tmp:
        bd, meta = biblioteca_com(longa, Path(tmp), sha1="sha-longa")
        achados = len(meta.fatos("requests"))
        pacote = decidir(meta, "quais os pedidos?")
        checar(achados >= roteador.FATOS_MAX, f"a peça tem {achados} pedidos escritos")
        checar(pacote.fallback, "e a resposta escala em vez de cortar a lista", pacote.trace)
        bd.fechar()


# ------------------------------------------------------------------- frases


def test_onde_a_frase_acaba() -> None:
    """
    O ponto que não termina frase - a maioria deles, num documento jurídico.

    Sem isto, "requer, nos termos do art. 300 do CPC, a tutela" vira "requer,
    nos termos do art." e a resposta fica sem o pedido.
    """
    print("\nonde a frase acaba")
    texto = ("Nos termos do art. 300 do CPC, requer a tutela de urgência, para que\n"
             "a ré se abstenha de cobrar. Outra frase.")
    inicio = texto.find("requer")
    trecho = texto[slice(*frases.clausula(texto, inicio))]
    checar(trecho.endswith("abstenha de cobrar."), "'art. 300' não termina a frase", trecho)
    checar("para que\na ré" in trecho, "e a quebra de linha do PDF também não", trecho)

    valor = "O valor da causa é de R$ 15.000,00. Fim."
    trecho = valor[slice(*frases.clausula(valor, 0))]
    checar(trecho.strip() == "O valor da causa é de R$ 15.000,00.",
           "o ponto do milhar não termina frase", trecho)


def main() -> int:
    print("=" * 55)
    print("  PAULUS - colecoes de extensao (passo 7)")
    print("=" * 55)
    test_onde_a_frase_acaba()
    test_pedidos()
    test_procuracao_nao_pede_nada()
    test_colecao_nova_nao_migra_nada()
    test_analise_guarda_as_colecoes()
    test_roteador_lista_pedidos()
    test_lista_longa_demais_escala()
    test_decisoes()
    test_roteador_lista_decisoes()

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
