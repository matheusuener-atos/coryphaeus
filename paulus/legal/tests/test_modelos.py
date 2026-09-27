"""
Testes da camada de modelos do PAULUS (src/modelos.py e /api/modelos).

  - a delegação: tarefa sem modelo vai ao padrão; modelo delegado que foi
    removido volta ao padrão; Ollama fora ("não sei") confia na escolha;
  - o nome do modelo é conferido antes de ir ao Ollama;
  - o download: andamento em bytes somando as camadas, "success" conclui,
    erro do Ollama vira frase legível, cancelar para e marca cancelado;
  - pela API: o padrão não pode ser removido, tarefa desconhecida é recusada,
    delegar e devolver ao padrão valem na hora.

Sem Ollama: o HTTP é trocado por respostas prontas.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_modelos.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import modelos  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_delegacao() -> None:
    print("\nquem faz cada tarefa")
    f = modelos.modelo_da_tarefa
    checar(f("email", {}, "padrao:3b", {"padrao:3b"}) == "padrao:3b", "sem escolha: o padrão")
    checar(f("email", {"email": "leve:1b"}, "padrao:3b", {"padrao:3b", "leve:1b"}) == "leve:1b", "com escolha instalada: ela")
    checar(f("email", {"email": "leve:1b"}, "padrao:3b", {"padrao:3b"}) == "padrao:3b", "escolha removida: volta ao padrão")
    checar(f("email", {"email": "leve:1b"}, "padrao:3b", None) == "leve:1b", "Ollama fora (não sei): confia na escolha")
    checar(set(modelos.IDS_TAREFAS) == {"conversa", "juiz", "email", "redacao", "resumos", "leitura"}, "as seis tarefas")


def test_nome() -> None:
    print("\no nome do modelo")
    for bom in ("llama3.2:3b", "qwen2.5:7b", "hf.co/usuario/modelo-GGUF:Q4_K_M".lower(), "alibayram/ministral-3b-instruct:latest"):
        checar(modelos.nome_valido(bom), "aceita " + bom)
    for ruim in ("", "rm -rf /", "a", "modelo com espaço", "../../etc", "x" * 200):
        checar(not modelos.nome_valido(ruim), "recusa " + repr(ruim[:20]))


class _Resp:
    def __init__(self, linhas, espera=0.0, status=200):
        self.linhas = linhas
        self.espera = espera
        self.status_code = status
        self.fechada = False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            erro = requests.HTTPError("erro")
            erro.response = self
            raise erro

    def json(self):
        return {"error": "pull model manifest: file does not exist"}

    def iter_lines(self, decode_unicode=True):
        for l in self.linhas:
            if self.espera:
                time.sleep(self.espera)
            if self.fechada:
                return
            yield json.dumps(l)

    def close(self):
        self.fechada = True


def _esperar(b, limite=5.0):
    fim = time.time() + limite
    while b.estado.get("andando") and time.time() < fim:
        time.sleep(0.05)


def test_download() -> None:
    print("\no download pela API do Ollama")
    linhas = [
        {"status": "pulling manifest"},
        {"status": "pulling a", "digest": "a", "total": 1_000_000_000, "completed": 500_000_000},
        {"status": "pulling b", "digest": "b", "total": 1_000_000_000, "completed": 0},
        {"status": "pulling a", "digest": "a", "total": 1_000_000_000, "completed": 1_000_000_000},
        {"status": "pulling b", "digest": "b", "total": 1_000_000_000, "completed": 1_000_000_000},
        {"status": "verifying sha256 digest"}, {"status": "writing manifest"}, {"status": "success"},
    ]
    avisado = []
    b = modelos.Baixador(lambda: "http://x", postar=lambda *a, **k: _Resp(linhas))
    b.iniciar("leve:1b", ao_terminar=avisado.append)
    _esperar(b)
    e = b.andamento()
    checar(e["pronto"] and e["progresso"] == 100 and e["total_gb"] == 2.0 and not e["andando"],
           "soma as camadas em bytes e termina pronto", e)
    checar(avisado == ["leve:1b"], "avisa quem pediu quando termina", avisado)

    b = modelos.Baixador(lambda: "http://x", postar=lambda *a, **k: _Resp([{"status": "pulling manifest"}], status=500))
    b.iniciar("naoexiste:9b")
    _esperar(b)
    checar("não existe no registro" in b.andamento()["erro"], "erro do Ollama vira frase legível", b.andamento())

    lentas = [{"status": "pulling a", "digest": "a", "total": 100, "completed": i} for i in range(0, 100, 5)]
    b = modelos.Baixador(lambda: "http://x", postar=lambda *a, **k: _Resp(lentas, espera=0.05))
    b.iniciar("lento:3b")
    time.sleep(0.2)
    try:
        b.iniciar("outro:1b")
        checar(False, "um download de cada vez")
    except RuntimeError:
        checar(True, "um download de cada vez")
    b.cancelar()
    _esperar(b)
    e = b.andamento()
    checar(e["cancelado"] and not e["pronto"] and not e["andando"], "cancelar para e marca cancelado", e)
    try:
        b.iniciar("rm -rf /")
        checar(False, "nome inválido é recusado antes do Ollama")
    except ValueError:
        checar(True, "nome inválido é recusado antes do Ollama")


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    padrao = api.estado.client.model
    original = api.modelos_mod.instalados
    api.modelos_mod.instalados = lambda host: [{"nome": padrao, "gb": 2.0}, {"nome": "leve:1b", "gb": 1.3}]
    api.estado._presentes = (0.0, None)
    try:
        checar(c.post("/api/modelos/remover", json={"nome": padrao}).status_code == 409, "o padrão não pode ser removido")
        checar(c.post("/api/modelos/tarefa", json={"tarefa": "nada", "modelo": ""}).status_code == 400, "tarefa desconhecida é recusada")
        checar(c.post("/api/modelos/tarefa", json={"tarefa": "email", "modelo": "sumiu:7b"}).status_code == 404,
               "modelo que não está instalado não é delegado")
        r = c.post("/api/modelos/tarefa", json={"tarefa": "email", "modelo": "leve:1b"}).json()
        checar(r["em_uso"] == "leve:1b" and api.estado.cliente_para("email").model == "leve:1b",
               "delegar vale na hora: o e-mail passa a usar o leve", r)
        checar(api.estado.cliente_para("conversa") is api.estado.client, "as outras tarefas continuam no padrão")
        r = c.post("/api/modelos/tarefa", json={"tarefa": "email", "modelo": ""}).json()
        checar(r["em_uso"] == padrao, "vazio devolve ao padrão", r)
    finally:
        api.modelos_mod.instalados = original
        api.estado.prefs.atualizar({"tarefas_modelo": {"email": ""}})
        api.estado._presentes = (0.0, None)


def test_escolha_do_instalador() -> None:
    print("\na escolha da tela Modelo de IA do instalador")
    import api

    padrao_antes = api.estado.client.model
    originais = (api.ollama_ligar, api.modelos_mod.instalados, api.estado.baixador.iniciar, api.preferencias_gravar)
    iniciados, gravados = [], []
    api.ollama_ligar = lambda: {"ligado": True}
    api.modelos_mod.instalados = lambda host: [{"nome": "llama3.2:3b", "gb": 2.0}]
    api.preferencias_gravar = lambda dados: gravados.append(dados) or {}

    def iniciar(nome, ao_terminar=None):
        iniciados.append(nome)
        if ao_terminar:
            ao_terminar(nome)
        return {}

    api.estado.baixador.iniciar = iniciar
    anotados = api.BAIXADOS_PELO_PAULUS_PATH
    anotados_antes = anotados.read_text(encoding="utf-8") if anotados.exists() else None
    try:
        api.ESCOLHA_DO_INSTALADOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        api.ESCOLHA_DO_INSTALADOR_PATH.write_text('{"modelo": "qwen2.5:3b", "baixar": true}', encoding="utf-8-sig")
        api._cumprir_escolha_do_instalador()
        checar(gravados == [{"modelo": "qwen2.5:3b"}] and iniciados == ["qwen2.5:3b"],
               "a escolha vira o padrão e o download começa", (gravados, iniciados))
        checar("qwen2.5:3b" in anotados.read_text(encoding="utf-8").split(), "o modelo baixado fica anotado para o desinstalador")
        api._cumprir_escolha_do_instalador()
        checar(iniciados == ["qwen2.5:3b"], "só uma vez: a escolha cumprida não se repete")
        api.ESCOLHA_DO_INSTALADOR_PATH.write_text('{"modelo": "llama3.2:3b", "baixar": true}', encoding="utf-8-sig")
        api._cumprir_escolha_do_instalador()
        checar(iniciados == ["qwen2.5:3b"], "modelo que já está instalado não é baixado de novo")
        api.ESCOLHA_DO_INSTALADOR_PATH.write_text('{"modelo": "rm -rf /", "baixar": true}', encoding="utf-8-sig")
        api._cumprir_escolha_do_instalador()
        checar(len(gravados) == 2, "nome de modelo inválido é ignorado")
    finally:
        api.ollama_ligar, api.modelos_mod.instalados, api.estado.baixador.iniciar, api.preferencias_gravar = originais
        for sufixo in ("", ".feita"):
            alvo = api.ESCOLHA_DO_INSTALADOR_PATH.with_suffix(sufixo + ".json") if sufixo else api.ESCOLHA_DO_INSTALADOR_PATH
            alvo.unlink(missing_ok=True)
        if anotados_antes is None:
            anotados.unlink(missing_ok=True)
        else:
            anotados.write_text(anotados_antes, encoding="utf-8")
        api.estado.client.model = padrao_antes


def main() -> int:
    print("=" * 55)
    print("  os modelos do PAULUS")
    print("=" * 55)
    test_delegacao()
    test_nome()
    test_download()
    test_api()
    test_escolha_do_instalador()
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
