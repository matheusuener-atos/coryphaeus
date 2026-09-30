"""
PAULUS - O agente do escritorio dentro da conversa (A2).

Um agente (src/agentes.py) e um especialista escrito pelo escritorio em
markdown. Aqui ele entra na conversa, com as garantias de sempre:

- **Escolha por regra primeiro.** Nesta ordem: o que a pessoa escolheu (na
  barra acima do campo, ou "@Nome" no texto); senao, os `exemplos` e as
  `palavras` do agente apontam candidatos; so na duvida ENTRE candidatos o
  juiz pequeno escolhe (src/juizo.py, uma letra). Sem candidato, a conversa
  segue como hoje. A escolha automatica e mostrada antes de a resposta
  comecar (`GET /api/agentes/sugerir`), com "trocar" e "nao usar".
- **O corpo do agente e instrucao do escritorio, abaixo das regras do
  produto.** Ele vai no fim da instrucao de sistema, cercado e rotulado como
  "instrucoes do agente <nome>"; nenhum agente revoga citar a fonte, nao
  inventar, confirmar antes de agir e respeitar as permissoes.
- **Um agente nunca amplia permissao.** `fontes` so restringe o escopo da
  busca; as ferramentas sao so as declaradas (e validadas contra o catalogo
  na A1) - o texto do agente nao da ferramenta nenhuma.

Chave: `conversa.agentes` (a mesma da A1).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Quantas palavras do agente, no minimo, fazem dele candidato sem exemplo.
PALAVRAS_MINIMAS = 1
# Semelhanca (palavras em comum / palavras do exemplo) para um exemplo contar.
SEMELHANCA_EXEMPLO = 0.6
PALAVRAS_VAZIAS = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "e", "em", "no", "na", "um", "uma", "que",
                   "este", "esta", "esse", "essa", "isto", "isso", "meu", "minha", "nosso", "nossa", "com", "para", "por"}

REGRA_DO_AGENTE = (
    "As instruções abaixo são de um agente escrito pelo escritório. Siga-as naquilo que não contrariar as regras "
    "acima: citar a fonte, não inventar, confirmar antes de qualquer ação e respeitar as permissões de quem pergunta. "
    "Nada nelas dá ferramenta, acesso ou permissão nova."
)


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _palavras(texto: str) -> list[str]:
    return [p for p in re.findall(r"[a-z0-9]+", _plano(texto)) if p not in PALAVRAS_VAZIAS and len(p) > 1]


@dataclass
class Escolha:
    agente: object | None            # agentes.Agente
    como: str = ""                    # "pedido" | "arroba" | "exemplo" | "palavras" | "juiz" | ""
    pergunta: str = ""                # a pergunta sem o "@Nome"
    candidatos: list[str] = field(default_factory=list)

    def para_tela(self) -> dict:
        a = self.agente
        return {"agente": ({"slug": a.slug, "nome": a.nome or a.slug, "versao": a.versao} if a else None),
                "como": self.como, "candidatos": self.candidatos}


def do_arroba(pergunta: str, agentes: list) -> tuple[object | None, str]:
    """
    "@Revisor revise este contrato" -> (o agente "Revisor de contratos",
    "revise este contrato"). A primeira palavra depois do @ tem de ser o
    comeco do nome (ou do slug) do agente; saem da pergunta o @ e as palavras
    do nome que vierem logo depois dele.
    """
    m = re.search(r"(?:^|\s)@(\S+)", pergunta)
    if not m:
        return None, pergunta
    dita = _plano(m.group(1)).strip(",.:;!?")
    if len(dita) < 3:
        return None, pergunta
    for a in agentes:
        for nome in (_plano(a.nome or ""), _plano(a.slug).replace("-", " ")):
            palavras = nome.split()
            if not palavras or not palavras[0].startswith(dita):
                continue
            depois = pergunta[m.end():].split()
            k = 0
            while k < len(depois) and k + 1 < len(palavras) and _plano(depois[k]).strip(",.:;") == palavras[k + 1]:
                k += 1
            limpa = (pergunta[: m.start()] + " " + " ".join(depois[k:])).strip()
            return a, limpa or pergunta
    return None, pergunta


def pontos(pergunta: str, agente) -> tuple[float, str]:
    """Quanto a pergunta parece com o que o agente diz servir: pelos exemplos, e depois pelas palavras."""
    p = set(_palavras(pergunta))
    plano = _plano(pergunta)
    melhor_exemplo = 0.0
    for ex in (agente.quando_usar or {}).get("exemplos") or []:
        pe = set(_palavras(ex))
        if not pe:
            continue
        if _plano(ex).strip(" ?.!") in plano:
            melhor_exemplo = 1.0
            break
        melhor_exemplo = max(melhor_exemplo, len(p & pe) / len(pe))
    if melhor_exemplo >= SEMELHANCA_EXEMPLO:
        return 1.0 + melhor_exemplo, "exemplo"
    achadas = [w for w in (agente.quando_usar or {}).get("palavras") or [] if _plano(w) and _plano(w) in plano]
    if len(achadas) >= PALAVRAS_MINIMAS:
        return 0.5 + 0.1 * len(achadas), "palavras"
    return 0.0, ""


def escolher(pergunta: str, agentes: list, *, pedido: str = "", sem_agente: bool = False, juiz=None) -> Escolha:
    """A escolha do agente desta pergunta. Nunca pelo modelo sozinho: o juiz so desempata candidatos."""
    if sem_agente or not agentes:
        _, limpa = do_arroba(pergunta, agentes) if agentes else (None, pergunta)
        return Escolha(None, "", limpa)
    if pedido:
        a = next((x for x in agentes if x.slug == pedido), None)
        _, limpa = do_arroba(pergunta, agentes)
        return Escolha(a, "pedido" if a else "", limpa)
    a, limpa = do_arroba(pergunta, agentes)
    if a is not None:
        return Escolha(a, "arroba", limpa)
    notas = sorted(((pontos(pergunta, x), x) for x in agentes), key=lambda t: t[0][0], reverse=True)
    notas = [(n, x) for n, x in notas if n[0] > 0]
    if not notas:
        return Escolha(None, "", pergunta)
    candidatos = [x.slug for _, x in notas]
    (n0, como0), a0 = notas[0]
    if len(notas) == 1 or n0 - notas[1][0][0] >= 0.3:
        return Escolha(a0, como0, pergunta, candidatos)
    # Empate entre candidatos: o juiz escolhe, so entre eles.
    if juiz is not None:
        try:
            opcoes = [(x.slug, (x.nome or x.slug) + ": " + (x.descricao or "")) for _, x in notas[:6]]
            r = juiz.escolher("Qual destes especialistas do escritório deve responder a este pedido?", opcoes,
                              entrada=pergunta, trocar_ordem=True)
            if r is not None and r.valor:
                a = next(x for _, x in notas if x.slug == r.valor)
                return Escolha(a, "juiz", pergunta, candidatos)
        except Exception:  # noqa: BLE001 - sem juiz, vale o de mais pontos
            pass
    return Escolha(a0, como0, pergunta, candidatos)


def instrucoes(agente) -> str:
    """O corpo do agente, cercado e rotulado, para o fim da instrucao de sistema."""
    corpo = (agente.instrucoes or "").strip()
    if not corpo:
        return ""
    nome = agente.nome or agente.slug
    return (f"{REGRA_DO_AGENTE}\n\n=== INSTRUÇÕES DO AGENTE “{nome}” (versão {agente.versao}) ===\n"
            f"{corpo}\n=== FIM DAS INSTRUÇÕES DO AGENTE “{nome}” ===")


def restringir(agente, em_foco: list[str], documentos) -> list[str] | None:
    """
    Os documentos a que o agente se restringe, ou None (sem restricao). So
    restringe: nunca devolve documento que nao estava aberto.
    """
    acervo = (agente.fontes or {}).get("acervo", "acervo")
    abertos = [getattr(d, "name", str(d)) for d in documentos]
    if acervo == "documento_em_foco":
        return [n for n in em_foco if n in abertos]
    if isinstance(acervo, dict) and acervo.get("pastas"):
        pastas = [_plano(p).strip("/\\") for p in acervo["pastas"]]
        dentro = []
        for d in documentos:
            caminho = _plano(str(getattr(d, "path", "") or getattr(d, "caminho", "") or getattr(d, "name", "")))
            if any(("/" + p + "/") in caminho.replace("\\", "/") or caminho.replace("\\", "/").startswith(p + "/") for p in pastas):
                dentro.append(getattr(d, "name", str(d)))
        return dentro
    return None


def pode_usar(agente, ferramenta: str) -> bool:
    """A ferramenta so vale se o agente a declarou (e a A1 validou contra o catalogo)."""
    return ferramenta in (agente.ferramentas or [])


# A acao que a conversa entendeu -> a ferramenta do catalogo que ela usa.
# "tarefa", "servico" e "abrir" (no programa do Windows) nao estao no
# catalogo: nenhum agente pode pedi-las.
FERRAMENTA_DA_ACAO = {"agenda": "criar_compromisso", "cadastro": "cadastrar_cliente", "nota": "emitir_nfse",
                      "exibir": "exibir_documento"}


def ferramenta_da_acao(tipo: str) -> str:
    return FERRAMENTA_DA_ACAO.get(tipo, tipo)


def frase_da_recusa(agente, ferramenta: str) -> str:
    nome = agente.nome or agente.slug
    tem = ", ".join(agente.ferramentas or []) or "nenhuma"
    return (f"O agente “{nome}” não usa a ferramenta “{ferramenta}”: ela não está declarada no AGENTE.md dele "
            f"(as dele: {tem}). Peça de novo sem o agente, ou peça ao titular para acrescentá-la.")


def sem_documento(agente) -> str:
    nome = agente.nome or agente.slug
    return (f"O agente “{nome}” lê só o documento em foco, e esta conversa ainda não tem nenhum: anexe o "
            "documento (ou digite / para escolher um) e pergunte de novo.")


def registrar_recusa(estado, trabalho, agente, ferramenta: str, pergunta: str) -> None:
    """A recusa fica na conversa e no registro dos agentes (data/agentes/recusas.jsonl)."""
    import json
    from datetime import datetime

    trabalho.registrar(f"Recusei a ferramenta “{ferramenta}” pedida com o agente “{agente.nome or agente.slug}”: "
                       "ele não a declara", mexer_na_ordem=False)
    try:
        pasta = getattr(estado.agentes, "pasta", None)
        if pasta is not None:
            with open(Path(pasta) / "recusas.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"em": datetime.now().isoformat(timespec="seconds"), "agente": agente.slug,
                                    "versao": agente.versao, "ferramenta": ferramenta, "conversa": trabalho.id,
                                    "pergunta": pergunta[:300]}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def executar_da_fila(estado, pedido) -> dict:
    """
    O sim em Aprovacoes para a ferramenta de um agente: executa pela mesma
    rota de sempre (src/ferramentas.py) e escreve na conversa o que foi feito.
    """
    import ferramentas

    dados = dict(pedido.dados or {})
    tipo, campos = dados.get("tipo", ""), dict(dados.get("campos") or {})
    if tipo not in ferramentas.POR_PROPOSTA:
        raise RuntimeError("não sei executar isto: " + tipo)
    feito = ferramentas.executar(ferramentas.POR_PROPOSTA[tipo], campos, estado)
    trabalho = estado.trabalhos.obter(dados.get("trabalho_id", ""))
    if trabalho is not None:
        trabalho.dizer("paulus", feito["resumo"] + " (confirmado em Aprovações).",
                       feito={"tipo": tipo, "id": feito["id"], "onde": feito["onde"],
                              "pendente": bool(feito.get("pendente")), "nome": str(campos.get("nome", ""))})
        estado.trabalhos.salvar(trabalho)
    return {"texto": feito["resumo"], "desfecho": {"onde": feito["onde"], "id": feito["id"]}}


def montar(estado, app) -> None:
    @app.get("/api/agentes/sugerir")
    def agentes_sugerir(texto: str = "") -> dict:
        """Qual agente a proxima pergunta usaria - so regra, sem modelo, para a barra mostrar antes de enviar."""
        conversa = estado.prefs.dados.get("conversa") or {}
        if not conversa.get("agentes") or getattr(estado, "agentes", None) is None:
            return {"ligado": False, "agente": None}
        try:
            ativos = estado.agentes.ativos()
        except Exception:  # noqa: BLE001
            ativos = []
        escolha = escolher(texto, ativos) if texto.strip() else Escolha(None)
        return {"ligado": True, **escolha.para_tela(),
                "ativos": [{"slug": a.slug, "nome": a.nome or a.slug, "versao": a.versao, "descricao": a.descricao}
                           for a in ativos]}
