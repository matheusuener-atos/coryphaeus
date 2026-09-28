"""
Portao da I1 - o que chega ao modelo (src/inferencia.py, src/llama_client.py)
e a linha de medicao de cada pergunta (src/medicao.py).

Com o HTTP trocado por um Ollama de mentira, que guarda cada pedido:

  - temperatura 0, semente 42, keep_alive 30m e o teto de resposta por
    tarefa (conversa 700, JSON 800) chegam no payload, vindos do catalogo;
  - a janela nao muda quando o Acervo cresce (antes crescia, e cada mudanca
    recarregava o modelo);
  - prompt que encosta no fim da janela vira o evento "truncou", que a tela
    mostra, e a linha da medicao diz truncou;
  - `think` so vai para modelo que declara a capacidade `thinking`;
  - cada pergunta grava uma linha em data/medicao/perguntas.jsonl, sem o
    texto da pergunta.

Com o Ollama no ar (senao pula): a mesma pergunta duas vezes da a mesma
resposta.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i1_inferencia.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-i1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Resposta:
    def __init__(self, corpo: dict | None = None, linhas: list[dict] | None = None) -> None:
        self._corpo = corpo or {}
        self._linhas = linhas or []
        self.status_code = 200
        self.text = json.dumps(self._corpo)

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._corpo

    def iter_lines(self, decode_unicode=True):
        for linha in self._linhas:
            yield json.dumps(linha)

    def close(self) -> None:
        pass


class Ollama:
    """O Ollama de mentira: guarda os pedidos e responde conforme o modelo."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.capacidades = {"pensa:1b": ["completion", "thinking"]}
        self.lidos = 900  # prompt_eval_count devolvido

    def post(self, url, json=None, stream=False, timeout=None):  # noqa: A002 - o nome e o do requests
        if url.endswith("/api/show"):
            return Resposta({"capabilities": self.capacidades.get(json["model"], ["completion"])})
        self.pedidos.append(json)
        fim = {"done": True, "prompt_eval_count": self.lidos, "eval_count": 12,
               "prompt_eval_duration": 2_000_000_000, "eval_duration": 1_000_000_000}
        if json.get("format") == "json":
            return Resposta({"message": {"content": '{"ok": true}'}, **fim})
        if not stream:
            return Resposta({"message": {"content": "A multa é de dez por cento."}, **fim})
        pedacos = [{"message": {"content": p}} for p in ("A multa ", "é de dez ", "por cento.")]
        return Resposta(linhas=pedacos + [{"message": {"content": ""}, **fim}])

    def get(self, url, timeout=None):
        return Resposta({"models": [{"name": "falso:1b", "digest": "abc123def456"}]})


def test_opcoes() -> None:
    print("\nas opcoes vem do catalogo")
    import inferencia
    from inteligencia.catalogo import Catalogo

    catalogo = Catalogo.carregar()
    checar("conversa" in catalogo.modelos, "o catalogo tem o perfil conversa")
    o = inferencia.opcoes(catalogo, {}, "llama3.2:3b")
    checar((o.temperature, o.seed, o.keep_alive, o.num_ctx) == (0.0, 42, "30m", 16384),
           "temperatura 0, semente 42, 30m, janela 16384", o)
    checar(o.num_predict.get("conversa") == 700 and o.num_predict.get("json") == 800
           and o.num_predict.get("juiz") == 1, "teto por tarefa: 700 / 800 / 1", o.num_predict)
    o2 = inferencia.opcoes(catalogo, {"ia": {"janela_por_modelo": {"qwen:9b": 8192}}}, "qwen:9b")
    checar(o2.num_ctx == 8192, "a janela e configuravel por modelo", o2.num_ctx)
    velho = inferencia.opcoes(catalogo, {"ia": {"opcoes_fixas": False}}, "llama3.2:3b")
    checar(velho.temperature == 0.1 and velho.seed is None and not velho.keep_alive
           and "num_predict" not in velho.options("conversa"), "a chave desligada volta ao de antes",
           velho.options("conversa"))


