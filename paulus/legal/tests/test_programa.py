"""
Testes da camada do programa (programa.py) e do julgamento tipado (juizo.py).

A conversa passou a responder sobre o próprio PAULUS - o que está na agenda,
as tarefas atrasadas, o mês do Financeiro, a fila de Aprovações, como se faz
cada coisa, abrir uma tela - antes de procurar nos documentos. O que pode dar
errado aqui é tirar dos documentos uma pergunta que era sobre eles, ou
ensinar um caminho que não existe. Os testes cobrem as garantias:

  - o julgamento lê as probabilidades das letras, troca a ordem para anular o
    viés de posição, e sem resposta devolve None (nunca "a primeira opção")
  - a regra decide sozinha a navegação, o "como faço", a consulta sem âncora
    de documento e a consulta sobre os próprios registros
  - NENHUMA das perguntas de documento da regressão (test_inteligencia_
    regressao) sai dos documentos - e nenhuma sequer chama o modelo
  - o modelo só é chamado com sinal forte do programa, e abaixo do limiar a
    pergunta segue para os documentos
  - as consultas contam do banco (um banco temporário, semeado aqui)
  - o mapa das telas: toda tarefa aponta um arquivo e uma linha que existem,
    e todo rótulo citado num "clique em X" existe no frontend
  - pela API: a resposta vem sem modelo, com o cartão; "Procurar nos
    documentos" pula a camada

Não precisa do Ollama.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_programa.py
"""

from __future__ import annotations

import math
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import juizo  # noqa: E402
import programa  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    if cond:
        print(f"  ok  {nome}")
    else:
        print(f"  FALHOU  {nome}" + (f"  -> {detalhe!r}" if detalhe is not None else ""))
        _falhas.append(nome)


# ------------------------------------------------------------------ juizo


class _Resposta:
    def __init__(self, dado):
        self.dado = dado

    def raise_for_status(self):
        pass

    def json(self):
        return self.dado


def _post_que_prefere(letra_por_posicao: dict[str, float], chamadas: list):
    """Um Ollama falso: devolve as mesmas probabilidades por POSIÇÃO de letra."""
    def post(url, json=None, timeout=None):
        chamadas.append(json)
        top = [{"token": l, "logprob": math.log(p)} for l, p in letra_por_posicao.items()]
        return _Resposta({"message": {"content": "A"}, "logprobs": [{"top_logprobs": top}],
                          "prompt_eval_count": 10})
    return post


def test_distribuicao() -> None:
    print("\njuizo: da probabilidade de cada token à de cada letra")
    d = juizo.distribuicao([{"token": " B", "logprob": math.log(0.6)},
                            {"token": "A)", "logprob": math.log(0.3)},
                            {"token": "Eu", "logprob": math.log(0.1)}], "AB")
    checar(d and abs(d["B"] - 2 / 3) < 1e-6 and abs(d["A"] - 1 / 3) < 1e-6,
           "' B' e 'A)' contam como B e A, e a distribuição é renormalizada", d)
    d = juizo.distribuicao([{"token": "Eu", "logprob": math.log(0.9)},
                            {"token": "A", "logprob": math.log(0.05)}], "AB")
    checar(d is None, "quase toda a massa fora das letras: sem resposta, não um número sem lastro", d)
    checar(juizo.distribuicao([], "AB") is None, "sem candidatos: sem resposta")


