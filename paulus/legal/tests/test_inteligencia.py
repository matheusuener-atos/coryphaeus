"""
A camada de inteligencia de documentos: guardar o que ja foi entendido.

Este arquivo cobre o passo 1 da implantacao - persistir o que o programa ja
extrai, com identidade estavel e mapa de paginas. Nada aqui muda o
comportamento do chatbot: o que se testa e que o alicerce esta no lugar.

O que importa provar:

  - o texto guardado e o MESMO que o buscador usa, byte a byte; se divergir,
    todo span citado passa a apontar para outro lugar
  - o mapa de paginas sai das marcas que o extrator ja escreve, e documento
    sem pagina nao inventa "p. 1"
  - a normalizacao aproxima a citacao do modelo do texto do documento sem
    perder o caminho de volta ao original
  - identidade: renomear nao cria documento novo, mudar o conteudo cria versao
    nova e a anterior fica

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as base_mod  # noqa: E402
from inteligencia import esquema, guarda, texto as texto_mod  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


DOC_PDF = (
    "[pagina 1]\n"
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS\n"
    "COOPERATIVA BRASILEIRA LTDA., pessoa jurídica de direito privado, inscrita no "
    "CNPJ sob o nº 11.222.333/0001-81, doravante CONTRATANTE.\n\n"
    "[pagina 2]\n"
    "CLÁUSULA QUARTA — Os honorários são de R$ 15.000,00, pagos em doze parcelas.\n"
    "Processo nº 1234567-89.2025.8.26.0100, em trâmite na 3ª Vara Cível de São Paulo.\n"
)


def test_mapa_de_paginas() -> None:
    print("\no mapa de paginas")
    paginas = texto_mod.mapa_de_paginas(DOC_PDF)
    checar(len(paginas) == 2, f"as duas paginas foram achadas ({len(paginas)})")
    checar(paginas[0].numero == 1 and paginas[0].inicio == 0, "a primeira comeca no comeco", paginas[0].to_dict())
    checar(paginas[1].fim == len(DOC_PDF), "e a ultima vai ate o fim do texto", paginas[1].to_dict())

    onde = DOC_PDF.index("CLÁUSULA QUARTA")
    checar(texto_mod.pagina_de(paginas, onde) == 2, "um caractere da segunda pagina cai na pagina 2")
    checar(texto_mod.pagina_de(paginas, 5) == 1, "e um da primeira, na pagina 1")

    # DOCX e TXT nao tem pagina: dizer "p. 1" seria mandar a pessoa procurar
    # uma pagina que o arquivo nao tem.
    sem = texto_mod.mapa_de_paginas("Um texto qualquer, sem marca de pagina.")
    checar(len(sem) == 1 and sem[0].numero == 0, "documento sem pagina vira uma faixa so")
    checar(texto_mod.pagina_de(sem, 3) is None, "e a pagina de um caractere dele e nenhuma")


def test_normalizar() -> None:
    """A citacao do modelo quase nunca sai byte a byte igual ao documento."""
    print("\nnormalizar para comparar, sem perder o caminho de volta")
    bruto = "A CONTRA-\nTANTE  declara   que\nleu a “cláusula” — e concordou."
    n = texto_mod.normalizar(bruto)

    checar("CONTRATANTE declara que leu" in n.plano,
           "palavra partida no fim da linha volta inteira, espacos colapsados", n.plano)
    checar('"cláusula"' in n.plano, "aspas curvas viram aspas retas", n.plano)
    checar(" - e concordou." in n.plano, "e o travessao vira hifen", n.plano)
    checar("cláusula" in n.plano, "o acento fica: a citacao vai para a tela como esta escrita")

    # O caminho de volta: achar na forma normalizada tem de virar um span no
    # texto de verdade, senao a citacao aponta para um texto que so existe
    # dentro do programa.
    onde = n.plano.index("declara")
    inicio, fim = n.original(onde, onde + len("declara"))
    checar(bruto[inicio:fim] == "declara", "o span volta para o original certo", bruto[inicio:fim])

    onde = n.plano.index("CONTRATANTE")
    inicio, fim = n.original(onde, onde + len("CONTRATANTE"))
    checar(bruto[inicio:fim].replace("-\n", "") == "CONTRATANTE",
           "inclusive a palavra que estava partida", repr(bruto[inicio:fim]))

    checar(texto_mod.normalizar("").plano == "", "texto vazio nao quebra")
    checar("[pagina 1]" in texto_mod.normalizar(DOC_PDF).plano,
           "a marca de pagina continua no texto: ela e do original")


def test_biblioteca() -> None:
    print("\na biblioteca: identidade, versoes e o que fica no disco")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        bd = base_mod.Base(pasta / "teste.db")
        bd.migrar()
        biblioteca = guarda.Biblioteca(pasta / "conhecimento", bd)

        arquivo = pasta / "contrato.txt"
        arquivo.write_text(DOC_PDF, encoding="utf-8")

        r1 = biblioteca.registrar(arquivo, DOC_PDF, paginas=2, sha1="abc123")
        checar(r1.documento_novo and r1.versao_nova, "o primeiro registro cria documento e versao")
        checar(r1.document_id.startswith("doc_") and r1.version_id.startswith("ver_"),
               "com ids proprios, que nao dependem do nome do arquivo", (r1.document_id, r1.version_id))

        guardado = biblioteca.texto_da_versao(r1.document_id, r1.version_id)
        checar(guardado == DOC_PDF, "o texto guardado e byte a byte o que o buscador usa")
        checar(len(biblioteca.paginas_da_versao(r1.document_id, r1.version_id)) == 2,
               "o mapa de paginas foi para o disco junto")

        alvo = biblioteca.pasta_da_versao(r1.document_id, r1.version_id) / "metadata.json"
        dados = json.loads(alvo.read_text(encoding="utf-8"))
        checar(dados["schema"] == esquema.ESQUEMA, "o metadata declara o esquema", dados.get("schema"))
        checar(not esquema.problemas(dados), "e nasce sem problema de formato", esquema.problemas(dados))
        checar(dados["provenance"]["text_sha256"], "com o hash do texto extraido")
        checar(dados["version"]["page_count"] == 2 and dados["version"]["sha1"] == "abc123",
               "e com o que a ingestao ja sabia: paginas e o sha1 do acervo")

        # Idempotente: a ingestao roda de novo em cima do acervo sem duplicar.
        r2 = biblioteca.registrar(arquivo, DOC_PDF, paginas=2, sha1="abc123")
        checar(not r2.versao_nova and r2.version_id == r1.version_id,
               "registrar de novo o mesmo arquivo nao cria versao nova")
        checar(len(biblioteca.listar()) == 1, "e o acervo continua com um documento")

        # Renomear nao e criar documento: o conteudo e o mesmo.
        renomeado = pasta / "contrato assinado.txt"
        arquivo.rename(renomeado)
        r3 = biblioteca.registrar(renomeado, DOC_PDF, paginas=2, sha1="abc123")
        checar(r3.document_id == r1.document_id and not r3.versao_nova,
               "renomear o arquivo nao cria documento novo")
        checar(biblioteca.ler(r3.document_id).version["source_path"].endswith("contrato assinado.txt"),
               "mas o caminho novo fica anotado")

        # Mudar o conteudo e outra versao - e a anterior nao some.
        mudado = DOC_PDF.replace("R$ 15.000,00", "R$ 18.000,00")
        renomeado.write_text(mudado, encoding="utf-8")
        r4 = biblioteca.registrar(renomeado, mudado, paginas=2, sha1="def456")
        checar(r4.versao_nova and r4.document_id == r1.document_id,
               "conteudo diferente cria versao nova do mesmo documento")
        checar(biblioteca.ler(r1.document_id, r1.version_id) is not None,
               "a versao anterior continua legivel - e ela que sustenta o que ja foi citado")
        checar(biblioteca.ler(r1.document_id).version_id == r4.version_id,
               "e a atual passa a ser a nova")
        checar(biblioteca.ler_por_sha1("def456").version_id == r4.version_id,
               "da para achar pelo sha1, que e como o acervo deste programa identifica arquivo")

        historico = (biblioteca.pasta_da_versao(r1.document_id, r1.version_id) / "analysis-history.jsonl")
        checar(historico.exists() and historico.read_text(encoding="utf-8").count("\n") >= 1,
               "cada gravacao deixa linha no historico da versao")

        # O original nunca e tocado: e a regra que faz o programa confiavel.
        checar(renomeado.read_text(encoding="utf-8") == mudado, "o arquivo original continua como estava")
        dentro = [p.name for p in (pasta / "conhecimento" / "documents").iterdir()]
        checar(dentro == [r1.document_id], "e a biblioteca vive so na pasta do programa", dentro)
        bd.fechar()


def test_secoes_e_fatos() -> None:
    """O indice em sqlite e o espelho do metadata - e so do que foi conferido."""
    print("\no indice: secoes e fatos")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        bd = base_mod.Base(pasta / "teste.db")
        bd.migrar()
        biblioteca = guarda.Biblioteca(pasta / "conhecimento", bd)
        arquivo = pasta / "contrato.txt"
        arquivo.write_text(DOC_PDF, encoding="utf-8")
        registro = biblioteca.registrar(arquivo, DOC_PDF, paginas=2)
        meta = registro.metadata

        conferido = esquema.Item(
            id="party_001", dados={"name": "Cooperativa Brasileira Ltda.", "role": "contratante"},
            quote="COOPERATIVA BRASILEIRA LTDA.", certainty="explicit", verified=True,
            source=esquema.Fonte(version_id=meta.version_id, kind="text", page=1,
                                 char_start=60, char_end=88),
            produced_by="teste/v1")
        chutado = esquema.Item(
            id="party_002", dados={"name": "Alguém Não Conferido", "role": "contratado"},
            quote="", certainty="inferred", verified=False, produced_by="teste/v1")
        meta.parties = [conferido, chutado]
        meta.marcar_secao("parties", esquema.Secao(
            extractor="teste/v1", status="ok", item_count=2, unverified_count=1,
            generated_at=esquema.agora()))
        biblioteca.gravar(meta, nota="teste")

        fatos = bd.buscar("SELECT * FROM meta_fatos WHERE secao = 'parties' ORDER BY item_id")
        checar(len(fatos) == 2, "os dois itens foram indexados", len(fatos))
        checar(fatos[0]["verificado"] == 1 and fatos[1]["verificado"] == 0,
               "e so o conferido esta marcado como utilizavel", [f["verificado"] for f in fatos])
        checar(fatos[0]["chave"] == "contratante" and fatos[0]["pagina"] == 1,
               "com o papel e a pagina, que e o que a resposta cita", fatos[0])

        checar([i.id for i in meta.fatos("parties")] == ["party_001"],
               "e a regra do fato so deixa passar o conferido e explicito")

        # Secao velha e tratada como inexistente, nao como errada: o roteador
        # escala e a resposta volta a ser a de hoje.
        biblioteca.envelhecer("parties", "extractor_version_changed")
        depois = biblioteca.ler(registro.document_id)
        checar(depois.secao("parties").status == "stale", "envelhecer marca a secao")
        checar(depois.fatos("parties") == [], "e secao stale nao produz fato nenhum")
        checar(bd.buscar("SELECT * FROM meta_fatos WHERE secao = 'parties'") == [],
               "nem no indice")
        bd.fechar()


def test_problemas_do_formato() -> None:
    print("\no formato se defende")
    ruim = {
        "schema": "outro/v9",
        "document": {"id": ""}, "version": {"id": "ver_1"},
        "parties": [{"id": "", "name": "X", "certainty": "explicit", "verified": True}],
        "analysis": {"sections": {"parties": {"status": "inventado"}}},
    }
    achados = " | ".join(esquema.problemas(ruim))
    for pedaco in ("schema", "document.id", "version.sha256", "sem id", "explicit sem quote",
                   "verificado sem fonte", "status 'inventado'"):
        checar(pedaco in achados, f"reclama de “{pedaco}”", achados)


def main() -> int:
    print("=" * 55)
    print("  PAULUS - camada de inteligencia (passo 1)")
    print("=" * 55)
    test_mapa_de_paginas()
    test_normalizar()
    test_biblioteca()
    test_secoes_e_fatos()
    test_problemas_do_formato()

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
