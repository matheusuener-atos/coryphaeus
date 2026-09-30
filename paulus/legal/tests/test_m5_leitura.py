"""
Portão da M5 da Biblioteca: a leitura das obras em segundo plano
(src/biblioteca/leitura.py), com um modelo de mentira.

  - zero item com `quote` não verificada guardado: o que o modelo "cita" e
    não está no trecho é descartado;
  - os dispositivos da tese saem da frase conferida, por regra;
  - interromper e reabrir continua do trecho em que parou (nada é lido duas
    vezes);
  - trocar o modelo marca a leitura como `stale`, e ela é refeita;
  - o termo que a obra define vira entrada a mais na busca, apontando para o
    trecho que o define;
  - a tese sobre um artigo aparece para a tela da lei.

A conferência com o modelo de verdade (20 trechos, ≥ 80% certos à mão) é
registrada em docs/PROGRESSO-BIBLIOTECA.md, M5.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m5_leitura.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import material as material_mod  # noqa: E402
from biblioteca import ficha as ficha_mod  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class ModeloDeMentira:
    """Devolve a primeira frase do trecho como conceito e como tese - e uma frase inventada de cada."""

    def __init__(self, nome="leitor-falso", quebrar_depois=None):
        self.model = nome
        self.chamadas = 0
        self.quebrar_depois = quebrar_depois

    def digest(self, _):
        return "d-" + self.model

    def _chat(self, messages, fmt=None, tarefa=""):
        self.chamadas += 1
        if self.quebrar_depois is not None and self.chamadas > self.quebrar_depois:
            raise ConnectionError("o Ollama caiu no meio da leitura")
        trecho = messages[-1]["content"].split("Trecho de uma obra jurídica:\n\n", 1)[1].split("\n\nListe em JSON", 1)[0]
        from citacoes import _frases

        frases = [f.strip() for f in _frases(" ".join(trecho.split())) if len(f.strip()) > 40]
        com_artigo = [f for f in frases if "art." in f]
        real = (com_artigo or frases or [trecho[:80]])[0 if com_artigo else -1]
        termo = "vulnerabilidade técnica" if "vulnerabilidade técnica" in trecho else "termo do trecho"
        return json.dumps({
            "conceitos": [{"termo": termo, "quote": real}, {"termo": "inventado", "quote": "Esta frase não existe no livro."}],
            "posicoes": [{"afirmacao": "o autor sustenta o que está na frase", "quote": real, "dispositivos": ["art. 999 do CDC"]},
                         {"afirmacao": "tese inventada", "quote": "O autor nunca escreveu isto aqui."}],
        })


def _obra(pasta: Path):
    import biblioteca_demo

    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: None, chaves={"leitura": True})
    item = m.absorver(biblioteca_demo.OBRA_A["arquivo"], biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_A))
    m.definir_ficha(item["id"], {**ficha_mod.vazia("doutrina"), "autor": "Heitor Valadares Brandão", "ano": "2015"})
    return m, item


def test_so_o_conferido(pasta: Path) -> None:
    print("\nsó o que a frase do livro confirma")
    m, item = _obra(pasta)
    modelo = ModeloDeMentira()
    m.cliente_leitura = lambda: modelo
    m.leitura.iniciar(esperar=True)
    total = len(m._montar_hibrido().searcher.chunks)
    d = m.leitura.de(item["id"])
    checar(modelo.chamadas == total and d["estado"] == "completa", "cada trecho lido uma vez, e a leitura completa",
           (modelo.chamadas, total, d["estado"]))
    todos = d["conceitos"] + d["posicoes"]
    checar(todos and not any("não existe" in x["quote"] or "nunca escreveu" in x["quote"] for x in todos),
           "zero item com frase que não está no livro", [x["quote"][:30] for x in todos][:3])
    texto = " ".join(m.texto_de(item["id"]).split())
    checar(all(" ".join(x["quote"].split())[:40] in texto for x in todos), "toda frase guardada está no arquivo")
    checar(not any(["cdc", "999"] in p["dispositivos"] for p in d["posicoes"]),
           "o artigo que o modelo listou e a frase não cita não entra", [p["dispositivos"] for p in d["posicoes"]][:3])
    salvo = json.loads((pasta / "leituras" / f"{item['id']}.json").read_text(encoding="utf-8"))
    checar(salvo["extrator"] and salvo["modelo"] == "leitor-falso" and salvo["digest"] and salvo["prompt"],
           "guardado com extrator, modelo, digest e versão do prompt")
    checar(m.leitura.chunks_do_termo("o que é vulnerabilidade técnica para a doutrina?"),
           "o termo definido na obra vira entrada da busca")
    listas = m.listas_do_dispositivo("o que é vulnerabilidade técnica para a doutrina?")
    alvo = next(c for c in m._montar_hibrido().searcher.chunks if "vulnerabilidade técnica" in c.text)
    checar(listas and alvo.chunk_id in listas[-1], "apontando para o trecho que o define")
    teses = [p for p in d["posicoes"] if ["cdc", "4º"] in p["dispositivos"]]
    checar(teses and m.leitura.teses_do_artigo(item["id"], "cdc", "4"), "a tese sobre o art. 4º vai para a tela da lei")
    m.fechar()


def test_retomar_e_stale(pasta: Path) -> None:
    print("\ninterromper, reabrir e trocar o modelo")
    m, item = _obra(pasta)
    total = len(m._montar_hibrido().searcher.chunks)
    quebra = ModeloDeMentira(quebrar_depois=4)
    m.cliente_leitura = lambda: quebra
    estado = m.leitura.iniciar(esperar=True)
    checar(estado["erro"] and m.leitura.de(item["id"])["estado"] == "parcial", "o Ollama cai no meio: fica parcial",
           estado)
    reaberto = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: None, chaves={"leitura": True})
    segundo = ModeloDeMentira()
    reaberto.cliente_leitura = lambda: segundo
    reaberto.leitura.iniciar(esperar=True)
    checar(segundo.chamadas == total - 4 and reaberto.leitura.de(item["id"])["estado"] == "completa",
           "reabrir continua do trecho em que parou", (segundo.chamadas, total - 4))
    outro = ModeloDeMentira(nome="leitor-maior")
    reaberto.cliente_leitura = lambda: outro
    checar(len(reaberto.leitura.pendentes(outro)) == total and reaberto.leitura.carregar(item["id"])["estado"] == "stale",
           "trocar o modelo marca a leitura como stale e manda ler de novo")
    reaberto.fechar()
    m.fechar()


def main() -> int:
    print("=" * 55)
    print("  M5 — a leitura das obras")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-m5-{i}-")) for i in range(2)]
    try:
        test_so_o_conferido(pastas[0])
        test_retomar_e_stale(pastas[1])
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
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
