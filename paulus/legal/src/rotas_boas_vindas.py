"""
As rotas do assistente de configuração novo (frontend/js/23-boas-vindas.js,
o desenho "Pós-instalador" entregue em 07/10/2026) que o servidor não tinha.

  GET  /api/assinatura          a assinatura da conta Google que entrou (a do
                                vínculo, src/vinculo.py), com os dados do
                                cadastro feito no site
  POST /api/conexoes/autorizar  um consentimento só do Google para os serviços
                                marcados no passo Conexões; devolve o endereço
                                que a tela abre no navegador
  POST /api/conexoes/cancelar   desiste da espera desse consentimento
  GET  /api/conexoes            (src/api.py) ganha o que o Google já autorizou

O "Trocar de conta" do passo Assinatura é o /api/vinculo/desvincular de
sempre: o passo Conta Google volta a pedir o Google.

A assinatura. A conta da nuvem do Paulus é a da conta Google
(worker/ia.js): esta instalação fala com ela pelo segredo que o Worker dá ao
ativar (src/nuvem.py). Sem segredo ainda, e com o login do Google recente (o
id_token do passo Conta Google, que vale 1 h), a rota ativa a nuvem desta
instalação com essa conta - a mesma ativação de Configurações › Modelos; daí
em diante a conferência é pelo segredo, sem depender do login. Se esta
instalação já usa a nuvem de OUTRA conta Google, nada se troca daqui (seria
tirar a assinatura de quem usa o Paulus): só se lê a situação da conta que
entrou, pelo login recente. A exceção é a nuvem que este mesmo assistente
ativou minutos antes e a pessoa trocou de conta: aí ela passa para a de agora.

Os dados de "Seus dados" vêm do cadastro do site (GET /api/ia/cadastro, só o
da conta dona do segredo); o nome é o do Google. Só vão os campos que o
cadastro tem - o que ele não tem fica como está aqui.

Os serviços do Google. Neste Paulus, a Agenda e o Drive usam a mesma
autorização da conta de e-mail do escritório (src/correio_contas.py): sem
ela, o pedido precisa incluir o Gmail. O consentimento é incremental
(include_granted_scopes): o que já estava concedido continua. O que voltar
fica guardado nessa conta, cifrado pela DPAPI, como no login do e-mail.
"""

import threading
import time

from fastapi import HTTPException
from pydantic import BaseModel

import campos_br
import correio_oauth
import google_nuvem
import google_servicos
import nuvem

# A conferência da assinatura vale por alguns segundos: a tela pergunta a cada
# 5 s enquanto espera o site, e as rotas do site no Worker têm limite por minuto.
VALIDADE_S = 10
TEMPO_REDE = (10, 20)
MAIL = correio_oauth.ESCOPO_DO_EMAIL["google"]
# O serviço como o assistente chama (SERVICOS_BV) -> o escopo que o Google concede.
ESCOPOS_DO_ASSISTENTE = {
    "gmail": MAIL,
    "agenda": google_servicos.ESCOPOS["agenda"],
    "drive": google_servicos.ESCOPOS["drive"],
    "drive_leitura": google_servicos.ESCOPOS["drive_leitura"],
}

_cache: dict = {"quando": 0.0, "email": "", "resposta": None}
_trava = threading.Lock()
# A conta Google cuja nuvem este assistente ativou nesta execução: só ela
# troca sozinha quando a pessoa troca de conta no passo Assinatura.
_ativada_aqui: dict = {"email": ""}
# O consentimento pedido pelo passo Conexões (para cancelar só ele).
_consentimento: dict = {"entrada": None}


class Autorizar(BaseModel):
    servicos: list[str] = []
    tema: str = ""


# ------------------------------------------------------------ a assinatura

def _email_do_vinculo(estado) -> str:
    return str((estado.prefs.dados.get("vinculo") or {}).get("email") or "").strip().lower()


def esquecer() -> None:
    """A próxima pergunta confere de novo (depois de trocar de conta, por exemplo)."""
    _cache.update(quando=0.0, email="", resposta=None)


