"""
A conversa que continua do que acabou de ser dito (caso real de 13/10/2026,
conversa "Contrato Obedi Lourenço", src/conversa_continua.py):

  - "O que você acha dele? Está bom assim?": a instrução de revisão como
    colega vai à nuvem, e a frase "deve ser feita por um profissional
    qualificado, como um advogado" sai da resposta;
  - a instrução da nuvem não manda consultar advogado;
  - "Em quais cláusulas esses pontos aparecem?": a última resposta vai
    INTEIRA, com a instrução de continuidade (antes, ~600 tokens cortavam a lista);
  - "Cláusula 3ª, Parágrafo 1º" que o contrato não tem, e a "Cláusula 12ª"
    inexistente, ficam marcadas (citacoes.conferir_clausulas);
  - "Então vamos ajustar o que falta. Me pergunte aqui": uma pergunta por
    ponto da última resposta, no cartão de perguntas, sem modelo e sem resumo;
  - a resposta (pelo cartão ou numerada na caixa) vira o cartão "aplicar os
    ajustes", e nada é gravado antes do sim; o sim (/fazer) abre a cópia
    editável do documento - ou o rascunho do trabalho redigido aqui - e
    devolve o pedido para o assistente do editor.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_conversa_continua.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-continua-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

import citacoes  # noqa: E402
import conversa_continua as cc  # noqa: E402
import instrucao_nuvem  # noqa: E402

_falhas: list[str] = []

CONTRATO_NOME = "CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO.txt"
CONTRATO = """CONTRATO DE COMPRA E VENDA DE IMÓVEL URBANO

CLÁUSULA 1ª – DO OBJETO
O presente contrato tem como objeto a venda do imóvel urbano medindo 360 m², no Setor Atlanta, São Félix do Xingu.

CLÁUSULA 2ª – DO PREÇO E FORMA DE PAGAMENTO
O preço é de R$ 30.000,00, pago em 2 parcelas de R$ 15.000,00.

CLÁUSULA 3ª – DA ENTREGA DO IMÓVEL
O Vendedor entregará o imóvel ao Comprador de forma imediata, após a assinatura deste instrumento, livre de ônus.

CLÁUSULA 4ª – DAS OBRIGAÇÕES DO VENDEDOR
I. Entregar o imóvel;
II. Garantir que o imóvel esteja livre de débitos.

CLÁUSULA 10ª – DA RESOLUÇÃO DE DISPUTAS
Fica eleito o foro da Comarca de São Félix do Xingu-PA.
"""
PONTOS = [
    "Incluir uma cláusula que especifique o prazo para a entrega do imóvel e as consequências em caso de atraso.",
    "Estabelecer um mecanismo para resolver disputas ou controvérsias que possam surgir durante a vigência do contrato.",
    "Incluir uma cláusula que especifique as responsabilidades das partes em caso de danos ou prejuízos causados ao imóvel.",
    "Estabelecer um prazo para a devolução do sinal ou das parcelas pagas em caso de rescisão do contrato.",
]
RESSALVA = ("No entanto, é importante notar que a análise de um contrato deve ser feita por um profissional qualificado, "
            "como um advogado, que pode avaliar se o contrato atende às necessidades específicas das partes.")
OPINIAO = ("O contrato aborda os principais aspectos de uma compra e venda de imóvel urbano: objeto, preço, entrega e foro. "
           + "Faltam regras importantes para o vendedor, que é o cliente do escritório. " * 25 + "\n\n" + RESSALVA + "\n\n"
           "Pontos que podem melhorar:\n\n" + "\n".join("* " + p for p in PONTOS) + "\n\n"
           "A Cláusula 12ª trata da multa por inadimplemento.")
ONDE = ("Os pontos aparecem assim no contrato:\n\n"
        "1. **Prazo de entrega do imóvel e consequências do atraso**: a Cláusula 3ª fala da entrega imediata; a Cláusula 3ª, "
        "Parágrafo 1º, considera a entrega feita no pagamento da entrada.\n"
        "2. **Mecanismo de resolução de disputas**: a Cláusula 10ª elege o foro de São Félix do Xingu.\n"
        "3. **Responsabilidade por danos ao imóvel**: a Cláusula 4ª, Inciso IV, trata disso.\n"
        "4. **Prazo de devolução do sinal ou das parcelas na rescisão**: não há cláusula sobre isso.")


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


class Nuvem:
    """A nuvem de mentira: devolve as respostas da fila, na ordem, e guarda o que recebeu."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.respostas: list[str] = []

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        self.chamadas.append({"url": url, "corpo": corpo})
        sistema = " ".join(m["content"] for m in (corpo or {}).get("messages") or [] if m["role"] == "system")
        if "Você faz a triagem" in sistema:
            texto = '{"assunto": "documento", "documentos": [], "em_tese": "", "dispositivos": []}'
        else:
            texto = self.respostas.pop(0) if self.respostas else "Resposta comum da nuvem."
        pedacos = [texto[:40], texto[40:]]

        class R:
            status_code = 200

            def json(self):
                return {}

            def iter_lines(self, decode_unicode=True):
                for p in pedacos:
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
                yield "data: [DONE]"

            def close(self):
                pass
        return R()

    def respostas_ao_modelo(self) -> list[dict]:
        """As chamadas de resposta (sem a triagem)."""
        return [c for c in self.chamadas
                if "Você faz a triagem" not in " ".join(m["content"] for m in c["corpo"]["messages"] if m["role"] == "system")]


