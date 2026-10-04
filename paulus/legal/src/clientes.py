"""
Visão por cliente e muralha ética (docs/PLANO-PILOTO.md, L3).

A mesma base para as duas coisas: reconhecer que "Empresa X Ltda.",
"EMPRESA X" e "Empresa X - ME" são a mesma entidade.

- **A entidade** (`chave`, `mesma`): sem acento, sem pontuação, sem a forma
  jurídica (Ltda., S/A, ME, EPP, EIRELI...) e sem "de/da/do". Com os dois
  documentos, manda o documento: CPF igual, ou a mesma raiz do CNPJ (os 8
  primeiros dígitos: a matriz e as filiais), é a mesma; documento diferente
  não é, mesmo com o nome igual. Sem documento, o nome: chave igual é "a
  mesma"; quase igual (as palavras quase todas em comum) é "parece ser" -
  e a tela diz qual das duas.
- **A parte contrária** de cada Serviço (`servicos.partes`, migração 029).
- **Sugerida pelos documentos** (`sugerir_partes`, N3): nos documentos do
  Serviço (a pasta dele e os ligados a ele), a leitura já achou as partes e o
  papel de cada uma (autor e réu, locador e locatário, contratante e
  contratado...). Onde o cliente do Serviço aparece, a parte do papel oposto
  é a sugestão de parte contrária (e o fiador do outro lado, interessado),
  com o documento e o porquê, e o CPF ou CNPJ escrito perto do nome. Onde o
  cliente não aparece, não dá para saber o lado: a tela diz em quantos. A
  pessoa confirma; o que ela dispensa não volta.
- **Conflito de interesse** (`conflitos`): o cliente que é parte contrária em
  outro Serviço, e a parte contrária que é cliente do escritório. Avisa, não
  bloqueia: quem decide é o advogado.
- **Guardado como pendência** (N4, tabela `conflitos`): cada conflito achado
  fica aberto até alguém dizer como resolveu (não é a mesma pessoa; os
  clientes autorizaram por escrito; muralha aplicada; o escritório recusou um
  dos casos; outro motivo, escrito), com quem e quando. Aparece na Central de
  avisos, no Serviço e na visão do cliente. O que deixa de existir (a parte
  saiu do Serviço) fecha sozinho, e diz. A muralha dada por aplicada, com a
  pessoa ainda nas duas equipes, reabre.
- **Muralha ética**: a separação por equipe já existe (quem não está na
  equipe não vê o Serviço de fora). O conflito diz, além disso, quem está na
  equipe dos dois lados - é essa pessoa que a muralha precisa separar.
- **Tudo sobre o cliente** (`visao`): os Serviços, os processos (L2), os
  prazos e compromissos, os documentos (os ligados e os em que ele aparece
  como parte, pelo nome ou pelo documento), as partes contrárias, os outros
  nomes com que ele aparece e os conflitos.
"""

from __future__ import annotations

import json
import re
import unicodedata

from fastapi import HTTPException, Request
from pydantic import BaseModel

FORMAS = {"ltda", "limitada", "me", "epp", "eireli", "sa", "cia", "companhia", "mei", "slu", "ss", "sociedade",
          "anonima", "empresarial", "simples", "unipessoal"}
LIGA = {"de", "da", "do", "das", "dos", "e", "a", "o"}
PAPEIS = {"contraria": "parte contrária", "interessado": "interessado"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c))