def test_juiz() -> None:
    print("\njuizo: escolha, sim ou não, nota - e o que acontece quando falha")
    chamadas: list = []
    j = juizo.Juiz(model="falso", host="http://x", post=_post_que_prefere({"A": 0.2, "B": 0.8}, chamadas))
    e = j.escolher("qual?", [("um", "primeira"), ("dois", "segunda")], entrada="frase")
    checar(e and e.valor == "dois" and abs(e.p - 0.8) < 1e-6, "escolha devolve o id, não a letra", e)
    checar(chamadas and chamadas[-1]["options"]["num_predict"] == 1 and chamadas[-1]["logprobs"],
           "um token só, com logprobs, temperatura zero",
           chamadas[-1]["options"] if chamadas else None)
    usuario = chamadas[-1]["messages"][-1]["content"]
    checar(usuario.index("OPÇÕES") < usuario.index("ENTRADA"),
           "a frase da pessoa vai no fim (o começo fixo fica em cache no Ollama)")

    n = len(chamadas)
    j.escolher("qual?", [("um", "primeira"), ("dois", "segunda")], entrada="frase")
    checar(len(chamadas) == n, "a mesma pergunta não vai ao modelo duas vezes")

    # Um modelo que só gosta da letra B, fosse qual fosse a opção: trocando a
    # ordem, a preferência se anula - e o que sobra é empate.
    chamadas.clear()
    j2 = juizo.Juiz(model="falso", host="http://x", post=_post_que_prefere({"A": 0.2, "B": 0.8}, chamadas))
    e = j2.escolher("qual?", [("um", "primeira"), ("dois", "segunda")], entrada="x", trocar_ordem=True)
    checar(e and abs(e.probabilidades["um"] - 0.5) < 1e-6 and len(chamadas) == 2,
           "trocar_ordem: viés de posição puro vira 50/50, em duas chamadas", e and e.probabilidades)

    j3 = juizo.Juiz(model="falso", host="http://x", post=_post_que_prefere({"A": 0.7, "B": 0.3}, []))
    p = j3.sim_ou_nao("vale?", entrada="x")
    checar(p is not None and abs(p - 0.7) < 1e-6, "sim ou não: a probabilidade do sim", p)
    nota = juizo.Juiz(model="falso", host="http://x",
                      post=_post_que_prefere({"A": 0.0001, "B": 0.5, "C": 0.5}, [])).nota(
        "quanto?", ["nada", "algo", "muito"], entrada="x")
    checar(nota and abs(nota.valor - 0.75) < 0.01, "nota: posição esperada entre 0 e 1", nota and nota.valor)

    def quebra(url, json=None, timeout=None):
        raise ConnectionError("ollama fora")
    checar(juizo.Juiz(model="f", host="http://x", post=quebra).escolher(
        "q", [("a", "a"), ("b", "b")], entrada="x") is None, "Ollama fora do ar: None, não um palpite")

    def sem_logprobs(url, json=None, timeout=None):
        return _Resposta({"message": {"content": "A"}})
    checar(juizo.Juiz(model="f", host="http://x", post=sem_logprobs).escolher(
        "q", [("a", "a"), ("b", "b")], entrada="x") is None, "versão do Ollama sem logprobs: None")


# --------------------------------------------------------------- a regra


POSITIVOS = [
    # navegação
    ("abra o financeiro", "ir", "financeiro"),
    ("vá para a agenda", "ir", "calendario"),
    ("me mostra o calendário", "ir", "calendario"),
    ("abrir configurações", "ir", "config"),
    ("abre o acervo", "ir", "biblioteca"),
    # como fazer
    ("como eu assino um documento?", "como", "assinar"),
    ("como conecto meu e-mail?", "como", "caixa"),
    ("como traduzo um e-mail?", "como", "caixa"),
    ("como faço para cadastrar o certificado digital?", "como", "certificado"),
    ("como mudo para o tema escuro?", "como", "config"),
    ("mude o tema para escuro", "como", "config"),
    ("como lanço uma despesa?", "como", "financeiro"),
    ("como faço para lançar uma despesa?", "como", "financeiro"),
    ("dá pra traduzir e-mail?", "como", "caixa"),
    ("como gravo uma reunião?", "como", "gravacoes"),
    ("como faço para imprimir o contrato?", "como", "editor"),
    ("como assino o contrato da Cooperativa?", "como", "assinar"),
    ("o que é a tela de aprovações?", "como", "aprovacoes"),
    ("para que serve o acervo?", "como", "biblioteca"),
    # consulta
    ("quais compromissos tenho amanhã?", "consulta", "calendario"),
    ("quais reuniões tenho essa semana?", "consulta", "calendario"),
    ("tenho alguma tarefa atrasada?", "consulta", "tarefas"),
    ("mostre as tarefas de hoje", "consulta", "tarefas"),
    ("quanto recebi este mês?", "consulta", "financeiro"),
    ("quanto gastei no mês passado?", "consulta", "financeiro"),
    ("onde vejo minhas contas a pagar?", "consulta", "financeiro"),
    ("quantos clientes eu tenho?", "consulta", "cadastros"),
    ("tem algo para eu aprovar?", "consulta", "aprovacoes"),
    # consulta sobre os próprios registros, mesmo com palavra de documento
    ("tenho reunião com o autor do processo?", "consulta", "calendario"),
    ("quais tarefas eu tenho para o processo da Maria?", "consulta", "tarefas"),
    ("tem aprovação pendente para o contrato da Cooperativa?", "consulta", "aprovacoes"),
    # consultas que o banco de provas pediu (27/09/2026)
    ("o que tenho para hoje?", "consulta", "calendario"),
    ("tem algum cliente com pagamento atrasado?", "consulta", "financeiro"),
    ("quem está devendo?", "consulta", "financeiro"),
    ("quais serviços estão em andamento?", "consulta", "servicos"),
    ("quando vence o meu certificado digital?", "consulta", "certificado"),
]

