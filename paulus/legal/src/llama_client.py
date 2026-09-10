"""
PAULUS Legal - Cliente Ollama.

Fala com o servidor local do Ollama (http://localhost:11434). Nenhum dado sai
da maquina.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

import requests

DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("PAULUS_MODEL", "llama3.2:3b")

SYSTEM_PROMPT = """Voce e o PAULUS, um assistente juridico que analisa contratos.

Regras obrigatorias:
1. Responda SOMENTE com base nos trechos de contrato fornecidos. Nunca invente
   clausulas, valores, datas ou nomes.
2. Sempre cite o nome do arquivo de onde tirou cada informacao.
3. Se a resposta nao estiver nos trechos, diga exatamente: "Nao encontrei essa
   informacao nos trechos fornecidos." Nao chute.
4. Cite o numero da clausula APENAS quando ele aparecer literalmente no
   trecho. Nunca deduza nem invente numeracao de clausula.
5. Cada contrato aparece uma unica vez no contexto, sob o cabecalho
   "--- nome_do_arquivo ---". Nao repita o mesmo contrato em secoes separadas.
6. Responda em portugues do Brasil, de forma direta e objetiva.
7. Voce nao presta consultoria juridica - voce resume e localiza o que esta
   escrito nos documentos."""

USER_TEMPLATE = """Trechos de contratos:

{context}

Pergunta: {question}"""


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
        self.host = host.rstrip("/")
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
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if fmt:
            payload["format"] = fmt

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

        partes: list[str] = []
        for linha in resp.iter_lines(decode_unicode=True):
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
                partes.append(token)
                if on_token:
                    on_token(token)
            if dado.get("done"):
                break
        return "".join(partes).strip()

    # ------------------------------------------------------------ publico

    def ask(
        self,
        question: str,
        context: str = "",
        *,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Pergunta com contexto de contratos."""
        conteudo = (
            USER_TEMPLATE.format(context=context, question=question)
            if context
            else question
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": conteudo},
        ]
        return self._chat(messages, stream=stream, on_token=on_token)

    def ask_json(self, instruction: str, context: str = "", schema_hint: str = "") -> dict | list | None:
        """
        Extracao estruturada. Usado a partir da Semana 2 (vencimentos -> Excel).
        Retorna None se o modelo nao produzir JSON valido.
        """
        prompt = instruction
        if schema_hint:
            prompt += f"\n\nResponda APENAS com JSON neste formato:\n{schema_hint}"
        if context:
            prompt = f"Trechos de contratos:\n\n{context}\n\n{prompt}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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


def check_ollama(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> tuple[bool, str]:
    """Valida servidor + presenca do modelo. Retorna (ok, mensagem)."""
    host = host.rstrip("/")
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
