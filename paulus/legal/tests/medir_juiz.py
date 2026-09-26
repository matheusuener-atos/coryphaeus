"""
Medição do juiz da camada do programa com o modelo de verdade.

Não é teste de regressão (esse é test_programa.py, que não precisa do
Ollama): é a régua que escolheu o LIMIAR de programa.py. Cada frase aqui
chega ao juiz - a regra sozinha não decide - e tem a resposta certa anotada.
As frases misturam palavra de tela ("reunião", "recebi", "aprovação") com
âncora de documento ("contrato", "processo"), que é exatamente onde a regra
para e o modelo escolhe.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/medir_juiz.py

Imprime, por frase, o que o modelo escolheu, com que probabilidade e em
quanto tempo; no fim, a acurácia em cada limiar.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import juizo  # noqa: E402
import programa  # noqa: E402

# (frase, respostas aceitas). "documentos" = seguir para a busca.
CASOS = [
    ("quais compromissos o contrato prevê?", {"documentos"}),
    ("a procuração tem alguma audiência marcada?", {"documentos"}),
    ("qual o saldo devedor previsto no contrato?", {"documentos"}),
    ("quais reuniões estão previstas no aditivo?", {"documentos"}),
    ("meus clientes têm contrato vencendo?", {"documentos"}),
    ("qual a multa se eu atrasar o pagamento das contas a pagar do contrato?", {"documentos"}),
    ("o que tenho a receber da Cooperativa segundo o contrato?", {"documentos"}),
    ("o contrato marca reunião de diretoria?", {"documentos"}),
    ("qual o faturamento previsto no contrato de prestação?", {"documentos"}),
    ("quais pendências o parecer aponta?", {"documentos"}),
    ("a sentença menciona despesas processuais?", {"documentos"}),
    ("qual a data da audiência na petição?", {"documentos"}),
    ("quantos clientes o contrato menciona?", {"documentos"}),
    ("o réu pagou as despesas do processo?", {"documentos"}),
    ("quanto recebi do contrato da Cooperativa este mês?", {"consulta:financeiro", "documentos"}),
    ("quanto paguei de despesas com o processo?", {"consulta:financeiro", "documentos"}),
    ("quais tarefas eu tenho para o processo da Maria?", {"consulta:tarefas"}),
    ("tem alguma audiência marcada na agenda para o processo 123?", {"consulta:calendario"}),
    ("tenho reunião com o autor do processo?", {"consulta:calendario"}),
    ("quais audiências do processo estão na minha agenda?", {"consulta:calendario"}),
    ("tem aprovação pendente para o contrato da Cooperativa?", {"consulta:aprovacoes"}),
    ("onde vejo os prazos dos contratos?", {"como:biblioteca", "como:tarefas"}),
    ("como faço para imprimir o contrato?", {"como:editor"}),
    ("como anexo o contrato no e-mail?", {"como:caixa"}),
]


class DadosFalsos:
    """A consulta precisa responder algo; aqui só importa para onde foi."""

    class _Vazio:
        def __getattr__(self, _):
            return lambda *a, **k: []

    agenda = tarefas = _Vazio()

    class financeiro:  # noqa: N801
        @staticmethod
        def painel(mes=""):
            return {"tem_dado": False}

    class fila:  # noqa: N801
        pendentes: list = []

    class cadastros:  # noqa: N801
        @staticmethod
        def contagem():
            return {}


def main() -> int:
    juiz = juizo.Juiz(timeout=120, num_ctx=8192)
    linhas = []
    for frase, aceitas in CASOS:
        visto: dict = {}

        class Espiao:
            def escolher(self, instrucao, opcoes, estado=None, entrada="", trocar_ordem=False):
                comeco = time.time()
                e = juiz.escolher(instrucao, opcoes, estado=estado, entrada=entrada, trocar_ordem=trocar_ordem)
                visto.update(e=e, opcoes=opcoes, segundos=time.time() - comeco)
                return e

        # Limiar zero: queremos ver a escolha crua; o limiar é aplicado depois.
        guardado = programa.LIMIAR
        programa.LIMIAR = 0.0
        try:
            leitura = programa.ler(frase, dados=DadosFalsos(), juiz=Espiao())
        finally:
            programa.LIMIAR = guardado
        e = visto.get("e")
        if not visto:
            # A regra decidiu sozinha: entra na conta como certeza.
            alvo = f"{leitura.tipo}:{leitura.destino}" if leitura else "documentos"
            linhas.append((frase, aceitas, alvo, 1.0 if leitura else 0.0, 0.0))
            marca = "ok " if alvo in aceitas else "ERR"
            print(f"  {marca} regra              {alvo:20} {frase}")
            continue
        if e is None:
            print(f"  SEM RESPOSTA do modelo: {frase}")
            continue
        # A leitura com limiar zero sempre existe; o "programa" dela vale p.
        p = e.probabilidades.get("programa", 0.0)
        alvo = f"{leitura.tipo}:{leitura.destino}" if leitura else "?"
        escolhido = alvo if p >= 0.5 else "documentos"
        linhas.append((frase, aceitas, alvo, p, visto["segundos"]))
        marca = "ok " if escolhido in aceitas else "ERR"
        print(f"  {marca} p(programa)={p:.2f} {visto['segundos']:5.1f}s  {alvo:20} {frase}")

    if not linhas:
        print("nenhuma medida: o Ollama respondeu?")
        return 1
    print()
    tempos = sorted(x[4] for x in linhas)
    print(f"tempo por julgamento: mediana {tempos[len(tempos) // 2]:.1f} s, máximo {tempos[-1]:.1f} s")
    for limiar in (0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9):
        certos = 0
        desviados_errado = 0
        for frase, aceitas, alvo, p, _ in linhas:
            final = alvo if p >= max(limiar, 1e-9) else "documentos"
            certos += final in aceitas
            desviados_errado += final != "documentos" and final not in aceitas
        print(f"limiar {limiar:.2f}: {certos}/{len(linhas)} certos, "
              f"{desviados_errado} tirados dos documentos por engano")
    return 0


if __name__ == "__main__":
    sys.exit(main())
