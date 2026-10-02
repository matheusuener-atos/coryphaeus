"""
A IA faz parte da assinatura (src/plano.py, 02/10/2026).

  - fora do instalado (terminal, testes), nada muda;
  - com a cobrança ligada e sem conta ou sem plano, o modelo local não é
    chamado - em lugar nenhum - e a conversa diz onde assinar;
  - o que a regra responde (navegação, agenda) continua sem plano;
  - com o plano vigente, liberada; sem internet, vale o plano guardado até o
    fim do ciclo pago, e nunca depois.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_plano.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-plano-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ.pop("PAULUS_COBRANCA", None)
os.environ.pop("PAULUS_INSTALADO", None)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _iso(dias: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


def test_regra() -> None:
    print("\na regra")
    import api
    import nuvem
    import plano
    from llama_client import LlamaClient

    e = api.estado
    plano.esquecer()
    checar(plano.liberada(e) and not plano.cobranca_ligada(), "fora do instalado: liberada, sem cobrança")

    os.environ["PAULUS_INSTALADO"] = "1"
    checar(plano.cobranca_ligada(), "instalado: a cobrança vale")
    os.environ["PAULUS_COBRANCA"] = "0"
    checar(not plano.cobranca_ligada(), "PAULUS_COBRANCA=0 desliga até no instalado")
    os.environ["PAULUS_COBRANCA"] = "1"
    os.environ.pop("PAULUS_INSTALADO", None)

    original = nuvem.conta_paulus
    try:
        nuvem.conta_paulus = lambda estado, forcar=False: None
        plano.esquecer()
        s = plano.situacao(e)
        checar(not s["ia"] and s["motivo"] == "sem_conta", "sem conta da nuvem: sem IA", s)
        try:
            LlamaClient(host="http://127.0.0.1:9").ask("oi")
            barrou = False
        except plano.SemPlano:
            barrou = True
        checar(barrou, "o modelo local não é chamado sem o plano")
        checar(api._juiz() is None, "nem o juiz de uma letra")

        nuvem.conta_paulus = lambda estado, forcar=False: {"plano_vigente": False, "ciclo": None}
        plano.esquecer()
        checar(plano.situacao(e)["motivo"] == "sem_plano", "conta sem plano vigente: sem IA")

        nuvem.conta_paulus = lambda estado, forcar=False: {"plano_vigente": True, "ciclo": {"fim": _iso(20)}}
        plano.esquecer()
        checar(plano.liberada(e), "plano vigente: liberada")
        checar((e.prefs.dados.get("plano") or {}).get("ativo") is True, "o plano fica guardado para sem internet")

        def sem_internet(estado, forcar=False):
            raise OSError("sem rede")

        nuvem.conta_paulus = sem_internet
        plano.esquecer()
        s = plano.situacao(e)
        checar(s["ia"] and s["fonte"] == "guardado", "sem internet: vale o plano guardado até o fim do ciclo", s)
        e.prefs.atualizar({"plano": {"ativo": True, "ate": _iso(-1)}})
        plano.esquecer()
        checar(not plano.liberada(e), "sem internet e o ciclo vencido: sem IA")
    finally:
        nuvem.conta_paulus = original
        plano.esquecer()


def test_conversa() -> None:
    print("\nna conversa, sem plano")
    import api
    import nuvem
    import plano
    import test_c3_painel as c3
    from test_gravacoes import _porta_livre, _subir_servidor

    original = nuvem.conta_paulus
    nuvem.conta_paulus = lambda estado, forcar=False: None
    plano.esquecer()
    hab = api.estado.registro.obter("perguntar")
    antes = hab.executar
    hab.executar = c3.executar_simulado
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    try:
        def perguntar(frase):
            t = c3._pedir(base, "POST", "/api/trabalhos", {"pedido": "plano"})
            r = c3._pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": frase}, stream=True)
            c3._ler_eventos(r)
            r.close()
            m = c3._pedir(base, "GET", f"/api/trabalhos/{t['id']}")["mensagens"][-1]
            c3._pedir(base, "DELETE", f"/api/trabalhos/{t['id']}")
            return m

        m = perguntar("qual a multa do contrato?")
        checar("assinatura" in (m.get("texto") or "") and "multa é de" not in (m.get("texto") or ""),
               "a pergunta sobre documento diz onde assinar, sem ler", m.get("texto"))
        m = perguntar("abra a agenda")
        checar((m.get("proposta") or {}).get("tipo") == "programa", "a navegação continua (regra)", m.get("proposta"))
        s = c3._pedir(base, "GET", "/api/plano")
        checar(s.get("ia") is False and s.get("cobranca") is True and "assinatura" in s.get("frase", ""),
               "/api/plano diz a situação e a frase", s)
    finally:
        hab.executar = antes
        nuvem.conta_paulus = original
        os.environ.pop("PAULUS_COBRANCA", None)
        plano.esquecer()


def main() -> int:
    print("=" * 55)
    print("  A IA faz parte da assinatura")
    print("=" * 55)
    try:
        test_regra()
        test_conversa()
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