def palavras(nome: str) -> list[str]:
    t = _sem_acento(nome).lower().replace("&", " e ")
    t = re.sub(r"\bs\s*/\s*a\b|\bs\.\s*a\.?(?=\s|$)", " sa ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return [p for p in t.split() if p not in FORMAS and p not in LIGA]


def chave(nome: str) -> str:
    return " ".join(palavras(nome))


def digitos(doc: str) -> str:
    return re.sub(r"\D", "", str(doc or ""))


def mesma(nome_a: str, doc_a: str, nome_b: str, doc_b: str) -> str:
    """"igual", "parecida" ou "" - se as duas são a mesma entidade."""
    da, db = digitos(doc_a), digitos(doc_b)
    if len(da) in (11, 14) and len(db) in (11, 14):
        if da == db or (len(da) == 14 and len(db) == 14 and da[:8] == db[:8]):
            return "igual"
        return ""
    ka, kb = chave(nome_a), chave(nome_b)
    if not ka or not kb:
        return ""
    if ka == kb:
        return "igual"
    pa, pb = set(ka.split()), set(kb.split())
    if min(len(pa), len(pb)) >= 2:
        comum = len(pa & pb) / len(pa | pb)
        if comum >= 0.75 or (pa <= pb or pb <= pa) and len(pa & pb) >= 2:
            return "parecida"
    return ""


def _json(bruto, padrao):
    try:
        return json.loads(bruto) if isinstance(bruto, str) else (bruto or padrao)
    except ValueError:
        return padrao


def limpar_partes(bruto) -> list[dict]:
    saida = []
    for p in bruto or []:
        nome = " ".join(str((p or {}).get("nome") or "").split())[:160]
        if not nome:
            continue
        papel = (p or {}).get("papel") if (p or {}).get("papel") in PAPEIS else "contraria"
        saida.append({"nome": nome, "documento": str((p or {}).get("documento") or "")[:20], "papel": papel})
    return saida[:40]


# ------------------------------------------------------------ o conflito

def _equipe(base, servico_id) -> dict[int, str]:
    l = base.um("SELECT equipe FROM servicos WHERE id = ?", (int(servico_id),)) if servico_id else None
    ids = _json((l or {}).get("equipe"), [])
    if not ids:
        return {}
    marcas = ",".join("?" * len(ids))
    return {int(x["id"]): x["nome"] for x in base.buscar(f"SELECT id, nome FROM cadastros WHERE id IN ({marcas})", tuple(ids))}


def conflitos(base, nome: str, documento: str = "", *, papel: str = "cliente", servico_id=None, cadastro_id=None) -> list[dict]:
    """
    Onde esta entidade já aparece do outro lado. `papel`: "cliente" (a ficha
    de um cliente, ou o cliente de um Serviço) ou "contraria" (a parte
    contrária sendo posta em `servico_id`).
    """
    saida: list[dict] = []
    if not chave(nome) and len(digitos(documento)) not in (11, 14):
        return saida
    if papel == "contraria":
        proprio = (base.um("SELECT cadastro_id FROM servicos WHERE id = ?", (int(servico_id),)) or {}).get("cadastro_id") if servico_id else None
        minha_equipe = _equipe(base, servico_id)
        for c in base.buscar("SELECT id, nome, documento FROM cadastros WHERE tipo = 'cliente'"):
            grau = mesma(nome, documento, c["nome"], c["documento"])
            if not grau:
                continue
            if proprio and int(c["id"]) == int(proprio):
                saida.append({"tipo": "proprio", "grau": grau, "cadastro_id": c["id"],
                              "texto": f"“{c['nome']}” é o próprio cliente deste Serviço"})
                continue
            saida.append({"tipo": "cliente", "grau": grau, "cadastro_id": c["id"],
                          "texto": ("" if grau == "igual" else "parece ser: ") + f"“{c['nome']}” é cliente do escritório"})
            for s in base.buscar("SELECT id, nome FROM servicos WHERE cadastro_id = ? AND status != 'concluido'", (c["id"],)):
                dos_dois = sorted(set(minha_equipe) & set(_equipe(base, s["id"])))
                for pid in dos_dois:
                    saida.append({"tipo": "muralha", "grau": grau, "servico_id": s["id"], "pessoa_id": pid,
                                  "texto": f"{minha_equipe[pid]} está na equipe dos dois lados: deste Serviço e de “{s['nome']}”"})
        return saida
    for s in base.buscar("SELECT s.id, s.nome, s.partes, s.cadastro_id, c.nome AS cliente FROM servicos s"
                         " LEFT JOIN cadastros c ON c.id = s.cadastro_id WHERE s.partes IS NOT NULL AND s.partes != '[]'"):
        if servico_id and int(s["id"]) == int(servico_id):
            continue
        for p in _json(s["partes"], []):
            if p.get("papel") != "contraria":
                continue
            grau = mesma(nome, documento, p.get("nome", ""), p.get("documento", ""))
            if grau:
                saida.append({"tipo": "contraria", "grau": grau, "servico_id": s["id"],
                              "texto": ("" if grau == "igual" else "parece ser: ") + f"“{p['nome']}” é parte contrária no Serviço “{s['nome']}”"
                                       + (f" (cliente {s['cliente']})" if s.get("cliente") else "")})
    return saida


# ------------------------------------------------------------ a pendência (N4)

RESOLUCOES = {
    "nao_e": "Não é a mesma pessoa ou empresa",
    "autorizado": "Os clientes autorizaram, por escrito",
    "muralha": "Muralha aplicada: a pessoa saiu de uma das equipes",
    "recusado": "O escritório recusou ou deixou um dos casos",
    "outro": "Outro motivo",
    "sumiu": "Deixou de existir (a parte ou a equipe mudou)",
}


def _agora() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def chave_do_conflito(c: dict, contexto_servico=None, contexto_cadastro=None) -> str:
    """A mesma situação dá a mesma chave, venha da ficha, do Serviço ou da conferência geral."""
    tipo = c.get("tipo", "")
    s_ctx = int(contexto_servico) if contexto_servico else 0
    outro = int(c.get("servico_id") or 0)
    cad = int(c.get("cadastro_id") or contexto_cadastro or 0)
    pessoa = int(c.get("pessoa_id") or 0)
    parte = chave(c.get("parte") or "")
    if tipo == "muralha":
        a, b = sorted((s_ctx, outro))
        return f"muralha|{a}|{b}|{pessoa}"
    # O cliente `cad` como parte contrária num Serviço é uma situação só, vista
    # da ficha dele ("contraria": o Serviço é `outro`) ou do Serviço ("cliente":
    # o Serviço é o do contexto).
    if tipo == "contraria":
        return f"lados|{cad}|{outro}"
    if tipo == "cliente":
        return f"lados|{cad}|{s_ctx}"
    return f"{tipo}|{s_ctx}|{cad}|{parte}"


def registrar(base, achados: list[dict], *, servico_id=None, cadastro_id=None) -> list[dict]:
    """Guarda cada conflito achado (uma vez) e devolve os achados com o id e o estado da pendência."""
    agora = _agora()
    saida = []
    for c in achados:
        k = chave_do_conflito(c, servico_id, cadastro_id)
        ja = base.um("SELECT * FROM conflitos WHERE chave = ?", (k,))
        if ja is None:
            outro = c.get("servico_id")
            texto = c.get("texto", "")
            if servico_id and "deste Serviço" in texto:
                # Guardado, o texto sai do Serviço: "deste" vira o nome dele.
                nome_ctx = (base.um("SELECT nome FROM servicos WHERE id = ?", (int(servico_id),)) or {}).get("nome") or "deste Serviço"
                texto = texto.replace("deste Serviço", f"“{nome_ctx}”")
            # servico_id: o Serviço onde a conferência aconteceu; outro_servico_id: o do outro lado.
            cid = base.escrever(
                "INSERT INTO conflitos (chave, tipo, texto, parte, grau, servico_id, outro_servico_id, cadastro_id, pessoa_id,"
                " criado_em, visto_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (k, c.get("tipo", ""), texto, c.get("parte", ""), c.get("grau", ""),
                 int(servico_id) if servico_id else None, int(outro) if outro else None,
                 int(c.get("cadastro_id") or cadastro_id or 0) or None, int(c.get("pessoa_id") or 0) or None, agora, agora))
            ja = base.um("SELECT * FROM conflitos WHERE id = ?", (cid,))
        else:
            if ja["estado"] == "resolvido" and (ja["resolucao"] == "sumiu" or (ja["tipo"] == "muralha" and ja["resolucao"] == "muralha")):
                # Voltou a existir, ou a pessoa continua nas duas equipes: reabre, dito.
                motivo = ("voltou a aparecer" if ja["resolucao"] == "sumiu" else "a pessoa continua nas duas equipes")
                base.escrever("UPDATE conflitos SET estado = 'aberto', nota = ?, visto_em = ? WHERE id = ?",
                              ((ja.get("nota") or "") + f"\nReaberto em {agora[:10]}: {motivo}.", agora, ja["id"]))
            else:
                base.escrever("UPDATE conflitos SET visto_em = ? WHERE id = ?", (agora, ja["id"]))
            ja = base.um("SELECT * FROM conflitos WHERE id = ?", (ja["id"],))
        saida.append(dict(c, id=ja["id"], estado=ja["estado"], resolucao=ja["resolucao"], resolucao_rotulo=RESOLUCOES.get(ja["resolucao"], ""),
                          resolvido_por=ja["resolvido_por"], resolvido_em=ja["resolvido_em"], nota=ja["nota"]))
    return saida


