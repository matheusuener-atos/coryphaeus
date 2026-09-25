"""
Testes do certificado instalado no Windows, do lado do cofre.

A chave de um certificado do Windows nunca passa por aqui; o que o cofre
guarda e a parte publica e a MARCA da senha do PAULUS. Entao os testes
cobrem:

  - a senha do PAULUS confere quando certa e recusa quando errada;
  - a marca nao contem a senha;
  - o cofre le titular e validade sem senha (sao publicos);
  - enviar um .pfx depois tira o do Windows, e remover limpa tudo.

A assinatura em si pelo Windows depende de um certificado instalado na
maquina e fica fora daqui.

    python tests/test_certificado_windows.py
"""

from __future__ import annotations

import base64
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import certificado  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _publico_de_teste(pasta: Path) -> dict:
    """Um certificado gerado na hora, no formato que o Windows devolveria."""
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs12

    pfx = certificado.gerar_de_teste(pasta / "t.pfx", "x", "FULANO DE TESTE")
    _, cert, _ = pkcs12.load_key_and_certificates(pfx.read_bytes(), b"x")
    return {"impressao": "A" * 40, "der": base64.b64encode(cert.public_bytes(Encoding.DER)).decode(), "cadeia": []}


def main() -> int:
    with tempfile.TemporaryDirectory() as bruto:
        pasta = Path(bruto)
        cofre = certificado.Cofre(pasta / "cofre.json", pasta / "cofre")
        publico = _publico_de_teste(pasta)

        cofre.usar_windows(publico, "minha-senha")
        tela = cofre.para_tela()
        checar(tela["instalado"] and tela["origem"] == "windows", "o certificado do Windows conta como instalado")
        checar((tela["certificado"] or {}).get("titular") == "FULANO DE TESTE", "titular lido sem senha", str(tela["certificado"]))
        checar("minha-senha" not in (pasta / "cofre.json").read_text(encoding="utf-8"), "a senha não vai para o disco, só a marca")
        checar(not cofre.abrir("minha-senha").erro, "a senha certa abre")
        checar(cofre.abrir("outra").erro == "senha do PAULUS incorreta", "a senha errada é recusada")

        # Relido do disco, como depois de fechar e abrir o programa.
        de_novo = certificado.Cofre(pasta / "cofre.json", pasta / "cofre")
        checar(de_novo.origem == "windows" and not de_novo.abrir("minha-senha").erro, "vale depois de reabrir o programa")

        de_novo.guardar_arquivo("c.pfx", (pasta / "t.pfx").read_bytes())
        checar(de_novo.origem == "arquivo" and not de_novo.dados["senha_paulus"], "enviar um .pfx tira o do Windows")

        de_novo.usar_windows(publico, "1234")
        de_novo.remover()
        checar(not de_novo.instalado and not de_novo.windows, "remover limpa o certificado do Windows")

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
