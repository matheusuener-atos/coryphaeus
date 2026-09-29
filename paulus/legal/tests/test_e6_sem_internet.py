"""
Entrar no servidor sem internet (src/vinculo.py): o PAULUS vinculado a conta
Google abre travado, e sem internet o Google nao responde. O codigo do celular
(Google Authenticator funciona sem conexao) abre o PAULUS:

  - sem nada ligado, a tela diz o que falta (e nao abre);
  - o codigo proprio do servidor: QR, primeiro codigo, codigos de recuperacao;
    o segredo guardado pela protecao de dados do Windows, nao em texto;
  - travado, o codigo certo abre; o mesmo codigo de novo nao; o de
    recuperacao vale uma vez;
  - cinco erros seguidos param as tentativas;
  - com a conta de titular do mesmo e-mail, o codigo dela vale;
  - desligar; e de fora, as rotas nao existem.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e6_sem_internet.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-e6-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_sem_internet() -> None:
    print("\nentrar no servidor sem internet")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    v = api.estado.vinculo
    prefs = api.estado.prefs.dados
    local = TestClient(api.app, headers=api.cabecalho_local())
    agora = [time.time()]
    v.relogio = lambda: agora[0]
    passo = lambda d=0: int(agora[0] // 30) + d  # noqa: E731

    prefs["vinculo"].update(email="dona@gmail.com", nome="Dona", manter_aberto=False, saiu=False)
    v.destravado = False
    e = local.get("/api/vinculo").json()
    checar(e["travado"] and e["sem_internet"]["pronto"] is False, "vinculado e travado, sem nada ligado", e.get("sem_internet"))
    r = local.post("/api/vinculo/sem-internet", json={"codigo": "123456"})
    checar(r.status_code == 400 and "Configurações" in r.json().get("detail", ""), "sem nada ligado: diz o que falta", r.text[:160])

    print("  ligar o codigo do servidor")
    v.destravado = True
    r = local.post("/api/vinculo/sem-internet/ligar")
    novo = r.json()
    checar(r.status_code == 200 and novo["qr_svg"].startswith("<svg") and novo["uri"].startswith("otpauth://"), "o QR", r.text[:120])
    r = local.post("/api/vinculo/sem-internet/confirmar", json={"codigo": "000000"})
    checar(r.status_code == 400, "codigo errado nao liga")
    r = local.post("/api/vinculo/sem-internet/confirmar", json={"codigo": codigo_totp(novo["segredo"], passo())})
    codigos = r.json().get("codigos_recuperacao") or []
    checar(r.status_code == 200 and len(codigos) == 10 and r.json()["estado"]["sem_internet"]["por"] == "servidor",
           "o primeiro codigo liga, com os codigos de recuperacao", r.text[:200])
    guardado = prefs["vinculo"]["offline"]["segredo"]
    checar(guardado and novo["segredo"] not in guardado, "o segredo fica protegido, nao em texto")

    print("  travado, o codigo abre")
    local.post("/api/vinculo/travar")
    checar(local.get("/api/documentos").status_code == 423, "saiu: travado")
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(novo["segredo"], passo())})
    checar(r.status_code == 400, "o codigo que ja ligou nao vale de novo", r.status_code)
    agora[0] += 30
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(novo["segredo"], passo())})
    checar(r.status_code == 200 and not r.json()["travado"] and not r.json()["saiu"], "o codigo novo abre (e limpa o 'saiu')",
           r.text[:160])
    checar(local.get("/api/documentos").status_code == 200, "e o programa responde")
    local.post("/api/vinculo/travar")
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(novo["segredo"], passo())})
    checar(r.status_code == 400, "o mesmo codigo, depois de sair: nao (vale uma vez)")
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigos[0].lower()})
    checar(r.status_code == 200 and not r.json()["travado"], "o codigo de recuperacao abre", r.text[:160])
    local.post("/api/vinculo/travar")
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigos[0]})
    checar(r.status_code == 400, "e vale uma vez so")
    checar(local.get("/api/vinculo").json()["sem_internet"]["recuperacao_restantes"] == 9, "sobram nove")

    print("  tentativas em serie")
    for _ in range(4):
        local.post("/api/vinculo/sem-internet", json={"codigo": "000000"})
    agora[0] += 30
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(novo["segredo"], passo())})
    checar(r.status_code == 400 and "tente de novo" in r.json().get("detail", ""), "cinco erros seguidos param ate o codigo certo",
           r.text[:160])
    agora[0] += 601
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(novo["segredo"], passo())})
    checar(r.status_code == 200, "dez minutos depois, volta", r.text[:160])

    print("  com a conta de titular do mesmo e-mail")
    t = api.estado.acesso_de_fora.contas.criar("Dona", "dona@gmail.com", "titular", "senha-da-dona-12")
    # a conta confere pelo relogio de verdade (o falso acima e so do vinculo)
    real = int(time.time() // 30)
    api.estado.acesso_de_fora.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], real - 1))
    checar(local.get("/api/vinculo").json()["sem_internet"]["por"] == "titular", "a conta de titular vale")
    local.post("/api/vinculo/travar")
    r = local.post("/api/vinculo/sem-internet", json={"codigo": codigo_totp(t["segredo"], real)})
    checar(r.status_code == 200 and not r.json()["travado"], "o codigo do celular da titular abre", r.text[:160])

    print("  desligar, e de fora")
    r = local.post("/api/vinculo/sem-internet/desligar")
    checar(r.status_code == 200 and not prefs["vinculo"]["offline"]["segredo"], "desligar apaga o codigo do servidor")
    prefs["acesso_remoto"]["ligado"] = True
    try:
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
        checar(fora.post("/api/vinculo/sem-internet", json={"codigo": "1"}).status_code in (401, 403), "de fora: nao existe")
    finally:
        prefs["acesso_remoto"]["ligado"] = False


def main() -> int:
    test_sem_internet()
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
