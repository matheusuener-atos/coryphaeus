"""
Materiais entre advogados (docs/PLANO-PILOTO.md, L9) - sem servidor novo e sem
custo: o site do PAULUS (paulus.ia.br) publica uma lista curada,
`site/dados/materiais.json`, e os arquivos em `site/materiais/`.

- **Ver e trazer** ("Da comunidade", na Biblioteca): o PAULUS lê a lista do
  site **só quando a pessoa pede** - vai só o pedido do arquivo público,
  nada do escritório - e traz o material escolhido para a Biblioteca, com a
  origem "comunidade", o autor e a licença. O arquivo é conferido pelo
  SHA-256 que a lista publica: diferente, não entra.
- **Enviar um material**: o PAULUS **confere os dados pessoais antes** -
  CPF, CNPJ, número de processo, e-mail, telefone e o nome de cada cliente do
  escritório que aparecer no texto - e mostra o que achou. Com o "tirei ou
  autorizo", monta o e-mail para contato@paulus.ia.br (a mesma saída do
  feedback: a pessoa revisa, e o envio passa por Aprovações). A publicação é
  moderada: o dono lê, e só então põe na lista (docs/materiais.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date

from fastapi import HTTPException
from pydantic import BaseModel

SITE = os.environ.get("PAULUS_SITE_URL") or "https://paulus.ia.br"
LISTA = "/dados/materiais.json"
PARA = "contato@paulus.ia.br"
LICENCA = "CC BY 4.0 (Creative Commons Atribuição)"
MAX_BYTES = 2 * 1024 * 1024
RE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")

RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
RE_TELEFONE = re.compile(r"(?:\(?\b\d{2}\)?\s?)?\b9?\d{4}-?\d{4}\b")


def _baixar_padrao(url: str) -> bytes:
    import requests

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES:
        raise ValueError("o arquivo do site é grande demais")
    return r.content


# Os testes trocam o download aqui.
BAIXAR = {"fn": _baixar_padrao}


def listar() -> dict:
    bruto = BAIXAR["fn"](SITE + LISTA)
    dados = json.loads(bruto.decode("utf-8"))
    materiais = [m for m in dados.get("materiais") or [] if RE_SLUG.match(str(m.get("slug") or ""))]
    return {"materiais": materiais, "atualizado_em": dados.get("atualizado_em", ""), "fonte": SITE + LISTA}


def trazer(material, slug: str) -> dict:
    lista = listar()["materiais"]
    m = next((x for x in lista if x.get("slug") == slug), None)
    if m is None:
        raise LookupError("esse material não está mais na lista do site")
    arquivo = str(m.get("arquivo") or "")
    if not arquivo.startswith("/materiais/") or ".." in arquivo:
        raise ValueError("o endereço do material não é do site do PAULUS")
    conteudo = BAIXAR["fn"](SITE + arquivo)
    sha = hashlib.sha256(conteudo).hexdigest()
    if m.get("sha256") and sha != m["sha256"]:
        raise ValueError("o arquivo baixado não confere com o hash publicado na lista: não entrou")
    texto = conteudo.decode("utf-8", errors="replace")
    ficha = {"tipo": m.get("tipo") if m.get("tipo") in ("doutrina", "manual", "tabela", "artigo", "modelo_de_peca", "outro") else "artigo",
             "titulo": str(m.get("titulo") or slug)[:200], "autor": str(m.get("autor") or "")[:120],
             "edicao": "", "ano": str(m.get("publicado_em") or "")[:4], "editora": "PAULUS · materiais entre advogados",
             "isbn": "", "areas": [a for a in (m.get("areas") or []) if isinstance(a, str)][:4], "origem": "comunidade",
             "licenca": str(m.get("licenca") or LICENCA)[:120], "editado": [], "confirmada": True}
    return material.absorver_texto(f"{slug}.md", "[pagina 1]\n" + texto, ficha, sha1=hashlib.sha1(conteudo).hexdigest())


def _cpf_valido(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def conferir_dados(texto: str, clientes: list[str]) -> list[dict]:
    """Os dados pessoais que um texto tem, para a pessoa tirar antes de mandar."""
    from inteligencia.extratores import regras_processo

    achados: list[dict] = []

    def junta(tipo, trecho):
        if not any(a["tipo"] == tipo and a["trecho"] == trecho for a in achados):
            achados.append({"tipo": tipo, "trecho": trecho})

    sem_processos = texto or ""
    for p in regras_processo.achar(texto or ""):
        junta("número de processo", (texto or "")[p["inicio"]:p["fim"]] or str(p.get("numero")))
        sem_processos = sem_processos[:p["inicio"]] + " " * (p["fim"] - p["inicio"]) + sem_processos[p["fim"]:]
    for m in RE_CNPJ.finditer(sem_processos):
        junta("CNPJ", m.group(0))
    for m in RE_CPF.finditer(sem_processos):
        if _cpf_valido(re.sub(r"\D", "", m.group(0))):
            junta("CPF", m.group(0))
    for m in RE_EMAIL.finditer(texto or ""):
        junta("e-mail", m.group(0))
    for m in RE_TELEFONE.finditer(RE_CNPJ.sub(" ", RE_CPF.sub(" ", sem_processos))):
        if len(re.sub(r"\D", "", m.group(0))) >= 10:
            junta("telefone", m.group(0))
    import clientes as clientes_mod

    plano = " " + clientes_mod.chave(texto or "") + " "
    for nome in clientes:
        k = clientes_mod.chave(nome)
        if k and len(k) >= 4 and f" {k} " in plano:
            junta("nome de cliente do escritório", nome)
    return achados


def preparar(texto: str, dados: dict) -> dict:
    titulo = " ".join(str(dados.get("titulo") or "").split())[:160]
    if not titulo:
        raise ValueError("o material precisa de um título")
    corpo = (f"Material para a página de materiais do PAULUS\n\nTítulo: {titulo}\n"
             f"Autor (como aparece): {dados.get('autor') or '—'}" + (f" · OAB {dados['oab']}" if dados.get("oab") else "") +
             f"\nÁrea: {dados.get('area') or '—'} · Tipo: {dados.get('tipo') or 'artigo'}\n"
             f"Resumo: {dados.get('resumo') or '—'}\n\n"
             f"Autorizo a publicação deste texto no site do PAULUS sob a licença {LICENCA}, e declaro que ele não tem "
             f"dado de cliente nem de terceiro.\n\n---\n\n{texto.strip()}\n")
    return {"para": PARA, "assunto": f"[PAULUS · material] {titulo}", "corpo": corpo}


# ------------------------------------------------------------------ rotas

class Envio(BaseModel):
    titulo: str = ""
    autor: str = ""
    oab: str = ""
    area: str = ""
    tipo: str = "artigo"
    resumo: str = ""
    texto: str = ""
    material_id: str = ""


def montar(estado, app) -> None:
    @app.get("/api/comunidade/materiais")
    def comunidade_listar() -> dict:
        """A lista do site - só agora, porque a pessoa pediu."""
        try:
            return listar()
        except Exception as exc:  # noqa: BLE001 - sem rede, site fora: dito
            raise HTTPException(status_code=502, detail=f"não consegui ler a lista do site agora: {exc}") from None

    @app.post("/api/comunidade/materiais/{slug}/trazer")
    def comunidade_trazer(slug: str) -> dict:
        if not RE_SLUG.match(slug):
            raise HTTPException(status_code=404, detail="material não encontrado")
        try:
            return {"item": trazer(estado.material, slug)}
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"não consegui baixar agora: {exc}") from None

    @app.post("/api/comunidade/preparar")
    def comunidade_preparar(payload: Envio) -> dict:
        """A conferência dos dados pessoais e o e-mail montado - nada é enviado aqui."""
        texto = payload.texto
        if payload.material_id:
            texto = re.sub(r"\[pagina \d+\]", "", estado.material.texto_de(payload.material_id) or "")
        texto = (texto or "").strip()
        if len(texto) < 200:
            raise HTTPException(status_code=400, detail="o material precisa ter pelo menos um parágrafo de texto")
        clientes = [c["nome"] for c in estado.cadastros.listar(tipo="cliente")]
        try:
            email = preparar(texto[:200_000], payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"achados": conferir_dados(texto, clientes), "email": email, "caracteres": len(texto)}
