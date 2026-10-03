"""
N11 - a posição na fila da resposta que volta do aparelho (habilidades/perguntar.py, js/03-assistente.js).

Com o circuito da D3 (o Ollama de mentira, a Helena de fora com o nível do
aparelho e o aparelho simulado pela API), e a fila do modelo ligada (F1):

  - o texto do aparelho reprovado volta para o escritório; com outra pessoa
    na vez do modelo, a resposta espera e manda a posição para a tela
    (evento `fila` marcado `depois_do_aparelho`), e o detalhe diz "voltou ao
    escritório e espera a vez";
  - liberada a vez, o escritório escreve, e a vez é devolvida no fim;
  - sem ninguém na frente, nenhum evento de fila;
  - a tela: o texto da fila diz que a resposta voltou ao escritório.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d3_conferencia.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-n11-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
CONTINUACAO = " o valor devido, conforme a cláusula."


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
    """Responde na hora; anota as mensagens. Com a resposta começada pelo assistente, devolve a continuação."""

    def __init__(self) -> None:
        self.pedidos: list[list[dict]] = []

    def post(self, url, json=None, stream=False, timeout=None, **k):
        msgs = (json or {}).get("messages") or []
        self.pedidos.append(msgs)
        texto = CONTINUACAO if msgs and msgs[-1].get("role") == "assistant" else "Escrita no escritório."

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


def _evento(execs: Path, conversa: str, tipo: str) -> dict | None:
    for f in execs.glob("*.jsonl"):
        linhas = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        if linhas and linhas[0].get("conversa_id") == conversa:
            for l in linhas:
                if l["tipo"] == tipo:
                    return l["dados"]
    return None


def main() -> int:
    print("=" * 55)
    print("  N11 — a fila depois do aparelho")
    print("=" * 55)
    import requests

    import api
    import aparelho
    import llama_client
    import segredos
    from fastapi.testclient import TestClient

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return 0
    from acesso.contas import codigo_totp

    ollama = Ollama()
    llama_client.requests = SimpleNamespace(post=ollama.post, get=ollama.get, exceptions=requests.exceptions)
    cliente = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9")
    api.estado.saber.ligada = False
    api._juiz = lambda: None
    api.estado.prefs.dados.setdefault("ia", {}).update({"leitura": "trechos", "denso": False})
    api.estado.prefs.dados.setdefault("aparelho", {})["ligado"] = True
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
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2", "User-Agent": "T/" + nome})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    try:
        entrar("Mateus", "mateus@x.com", "titular")
        helena = entrar("Helena", "helena@x.com", "colaborador", {"aparelho": "faz", "acervo": "ver"})
        api.estado.client = cliente
        api.estado.cliente_para = lambda tarefa, **k: cliente
        pasta = Path(api.estado.pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        clausulas = "\n\n".join(f"Cláusula {i}. O locatário cumpre a obrigação número {i}, com aviso por escrito."
                                for i in range(1, 160))
        (pasta / "contrato-clinica.txt").write_text(
            "CONTRATO DE LOCAÇÃO DA CLÍNICA.\n\n" + clausulas +
            "\n\nCláusula 160. A multa por atraso no aluguel é de 10% sobre o valor devido.", encoding="utf-8")
        api.estado.recarregar()
        execs = Path(os.environ["PAULUS_DADOS"]) / "execucoes"
        pergunta = "qual a multa por atraso no aluguel?"

        def rodada(fazer, depois=None):
            """Pergunta pela Helena, pega o pacote, deixa `fazer(pid, assinatura)` agir como o aparelho, e devolve a mensagem final."""
            tid = helena.post("/api/trabalhos", json={"pedido": "d3"}).json()["id"]
            n0 = len(ollama.pedidos)
            th = threading.Thread(target=lambda: helena.post(f"/api/trabalhos/{tid}/perguntar",
                                                             json={"pergunta": pergunta, "aparelho": True}), daemon=True)
            th.start()
            if not esperar(lambda: _evento(execs, tid, "aparelho") is not None):
                return {}, 0
            ev = _evento(execs, tid, "aparelho")
            conteudo = helena.get(f"/api/aparelho/pacote/{ev['pacote']}", params={"assinatura": ev["assinatura"]}).json()
            fazer(ev["pacote"], ev["assinatura"], conteudo)
            if depois is not None:
                depois(tid)
            th.join(60)
            esperar(lambda: not api.estado.respondendo.get(tid))
            m = helena.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
            return m, len(ollama.pedidos) - n0

        api.estado.prefs.dados.setdefault("aparelho", {})["fila"] = True
        fila = api.estado.fila_modelo

        def devolver(texto):
            return lambda pid, ass, c: helena.post(f"/api/aparelho/pacote/{pid}/devolver", json={"assinatura": ass, "texto": texto})

        reprovado = devolver("A multa por atraso no aluguel é de 25% sobre o valor devido [T1].")
        print("\ncom alguém na vez do modelo")
        outro = fila.entrar("conta:999", rotulo="outra conversa", origem="conversa", nome="Rui")
        checar(fila.esperar(outro, timeout=1), "(o Rui está com a vez)")
        visto = {}

        def soltar(tid):
            visto["fila"] = esperar(lambda: _evento(execs, tid, "fila") is not None, 20)
            visto["posicao"] = fila.posicao(next(v for v in fila._fila if v.dono != "conta:999")) if len(fila._fila) > 1 else None
            fila.sair(outro)

        m, chamadas = rodada(reprovado, soltar)
        tid_ultimo = [f for f in execs.glob("*.jsonl")]
        ev_fila = None
        for f in execs.glob("*.jsonl"):
            linhas = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            for l in linhas:
                if l["tipo"] == "fila" and (l.get("dados") or {}).get("depois_do_aparelho"):
                    ev_fila = l["dados"]
        checar(visto.get("fila") and ev_fila and ev_fila.get("posicao") == 1 and ev_fila["na_frente"][0]["nome"] == "Rui", "reprovado e com o Rui na vez: a posição (e quem está na frente) vai para a tela", (visto, ev_fila))
        checar(chamadas >= 1 and "Escrita no escritório" in (m.get("texto") or ""), "liberada a vez, o escritório escreve", (chamadas, (m.get("texto") or "")[:80]))
        detalhes = json.dumps((m.get("cobertura") or {}).get("detalhes") or [], ensure_ascii=False)
        checar("esperando a vez no modelo" in detalhes, "o detalhe da resposta guarda a espera", detalhes[:300])
        checar(not fila._fila, "no fim, a vez foi devolvida (a fila está vazia)", [v.dono for v in fila._fila])

        print("\nsem ninguém na frente")
        antes = {f.name for f in execs.glob("*.jsonl")}
        m, chamadas = rodada(reprovado)
        novos = [f for f in execs.glob("*.jsonl") if f.name not in antes]
        tem_fila = any(json.loads(l)["tipo"] == "fila" for f in novos for l in f.read_text(encoding="utf-8").splitlines() if l.strip())
        checar(chamadas >= 1 and not tem_fila, "passa direto, sem evento de fila", tem_fila)
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False

    print("\na tela")
    js = (RAIZ / "frontend" / "js" / "03-assistente.js").read_text(encoding="utf-8")
    checar('d.depois_do_aparelho ? "a resposta voltou ao escritório e "' in js, "o texto da fila diz que a resposta voltou ao escritório")

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
