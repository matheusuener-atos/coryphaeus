"""
A nuvem com a chave do escritório (docs/PLANO-PILOTO.md, N15; o estudo é
docs/estrategia-ia-nuvem.md, de 27/09/2026).

A primeira volta deixou de fora de propósito; o dono decidiu fazer, do jeito
que o estudo recomenda:

- **A chave de API do próprio escritório** (Anthropic ou OpenAI, direto), paga
  por ele, guardada cifrada pela DPAPI do Windows. Nunca o login da assinatura
  de consumidor (ChatGPT Plus, Claude Pro): os termos dos dois proíbem.
- **Desligada de fábrica**, e só na janela do escritório.
- **Só a resposta da conversa sobre os documentos**: a pergunta e os trechos
  que a busca achou (os mesmos que iriam ao modelo local). O juiz, as regras,
  a busca e a conferência continuam neste computador; o texto que volta passa
  pelas mesmas conferências do local (I8, a cerca).
- **Cada envio espera o sim** em Aprovações, com o texto exato que sai, o
  provedor, o modelo e o tamanho. Dá para liberar uma conversa inteira, ou -
  pela regra de alçada "Mandar à nuvem sem pedir a cada pergunta" - todas.
- **Nunca sai**: o que veio do e-mail (os anexos guardados por esta versão em
  diante, marcados), a cópia das pastas do Drive que o PAULUS faz (dado das
  APIs do Google) e o caso "só no escritório". Cadastros, financeiro e agenda
  nem entram na pergunta.
- **Mascarar** (ligado de fábrica): CPF, CNPJ, número de processo, e-mail e
  telefone viram "[CPF 1]"... antes de sair e voltam na resposta. Reduz a
  exposição - não anonimiza: o nome, o endereço e o resto do texto vão como
  estão.
- **O registro**: cada envio fica anotado, com o texto que saiu, em
  `<dados>/nuvem/`, e na auditoria.

**A nuvem vendida** (docs/PLANO-NUVEM.md, V1-V7, 01/10/2026): o provedor
"paulus" é o portão do Worker de paulus.ia.br (worker/ia.js), que chama o
DeepInfra com a chave do PAULUS e conta os tokens do plano do escritório. A
chave desta instalação é o segredo que o Worker deu ao ativar (com o Google),
guardado pela DPAPI como as outras. O DeepInfra também entra com a chave do
próprio escritório, como a Anthropic e a OpenAI.

- **Consentimento uma vez**, pelo titular, na janela do escritório: o termo
  tem versão (`TERMO_VERSAO`); sem o sim da versão de agora, a nuvem não liga.
  Para o "paulus", o sim também vai ao Worker, que recusa sem ele. Dado o
  sim, a pergunta vai sem pedir; pedir a cada envio (o jeito da N15) é opção.
- **De fora também**: com o sim do titular, quem entra pelo acesso de fora
  usa a nuvem como a janela. As mesmas exclusões valem.
- **Alcance por funcionalidade** (`tarefas`): conversa, resumos (serviços e
  gravações) e redação (editor, comentário, fórmula, comparar com o padrão).
  Fica sempre aqui: o e-mail (inclusive a reescrita), o juiz, a leitura do
  Acervo e o parecer do Financeiro. `ClienteNuvem` é o cliente dessas tarefas.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from urllib.parse import unquote
from datetime import datetime
from pathlib import Path

from versao import VERSAO

SITE = os.environ.get("PAULUS_SITE", "https://paulus.ia.br").rstrip("/")
PROVEDORES = {
    "paulus": {"nome": "Paulus (nuvem)", "padrao": "meta-llama/Llama-3.3-70B-Instruct", "formato": "openai",
               "modelos": SITE + "/api/ia/modelos", "url": SITE + "/api/ia/v1/chat/completions", "assinatura": True},
    "deepinfra": {"nome": "DeepInfra (chave do escritório)", "padrao": "meta-llama/Llama-3.3-70B-Instruct", "formato": "openai",
                  "modelos": "https://api.deepinfra.com/v1/openai/models",
                  "url": "https://api.deepinfra.com/v1/openai/chat/completions"},
    "anthropic": {"nome": "Anthropic (Claude)", "padrao": "claude-sonnet-5-5", "formato": "anthropic",
                  "modelos": "https://api.anthropic.com/v1/models", "url": "https://api.anthropic.com/v1/messages"},
    "openai": {"nome": "OpenAI (GPT)", "padrao": "", "formato": "openai",
               "modelos": "https://api.openai.com/v1/models", "url": "https://api.openai.com/v1/chat/completions"},
}
# As funcionalidades que podem ir à nuvem, com a chave de cada uma.
TAREFAS = {"conversa": "Perguntas sobre documentos", "resumos": "Resumos de serviços e gravações",
           "redacao": "Redação no editor, comentário e fórmula"}
ESPERA_S = 600
MAX_TOKENS = 2000
# Os testes trocam a chamada à internet aqui: (método, url, cabeçalhos, corpo, stream) -> resposta tipo requests.
PEDIR: dict = {"fn": None}
_ESPERANDO: dict[str, "Envio"] = {}
_trava = threading.Lock()
_log = logging.getLogger("paulus.nuvem")


class ErroNuvem(RuntimeError):
    """A nuvem não respondeu; a frase vai para a tela. `motivo`: "cota", "sem_plano", "consentimento"..."""

    def __init__(self, mensagem: str, motivo: str = "") -> None:
        super().__init__(mensagem)
        self.motivo = motivo


# ------------------------------------------------------------ a chave

def _pasta(estado) -> Path:
    return Path(estado.dados_dir) / "nuvem"


def _arquivo_da_chave(estado, provedor: str) -> Path:
    return _pasta(estado) / f"chave-{provedor}.dpapi"


def guardar_chave(estado, provedor: str, chave: str) -> None:
    import segredos

    if provedor not in PROVEDORES:
        raise ValueError("provedor desconhecido")
    chave = str(chave or "").strip()
    if len(chave) < 20:
        raise ValueError("essa chave é curta demais para ser uma chave de API")
    if not segredos.disponivel():
        raise ValueError("este Windows não guarda segredo cifrado (DPAPI): a chave não é guardada")
    arq = _arquivo_da_chave(estado, provedor)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(segredos.proteger(chave), encoding="utf-8")


def chave(estado, provedor: str) -> str:
    import segredos

    arq = _arquivo_da_chave(estado, provedor)
    if not arq.exists():
        return ""
    try:
        return segredos.revelar(arq.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - chave de outra conta do Windows: como se não houvesse
        return ""


def apagar_chave(estado, provedor: str) -> None:
    arq = _arquivo_da_chave(estado, provedor)
    if arq.exists():
        arq.unlink()


def config(estado) -> dict:
    return dict(estado.prefs.dados.get("nuvem") or {})


def ligada(estado) -> bool:
    c = config(estado)
    return bool(c.get("ligado") and c.get("provedor") in PROVEDORES and c.get("modelo") and chave(estado, c["provedor"])
                and consentido(estado))


def usa(estado, tarefa: str) -> bool:
    """A nuvem está ligada e esta funcionalidade vai a ela."""
    return tarefa in TAREFAS and bool((config(estado).get("tarefas") or {}).get(tarefa, True)) and ligada(estado)


# ------------------------------------------------------------ o consentimento

# 03/10/2026: cada plano tem o seu provedor (DeepInfra, Mistral AI, Anthropic):
# o sim dado ao termo de antes, que so falava do DeepInfra, e pedido de novo.
TERMO_VERSAO = "2026-10-03"


def termo(provedor: str) -> list[str]:
    """O texto que o titular lê antes do sim. Cada frase tem código que a garante (tests/test_v_nuvem.py)."""
    if provedor == "paulus":
        para_onde = ("Para onde: para o portão do Paulus em paulus.ia.br (Cloudflare), que repassa à empresa que roda o modelo "
                     "do plano: o DeepInfra (Estados Unidos) no Advogado, a Mistral AI (França) no Escritório e a Anthropic "
                     "(Estados Unidos) no Escritório Plus. É transferência internacional de dados pessoais (LGPD, art. 33). O "
                     "portão não guarda o texto: anota só os créditos gastos, as datas, o modelo e o plano.")
        politica = ("As políticas publicadas dizem: o DeepInfra não grava em disco nem registra o conteúdo que recebe pela API; a Mistral "
                    "e a Anthropic guardam a entrada e a saída da API por até 30 dias (para conferir abuso, e no que a lei "
                    "pedir) e apagam depois; nenhum dos três usa esse conteúdo para treinar modelos. Isso é a política de cada "
                    "provedor, e não isolamento técnico: os servidores são compartilhados com outros clientes deles.")
        custo = ("O que sai gasta os créditos do plano do escritório (por semana, com a cota do mês); quando acabam, as "
                 "respostas voltam a ser escritas neste computador.")
    else:
        nome = PROVEDORES.get(provedor, {}).get("nome", provedor)
        para_onde = (f"Para onde: direto para a {nome}, com a chave de API do escritório. É transferência internacional de "
                     "dados pessoais (LGPD, art. 33), e o contrato é do escritório com esse provedor.")
        politica = "O que o provedor guarda, por quanto tempo e se treina com o texto é o que os termos da conta de API dele dizem: leia antes."
        custo = "O que sai é cobrado pelo provedor, na conta do escritório."
    return [
        "O que vai: na conversa, a pergunta e os trechos dos documentos que a busca achou; nos resumos, o texto do serviço "
        "ou da gravação; na redação, o texto que você pediu para a IA trabalhar. Só das funcionalidades ligadas abaixo.",
        para_onde,
        politica,
        "Nunca vai: o que veio do e-mail (os anexos guardados desta versão em diante e a reescrita de e-mail), a cópia das "
        "pastas do Drive feita pelo Paulus, o caso marcado só no escritório, o parecer do Financeiro, o juiz e a leitura do Acervo.",
        "Mascarar (ligado de fábrica): CPF, CNPJ, número de processo, e-mail e telefone saem como marcadores e voltam na "
        "resposta. Reduz a exposição, não anonimiza: nomes, endereços e o resto do texto vão como estão.",
        custo,
        "O escritório é o controlador dos dados dos clientes dele: cabe a ele ter a base legal e avisar o cliente do uso de IA. "
        "Cada envio fica no registro deste computador, com o texto exato que saiu.",
        "O sim pode ser retirado a qualquer momento em Configurações › Modelos: a nuvem desliga na hora.",
    ]


def consentido(estado) -> bool:
    """O sim da versão de agora, para o provedor de agora: o termo diz para onde o texto vai."""
    c = config(estado)
    sim = c.get("consentimento") or {}
    return sim.get("versao") == TERMO_VERSAO and sim.get("provedor") == (c.get("provedor") or "paulus")


def consentir(estado, quem: str) -> dict:
    """O sim do titular, com a versão do termo. Para o "paulus", vai também ao Worker (que recusa sem ele)."""
    c = config(estado)
    if c.get("provedor") == "paulus" and chave(estado, "paulus"):
        _paulus(estado, "POST", "/api/ia/consentimento", {"aceito": True, "versao": TERMO_VERSAO, "quem": quem})
    registro = {"versao": TERMO_VERSAO, "quem": quem, "quando": datetime.now().isoformat(timespec="seconds"),
                "provedor": c.get("provedor") or ""}
    estado.prefs.atualizar({"nuvem": {"consentimento": registro}})
    _historico_do_sim(estado, dict(registro, acao="sim"))
    return registro


def retirar(estado, quem: str) -> None:
    if chave(estado, "paulus"):
        try:
            _paulus(estado, "POST", "/api/ia/consentimento", {"aceito": False})
        except ErroNuvem:
            pass  # sem internet agora: aqui já desliga, e o Worker sem o sim do app não importa
    # As preferencias se fundem (config._fundir): {} nao apagaria o sim; a versao vazia apaga.
    estado.prefs.atualizar({"nuvem": {"consentimento": {"versao": "", "quem": "", "quando": "", "provedor": ""}, "ligado": False}})
    _historico_do_sim(estado, {"acao": "retirado", "quem": quem, "quando": datetime.now().isoformat(timespec="seconds")})


def _historico_do_sim(estado, linha: dict) -> None:
    arq = _pasta(estado) / "consentimentos.jsonl"
    arq.parent.mkdir(parents=True, exist_ok=True)
    with arq.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


# ------------------------------------------------------------ o PAULUS (nuvem)

_CONTA_CACHE: dict = {"quando": 0.0, "dados": None}
# Quem quer saber de cada leitura da conta no Worker: (estado, dados) -> nada.
# O api.py liga a ordem do Google do escritorio (src/google_nuvem.py), que vem
# no mesmo resumo (`google_pendente`). Um erro aqui nao muda a leitura.
AO_LER_CONTA: list = []


def _paulus(estado, metodo: str, caminho: str, corpo: dict | None = None, segredo: str = "",
            timeout=None) -> dict:
    """
    Uma chamada ao Worker com o segredo desta instalação. Levanta ErroNuvem com
    a frase do Worker. `timeout` (segundos, ou (conexão, leitura)) troca o de
    sempre - o da conversa espera a resposta inteira do modelo.
    """
    # segredo="-": a chamada que ainda não tem segredo (ativar).
    k = "" if segredo == "-" else (segredo or chave(estado, "paulus"))
    # A versão vai só ao paulus.ia.br: é a que a Minha conta mostra na lista de instalações.
    cab = {"Content-Type": "application/json", "X-PAULUS-Versao": VERSAO}
    if k:
        cab["Authorization"] = f"Bearer {k}"
    try:
        r = _pedir(metodo, SITE + caminho, cab, corpo, False, **({"timeout": timeout} if timeout else {}))
    except Exception as exc:  # noqa: BLE001
        raise ErroNuvem("não consegui falar com paulus.ia.br agora (sem internet?)") from exc
    try:
        dados = r.json()
    except Exception:  # noqa: BLE001
        dados = {}
    if r.status_code >= 400:
        raise ErroNuvem(str((dados or {}).get("erro") or f"paulus.ia.br respondeu com erro ({r.status_code})"),
                        str((dados or {}).get("motivo") or ""))
    return dados or {}


def paulus_bytes(estado, caminho: str) -> tuple[bytes, str]:
    """
    Um arquivo do Worker (o PDF ou o XML de uma NFS-e), com o mesmo segredo
    desta instalação que a _paulus usa. Devolve (bytes, content-type).
    LookupError quando o Worker diz 404; ErroNuvem nos outros erros e sem conta.
    """
    k = chave(estado, "paulus")
    if not k:
        raise ErroNuvem("a conta da nuvem do Paulus não está ativada nesta instalação")
    try:
        r = _pedir("GET", SITE + caminho, {"Authorization": f"Bearer {k}", "X-PAULUS-Versao": VERSAO}, None, False)
    except Exception as exc:  # noqa: BLE001
        raise ErroNuvem("não consegui falar com paulus.ia.br agora (sem internet?)") from exc
    if r.status_code == 404:
        raise LookupError("esse arquivo não está em paulus.ia.br")
    if r.status_code >= 400:
        try:
            msg = str((r.json() or {}).get("erro") or "")
        except Exception:  # noqa: BLE001
            msg = ""
        raise ErroNuvem(msg or f"paulus.ia.br respondeu com erro ({r.status_code})")
    tipo = ""
    try:
        tipo = str((getattr(r, "headers", None) or {}).get("content-type") or "")
    except Exception:  # noqa: BLE001
        tipo = ""
    return bytes(r.content or b""), tipo


def instalacao_id(estado) -> str:
    """O mesmo id do acesso de fora (src/acesso/conexao.py): uma instalação, um id."""
    a = estado.prefs.dados.get("acesso_remoto") or {}
    if a.get("instalacao_id"):
        return str(a["instalacao_id"])
    novo = uuid.uuid4().hex
    estado.prefs.atualizar({"acesso_remoto": {"instalacao_id": novo}})
    return novo


def ativar_paulus(estado, id_token: str, nome: str = "") -> dict:
    """Com o login Google recente: a conta da nuvem no Worker e o segredo desta instalação, guardado cifrado."""
    import segredos

    if not segredos.disponivel():
        raise ErroNuvem("este Windows não guarda segredo cifrado (DPAPI): não dá para ativar aqui")
    d = _paulus(estado, "POST", "/api/ia/ativar", {"id_token": id_token, "instalacao_id": instalacao_id(estado),
                                                   "nome_escritorio": nome}, segredo="-")
    segredo = str(d.get("segredo") or "")
    if not segredo.startswith("pia_"):
        raise ErroNuvem("paulus.ia.br não devolveu o segredo desta instalação")
    guardar_chave(estado, "paulus", segredo)
    estado.prefs.atualizar({"nuvem": {"provedor": "paulus", "modelo": config(estado).get("modelo") if config(estado).get("provedor") == "paulus"
                                      and config(estado).get("modelo") else PROVEDORES["paulus"]["padrao"]}})
    # Quem já deu o sim nesta versão leva o sim ao Worker da conta nova.
    c = config(estado).get("consentimento") or {}
    if consentido(estado):
        _paulus(estado, "POST", "/api/ia/consentimento", {"aceito": True, "versao": TERMO_VERSAO, "quem": c.get("quem", "")})
    _CONTA_CACHE.update(quando=0.0, dados=None)
    import plano

    plano.esquecer()
    # Com a IA so na assinatura (src/plano.py), a conta ativada ja liga a
    # nuvem: a conversa, os resumos e a redacao vao a ela sem outro passo.
    if plano.cobranca_ligada():
        estado.prefs.atualizar({"nuvem": {"ligado": True}})
    return conta_paulus(estado, forcar=True)


def conta_paulus(estado, forcar: bool = False) -> dict | None:
    """O plano e os tokens, do Worker (guardado 30 s). None sem conta ativada."""
    if not chave(estado, "paulus"):
        return None
    if not forcar and _CONTA_CACHE["dados"] is not None and time.time() - _CONTA_CACHE["quando"] < 30:
        return _CONTA_CACHE["dados"]
    d = _paulus(estado, "GET", "/api/ia/conta")
    _CONTA_CACHE.update(quando=time.time(), dados=d)
    for ouvir in list(AO_LER_CONTA):
        try:
            ouvir(estado, d)
        except Exception:  # noqa: BLE001 - quem ouve nao derruba a leitura da conta
            _log.debug("quem ouvia a conta falhou", exc_info=True)
    return d


def sair_paulus(estado) -> None:
    try:
        _paulus(estado, "POST", "/api/ia/sair", {})
    except ErroNuvem:
        pass  # o segredo some daqui de qualquer jeito
    apagar_chave(estado, "paulus")
    _CONTA_CACHE.update(quando=0.0, dados=None)
    import plano

    plano.esquecer()
    if config(estado).get("provedor") == "paulus":
        estado.prefs.atualizar({"nuvem": {"ligado": False}})


# ------------------------------------------------------------ o que vem do e-mail

def _origens(estado) -> Path:
    return _pasta(estado) / "do-email.json"


def marcar_do_email(estado, caminho) -> None:
    """O anexo guardado do e-mail: nunca vai à nuvem (a política do Google e a do PAULUS)."""
    arq = _origens(estado)
    arq.parent.mkdir(parents=True, exist_ok=True)
    try:
        lista = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lista = []
    alvo = str(Path(caminho).resolve()).lower()
    if alvo not in lista:
        lista.append(alvo)
    arq.write_text(json.dumps(lista[-5000:], ensure_ascii=False), encoding="utf-8")


def do_email(estado) -> set[str]:
    try:
        return set(json.loads(_origens(estado).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _da_copia_do_drive(estado, caminhos: list[str]) -> bool:
    espelho = getattr(estado, "drive_online", None)
    if espelho is None:
        return False
    try:
        raiz = espelho.raiz().resolve()
    except Exception:  # noqa: BLE001
        return False
    for c in caminhos:
        try:
            if c and Path(c).resolve().is_relative_to(raiz):
                return True
        except OSError:
            continue
    return False


# ------------------------------------------------------------ mascarar

RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}\s*/\s*\d{4}\s*-?\s*\d{2}\b")
RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}\s*-?\s*\d{2}\b")
RE_CPF_FORMATADO = re.compile(r"\d{3}\.\d{3}\.\d{3}\s*-\s*\d{2}")
RE_CNPJ_FORMATADO = re.compile(r"\d{2}\.\d{3}\.\d{3}\s*/\s*\d{4}\s*-\s*\d{2}")
RE_PROCESSO = re.compile(r"\b\d{7}\s*-\s*\d{2}\s*\.\s*\d{4}\s*\.\s*\d\s*\.\s*\d{2}\s*\.\s*\d{4}\b")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
RE_TELEFONE = re.compile(r"(?:\(\d{2}\)\s*|\b\d{2}\s)9?\d{4}\s*-?\s*\d{4}\b")


class Mascara:
    """O mesmo dado vira sempre o mesmo marcador ("[CPF 1]"), e o marcador volta na resposta."""

    def __init__(self) -> None:
        self.mapa: dict[str, str] = {}
        self._de_volta: dict[str, str] = {}
        self.contagem: dict[str, int] = {}

    def _marcador(self, tipo: str, original: str) -> str:
        if original in self.mapa:
            return self.mapa[original]
        self.contagem[tipo] = self.contagem.get(tipo, 0) + 1
        m = f"[{tipo} {self.contagem[tipo]}]"
        self.mapa[original] = m
        self._de_volta[m] = original
        return m

    def aplicar(self, texto: str) -> str:
        import campos_br

        t = str(texto or "")
        t = RE_PROCESSO.sub(lambda m: self._marcador("PROCESSO", m.group(0)), t)
        # Escrito com a pontuação do documento ("057.648.816-38") ou logo depois
        # de "CPF"/"CNPJ", é o dado da pessoa mesmo com o dígito verificador
        # errado - erro de digitação no original não pode deixá-lo sair
        # (bateria de 02/10/2026). Só o número solto, sem pontuação nem
        # rótulo, precisa do dígito certo para não pegar qualquer sequência.
        def _e_dado(m, rotulo: str, formatado, valido) -> bool:
            return bool(formatado.fullmatch(m.group(0)) or valido(m.group(0))
                        or re.search(rotulo + r"\W{0,12}(?:n[º°o.]?\W{0,4})?$", t[max(0, m.start() - 24):m.start()], re.I))

        t = RE_CNPJ.sub(lambda m: self._marcador("CNPJ", m.group(0))
                        if _e_dado(m, "CNPJ", RE_CNPJ_FORMATADO, campos_br.cnpj_valido) else m.group(0), t)
        t = RE_CPF.sub(lambda m: self._marcador("CPF", m.group(0))
                       if _e_dado(m, "CPF", RE_CPF_FORMATADO, campos_br.cpf_valido) else m.group(0), t)
        t = RE_EMAIL.sub(lambda m: self._marcador("E-MAIL", m.group(0)), t)
        t = RE_TELEFONE.sub(lambda m: self._marcador("TELEFONE", m.group(0)), t)
        return t

    def desfazer(self, texto: str) -> str:
        for m, original in self._de_volta.items():
            texto = texto.replace(m, original)
        return texto


class Desmascarador:
    """Na resposta que chega aos pedaços: segura o "[" até ver se é um marcador."""

    def __init__(self, mascara: Mascara | None) -> None:
        self.mascara = mascara
        self.buffer = ""

    def entrar(self, pedaco: str) -> str:
        if self.mascara is None or not self.mascara.mapa:
            return pedaco
        self.buffer += pedaco
        corte = self.buffer.rfind("[")
        if corte >= 0 and "]" not in self.buffer[corte:] and len(self.buffer) - corte < 20:
            pronto, self.buffer = self.buffer[:corte], self.buffer[corte:]
        else:
            pronto, self.buffer = self.buffer, ""
        return self.mascara.desfazer(pronto)

    def fim(self) -> str:
        resto, self.buffer = self.buffer, ""
        return self.mascara.desfazer(resto) if self.mascara else resto


# ------------------------------------------------------------ a chamada

def _pedir(metodo: str, url: str, cabecalhos: dict, corpo: dict | None, stream: bool, timeout=None):
    if PEDIR["fn"] is not None:
        return PEDIR["fn"](metodo, url, cabecalhos, corpo, stream)
    import requests

    if metodo == "GET":
        return requests.get(url, headers=cabecalhos, timeout=timeout or 30)
    return requests.post(url, headers=cabecalhos, json=corpo, stream=stream, timeout=timeout or (15, 180))


def _cabecalhos(provedor: str, k: str) -> dict:
    if provedor == "anthropic":
        return {"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if provedor == "paulus":
        return {"Authorization": f"Bearer {k}", "Content-Type": "application/json", "X-PAULUS-Versao": VERSAO}
    return {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}


FRASES_DO_PORTAO = {
    "cota": "os tokens deste ciclo do plano acabaram (a recarga fica em Configurações › Modelos)",
    "sem_plano": "o plano da nuvem do Paulus não está em dia",
    "consentimento": "paulus.ia.br não tem o sim do titular: dê o sim de novo em Configurações › Modelos",
    "por_minuto": "muitos pedidos à nuvem neste minuto; espere um pouco",
}


def _erro_http(r, provedor: str = "") -> ErroNuvem:
    try:
        corpo = r.json()
        msg = ((corpo.get("error") or {}).get("message") if isinstance(corpo.get("error"), dict) else corpo.get("error")) or ""
    except Exception:  # noqa: BLE001
        corpo, msg = {}, ""
    if provedor == "paulus":
        # O portão (worker/ia.js) diz o motivo; a frase sai daqui.
        motivo = str((corpo or {}).get("motivo") or "")
        if motivo in FRASES_DO_PORTAO:
            return ErroNuvem(FRASES_DO_PORTAO[motivo], motivo)
        if r.status_code == 401:
            return ErroNuvem("paulus.ia.br não reconheceu esta instalação: ative a nuvem de novo", "segredo")
        return ErroNuvem(str((corpo or {}).get("erro") or f"paulus.ia.br respondeu com erro ({r.status_code})"))
    return ErroNuvem(_frase_http(r.status_code, msg))


def _frase_http(status: int, msg: str) -> str:
    if status in (401, 403):
        return "o provedor recusou a chave (confira se ela está ativa e tem crédito)"
    if status == 402:
        return "o provedor disse que a conta está sem crédito"
    if status == 429:
        return "o provedor disse que a conta passou do limite agora; tente mais tarde"
    if status == 404:
        return "o provedor não conhece esse modelo para esta chave"
    return f"o provedor respondeu com erro ({status}){': ' + str(msg)[:160] if msg else ''}"


def testar(estado, provedor: str) -> list[str]:
    """Os modelos que a chave enxerga (a única chamada que "Guardar e testar" faz). Levanta ErroNuvem."""
    k = chave(estado, provedor)
    if not k:
        raise ErroNuvem("guarde a chave antes")
    try:
        r = _pedir("GET", PROVEDORES[provedor]["modelos"], _cabecalhos(provedor, k), None, False)
    except Exception as exc:  # noqa: BLE001
        raise ErroNuvem("não consegui falar com o provedor agora (sem internet?)") from exc
    if r.status_code >= 400:
        raise _erro_http(r, provedor)
    if provedor == "paulus":
        return [str(m) for m in (r.json().get("modelos") or [])]
    ids = [str(m.get("id") or "") for m in (r.json().get("data") or [])]
    if provedor == "anthropic":
        ids = [i for i in ids if i.startswith("claude")]
    elif provedor == "deepinfra":
        # O DeepInfra lista imagem, voz e embeddings também: só os de texto que servem aqui.
        ids = [i for i in ids if re.search(r"(llama|qwen|mistral|deepseek|gemma)", i, re.I) and re.search(r"instruct|chat", i, re.I)]
    else:
        ids = [i for i in ids if re.match(r"(gpt|o\d|chatgpt)", i)]
    return sorted(set(ids))


def _mensagens_do_provedor(provedor: str, mensagens: list[dict]) -> tuple[str, list[dict]]:
    """[system, ..., user] do llama_client -> (o sistema, as mensagens alternadas)."""
    sistema = "\n\n".join(m["content"] for m in mensagens if m.get("role") == "system")
    resto = []
    for m in mensagens:
        if m.get("role") not in ("user", "assistant"):
            continue
        if resto and resto[-1]["role"] == m["role"]:
            resto[-1]["content"] += "\n\n" + m["content"]
        else:
            resto.append({"role": m["role"], "content": m["content"]})
    if resto and resto[0]["role"] == "assistant":
        resto.insert(0, {"role": "user", "content": "(continuação da conversa)"})
    return sistema, resto


def chamar(provedor: str, modelo: str, k: str, mensagens: list[dict], on_token, parar=None, json_mode: bool = False,
           max_tokens: int = MAX_TOKENS, nivel: str = "") -> dict:
    """
    Manda e devolve {"tokens_entrada", "tokens_saida"} (e "modelo", o que o
    Worker usou); cada pedaço do texto vai a `on_token`. No PAULUS (nuvem), o
    `nivel` da profundidade vai junto: o Worker escolhe o modelo do plano para
    ele e recusa o nível que o plano não tem.
    """
    sistema, msgs = _mensagens_do_provedor(provedor, mensagens)
    if provedor == "anthropic":
        corpo = {"model": modelo, "max_tokens": max_tokens, "system": sistema, "messages": msgs, "stream": True}
    else:
        corpo = {"model": modelo, "messages": ([{"role": "system", "content": sistema}] if sistema else []) + msgs,
                 "stream": True, "stream_options": {"include_usage": True}}
        if provedor in ("paulus", "deepinfra"):
            corpo["max_tokens"] = max_tokens
            corpo["temperature"] = 0.2
        if provedor == "paulus" and nivel:
            corpo["paulus_nivel"] = nivel
        if json_mode:
            corpo["response_format"] = {"type": "json_object"}
    try:
        r = _pedir("POST", PROVEDORES[provedor]["url"], _cabecalhos(provedor, k), corpo, True)
    except Exception as exc:  # noqa: BLE001
        raise ErroNuvem("não consegui falar com o provedor agora (sem internet?)") from exc
    if r.status_code >= 400:
        raise _erro_http(r, provedor)
    uso = {"tokens_entrada": 0, "tokens_saida": 0}
    cab = getattr(r, "headers", None) or {}
    real = str(cab.get("x-paulus-modelo") or "")
    if real:
        uso["modelo"] = real
    # O aviso do Worker (ex.: na primeira semana do Plus, o Opus libera no 8º dia).
    aviso = unquote(str(cab.get("x-paulus-aviso") or ""))[:240]
    if aviso:
        uso["aviso"] = aviso
    for linha in r.iter_lines(decode_unicode=True):
        if parar is not None and parar():
            break
        if not linha or not linha.startswith("data:"):
            continue
        bruto = linha[5:].strip()
        if bruto == "[DONE]":
            break
        try:
            ev = json.loads(bruto)
        except ValueError:
            continue
        if provedor == "anthropic":
            if ev.get("type") == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
                on_token(ev["delta"].get("text", ""))
            elif ev.get("type") == "message_start":
                uso["tokens_entrada"] = int(((ev.get("message") or {}).get("usage") or {}).get("input_tokens") or 0)
            elif ev.get("type") == "message_delta":
                uso["tokens_saida"] = int((ev.get("usage") or {}).get("output_tokens") or 0)
            elif ev.get("type") == "error":
                raise ErroNuvem("o provedor parou no meio: " + str((ev.get("error") or {}).get("message") or "")[:160])
        else:
            for c in ev.get("choices") or []:
                pedaco = (c.get("delta") or {}).get("content")
                if pedaco:
                    on_token(pedaco)
            if ev.get("usage"):
                uso["tokens_entrada"] = int(ev["usage"].get("prompt_tokens") or 0)
                uso["tokens_saida"] = int(ev["usage"].get("completion_tokens") or 0)
    try:
        r.close()
    except Exception:  # noqa: BLE001
        pass
    return uso


# ------------------------------------------------------------ o que fica aqui

def motivo_para_ficar(estado, caminhos) -> str:
    """Por que este texto não pode sair ("" = pode). O mesmo para a conversa, os resumos e a redação."""
    import aparelho

    caminhos = [str(c) for c in caminhos or [] if c]
    if aparelho.so_no_escritorio().toca(estado, caminhos):
        return "usa um caso marcado só no escritório"
    marcados = do_email(estado)
    if any(str(Path(c).resolve()).lower() in marcados for c in caminhos):
        return "usa um anexo que veio do e-mail, e o que vem do e-mail nunca vai à nuvem"
    # A cópia das pastas do Drive feita pelo PAULUS vem das APIs do Google:
    # pela política (Uso Limitado), não vai a terceiros.
    if _da_copia_do_drive(estado, caminhos):
        return "usa um arquivo copiado do Google Drive pelo Paulus, e o que vem das APIs do Google nunca vai à nuvem"
    return ""


def _data_do_sim(estado) -> str:
    q = str((config(estado).get("consentimento") or {}).get("quando") or "")
    try:
        return datetime.fromisoformat(q).strftime("%d/%m/%Y")
    except ValueError:
        return q[:10]


def caminhos_de(estado, servico=None, cadastro=None, caminhos=()) -> list[str]:
    """
    As pastas de onde vem o texto de um resumo ou de uma redação: a do
    serviço, as de todos os serviços do cliente (o documento do editor é do
    cliente, não de uma pasta) e os arquivos dados. É com elas que o "só no
    escritório" confere - o mesmo de sempre, por pasta.
    """
    saida = [str(c) for c in caminhos or [] if c]
    servicos = getattr(estado, "servicos", None)
    if servicos is None:
        return saida
    ids = []
    try:
        if servico:
            ids.append(int(servico))
        if cadastro:
            ids += [int(s["id"]) for s in servicos.base.buscar("SELECT id FROM servicos WHERE cadastro_id = ?", (int(cadastro),))]
    except (TypeError, ValueError, AttributeError):
        return saida
    for i in ids:
        try:
            pasta = servicos.pasta_de(i, criar=False)
        except Exception:  # noqa: BLE001 - serviço apagado: nada a conferir
            pasta = None
        if pasta:
            saida.append(str(pasta))
    return saida


def quem_envia(estado, pessoa=None) -> dict:
    """
    De quem e o envio, para Plano e consumo (src/consumo.py): a conta da
    equipe que fez o pedido de fora, ou a janela do escritorio (conta 0).
    """
    p = pessoa
    if p is None:
        try:
            import equipe

            p = equipe.pessoa_da_vez()
        except Exception:  # noqa: BLE001 - sem a sessao, a janela do escritorio
            p = None
    if p:
        return {"conta_id": int(p.get("conta_id") or 0), "nome": str(p.get("nome") or "")}
    import consumo

    return {"conta_id": 0, "nome": consumo.nome_da_janela(estado)}


def limite_atingido(estado, quem: dict) -> str:
    """O limite de uso que impede este envio (src/consumo.py), ou ""."""
    try:
        import consumo

        return consumo.motivo_do_limite(estado, int(quem.get("conta_id") or 0))
    except Exception:  # noqa: BLE001 - na duvida sobre o limite, o envio segue
        return ""


def registrar_envio(estado, mensagens: list[dict], linha: dict) -> None:
    """A linha do registro de envios, e o texto exato que saiu ao lado."""
    pasta = _pasta(estado) / "envios"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{linha['envio']}.txt").write_text("\n\n".join(f"[{x['role']}]\n{x['content']}" for x in mensagens), encoding="utf-8")
    linha = {"quando": datetime.now().isoformat(timespec="seconds"), **linha}
    with (_pasta(estado) / "envios.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    _CONTA_CACHE["quando"] = 0.0
    try:
        estado.acesso_de_fora.anotar(acao="nuvem", alvo=f"{linha.get('provedor')}/{linha.get('modelo')}: {linha.get('caracteres', 0)} "
                                                       f"caracteres ({linha.get('tarefa', 'conversa')})",
                                     pessoa="de fora" if linha.get("de_fora") else "janela do escritório")
    except Exception:  # noqa: BLE001 - a auditoria não derruba a resposta
        pass


# ------------------------------------------------------------ um envio

class Envio:
    """Uma pergunta que pode ir à nuvem: montar, pedir o sim, mandar, anotar."""

    def __init__(self, estado, trabalho, pessoa=None) -> None:
        self.estado = estado
        self.trabalho = trabalho
        self.pessoa = pessoa
        c = config(estado)
        self.provedor = c.get("provedor") or "anthropic"
        self.modelo = c.get("modelo") or PROVEDORES.get(self.provedor, {}).get("padrao", "")
        self.mascarar = bool(c.get("mascarar", True))
        self.id = uuid.uuid4().hex[:12]
        self.motivo = ""
        self.pedido_id = ""
        self.mensagens: list[dict] = []
        self.mascara: Mascara | None = None
        self.decidido = threading.Event()
        self.como = ""
        self.foi = False
        self.uso: dict = {}
        self.caracteres = 0
        self.documentos: list[str] = []
        # A profundidade escolhida na caixa da pergunta (src/profundidade.py):
        # a instrução do nível, o teto da resposta e, se o escritório quis, o modelo.
        self.profundidade = ""

    @property
    def nome_do_provedor(self) -> str:
        return PROVEDORES.get(self.provedor, {}).get("nome", self.provedor)

    def vai_sem_pedir(self) -> bool:
        """
        O envio desta conversa sai sem pedir o sim em Aprovações - as mesmas
        regras de `preparar`. A triagem (src/triagem.py) só vai nesse caso: o
        que precisa do sim a cada envio não sai antes dele, nem para triar.
        """
        if not ligada(self.estado) or not usa(self.estado, "conversa"):
            return False
        if bool((self.trabalho.contexto or {}).get("nuvem_liberada")) or self.estado.prefs.pode("modelo_nuvem"):
            return True
        return not config(self.estado).get("pedir_cada_envio")

    def preparar(self, pergunta: str, contexto: str, regra: str, hits, historico=None) -> dict | None:
        """O pacote, ou None com o motivo de ficar neste computador."""
        if not ligada(self.estado):
            self.motivo = ("o titular ainda não deu o sim para a nuvem (Configurações › Modelos)" if not consentido(self.estado)
                           else "a nuvem está desligada (ou sem chave) em Configurações › Modelos")
            return None
        if not usa(self.estado, "conversa"):
            self.motivo = "a conversa está desligada da nuvem em Configurações › Modelos"
            return None
        # Plano e consumo: de quem e a pergunta, e se o limite dela (ou do
        # escritorio) ainda deixa ir a nuvem.
        self.quem = quem_envia(self.estado, self.pessoa)
        self.pergunta = " ".join(str(pergunta or "").split())[:140]
        limite = limite_atingido(self.estado, self.quem)
        if limite:
            self.motivo = limite
            return None
        caminhos = [str(getattr(h.chunk, "doc_path", "") or "") for h in hits or []]
        motivo = motivo_para_ficar(self.estado, caminhos)
        if motivo:
            self.motivo = "a resposta " + motivo
            return None
        self.mascara = Mascara() if self.mascarar else None
        m = self.mascara
        # A instrução da nuvem é a dela (src/instrucao_nuvem.py), e não a do 3B
        # deste computador: com a do 3B o modelo recusava o direito em tese e não
        # sabia a data de hoje (bateria de 02/10/2026).
        import instrucao_nuvem

        import profundidade as profundidade_mod

        if self.profundidade:
            nivel = profundidade_mod.obter(self.profundidade, self.estado.prefs.dados)
            self.modelo = profundidade_mod.modelo_do_nivel(self.estado.prefs.dados, nivel, self.modelo)
            regra = ((regra or "").strip() + "\n\n" + profundidade_mod.INSTRUCAO_RESPOSTA[nivel.id]).strip()
        mensagens = instrucao_nuvem.montar_mensagens(
            m.aplicar(pergunta) if m else pergunta, m.aplicar(contexto) if m else contexto, ensinado=regra,
            historico=[dict(x, content=m.aplicar(x.get("content", "")) if m else x.get("content", ""))
                       for x in (historico or [])])
        self.mensagens = mensagens
        self.caracteres = sum(len(x.get("content", "")) for x in mensagens)
        self.documentos = list(dict.fromkeys(getattr(h, "doc_name", "") for h in hits or [] if getattr(h, "doc_name", "")))
        liberada = bool((self.trabalho.contexto or {}).get("nuvem_liberada"))
        sem_pedir = self.estado.prefs.pode("modelo_nuvem")
        # V5: dado o sim do titular, vai sem pedir - pedir a cada envio é opção.
        pelo_sim = not config(self.estado).get("pedir_cada_envio")
        resumo = {"envio": self.id, "provedor": self.nome_do_provedor, "modelo": self.modelo, "caracteres": self.caracteres,
                  "tokens_aprox": round(self.caracteres / 3.5), "documentos": self.documentos,
                  "mascarados": dict(m.contagem) if m else {}, "mascarar": self.mascarar}
        if liberada or sem_pedir or pelo_sim:
            self.como = ("conversa liberada" if liberada else "regra de alçada (sem pedir)" if sem_pedir
                         else "com o sim do titular de " + _data_do_sim(self.estado))
            self.decidido.set()
            return dict(resumo, precisa_aprovar=False, como=self.como)
        if self.pessoa is not None:
            # O sim de cada envio é da janela do escritório (Aprovações): de fora não há quem aprove.
            self.motivo = "a nuvem está pedindo o sim a cada envio, e esse sim é dado no computador do escritório"
            return None
        texto = "\n\n".join(f"[{x['role']}]\n{x['content']}" for x in mensagens)
        pedido = self.estado.fila.pedir(
            f"Mandar à nuvem ({self.nome_do_provedor}): {pergunta[:80]}", "nuvem", acao="nuvem.enviar",
            pedido_por="Conversa", reversivel=False, etiquetas=["sai desta máquina", self.modelo],
            resumo=(f"Vai para a {self.nome_do_provedor}, modelo {self.modelo}: a pergunta e "
                    f"{len(hits or [])} trecho(s) de {len(self.documentos)} documento(s), {self.caracteres:,} caracteres "
                    f"(~{resumo['tokens_aprox']:,} tokens, cobrados na conta do escritório).".replace(",", ".") +
                    (" Mascarados: " + ", ".join(f"{n} {t}" for t, n in m.contagem.items()) + "." if m and m.contagem else
                     (" Nada para mascarar." if m else " Sem mascarar.")) +
                    " Recusar: a resposta é escrita neste computador."),
            dados={"envio": self.id, "trabalho_id": self.trabalho.id, "texto_exato": texto[:60000], "sai_daqui": True,
                   "provedor": self.provedor, "modelo": self.modelo})
        self.pedido_id = pedido.id
        with _trava:
            _ESPERANDO[pedido.id] = self
        return dict(resumo, precisa_aprovar=True, pedido_id=pedido.id)

    def esperar(self, parar=None) -> str:
        """"aprovado", "recusado", "vencido" ou "parado"."""
        limite = time.time() + ESPERA_S
        try:
            while not self.decidido.wait(0.5):
                if parar is not None and parar():
                    return "parado"
                p = self.estado.fila.obter(self.pedido_id)
                if p is not None and p.estado == "recusado":
                    return "recusado"
                if time.time() > limite:
                    return "vencido"
            return "aprovado"
        finally:
            with _trava:
                _ESPERANDO.pop(self.pedido_id, None)

    def mandar(self, on_token, parar=None) -> dict:
        desm = Desmascarador(self.mascara)
        import profundidade as profundidade_mod

        teto = profundidade_mod.SAIDA_RESPOSTA.get(self.profundidade, MAX_TOKENS)
        uso = chamar(self.provedor, self.modelo, chave(self.estado, self.provedor), self.mensagens,
                     lambda t: on_token(desm.entrar(t)), parar=parar, max_tokens=teto, nivel=self.profundidade)
        # O modelo que respondeu de fato (o do plano, no PAULUS nuvem).
        self.modelo = uso.pop("modelo", "") or self.modelo
        self.aviso = uso.pop("aviso", "")
        resto = desm.fim()
        if resto:
            on_token(resto)
        self.foi = True
        self.uso = uso
        self.registrar()
        return uso

    def registrar(self) -> None:
        """A linha do registro de envios (e o texto exato que saiu, ao lado)."""
        registrar_envio(self.estado, self.mensagens, {
            "envio": self.id, "tarefa": "conversa", "trabalho_id": self.trabalho.id, "titulo": self.trabalho.titulo,
            "provedor": self.provedor, "modelo": self.modelo, "caracteres": self.caracteres, "documentos": self.documentos,
            "mascarados": dict(self.mascara.contagem) if self.mascara else {}, "como": self.como or "aprovado em Aprovações",
            "pedido_id": self.pedido_id, "de_fora": self.pessoa is not None,
            "pessoa": getattr(self, "quem", None) or quem_envia(self.estado, self.pessoa),
            "pergunta": getattr(self, "pergunta", ""), "profundidade": self.profundidade, **self.uso})

    def resumo(self) -> dict:
        return {"onde": "nuvem" if self.foi else "computador", "provedor": self.nome_do_provedor, "modelo": self.modelo,
                "motivo": self.motivo, "caracteres": self.caracteres, "como": self.como,
                "mascarados": dict(self.mascara.contagem) if self.mascara else {}, **self.uso,
                **({"aviso": self.aviso} if getattr(self, "aviso", "") else {})}


def liberar_da_fila(pedido) -> str:
    """O sim em Aprovações: a pergunta que esperava segue para a nuvem."""
    with _trava:
        envio = _ESPERANDO.get(pedido.id)
    if envio is None:
        return "a pergunta já não esperava (passou o tempo, ou a conversa parou): pergunte de novo"
    envio.como = "aprovado em Aprovações"
    envio.decidido.set()
    return f"liberado: a resposta da {envio.nome_do_provedor} sai na conversa"


def envios(estado, limite: int = 30) -> list[dict]:
    try:
        linhas = (_pasta(estado) / "envios.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    saida = []
    for l in reversed(linhas[-500:]):
        try:
            saida.append(json.loads(l))
        except ValueError:
            continue
        if len(saida) >= limite:
            break
    return saida


# ------------------------------------------------------------ resumos e redação (V6)

def _desmascarar_tudo(valor, mascara: Mascara | None):
    if mascara is None:
        return valor
    if isinstance(valor, str):
        return mascara.desfazer(valor)
    if isinstance(valor, list):
        return [_desmascarar_tudo(v, mascara) for v in valor]
    if isinstance(valor, dict):
        return {k: _desmascarar_tudo(v, mascara) for k, v in valor.items()}
    return valor


class ClienteNuvem:
    """
    O cliente das tarefas "resumos" e "redacao" com a nuvem ligada para elas:
    a mesma cara do LlamaClient (ask, ask_json), mascarado e registrado como a
    conversa. Se o texto não pode sair (`caminhos` de um caso só no escritório,
    do e-mail, do Drive) ou a nuvem falha (sem internet, a cota acabou), quem
    escreve é o modelo deste computador - e `ultima["nuvem"]` diz por quê.
    O resto (model, num_ctx, opcoes...) é o do cliente local.
    """

    aceita_tarefa = True

    def __init__(self, estado, tarefa: str, local, caminhos=()) -> None:
        self.estado = estado
        self.tarefa = tarefa
        self.local = local
        self.caminhos = [str(c) for c in caminhos or [] if c]
        c = config(estado)
        self.provedor = c.get("provedor") or "paulus"
        self.modelo = c.get("modelo") or PROVEDORES.get(self.provedor, {}).get("padrao", "")
        self.mascarar = bool(c.get("mascarar", True))
        self.ultima: dict = {}

    def __getattr__(self, nome):
        # Só chega aqui o que esta classe não tem: o do cliente local.
        return getattr(self.__dict__["local"], nome)

    def _motivo(self) -> str:
        if not usa(self.estado, self.tarefa):
            return "a nuvem não está ligada para esta tarefa"
        limite = limite_atingido(self.estado, quem_envia(self.estado))
        if limite:
            return limite
        m = motivo_para_ficar(self.estado, self.caminhos)
        return ("o texto " + m) if m else ""

    def _mandar(self, mensagens: list[dict], on_token=None, parar=None, json_mode: bool = False) -> str:
        mascara = Mascara() if self.mascarar else None
        if mascara is not None:
            mensagens = [dict(x, content=mascara.aplicar(x.get("content", ""))) for x in mensagens]
        desm = Desmascarador(mascara)
        partes: list[str] = []

        def entrou(t: str) -> None:
            pronto = desm.entrar(t)
            if pronto:
                partes.append(pronto)
                if on_token:
                    on_token(pronto)

        uso = chamar(self.provedor, self.modelo, chave(self.estado, self.provedor), mensagens, entrou, parar=parar,
                     json_mode=json_mode, max_tokens=4000 if self.provedor in ("paulus", "deepinfra") else MAX_TOKENS)
        self.modelo = uso.pop("modelo", "") or self.modelo
        aviso = uso.pop("aviso", "")
        resto = desm.fim()
        if resto:
            partes.append(resto)
            if on_token:
                on_token(resto)
        caracteres = sum(len(x.get("content", "")) for x in mensagens)
        registrar_envio(self.estado, mensagens, {
            "envio": uuid.uuid4().hex[:12], "tarefa": self.tarefa, "titulo": TAREFAS.get(self.tarefa, self.tarefa),
            "provedor": self.provedor, "modelo": self.modelo, "caracteres": caracteres, "documentos": [],
            "mascarados": dict(mascara.contagem) if mascara else {}, "como": "com o sim do titular de " + _data_do_sim(self.estado),
            "pessoa": quem_envia(self.estado), "pergunta": TAREFAS.get(self.tarefa, self.tarefa), **uso})
        self.ultima = {"prompt_eval_count": uso.get("tokens_entrada", 0), "eval_count": uso.get("tokens_saida", 0),
                       "truncou": False, "nuvem": {"onde": "nuvem", "provedor": PROVEDORES.get(self.provedor, {}).get("nome", ""),
                                                   "modelo": self.modelo, **uso, **({"aviso": aviso} if aviso else {})}}
        return "".join(partes).strip()

    def _aqui(self, motivo: str) -> None:
        self.ultima = {"nuvem": {"onde": "computador", "motivo": motivo}}
        if motivo and "não está ligada" not in motivo:
            _log.info("%s ficou neste computador: %s", self.tarefa, motivo)

    def ask(self, question: str, context: str = "", **k) -> str:
        import llama_client

        motivo = self._motivo()
        # "continuar" é a escrita no aparelho: ela é do modelo local.
        if motivo or k.get("continuar"):
            self._aqui(motivo)
            return self.local.ask(question, context, **k)
        mensagens = llama_client.montar_mensagens(question, context, sistema=k.get("sistema", ""), ensinado=k.get("ensinado", ""),
                                                  historico=k.get("historico"))
        try:
            return self._mandar(mensagens, on_token=k.get("on_token"), parar=k.get("parar"))
        except ErroNuvem as exc:
            self._aqui(str(exc))
            local = self.local.ask(question, context, **k)
            self.ultima = dict(getattr(self.local, "ultima", {}) or {}, nuvem={"onde": "computador", "motivo": str(exc)})
            return local

    def ask_json(self, instruction: str, context: str = "", schema_hint: str = "", sistema: str = ""):
        import llama_client

        motivo = self._motivo()
        if motivo:
            self._aqui(motivo)
            return self.local.ask_json(instruction, context, schema_hint=schema_hint, sistema=sistema)
        prompt = instruction
        if schema_hint:
            prompt += f"\n\nResponda APENAS com JSON neste formato:\n{schema_hint}"
        if context:
            prompt = f"Trechos de contratos:\n\n{context}\n\n{prompt}"
        mensagens = [{"role": "system", "content": sistema or llama_client.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        try:
            bruto = self._mandar(mensagens, json_mode=self.provedor != "anthropic")
        except ErroNuvem as exc:
            self._aqui(str(exc))
            return self.local.ask_json(instruction, context, schema_hint=schema_hint, sistema=sistema)
        try:
            return json.loads(bruto)
        except ValueError:
            ini = min((i for i in (bruto.find("{"), bruto.find("[")) if i != -1), default=-1)
            fim = max(bruto.rfind("}"), bruto.rfind("]"))
            if ini != -1 and fim > ini:
                try:
                    return json.loads(bruto[ini:fim + 1])
                except ValueError:
                    return None
            return None


# ------------------------------------------------------------ o trabalho em etapas

def motivo_para_trabalhar_aqui(estado, trabalho=None, pessoa=None, caminhos=()) -> str:
    """
    Por que a entrevista e a elaboração em etapas (src/entrevista.py,
    src/elaboracao.py) não vão à nuvem ("" = vão). São várias chamadas por
    pedido: só sem pedir o sim a cada envio - o sim do titular, a conversa
    liberada ou a regra de alçada. Os limites de uso e o que nunca sai valem
    como na conversa.
    """
    if not usa(estado, "conversa"):
        return "a nuvem não está ligada para a conversa"
    liberada = bool(((getattr(trabalho, "contexto", None) or {}).get("nuvem_liberada")))
    if config(estado).get("pedir_cada_envio") and not liberada and not estado.prefs.pode("modelo_nuvem"):
        return "a nuvem está pedindo o sim a cada envio"
    limite = limite_atingido(estado, quem_envia(estado, pessoa))
    if limite:
        return limite
    m = motivo_para_ficar(estado, caminhos)
    return ("o texto " + m) if m else ""


def chamada(estado, mensagens: list[dict], *, pessoa=None, trabalho=None, etapa: str = "", pergunta: str = "",
            mascara: "Mascara | None" = None, on_token=None, desmascarar: bool = True, json_mode: bool = False,
            max_tokens: int = MAX_TOKENS, parar=None, modelo: str = "", profundidade: str = "") -> tuple[str, dict]:
    """
    Uma chamada de uma etapa do trabalho: mascarada com a `mascara` do pedido
    (a mesma em todas as etapas, para "[CPF 1]" ser o mesmo CPF do começo ao
    fim), registrada como todo envio, com quem pediu, a etapa e a
    profundidade. Devolve (texto, uso). Com `desmascarar`, o texto volta com os
    dados; sem, fica com os marcadores - é o que vai para a etapa seguinte.
    Erro da nuvem sobe como ErroNuvem.
    """
    c = config(estado)
    provedor = c.get("provedor") or "paulus"
    modelo = modelo or c.get("modelo") or PROVEDORES.get(provedor, {}).get("padrao", "")
    if mascara is not None:
        mensagens = [dict(x, content=mascara.aplicar(x.get("content", ""))) for x in mensagens]
    desm = Desmascarador(mascara if desmascarar else None)
    partes: list[str] = []

    def entrou(t: str) -> None:
        pronto = desm.entrar(t)
        if pronto:
            partes.append(pronto)
            if on_token:
                on_token(pronto)

    uso = chamar(provedor, modelo, chave(estado, provedor), mensagens, entrou, parar=parar, json_mode=json_mode,
                 max_tokens=max_tokens, nivel=profundidade)
    modelo = uso.pop("modelo", "") or modelo
    aviso = uso.pop("aviso", "")
    resto = desm.fim()
    if resto:
        partes.append(resto)
        if on_token:
            on_token(resto)
    registrar_envio(estado, mensagens, {
        "envio": uuid.uuid4().hex[:12], "tarefa": "conversa",
        "titulo": getattr(trabalho, "titulo", "") or "Conversa", "trabalho_id": getattr(trabalho, "id", ""),
        "provedor": provedor, "modelo": modelo, "caracteres": sum(len(x.get("content", "")) for x in mensagens),
        "documentos": [], "mascarados": dict(mascara.contagem) if mascara else {},
        "como": "com o sim do titular de " + _data_do_sim(estado), "de_fora": pessoa is not None,
        "pessoa": quem_envia(estado, pessoa), "pergunta": " ".join(str(pergunta or "").split())[:140],
        "etapa": etapa, "profundidade": profundidade, **uso})
    return "".join(partes).strip(), {**uso, "provedor": PROVEDORES.get(provedor, {}).get("nome", provedor),
                                     "modelo": modelo, **({"aviso": aviso} if aviso else {})}
