"""
Profundidade jurídica e conversa modular (03/10/2026): src/profundidade.py,
src/entrevista.py, src/elaboracao.py e a rota da conversa.

Tudo de mentira: a nuvem (`nuvem.PEDIR`) responde conforme a etapa que a
chamada pede, e o Ollama não pode ser chamado. Nada sai da máquina.

  - os cinco níveis, na ordem, com o padrão Advogado; a resposta comum na
    nuvem leva a instrução e o teto do nível;
  - "é pedido de trabalho?" por regra: pergunta simples não ganha entrevista;
  - a conferência do que o modelo devolveu: pergunta sem porquê não passa,
    "Outro"/"Não sei" saem das opções (a tela já oferece), sim/não vira
    escolha, o teto do nível vale, rodada além do limite executa;
  - o fluxo: pedido aberto -> módulo de perguntas (cartão); respostas ->
    nova rodada só com o que surgiu; "Decida por mim" -> executa, com o
    pedido de decidir no texto que vai à elaboração;
  - as etapas de cada nível: Estagiário só redige; Advogado planeja e redige;
    Juiz revisa e reescreve o que a revisão apontou; o CPF sai mascarado em
    todas as etapas e volta no texto;
  - texto livre com a entrevista aberta é resposta; outra pergunta segue o
    caminho de sempre;
  - o trabalho vai para o editor pelo cartão;
  - com "pedir o sim a cada envio", o trabalho fica no caminho de sempre.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_profundidade.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-profundidade-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

_falhas: list[str] = []
CPF = "529.982.247-25"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, segundos: float = 30.0) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.05)
    return False


class Ollama:
    def __init__(self) -> None:
        self.pedidos: list = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        self.pedidos.append((json or {}).get("messages") or [])
        texto = '{"ok": "local"}' if (json or {}).get("format") == "json" else "Escrita no escritório."

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": texto}, "done": True}

            def iter_lines(self, decode_unicode=True):
                yield __import__("json").dumps({"message": {"content": texto}})
                yield __import__("json").dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5})

            def close(self):
                pass
        return R()

    def get(self, url, **k):
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": []})


def etapa_da_chamada(corpo: dict) -> str:
    """Qual etapa a chamada pede, pelo texto que vai (é assim que o fake responde)."""
    msgs = corpo.get("messages") or []
    sistema = " ".join(m["content"] for m in msgs if m["role"] == "system")
    ultima = msgs[-1]["content"] if msgs else ""
    if "PRINCÍPIO: primeiro entenda o trabalho" in sistema:
        return "entrevista"
    if "Você faz a triagem" in sistema:
        return "triagem"
    if "CLÁUSULA POR CLÁUSULA" in sistema:
        return "clausula"
    if "Planeje o trabalho em SEÇÕES" in ultima:
        return "plano_secoes"
    if "TRABALHO JURÍDICO" in sistema:
        if ultima.rstrip().endswith("O que precisa estar no documento por causa disso."):
            return "analise"
        if "Monte o PLANO do trabalho" in ultima:
            return "plano"
        if "Você é o revisor sênior" in ultima:
            return "revisao"
        if "Reescreva o TEXTO inteiro" in ultima:
            return "reescrita"
        if "Agora redija o trabalho completo" in ultima:
            return "redacao"
    return "resposta"


class Nuvem:
    def __init__(self) -> None:
        self.chamadas: list[dict] = []
        self.entrevistas: list[dict] = []   # o que a avaliação devolve, rodada a rodada
        self.revisao = {"problemas": [], "refazer": False}

    def __call__(self, metodo, url, cabecalhos, corpo, stream):
        etapa = etapa_da_chamada(corpo or {})
        self.chamadas.append({"url": url, "corpo": corpo, "etapa": etapa})
        if etapa == "entrevista":
            dados = self.entrevistas.pop(0) if self.entrevistas else {"decisao": "executar", "abertura": "Perfeito."}
            pedacos = [json.dumps(dados, ensure_ascii=False)]
        elif etapa == "plano_secoes":
            pedacos = [json.dumps({"titulo_documento": "Contrato de arrendamento rural", "unidade": "cláusula",
                                   "secoes": [{"titulo": "Do objeto", "objetivo": "a área arrendada e o uso"},
                                              {"titulo": "Do preço", "objetivo": "o preço do arrendamento e o pagamento"}],
                                   "leis": [{"nome": "Estatuto da Terra (Lei 4.504/1964)", "codigo": ""},
                                            {"nome": "Código Civil", "codigo": "cc"}]}, ensure_ascii=False)]
        elif etapa == "clausula":
            ultima = (corpo.get("messages") or [{}])[-1].get("content", "")
            titulo = ultima.rsplit("Primeira linha: ", 1)[-1].strip()
            ajustada = " (ajustada)" if "AJUSTES PEDIDOS" in ultima else ""
            pedacos = [titulo + "\nTexto da cláusula" + ajustada + ", com o arrendatário CPF [CP", "F 1] e [●].\n###PON",
                       'TOS###\n{"pontos": [{"ponto": "Prazo de pagamento", "atual": "30 dias", "alternativas": ["15 dias", '
                       '"na colheita"]}], "aviso": ""}']
        elif etapa == "triagem":
            pedacos = ['{"assunto": "lei", "documentos": [], "em_tese": "", "dispositivos": []}']
        elif etapa == "analise":
            pedacos = ["- Risco: benfeitorias sem regra.\n- Ambiguidade: prazo."]
        elif etapa == "plano":
            pedacos = ["1. Partes\n2. Objeto\n3. Preço\n4. Benfeitorias"]
        elif etapa == "revisao":
            pedacos = [json.dumps(self.revisao, ensure_ascii=False)]
        elif etapa == "reescrita":
            pedacos = ["CONTRATO REVISTO. Arrendatário CPF [CP", "F 1]. Cláusula de benfeitorias incluída.\n---\nNotas"]
        elif etapa == "redacao":
            pedacos = ["CONTRATO DE ARRENDAMENTO RURAL. Arrendatário CPF [CP", "F 1]. Cláusula 1 [●].\n---\nNotas para o advogado"]
        else:
            pedacos = ["Resposta comum da nuvem."]

        class R:
            status_code = 200

            def json(self):
                return {}

            def iter_lines(self, decode_unicode=True):
                for p in pedacos:
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": p}}]})
                yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 50}})
                yield "data: [DONE]"

            def close(self):
                pass
        return R()

    def etapas(self, desde: int = 0) -> list[str]:
        return [c["etapa"] for c in self.chamadas[desde:]]


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


# ------------------------------------------------------------ sem servidor

def test_niveis() -> None:
    print("\nos níveis")
    import profundidade

    t = profundidade.para_tela({})
    checar([n["id"] for n in t["niveis"]] == ["estagiario", "bacharel", "advogado", "juiz", "ministro"],
           "Estagiário → Bacharel → Advogado → Juiz → Ministro")
    checar([n["nome"] for n in t["niveis"]] == ["Estagiário", "Bacharel", "Advogado", "Juiz", "Ministro"], "os nomes")
    checar(t["padrao"] == "advogado" and t["entrevista"] is True, "o padrão é Advogado, com a entrevista ligada")
    checar(profundidade.obter("", {"profundidade": {"padrao": "juiz"}}).id == "juiz", "o padrão do escritório vale")
    checar(profundidade.obter("xyz", {}).id == "advogado", "nível desconhecido vira o padrão")
    n = profundidade.NIVEIS
    checar(all(n[a].consumo < n[b].consumo and n[a].saida_tokens <= n[b].saida_tokens
               for a, b in zip(profundidade.ORDEM, profundidade.ORDEM[1:])), "cada nível gasta mais e escreve mais que o anterior")
    checar(n["estagiario"].etapas == ("redacao",) and n["advogado"].etapas == ("plano", "redacao")
           and n["juiz"].etapas == ("plano", "redacao", "revisao") and n["ministro"].etapas[0] == "analise",
           "as etapas: Estagiário redige; Advogado planeja; Juiz revisa; Ministro começa pela análise")
    checar("postura" not in t["niveis"][0], "a instrução interna não vai para a tela")
    checar(profundidade.modelo_do_nivel({"profundidade": {"modelos": {"ministro": "Qwen/Qwen2.5-72B-Instruct"}}},
                                        n["ministro"], "padrao") == "Qwen/Qwen2.5-72B-Instruct"
           and profundidade.modelo_do_nivel({}, n["juiz"], "padrao") == "padrao", "o modelo por nível, se o escritório quiser")


def test_e_trabalho() -> None:
    print("\né pedido de trabalho? (regra)")
    import entrevista

    sim = ["Preciso fazer um contrato de arrendamento rural", "Elabore uma contestação para ação de cobrança",
           "Redija uma notificação extrajudicial para o inquilino", "Analise este contrato e aponte riscos",
           "faça um parecer sobre usucapião", "Quero entrar com uma ação de despejo", "Pode fazer uma procuração ad judicia?",
           "Revise a minuta do aditivo", "preciso de uma petição inicial de alimentos", "me ajude a fazer um recurso de apelação"]
    nao = ["Explique o art. 335 do CPC", "qual o valor do contrato?", "crie uma tarefa para amanhã", "Resuma o contrato da Clínica",
           "qual o prazo do recurso de apelação?", "o contrato da clínica tem multa?", "Quais as cláusulas do contrato de locação?",
           "faça uma busca no acervo", "Gostaria de saber se o contrato tem multa", "Quero saber o valor do contrato",
           "Analise o contrato da Clínica e me diga a multa", "crie um compromisso amanhã às 10h"]
    errados = [p for p in sim if not entrevista.e_trabalho(p)] + [p for p in nao if entrevista.e_trabalho(p)]
    checar(not errados, f"{len(sim)} pedidos de trabalho e {len(nao)} perguntas, cada um no seu caminho", errados)
    checar(entrevista.parece_outro_assunto("qual o valor do contrato da clínica e quando vence?", "contrato de arrendamento")
           and not entrevista.parece_outro_assunto("agricultura, com valor fixo em sacas", "contrato de arrendamento")
           and entrevista.parece_outro_assunto("faça uma contestação de cobrança", "contrato de arrendamento")
           and not entrevista.parece_outro_assunto("faça o contrato com cláusula de garantia", "contrato de arrendamento"),
           "com a entrevista aberta: resposta é resposta; outra pergunta ou outra peça é outro assunto")


def test_conferir() -> None:
    print("\na conferência do que o modelo devolveu")
    import entrevista
    import profundidade

    adv = profundidade.NIVEIS["advogado"]
    dados = {"decisao": "perguntar", "abertura": "Claro.", "titulo": "Vamos definir esse contrato",
             "perguntas": [
                 {"id": "objeto", "pergunta": "Qual é o objeto do arrendamento?", "porque": "muda as cláusulas de uso",
                  "tipo": "escolha", "opcoes": ["Área rural", "Maquinário", "Outro", "Não sei"], "sugestao": "Área rural",
                  "impede": True, "impacto": "alto"},
                 {"id": "x", "pergunta": "Qual a cor da porteira?", "porque": "", "tipo": "texto"},
                 {"id": "garantia", "pergunta": "Haverá garantia?", "porque": "define a cláusula de garantia", "tipo": "sim_nao",
                  "impede": True},
                 {"id": "situacoes", "pergunta": "Quais situações prever?", "porque": "cada uma vira cláusula",
                  "tipo": "multipla", "opcoes": ["Benfeitorias", "Decida por mim"]},
                 {"id": "prazo", "pergunta": "Prazo pretendido?", "porque": "o Estatuto da Terra tem prazo mínimo", "tipo": "esquisito"},
                 {"id": "a", "pergunta": "Pergunta A extra?", "porque": "muda algo", "tipo": "texto"},
                 {"id": "b", "pergunta": "Pergunta B extra?", "porque": "muda algo", "tipo": "texto"},
             ], "premissas": ["foro da comarca do imóvel"]}
    c = entrevista.conferir(dados, adv, 1)
    qs = c["perguntas"]
    checar(c["decisao"] == "perguntar" and len(qs) == adv.perguntas_max, "o teto do nível (Advogado: 5)", len(qs))
    checar(all(q["porque"] for q in qs) and not any("porteira" in q["pergunta"] for q in qs), "pergunta sem porquê não passa")
    checar(qs[0]["opcoes"] == ["Área rural", "Maquinário"] and qs[0]["sugestao"] == "Área rural",
           "'Outro' e 'Não sei' saem das opções (a tela já oferece)", qs[0]["opcoes"])
    checar(qs[1]["tipo"] == "escolha" and qs[1]["opcoes"] == ["Sim", "Não"], "sim/não vira escolha")
    checar(qs[2]["tipo"] == "texto" and qs[2]["opcoes"] == [], "múltipla com uma opção só vira texto", qs[2])
    checar(qs[3]["tipo"] == "texto", "tipo desconhecido vira texto")
    checar(len({q["id"] for q in qs}) == len(qs) and all(q["id"].startswith("r1_") for q in qs), "ids únicos, da rodada")
    estag = entrevista.conferir(dados, profundidade.NIVEIS["estagiario"], 1)
    checar([q["pergunta"] for q in estag["perguntas"]] == ["Qual é o objeto do arrendamento?", "Haverá garantia?"],
           "Estagiário: só o que impede o trabalho", [q["pergunta"] for q in estag["perguntas"]])
    bach = entrevista.conferir(dados, profundidade.NIVEIS["bacharel"], 1)
    checar(len(bach["perguntas"]) == 2, "Bacharel: o que impede ou tem impacto alto", len(bach["perguntas"]))
    baixo = entrevista.conferir({"decisao": "perguntar", "perguntas": [
        {"pergunta": "Qual o foro?", "porque": "muda a cláusula de foro", "impacto": "baixo"},
        {"pergunta": "Qual o nome do arrendatário?", "porque": "qualifica", "impacto": "alto", "impede": True},
        {"pergunta": "Quem é a parte arrendadora?", "porque": "qualifica", "tipo": "parte", "impacto": "alto"},
        {"pergunta": "Quem o escritório representa?", "porque": "define a quem as cláusulas protegem", "impacto": "alto"}]}, adv, 1)
    checar([q["pergunta"] for q in baixo["perguntas"]] == ["Quem é a parte arrendadora?", "Quem o escritório representa?"],
           "impacto baixo vira premissa; o nome solto não é pergunta; 'quem é a parte' (Cadastros) e 'quem o escritório representa' ficam",
           [q["pergunta"] for q in baixo["perguntas"]])
    checar(entrevista.conferir(dados, adv, 3)["decisao"] == "executar", "além das rodadas do nível, executa")
    checar(entrevista.conferir({"decisao": "perguntar", "perguntas": []}, adv, 1)["decisao"] == "executar",
           "perguntar sem pergunta válida é executar")
    checar(entrevista.conferir(dados, adv, 2, ja_perguntadas=["Qual é o objeto do arrendamento?"])["perguntas"][0]["id"] != "r2_objeto",
           "não repete pergunta de rodada anterior")
    vagas = entrevista.conferir({"decisao": "perguntar", "perguntas": [
        {"pergunta": "Há outros termos ou condições específicas?", "porque": "pode incluir detalhes", "impacto": "alto"},
        {"pergunta": "Há cláusulas adicionais que devem ser incluídas?", "porque": "personaliza", "impacto": "alto"},
        {"pergunta": "Algo mais?", "porque": "x", "impacto": "alto"},
        {"pergunta": "Haverá direito de preferência na venda?", "porque": "exige a cláusula do art. 92 do Estatuto da Terra",
         "impacto": "alto"}]}, adv, 1)
    checar([q["pergunta"] for q in vagas["perguntas"]] == ["Haverá direito de preferência na venda?"],
           "pergunta vaga não passa", [q["pergunta"] for q in vagas["perguntas"]])
    checar(entrevista.separar_analise("O regime é o Estatuto da Terra.\n###JSON###\n{\"decisao\": \"executar\"}")
           == ("O regime é o Estatuto da Terra.", "\n{\"decisao\": \"executar\"}"), "a análise livre sai antes do JSON")
    juiz = profundidade.NIVEIS["juiz"]
    checar(entrevista.SEPARADOR in entrevista.instrucao(juiz, 1) and entrevista.SEPARADOR not in entrevista.instrucao(adv, 1),
           "Juiz e Ministro escrevem a análise antes; o Advogado, dentro do JSON")
    import elaboracao

    probs, refazer = elaboracao.problemas_da_revisao({"problemas": [
        {"gravidade": "alta", "onde": "c3", "o_que": "não especifica a quantidade de sacas por hectare", "correcao": "inserir o valor exato"},
        {"gravidade": "media", "onde": "c5", "o_que": "não especifica a forma de garantia", "correcao": "caução ou fiança"}]})
    checar([p["gravidade"] for p in probs] == ["baixa", "media"] and refazer,
           "dado não informado não é defeito (fica [●]); a forma de garantia é", probs)
    checar(not elaboracao.problemas_da_revisao({"problemas": [
        {"gravidade": "alta", "o_que": "falta o valor do aluguel", "correcao": "inserir o valor"}]})[1],
        "só dado faltante: não reescreve")
    import nuvem

    m = nuvem.Mascara()
    m.aplicar("CPF 529.982.247-25")
    limpo = elaboracao.limpar_texto("#### CLÁUSULA 1\n**Partes**: [CPF 1] e a testemunha [CPF 3].", m)
    checar(limpo == "CLÁUSULA 1\nPartes: 529.982.247-25 e a testemunha [●].",
           "texto final sem markdown, com o dado de volta e o marcador inventado em [●]", limpo)
    e = entrevista.novo_estado("contrato de arrendamento", "advogado")
    entrevista.aplicar(e, c)
    entrevista.juntar_respostas(e, [{"id": qs[0]["id"], "resposta": "Área rural"}, {"id": qs[1]["id"], "modo": "decida"},
                                    {"id": qs[2]["id"], "modo": "nao_sei"}, {"id": "inventado", "resposta": "x"}],
                                "o arrendatário vai construir um galpão")
    b = entrevista.briefing(e)
    checar("Área rural" in b and "DECIDA" in b and "SEM RESPOSTA" in b and "galpão" in b and "foro da comarca" in b,
           "o briefing leva respostas, o 'decida por mim', o 'não sei', a explicação e as premissas", b)
    checar(len(e["respostas"]) == 3, "resposta a pergunta que não existe é ignorada")
    un = entrevista.conferir({"decisao": "perguntar", "perguntas": [
        {"pergunta": "Qual é a área total a ser arrendada em hectares?", "porque": "define o preço", "tipo": "valor"},
        {"pergunta": "Quantas sacas por hectare o arrendatário pagará?", "porque": "remuneração", "tipo": "valor"},
        {"pergunta": "Qual o valor da multa?", "porque": "define a multa", "tipo": "valor"},
        {"pergunta": "Prazo?", "porque": "prazo mínimo", "tipo": "numero", "unidade": "anos"}]}, adv, 1)
    checar([(q["tipo"], q["unidade"]) for q in un["perguntas"]] == [("numero", "ha"), ("numero", "sacas/ha"), ("valor", "R$"),
                                                                    ("numero", "anos")],
           "quantidade não é dinheiro: a unidade certa (ha, sacas/ha, anos); R$ só no valor",
           [(q["tipo"], q["unidade"]) for q in un["perguntas"]])
    novos = entrevista.conferir({"decisao": "perguntar", "perguntas": [
        {"pergunta": "Quem é o arrendador?", "porque": "qualifica a parte e define a quem o contrato protege", "tipo": "parte",
         "impacto": "alto"},
        {"pergunta": "Qual o CPF do arrendador?", "porque": "qualifica", "tipo": "texto", "impacto": "alto"},
        {"pergunta": "Em qual comarca fica o imóvel?", "porque": "define o foro", "tipo": "escolha", "impacto": "alto",
         "opcoes": [f"Comarca {n}" for n in range(1, 10)]},
        {"pergunta": "O imóvel está livre de débitos de ITR?", "porque": "muda a cláusula de tributos", "tipo": "confirmacao",
         "afirmacao": "O imóvel não tem débitos de ITR", "impacto": "alto"},
        {"pergunta": "Qual a matrícula do imóvel?", "porque": "o objeto se descreve por ela", "tipo": "documento",
         "impacto": "alto"}]}, adv, 1)
    tipos = [(q["pergunta"], q["tipo"]) for q in novos["perguntas"]]
    checar(tipos == [("Quem é o arrendador?", "parte"), ("Em qual comarca fica o imóvel?", "lista"),
                     ("O imóvel está livre de débitos de ITR?", "confirmacao"), ("Qual a matrícula do imóvel?", "documento")],
           "quem é a parte vale como 'parte'; o CPF solto não; 9 opções viram lista; confirmação e documento", tipos)
    checar(novos["perguntas"][2]["afirmacao"] == "O imóvel não tem débitos de ITR" and len(novos["perguntas"][1]["opcoes"]) == 9,
           "a afirmação a confirmar e as opções da lista")
    e2 = entrevista.novo_estado("contrato de arrendamento", "advogado")
    entrevista.aplicar(e2, novos)
    ids2 = [q["id"] for q in e2["perguntas"]]
    entrevista.juntar_respostas(e2, [{"id": ids2[0], "resposta": "joão da silva"},
                                     {"id": ids2[3], "resposta": "matricula 123.pdf, outro.pdf"}])
    entrevista.enriquecer(e2, [{"nome": "João da Silva", "documento": "529.982.247-25", "endereco": "Rua A, 1"}],
                          ["matricula 123.pdf"])
    r0 = e2["respostas"][0]
    checar("529.982.247-25" in r0.get("qualificacao", "") and "Rua A, 1" in r0["qualificacao"]
           and "estado civil" in r0.get("falta_na_ficha", []), "a parte dos Cadastros vira qualificação, e diz o que falta",
           r0.get("qualificacao"))
    checar(e2.get("materiais") == ["matricula 123.pdf"], "o documento apontado entra como material (o que não existe, não)",
           e2.get("materiais"))
    checar("use esta qualificação" in entrevista.briefing(e2), "a qualificação vai para a redação")
    ab = entrevista.conferir({"decisao": "executar", "trabalho": "Contrato de arrendamento rural",
                              "abertura": "Para criar o contrato, precisamos definir alguns pontos adicionais."}, adv, 1)
    checar(ab["abertura"].startswith("Perfeito, já tenho o necessário") and "contrato de arrendamento rural" in ab["abertura"],
           "executar não abre dizendo que falta definir algo", ab["abertura"])


# ------------------------------------------------------------ pela rota

def main() -> int:
    print("=" * 60)
    print("  Profundidade jurídica e conversa modular")
    print("=" * 60)
    test_niveis()
    test_e_trabalho()
    test_conferir()

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
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "trechos", "denso": False})
    api.estado.modelo_para = lambda tarefa: "falso:1b"
    api.check_ollama = lambda *a, **k: (True, "")
    api.plano_mod.liberada = lambda estado: True
    nuvem.chave = lambda estado, provedor: "di-chave-de-mentira"
    nuvem.consentido = lambda estado: True
    api.estado.prefs.dados["nuvem"] = {"ligado": True, "provedor": "deepinfra", "modelo": "meta-llama/Llama-3.3-70B-Instruct",
                                       "mascarar": True, "tarefas": {"conversa": True}}
    local = TestClient(api.app, headers=api.cabecalho_local())

    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "minuta-anterior.txt").write_text("MINUTA ANTERIOR. Arrendatário CPF " + CPF + ". Prazo de 3 anos.", encoding="utf-8")
    (pasta / "modelo arrendamento soja.txt").write_text(
        "CONTRATO DE ARRENDAMENTO RURAL\n\nCLÁUSULA 2ª – DO PREÇO\n\nO preço do arrendamento será pago em dinheiro, "
        "anualmente, até o fim da colheita, corrigido pelo índice escolhido pelas partes.", encoding="utf-8")
    (pasta / "estatuto da terra.txt").write_text(
        "LEI Nº 4.504, DE 30 DE NOVEMBRO DE 1964 - Estatuto da Terra\n" + "\n".join(
            f"Art. {n}. Disposição {n} sobre o imóvel rural." for n in range(1, 10))
        + "\nArt. 95. O preço do arrendamento não pode ser superior a 15% do valor cadastral do imóvel, pago em dinheiro.\n",
        encoding="utf-8")
    api.estado.recarregar()

    situacao = local.get("/api/nuvem/situacao").json()
    checar(situacao["ligada"] and len(situacao["profundidade"]["niveis"]) == 5, "a caixa da pergunta recebe os níveis")

    def perguntar(tid, corpo):
        saida = {}
        th = threading.Thread(target=lambda: saida.update(r=local.post(f"/api/trabalhos/{tid}/perguntar", json=corpo)), daemon=True)
        th.start()
        th.join(60)
        esperar(lambda: not api.estado.respondendo.get(tid))
        evs = eventos(saida["r"].text) if "r" in saida else []
        t = local.get(f"/api/trabalhos/{tid}").json()
        return evs, t

    def nova():
        return local.post("/api/trabalhos", json={"pedido": "p"}).json()["id"]

    print("\npedido aberto: o módulo de perguntas")
    fake.entrevistas = [{
        "decisao": "perguntar", "trabalho": "contrato de arrendamento rural", "entendimento": "um contrato de arrendamento rural",
        "abertura": "Claro. Antes de redigir, há alguns pontos que mudam bastante a estrutura desse contrato.",
        "titulo": "Vamos definir esse contrato",
        "perguntas": [
            {"id": "objeto", "pergunta": "Qual é o objeto do arrendamento?", "porque": "muda as obrigações de uso",
             "tipo": "escolha", "opcoes": ["Área rural", "Maquinário"]},
            {"id": "remuneracao", "pergunta": "Como será a remuneração?", "porque": "o Estatuto da Terra limita o preço",
             "tipo": "escolha", "opcoes": ["Valor fixo", "Percentual da produção", "Sacas/produtos"]},
            {"id": "lado", "pergunta": "Quem o escritório representa?", "porque": "muda o equilíbrio das cláusulas",
             "tipo": "escolha", "opcoes": ["Arrendador", "Arrendatário"]},
        ], "premissas": ["foro da comarca do imóvel"]}]
    n0 = len(fake.chamadas)
    o0 = len(ollama.pedidos)
    tid = nova()
    evs, t = perguntar(tid, {"pergunta": "Preciso fazer um contrato de arrendamento rural", "nuvem": True, "profundidade": "advogado"})
    prop = next((d for k, d in evs if k == "proposta"), {})
    checar(fake.etapas(n0) == ["entrevista"], "uma chamada só: entender o pedido (nada redigido ainda)", fake.etapas(n0))
    checar(prop.get("tipo") == "entrevista" and len(prop.get("perguntas") or []) == 3 and prop.get("titulo") == "Vamos definir esse contrato",
           "o cartão com as perguntas que o modelo montou para ESTE pedido", prop.get("titulo"))
    ultima = t["mensagens"][-1]
    checar(ultima["autor"] == "paulus" and ultima["texto"].startswith("Claro. Antes de redigir")
           and ultima["proposta"]["tipo"] == "entrevista", "a abertura natural fica na conversa, com o cartão")
    checar((t["contexto"].get("entrevista") or {}).get("status") == "aberta", "a entrevista fica aberta na conversa")
    checar(len(ollama.pedidos) == o0, "o modelo deste computador não foi chamado")
    entrada = json.dumps(fake.chamadas[n0]["corpo"], ensure_ascii=False)
    checar("NÍVEL DE PROFUNDIDADE ESCOLHIDO: Advogado" in entrada and "No máximo 5 perguntas" in entrada,
           "a instrução da entrevista leva o nível e o teto")

    print("\nas respostas: nova rodada só com o que surgiu")
    fake.entrevistas = [{
        "decisao": "perguntar", "abertura": "Perfeito. Como haverá benfeitorias do arrendatário, falta um ponto.",
        "titulo": "Benfeitorias",
        "perguntas": [
            {"id": "objeto", "pergunta": "Qual é o objeto do arrendamento?", "porque": "repetida", "tipo": "texto"},
            {"id": "benfeitorias", "pergunta": "Como ficam as benfeitorias no fim do contrato?", "porque": "muda a indenização",
             "tipo": "escolha", "opcoes": ["Indenizadas", "Sem indenização", "Retiradas"]}]}]
    ids = [q["id"] for q in prop["perguntas"]]
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Qual é o objeto? — Área rural", "nuvem": True, "profundidade": "advogado",
                             "entrevista": {"id": prop["entrevista_id"], "acao": "responder",
                                            "respostas": [{"id": ids[0], "resposta": "Área rural"},
                                                          {"id": ids[1], "resposta": "Sacas/produtos"},
                                                          {"id": ids[2], "modo": "nao_sei"}],
                                            "explicacao": "O arrendatário vai construir um galpão."}})
    prop2 = next((d for k, d in evs if k == "proposta"), {})
    checar(fake.etapas(n0) == ["entrevista"] and prop2.get("rodada") == 2, "uma nova análise, rodada 2", fake.etapas(n0))
    checar([q["pergunta"] for q in prop2.get("perguntas") or []] == ["Como ficam as benfeitorias no fim do contrato?"],
           "só o módulo novo: a pergunta repetida não volta", prop2.get("perguntas"))
    enviado = fake.chamadas[n0]["corpo"]["messages"][-1]["content"]
    checar("Sacas/produtos" in enviado and "não sei" in enviado and "galpão" in enviado, "a nova análise leu as respostas e a explicação")
    respondida = [m for m in t["mensagens"] if (m.get("proposta") or {}).get("entrevista_id") == prop["entrevista_id"]]
    checar(respondida and respondida[0]["proposta"].get("respondida") is True, "o cartão da rodada 1 fica respondido")
    pessoa = [m for m in t["mensagens"] if m["autor"] == "pessoa"][-1]
    checar("Área rural" in pessoa["texto"], "a resposta da pessoa fica legível na conversa")

    print("\na parte pelos Cadastros")
    api.estado.cadastros.salvar({"tipo": "cliente", "nome": "Agro Sul Ltda", "documento": "11.222.333/0001-81",
                                 "endereco": "Av. Brasil, 100"})
    fake.entrevistas = [{"decisao": "perguntar", "trabalho": "contrato de arrendamento rural", "abertura": "Um ponto.",
                         "titulo": "Quem é quem", "perguntas": [
                             {"id": "arrendatario", "pergunta": "Quem é o arrendatário?", "porque": "qualifica a parte",
                              "tipo": "parte", "impacto": "alto"}]},
                        {"decisao": "executar", "abertura": "Certo."}]
    tid_p = nova()
    evs, t = perguntar(tid_p, {"pergunta": "Preciso fazer um contrato de arrendamento rural para um cliente", "nuvem": True})
    prop_p = next((d for k, d in evs if k == "proposta"), {})
    checar("Agro Sul Ltda" in prop_p.get("cadastros", []), "o campo de parte oferece os Cadastros", prop_p.get("cadastros"))
    evs, t = perguntar(tid_p, {"pergunta": "Quem é o arrendatário? — Agro Sul Ltda", "nuvem": True,
                               "entrevista": {"id": prop_p["entrevista_id"], "acao": "responder",
                                              "respostas": [{"id": prop_p["perguntas"][0]["id"], "resposta": "Agro Sul Ltda"}]}})
    prep_p = next((d for k, d in evs if k == "proposta"), {})
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid_p, {"pergunta": "Pode começar.", "nuvem": True,
                               "entrevista": {"id": prep_p["entrevista_id"], "acao": "comecar"}})
    pedido_q = json.dumps(fake.chamadas[-1]["corpo"], ensure_ascii=False)
    checar("AGRO SUL LTDA, pessoa jurídica de direito privado" in pedido_q and "Av. Brasil, 100" in pedido_q
           and "11.222.333/0001-81" not in pedido_q, "a qualificação da ficha vai à cláusula (com o CNPJ mascarado)")

    print("\n'Decida por mim': o plano das cláusulas, antes de redigir")
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Decida por mim o que faltar.", "nuvem": True, "profundidade": "advogado",
                             "entrevista": {"id": prop2["entrevista_id"], "acao": "decidir", "respostas": []}})
    checar(fake.etapas(n0) == ["plano_secoes"], "sem nova entrevista: só o plano das cláusulas", fake.etapas(n0))
    prep = next((d for k, d in evs if k == "proposta"), {})
    checar(prep.get("tipo") == "preparo" and prep["secoes"][0] == "QUALIFICAÇÃO DAS PARTES"
           and prep["secoes"][1] == "CLÁUSULA 1ª – DO OBJETO", "a qualificação das partes primeiro, e as cláusulas numeradas",
           prep.get("secoes"))
    frase = t["mensagens"][-1]["texto"]
    checar("cláusula por cláusula, juntos, começando pela qualificação das partes" in frase and "compilo tudo num documento só" in frase,
           "diz que vamos fazer cláusula por cláusula, juntos, e compilar no fim", frase)
    checar("Estatuto da Terra" in frase and "modelo já feito" in frase, "pede a lei que falta e um modelo", frase)
    leis = {l["nome"]: l["na_biblioteca"] for l in prep["leis"]}
    checar(leis.get("Estatuto da Terra (Lei 4.504/1964)") is False, "o Estatuto da Terra não está na Biblioteca", leis)
    checar("modelo arrendamento soja.txt" in prep.get("modelos_acervo", []), "oferece o modelo do Acervo", prep.get("modelos_acervo"))
    checar(t["contexto"]["entrevista"]["fase"] == "preparo", "a conversa espera o começo")

    print("\ncláusula por cláusula")
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Pode começar pela qualificação das partes.", "nuvem": True, "profundidade": "advogado",
                             "apenas": ["estatuto da terra.txt"],
                             "entrevista": {"id": prep["entrevista_id"], "acao": "comecar", "modelos": ["modelo arrendamento soja.txt"]}})
    checar(fake.etapas(n0) == ["clausula"], "uma chamada: a qualificação das partes", fake.etapas(n0))
    tokens = "".join(d["t"] for k, d in evs if k == "token")
    checar("###" not in tokens and "pontos" not in tokens and tokens.startswith("QUALIFICAÇÃO DAS PARTES"),
           "à tela vai só a cláusula, sem o JSON dos pontos", tokens[:120])
    c1 = next((d for k, d in evs if k == "oferta"), {})
    checar(c1.get("tipo") == "clausula" and c1.get("indice") == 0 and c1.get("total") == 3
           and c1["pontos"][0]["alternativas"] == ["15 dias", "na colheita"], "o cartão: Aprovar, Corrigir e os pontos ajustáveis", c1)
    checar(CPF not in json.dumps(fake.chamadas[-1]["corpo"], ensure_ascii=False), "a cláusula vai mascarada")
    checar(sorted(t["contexto"]["entrevista"]["materiais"]) == ["estatuto da terra.txt", "modelo arrendamento soja.txt"],
           "a lei anexada e o modelo escolhido ficam como material", t["contexto"]["entrevista"]["materiais"])
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Aprovada", "nuvem": True, "profundidade": "advogado",
                             "entrevista": {"id": c1["entrevista_id"], "acao": "aprovar", "secao": c1["secao"]}})
    c2 = next((d for k, d in evs if k == "oferta"), {})
    pedido_c2 = fake.chamadas[-1]["corpo"]["messages"][-1]["content"]
    checar(c2.get("indice") == 1 and c2["titulo"] == "CLÁUSULA 1ª – DO OBJETO" and "SEÇÕES JÁ APROVADAS" in pedido_c2,
           "aprovada, vem a próxima, com as aprovadas junto", c2.get("titulo"))
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Corrigir", "nuvem": True, "profundidade": "advogado",
                             "entrevista": {"id": c2["entrevista_id"], "acao": "corrigir", "secao": c2["secao"],
                                            "pontos": [{"ponto": "Prazo de pagamento", "escolha": "na colheita"}],
                                            "pedido": "inclua a reserva legal"}})
    c2b = next((d for k, d in evs if k == "oferta"), {})
    pedido = fake.chamadas[-1]["corpo"]["messages"][-1]["content"]
    checar(c2b.get("secao") == c2["secao"] and c2b.get("versao") == 2 and "na colheita" in pedido and "reserva legal" in pedido
           and "VERSÃO ANTERIOR" in pedido, "corrigir refaz a mesma cláusula com os pontos e o pedido livre", c2b.get("versao"))
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "ok", "nuvem": True, "profundidade": "advogado"})
    c3 = next((d for k, d in evs if k == "oferta"), {})
    pedido_c3 = fake.chamadas[-1]["corpo"]["messages"][-1]["content"]
    checar(c3.get("titulo") == "CLÁUSULA 2ª – DO PREÇO", "'ok' na caixa aprova e segue", c3.get("titulo"))
    checar("LEI ANEXADA" in pedido_c3 and "Art. 95" in pedido_c3 and "MODELO «modelo arrendamento soja.txt»" in pedido_c3,
           "a cláusula do preço leva o artigo da lei anexada e o trecho do modelo sobre o preço")
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid, {"pergunta": "Aprovada", "nuvem": True, "profundidade": "advogado",
                             "entrevista": {"id": c3["entrevista_id"], "acao": "aprovar", "secao": c3["secao"]}})
    final = t["mensagens"][-1]
    checar(fake.etapas(n0) == [], "a última aprovada: compila, sem chamar o modelo (Advogado não revisa)", fake.etapas(n0))
    checar(final["texto"].startswith("CONTRATO DE ARRENDAMENTO RURAL") and "QUALIFICAÇÃO DAS PARTES" in final["texto"]
           and "(ajustada)" in final["texto"] and final["texto"].index("CLÁUSULA 1ª") < final["texto"].index("CLÁUSULA 2ª"),
           "o documento compilado, na ordem, com a versão corrigida", final["texto"][:200])
    checar((final.get("proposta") or {}).get("tipo") == "levar_ao_editor", "o cartão para levar ao editor")
    checar(t["contexto"]["entrevista"]["status"] == "executada", "a entrevista se fecha")

    print("\nlevar ao editor")
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "levar_ao_editor", "campos": {}})
    d = r.json() if r.status_code == 200 else {}
    checar(r.status_code == 200 and (d.get("proposta") or {}).get("tipo") == "editor_criado", "vira rascunho no editor", r.text[:200])
    if d:
        doc = api.estado.documentos.obter(d["proposta"]["campos"]["id"])
        conteudo = json.dumps(doc, ensure_ascii=False, default=str) if doc else ""
        checar("CONTRATO DE ARRENDAMENTO RURAL" in conteudo and d["proposta"]["titulo"].lower().startswith("contrato de arrendamento"),
               "com o texto e o título do trabalho", d["proposta"]["titulo"])
        r2 = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "levar_ao_editor", "campos": {}}).json()
        checar(r2["proposta"]["campos"]["id"] == d["proposta"]["campos"]["id"], "de novo, abre o mesmo rascunho")

    print("\nJuiz: revisa e reescreve o que a revisão apontou")
    fake.entrevistas = [{"decisao": "executar", "abertura": "Perfeito. Já tenho o necessário.", "trabalho": "contestação"}]
    fake.revisao = {"problemas": [{"gravidade": "alta", "onde": "preliminares", "o_que": "falta a prescrição",
                                   "correcao": "incluir a prescrição"}, {"gravidade": "baixa", "onde": "x", "o_que": "estilo", "correcao": ""}],
                    "refazer": True}
    n0 = len(fake.chamadas)
    tid2 = nova()
    evs, t = perguntar(tid2, {"pergunta": "Elabore uma contestação completa para a ação de cobrança contra o arrendatário CPF " + CPF,
                              "nuvem": True, "profundidade": "juiz"})
    prep2 = next((d for k, d in evs if k == "proposta"), {})
    checar(fake.etapas(n0) == ["entrevista", "plano_secoes"] and prep2.get("tipo") == "preparo", "entender e planejar as seções",
           fake.etapas(n0))
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid2, {"pergunta": "Faça tudo de uma vez.", "nuvem": True, "profundidade": "juiz"})
    checar(fake.etapas(n0) == ["plano", "redacao", "revisao", "reescrita"],
           "'faça tudo de uma vez' na caixa: planejar, redigir, revisar e reescrever", fake.etapas(n0))
    tipos = [k for k, _ in evs]
    checar("reescrevendo" in tipos and tipos.index("reescrevendo") < tipos.index("fim"), "a tela é avisada antes da versão revista")
    final = t["mensagens"][-1]["texto"]
    checar(final.startswith("Faço tudo de uma vez, como você pediu. Com honestidade") and "CONTRATO REVISTO" in final
           and "ARRENDAMENTO RURAL." not in final and CPF in final, "honesto sobre o que se perde; a versão revista, com o CPF", final[:160])
    tokens = "".join(d["t"] for k, d in evs if k == "token")
    checar("[CPF 1]" not in tokens and CPF in tokens, "o que chega à tela traz o CPF, e não o marcador")
    rev = t["mensagens"][-1]["cobertura"]["como"]["profundidade"]["revisao"]
    checar(rev.get("refeito") is True and len(rev.get("problemas") or []) == 2, "a revisão fica registrada", rev)
    checar(CPF not in json.dumps([c["corpo"] for c in fake.chamadas[n0:]], ensure_ascii=False), "o CPF do pedido não sai em etapa nenhuma")
    titulos = [e["titulo"] for e in t["etapas"]]
    checar(titulos[-3:] == ["Planejar a estrutura", "Redigir", "Revisar criticamente"], "as etapas na tela", titulos)
    entradas = [c["corpo"].get("max_tokens") for c in fake.chamadas[n0:] if c["etapa"] in ("redacao", "reescrita")]
    checar(entradas == [7000, 7000], "o teto do Juiz na redação", entradas)

    print("\nMinistro: análise antes do plano")
    fake.entrevistas = [{"decisao": "executar", "abertura": "Certo."}]
    fake.revisao = {"problemas": [], "refazer": False}
    n0 = len(fake.chamadas)
    tid5 = nova()
    evs, t = perguntar(tid5, {"pergunta": "Faça um parecer sobre usucapião extrajudicial de imóvel rural", "nuvem": True,
                              "profundidade": "ministro"})
    prep5 = next((d for k, d in evs if k == "proposta"), {})
    checar(prep5.get("unidade") == "seção", "parecer vai seção por seção", prep5.get("unidade"))
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid5, {"pergunta": "Faça tudo de uma vez.", "nuvem": True, "profundidade": "ministro",
                              "entrevista": {"id": prep5["entrevista_id"], "acao": "tudo"}})
    checar(fake.etapas(n0) == ["analise", "plano", "redacao", "revisao"], "análise, plano, redação e revisão", fake.etapas(n0))
    checar("reescrevendo" not in [k for k, _ in evs], "sem problema alto ou médio, não reescreve")

    print("\nEstagiário sem perguntar antes: o plano; de uma vez, só redige")
    n0 = len(fake.chamadas)
    tid6 = nova()
    evs, t = perguntar(tid6, {"pergunta": "Redija uma notificação extrajudicial para o inquilino", "nuvem": True,
                              "profundidade": "estagiario", "perguntar": False})
    checar(fake.etapas(n0) == ["plano_secoes"], "sem entrevista, direto ao plano", fake.etapas(n0))
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid6, {"pergunta": "faça tudo de uma vez", "nuvem": True, "profundidade": "estagiario"})
    checar(fake.etapas(n0) == ["redacao"], "uma chamada só", fake.etapas(n0))
    checar(fake.chamadas[-1]["corpo"].get("max_tokens") == 2000, "com o teto do Estagiário")

    print("\npergunta simples: sem entrevista, com a instrução do nível")
    n0 = len(fake.chamadas)
    evs, t = perguntar(nova(), {"pergunta": "Explique o art. 335 do CPC", "nuvem": True, "profundidade": "juiz"})
    etapas = fake.etapas(n0)
    checar("entrevista" not in etapas and etapas[-1] == "resposta", "sem módulo de perguntas", etapas)
    corpo = fake.chamadas[-1]["corpo"]
    checar("PROFUNDIDADE: Juiz" in json.dumps(corpo, ensure_ascii=False) and corpo.get("max_tokens") == 4000,
           "a resposta comum leva a instrução e o teto do Juiz", corpo.get("max_tokens"))
    ultima = t["mensagens"][-1]
    checar(ultima["autor"] == "paulus" and "Resposta comum da nuvem" in ultima["texto"]
           and ((ultima.get("cobertura") or {}).get("como") or {}).get("profundidade", {}).get("nome") == "Juiz",
           "a resposta fica na conversa, com o nível", ultima.get("texto"))

    print("\ncom a entrevista aberta")
    fake.entrevistas = [
        {"decisao": "perguntar", "trabalho": "procuração", "abertura": "Antes, um ponto.", "titulo": "A procuração",
         "perguntas": [{"id": "poderes", "pergunta": "Quais poderes?", "porque": "muda o alcance", "tipo": "multipla",
                        "opcoes": ["Ad judicia", "Especiais"]}]},
        {"decisao": "executar", "abertura": "Perfeito, vou redigir."}]
    tid3 = nova()
    evs, t = perguntar(tid3, {"pergunta": "Pode fazer uma procuração para o cliente?", "nuvem": True})
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid3, {"pergunta": "qual o prazo de prescrição da cobrança de aluguel e quando ele começa?", "nuvem": True})
    checar("entrevista" not in fake.etapas(n0), "outra pergunta segue o caminho de sempre", fake.etapas(n0))
    checar((t["contexto"].get("entrevista") or {}).get("status") == "aberta", "e as perguntas ficam para depois")
    n0 = len(fake.chamadas)
    evs, t = perguntar(tid3, {"pergunta": "só ad judicia, com poderes para receber e dar quitação", "nuvem": True,
                              "profundidade": "advogado"})
    checar(fake.etapas(n0) == ["entrevista", "plano_secoes"], "texto livre é resposta: nova análise e o plano", fake.etapas(n0))
    checar("receber e dar quitação" in json.dumps(fake.chamadas[n0]["corpo"], ensure_ascii=False), "a explicação vai à análise")

    print("\nmodo criativo: sem ler documento")
    n0 = len(fake.chamadas)
    evs, t = perguntar(nova(), {"pergunta": "Quais as teses de defesa mais comuns numa ação de despejo?", "nuvem": True,
                                "criativo": True, "profundidade": "advogado"})
    etapas = fake.etapas(n0)
    checar(etapas == ["resposta"], "uma chamada só, sem triagem nem busca", etapas)
    enviado = json.dumps(fake.chamadas[-1]["corpo"], ensure_ascii=False)
    checar("MODO CRIATIVO" in enviado and "PROFUNDIDADE: Advogado" in enviado and "minuta-anterior" not in enviado,
           "a instrução do modo criativo e do nível, sem trecho de documento")
    ultima = t["mensagens"][-1]
    checar(ultima["autor"] == "paulus" and "Resposta comum da nuvem" in ultima["texto"]
           and ultima["cobertura"]["como"]["caminho"] == "criativo", "a resposta fica, marcada como criativa", ultima.get("cobertura"))
    evs, t = perguntar(nova(), {"pergunta": "Quais as teses de defesa numa ação de despejo?", "nuvem": False, "criativo": True})
    checar("nuvem" in t["mensagens"][-1]["texto"], "sem a nuvem, diz por quê", t["mensagens"][-1]["texto"])

    print("\npedir o sim a cada envio: o caminho de sempre")
    api.estado.prefs.dados["nuvem"]["pedir_cada_envio"] = True
    n0 = len(fake.chamadas)
    tid4 = nova()
    saida = {}
    th = threading.Thread(target=lambda: saida.update(r=local.post(f"/api/trabalhos/{tid4}/perguntar",
                                                                    json={"pergunta": "Faça um contrato de comodato", "nuvem": True})),
                          daemon=True)
    th.start()
    esperar(lambda: len(api.estado.fila.pendentes) > 0 or not th.is_alive(), 20)
    for p in list(api.estado.fila.pendentes):
        if getattr(p, "acao", "") == "nuvem.enviar":
            local.post("/api/aprovacoes/decidir", json={"ids": [p.id], "aprovar": False})
    th.join(60)
    checar("entrevista" not in fake.etapas(n0), "sem entrevista nem etapas", fake.etapas(n0))
    api.estado.prefs.dados["nuvem"]["pedir_cada_envio"] = False

    print("\nsem a nuvem (pílula 'Aqui'): o caminho de sempre")
    n0 = len(fake.chamadas)
    evs, t = perguntar(nova(), {"pergunta": "Faça um contrato de prestação de serviços", "nuvem": False})
    checar(fake.etapas(n0) == [], "nada vai à nuvem", fake.etapas(n0))

    print()
    if _falhas:
        print(f"FALHARAM {len(_falhas)}: " + "; ".join(_falhas))
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
