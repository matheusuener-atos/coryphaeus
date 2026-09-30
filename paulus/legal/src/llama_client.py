"""
PAULUS Legal - Cliente Ollama.

Fala com o servidor local do Ollama (http://127.0.0.1:11434). Nenhum dado sai
da maquina.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import replace

import requests

import inferencia


def _host_do_ollama(bruto: str) -> str:
    """
    O endereco do Ollama, com 127.0.0.1 no lugar de "localhost".

    No Windows, "localhost" tenta primeiro o IPv6 (::1); o Ollama so escuta
    no IPv4, e cada pedido esperava ~2 s o IPv6 desistir. Medido: 2.072 ms
    por localhost, 32 ms por 127.0.0.1 - em toda conversa e em todo status.
    """
    host = bruto.strip().rstrip("/")
    if "://" not in host:
        host = "http://" + host
    return host.replace("://localhost", "://127.0.0.1")


DEFAULT_HOST = _host_do_ollama(os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
DEFAULT_MODEL = os.getenv("PAULUS_MODEL", "llama3.2:3b")

# A janela ja cresceu com o acervo (de 8192 a 32768): com 6.000 caracteres o
# modelo respondia "nao encontrei os nomes" sobre quatro procuracoes que o
# acervo inteiro, 21.382 caracteres, respondia. Mas cada mudanca de janela
# faz o Ollama recarregar o modelo - um documento novo custava uma recarga
# na pergunta seguinte. Desde a I1 a janela e fixa por modelo
# (src/inferencia.py), 16384 de fabrica: o acervo que cabe ainda vai
# inteiro, e o que nao cabe passa pela busca.

_log = logging.getLogger("paulus.modelo")

# A instrucao anterior tinha sete regras numeradas, e a de numero 3 entregava
# ao modelo uma frase de fuga pronta: "se a resposta nao estiver nos trechos,
# diga exatamente Nao encontrei essa informacao". Um modelo de 3 bilhoes de
# parametros usa essa saida cedo demais.
#
# Medido nesta maquina, mesmos documentos e mesmo modelo, so trocando a
# instrucao: das seis informacoes perguntadas, a instrucao antiga achou UMA e
# esta achou as SEIS. Numa das perguntas a antiga desistiu em 8 segundos, sem
# ler - a resposta estava escrita no primeiro documento.
#
# O que NAO saiu: a trava contra invencao. Num programa juridico, inventar
# clausula ou numero e o dano que nenhum ganho de recall paga.
#
# 27/09/2026, banco de provas (tools/demo/roteiro.py --dificil): tres regras
# entraram - trazer a lista inteira, dizer primeiro quando o documento nao
# preve o que foi perguntado, e nao trocar o advogado de uma parte pelo da
# outra ("quem e o advogado da Rio Fresco?" saia "Helena Moura", que e da
# Cooperativa). Medidas antes e depois no mesmo conjunto.
SYSTEM_PROMPT = """Voce e o PAULUS, assistente do escritorio. Responde sobre os
documentos abaixo, em portugues do Brasil, direto e sem preambulo.

O texto abaixo e tudo o que voce tem, e voce tem ele INTEIRO. Leia todos os
documentos antes de responder: a resposta quase sempre esta em algum deles.

Nunca invente clausula, valor, data, nome ou numero de clausula que nao esteja
escrito. Numero de clausula so quando aparecer literalmente no texto. Cite o
nome do arquivo de onde tirou cada informacao.

Voce nao presta consultoria juridica - voce localiza e resume o que esta
escrito nos documentos.

Voce NAO conhece a tela deste programa. Nunca diga onde clicar, nunca cite
botao, menu ou atalho, nunca ensine a usar o sistema. Quem explica a tela e o
proprio programa, que sabe quais botoes existem.

Traga tudo o que a pergunta pede: se ela pedir consequencias, condicoes,
prazos ou uma lista, traga todos os itens que estiverem escritos, e nao so o
primeiro.

