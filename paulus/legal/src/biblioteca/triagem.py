"""
A triagem na entrada da Biblioteca (M2): o que é este arquivo, e para onde vai.

Antes, tudo o que se entregava virava "material" e era cortado do mesmo jeito.
Um PDF do CDC virava blocos de 1.200 caracteres que partiam artigos e
separavam o inciso do caput. Agora, na entrada:

- **lei conhecida** (CDC, CC, CPC...: `leis.reconhecer_texto`): vai para as
  leis em casa, artigo por artigo, com os revogados marcados - e não vira
  material. Se o código já estiver guardado (do Planalto, com data), não é
  guardado de novo: o texto oficial vale mais que a cópia;
- **lei não catalogada** (muitos "Art. N" no começo da linha): fica como
  material no regime A, com o tipo `lei` e o aviso de que ninguém conferiu a
  vigência;
- **súmulas e enunciados**: um trecho por enunciado;
- **doutrina, manual, tabela, modelo de peça**: o corte de cada um (M1).

**Tudo por regra, sem modelo.** Na dúvida, a tela pergunta, e sugere o mais
provável; o que a pessoa escolhe vale.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import leis as leis_mod
import trechos
from biblioteca import ficha as ficha_mod
from biblioteca import sumulas

RE_ARTIGO_LINHA = re.compile(r"^[ \t]*Art\.?\s*\d{1,4}", re.M)
RE_VALOR = re.compile(r"R\$\s*\d")
RE_PECA = re.compile(r"EXCELENT[ÍI]SSIM[OA]|MERIT[ÍI]SSIM[OA]|\bDOS FATOS\b|\bDOS PEDIDOS\b|\bNESTES TERMOS\b")
RE_MANUAL = re.compile(r"\bmanual\b|\brotinas?\b|\bprocedimentos? interno|\bregimento\b|\bpol[íi]tica interna|"
                       r"\bnormas internas|\bregras? da casa", re.I)
RE_TABELA = re.compile(r"\btabela\b", re.I)

# Quantos "Art. N" no começo de linha fazem de um texto uma lei: pelo menos
# 20, e pelo menos um a cada 20 linhas. Uma obra que comenta o CDC cita
# artigos no meio da frase ("art. 18 do CDC"), quase nunca abrindo linha com
# "Art." - e a que transcreve dez artigos continua sendo obra.
MIN_ARTIGOS = 20
DENSIDADE = 0.05


def _linhas(texto: str) -> list[str]:
    return [l for l in (texto or "").splitlines() if l.strip() and not re.fullmatch(r"\s*\[pagina \d+\]\s*", l)]


def densidade_de_artigos(texto: str) -> tuple[int, float]:
    linhas = _linhas(texto)
    n = len(RE_ARTIGO_LINHA.findall(texto or ""))
    return n, (n / len(linhas) if linhas else 0.0)


def triar(nome: str, texto: str) -> dict:
    """
    {'destino': 'lei' | 'material', 'codigo', 'tipo', 'certeza': 'alta' | 'duvida', 'motivo', 'mensagem'}.
    `destino: lei` só para lei que o PAULUS conhece (leis.CODIGOS).
    """
    n_art, dens = densidade_de_artigos(texto)
    if n_art >= MIN_ARTIGOS and dens >= DENSIDADE:
        codigo = leis_mod.reconhecer_texto(texto)
        if codigo:
            nome_lei = leis_mod.CODIGOS[codigo]["nome"]
            return {"destino": "lei", "codigo": codigo, "tipo": "lei", "certeza": "alta",
                    "motivo": f"{n_art} artigos, e o título da {leis_mod.CODIGOS[codigo]['lei']}",
                    "mensagem": f"Isto é o {nome_lei}. Vou guardar artigo por artigo, como lei."}
        return {"destino": "material", "codigo": "", "tipo": "lei", "certeza": "alta",
                "motivo": f"{n_art} artigos no começo da linha, de uma lei que eu não conheço",
                "mensagem": "Guardei como lei, artigo por artigo, sem conferência de vigência: não sei "
                            "se este texto é o compilado atual."}
    if sumulas.parece_sumulas(texto):
        n = len(sumulas.RE_ENUNCIADO.findall(texto))
        return {"destino": "material", "codigo": "", "tipo": "sumulas", "certeza": "alta",
                "motivo": f"{n} enunciados", "mensagem": "Guardei um trecho por enunciado."}
    inicio = ficha_mod.frente(texto)
    tem_cip = bool(ficha_mod.RE_CIP.search(inicio)) or bool(ficha_mod.RE_ISBN.search(inicio))
    obra = trechos.parece_obra(texto)
    if tem_cip:
        return {"destino": "material", "codigo": "", "tipo": "doutrina", "certeza": "alta",
                "motivo": "ficha catalográfica ou ISBN nas primeiras páginas", "mensagem": ""}
    linhas = _linhas(texto)
    valores = sum(1 for l in linhas if RE_VALOR.search(l))
    nome_plano = ficha_mod._plano(nome)
    if RE_MANUAL.search(nome_plano) or RE_MANUAL.search(inicio[:1500]):
        return {"destino": "material", "codigo": "", "tipo": "manual",
                "certeza": "alta" if RE_MANUAL.search(nome_plano) else "duvida",
                "motivo": "a palavra manual, rotina ou regra interna", "mensagem": ""}
    if valores >= 6 and valores >= 0.25 * max(1, len(linhas)):
        return {"destino": "material", "codigo": "", "tipo": "tabela",
                "certeza": "alta" if RE_TABELA.search(nome_plano + " " + inicio[:500]) else "duvida",
                "motivo": f"{valores} linhas com valor em reais", "mensagem": ""}
    if len(RE_PECA.findall(texto[:20000])) >= 2:
        return {"destino": "material", "codigo": "", "tipo": "modelo_de_peca", "certeza": "duvida",
                "motivo": "tem cara de petição", "mensagem": ""}
    if obra:
        return {"destino": "material", "codigo": "", "tipo": "doutrina", "certeza": "duvida",
                "motivo": "capítulos e seções, mas sem ficha catalográfica", "mensagem": ""}
    return {"destino": "material", "codigo": "", "tipo": "outro", "certeza": "duvida",
            "motivo": "não reconheci", "mensagem": ""}


def entregar(material, leis, nome: str, conteudo: bytes, pasta_leis: Path) -> dict:
    """
    O arquivo entra na Biblioteca: lido uma vez, triado, e guardado onde deve.

    Devolve {'destino', 'mensagem', 'triagem', e 'item' (material) ou 'lei'}.
    """
    item = material.absorver(nome, conteudo)
    if item.get("ja_existia"):
        return {"destino": "material", "item": item, "triagem": {}, "mensagem": ""}
    texto = material.texto_de(item["id"])
    t = triar(nome, texto)
    if t["destino"] == "lei":
        codigo = t["codigo"]
        ja = next((l for l in leis.instalados() if l["codigo"] == codigo and l["instalado"]), None)
        if ja:
            material.remover(item["id"])
            return {"destino": "lei", "triagem": t, "lei": {"codigo": codigo, "nome": ja["nome"], "ja_existia": True},
                    "mensagem": f"Isto é o {ja['nome']}, que já está guardado artigo por artigo "
                                f"(importado em {ja['importado_em'][:10]}). Não guardei de novo."}
        pasta_leis.mkdir(parents=True, exist_ok=True)
        destino = pasta_leis / Path(item["arquivo"]).name
        try:
            r = leis.importar_texto(texto, codigo, arquivo=str(destino))
        except ValueError as exc:
            # Não deu para ler artigo por artigo: fica como material de lei.
            t = {**t, "destino": "material", "mensagem": "Não consegui guardar artigo por artigo (" + str(exc) +
                 "); ficou como material de consulta."}
        else:
            shutil.copyfile(item["arquivo"], destino)
            material.remover(item["id"])
            return {"destino": "lei", "triagem": t, "lei": r,
                    "mensagem": t["mensagem"] + f" Guardei {r['artigos']} artigos"
                                + (f", {r['revogados']} revogados" if r["revogados"] else "") + "."}
    ficha = ficha_mod.ler_ficha(texto, t["tipo"])
    if t["tipo"] == "lei":
        ficha["aviso"] = "lei guardada sem conferência de vigência"
    item = material.definir_ficha(item["id"], ficha)
    return {"destino": "material", "item": item, "triagem": t, "mensagem": t.get("mensagem", "")}
