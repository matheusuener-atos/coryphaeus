"""
Ponte de medição: o LiteRT-LM (Google AI Edge) falando a língua do Ollama.

Para comparar motores sem mudar uma linha do PAULUS. A ponte escuta numa porta
própria e atende o que o produto pede ao Ollama para escrever e julgar:

- /api/chat - conversa, com ou sem streaming, `format` "json" ou esquema
  (geração restringida pelo LLGuidance do LiteRT-LM) e o pedido do juiz
  (`logprobs` + `num_predict: 1`), respondido pela nota de cada letra
  (`run_text_scoring`) em vez do palpite de um token;
- /api/show e /api/tags - o modelo da ponte aparece na lista;
- o resto (/api/embed, /api/ps, /api/pull...) vai ao Ollama de verdade. A busca
  continua com o bge-m3: só muda quem escreve.

Não é produto. Roda com o Python de uma venv onde está o `litert-lm`:

    <venv-litert>\\Scripts\\python.exe tools\\litert_ponte.py --modelo gemma-4-E2B-it.litertlm
    set OLLAMA_HOST=http://127.0.0.1:11435
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --tudo --modelo gemma4-e2b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import litert_lm as lm

OLLAMA = "http://127.0.0.1:11434"


class Motor:
    """Um modelo carregado e uma chamada por vez, como a fila do PAULUS."""

    def __init__(self, caminho: str, nome: str, backend: str, janela: int) -> None:
        self.nome = nome
        self.janela = janela
        comeco = time.time()
        self.engine = lm.Engine(caminho, backend=lm.Backend.GPU() if backend == "gpu" else lm.Backend.CPU(),
                                max_num_tokens=janela)
        self.carregou_em = time.time() - comeco
        self.vez = threading.Lock()
        print(f"[ponte] {nome} carregado em {self.carregou_em:.1f} s ({backend}, janela {janela})", flush=True)

    def contar(self, texto: str) -> int:
        try:
            return len(self.engine.tokenize(texto))
        except Exception:
            return len(texto) // 4

    @staticmethod
    def _separar(mensagens: list[dict]) -> tuple[str, list[dict], str]:
        sistema = "\n\n".join(m.get("content", "") for m in mensagens if m.get("role") == "system")
        resto = [m for m in mensagens if m.get("role") != "system"]
        ultima = resto[-1]["content"] if resto else ""
        historia = [{"role": m["role"], "content": m.get("content", "")} for m in resto[:-1]]
        return sistema, historia, ultima

    def conversa(self, mensagens: list[dict], opcoes: dict, formato):
        """Gera a resposta em pedaços (texto) e devolve os números no fim."""
        sistema, historia, ultima = self._separar(mensagens)
        temperatura = float(opcoes.get("temperature", 0.2) or 0)
        amostra = lm.SamplerConfig(temperature=temperatura, top_k=1 if temperatura == 0 else 40,
                                   top_p=1.0 if temperatura == 0 else 0.95, seed=int(opcoes.get("seed", 7) or 7))
        restringir = None
        resposta = None
        if formato:
            restringir = lm.ConstrainedDecodingConfig(enable=True, provider=lm.LiteRtLmConstraintProviderType.LL_GUIDANCE)
            resposta = lm.ResponseFormat.json(formato if isinstance(formato, dict) else {"type": "object"})
        maximo = int(opcoes.get("num_predict", 0) or 0)
        if maximo <= 0:
            maximo = None
        conversa = self.engine.create_conversation(
            messages=historia or None, system_message=sistema or None, sampler_config=amostra,
            constrained_decoding_config=restringir, max_output_tokens=maximo,
            thinking_config=lm.ThinkingConfig(enable_thinking=False))
        try:
            for msg in conversa.send_message_async(ultima, response_format=resposta,
                                                   thinking_config=lm.ThinkingConfig(enable_thinking=False)):
                texto = str(msg.contents)
                if texto:
                    yield texto
        finally:
            conversa.close()

    def notas_das_letras(self, mensagens: list[dict]) -> list[dict]:
        """
        A nota de cada letra como primeira palavra da resposta.

        O Ollama devolve o palpite de um token e as 20 alternativas; aqui cada
        letra candidata é pontuada inteira (log-verossimilhança), e a lista
        sai no formato `top_logprobs` que o juizo.py já lê.
        """
        sistema, historia, ultima = self._separar(mensagens)
        conversa = self.engine.create_conversation(messages=historia or None, system_message=sistema or None)
        try:
            prompt = conversa.render_message_to_string({"role": "user", "content": ultima})
        finally:
            conversa.close()
        # Só as letras que o juizo.py pôs no bloco "OPÇÕES:" - cada uma custa
        # uma leitura do prompt (a 0.18.1 aceita um alvo por chamada e ainda
        # não tem Session.clone).
        bloco = ultima.split("OPÇÕES:", 1)[-1]
        letras = re.findall(r"^([A-Z])\) ", bloco, flags=re.M) or list("AB")
        notas = []
        for letra in letras:
            sessao = self.engine.create_session(apply_prompt_template=False)
            try:
                sessao.run_prefill([prompt])
                notas.append((letra, float(sessao.run_text_scoring([letra]).scores[0])))
            finally:
                sessao.close()
        return [{"token": l, "logprob": n} for l, n in notas]


MOTOR: Motor | None = None


def _ollama(metodo: str, caminho: str, corpo: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(OLLAMA + caminho, data=corpo, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # Ollama fora do ar
        return 502, json.dumps({"error": str(e)}).encode()


class Atendente(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a) -> None:  # o terminal fica para a medida
        pass

    def _json(self, status: int, dado) -> None:
        corpo = dado if isinstance(dado, bytes) else json.dumps(dado, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self) -> None:
        if self.path.startswith("/api/tags"):
            status, bruto = _ollama("GET", "/api/tags", None)
            dado = json.loads(bruto or b"{}") if status == 200 else {"models": []}
            dado.setdefault("models", []).insert(0, {"name": MOTOR.nome, "model": MOTOR.nome, "size": 0,
                                                     "details": {"format": "litertlm", "family": "gemma"}})
            return self._json(200, dado)
        if self.path.startswith("/api/version"):
            return self._json(200, {"version": "0.0.0-litert-ponte"})
        status, bruto = _ollama("GET", self.path, None)
        self._json(status, bruto)

    def do_POST(self) -> None:
        bruto = self._corpo()
        try:
            pedido = json.loads(bruto or b"{}")
        except json.JSONDecodeError:
            pedido = {}
        if pedido.get("model") != MOTOR.nome:
            status, resposta = _ollama("POST", self.path, bruto)
            return self._json(status, resposta)
        if self.path.startswith("/api/show"):
            return self._json(200, {"capabilities": ["completion"], "details": {"family": "gemma"},
                                    "model_info": {"general.context_length": MOTOR.janela}})
        if self.path.startswith("/api/chat"):
            return self._chat(pedido)
        if self.path.startswith("/api/generate"):
            pedido["messages"] = [{"role": "user", "content": pedido.get("prompt", "")}]
            return self._chat(pedido, gerar=True)
        self._json(404, {"error": f"a ponte não atende {self.path}"})

    def _chat(self, pedido: dict, gerar: bool = False) -> None:
        mensagens = pedido.get("messages") or []
        opcoes = pedido.get("options") or {}
        lidos = MOTOR.contar("\n".join(str(m.get("content", "")) for m in mensagens))
        chave = "response" if gerar else "message"

        def pedaco(texto: str) -> dict:
            return {"model": MOTOR.nome, chave: texto} if gerar else \
                {"model": MOTOR.nome, "message": {"role": "assistant", "content": texto}}

        with MOTOR.vez:
            comeco = time.time()
            if pedido.get("logprobs") and int(opcoes.get("num_predict", 0) or 0) == 1:
                notas = MOTOR.notas_das_letras(mensagens)
                melhor = max(notas, key=lambda n: n["logprob"])
                total = time.time() - comeco
                return self._json(200, {**pedaco(melhor["token"]), "done": True,
                                        "logprobs": [{"token": melhor["token"], "logprob": melhor["logprob"],
                                                      "top_logprobs": notas}],
                                        "prompt_eval_count": lidos, "eval_count": 1,
                                        "prompt_eval_duration": int(total * 1e9), "eval_duration": 0})
            fluxo = pedido.get("stream", True)
            if not fluxo:
                texto = "".join(MOTOR.conversa(mensagens, opcoes, pedido.get("format")))
                total = time.time() - comeco
                return self._json(200, {**pedaco(texto), "done": True, "prompt_eval_count": lidos,
                                        "eval_count": MOTOR.contar(texto), "total_duration": int(total * 1e9)})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def mandar(dado: dict) -> None:
                linha = (json.dumps(dado, ensure_ascii=False) + "\n").encode()
                self.wfile.write(f"{len(linha):X}\r\n".encode() + linha + b"\r\n")
                self.wfile.flush()

            primeiro = 0.0
            partes: list[str] = []
            try:
                for texto in MOTOR.conversa(mensagens, opcoes, pedido.get("format")):
                    primeiro = primeiro or time.time()
                    partes.append(texto)
                    mandar({**pedaco(texto), "done": False})
                fim = time.time()
                mandar({**pedaco(""), "done": True, "prompt_eval_count": lidos,
                        "eval_count": MOTOR.contar("".join(partes)),
                        "prompt_eval_duration": int(((primeiro or fim) - comeco) * 1e9),
                        "eval_duration": int((fim - (primeiro or fim)) * 1e9)})
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass  # quem pediu apertou parar


def main() -> None:
    global MOTOR
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", required=True, help="arquivo .litertlm")
    p.add_argument("--nome", default="gemma4-e2b")
    p.add_argument("--backend", default="cpu", choices=["cpu", "gpu"])
    p.add_argument("--janela", type=int, default=8192)
    p.add_argument("--porta", type=int, default=11435)
    a = p.parse_args()
    lm.set_min_log_severity(lm.LogSeverity.ERROR)
    MOTOR = Motor(a.modelo, a.nome, a.backend, a.janela)
    servidor = ThreadingHTTPServer(("127.0.0.1", a.porta), Atendente)
    print(f"[ponte] escutando em http://127.0.0.1:{a.porta}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