def do_servico(base, id_: int) -> list[dict]:
    """Todos os conflitos de um Serviço (o cliente dele do outro lado, e as partes contrárias dele)."""
    s = base.um("SELECT s.id, s.partes, s.cadastro_id, c.nome, c.documento FROM servicos s LEFT JOIN cadastros c ON c.id = s.cadastro_id"
                " WHERE s.id = ?", (int(id_),))
    if not s:
        return []
    achados = [dict(x, parte=s["nome"]) for x in conflitos(base, s.get("nome") or "", s.get("documento") or "", papel="cliente",
                                                          servico_id=id_, cadastro_id=s.get("cadastro_id"))] if s.get("nome") else []
    for x in achados:
        x.setdefault("cadastro_id", s.get("cadastro_id"))
    for p in _json(s["partes"], []):
        if p.get("papel") == "contraria":
            achados += [dict(x, parte=p["nome"]) for x in conflitos(base, p["nome"], p.get("documento", ""), papel="contraria", servico_id=id_)]
    return achados


def conferir_todos(base) -> dict:
    """
    A conferência geral: todos os Serviços em andamento. O conflito aberto
    que não aparece mais fecha sozinho ("deixou de existir").
    """
    achadas: set[int] = set()
    for s in base.buscar("SELECT id FROM servicos WHERE status != 'concluido'"):
        for c in registrar(base, do_servico(base, s["id"]), servico_id=s["id"]):
            achadas.add(int(c["id"]))
    fechados = 0
    agora = _agora()
    for c in base.buscar("SELECT id FROM conflitos WHERE estado = 'aberto'"):
        if int(c["id"]) not in achadas:
            base.escrever("UPDATE conflitos SET estado = 'resolvido', resolucao = 'sumiu', resolvido_por = 'PAULUS', resolvido_em = ?"
                          " WHERE id = ?", (agora, c["id"]))
            fechados += 1
    return {"abertos": base.contar("conflitos", "estado = 'aberto'"), "fechados_sozinhos": fechados}


