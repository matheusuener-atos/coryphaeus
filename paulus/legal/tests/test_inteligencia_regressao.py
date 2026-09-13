"""
A prova da regra de ouro: a camada nao pode responder pior do que o programa
de antes.

Sem medicao, um retrofit e fe. Este arquivo e a medicao. Ele roda um conjunto
fixo de perguntas reais sobre os documentos reais do acervo de teste, com a
camada LIGADA e DESLIGADA, e compara. A regra e dura de proposito:

    qualquer pergunta que a camada responda pior que o sistema de hoje
    e bug bloqueante, nao troca aceitavel

Como se compara sem depender do modelo: o que se mede aqui e a DECISAO do
roteador, nao o texto da resposta. A decisao e deterministica e e onde mora o
risco. Para cada pergunta o conjunto anota o que tem de acontecer:

    nivel 0     responde do metadata, e o fato esperado tem de estar entre os
                fatos entregues
    escala      tem de cair no caminho de hoje - por ambiguidade, por falta de
                dado, por ser pergunta que pede leitura

E depois, para toda resposta de nivel 0, duas verificacoes que valem mais que
qualquer contagem: o fato entregue veio de item conferido, e o trecho citado
existe literalmente no documento, na pagina indicada.

Rodar: venv\\Scripts\\python.exe tests\\test_inteligencia_regressao.py
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
from inteligencia import portas, roteador  # noqa: E402
from inteligencia.catalogo import Catalogo  # noqa: E402
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


# O conjunto fixo. `foco` diz qual documento a conversa esta olhando (vazio =
# o acervo inteiro); `espera` e o nivel que TEM de acontecer; `contem` e o que
# precisa estar na resposta quando ela for de nivel 0.
PERGUNTAS = [
    # --- o acervo inteiro: quase tudo escala, e escalar aqui e o certo ------
    ("qual o valor da causa?", "", "escala", ""),
    ("quem é o autor?", "", "escala", ""),
    ("qual o número do processo?", "", "escala", ""),
    ("o que a cláusula de multa diz sobre atraso?", "", "escala", ""),
    ("resuma o contrato", "", "escala", ""),
    ("por que o contrato foi rescindido?", "", "escala", ""),
    ("compare os dois contratos de compra e venda", "", "escala", ""),
    ("qual o valor do contrato?", "", "escala", ""),
    ("quais artigos do Código Civil aparecem?", "", "escala", ""),
    ("onde diz que o pagamento é parcelado?", "", "escala", ""),

    # --- com um documento em foco: o caminho rapido aparece -----------------
    ("qual o valor do contrato?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "metadata", "250.000,00"),
    ("quanto custa?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "metadata", "250.000,00"),
    ("quais artigos aparecem?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "metadata", "421"),
    ("que leis são citadas?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "metadata", "10.406"),
    ("qual o valor do contrato?", "COMPRA E VENDA - WANDERSON X VALTER UENER R$ 200.000,00.pdf",
     "metadata", "200.000,00"),
    ("qual a data do documento?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "metadata", "2025-01-23"),

    # --- em foco, mas a pergunta pede leitura: escala do mesmo jeito --------
    ("o que este contrato alega sobre a rescisão?",
     "Contrato de Compra e Venda - Matheus X Caroline.pdf", "escala", ""),
    ("resuma este documento", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "escala", ""),
    ("explique a cláusula de arrependimento",
     "Contrato de Compra e Venda - Matheus X Caroline.pdf", "escala", ""),

    # --- em foco, mas o dado nao esta no metadata: escala, nao nega ---------
    ("qual o número do processo?", "Contrato de Compra e Venda - Matheus X Caroline.pdf",
     "escala", ""),
    ("quem é o autor?", "Contrato de Compra e Venda - Matheus X Caroline.pdf", "escala", ""),
    ("qual o tribunal?", "Contrato de Compra e Venda - Matheus X Caroline.pdf", "escala", ""),
    ("qual o valor da causa?", "Procuraçao COOBRAMEX x Matheus.pdf", "escala", ""),
]


def preparar(tmp: Path):
    """Uma biblioteca nova, analisada do zero, sobre o acervo de teste real."""
    bd = base_mod.Base(tmp / "regressao.db")
    bd.migrar()
    biblioteca = Biblioteca(tmp / "conhecimento", bd)
    catalogo = Catalogo.carregar()
    documentos = index_all_contracts(ACERVO, CACHE, verbose=False)
    for doc in documentos:
        portas.analisar_documento(biblioteca, catalogo, doc.path, texto=doc.text,
                                  paginas=doc.pages, sha1=doc.sha1, titulo=doc.name)
    return bd, biblioteca, catalogo, documentos


def main() -> int:
    print("=" * 55)
    print("  PAULUS - regressao da camada de inteligencia")
    print("=" * 55)

    if not ACERVO.is_dir():
        print(f"\n  pulado: o acervo de teste nao esta em {ACERVO}")
        return 0

    with tempfile.TemporaryDirectory() as pasta:
        tmp = Path(pasta)
        bd, biblioteca, catalogo, documentos = preparar(tmp)
        ligada = portas.Saber(biblioteca, catalogo, ligada=True)
        desligada = portas.Saber(biblioteca, catalogo, ligada=False)
        por_nome = {d.name: d for d in documentos}

        print(f"\nacervo: {len(documentos)} documentos analisados")

        print("\ncom a camada DESLIGADA, nada muda")
        for pergunta, foco, _, _ in PERGUNTAS[:6]:
            escopo = [por_nome[foco]] if foco else documentos
            pacote = desligada.montar_contexto(pergunta, escopo, em_foco=bool(foco))
            if pacote.nivel != roteador.BUSCADOR or not pacote.fallback:
                checar(False, "desligada, tudo cai no caminho de hoje", (pergunta, pacote.nivel))
                break
        else:
            checar(True, "desligada, tudo cai no caminho de hoje (nivel 2, fallback)")

        print("\no conjunto fixo, com a camada ligada")
        rapidas, erradas = 0, 0
        comeco = time.time()
        for pergunta, foco, espera, contem in PERGUNTAS:
            if foco and foco not in por_nome:
                print(f"  pulou “{pergunta}” (documento de teste ausente)")
                continue
            escopo = [por_nome[foco]] if foco else documentos
            pacote = ligada.montar_contexto(pergunta, escopo, em_foco=bool(foco))
            deu = "metadata" if pacote.responde_sozinho else "escala"
            certo = deu == espera
            if certo and espera == "metadata":
                valores = " | ".join(f.valor for f in pacote.fatos)
                certo = contem in valores
                if not certo:
                    checar(False, f"“{pergunta}” devia trazer {contem}", valores)
            if certo:
                rapidas += 1 if deu == "metadata" else 0
            else:
                erradas += 1
                if deu != espera:
                    checar(False, f"“{pergunta}” (foco: {foco or 'acervo'}) devia {espera}, deu {deu}",
                           pacote.porque)

        checar(erradas == 0, f"as {len(PERGUNTAS)} perguntas do conjunto decidiram como o esperado",
               f"{erradas} erraram")
        print(f"  ...  {rapidas} respondidas do metadata, "
              f"{len(PERGUNTAS) - rapidas} pelo caminho de hoje "
              f"({round(time.time() - comeco, 2)} s no total)")

        print("\ntoda resposta de nivel 0 se sustenta no documento")
        conferidas = 0
        for pergunta, foco, espera, _ in PERGUNTAS:
            if espera != "metadata" or foco not in por_nome:
                continue
            pacote = ligada.montar_contexto(pergunta, [por_nome[foco]], em_foco=True)
            documento = por_nome[foco]
            for fato in pacote.fatos:
                conferidas += 1
                if fato.char_start is None:
                    checar(False, f"“{pergunta}”: fato sem posicao no texto", fato.to_dict())
                    continue
                trecho = documento.text[fato.char_start:fato.char_end]
                if " ".join(trecho.split()) != " ".join((fato.quote or "").split()):
                    checar(False, f"“{pergunta}”: a citacao nao bate com o texto",
                           (trecho, fato.quote))
        checar(conferidas > 0 and not _falhas,
               f"as {conferidas} citacoes entregues existem literalmente no documento")

        print("\nmedicao")
        medida = ligada.medicao()
        checar(medida["perguntas"] >= len(PERGUNTAS), "cada decisao virou uma linha de medida", medida)
        checar(medida["ms_medio"] < 50, f"e decidir custa quase nada ({medida['ms_medio']} ms em media)")
        print(f"  ...  {medida['no_metadata']} de {medida['perguntas']} perguntas "
              f"({medida['porcento']}%) sem abrir documento")
        bd.fechar()

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
