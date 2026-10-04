"""
O aviso da nuvem (x-paulus-aviso, worker/ia.js): na primeira semana do Plus, o
Opus libera no 8º dia e o Sonnet responde. O PAULUS lê o cabeçalho, mostra o
aviso embaixo da resposta e não o grava no registro de envios.

Rodar: venv\\Scripts\\python.exe tests\\test_aviso_nuvem.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-aviso-nuvem-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
AVISO = "Claude Opus 5.5 libera no 8º dia da assinatura (11/10/2026); até lá, responde o Claude Sonnet 5.5"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def resposta(cabecalhos: dict):
    class R:
        status_code = 200
        headers = cabecalhos

        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "Resposta."}}]})
            yield "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
            yield "data: [DONE]"

        def close(self):
            pass
    return R()


def main() -> int:
    import nuvem

    original = nuvem._pedir
    try:
        nuvem._pedir = lambda *a, **k: resposta({"x-paulus-modelo": "claude-sonnet-5-5", "x-paulus-aviso": quote(AVISO)})
        partes: list[str] = []
        uso = nuvem.chamar("paulus", "meta-llama/Llama-3.3-70B-Instruct", "pia_x", [{"role": "user", "content": "oi"}], partes.append, nivel="ministro")
        checar(uso.get("aviso") == AVISO and uso.get("modelo") == "claude-sonnet-5-5" and "".join(partes) == "Resposta.",
               "o aviso do cabeçalho chega decodificado, com o modelo que respondeu", uso)
        nuvem._pedir = lambda *a, **k: resposta({"x-paulus-modelo": "claude-opus-5-5"})
        uso = nuvem.chamar("paulus", "x", "pia_x", [{"role": "user", "content": "oi"}], lambda t: None)
        checar("aviso" not in uso, "sem o cabeçalho, sem aviso", uso)
    finally:
        nuvem._pedir = original

    js = (RAIZ / "frontend" / "js" / "03-assistente.js").read_text(encoding="utf-8")
    checar("como.nuvem.aviso" in js and "ass-aviso" in js, "a conversa mostra o aviso embaixo da resposta (03-assistente.js)")
    css = (RAIZ / "frontend" / "css" / "02-conversa.css").read_text(encoding="utf-8")
    checar(".ass-aviso" in css, "e o estilo dele (02-conversa.css)")
    fonte = (RAIZ / "src" / "nuvem.py").read_text(encoding="utf-8")
    checar(fonte.count('uso.pop("aviso", "")') == 3, "nos três caminhos da nuvem o aviso sai do uso antes do registro de envios")

    if _falhas:
        print(f"\n  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
