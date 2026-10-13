"""
O agente de edição (docs/PLANO-EDITOR.md, E5), sem modelo de verdade.

  - entender por regra: concluir, desfazer, aceitar e recusar tudo,
    renumerar, pergunta ou edição; o foco que a frase aponta ("a cláusula do
    prazo"), o limite ("só na cláusula do foro") e a troca entre aspas;
  - o JSON lido enquanto chega: cada operação sai assim que fecha, com chave,
    aspas e barra dentro do texto;
  - a rodada: as mudanças entrando uma a uma (remendos), a operação que não
    bateu com o texto volta ao modelo com o texto exato do bloco, a cláusula
    nova renumera as seguintes, a segunda leitura nos níveis Max e Ultra, a
    pergunta respondida pelo documento com o bloco citado;
  - a resposta diz o que foi aplicado, o que não deu e o que talvez devesse
    mudar junto - nada que o programa não tenha feito;
  - a rota /api/documentos/{id}/editar: grava o que a tela mandou, transmite
    as mudanças, grava a rodada e a versão de antes, registra na conversa; a
    nuvem fora do ar cai no modelo deste computador; desfazer, aceitar tudo e
    concluir pela frase; a nota da rodada (E9).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_agente.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-agente-editor-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))

import agente_de_edicao as AG  # noqa: E402
import bancada  # noqa: E402
import blocos as B  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Falso:
    """O modelo de mentira: responde a fila de respostas, em pedaços, e guarda o que leu."""

    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.lido: list[list[dict]] = []

    def __call__(self, mensagens, *, json_mode=False, max_tokens=4000, on_token=None):
        self.lido.append(mensagens)
        texto = self.respostas.pop(0) if self.respostas else "{}"
        if on_token:
            for i in range(0, len(texto), 17):
                on_token(texto[i:i + 17])
        return texto


def rodada(chamar, nome: str, pedido: str, **k):
    eventos = list(AG.rodar(chamar, bancada.documento(nome), pedido, rodada=1, titulo=nome, **k))
    fim = next(d["rodada"] for t, d in eventos if t == "fim")
    return eventos, fim


def teste_entender() -> None:
    print("entender por regra")
    bs = bancada.documento("locacao")
    casos = {"pode concluir": "concluir", "Conclua o documento.": "concluir", "está pronto, pode salvar": "concluir",
             "desfaça": "desfazer", "descarte a última alteração": "desfazer", "aceite todas": "aceitar",
             "recuse tudo": "recusar", "renumere as cláusulas": "renumerar", "Qual é o prazo da locação?": "pergunta",
             "o que diz a cláusula do foro?": "pergunta", "Mude o prazo para 24 meses": "editar",
             "você pode deixar a cláusula 5ª mais formal?": "editar", "Inclua uma cláusula de multa": "editar"}
    for frase, tipo in casos.items():
        e = AG.entender(bs, frase)
        checar(e.tipo == tipo, f"“{frase}” é {tipo}", e.tipo)
    e = AG.entender(bs, "Inclua uma cláusula de multa logo depois da cláusula do prazo")
    checar(e.foco == ["b0b0007", "b0b0008", "b0b0009"] and not e.restrito, "o foco: a cláusula do prazo, sem limite", e.foco)
    e = AG.entender(bs, "Troque “Belo Horizonte/MG” por “Belo Horizonte – MG” só na cláusula do foro")
    checar(e.restrito and e.foco == ["b0b0025", "b0b0026"], "“só na cláusula do foro” limita", e.foco)
    checar(e.regra == [{"op": "substituir", "bloco": "b0b0026", "de": "Belo Horizonte/MG", "para": "Belo Horizonte – MG"}],
           "a troca entre aspas é regra, no bloco certo", e.regra)
    e = AG.entender(bs, "troque “IGP-M/FGV” por “IPCA/IBGE”")
    checar(e.regra and e.regra[0]["op"] == "substituir_em_tudo", "entre aspas em vários blocos: em todo o documento", e.regra)
    e = AG.entender(bs, "mude a cláusula décima")
    checar(e.nao_existe == "Cláusula 10ª", "cláusula que não existe é dita", e.nao_existe)
    e = AG.entender(bs, "reescreva isto", selecao={"bloco": "b0b0021", "texto": "obrigando-se a devolvê-lo"})
    checar(e.restrito and e.foco == ["b0b0021"], "a seleção é limite")


def teste_leitor() -> None:
    print("o JSON lido enquanto chega")
    texto = ('{"entendi": "trocar {x}", "operacoes": [{"op": "substituir", "bloco": "b1", "de": "a \\"b\\" {c}", '
             '"para": "d"}, {"op": "apagar", "bloco": "b2"}], "nao_fiz": []}')
    leitor = AG.LeitorDeOperacoes()
    vistos = []
    momentos = []
    for i in range(0, len(texto), 5):
        novos = leitor.entrar(texto[i:i + 5])
        vistos += novos
        if novos:
            momentos.append(i)
    checar([o["op"] for o in vistos] == ["substituir", "apagar"], "as duas operações", vistos)
    checar(vistos[0]["de"] == 'a "b" {c}', "com aspas e chaves dentro do texto", vistos[0])
    checar(momentos and momentos[0] < len(texto) - 40, "a primeira sai antes de o JSON acabar", momentos)
    checar(AG.ler_json("```json\n" + texto + "\n```")["entendi"] == "trocar {x}", "ler o JSON com cerca de código")


def teste_rodada() -> None:
    print("a rodada")
    ops = {"entendi": "mudar o prazo", "operacoes": [
        {"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "24 (vinte e quatro) meses"},
        {"op": "substituir", "bloco": "b0b0008", "de": "30 de abril de 2029 (texto que não existe)", "para": "x"}],
        "nao_fiz": [], "sugestoes": ["a caução da Cláusula 4ª equivale a 3 aluguéis"], "lacunas": []}
    correcao = {"operacoes": [{"op": "substituir", "bloco": "b0b0008", "de": "30 de abril de 2029",
                               "para": "31 de outubro de 2028"}]}
    falso = Falso([json.dumps(ops, ensure_ascii=False), json.dumps(correcao, ensure_ascii=False)])
    eventos, r = rodada(falso, "locacao", "Mude o prazo da locação para 24 meses.")
    remendos = [d for t, d in eventos if t == "remendo"]
    checar(len(remendos) == 2 and len(r.aplicadas) == 2, "duas mudanças, cada uma num remendo", len(remendos))
    checar(len(falso.lido) == 2 and "texto EXATO de b0b0008" in falso.lido[1][-1]["content"],
           "a que não bateu voltou ao modelo com o texto exato do bloco")
    aceito = B.texto_puro(B.aceito(r.blocos))
    checar("24 (vinte e quatro) meses" in aceito and "31 de outubro de 2028" in aceito, "as duas aplicadas")
    texto = AG.resposta(r, "Locação")
    checar("Fiz 2 mudanças" in texto and "Cláusula 2ª" in texto, "a resposta diz o que mudou e onde", texto)
    checar("caução" in texto and "não mudei" in texto, "e o que talvez devesse mudar junto, sem ter mudado", texto)
    mensagens = falso.lido[0]
    checar("[b0b0008 · Cláusula 2ª]" in mensagens[1]["content"] and "ESBOÇO" in mensagens[1]["content"],
           "o modelo lê o documento com os nomes e o esboço")

    print("a cláusula nova e a numeração")
    ins = {"operacoes": [{"op": "inserir", "depois_de": "b0b0007", "blocos": [
        {"texto": "CLÁUSULA 3ª – DA RESCISÃO ANTECIPADA"}, {"texto": "Multa de 3 aluguéis proporcionais."}]}]}
    eventos, r = rodada(Falso([json.dumps(ins, ensure_ascii=False)]), "locacao", "Inclua uma cláusula de rescisão antecipada "
                        "depois da cláusula do prazo")
    aceito = [b.texto for b in B.aceito(r.blocos)]
    checar("CLÁUSULA 4ª – DO ALUGUEL E DOS ENCARGOS" in aceito and "CLÁUSULA 8ª – DO FORO" in aceito,
           "as seguintes renumeradas", [t for t in aceito if t.startswith("CLÁUSULA")])
    checar(any(a["tipo"] == "renumerar" for a in r.aplicadas), "a renumeração é uma sugestão própria")
    renum = [d for t, d in eventos if t == "remendo" and d["resumo"].startswith("Renumerei")]
    checar(renum and renum[0]["remendos"], "e chega à tela como remendo (não só no que é gravado)", renum)
    checar(aceito.index("CLÁUSULA 3ª – DA RESCISÃO ANTECIPADA") == aceito.index(
        "Parágrafo único. Findo o prazo ajustado, se a LOCATÁRIA continuar na posse do imóvel por mais de 30 (trinta) "
        "dias sem oposição do LOCADOR, a locação prorrogar-se-á por prazo indeterminado.") + 1,
        "a cláusula nova depois do último bloco da do prazo")

    print("número igual não é o mesmo dado (a regra 2, conferida pelo programa)")
    checar(AG._quantidades("30 (trinta) meses, 3 (três) aluguéis e 1 mês; R$ 2.400,00, art. 30 e 30 de abril")
           == {(30, "mes"), (3, "aluguel"), (1, "mes")}, "as quantidades com unidade, e só elas")
    ops = {"operacoes": [
        {"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "24 (vinte e quatro) meses"},
        {"op": "substituir", "bloco": "b0b0009", "de": "30 (trinta) dias", "para": "24 (vinte e quatro) dias"}]}
    eventos, r = rodada(Falso([json.dumps(ops, ensure_ascii=False)]), "locacao", "Mude o prazo da locação para 24 meses.")
    aceito = B.texto_puro(B.aceito(r.blocos))
    checar(len(r.aplicadas) == 1 and "24 (vinte e quatro) meses" in aceito and "por mais de 30 (trinta) dias" in aceito,
           "o 24 posto em dias, no parágrafo único, não entra", [a["resumo"] for a in r.aplicadas])
    texto = AG.resposta(r, "Locação")
    checar("ficou como estava" in texto and "24 meses" in texto and "não mudei" in texto,
           "e a resposta diz que ficou como estava, para o advogado decidir", texto)
    ops = {"operacoes": [{"op": "substituir", "bloco": "b0b0009", "de": "30 (trinta) dias", "para": "60 (sessenta) dias"}]}
    eventos, r = rodada(Falso([json.dumps(ops, ensure_ascii=False)]), "locacao",
                        "No parágrafo único da cláusula 2ª, o prazo passa a ser de 60 dias.")
    checar(len(r.aplicadas) == 1 and not r.sugestoes, "na unidade do pedido, a troca passa", r.sugestoes)

    print("pedaços separados no mesmo bloco")
    junto = {"operacoes": [{"op": "substituir", "bloco": "b0c0005", "de": "confessar, renunciar ao direito sobre o qual se "
                            "funda a ação", "para": ""}]}
    separado = {"operacoes": [{"op": "substituir", "bloco": "b0c0005", "de": "confessar, ", "para": ""},
                              {"op": "substituir", "bloco": "b0c0005", "de": "renunciar ao direito sobre o qual se funda a "
                               "ação, ", "para": ""}]}
    falso = Falso([json.dumps(junto, ensure_ascii=False), json.dumps(separado, ensure_ascii=False)])
    eventos, r = rodada(falso, "procuracao", "Retire os poderes para confessar e para renunciar ao direito.")
    checar(len(falso.lido) == 2 and "os pedaços estão no bloco, mas separados" in falso.lido[1][-1]["content"],
           "a correção diz que os pedaços existem, mas não juntos")
    aceito = B.texto_puro(B.aceito(r.blocos))
    checar(len(r.aplicadas) == 2 and "confessar" not in aceito and "renunciar ao direito" not in aceito,
           "e as duas retiradas entram, cada uma no seu lugar", [a["resumo"] for a in r.aplicadas])

    print("a mesma troca duas vezes não vira “ALVES ALVES”")
    troca = {"op": "substituir", "bloco": "b0b0003", "de": "MARIANA COSTA RIBEIRO", "para": "MARIANA COSTA RIBEIRO ALVES"}
    em_tudo = {"op": "substituir_em_tudo", "de": "MARIANA COSTA RIBEIRO", "para": "MARIANA COSTA RIBEIRO ALVES"}
    falso = Falso([json.dumps({"operacoes": [troca, troca, em_tudo]}, ensure_ascii=False)])
    eventos, r = rodada(falso, "locacao", "A locatária se chama Mariana Costa Ribeiro Alves, corrija o nome dela.")
    aceito = B.texto_puro(B.aceito(r.blocos))
    checar("ALVES ALVES" not in aceito and "MARIANA COSTA RIBEIRO ALVES, brasileira" in aceito
           and aceito.count("MARIANA COSTA RIBEIRO ALVES") == aceito.count("MARIANA COSTA RIBEIRO"),
           "o trecho que já está como o novo não é trocado de novo", aceito[:200])
    checar(not r.falhas and len(falso.lido) == 1, "e não é falha: nada de correção à toa", [f["motivo"] for f in r.falhas])

    print("o dado novo do pedido que não entrou")
    checar([d[0] for d in AG.dados_do_pedido("O comprador é casado com Juliana Torres Pereira; o preço passa a "
                                             "R$ 900.000,00 em 12 parcelas, a partir de 20 de agosto de 2026.")]
           == ["Juliana Torres Pereira", "R$ 900.000,00", "20 de agosto de 2026", "12 parcelas"], "os dados do pedido")
    checar([d[0] for d in AG.dados_do_pedido("Troque Belo Horizonte por Contagem.")] == ["Belo Horizonte"],
           "a maiúscula do começo da frase não vira nome")
    checar(AG.dados_do_pedido("No Parágrafo Único da Cláusula Segunda, cite a Lei do Inquilinato.") == [],
           "o que aponta o lugar ou a lei não é dado para escrever")
    pedido_cv = "O comprador é casado sob comunhão parcial com Juliana Torres Pereira, ajuste a qualificação dele."
    sem_nome = {"operacoes": [{"op": "substituir", "bloco": "b0a0003", "de": "solteiro",
                               "para": "casado sob o regime da comunhão parcial de bens"}]}
    com_nome = {"operacoes": [{"op": "substituir", "bloco": "b0a0003", "de": "comunhão parcial de bens",
                               "para": "comunhão parcial de bens com JULIANA TORRES PEREIRA"}]}
    falso = Falso([json.dumps(sem_nome, ensure_ascii=False), json.dumps(com_nome, ensure_ascii=False)])
    eventos, r = rodada(falso, "compra_venda", pedido_cv)
    checar(len(falso.lido) == 2 and "“Juliana Torres Pereira”" in falso.lido[1][-1]["content"],
           "o nome que não entrou volta ao modelo")
    checar("com JULIANA TORRES PEREIRA" in B.texto_puro(B.aceito(r.blocos)) and not r.nao_fiz,
           "e entra no texto, marcado", r.nao_fiz)
    falso = Falso([json.dumps(sem_nome, ensure_ascii=False), json.dumps({"operacoes": []})])
    eventos, r = rodada(falso, "compra_venda", pedido_cv)
    checar("o pedido traz “Juliana Torres Pereira”, que não entrou no texto" in AG.resposta(r, "Compra e venda"),
           "se nem assim entra, a resposta diz", AG.resposta(r, "Compra e venda"))

    print("a segunda leitura (Max)")
    rev = {"ok": False, "problemas": ["a data de término não acompanhou o prazo"],
           "operacoes": [{"op": "substituir", "bloco": "b0b0008", "de": "30 de abril de 2029", "para": "31 de outubro de 2028"}]}
    um = {"operacoes": [{"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "24 (vinte e quatro) meses"}]}
    falso = Falso([json.dumps(um, ensure_ascii=False), json.dumps(rev, ensure_ascii=False)])
    eventos, r = rodada(falso, "locacao", "prazo de 24 meses", nivel="juiz")
    checar(len(falso.lido) == 2 and "revisor" in falso.lido[1][0]["content"], "no nível Juiz, a segunda leitura")
    checar(any(a["resumo"].startswith("Revisão:") for a in r.aplicadas) and "31 de outubro de 2028" in
           B.texto_puro(B.aceito(r.blocos)), "a correção da revisão entra marcada")
    checar(any("revisão:" in a for a in r.avisos), "e o problema que ela achou é dito")
    falso = Falso([json.dumps(um, ensure_ascii=False)])
    rodada(falso, "locacao", "prazo de 24 meses", nivel="advogado")
    checar(len(falso.lido) == 1, "no Advogado, sem segunda leitura")

    print("a pergunta")
    falso = Falso(["O prazo é de 30 (trinta) meses [b0b0008 · Cláusula 2ª], até 30 de abril de 2029 [b0b0008]."])
    eventos, r = rodada(falso, "locacao", "Qual é o prazo da locação?")
    tokens = "".join(d["t"] for t, d in eventos if t == "token")
    checar(r.tipo == "pergunta" and tokens.startswith("O prazo é de"), "a resposta chega ao vivo")
    checar(r.citados == ["b0b0008"] and "[b0b0008]" in r.resposta and "·" not in r.resposta, "o bloco citado", r.resposta)
    checar(B.html(r.blocos) == B.html(bancada.documento("locacao")), "a pergunta não muda o documento")

    print("a regra sem modelo")
    falso = Falso([])
    eventos, r = rodada(falso, "compra_venda", "Troque “Belo Horizonte/MG” por “Belo Horizonte – MG” só na cláusula do foro")
    checar(not falso.lido and len(r.aplicadas) == 1 and r.aplicadas[0]["ids"] == ["b0a0021"], "a troca entre aspas, sem modelo")
    eventos, r = rodada(Falso([]), "locacao", "renumere as cláusulas")
    checar(r.tipo == "renumerar" and not r.aplicadas and "em sequência" in AG.resposta(r), "renumerar o que já está em ordem")


def teste_rota() -> None:
    print("a rota /api/documentos/{id}/editar")
    import requests

    import api
    import llama_client
    import nuvem
    from fastapi.testclient import TestClient

    respostas: list[str] = []
    chamadas: list[dict] = []

    def nuvem_falsa(metodo, url, cabecalhos, corpo, stream):
        chamadas.append(corpo)
        texto = respostas.pop(0) if respostas else "{}"
        if texto == "ERRO":
            return SimpleNamespace(status_code=402, json=lambda: {"erro": "sem crédito"}, text="sem crédito", headers={},
                                   close=lambda: None)
        pedacos = [texto[i:i + 23] for i in range(0, len(texto), 23)]

        class R:
            status_code = 200
            headers = {"x-paulus-modelo": "meta-llama/Llama-3.3-70B-Instruct"}

            def iter_lines(self, decode_unicode=True):
                for p in pedacos:
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 50}})
                yield "data: [DONE]"

            def close(self):
                pass
        return R()

    locais: list[dict] = []

    def ollama_post(url, json=None, stream=False, timeout=None, **k):
        locais.append(json)
        conteudo = respostas.pop(0) if respostas else "{}"
        corpo = {"message": {"content": conteudo}, "done": True, "prompt_eval_count": 10, "eval_count": 10}
        linhas = [__import__("json").dumps(corpo)]
        return SimpleNamespace(status_code=200, json=lambda: corpo, raise_for_status=lambda: None,
                               iter_lines=lambda decode_unicode=True: iter(linhas), close=lambda: None)

    nuvem.PEDIR["fn"] = nuvem_falsa
    llama_client.requests = SimpleNamespace(post=ollama_post, get=lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: {"models": [{"name": "falso:1b"}]}, raise_for_status=lambda: None),
        exceptions=requests.exceptions)
    api.estado.client = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.check_ollama = lambda *a, **k: (True, "")
    api.plano_mod.liberada = lambda estado: True
    nuvem.chave = lambda estado, provedor: "chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"provedor": "paulus", "modelo": "meta-llama/Llama-3.3-70B-Instruct", "mascarar": True,
                                       "tarefas": {"conversa": True}}
    local = TestClient(api.app, headers=api.cabecalho_local())

    tid = local.post("/api/trabalhos", json={"pedido": "locação"}).json()["id"]
    corpo = (bancada.CORPUS / "locacao.html").read_text(encoding="utf-8")
    did = api.estado.documentos.criar("Contrato de locação", "texto", corpo, None, trabalho_id=tid, situacao="conversa")
    doc = local.get(f"/api/documentos/{did}").json()

    def editar(pedido: str, **extra) -> list[tuple[str, dict]]:
        r = local.post(f"/api/documentos/{did}/editar", json={"pedido": pedido, "trabalho_id": tid, **extra})
        return [(t, d) for t, d in _eventos(r.text)]

    ops = {"entendi": "mudar o prazo", "operacoes": [
        {"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "24 (vinte e quatro) meses"}],
        "nao_fiz": [], "sugestoes": [], "lacunas": []}
    respostas.append(json.dumps(ops, ensure_ascii=False))
    tela = doc["corpo"].replace("Rua Jacuí, nº 815", "Rua Jacuí, nº 817")
    ev = editar("Mude o prazo da locação para 24 meses.", corpo=tela, revisao=doc["revisao"])
    tipos = [t for t, _ in ev]
    checar("remendo" in tipos and tipos[-1] == "fim", "transmite a mudança e o fim", tipos)
    fim = ev[-1][1]
    checar(fim["pendentes"] == 1 and fim["mudancas"][0]["resumo"].startswith("Cláusula 2ª"), "uma sugestão pendente", fim)
    checar(fim["onde"]["onde"] == "nuvem", "escrito na nuvem", fim["onde"])
    gravado = local.get(f"/api/documentos/{did}").json()
    checar("nº 817" in gravado["corpo"] and '<ins data-s="' in gravado["corpo"], "o que a tela mandou e a sugestão, gravados")
    versoes = local.get(f"/api/documentos/{did}/versoes").json()["versoes"]
    checar(any((v.get("nota") or "").startswith("antes da rodada 1") for v in versoes) and
           any((v.get("nota") or "").startswith("rodada 1") for v in versoes), "a versão de antes e a da rodada")
    t = local.get(f"/api/trabalhos/{tid}").json()
    ultima = t["mensagens"][-1]
    checar(ultima["autor"] == "paulus" and (ultima.get("feito") or {}).get("tipo") == "alteracao" and
           (ultima["feito"]["mudancas"][0]["ids"] == ["b0b0008"]), "a conversa registra a mudança e o lugar", ultima.get("feito"))
    checar(t["mensagens"][-2]["texto"] == "Mude o prazo da locação para 24 meses.", "e o pedido, como fala da pessoa")
    rodadas = local.get(f"/api/documentos/{did}/rodadas").json()["rodadas"]
    checar(len(rodadas) == 1 and rodadas[0]["resultado"]["resumos"], "a rodada registrada")

    print("desfazer, aceitar, a nota e concluir pela frase")
    ev = editar("desfaça")
    checar(ev[-1][1]["pendentes"] == 0 and "Desfiz" in ev[-1][1]["texto"], "desfazer recusa a última resposta", ev[-1][1])
    checar("30 (trinta) meses" in local.get(f"/api/documentos/{did}").json()["corpo"], "o prazo voltou")
    respostas.append(json.dumps(ops, ensure_ascii=False))
    editar("Mude o prazo da locação para 24 meses.")
    ev = editar("aceite todas")
    gravado = local.get(f"/api/documentos/{did}").json()
    checar("24 (vinte e quatro) meses" in gravado["corpo"] and gravado["pendentes"] == 0, "aceitar todas")
    r = local.post(f"/api/documentos/{did}/rodadas/2/avaliar", json={"nota": -1, "comentario": "devia ajustar a data"})
    linhas = (api.DADOS_DIR / "medicao" / "editor-avaliacoes.jsonl").read_text(encoding="utf-8").splitlines()
    checar(r.status_code == 200 and "devia ajustar a data" in linhas[-1], "a nota ruim vira caso para o banco de provas")
    ev = editar("pode concluir")
    tipos = [t for t, _ in ev]
    checar("concluir" in tipos and ev[-1][1]["tipo"] == "concluir", "concluir pela frase abre o cartão", tipos)
    checar(local.get(f"/api/documentos/{did}").json()["situacao"] == "conversa", "e não conclui sem o cartão")

    print("a nuvem fora do ar: o modelo deste computador")
    respostas.extend(["ERRO", json.dumps({"operacoes": [{"op": "substituir", "bloco": "b0b0011", "de": "dia 5 (cinco)",
                                                          "para": "dia 10 (dez)"}]}, ensure_ascii=False)])
    ev = editar("O vencimento passa para o dia 10.")
    fim = ev[-1][1] if ev and ev[-1][0] == "fim" else {"onde": {}, "ev": ev[-3:]}
    checar(fim["onde"].get("onde") == "computador" and fim["onde"].get("motivo"), "a reserva é este computador, dizendo por quê",
           fim)
    checar("dia 10 (dez)" in B.texto_puro(B.aceito(B.ler(local.get(f"/api/documentos/{did}").json()["corpo"]))),
           "e a mudança entra do mesmo jeito, marcada")

    print("o jeito do escritório (E7)")
    api.estado.clausulas.gravar("Foro do escritório", "Fica eleito o foro da Comarca de Belo Horizonte/MG, com renúncia "
                                "expressa a qualquer outro, por mais privilegiado que seja.")
    antes_n = len(chamadas)
    respostas.append(json.dumps({"operacoes": []}))
    editar("use a cláusula de foro do escritório")
    lido = json.dumps(chamadas[antes_n:], ensure_ascii=False)
    checar("CLÁUSULAS DO ESCRITÓRIO" in lido and "renúncia expressa a qualquer outro" in lido,
           "a cláusula da casa vai ao modelo quando o pedido a chama")
    antes_n = len(chamadas)
    respostas.append(json.dumps({"operacoes": []}))
    editar("Mude o vencimento para o dia 15.")
    checar("CLÁUSULAS DO ESCRITÓRIO" not in json.dumps(chamadas[antes_n:], ensure_ascii=False),
           "e não vai quando o pedido não chama")
    checar("O QUE JÁ FOI PEDIDO E DECIDIDO NESTE DOCUMENTO" in json.dumps(chamadas[antes_n:], ensure_ascii=False),
           "a memória do documento (as rodadas de antes) vai junto")

    print("a pergunta pela rota")
    respostas.append("O aluguel é de R$ 2.400,00 [b0b0011].")
    ev = editar("Qual é o valor do aluguel?")
    fim = ev[-1][1]
    checar(fim["tipo"] == "pergunta" and fim["citados"] == [{"id": "b0b0011", "rotulo": "Cláusula 3ª"}],
           "o bloco citado, com o rótulo", fim["citados"])
    checar("".join(d.get("t", "") for t, d in ev if t == "token").startswith("O aluguel"), "a resposta ao vivo")


def _eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


if __name__ == "__main__":
    teste_entender()
    teste_leitor()
    teste_rodada()
    teste_rota()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        sys.exit(1)
    print("todos os testes passaram")