def listar_conflitos(base, *, estado: str = "", cadastro_id=None, servico_id=None) -> list[dict]:
    onde, args = [], []
    if estado:
        onde.append("f.estado = ?")
        args.append(estado)
    if cadastro_id:
        onde.append("(f.cadastro_id = ? OR f.servico_id IN (SELECT id FROM servicos WHERE cadastro_id = ?)"
                    " OR f.outro_servico_id IN (SELECT id FROM servicos WHERE cadastro_id = ?))")
        args += [int(cadastro_id)] * 3
    if servico_id:
        onde.append("(f.servico_id = ? OR f.outro_servico_id = ?)")
        args += [int(servico_id)] * 2
    sql = ("SELECT f.*, s.nome AS servico_nome, o.nome AS outro_servico_nome, c.nome AS cliente_nome FROM conflitos f"
           " LEFT JOIN servicos s ON s.id = f.servico_id LEFT JOIN servicos o ON o.id = f.outro_servico_id"
           " LEFT JOIN cadastros c ON c.id = f.cadastro_id" + (" WHERE " + " AND ".join(onde) if onde else "") +
           " ORDER BY CASE f.estado WHEN 'aberto' THEN 0 ELSE 1 END, f.visto_em DESC LIMIT 300")
    return [dict(l, resolucao_rotulo=RESOLUCOES.get(l["resolucao"] or "", "")) for l in base.buscar(sql, tuple(args))]


def resolver(base, id_: int, resolucao: str, nota: str, quem: str) -> dict:
    if resolucao not in RESOLUCOES or resolucao == "sumiu":
        raise ValueError("escolha como o conflito foi resolvido")
    nota = " ".join(str(nota or "").split())[:1000]
    if resolucao == "outro" and len(nota) < 5:
        raise ValueError("diga, em uma frase, como foi resolvido")
    if not base.um("SELECT id FROM conflitos WHERE id = ?", (int(id_),)):
        raise LookupError("conflito não encontrado")
    base.escrever("UPDATE conflitos SET estado = 'resolvido', resolucao = ?, nota = ?, resolvido_por = ?, resolvido_em = ? WHERE id = ?",
                  (resolucao, nota, quem, _agora(), int(id_)))
    return next(c for c in listar_conflitos(base) if c["id"] == int(id_))


def reabrir(base, id_: int, quem: str) -> dict:
    l = base.um("SELECT nota FROM conflitos WHERE id = ?", (int(id_),))
    if not l:
        raise LookupError("conflito não encontrado")
    base.escrever("UPDATE conflitos SET estado = 'aberto', nota = ?, resolucao = '', resolvido_por = '', resolvido_em = '' WHERE id = ?",
                  ((l.get("nota") or "") + f"\nReaberto por {quem} em {_agora()[:10]}.", int(id_)))
    return next(c for c in listar_conflitos(base) if c["id"] == int(id_))


# ------------------------------------------------------------ sugerida pelos documentos (N3)