def assinatura(estado) -> dict:
    """
    {ativa, situacao: "ativa"|"vencida"|"nenhuma", email, pessoa, escritorio,
    plano, renova_em}: o formato que js/23-boas-vindas.js lê. `motivo` diz por
    que não deu para conferir, quando não deu.
    """
    email = _email_do_vinculo(estado)
    vazia = {"ativa": False, "situacao": "nenhuma", "email": email, "pessoa": {}, "escritorio": "", "plano": "", "renova_em": ""}
    if not email:
        return {**vazia, "motivo": "entre com a conta Google no passo Conta Google"}
    # Uma conferencia por vez: duas perguntas juntas (rede lenta) nao ativam a nuvem duas vezes.
    with _trava:
        agora = time.time()
        if _cache["resposta"] is not None and _cache["email"] == email and agora - _cache["quando"] < VALIDADE_S:
            return _cache["resposta"]
        try:
            resumo, cadastro, motivo = _ler(estado, email)
            resposta = {**vazia, "motivo": motivo} if resumo is None else _montar(estado, email, resumo, cadastro)
        except nuvem.ErroNuvem as exc:
            # Tambem a falha fica os segundos do cache: a tela pergunta a cada 5 s, e
            # ativar no Worker tem limite por minuto.
            resposta = _sem_resposta(estado, vazia, str(exc))
        _cache.update(quando=time.time(), email=email, resposta=resposta)
        return resposta


def _ler(estado, email: str):
    """(o resumo da conta da nuvem, o cadastro, por que não deu) desta conta Google. ErroNuvem sem rede."""
    vinculo = getattr(estado, "vinculo", None)
    token = vinculo.id_token_valido() if vinculo is not None else ""
    if nuvem.chave(estado, "paulus"):
        r = nuvem.conta_paulus(estado, forcar=True) or {}
        dono = str(r.get("email") or "").strip().lower()
        if dono == email:
            return r, _cadastro_pela_chave(estado), ""
        if not token:
            return None, None, (f"este computador usa a nuvem do Paulus de {dono or 'outra conta Google'}; "
                                f"para conferir a de {email}, entre de novo com o Google")
        if not (dono and _ativada_aqui["email"] == dono):
            # Ativada antes, por outra conta (ou de conta que nao se sabe): nao se troca daqui. So se le a situacao desta.
            r = _pelo_google(estado, token)
            return r, r.get("cadastro"), ""
        # Ativada por este assistente minutos antes, e a pessoa trocou de conta: passa para a de agora.
        nuvem.sair_paulus(estado)
    elif not token:
        return None, None, "entre de novo com o Google no passo Conta Google para conferir a assinatura"
    import segredos

    if not segredos.disponivel():
        # Sem como guardar o segredo cifrado: so se le, pela conta Google.
        r = _pelo_google(estado, token)
        return r, r.get("cadastro"), ""
    r = nuvem.ativar_paulus(estado, token, _nome_do_escritorio(estado)) or {}
    _ativada_aqui["email"] = email
    return r, _cadastro_pela_chave(estado), ""


def _pelo_google(estado, token: str) -> dict:
    """A situação da conta pelo login recente (as rotas do site no Worker; elas trazem o cadastro)."""
    return nuvem._paulus(estado, "POST", "/api/ia/site/situacao", {"id_token": token}, segredo="-", timeout=TEMPO_REDE) or {}


def _cadastro_pela_chave(estado) -> dict | None:
    """O cadastro do site da conta dona do segredo desta instalação (None sem ele, ou com o Worker antigo)."""
    try:
        d = nuvem._paulus(estado, "GET", "/api/ia/cadastro", timeout=TEMPO_REDE)
    except nuvem.ErroNuvem:
        return None
    c = d.get("cadastro") if isinstance(d, dict) else None
    return c if isinstance(c, dict) else None


def _nome_do_escritorio(estado) -> str:
    return str((estado.prefs.dados.get("escritorio") or {}).get("nome") or "").strip()


def _sem_resposta(estado, vazia: dict, motivo: str) -> dict:
    """Sem falar com paulus.ia.br: com a nuvem já ativada aqui, vale o último plano conhecido (src/plano.py)."""
    guardado = dict(estado.prefs.dados.get("plano") or {})
    ate = str(guardado.get("ate") or "")
    try:
        from datetime import datetime, timezone

        fim = datetime.fromisoformat(ate.replace("Z", "+00:00"))
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        vale = bool(guardado.get("ativo")) and fim > datetime.now(timezone.utc)
    except ValueError:
        vale = False
    if vale and nuvem.chave(estado, "paulus"):
        return {**vazia, "ativa": True, "situacao": "ativa", "plano": str(guardado.get("nome") or ""), "fonte": "guardado",
                "motivo": motivo}
    return {**vazia, "motivo": motivo}


