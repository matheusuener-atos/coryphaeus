"""
C2 - a tela enquanto pensa.

Com a habilidade de perguntar simulada (12 documentos sem trecho, texto
devagar) e as chaves `conversa.execucao` e `conversa.pensando` ligadas:

  - as etapas chegam com os nomes do servidor desde o primeiro evento;
  - a resposta salva nunca tem lista de mais de 5 nomes de documento: os
    documentos sem trecho viram contagem, e o "ver detalhes" fica guardado
    com a resposta (src/detalhes.py);
  - na tela (Edge): a linha de estado aparece no lugar da resposta; cartao e
    painel nunca mostram contagens de etapa diferentes; nenhum texto
    informativo com a cor de erro; a lista dos sem-trecho fica recolhida;
    "Tentar de novo" faz a pergunta de novo;
  - com a chave desligada, a resposta salva tem a lista como antes.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_c2_pensando.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import detalhes  # noqa: E402
from test_c1_execucao import _esperar, _ler_eventos, _pedir  # noqa: E402

_falhas: list[str] = []
SEM_TRECHO = [f"Contrato {i:02d} - cliente de teste.docx" for i in range(12)]
PEDACOS = [f"parte{i} " for i in range(16)]
FALHAR = {"vezes": 0}


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def executar_simulado(ctx, pergunta: str = "", top: int = 6, apenas=None):
    if FALHAR["vezes"] > 0:
        FALHAR["vezes"] -= 1
        raise RuntimeError("o modelo não respondeu (simulado)")
    yield "fontes", {"consultados": ["Contrato A.docx"], "ignorados": list(SEM_TRECHO), "total_contratos": 13,
                     "apenas": [], "trechos": [{"documento": "Contrato A.docx", "trecho": 1, "score": 1.0, "texto": "multa de 10%"}]}
    time.sleep(0.4)
    yield "lendo", {"caracteres": 3400, "trechos": 1, "documentos": 1, "caminho": "busca", "modelo": "simulado",
                    "janela": 8192, "previsao": {"sabe": True, "segundos": 42, "medicoes": 5}}
    time.sleep(0.6)
    yield "escrevendo", {"lendo_segundos": 1.0}
    for p in PEDACOS:
        if ctx.parar and ctx.parar():
            return
        time.sleep(0.15)
        yield "token", {"t": p}
    yield "fim", {}


def test_modulo() -> None:
    print("\no \"ver detalhes\" a partir do registro")
    eventos = [
        {"seq": 1, "em": "2026-09-30T10:00:00", "tipo": "execucao", "dados": {}},
        {"seq": 2, "em": "2026-09-30T10:00:01", "tipo": "fontes",
         "dados": {"consultados": ["A"], "ignorados": SEM_TRECHO, "total_contratos": 13, "apenas": [], "trechos": [{}]}},
        {"seq": 3, "em": "2026-09-30T10:00:02", "tipo": "lendo", "dados": {"caracteres": 3400, "modelo": "m", "janela": 8192}},
        {"seq": 4, "em": "2026-09-30T10:00:40", "tipo": "escrevendo", "dados": {"lendo_segundos": 38.2}},
        {"seq": 5, "em": "2026-09-30T10:00:50", "tipo": "erro", "dados": {"mensagem": "caiu"}},
    ]
    linhas = detalhes.linhas(eventos)
    textos = [l["texto"] for l in linhas]
    checar(any("12 documentos sem nada sobre isso" == x for x in textos), "os sem-trecho viram contagem", textos)
    checar(not any(SEM_TRECHO[0] in x for x in textos), "nenhum nome de documento sem trecho nas linhas")
    checar(linhas[-1]["classe"] == "erro" and all(l["classe"] != "erro" for l in linhas[:-1]),
           "só o erro leva a classe de erro")
    checar(linhas[2]["s"] == 2.0 and linhas[3]["s"] == 40.0, "cada linha com os segundos desde o começo",
           [l["s"] for l in linhas])
    checar(detalhes.nomes_curtos([f"d{i}" for i in range(8)]) == "d0, d1, d2, d3, d4 e mais 3",
           "mais de 5 nomes vira 'e mais N'")


def test_api_e_tela() -> None:
    print("\npela API e na tela")
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    habilidade = api.estado.registro.obter("perguntar")
    antes_exec, antes_prefs = habilidade.executar, dict(api.estado.prefs.dados.get("conversa") or {})
    habilidade.executar = executar_simulado
    api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "pensando": True, "painel": False}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    criados = []
    try:
        t = _pedir(base, "POST", "/api/trabalhos", {"pedido": "teste C2"})
        criados.append(t["id"])
        r = _pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar",
                   {"pergunta": "qual a multa do contrato A?", "apenas": ["Contrato A.docx"]}, stream=True)
        eventos = _ler_eventos(r)
        r.close()
        tipos = [tp for tp, _ in eventos]
        checar(tipos[:2] == ["execucao", "etapas"] and eventos[1][1]["etapas"][0]["titulo"] == "Procurar nos documentos",
               "as etapas do servidor chegam logo depois do id, com os nomes dele", tipos[:3])
        conversa = _pedir(base, "GET", f"/api/trabalhos/{t['id']}")
        m = conversa["mensagens"][-1]
        cob = m.get("cobertura") or {}
        checar(cob.get("ignorados") == [] and cob.get("ignorados_n") == 12,
               "a resposta salva guarda a contagem dos sem-trecho, não a lista", (len(cob.get("ignorados") or []), cob.get("ignorados_n")))
        nomes = sum(1 for n in SEM_TRECHO if n in str(m))
        checar(nomes == 0, "a resposta salva não tem nenhum dos 12 nomes", nomes)
        det = cob.get("detalhes") or []
        checar(len(det) >= 4 and cob.get("execucao_id"), "o \"ver detalhes\" fica guardado com a resposta",
               [d["texto"][:30] for d in det])
        test_tela(base, criados)

        # chave desligada: a lista como antes
        api.estado.prefs.dados["conversa"] = {**antes_prefs, "execucao": True, "pensando": False}
        c = _pedir(base, "POST", "/api/trabalhos", {"pedido": "sem pensando"})
        criados.append(c["id"])
        r = _pedir(base, "POST", f"/api/trabalhos/{c['id']}/perguntar",
                   {"pergunta": "qual a multa do contrato A?", "apenas": ["Contrato A.docx"]}, stream=True)
        _ler_eventos(r)
        r.close()
        m = _pedir(base, "GET", f"/api/trabalhos/{c['id']}")["mensagens"][-1]
        checar(len((m.get("cobertura") or {}).get("ignorados") or []) == 12 and "detalhes" not in (m.get("cobertura") or {}),
               "com a chave desligada, a resposta salva como antes")
    finally:
        habilidade.executar = antes_exec
        api.estado.prefs.dados["conversa"] = antes_prefs
        for id_ in criados:
            try:
                _pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass


def test_tela(base: str, criados: list) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api

    a = _pedir(base, "POST", "/api/trabalhos", {"pedido": "Conversa da tela C2"})
    criados.append(a["id"])
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1440, "height": 900})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); localStorage.setItem('paulus.lateral', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(1500)
        checar(pag.evaluate("() => pensando() && document.documentElement.classList.contains('pensando')"),
               "a tela sabe que a chave está ligada")
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_timeout(500)
        pag.evaluate("() => { enviar({ texto: 'qual a multa do contrato A?', apenas: ['Contrato A.docx'] }); }")
        # Pacote de telas (`Conversa - Carregando`): um cartao so, com o titulo
        # "Trabalhando · etapa k de n", o tempo, as faixas das etapas e o
        # registro aberto dentro dele; a coluna conta igual ao cartao.
        pag.wait_for_selector("#centro .trab-cartao", timeout=8000)
        linhas_vistas, contas, tempos = set(), [], set()
        for _ in range(14):
            estado = pag.evaluate("""() => {
              const andando = document.querySelector('#centro .trab-cartao .agr-etapa.andando > span');
              const quem = document.querySelector('#centro .trab-cartao .quem');
              const m = quem ? quem.textContent.match(/etapa (\\d+) de (\\d+)/) : null;
              const painel = (document.getElementById('lat-progresso-conta') || {}).textContent || '';
              const p = painel.match(/(\\d+) de (\\d+)/);
              const tempo = (document.getElementById('cronometro') || {}).textContent || '';
              return { linha: andando ? andando.textContent : '', cartao: m ? m[1] + ' de ' + m[2] : '', painel: p ? p[1] + ' de ' + p[2] : '', tempo: tempo };
            }""")
            if estado["linha"]:
                linhas_vistas.add(estado["linha"])
            if estado["tempo"]:
                tempos.add(estado["tempo"])
            if estado["cartao"]:
                contas.append((estado["cartao"], estado["painel"]))
            pag.wait_for_timeout(200)
        if os.environ.get("PAULUS_CAPTURAS"):
            pag.screenshot(path=str(Path(os.environ["PAULUS_CAPTURAS"]) / "c2-pensando.png"))
        checar(any(x.startswith(("Ler", "Procurar", "Responder")) for x in linhas_vistas),
               "a etapa que anda diz o que acontece, em linguagem simples", sorted(linhas_vistas))
        checar(any(" de ~4" in x for x in tempos), "com a estimativa do ritmo no tempo do cartão (~42 s de leitura)", sorted(tempos))
        checar(contas and all(c == pn for c, pn in contas), "cartão e painel sempre com a mesma conta de etapas", contas[:4])
        checar(pag.evaluate("() => !!document.querySelector('#centro .trab-cartao .bastidor.solto')"),
               "o registro mora aberto dentro do cartão de trabalho")
        pag.wait_for_function("() => document.querySelector('#centro .resposta .texto')?.textContent.includes('parte15')",
                              timeout=15000)
        pag.wait_for_timeout(800)
        cores = pag.evaluate("""() => {
          const ref = document.createElement('span'); ref.style.color = 'var(--acc)'; document.body.appendChild(ref);
          const erro = getComputedStyle(ref).color; ref.remove();
          const alvos = [...document.querySelectorAll('#centro .bastidor-linha:not(.erro), #centro .aviso-cobertura, #centro .agr-etapa')];
          return { erro: erro, iguais: alvos.filter(e => getComputedStyle(e).color === erro).map(e => e.className + ': ' + e.textContent.slice(0, 40)) };
        }""")
        checar(not cores["iguais"], "nenhum texto informativo com a cor de erro", cores["iguais"][:3])
        aviso = pag.evaluate("() => { const a = document.querySelector('#centro .aviso-cobertura'); const d = a && a.querySelector('details');"
                             " return { texto: a ? a.textContent : '', aberta: d ? d.open : null }; }")
        checar("12 documentos sem nada sobre isso" in aviso["texto"] and aviso["aberta"] is False,
               "ao vivo: a contagem, e a lista recolhida em \"ver lista\"", aviso)
        pag.evaluate(f"() => abrirTrabalho('{a['id']}')")
        pag.wait_for_timeout(1200)
        reaberto = pag.evaluate("() => ({ aviso: (document.querySelector('#centro .aviso-cobertura') || {}).textContent || '',"
                                " detalhes: !!document.querySelector('#centro .detalhes-resposta') })")
        if os.environ.get("PAULUS_CAPTURAS"):
            pag.screenshot(path=str(Path(os.environ["PAULUS_CAPTURAS"]) / "c2-reaberta.png"))
        checar("12 documentos" in reaberto["aviso"] and SEM_TRECHO[0] not in reaberto["aviso"] and reaberto["detalhes"],
               "reaberta: só a contagem, e o \"ver detalhes\" guardado", reaberto)
        # Tentar de novo
        FALHAR["vezes"] = 1
        pag.evaluate("() => { enviar({ texto: 'e o foro?', apenas: ['Contrato A.docx'] }); }")
        pag.wait_for_selector("#centro [data-recarregar]", timeout=10000)
        pag.wait_for_function("() => !estado.ocupado", timeout=10000)
        pag.click("#centro [data-recarregar]")
        pag.wait_for_function("() => [...document.querySelectorAll('#centro .resposta .texto')].pop()?.textContent.includes('parte15')",
                              timeout=20000)
        checar(True, "\"Tentar de novo\" faz a pergunta de novo, e a resposta chega")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  C2 — a tela enquanto pensa")
    print("=" * 55)
    test_modulo()
    test_api_e_tela()
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
