"""
A semana na conversa (`Conversa - Agendar`, js/83-agendar-na-conversa.js):
dois compromissos no mesmo horário ficam lado a lado, e não um em cima do
outro; o horário proposto (tracejado) também divide a faixa.

    python tests/test_agenda_faixas.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-agf-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


def _dia_util() -> date:
    d = date.today() + timedelta(days=2)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    dia = _dia_util()
    e.agenda.salvar({"titulo": "Audiência Rio Fresco", "data": dia.isoformat(), "hora": "10:00", "duracao": 60})
    e.agenda.salvar({"titulo": "Reunião com o perito", "data": dia.isoformat(), "hora": "10:30", "duracao": 60})
    e.agenda.salvar({"titulo": "Almoço", "data": dia.isoformat(), "hora": "13:00", "duracao": 60})
    porta = _porta_livre()
    _subir_servidor(porta)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1984, "height": 1064})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)
        pag.fill("#pedido", f"marque uma reunião com a Priscila dia {dia.day:02d}/{dia.month:02d} às 10h")
        pag.click("#enviar")
        pag.wait_for_selector(f".agc-col[data-agc-dia='{dia.isoformat()}'] .agc-bloco", timeout=20000)
        pag.wait_for_timeout(800)
        blocos = pag.evaluate(f"""() => {{ const col = document.querySelector(".agc-col[data-agc-dia='{dia.isoformat()}']");
          const c = col.getBoundingClientRect();
          return [...col.querySelectorAll('.agc-bloco')].map(b => {{ const r = b.getBoundingClientRect();
            return {{titulo: b.querySelector('b').textContent, x: Math.round(r.left - c.left), w: Math.round(r.width), col: Math.round(c.width),
                    proposta: b.classList.contains('agc-proposta')}}; }}); }}""")
        por = {b["titulo"]: b for b in blocos}
        aud, per, alm = por.get("Audiência Rio Fresco"), por.get("Reunião com o perito"), por.get("Almoço")
        prop = next((b for b in blocos if b["proposta"]), None)
        checar(aud and per and prop, "os três blocos das 10h e o tracejado", blocos)
        if aud and per and prop:
            xs = sorted({aud["x"], per["x"], prop["x"]})
            checar(len(xs) == 3 and max(b["w"] for b in (aud, per, prop)) < aud["col"] / 2, "lado a lado, cada um com a sua faixa", blocos)
        checar(alm and alm["w"] > alm["col"] - 12, "o que não se sobrepõe fica com a largura toda", alm)
        pag.screenshot(path=str(CAPTURAS / "faltas-agenda-faixas.png"))
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
