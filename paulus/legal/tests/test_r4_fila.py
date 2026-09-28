"""
Portao da R4 - a fila do modelo (src/fila_modelo.py).

Com um cliente falso que demora (dorme entre as palavras) e escreve a propria
pergunta em cada palavra - assim, resposta misturada aparece na hora:

  - duas pessoas perguntando ao mesmo tempo: o modelo atende uma de cada vez,
    na ordem de chegada, e nenhuma resposta traz palavra da outra; quem
    esperou viu a posicao na fila;
  - a 3a pergunta da mesma pessoa, com duas na fila, e recusada com frase
    clara (429);
  - parar a pergunta de A tira A da fila e nao encosta na de B;
  - o segundo plano cede a vez: `ceder()` espera enquanto ha pergunta.

Servidor de verdade (uvicorn), e nao o TestClient: o TestClient junta a
resposta inteira antes de entregar, e a fila so se ve com as duas respostas
andando juntas.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r4_fila.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Lento:
    """O modelo de mentira: 6 palavras, 0,25 s cada, cada uma com a pergunta dentro."""

    model = "falso:1b"
    num_ctx = 8192
    host = "http://127.0.0.1:9"

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.ativos = 0
        self.max_ativos = 0
        self.log: list[tuple[str, str]] = []

    def ask(self, question, context="", *, sistema="", ensinado="", stream=False, on_token=None,
            on_fase=None, parar=None):
        marca = question.split()[-1]
        with self.trava:
            self.ativos += 1
            self.max_ativos = max(self.max_ativos, self.ativos)
            self.log.append(("inicio", marca))
        escrito = []
        try:
            if on_fase:
                on_fase("escrevendo", {"lendo_segundos": 0.1})
            for _ in range(6):
                if parar and parar():
                    break
                time.sleep(0.25)
                escrito.append(f"<{marca}> ")
                if on_token:
                    on_token(f"<{marca}> ")
            return "".join(escrito)
        finally:
            with self.trava:
                self.ativos -= 1
                self.log.append(("fim", marca))

    def digest(self, model=""):
        return ""


def test_fila_sozinha() -> None:
    print("\na fila, sem servidor")
    from fila_modelo import FilaCheia, FilaDoModelo

    f = FilaDoModelo(segundos_por_resposta=lambda: 20.0)
    a = f.entrar("ana")
    b = f.entrar("beto")
    a2 = f.entrar("ana")
    try:
        f.entrar("ana")
        checar(False, "a 3a da mesma pessoa e recusada")
    except FilaCheia as exc:
        checar("2 perguntas" in str(exc), "a 3a da mesma pessoa e recusada, dizendo por que", str(exc))
    checar(f.esperar(a, timeout=0.1) and not f.esperar(b, timeout=0.1), "a primeira que chegou e a da vez")
    checar(f.posicao(b) == 1 and f.posicao(a2) == 2, "posicao: 1 e 2", (f.posicao(b), f.posicao(a2)))
    checar(18 <= f.previsao(b) <= 20 and 38 <= f.previsao(a2) <= 40, "previsao pelo ritmo medido",
           (f.previsao(b), f.previsao(a2)))
    f.sair(b)
    checar(f.posicao(a2) == 1, "quem desiste sai, e os de tras andam")
    cedeu = []
    t = threading.Thread(target=lambda: (f.ceder(limite_s=5), cedeu.append(time.time())))
    comeco = time.time()
    t.start()
    time.sleep(0.4)
    checar(not cedeu, "o segundo plano espera enquanto ha pergunta")
    f.sair(a)
    f.esperar(a2, timeout=0.1)
    f.sair(a2)
    t.join(3)
    checar(cedeu and cedeu[0] - comeco >= 0.4, "e anda quando a fila esvazia")


def _eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo, corpo = "", ""
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                corpo += linha[6:]
        if tipo:
            saida.append((tipo, json.loads(corpo or "{}")))
    return saida


def test_duas_pessoas() -> None:
    print("\nduas pessoas, um modelo")
    import requests

    import segredos
    from test_gravacoes import _porta_livre, _subir_servidor

    import api
    from acesso.contas import codigo_totp
    from extract import Document

    lento = Lento()
    api.estado.client = lento
    api.estado.cliente_para = lambda tarefa: lento
    # O documento vai para a pasta do Acervo: ao subir, o servidor rele a
    # pasta e monta o indice de novo.
    Path(api.estado.pasta).mkdir(parents=True, exist_ok=True)
    (Path(api.estado.pasta) / "teste.txt").write_text(
        "CONTRATO DE TESTE. Cláusula 1. A multa por atraso é de dez por cento.", encoding="utf-8")
    _ = Document
    porta = _porta_livre()
    _subir_servidor(porta)
    for _ in range(40):
        if api.estado.searcher.documents:
            break
        time.sleep(0.25)
    base = f"http://127.0.0.1:{porta}"

    local = requests.Session()
    local.headers.update(api.cabecalho_local())

    # A segunda pessoa entra de fora (o cookie Secure vai a mao: o requests
    # nao manda cookie Secure por http, e aqui nao ha Cloudflare na frente).
    fora = None
    if segredos.disponivel():
        servico = api.estado.acesso_de_fora
        servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
        c = servico.contas.criar("Bia", "bia@escritorio.com", "titular", "senha-da-bia-12")
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30) - 1))
        fora = requests.Session()
        pend = fora.post(base + "/api/acesso/entrar", json={"email": "bia@escritorio.com", "senha": "senha-da-bia-12", "turnstile": "ok"}).json()["pendente"]
        r = fora.post(base + "/api/acesso/entrar/codigo",
                      json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30))})
        fora.headers.update({"Cookie": "paulus_sessao=" + r.cookies.get("paulus_sessao"), "X-PAULUS-CSRF": r.json()["csrf"]})
    else:
        print("  (sem DPAPI: a segunda pessoa e outra janela local)")
        fora = local

    def conversa(sessao) -> str:
        return sessao.post(base + "/api/trabalhos", json={"pedido": "teste da fila"}).json()["id"]

    def perguntar(sessao, id_: str, marca: str, saida: dict) -> None:
        corpo = {"pergunta": f"qual a multa? {marca}", "apenas": ["teste.txt"], "documentos": True}
        with sessao.post(f"{base}/api/trabalhos/{id_}/perguntar", json=corpo, stream=True, timeout=60) as r:
            saida["status"] = r.status_code
            saida["texto"] = r.text if r.status_code != 200 else r.content.decode("utf-8")

    ca, cb = conversa(local), conversa(fora)
    ra, rb = {}, {}
    ta = threading.Thread(target=perguntar, args=(local, ca, "AAA", ra))
    tb = threading.Thread(target=perguntar, args=(fora, cb, "BBB", rb))
    ta.start()
    time.sleep(0.4)
    tb.start()
    ta.join(60)
    tb.join(60)
    ea, eb = _eventos(ra.get("texto", "")), _eventos(rb.get("texto", ""))
    texto_a = "".join(d.get("t", "") for t, d in ea if t == "token")
    texto_b = "".join(d.get("t", "") for t, d in eb if t == "token")
    checar(lento.max_ativos == 1, "o modelo atende uma pergunta por vez", lento.max_ativos)
    checar("<AAA>" in texto_a and "<BBB>" not in texto_a, "a resposta de A so tem A", texto_a[:80])
    checar("<BBB>" in texto_b and "<AAA>" not in texto_b, "a resposta de B so tem B", texto_b[:80])
    ordem = [m for ev, m in lento.log if ev == "inicio"]
    checar(ordem[-2:] == ["AAA", "BBB"], "na ordem de chegada", lento.log)
    fila_b = [d for t, d in eb if t == "fila"]
    checar(fila_b and fila_b[0].get("posicao") == 1, "B viu que era o 1o na fila", fila_b[:2])
    checar(not [d for t, d in ea if t == "fila"], "A, sem ninguem na frente, nao viu fila nenhuma")

    print("\na 3a pergunta da mesma pessoa")
    c1, c2, c3 = conversa(local), conversa(local), conversa(local)
    r1, r2, r3 = {}, {}, {}
    t1 = threading.Thread(target=perguntar, args=(local, c1, "UM", r1))
    t2 = threading.Thread(target=perguntar, args=(local, c2, "DOIS", r2))
    t1.start()
    time.sleep(0.3)
    t2.start()
    time.sleep(0.3)
    perguntar(local, c3, "TRES", r3)
    checar(r3.get("status") == 429 and "2 perguntas" in r3.get("texto", ""), "recusada com frase clara (429)",
           (r3.get("status"), r3.get("texto", "")[:120]))
    t1.join(60)
    t2.join(60)
    checar(r1.get("status") == 200 and r2.get("status") == 200, "as duas primeiras seguem")

    print("\nparar A nao encosta em B")
    ca, cb = conversa(local), conversa(fora)
    ra, rb = {}, {}
    ta = threading.Thread(target=perguntar, args=(local, ca, "PARA", ra))
    tb = threading.Thread(target=perguntar, args=(fora, cb, "SEGUE", rb))
    ta.start()
    time.sleep(0.5)
    tb.start()
    time.sleep(0.3)
    local.post(f"{base}/api/trabalhos/{ca}/parar")
    ta.join(60)
    tb.join(60)
    ea, eb = _eventos(ra.get("texto", "")), _eventos(rb.get("texto", ""))
    checar(any(t == "parado" for t, _ in ea), "A parou", [t for t, _ in ea][-3:])
    texto_b = "".join(d.get("t", "") for t, d in eb if t == "token")
    checar(any(t == "fim" for t, _ in eb) and texto_b.count("<SEGUE>") == 6, "B terminou inteira", texto_b[:80])


def main() -> int:
    print("=" * 55)
    print("  R4 - a fila do modelo")
    print("=" * 55)
    try:
        test_fila_sozinha()
        test_duas_pessoas()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