class Ollama:
    def __init__(self) -> None:
        self.pedidos = 0

    def post(self, *a, **k):
        self.pedidos += 1
        raise RuntimeError("o modelo local não devia ser chamado")

    def get(self, *a, **k):
        return SimpleNamespace(status_code=200, json=lambda: {"models": [{"name": "falso:1b"}]}, raise_for_status=lambda: None)


# ------------------------------------------------------------ sem servidor

def test_regras() -> None:
    print("\nas regras, sem servidor")
    checar(cc.pede_opiniao("O que você acha dele? Está bom assim?"), "“o que você acha? está bom?” é opinião")
    checar(cc.pede_opiniao("revise criticamente o contrato"), "“revise criticamente” é opinião")
    checar(not cc.pede_opiniao("qual o valor do contrato?"), "pergunta de valor não é opinião")
    frase3 = "Então vamos ajustar o que falta. Me pergunte aqui e eu te digo como será feito"
    checar(cc.pede_perguntas(frase3) and cc.refere_a_anterior(frase3), "“vamos ajustar o que falta. Me pergunte” pede perguntas")
    for f in ("faça as perguntas", "pode perguntar", "me pergunta o que precisar"):
        checar(cc.pede_perguntas(f), f"“{f}” pede perguntas")
    checar(not cc.pede_perguntas("qual a pergunta que o juiz fez?"), "“a pergunta que o juiz fez” não")
    for f in ("esses pontos aparecem onde?", "faça isso", "isso que você sugeriu cabe aqui?", "aplique as sugestões"):
        checar(cc.refere_a_anterior(f), f"“{f}” se refere à resposta anterior")
    checar(cc.pede_aplicar("aplique as sugestões") and not cc.pede_aplicar("aplique a multa de 2%"), "“aplique as sugestões”")

    checar(cc.pontos_de(OPINIAO) == PONTOS, "os 4 pontos da lista", cc.pontos_de(OPINIAO))
    checar([p.split(":")[0] for p in cc.pontos_de(ONDE)][0] == "Prazo de entrega do imóvel e consequências do atraso",
           "com título em negrito, fica o título", cc.pontos_de(ONDE)[:1])
    qs = cc.perguntas_dos_pontos(PONTOS)
    checar(qs[0]["pergunta"] == "O prazo para a entrega do imóvel e as consequências em caso de atraso: como deve ficar?"
           and qs[3]["pergunta"].startswith("Prazo para a devolução") and all(q["porque"] for q in qs),
           "uma pergunta por ponto, com o ponto como porquê", [q["pergunta"] for q in qs])
    estado_a = cc.novo(PONTOS, {}, "x")
    livres = cc.respostas_livres("1. 30 dias, multa de 2% ao mês\n3. o comprador responde\nsalvo caso fortuito", estado_a)
    checar([(r["id"], r["resposta"]) for r in livres] == [("a1", "30 dias, multa de 2% ao mês"),
                                                          ("a3", "o comprador responde salvo caso fortuito")],
           "a resposta numerada na caixa vai para cada pergunta", livres)

    print("\nquem lê é advogado")
    for nome, texto in (("a instrução da nuvem", instrucao_nuvem.instrucao()), ("a instrução de opinião", cc.INSTRUCAO_OPINIAO)):
        plano = cc._plano(texto)
        checar("consulte um advogado" not in plano and "profissional qualificado" not in plano
               and "consultar um advogado" not in plano, f"{nome} não manda consultar advogado")
    checar("colega" in cc._plano(instrucao_nuvem.instrucao()) and "colega" in cc._plano(cc.INSTRUCAO_OPINIAO),
           "e fala como colega")
    limpo, tiradas = cc.sem_ressalva_de_leigo(OPINIAO)
    checar(tiradas == [RESSALVA] and "profissional qualificado" not in limpo and all(p in limpo for p in PONTOS),
           "a ressalva de leigo sai, a análise fica", tiradas)
    for frase in ("Portanto, é recomendável que um advogado especializado em direito imobiliário revise o contrato.",
                  "Consulte um advogado de sua confiança."):
        checar(cc.sem_ressalva_de_leigo("O prazo é de 15 dias. " + frase)[1], f"sai: “{frase[:50]}…”")
    for frase in ("A procuração dá ao advogado poderes para revisar o contrato.",
                  "O advogado do vendedor deve assinar como testemunha."):
        checar(not cc.sem_ressalva_de_leigo(frase)[1], f"fica: “{frase[:50]}…”")

    print("\ncláusula, parágrafo e inciso conferidos no documento")
    texto, marcadas = citacoes.conferir_clausulas(
        "A Cláusula 12ª trata da multa. A Cláusula 3ª, Parágrafo 1º, diz X. A Cláusula 4ª, Inciso II, diz Y. "
        "A Cláusula 4ª, Inciso IV, diz Z. A Cláusula Décima elege o foro.", [CONTRATO])
    checar("Cláusula 12ª [não encontrada no documento]" in texto, "a Cláusula 12ª inexistente fica marcada", texto)
    checar("Parágrafo 1º [esse parágrafo não está no documento]" in texto, "o parágrafo que não existe, marcado")
    checar("Inciso IV [esse inciso não está no documento]" in texto and "Inciso II [" not in texto,
           "o inciso IV marcado, o II não")
    checar("Décima elege" in texto and len(marcadas) == 3, "a cláusula décima (por extenso) existe", marcadas)
    checar(citacoes.conferir_clausulas("A Cláusula 12ª trata da multa.", ["Um texto sem cláusulas numeradas."])[1] == [],
           "documento sem cláusulas numeradas: nada a conferir")


