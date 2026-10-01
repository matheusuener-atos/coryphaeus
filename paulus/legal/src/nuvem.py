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
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

PROVEDORES = {
    "anthropic": {"nome": "Anthropic (Claude)", "padrao": "claude-sonnet-5-5",
                  "modelos": "https://api.anthropic.com/v1/models", "url": "https://api.anthropic.com/v1/messages"},
    "openai": {"nome": "OpenAI (GPT)", "padrao": "",
               "modelos": "https://api.openai.com/v1/models", "url": "https://api.openai.com/v1/chat/completions"},
}
ESPERA_S = 600
MAX_TOKENS = 2000
# Os testes trocam a chamada à internet aqui: (método, url, cabeçalhos, corpo, stream) -> resposta tipo requests.
PEDIR: dict = {"fn": None}
_ESPERANDO: dict[str, "Envio"] = {}
_trava = threading.Lock()


class ErroNuvem(RuntimeError):
    """A nuvem não respondeu; a frase vai para a tela."""


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
    return bool(c.get("ligado") and c.get("provedor") in PROVEDORES and c.get("modelo") and chave(estado, c["provedor"]))


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
        t = RE_CNPJ.sub(lambda m: self._marcador("CNPJ", m.group(0)) if campos_br.cnpj_valido(m.group(0)) else m.group(0), t)
        t = RE_CPF.sub(lambda m: self._marcador("CPF", m.group(0)) if campos_br.cpf_valido(m.group(0)) else m.group(0), t)
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

def _pedir(metodo: str, url: str, cabecalhos: dict, corpo: dict | None, stream: bool):
    if PEDIR["fn"] is not None:
        return PEDIR["fn"](metodo, url, cabecalhos, corpo, stream)
    import requests

    if metodo == "GET":
        return requests.get(url, headers=cabecalhos, timeout=30)
    return requests.post(url, headers=cabecalhos, json=corpo, stream=stream, timeout=(15, 180))


