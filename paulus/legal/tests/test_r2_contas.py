"""
Portao da R2 - contas, senha, TOTP e sessoes remotas (src/acesso/contas.py,
remoto.py e rotas.py).

  - senha certa + codigo certo abre a sessao; codigo de duas janelas atras
    (60 s) e recusado, e o mesmo codigo nao vale duas vezes;
  - a 6a tentativa encontra a conta bloqueada, e o bloqueio seguinte dobra;
  - a sessao morre com 30 min sem uso e com 12 h de idade, mesmo em uso;
  - sem o token anti-CSRF, pedido que altera algo recebe 403;
  - criar conta por requisicao remota: 403, mesmo com sessao valida;
  - trocar a senha derruba as sessoes da conta.

A parte das regras roda com relogio de mentira (o teste anda no tempo sem
esperar). A parte HTTP usa o app de verdade, com o Cloudflare Access simulado:
o JWT e conferido de verdade na R6; aqui o conferidor e trocado.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r2_contas.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Relogio:
    def __init__(self) -> None:
        self.t = 1_800_000_000.0

    def __call__(self) -> float:
        return self.t


def _contas(relogio, **extra):
    from acesso.contas import Contas

    # O segredo "protegido" de mentira: a DPAPI e do Windows, e as regras
    # valem em qualquer lugar.
    return Contas(TMP / f"contas-{time.time_ns()}.db", proteger=lambda s: "P" + s, revelar=lambda g: g[1:],
                  relogio=relogio, **extra)


def _codigo(segredo: str, instante: float, deslocamento: int = 0) -> str:
    from acesso.contas import codigo_totp

    return codigo_totp(segredo, int(instante // 30) + deslocamento)


def test_regras() -> None:
    print("\nas regras, com relogio de mentira")
    from acesso.contas import ErroConta, ErroEntrada, codigo_totp

    # Vetor da RFC 6238 (SHA-1, segredo "12345678901234567890", T = 59 s):
    # 94287082 em 8 digitos - em 6, os ultimos seis.
    import base64

    rfc = base64.b32encode(b"12345678901234567890").decode()
    checar(codigo_totp(rfc, 59 // 30) == "287082", "TOTP confere com o vetor da RFC 6238")

    r = Relogio()
    bloqueios = []
    c = _contas(r, ao_bloquear=lambda email, nome, ate: bloqueios.append((email, ate)))
    try:
        c.criar("Ana", "ana@escritorio.com", "titular", "curta")
        checar(False, "senha curta e recusada")
    except ErroConta:
        checar(True, "senha curta e recusada")
    criada = c.criar("Ana Titular", "ana@escritorio.com", "colaborador", "senha-longa-123")
    checar(criada["conta"]["papel"] == "titular", "o primeiro cadastro e sempre titular")
    checar(criada["otpauth"].startswith("otpauth://totp/PAULUS:ana%40escritorio.com?secret="), "otpauth://", criada["otpauth"])
    checar(criada["qr_svg"].startswith("<svg"), "o QR sai em SVG, sem dependencia nova")
    checar(len(criada["codigos_recuperacao"]) == 10, "10 codigos de recuperacao")
    segredo, ana = criada["segredo"], criada["conta"]["id"]
    try:
        c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
        checar(False, "sem confirmar o autenticador, nao entra")
    except ErroEntrada:
        checar(True, "sem confirmar o autenticador, nao entra")
    checar(c.confirmar_totp(ana, _codigo(segredo, r.t)), "confirmar o autenticador com o primeiro codigo")

    r.t += 60
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    s = c.entrar_com_codigo(pend, _codigo(segredo, r.t))
    checar(bool(s["sessao"]) and bool(s["csrf"]), "senha certa + codigo certo: sessao")
    checar(c.sessao(s["sessao"])["papel"] == "titular", "a sessao sabe o papel")

    r.t += 90
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    try:
        c.entrar_com_codigo(pend, _codigo(segredo, r.t, -2))
        checar(False, "codigo de duas janelas atras e recusado")
    except ErroEntrada:
        checar(True, "codigo de duas janelas atras e recusado")
    atual = _codigo(segredo, r.t, -1)
    s2 = c.entrar_com_codigo(pend, atual)
    checar(bool(s2["sessao"]), "uma janela atras ainda vale (relogio do celular atrasado)")
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    try:
        c.entrar_com_codigo(pend, atual)
        checar(False, "o mesmo codigo nao vale duas vezes")
    except ErroEntrada:
        checar(True, "o mesmo codigo nao vale duas vezes")
    recuperacao = criada["codigos_recuperacao"][0]
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    checar(bool(c.entrar_com_codigo(pend, recuperacao.lower())["sessao"]), "codigo de recuperacao entra")
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    try:
        c.entrar_com_codigo(pend, recuperacao)
        checar(False, "codigo de recuperacao vale uma vez so")
    except ErroEntrada:
        checar(True, "codigo de recuperacao vale uma vez so")
    checar(c.obter(ana)["codigos_restantes"] == 9, "sobram 9 codigos")

    print("\nforca bruta")
    c.criar("Beto", "beto@escritorio.com", "colaborador", "outra-senha-456")
    for i in range(5):
        try:
            c.entrar_com_senha("beto@escritorio.com", "errada-errada")
        except ErroEntrada as exc:
            ultimo = exc
    checar(ultimo.ate and bloqueios and bloqueios[-1][0] == "beto@escritorio.com", "o 5o erro bloqueia e avisa", bloqueios)
    try:
        c.entrar_com_senha("beto@escritorio.com", "outra-senha-456")
        checar(False, "a 6a tentativa, mesmo com a senha certa, encontra a conta bloqueada")
    except ErroEntrada as exc:
        checar(exc.ate and abs(exc.ate - r.t - 15 * 60) < 2, "a 6a tentativa, mesmo com a senha certa, encontra a conta bloqueada",
               exc.ate - r.t)
    r.t += 15 * 60 + 1
    for i in range(5):
        try:
            c.entrar_com_senha("beto@escritorio.com", "errada-errada")
        except ErroEntrada as exc:
            ultimo = exc
    checar(abs(ultimo.ate - r.t - 30 * 60) < 2, "o bloqueio seguinte dobra (30 min)", ultimo.ate - r.t)
    try:
        for i in range(5):
            try:
                c.entrar_com_senha("ninguem@escritorio.com", "qualquer-coisa")
            except ErroEntrada as exc:
                ultimo = exc
        checar(bool(ultimo.ate), "e-mail sem conta bloqueia igual (o bloqueio nao diz se a conta existe)")
    finally:
        pass

    print("\nsessao")
    r.t += 3600
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    s = c.entrar_com_codigo(pend, _codigo(segredo, r.t))
    r.t += 29 * 60
    checar(c.sessao(s["sessao"]) is not None, "29 min sem uso: viva")
    r.t += 29 * 60
    checar(c.sessao(s["sessao"]) is not None, "usada a cada 29 min: viva")
    r.t += 31 * 60
    checar(c.sessao(s["sessao"]) is None, "31 min sem uso: morta")
    r.t += 60
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    s = c.entrar_com_codigo(pend, _codigo(segredo, r.t))
    comeco = r.t
    viva = True
    for _ in range(12 * 3 + 2):
        r.t += 20 * 60
        viva = c.sessao(s["sessao"]) is not None
        if not viva:
            break
    idade_h = (r.t - comeco) / 3600
    checar(not viva and 12 < idade_h <= 12.34, "em uso sem parar, morre com 12 h de idade", idade_h)
    r.t += 60
    pend = c.entrar_com_senha("ana@escritorio.com", "senha-longa-123")
    s = c.entrar_com_codigo(pend, _codigo(segredo, r.t))
    caidas = c.trocar_senha(ana, "senha-nova-789-xyz")
    checar(caidas >= 1 and c.sessao(s["sessao"]) is None, "trocar a senha derruba as sessoes", caidas)
    try:
        c.remover(ana)
        checar(False, "o unico titular nao sai")
    except ErroConta:
        checar(True, "o unico titular nao sai")


def test_http() -> None:
    print("\nHTTP, com o Cloudflare Access simulado")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    local = TestClient(api.app, headers=api.cabecalho_local())
    # O Access simulado: o JWT "ok:<email>" passa com aquele e-mail.
    servico.verificar_jwt = lambda t: {"email": t[3:]} if t and t.startswith("ok:") else None

    def de_fora(email: str = "carla@escritorio.com") -> TestClient:
        return TestClient(api.app, base_url="https://carla.paulus.ia.br",
                          headers={"Cf-Access-Jwt-Assertion": "ok:" + email, "Cf-Connecting-IP": "200.1.2.3"})

    r = local.post("/api/acesso/contas", json={"nome": "Carla", "email": "carla@escritorio.com",
                                               "papel": "titular", "senha": "carla-senha-forte"})
    checar(r.status_code == 200, "a janela local cria a conta", r.text[:200])
    criada = r.json()
    cid = criada["conta"]["id"]
    agora = time.time()
    r = local.post(f"/api/acesso/contas/{cid}/autenticador/confirmar",
                   json={"codigo": codigo_totp(criada["segredo"], int(agora // 30))})
    checar(r.status_code == 200, "e confirma o autenticador", r.text[:200])

    fora = de_fora()
    checar(fora.get("/api/acesso/eu").status_code == 403, "modulo desligado: 403 mesmo com o Access")
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    try:
        sem_jwt = TestClient(api.app, base_url="https://carla.paulus.ia.br")
        checar(sem_jwt.get("/api/acesso/eu").status_code == 403, "sem o JWT do Access: 403")
        pagina = fora.get("/")
        checar(pagina.status_code == 200 and "entrar-senha" in pagina.text, "sem sessao, / e a tela de entrar")
        checar(fora.get("/api/status").status_code == 401, "sem sessao, a API responde 401")
        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte"})
        checar(r.status_code == 200 and r.json().get("pendente"), "senha certa: falta o codigo", r.text[:200])
        pend = r.json()["pendente"]
        # O codigo da confirmacao nao vale de novo: o passo seguinte.
        codigo = codigo_totp(criada["segredo"], int(agora // 30) + 1)
        r = fora.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo})
        checar(r.status_code == 200, "codigo certo: sessao", r.text[:200])
        bruto = r.headers.get("set-cookie", "")
        checar("HttpOnly" in bruto and "Secure" in bruto and "SameSite=strict" in bruto.replace("Strict", "strict"),
               "cookie HttpOnly; Secure; SameSite=Strict", bruto)
        csrf = r.json()["csrf"]
        eu = fora.get("/api/acesso/eu").json()
        checar(eu.get("pessoa", {}).get("nome") == "Carla" and eu.get("csrf") == csrf, "de fora, com sessao, sabe quem e", eu)
        outro = de_fora("intruso@x.com")
        outro.cookies = fora.cookies
        checar(outro.get("/api/acesso/eu").json().get("pessoa") is None, "sessao com JWT de outro e-mail nao vale")
        r = fora.post("/api/acesso/contas", json={"nome": "X", "email": "x@x.com", "senha": "0123456789ab"},
                      headers={"X-PAULUS-CSRF": csrf})
        checar(r.status_code == 403, "criar conta de fora: 403 mesmo com sessao e CSRF", r.status_code)
        checar(len(servico.contas.listar()) == 1, "e nada foi criado")
        r = fora.post("/api/acesso/sair")
        checar(r.status_code == 403, "sem o token anti-CSRF: 403", r.status_code)
        caidas = local.post(f"/api/acesso/contas/{cid}/senha", json={"senha": "carla-senha-nova-2"}).json()
        checar(caidas.get("sessoes_encerradas") == 1, "trocar a senha pela janela local encerra a sessao", caidas)
        checar(fora.get("/api/acesso/eu").json().get("pessoa") is None, "e quem estava de fora fica sem sessao")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        servico.verificar_jwt = None


def main() -> int:
    print("=" * 55)
    print("  R2 - contas, senha, TOTP e sessoes")
    print("=" * 55)
    try:
        test_regras()
        test_http()
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
