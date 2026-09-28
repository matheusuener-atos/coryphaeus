"""
Portao da R6 - o tunel dentro do PAULUS (src/acesso/tunel.py e servico.py).

  - com um `cloudflared` de mentira (um script que registra argumentos e
    ambiente, escreve o token no proprio log e diz que conectou): o token NAO
    aparece nos argumentos nem no log do PAULUS, e aparece no ambiente;
  - caiu, levanta de novo; desligar encerra o processo;
  - a versao minima e conferida; o executavel do instalador vem primeiro;
  - o Turnstile do login, conferido no Worker com o segredo da instalacao
    (sem Cloudflare Access, decisao de 28/09/2026): aprovado passa;
    recusado, token vazio, Worker fora do ar e PAULUS sem segredo, nao -
    indisponivel nunca libera;
  - o Worker diz que o endereco foi liberado (por falta de uso): o PAULUS
    desliga, apaga o que guardou, derruba as sessoes e avisa "conecte de
    novo"; na abertura, a mesma pergunta;
  - porta fixa ocupada: o acesso de fora fica "porta ocupada" e o tunel nao
    liga; a janela local nao depende dela (a porta fixa e um segundo
    ouvinte, so do tunel);
  - com o acesso ligado, quem chega de fora sem sessao so ve a tela de
    entrar.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r6_tunel.py
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r6-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
TOKEN = "eyJhIjoiY29udGEiLCJ0IjoidHVuZWwiLCJzIjoiU0VHUkVETy1ERS1URVNURSJ9"

FALSO = r'''
import json, os, sys, time, pathlib
reg = pathlib.Path(os.environ["FALSO_REGISTRO"])
if "--version" in sys.argv:
    print("cloudflared version 2026.9.3 (built 2026-09-24T08:31 UTC)")
    sys.exit(0)
antes = reg.read_text(encoding="utf-8").splitlines() if reg.exists() else []
with open(reg, "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "token": os.environ.get("TUNNEL_TOKEN", "")}) + "\n")
print("INF Starting tunnel tunnelID=abc token=" + os.environ.get("TUNNEL_TOKEN", ""), flush=True)
print("INF Registered tunnel connection connIndex=0 location=gru", flush=True)
if os.environ.get("FALSO_CAI") and len(antes) == 0:
    time.sleep(0.3)
    sys.exit(1)
while True:
    time.sleep(0.2)
'''


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def esperar(cond, limite=10.0) -> bool:
    fim = time.time() + limite
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


def test_processo() -> None:
    print("\no cloudflared como processo filho")
    from acesso.tunel import Tunel, versao_basta, versao_de

    falso = TMP / "cloudflared_falso.py"
    falso.write_text(FALSO, encoding="utf-8")
    registro = TMP / "registro.jsonl"
    os.environ["FALSO_REGISTRO"] = str(registro)
    os.environ["FALSO_CAI"] = "1"
    base = [sys.executable, str(falso)]
    checar(versao_de(base) == "2026.9.3", "le a versao do --version", versao_de(base))
    checar(versao_basta("2026.9.3") and not versao_basta("2024.1.0"), "a versao minima e conferida")

    log = TMP / "dados" / "logs" / "tunel.log"
    t = Tunel(lambda: base + ["tunnel", "--no-autoupdate", "run"], lambda: TOKEN, log, espera_inicial=0.3)
    t.ligar()
    checar(esperar(lambda: t.partidas >= 2 and t.estado == "conectado", 15), "caiu e levantou de novo, conectado",
           (t.partidas, t.estado))
    chamadas = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
    checar(all(TOKEN not in " ".join(c["argv"]) for c in chamadas), "o token nao vai na linha de comando",
           chamadas[0]["argv"])
    checar(chamadas[0]["argv"] == ["tunnel", "--no-autoupdate", "run"], "tunnel --no-autoupdate run", chamadas[0]["argv"])
    checar(all(c["token"] == TOKEN for c in chamadas), "o token vai no ambiente (TUNNEL_TOKEN)")
    texto = log.read_text(encoding="utf-8")
    checar(TOKEN not in texto and "token=***" in texto, "o log do PAULUS nao tem o token", texto[:200])
    t.desligar()
    checar(t.estado == "desligado" and not t.ligado, "desligar encerra o processo")
    del os.environ["FALSO_CAI"]


def test_onde_esta() -> None:
    print("\nonde esta o cloudflared")
    from acesso import tunel

    antes = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(TMP / "local")
    try:
        exe = tunel.pasta_do_instalador() / "cloudflared.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"MZ")
        checar(tunel.achar_cloudflared() == exe, "o do instalador vem primeiro", tunel.achar_cloudflared())
    finally:
        if antes is not None:
            os.environ["LOCALAPPDATA"] = antes


class CofreFalso:
    """O cofre do tunel sem DPAPI: o teste nao mexe no que a maquina guardou."""

    def __init__(self, token: str = "", segredo: str = "") -> None:
        self._t, self._s = token, segredo

    def guardar(self, token: str, segredo: str) -> None:
        self._t, self._s = token, segredo

    def token(self) -> str:
        return self._t

    def segredo(self) -> str:
        return self._s

    def tem(self) -> bool:
        return bool(self._t)

    def apagar(self) -> None:
        self._t = self._s = ""


class ProvisaoFalsa:
    """O Worker de mentira: so as rotas que a R6 usa."""

    def __init__(self) -> None:
        self.chamadas = []
        self.removido = ""

    def turnstile(self, segredo: str, token: str, ip: str = "") -> bool:
        from acesso.provisao import ErroProvisao, ErroRemovido

        self.chamadas.append(("turnstile", segredo, token, ip))
        if self.removido:
            raise ErroRemovido(self.removido)
        if token == "fora":
            raise ErroProvisao("não consegui falar com paulus.ia.br")
        return token == "ok"

    def situacao(self, segredo: str) -> dict:
        from acesso.provisao import ErroRemovido

        self.chamadas.append(("situacao", segredo))
        if self.removido:
            raise ErroRemovido(self.removido)
        return {"endereco": "x.paulus.ia.br", "tunel": "healthy"}


def test_turnstile() -> None:
    print("\no Turnstile do login, conferido no Worker")
    import api
    from acesso.conexao import ConexaoDoTunel

    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    antes = (servico.cofre, servico.conexao, dict(prefs))
    falsa = ProvisaoFalsa()
    try:
        servico.cofre = CofreFalso()
        ConexaoDoTunel(servico, provisao=falsa, abrir_navegador=lambda url: None)
        checar(servico.conferir_turnstile("ok", "200.1.1.1") == "indisponivel" and not falsa.chamadas,
               "sem o segredo da instalacao (nao conectado): indisponivel, sem perguntar")
        servico.cofre.guardar("token-do-tunel", "segredo-da-instalacao")
        checar(servico.conferir_turnstile("ok", "200.1.1.1") == "ok", "aprovado no Worker: ok")
        checar(falsa.chamadas[-1] == ("turnstile", "segredo-da-instalacao", "ok", "200.1.1.1"),
               "vai o segredo da instalacao, o token e o IP da Cloudflare", falsa.chamadas[-1])
        checar(servico.conferir_turnstile("robo", "") == "recusado", "recusado no Worker: recusado")
        n = len(falsa.chamadas)
        checar(servico.conferir_turnstile("  ", "") == "recusado" and len(falsa.chamadas) == n,
               "token vazio: recusado, sem ir ao Worker")
        checar(servico.conferir_turnstile("fora", "") == "indisponivel", "Worker fora do ar: indisponivel (ninguem entra)")

        print("\no endereco liberado por falta de uso")
        prefs.update(ligado=True, hostname="moura-associados.paulus.ia.br", turnstile_sitekey="0x4AAA", porta=47123, liberado="")
        falsa.removido = "parado há mais de 180 dias"
        checar(servico.conferir_turnstile("ok", "") == "indisponivel", "no login: indisponivel")
        checar(not servico.cofre.tem() and not prefs["ligado"] and prefs["hostname"] == "" and prefs["turnstile_sitekey"] == "",
               "desligou e apagou o token, o segredo, o endereco e a sitekey", dict(prefs))
        checar(prefs["liberado"] == "o endereço foi liberado por falta de uso; conecte de novo", "e deixou o aviso",
               prefs["liberado"])
        sit = servico.situacao()
        checar(sit["estado"] == "liberado" and sit["liberado"], "a situacao diz 'liberado' para a tela", sit["estado"])
        checar(any(e.get("acao") == "liberado" for e in servico.eventos[-5:]), "e ficou no registro de acessos")

        # Na abertura, o PAULUS pergunta: o mesmo desfecho.
        servico.cofre.guardar("token-do-tunel", "segredo-da-instalacao")
        prefs.update(ligado=True, hostname="moura-associados.paulus.ia.br", liberado="")
        servico.conexao.verificar_endereco()
        checar(not servico.cofre.tem() and prefs["liberado"], "na abertura, o mesmo: desliga, apaga e avisa")
        falsa.removido = ""
        servico.cofre.guardar("token-do-tunel", "segredo-da-instalacao")
        prefs.update(liberado="")
        servico.conexao.verificar_endereco()
        checar(servico.cofre.tem(), "endereco vivo: nada muda")
    finally:
        servico.parar()
        servico.cofre, servico.conexao = antes[0], antes[1]
        prefs.clear()
        prefs.update(antes[2])


def test_porta_ocupada() -> None:
    """
    A porta fixa e um segundo ouvinte, so do tunel (tambem em 127.0.0.1): a
    janela local continua na porta dela, e a porta fixa ocupada por outro
    programa so deixa o acesso de fora "indisponivel: porta ocupada" - e o
    tunel nao liga, porque o que chegasse de fora iria para aquele programa.
    """
    print("\nporta fixa ocupada")
    import urllib.request

    import api

    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        livre = s.getsockname()[1]
    prefs.update(porta=livre)
    try:
        with socket.socket() as ocupante:
            ocupante.bind(("127.0.0.1", livre))
            ocupante.listen(1)
            checar(not servico.abrir_porta_de_fora() and servico.porta_ocupada, "ocupada: nao abre, e o estado diz")
            checar(servico.situacao()["estado"] == "porta_ocupada", "a situacao diz porta ocupada", servico.situacao()["estado"])
        checar(servico.abrir_porta_de_fora() and not servico.porta_ocupada, "livre: o ouvinte do tunel abre")
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{livre}/api/status",
                                                           headers=api.cabecalho_local()), timeout=5) as r:
            checar(r.status == 200, "e atende o mesmo PAULUS (com o porteiro na frente)")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{livre}/api/status", timeout=5)
            checar(False, "sem chave, nessa porta tambem e 403")
        except urllib.error.HTTPError as exc:
            checar(exc.code == 403, "sem chave, nessa porta tambem e 403", exc.code)
    finally:
        servico.fechar_porta_de_fora()
        prefs.update(porta=0)


def test_porteiro() -> None:
    print("\no porteiro, sem Cloudflare Access")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return
    from fastapi.testclient import TestClient

    import api

    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    prefs.update(ligado=True)
    try:
        de_fora = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.1.2.3"})
        r = de_fora.get("/")
        checar(r.status_code == 200 and "entrar-senha" in r.text and "challenges.cloudflare.com" in r.text,
               "sem sessao, chega a tela de entrar, com o Turnstile")
        checar(de_fora.get("/api/status").status_code == 401, "e a API responde 401")
        checar(not hasattr(servico, "verificar_jwt"), "nao ha mais conferidor do Access")
        s = servico.situacao()
        checar(set(s) >= {"estado", "cloudflared", "porta", "porta_ocupada", "hostname", "liberado"},
               "a situacao do tunel para a tela", s)
    finally:
        prefs.update(ligado=False)


def main() -> int:
    print("=" * 55)
    print("  R6 - o tunel dentro do PAULUS")
    print("=" * 55)
    try:
        test_processo()
        test_onde_esta()
        test_turnstile()
        test_porta_ocupada()
        test_porteiro()
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