def _cabecalhos(provedor: str, k: str) -> dict:
    if provedor == "anthropic":
        return {"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    return {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}


def _erro_http(r) -> str:
    try:
        corpo = r.json()
        msg = ((corpo.get("error") or {}).get("message") if isinstance(corpo.get("error"), dict) else corpo.get("error")) or ""
    except Exception:  # noqa: BLE001
        msg = ""
    if r.status_code in (401, 403):
        return "o provedor recusou a chave (confira se ela está ativa e tem crédito)"
    if r.status_code == 429:
        return "o provedor disse que a conta passou do limite agora; tente mais tarde"
    if r.status_code == 404:
        return "o provedor não conhece esse modelo para esta chave"
    return f"o provedor respondeu com erro ({r.status_code}){': ' + str(msg)[:160] if msg else ''}"


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
        raise ErroNuvem(_erro_http(r))
    ids = [str(m.get("id") or "") for m in (r.json().get("data") or [])]
    if provedor == "anthropic":
        ids = [i for i in ids if i.startswith("claude")]
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


def chamar(provedor: str, modelo: str, k: str, mensagens: list[dict], on_token, parar=None) -> dict:
    """Manda e devolve {"tokens_entrada", "tokens_saida"}; cada pedaço do texto vai a `on_token`."""
    sistema, msgs = _mensagens_do_provedor(provedor, mensagens)
    if provedor == "anthropic":
        corpo = {"model": modelo, "max_tokens": MAX_TOKENS, "system": sistema, "messages": msgs, "stream": True}
    else:
        corpo = {"model": modelo, "messages": ([{"role": "system", "content": sistema}] if sistema else []) + msgs,
                 "stream": True, "stream_options": {"include_usage": True}}
    try:
        r = _pedir("POST", PROVEDORES[provedor]["url"], _cabecalhos(provedor, k), corpo, True)
    except Exception as exc:  # noqa: BLE001
        raise ErroNuvem("não consegui falar com o provedor agora (sem internet?)") from exc
    if r.status_code >= 400:
        raise ErroNuvem(_erro_http(r))
    uso = {"tokens_entrada": 0, "tokens_saida": 0}
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

    @property
    def nome_do_provedor(self) -> str:
        return PROVEDORES.get(self.provedor, {}).get("nome", self.provedor)

    def preparar(self, pergunta: str, contexto: str, regra: str, hits, historico=None) -> dict | None:
        """O pacote, ou None com o motivo de ficar neste computador."""
        import aparelho
        import llama_client

        if self.pessoa is not None:
            self.motivo = "de fora, a resposta é sempre escrita no computador do escritório"
            return None
        if not ligada(self.estado):
            self.motivo = "a nuvem está desligada (ou sem chave) em Configurações › Modelos"
            return None
        caminhos = [str(getattr(h.chunk, "doc_path", "") or "") for h in hits or []]
        if aparelho.so_no_escritorio().toca(self.estado, caminhos):
            self.motivo = "a resposta usa um caso marcado só no escritório"
            return None
        marcados = do_email(self.estado)
        if any(c and str(Path(c).resolve()).lower() in marcados for c in caminhos):
            self.motivo = "a resposta usa um anexo que veio do e-mail, e o que vem do e-mail nunca vai à nuvem"
            return None
        # A cópia das pastas do Drive feita pelo PAULUS vem das APIs do Google:
        # pela política (Uso Limitado), não vai a terceiros.
        if _da_copia_do_drive(self.estado, caminhos):
            self.motivo = "a resposta usa um arquivo copiado do Google Drive pelo PAULUS, e o que vem das APIs do Google nunca vai à nuvem"
            return None
        self.mascara = Mascara() if self.mascarar else None
        m = self.mascara
        mensagens = llama_client.montar_mensagens(m.aplicar(pergunta) if m else pergunta, m.aplicar(contexto) if m else contexto,
                                                  ensinado=regra, historico=[dict(x, content=m.aplicar(x.get("content", "")) if m else x.get("content", ""))
                                                                             for x in (historico or [])])
        self.mensagens = mensagens
        self.caracteres = sum(len(x.get("content", "")) for x in mensagens)
        self.documentos = list(dict.fromkeys(getattr(h, "doc_name", "") for h in hits or [] if getattr(h, "doc_name", "")))
        liberada = bool((self.trabalho.contexto or {}).get("nuvem_liberada"))
        sem_pedir = self.estado.prefs.pode("modelo_nuvem")
        resumo = {"envio": self.id, "provedor": self.nome_do_provedor, "modelo": self.modelo, "caracteres": self.caracteres,
                  "tokens_aprox": round(self.caracteres / 3.5), "documentos": self.documentos,
                  "mascarados": dict(m.contagem) if m else {}, "mascarar": self.mascarar}
        if liberada or sem_pedir:
            self.como = "conversa liberada" if liberada else "regra de alçada (sem pedir)"
            self.decidido.set()
            return dict(resumo, precisa_aprovar=False, como=self.como)
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
        uso = chamar(self.provedor, self.modelo, chave(self.estado, self.provedor), self.mensagens,
                     lambda t: on_token(desm.entrar(t)), parar=parar)
        resto = desm.fim()
        if resto:
            on_token(resto)
        self.foi = True
        self.uso = uso
        self.registrar()
        return uso

    def registrar(self) -> None:
        """A linha do registro de envios (e o texto exato que saiu, ao lado)."""
        pasta = _pasta(self.estado) / "envios"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{self.id}.txt").write_text("\n\n".join(f"[{x['role']}]\n{x['content']}" for x in self.mensagens), encoding="utf-8")
        linha = {"quando": datetime.now().isoformat(timespec="seconds"), "envio": self.id, "trabalho_id": self.trabalho.id,
                 "titulo": self.trabalho.titulo, "provedor": self.provedor, "modelo": self.modelo, "caracteres": self.caracteres,
                 "documentos": self.documentos, "mascarados": dict(self.mascara.contagem) if self.mascara else {},
                 "como": self.como or "aprovado em Aprovações", "pedido_id": self.pedido_id, **self.uso}
        with (_pasta(self.estado) / "envios.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        try:
            self.estado.acesso_de_fora.anotar(acao="nuvem", alvo=f"{self.provedor}/{self.modelo}: {self.caracteres} caracteres de "
                                                           f"{len(self.documentos)} documento(s)", pessoa="janela do escritório")
        except Exception:  # noqa: BLE001 - a auditoria não derruba a resposta
            pass

    def resumo(self) -> dict:
        return {"onde": "nuvem" if self.foi else "computador", "provedor": self.nome_do_provedor, "modelo": self.modelo,
                "motivo": self.motivo, "caracteres": self.caracteres, "como": self.como,
                "mascarados": dict(self.mascara.contagem) if self.mascara else {}, **self.uso}


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
