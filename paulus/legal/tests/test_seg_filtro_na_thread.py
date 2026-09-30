"""
O filtro de Serviços por equipe vale também dentro da resposta da conversa.

O `search.FILTRO` (e a pessoa da vez) são ContextVar postos pelo porteiro na
requisição. A resposta da conversa roda numa thread da execução
(src/execucoes.py); no Python 3.14 comum a thread nova começa com o contexto
vazio, e a busca da resposta via o Acervo inteiro. Este teste vai de ponta a
ponta, pela conversa de fora:

  Serviço A: Mateus e Sara.   Serviço B: Mateus e João.
  O parecer sigiloso do B fala da fusão Zebralux; a nota do A também cita.

  - a Sara pergunta pela conversa: nem o trecho do parecer do B chega ao
    modelo, nem ele aparece nas fontes da resposta;
  - o João (equipe do B) pergunta o mesmo: o parecer chega (o teste enxerga
    o furo, se ele voltar);
  - a janela do escritório vê os dois.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_seg_filtro_na_thread.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-filtro-thread-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
SIGILO = "Parecer sigiloso"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Anota:
    """O modelo de mentira: guarda o contexto que recebeu, e responde qualquer coisa."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"
    aceita_tarefa = True
    opcoes: dict = {}

    def __init__(self) -> None:
        self.contextos: list[str] = []

    def ask(self, question, context="", *, sistema="", ensinado="", stream=False, on_token=None, on_fase=None,
            parar=None, tarefa="", historico=None):
        self.contextos.append(str(context or ""))
        texto = "A fusão Zebralux está descrita nos documentos."
        if on_token:
            on_token(texto)
        return texto

    def ask_json(self, *a, **k):
        return {}

    def digest(self, model=""):
        return ""


def test_conversa_de_fora() -> None:
    print("\na resposta da conversa respeita a equipe do Serviço")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    anota = Anota()
    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())

    def entrar(nome, email, papel):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        passo = int(time.time() // 30)
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
        if papel != "titular":
            local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes",
                      json={"niveis": {"servicos": "faz", "acervo": "ver"}})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        resp = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(), "turnstile": "ok"})
        assert "pendente" in resp.json(), (resp.status_code, resp.text[:300])
        pend = resp.json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    def cad(nome, email, tipo="colaborador"):
        return local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "email": email}}).json()["id"]

    def perguntar(cliente, pergunta: str) -> dict:
        """Pergunta numa conversa nova e devolve {contexto que chegou ao modelo, fontes da resposta}."""
        t = cliente.post("/api/trabalhos", json={"pedido": "teste do filtro"})
        assert t.status_code == 200, t.text[:200]
        id_ = t.json()["id"]
        antes = len(anota.contextos)
        r = cliente.post(f"/api/trabalhos/{id_}/perguntar", json={"pergunta": pergunta})
        assert r.status_code == 200, r.text[:200]
        limite = time.time() + 30
        while time.time() < limite:
            m = cliente.get(f"/api/trabalhos/{id_}").json()["mensagens"]
            if m and m[-1]["autor"] != "voce" and not api.estado.respondendo.get(id_):
                break
            time.sleep(0.2)
        fontes = [f.get("documento", "") for f in (m[-1].get("fontes") or [])]
        return {"contexto": " ".join(anota.contextos[antes:]), "fontes": fontes, "texto": m[-1].get("texto", "")}

    try:
        entrar("Mateus", "mateus@x.com", "titular")
        f_sara = entrar("Sara", "sara@x.com", "colaborador")
        f_joao = entrar("Joao", "joao@x.com", "colaborador")
        # O modelo de mentira entra depois das entradas: o login conversa com o cliente de verdade.
        api.estado.client = anota
        api.estado.cliente_para = lambda tarefa: anota
        api.estado.saber.ligada = False
        # Sem juiz de uma letra: este teste é da busca, não do roteamento.
        api._juiz = lambda: None
        mateus = cad("Mateus", "mateus@x.com", "socio")
        sara = cad("Sara", "sara@x.com")
        joao = cad("João", "joao@x.com")
        a = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Serviço A", "equipe": [mateus, sara]}}).json()["id"]
        b = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Serviço B", "equipe": [mateus, joao]}}).json()["id"]
        (api.estado.servicos.pasta_de(b, criar=True) / "parecer-do-b.txt").write_text(
            SIGILO + " sobre a fusão Zebralux do serviço B: o preço da fusão Zebralux é de R$ 9.900.000,00.", encoding="utf-8")
        (api.estado.servicos.pasta_de(a, criar=True) / "nota-do-a.txt").write_text(
            "Nota do serviço A: acompanhar a fusão Zebralux pelos jornais.", encoding="utf-8")
        api.estado.recarregar()

        pergunta = "o que diz o parecer sobre a fusão Zebralux?"
        s = perguntar(f_sara, pergunta)
        checar(s["contexto"] and SIGILO not in s["contexto"], "Sara: o parecer do B não chega ao modelo",
               s["contexto"][:300])
        checar(all("parecer-do-b" not in x for x in s["fontes"]), "Sara: nem aparece nas fontes da resposta", s["fontes"])
        checar("9.900.000" not in s["texto"], "Sara: nem o valor do B na resposta")

        j = perguntar(f_joao, pergunta)
        checar(SIGILO in j["contexto"], "João (equipe do B): o parecer chega — o teste enxerga o furo", j["contexto"][:300])

        l = perguntar(local, pergunta)
        checar(SIGILO in l["contexto"], "a janela do escritório vê o parecer", l["contexto"][:300])
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True


def main() -> int:
    test_conversa_de_fora()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
