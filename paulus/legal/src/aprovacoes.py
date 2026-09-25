"""
PAULUS - Fila de aprovacoes.

A regra central do manual: nada com efeito externo acontece sem o sim de uma
pessoa. Enviar e-mail, assinar, pagar, mover arquivo em lote e conceder acesso
param aqui.

Ate agora isso existia so dentro do organizador, como um cartao no meio da
conversa. Vira fila propria por dois motivos: as acoes que vem nas proximas
etapas precisam de um lugar comum para cair, e um pedido que sobrevive ao
fechamento do programa nao pode viver so na tela.

Quem executa a acao aprovada nao mora aqui. Este modulo guarda o pedido e a
decisao; a execucao fica com quem sabe fazer aquilo - o organizador move os
arquivos, o e-mail envia. Assim a fila nao precisa entender de nada.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

PENDENTE = "pendente"
APROVADO = "aprovado"
RECUSADO = "recusado"
FALHOU = "falhou"

# Categorias do manual. A etiqueta aparece na fila, ao lado do pedido.
CATEGORIAS = {
    "organizar": "Organizar pastas",
    "email": "E-mail",
    "assinatura": "Assinatura",
    "permissao": "Permissão",
    "financeiro": "Financeiro",
}


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Pedido:
    id: str
    titulo: str
    categoria: str
    resumo: str = ""
    etiquetas: list[str] = field(default_factory=list)
    pedido_por: str = "Assistente"
    acao: str = ""                       # quem executa sabe o que isto significa
    dados: dict = field(default_factory=dict)
    reversivel: bool = True
    prazo: str = ""                      # data ISO, quando o pedido tem prazo
    criado_em: str = field(default_factory=agora)
    estado: str = PENDENTE
    decidido_em: str = ""
    resultado: str = ""                  # o que aconteceu ao executar

    @property
    def categoria_rotulo(self) -> str:
        return CATEGORIAS.get(self.categoria, self.categoria)

    @property
    def vence_hoje(self) -> bool:
        return bool(self.prazo) and self.prazo[:10] <= datetime.now().strftime("%Y-%m-%d")

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados["categoria_rotulo"] = self.categoria_rotulo
        dados["vence_hoje"] = self.vence_hoje
        return dados


class Fila:
    """Pedidos em disco: fechar o programa nao apaga o que espera decisao."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._itens: dict[str, Pedido] = {}
        self._trava = threading.Lock()
        self.ao_pedir = None
        self._carregar()

    # ---------------------------------------------------------------- disco

    def _carregar(self) -> None:
        if not self.caminho.exists():
            return
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in bruto.get("pedidos", []):
            campos = {k: v for k, v in item.items() if k in Pedido.__dataclass_fields__}
            try:
                pedido = Pedido(**campos)
            except TypeError:
                continue
            self._itens[pedido.id] = pedido

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": 1, "pedidos": [asdict(p) for p in self._itens.values()]}
        self.caminho.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # --------------------------------------------------------------- acesso

    def pedir(self, titulo: str, categoria: str, **extras) -> Pedido:
        with self._trava:
            pedido = Pedido(id=uuid.uuid4().hex[:12], titulo=titulo, categoria=categoria, **extras)
            self._itens[pedido.id] = pedido
        self.salvar()
        # Quem precisa saber que chegou pedido (o aviso do Windows) se pendura
        # aqui; um aviso que falha nao pode desfazer o pedido gravado.
        if self.ao_pedir:
            try:
                self.ao_pedir(pedido)
            except Exception:  # noqa: BLE001
                pass
        return pedido

    def obter(self, id_: str) -> Pedido | None:
        return self._itens.get(id_)

    def decidir(self, id_: str, aprovado: bool) -> Pedido | None:
        pedido = self._itens.get(id_)
        if not pedido or pedido.estado != PENDENTE:
            return None
        pedido.estado = APROVADO if aprovado else RECUSADO
        pedido.decidido_em = agora()
        self.salvar()
        return pedido

    def registrar_resultado(self, id_: str, resultado: str, *, falhou: bool = False) -> None:
        pedido = self._itens.get(id_)
        if not pedido:
            return
        pedido.resultado = resultado
        if falhou:
            pedido.estado = FALHOU
        self.salvar()

    def esquecer(self, id_: str) -> bool:
        with self._trava:
            if id_ not in self._itens:
                return False
            del self._itens[id_]
        self.salvar()
        return True

    # ---------------------------------------------------------------- leitura

    @property
    def pendentes(self) -> list[Pedido]:
        return sorted(
            (p for p in self._itens.values() if p.estado == PENDENTE),
            key=lambda p: p.criado_em,
        )

    def decididos_hoje(self) -> list[Pedido]:
        hoje = datetime.now().strftime("%Y-%m-%d")
        return sorted(
            (p for p in self._itens.values()
             if p.estado != PENDENTE and p.decidido_em[:10] == hoje),
            key=lambda p: p.decidido_em,
            reverse=True,
        )

    def leitura(self) -> dict:
        """
        O que a fila diz sobre si mesma.

        O manual chama isso de "leitura da fila": frases curtas que ajudam a
        decidir o que ver primeiro, com numero real - nunca "voce tem pedidos
        pendentes", que nao ajuda ninguem.
        """
        pendentes = self.pendentes
        decididos = self.decididos_hoje()
        com_prazo = [p for p in pendentes if p.vence_hoje]
        irreversiveis = [p for p in pendentes if not p.reversivel]

        linhas: list[str] = []
        if com_prazo:
            linhas.append(f"{len(com_prazo)} com prazo hoje")
        if irreversiveis:
            linhas.append(f"{len(irreversiveis)} sem desfazer depois")
        if decididos:
            aprovadas = sum(1 for p in decididos if p.estado == APROVADO)
            linhas.append(f"{aprovadas} aprovada(s) hoje")

        return {
            "pendentes": len(pendentes),
            "com_prazo": len(com_prazo),
            "irreversiveis": len(irreversiveis),
            "decididos_hoje": len(decididos),
            "linhas": linhas,
        }

    def para_tela(self) -> dict:
        return {
            "pendentes": [p.to_dict() for p in self.pendentes],
            "hoje": [p.to_dict() for p in self.decididos_hoje()],
            "leitura": self.leitura(),
        }
