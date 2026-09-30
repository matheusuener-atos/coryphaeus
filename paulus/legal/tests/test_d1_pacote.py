"""
D1 - o pacote de escrita e a porta do aparelho (src/aparelho.py).

Com o cliente do modelo de verdade e a rede trocada por um Ollama de mentira
(o teste segura e solta cada chamada), contas de fora e Serviços por equipe:

  - conta sem liberação, recurso desligado, janela local: nada de pacote, a
    resposta é do escritório, com o motivo;
  - o pacote: só trechos (nunca o documento inteiro), dentro do orçamento da
    busca, sem trecho de Serviço que a pessoa não vê, sem os lembretes do
    escritório; o evento da execução leva só o id e a assinatura;
  - a porta: o conteúdo sai uma vez, para a mesma sessão; devolver com a
    assinatura errada, de outra sessão, já usado ou vencido: recusa;
  - enquanto o aparelho escreve, a vez do modelo volta para a fila;
  - até a D3, a conferência reprova tudo: o escritório reescreve, e a
    resposta diz onde foi escrita e por quê; abandonar e vencer também;
  - caso "só no escritório": sem pacote, e a resposta vai para o escritório;
  - tudo na auditoria.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d1_pacote.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-d1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

import fila_modelo  # noqa: E402

_falhas: list[str] = []
LEMBRETE = "LEMBRETE-INTERNO-DO-ESCRITORIO-7731"
SIGILO = "Zebralux"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, segundos: float = 20.0) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.05)
    return False


class Chamada:
    def __init__(self, dados: dict) -> None:
        self.soltar = threading.Event()
        self.soltar.set()                     # o escritório responde na hora
        self.pedido = dict(fila_modelo.PEDIDO.get() or {})
        self.dados = dados


class Resposta:
    def __init__(self, c: Chamada) -> None:
        self.c, self.status_code = c, 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        self.c.soltar.wait(30)
        return {"message": {"content": "Escrita no escritório."}, "done": True}

    def iter_lines(self, decode_unicode=True):
        self.c.soltar.wait(30)
        yield json.dumps({"message": {"content": "Escrita no escritório."}})
        yield json.dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5})

    def close(self) -> None:
        pass


class Ollama:
    def __init__(self) -> None:
        self.chamadas: list[Chamada] = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        c = Chamada(json or {})
        self.chamadas.append(c)
        return Resposta(c)

    def get(self, url, **k):
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"models": []})


def test_unidade() -> None:
    print("\no pacote, por dentro")
    import aparelho

    est = SimpleNamespace(prefs=SimpleNamespace(dados={"aparelho": {"ligado": False}}))
    pode, motivo = aparelho.pode_escrever(est, None)
    checar(not pode and "não ligou" in motivo, "recurso desligado: não", motivo)
    est.prefs.dados["aparelho"]["ligado"] = True
    pode, motivo = aparelho.pode_escrever(est, None)
    checar(not pode and "janela do escritório" in motivo, "janela local: não", motivo)
    fora = SimpleNamespace(scope={"state": {"paulus_pessoa": {"conta_id": 5, "nome": "Rui", "hash": "s1",
                                                              "permissoes": {"aparelho": "nao", "acervo": "ver"}}}})
    checar(aparelho.pode_escrever(est, fora)[1].startswith("o titular não liberou"), "conta sem o nível: não")
    fora.scope["state"]["paulus_pessoa"]["permissoes"]["aparelho"] = "faz"
    checar(aparelho.pode_escrever(est, fora) == (True, ""), "com o nível do titular: sim")

    class H:
        def __init__(self, caminho, texto):
            self.chunk = SimpleNamespace(doc_path=caminho, text=texto)
    est.fila_modelo = SimpleNamespace(sair=lambda v: None)
    est.pasta = str(TMP)
    esc = aparelho.Escrita(est, fora, "t")
    base = dict(pergunta="p", mensagens=[], parametros={})
    checar(esc.preparar(**base, fontes=[], hits=[], caminho="tudo", por_trechos=False) is None
           and "Acervo inteiro" in esc.motivo, "o Acervo inteiro não sai", esc.motivo)
    checar(esc.preparar(**base, fontes=[], hits=[], caminho="foco", por_trechos=False) is None
           and "documento inteiro" in esc.motivo, "o documento inteiro não sai", esc.motivo)
    grande = [{"documento": "a.txt", "texto": "x" * 5000}, {"documento": "b.txt", "texto": "y" * 5000}]
    checar(esc.preparar(**base, fontes=grande, hits=[H("a.txt", ""), H("b.txt", "")], caminho="busca", por_trechos=True) is None
           and "demais" in esc.motivo, "acima do orçamento da busca (9.000 caracteres): não sai", esc.motivo)
    import search

    tok = search.FILTRO.set(lambda c: "segredo" not in c)
    try:
        checar(esc.preparar(**base, fontes=[{"documento": "segredo.txt", "texto": "t"}], hits=[H("/x/segredo.txt", "t")],
                            caminho="busca", por_trechos=True) is None and "não é de documento" in esc.motivo,
               "trecho fora do filtro da pessoa: não sai (defesa em profundidade)", esc.motivo)
    finally:
        search.FILTRO.reset(tok)


def _evento(caminho_exec_dir: Path, conversa: str, tipo: str) -> dict | None:
    for f in caminho_exec_dir.glob("*.jsonl"):
        linhas = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        if linhas and linhas[0].get("conversa_id") == conversa:
            for l in linhas:
                if l["tipo"] == tipo:
                    return l["dados"]
    return None


def test_api() -> None:
    print("\npela API, com contas de fora")
    import requests

    import api
    import aparelho
    import llama_client
    import segredos
    from fastapi.testclient import TestClient

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return
    from acesso.contas import codigo_totp

    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    ia = api.estado.prefs.dados.setdefault("ia", {})
    ia.update({"leitura": "trechos", "denso": False})
    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())

    def entrar(nome, email, papel, niveis=None):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30)))
        if niveis:
            local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": niveis})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2",
                                                                            "User-Agent": "Teste/" + nome})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    def cad(nome, email, tipo="colaborador"):
        return local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "email": email}}).json()["id"]

    try:
        entrar("Mateus", "mateus@x.com", "titular")
        helena = entrar("Helena", "helena@x.com", "colaborador", {"aparelho": "faz", "servicos": "faz", "acervo": "ver"})
        rui = entrar("Rui", "rui@x.com", "colaborador", {"servicos": "faz", "acervo": "ver"})
        api.estado.client = cliente
        api.estado.cliente_para = lambda tarefa: cliente
        api.check_ollama = lambda modelo: (True, "")
        mateus, h, r_ = cad("Mateus", "mateus@x.com", "socio"), cad("Helena", "helena@x.com"), cad("Rui", "rui@x.com")
        s1 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Locação da Clínica", "equipe": [mateus, h, r_]}}).json()["id"]
        s2 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Fusão", "equipe": [mateus]}}).json()["id"]
        clausulas = "\n\n".join(f"Cláusula {i}. O locatário cumpre a obrigação número {i} do contrato de locação, "
                                f"com prazo de {i} dias e aviso por escrito ao locador." for i in range(1, 160))
        (api.estado.servicos.pasta_de(s1, criar=True) / "contrato-clinica.txt").write_text(
            "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\n" + clausulas + "\n\nCláusula 160. A multa por atraso no aluguel é de 10% "
            "sobre o valor devido.", encoding="utf-8")
        (api.estado.servicos.pasta_de(s2, criar=True) / "parecer-fusao.txt").write_text(
            f"Parecer sigiloso sobre a fusão {SIGILO}: a multa de saída da fusão {SIGILO} é de 40%.", encoding="utf-8")
        api.estado.recarregar()
        local.post("/api/contextos", json={"titulo": "interno", "texto": LEMBRETE})
        execs = Path(os.environ["PAULUS_DADOS"]) / "execucoes"

        def perguntar(cli, texto, aparelho_=True):
            tid = cli.post("/api/trabalhos", json={"pedido": "d1"}).json()["id"]
            caixa = {"tid": tid}

            def rodar():
                caixa["r"] = cli.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": texto, "aparelho": aparelho_})
            caixa["t"] = threading.Thread(target=rodar, daemon=True)
            caixa["t"].start()
            return caixa

        def fim(caixa, cli):
            caixa["t"].join(30)
            ok = esperar(lambda: not api.estado.respondendo.get(caixa["tid"]), 30)
            m = cli.get(f"/api/trabalhos/{caixa['tid']}").json()["mensagens"]
            return m[-1] if ok and m else {}

        pergunta = "qual a multa por atraso no aluguel e a multa da fusão?"

        print("  quem não pode")
        api.estado.prefs.dados.setdefault("aparelho", {})["ligado"] = False
        c = perguntar(helena, pergunta)
        m = fim(c, helena)
        checar(m.get("cobertura", {}).get("como", {}).get("escrita", {}).get("motivo", "").startswith("o escritório não ligou"),
               "recurso desligado: escrita no escritório, com o motivo", m.get("cobertura", {}).get("como", {}).get("escrita"))
        api.estado.prefs.dados["aparelho"]["ligado"] = True
        c = perguntar(rui, pergunta)
        m = fim(c, rui)
        checar("não liberou" in m["cobertura"]["como"]["escrita"]["motivo"] and _evento(execs, c["tid"], "aparelho") is None,
               "conta sem liberação: nenhum pacote, escrita no escritório", m["cobertura"]["como"]["escrita"])
        c = perguntar(local, pergunta)
        m = fim(c, local)
        checar("janela do escritório" in m["cobertura"]["como"]["escrita"]["motivo"], "a janela local escreve aqui")

        print("  o pacote")
        n0 = len(ollama.chamadas)
        c = perguntar(helena, pergunta)
        if not esperar(lambda: _evento(execs, c["tid"], "aparelho") is not None):
            m = fim(c, helena)
            checar(False, "a Helena recebe o aviso do pacote", (m.get("cobertura") or {}).get("como"))
            return
        ev = _evento(execs, c["tid"], "aparelho")
        checar(set(ev) == {"pacote", "assinatura", "expira_s"}, "o evento no disco leva só id, assinatura e validade", ev)
        checar(len(ollama.chamadas) == n0 and not any(v["nome"] == "Helena" for v in api.estado.fila_modelo.foto()),
               "enquanto o aparelho escreve, o modelo do escritório não foi chamado e a vez voltou para a fila")
        pid, ass = ev["pacote"], ev["assinatura"]
        checar(rui.get(f"/api/aparelho/pacote/{pid}", params={"assinatura": ass}).status_code == 403,
               "outra sessão não pega o pacote, nem com a assinatura")
        checar(helena.get(f"/api/aparelho/pacote/{pid}", params={"assinatura": "x" * 64}).status_code == 403,
               "assinatura errada: recusa")
        r = helena.get(f"/api/aparelho/pacote/{pid}", params={"assinatura": ass})
        conteudo = r.json()
        todo = json.dumps(conteudo, ensure_ascii=False)
        checar(r.status_code == 200 and conteudo["trechos"], "a mesma sessão recebe o conteúdo", r.status_code)
        checar(SIGILO not in todo, "o parecer do Serviço que a Helena não vê não está no pacote")
        checar(LEMBRETE not in todo, "os lembretes do escritório não vão ao aparelho")
        doc_inteiro = (api.estado.servicos.pasta_de(s1) / "contrato-clinica.txt").read_text(encoding="utf-8")
        checar(all(len(t["texto"]) < len(doc_inteiro) for t in conteudo["trechos"])
               and sum(len(t["texto"]) for t in conteudo["trechos"]) <= aparelho.ORCAMENTO_CARACTERES,
               "só trechos, dentro do orçamento da busca", [len(t["texto"]) for t in conteudo["trechos"]])
        checar(conteudo["mensagens"][0]["role"] == "system" and conteudo["mensagens"][-1]["role"] == "user"
               and pergunta in conteudo["mensagens"][-1]["content"], "as mensagens são as de uma pergunta ao modelo")
        checar(helena.get(f"/api/aparelho/pacote/{pid}", params={"assinatura": ass}).status_code == 409,
               "o conteúdo sai uma vez só")
        checar(rui.post(f"/api/aparelho/pacote/{pid}/devolver", json={"assinatura": ass, "texto": "x"}).status_code == 403,
               "devolver de outra sessão: recusa")
        # Um número que não está nos trechos: a conferência (D3) reprova.
        r = helena.post(f"/api/aparelho/pacote/{pid}/devolver", json={"assinatura": ass, "texto": "A multa é de 99%."})
        checar(r.status_code == 200, "a Helena devolve o texto")
        checar(helena.post(f"/api/aparelho/pacote/{pid}/devolver", json={"assinatura": ass, "texto": "de novo"}).status_code == 409,
               "devolver de novo: recusa (já usado)")
        m = fim(c, helena)
        esc = m["cobertura"]["como"]["escrita"]
        checar(esc["onde"] == "escritorio" and esc["motivo"] == "conferência reprovou" and "Escrita no escritório" in m["texto"],
               "número fora dos trechos: a conferência reprova, o escritório reescreve, e a resposta diz por quê", esc)
        checar(len(ollama.chamadas) == n0 + 1 and ollama.chamadas[-1].dados.get("messages"),
               "o escritório chamou o modelo uma vez, depois de o aparelho devolver")

        print("  abandonar e vencer")
        c = perguntar(helena, pergunta)
        esperar(lambda: _evento(execs, c["tid"], "aparelho") is not None)
        ev = _evento(execs, c["tid"], "aparelho")
        helena.get(f"/api/aparelho/pacote/{ev['pacote']}", params={"assinatura": ev["assinatura"]})
        r = helena.post(f"/api/aparelho/pacote/{ev['pacote']}/abandonar", json={"assinatura": ev["assinatura"], "parcial": "A mul"})
        m = fim(c, helena)
        checar(r.status_code == 200 and m["cobertura"]["como"]["escrita"]["motivo"] == "o aparelho não terminou"
               and "Escrita no escritório" in m["texto"], "abandonou: o escritório termina", m["cobertura"]["como"]["escrita"])
        aparelho.VALIDADE_S = 1
        c = perguntar(helena, pergunta)
        esperar(lambda: _evento(execs, c["tid"], "aparelho") is not None)
        ev = _evento(execs, c["tid"], "aparelho")
        time.sleep(1.6)
        r = helena.post(f"/api/aparelho/pacote/{ev['pacote']}/devolver", json={"assinatura": ev["assinatura"], "texto": "tarde"})
        m = fim(c, helena)
        checar(r.status_code == 410 and m["cobertura"]["como"]["escrita"]["motivo"] == "o aparelho não terminou",
               "pacote vencido: devolver é recusado e o escritório escreve", r.status_code)
        aparelho.VALIDADE_S = 600

        print("  caso só no escritório")
        aparelho.so_no_escritorio().guardar([{"tipo": "servico", "valor": s1}])
        c = perguntar(helena, pergunta)
        m = fim(c, helena)
        checar(_evento(execs, c["tid"], "aparelho") is None and "só no escritório" in m["cobertura"]["como"]["escrita"]["motivo"],
               "o caso marcado não sai: sem pacote, escrita no escritório com o motivo", m["cobertura"]["como"]["escrita"])
        aparelho.so_no_escritorio().guardar([])

        print("  a auditoria")
        acessos = [json.loads(l) for l in (Path(os.environ["PAULUS_DADOS"]) / "acesso" / "acessos.jsonl").read_text(encoding="utf-8").splitlines()]
        linhas = [a["alvo"] for a in acessos if a["acao"] == "aparelho" and a["pessoa"] == "Helena"]
        checar(any("recebeu" in l and "contrato-clinica.txt" in l and "navegador " in l for l in linhas)
               and any("devolveu" in l for l in linhas) and any("abandonou" in l for l in linhas),
               "entrega, devolução e abandono na auditoria: pessoa, aparelho (sem identificador invasivo), documentos",
               linhas[:3])
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True


def main() -> int:
    print("=" * 55)
    print("  D1 — o pacote e a porta")
    print("=" * 55)
    test_unidade()
    test_api()
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
