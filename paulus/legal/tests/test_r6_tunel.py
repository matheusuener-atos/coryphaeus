"""
Portao da R6 - o tunel dentro do PAULUS (src/acesso/tunel.py e jwt_access.py).

  - com um `cloudflared` de mentira (um script que registra argumentos e
    ambiente, escreve o token no proprio log e diz que conectou): o token NAO
    aparece nos argumentos nem no log do PAULUS, e aparece no ambiente;
  - caiu, levanta de novo; desligar encerra o processo;
  - a versao minima e conferida; o executavel do instalador vem primeiro;
  - o JWT do Access: valido passa; vencido, de outra aplicacao (aud), de
    outro time (iss) e assinado com outra chave, nao; sem as chaves
    alcancaveis, nega;
  - porta fixa ocupada: o acesso de fora fica "porta ocupada" e o tunel nao
    liga; a janela local nao depende dela (a porta fixa e um segundo
    ouvinte, so do tunel);
  - com o acesso ligado, o porteiro usa o conferidor de verdade.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r6_tunel.py
"""

from __future__ import annotations

import base64
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


def _chaves():
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(privada, kid: str) -> dict:
    n = privada.public_key().public_numbers()
    b = lambda i: base64.urlsafe_b64encode(i.to_bytes((i.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()
    return {"kty": "RSA", "kid": kid, "alg": "RS256", "n": b(n.n), "e": b(n.e)}


def _jwt(privada, kid: str, **claims) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    corpo = {"aud": ["aud-do-escritorio"], "iss": "https://atos.cloudflareaccess.com", "email": "ana@x.com",
             "exp": time.time() + 600, **claims}
    entrada = b({"alg": "RS256", "kid": kid, "typ": "JWT"}) + "." + b(corpo)
    assinatura = privada.sign(entrada.encode(), padding.PKCS1v15(), hashes.SHA256())
    return entrada + "." + base64.urlsafe_b64encode(assinatura).rstrip(b"=").decode()


def test_jwt() -> None:
    print("\no JWT do Cloudflare Access")
    from acesso.jwt_access import ConferidorAccess

    chave, outra = _chaves(), _chaves()
    buscas = []
    certs = {"keys": [_jwk(chave, "k1")]}
    c = ConferidorAccess("atos.cloudflareaccess.com", "aud-do-escritorio", buscar=lambda d: buscas.append(d) or certs)
    checar((c(_jwt(chave, "k1")) or {}).get("email") == "ana@x.com", "valido passa")
    checar(c(_jwt(chave, "k1", exp=time.time() - 5)) is None, "vencido: nao")
    checar(c(_jwt(chave, "k1", aud=["outra-app"])) is None, "aud de outra aplicacao: nao")
    checar(c(_jwt(chave, "k1", iss="https://outro.cloudflareaccess.com")) is None, "iss de outro time: nao")
    checar(c(_jwt(outra, "k1")) is None, "assinado com outra chave: nao")
    checar(c("isto.nao.e") is None and c("") is None, "lixo e vazio: nao")
    checar(len(buscas) == 1, "as chaves ficam guardadas (uma busca so)", len(buscas))
    sem_rede = ConferidorAccess("atos.cloudflareaccess.com", "aud-do-escritorio",
                                buscar=lambda d: (_ for _ in ()).throw(OSError("sem internet")))
    checar(sem_rede(_jwt(chave, "k1")) is None, "sem as chaves alcancaveis: nega")


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
    print("\no porteiro com o conferidor de verdade")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.jwt_access import ConferidorAccess

    chave = _chaves()
    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    prefs.update(ligado=True, aud="aud-do-escritorio", team_domain="atos.cloudflareaccess.com")
    servico.configurar_conferidor(buscar=lambda d: {"keys": [_jwk(chave, "k1")]})
    try:
        checar(isinstance(servico.verificar_jwt, ConferidorAccess), "ligado e conectado, o conferidor e montado")
        de_fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
        r = de_fora.get("/", headers={"Cf-Access-Jwt-Assertion": _jwt(chave, "k1")})
        checar(r.status_code == 200 and "entrar-senha" in r.text, "JWT valido: chega a tela de entrar")
        r = de_fora.get("/", headers={"Cf-Access-Jwt-Assertion": _jwt(chave, "k1", aud=["outra"])})
        checar(r.status_code == 403, "JWT de outra aplicacao: 403 antes do login")
        checar(de_fora.get("/").status_code == 403, "sem JWT: 403")
        s = servico.situacao()
        checar(set(s) >= {"estado", "cloudflared", "porta", "porta_ocupada", "hostname"}, "a situacao do tunel para a tela", s)
    finally:
        prefs.update(ligado=False, aud="", team_domain="")
        servico.verificar_jwt = None


def main() -> int:
    print("=" * 55)
    print("  R6 - o tunel dentro do PAULUS")
    print("=" * 55)
    try:
        test_processo()
        test_onde_esta()
        test_jwt()
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