# O papel do outro lado, pelo papel que a leitura deu ao cliente.
OPOSTO = {"plaintiff": "defendant", "defendant": "plaintiff", "contracting_party": "contractor",
          "contractor": "contracting_party", "lessor": "lessee", "lessee": "lessor", "seller": "buyer",
          "buyer": "seller", "grantor": "grantee", "grantee": "grantor", "assignor": "assignee",
          "assignee": "assignor", "creditor": "debtor", "debtor": "creditor"}
# O fiador fica do lado de quem ele garante (o locatário, o devedor).
GARANTIDO = {"lessee", "debtor", "buyer", "contracting_party"}
NAO_E_PARTE = {"lawyer", "witness"}
PAPEL_BR = {"plaintiff": "autor", "defendant": "réu", "contracting_party": "contratante", "contractor": "contratado",
            "lessor": "locador", "lessee": "locatário", "seller": "vendedor", "buyer": "comprador",
            "grantor": "outorgante", "grantee": "outorgado", "assignor": "cedente", "assignee": "cessionário",
            "creditor": "credor", "debtor": "devedor", "guarantor": "fiador"}
_RE_DOC = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}\s*/\s*\d{4}\s*-?\s*\d{2}|\d{3}\.?\d{3}\.?\d{3}\s*-?\s*\d{2})\b")


def _plano(texto: str) -> str:
    """Sem acento e em minúscula, com o mesmo tamanho (a posição vale no original)."""
    return "".join((_sem_acento(c) or c)[:1] for c in str(texto or "")).lower()


def documento_perto(texto: str, nome: str, alcance: int = 260) -> str:
    """O CPF ou o CNPJ válido escrito logo depois do nome (a qualificação da parte)."""
    import campos_br

    t = _plano(texto)
    alvo = _plano(" ".join(str(nome or "").split()))
    if len(alvo) < 3:
        return ""
    i = t.find(alvo)
    if i < 0:
        return ""
    trecho = str(texto)[i + len(alvo): i + len(alvo) + alcance]
    for m in _RE_DOC.finditer(trecho):
        bruto = re.sub(r"\s", "", m.group(1))
        if campos_br.cnpj_valido(bruto):
            return campos_br.mascara_cnpj(bruto)
        if campos_br.cpf_valido(bruto):
            return campos_br.mascara_cpf(bruto)
    return ""


def _normal(caminho: str) -> str:
    import os

    return os.path.normcase(os.path.normpath(str(caminho or "")))


def documentos_do_servico(estado, servico_id: int) -> list:
    """Os documentos lidos do Serviço: os da pasta dele e os ligados a ele."""
    from pathlib import Path

    pasta = estado.servicos.pasta_de(int(servico_id), criar=False) if getattr(estado, "servicos", None) else None
    raiz = Path(pasta).resolve() if pasta else None
    ligados = {v["sha1"] for v in estado.base.buscar("SELECT sha1 FROM vinculos WHERE tipo = 'servico' AND alvo_id = ?", (int(servico_id),))}
    saida = []
    for d in getattr(estado.searcher, "documents", []) or []:
        try:
            dentro = raiz is not None and Path(d.path).resolve().is_relative_to(raiz)
        except (OSError, ValueError, TypeError):
            dentro = False
        if dentro or getattr(d, "sha1", "") in ligados:
            saida.append(d)
    return saida