def _montar(estado, email: str, r: dict, cadastro) -> dict:
    vigente = bool(r.get("plano_vigente"))
    # Venceu: já teve um ciclo pago (ou o ano, ou o mês avulso). Sem nenhum, ainda não assinou.
    teve = bool(r.get("ciclo") or r.get("pago_ate"))
    a = r.get("assinatura") or {}
    renova = ""
    # "renova em" só quando renova mesmo: a mensal no cartão, autorizada. O ano e o mês avulso
    # pagos de uma vez não renovam sozinhos, nem a cortesia.
    if vigente and not r.get("cortesia") and a.get("situacao") == "authorized" and (r.get("periodo") or "mensal") == "mensal":
        renova = str((r.get("ciclo") or {}).get("fim") or "")[:10]
    cad = cadastro if isinstance(cadastro, dict) else {}
    return {
        "ativa": vigente,
        "situacao": "ativa" if vigente else ("vencida" if teve else "nenhuma"),
        "email": email,
        "pessoa": _pessoa(estado, email, cad),
        "escritorio": str(cad.get("nome_escritorio") or ""),
        "plano": str((r.get("plano") or {}).get("nome") or "") if vigente else "",
        "renova_em": renova,
        "cortesia": bool(r.get("cortesia")),
    }


def _pessoa(estado, email: str, cad: dict) -> dict:
    """Só o que se sabe: a tela junta com o que já há aqui, e um campo vazio apagaria o daqui."""
    p = {"email": email}
    nome = str((estado.prefs.dados.get("vinculo") or {}).get("nome") or "").strip()
    if nome:
        p["nome"] = nome
    doc = str(cad.get("documento") or "")
    if doc and not campos_br.problema("cpf-cnpj", doc):
        p["cpf"] = campos_br.mascara("cpf-cnpj", doc)
    if cad.get("oab"):
        p["oab"] = str(cad["oab"])
    tel = str(cad.get("telefone") or "")
    if tel and not campos_br.problema("telefone", tel):
        p["telefone"] = campos_br.mascara("telefone", tel)
    endereco = _endereco(cad.get("endereco"))
    if endereco:
        p["endereco"] = endereco
    return p


def _endereco(e) -> str:
    """O endereço do cadastro numa linha: "Rua, 100, sala 2 - Bairro, Cidade - UF, CEP 00000-000"."""
    if not isinstance(e, dict) or not e.get("logradouro"):
        return ""
    texto = str(e.get("logradouro") or "") + (", " + str(e["numero"]) if e.get("numero") else "")
    if e.get("complemento"):
        texto += ", " + str(e["complemento"])
    if e.get("bairro"):
        texto += " - " + str(e["bairro"])
    cidade = str(e.get("cidade") or "") + (" - " + str(e["uf"]) if e.get("uf") else "")
    if cidade:
        texto += ", " + cidade
    cep = campos_br.so_digitos(e.get("cep"))
    if len(cep) == 8:
        texto += ", CEP " + cep[:5] + "-" + cep[5:]
    return texto


# ------------------------------------------------------------ os servicos do Google

def autorizados(estado) -> dict:
    """
    O que a conta Google do escritório deixa usar agora, por serviço do
    assistente (o Meet vem com a Agenda): concedido, com a autorização
    valendo e sem a Minha conta ter desligado (src/google_nuvem.py).
    """
    conta = estado.conta_google_do_escritorio()
    valendo = conta is not None and estado.contas.tem_credencial(conta)
    tem = set(conta.escopos.split()) if valendo else set()
    r = {s: escopo in tem and not google_nuvem.frase(estado, s, conta) for s, escopo in ESCOPOS_DO_ASSISTENTE.items()}
    r["meet"] = r["agenda"]
    entrada = _consentimento["entrada"]
    r["consentimento"] = {"fase": entrada.fase, "mensagem": entrada.mensagem} if entrada else {"fase": "nenhum", "mensagem": ""}
    return r