NEGATIVOS = [
    "qual o valor do contrato da Cooperativa?",
    "quem é o cliente da procuração?",
    "como devo interpretar a cláusula 5?",
    "o contrato prevê multa por atraso?",
    "como está o prazo do contrato?",
    "como isso funciona no contrato?",
    "o que tenho a receber da Cooperativa segundo o contrato?",
    "quais compromissos o contrato prevê?",
    "a sentença menciona despesas processuais?",
    "qual o prazo de pagamento do contrato?",
]


class _Dados:
    """Bancos vazios: as consultas respondem, e o teste olha para onde foram."""

    class _Lista:
        def listar(self, *a, **k):
            return []

    agenda = tarefas = servicos = _Lista()

    class financeiro:  # noqa: N801
        @staticmethod
        def painel(mes=""):
            return {"tem_dado": False}

        @staticmethod
        def listar(**k):
            return []

    class fila:  # noqa: N801
        pendentes: list = []

    class cadastros:  # noqa: N801
        @staticmethod
        def contagem():
            return {}

    class cofre:  # noqa: N801
        instalado = False


class _Espiao:
    def __init__(self, p_programa: float | None = 0.99):
        self.p = p_programa
        self.chamadas: list[str] = []

    def escolher(self, instrucao, opcoes, estado=None, entrada="", trocar_ordem=False):
        self.chamadas.append(entrada)
        if self.p is None:
            return None
        ids = [i for i, _ in opcoes]
        probs = {i: (self.p if i == "programa" else 1 - self.p) for i in ids}
        return juizo.Escolha(valor=max(probs, key=probs.get), probabilidades=probs, confianca=0.5)


def test_regra() -> None:
    print("\nprograma: o que a regra decide sozinha")
    for frase, tipo, destino in POSITIVOS:
        espiao = _Espiao()
        l = programa.ler(frase, dados=_Dados(), juiz=espiao)
        checar(l and l.tipo == tipo and l.destino == destino and not espiao.chamadas,
               f"{frase!r} -> {tipo}:{destino}, sem modelo",
               (l.tipo, l.destino, espiao.chamadas) if l else espiao.chamadas)
    for frase in NEGATIVOS:
        l = programa.ler(frase, dados=_Dados())
        checar(l is None, f"{frase!r} fica com os documentos", l and (l.tipo, l.destino))


def test_regressao_nao_sai_dos_documentos() -> None:
    print("\nprograma: as perguntas de documento da regressão não saem dos documentos")
    from test_inteligencia_regressao import PERGUNTAS

    desviadas, julgadas = [], []
    for item in PERGUNTAS:
        espiao = _Espiao(0.99)   # um juiz que diria "programa" para tudo
        if programa.ler(item[0], dados=_Dados(), juiz=espiao):
            desviadas.append(item[0])
        julgadas += espiao.chamadas
    checar(not desviadas, f"nenhuma das {len(PERGUNTAS)} saiu dos documentos", desviadas)
    checar(not julgadas, "e nenhuma chegou a custar uma chamada ao modelo", julgadas)