def sugerir_partes(estado, servico_id: int) -> dict:
    """As partes do outro lado, pelos papéis que a leitura achou nos documentos do Serviço."""
    base = estado.base
    s = base.um("SELECT s.id, s.partes, s.partes_dispensadas, c.nome AS cliente, c.documento AS cliente_doc FROM servicos s"
                " LEFT JOIN cadastros c ON c.id = s.cadastro_id WHERE s.id = ?", (int(servico_id),))
    if not s:
        raise LookupError("serviço não encontrado")
    if not s.get("cliente"):
        return {"sugeridas": [], "sem_lado": [], "lidos": 0,
                "motivo": "o Serviço não tem cliente: sem ele, não dá para saber de que lado está cada parte"}
    # As já anotadas e as dispensadas não voltam, nem com outro jeito de escrever.
    ja = [(p.get("nome", ""), p.get("documento", "")) for p in _json(s.get("partes"), [])]
    ja += [(k, "") for k in _json(s.get("partes_dispensadas"), [])]
    escritorio = ((estado.prefs.dados.get("escritorio") or {}).get("nome") or "") if getattr(estado, "prefs", None) else ""
    metas = {_normal(l["caminho"]): l for l in base.buscar("SELECT id, caminho, titulo, versao_atual FROM meta_documentos")}
    sugeridas: dict[str, dict] = {}
    sem_lado: list[str] = []
    lidos = 0
    for d in documentos_do_servico(estado, servico_id):
        m = metas.get(_normal(d.path))
        if not m or not m.get("versao_atual"):
            continue
        fatos = base.buscar("SELECT chave, mostrar FROM meta_fatos WHERE versao_id = ? AND secao = 'parties' AND verificado = 1",
                            (m["versao_atual"],))
        if not fatos:
            continue
        lidos += 1
        titulo = m.get("titulo") or d.name
        do_cliente = [f["chave"] for f in fatos if mesma(s["cliente"], s.get("cliente_doc") or "", f["mostrar"], "")]
        if not do_cliente:
            sem_lado.append(titulo)
            continue
        opostos = {OPOSTO[p] for p in do_cliente if p in OPOSTO}
        for f in fatos:
            nome = " ".join(str(f["mostrar"] or "").split())
            k = chave(nome)
            if not k or f["chave"] in NAO_E_PARTE or mesma(s["cliente"], "", nome, "") or any(mesma(n, dd, nome, "") for n, dd in ja):
                continue
            if escritorio and mesma(escritorio, "", nome, ""):
                continue
            if f["chave"] in opostos:
                papel = "contraria"
            elif f["chave"] == "guarantor" and opostos & GARANTIDO:
                papel = "interessado"
            else:
                continue
            pc = do_cliente[0]
            porque = (f"em “{titulo}”, {s['cliente']} aparece como {PAPEL_BR.get(pc, pc)} e {nome}, como "
                      f"{PAPEL_BR.get(f['chave'], f['chave'])}")
            doc = documento_perto(getattr(d, "text", "") or "", nome)
            # A mesma entidade com outro nome (ou o mesmo CNPJ) junta numa sugestão só.
            item = next((x for x in sugeridas.values() if mesma(x["nome"], x["documento"], nome, doc)), None)
            if item is None:
                item = sugeridas.setdefault(k, {"nome": nome, "documento": "", "papel": papel, "documentos": [], "porque": porque,
                                                "chave": k, "outros_nomes": []})
            elif nome != item["nome"] and nome not in item["outros_nomes"]:
                item["outros_nomes"].append(nome)
            if titulo not in item["documentos"]:
                item["documentos"].append(titulo)
            if not item["documento"]:
                item["documento"] = doc
    lista = sorted(sugeridas.values(), key=lambda x: (x["papel"] != "contraria", -len(x["documentos"]), x["nome"].lower()))
    return {"sugeridas": lista, "sem_lado": sem_lado, "lidos": lidos, "motivo": ""}


# ------------------------------------------------------------ tudo sobre o cliente

def _partes_nos_documentos(base) -> list[dict]:
    return base.buscar(
        "SELECT f.mostrar, f.chave, d.titulo, d.caminho FROM meta_fatos f JOIN meta_documentos d ON d.versao_atual = f.versao_id"
        " WHERE f.secao = 'parties'")


