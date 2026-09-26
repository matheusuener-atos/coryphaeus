"""
Apoiar o projeto (src/apoio.py): o programa so repassa ao site, nunca fala
com o Mercado Pago e nunca manda chave nenhuma. Sem rede: requests e trocado.

Rodar: venv\\Scripts\\python.exe tests\\test_apoio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import apoio  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    print(("  ok   " if condicao else "  FALHA ") + descricao + ("" if condicao or not detalhe else f"\n         {detalhe}"))
    if not condicao:
        _falhas.append(descricao)


class _Resposta:
    def __init__(self, status: int, dados: dict):
        self.status_code, self._dados, self.ok = status, dados, 200 <= status < 300

    def json(self):
        return self._dados


def main() -> int:
    chamadas: list[tuple] = []
    original = apoio.requests.request

    def falso(metodo, url, json=None, timeout=None):
        chamadas.append((metodo, url, json))
        if url.endswith("/api/mp/pix") and json and json.get("valor", 0) < 5:
            return _Resposta(400, {"erro": "o valor precisa estar entre R$ 5 e R$ 5000"})
        if url.endswith("/api/mp/pix"):
            return _Resposta(200, {"id": "ORD01TESTE", "qr_code": "000201", "qr_code_base64": "iVBOR"})
        if "/api/mp/pix/" in url:
            return _Resposta(200, {"id": "ORD01TESTE", "pago": True})
        return _Resposta(200, {"id": "pre1", "link": "https://www.mercadopago.com.br/subscriptions/checkout?x"})

    apoio.requests.request = falso
    try:
        print("\nApoiar o projeto")
        d = apoio.criar_pix(40, "apoiador@exemplo.com.br")
        checar(d["qr_code_base64"] == "iVBOR", "o Pix volta com o QR")
        metodo, url, corpo = chamadas[-1]
        checar(url == apoio.SITE + "/api/mp/pix" and url.startswith("https://paulus.ia.br"), "pede ao site, não ao Mercado Pago", url)
        checar(set(corpo) == {"valor", "email"}, "manda só valor e e-mail - nenhuma chave", str(corpo))
        checar(apoio.situacao_do_pix("ORD01TESTE")["pago"] is True, "consulta se o Pix foi pago")
        try:
            apoio.situacao_do_pix("../../etc")
            checar(False, "recusa id de Pix esquisito")
        except apoio.ErroDeApoio:
            checar(True, "recusa id de Pix esquisito")
        try:
            apoio.criar_pix(1, "apoiador@exemplo.com.br")
            checar(False, "o erro do site chega em português")
        except apoio.ErroDeApoio as exc:
            checar("R$ 5" in str(exc), "o erro do site chega em português", str(exc))
        a = apoio.criar_assinatura(40, "apoiador@exemplo.com.br", "qualquer")
        checar(a["link"].startswith("https://www.mercadopago.com.br/"), "a assinatura volta com o link do Mercado Pago")
        checar(chamadas[-1][2]["frequencia"] == "mensal", "frequência desconhecida vira mensal")
    finally:
        apoio.requests.request = original

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S)")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
