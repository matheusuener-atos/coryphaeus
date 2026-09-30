"""
D2 - o motor que escreve no aparelho (src/aparelho_motor.py,
frontend/motor/trabalhador.js, js/60-aparelho.js).

  - a biblioteca (wllama 3.6.1) é servida daqui, com o SHA-256 de cada
    arquivo conferido; arquivo trocado não chega à página;
  - os pesos saem do Ollama deste escritório pelo hash do blob, divididos em
    partes (D2b: o gguf-split fixo em src/bin); o servidor confere o modelo
    e cada parte; só quem pode escrever no aparelho baixa;
  - a capacidade aceita só números;
  - a CSP de fora deixa compilar WebAssembly e continua sem origem nova;
  - no Edge, com o motor falso (o mesmo trabalhador, sem a biblioteca - não
    precisa de WebGPU): depois de uma escrita, nenhum armazenamento do
    navegador guarda a pergunta, os trechos ou a resposta; o único cache é o
    dos pesos, sob o hash; peso adulterado é apagado e recusado; nenhuma
    requisição sai do PAULUS; a capacidade manda só números.
  - Com WebGPU e memória, o motor de verdade carrega o modelo e escreve;
    sem eles, esse pedaço pula com aviso.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d2_motor.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-d2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
OLLAMA = TMP / "ollama"
os.environ["OLLAMA_MODELS"] = str(OLLAMA)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
SEGREDO_PERGUNTA = "PERGUNTA-SIGILOSA-7731"
SEGREDO_TRECHO = "TRECHO-SIGILOSO-4412"
PESO = b"GGUF-falso-do-teste-" * 512


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def ollama_falso() -> str:
    sha = hashlib.sha256(PESO).hexdigest()
    (OLLAMA / "blobs").mkdir(parents=True, exist_ok=True)
    (OLLAMA / "blobs" / f"sha256-{sha}").write_bytes(PESO)
    man = OLLAMA / "manifests" / "registry.ollama.ai" / "library" / "teste" / "1b"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:" + sha}]}),
                   encoding="utf-8")
    return sha


def _cortar(arquivo, destino):
    destino.mkdir(parents=True, exist_ok=True)
    dados = Path(arquivo).read_bytes()
    metade = len(dados) // 2
    saida = []
    for i, pedaco in enumerate((dados[:metade], dados[metade:]), 1):
        alvo = destino / f"modelo-0000{i}-of-00002.gguf"
        alvo.write_bytes(pedaco)
        saida.append(alvo)
    return saida


def test_servidor(api) -> str:
    print("\no servidor")
    import aparelho_motor
    from acesso import remoto
    from fastapi.testclient import TestClient

    for nome, (sha, _) in aparelho_motor.MOTOR["arquivos"].items():
        arq = aparelho_motor.VENDOR / aparelho_motor.MOTOR["pasta"] / nome
        checar(arq.exists() and aparelho_motor.sha256_do_arquivo(arq) == sha, f"a biblioteca: {nome} bate com o hash fixo")
    checar((aparelho_motor.VENDOR / aparelho_motor.MOTOR["pasta"] / "LICENCE").exists(), "a licença (MIT) vai junto")
    codigo = (aparelho_motor.VENDOR / aparelho_motor.MOTOR["pasta"] / "index.js").read_text(encoding="utf-8")
    checar("import " not in codigo.split("\n", 5)[0] and "from \"http" not in codigo and "from 'http" not in codigo,
           "a biblioteca não importa código de outra origem")
    local = TestClient(api.app, headers=api.cabecalho_local())
    r = local.get("/motor/wllama-3.6.1/wllama.wasm")
    checar(r.status_code == 200 and r.headers["content-type"].startswith("application/wasm"), "o wasm sai daqui, com o tipo certo")
    checar(local.get("/motor/wllama-3.6.1/package.json").status_code == 404, "arquivo fora da lista: 404")
    original = aparelho_motor.MOTOR["arquivos"]["index.js"]
    aparelho_motor.MOTOR["arquivos"]["index.js"] = ("0" * 64, original[1])
    checar(local.get("/motor/wllama-3.6.1/index.js").status_code == 409, "arquivo que não bate com o hash fixo não chega à página")
    aparelho_motor.MOTOR["arquivos"]["index.js"] = original

    pronto, motivo = aparelho_motor.partidor_pronto()
    checar(pronto, "o gguf-split (b11292) está aqui e bate com os hashes fixos", motivo)

    sha = ollama_falso()
    api.estado.prefs.dados.setdefault("aparelho", {})["modelo"] = "teste:1b"
    blob = OLLAMA / "blobs" / f"sha256-{sha}"
    # O modelo falso não é GGUF: a divisão, aqui, só corta os bytes.
    dividir_de_verdade = aparelho_motor.dividir

    def dividir_falso(arquivo, destino):
        destino.mkdir(parents=True, exist_ok=True)
        dados = Path(arquivo).read_bytes()
        metade = len(dados) // 2
        saida = []
        for i, pedaco in enumerate((dados[:metade], dados[metade:]), 1):
            alvo = destino / f"modelo-0000{i}-of-00002.gguf"
            alvo.write_bytes(pedaco)
            saida.append(alvo)
        return saida
    aparelho_motor.dividir = dividir_falso
    blob.write_bytes(PESO[:-1] + b"X")
    os.utime(blob, (time.time() + 5, time.time() + 5))
    m = local.get("/api/aparelho/modelo").json()
    checar(not m.get("disponivel") and "não confere" in m.get("motivo", ""),
           "blob adulterado (o nome diz um hash, o conteúdo outro): nem divide", m)
    blob.write_bytes(PESO)
    os.utime(blob, (time.time() + 10, time.time() + 10))
    m = local.get("/api/aparelho/modelo").json()
    partes = m.get("partes") or []
    checar(m.get("disponivel") and m["sha256"] == sha and len(partes) == 2
           and all(x["url"].startswith(f"/api/aparelho/modelo/{sha}/parte/") for x in partes),
           "o modelo: o blob do Ollama, em partes, pelo hash", m)
    junto = b"".join(local.get(x["url"]).content for x in partes)
    checar(junto == PESO and all(hashlib.sha256(local.get(x["url"]).content).hexdigest() == x["sha256"] for x in partes),
           "as partes saem daqui, inteiras e com o hash anotado")
    guardada = TMP / "dados" / "aparelho" / "partes" / sha / "modelo-00002-of-00002.gguf"
    certa = guardada.read_bytes()
    guardada.write_bytes(b"Z" * len(certa))
    os.utime(guardada, (time.time() + 15, time.time() + 15))
    checar(local.get(partes[1]["url"]).status_code == 409, "parte trocada no disco (mesmo tamanho): o hash não bate, não sai")
    guardada.write_bytes(b"trocada")
    os.utime(guardada, (time.time() + 20, time.time() + 20))
    r = local.get(partes[1]["url"])
    checar(r.status_code == 200 and r.content == certa, "com outro tamanho: divide de novo do modelo conferido e sai a parte certa")
    import shutil as _sh
    _sh.rmtree(TMP / "dados" / "aparelho" / "partes" / sha)
    m = local.get("/api/aparelho/modelo").json()
    partes = m.get("partes") or []
    checar(local.get(f"/api/aparelho/modelo/{'a' * 64}/parte/1").status_code == 404, "hash que não é o do modelo: 404")
    aparelho_motor.dividir = dividir_de_verdade

    # O gguf-split de verdade, no 3B deste computador (se estiver aqui).
    real = aparelho_motor.modelo_do_aparelho("llama3.2:3b", Path.home() / ".ollama" / "models")
    if real.get("erro") or not pronto:
        print("  pulado: sem o llama3.2:3b no Ollama desta máquina — a divisão de verdade não rodou")
    else:
        t0 = time.time()
        feitas = aparelho_motor.dividir(real["arquivo"], TMP / "partes-3b")
        tam = [x.stat().st_size for x in feitas]
        checar(len(feitas) >= 4 and max(tam) <= 540 * 1024 * 1024 and abs(sum(tam) - real["bytes"]) < 50 * 1024 * 1024,
               f"o gguf-split divide o 3B em partes de até 512 MB ({time.time() - t0:.0f} s)", tam)
        _sh.rmtree(TMP / "partes-3b", ignore_errors=True)

    r = local.post("/api/aparelho/capacidade", json={"webgpu": True, "memoria_gb": 8, "tokens_por_segundo": 12.5, "navegador": "Edge"})
    checar(r.status_code == 422, "a capacidade recusa campo que não é número da lista")
    r = local.post("/api/aparelho/capacidade", json={"webgpu": True, "memoria_gb": 8, "tokens_por_segundo": 12.5, "carregou_s": 3.1})
    checar(r.status_code == 200 and r.json()["capacidade"]["tokens_por_segundo"] == 12.5, "e guarda os números")

    csp = remoto.politica_de_conteudo()
    checar("'wasm-unsafe-eval'" in csp and "connect-src 'self';" in csp and "'unsafe-eval'" not in csp.replace("'wasm-unsafe-eval'", ""),
           "a CSP de fora: WebAssembly sim, eval de JavaScript não, e nenhuma origem nova")
    return sha


def test_navegador(api, sha: str) -> None:
    print("\nno navegador (Edge pelo Playwright), com o motor falso")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    from test_gravacoes import _porta_livre, _subir_servidor

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        pag = ctx.new_page()
        erros, pedidos, capacidades = [], [], []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        ctx.on("request", lambda r: pedidos.append(r.url))
        ctx.on("request", lambda r: capacidades.append(r.post_data) if r.url.endswith("/api/aparelho/capacidade") else None)
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof testarCapacidadeDoAparelho === 'function'")
        pag.wait_for_timeout(1500)
        antes = pag.evaluate("() => Object.keys(localStorage).length")

        r = pag.evaluate("async () => { motorAparelho.falso = true; return await testarCapacidadeDoAparelho(); }")
        checar(r.get("tokens_por_segundo") == 42 and r.get("carregou_s") is not None, "o teste de capacidade carrega e mede", r)
        corpo = json.loads(capacidades[-1]) if capacidades else {}
        checar(set(corpo) <= {"webgpu", "memoria_gb", "tokens_por_segundo", "leitura_tps", "carregou_s"}
               and all(isinstance(v, (int, float, bool)) or v is None for v in corpo.values()),
               "a capacidade manda ao servidor só números", corpo)

        texto = pag.evaluate("async (s) => await escreverNoAparelho([{role: 'system', content: 'regras'},"
                             " {role: 'user', content: s}], {temperature: 0.2})",
                             SEGREDO_PERGUNTA + " — trechos: " + SEGREDO_TRECHO)
        checar(texto == "Texto escrito pelo motor falso.", "o trabalhador escreve e devolve", texto)

        varredura = pag.evaluate("""async () => {
          const guardado = [];
          for (const k of Object.keys(localStorage)) guardado.push(k + '=' + localStorage.getItem(k));
          for (const k of Object.keys(sessionStorage)) guardado.push(k + '=' + sessionStorage.getItem(k));
          const bancos = indexedDB.databases ? (await indexedDB.databases()).map((b) => b.name) : [];
          const caches_ = [];
          for (const nome of await caches.keys()) {
            const c = await caches.open(nome);
            for (const req of await c.keys()) {
              const resp = await c.match(req);
              const txt = await resp.clone().text();
              caches_.push({ nome: nome, url: new URL(req.url).pathname, tem: txt.length });
              guardado.push(txt.slice(0, 200000));
            }
          }
          let opfs = [];
          try { const raiz = await navigator.storage.getDirectory(); for await (const [n] of raiz.entries()) opfs.push(n); } catch (e) {}
          const sw = navigator.serviceWorker ? (await navigator.serviceWorker.getRegistrations()).length : 0;
          return { tudo: guardado.join('\\n'), bancos: bancos, caches: caches_, opfs: opfs, sw: sw };
        }""")
        tudo = varredura["tudo"]
        checar(SEGREDO_PERGUNTA not in tudo and SEGREDO_TRECHO not in tudo and "motor falso" not in tudo,
               "depois da escrita, nenhum armazenamento guarda a pergunta, os trechos ou a resposta")
        esperado = sorted(f"/api/aparelho/modelo/{sha}/parte/{i}" for i in (1, 2))
        checar(sorted(c["url"] for c in varredura["caches"]) == esperado and {c["nome"] for c in varredura["caches"]} == {"paulus-modelo"}
               and sum(c["tem"] for c in varredura["caches"]) == len(PESO),
               "o único cache é o dos pesos, parte por parte, sob o hash do modelo", varredura["caches"])
        checar(not varredura["bancos"] and not varredura["opfs"] and not varredura["sw"],
               "nada em IndexedDB, no sistema de arquivos do navegador, nem Service Worker", varredura)
        checar(pag.evaluate("() => Object.keys(localStorage).length") == antes, "e o localStorage continua como estava")

        # peso adulterado: o servidor mandaria certo, mas no caminho chega outro
        pag.evaluate("async () => { await apagarModeloDoAparelho(); }")
        pag.route(f"**/api/aparelho/modelo/{sha}/parte/2", lambda rota: rota.fulfill(status=200, body=b"outra coisa"))
        erro = pag.evaluate("async () => { try { await carregarModeloNoAparelho(); return ''; } catch (e) { return String(e.message); } }")
        caches_depois = pag.evaluate("async () => { const c = await caches.open('paulus-modelo'); return (await c.keys()).map((r) => new URL(r.url).pathname); }")
        checar("hash do modelo não confere" in erro and f"/api/aparelho/modelo/{sha}/parte/2" not in caches_depois,
               "parte com hash errado: apagada e recusada (a parte certa pode ficar)", (erro, caches_depois))
        pag.unroute(f"**/api/aparelho/modelo/{sha}/parte/2")
        pag.evaluate("async () => { await apagarModeloDoAparelho(); }")
        checar(pag.evaluate("async () => (await caches.keys()).length") == 0, "“apagar o modelo” tira os pesos do aparelho")

        fora = [u for u in pedidos if not u.startswith(base) and not u.startswith("data:") and not u.startswith("blob:")]
        checar(not fora, "nenhuma requisição para fora do PAULUS", fora[:3])

        tem_gpu = pag.evaluate("async () => Boolean(navigator.gpu && await navigator.gpu.requestAdapter())")
        if not tem_gpu:
            print("  pulado: este Edge não tem WebGPU — o motor de verdade fica para o teste real (D6)")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  D2 — o motor no aparelho")
    print("=" * 55)
    import api

    import aparelho_motor

    sha = test_servidor(api)
    # O navegador também usa as partes cortadas ao meio (o modelo falso).
    aparelho_motor.dividir, guardado = (lambda a, d: _cortar(a, d)), aparelho_motor.dividir
    try:
        test_navegador(api, sha)
    finally:
        aparelho_motor.dividir = guardado
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
