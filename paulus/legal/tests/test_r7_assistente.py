"""
Portao da R7 - o assistente de conexao (src/acesso/conexao.py) e o instalador
que traz o cloudflared (tools/instalador/Instalador.cs).

Com um Worker de mentira (responde "pendente" duas vezes e depois entrega o
token) e um cloudflared de mentira:

  - conectar: pede ao Worker, abre o navegador no endereco, espera; quando
    o titular confirma, guarda o token (DPAPI), grava endereco e porta, abre
    o ouvinte da porta fixa e liga o tunel;
  - a lista de e-mails do Access acompanha as contas: criar conta acrescenta,
    remover tira;
  - Remover apaga la (Worker) e aqui (segredos, endereco, sessoes) e para o
    tunel;
  - sem conta de titular pronta, o assistente diz o que falta.

E o instalador: compila com o csc.exe do .NET Framework 4, e a conferencia de
assinatura aceita o cloudflared da Cloudflare e recusa um executavel
assinado por outra empresa e um arquivo qualquer.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r7_assistente.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r7-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
TOKEN = "eyJhIjoiY29udGEiLCJ0IjoidHVuZWwifQ-token-de-mentira"
SEGREDO = "5e" * 32

FALSO = r'''
import os, sys, time
if "--version" in sys.argv:
    print("cloudflared version 2026.9.3 (built 2026-09-24T08:31 UTC)")
    sys.exit(0)
print("INF Registered tunnel connection connIndex=0 location=gru", flush=True)
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


class WorkerFalso:
    def __init__(self) -> None:
        self.iniciado: dict = {}
        self.consultas = 0
        self.emails_enviados: list[list[str]] = []
        self.removido = False

    def iniciar(self, instalacao_id, email_titular, nome_escritorio, porta):
        self.iniciado = {"instalacao_id": instalacao_id, "email": email_titular, "nome": nome_escritorio, "porta": porta}
        return {"codigo_dispositivo": "d" * 64, "codigo_usuario": "ABCD-EFGH",
                "url": "https://paulus.ia.br/conectar?c=ABCD-EFGH", "expira_em": "2026-09-28T12:00:00Z"}

    def estado(self, codigo):
        self.consultas += 1
        if self.consultas < 3:
            return {"estado": "pendente"}
        return {"estado": "pronto", "hostname": "escritorio-teste-1a2b.paulus.ia.br", "tunnel_token": TOKEN,
                "aud": "aud-teste", "team_domain": "atos.cloudflareaccess.com", "segredo_instalacao": SEGREDO}

    def emails(self, segredo, emails):
        assert segredo == SEGREDO
        self.emails_enviados.append(list(emails))
        return {"ok": True}

    def porta(self, segredo, porta):
        return {"ok": True, "porta": porta}

    def remover(self, segredo):
        assert segredo == SEGREDO
        self.removido = True
        return {"ok": True, "avisos": []}


def test_assistente() -> None:
    print("\no assistente de conexao, com o Worker de mentira")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    conexao = servico.conexao
    worker = WorkerFalso()
    abertos: list[str] = []
    conexao.provisao = worker
    conexao.intervalo = 0.1
    conexao.abrir_navegador = abertos.append
    falso = TMP / "cloudflared_falso.py"
    falso.write_text(FALSO, encoding="utf-8")
    servico.cloudflared = lambda: {"caminho": str(falso), "versao": "2026.9.3", "minima": "2025.4.0", "basta": True}
    servico._comando_cloudflared = lambda: [sys.executable, str(falso), "tunnel", "--no-autoupdate", "run"]
    servico.tunel.comando = servico._comando_cloudflared
    local = TestClient(api.app, headers=api.cabecalho_local())

    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Escritório Teste", "email": "tita@escritorio.com"})
    checar(r.status_code == 400 and "titular" in r.json().get("detail", ""), "sem conta de titular pronta, diz o que falta",
           r.text[:200])

    c = servico.contas.criar("Tita Titular", "tita@escritorio.com", "titular", "senha-da-tita-12")
    servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30)))
    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Escritório Teste", "email": "tita@escritorio.com"})
    checar(r.status_code == 200 and r.json()["pedido"]["codigo_usuario"] == "ABCD-EFGH", "conectar: o codigo curto", r.text[:200])
    checar("codigo_dispositivo" not in r.text, "o codigo secreto nao sai para a tela")
    checar(abertos == ["https://paulus.ia.br/conectar?c=ABCD-EFGH"], "abre o navegador em paulus.ia.br/conectar", abertos)
    checar(47000 <= worker.iniciado.get("porta", 0) <= 47999 and worker.iniciado["email"] == "tita@escritorio.com",
           "pediu com a porta fixa entre 47000 e 47999 e o e-mail do titular", worker.iniciado)
    estado = local.get("/api/acesso/tunel").json()
    checar(estado["conexao"]["pedido"]["estado"] in ("esperando", "concluido"), "a tela ve o pedido esperando", estado["conexao"])

    checar(esperar(lambda: (servico.conexao.andamento()["pedido"] or {}).get("estado") == "concluido", 10),
           "quando o titular confirma, conclui", servico.conexao.andamento())
    prefs = api.estado.prefs.dados["acesso_remoto"]
    checar(prefs["ligado"] and prefs["hostname"] == "escritorio-teste-1a2b.paulus.ia.br" and prefs["aud"] == "aud-teste"
           and prefs["porta"] == worker.iniciado["porta"], "grava endereco, aud, time e porta, e liga", prefs)
    checar(servico.cofre.token() == TOKEN and servico.cofre.segredo() == SEGREDO, "token e segredo guardados (DPAPI)")
    guardado = (servico.pasta / "tunel.json").read_text(encoding="utf-8")
    checar(TOKEN not in guardado and SEGREDO not in guardado, "e nao em texto puro no arquivo")
    checar(esperar(lambda: servico.tunel.estado == "conectado", 10), "o tunel ligou", servico.tunel.estado)
    checar(servico.situacao()["estado"] == "conectado", "a situacao diz conectado", servico.situacao()["estado"])
    checar(servico.verificar_jwt is not None, "o conferidor do Access ficou montado")
    checar(worker.emails_enviados and worker.emails_enviados[-1] == ["tita@escritorio.com"], "a lista do Access tem o titular",
           worker.emails_enviados)

    print("\na lista do Access acompanha as contas")
    r = local.post("/api/acesso/contas", json={"nome": "Caio", "email": "caio@escritorio.com", "papel": "colaborador",
                                               "senha": "senha-do-caio-12"})
    checar(worker.emails_enviados[-1] == ["tita@escritorio.com", "caio@escritorio.com"], "criar conta acrescenta o e-mail",
           worker.emails_enviados[-1])
    local.delete(f"/api/acesso/contas/{r.json()['conta']['id']}")
    checar(worker.emails_enviados[-1] == ["tita@escritorio.com"], "remover conta tira o e-mail", worker.emails_enviados[-1])

    print("\ndesligar e ligar")
    local.post("/api/acesso/tunel/ligar", json={"ligado": False})
    checar(not servico.tunel.ligado and servico.situacao()["estado"] == "desligado", "desligar para o tunel e mantem o endereco")
    checar(api.estado.prefs.dados["acesso_remoto"]["hostname"], "o endereco ficou")
    local.post("/api/acesso/tunel/ligar", json={"ligado": True})
    checar(esperar(lambda: servico.tunel.estado == "conectado", 10), "ligar sobe de novo")

    print("\nremover")
    r = local.post("/api/acesso/tunel/remover")
    checar(r.status_code == 200 and worker.removido, "remove no Worker", r.text[:200])
    prefs = api.estado.prefs.dados["acesso_remoto"]
    checar(not servico.cofre.tem() and not prefs["ligado"] and not prefs["hostname"] and not prefs["aud"],
           "e aqui: segredos, endereco e aud", prefs)
    checar(not servico.tunel.ligado and servico.verificar_jwt is None, "o tunel parou e o conferidor saiu")


def test_instalador() -> None:
    print("\no instalador: compila e confere a assinatura")
    csc = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    if sys.platform != "win32" or not csc.exists():
        print("  pulado: sem o csc.exe do .NET Framework 4")
        return
    aqui = RAIZ / "tools" / "instalador"
    versao = TMP / "Versao.cs"
    versao.write_text('static class Versao { public const string Numero = "0.0.0-teste"; }\n', encoding="utf-8")
    exe = TMP / "instalador-teste.exe"
    fontes = [f"/resource:{f},{f.name}" for f in sorted((aqui / "fontes").glob("*.ttf"))]
    r = subprocess.run([str(csc), "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
                        "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll", *fontes,
                        f"/out:{exe}", str(aqui / "Instalador.cs"), str(versao)], capture_output=True, text=True)
    checar(r.returncode == 0 and exe.exists(), "compila com o csc.exe (C# 5, sem pacotes)", (r.stdout + r.stderr)[-400:])
    if not exe.exists():
        return

    def conferir(arquivo) -> int:
        return subprocess.run([str(exe), f"/conferir-assinatura={arquivo}"], timeout=60).returncode

    falso = TMP / "falso.exe"
    falso.write_bytes(b"MZ nao sou programa")
    checar(conferir(falso) == 3, "um arquivo qualquer e recusado")
    checar(conferir(sys.executable) == 3, "um executavel assinado por outra empresa (o Python) e recusado")
    from acesso.tunel import achar_cloudflared

    reais = [p for p in (achar_cloudflared(), Path(os.environ.get("ProgramFiles(x86)", "")) / "cloudflared" / "cloudflared.exe")
             if p and Path(p).is_file()]
    if reais:
        checar(conferir(reais[0]) == 0, f"o cloudflared da Cloudflare e aceito ({reais[0]})")
    else:
        print("  --   sem cloudflared nesta maquina: o caso aceito foi conferido a mao (docs/PROGRESSO)")


def main() -> int:
    print("=" * 55)
    print("  R7 - o assistente de conexao e o instalador")
    print("=" * 55)
    try:
        test_assistente()
        test_instalador()
    finally:
        try:
            import api

            api.estado.acesso_de_fora.parar()
        except Exception:  # noqa: BLE001
            pass
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