Se o documento trata do assunto mas nao traz exatamente o que foi perguntado,
diga isso na primeira frase (por exemplo: "O contrato nao preve multa por
atraso no aluguel.") e so depois diga o que ele traz sobre o assunto.

Papel de uma pessoa (advogado, procurador, representante, parte) vale so como
esta escrito: nunca atribua a uma parte o advogado ou o procurador de outra.

Se, depois de ler todos, a informacao realmente nao estiver em nenhum, diga que
nao achou e diga em quais documentos procurou."""

USER_TEMPLATE = """Documentos do escritorio:

{context}

Pergunta: {question}"""

# Para quem nao esta perguntando sobre o acervo - o editor, por exemplo. Sem o
# cabecalho "Documentos do escritorio", que faz o modelo responder como se
# estivesse citando arquivo.
MOLDE_SIMPLES = """{context}

{question}"""


class OllamaError(RuntimeError):
    pass


def montar_mensagens(question: str, context: str = "", *, sistema: str = "", ensinado: str = "",
                     historico: list[dict] | None = None) -> list[dict]:
    """
    As mensagens do chat de uma pergunta: a instrucao, os pares anteriores e a
    pergunta com o contexto. Fora do `ask` porque o pacote da escrita no
    aparelho (src/aparelho.py) leva as mesmas mensagens que o escritorio
    mandaria ao modelo.
    """
    molde = USER_TEMPLATE if not sistema else MOLDE_SIMPLES
    conteudo = molde.format(context=context, question=question) if context else question
    # `ensinado` e o que o escritorio escreveu em Configuracoes > Aprendizado.
    # Entra no fim da instrucao de sistema, e nao na mensagem do usuario:
    # e regra permanente da casa, nao parte do que foi perguntado agora.
    instrucao = sistema or SYSTEM_PROMPT
    if ensinado.strip():
        instrucao += "\n\n" + ensinado.strip()
    messages = [{"role": "system", "content": instrucao}]
    messages += [m for m in (historico or []) if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": conteudo})
    return messages


class LlamaClient:
    # Quem chama a conversa pergunta isto antes de mandar `tarefa`: o cliente
    # de mentira dos testes nao conhece o argumento, e nao precisa conhecer.
    aceita_tarefa = True

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        *,
        opcoes: inferencia.Opcoes | None = None,
        temperature: float | None = None,
        num_ctx: int | None = None,
        timeout: int = 300,
    ) -> None:
        self.model = model
        self.host = _host_do_ollama(host)
        # As opcoes vem do catalogo (src/inferencia.py); `temperature` e
        # `num_ctx` soltos ficam para quem usa o cliente fora do programa
        # (src/main.py, os testes).
        self.opcoes = replace(opcoes) if opcoes else inferencia.Opcoes()
        if temperature is not None:
            self.opcoes.temperature = temperature
        if num_ctx is not None:
            self.opcoes.num_ctx = num_ctx
        self.timeout = timeout
        # Os numeros da ultima chamada: tokens lidos e escritos, e se o
        # prompt encostou no fim da janela.
        self.ultima: dict = {}

    @property
    def num_ctx(self) -> int:
        return self.opcoes.num_ctx

    @num_ctx.setter
    def num_ctx(self, valor: int) -> None:
        self.opcoes.num_ctx = int(valor)

    @property
    def temperature(self) -> float:
        return self.opcoes.temperature

    # ---------------------------------------------------------------- chat

    def _payload(self, messages: list[dict], *, fmt: str | None, stream: bool, tarefa: str) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": self.opcoes.options(tarefa),
        }
        if self.opcoes.keep_alive:
            payload["keep_alive"] = self.opcoes.keep_alive
        # O modo de pensar gasta a janela e o tempo antes da primeira
        # palavra - e so existe em alguns modelos. So para esses vai a flag.
        if self.opcoes.desligar_pensar and inferencia.pensa(self.host, self.model):
            payload["think"] = False
        if fmt:
            payload["format"] = fmt
        return payload

    def _anotar(self, dado: dict, on_fase: Callable[[str, dict], None] | None = None) -> dict:
        """Guarda os numeros do fim e avisa quando o texto nao coube."""
        lidos = int(dado.get("prompt_eval_count", 0) or 0)
        cortou = inferencia.truncou(lidos, self.num_ctx)
        self.ultima = {"prompt_eval_count": lidos, "eval_count": int(dado.get("eval_count", 0) or 0),
                       "num_ctx": self.num_ctx, "truncou": cortou}
        if cortou:
            # O Ollama corta calado: descarta o comeco do prompt e responde
            # com o resto. Registrado aqui e dito na tela - uma resposta sobre
            # metade do documento nao pode passar por resposta sobre ele todo.
            _log.warning("o prompt encostou no fim da janela: %s de %s tokens (%s)", lidos, self.num_ctx, self.model)
            if on_fase:
                on_fase("truncou", {"tokens_lidos": lidos, "num_ctx": self.num_ctx})
        return self.ultima

    def _chat(
        self,
        messages: list[dict],
        *,
        fmt: str | None = None,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_fase: Callable[[str, dict], None] | None = None,
        parar: Callable[[], bool] | None = None,
        tarefa: str = "",
    ) -> str:
        # F1: toda chamada ao modelo espera a vez na fila unica, de qualquer
        # tela (src/fila_modelo.py). Com a chave desligada, ou com a vez ja na
        # mao (a conversa), passa direto, como antes.
        import fila_modelo

        try:
            with fila_modelo.vez_para_o_modelo(parar=parar):
                return self._chat_na_vez(messages, fmt=fmt, stream=stream, on_token=on_token, on_fase=on_fase,
                                         parar=parar, tarefa=tarefa)
        except fila_modelo.Parado:
            return ""

    def _chat_na_vez(
        self,
        messages: list[dict],
        *,
        fmt: str | None = None,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_fase: Callable[[str, dict], None] | None = None,
        parar: Callable[[], bool] | None = None,
        tarefa: str = "",
    ) -> str:
        payload = self._payload(messages, fmt=fmt, stream=stream, tarefa=tarefa)

        # O relogio comeca aqui, antes do POST. Com stream=True o requests so
        # retorna quando o Ollama manda o primeiro pedaco - e o Ollama so manda
        # depois de carregar o modelo e ler o prompt. Comecando a contar depois
        # da chamada, os nove segundos de espera ficavam fora da conta e a tela
        # dizia "terminou de ler em menos de 0,1 s" apos nove segundos parada.
        import time

        comeco = time.time()

        try:
            resp = requests.post(
                f"{self.host}/api/chat", json=payload, stream=stream, timeout=self.timeout
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Nao consegui conectar em {self.host}. O Ollama esta rodando? (`ollama serve`)"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                f"Timeout de {self.timeout}s. Em CPU, modelos grandes demoram - "
                "tente um modelo menor ou reduza o numero de trechos (--top)."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            detalhe = ""
            try:
                detalhe = resp.json().get("error", "")
            except Exception:
                detalhe = resp.text[:200]
            raise OllamaError(f"Ollama retornou erro: {detalhe or exc}") from exc

        if not stream:
            dado = resp.json()
            self._anotar(dado, on_fase)
            return dado.get("message", {}).get("content", "").strip()

        # As duas fases tem nomes e tempos diferentes, e quem olha a tela
        # precisa saber em qual esta. LER o prompt inteiro e o silencio longo -
        # o Ollama nao emite nada ate a primeira palavra. ESCREVER comeca no
        # primeiro token e da para acompanhar palavra a palavra.
        primeiro_token = 0.0
        partes: list[str] = []

        for linha in resp.iter_lines(decode_unicode=True):
            # A pessoa apertou parar: fechar a conexao e o que faz o Ollama
            # largar a geracao - ele cancela quando o cliente vai embora. O que
            # ja foi escrito volta, e quem chamou decide o que fazer com ele.
            if parar and parar():
                resp.close()
                break
            if not linha:
                continue
            try:
                dado = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if dado.get("error"):
                raise OllamaError(dado["error"])
            token = dado.get("message", {}).get("content", "")
            if token:
                if not primeiro_token:
                    primeiro_token = time.time()
                    if on_fase:
                        on_fase("escrevendo", {"lendo_segundos": round(primeiro_token - comeco, 1)})
                partes.append(token)
                if on_token:
                    on_token(token)
            if dado.get("done"):
                numeros = self._anotar(dado, on_fase)
                if on_fase:
                    fim = time.time()
                    # Os tempos vem do proprio Ollama, em nanossegundos. O
                    # relogio daqui mede a espera; o dele mede o trabalho, e os
                    # dois divergem quando o prompt ja esta em cache: 7.092
                    # tokens "lidos em 0 s" nao e um numero, e um artefato.
                    lendo = dado.get("prompt_eval_duration", 0) / 1e9
                    escrevendo = dado.get("eval_duration", 0) / 1e9
                    espera = (primeiro_token or fim) - comeco
                    on_fase("medida", {
                        "lendo_segundos": round(lendo or espera, 1),
                        "escrevendo_segundos": round(escrevendo or (fim - (primeiro_token or fim)), 1),
                        "esperou_segundos": round(espera, 1),
                        # Prompt repetido: o Ollama reaproveita o que ja
                        # calculou, e a leitura sai de graca. Dizer isso e
                        # melhor que mostrar um tempo que nao aconteceu.
                        "do_cache": bool(lendo and espera and lendo < espera / 3),
                        "tokens_lidos": dado.get("prompt_eval_count", 0),
                        "tokens_escritos": dado.get("eval_count", 0),
                        "num_ctx": self.num_ctx,
                        "truncou": numeros["truncou"],
                    })
                break
        return "".join(partes).strip()

    # ------------------------------------------------------------ publico

    def ask(
        self,
        question: str,
        context: str = "",
        *,
        sistema: str = "",
        ensinado: str = "",
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_fase: Callable[[str, dict], None] | None = None,
        parar: Callable[[], bool] | None = None,
        tarefa: str = "",
        historico: list[dict] | None = None,
    ) -> str:
        """
        Pergunta com contexto de contratos.

        `historico` sao os pares anteriores da conversa, como mensagens do
        chat (src/memoria.py): vao entre a instrucao e a pergunta de agora.

        `tarefa` escolhe o teto de resposta (src/inferencia.py): "conversa"
        para a pergunta sobre documentos. Sem tarefa, sem teto - o editor e
        os resumos escrevem o quanto o texto pedir.

        `sistema` troca a instrucao de sistema para quem nao esta perguntando
        sobre o acervo. Sem isso, o editor pedia "devolva APENAS o texto" numa
        mensagem de usuario enquanto o sistema mandava "cite o nome do arquivo
        de onde tirou a informacao" - duas ordens opostas, e o modelo obedecia
        as duas: a sugestao vinha com "Arquivo: contrato.txt" na frente, e o
        nome do arquivo era inventado.
        """
        messages = montar_mensagens(question, context, sistema=sistema, ensinado=ensinado, historico=historico)
        # `parar` so vai quando existe: quem troca o `_chat` num teste nao
        # precisa conhecer o argumento.
        extra = {"parar": parar} if parar else {}
        if tarefa:
            extra["tarefa"] = tarefa
        return self._chat(messages, stream=stream, on_token=on_token, on_fase=on_fase, **extra)

    def ask_json(self, instruction: str, context: str = "", schema_hint: str = "",
                 sistema: str = "") -> dict | list | None:
        """
        Extracao estruturada. Usado a partir da Semana 2 (vencimentos -> Excel).
        Retorna None se o modelo nao produzir JSON valido.

        `sistema` troca a instrucao de sistema: o contrato das ferramentas nao
        e o de ler contratos.
        """
        prompt = instruction
        if schema_hint:
            prompt += f"\n\nResponda APENAS com JSON neste formato:\n{schema_hint}"
        if context:
            prompt = f"Trechos de contratos:\n\n{context}\n\n{prompt}"

        messages = [
            {"role": "system", "content": sistema or SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        bruto = self._chat(messages, fmt="json", tarefa="json")
        try:
            return json.loads(bruto)
        except json.JSONDecodeError:
            inicio = min(
                (i for i in (bruto.find("{"), bruto.find("[")) if i != -1), default=-1
            )
            fim = max(bruto.rfind("}"), bruto.rfind("]"))
            if inicio != -1 and fim > inicio:
                try:
                    return json.loads(bruto[inicio : fim + 1])
                except json.JSONDecodeError:
                    return None
            return None

    # ------------------------------------------------------------- saude

    def list_models(self) -> list[str]:
        resp = requests.get(f"{self.host}/api/tags", timeout=10)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    def digest(self, model: str = "") -> str:
        """
        A impressao digital do modelo instalado - o sha256 que o Ollama guarda.

        Serve para saber que o modelo MUDOU. "llama3.2:3b" hoje e "llama3.2:3b"
        depois de um `ollama pull` sao o mesmo nome e podem ser pesos
        diferentes; sem o digest, o metadata extraido pelo modelo antigo
        passaria por atual para sempre. Devolve vazio quando nao da para
        perguntar: nao saber o digest nao pode impedir nada de rodar.
        """
        alvo = model or self.model
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
            for instalado in resp.json().get("models", []):
                if instalado.get("name") == alvo or instalado.get("model") == alvo:
                    return str(instalado.get("digest", ""))[:24]
        except Exception:
            return ""
        return ""


def check_ollama(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> tuple[bool, str]:
    """Valida servidor + presenca do modelo. Retorna (ok, mensagem)."""
    host = _host_do_ollama(host)
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return False, (
            f"Ollama nao respondeu em {host}.\n"
            "  1. Instale: https://ollama.ai/download\n"
            "  2. Rode: ollama serve"
        )

    disponiveis = [m["name"] for m in resp.json().get("models", [])]
    if not disponiveis:
        return False, f"Ollama esta rodando, mas sem modelos. Rode: ollama pull {model}"

    if model not in disponiveis:
        return False, (
            f"Modelo '{model}' nao encontrado.\n"
            f"  Disponiveis: {', '.join(disponiveis)}\n"
            f"  Baixe com: ollama pull {model}\n"
            f"  Ou use outro: python src/main.py --model {disponiveis[0]}"
        )

    return True, f"Ollama OK - modelo '{model}'"
