"""
A ata da cooperativa (14/10/2026): o dono pediu "Não precisa dizer que o
'Cotovelo' foi advertido por falta de companheirismo, ele será advertido pelo
abandono ao serviço" - com erro de digitação - e o Paulus respondeu "Não mudei
nada"; selecionou a linha e perguntou "E isso aqui é o que?" e veio uma
resposta genérica, repetida, com os nomes internos dos blocos à mostra; e o
documento tinha "* " no lugar da lista. Os mesmos erros, com dados fictícios:

  - o esboço do documento sem cláusula (ata, parecer): as seções em maiúsculas
    e os parágrafos e itens numerados dentro delas, nada de "Preâmbulo";
  - a marcação de rascunho ("* item", "**negrito**", "# Título") vira lista,
    negrito e título, palavra nenhuma mudando - na criação, no botão, na
    revisão e no "tire os asteriscos" (sem modelo);
  - o pedido com erro de digitação acha o trecho; a correção que não trouxe
    nada não apaga o motivo; a segunda tentativa reescreve o bloco provável;
    sem nada feito, a resposta mostra o trecho mais parecido e o "sim" faz ali;
  - "E isso aqui?" com o trecho selecionado depois de um pedido que não mudou
    nada é o lugar do pedido; a pergunta sobre a seleção lê a seleção e a
    conversa;
  - a segunda leitura que diz "a mudança não foi feita" não vira aviso;
  - a sugestão repetida não volta.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_ata.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-editor-ata-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

import agente_de_edicao as AG  # noqa: E402
import blocos as B  # noqa: E402
import esboco as E  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def html(linhas: list[str]) -> str:
    return "".join(f"<p>{x}</p>" for x in linhas)


ATA = [
    "ATA DA REUNIÃO EXTRAORDINÁRIA DA COOPERATIVA COOPERTESTE",
    "INTRODUÇÃO",
    "A reunião extraordinária da cooperativa COOPERTESTE foi realizada em 10 de outubro de 2026, na sede da cooperativa.",
    "Estiveram presentes os membros da diretoria e os cooperados convocados.",
    "OBJETIVO DA REUNIÃO",
    "O objetivo da reunião foi discutir a falta de empenho de alguns cooperados.",
    "PROVIDÊNCIAS",
    "As providências tomadas em relação ao operador 'Martelo' incluem:",
    "* O operador 'Martelo' será advertido por sua falta de empenho e companheirismo;",
    "* O operador 'Martelo' terá um prazo de 30 dias para retornar às atividades;",
    "* **Atenção:** o descumprimento levará ao afastamento.",
    "CONCLUSÃO",
    "A cooperativa está comprometida em resolver os problemas apontados.",
    "Belo Horizonte, 10 de outubro de 2026.",
    "JOSÉ PRESIDENTE TESTE",
    "MARIA SECRETÁRIA EXEMPLO",
]
PEDIDO = ("Não precisa dizer que o 'Martelo' foi advertido por falta de companherismo, ele será advertido pelo abandono "
          "ao serviço")


class Falso:
    """O modelo de mentira: responde a fila de respostas e guarda o que leu."""

    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.lido: list[list[dict]] = []

    def __call__(self, mensagens, *, json_mode=False, max_tokens=4000, on_token=None):
        self.lido.append(mensagens)
        texto = self.respostas.pop(0) if self.respostas else "{}"
        if on_token:
            on_token(texto)
        return texto


def j(**k) -> str:
    return json.dumps(k, ensure_ascii=False)


def rodada(chamar, blocos, pedido: str, **k):
    eventos = list(AG.rodar(chamar, blocos, pedido, rodada=1, titulo="Ata da cooperativa", **k))
    return eventos, next(d["rodada"] for t, d in eventos if t == "fim")


def bloco(blocos, comeco: str):
    return next(b for b in blocos if b.texto.startswith(comeco))


def teste_esboco() -> None:
    print("o esboço da ata: seções, parágrafos e itens")
    bl, _ = B.sem_marcacao_de_rascunho(B.ler(html(ATA)))
    partes = [(b.texto, p.rotulo) for b, p in zip(bl, E.esboco(bl))]

    def rot(comeco: str) -> str:
        return next((r for t, r in partes if t.startswith(comeco)), "")

    checar(rot("ATA DA REUNIÃO") == "Título", "a primeira linha é o título", partes[:2])
    checar(rot("PROVIDÊNCIAS") == "PROVIDÊNCIAS" and rot("OBJETIVO DA REUNIÃO") == "OBJETIVO DA REUNIÃO",
           "as linhas em maiúsculas são seções (e não nome de quem assina)", partes)
    checar(rot("As providências tomadas") == "PROVIDÊNCIAS, 1º parágrafo"
           and rot("O operador 'Martelo' será") == "PROVIDÊNCIAS, 1º item"
           and rot("Atenção:") == "PROVIDÊNCIAS, 3º item" and rot("A cooperativa está") == "CONCLUSÃO, 1º parágrafo",
           "o parágrafo e os itens contados à parte, dentro da seção", partes)
    checar(rot("JOSÉ PRESIDENTE TESTE") == "Assinaturas", "os nomes no fim são as assinaturas", rot("JOSÉ PRESIDENTE"))
    checar("Preâmbulo" not in [r for _, r in partes],
           "nada é “Preâmbulo” (a resposta dizia “Reescrevi o preâmbulo” quatro vezes)")


def teste_marcacao() -> None:
    print("\na marcação de rascunho vira lista, negrito e título")
    bl = B.ler(html(ATA))
    checar(B.marcas_de_rascunho(bl) == 3, "3 parágrafos com marca de rascunho", B.marcas_de_rascunho(bl))
    novos, rel = B.sem_marcacao_de_rascunho(bl)
    checar(rel == {"itens": 3, "titulos": 0, "negritos": 1}, "3 itens de lista e 1 negrito", rel)
    item = bloco(novos, "O operador 'Martelo' será")
    checar(item.tipo == "li" and item.lista == "ul" and item.id == bloco(bl, "* O operador 'Martelo' será").id,
           "“* item” é item de lista de verdade, com o mesmo nome de bloco")
    atencao = bloco(novos, "Atenção:")
    checar(atencao.corridas[0].texto == "Atenção:" and atencao.corridas[0].marcas == ("b",),
           "“**Atenção:**” fica em negrito, sem os asteriscos", [(c.texto, c.marcas) for c in atencao.corridas])
    saida = B.html(novos)
    checar("<ul><li" in saida and "* " not in saida and "**" not in saida, "o HTML tem a lista e nenhum asterisco")
    checar(B.marcas_de_rascunho(B.ler(saida)) == 0, "depois de arrumado, nada a arrumar")
    outros, rel2 = B.sem_marcacao_de_rascunho(B.ler(html(["# DOS FATOS", "* * *", "- item com traço", "-5 graus",
                                                          "<b>**já em negrito**</b>"])))
    tipos = [(b.tipo, b.texto) for b in outros]
    checar(tipos == [("h2", "DOS FATOS"), ("p", "* * *"), ("li", "item com traço"), ("p", "-5 graus"),
                     ("p", "já em negrito")], "“# ” vira título; o separador e o número negativo ficam", tipos)
    sugerido = B.ler(html(ATA))
    B.reescrever(sugerido[2], sugerido[2].texto + " (teste)", "s1", 1)
    try:
        B.sem_marcacao_de_rascunho(sugerido)
        checar(False, "com sugestão pendente, não arruma")
    except ValueError as exc:
        checar("sugest" in str(exc), "com sugestão pendente, não arruma", str(exc))


def teste_corpo_do_editor() -> None:
    print("\no texto do modelo vira documento sem asterisco")
    import api

    corpo = api._corpo_do_editor(["As providências incluem:", "* advertência por escrito;", "* prazo de **30 dias**.",
                                  "---", "Nada mais."])
    checar(corpo.startswith("<p>As providências incluem:</p><ul><li>advertência por escrito;</li>"
                            "<li>prazo de <b>30 dias</b>.</li></ul>") and "Nada mais." in corpo,
           "“* item” vira lista e “**x**” vira negrito", corpo)


def teste_entender() -> None:
    print("\no que o pedido é")
    bl = B.ler(html(ATA))
    e = AG.entender(bl, PEDIDO)
    checar(e.tipo == "editar" and not e.formatacao, "“Não precisa dizer que…, ele será advertido pelo…” é mudança", e.tipo)
    for frase in ("Tire os asteriscos", "remova esses asteriscos do texto", "tire o markdown", "limpe as marcas de rascunho"):
        e = AG.entender(bl, frase)
        checar(e.formatacao and e.tipo == "editar", f"“{frase}” é a marcação de rascunho", (e.tipo, e.formatacao))
    for frase in ("sim", "Sim, é este", "é esse", "esse mesmo", "isso mesmo"):
        checar(AG.entender(bl, frase).tipo == "confirmar", f"“{frase}” confirma")
    checar(AG.entender(bl, "Esta cláusula está confusa").tipo != "confirmar", "“Esta cláusula está confusa” não confirma")
    alvo = bloco(bl, "* O operador 'Martelo' será")
    checar(AG.relevantes(bl, "advertido por falta de companherismo")[:1] == [alvo.id],
           "a palavra com erro de digitação (“companherismo”) acha o trecho certo")


def teste_correcao_e_candidatos() -> None:
    print("\no pedido que não bateu com o texto")
    bl = B.ler(html(ATA))
    alvo = bloco(bl, "* O operador 'Martelo' será")
    errado = j(operacoes=[{"op": "substituir", "bloco": alvo.id, "de": "falta de companherismo",
                           "para": "abandono do serviço"}])

    # Nada entra nem na segunda tentativa: o motivo fica, e o trecho mais parecido vai para a resposta.
    falso = Falso([errado, j(operacoes=[]), j(operacoes=[], nao_fiz=["não sei qual trecho"])])
    _, r = rodada(falso, bl, PEDIDO)
    checar(len(falso.lido) == 3, "três chamadas: o pedido, a correção e a tentativa pelo sentido", len(falso.lido))
    checar(any("não achei" in f["motivo"] for f in r.falhas), "a correção vazia não apaga o motivo da falha",
           [f["motivo"] for f in r.falhas])
    checar("pelo sentido" in falso.lido[2][-1]["content"] and alvo.texto[:40] in falso.lido[2][-1]["content"],
           "a tentativa pelo sentido mostra o texto exato do trecho provável")
    checar(r.candidatos and r.candidatos[0]["bloco"] == alvo.id and r.candidatos[0]["rotulo"].startswith("PROVIDÊNCIAS"),
           "o trecho mais parecido, com o lugar", r.candidatos)
    texto = AG.resposta(r, "Ata da cooperativa")
    checar(texto.startswith("Não consegui fazer isso com segurança.\nO trecho mais parecido com o que você pediu é “")
           and "diga “sim”" in texto and "Não mudei nada" not in texto, "a resposta mostra o trecho e como confirmar", texto)

    # A tentativa pelo sentido reescreve o bloco: entra, e a falha some.
    novo = "O operador 'Martelo' será advertido pelo abandono do serviço;"
    falso = Falso([errado, j(operacoes=[]), j(operacoes=[{"op": "reescrever", "bloco": alvo.id, "texto": "* " + novo}])])
    _, r = rodada(falso, bl, PEDIDO)
    aceito = [b.texto for b in B.aceito(r.blocos)]
    checar(len(r.aplicadas) == 1 and not r.falhas and not r.candidatos and any("pelo abandono do serviço" in t for t in aceito),
           "a reescrita do bloco provável entra, e a resposta não fala em falha", (r.falhas, aceito[8:9]))

    # A recusa com motivo fica: sem segunda tentativa, sem "trecho mais parecido".
    falso = Falso([j(operacoes=[], nao_fiz=["a ata já diz que a advertência é pelo abandono do serviço"])])
    _, r = rodada(falso, bl, PEDIDO)
    checar(len(falso.lido) == 1 and not r.candidatos and "já diz" in AG.resposta(r, "Ata"),
           "o modelo que recusa e diz por quê não é forçado a mudar", AG.resposta(r, "Ata"))

    # A correção acerta o trecho: entra na segunda chamada.
    falso = Falso([errado, j(operacoes=[{"op": "substituir", "bloco": alvo.id,
                                         "de": "por sua falta de empenho e companheirismo",
                                         "para": "pelo abandono do serviço"}])])
    _, r = rodada(falso, bl, PEDIDO)
    checar(len(falso.lido) == 2 and len(r.aplicadas) == 1 and not r.falhas, "a correção com o trecho certo entra",
           (len(falso.lido), r.falhas))


def teste_concordancia() -> None:
    print("\na concordância na emenda")
    import edicao as ED

    def troca(texto: str, de: str, para: str, **k) -> tuple[str, str]:
        bl = B.ler(f"<p>{texto}</p>")
        r = ED.aplicar(bl, [{"op": "substituir", "bloco": bl[0].id, "de": de, "para": para, **k}], rodada=1)
        return B.aceito(r.blocos)[0].texto, (r.aplicadas[0]["resumo"] if r.aplicadas else "")

    casos = [
        ("advertido por sua falta de empenho e companheirismo;", "falta de empenho e companheirismo",
         "abandono do serviço", "advertido por seu abandono do serviço;"),
        ("O valor da multa é de R$ 100,00.", "multa", "aluguel", "O valor do aluguel é de R$ 100,00."),
        ("JOÃO TESTE, pela sua conduta.", "conduta", "comportamento", "JOÃO TESTE, pelo seu comportamento."),
        ("Paga a outra multa.", "multa", "valor", "Paga o outro valor."),
        ("O prazo é de 30 dias.", "prazo", "vigência", "A vigência é de 30 dias."),
        ("Na forma da lei.", "forma", "modo", "No modo da lei."),
        ("Recebe conforme o laudo de vistoria anexo.", "laudo de vistoria anexo", "vistoria fotográfica anexa",
         "Recebe conforme a vistoria fotográfica anexa."),
    ]
    for texto, de, para, esperado in casos:
        feito, _ = troca(texto, de, para)
        checar(feito == esperado, f"“{texto}” → “{esperado}”", feito)
    for texto, de, para in [("Referente a multa contratual.", "multa", "valor"),      # "a" pode ser preposição
                            ("A parte da contratante.", "contratante", "locador"),      # "contratante": os dois gêneros
                            ("Sua obrigação é esta.", "obrigação", "obrigações")]:      # número diferente
        feito, _ = troca(texto, de, para)
        checar(feito == texto.replace(de, para), f"sem certeza, só a troca pedida: “{feito}”")
    _, resumo = troca("advertido por sua falta de empenho;", "falta de empenho", "abandono do serviço")
    checar("“sua falta de empenho” → “seu abandono do serviço”" in resumo, "o resumo mostra a palavra que mudou junto",
           resumo)
    bl = B.ler("<p>Primeiro parágrafo.</p><p>O operador por sua abandono do serviço.</p>")
    r = ED.aplicar(bl, [{"op": "substituir", "texto": "sua abandono", "por": "seu abandono"}], rodada=1)
    checar(B.aceito(r.blocos)[1].texto == "O operador por seu abandono do serviço." and not r.falhas,
           "a operação escrita com outros nomes e sem o bloco (a segunda leitura) entra no único lugar possível",
           r.falhas)


def teste_numero_em_outro_assunto() -> None:
    print("\no número do pedido no lugar de outro assunto (loc-12 do banco, 14/10/2026)")
    sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))
    import bancada

    bl = bancada.documento("locacao")
    pedido = "Faça estes ajustes: 1) prazo de 36 meses; 2) vencimento do aluguel no dia 10; 3) caução de 2 aluguéis."
    falso = Falso([j(operacoes=[
        {"op": "substituir", "bloco": "b0b0019", "de": "3 (três) aluguéis", "para": "2 (dois) aluguéis"},
        {"op": "substituir", "bloco": "b0b0024", "de": "3 (três) aluguéis vigentes", "para": "2 (dois) aluguéis vigentes"}])])
    _, r = rodada(falso, bl, pedido)
    aceito = {b.id: b.texto for b in B.aceito(r.blocos)}
    checar("2 (dois) aluguéis" in aceito["b0b0019"] and "3 (três) aluguéis vigentes" in aceito["b0b0024"],
           "a caução muda; a multa da rescisão, que tem o mesmo “aluguéis”, fica", aceito["b0b0024"][:90])
    checar(any("o pedido fala de caução" in s for s in r.sugestoes), "e a resposta diz por quê", r.sugestoes)
    checar(AG._assuntos_das_quantidades("Mude o prazo da locação para 24 meses.") == {(24, "mes"): ["prazo", "locação"]},
           "o assunto da quantidade é o que vem antes dela no pedido")


def teste_segunda_leitura() -> None:
    print("\na segunda leitura (Max, Ultra)")
    bl = B.ler(html(ATA))
    alvo = bloco(bl, "* O operador 'Martelo' será")
    falso = Falso([
        j(operacoes=[{"op": "substituir", "bloco": alvo.id, "de": "por sua falta de empenho e companheirismo",
                      "para": "por sua abandono do serviço"}]),
        j(problemas=[{"bloco": alvo.id, "texto": "A mudança pedida não foi feita no bloco " + alvo.id + "."},
                     {"bloco": alvo.id, "texto": "“por sua abandono” está errado: o certo é “pelo abandono”."},
                     {"bloco": "", "texto": "Nenhum outro problema."}], operacoes=[])])
    _, r = rodada(falso, bl, PEDIDO, nivel="juiz")
    checar(len(falso.lido) == 2 and "concordância" in falso.lido[1][0]["content"],
           "a segunda leitura confere o português da frase mudada")
    checar([p["texto"] for p in r.segunda_leitura] == ["“por sua abandono” está errado: o certo é “pelo abandono”."]
           and r.segunda_leitura[0]["rotulo"].startswith("PROVIDÊNCIAS"),
           "fica o problema real, com o lugar; “a mudança não foi feita” e o item vazio não", r.segunda_leitura)
    checar(not any("revisão" in a for a in r.avisos), "e nada vira “Conferi: revisão…”", r.avisos)


def teste_pergunta_com_selecao() -> None:
    print("\na pergunta sobre o trecho selecionado")
    bl = B.ler(html(ATA))
    alvo = bloco(bl, "* O operador 'Martelo' será")
    msgs = AG.mensagens_de_pergunta(bl, "E isso aqui é o que?", "Ata", selecao={"bloco": alvo.id, "blocos": [alvo.id],
                                                                                "texto": alvo.texto},
                                    conversa="Advogado: " + PEDIDO + "\nPaulus: Não mudei nada.")
    ultimo = msgs[-1]["content"]
    checar("O ADVOGADO SELECIONOU ESTE TRECHO" in ultimo and "falta de empenho e companheirismo" in ultimo,
           "o modelo lê o trecho selecionado como o assunto da pergunta")
    checar("A CONVERSA ATÉ AQUI" in ultimo and "abandono ao serviço" in ultimo, "e a conversa até ali")


def eventos_sse(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for parte in texto.split("\n\n"):
        tipo = next((l[7:] for l in parte.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in parte.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


def teste_api() -> None:
    print("\npela API")
    import api
    import nuvem
    from fastapi.testclient import TestClient

    nuvem.chave = lambda estado, provedor: ""
    api.plano_mod.liberada = lambda estado: True
    local = TestClient(api.app, headers=api.cabecalho_local())
    falso = Falso([])
    api._modelo_do_editor = lambda *a, **k: (falso, {"onde": "teste", "modelo": "falso", "provedor": "", "motivo": ""})
    tid = local.post("/api/trabalhos", json={"pedido": "Faça uma ata da cooperativa"}).json()["id"]

    def novo_documento() -> int:
        return api.estado.documentos.criar("Ata da cooperativa", "texto", html(ATA), None, trabalho_id=tid,
                                           situacao="conversa")

    def editar(did: int, pedido: str, **k) -> tuple[list, dict]:
        resp = local.post(f"/api/documentos/{did}/editar", json={"pedido": pedido, "trabalho_id": tid, **k})
        ev = eventos_sse(resp.text)
        return ev, next((d for t, d in ev if t == "fim"), {})

    def alvo_de(did: int):
        return bloco(B.ler(api.estado.documentos.obter(did)["corpo"]), "* O operador 'Martelo' será")

    # A marca de rascunho na tela, o botão e o "tire os asteriscos".
    did = novo_documento()
    doc = local.get(f"/api/documentos/{did}").json()
    checar(doc.get("marcas_rascunho") == 3, "a tela sabe que há 3 parágrafos com marca de rascunho", doc.get("marcas_rascunho"))
    falso.lido.clear()
    ev, fim = editar(did, "Tire os asteriscos")
    corpo = api.estado.documentos.obter(did)["corpo"]
    checar(not falso.lido and fim.get("chamadas") == 0, "“tire os asteriscos” é regra: nenhum modelo chamado")
    checar("documento" in [t for t, _ in ev] and "<ul>" in corpo and "* " not in corpo and "**" not in corpo,
           "o documento ficou com a lista de verdade, e a folha é trocada inteira")
    checar(fim.get("texto", "").startswith("Arrumei a formatação: 3 linhas com asterisco viraram itens de lista e 1 trecho "
                                           "entre “**” ficou em negrito. Nenhuma palavra do texto mudou"),
           "a resposta diz o que foi arrumado", fim.get("texto"))
    voltou = local.post(f"/api/documentos/{did}/restaurar", json={"numero": fim["limpeza"]["versao_antes"]}).json()
    checar("* O operador" in voltou["documento"]["corpo"], "o Desfazer volta a versão de antes, do Histórico")
    r = local.post(f"/api/documentos/{did}/limpar-pdf", json={}).json()
    checar(r.get("frase", "").startswith("Arrumei a formatação") and "<ul>" in r.get("corpo", "")
           and "INTRODUÇÃO</p><p" in r.get("corpo", ""),
           "o botão “Arrumar a formatação” faz o mesmo, sem juntar os parágrafos da ata", r.get("frase"))
    checar(local.get(f"/api/documentos/{did}").json().get("marcas_rascunho") == 0, "e a marca some da tela")
    sem_ponto = api.estado.documentos.criar("Ata curta", "texto", html(["ATA DA REUNIÃO DE TESTE",
                                                                        "Presentes os cooperados abaixo",
                                                                        "* José Teste", "* Maria Exemplo",
                                                                        "Belo Horizonte, 10 de outubro de 2026",
                                                                        "Sem mais assuntos a tratar"]), None)
    r = local.post(f"/api/documentos/{sem_ponto}/limpar-pdf", json={}).json()
    checar(r.get("corpo", "").count("<p") == 4 and "Juntei" not in r.get("frase", ""),
           "fora do rascunho do PDF, o botão não junta os parágrafos sem ponto final", r.get("frase"))

    # O pedido que não mudou nada mostra o trecho parecido; "sim, é este" faz ali.
    did = novo_documento()
    alvo = alvo_de(did)
    errado = j(operacoes=[{"op": "substituir", "bloco": alvo.id, "de": "falta de companherismo", "para": "abandono"}])
    falso.respostas = [errado, j(operacoes=[]), j(operacoes=[])]
    _, fim = editar(did, PEDIDO)
    checar(fim.get("candidatos") and fim["candidatos"][0]["bloco"] == alvo.id and fim["texto"].startswith("Não consegui"),
           "nada feito: a resposta traz o trecho mais parecido", fim.get("texto"))
    falso.respostas = [j(operacoes=[{"op": "reescrever", "bloco": alvo.id,
                                     "texto": "* O operador 'Martelo' será advertido pelo abandono do serviço;"}])]
    falso.lido.clear()
    _, fim = editar(did, "Sim, é este")
    lido = falso.lido[0][-1]["content"] if falso.lido else ""
    checar("TRECHO SELECIONADO" in lido and alvo.id in lido and "abandono ao serviço" in lido,
           "o “sim” refaz o pedido de antes, no trecho que a resposta mostrou")
    checar(len(fim.get("mudancas") or []) == 1 and "pelo abandono do serviço" in api.estado.documentos.obter(did)["corpo"],
           "e a mudança entra, marcada", fim.get("texto"))
    falso.lido.clear()
    _, fim = editar(did, "tire os asteriscos")
    checar(not falso.lido and fim.get("texto", "").startswith("Antes de arrumar a formatação, decida as sugestões"),
           "com sugestão esperando decisão, “tire os asteriscos” pede a decisão antes (sem modelo)", fim.get("texto"))

    # "E isso aqui é o que?" com a linha selecionada, logo depois do pedido que não mudou nada: é o lugar.
    did = novo_documento()
    alvo = alvo_de(did)
    falso.respostas = [errado, j(operacoes=[]), j(operacoes=[])]
    editar(did, PEDIDO)
    falso.respostas = [j(operacoes=[{"op": "substituir", "bloco": alvo.id, "de": "por sua falta de empenho e companheirismo",
                                     "para": "pelo abandono do serviço"}])]
    falso.lido.clear()
    _, fim = editar(did, "E isso aqui é o que?", selecao={"bloco": alvo.id, "blocos": [alvo.id], "texto": alvo.texto})
    checar(falso.lido and "abandono ao serviço" in falso.lido[0][-1]["content"],
           "o modelo recebe o pedido de antes, não a pergunta")
    checar(fim.get("texto", "").startswith("Era este o trecho do seu pedido anterior - agora achei.")
           and len(fim.get("mudancas") or []) == 1, "e a resposta diz que achou e mostra a mudança", fim.get("texto"))

    # "É aqui", com outro trecho selecionado do que o sugerido: vale o que a pessoa selecionou.
    did2 = novo_documento()
    alvo2 = alvo_de(did2)
    outro = bloco(B.ler(api.estado.documentos.obter(did2)["corpo"]), "* O operador 'Martelo' terá")
    falso.respostas = [j(operacoes=[{"op": "substituir", "bloco": outro.id, "de": "falta", "para": "x"}]),
                       j(operacoes=[]), j(operacoes=[])]
    _, fim = editar(did2, PEDIDO)
    checar(fim.get("candidatos") and fim["candidatos"][0]["bloco"] in (alvo2.id, outro.id), "nada feito, com o trecho parecido")
    falso.respostas = [j(operacoes=[{"op": "reescrever", "bloco": alvo2.id,
                                     "texto": "* O operador 'Martelo' será advertido pelo abandono do serviço;"}])]
    falso.lido.clear()
    _, fim = editar(did2, "é aqui", selecao={"bloco": alvo2.id, "blocos": [alvo2.id], "texto": alvo2.texto})
    lido = falso.lido[0][-1]["content"] if falso.lido else ""
    checar(f"no bloco {alvo2.id}" in lido and "abandono ao serviço" in lido and len(fim.get("mudancas") or []) == 1,
           "“é aqui” com a seleção: o pedido de antes, no trecho que a pessoa selecionou", fim.get("texto"))
    falso.respostas = [j(operacoes=[])]
    falso.lido.clear()
    editar(did2, "isso aqui está repetido, tire", selecao={"bloco": outro.id, "blocos": [outro.id], "texto": outro.texto})
    lido = falso.lido[0][-1]["content"] if falso.lido else ""
    checar("está repetido, tire" in lido and "abandono ao serviço" not in lido.split("PEDIDO")[-1],
           "com verbo de mudança, é pedido novo (não o de antes)")

    # Depois de uma mudança que entrou, "e isso aqui?" com a seleção é pergunta sobre a seleção.
    falso.respostas = ["É o item que diz a advertência do operador."]
    falso.lido.clear()
    _, fim = editar(did, "E isso aqui?", selecao={"bloco": alvo.id, "blocos": [alvo.id], "texto": alvo.texto})
    lido = falso.lido[0][-1]["content"] if falso.lido else ""
    checar(fim.get("tipo") == "pergunta" and "O ADVOGADO SELECIONOU ESTE TRECHO" in lido and "A CONVERSA ATÉ AQUI" in lido,
           "a pergunta lê o trecho selecionado e a conversa", fim.get("tipo"))

    # A sugestão que a rodada anterior deu não volta.
    did = novo_documento()
    alvo = alvo_de(did)
    dica = "Vale registrar a data em que a advertência será entregue."
    for _ in range(2):
        falso.respostas = [j(operacoes=[{"op": "substituir", "bloco": alvo.id, "de": "30 dias", "para": "15 dias"}],
                             sugestoes=[dica])]
        _, fim = editar(did, "Mude o prazo do Martelo para 15 dias")
    checar(dica not in (fim.get("sugestoes") or []) and dica not in fim.get("texto", ""),
           "a mesma sugestão, na rodada seguinte, não aparece de novo", fim.get("sugestoes"))


def main() -> int:
    print("=" * 60)
    print("  A ata da cooperativa")
    print("=" * 60)
    teste_esboco()
    teste_marcacao()
    teste_corpo_do_editor()
    teste_entender()
    teste_correcao_e_candidatos()
    teste_concordancia()
    teste_numero_em_outro_assunto()
    teste_segunda_leitura()
    teste_pergunta_com_selecao()
    teste_api()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