def test_payload() -> None:
    print("\no que chega ao Ollama")
    import inferencia
    import llama_client
    from inteligencia.catalogo import Catalogo

    falso = Ollama()
    llama_client.requests.post = falso.post
    inferencia.esquecer_capacidades()
    o = inferencia.opcoes(Catalogo.carregar(), {}, "falso:1b")
    c = llama_client.LlamaClient(model="falso:1b", host="http://127.0.0.1:9", opcoes=o)

    c.ask("qual a multa?", "CONTRATO", tarefa="conversa")
    p = falso.pedidos[-1]
    opts = p.get("options", {})
    checar(opts.get("temperature") == 0 and opts.get("seed") == 42, "temperatura 0 e semente 42", opts)
    checar(opts.get("num_ctx") == 16384 and opts.get("num_predict") == 700, "janela 16384 e teto 700", opts)
    checar(p.get("keep_alive") == "30m", "keep_alive 30m", p.get("keep_alive"))
    checar("think" not in p, "sem a capacidade, `think` nem aparece", sorted(p))

    c.ask_json("extraia", "texto")
    checar(falso.pedidos[-1]["options"].get("num_predict") == 800, "JSON: teto 800", falso.pedidos[-1]["options"])
    c.ask("reescreva", "texto", sistema="editor")
    checar("num_predict" not in falso.pedidos[-1]["options"], "tarefa sem teto (editor) nao e cortada",
           falso.pedidos[-1]["options"])

    pensa = llama_client.LlamaClient(model="pensa:1b", host="http://127.0.0.1:9", opcoes=o)
    pensa.ask("qual a multa?", "CONTRATO", tarefa="conversa")
    checar(falso.pedidos[-1].get("think") is False, "modelo com `thinking`: think false", falso.pedidos[-1].get("think"))

    print("\no texto que nao coube")
    falso.lidos = 16384 - 10
    fases: list[tuple[str, dict]] = []
    c.ask("qual a multa?", "CONTRATO", stream=True, tarefa="conversa", on_fase=lambda f, d: fases.append((f, d)))
    cortes = [d for f, d in fases if f == "truncou"]
    medida = next((d for f, d in fases if f == "medida"), {})
    checar(cortes and cortes[0].get("num_ctx") == 16384, "o evento truncou sai", fases)
    checar(medida.get("truncou") is True and medida.get("num_ctx") == 16384, "e a medida diz truncou", medida)
    falso.lidos = 900
    fases.clear()
    c.ask("qual a multa?", "CONTRATO", stream=True, tarefa="conversa", on_fase=lambda f, d: fases.append((f, d)))
    checar(not [f for f, _ in fases if f == "truncou"], "com folga, nao sai", [f for f, _ in fases])
    c.ask("qual a multa?", "CONTRATO", tarefa="conversa")
    checar(c.ultima.get("truncou") is False and c.ultima.get("prompt_eval_count") == 900,
           "sem stream, o corte fica em `ultima`", c.ultima)