# ------------------------------------------------------------ na tela

def test_tela() -> None:
    """Na tela: "me pergunte" mostra o cartão; respondido, o de aplicar; o sim abre o editor."""
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    sys.path.insert(0, str(RAIZ / "tests"))
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    t = e.trabalhos.criar("Ajustes na tela")
    t.dizer("pessoa", "Vamos criar um contrato de compra e venda")
    t.dizer("paulus", "CONTRATO DE COMPRA E VENDA\n\nCLÁUSULA 1ª – DO OBJETO\nO lote urbano da tela.",
            proposta={"tipo": "levar_ao_editor", "titulo": "CONTRATO NA TELA", "campos": {}})
    t.dizer("pessoa", "O que você acha dele?")
    t.dizer("paulus", "Faltam dois pontos:\n\n- Prever multa por atraso no pagamento.\n- Definir o foro da comarca do imóvel.")
    e.trabalhos.salvar(t)
    porta = _porta_livre()
    _subir_servidor(porta)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1600, "height": 1000})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.evaluate(f"() => abrirTrabalho('{t.id}')")
        pag.wait_for_timeout(800)
        pag.fill("#pedido", "Então vamos ajustar o que falta. Me pergunte aqui")
        pag.click("#enviar")
        try:
            pag.wait_for_selector(".proposta.entrevista .ent-q", timeout=15000)
            perguntas = pag.evaluate("() => [...document.querySelectorAll('.proposta.entrevista .ent-titulo')]"
                                     ".map(x => x.textContent).filter(x => x.includes('como deve ficar'))")
        except Exception as exc:  # noqa: BLE001
            perguntas = ["não apareceu: " + str(exc)[:60]]
        checar(len(perguntas) == 2, "o cartão com as 2 perguntas", perguntas)
        campos = pag.query_selector_all(".proposta.entrevista .ent-q textarea, .proposta.entrevista .ent-q input[type=text]")
        if campos:
            campos[0].fill("multa de 10% sobre a parcela")
        pag.click('[data-ent-acao="responder"]')
        try:
            pag.wait_for_selector('[data-prop="aplicar-ajustes"]', timeout=15000)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        checar(ok, "respondido, o cartão “Aplicar no editor”")
        if ok:
            pag.click('[data-prop="aplicar-ajustes"]')
            try:
                pag.wait_for_selector("#editor-lado #dp-folha", timeout=15000)
                aberto = pag.evaluate("() => document.querySelector('#dp-folha').textContent")
            except Exception as exc:  # noqa: BLE001
                aberto = "não abriu: " + str(exc)[:60]
            checar("O lote urbano da tela" in aberto, "o sim abre o rascunho do trabalho no editor", aberto[:100])
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


