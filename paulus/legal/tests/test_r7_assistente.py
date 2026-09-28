"""
Portao da R7 - o passo "Acesso a distancia" (src/acesso/conexao.py,
rotas_tunel.py; a tela e js/23-boas-vindas.js + js/43-acesso-tunel.js) e o
instalador que traz o cloudflared (tools/instalador/Instalador.cs).

Com um Worker de mentira (disponibilidade, reserva do nome, "pendente" duas
vezes e depois a entrega; ou "expirado") e um cloudflared de mentira:

  - a sugestao do endereco a partir do nome do escritorio: acento, "&",
    "Advocacia", "Advogados Associados" e parecidos;
  - nome indisponivel: o motivo e uma sugestao; nome fora da regra ou
    reservado: o motivo, sem ir ao Worker;
  - interruptor desligado: abrir o passo nao chama o Worker nem cria nada;
  - fluxo completo: nome -> conta do titular com TOTP -> iniciar -> pendente
    -> concluido -> tunel ligado, com a sitekey do Turnstile para a tela de
    entrar;
  - codigo expirado: "tentar de novo" usa o mesmo nome;
  - Remover apaga la (Worker) e aqui (segredos, endereco, sitekey, sessoes),
    para o tunel, e o nome volta a ficar livre.

E o instalador: compila com o csc.exe do .NET Framework 4, traz o
cloudflared sempre que falta (sem caixa de marcar), e a conferencia de
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
    """O Worker de paulus.ia.br, de mentira: conta cada chamada."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.tomados = {"moura", "silva-advogados"}
        self.iniciado: dict = {}
        self.consultas = 0
        self.expira = False
        self.removido = False

    def disponivel(self, nome, instalacao_id):
        self.chamadas.append("disponivel")
        if nome in self.tomados:
            return {"disponivel": False, "motivo": "esse endereço já está em uso", "sugestao": nome + "-2"}
        return {"disponivel": True, "motivo": "", "sugestao": ""}

    def iniciar(self, instalacao_id, nome_escritorio, slug, porta):
        self.chamadas.append("iniciar")
        self.iniciado = {"instalacao_id": instalacao_id, "nome": nome_escritorio, "slug": slug, "porta": porta}
        self.consultas = 0
        return {"codigo_dispositivo": "d" * 64, "codigo_usuario": "ABCD-EFGH",
                "url": "https://paulus.ia.br/conectar?c=ABCD-EFGH", "expira_em": "2026-09-28T12:00:00Z"}

    def estado(self, codigo):
        self.chamadas.append("estado")
        self.consultas += 1
        if self.expira and self.consultas >= 2:
            return {"estado": "expirado"}
        if self.consultas < 3:
            return {"estado": "pendente"}
        self.tomados.add(self.iniciado["slug"])
        return {"estado": "pronto", "hostname": self.iniciado["slug"] + ".paulus.ia.br", "tunnel_token": TOKEN,
                "turnstile_sitekey": "0x4AAAAAAA-sitekey", "segredo_instalacao": SEGREDO}

    def situacao(self, segredo):
        self.chamadas.append("situacao")
        return {"endereco": self.iniciado.get("slug", "") + ".paulus.ia.br", "tunel": "healthy"}

    def porta(self, segredo, porta):
        self.chamadas.append("porta")
        return {"ok": True, "porta": porta}

    def remover(self, segredo):
        assert segredo == SEGREDO
        self.chamadas.append("remover")
        self.removido = True
        self.tomados.discard(self.iniciado.get("slug"))
        return {"ok": True, "avisos": []}


def test_sugestao() -> None:
    print("\no endereco sugerido a partir do nome do escritorio")
    from acesso.conexao import motivo_do_formato, sugerir_endereco

    casos = {
        "Moura & Associados Advocacia": "moura-associados",
        "Advocacia Conceição Góes": "conceicao-goes",
        "Silva, Araújo e Mendonça Advogados Associados": "silva-araujo-mendonca",
        "Escritório de Advocacia Dr. Pereira": "dr-pereira",
        "Sociedade de Advogados São João Ltda.": "sao-joao",
        "Advogados Associados": "associados",
        "Ávila Gonçalves Irmãos Barbosa Advogados": "avila-goncalves-irmaos",
        "Advocacia": "advocacia",
    }
    for nome, esperado in casos.items():
        obtido = sugerir_endereco(nome)
        checar(obtido == esperado, f"{nome!r} -> {esperado}", obtido)
    for nome in casos:
        checar(motivo_do_formato(sugerir_endereco(nome)) == "", f"a sugestao de {nome!r} ja cabe na regra")
    checar(sugerir_endereco("Atos") != "atos", "nome reservado nao e sugerido", sugerir_endereco("Atos"))