def autorizar(estado, servicos, tema: str, credenciais, ao_voltar, ao_ligar_agenda) -> dict:
    """Começa o consentimento e devolve o endereço do Google (quem abre é a tela)."""
    pedidos: list[str] = []
    for s in servicos or []:
        s = "agenda" if s == "meet" else str(s)
        if s in ESCOPOS_DO_ASSISTENTE and s not in pedidos:
            pedidos.append(s)
    if not pedidos:
        raise HTTPException(status_code=400, detail="marque pelo menos um serviço")
    conta = estado.conta_google_do_escritorio()
    esperado = conta.email if conta else _email_do_vinculo(estado)
    for s in pedidos:
        desligado = google_nuvem.frase(estado, s, conta)
        if desligado:
            raise HTTPException(status_code=409, detail=desligado)
    com_gmail = conta is not None and estado.contas.tem_credencial(conta) and MAIL in conta.escopos.split()
    if "gmail" not in pedidos and not com_gmail:
        raise HTTPException(status_code=409, detail=(
            "neste Paulus, a Agenda e o Drive usam a mesma autorização da conta de e-mail do escritório: marque também o "
            "Gmail (o Paulus só abre a caixa quando você pedir)"))
    escopos = "openid email " + " ".join(sorted({ESCOPOS_DO_ASSISTENTE[s] for s in pedidos}))

    def concluir(provedor: str, tokens: dict, email: str, nome: str) -> dict:
        if esperado and email.lower() != esperado.lower():
            raise correio_oauth.ErroOAuth(f"o Google entrou com {email}, mas a conta deste Paulus é {esperado}: entre com a mesma conta")
        estado.contas.ligar_oauth(provedor, email, nome, tokens, dono=0)
        concedidos = set(str(tokens.get("scope") or "").split())
        agenda = "agenda" in pedidos and ESCOPOS_DO_ASSISTENTE["agenda"] in concedidos
        novo = {"conta": email}
        if agenda:
            # Como em Conexões: a Agenda conectada sincroniza e mostra os eventos de lá.
            novo.update(agenda_sincronizar=True, agenda_mostrar=True)
        estado.prefs.atualizar({"google": novo})
        if agenda and ao_ligar_agenda:
            ao_ligar_agenda()
        return {"conta": email, "servicos": [s for s in pedidos if ESCOPOS_DO_ASSISTENTE[s] in concedidos]}

    anterior = estado.entrada_oauth
    if anterior and not anterior.terminou:
        anterior.cancelar()
    try:
        entrada = correio_oauth.Entrada("google", credenciais("google"), concluir, login_hint=esperado, escopos=escopos,
                                        tema="claro" if tema == "claro" else "escuro", ao_voltar=ao_voltar,
                                        # Quem abre o navegador é a tela (window.open com o endereço devolvido).
                                        abrir=lambda url: False,
                                        # Os endereços do Google trocados nos testes (os mesmos da renovação).
                                        endpoints=dict((getattr(estado.contas, "endpoints_oauth", None) or {}).get("google") or {}))
    except correio_oauth.ErroOAuth as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    estado.entrada_oauth = entrada
    _consentimento["entrada"] = entrada
    try:
        andamento = entrada.iniciar()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir a porta local para o login: {exc}") from exc
    return {"url": andamento.get("url", ""), "fase": andamento.get("fase", ""), "servicos": pedidos, "conta": esperado}


def cancelar() -> dict:
    """Desiste do consentimento do passo Conexões (e só dele: um login do e-mail em andamento continua)."""
    entrada = _consentimento["entrada"]
    if entrada is None:
        return {"fase": "nenhum"}
    if not entrada.terminou:
        entrada.cancelar()
    return entrada.andamento()


# ------------------------------------------------------------ as rotas

def montar(estado, app, *, credenciais, ao_voltar=None, ao_ligar_agenda=None) -> None:
    """`credenciais(provedor)`: os IDs do aplicativo (src/oauth_app.py); `ao_voltar`: traz a janela; `ao_ligar_agenda`: sincroniza."""

    @app.get("/api/assinatura")
    def assinatura_da_conta() -> dict:
        """A assinatura da conta Google que entrou (o passo Assinatura e "Seus dados" do assistente)."""
        return assinatura(estado)

    @app.post("/api/conexoes/autorizar")
    def conexoes_autorizar(payload: Autorizar) -> dict:
        """Um consentimento do Google para os serviços marcados no passo Conexões: {url} para a tela abrir."""
        return autorizar(estado, payload.servicos, payload.tema, credenciais, ao_voltar, ao_ligar_agenda)

    @app.post("/api/conexoes/cancelar")
    def conexoes_cancelar() -> dict:
        return cancelar()
