"""
PAULUS - A medida dos agentes do escritorio (A4).

Um agente e um texto que o modelo segue. Trocar o modelo da maquina, ou
editar o texto, pode fazer o agente deixar de acertar o que acertava - e
ninguem percebe olhando a lista. Aqui fica, por agente, o que da para medir
sem ler conversa nenhuma de novo:

- **o ultimo resultado dos testes** (`testes` do AGENTE.md), rodados pelo
  Testar da tela ou por `tools/medir.py --agentes`, com a versao testada e o
  que faltou em cada falha;
- **vezes usado**: um contador, somado quando a pergunta SAI com o agente
  (escolhido pela pessoa, por "@Nome" ou pela regra). Contar pelas respostas
  guardadas pediria abrir todas as conversas a cada vez que a tela abre, e a
  conta mudaria quando alguem apaga uma conversa; o contador e barato e nao
  depende do que foi apagado. A pergunta parada no meio tambem conta: o
  agente foi usado;
- **vezes "nao usar"**: a pessoa escolheu "sem agente" numa pergunta para a
  qual a regra sugeria um agente. So conta quando havia sugestao: escolher
  "sem agente" numa pergunta que nao tinha agente nenhum nao diz nada sobre
  agente nenhum.

"Respostas avaliadas como ruins" fica de fora: o programa nao tem avaliacao
de resposta (nenhum polegar, nenhum "resposta ruim" na conversa). A tela diz
"sem avaliação", em vez de mostrar um zero que pareceria medida.

**Precisa de revisao**: o ultimo resultado, DA VERSAO ATUAL, teve falha. O
agente continua funcionando pelo nome (barra ou "@Nome"), mas a escolha
automatica (exemplos e palavras) o pula ate alguem revisar - salvar uma
versao nova (a versao muda, e o resultado antigo deixa de valer) ou rodar os
testes de novo e passar.

Tudo mora em `data/agentes/<slug>/medida.json`, na pasta do agente; nada
sai da maquina.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

ARQUIVO = "medida.json"
# O que fica de cada teste que falhou: a pergunta, o que faltou e o erro.
# A resposta inteira nao: ela ja volta para a tela na hora do teste, e aqui
# seria so texto de documento de cliente guardado a toa.
MAX_FALHAS = 20
SEM_AVALIACAO = "sem avaliação: o programa ainda não avalia respostas"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Medidas:
    """
    As medidas dos agentes de uma pasta: um `medida.json` dentro da pasta de
    cada agente, ao lado do AGENTE.md e do estado.json. Dentro da pasta, e nao
    num arquivo so para todos, porque a medida e daquele agente: apagada a
    pasta, a conta vai junto, e um agente novo com o mesmo nome comeca do zero.
    """

    def __init__(self, pasta: Path | str) -> None:
        self.pasta = Path(pasta)
        self._trava = threading.Lock()

    def _arquivo(self, slug: str) -> Path:
        return self.pasta / slug / ARQUIVO

    def de(self, slug: str) -> dict:
        try:
            dados = json.loads(self._arquivo(slug).read_text(encoding="utf-8"))
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            # Ainda sem medida, ou arquivo estragado: comeca do zero, e a
            # proxima conta o regrava inteiro. Nao vale derrubar a conversa.
            return {}

    def todas(self) -> dict:
        if not self.pasta.is_dir():
            return {}
        return {p.name: self.de(p.name) for p in self.pasta.iterdir() if (p / ARQUIVO).is_file()}

    def _mudar(self, slug: str, mudar) -> dict:
        pasta = self.pasta / slug
        with self._trava:
            # Agente que nao existe (apagado no meio) nao ganha pasta nova.
            if not pasta.is_dir():
                return {}
            m = self.de(slug)
            mudar(m)
            temp = pasta / (ARQUIVO + ".tmp")
            temp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(pasta / ARQUIVO)
            return m

    def registrar_teste(self, slug: str, resultado: dict, *, origem: str = "tela") -> dict:
        """Guarda o resultado de `agentes.rodar_testes` como o ultimo deste agente."""
        falhas = [{"pergunta": r.get("pergunta", ""), "faltou": list(r.get("faltou") or []), "erro": r.get("erro", "")}
                  for r in resultado.get("resultados") or [] if not r.get("passou")]
        teste = {"em": _agora(), "versao": int(resultado.get("versao") or 0), "total": int(resultado.get("total") or 0),
                 "passaram": int(resultado.get("passaram") or 0), "falhas": falhas[:MAX_FALHAS], "origem": origem}
        self._mudar(slug, lambda m: m.__setitem__("teste", teste))
        return teste

    def contar(self, slug: str, qual: str) -> int:
        """Soma 1 em `usado` ou `nao_usar` e devolve o total."""
        if qual not in ("usado", "nao_usar"):
            raise ValueError(qual)

        def somar(m: dict) -> None:
            m[qual] = int(m.get(qual) or 0) + 1
            m[qual + "_em"] = _agora()

        return int(self._mudar(slug, somar).get(qual) or 0)


def precisa_revisao(versao: int, medida: dict) -> bool:
    """O ultimo teste e desta versao e alguma pergunta falhou."""
    t = (medida or {}).get("teste") or {}
    total = int(t.get("total") or 0)
    return bool(total) and int(t.get("versao") or 0) == int(versao or 0) and int(t.get("passaram") or 0) < total


def motivo_da_revisao(medida: dict) -> str:
    """Em uma frase, para a tela: o que falhou e o que fazer."""
    t = (medida or {}).get("teste") or {}
    falhas = t.get("falhas") or []
    partes = []
    for f in falhas[:3]:
        if f.get("erro"):
            partes.append(f"“{f.get('pergunta', '')}” deu erro ({f['erro'][:80]})")
        else:
            partes.append(f"“{f.get('pergunta', '')}”: faltou " + ", ".join(f.get("faltou") or []))
    quando = str(t.get("em") or "")[:10]
    data = f"{quando[8:10]}/{quando[5:7]}" if len(quando) == 10 else ""
    return (f"os testes da versão {t.get('versao')} falharam em {int(t.get('total') or 0) - int(t.get('passaram') or 0)} "
            f"de {t.get('total')}" + (f" ({data})" if data else "") + (": " + "; ".join(partes) if partes else "")
            + ". Ele não é escolhido sozinho até alguém revisar: salvar uma versão nova, ou testar de novo e passar.")


def resumo(versao: int, medida: dict) -> dict:
    """O que o painel mostra por agente."""
    m = medida or {}
    t = m.get("teste") or {}
    return {
        "testes": ({"passaram": int(t.get("passaram") or 0), "total": int(t.get("total") or 0), "versao": t.get("versao"),
                    "em": t.get("em", ""), "origem": t.get("origem", ""), "falhas": t.get("falhas") or [],
                    "da_versao_atual": int(t.get("versao") or 0) == int(versao or 0)} if t else None),
        "usado": int(m.get("usado") or 0), "usado_em": m.get("usado_em", ""),
        "nao_usar": int(m.get("nao_usar") or 0), "nao_usar_em": m.get("nao_usar_em", ""),
        # Sem avaliacao de resposta no programa: None, e nao zero.
        "ruins": None, "ruins_aviso": SEM_AVALIACAO,
    }


def _medidas(estado) -> Medidas | None:
    ag = getattr(estado, "agentes", None)
    return getattr(ag, "medidas", None) if ag is not None else None


def usou(estado, agente) -> None:
    """A pergunta saiu com este agente. Nunca para a conversa por causa da conta."""
    m = _medidas(estado)
    if m is None or agente is None:
        return
    try:
        m.contar(agente.slug, "usado")
    except (OSError, ValueError):
        pass


def anotar_nao_usar(estado, pergunta: str, ativos: list) -> str:
    """
    A pessoa escolheu "sem agente". Se a regra sugeria um agente para esta
    pergunta (exemplos ou palavras - a mesma conta da barra, sem juiz), soma
    no "nao usar" dele. Devolve o slug contado, ou "".
    """
    m = _medidas(estado)
    if m is None or not ativos:
        return ""
    import agente_na_conversa

    try:
        escolha = agente_na_conversa.escolher(pergunta, ativos)
        if escolha.agente is None or escolha.como not in ("exemplo", "palavras"):
            return ""
        m.contar(escolha.agente.slug, "nao_usar")
        return escolha.agente.slug
    except (OSError, ValueError):
        return ""


__all__ = ["Medidas", "SEM_AVALIACAO", "anotar_nao_usar", "motivo_da_revisao", "precisa_revisao", "resumo", "usou"]