def visao(estado, cadastro_id: int) -> dict:
    base = estado.base
    c = base.um("SELECT * FROM cadastros WHERE id = ?", (int(cadastro_id),))
    if not c:
        raise LookupError("cadastro não encontrado")
    servicos = base.buscar("SELECT id, nome, status, partes FROM servicos WHERE cadastro_id = ? ORDER BY atualizado_em DESC", (c["id"],))
    ids = [int(s["id"]) for s in servicos]
    marcas = ",".join("?" * len(ids)) or "NULL"
    processos = []
    if getattr(estado, "processos", None) is not None and ids:
        processos = [p for p in estado.processos.listar() if p.get("servico_id") in ids]
    prazos = base.buscar(
        f"SELECT id, titulo, prazo, lista, servico_id FROM tarefas WHERE concluida = 0 AND (cadastro_id = ? OR servico_id IN ({marcas}))"
        " ORDER BY CASE WHEN prazo = '' THEN 1 ELSE 0 END, prazo LIMIT 40", (c["id"], *ids))
    compromissos = base.buscar(
        f"SELECT id, titulo, data, hora FROM compromissos WHERE data >= date('now') AND (cadastro_id = ? OR servico_id IN ({marcas}))"
        " ORDER BY data, hora LIMIT 20", (c["id"], *ids))
    documentos: dict[str, dict] = {}
    for v in base.buscar("SELECT nome FROM vinculos WHERE tipo = 'cadastro' AND alvo_id = ?", (c["id"],)):
        documentos.setdefault(v["nome"], {"nome": v["nome"], "como": "ligado à ficha"})
    for v in base.buscar(f"SELECT nome FROM vinculos WHERE tipo = 'servico' AND alvo_id IN ({marcas})", tuple(ids)):
        documentos.setdefault(v["nome"], {"nome": v["nome"], "como": "de um Serviço"})
    outros_nomes: dict[str, str] = {}
    for f in _partes_nos_documentos(base):
        grau = mesma(c["nome"], c.get("documento") or "", f["mostrar"], "")
        if not grau:
            continue
        nome_doc = f["titulo"] or f["caminho"]
        documentos.setdefault(nome_doc, {"nome": nome_doc, "como": "aparece como parte" + ("" if grau == "igual" else " (parece ser)")})
        if chave(f["mostrar"]) != chave(c["nome"]) or f["mostrar"].strip() != c["nome"].strip():
            outros_nomes.setdefault(f["mostrar"].strip(), grau)
    contrarias = []
    for s in servicos:
        for p in _json(s.get("partes"), []):
            if p.get("papel") == "contraria":
                contrarias.append({"nome": p["nome"], "documento": p.get("documento", ""), "servico": s["nome"], "servico_id": s["id"]})
    return {
        "cliente": {k: c.get(k) for k in ("id", "tipo", "nome", "documento", "email", "telefone")},
        "servicos": [{"id": s["id"], "nome": s["nome"], "status": s["status"]} for s in servicos],
        "processos": [{"id": p["id"], "numero_fmt": p["numero_fmt"], "servico_nome": p.get("servico_nome"), "novas": p.get("novas", 0),
                       "classe": p.get("classe", "")} for p in processos],
        "prazos": prazos, "compromissos": compromissos,
        "documentos": sorted(documentos.values(), key=lambda d: d["nome"].lower())[:80],
        "partes_contrarias": contrarias,
        "outros_nomes": [{"nome": n, "grau": g} for n, g in sorted(outros_nomes.items())][:20],
        "conflitos": registrar(base, [dict(x, parte=c["nome"]) for x in conflitos(base, c["nome"], c.get("documento") or "",
                                                                                   papel="cliente", cadastro_id=c["id"])],
                               cadastro_id=c["id"]) if c.get("tipo") == "cliente" else [],
        "conflitos_resolvidos": listar_conflitos(base, estado="resolvido", cadastro_id=c["id"]) if c.get("tipo") == "cliente" else [],
    }


# ------------------------------------------------------------------ rotas

class Partes(BaseModel):
    partes: list[dict] = []


class Dispensar(BaseModel):
    nome: str


class Resolucao(BaseModel):
    resolucao: str
    nota: str = ""


def _quem(request) -> str:
    """Quem resolveu: a pessoa de fora pelo nome; na janela do escritório, o nome de Meus dados."""
    try:
        from acesso import rotas as rotas_do_acesso

        p = rotas_do_acesso.pessoa(request) if request is not None else None
        if p:
            return p.get("nome") or p.get("email") or "de fora"
    except Exception:  # noqa: BLE001
        pass
    return ""


class Consulta(BaseModel):
    nome: str = ""
    documento: str = ""
    papel: str = "cliente"
    servico_id: int | None = None
    cadastro_id: int | None = None