def test_juiz_na_duvida() -> None:
    print("\nprograma: a dúvida vai ao modelo, e o limiar manda")
    frase = "a procuração tem alguma audiência marcada?"
    espiao = _Espiao(0.99)
    l = programa.ler(frase, dados=_Dados(), juiz=espiao)
    checar(espiao.chamadas == [frase], "palavra forte + âncora de documento: o modelo é chamado uma vez", espiao.chamadas)
    checar(l and l.por_modelo and l.julgamento.get("p", 0) > 0.9, "acima do limiar: a resposta diz que veio do modelo",
           l and l.julgamento)
    checar(programa.ler(frase, dados=_Dados(), juiz=_Espiao(programa.LIMIAR - 0.01)) is None,
           "abaixo do limiar: segue para os documentos")
    checar(programa.ler(frase, dados=_Dados(), juiz=_Espiao(None)) is None,
           "modelo sem resposta: segue para os documentos")
    checar(programa.ler(frase, dados=_Dados(), juiz=None) is None, "sem juiz: segue para os documentos")
    espiao = _Espiao(0.99)
    programa.ler("onde diz que o pagamento é parcelado?", dados=_Dados(), juiz=espiao)
    checar(not espiao.chamadas, "só palavra fraca (\"pagamento\"): nem pergunta ao modelo", espiao.chamadas)


# -------------------------------------------------------------- consultas


def test_consultas() -> None:
    print("\nprograma: as consultas contam do banco")
    import agenda
    import aprovacoes
    import base
    import cadastros
    import financeiro
    import tarefas
    import types

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        pasta = Path(pasta)
        b = base.Base(pasta / "teste.db")
        dados = types.SimpleNamespace(
            agenda=agenda.Agenda(b), tarefas=tarefas.Tarefas(b), financeiro=financeiro.Financeiro(b),
            cadastros=cadastros.Cadastros(b, pasta / "ign.json"), fila=aprovacoes.Fila(pasta / "fila.json"))
        hoje = date.today()
        amanha = (hoje + timedelta(days=1)).isoformat()
        dados.agenda.salvar({"titulo": "Audiência Cooperativa", "data": amanha, "hora": "14:00", "duracao": 90})
        dados.tarefas.salvar({"titulo": "Revisar aditivo", "prazo": (hoje - timedelta(days=3)).isoformat()})
        dados.tarefas.salvar({"titulo": "Tarefa sem prazo"})
        dados.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários set", "valor": "1500,00",
                                 "liquidado_em": hoje.isoformat()})
        dados.financeiro.salvar({"tipo": "despesa", "descricao": "Aluguel", "valor": "800,00",
                                 "vencimento": (hoje + timedelta(days=5)).isoformat()})
        dados.fila.pedir("Enviar e-mail à Cooperativa", "email")
        dados.cadastros.salvar({"nome": "Cooperativa Teste", "tipo": "cliente"})

        def texto(frase):
            l = programa.ler(frase, dados=dados)
            return l.texto if l else ""

        t = texto("quais compromissos tenho amanhã?")
        checar("Audiência Cooperativa" in t and "14:00–15:30" in t, "agenda de amanhã, com início e fim", t)
        checar("Nada marcado" in texto("quais compromissos tenho hoje?"), "dia sem nada: diz que não há nada")
        t = texto("tenho alguma tarefa atrasada?")
        checar("Revisar aditivo" in t and "atrasada 3" in t and "sem prazo" not in t,
               "só as atrasadas, com os dias de atraso", t)
        t = texto("quanto recebi este mês?")
        checar("1.500" in t and "800" in t, "o mês do Financeiro: entrou e o que está a pagar", t)
        t = texto("tem algo para eu aprovar?")
        checar("1 pedido" in t and "Enviar e-mail à Cooperativa" in t, "a fila de Aprovações", t)
        t = texto("quantos clientes eu tenho?")
        checar(t.startswith("1 ficha") and "Clientes" in t, "Cadastros: conta as fichas e cala os zeros", t)


# ------------------------------------------------------------------- mapa


