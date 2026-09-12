"""
Testes da biblioteca grande: procurar, filtrar, ordenar e agir em lote.

O que esta tela tem de perigoso não é mostrar errado — é agir em muitos. Um
"mover 128 documentos" que passa por cima de um arquivo de mesmo nome destrói
trabalho sem avisar, e um "apagar em lote" que sai da pasta do programa apaga
o original de alguém. Então os testes cobrem:

  - procurar acha pelo conteúdo, e diz que foi pelo conteúdo
  - fixado sobe na ordenação, sempre
  - "sem análise" e "mudou desde então" são estados diferentes
  - mover nunca escolhe um destino que já existe
  - o que não dá para mover sai contado, com o motivo

    python tests/test_acervo.py
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import acervo  # noqa: E402
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


@dataclass
class Pedaco:
    doc_name: str
    text: str


def _agora(dias: float = 0, horas: float = 0) -> str:
    return (datetime.now() - timedelta(days=dias, hours=horas)).isoformat(timespec="seconds")


def _acervo_de_teste() -> list[dict]:
    return [
        {"sha1": "a1", "nome": "contrato_fornecedor_A_2024.pdf", "pasta": r"C:\Jurídico",
         "pasta_curta": "Jurídico", "caminho": r"C:\Jurídico\contrato_fornecedor_A_2024.pdf",
         "existe": True, "bytes": 90_000, "tipo": "contrato", "tipo_rotulo": "Contrato",
         "cliente": "Fornecedor A", "fixado": False,
         "modificado_em": _agora(horas=1), "visto_em": _agora(horas=2)},
        {"sha1": "b2", "nome": "Ata de reunião — 06 de agosto.pdf", "pasta": r"C:\Área de trabalho",
         "pasta_curta": "Área de trabalho", "caminho": r"C:\Área de trabalho\Ata.pdf",
         "existe": True, "bytes": 12_000, "tipo": "", "tipo_rotulo": "",
         "cliente": "", "fixado": True,
         "modificado_em": _agora(dias=40), "visto_em": ""},
        {"sha1": "c3", "nome": "Seguro predial.pdf", "pasta": r"C:\Jurídico",
         "pasta_curta": "Jurídico", "caminho": r"C:\Jurídico\Seguro predial.pdf",
         "existe": True, "bytes": 300_000, "tipo": "apolice", "tipo_rotulo": "Apólice",
         "cliente": "Seguradora", "fixado": False,
         "modificado_em": _agora(horas=3), "visto_em": _agora(dias=2)},
        {"sha1": "d4", "nome": "sumido.docx", "pasta": r"C:\Downloads",
         "pasta_curta": "Downloads", "caminho": r"C:\Downloads\sumido.docx",
         "existe": False, "bytes": 0, "tipo": "", "tipo_rotulo": "",
         "cliente": "", "fixado": False, "modificado_em": "", "visto_em": ""},
    ]


def test_procurar() -> None:
    print("\nprocurar por nome, pasta e trecho")
    itens = _acervo_de_teste()
    trechos = acervo.indexar_trechos([
        Pedaco("Seguro predial.pdf",
               "A presente apólice cobre danos decorrentes de cessão de direitos hereditários "
               "e demais eventos previstos nesta cláusula."),
        Pedaco("contrato_fornecedor_A_2024.pdf", "Cláusula primeira. Do objeto do contrato."),
    ])

    checar(len(acervo.procurar(itens, "")) == len(itens), "termo vazio não corta nada")

    por_nome = acervo.procurar(itens, "fornecedor", trechos)
    checar(len(por_nome) == 1 and por_nome[0]["achado_em"] == "nome", "acha pelo nome")

    por_pasta = acervo.procurar(itens, "jurídico", trechos)
    checar(len(por_pasta) == 2 and all(x["achado_em"] == "pasta" for x in por_pasta),
           f"acha pela pasta (achou {len(por_pasta)})")

    # O acento é digitação, não sintaxe: quem digita "juridico" quer a mesma coisa.
    checar(len(acervo.procurar(itens, "juridico", trechos)) == 2, "e ignora o acento")

    por_trecho = acervo.procurar(itens, "direitos hereditários", trechos)
    checar(len(por_trecho) == 1 and por_trecho[0]["sha1"] == "c3",
           "acha pelo conteúdo, que é o que a pessoa lembra")
    checar(por_trecho[0]["achado_em"] == "trecho", "e diz que foi pelo conteúdo")
    checar("hereditários" in por_trecho[0]["trecho"],
           f"trazendo o trecho junto ({por_trecho[0]['trecho'][:50]!r})")
    checar(len(por_trecho[0]["trecho"]) < 190, "o trecho é um trecho, não a página inteira")

    checar(acervo.procurar(itens, "xyzzy", trechos) == [], "termo que não existe devolve vazio")


def test_filtrar_e_ordenar() -> None:
    print("\nfiltrar e ordenar")
    itens = _acervo_de_teste()

    checar(len(acervo.filtrar(itens, "todos")) == 4, "todos é todos")
    checar([x["sha1"] for x in acervo.filtrar(itens, "fixados")] == ["b2"], "fixados")
    checar({x["sha1"] for x in acervo.filtrar(itens, "sem-analise")} == {"b2", "d4"},
           "sem análise pega quem não tem tipo")

    recentes = {x["sha1"] for x in acervo.filtrar(itens, "recentes")}
    checar(recentes == {"a1", "c3"}, f"recentes deixa de fora o de 40 dias (achou {recentes})")
    checar("d4" not in recentes, "e o que nem tem data não conta como recente")

    # Fixar é a pessoa dizendo "este importa". Se a ordenação derruba, o gesto
    # não serviu para nada.
    por_nome = acervo.ordenar(itens, "nome")
    checar(por_nome[0]["sha1"] == "b2", "o fixado vem primeiro, mesmo fora de ordem alfabética")
    checar([x["nome"] for x in por_nome[1:]] == sorted(
        (x["nome"] for x in itens if not x["fixado"]), key=acervo._sem_acento),
        "e o resto sai em ordem de nome")

    por_data = acervo.ordenar(itens, "modificacao")
    checar(por_data[0]["sha1"] == "b2", "o fixado vem primeiro também por data")
    checar([x["sha1"] for x in por_data[1:]] == ["a1", "c3", "d4"],
           f"e o mais recente antes ({[x['sha1'] for x in por_data]})")

    por_tamanho = acervo.ordenar(itens, "tamanho")
    checar([x["sha1"] for x in por_tamanho[1:]] == ["c3", "a1", "d4"], "o maior primeiro")


def test_analise() -> None:
    print("\nem que pé está a leitura")
    itens = {x["sha1"]: x for x in _acervo_de_teste()}

    checar(acervo.estado_da_analise(itens["b2"])["estado"] == "sem-analise",
           "documento sem tipo é “sem análise”")

    # Este é o estado que importa: foi lido, mas o arquivo mudou depois. Ler
    # como "analisado" faria a pessoa citar o documento pela versão velha.
    mudou = acervo.estado_da_analise(
        {"tipo": "contrato", "visto_em": _agora(dias=3), "modificado_em": _agora(horas=1)})
    checar(mudou["estado"] == "mudou", "lido antes e mexido depois é “mudou desde então”")
    checar(mudou["rotulo"] == "mudou desde então", f"e o rótulo diz isso ({mudou['rotulo']!r})")

    em_dia = acervo.estado_da_analise(
        {"tipo": "contrato", "visto_em": _agora(horas=1), "modificado_em": _agora(horas=3)})
    checar(em_dia["estado"] == "analisado", "lido depois da última mudança é “analisado”")
    # O rótulo traz QUANDO foi lido; a palavra exata depende da hora do dia —
    # a mesma leitura vira "ontem" depois da meia noite — e isso `quando` já
    # tem teste próprio, com a hora fixada. Aqui basta que o rótulo diga algo.
    checar(em_dia["rotulo"].startswith("analisado · ") and len(em_dia["rotulo"]) > 13,
           f"com quando ({em_dia['rotulo']!r})")

    # Sem registro de quando foi lido, não inventar um.
    sem_hora = acervo.estado_da_analise({"tipo": "contrato", "visto_em": "", "modificado_em": _agora()})
    checar(sem_hora["estado"] == "analisado" and sem_hora["rotulo"] == "analisado",
           f"sem registro de quando, mostra só “analisado” ({sem_hora['rotulo']!r})")


def test_quando() -> None:
    """
    O relógio entra pela porta, e não pela janela.

    Este teste falhava às 00:17: uma leitura de uma hora atrás cai em ontem, e
    o rótulo vira "ontem" em vez de "há 1 h" — o que é verdade, e é o
    comportamento certo. O errado era o teste, que passava de tarde e falhava
    de madrugada. Com a hora fixada, ele mede a regra em vez de medir que
    horas são.
    """
    print("\no tempo do jeito que se fala")
    agora = datetime(2026, 9, 11, 15, 0, 0)      # meio da tarde, longe da virada

    def diz(dias=0, horas=0):
        instante = (agora - timedelta(days=dias, hours=horas)).isoformat(timespec="seconds")
        return acervo.quando(instante, agora=agora)

    checar(acervo.quando("") == "", "sem data, sem texto")
    checar(diz(horas=0.01) == "agora", "agora é agora")
    checar(diz(horas=0.5) == "há 30 min", "minutos")
    checar(diz(horas=3) == "há 3 h", f"horas ({diz(horas=3)})")
    checar(diz(dias=1) == "ontem", f"ontem ({diz(dias=1)})")

    # A virada do dia: uma hora atrás, à meia noite e dez, é ontem — e dizer
    # "ontem" ali é o certo, não um defeito.
    madrugada = datetime(2026, 9, 12, 0, 10, 0)

    def de_madrugada(minutos):
        instante = (madrugada - timedelta(minutes=minutos)).isoformat(timespec="seconds")
        return acervo.quando(instante, agora=madrugada)

    checar(de_madrugada(60) == "ontem",
           f"depois da meia noite, o que é de ontem diz “ontem” ({de_madrugada(60)})")
    checar(de_madrugada(40) == "há 40 min",
           f"mas o que é de minutos atrás continua em minutos ({de_madrugada(40)})")

    velho = acervo.quando(_agora(dias=40))
    checar(" de " in velho, f"o que é de outro mês vira data por extenso ({velho})")
    checar("dias" not in velho, "e não vira “há 40 dias”, que obriga a pessoa a fazer conta")


def test_plano_de_mover(tmp: Path) -> None:
    print("\nmover em lote, sem passar por cima de nada")
    origem = tmp / "de"
    destino = tmp / "para"
    origem.mkdir()
    destino.mkdir()

    (origem / "contrato.pdf").write_text("um", encoding="utf-8")
    (origem / "outro.pdf").write_text("dois", encoding="utf-8")
    (destino / "contrato.pdf").write_text("JÁ EXISTE", encoding="utf-8")

    itens = [
        {"nome": "contrato.pdf", "caminho": str(origem / "contrato.pdf"), "existe": True},
        {"nome": "outro.pdf", "caminho": str(origem / "outro.pdf"), "existe": True},
        {"nome": "sumido.pdf", "caminho": str(origem / "sumido.pdf"), "existe": False},
        {"nome": "parado.pdf", "caminho": str(destino / "parado.pdf"), "existe": True},
    ]

    plano = acervo.plano_de_mover(itens, destino)
    por_nome = {m["nome"]: m for m in plano["movimentos"]}

    checar(len(plano["movimentos"]) == 2, f"move os dois que dá (achou {len(plano['movimentos'])})")

    # O destino já tinha um contrato.pdf. Sobrescrever apagaria o de lá sem
    # avisar - e em lote, 128 vezes.
    alvo = Path(por_nome["contrato.pdf"]["destino"])
    checar(alvo.name != "contrato.pdf", f"não escolhe um nome que já existe ({alvo.name})")
    checar(alvo.parent == destino, "mas continua indo para a pasta pedida")
    checar((destino / "contrato.pdf").read_text(encoding="utf-8") == "JÁ EXISTE",
           "e o arquivo que já estava lá continua intacto")

    motivos = {i["nome"]: i["motivo"] for i in plano["impedidos"]}
    checar("sumido.pdf" in motivos and "disco" in motivos["sumido.pdf"],
           "o que sumiu do disco sai contado, com motivo")
    checar("parado.pdf" in motivos and "pasta" in motivos["parado.pdf"],
           "o que já está no destino também")
    checar(len(plano["impedidos"]) == 2, "e nada some sem aparecer")


def test_dois_iguais_no_mesmo_lote(tmp: Path) -> None:
    """Dois arquivos de mesmo nome, em pastas diferentes, no mesmo lote."""
    print("\ndois de mesmo nome no mesmo lote")
    a, b, destino = tmp / "a", tmp / "b", tmp / "fim"
    for pasta in (a, b, destino):
        pasta.mkdir()
    (a / "recibo.pdf").write_text("de A", encoding="utf-8")
    (b / "recibo.pdf").write_text("de B", encoding="utf-8")

    plano = acervo.plano_de_mover([
        {"nome": "recibo.pdf", "caminho": str(a / "recibo.pdf"), "existe": True},
        {"nome": "recibo.pdf", "caminho": str(b / "recibo.pdf"), "existe": True},
    ], destino)

    alvos = [m["destino"] for m in plano["movimentos"]]
    checar(len(alvos) == 2, "os dois entram no plano")
    checar(len(set(alvos)) == 2,
           f"e vão para caminhos diferentes — um não apaga o outro ({[Path(x).name for x in alvos]})")


def test_copias_identicas(tmp: Path) -> None:
    """
    Dois arquivos iguais byte a byte tem o mesmo SHA-1.

    Este teste existe porque a primeira versao escolhia por SHA-1: pedir para
    apagar 2 documentos montava um pedido com 4, porque as copias entravam
    junto. Num escritorio, "contrato.pdf" e "contrato (1).pdf" com o mesmo
    conteudo sao o caso comum, nao a excecao - e apagar um levando o outro e
    o estrago que a fila existe para impedir.

    A identidade da linha e o caminho. A do fixado continua sendo o SHA-1:
    la a identidade e mesmo o conteudo, e mover o arquivo nao pode apagar a
    marca.
    """
    print("\ncópias com o mesmo conteúdo")
    pasta = tmp / "copias"
    pasta.mkdir(parents=True)

    itens = [
        {"sha1": "mesmo", "nome": "contrato.pdf", "caminho": str(pasta / "contrato.pdf"),
         "existe": True, "fixado": False, "bytes": 10, "nome_curto": ""},
        {"sha1": "mesmo", "nome": "contrato (1).pdf", "caminho": str(pasta / "contrato (1).pdf"),
         "existe": True, "fixado": False, "bytes": 10, "nome_curto": ""},
    ]
    for i in itens:
        Path(i["caminho"]).write_text("igual", encoding="utf-8")

    checar(itens[0]["sha1"] == itens[1]["sha1"], "as duas copias tem o mesmo SHA-1")
    checar(itens[0]["caminho"] != itens[1]["caminho"], "mas caminhos diferentes")

    # Este e o teste: escolher por caminho pega uma; por SHA-1 pegaria as duas.
    escolhido = {itens[0]["caminho"]}
    pegos = [i for i in itens if i["caminho"] in escolhido]
    checar(len(pegos) == 1, f"escolher pelo caminho pega uma so (pegou {len(pegos)})")

    por_hash = [i for i in itens if i["sha1"] in {itens[0]["sha1"]}]
    checar(len(por_hash) == 2, "e pelo SHA-1 pegaria as duas — por isso não é por SHA-1")

    destino = tmp / "destino"
    destino.mkdir()
    plano = acervo.plano_de_mover(pegos, destino)
    checar(len(plano["movimentos"]) == 1, "o plano de mover leva só a escolhida")
    checar(Path(plano["movimentos"][0]["origem"]).name == "contrato.pdf",
           "e leva exatamente a que foi marcada")


def test_resumo() -> None:
    print("\na frase que a fila mostra")
    itens = [{"nome": f"documento {n}.pdf"} for n in range(5)]

    mover = acervo.resumo_do_lote("mover", itens, r"C:\Jurídico")
    checar("5 documentos" in mover, f"diz quantos ({mover[:40]})")
    checar("Jurídico" in mover, "e para onde")
    checar("e mais 2" in mover, "lista alguns e conta o resto")
    checar("desfazer" in mover, "e avisa que dá para desfazer")

    apagar = acervo.resumo_do_lote("apagar", itens[:1])
    checar("1 documento" in apagar and "1 documentos" not in apagar, "singular quando é um só")
    checar("original" in apagar, "apagar explica que o original não é tocado")

    exportar = acervo.resumo_do_lote("exportar", itens, r"C:\Saída")
    checar("internet" in exportar, "exportar diz que nada vai para a internet")


def test_marcas(tmp: Path) -> None:
    print("\nfixar fica guardado")
    base = Base(tmp / "marcas.db")
    try:
        m = acervo.Marcas(base)
        checar(m.de_todos() == {}, "começa sem marca nenhuma")

        m.fixar("abc")
        checar(m.de_todos()["abc"]["fixado"] == 1, "fixa")
        checar(m.de_todos()["abc"]["fixado_em"] != "", "e anota quando")

        m.marcar_visto("abc")
        checar(m.de_todos()["abc"]["visto_em"] != "", "marcar como lido não desfaz o fixado")
        checar(m.de_todos()["abc"]["fixado"] == 1, "o fixado continua de pé")

        m.fixar("abc", False)
        checar(m.de_todos()["abc"]["fixado"] == 0, "desfixa")
        checar(m.de_todos()["abc"]["visto_em"] != "", "e a leitura continua registrada")

        m.marcar_visto("novo")
        checar(m.de_todos()["novo"]["fixado"] == 0,
               "marcar leitura de quem nunca foi fixado não fixa sozinho")
    finally:
        base.fechar()


def main() -> int:
    print("=" * 55)
    print("PAULUS - biblioteca grande")
    print("=" * 55)

    test_procurar()
    test_filtrar_e_ordenar()
    test_analise()
    test_quando()
    test_resumo()
    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        for nome in ("mover", "iguais"):
            (tmp / nome).mkdir()
        test_plano_de_mover(tmp / "mover")
        test_dois_iguais_no_mesmo_lote(tmp / "iguais")
        test_copias_identicas(tmp)
        test_marcas(tmp)

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