def montar(estado, app) -> None:
    import servicos_acesso

    @app.put("/api/servicos/{id_}/partes")
    def servicos_partes(id_: int, payload: Partes, request: Request = None) -> dict:
        if not estado.base.um("SELECT id FROM servicos WHERE id = ?", (id_,)) or not servicos_acesso.visivel(id_):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        partes = limpar_partes(payload.partes)
        estado.base.escrever("UPDATE servicos SET partes = ? WHERE id = ?", (json.dumps(partes, ensure_ascii=False), id_))
        achados = []
        for p in partes:
            if p["papel"] == "contraria":
                for x in conflitos(estado.base, p["nome"], p["documento"], papel="contraria", servico_id=id_):
                    achados.append(dict(x, parte=p["nome"]))
        return {"partes": partes, "conflitos": registrar(estado.base, achados, servico_id=id_)}

    @app.get("/api/servicos/{id_}/partes/sugeridas")
    def servicos_partes_sugeridas(id_: int) -> dict:
        """N3: a parte contrária sugerida pelos documentos do Serviço (a pessoa confirma)."""
        if not servicos_acesso.visivel(id_):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        try:
            return sugerir_partes(estado, id_)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.post("/api/servicos/{id_}/partes/dispensar")
    def servicos_partes_dispensar(id_: int, payload: Dispensar) -> dict:
        """"Não é parte": a sugestão deste nome não volta neste Serviço."""
        s = estado.base.um("SELECT partes_dispensadas FROM servicos WHERE id = ?", (id_,))
        if not s or not servicos_acesso.visivel(id_):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        lista = _json(s.get("partes_dispensadas"), [])
        k = chave(payload.nome)
        if k and k not in lista:
            lista.append(k)
        estado.base.escrever("UPDATE servicos SET partes_dispensadas = ? WHERE id = ?", (json.dumps(lista[-200:], ensure_ascii=False), id_))
        return {"dispensadas": len(lista)}

    @app.get("/api/servicos/{id_}/conflitos")
    def servicos_conflitos(id_: int) -> dict:
        """Os conflitos deste Serviço: o cliente dele do outro lado em outro Serviço, e as partes contrárias dele que são clientes."""
        import recursos_do_plano

        if not recursos_do_plano.pode(estado, "muralha"):
            return {"conflitos": [], "abertos": 0, "conferido": None, "resolucoes": [], "no_plano": recursos_do_plano.frase(estado, "muralha")}
        if not estado.base.um("SELECT id FROM servicos WHERE id = ?", (id_,)):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        # N4: cada conflito achado fica guardado como pendência; os já resolvidos vêm com a resolução.
        return {"conflitos": registrar(estado.base, do_servico(estado.base, id_), servico_id=id_)}

    @app.post("/api/clientes/conflitos")
    def clientes_conflitos(payload: Consulta) -> dict:
        import recursos_do_plano

        if not recursos_do_plano.pode(estado, "muralha"):
            return {"conflitos": [], "abertos": 0, "conferido": None, "resolucoes": [], "no_plano": recursos_do_plano.frase(estado, "muralha")}
        achados = conflitos(estado.base, payload.nome, payload.documento, papel=payload.papel,
                            servico_id=payload.servico_id, cadastro_id=payload.cadastro_id)
        if payload.cadastro_id or payload.servico_id:
            achados = registrar(estado.base, [dict(x, parte=x.get("parte") or payload.nome) for x in achados],
                                servico_id=payload.servico_id, cadastro_id=payload.cadastro_id)
        return {"conflitos": achados}

    @app.get("/api/conflitos")
    def conflitos_listar(situacao: str = "", cadastro_id: int | None = None, servico_id: int | None = None, conferir: bool = False) -> dict:
        """As pendências de conflito (N4); `conferir` refaz a conferência de todos os Serviços antes."""
        import recursos_do_plano

        if not recursos_do_plano.pode(estado, "muralha"):
            return {"conflitos": [], "abertos": 0, "conferido": None, "resolucoes": [], "no_plano": recursos_do_plano.frase(estado, "muralha")}
        feito = conferir_todos(estado.base) if conferir else None
        return {"conflitos": listar_conflitos(estado.base, estado=situacao, cadastro_id=cadastro_id, servico_id=servico_id),
                "abertos": estado.base.contar("conflitos", "estado = 'aberto'"), "conferido": feito,
                "resolucoes": [{"valor": k, "rotulo": v} for k, v in RESOLUCOES.items() if k != "sumiu"]}

    @app.get("/api/conflitos/{id_}")
    def conflitos_um(id_: int) -> dict:
        c = next((x for x in listar_conflitos(estado.base) if x["id"] == id_), None)
        if not c:
            raise HTTPException(status_code=404, detail="conflito não encontrado")
        return {"conflito": c, "resolucoes": [{"valor": k, "rotulo": v} for k, v in RESOLUCOES.items() if k != "sumiu"]}

    @app.post("/api/conflitos/{id_}/resolver")
    def conflitos_resolver(id_: int, payload: Resolucao, request: Request = None) -> dict:
        import recursos_do_plano

        recursos_do_plano.exigir(estado, "muralha")
        quem = _quem(request) or ((estado.prefs.dados.get("pessoa") or {}).get("nome") or "o escritório")
        try:
            return {"conflito": resolver(estado.base, id_, payload.resolucao, payload.nota, quem)}
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/conflitos/{id_}/reabrir")
    def conflitos_reabrir(id_: int, request: Request = None) -> dict:
        import recursos_do_plano

        recursos_do_plano.exigir(estado, "muralha")
        quem = _quem(request) or ((estado.prefs.dados.get("pessoa") or {}).get("nome") or "o escritório")
        try:
            return {"conflito": reabrir(estado.base, id_, quem)}
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.get("/api/clientes/{cadastro_id}/visao")
    def clientes_visao(cadastro_id: int) -> dict:
        try:
            return visao(estado, cadastro_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
