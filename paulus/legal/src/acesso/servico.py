"""
O acesso de fora montado: as contas, o portao, o tunel e a auditoria, num
objeto so, que o api.py cria uma vez e o porteiro consulta a cada pedido.
"""

from __future__ import annotations

import time
from pathlib import Path

from acesso.contas import Contas
from acesso.remoto import PortaoRemoto


class AcessoDeFora:
    def __init__(self, dados_dir: Path, prefs, chave) -> None:
        self.dados_dir = Path(dados_dir)
        self.pasta = self.dados_dir / "acesso"
        self.prefs = prefs
        self.chave = chave
        self.contas = Contas(self.pasta / "contas.db", ao_bloquear=self._bloqueou)
        # O conferidor do JWT do Cloudflare Access (jwt_access.py). Sem ele -
        # tunel nunca conectado -, ninguem de fora passa.
        self.verificar_jwt = None
        # Os ultimos eventos, para a tela; o registro que vale e o da
        # auditoria (R8), quando existir.
        self.eventos: list[dict] = []
        self.auditoria = None
        self.ao_mudar_contas = []
        self.portao = PortaoRemoto(self.contas, self.ligado, self._conferir_jwt, registrar=self.anotar)

    # ------------------------------------------------------------- estado

    def preferencias(self) -> dict:
        return dict(self.prefs.dados.get("acesso_remoto") or {})

    def ligado(self) -> bool:
        return bool(self.preferencias().get("ligado"))

    def _conferir_jwt(self, token: str):
        return self.verificar_jwt(token) if self.verificar_jwt else None

    # ------------------------------------------------------------ eventos

    def anotar(self, **evento) -> None:
        evento.setdefault("quando", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.eventos = (self.eventos + [evento])[-200:]
        if self.auditoria is not None:
            try:
                self.auditoria.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria nao derruba o pedido
                pass

    def _bloqueou(self, email: str, nome: str, ate: float) -> None:
        minutos = max(1, round((ate - time.time()) / 60))
        quem = nome or email
        self.anotar(acao="bloqueio", alvo=f"{minutos} min", pessoa=quem, email=email)
        try:
            import avisos

            avisos.avisar("acesso", "Acesso de fora bloqueado",
                          f"Alguém errou a senha de {quem} 5 vezes. A conta ficou bloqueada por {minutos} min.")
        except Exception:  # noqa: BLE001 - sem aviso do Windows, o evento fica na tela
            pass

    def contas_mudaram(self) -> None:
        """Criou, mudou ou tirou conta: quem depende da lista (o Access, na R7) fica sabendo."""
        for f in list(self.ao_mudar_contas):
            try:
                f()
            except Exception:  # noqa: BLE001
                pass
