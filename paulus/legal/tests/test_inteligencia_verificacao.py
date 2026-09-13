"""
A conferencia da citacao: a barreira que separa fato de frase bem escrita.

Esta e a peca mais importante da camada, e por isso a mais testada. A regra
que ela impoe: o que o modelo afirma so vira fato se a citacao dele existir no
documento. O que nao casa fica marcado, sobrevive no metadata para ser contado
- e nao pode ser apresentado como fato.

Os dois erros opostos importam igualmente:

  - reprovar citacao correta e perder um fato verdadeiro. O modelo junta
    espacos, perde acento, desfaz a quebra de linha e nao repete o hifen da
    palavra partida - nada disso muda o que esta escrito
  - aprovar citacao errada e o proprio desastre que a camada existe para
    evitar. E o caso perigoso nao e a frase inventada do zero, que qualquer
    comparacao pega: e a frase CERTA com o numero TROCADO

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia_verificacao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from inteligencia import alinhar  # noqa: E402
from inteligencia.esquema import Fonte, Item  # noqa: E402
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


DOC = (
    "[pagina 1]\n"
    "COOPERATIVA BRASILEIRA LTDA., pessoa jurídica de direito privado, inscrita no CNPJ\n"
    "sob o nº 11.222.333/0001-81, doravante CONTRA-\n"
    "TANTE, neste ato representada por seu presidente.\n\n"
    "[pagina 2]\n"
    "CLÁUSULA QUARTA — Os honorários são de R$ 15.000,00, pagos em doze parcelas iguais.\n"
    "O prazo de aviso de não renovação é de 90 (noventa) dias, nos termos da cláusula sexta.\n"
)
PAGINAS = mapa_de_paginas(DOC)


def test_aceita_o_que_e_a_mesma_citacao() -> None:
    print("\naceita a citacao correta escrita de outro jeito")
    casos = [
        ("COOPERATIVA BRASILEIRA LTDA., pessoa jurídica de direito privado", "igual ao documento"),
        ("COOPERATIVA BRASILEIRA LTDA., pessoa juridica de direito privado", "sem os acentos"),
        ("cooperativa brasileira ltda., pessoa jurídica de direito privado", "em caixa baixa"),
        ("doravante CONTRATANTE, neste ato representada", "com a palavra que estava partida na linha"),
        ("CLÁUSULA QUARTA - Os honorários são de R$ 15.000,00", "com hifen no lugar do travessao"),
        ("Os honorarios   sao de R$ 15.000,00,  pagos em doze parcelas", "com espacos sobrando"),
    ]
    for citacao, rotulo in casos:
        r = alinhar.conferir(DOC, citacao, PAGINAS)
        checar(r.achou, f"aceita {rotulo}", r.motivo)
        if r.achou:
            checar(DOC[r.char_start:r.char_end].strip() != "",
                   f"   e o span aponta para o texto de verdade ({rotulo})")

    r = alinhar.conferir(DOC, "Os honorários são de R$ 15.000,00, pagos em doze parcelas", PAGINAS)
    checar(r.pagina == 2, "a pagina sai do mapa de layout", r.to_dict())
    checar("15.000,00" in r.trecho, "e o trecho devolvido e o do documento, com acento e pontuacao", r.trecho)


def test_reprova_o_que_nao_esta_la() -> None:
    print("\nreprova o que o documento nao diz")
    inventada = alinhar.conferir(DOC, "O autor é João da Silva, conforme fls. 3 dos autos", PAGINAS)
    checar(not inventada.achou, "frase inventada do zero nao passa", inventada.to_dict())
    checar("não está no documento" in inventada.motivo, "e o motivo diz isso em portugues", inventada.motivo)

    # O caso perigoso: a frase certa com o numero trocado. A semelhanca e
    # altissima - um zero a mais em quinze mil da 98% - e a resposta estaria
    # errada por dez vezes.
    for citacao, rotulo in (
        ("Os honorários são de R$ 150.000,00, pagos em doze parcelas", "valor com um zero a mais"),
        ("Os honorários são de R$ 15.000,00, pagos em dez parcelas", "quantidade de parcelas trocada"),
        ("O prazo de aviso de não renovação é de 30 (trinta) dias", "prazo trocado"),
        ("inscrita no CNPJ sob o nº 11.222.333/0001-82", "digito do CNPJ trocado"),
    ):
        r = alinhar.conferir(DOC, citacao, PAGINAS)
        checar(not r.achou, f"reprova {rotulo}", r.to_dict())

    curta = alinhar.conferir(DOC, "o nº", PAGINAS)
    checar(not curta.achou and "curta" in curta.motivo,
           "citacao curta demais nao prova nada", curta.motivo)
    checar(not alinhar.conferir("", "qualquer coisa", PAGINAS).achou, "documento sem texto nao confirma nada")
    checar(not alinhar.conferir(DOC, "", PAGINAS).achou, "e citacao vazia tambem nao")


def test_o_item_sai_marcado() -> None:
    print("\no item volta com o veredito escrito")
    bom = Item(id="party_001", dados={"name": "Cooperativa Brasileira Ltda.", "role": "contratante"},
               quote="COOPERATIVA BRASILEIRA LTDA., pessoa juridica de direito privado",
               certainty="explicit", produced_by="teste/v1")
    ruim = Item(id="party_002", dados={"name": "João da Silva", "role": "réu"},
                quote="o réu João da Silva, brasileiro, casado, conforme fls. 3",
                certainty="explicit", produced_by="teste/v1")

    conferidos, quantos = alinhar.verificar_todos([bom, ruim], DOC, "ver_teste", PAGINAS)
    checar(quantos == 1, "um dos dois nao passou", quantos)

    checar(conferidos[0].verified and conferidos[0].pode_virar_fato,
           "o conferido pode virar fato", conferidos[0].to_dict())
    checar(conferidos[0].source.page == 1 and conferidos[0].source.version_id == "ver_teste",
           "com pagina e versao na fonte", conferidos[0].source.to_dict())
    checar("jurídica" in conferidos[0].quote,
           "e a citacao gravada passa a ser a do documento, nao a que o modelo escreveu",
           conferidos[0].quote)

    checar(not conferidos[1].verified, "o reprovado fica marcado")
    checar(conferidos[1].certainty == "inferred",
           "e cai de explicito para deduzido - deixa de ser 'esta escrito'", conferidos[1].certainty)
    checar(not conferidos[1].pode_virar_fato, "e nao pode ser apresentado como fato")
    checar(conferidos[1].dados.get("verification_note"),
           "o motivo fica guardado, para contar alucinacao por extrator",
           conferidos[1].dados)


def test_nao_apaga_o_reprovado() -> None:
    """Descartar esconderia do log que o extrator alucinou."""
    print("\no reprovado sobrevive, marcado")
    itens = [Item(id=f"x_{i}", dados={"name": f"Nome {i}"}, quote="nao esta escrito em lugar nenhum disto",
                  certainty="explicit", produced_by="teste/v1") for i in range(3)]
    conferidos, quantos = alinhar.verificar_todos(itens, DOC, "ver_teste", PAGINAS)
    checar(len(conferidos) == 3 and quantos == 3, "os tres continuam na lista, todos marcados", quantos)
    checar(all(not i.verified for i in conferidos), "nenhum passou")


def test_documento_grande_nao_trava() -> None:
    """Um processo de centenas de paginas nao pode fazer a conferencia rastejar."""
    print("\ntamanho: a conferencia continua barata")
    import time

    grande = (DOC + "\n" + "Texto de enchimento para simular um processo longo. " * 400) * 6
    citacao = "O prazo de aviso de não renovação é de 90 (noventa) dias"
    comeco = time.time()
    r = alinhar.conferir(grande, citacao, mapa_de_paginas(grande))
    demorou = time.time() - comeco
    checar(r.achou, "acha a citacao no documento grande", r.motivo)
    checar(demorou < 1.5, f"e em menos de 1,5 s ({demorou:.2f} s, {len(grande):,} caracteres)")

    comeco = time.time()
    ruim = alinhar.conferir(grande, "uma frase que nao existe neste documento nenhuma vez", mapa_de_paginas(grande))
    checar(not ruim.achou and (time.time() - comeco) < 1.5,
           "e reprovar o que nao existe tambem e rapido")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - verificacao de citacao (passo 3)")
    print("=" * 55)
    test_aceita_o_que_e_a_mesma_citacao()
    test_reprova_o_que_nao_esta_la()
    test_o_item_sai_marcado()
    test_nao_apaga_o_reprovado()
    test_documento_grande_nao_trava()

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
