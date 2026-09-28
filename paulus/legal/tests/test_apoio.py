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
        checar(set(corpo) == {"valor", "email", "mural"} and corpo["mural"] == "",
               "manda só valor, e-mail e o nome do mural (vazio sem autorização) - nenhuma chave", str(corpo))
        apoio.criar_pix(40, "apoiador@exemplo.com.br", "Ana Exemplo")
        checar(chamadas[-1][2]["mural"] == "Ana Exemplo", "com autorização, o nome vai para o mural")
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
        a = apoio.criar_assinatura(40, "apoiador@exemplo.com.br")
        checar(a["link"].startswith("https://www.mercadopago.com.br/"), "a assinatura volta com o link do Mercado Pago")
        apoio.mudar_valor("PRE0001", "chave-1", 36)
        checar(chamadas[-1][1].endswith("/api/mp/assinatura/PRE0001/valor") and chamadas[-1][2] == {"chave": "chave-1", "valor": 36},
               "diminuir manda a chave e o valor novo", str(chamadas[-1]))
        apoio.interromper("PRE0001", "chave-1")
        checar(chamadas[-1][1].endswith("/api/mp/assinatura/PRE0001/interromper"), "interromper chama o site")
    finally:
        apoio.requests.request = original

    print("\nO que o site publica")
    import tempfile as _tmp

    with _tmp.TemporaryDirectory() as pasta:
        publicado = {"atualizadoEm": "2026-09-28", "meses": [{"month": "2026-09", "releases": []}]}
        apoio.requests.request = lambda metodo, url, json=None, timeout=None: (
            chamadas.append((metodo, url, json)) or _Resposta(200, publicado))
        try:
            d = apoio.publico("desenvolvimento", pasta)
            checar(chamadas[-1][:2] == ("GET", apoio.SITE + "/api/public/desenvolvimento") and chamadas[-1][2] is None,
                   "lê o histórico público sem mandar nada", str(chamadas[-1]))
            checar(d["meses"] == publicado["meses"] and d["offline"] is False, "e devolve o que o site publica")

            def sem_rede(*a, **k):
                raise apoio.requests.ConnectionError("sem rede")

            apoio.requests.request = sem_rede
            d = apoio.publico("desenvolvimento", pasta)
            checar(d["offline"] is True and d["meses"] == publicado["meses"], "sem internet, volta a última cópia guardada")
            try:
                apoio.publico("apoiadores", pasta)
                checar(False, "sem internet e sem cópia, diz que não deu")
            except apoio.ErroDeApoio:
                checar(True, "sem internet e sem cópia, diz que não deu")
            try:
                apoio.publico("../segredo", pasta)
                checar(False, "só lê o que o site publica")
            except apoio.ErroDeApoio:
                checar(True, "só lê o que o site publica")
        finally:
            apoio.requests.request = original

    print("\nExtrato de contribuições")
    import tempfile

    import extrato_apoio

    linhas = extrato_apoio.montar_linhas(
        [{"data": "2026-09-26T10:00:00", "valor": 5, "id": "ORD01X"}],
        [{"data": "2026-08-27T00:00:00.000-04:00", "valor": 50, "id": "7001", "situacao": "approved"},
         {"data": "2026-09-27T00:00:00.000-04:00", "valor": 50, "id": "7002", "situacao": "scheduled"}])
    checar([l["forma"] for l in linhas] == ["Cartão de crédito", "Pix", "Cartão de crédito"], "da mais antiga à mais nova, Pix e cartão juntos")
    checar([l["tipo"] for l in linhas] == ["Recorrente", "Avulsa", "Recorrente"], "Pix é avulsa; cobrança do cartão, recorrente")
    checar([l["situacao"] for l in linhas] == ["Confirmada", "Confirmada", "Agendada"], "situação em português", str(linhas))
    soma = extrato_apoio.resumo(linhas)
    checar(soma == {"total": 55.0, "periodo": "27/08/2026 a 26/09/2026", "contagem": "2 confirmadas"},
           "o resumo conta só as confirmadas, com o período delas", str(soma))
    checar(extrato_apoio.resumo([])["contagem"] == "nenhuma confirmada", "sem contribuição, o resumo diz nenhuma")
    with tempfile.TemporaryDirectory() as pasta:
        pdf = extrato_apoio.gerar(Path(pasta), nome="Escritório Exemplo", email="apoiador@exemplo.com.br",
                                  pix=[{"data": "2026-09-26T10:00:00", "valor": 5, "id": "ORD01X"}],
                                  cobrancas=[{"data": "2026-08-27", "valor": 50, "id": "7001", "situacao": "approved"},
                                             {"data": "2026-09-27", "valor": 50, "id": "7002", "situacao": "scheduled"}])
        import pypdfium2 as pdfium
        bruto = pdf.read_bytes()
        documento = pdfium.PdfDocument(bruto)
        texto = "\n".join(documento[i].get_textpage().get_text_range() for i in range(len(documento)))
        texto = " ".join(texto.split())  # a linha que quebra no PDF volta inteira
        documento.close()
    checar("Extrato de contribuições" in texto and "R$ 55,00" in texto,
           "título do desenho e o total só do que foi confirmado (5 + 50)", texto[:200])
    checar("TOTAL CONTRIBUÍDO" in texto and "PERÍODO" in texto and "2 confirmadas" in texto, "o quadro tem total, período e contagem")
    checar("Agendada" in texto and "Avulsa" in texto and "Recorrente" in texto, "cada linha tem tipo e situação")
    checar("voluntárias e sem contrapartida" in texto, "diz que a contribuição é voluntária, sem contrapartida")
    checar("não gera ao apoiador direito à dedução do Imposto de Renda" in texto, "diz que não dá dedução do IR")
    checar("Não é nota fiscal nem documento fiscal" in texto, "diz que não é nota fiscal")
    checar("emitido em" in texto and "paulus.ia.br" in texto, "o rodapé traz a emissão e o site")
    embutidas = [n for n in ("PAULUSGaramond", "PAULUSManrope", "PAULUSMono") if n.encode() in bruto]
    checar(len(embutidas) == 3, "Garamond, Manrope e a mono do desenho vão embutidas", str(embutidas))

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S)")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
