"""
Testes das verificações por regra na resposta sobre documentos (src/verificacao.py).

  - "quem é o advogado de X?": sem ligação escrita entre advogado e X, a
    resposta sai por regra; com ligação (outorgante, contratante de
    honorários, "representada por"), a pergunta segue para o modelo;
  - a ligação é pela estrutura, e não pela proximidade: o "outorgante" de
    outra parte na frase seguinte não conta;
  - em pergunta de consequência, a frase do documento que decide vai
    literal embaixo da resposta - só quando traz o que a resposta omitiu.

Sem Ollama.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_verificacao_resposta.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import verificacao  # noqa: E402
from search import Chunk, Hit  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PROCURACAO = NS(name="Procuração - Alfa.docx", text=(
    "PROCURAÇÃO AD JUDICIA. OUTORGANTE: ALFA AGRO LTDA., CNPJ 00.000.000/0001-00. "
    "OUTORGADA: MARIA SOUZA, advogada, OAB/PA 1.234. PODERES: negociar e transigir, em especial nas "
    "questões do contrato com a Beta Transportes Ltda. Não estão incluídos os poderes para renunciar a créditos "
    "da OUTORGANTE."))
CONTRATO = NS(name="Contrato - Alfa x Beta.docx", text=(
    "CONTRATANTE: ALFA AGRO LTDA. CONTRATADA: BETA TRANSPORTES LTDA. Cláusula 5ª - Da rescisão. "
    "Qualquer das partes pode rescindir o contrato sem motivo, com aviso prévio de 30 (trinta) dias. "
    "Quem rescindir pagará multa de 10% (dez por cento) sobre as parcelas restantes."))
HONORARIOS = NS(name="Contrato de honorários - Carlos Lima.docx", text=(
    "CONTRATO DE HONORÁRIOS ADVOCATÍCIOS. CONTRATANTE: CARLOS LIMA, CPF 000. CONTRATADA: Souza Advocacia, "
    "por sua sócia Maria Souza."))
PETICAO = NS(name="Petição - Gama.docx", text=(
    "GAMA COMÉRCIO LTDA., representada por seus advogados que esta subscrevem, vem propor a ação."))
DOCS = [PROCURACAO, CONTRATO, HONORARIOS, PETICAO]


def test_papel() -> None:
    print("\nquem é o advogado de X")
    r = verificacao.papel_sem_prova("quem é o advogado da Beta Transportes?", DOCS)
    checar(r.startswith("Nenhum documento") and "Beta Transportes" in r,
           "a Beta aparece, mas ninguém a representa: responde por regra", r)
    checar(verificacao.papel_sem_prova("quem é a advogada da Alfa Agro?", DOCS) == "",
           "OUTORGANTE: Alfa - segue para o modelo")
    checar(verificacao.papel_sem_prova("quem é o advogado do Carlos Lima?", DOCS) == "",
           "contratante de honorários advocatícios é cliente - segue para o modelo")
    checar(verificacao.papel_sem_prova("quem é o advogado da Gama Comércio?", DOCS) == "",
           "'representada por seus advogados' - segue para o modelo")
    checar(verificacao.papel_sem_prova("quem é o advogado da Delta?", DOCS) == "",
           "parte que nem aparece: o caminho de sempre diz que não achou")
    checar(verificacao.papel_sem_prova("qual o valor do contrato?", DOCS) == "", "pergunta que não é de papel: nada")


def test_trecho() -> None:
    print("\na frase que decide, literal, quando a resposta omite")
    hits = [Hit(Chunk(d.name, "", 0, d.text), 1.0, "") for d in DOCS]
    r = verificacao.trecho_decisivo("quanto custa rescindir o contrato sem motivo?",
                                    "A multa é de 10% sobre as parcelas restantes.", hits)
    checar("30 (trinta) dias" in r and r.strip().startswith("No documento"), "o aviso de 30 dias que faltou vem literal", r)
    r = verificacao.trecho_decisivo("quanto custa rescindir o contrato sem motivo?",
                                    "Com aviso prévio de 30 dias e multa de 10%.", hits)
    checar(r == "", "a resposta já trouxe tudo: nada é acrescentado", r)
    checar(verificacao.trecho_decisivo("qual o foro?", "Belém", hits) == "", "pergunta que não é de consequência: nada")


def main() -> int:
    print("=" * 55)
    print("  verificação por regra na resposta sobre documentos")
    print("=" * 55)
    test_papel()
    test_trecho()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