# ------------------------------------------------------------ pela conversa

def main() -> int:
    print("=" * 60)
    print("  A conversa que continua do que acabou de ser dito")
    print("=" * 60)
    test_regras()

    import requests

    import api
    import llama_client
    import nuvem
    from fastapi.testclient import TestClient

    fake = Nuvem()
    nuvem.PEDIR["fn"] = fake
    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    api.estado.client = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.check_ollama = lambda *a, **k: (True, "")
    api.plano_mod.liberada = lambda estado: True
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "trechos", "denso": False})
    api.estado.modelo_para = lambda tarefa: "falso:1b"
    nuvem.chave = lambda estado, provedor: "di-chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    local = TestClient(api.app, headers=api.cabecalho_local())
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / CONTRATO_NOME).write_text(CONTRATO, encoding="utf-8")
    api.estado.recarregar()

    def n_documentos() -> int:
        return int((api.estado.base.um("SELECT COUNT(*) AS n FROM documentos") or {}).get("n") or 0)

    def perguntar(tid: str, frase: str, **extra) -> dict:
        r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": frase, "nuvem": True,
                                                                "profundidade": "ministro", **extra})
        ev = eventos(r.text)
        t = local.get(f"/api/trabalhos/{tid}").json()
        return {"status": r.status_code, "proposta": next((d for k, d in ev if k == "proposta"), {}),
                "salvo": t["mensagens"][-1], "eventos": [k for k, _ in ev], "trabalho": t}

    print("\n1. “O que você acha dele? Está bom assim?” (o contrato no escopo, a nuvem)")
    tid = local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]
    fake.respostas = [OPINIAO]
    n0 = len(fake.respostas_ao_modelo())
    r = perguntar(tid, "O que você acha dele? Está bom assim?", apenas=[CONTRATO_NOME])
    chamadas = fake.respostas_ao_modelo()[n0:]
    sistema = " ".join(m["content"] for m in chamadas[-1]["corpo"]["messages"] if m["role"] == "system") if chamadas else ""
    checar(len(chamadas) == 1 and "PEDIDO DE OPINIÃO OU REVISÃO" in sistema and "colega" in sistema,
           "a nuvem recebe a instrução de revisão como colega", (len(chamadas), sistema[-300:]))
    salvo = r["salvo"]["texto"]
    checar("profissional qualificado" not in salvo and all(p.rstrip(".") in salvo for p in PONTOS),
           "a resposta guardada fica sem a ressalva de leigo, com as 4 sugestões", salvo[-600:])
    checar("Cláusula 12ª [não encontrada no documento]" in salvo, "a Cláusula 12ª inexistente sai marcada", salvo[-200:])
    checar(not ollama.pedidos, "o modelo local não foi chamado")

    print("\n2. “Em quais cláusulas esses pontos aparecem?”: a última resposta inteira")
    fake.respostas = [ONDE]
    n0 = len(fake.respostas_ao_modelo())
    r = perguntar(tid, "Em quais cláusulas esses pontos aparecem?", apenas=[CONTRATO_NOME])
    chamada = (fake.respostas_ao_modelo()[n0:] or [{}])[-1]
    msgs = (chamada.get("corpo") or {}).get("messages") or []
    anteriores = " ".join(m["content"] for m in msgs if m["role"] == "assistant")
    sistema = " ".join(m["content"] for m in msgs if m["role"] == "system")
    checar(PONTOS[3].rstrip(".") in anteriores, "o último ponto da resposta anterior vai junto (sem corte)", anteriores[-300:])
    checar("CONTINUAÇÃO DA CONVERSA" in sistema, "com a instrução de continuidade")
    salvo = r["salvo"]["texto"]
    checar("Parágrafo 1º [esse parágrafo não está no documento]" in salvo
           and "Inciso IV [esse inciso não está no documento]" in salvo, "parágrafo e inciso inventados ficam marcados", salvo)
    checar("Cláusula 10ª elege" in salvo, "a Cláusula 10ª, que existe, fica como está")

    print("\n3. “Então vamos ajustar o que falta. Me pergunte aqui”")
    n0 = len(fake.chamadas)
    antes = n_documentos()
    r = perguntar(tid, "Então vamos ajustar o que falta. Me pergunte aqui e eu te digo como será feito",
                  apenas=[CONTRATO_NOME])
    p = r["proposta"]
    checar(p.get("tipo") == "entrevista" and p.get("ajustes") and len(p.get("perguntas") or []) == 4,
           "o cartão de perguntas, uma por ponto", (p.get("tipo"), len(p.get("perguntas") or [])))
    texto = r["salvo"]["texto"]
    checar("1. Prazo de entrega do imóvel e consequências do atraso: como deve ficar?" in texto
           and "nada muda sem o seu sim" in texto, "a resposta são as perguntas, numeradas", texto[:300])
    checar("entrega imediata" not in texto and "Cláusula 3ª" not in texto, "e não um resumo do contrato de novo")
    checar(len(fake.chamadas) == n0 and n_documentos() == antes, "sem modelo e sem gravar nada")
    aj = r["trabalho"]["contexto"].get("ajustes") or {}
    checar(aj.get("status") == "aberta" and (aj.get("alvo") or {}).get("nome") == CONTRATO_NOME,
           "as perguntas ficam guardadas na conversa, com o contrato como alvo", aj.get("alvo"))

    print("\n4. as respostas, pelo cartão: o cartão de aplicar, nada gravado")
    resposta_cartao = {"id": p["entrevista_id"], "acao": "responder", "explicacao": "",
                       "respostas": [{"id": "a1", "modo": "valor", "resposta": "30 dias, multa de 2% ao mês de atraso"},
                                     {"id": "a2", "modo": "decida", "resposta": ""},
                                     {"id": "a4", "modo": "valor", "resposta": "devolver em 30 dias, retendo 10%"}]}
    r = perguntar(tid, "Prazo... — 30 dias", entrevista=resposta_cartao)
    p2 = r["proposta"]
    checar(p2.get("tipo") == "aplicar_ajustes" and len(p2.get("ajustes") or []) == 3,
           "o cartão “aplicar os ajustes”, com os 3 definidos", (p2.get("tipo"), p2.get("ajustes")))
    checar("30 dias, multa de 2%" in r["salvo"]["texto"] and "você pediu que eu decida" in r["salvo"]["texto"],
           "a conversa diz como ficou", r["salvo"]["texto"][:300])
    checar(len(fake.chamadas) == n0 and n_documentos() == antes, "nada gravado antes do sim, sem modelo")
    cartao = next(m for m in r["trabalho"]["mensagens"] if (m.get("proposta") or {}).get("entrevista_id") == p["entrevista_id"])
    checar(cartao["proposta"].get("respondida"), "o cartão de perguntas fica respondido")

    print("\n5. o sim: a cópia editável do contrato e o pedido ao editor")
    rr = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "aplicar_ajustes", "campos": p2["campos"]})
    d = (rr.json().get("proposta") or {}) if rr.status_code == 200 else {}
    c = d.get("campos") or {}
    doc = api.estado.documentos.obter(c.get("id") or 0) or {}
    checar(rr.status_code == 200 and "DA ENTREGA DO IMÓVEL" in json.dumps(doc, ensure_ascii=False),
           "o rascunho é a cópia do contrato do Acervo", rr.text[:200])
    checar(n_documentos() == antes + 1, "uma cópia, criada só agora")
    pedido = c.get("pedido") or ""
    checar("30 dias, multa de 2% ao mês de atraso" in pedido and "decida" in pedido and "retendo 10%" in pedido
           and "responsabilidades das partes" not in pedido, "o pedido leva o que foi definido (e só isso)", pedido)
    rr2 = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "aplicar_ajustes", "campos": p2["campos"]})
    checar(rr2.status_code == 404, "aplicado, não aplica de novo", rr2.status_code)
    t = local.get(f"/api/trabalhos/{tid}").json()
    aplicado = next(m for m in t["mensagens"] if (m.get("proposta") or {}).get("tipo") == "aplicar_ajustes")
    checar(aplicado["proposta"].get("feito") and (aplicado.get("feito") or {}).get("nome") == CONTRATO_NOME,
           "o cartão fica “aplicado” e a conversa sabe qual rascunho abriu")

    print("\nno trabalho redigido aqui, respondendo na caixa")
    tid2 = local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]
    t2 = api.estado.trabalhos.obter(tid2)
    t2.dizer("pessoa", "Vamos criar um contrato de compra e venda")
    t2.dizer("paulus", "CONTRATO DE COMPRA E VENDA\n\nCLÁUSULA 1ª – DO OBJETO\nO lote urbano.",
             proposta={"tipo": "levar_ao_editor", "titulo": "CONTRATO DE COMPRA E VENDA", "campos": {}})
    t2.dizer("pessoa", "O que você acha dele?")
    t2.dizer("paulus", "Faltam dois pontos:\n\n- Prever multa por atraso no pagamento das parcelas.\n"
                       "- Definir o foro da comarca do imóvel.")
    api.estado.trabalhos.salvar(t2)
    antes = n_documentos()
    r = perguntar(tid2, "pode perguntar")
    checar(r["proposta"].get("tipo") == "entrevista" and len(r["proposta"].get("perguntas") or []) == 2,
           "“pode perguntar”: as 2 perguntas", r["salvo"]["texto"][:200])
    r = perguntar(tid2, "1. multa de 10% sobre a parcela\n2. São Félix do Xingu")
    p3 = r["proposta"]
    checar(p3.get("tipo") == "aplicar_ajustes" and [a["como"] for a in p3.get("ajustes") or []]
           == ["multa de 10% sobre a parcela", "São Félix do Xingu"], "a resposta numerada na caixa vira os ajustes",
           p3.get("ajustes"))
    checar((p3.get("alvo") or {}).get("tipo") == "trabalho" and n_documentos() == antes, "o alvo é o trabalho redigido; nada gravado")
    rr = local.post(f"/api/trabalhos/{tid2}/fazer", json={"tipo": "aplicar_ajustes", "campos": p3["campos"]})
    c = (rr.json().get("proposta") or {}).get("campos") or {} if rr.status_code == 200 else {}
    doc = api.estado.documentos.obter(c.get("id") or 0) or {}
    checar("O lote urbano" in json.dumps(doc, ensure_ascii=False) and "multa de 10%" in (c.get("pedido") or ""),
           "o sim leva o trabalho ao editor (o mesmo rascunho do botão) com o pedido", rr.text[:200])
    rr = local.post(f"/api/trabalhos/{tid2}/fazer", json={"tipo": "levar_ao_editor", "campos": {}})
    checar(rr.status_code == 200 and rr.json()["proposta"]["campos"]["id"] == c.get("id"), "o botão abre o mesmo rascunho")

    print("\nsem pontos para perguntar")
    tid3 = local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]
    r = perguntar(tid3, "me pergunte o que precisar")
    checar(not r["proposta"] and "não traz uma lista de pontos" in r["salvo"]["texto"], "diz que não há pontos, sem inventar",
           r["salvo"]["texto"])
    checar(not ollama.pedidos, "o modelo local nunca foi chamado")

    test_tela()

    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s):")
        for f in _falhas:
            print("  - " + f)
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