def test_mapa() -> None:
    print("\nprograma: o mapa das telas não promete botão que não existe")
    mapa = programa.mapa()
    conhecidas = set(programa.telas_conhecidas())
    checar(len(mapa) >= 20, "o mapa cobre as telas do menu", len(mapa))
    fora = [d for d in mapa if d not in conhecidas]
    checar(not fora, "todo destino do mapa é uma tela que abre", fora)

    front = "\n".join(p.read_text(encoding="utf-8")
                      for p in list((RAIZ / "frontend" / "js").glob("*.js")) + [RAIZ / "frontend" / "index.html"])
    rotulo = re.compile(r"(?:[Cc]lique|clicar) (?:em|no ícone|na aba|no botão) "
                        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.,;:()“”]*?)(?= e[ ,]| ou | para | no | na | ao | do | da | à |, |\.|;| \(|$)")
    sem_arquivo, sem_rotulo, total = [], [], 0
    for tela in mapa.values():
        for t in tela.tarefas:
            arq, _, linha = t.evidencia.partition(":")
            caminho = RAIZ / arq
            if not caminho.exists() or int(linha or 0) > len(caminho.read_text(encoding="utf-8").splitlines()):
                sem_arquivo.append(t.evidencia)
            for passo in t.passos:
                for r in rotulo.findall(passo):
                    total += 1
                    if r.strip() not in front and r.replace(" N ", " ").strip() not in front:
                        sem_rotulo.append((tela.destino, r))
    checar(not sem_arquivo, "toda tarefa aponta um arquivo:linha que existe", sem_arquivo)
    checar(total > 150 and not sem_rotulo, f"os {total} rótulos de “clique em X” existem no frontend", sem_rotulo)


# -------------------------------------------------------------------- API


def test_pela_api() -> None:
    print("\npela API: a camada responde sem modelo e sabe sair do caminho")
    from test_gravacoes import Cliente, _porta_livre, _subir_servidor

    import api

    porta = _porta_livre()
    _subir_servidor(porta)
    c = Cliente(porta)
    chamadas: list = []
    original_chat, original_juiz = api.estado.client._chat, api._juiz
    api.estado.client._chat = lambda *a, **k: chamadas.append(a) or "ok"
    api._juiz = lambda: None
    criados = []
    try:
        st, t = c.pedir("POST", "/api/trabalhos", {"pedido": "programa"})
        criados.append(t["id"])
        url = f"/api/trabalhos/{t['id']}/perguntar"

        eventos = c.conversar(url, {"pergunta": "quanto recebi este mês?"})
        tipos = [tipo for tipo, _ in eventos]
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar("token" in tipos and p.get("tipo") == "programa" and p["campos"]["modo"] == "consulta"
               and p["campos"]["destino"] == "financeiro", "consulta: texto e cartão do Financeiro", tipos)
        checar(not chamadas, "sem chamar o modelo", len(chamadas))

        eventos = c.conversar(url, {"pergunta": "abra o financeiro"})
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar(p.get("campos", {}).get("modo") == "ir", "navegação: o cartão pede para abrir a tela", p)

        # "Procurar nos documentos": a camada não decide de novo. Com o
        # "pergunto onde procurar" ligado, a resposta é esse cartão - sem
        # modelo, e prova que a pergunta foi para o caminho dos documentos.
        eventos = c.conversar(url, {"pergunta": "abra o financeiro", "retomar": True,
                                    "documentos": True, "sem_anexo": True})
        p = next((d for tipo, d in eventos if tipo == "proposta"), {})
        checar(p.get("tipo") == "escopo", "documentos=true pula a camada", p.get("tipo"))
        st, trabalho = c.pedir("GET", f"/api/trabalhos/{t['id']}")
        tipos_guardados = [(m.get("proposta") or {}).get("tipo") for m in trabalho["mensagens"] if m["autor"] == "paulus"]
        checar(tipos_guardados == ["programa", "escopo"],
               "o Retomar troca o cartão do programa, sem repetir a pergunta", tipos_guardados)
    finally:
        api.estado.client._chat = original_chat
        api._juiz = original_juiz
        for id_ in criados:
            c.pedir("DELETE", f"/api/trabalhos/{id_}")


def main() -> int:
    print("=" * 55)
    print("  camada do programa e julgamento tipado")
    print("=" * 55)

    test_distribuicao()
    test_juiz()
    test_regra()
    test_regressao_nao_sai_dos_documentos()
    test_juiz_na_duvida()
    test_consultas()
    test_mapa()
    test_pela_api()

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
