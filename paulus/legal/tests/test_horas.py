"""
Horas por servico e a cobranca delas (src/horas.py, docs/PLANO-PRODUTO.md P4).

  - a duracao escrita de varios jeitos;
  - registrar a mao; o cronometro (um por pessoa; comecar em outro servico
    fecha o de antes); o tempo arredondado para cima;
  - cobrar: as horas nao cobradas viram recebimento de honorarios no
    Financeiro, do cliente do servico, e passam a cobradas;
  - registro cobrado nao se apaga;
  - de fora: o colaborador com "faz" registra as proprias horas e nao apaga as
    dos outros; servico de que nao participa da 404; cobrar e so no servidor.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_horas.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-horas-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_duracao() -> None:
    print("\na duracao")
    import horas

    casos = {"1:30": 90, "1h30": 90, "2h": 120, "90min": 90, "1,5": 90, "0,25": 15, "45min": 45}
    lidos = {k: horas.ler_duracao(k) for k in casos}
    checar(lidos == casos, "1:30, 1h30, 2h, 90min, 1,5", lidos)
    try:
        horas.ler_duracao("muito")
        recusou = False
    except horas.ErroHoras:
        recusou = True
    checar(recusou, "o que nao entende: recusado")
    checar(horas.texto_da_duracao(95) == "1h35" and horas.texto_da_duracao(40) == "40min", "e o texto de volta")


def test_http() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    cli = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Cliente das Horas"}}).json()["id"]
    sid = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Inventário", "cadastro_id": cli}}).json()["id"]
    outro = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Outro serviço"}}).json()["id"]

    r = local.post(f"/api/servicos/{sid}/horas", json={"duracao": "1h30", "descricao": "Petição inicial"})
    checar(r.status_code == 200 and r.json()["total_min"] == 90, "registrar a mao", r.text[:160])
    checar(local.post(f"/api/servicos/{sid}/horas", json={"duracao": "25h"}).status_code == 400, "mais de 24 h num registro: nao")

    agora = [time.time()]
    api.estado.horas.relogio = lambda: agora[0]
    r = local.post(f"/api/servicos/{sid}/horas/cronometro", json={"acao": "comecar", "descricao": "Reunião"})
    checar(r.json()["cronometro"] and r.json()["cronometro"]["neste"], "o cronometro comeca neste servico")
    agora[0] += 20 * 60 + 5
    local.post(f"/api/servicos/{outro}/horas/cronometro", json={"acao": "comecar"})
    h = local.get(f"/api/servicos/{sid}/horas").json()
    checar(h["total_min"] == 90 + 21 and not (h["cronometro"] or {}).get("neste"),
           "comecar em outro servico fecha o de antes (20min05s vira 21 min)", h["total_min"])
    agora[0] += 30 * 60
    r = local.post(f"/api/servicos/{outro}/horas/cronometro", json={"acao": "parar"})
    checar(r.json()["total_min"] == 30 and r.json()["cronometro"] is None, "parar registra o tempo", r.json()["total_min"])

    print("  cobrar")
    r = local.post(f"/api/servicos/{sid}/horas/cobrar", json={})
    checar(r.status_code == 400 and "valor da hora" in r.json().get("detail", ""), "sem o valor da hora: pede antes")
    local.post(f"/api/servicos/{sid}/horas/valor", json={"valor": "300,00"})
    h = local.get(f"/api/servicos/{sid}/horas").json()
    checar(h["valor_hora"] == 30000 and h["a_cobrar_centavos"] == round(111 * 30000 / 60), "o valor a cobrar: 1h51 x R$ 300", h["a_cobrar_centavos"])
    r = local.post(f"/api/servicos/{sid}/horas/cobrar", json={"vencimento": "2026-10-10"})
    lanc = api.estado.financeiro.obter(r.json()["lancamento_id"])
    checar(r.status_code == 200 and lanc["centavos"] == 55500 and lanc["tipo"] == "recebimento" and lanc["categoria"] == "honorarios"
           and lanc["cadastro_id"] == cli and lanc["vencimento"] == "2026-10-10", "vira recebimento de honorarios do cliente", lanc)
    h = local.get(f"/api/servicos/{sid}/horas").json()
    checar(h["a_cobrar_min"] == 0 and h["total_min"] == 111, "as horas passam a cobradas (e continuam no total)")
    cobrado = h["registros"][0]["id"]
    checar(local.delete(f"/api/servicos/{sid}/horas/{cobrado}").status_code == 400, "registro cobrado nao se apaga")

    import segredos

    if not segredos.disponivel():
        return
    print("  de fora")
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"].update(ligado=True, so_google=False)
    passo = int(time.time() // 30) - 1
    try:
        def entrar(nome, email, papel):
            c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
            servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
            if papel != "titular":
                local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": {"servicos": "faz"}})
            f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
            pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(), "turnstile": "ok"}).json()["pendente"]
            r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
            f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
            return f

        entrar("Tita", "tita@x.com", "titular")
        bia = entrar("Bia", "bia@x.com", "colaborador")
        ficha = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "colaborador", "nome": "Bia", "email": "bia@x.com"}}).json()["id"]
        local.post("/api/servicos", json={"id": sid, "dados": {"nome": "Inventário", "cadastro_id": cli, "equipe": [ficha]}})
        r = bia.post(f"/api/servicos/{sid}/horas", json={"duracao": "45min", "descricao": "Pesquisa"})
        checar(r.status_code == 200 and any(x["quem"] == "Bia" and x["minutos"] == 45 for x in r.json()["registros"]),
               "a colaboradora registra as proprias horas, com o nome dela", r.text[:200])
        dela = next(x["id"] for x in r.json()["registros"] if x["quem"] == "Bia")
        nao_dela = next(x["id"] for x in r.json()["registros"] if x["quem"] != "Bia" and not x.get("lancamento_id")) \
            if any(x["quem"] != "Bia" and not x.get("lancamento_id") for x in r.json()["registros"]) else None
        if nao_dela is None:
            local.post(f"/api/servicos/{sid}/horas", json={"duracao": "10min"})
            nao_dela = next(x["id"] for x in local.get(f"/api/servicos/{sid}/horas").json()["registros"] if x["quem"] != "Bia" and not x.get("lancamento_id"))
        checar(bia.delete(f"/api/servicos/{sid}/horas/{nao_dela}").status_code == 400, "e nao apaga as dos outros")
        checar(bia.delete(f"/api/servicos/{sid}/horas/{dela}").status_code == 200, "a propria, apaga")
        checar(bia.get(f"/api/servicos/{outro}/horas").status_code == 404, "servico de que nao participa: 404")
        checar(bia.post(f"/api/servicos/{sid}/horas/cobrar", json={}).status_code in (401, 403), "cobrar de fora: nao")
    finally:
        api.estado.prefs.dados["acesso_remoto"].update(ligado=False, so_google=True)


def main() -> int:
    test_duracao()
    test_http()
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
