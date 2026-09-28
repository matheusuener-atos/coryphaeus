"""
Mede o reranker bge-reranker-v2-m3 (ONNX, int8) em CPU, para 20 pares
pergunta/trecho - a regua da I7: passou de 3 s, ele nao entra no v0.

O modelo nao vem com o programa. Para medir, baixe os dois arquivos do
repositorio onnx-community/bge-reranker-v2-m3-ONNX (onnx/model_int8.onnx e
tokenizer.json) numa pasta e passe o caminho:

    venv\\Scripts\\python.exe tools\\medir_reranker.py <pasta>

onnxruntime e tokenizers ja estao no ambiente (vem com o faster-whisper).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools" / "demo"))


def pares_de_teste() -> list[tuple[str, str]]:
    """20 trechos de ~1.500 caracteres (o tamanho tipico de uma clausula longa) e uma pergunta."""
    from criar_demo import DOCUMENTOS, MANUAL

    texto = " ".join(t for blocos in DOCUMENTOS.values() for _, t in blocos)
    texto += " " + " ".join(p for _, paragrafos in MANUAL for p in paragrafos)
    while len(texto) < 20 * 1500:
        texto += " " + texto
    trechos = [texto[i * 1500:(i + 1) * 1500] for i in range(20)]
    return [("qual a multa por atraso no pagamento do contrato de transporte?", t) for t in trechos]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pasta = Path(sys.argv[1])
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(str(pasta / "tokenizer.json"))
    tok.enable_truncation(max_length=512)
    tok.enable_padding()
    comeco = time.time()
    sessao = ort.InferenceSession(str(pasta / "model_int8.onnx"), providers=["CPUExecutionProvider"])
    carregar = time.time() - comeco
    entradas = {i.name for i in sessao.get_inputs()}

    def pontuar(pares):
        codificados = tok.encode_batch(pares)
        ids = np.array([c.ids for c in codificados], dtype=np.int64)
        mascara = np.array([c.attention_mask for c in codificados], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mascara}
        if "token_type_ids" in entradas:
            feed["token_type_ids"] = np.zeros_like(ids)
        return sessao.run(None, feed)[0].reshape(-1)

    pares = pares_de_teste()
    pontuar(pares[:2])  # aquece
    tempos = []
    for _ in range(3):
        comeco = time.time()
        escores = pontuar(pares)
        tempos.append(time.time() - comeco)
    tokens = sum(len(c.ids) for c in tok.encode_batch(pares))
    mediana = sorted(tempos)[1]
    print(f"carregar o modelo: {carregar:.1f} s")
    print(f"20 pares ({tokens} tokens): {', '.join(f'{t:.2f}' for t in tempos)} s  -> mediana {mediana:.2f} s")
    print(f"escores: {np.round(escores[:5], 2).tolist()} ...")
    print("ENTRA" if mediana <= 3.0 else "NAO ENTRA (passou de 3 s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
