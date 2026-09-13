"""
Os extratores de regra - o nivel mais confiavel da camada.

Nivel 0 nao e atalho. Numero de processo tem digito verificador, data e valor
em portugues tem forma fixa e citacao de lei e altamente regular: tudo isso
uma expressao regular acerta sempre e de graca, enquanto um modelo de tres
bilhoes de parametros erraria de formas imprevisiveis - e cobrando um minuto
por documento.

O que se testa aqui e o que faria a camada mentir se estivesse errado:

  - o digito verificador do CNJ, nos dois sentidos: numero valido passa,
    numero com um digito trocado nao passa
  - o rotulo do valor e da data sai da pista MAIS PROXIMA, e nao da primeira
    da lista - senao "a multa e de R$ 1.500,00" vira valor da causa
  - citacao sem instrumento fica sem instrumento, em vez de virar "do CPC"
  - todo item nasce com fonte que aponta para o texto de verdade

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia_regras.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as base_mod  # noqa: E402
from inteligencia import esquema, portas  # noqa: E402
from inteligencia.catalogo import Catalogo  # noqa: E402
from inteligencia.extratores import (  # noqa: E402
    regras_datas, regras_leis, regras_processo, regras_valores,
)
from inteligencia.extratores.base import Pedido  # noqa: E402
from inteligencia.guarda import Biblioteca  # noqa: E402
from inteligencia.texto import mapa_de_paginas  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


PECA = (
    "[pagina 1]\n"
    "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL\n"
    "Processo nº 0001327-64.2018.8.26.0158\n"
    "COOPERATIVA BRASILEIRA LTDA., já qualificada, vem apresentar contestação.\n\n"
    "[pagina 2]\n"
    "Nos termos do art. 300, §1º, II, do CPC, e do artigo 5º, inciso LV, da Constituição "
    "Federal, requer a tutela. Aplica-se ainda o art. 42 do CDC e a Súmula 331 do TST.\n"
    "O contrato foi assinado em 12 de março de 2025; o aviso de não renovação vence em "
    "15/06/2025. A audiência foi designada para 20/08/2025.\n"
    "O valor da causa é de R$ 15.000,00; a multa contratual é de R$ 1.500,00 e os "
    "honorários advocatícios, R$ 3.000,00.\n"
    "Na forma do art. 927, requer-se o acolhimento.\n"
)


def pedido_da_peca() -> Pedido:
    return Pedido(texto=PECA, version_id="ver_teste", paginas=mapa_de_paginas(PECA), nome="peca.pdf")


def test_digito_do_processo() -> None:
    """O unico campo deste sistema que se confere sozinho."""
    print("\no numero do processo e o digito verificador")
    for numero, ano, justica, tribunal, origem in (
        ("1234567", "2025", "8", "26", "0100"),
        ("0000001", "2010", "8", "26", "0001"),
        ("7654321", "2019", "5", "02", "0011"),
    ):
        dv = regras_processo.digito_verificador(numero, ano, justica, tribunal, origem)
        checar(regras_processo.valido(numero, dv, ano, justica, tribunal, origem),
               f"o digito calculado fecha ({regras_processo.formatar(numero, dv, ano, justica, tribunal, origem)})")
        trocado = f"{(int(dv) + 1) % 100:02d}"
        checar(not regras_processo.valido(numero, trocado, ano, justica, tribunal, origem),
               "e um digito trocado nao fecha")

    # Numero real, com a pontuacao que aparece na capa do processo.
    achados = regras_processo.achar("Autos nº 0001327-64.2018.8.26.0158, em tramite.")
    checar(len(achados) == 1 and achados[0]["valido"], "um numero real e reconhecido e validado", achados)
    checar(achados[0]["justica"] == "Justiça Estadual", "com o segmento do Judiciario", achados[0])

    # A forma crua, que e como sai de sistema e de planilha.
    cru = regras_processo.achar("processo 00013276420188260158 protocolado")
    checar(len(cru) == 1 and cru[0]["numero"] == "0001327-64.2018.8.26.0158",
           "a forma sem pontuacao vira a forma canonica", cru)

    # CNPJ tem 14 digitos, telefone tem 11: nada disso pode virar processo.
    checar(not regras_processo.achar("CNPJ 11.222.333/0001-81, telefone (62) 99999-0000"),
           "CNPJ e telefone nao viram numero de processo")

    resultado = regras_processo.extrair(pedido_da_peca())
    caso = resultado.objeto or {}
    checar(caso.get("case_number") == "0001327-64.2018.8.26.0158" and caso.get("case_number_valid"),
           "a secao `case` sai da peca com o numero certo", caso)
    checar(caso.get("source", {}).get("page") == 1, "e com a pagina em que ele aparece", caso.get("source"))

    # Digito que nao fecha nao vira fato: fica dito, para conferencia humana.
    torto = regras_processo.extrair(Pedido(texto="Processo nº 1234567-89.2025.8.26.0100"))
    checar(torto.objeto.get("verified") is False and "dígito" in torto.objeto.get("note", ""),
           "numero com digito errado nao e apresentado como fato", torto.objeto)


def test_datas_e_valores() -> None:
    print("\ndatas e valores: o rotulo vem da pista mais proxima")
    datas = {i.dados["date"]: i.dados["kind"] for i in regras_datas.extrair(pedido_da_peca()).itens}
    checar(datas.get("2025-03-12") == "signature", "a data de assinatura e assinatura", datas)
    checar(datas.get("2025-06-15") == "deadline", "a que vence e prazo", datas)
    checar(datas.get("2025-08-20") == "hearing", "e a da audiencia e audiencia", datas)

    valores = {i.dados["value"]: i.dados["kind"] for i in regras_valores.extrair(pedido_da_peca()).itens}
    checar(valores.get(15000.0) == "claim", "o valor da causa e valor da causa", valores)
    checar(valores.get(1500.0) == "penalty", "a multa nao virou valor da causa", valores)
    checar(valores.get(3000.0) == "fee", "e o honorario e honorario", valores)

    # O numero entra como numero: guardar "R$ 15.000,00" em texto faz alguem
    # reinterpretar depois, e quinze mil vira quinze.
    item = next(i for i in regras_valores.extrair(pedido_da_peca()).itens if i.dados["value"] == 15000.0)
    checar(isinstance(item.dados["value"], float) and item.dados["currency"] == "BRL",
           "o valor e numero e moeda, nao texto", item.dados)
    checar(item.dados["value_text"] == "R$ 15.000,00", "e o texto original fica para conferir")
    checar(item.source.page == 2 and PECA[item.source.char_start:item.source.char_end] == "R$ 15.000,00",
           "a fonte aponta para o lugar exato do texto", item.source.to_dict())

    vazio = regras_datas.extrair(Pedido(texto="Um texto sem data nenhuma."))
    checar(vazio.itens == [], "texto sem data nao inventa data")


def test_referencias_de_lei() -> None:
    print("\nas citacoes de lei")
    itens = regras_leis.extrair(pedido_da_peca()).itens
    por_artigo = {i.dados.get("article"): i.dados for i in itens if i.dados.get("kind") == "article"}

    checar(por_artigo.get("300", {}).get("instrument_id") == "lei_13105_2015",
           "“art. 300 do CPC” vira o identificador da lei 13.105/2015", por_artigo.get("300"))
    checar(por_artigo.get("300", {}).get("paragraph") == "1" and por_artigo["300"].get("item") == "II",
           "com paragrafo e inciso separados", por_artigo.get("300"))
    checar(por_artigo.get("5", {}).get("instrument_id") == "constituicao_1988",
           "a Constituicao escrita por extenso cai no mesmo identificador", por_artigo.get("5"))
    checar(por_artigo.get("42", {}).get("instrument") == "CDC", "e o CDC e reconhecido", por_artigo.get("42"))

    # A regra que impede a camada de completar o que o documento nao disse.
    checar("instrument" not in por_artigo.get("927", {}),
           "“art. 927” sem dizer a lei fica sem lei, em vez de virar CPC", por_artigo.get("927"))

    sumula = next((i.dados for i in itens if i.dados.get("kind") == "precedent"), {})
    checar(sumula.get("number") == "331" and sumula.get("court") == "TST",
           "a sumula sai com numero e tribunal", sumula)

    lei = next((i.dados for i in itens if i.dados.get("kind") == "law"), {})
    checar(not lei or lei.get("instrument_id", "").startswith("lei_"),
           "lei citada sozinha vira item proprio", lei)

    # A mesma citacao repetida no documento e uma citacao so.
    repetido = regras_leis.extrair(Pedido(texto="art. 300 do CPC ... novamente o art. 300 do CPC"))
    checar(len(repetido.itens) == 1, "citacao repetida nao vira dois itens", len(repetido.itens))


def test_analise_inteira() -> None:
    """O HOOK 1 de ponta a ponta: analisar duas vezes nao refaz nada."""
    print("\nanalisar o documento (HOOK 1)")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        bd = base_mod.Base(pasta / "teste.db")
        bd.migrar()
        biblioteca = Biblioteca(pasta / "conhecimento", bd)
        catalogo = Catalogo.carregar()
        checar(not catalogo.problemas(), "o catalogo do repositorio esta coerente", catalogo.problemas())

        arquivo = pasta / "peca.txt"
        arquivo.write_text(PECA, encoding="utf-8")

        primeira = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                             paginas=2, sha1="sha-teste", titulo="peca.txt")
        # Com o assistente desligado rodam as secoes que nao precisam dele:
        # as quatro de regra pura mais classificacao e juizo, que so chamam o
        # modelo quando a regra nao decide.
        checar(sorted(primeira.rodadas) == ["amounts", "case", "classification", "dates",
                                            "jurisdiction", "legal_references"],
               "as secoes que nao precisam do modelo rodaram", primeira.rodadas)
        checar(not primeira.falhas, "sem falha", primeira.falhas)

        meta = primeira.metadata
        checar(meta.case.get("case_number_valid") is True, "o caso ficou com numero validado")
        checar(len(meta.fatos("amounts")) == 3, "e os valores viraram fatos utilizaveis",
               [i.valor for i in meta.fatos("amounts")])
        checar(all(i.source.version_id == meta.version_id for i in meta.amounts),
               "cada fato aponta para a versao de onde veio")
        checar(not esquema.problemas(meta.to_dict()), "o metadata gravado e valido",
               esquema.problemas(meta.to_dict()))

        segunda = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                            paginas=2, sha1="sha-teste")
        checar(segunda.rodadas == [], "analisar de novo nao refaz o que ja estava bom", segunda.rodadas)

        # Trocar o extrator de uma secao envelhece SO aquela secao.
        biblioteca.envelhecer("dates", "extractor_version_changed")
        terceira = portas.analisar_documento(biblioteca, catalogo, arquivo, texto=PECA,
                                             paginas=2, sha1="sha-teste")
        checar(terceira.rodadas == ["dates"], "so a secao envelhecida e reprocessada", terceira.rodadas)
        checar(terceira.metadata.secao("amounts").status == "ok",
               "e as outras continuam como estavam")

        # Extrator que quebra nao derruba a ingestao: a secao fica `failed` e o
        # roteador trata como inexistente.
        quebrado = Catalogo.carregar()
        quebrado.extratores["date-parser/v1"].modulo = "modulo_que_nao_existe"
        biblioteca.envelhecer("dates", "teste")
        ruim = portas.analisar_documento(biblioteca, quebrado, arquivo, texto=PECA, paginas=2)
        checar("dates" in ruim.falhas, "extrator quebrado vira falha declarada", ruim.falhas)
        checar(ruim.metadata.secao("dates").status == "failed" and ruim.metadata.fatos("dates") == [],
               "e secao falhada nao produz fato nenhum")
        bd.fechar()


def main() -> int:
    print("=" * 55)
    print("  PAULUS - extratores de regra (passo 2)")
    print("=" * 55)
    test_digito_do_processo()
    test_datas_e_valores()
    test_referencias_de_lei()
    test_analise_inteira()

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
