"""
L1 - aprender com o uso (src/aprendizado.py, js/63-aprendizado.js).

  - 👍/👎 numa resposta: grava a nota com a cópia do que foi avaliado; a
    mesma pessoa avaliando de novo troca a nota (uma linha por resposta e
    pessoa); mensagem que não é resposta, nota ou motivo inválidos: recusa;
  - a 👎 com "o que a resposta certa precisa ter" vira caso de teste no
    conjunto real (docs/medicao.md), com cada termo obrigatório;
  - o caderno de falhas: as 👎, as contas por caminho e por motivo, virar
    caso depois, resolver e reabrir; só na janela do escritório;
  - de fora, cada pessoa avalia as próprias respostas e não lê o caderno;
  - a chave desligada recusa a avaliação;
  - no Edge: os polegares na assinatura, o cartão da 👎, a marca na
    resposta, a linha no painel e o caderno em Configurações › Feedback.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l1_aprender.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def conversa(api, pergunta: str, resposta: str, documento: str = "contrato-locacao.txt") -> tuple[str, int]:
    t = api.estado.trabalhos.criar(pergunta) if hasattr(api.estado.trabalhos, "criar") else None
    if t is None:
        raise RuntimeError("Trabalhos.criar não existe")
    t.dizer("pessoa", pergunta)
    t.dizer("paulus", resposta, fontes=[{"documento": documento, "texto": "trecho"}],
            cobertura={"como": {"caminho": "busca", "modelo": "llama3.2:3b"}}, segundos=12)
    api.estado.trabalhos.salvar(t)
    return t.id, len(t.mensagens) - 1


def main() -> int:
    print("=" * 55)
    print("  L1 — aprender com o uso")
    print("=" * 55)
    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    conjunto = TMP / "dados" / "medicao" / "conjunto-real.jsonl"

    print("\navaliar")
    tid, i = conversa(api, "qual o prazo de aviso ao locador?", "O prazo de aviso é de 10 dias.")
    r = local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "bom"})
    checar(r.status_code == 200 and r.json()["nota"] == "bom" and r.json()["pergunta"] == "qual o prazo de aviso ao locador?"
           and r.json()["documentos"] == ["contrato-locacao.txt"] and r.json()["caminho"] == "busca",
           "👍 grava a nota com a cópia da pergunta, dos documentos e do caminho", r.json())
    checar(local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i - 1, "nota": "bom"}).status_code == 404,
           "a mensagem da pessoa não se avalia")
    checar(local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "ótimo"}).status_code == 400,
           "nota desconhecida: recusa")
    checar(local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "ruim", "motivo": "x"}).status_code == 400,
           "motivo desconhecido: recusa")
    r = local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "ruim", "motivo": "fato",
                                                    "comentario": "o prazo é outro", "correcao": "São 30 dias.",
                                                    "deve_conter": "30 dias; cláusula 7"})
    d = r.json()
    checar(r.status_code == 200 and d["nota"] == "ruim" and d["caso"] and d["termos"] == ["30 dias", "cláusula 7"],
           "👎 com o que a resposta certa precisa ter: vira caso de teste", d)
    linhas = [json.loads(x) for x in conjunto.read_text(encoding="utf-8").splitlines()] if conjunto.exists() else []
    checar(len(linhas) == 1 and linhas[0]["pergunta"] == "qual o prazo de aviso ao locador?"
           and linhas[0]["todas"] == [["30 dias"], ["cláusula 7"]] and linhas[0]["documentos"] == ["contrato-locacao.txt"]
           and linhas[0]["origem"] == "caderno de falhas", "o caso entra no conjunto real, com cada termo obrigatório", linhas)
    checar(len(api.estado.base.buscar("SELECT id FROM avaliacoes")) == 1, "avaliar de novo troca a nota: uma linha por resposta e pessoa")
    local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "ruim", "motivo": "fato", "deve_conter": "30 dias"})
    checar(len(conjunto.read_text(encoding="utf-8").splitlines()) == 1, "o caso não se repete quando a nota é gravada de novo")
    checar(local.get(f"/api/aprendizado/da-conversa/{tid}").json()["avaliacoes"].get(str(i), {}).get("nota") == "ruim",
           "a conversa devolve a nota desta pessoa")

    print("\no caderno")
    tid2, i2 = conversa(api, "quem é o fiador?", "Não encontrei o fiador.", "fianca.txt")
    local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid2, "indice": i2, "nota": "ruim", "motivo": "faltou"})
    tid3, i3 = conversa(api, "qual o valor do aluguel?", "O aluguel é R$ 2.000,00.")
    local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid3, "indice": i3, "nota": "bom"})
    c = local.get("/api/aprendizado/caderno").json()
    checar(len(c["falhas"]) == 2 and c["conta"] == {"bom": 1, "ruim": 2} and c["por_caminho"]["busca"] == {"bom": 1, "ruim": 2}
           and c["por_motivo"].get("errou um fato") == 1 and c["casos"] == 1, "as 👎, as contas por caminho e por motivo", c["conta"])
    falha = next(f for f in c["falhas"] if f["pergunta"] == "quem é o fiador?")
    checar(local.post(f"/api/aprendizado/caderno/{falha['id']}/caso", json={"deve_conter": ""}).status_code == 400,
           "virar caso sem dizer o que precisa ter: recusa")
    r = local.post(f"/api/aprendizado/caderno/{falha['id']}/caso", json={"deve_conter": "Carlos Pereira"})
    checar(r.status_code == 200 and r.json()["caso"] and len(conjunto.read_text(encoding="utf-8").splitlines()) == 2,
           "pelo caderno, a falha vira caso depois")
    r = local.post(f"/api/aprendizado/caderno/{falha['id']}/resolver", json={"resolvida": True})
    checar(r.json()["resolvida"] and len(local.get("/api/aprendizado/caderno?abertas=true").json()["falhas"]) == 1,
           "resolvida sai das abertas")
    local.post(f"/api/aprendizado/caderno/{falha['id']}/resolver", json={"resolvida": False})
    boa = api.estado.base.um("SELECT id FROM avaliacoes WHERE nota = 'bom'")
    checar(local.post(f"/api/aprendizado/caderno/{boa['id']}/caso", json={"deve_conter": "x"}).status_code == 400,
           "👍 não vira caso de teste")

    print("\nde fora")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
    else:
        from acesso.contas import codigo_totp

        servico = api.estado.acesso_de_fora
        servico.conferir_turnstile = lambda token, ip="": "ok"
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
        conta = servico.contas.criar("Helena", "helena@x.com", "colaborador", "senha-forte-helena")
        servico.contas.confirmar_totp(conta["conta"]["id"], codigo_totp(conta["segredo"], int(time.time() // 30)))
        local.put(f"/api/acesso/contas/{conta['conta']['id']}/permissoes", json={"niveis": {"acervo": "ver"}})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": "helena@x.com", "senha": "senha-forte-helena", "turnstile": "ok"}).json()["pendente"]
        rr = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(conta["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = rr.json()["csrf"]
        r = f.post("/api/aprendizado/avaliar", json={"trabalho_id": tid3, "indice": i3, "nota": "ruim", "motivo": "fato"})
        checar(r.status_code == 200 and r.json()["pessoa"] == f"conta:{conta['conta']['id']}" and r.json()["pessoa_nome"] == "Helena",
               "de fora, a pessoa avalia com o nome dela", r.status_code)
        checar(local.get(f"/api/aprendizado/da-conversa/{tid3}").json()["avaliacoes"][str(i3)]["nota"] == "bom",
               "e a nota da janela local continua a dela (uma por pessoa)")
        checar(f.get("/api/aprendizado/caderno").status_code == 403 and
               f.post(f"/api/aprendizado/caderno/{falha['id']}/resolver", json={"resolvida": True}).status_code == 403,
               "de fora, ninguém lê nem mexe no caderno")
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False

    print("\ndesligado")
    api.estado.prefs.dados.setdefault("aprendizado", {})["avaliar"] = False
    checar(local.post("/api/aprendizado/avaliar", json={"trabalho_id": tid, "indice": i, "nota": "bom"}).status_code == 409,
           "com a chave desligada, não avalia")
    api.estado.prefs.dados["aprendizado"]["avaliar"] = True

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        sync_playwright = None
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        tid4, i4 = conversa(api, "qual a multa por atraso?", "A multa é de 2% sobre o valor.")
        porta = _porta_livre()
        _subir_servidor(porta)
        base = f"http://127.0.0.1:{porta}"
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                ctx = nav.new_context(viewport={"width": 1280, "height": 860})
                ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag = ctx.new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abrirTrabalho === 'function' && typeof botoesDeAvaliacao === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("(id) => abrirTrabalho(id)", tid4)
                pag.wait_for_selector(".resposta [data-avaliar='bom']", timeout=15000)
                pag.click(".resposta [data-avaliar='bom']")
                pag.wait_for_function("() => document.querySelector(\".resposta [data-avaliar='bom']\").classList.contains('on')", timeout=10000)
                checar(api.estado.base.um("SELECT nota FROM avaliacoes WHERE trabalho_id = ?", (tid4,))["nota"] == "bom",
                       "👍 na assinatura grava e marca o botão")
                pag.click(".resposta [data-avaliar='ruim']")
                pag.wait_for_selector(".apr-cartao", timeout=10000)
                pag.click("[data-apr-motivo='fato']")
                pag.fill("[data-apr='correcao']", "A multa é de 10%.")
                pag.fill("[data-apr='deve_conter']", "10%")
                pag.screenshot(path=str(TMP / "l1-cartao.png"))
                pag.click("[data-apr-enviar]")
                pag.wait_for_selector("text=virou caso de teste", timeout=10000)
                av = api.estado.base.um("SELECT * FROM avaliacoes WHERE trabalho_id = ?", (tid4,))
                checar(av["nota"] == "ruim" and av["motivo"] == "fato" and av["caso"] == 1 and av["correcao"] == "A multa é de 10%.",
                       "👎 abre o cartão: motivo, a resposta certa e o caso de teste", dict(av))
                checar(pag.evaluate("() => document.querySelector(\".resposta [data-avaliar='ruim']\").classList.contains('on')"),
                       "a resposta fica marcada 👎")
                pag.reload(wait_until="load")
                pag.wait_for_function("() => typeof abrirTrabalho === 'function'")
                pag.wait_for_timeout(600)
                pag.evaluate("(id) => abrirTrabalho(id)", tid4)
                pag.wait_for_function("() => { const b = document.querySelector(\".resposta [data-avaliar='ruim']\"); return b && b.classList.contains('on'); }",
                                      timeout=15000)
                checar(True, "reaberta a conversa, a marca volta")
                pag.evaluate("() => mostrarConfig('feedback')")
                pag.wait_for_selector(".apr-falha", timeout=15000)
                texto = pag.inner_text("#apr-caderno")
                checar("qual a multa por atraso?" in texto and "A multa é de 10%." in texto and "caso de teste" in texto,
                       "o caderno em Configurações › Feedback mostra a falha", texto[:200])
                pag.screenshot(path=str(TMP / "l1-caderno.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

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
