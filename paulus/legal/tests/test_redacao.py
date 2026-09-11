"""
Testes das ferramentas de redigir contrato.

Renumerar mexe no documento inteiro de uma vez, e é a operação com maior
potencial de estrago silencioso desta tela: um número trocado onde não devia
muda o que o contrato diz. Então os testes perseguem, nesta ordem:

  - contrato já em ordem sai BYTE A BYTE igual — o que não precisa mudar, não muda
  - referência ("conforme cláusula 4") não é confundida com título de cláusula
  - renumerar leva as referências junto: é a metade que costuma ficar para trás
  - o estilo do documento é respeitado — renumerar não é reformatar
  - a qualificação não inventa dado que o cadastro não tem

Os estilos testados saíram dos contratos reais deste escritório: "1ª CLAUSULA –"
e "CLÁUSULA 1ª –", com e sem acento, hífen ou travessão, espaço duplo.

    python tests/test_redacao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import redacao  # noqa: E402
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


def test_acha_os_estilos_reais() -> None:
    print("\nos estilos que aparecem de verdade")
    casos = [
        ("1ª CLAUSULA – Do objeto.", "antes", 1),
        ("2ª CLAUSULA - Do preço.", "antes", 2),
        ("6ª CLAUSULA  – Espaço duplo.", "antes", 6),
        ("CLÁUSULA 1ª – OBJETO DO CONTRATO:", "depois", 1),
        ("CLAUSULA 12 - Sem ordinal.", "depois", 12),
        ("CLÁUSULA PRIMEIRA - por extenso", "extenso", 1),
        ("Cláusula Décima Segunda", "extenso", 12),
    ]
    for texto, estilo, numero in casos:
        achadas = redacao.achar_clausulas(texto)
        ok = achadas and achadas[0]["estilo"] == estilo and achadas[0]["numero"] == numero
        checar(bool(ok), f"“{texto[:34]}” → {estilo} {numero}",
               str(achadas[:1]))

    checar(redacao.achar_clausulas("um texto sem cláusula nenhuma") == [],
           "texto sem cláusula não inventa uma")


def test_referencia_nao_e_titulo() -> None:
    """
    "conforme cláusula 2" no meio da frase não é uma cláusula.

    Sem essa distinção, renumerar reescrevia a referência como se fosse título
    e a cláusula seguinte saía com o número errado — aconteceu, e o contrato
    ficou com 1, 2, 3, 4 e 6.
    """
    print("\nreferência no meio da frase não é título")
    texto = ("1ª CLAUSULA – Do objeto.\n"
             "2ª CLAUSULA – Da posse, conforme cláusula 1 deste instrumento.\n"
             "3ª CLAUSULA – Do foro, nos termos da cláusula 2.")

    achadas = redacao.achar_clausulas(texto)
    checar(len(achadas) == 3, f"acha 3 cláusulas, não 5 (achou {len(achadas)})",
           str([a["texto"] for a in achadas]))
    checar([a["numero"] for a in achadas] == [1, 2, 3], "com os números certos")

    refs = redacao.referencias(texto)
    checar(len(refs) == 2, f"e 2 referências cruzadas (achou {len(refs)})")
    checar(all(r["existe"] for r in refs), "as duas apontam para cláusula que existe")

    # No HTML do editor os blocos são <p>: a marca abre o bloco depois do ">".
    html = "<p>1ª CLAUSULA – a.</p><p>2ª CLAUSULA – b, conforme cláusula 1.</p>"
    checar(len(redacao.achar_clausulas(html)) == 2, "o mesmo vale no HTML do editor")
    checar(len(redacao.referencias(html)) == 1, "e a referência continua sendo referência")


def test_o_que_esta_em_ordem_nao_muda() -> None:
    """
    A propriedade que mais importa: não mexer no que está certo.

    Um contrato já numerado tem que sair idêntico. Qualquer diferença aqui é
    o programa reescrevendo documento assinado por conta própria.
    """
    print("\ncontrato em ordem sai igual")
    if not CONTRATOS.exists():
        print("  pulado: pasta de contratos não existe")
        return

    docs = index_all_contracts(CONTRATOS, verbose=False)
    com_clausula = [d for d in docs if redacao.achar_clausulas(d.text)]
    checar(bool(com_clausula), f"há contratos com cláusula para testar ({len(com_clausula)})")

    for d in com_clausula:
        r = redacao.renumerar(d.text)
        checar(r["texto"] == d.text,
               f"{d.name[:38]}: {r['clausulas']} cláusulas, texto intacto",
               f"{len(r['trocas'])} trocas indevidas: {r['trocas'][:2]}")


def test_renumerar_leva_as_referencias() -> None:
    """
    Renumerar sem mexer nas referências é metade do trabalho.

    E a metade que sobra é a que dá problema: a cláusula 7 que cita "a
    cláusula 4" depois que a 4 virou 5.
    """
    print("\nrenumerar leva as referências junto")
    # Duas cláusulas "2" — foi inserida uma no meio.
    texto = ("1ª CLAUSULA – Do objeto.\n"
             "2ª CLAUSULA – Da forma de pagamento.\n"
             "2ª CLAUSULA – Do preço.\n"
             "3ª CLÁUSULA – Da posse, conforme cláusula 2 deste instrumento.\n"
             "4ª CLAUSULA  – Do foro, nos termos da cláusula 3.")

    r = redacao.renumerar(texto)
    numeros = [a["numero"] for a in redacao.achar_clausulas(r["texto"])]
    checar(numeros == [1, 2, 3, 4, 5], f"as cláusulas ficam em sequência ({numeros})")

    refs = [x["texto"] for x in redacao.referencias(r["texto"])]
    checar("cláusula 3" in refs, f"a referência à 2 vira 3 ({refs})")
    checar("cláusula 4" in refs, "e a referência à 3 vira 4")
    checar(all(x["existe"] for x in redacao.referencias(r["texto"])),
           "nenhuma referência fica apontando para o nada")

    tipos = {t["tipo"] for t in r["trocas"]}
    checar(tipos == {"clausula", "referencia"}, f"a lista diz o tipo de cada troca ({tipos})")
    checar(len(r["referencias"]) == 2, "e separa as referências, para a tela avisar")

    # Sem seguir: o pedido é explícito, e o resultado também.
    sem = redacao.renumerar(texto, seguir_referencias=False)
    checar(all(t["tipo"] == "clausula" for t in sem["trocas"]),
           "com seguir_referencias=False, só as cláusulas mudam")


def test_o_estilo_do_documento_manda() -> None:
    """Renumerar não é reformatar: muda o número, e só ele."""
    print("\no estilo do documento é respeitado")

    sem_acento = "3ª CLAUSULA – a.\n5ª CLAUSULA – b."
    r = redacao.renumerar(sem_acento)
    checar("CLAUSULA" in r["texto"] and "CLÁUSULA" not in r["texto"],
           "sem acento continua sem acento")
    checar("1ª" in r["texto"] and "2ª" in r["texto"], "e os números entram em sequência")

    depois = "CLÁUSULA 4ª – OBJETO:\nCLÁUSULA 9ª – FORO:"
    d = redacao.renumerar(depois)
    checar(d["texto"].startswith("CLÁUSULA 1ª"), f"“CLÁUSULA Nª” mantém a forma ({d['texto'][:18]})")

    travessao = "2ª CLAUSULA  – espaço duplo antes do travessão."
    checar("  –" in redacao.renumerar(travessao)["texto"],
           "espaço duplo e travessão ficam como estavam")

    extenso = "CLÁUSULA PRIMEIRA - a.\nCLÁUSULA PRIMEIRA - b."
    e = redacao.renumerar(extenso)
    checar("SEGUNDA" in e["texto"], f"por extenso vira por extenso ({e['texto'][-24:]})")

    titulo = "Cláusula Primeira - a.\nCláusula Primeira - b."
    checar("Segunda" in redacao.renumerar(titulo)["texto"],
           "e a caixa do documento é mantida")


def test_referencia_quebrada() -> None:
    print("\nreferência apontando para o nada")
    texto = "<p>1ª CLAUSULA – a.</p><p>2ª CLAUSULA – b, conforme cláusula 12.</p>"
    quebradas = redacao.referencias_quebradas(texto)
    checar(len(quebradas) == 1, f"acha a referência impossível ({len(quebradas)})")
    checar(quebradas[0]["numero"] == 12, "dizendo qual número não existe")

    inteiro = "<p>1ª CLAUSULA – a.</p><p>2ª CLAUSULA – b, conforme cláusula 1.</p>"
    checar(redacao.referencias_quebradas(inteiro) == [],
           "e não reclama do que está certo")


def test_qualificacao() -> None:
    """O que o cadastro não tem vira lacuna — nunca invenção."""
    print("\nqualificação das partes")

    juridica = redacao.qualificar({
        "nome": "Cooperativa Brasileira de Mineradores",
        "documento": "31.984.284/0001-21",
        "endereco": "Av. Rio Xingu, 1995",
    })
    checar("CNPJ" in juridica, "CNPJ de 14 dígitos vira pessoa jurídica")
    checar("pessoa jurídica" in juridica, "e é qualificada como tal")
    checar("COOPERATIVA BRASILEIRA" in juridica, "com o nome em caixa alta")
    checar("[" not in juridica, f"sem lacuna quando o cadastro tem tudo ({juridica[-40:]})")

    fisica = redacao.qualificar({"nome": "Matheus Uener Silva",
                                 "documento": "103.253.656-01",
                                 "endereco": "Rua Aureliano Chaves, 600"})
    checar("CPF" in fisica, "CPF de 11 dígitos vira pessoa física")
    checar("[ESTADO CIVIL]" in fisica and "[PROFISSÃO]" in fisica,
           "o que o cadastro não guarda vira lacuna visível")

    vazio = redacao.qualificar({"nome": "Sem dados"})
    checar("[CPF]" in vazio and "[ENDEREÇO]" in vazio,
           "cadastro vazio vira lacuna, não invenção")
    checar("Sem dados" in vazio, "mas o nome que existe é usado")

    falta = redacao.o_que_falta({"nome": "Sem dados"})
    checar("CPF ou CNPJ" in falta and "endereço" in falta,
           f"e o que falta sai declarado antes de inserir ({falta})")
    checar(redacao.o_que_falta({"nome": "X", "documento": "31.984.284/0001-21",
                                "endereco": "Rua A"}) == [],
           "cadastro completo de pessoa jurídica não falta nada")


def test_bordas() -> None:
    print("\nborda")
    for vazio in ("", "   ", None):
        r = redacao.renumerar(vazio or "")
        checar(r["clausulas"] == 0, f"texto vazio não quebra ({vazio!r})")
    checar(redacao.referencias("") == [], "referências em texto vazio")
    checar(redacao.estilo_do_documento("") == "", "sem cláusula, sem estilo")
    checar(redacao.qualificar({}).startswith("[NOME]"), "ficha vazia não quebra")


def main() -> int:
    print("=" * 55)
    print("PAULUS - redigir contrato")
    print("=" * 55)

    test_acha_os_estilos_reais()
    test_referencia_nao_e_titulo()
    test_renumerar_leva_as_referencias()
    test_o_estilo_do_documento_manda()
    test_referencia_quebrada()
    test_o_que_esta_em_ordem_nao_muda()
    test_qualificacao()
    test_bordas()

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