def _preparar(api, worker):
    servico = api.estado.acesso_de_fora
    conexao = servico.conexao
    abertos: list[str] = []
    conexao.provisao = worker
    conexao.intervalo = 0.1
    conexao.abrir_navegador = abertos.append
    falso = TMP / "cloudflared_falso.py"
    falso.write_text(FALSO, encoding="utf-8")
    servico.cloudflared = lambda: {"caminho": str(falso), "versao": "2026.9.3", "minima": "2025.4.0", "basta": True}
    servico._comando_cloudflared = lambda: [sys.executable, str(falso), "tunnel", "--no-autoupdate", "run"]
    servico.tunel.comando = servico._comando_cloudflared
    return servico, conexao, abertos


def test_assistente() -> None:
    print("\no passo 'Acesso a distancia', com o Worker de mentira")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    worker = WorkerFalso()
    servico, conexao, abertos = _preparar(api, worker)
    local = TestClient(api.app, headers=api.cabecalho_local())
    api.estado.prefs.atualizar({"escritorio": {"nome": "Moura & Associados Advocacia"}})

    print("  interruptor desligado")
    d = local.get("/api/acesso/tunel").json()
    checar(d["sugestao"] == "moura-associados" and d["escritorio"] == "Moura & Associados Advocacia",
           "o passo sabe o nome do escritorio e a sugestao", (d["escritorio"], d["sugestao"]))
    local.get("/api/acesso/tunel/sugestao", params={"nome": "Outro Nome Advocacia"})
    checar(worker.chamadas == [], "abrir o passo (e a sugestao) nao chama o Worker", worker.chamadas)
    prefs = api.estado.prefs.dados["acesso_remoto"]
    checar(not prefs["hostname"] and not prefs["ligado"] and not servico.contas.listar() and not servico.cofre.tem(),
           "e nada foi criado: nem conta, nem endereco, nem token")

    print("  o nome")
    r = local.get("/api/acesso/tunel/disponivel", params={"nome": "moura"}).json()
    checar(r["disponivel"] is False and r["motivo"] and r["sugestao"] == "moura-2", "tomado: o motivo e a sugestao", r)
    r = local.get("/api/acesso/tunel/disponivel", params={"nome": "moura-associados"}).json()
    checar(r["disponivel"] is True, "livre: disponivel", r)
    n = len(worker.chamadas)
    r = local.get("/api/acesso/tunel/disponivel", params={"nome": "www"}).json()
    checar(r["disponivel"] is False and "reservado" in r["motivo"] and len(worker.chamadas) == n,
           "reservado: o motivo, sem ir ao Worker", r)
    r = local.get("/api/acesso/tunel/disponivel", params={"nome": "Moura Associados"}).json()
    checar(r["disponivel"] is False and r["motivo"] and r["sugestao"] == "moura-associados" and len(worker.chamadas) == n,
           "fora da regra: o motivo e a forma certa", r)

    print("  a conta do titular")
    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Moura & Associados Advocacia", "slug": "moura-associados"})
    checar(r.status_code == 400 and "titular" in r.json().get("detail", ""), "sem conta de titular pronta, diz o que falta",
           r.text[:200])
    checar("iniciar" not in worker.chamadas, "e nao pede nada ao Worker")
    r = local.post("/api/acesso/contas", json={"nome": "Tita Moura", "email": "tita@moura.adv.br", "papel": "titular",
                                               "senha": "senha-da-tita-12"})
    criada = r.json()
    checar(r.status_code == 200 and criada["qr_svg"].startswith("<svg") and len(criada["codigos_recuperacao"]) == 10,
           "cria a conta: QR e codigos de recuperacao", r.text[:120])
    r = local.post(f"/api/acesso/contas/{criada['conta']['id']}/autenticador/confirmar",
                   json={"codigo": codigo_totp(criada["segredo"], int(time.time() // 30))})
    checar(r.status_code == 200 and local.get("/api/acesso/tunel").json()["titular_pronto"], "confere um codigo: pronta")

    print("  codigo expirado")
    worker.expira = True
    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Moura & Associados Advocacia", "slug": "moura-associados"})
    checar(r.status_code == 200 and r.json()["pedido"]["estado"] == "esperando", "iniciar: esperando", r.text[:160])
    checar(esperar(lambda: (conexao.andamento()["pedido"] or {}).get("estado") == "expirado", 10), "venceu: expirado",
           conexao.andamento())
    pedido = local.get("/api/acesso/tunel").json()["conexao"]["pedido"]
    checar(pedido["slug"] == "moura-associados" and pedido["nome"] == "Moura & Associados Advocacia"
           and pedido["endereco"] == "moura-associados.paulus.ia.br", "o nome escolhido continua no pedido", pedido)
    checar(not servico.cofre.tem() and not prefs["hostname"], "e nada ficou guardado")
    worker.expira = False

    print("  tentar de novo, e o fluxo inteiro")
    abertos.clear()
    r = local.post("/api/acesso/tunel/conectar", json={"nome": pedido["nome"], "slug": pedido["slug"]})
    checar(r.status_code == 200 and worker.iniciado["slug"] == "moura-associados", "tentar de novo usa o mesmo nome",
           worker.iniciado)
    corpo = r.json()
    checar(corpo["pedido"]["codigo_usuario"] == "ABCD-EFGH" and "codigo_dispositivo" not in r.text,
           "a tela recebe o codigo curto, e nao o secreto")
    checar(abertos == ["https://paulus.ia.br/conectar?c=ABCD-EFGH"], "abre o navegador em paulus.ia.br/conectar", abertos)
    checar(47000 <= worker.iniciado["porta"] <= 47999, "a porta fixa entre 47000 e 47999", worker.iniciado["porta"])
    checar(worker.iniciado["nome"] == "Moura & Associados Advocacia" and worker.iniciado["instalacao_id"],
           "vai o nome do escritorio e a instalacao", worker.iniciado)
    checar(esperar(lambda: (conexao.andamento()["pedido"] or {}).get("estado") == "concluido", 10),
           "pendente, pendente, pronto: concluido", conexao.andamento())
    prefs = api.estado.prefs.dados["acesso_remoto"]
    checar(prefs["ligado"] and prefs["hostname"] == "moura-associados.paulus.ia.br"
           and prefs["turnstile_sitekey"] == "0x4AAAAAAA-sitekey" and prefs["porta"] == worker.iniciado["porta"],
           "grava endereco, sitekey e porta, e liga", prefs)
    checar(servico.cofre.token() == TOKEN and servico.cofre.segredo() == SEGREDO, "token e segredo guardados (DPAPI)")
    guardado = (servico.pasta / "tunel.json").read_text(encoding="utf-8")
    checar(TOKEN not in guardado and SEGREDO not in guardado, "e nao em texto puro no arquivo")
    checar(esperar(lambda: servico.tunel.estado == "conectado", 10), "o tunel ligou", servico.tunel.estado)
    checar(servico.situacao()["estado"] == "conectado", "a situacao diz conectado", servico.situacao()["estado"])
    checar(local.get("/api/acesso/entrar/config").json()["turnstile_sitekey"] == "0x4AAAAAAA-sitekey",
           "a tela de entrar recebe a sitekey")
    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Outro", "slug": "outro-nome"})
    checar(r.status_code == 400 and "remova" in r.json().get("detail", ""), "ja conectado: para trocar, remover antes")

    print("  desligar e ligar")
    local.post("/api/acesso/tunel/ligar", json={"ligado": False})
    checar(not servico.tunel.ligado and servico.situacao()["estado"] == "desligado", "desligar para o tunel e mantem o endereco")
    checar(api.estado.prefs.dados["acesso_remoto"]["hostname"], "o endereco ficou")
    local.post("/api/acesso/tunel/ligar", json={"ligado": True})
    checar(esperar(lambda: servico.tunel.estado == "conectado", 10), "ligar sobe de novo")

    print("  remover")
    r = local.post("/api/acesso/tunel/remover")
    checar(r.status_code == 200 and worker.removido, "remove no Worker", r.text[:200])
    prefs = api.estado.prefs.dados["acesso_remoto"]
    checar(not servico.cofre.tem() and not prefs["ligado"] and not prefs["hostname"] and not prefs["turnstile_sitekey"]
           and not prefs["porta"], "e aqui: token, segredo, endereco, sitekey e porta", prefs)
    checar(not servico.tunel.ligado and servico.situacao()["estado"] in ("desligado", "nao_conectado"), "o tunel parou",
           servico.situacao()["estado"])
    checar(local.get("/api/acesso/tunel").json()["conexao"]["pedido"] is None, "o pedido saiu da tela")
    r = local.get("/api/acesso/tunel/disponivel", params={"nome": "moura-associados"}).json()
    checar(r["disponivel"] is True, "e o nome volta a ficar livre", r)


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
    fonte = (aqui / "Instalador.cs").read_text(encoding="utf-8")
    checar("o.Tunel = !temCloudflared;" in fonte and "o.Tunel = !CloudflaredPresente();" in fonte,
           "o cloudflared vem sempre que falta, na instalacao e na atualizacao")
    checar('"tunel", delegate' not in fonte and "configurar-acesso" not in fonte,
           "sem caixa de marcar e sem 'configurar agora' no instalador (a escolha e do assistente, no app)")
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
    print("  R7 - o passo 'Acesso a distancia' e o instalador")
    print("=" * 55)
    try:
        test_sugestao()
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
