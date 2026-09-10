"""
Testes do financeiro, dos relatórios, do bem-estar e das conexões.

Esta é a etapa em que inventar número é mais fácil e mais tentador: todas as
quatro telas mostram totais, médias e gráficos. O manual do sistema tem uma
regra para isso — "número na tela é número medido, sem placeholder, sem
estimativa" — e é ela que os testes daqui cobrem.

  - dinheiro em centavos inteiros; 0,1 + 0,2 tem que dar 0,30
  - sem lançamento, o painel dá zero e diz que está vazio
  - média de dois recebimentos não vira "prazo médio"
  - sem medição ligada, o relatório omite o tempo em vez de estimar
  - o bem-estar mede tempo ocioso, e nunca guarda linha do tempo

    python tests/test_historia.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import bemestar as BE  # noqa: E402
import conexoes as CX  # noqa: E402
import financeiro as F  # noqa: E402
import relatorios as REL  # noqa: E402
from base import Base  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


HOJE = date.today()


def _dia(mais: int) -> str:
    return (HOJE + timedelta(days=mais)).isoformat()


# ------------------------------------------------------------ financeiro


def test_dinheiro() -> None:
    """
    0,1 + 0,2 em ponto flutuante da 0,30000000000000004. Num extrato de
    honorarios o erro aparece depois de algumas dezenas de lancamentos.
    """
    print("\ndinheiro em centavos")
    for texto, esperado in [
        ("12.000,00", 1200000), ("R$ 8.500,00", 850000), ("1.234", 123400),
        ("0,50", 50), ("(300,00)", -30000), ("-1.200,50", -120050), ("", 0),
        ("abacaxi", 0), (1234.56, 123456),
    ]:
        lido = F.para_centavos(texto)
        checar(lido == esperado, f"{texto!r} vira {esperado} centavos", f"achou {lido}")

    soma = F.para_centavos("0,10") + F.para_centavos("0,20")
    checar(soma == 30, "0,10 + 0,20 da exatamente 0,30", f"achou {soma}")
    checar(F.em_reais(1200000) == "R$ 12.000,00", "centavos viram texto brasileiro")
    checar(F.em_reais(-30000) == "-R$ 300,00", "valor negativo tambem")
    checar(F.curto(8432000) == "R$ 84.320", "versao curta some com os centavos")

    # Mil somas de um centavo tem que dar dez reais exatos.
    total = sum(F.para_centavos("0,01") for _ in range(1000))
    checar(total == 1000, "mil somas de um centavo dao R$ 10,00 exatos", F.em_reais(total))


def test_painel_vazio(tmp: Path) -> None:
    """Sem lancamento, o painel da zero e avisa - nao desenha grafico bonito."""
    print("\npainel sem lancamento nenhum")
    base = Base(tmp / "vazio.db")
    fin = F.Financeiro(base)

    p = fin.painel()
    checar(p["tem_dado"] is False, "o painel diz que nao ha dado")
    checar(p["saldo"] == 0 and p["a_receber"] == 0 and p["atrasado"] == 0,
           "todos os totais sao zero")
    checar(fin.precisa_de_voce() == [], "e nao inventa pendencia")
    checar(all(m["entradas"] == 0 for m in fin.fluxo()), "o grafico de fluxo vem zerado")
    checar(fin.extrato()["linhas"] == [], "o extrato vem vazio")
    base.fechar()


def test_financeiro(tmp: Path) -> Base:
    print("\nlancamentos e o painel")
    base = Base(tmp / "fin.db")
    fin = F.Financeiro(base)

    fin.salvar({"tipo": "recebimento", "descricao": "Cooperativa · honorários",
                "valor": "12.000,00", "categoria": "honorarios", "vencimento": _dia(30)})
    atrasado = fin.salvar({"tipo": "recebimento", "descricao": "Fornecedor A",
                           "valor": "8.500,00", "categoria": "honorarios", "vencimento": _dia(-12)})
    fin.salvar({"tipo": "recebimento", "descricao": "Condomínio 402", "valor": "3.200,00",
                "categoria": "honorarios", "vencimento": _dia(-8), "liquidado_em": _dia(-8)})
    fin.salvar({"tipo": "despesa", "descricao": "Folha de setembro", "valor": "18.400,00",
                "categoria": "folha", "vencimento": _dia(3)})
    fin.salvar({"tipo": "despesa", "descricao": "Assinaturas", "valor": "1.800,00",
                "categoria": "sistemas", "vencimento": _dia(-5), "liquidado_em": _dia(-5)})

    p = fin.painel()
    checar(p["saldo"] == 140000, f"saldo e o que entrou menos o que saiu ({p['saldo_texto']})")
    checar(p["a_receber"] == 2050000, f"a receber soma so o que esta aberto ({p['a_receber_texto']})")
    checar(p["atrasado"] == 850000, f"em atraso soma so o vencido em aberto ({p['atrasado_texto']})")
    checar(p["atrasado_quantos"] == 1, "e conta quantas cobrancas")
    checar(p["a_pagar_quantos"] == 1, "a pagar conta so o que falta pagar")

    aberto = fin.listar(tipo="recebimento", situacao="aberto")
    vencido = next(l for l in aberto if l["id"] == atrasado)
    checar(vencido["atrasado"] is True, "marca o atrasado")
    checar(vencido["dias_atraso"] == 12, f"e conta os dias ({vencido['dias_atraso']})")
    checar("atrasado" in vencido["situacao"], f"a tela recebe a frase pronta ({vencido['situacao']})")

    avisos = fin.precisa_de_voce()
    titulos = " ".join(a["titulo"] for a in avisos)
    checar("atrasada" in titulos, "avisa da cobranca atrasada")
    checar("Folha" in titulos, "avisa da despesa que vence em 3 dias")
    checar(any("comprovante" in a["titulo"] for a in avisos), "avisa do que foi liquidado sem comprovante")

    # Liquidar muda o painel.
    fin.liquidar(atrasado)
    checar(fin.painel()["atrasado"] == 0, "depois de receber, o atraso zera")
    checar(fin.painel()["saldo"] == 140000 + 850000, "e o saldo sobe")
    fin.reabrir(atrasado)
    checar(fin.painel()["atrasado"] == 850000, "reabrir volta ao estado anterior")

    try:
        fin.salvar({"tipo": "recebimento", "descricao": "", "valor": "10,00"})
        checar(False, "recusa lancamento sem descricao")
    except ValueError:
        checar(True, "recusa lancamento sem descricao")
    try:
        fin.salvar({"tipo": "recebimento", "descricao": "x", "valor": "0"})
        checar(False, "recusa lancamento sem valor")
    except ValueError:
        checar(True, "recusa lancamento sem valor")

    return base


def test_extrato(base: Base) -> None:
    print("\nextrato com saldo correndo")
    fin = F.Financeiro(base)
    e = fin.extrato()

    checar(len(e["linhas"]) == 2, f"so o que foi liquidado entra no extrato (achou {len(e['linhas'])})")
    saldos = [l["saldo"] for l in e["linhas"]]
    checar(saldos == sorted(saldos, key=lambda x: saldos.index(x)),
           "o saldo corre linha a linha")
    checar(e["saldo_final"] == 140000, f"o saldo final fecha ({e['saldo_final_texto']})")
    checar(all(l["movimento_texto"][0] in "+−" for l in e["linhas"]),
           "cada linha diz se entrou ou saiu")


# ------------------------------------------------------------ relatorios


def test_relatorio_vazio(tmp: Path) -> None:
    print("\nrelatorio sem historia")
    base = Base(tmp / "rel-vazio.db")
    rel = REL.Relatorios(base)

    d = rel.para_tela()
    checar(d["vazio"] is True, "diz que nao ha o que resumir")
    checar(d["dia"]["tarefas"]["planejado"] == 0, "sem tarefa, o planejado e zero")
    checar(d["dia"]["tarefas"]["percentual"] == 0, "e o percentual nao divide por zero")
    checar(d["dia"]["sem_medicao"] is True, "avisa que nao ha medicao de tempo")
    checar("tempo_ativo" not in d["dia"]["medido"],
           "e NAO inventa tempo no escritorio")
    checar(d["mes"]["comparacao"]["tem_base"] is False,
           "sem mes anterior, nao compara com o mes anterior")
    base.fechar()


def test_prazo_medio(tmp: Path) -> None:
    """
    Media de dois numeros nao descreve habito nenhum. "Prazo medio: 14 dias"
    apoiado em duas linhas e inventar precisao.
    """
    print("\nmedia so quando ha o que medir")
    base = Base(tmp / "prazo.db")
    fin = F.Financeiro(base)
    rel = REL.Relatorios(base)
    mes = HOJE.strftime("%Y-%m")

    for i in range(2):
        fin.salvar({"tipo": "recebimento", "descricao": f"Cliente {i}", "valor": "1.000,00",
                    "vencimento": _dia(-10), "liquidado_em": _dia(-5)})
    p = rel.mes(mes)["prazo_medio"]
    checar(p["tem"] is False, "com dois recebimentos, nao devolve media")
    checar("três" in p["porque"], f"e explica por que ({p['porque'][:60]})")

    fin.salvar({"tipo": "recebimento", "descricao": "Cliente 3", "valor": "1.000,00",
                "vencimento": _dia(-10), "liquidado_em": _dia(-4)})
    p = rel.mes(mes)["prazo_medio"]
    checar(p["tem"] is True, "com tres, ja da uma media")
    checar(p["quantos"] == 3, "e diz sobre quantos ela foi calculada")
    base.fechar()


def test_relatorio_com_dado(tmp: Path) -> None:
    print("\nrelatorio do dia")
    base = Base(tmp / "rel.db")
    fin = F.Financeiro(base)
    rel = REL.Relatorios(base)

    hoje = HOJE.isoformat()
    base.escrever(
        "INSERT INTO tarefas (titulo, concluida, concluida_em, criada_em, meu_dia) "
        "VALUES (?, 1, ?, datetime('now'), 1)", ("Reler a cláusula 7", hoje + " 09:12:00"))
    base.escrever(
        "INSERT INTO tarefas (titulo, concluida, criada_em, meu_dia, prazo) "
        "VALUES (?, 0, datetime('now'), 1, ?)", ("Ligar para o cartório", ""))
    fin.salvar({"tipo": "recebimento", "descricao": "Condomínio", "valor": "3.200,00",
                "liquidado_em": hoje, "vencimento": hoje})

    d = rel.dia()
    checar(len(d["tarefas"]["feitas"]) == 1, "conta a tarefa concluida hoje")
    checar(d["tarefas"]["feitas"][0]["hora"] == "09:12", "com a hora em que foi fechada")
    checar(d["tarefas"]["planejado"] == 2, "planejado e o que estava no Meu dia")
    checar(d["tarefas"]["percentual"] == 50, f"e o percentual sai disso ({d['tarefas']['percentual']}%)")

    numeros = rel.numeros_para_o_parecer()
    checar("1 de 2" in numeros, "os numeros do parecer trazem a contagem certa")
    checar("Reler a cláusula 7" in numeros, "e citam a tarefa pelo nome")
    checar("3.200" in numeros, "e o valor do lancamento")
    checar("Tempo ativo" not in numeros,
           "e NAO citam tempo ativo, que nao foi medido")
    base.fechar()


def test_acoes_da_fila(tmp: Path) -> None:
    """A fila e o que torna "aprovei alguma coisa ontem" conferivel depois."""
    print("\nacoes aprovadas, lidas da fila")
    import aprovacoes

    base = Base(tmp / "acoes.db")
    fila = aprovacoes.Fila(tmp / "fila.json")
    rel = REL.Relatorios(base, fila=fila)

    p1 = fila.pedir("Assinar procuração", "assinatura", acao="assinatura.assinar", reversivel=False)
    p2 = fila.pedir("Mover 16 arquivos", "organizar", acao="organizar.mover")
    fila.pedir("Enviar e-mail", "email", acao="correio.enviar")

    fila.decidir(p1.id, True)
    fila.registrar_resultado(p1.id, "assinado, codigo ABC123")
    fila.decidir(p2.id, False)

    acoes = rel.acoes()
    checar(len(acoes) == 2, f"so o que foi decidido entra (achou {len(acoes)})")
    checar(any(a["estado"] == "recusado" for a in acoes), "o recusado tambem aparece")
    aprovado = next(a for a in acoes if a["estado"] == "aprovado")
    checar("ABC123" in aprovado["resultado"], "com o resultado que ficou registrado")
    checar(aprovado["reversivel"] is False, "e dizendo se dava para desfazer")
    base.fechar()


# ------------------------------------------------------------ bem-estar


def test_o_que_e_medido() -> None:
    """
    A medida e "ha quanto tempo ninguem toca", nunca "o que foi digitado".
    Nao existe caminho daqui para conteudo de tecla.
    """
    print("\no que o bem-estar mede")
    ocioso = BE.tempo_ocioso_segundos()
    if sys.platform == "win32":
        checar(ocioso is not None, "no Windows da para medir o tempo ocioso")
        checar(isinstance(ocioso, float) and ocioso >= 0, f"e vem um numero de segundos ({ocioso})")
    else:
        checar(ocioso is None, "fora do Windows devolve None em vez de estimar")

    fonte = (RAIZ / "src" / "bemestar.py").read_text(encoding="utf-8")
    for proibido in ("GetAsyncKeyState", "SetWindowsHookEx", "GetKeyboardState", "keylog"):
        checar(proibido not in fonte, f"o modulo nao usa {proibido}")
    checar("GetLastInputInfo" in fonte, "usa so o tempo desde o ultimo toque")


def test_bem_estar(tmp: Path) -> None:
    print("\nciclos, lembretes e totais do dia")
    base = Base(tmp / "be.db")
    be = BE.BemEstar(base)

    checar(be.sugerir_lembretes() == 4, "cria a lista inicial de lembretes")
    checar(be.sugerir_lembretes() == 0, "e nao duplica se ja houver")

    c = be.comecar_ciclo("enviar aviso", foco=25, pausa=5)
    checar(c["estado"] == "foco" and c["numero"] == 1, "comeca o ciclo de foco")
    checar(c["restante"] > 24 * 60, f"com o tempo certo ({c['restante_texto']})")
    checar(c["tarefa"] == "enviar aviso", "guardando a tarefa do ciclo")

    be.ir_para_pausa()
    hoje = be.dia()
    checar(hoje["ciclos"] == 1, "o ciclo entra no total do dia")
    checar(hoje["pausas"] == 1, "a pausa tambem")

    # Parar antes do fim ainda conta como pausa.
    be.comecar_ciclo()
    be.ir_para_pausa()
    checar(be.dia()["pausas"] == 2, "quem para antes descansou do mesmo jeito")

    agua = next(l for l in be.lembretes() if "gua" in l["titulo"])
    be.marcar_lembrete(agua["id"])
    be.marcar_lembrete(agua["id"])
    checar(be.dia()["copos_agua"] == 2, "beber agua entra no total do dia")
    marcado = next(l for l in be.lembretes() if l["id"] == agua["id"])
    checar(marcado["meta_texto"] == "2 de 8", f"e o lembrete mostra o progresso ({marcado['meta_texto']})")

    # O que fica guardado sao totais, nunca uma linha do tempo.
    colunas = {c["name"] for c in base.buscar("PRAGMA table_info(bem_estar)")}
    checar(colunas == {"dia", "minutos_ativos", "ciclos", "pausas", "copos_agua",
                       "maior_seguida", "atualizado_em"},
           f"a tabela guarda so totais do dia ({sorted(colunas)})")
    checar(base.contar("bem_estar") == 1, "uma linha por dia, nao por evento")

    s = be.semana()
    checar(len(s["dias"]) == 7, "a semana tem sete dias")
    checar(s["ciclos"] == 2, "e soma os ciclos")
    checar(be.alerta() is None, "sem medicao ligada, nao ha sugestao baseada em nada")
    base.fechar()


# ------------------------------------------------------------- conexoes


def test_conexoes(tmp: Path) -> None:
    print("\nconexoes")
    for bruto, esperado in [
        ("(62) 99999-8888", "5562999998888"),
        ("62999998888", "5562999998888"),
        ("+55 62 99999-8888", "5562999998888"),
        ("0055 62 99999-8888", "5562999998888"),
        ("6233334444", "556233334444"),
        ("", ""), ("sem numero", ""),
    ]:
        lido = CX.numero_whatsapp(bruto)
        checar(lido == esperado, f"{bruto!r} vira {esperado!r}", f"achou {lido!r}")

    link = CX.link_de_conversa("(62) 99999-8888", "Segue a procuração assinada.")
    checar(link.startswith("https://web.whatsapp.com/send?phone=5562999998888"),
           "monta o endereço de conversa oficial")
    checar("procura%C3%A7%C3%A3o" in link, "com o texto codificado corretamente")
    checar(CX.link_de_conversa("", "oi") == "", "sem telefone, nao monta endereco")

    cx = CX.Conexoes(tmp / "cx.json", tmp / "sessoes")
    checar(cx.sessao().existe is False, "sem sessao, diz que nao ha")

    pasta = tmp / "sessoes" / "whatsapp"
    pasta.mkdir(parents=True)
    (pasta / "dados.bin").write_bytes(b"x" * 4096)
    checar(cx.sessao().existe is True, "com a pasta, reconhece a sessao")
    checar(cx.sessao().tamanho_kb == 4, "e sabe o tamanho")

    checar(cx.apagar_sessao() is True, "apagar apaga")
    checar(not pasta.exists(), "e a pasta some de verdade")

    cx.anotar("(62) 99999-8888", "Priscila", str(tmp / "doc.pdf"))
    guardado = cx.itens[0]
    checar(guardado["para"] == "5562999998888", "o registro guarda o numero normalizado")
    checar(guardado["anexo"] == "doc.pdf", "e o nome do anexo")
    checar("texto" not in guardado,
           "mas NAO guarda o texto da mensagem - ele ja esta na conversa")

    tela = cx.para_tela()
    nao_faz = [o["texto"] for o in tela["o_que_faco"] if not o["faz"]]
    checar(any("enviar" in t.lower() for t in nao_faz),
           "a tela declara que nao aperta enviar por voce")
    checar(any("conversas" in t.lower() for t in nao_faz),
           "e que nao le as conversas")


def main() -> int:
    print("=" * 55)
    print("PAULUS - financeiro, relatórios, bem-estar e conexões")
    print("=" * 55)

    test_dinheiro()
    test_o_que_e_medido()

    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_painel_vazio(tmp)
        base = test_financeiro(tmp)
        test_extrato(base)
        base.fechar()
        test_relatorio_vazio(tmp)
        test_prazo_medio(tmp)
        test_relatorio_com_dado(tmp)
        test_acoes_da_fila(tmp)
        test_bem_estar(tmp)
        test_conexoes(tmp)

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
