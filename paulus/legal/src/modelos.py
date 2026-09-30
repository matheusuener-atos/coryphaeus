"""
Os modelos do PAULUS: baixar, trocar, medir e delegar tarefas.

O motor continua sendo o Ollama, local e de graça. O que é do PAULUS é esta
camada por cima dele:

- **Catálogo.** Uma lista curta de modelos que rodam em computador de
  escritório, com o tamanho lido do registro do Ollama na hora (não um número
  decorado que envelhece). Qualquer outro nome do Ollama também pode ser
  baixado.
- **Download pela tela.** A API do Ollama (`/api/pull`) manda o andamento em
  bytes; a tela mostra a barra de verdade e dá para cancelar. Um de cada vez.
- **Remover.** Menos o padrão: sem ele a conversa para.
- **Medir nesta máquina.** Uma resposta curta e fixa, e o próprio Ollama diz
  quantas palavras por segundo saíram e quanto levou para carregar. É o número
  que decide qual modelo vai para qual tarefa - não a fama do modelo.
- **Delegar.** Cada tarefa do programa (a conversa, os julgamentos de uma
  letra, o e-mail, a redação, os resumos, a leitura do acervo) pode ir para um
  modelo diferente. Sem escolha, vai para o padrão. Modelo delegado que foi
  removido volta para o padrão, sem erro.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

# As tarefas do programa que usam modelo, na ordem em que aparecem na tela.
TAREFAS = [
    ("conversa", "Perguntas sobre documentos", "a resposta da conversa, lendo o Acervo"),
    ("juiz", "Julgamentos rápidos", "decisões de uma palavra, como \"é pergunta sobre o programa ou sobre um documento?\""),
    ("email", "E-mail", "rascunho de resposta, o Contexto IA e o resumo da caixa"),
    ("redacao", "Redação", "o assistente do editor, a fórmula da planilha e a reescrita de e-mail"),
    ("resumos", "Resumos", "gravações, serviços e o parecer do Financeiro"),
    ("leitura", "Leitura do Acervo", "classificar e ler os documentos quando eles entram"),
]
IDS_TAREFAS = [t[0] for t in TAREFAS]

# Modelos que rodam num computador de escritório sem placa de vídeo. O papel
# diz para que servem AQUI; a medida real vem de medir().
#
# `parametros` e `quantizacao` são os da etiqueta padrão de cada um no
# registro do Ollama, e `gb_aprox` o tamanho dela: servem para estimar o tempo
# ANTES de baixar (src/maquina.py). O tamanho de verdade vem do registro quando
# há internet; instalado, vale o que o Ollama diz.
CATALOGO = [
    {"nome": "llama3.2:3b", "papel": "O padrão: equilibra qualidade e tempo num computador sem placa de vídeo.",
     "parametros": "3.2B", "quantizacao": "Q4_K_M", "gb_aprox": 2.0},
    {"nome": "llama3.2:1b", "papel": "O mais leve: pensado para os julgamentos rápidos. Para ler documentos, meça antes.",
     "parametros": "1.2B", "quantizacao": "Q8_0", "gb_aprox": 1.3},
    {"nome": "qwen2.5:3b", "papel": "Do tamanho do padrão, de outra família: vale medir e comparar.",
     "parametros": "3.1B", "quantizacao": "Q4_K_M", "gb_aprox": 1.9},
    {"nome": "gemma2:2b", "papel": "Leve, de outra família: alternativa para e-mail e resumos.",
     "parametros": "2.6B", "quantizacao": "Q4_0", "gb_aprox": 1.6},
    {"nome": "qwen2.5:7b", "papel": "Maior: lê melhor e demora mais. Pede 16 GB de memória.",
     "parametros": "7.6B", "quantizacao": "Q4_K_M", "gb_aprox": 4.7},
    {"nome": "llama3.1:8b", "papel": "Maior: lê melhor e demora mais. Pede 16 GB; com placa de vídeo fica rápido.",
     "parametros": "8.0B", "quantizacao": "Q4_K_M", "gb_aprox": 4.9},
]

# Quanto cada modelo acertou no nosso banco de provas (tools/demo/roteiro.py
# --tudo): perguntas com resposta conhecida sobre o escritório de
# demonstração - fato, lista, ausência, consequência, material de consulta.
# Não depende da máquina: o mesmo modelo responde igual em qualquer
# computador. Modelo fora daqui não tem nota, e não é recomendado.
QUALIDADE = {
    "llama3.2:3b": {"certas": 41, "total": 41, "quando": "2026-09-27"},
    "llama3.2:3b-instruct-q8_0": {"certas": 36, "total": 36, "quando": "2026-09-27"},
    # Rápido (escreve 26 e lê 98 tokens/s onde o 3b faz 11 e 60), mas
    # respondia "não achei" com a resposta no texto: 10 de 29 nos documentos.
    "llama3.2:1b": {"certas": 22, "total": 41, "quando": "2026-09-27"},
}

RE_NOME = re.compile(r"^[a-z0-9][a-z0-9._:/-]{1,100}$")
REGISTRO = "https://registry.ollama.ai/v2"
PROMPT_DA_MEDIDA = "Em uma frase curta, em português: o que é uma procuração?"
# O que o modelo lê antes de responder, na medida: umas mil e quinhentas
# unidades de texto, o tamanho de um contrato curto. Ler é a espera longa da
# primeira pergunta sobre um documento; sem medir, a estimativa só sabia
# escrever.
_CLAUSULA = (
    "CLÁUSULA {n}. O CONTRATANTE pagará ao CONTRATADO o valor mensal ajustado até o quinto dia útil de cada "
    "mês, mediante boleto ou transferência, sob pena de multa de dois por cento e juros de um por cento ao mês. "
    "O atraso superior a trinta dias autoriza a suspensão dos serviços, com aviso prévio por escrito, sem "
    "prejuízo da cobrança do que for devido. As partes elegem o foro da comarca do local da prestação.\n"
)
TEXTO_DA_MEDIDA = "".join(_CLAUSULA.format(n=n) for n in range(1, 15))


def nome_valido(nome: str) -> bool:
    return bool(RE_NOME.match((nome or "").strip().lower()))


def _gb(bytes_: int) -> float:
    return round((bytes_ or 0) / 1e9, 2)


# ------------------------------------------------------------ registro

_tamanhos: dict[str, float | None] = {}


def tamanho_no_registro(nome: str, timeout: float = 4.0) -> float | None:
    """O tamanho do download, em GB, somando as camadas do manifesto. None: não deu para saber."""
    if nome in _tamanhos:
        return _tamanhos[nome]
    base, _, tag = nome.partition(":")
    caminho = base if "/" in base else "library/" + base
    try:
        r = requests.get(f"{REGISTRO}/{caminho}/manifests/{tag or 'latest'}", timeout=timeout,
                         headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
        r.raise_for_status()
        valor = _gb(sum(int(c.get("size", 0)) for c in r.json().get("layers", [])))
    except (requests.RequestException, ValueError):
        return None  # sem internet: não guarda, tenta de novo depois
    _tamanhos[nome] = valor
    return valor


def tamanhos_do_catalogo() -> dict[str, float | None]:
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(zip([m["nome"] for m in CATALOGO], pool.map(tamanho_no_registro, [m["nome"] for m in CATALOGO])))


# ------------------------------------------------------------- ollama

def instalados(host: str) -> list[dict]:
    """Os modelos que o Ollama tem, com tamanho e o que ele diz deles."""
    r = requests.get(f"{host}/api/tags", timeout=5)
    r.raise_for_status()
    saida = []
    for m in r.json().get("models", []):
        det = m.get("details") or {}
        saida.append({
            "nome": m.get("name", ""),
            "gb": _gb(m.get("size", 0)),
            "parametros": det.get("parameter_size", ""),
            "quantizacao": det.get("quantization_level", ""),
            "familia": det.get("family", ""),
        })
    return sorted(saida, key=lambda x: x["gb"])


def remover(host: str, nome: str) -> None:
    r = requests.delete(f"{host}/api/delete", json={"model": nome}, timeout=30)
    if r.status_code == 404:
        raise ValueError("esse modelo não está instalado")
    r.raise_for_status()


def medir(host: str, nome: str, timeout: int = 300) -> dict:
    """
    Um texto fixo para ler e uma resposta curta para escrever; o Ollama
    devolve os tempos de cada parte. Carregar é a primeira espera (o modelo sai
    do disco para a memória); ler é o que pesa na primeira pergunta sobre um
    documento; escrever é o ritmo da resposta.

    A marca no começo muda a cada medida: o Ollama guarda o começo do último
    texto lido, e medir de novo leria em meio segundo o que não foi lido.
    """
    import fila_modelo

    prompt = f"[medida {time.time_ns()}]\n{TEXTO_DA_MEDIDA}\n\n{PROMPT_DA_MEDIDA}"
    # F1: a medida espera a vez como qualquer chamada - e sai mais certa, sem
    # outra resposta dividindo o processador.
    with fila_modelo.vez_para_o_modelo():
        comeco = time.time()
        r = requests.post(f"{host}/api/generate", timeout=timeout, json={
            "model": nome, "prompt": prompt, "stream": False,
            "options": {"temperature": 0, "num_predict": 60, "num_ctx": 4096},
        })
    r.raise_for_status()
    d = r.json()
    escreveu = (d.get("eval_duration") or 0) / 1e9
    leu = (d.get("prompt_eval_duration") or 0) / 1e9
    # Com o modelo ainda carregado: quanto dele o Ollama pôs na placa de vídeo.
    # É isto, e não a lista de placas, que diz se a placa é usada aqui.
    import maquina

    fracao = maquina.na_placa(host, nome)
    return {
        **({"na_placa": fracao} if fracao is not None else {}),
        "tokens_por_segundo": round((d.get("eval_count") or 0) / escreveu, 1) if escreveu else 0.0,
        "leitura_tokens_por_segundo": round((d.get("prompt_eval_count") or 0) / leu, 1) if leu else 0.0,
        "tokens_lidos": d.get("prompt_eval_count") or 0,
        "carregar_s": round((d.get("load_duration") or 0) / 1e9, 1),
        "total_s": round(time.time() - comeco, 1),
        "quando": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ----------------------------------------------------------- download

class Baixador:
    """
    Um download por vez, pela API do Ollama, com o andamento em bytes.

    O Ollama manda uma linha por atualização: {"status", "digest", "total",
    "completed"} para cada camada, e {"status": "success"} no fim. Cancelar
    fecha a conexão - o Ollama guarda o que já veio, e baixar de novo continua
    de onde parou.
    """

    def __init__(self, host_de, postar=None) -> None:
        self._host_de = host_de
        self._postar = postar or requests.post
        self._cancelar = threading.Event()
        self.estado: dict = {"andando": False}

    def andamento(self) -> dict:
        return dict(self.estado)

    def iniciar(self, nome: str, ao_terminar=None) -> dict:
        nome = (nome or "").strip()
        if not nome_valido(nome):
            raise ValueError("nome de modelo inválido")
        if self.estado.get("andando"):
            raise RuntimeError("já estou baixando " + self.estado.get("modelo", "outro modelo") + " - espere ou cancele")
        self._cancelar.clear()
        self.estado = {"modelo": nome, "andando": True, "progresso": 0, "baixado_gb": 0.0, "total_gb": 0.0,
                       "fase": "começando", "erro": "", "pronto": False, "cancelado": False}
        threading.Thread(target=self._baixar, args=(nome, ao_terminar), name="modelo-pull", daemon=True).start()
        return self.andamento()

    def cancelar(self) -> dict:
        if self.estado.get("andando"):
            self._cancelar.set()
        return self.andamento()

    def _baixar(self, nome: str, ao_terminar) -> None:
        e = self.estado
        totais: dict[str, int] = {}
        feitos: dict[str, int] = {}
        try:
            r = self._postar(f"{self._host_de()}/api/pull", json={"model": nome, "stream": True},
                             stream=True, timeout=(10, 120))
            r.raise_for_status()
            for linha in r.iter_lines(decode_unicode=True):
                if self._cancelar.is_set():
                    r.close()
                    e.update(cancelado=True, fase="cancelado")
                    return
                if not linha:
                    continue
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if d.get("error"):
                    raise RuntimeError(d["error"])
                status = str(d.get("status", ""))
                if d.get("digest") and d.get("total"):
                    totais[d["digest"]] = int(d["total"])
                    feitos[d["digest"]] = int(d.get("completed") or 0)
                    total = sum(totais.values())
                    feito = sum(feitos.values())
                    e.update(fase="baixando", total_gb=_gb(total), baixado_gb=_gb(feito),
                             progresso=int(feito * 100 / total) if total else 0)
                elif status:
                    e["fase"] = {"pulling manifest": "lendo o registro", "verifying sha256 digest": "conferindo",
                                 "writing manifest": "gravando", "success": "pronto"}.get(status, e.get("fase", ""))
                if status == "success":
                    e.update(pronto=True, progresso=100)
            if not e.get("pronto") and not e.get("cancelado"):
                raise RuntimeError("o download terminou sem o Ollama confirmar")
            if ao_terminar:
                ao_terminar(nome)
        except requests.HTTPError as exc:
            detalhe = ""
            try:
                detalhe = exc.response.json().get("error", "")
            except Exception:  # noqa: BLE001
                pass
            e["erro"] = _erro_legivel(detalhe or str(exc))
        except requests.RequestException as exc:
            e["erro"] = "não consegui falar com o Ollama ou com o registro: " + str(exc)[:120]
        except Exception as exc:  # noqa: BLE001 - o erro vai para a tela
            e["erro"] = _erro_legivel(str(exc))
        finally:
            e["andando"] = False


def _erro_legivel(texto: str) -> str:
    t = texto.lower()
    if "file does not exist" in t or "not found" in t or "manifest unknown" in t:
        return "esse modelo não existe no registro do Ollama - confira o nome"
    if "no space" in t or "disk" in t:
        return "falta espaço em disco para esse modelo"
    return texto[:200]


# ---------------------------------------------------------- delegação

def modelo_da_tarefa(tarefa: str, delegados: dict, padrao: str, presentes: set[str] | None) -> str:
    """
    O modelo que faz a tarefa: o delegado, se ainda estiver instalado; senão
    o padrão. `presentes` None quer dizer "não sei" (Ollama fora): confia na
    escolha, e quem chamar descobre na hora.
    """
    escolhido = (delegados or {}).get(tarefa) or ""
    if not escolhido:
        return padrao
    if presentes is not None and escolhido not in presentes:
        return padrao
    return escolhido
