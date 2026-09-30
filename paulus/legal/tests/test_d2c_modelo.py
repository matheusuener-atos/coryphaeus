"""
D2c - qual modelo o aparelho usa (src/aparelho_motor.py, escolher_modelo).

Não depende de o escritório usar o llama3.2:3b: com um Ollama de mentira,
com vários modelos baixados,

  - o configurado para o aparelho, se está aqui e cabe no navegador;
  - senão, o mesmo que o escritório usa na conversa, se cabe;
  - senão, o maior modelo de texto que cabe - nunca um de vetores (embed);
  - grande demais (acima do teto do navegador): nunca;
  - nada serve: o erro diz o que fazer;
  - a lista dos modelos sai dos manifestos, com os nomes como o Ollama dá.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_d2c_modelo.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def baixar(pasta: Path, nome: str, tamanho: int, familia: str = "llama", espaco: str = "library") -> None:
    """Um modelo no formato do Ollama: o blob (nome = hash), o config com a família e o manifesto."""
    blobs = pasta / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    peso = (nome.encode() * (tamanho // max(1, len(nome)) + 1))[:tamanho]
    sha = hashlib.sha256(peso).hexdigest()
    (blobs / f"sha256-{sha}").write_bytes(peso)
    cfg = json.dumps({"model_format": "gguf", "model_family": familia}).encode()
    sha_cfg = hashlib.sha256(cfg).hexdigest()
    (blobs / f"sha256-{sha_cfg}").write_bytes(cfg)
    base, _, etiqueta = nome.partition(":")
    man = pasta / "manifests" / "registry.ollama.ai" / espaco / base.split("/")[-1] / (etiqueta or "latest")
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps({"config": {"digest": "sha256:" + sha_cfg},
                               "layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:" + sha}]}),
                   encoding="utf-8")


def main() -> int:
    print("=" * 55)
    print("  D2c — qual modelo o aparelho usa")
    print("=" * 55)
    import aparelho_motor as am

    am.LIMITE_BYTES = 3000   # o teto do navegador, em escala de teste
    pasta = Path(tempfile.mkdtemp(prefix="paulus-d2c-"))
    baixar(pasta, "qwen2.5:7b", 4500, "qwen2")          # o do escritório, grande demais
    baixar(pasta, "gemma3:1b", 800, "gemma3")
    baixar(pasta, "qwen2.5:3b", 1900, "qwen2")
    baixar(pasta, "nomic-embed-text:latest", 2500, "nomic-bert")
    baixar(pasta, "bge-m3:latest", 2600, "bert")

    nomes = am.modelos_do_ollama(pasta)
    checar(nomes == sorted(["qwen2.5:7b", "gemma3:1b", "qwen2.5:3b", "nomic-embed-text:latest", "bge-m3:latest"]),
           "a lista sai dos manifestos, com os nomes do Ollama", nomes)

    m = am.escolher_modelo("llama3.2:3b", "qwen2.5:7b", pasta)
    checar(m.get("nome") == "qwen2.5:3b" and "maior" in m.get("escolha", ""),
           "sem o 3B de fábrica e com o do escritório grande demais: o maior de texto que cabe (não o de vetores)", m.get("nome"))
    m = am.escolher_modelo("", "gemma3:1b", pasta)
    checar(m.get("nome") == "gemma3:1b" and m.get("escolha") == "o mesmo do escritório",
           "o do escritório cabe: o mesmo dos dois lados", m.get("nome"))
    baixar(pasta, "llama3.2:3b", 2000, "llama")
    m = am.escolher_modelo("", "qwen2.5:7b", pasta)
    checar(m.get("nome") == "llama3.2:3b" and m.get("escolha") == "o de fábrica", "com o 3B aqui: o de fábrica", m.get("nome"))
    m = am.escolher_modelo("gemma3:1b", "llama3.2:3b", pasta)
    checar(m.get("nome") == "gemma3:1b" and m.get("escolha") == "o configurado para o aparelho",
           "o configurado para o aparelho vem primeiro", m.get("nome"))
    m = am.escolher_modelo("qwen2.5:7b", "", pasta)
    checar(m.get("nome") != "qwen2.5:7b", "configurado grande demais: não usa, escolhe outro", m.get("nome"))
    m = am.escolher_modelo("nomic-embed-text:latest", "", pasta)
    checar(m.get("nome") != "nomic-embed-text:latest", "modelo de vetores nunca vai ao aparelho", m.get("nome"))
    checar(all(k in am.escolher_modelo("", "", pasta) for k in ("sha256", "bytes", "arquivo")),
           "o escolhido vem com hash, tamanho e arquivo (o resto do caminho não muda)")

    so_grandes = Path(tempfile.mkdtemp(prefix="paulus-d2c-"))
    baixar(so_grandes, "qwen2.5:7b", 4500, "qwen2")
    baixar(so_grandes, "nomic-embed-text:latest", 500, "nomic-bert")
    m = am.escolher_modelo("llama3.2:3b", "qwen2.5:7b", so_grandes)
    checar("erro" in m and "Configurações › Modelos" in m["erro"], "nada cabe: o erro diz o que fazer", m)
    checar("erro" in am.escolher_modelo("", "", Path(tempfile.mkdtemp())), "Ollama vazio: erro, sem quebrar")

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
