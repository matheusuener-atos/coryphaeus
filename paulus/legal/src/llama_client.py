"""
PAULUS Legal - Cliente Ollama.

Fala com o servidor local do Ollama (http://127.0.0.1:11434). Nenhum dado sai
da maquina.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

import requests


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

# A janela do modelo não pode ser menor que o acervo que ele precisa ler.
# Medido nesta máquina: com 6.000 caracteres o modelo respondeu "não encontrei
# os nomes" sobre quatro procurações; com os 21.382 do acervo inteiro, acertou
# os quatro. O preço foi 56 s virarem 95 s — resposta rápida e errada sobre um
# contrato não vale nada.
JANELA_MINIMA = 8192

# Teto para a memória não estourar: a janela é alocada quando o modelo carrega,
# e o computador do escritório também roda o resto do trabalho.
JANELA_MAXIMA = 32768


def janela_para(caracteres: int, reserva_tokens: int = 1200) -> int:
    """
    A janela que um acervo deste tamanho pede, arredondada para cima.

    Potência de dois porque é o que estes runtimes alocam bem. Acervo grande
    demais não estica a janela até o infinito: passa do teto, e aí quem
    escolhe o que ler é a busca.
    """
    precisa = caracteres // 3 + reserva_tokens
    janela = JANELA_MINIMA
    while janela < precisa and janela < JANELA_MAXIMA:
        janela *= 2
    return min(janela, JANELA_MAXIMA)

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


class LlamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        *,
        temperature: float = 0.1,
        num_ctx: int = 8192,
        timeout: int = 300,
    ) -> None:
        self.model = model
        self.host = _host_do_ollama(host)
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout

    # ---------------------------------------------------------------- chat

    def _chat(
        self,
        messages: list[dict],
        *,
        fmt: str | None = None,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_fase: Callable[[str, dict], None] | None = None,
        parar: Callable[[], bool] | None = None,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if fmt:
            payload["format"] = fmt

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
            return resp.json().get("message", {}).get("content", "").strip()

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
    ) -> str:
        """
        Pergunta com contexto de contratos.

        `sistema` troca a instrucao de sistema para quem nao esta perguntando
        sobre o acervo. Sem isso, o editor pedia "devolva APENAS o texto" numa
        mensagem de usuario enquanto o sistema mandava "cite o nome do arquivo
        de onde tirou a informacao" - duas ordens opostas, e o modelo obedecia
        as duas: a sugestao vinha com "Arquivo: contrato.txt" na frente, e o
        nome do arquivo era inventado.
        """
        molde = USER_TEMPLATE if not sistema else MOLDE_SIMPLES
        conteudo = molde.format(context=context, question=question) if context else question
        # `ensinado` e o que o escritorio escreveu em Configuracoes > Aprendizado.
        # Entra no fim da instrucao de sistema, e nao na mensagem do usuario:
        # e regra permanente da casa, nao parte do que foi perguntado agora.
        instrucao = sistema or SYSTEM_PROMPT
        if ensinado.strip():
            instrucao += "\n\n" + ensinado.strip()
        messages = [
            {"role": "system", "content": instrucao},
            {"role": "user", "content": conteudo},
        ]
        # `parar` so vai quando existe: quem troca o `_chat` num teste nao
        # precisa conhecer o argumento.
        extra = {"parar": parar} if parar else {}
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
        bruto = self._chat(messages, fmt="json")
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
