"""
D3 - a conferência do texto do aparelho e a retomada no escritório
(src/aparelho_conferencia.py, src/aparelho.py, habilidades/perguntar.py).

Com o cliente do modelo de verdade e a rede trocada por um Ollama de mentira
(que anota o que recebeu), a Helena (de fora, com o nível do aparelho) e um
aparelho simulado pela API:

  - texto com número que não está nos trechos: refeito no escritório;
  - texto com marca para trecho que não foi mandado: refeito;
  - lei inventada: sai do texto, como no escritório, e o resto fica;
  - texto aprovado: fica igual ao que o aparelho mandou, marcado como
    escrito no aparelho e conferido;
  - aparelho que some no meio: o escritório continua a partir do parcial (o
    modelo recebe o parcial como começo da resposta) e a resposta diz onde
    cada parte foi escrita; parcial com número inventado: do zero.

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
TMP = Path(tempfile.mkdtemp(prefix="paulus-d3-"))
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
    print("  D3 — conferência e retomada")
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

        def rodada(fazer):
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
            th.join(60)
            esperar(lambda: not api.estado.respondendo.get(tid))
            m = helena.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
            return m, len(ollama.pedidos) - n0

        def devolver(texto):
            return lambda pid, ass, c: helena.post(f"/api/aparelho/pacote/{pid}/devolver", json={"assinatura": ass, "texto": texto})

        print("\na conferência")
        m, chamadas = rodada(devolver("A multa por atraso no aluguel é de 25% sobre o valor devido [T1]."))
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(esc.get("onde") == "escritorio" and esc.get("motivo") == "conferência reprovou" and chamadas == 1
               and "Escrita no escritório" in m.get("texto", ""), "número que não está nos trechos (25%): refeito no escritório", esc)
        m, chamadas = rodada(devolver("A multa por atraso no aluguel é de 10% sobre o valor devido [T9]."))
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(esc.get("onde") == "escritorio" and esc.get("motivo") == "conferência reprovou" and chamadas == 1,
               "marca para trecho que não foi mandado ([T9]): refeito", esc)
        m, chamadas = rodada(devolver("A multa por atraso no aluguel é de 10% sobre o valor devido, conforme o art. 999 do CDC [T1]."))
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(esc.get("onde") == "aparelho" and "art. 999" not in m.get("texto", "") and "10%" in m.get("texto", "") and chamadas == 0,
               "lei inventada: sai do texto, como no escritório, e o resto fica escrito no aparelho", (esc, m.get("texto")))
        aprovado = "A multa por atraso no aluguel é de 10% sobre o valor devido [T1]."
        m, chamadas = rodada(devolver(aprovado))
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(m.get("texto") == aprovado and esc.get("onde") == "aparelho" and esc.get("conferida") and chamadas == 0
               and esc.get("partes") == [{"onde": "aparelho", "caracteres": len(aprovado)}],
               "texto aprovado: igual ao que o aparelho mandou, marcado como escrito nele e conferido", (m.get("texto"), esc))

        print("\na retomada")
        aparelho.SILENCIO_S = 1
        parcial = "A multa por atraso no aluguel é de 10% sobre"

        def some_no_meio(pid, ass, c):
            helena.post(f"/api/aparelho/pacote/{pid}/pedaco", json={"assinatura": ass, "texto": parcial})
        m, chamadas = rodada(some_no_meio)
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        ultimo = (ollama.pedidos[-1] or [{}])[-1] if ollama.pedidos else {}
        checar(ultimo.get("role") == "assistant" and ultimo.get("content") == parcial,
               "o aparelho sumiu no meio: o modelo do escritório recebe o parcial como começo da resposta", ultimo)
        checar(m.get("texto") == parcial + CONTINUACAO.rstrip() or m.get("texto", "").startswith(parcial) and CONTINUACAO.strip()[:10] in m.get("texto", ""),
               "e a resposta é o parcial do aparelho mais a continuação do escritório", m.get("texto"))
        checar(esc.get("onde") == "escritorio" and esc.get("motivo") == "o aparelho não terminou"
               and [p["onde"] for p in esc.get("partes") or []] == ["aparelho", "escritorio"],
               "e diz onde cada parte foi escrita", esc)

        def some_com_numero_inventado(pid, ass, c):
            helena.post(f"/api/aparelho/pacote/{pid}/pedaco", json={"assinatura": ass, "texto": "A multa é de 77% sobre"})
        m, chamadas = rodada(some_com_numero_inventado)
        ultimo = (ollama.pedidos[-1] or [{}])[-1] if ollama.pedidos else {}
        esc = m.get("cobertura", {}).get("como", {}).get("escrita", {})
        checar(ultimo.get("role") == "user" and "77%" not in m.get("texto", "") and not esc.get("partes"),
               "parcial com número inventado: o escritório escreve do zero", (ultimo.get("role"), m.get("texto"), esc))
        aparelho.SILENCIO_S = 45

        acessos = [json.loads(l) for l in (Path(os.environ["PAULUS_DADOS"]) / "acesso" / "acessos.jsonl").read_text(encoding="utf-8").splitlines()]
        alvos = [a["alvo"] for a in acessos if a["acao"] == "aparelho"]
        checar(any("reprovado na conferência" in a and "25" in a for a in alvos) and any("tirou do texto" in a and "999" in a for a in alvos),
               "o que reprovou e o que a conferência tirou vão para a auditoria", alvos[-4:])
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
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
