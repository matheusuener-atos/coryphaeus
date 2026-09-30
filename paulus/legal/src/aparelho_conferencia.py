"""
Pensar no aparelho, D3: a conferência do texto que volta do aparelho
(docs/PROGRESSO-APARELHO.md, §2.4).

O texto do aparelho é tratado como não confiável: um aparelho adulterado
poderia mandar qualquer coisa. Antes de gravar e mostrar, o escritório confere,
com as mesmas funções que conferem as respostas escritas aqui - nenhuma cópia:

1. **Marcas** ([T1], [T2]...) que apontam para trecho que não foi mandado:
   reprova (`citacoes.revisar`).
2. **Lei, súmula, artigo ou CNJ** citado que não está nos trechos: sai do texto,
   como no escritório (`citacoes.revisar`, a regra 3). Não reprova.
3. **Números** - valores, datas, percentuais, prazos, CPF, CNPJ, CNJ - que não
   estão nos trechos nem na pergunta: reprova (`molde.numeros_de`, a mesma
   forma canônica da conferência do nível 0). A numeração de lista ("1.",
   "2)") no começo da linha não conta.
4. **Link e e-mail** que não estão nos trechos: saem (`blindagem.tirar_estranhos`,
   a cerca do e-mail e da C6).

Reprovou: a resposta é refeita no escritório, e o motivo vai para o registro.

Observação: as conferências 1 e 3 são mais estritas que as que o escritório
aplica ao próprio texto de fábrica (lá, `ia.citacao` e a cerca vêm
desligadas, e os números só são conferidos no nível 0). Ligá-las também para
o texto do escritório mudaria respostas medidas no roteiro - ficou de fora.
"""

from __future__ import annotations

import re

import blindagem
import citacoes
from inteligencia import molde

RE_ENUMERACAO = re.compile(r"(?m)^\s*(?:\d{1,2}[.)]|[-*•])\s+")


def _numeros(texto: str) -> set[str]:
    return molde.numeros_de(RE_ENUMERACAO.sub(" ", texto or ""))


def conferir(texto: str, trechos: list[str], pergunta: str = "") -> dict:
    """
    {"ok": bool, "texto": o texto conferido (lei inventada e link estranho
    tirados), "motivos": [por que reprovou], "removidas": [o que saiu]}.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "texto": "", "motivos": ["o aparelho não mandou texto"], "removidas": []}
    motivos: list[str] = []
    rev = citacoes.revisar(texto, list(trechos))
    if rev.marcas_invalidas:
        motivos.append("marca para trecho que não foi mandado: " + ", ".join(f"[T{m}]" for m in rev.marcas_invalidas[:5]))
    # A regra 1 do revisar (o rótulo "sem fonte") é do modo de citação do
    # escritório; aqui só vale o que ela tirou.
    conferido = rev.texto.replace(" " + citacoes.SEM_FONTE, "").replace(citacoes.SEM_FONTE, "").strip()
    base = _numeros("\n".join(trechos) + "\n" + (pergunta or ""))
    fora = sorted(n for n in _numeros(citacoes.RE_MARCA.sub(" ", conferido)) if n not in base)
    if fora:
        motivos.append("número que não está nos trechos: " + ", ".join(fora[:5]))
    conferido, estranhos = blindagem.tirar_estranhos(conferido, "\n".join(trechos))
    return {"ok": not motivos, "texto": conferido, "motivos": motivos, "removidas": list(rev.removidas) + list(estranhos)}