def test_na_conversa() -> None:
    print("\nna conversa, pelo servidor")
    from fastapi.testclient import TestClient

    import api
    import inferencia
    import llama_client

    falso = Ollama()
    llama_client.requests.post = falso.post
    llama_client.requests.get = falso.get
    inferencia.esquecer_capacidades()
    api.estado.client = llama_client.LlamaClient(
        model="falso:1b", host="http://127.0.0.1:9",
        opcoes=inferencia.opcoes(api.estado.catalogo, api.estado.prefs.dados, "falso:1b"))
    api.estado.saber.ligada = False

    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "contrato.txt").write_text("CONTRATO DE TESTE. Cláusula 1. A multa por atraso é de dez por cento.",
                                        encoding="utf-8")
    api.estado.recarregar()
    janela = api.estado.client.num_ctx
    checar(janela == 16384, "a janela comeca em 16384", janela)
    (pasta / "grande.txt").write_text("Cláusula de teste com bastante texto. " * 6000, encoding="utf-8")
    api.estado.recarregar()
    checar(api.estado.client.num_ctx == janela, "o Acervo cresceu e a janela nao mudou", api.estado.client.num_ctx)
    checar(api._juiz().num_ctx == janela, "o juiz usa a mesma janela (sem recarga do modelo)", api._juiz().num_ctx)

    c = TestClient(api.app, headers=api.cabecalho_local())

    def perguntar(texto: str) -> list[tuple[str, dict]]:
        id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
        r = c.post(f"/api/trabalhos/{id_}/perguntar",
                   json={"pergunta": texto, "apenas": ["contrato.txt"], "documentos": True})
        eventos = []
        for bloco in r.text.split("\n\n"):
            tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
            corpo = "".join(l[6:] for l in bloco.splitlines() if l.startswith("data: "))
            if tipo:
                eventos.append((tipo, json.loads(corpo or "{}")))
        return eventos

    arquivo = api.DADOS_DIR / "medicao" / "perguntas.jsonl"
    eventos = perguntar("qual a multa segredo-da-pergunta?")
    checar(any(t == "fim" for t, _ in eventos), "a resposta chega ao fim", [t for t, _ in eventos])
    pedido = falso.pedidos[-1]
    checar(pedido["options"].get("num_predict") == 700 and pedido.get("keep_alive") == "30m",
           "a conversa manda o teto e o keep_alive", pedido["options"])
    linhas = [json.loads(l) for l in arquivo.read_text(encoding="utf-8").splitlines()] if arquivo.exists() else []
    ultima = linhas[-1] if linhas else {}
    esperado = {"modelo", "digest", "num_ctx", "prompt_eval_count", "eval_count", "lendo_s", "escrevendo_s",
                "caminho", "nivel", "trechos", "caracteres", "truncou", "fallback"}
    checar(esperado <= set(ultima), "uma linha com todos os campos", sorted(ultima))
    checar(ultima.get("caminho") == "foco" and ultima.get("num_ctx") == 16384
           and ultima.get("prompt_eval_count") == 900 and ultima.get("truncou") is False,
           "caminho, janela e tokens certos", ultima)
    checar(ultima.get("digest") == "abc123def456", "com o digest do modelo", ultima.get("digest"))
    checar("segredo-da-pergunta" not in arquivo.read_text(encoding="utf-8"),
           "o texto da pergunta nao vai para o arquivo")

    falso.lidos = 16384 - 1
    eventos = perguntar("qual a multa?")
    checar(any(t == "truncou" for t, _ in eventos), "o corte chega a tela como evento", [t for t, _ in eventos])
    ultima = json.loads(arquivo.read_text(encoding="utf-8").splitlines()[-1])
    checar(ultima.get("truncou") is True, "e a linha diz truncou", ultima)

    falso.lidos = 900
    antes = len(arquivo.read_text(encoding="utf-8").splitlines())
    api.estado.prefs.dados.setdefault("ia", {})["medir"] = False
    perguntar("qual a multa?")
    checar(len(arquivo.read_text(encoding="utf-8").splitlines()) == antes, "`ia.medir` desligado nao grava")
    api.estado.prefs.dados["ia"]["medir"] = True


def test_com_ollama() -> None:
    print("\ncom o Ollama de verdade")
    import requests

    import importlib

    import llama_client

    importlib.reload(requests)
    llama_client.requests = requests
    try:
        modelos = [m["name"] for m in requests.get("http://127.0.0.1:11434/api/tags", timeout=3).json()["models"]]
    except Exception:  # noqa: BLE001
        print("  (Ollama fora do ar: pulei)")
        return
    modelo = "llama3.2:3b" if "llama3.2:3b" in modelos else (modelos[0] if modelos else "")
    if not modelo:
        print("  (Ollama sem modelo: pulei)")
        return
    import inferencia
    from inteligencia.catalogo import Catalogo

    c = llama_client.LlamaClient(model=modelo, opcoes=inferencia.opcoes(Catalogo.carregar(), {}, modelo))
    contexto = ("CONTRATO DE LOCAÇÃO. Cláusula 5. O aluguel mensal é de R$ 2.300,00, pago até o dia 5. "
                "Cláusula 9. A multa por atraso é de 10% sobre o valor do aluguel, mais juros de 1% ao mês.")
    um = c.ask("Qual a multa por atraso e os juros?", contexto, tarefa="conversa")
    dois = c.ask("Qual a multa por atraso e os juros?", contexto, tarefa="conversa")
    checar(um and um == dois, "a mesma pergunta, duas vezes, a mesma resposta", (um[:120], dois[:120]))


def main() -> int:
    print("=" * 55)
    print("  I1 - ajustes de inferencia")
    print("=" * 55)
    try:
        test_opcoes()
        test_payload()
        test_na_conversa()
        test_com_ollama()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
