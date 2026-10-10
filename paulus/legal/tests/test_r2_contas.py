"""
Portao da R2 - contas, senha, TOTP e sessoes remotas (src/acesso/contas.py,
remoto.py e rotas.py).

  - senha certa + codigo certo abre a sessao; codigo de duas janelas atras
    (60 s) e recusado, e o mesmo codigo nao vale duas vezes;
  - a 6a tentativa encontra a conta bloqueada, e o bloqueio seguinte dobra;
  - a sessao morre com 30 min sem uso e com 12 h de idade, mesmo em uso;
  - o 20o erro do mesmo endereco em 10 min fecha o endereco por 1 hora -
    para qualquer conta, mesmo com a senha certa;
  - conta que nao existe e senha errada: a mesma resposta, no mesmo tempo;
  - a sessao morre com 30 min sem uso e com 12 h de idade, mesmo em uso;
  - sem o token anti-CSRF, pedido que altera algo recebe 403;
  - criar conta por requisicao remota: 403, mesmo com sessao valida;
  - trocar a senha derruba as sessoes da conta.

De fora (sem Cloudflare Access, decisao de 28/09/2026): o Turnstile vem antes
da senha e nao conta tentativa; sem sessao, so a tela de entrar e o que ela
carrega - toda /api/* responde 401; toda resposta leva os cabecalhos de
seguranca; trocar a propria senha e encerrar as sessoes pedem o codigo de
novo.

A parte das regras roda com relogio de mentira (o teste anda no tempo sem
esperar). A parte HTTP usa o app de verdade, com o Turnstile simulado: a
conferencia de verdade (no Worker) e testada na R6 e em worker/teste-tunel.mjs.

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
    checar(criada["otpauth"].startswith("otpauth://totp/Paulus:ana%40escritorio.com?secret="), "otpauth://", criada["otpauth"])
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

    print("\nforca bruta por endereco")
    r2 = Relogio()
    fechados = []
    c2 = _contas(r2, ao_bloquear=lambda email, nome, ate: fechados.append((email, nome, ate)))
    feita = c2.criar("Dora", "dora@escritorio.com", "titular", "senha-da-dora-1")
    c2.confirmar_totp(feita["conta"]["id"], _codigo(feita["segredo"], r2.t))
    ultimo = None
    for i in range(19):
        try:
            # Um e-mail por tentativa: o bloqueio da conta (5) nao entra no caminho.
            c2.entrar_com_senha(f"quem{i}@fora.com", "chute-chute", ip="200.5.5.5")
        except ErroEntrada as exc:
            ultimo = exc
        r2.t += 20
    checar(not ultimo.ate, "19 erros do mesmo endereco ainda nao fecham", ultimo.ate)
    try:
        c2.entrar_com_senha("quem19@fora.com", "chute-chute", ip="200.5.5.5")
    except ErroEntrada as exc:
        ultimo = exc
    checar(bool(ultimo.ate) and abs(ultimo.ate - r2.t - 3600) < 2, "o 20o erro em 10 min fecha o endereco por 1 hora",
           ultimo.ate and ultimo.ate - r2.t)
    checar(fechados and fechados[-1][1] == "o endereço 200.5.5.5", "e avisa a janela local", fechados[-1:])
    try:
        c2.entrar_com_senha("dora@escritorio.com", "senha-da-dora-1", ip="200.5.5.5")
        checar(False, "a 21a, com a senha certa de outra conta, encontra o endereco fechado")
    except ErroEntrada as exc:
        checar("endereço" in str(exc), "a 21a, com a senha certa de outra conta, encontra o endereco fechado", str(exc))
    checar(bool(c2.entrar_com_senha("dora@escritorio.com", "senha-da-dora-1", ip="200.6.6.6")),
           "de outro endereco, a Dora entra")
    r2.t += 3601
    checar(bool(c2.entrar_com_senha("dora@escritorio.com", "senha-da-dora-1", ip="200.5.5.5")),
           "passada 1 hora, o endereco abre de novo")
    for i in range(19):
        try:
            c2.entrar_com_senha(f"lento{i}@fora.com", "chute-chute", ip="200.7.7.7")
        except ErroEntrada:
            pass
        r2.t += 40  # 19 erros em 12 minutos: a janela e de 10
    try:
        c2.entrar_com_senha("lento19@fora.com", "chute-chute", ip="200.7.7.7")
    except ErroEntrada as exc:
        ultimo = exc
    checar(not ultimo.ate, "20 erros espalhados em mais de 10 min nao fecham", ultimo.ate)
    msgs = []
    for email, senha in (("ninguem-aqui@fora.com", "qualquer-uma"), ("dora@escritorio.com", "errada-errada")):
        try:
            c2.entrar_com_senha(email, senha, ip="200.8.8.8")
        except ErroEntrada as exc:
            msgs.append(str(exc))
    checar(len(msgs) == 2 and msgs[0] == msgs[1], "conta que nao existe e senha errada: a mesma frase", msgs)

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
    print("\nHTTP, de fora, com o Turnstile simulado")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    local = TestClient(api.app, headers=api.cabecalho_local())
    # O Turnstile simulado: "ok" passa, "fora" e o Worker fora do ar, o resto
    # e robo. A conferencia de verdade e do Worker (worker/teste-tunel.mjs).
    antes = servico.conferir_turnstile
    vistos = []

    def turnstile(token, ip=""):
        vistos.append((token, ip))
        return {"ok": "ok", "fora": "indisponivel"}.get(token, "recusado")

    servico.conferir_turnstile = turnstile

    def de_fora(ip: str = "200.1.2.3") -> TestClient:
        return TestClient(api.app, base_url="https://carla.paulus.ia.br", headers={"Cf-Connecting-IP": ip})

    r = local.post("/api/acesso/contas", json={"nome": "Carla", "email": "carla@escritorio.com",
                                               "papel": "titular", "senha": "carla-senha-forte"})
    checar(r.status_code == 200, "a janela local cria a conta", r.text[:200])
    criada = r.json()
    cid = criada["conta"]["id"]
    # A conta nasce sem senha (entra-se com a Conta Atos, 09/10/2026). O resto deste teste e da entrada por
    # senha de quem ja tinha uma: a senha entra pela rota local de trocar a senha.
    local.post(f"/api/acesso/contas/{cid}/senha", json={"senha": "carla-senha-forte"})
    recuperacao = list(criada["codigos_recuperacao"])
    agora = time.time()
    r = local.post(f"/api/acesso/contas/{cid}/autenticador/confirmar",
                   json={"codigo": codigo_totp(criada["segredo"], int(agora // 30))})
    checar(r.status_code == 200, "e confirma o autenticador", r.text[:200])

    fora = de_fora()
    checar(fora.get("/api/acesso/eu").status_code == 403, "modulo desligado: 403")
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    # entra por senha para testar outra coisa: a regra "so Google" fica de lado
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    try:
        print("  sem sessao")
        pagina = fora.get("/")
        checar(pagina.status_code == 200 and "entrar-senha" in pagina.text, "sem sessao, / e a tela de entrar")
        h = pagina.headers
        csp = h.get("content-security-policy", "")
        checar("frame-ancestors 'none'" in csp and "default-src 'self'" in csp and "https://challenges.cloudflare.com" in csp
               and "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0],
               "CSP: so a propria pagina e o Turnstile, sem script embutido solto", csp)
        checar(h.get("x-frame-options") == "DENY" and h.get("referrer-policy") == "no-referrer"
               and h.get("x-content-type-options") == "nosniff" and "camera=()" in h.get("permissions-policy", ""),
               "X-Frame-Options, Referrer-Policy, nosniff e Permissions-Policy", dict(h))
        checar("microphone=(self)" in h.get("permissions-policy", "") and "microphone=()" not in h.get("permissions-policy", ""),
               "o microfone so para o proprio endereco (Gravacoes de fora): o navegador pergunta", h.get("permissions-policy"))
        for caminho in ("/api/status", "/api/acesso/contas", "/api/documentos", "/api/preferencias"):
            r = fora.get(caminho)
            checar(r.status_code == 401 and r.headers.get("x-paulus-sessao") == "acabou",
                   f"sem sessao, {caminho} responde 401", r.status_code)
            checar(r.headers.get("x-frame-options") == "DENY", f"e o 401 de {caminho} leva os cabecalhos")
        r = fora.get("/js/02-casca.js")
        checar(r.status_code == 401 and "entrar-senha" in r.text, "sem sessao, o programa nao e servido: vem a tela de entrar")
        checar(fora.get("/fontes.css").status_code == 200 and fora.get("/css/00-tokens.css").status_code == 200,
               "as fontes e as cores da tela de entrar passam")
        r = fora.get("/api/acesso/entrar/config")
        checar(r.status_code == 200 and "turnstile_sitekey" in r.json(), "a tela de entrar sabe a sitekey", r.text[:120])
        checar(local.get("/").headers.get("x-frame-options") is None, "a janela local nao ganha os cabecalhos de fora")

        print("  o Turnstile antes da senha")
        for _ in range(7):
            r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte"})
        checar(r.status_code == 403 and "robôs" in r.json().get("detail", ""), "sem o Turnstile: 403", r.text[:160])
        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte", "turnstile": "robo"})
        checar(r.status_code == 403, "Turnstile recusado: 403", r.status_code)
        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte", "turnstile": "fora"})
        checar(r.status_code == 503, "sem o Worker para conferir: ninguem entra (503)", r.status_code)
        checar(vistos and vistos[-1][1] == "200.1.2.3", "o IP da Cloudflare vai junto na conferencia", vistos[-1:])
        checar(servico.contas.ip_bloqueado_ate("200.1.2.3") == 0, "Turnstile recusado nao conta tentativa")

        print("  conta que nao existe e senha errada")
        t0 = time.monotonic()
        a = fora.post("/api/acesso/entrar", json={"email": "ninguem@escritorio.com", "senha": "senha-qualquer", "turnstile": "ok"})
        t1 = time.monotonic()
        b = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "senha-errada-1", "turnstile": "ok"})
        t2 = time.monotonic()
        checar(a.status_code == b.status_code == 401 and a.json() == b.json(), "a mesma resposta", (a.text, b.text))
        checar(min(t1 - t0, t2 - t1) >= 0.44 and abs((t1 - t0) - (t2 - t1)) < 0.2, "no mesmo tempo",
               (round(t1 - t0, 3), round(t2 - t1, 3)))

        print("  entrar")
        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte", "turnstile": "ok"})
        checar(r.status_code == 200 and r.json().get("pendente"), "Turnstile + senha certa: falta o codigo", r.text[:200])
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
        checar(fora.get("/api/status").status_code == 200, "com sessao, a API responde")
        r = fora.post("/api/acesso/contas", json={"nome": "X", "email": "x@x.com", "senha": "0123456789ab"},
                      headers={"X-PAULUS-CSRF": csrf})
        checar(r.status_code == 403, "criar conta de fora: 403 mesmo com sessao e CSRF", r.status_code)
        checar(len(servico.contas.listar()) == 1, "e nada foi criado")
        r = fora.post("/api/acesso/sair")
        checar(r.status_code == 403, "sem o token anti-CSRF: 403", r.status_code)

        print("  acoes sensiveis do titular pedem o codigo de novo")
        cab = {"X-PAULUS-CSRF": csrf}
        r = fora.post("/api/acesso/minhas-sessoes/encerrar", json={"codigo": "000000"}, headers=cab)
        checar(r.status_code == 403 and fora.get("/api/acesso/eu").json().get("pessoa"),
               "encerrar as sessoes com codigo errado: 403, e a sessao continua", r.text[:160])
        # "Trocar minha senha" saiu (09/10/2026): a senha e da Conta Atos, em atos.dev.br.
        r = fora.post("/api/acesso/minha-senha", json={"atual": "carla-senha-forte", "nova": "outra-senha-forte-1",
                                                       "codigo": "000000"}, headers=cab)
        checar(r.status_code in (403, 404, 405) and fora.get("/api/acesso/eu").json().get("pessoa"),
               "trocar a propria senha de fora nao existe mais", r.status_code)
        fora.post("/api/acesso/sair", headers=cab)

        # Entra de novo (codigo de recuperacao) e encerra tudo com o codigo.
        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte", "turnstile": "ok"})
        r = fora.post("/api/acesso/entrar/codigo", json={"pendente": r.json()["pendente"], "codigo": recuperacao.pop()})
        csrf = r.json()["csrf"]
        r = fora.post("/api/acesso/minhas-sessoes/encerrar", json={"codigo": recuperacao.pop()}, headers={"X-PAULUS-CSRF": csrf})
        checar(r.status_code == 200 and r.json().get("encerradas") == 1, "encerrar as sessoes com o codigo", r.text[:160])
        checar(fora.get("/api/acesso/eu").json().get("pessoa") is None, "e ninguem fica de fora")

        r = fora.post("/api/acesso/entrar", json={"email": "carla@escritorio.com", "senha": "carla-senha-forte", "turnstile": "ok"})
        r = fora.post("/api/acesso/entrar/codigo", json={"pendente": r.json()["pendente"], "codigo": recuperacao.pop()})
        caidas = local.post(f"/api/acesso/contas/{cid}/senha", json={"senha": "carla-senha-nova-2"}).json()
        checar(caidas.get("sessoes_encerradas") == 1, "trocar a senha pela janela local encerra a sessao", caidas)
        checar(fora.get("/api/acesso/eu").json().get("pessoa") is None, "e quem estava de fora fica sem sessao")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
        servico.conferir_turnstile = antes


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
