"""
Testes da atualizacao do PAULUS (src/atualizacao.py e /api/atualizacao).

  - versao compara como numero (0.9.10 > 0.9.9);
  - o anuncio e conferido: instalador so de endereco conhecido, por HTTPS,
    e com SHA-256;
  - o download confere o SHA-256: diferente, o arquivo e apagado;
  - pelas rotas: verificar guarda o anuncio; do codigo-fonte nao instala;
    com "avisar antes" ligado, fechar o programa nao instala nada.

Sem internet: o HTTP e trocado por respostas prontas, e os dados ficam numa
pasta temporaria (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_atualizacao.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="paulus-atualizacao-"))
os.environ["PAULUS_DADOS"] = str(TMP)
os.environ.pop("PAULUS_INSTALADO", None)
RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import atualizacao as atu  # noqa: E402

_falhas: list[str] = []
CONTEUDO = b"MZ" + b"instalador de mentira " * 5000
SHA = hashlib.sha256(CONTEUDO).hexdigest()
URL = "https://github.com/matheusuener-atos/coryphaeus/releases/download/v9.9.9/PAULUS-9.9.9-instalador.exe"
ANUNCIO = {"versao": "9.9.9", "url": URL, "sha256": SHA, "tamanho": len(CONTEUDO), "publicada": "2026-10-01",
           "notas": "https://github.com/matheusuener-atos/coryphaeus/releases/tag/v9.9.9", "novidades": ["uma coisa nova"]}


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class _Resp:
    def __init__(self, dados=None, conteudo=b"", status=200):
        self._dados, self._conteudo, self.status_code = dados, conteudo, status
        self.headers = {"Content-Length": str(len(conteudo))}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._dados

    def iter_content(self, n):
        for i in range(0, len(self._conteudo), n):
            yield self._conteudo[i:i + n]


def test_versao_e_anuncio() -> None:
    print("\na versão e o anúncio")
    checar(atu.mais_nova("0.9.10", "0.9.9") and not atu.mais_nova("0.9.1", "0.9.1") and not atu.mais_nova("0.9.0", "0.9.1"),
           "compara como número: 0.9.10 é mais nova que 0.9.9")
    checar(not atu.mais_nova("lixo", "0.9.1"), "versão que não é número nunca é mais nova")
    r = atu.consultar("0.9.1", pegar=lambda u: _Resp(ANUNCIO))
    checar(r["nova"] and r["versao"] == "9.9.9" and r["sha256"] == SHA, "consultar lê o anúncio e diz que há versão nova", r)
    for nome, mudar in [("endereço de fora", {"url": "https://exemplo.com/x.exe"}),
                        ("sem HTTPS", {"url": URL.replace("https", "http")}),
                        ("sem SHA-256", {"sha256": "abc"}),
                        ("versão estranha", {"versao": "9.9.9; rm"})]:
        try:
            atu.validar({**ANUNCIO, **mudar})
            checar(False, f"recusa anúncio {nome}")
        except ValueError:
            checar(True, f"recusa anúncio {nome}")


def _esperar(b, limite=5.0):
    fim = time.time() + limite
    while b.andamento()["andando"] and time.time() < fim:
        time.sleep(0.05)


def test_download() -> None:
    print("\no download confere o SHA-256")
    pasta = TMP / "baixados"
    avisados = []
    b = atu.Baixador(pasta, pegar=lambda u: _Resp(conteudo=CONTEUDO))
    b.iniciar(ANUNCIO, ao_terminar=avisados.append)
    _esperar(b)
    e = b.andamento()
    arq = pasta / "PAULUS-9.9.9-instalador.exe"
    checar(e["pronto"] and arq.exists() and avisados == [arq], "baixa, confere e avisa", e)
    checar(b.pronto_para(ANUNCIO) == arq, "o conferido fica pronto para instalar")

    ruim = {**ANUNCIO, "versao": "9.9.10", "sha256": "0" * 64}
    b2 = atu.Baixador(pasta, pegar=lambda u: _Resp(conteudo=CONTEUDO))
    b2.iniciar(ruim)
    _esperar(b2)
    checar("não confere" in b2.andamento()["erro"] and not (pasta / "PAULUS-9.9.10-instalador.exe").exists()
           and not list(pasta.glob("*.parcial")), "SHA-256 diferente: erro e nada fica na pasta", b2.andamento())


def test_api() -> None:
    print("\npelas rotas")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    original = api.atualizacao_mod.consultar
    api.atualizacao_mod.consultar = lambda atual, **k: original(atual, pegar=lambda u: _Resp(ANUNCIO))
    try:
        d = c.get("/api/atualizacao").json()
        checar(d["verificar"] and d["avisar_antes"] and d["anuncio"] is None, "de fábrica: verifica e avisa antes; nada visto ainda", d)
        d = c.post("/api/atualizacao/verificar").json()
        checar(d["anuncio"] and d["anuncio"]["nova"] and d["ultima_consulta"], "verificar guarda o anúncio", d)
        r = c.post("/api/atualizacao/instalar")
        checar(r.status_code == 409 and "git pull" in r.json()["detail"], "rodando do código-fonte, não instala", r.json())
        checar(api.instalar_atualizacao_ao_fechar() is False, "com avisar antes ligado, fechar não instala nada")
        c.post("/api/preferencias", json={"atualizacoes": {"verificar": False, "avisar_antes": False}})
        d = c.get("/api/atualizacao").json()
        checar(not d["verificar"] and not d["avisar_antes"], "as duas chaves se guardam", d)
    finally:
        api.atualizacao_mod.consultar = original


def main() -> int:
    print("=" * 55)
    print("  a atualização")
    print("=" * 55)
    try:
        test_versao_e_anuncio()
        test_download()
        test_api()
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
