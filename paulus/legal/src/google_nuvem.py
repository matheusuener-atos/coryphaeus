"""
A ordem da Minha conta e do painel sobre o Google do escritório (07/10/2026).

O titular, em paulus.ia.br/minha-conta, e a equipe do Paulus, pelo painel,
dizem que serviços do Google o Paulus do escritório continua usando: a lista
`ligados`, com o nome curto de cada escopo (SERVICOS - os mesmos nomes da
Minha conta e do painel, worker/conta.js SERVICOS_G). A ordem fica na conta da
nuvem (worker/ia.js, `google_pendente`) até este programa cumprir e contar
que cumpriu (POST /api/ia/google, com `aplicado`).

Vale para a conta Google DO ESCRITÓRIO: a que entrou pelo Google sem ser de
ninguém da equipe (dono 0), a escolhida em Conexões ou a primeira. A conta
Google que uma pessoa da equipe conectou de fora (E3b) não muda.

O que cada ordem faz aqui:

- Serviço concedido no Google e fora da lista: este Paulus PARA DE USAR -
  `google.desligados` nas preferências. O Google não revoga um escopo
  sozinho: a permissão continua concedida lá, e o que muda é que o programa
  não chama mais aquele serviço - a Agenda e o Meet, o envio ao Drive, a
  leitura do Drive (src/google_servicos.py recusa antes de sair) - nem abre
  ou envia pela caixa do Gmail dessa conta (src/api.py).
- Serviço da lista que estava desligado aqui: volta a ser usado. Serviço da
  lista que a conta nunca concedeu continua fora: conceder é na tela do
  Google, no computador do escritório - de longe não dá, e o relatório
  seguinte diz a verdade.
- Lista vazia (desvincular): a concessão inteira é revogada no Google
  (oauth2.googleapis.com/revoke, com o refresh token) e a autorização
  guardada da conta é apagada: ela pede para entrar de novo. A conta de
  e-mail continua cadastrada e nada do que já foi baixado sai daqui. Sem
  conseguir falar com o Google, este Paulus já para de usar tudo, a ordem
  fica pendente e a revogação é tentada de novo na volta seguinte.

O que vai à nuvem: só os nomes curtos dos serviços em uso - concedidos e não
desligados aqui; nenhum, se a conta precisa entrar de novo ou não existe.
Nada de e-mail, token ou outro dado. Quando:

- depois de entrar ou sair com o Google (correio_contas.Contas.ao_mudar);
- quando o programa fala com a nuvem (src/nuvem.py, conta_paulus): na hora
  se o resumo da conta traz uma ordem pendente, senão no máximo a cada
  INTERVALO_S;
- no laço do Google em segundo plano, o do Drive pela internet (a cada 15
  minutos, src/api.py), com o mesmo limite.

Só com a conta da nuvem ativada nesta instalação. Sem rede, nada quebra: o
erro fica no registro e a volta seguinte tenta de novo.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import correio_oauth
import google_servicos
import nuvem

# O nome curto de cada servico (o da Minha conta e do painel) -> o escopo
# inteiro que o Google concede e que fica em Conta.escopos.
SERVICOS = {
    "mail.google.com": correio_oauth.ESCOPO_DO_EMAIL["google"],
    "calendar.events": google_servicos.ESCOPOS["agenda"],
    "drive.file": google_servicos.ESCOPOS["drive"],
    "drive.readonly": google_servicos.ESCOPOS["drive_leitura"],
}
# O servico como o programa chama (google_tem, Conexoes) -> o nome curto.
DO_PROGRAMA = {"gmail": "mail.google.com", "agenda": "calendar.events", "drive": "drive.file", "drive_leitura": "drive.readonly"}
# Como cada um aparece na frase, com o genero de "desligado".
TEXTOS = {
    "mail.google.com": ("o Gmail", "desligado"),
    "calendar.events": ("a Agenda do Google (e o Meet)", "desligada"),
    "drive.file": ("o envio ao Google Drive", "desligado"),
    "drive.readonly": ("a leitura do Google Drive", "desligada"),
}
# Quem deu a ordem (`por`, gravado pelo Worker).
POR = {"Minha conta": "pela Minha conta do Paulus", "painel": "pela equipe do Paulus"}
ROTULOS = {"Minha conta": "desligado na Minha conta", "painel": "desligado pela equipe do Paulus"}
ONDE_LIGAR = "na Minha conta (paulus.ia.br/minha-conta)"
CAMINHO = "/api/ia/google"
# No maximo uma volta a cada 10 minutos (salvo login novo ou ordem pendente).
INTERVALO_S = 600
# Depois de uma volta que falhou (sem internet), a proxima espera isto.
ESPERA_DEPOIS_DE_FALHA_S = 120
# A ordem pendente vista na conta faz uma volta na hora, mas nao mais que uma por minuto.
ESPERA_ENTRE_FORCADAS_S = 60
TEMPO_REDE = (10, 20)

_log = logging.getLogger("paulus.google_nuvem")
_trava = threading.Lock()
_mem: dict = {"relatado": 0.0, "tentado": 0.0, "de_novo": False}


# ------------------------------------------------------------ a conta e os servicos

def conta_do_escritorio(estado):
    """
    A conta Google do escritorio: entrou pelo Google e nao e de ninguem da
    equipe (dono 0); a escolhida em Conexoes (prefs google.conta) ou a
    primeira. E dela que a nuvem sabe, e e nela que a ordem vale.
    """
    preferida = str((estado.prefs.dados.get("google") or {}).get("conta", "")).lower()
    contas = [c for c in estado.contas.itens if c.autenticacao == "google" and not int(c.dono or 0)]
    return next((c for c in contas if c.email.lower() == preferida), contas[0] if contas else None)


def _do_escritorio(conta) -> bool:
    return getattr(conta, "autenticacao", "") == "google" and not int(getattr(conta, "dono", 0) or 0)


def curto(servico: str) -> str:
    """"agenda" (o programa) ou "calendar.events" (a nuvem) -> "calendar.events"; "" se nao e um dos quatro."""
    s = str(servico or "")
    return s if s in SERVICOS else DO_PROGRAMA.get(s, "")


def concedidos(conta) -> set[str]:
    """Os servicos que o Google concedeu a conta (o que ficou guardado no login), pelo nome curto."""
    if conta is None:
        return set()
    tem = set(str(getattr(conta, "escopos", "") or "").split())
    return {c for c, escopo in SERVICOS.items() if escopo in tem}


def _g(estado) -> dict:
    return dict(estado.prefs.dados.get("google") or {})


def desligados(estado, conta) -> set[str]:
    """Os servicos que a ordem desligou NESTA conta (so a conta do escritorio que recebeu a ordem)."""
    if conta is None or not _do_escritorio(conta):
        return set()
    g = _g(estado)
    if str((g.get("ordem") or {}).get("conta") or "").lower() != str(conta.email or "").lower():
        return set()
    return {s for s in (g.get("desligados") or []) if s in SERVICOS}


def _por(ordem: dict) -> str:
    return POR.get(str(ordem.get("por") or ""), "em paulus.ia.br")


def _em(ordem: dict) -> str:
    q = str(ordem.get("quando") or "")
    try:
        return " em " + datetime.fromisoformat(q.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y")
    except ValueError:
        return ""


def rotulo(estado) -> str:
    """A etiqueta curta da tela ("desligado na Minha conta")."""
    return ROTULOS.get(str((_g(estado).get("ordem") or {}).get("por") or ""), "desligado em paulus.ia.br")


def frase(estado, servico: str, conta) -> str:
    """
    Por que o servico desta conta nao e usado - a frase vai para a tela e para
    o erro de quem tentou usar. "" quando ele nao foi desligado de longe.
    """
    c = curto(servico)
    if not c or c not in desligados(estado, conta):
        return ""
    nome, genero = TEXTOS[c]
    ordem = _g(estado).get("ordem") or {}
    return (f"{nome} foi {genero} {_por(ordem)}{_em(ordem)}: este Paulus não usa mais esse serviço da conta "
            f"{conta.email}; para voltar a usar, ligue de novo {ONDE_LIGAR}")


def em_uso(estado) -> list[str]:
    """O que vai a nuvem: os servicos concedidos e nao desligados aqui; nenhum sem a autorizacao valendo."""
    conta = conta_do_escritorio(estado)
    if conta is None or not estado.contas.tem_credencial(conta):
        return []
    return sorted(concedidos(conta) - desligados(estado, conta))


def para_tela(estado, conta) -> dict:
    """
    O que Conexoes mostra da ordem: os servicos desligados de longe (com a
    frase de cada um), a etiqueta curta, o aviso honesto sobre a permissao que
    continua no Google e, depois de desvincular, o que aconteceu.
    """
    if conta is None or not _do_escritorio(conta):
        return {}
    ordem = _g(estado).get("ordem") or {}
    desl = desligados(estado, conta)
    servicos = {k: frase(estado, k, conta) for k, c in DO_PROGRAMA.items() if c in desl}
    desvinculo = None
    if ordem.get("id") and not ordem.get("ligados") and str(ordem.get("conta") or "").lower() == conta.email.lower():
        if not ordem.get("cumprida"):
            desvinculo = {"cumprida": False, "frase": (
                f"a conta Google foi desvinculada {_por(ordem)}{_em(ordem)}: este Paulus parou de usá-la, mas a revogação "
                "no Google ainda não foi confirmada (sem internet?) e é tentada de novo")}
        elif conta.precisa_entrar:
            desvinculo = {"cumprida": True, "frase": (
                f"a conta Google foi desvinculada {_por(ordem)}{_em(ordem)}: o acesso foi revogado no Google; para voltar "
                "a usar, entre de novo com o Google em E-mail › Contas")}
    aviso = ""
    if servicos:
        nomes = [TEXTOS[DO_PROGRAMA[k]][0] for k in servicos]
        lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        aviso = (f"Desligado {_por(ordem)}{_em(ordem)}: este Paulus não usa mais {lista}. A permissão continua concedida "
                 "no Google - o Google não revoga um serviço sozinho; para tirá-la de lá, desvincule a conta na Minha conta "
                 f"ou use myaccount.google.com/permissions. Para voltar a usar, ligue de novo {ONDE_LIGAR}.")
    return {"servicos": servicos, "rotulo": rotulo(estado), "aviso": aviso, "desvinculo": desvinculo}


def linha_da_conta(estado, conta) -> str:
    """A linha curta da conta em E-mail › Contas, quando a ordem mexeu nela ("" quando nao mexeu)."""
    if conta is None or not _do_escritorio(conta):
        return ""
    if frase(estado, "gmail", conta):
        return "Gmail " + rotulo(estado)
    d = para_tela(estado, conta).get("desvinculo")
    if d and d.get("cumprida"):
        return "Desvinculada " + _por(_g(estado).get("ordem") or {}) + " · entre de novo"
    return ""


# ------------------------------------------------------------ cumprir a ordem

def _gravar(estado, **campos) -> None:
    estado.prefs.atualizar({"google": campos})


def cumprir(estado, ordem: dict) -> bool:
    """
    Faz aqui o que a ordem pede (o docstring do modulo diz o que). True: a
    ordem esta cumprida e pode ir como `aplicado`; False: falta a revogacao
    no Google, e a volta seguinte tenta de novo.
    """
    ligados = sorted({s for s in (ordem.get("ligados") or []) if s in SERVICOS})
    conta = conta_do_escritorio(estado)
    registro = {"id": str(ordem.get("id") or "")[:40], "por": str(ordem.get("por") or "")[:40],
                "quando": str(ordem.get("quando") or "")[:40], "conta": conta.email if conta else "",
                "ligados": ligados, "cumprida": ""}
    agora = datetime.now().isoformat(timespec="seconds")
    if not ligados and conta is not None:
        # Desvincular: este Paulus para de usar tudo ja; a autorizacao guardada
        # so sai quando o Google confirmar a revogacao (senao ela se perderia
        # e nao daria mais para revogar daqui).
        _gravar(estado, desligados=sorted(SERVICOS), ordem=registro)
        if not _revogar(estado, conta, registro):
            return False
        _gravar(estado, desligados=[], ordem={**registro, "cumprida": agora})
        return True
    # So o que a conta concedeu e ficou fora da lista. O resto ja nao e usado.
    novos = sorted(concedidos(conta) - set(ligados))
    _gravar(estado, desligados=novos, ordem={**registro, "cumprida": agora})
    return True


def _revogar(estado, conta, registro: dict) -> bool:
    """Revoga a concessao no Google e apaga a autorizacao guardada. False: o Google nao confirmou."""
    token = estado.contas.token_para_revogar(conta)
    if token:
        endpoint = (estado.contas.endpoints_oauth.get(conta.autenticacao) or {}).get("revogar", "")
        try:
            correio_oauth.revogar(conta.autenticacao, token, endpoint=endpoint)
        except correio_oauth.ErroOAuth as exc:
            _log.info("a revogacao no Google fica para a proxima volta: %s", exc)
            return False
    estado.contas.esquecer_login(conta, motivo=(
        f"desvinculada {_por(registro)}{_em(registro)}: o acesso ao Google foi revogado; "
        "para voltar a usar, entre de novo com o Google"))
    return True


# ------------------------------------------------------------ contar a nuvem

def relatar(estado, aplicado: str = "") -> dict | None:
    """Conta a nuvem o que esta em uso (e a ordem cumprida); devolve a ordem pendente ou None. ErroNuvem sem rede."""
    corpo: dict = {"escopos": em_uso(estado)}
    if aplicado:
        corpo["aplicado"] = aplicado
    d = nuvem._paulus(estado, "POST", CAMINHO, corpo, timeout=TEMPO_REDE)
    p = d.get("pendente") if isinstance(d, dict) else None
    return p if isinstance(p, dict) and p.get("id") else None


def _tem_conta_da_nuvem(estado) -> bool:
    try:
        return bool(nuvem.chave(estado, "paulus"))
    except Exception:  # noqa: BLE001 - sem a pasta da nuvem: como se nao houvesse conta
        return False


def conferir(estado, forcar: bool = False) -> dict:
    """
    Uma volta: conta a nuvem, cumpre a ordem que vier e conta que cumpriu.
    Nunca levanta. Sem a conta da nuvem, ou dentro do intervalo (sem
    `forcar`), ou com outra volta andando, nao faz nada e devolve {}.
    """
    if not _tem_conta_da_nuvem(estado):
        return {}
    if not forcar and time.time() - _mem["relatado"] < INTERVALO_S:
        return {}
    if not _trava.acquire(blocking=False):
        if forcar:
            _mem["de_novo"] = True
        return {}
    try:
        resultado: dict = {}
        for _ in range(3):
            _mem["de_novo"] = False
            resultado = _uma_volta(estado)
            if not _mem["de_novo"]:
                break
        return resultado
    finally:
        _trava.release()


def _uma_volta(estado) -> dict:
    _mem["tentado"] = time.time()
    try:
        ordem = relatar(estado)
        cumprida = False
        if ordem:
            cumprida = cumprir(estado, ordem)
            # O que mudou aqui vai na hora - com o id, se a ordem foi cumprida;
            # sem ele, a nuvem continua mostrando a ordem como pendente.
            outra = relatar(estado, aplicado=str(ordem["id"]) if cumprida else "")
            # Uma ordem nova chegou enquanto esta era cumprida: mais uma volta.
            if cumprida and outra and outra.get("id") != ordem["id"]:
                _mem["de_novo"] = True
        _mem["relatado"] = time.time()
        return {"escopos": em_uso(estado), "ordem": str(ordem["id"]) if ordem else "", "cumprida": cumprida}
    except nuvem.ErroNuvem as exc:
        _log.info("o Google do escritorio nao foi contado a nuvem agora: %s", exc)
        erro = str(exc)
    except Exception as exc:  # noqa: BLE001 - nada aqui pode derrubar quem chamou
        _log.warning("a ordem do Google falhou: %s", exc, exc_info=True)
        erro = str(exc)
    _mem["relatado"] = time.time() - INTERVALO_S + ESPERA_DEPOIS_DE_FALHA_S
    return {"erro": erro}


def pedir(estado, forcar: bool = False) -> None:
    """Uma volta em segundo plano, sem prender quem pediu (uma por vez)."""
    if not _tem_conta_da_nuvem(estado):
        return
    if _trava.locked():
        if forcar:
            _mem["de_novo"] = True
        return
    threading.Thread(target=conferir, args=(estado, forcar), name="google-nuvem", daemon=True).start()


def depois_da_conta(estado, dados) -> None:
    """
    src/nuvem.py, a cada leitura da conta no Worker: a ordem pendente que vem
    no resumo vai na hora (uma volta por minuto, no maximo); sem ordem, conta
    o que usa no maximo a cada INTERVALO_S.
    """
    pendente = dados.get("google_pendente") if isinstance(dados, dict) else None
    agora = time.time()
    if isinstance(pendente, dict) and pendente.get("id") and agora - _mem["tentado"] >= ESPERA_ENTRE_FORCADAS_S:
        pedir(estado, forcar=True)
    elif agora - _mem["relatado"] >= INTERVALO_S:
        pedir(estado)


def ao_mudar_login(estado, conta) -> None:
    """correio_contas.Contas.ao_mudar: entrou, saiu ou venceu o login de uma conta do escritorio."""
    if conta is None or _do_escritorio(conta):
        pedir(estado, forcar=True)


def montar(estado) -> None:
    """Liga os avisos: o login que muda e cada leitura da conta na nuvem."""
    estado.contas.ao_mudar = lambda conta: ao_mudar_login(estado, conta)
    if depois_da_conta not in nuvem.AO_LER_CONTA:
        nuvem.AO_LER_CONTA.append(depois_da_conta)
