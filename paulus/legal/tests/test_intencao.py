"""
Testes do leitor de intenção da conversa.

Este módulo decide o caminho de TODA mensagem que a pessoa escreve. Errar para
um lado faz o programa procurar "reunião" dentro dos contratos quando pediram
para anotar uma — foi o que acontecia. Errar para o outro é pior: uma pergunta
sobre documentos virando um compromisso no calendário de alguém.

Então os testes cobrem os dois lados:

  - o pedido de ação é reconhecido, com data, hora e aviso
  - a pergunta sobre documentos NÃO vira ação
  - sem data, o compromisso não é marcado para hoje por conta própria
  - data sem ano não cai no passado
  - o título fica legível: "Reunião", não a frase inteira

    python tests/test_intencao.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import intencao  # noqa: E402

# Uma sexta-feira, para os testes de dia da semana não dependerem de quando
# a suíte roda.
HOJE = date(2026, 9, 11)

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def test_o_pedido_que_nao_era_entendido() -> None:
    """A frase exata que fazia o programa procurar nos contratos."""
    print("\no pedido que virava busca nos contratos")
    i = intencao.ler(
        "Anote uma reunião no calendario por favor 11/09/2026 às 13:40 "
        "com lembrete definido 10 minutos antes.", HOJE)

    checar(i.tipo == "agenda", f"vira pedido de agenda, e não busca ({i.tipo})")
    checar(i.campos["data"] == "2026-09-11", f"lê a data ({i.campos.get('data')})")
    checar(i.campos["hora"] == "13:40", f"lê a hora ({i.campos.get('hora')})")
    checar(i.campos["avisar_min"] == 10, f"lê o aviso ({i.campos.get('avisar_min')})")
    checar(i.titulo == "Reunião", f"e o título fica legível ({i.titulo!r})")
    # A explicacao volta com acento: a busca e sem, a tela nao.
    checar("anote" in i.porque and "reunião" in i.porque,
           f"dizendo o que na frase levou a isso ({i.porque})")


def test_nao_vira_acao_o_que_nao_e() -> None:
    """
    O erro caro é o contrário: pergunta virando compromisso.

    Errar aqui mexe na agenda de alguém por causa de uma pergunta. Por isso a
    regra exige duas coisas juntas — um verbo de ação E a palavra que diz o
    que é. Só uma das duas não basta.
    """
    print("\no que NÃO é pedido de ação")
    perguntas = [
        "quais as cláusulas de penalidade dos contratos?",
        "resuma o contrato de compra e venda",
        "tem alguma reunião marcada nos documentos?",
        "o contrato fala em prazo de entrega?",
        "quando vence o contrato da Cooperativa?",
        "qual o valor da tarefa de consultoria?",
        "crie um resumo dos documentos",
        "me mostre o que diz sobre multa",
        # Estes tem o verbo E a coisa, mas o verbo esta na terceira pessoa,
        # depois do sujeito: e pergunta sobre o documento, nao ordem.
        "o contrato marca reuniao de diretoria?",
        "a procuracao registra algum compromisso?",
        "liste os compromissos que o contrato cria para o vendedor",
        "quem colocou esse prazo no contrato?",
        "o contrato preve reuniao trimestral com o cliente",
    ]
    for p in perguntas:
        i = intencao.ler(p, HOJE)
        checar(i.tipo == "documentos", f"“{p[:44]}” continua indo para os documentos",
               f"virou {i.tipo}")


def test_titulo_fica_legivel() -> None:
    """
    O titulo vai para a grade do calendario: a frase inteira nao cabe.

    Gentileza ("por favor", "pode"), muleta ("ai") e a palavra que diz onde
    guardar ("na agenda") sao ruido no titulo. O que sobra e o assunto.
    """
    print("\ntítulo legível")
    casos = [
        ("Anote uma reunião no calendario por favor 11/09/2026 às 13:40 "
         "com lembrete definido 10 minutos antes.", "Reunião"),
        ("pode marcar uma audiência para 25/09?", "Audiência"),
        ("agenda aí uma call com o cliente segunda às 15h", "Call com o cliente"),
        ("anota aí um lembrete: ligar para o cartório", "Ligar para o cartório"),
        ("crie uma tarefa para revisar a procuração", "Revisar a procuração"),
        # Abreviacao nao e pontuacao sobrando: "Dr." continua com o ponto.
        ("anote um compromisso com o Dr. Silva dia 3 às 16h",
         "Compromisso com o Dr. Silva"),
    ]
    for frase, esperado in casos:
        achou = intencao.ler(frase, HOJE).titulo
        checar(achou == esperado, f"“{frase[:38]}…” → “{esperado}”", f"achou {achou!r}")


def test_datas() -> None:
    print("\nas datas do jeito que se escreve")
    def data(frase):
        return intencao.ler("anote uma reunião " + frase, HOJE).campos.get("data", "")

    checar(data("11/09/2026") == "2026-09-11", "dd/mm/aaaa")
    checar(data("11/09/26") == "2026-09-11", "dd/mm/aa")
    checar(data("20 de outubro") == "2026-10-20", "por extenso")
    checar(data("dia 20 de outubro") == "2026-10-20", "com “dia” na frente")
    checar(data("hoje") == "2026-09-11", "hoje")
    checar(data("amanhã") == "2026-09-12", "amanhã")
    checar(data("depois de amanhã") == "2026-09-13", "depois de amanhã")

    # 11/09/2026 é uma sexta. "Na segunda" é a que vem, não a que passou.
    checar(data("na segunda") == "2026-09-14", f"dia da semana vai para a frente ({data('na segunda')})")
    checar(data("na sexta") == "2026-09-18",
           f"e “sexta” numa sexta é a semana que vem ({data('na sexta')})")

    # Sem ano, o ano é o que não joga a data no passado: quem escreve
    # "3 de janeiro" em setembro quer o janeiro que vem.
    checar(data("3 de janeiro") == "2027-01-03", f"mês que já passou pula para o ano seguinte ({data('3 de janeiro')})")
    checar(data("20 de dezembro") == "2026-12-20", "mês que ainda vem fica neste ano")

    checar(data("dia 30") == "2026-09-30", "só o dia, ainda neste mês")
    checar(data("dia 3") == "2026-10-03", f"dia que já passou vai para o mês seguinte ({data('dia 3')})")
    checar(data("32/13/2026") == "", "data impossível não vira data")


def test_horas() -> None:
    print("\nas horas do jeito que se escreve")
    def hora(frase):
        return intencao.ler("anote uma reunião dia 20/10 " + frase, HOJE).campos.get("hora", "")

    checar(hora("às 13:40") == "13:40", "às 13:40")
    checar(hora("as 9h") == "09:00", "as 9h")
    checar(hora("14h30") == "14:30", "14h30")
    checar(hora("às 16 horas") == "16:00", "16 horas")
    checar(hora("") == "09:00", "sem hora, o padrão da agenda")

    # A data tem números que parecem hora: "11/09/2026" não pode virar 09:00.
    i = intencao.ler("anote uma reunião 11/09/2026 às 13:40", HOJE)
    checar(i.campos["hora"] == "13:40", f"a data não se confunde com a hora ({i.campos['hora']})")


def test_avisos() -> None:
    print("\no lembrete")
    def aviso(frase):
        return intencao.ler("anote uma reunião dia 20/10 " + frase, HOJE).campos.get("avisar_min", 0)

    checar(aviso("com lembrete 10 minutos antes") == 10, "minutos")
    checar(aviso("com lembrete definido 10 minutos antes") == 10, "com palavra no meio")
    checar(aviso("me avise 30 min antes") == 30, "min")
    checar(aviso("avisar 1 hora antes") == 60, "hora vira minutos")
    checar(aviso("com lembrete 2 dias antes") == 2880, "dia vira minutos")
    checar(aviso("") == 0, "sem pedir aviso, não avisa")


def test_sem_data_nao_inventa() -> None:
    """
    Compromisso sem data não vira compromisso hoje.

    Marcar por conta própria no dia de hoje é o erro mais irritante que uma
    agenda pode cometer: a pessoa descobre pelo alarme.
    """
    print("\nsem data, não inventa data")
    i = intencao.ler("anote uma reunião com o cliente", HOJE)
    checar(i.tipo == "agenda", "continua sendo pedido de agenda")
    checar(not i.campos.get("data"), f"mas sem data ({i.campos.get('data')!r})")
    checar(i.falta, f"e dizendo o que falta ({i.falta!r})")
    checar("data" in i.falta, "com a palavra “data” na frase, para a pessoa saber o que dizer")


def test_tarefas() -> None:
    print("\ntarefas e prazos")
    i = intencao.ler("crie uma tarefa para revisar o contrato", HOJE)
    checar(i.tipo == "tarefa", "“crie uma tarefa” vira tarefa")
    checar(i.titulo == "Revisar o contrato",
           f"e o título é o assunto, não a palavra “tarefa” ({i.titulo!r})")
    checar(not i.campos.get("prazo"), "tarefa sem prazo continua sendo tarefa")

    i2 = intencao.ler("crie uma tarefa: protocolar a petição até sexta", HOJE)
    checar(i2.campos["prazo"] == "2026-09-18", f"com prazo quando a frase tem ({i2.campos['prazo']})")

    i3 = intencao.ler("marque o prazo de contestação para 25/09", HOJE)
    checar(i3.tipo == "tarefa", "prazo também é tarefa")
    checar(i3.campos["importante"] is True, "e prazo entra como importante")


def test_sobre_o_programa() -> None:
    print("\nperguntas sobre o próprio programa")
    for p in ("o que você faz?", "o que você sabe fazer", "você consegue assinar?",
              "para que você serve", "quais suas funções"):
        i = intencao.ler(p, HOJE)
        checar(i.tipo == "sobre", f"“{p}” é pergunta sobre o programa", f"virou {i.tipo}")

    # E isto NÃO é: fala de documento.
    i = intencao.ler("o que o contrato faz com a multa?", HOJE)
    checar(i.tipo == "documentos", f"mas pergunta sobre contrato não é ({i.tipo})")


def test_texto_vazio() -> None:
    print("\nborda")
    checar(intencao.ler("", HOJE).tipo == "documentos", "texto vazio não quebra")
    checar(intencao.ler("   ", HOJE).tipo == "documentos", "só espaço também não")
    checar(intencao.ler("anote", HOJE).tipo == "documentos",
           "verbo sozinho, sem dizer o quê, não vira ação")


def main() -> int:
    print("=" * 55)
    print("PAULUS - o que a pessoa está pedindo")
    print("=" * 55)

    test_o_pedido_que_nao_era_entendido()
    test_nao_vira_acao_o_que_nao_e()
    test_titulo_fica_legivel()
    test_datas()
    test_horas()
    test_avisos()
    test_sem_data_nao_inventa()
    test_tarefas()
    test_sobre_o_programa()
    test_texto_vazio()

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
