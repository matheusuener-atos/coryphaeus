"""
A nuvem segue a conta (regra de 12/10/2026): o plano é da Conta Atos, não do
computador. A cada login com token, se a nuvem desta instalação está em outra
conta (ou em nenhuma), ela é ativada de novo com a conta que entrou.

Sem rede: as chamadas ao Worker são trocadas por funções daqui.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import nuvem  # noqa: E402
import segredos  # noqa: E402

_falhas: list[str] = []


def checar(cond: bool, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHA ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Prefs:
    def __init__(self, dados: dict) -> None:
        self.dados = dados


class Estado:
    def __init__(self, email: str, provedor: str = "paulus") -> None:
        self.prefs = Prefs({"vinculo": {"email": email}, "nuvem": {"provedor": provedor}})


def rodar(estado, *, tem_chave: bool, conta_email: str = "", sem_internet: bool = False) -> list[str]:
    """Devolve as ativações feitas, com as funções de rede trocadas e restauradas no fim."""
    feitas: list[str] = []
    antes = (nuvem.chave, nuvem.conta_paulus, nuvem.ativar_paulus, segredos.disponivel)

    def conta(_e, forcar=False):
        if sem_internet:
            raise nuvem.ErroNuvem("não consegui falar com paulus.ia.br agora (sem internet?)")
        return {"email": conta_email}

    try:
        nuvem.chave = lambda _e, _p: "pia_x" if tem_chave else ""
        nuvem.conta_paulus = conta
        nuvem.ativar_paulus = lambda _e, token, nome="": feitas.append(token)
        segredos.disponivel = lambda: True
        nuvem.seguir_conta_de_entrada(estado, "token-da-atos", "Escritório")
    finally:
        nuvem.chave, nuvem.conta_paulus, nuvem.ativar_paulus, segredos.disponivel = antes
    return feitas


def main() -> int:
    print("\na nuvem segue a conta de entrada")
    e = Estado("master@atos.dev.br")
    checar(rodar(e, tem_chave=True, conta_email="matheusueners@hotmail.com") == ["token-da-atos"],
           "nuvem em outra conta: passa para a conta que entrou")
    checar(rodar(e, tem_chave=True, conta_email="Master@atos.dev.br") == [],
           "já na conta de entrada (maiúsculas não contam): não ativa de novo")
    checar(rodar(e, tem_chave=False) == ["token-da-atos"], "sem nuvem ativada: ativa com a conta que entrou")
    checar(rodar(e, tem_chave=True, sem_internet=True) == [], "sem internet: não troca nada, confere no próximo login")
    checar(rodar(Estado("master@atos.dev.br", provedor="deepinfra"), tem_chave=True, conta_email="outro@x.com") == [],
           "chave própria do escritório: não é de conta nenhuma, fica como está")
    checar(rodar(Estado(""), tem_chave=True, conta_email="outro@x.com") == [], "sem conta de entrada: nada muda")

    print("\nao abrir: nuvem em outra conta pede o login uma vez")
    antes = (nuvem.chave, nuvem.conta_paulus)
    try:
        nuvem.chave = lambda _e, _p: "pia_x"
        nuvem.conta_paulus = lambda _e, forcar=False: {"email": "matheusueners@hotmail.com"}
        checar(nuvem.nuvem_em_outra_conta(Estado("master@atos.dev.br")), "a nuvem na conta do hotmail e a entrada na master: em outra conta")
        nuvem.conta_paulus = lambda _e, forcar=False: {"email": "master@atos.dev.br"}
        checar(not nuvem.nuvem_em_outra_conta(Estado("master@atos.dev.br")), "na mesma conta: não pede nada")

        def sem_rede(_e, forcar=False):
            raise nuvem.ErroNuvem("sem internet")

        nuvem.conta_paulus = sem_rede
        checar(not nuvem.nuvem_em_outra_conta(Estado("master@atos.dev.br")), "sem internet: não pede login por isso")
    finally:
        nuvem.chave, nuvem.conta_paulus = antes

    import vinculo

    class PrefsVinc:
        def __init__(self):
            self.dados = {"vinculo": {"email": "master@atos.dev.br", "manter_aberto": True}}

        def atualizar(self, novo):
            self.dados.setdefault("vinculo", {}).update(novo.get("vinculo", {}))

    v = vinculo.Vinculo.__new__(vinculo.Vinculo)
    v.prefs, v.destravado, v.pedir_entrada = PrefsVinc(), False, False
    v.dados = lambda: v.prefs.dados["vinculo"]
    checar(not v.travado(), "com 'manter aberto', abre direto")
    v.pedir_entrada = True
    checar(v.travado(), "com a nuvem em outra conta, pede o login mesmo com 'manter aberto'")
    v.destravado = True
    checar(not v.travado(), "e depois de entrar, abre")

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
