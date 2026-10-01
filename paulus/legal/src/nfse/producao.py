"""
A liberação da produção (N8): só o titular, só na janela do escritório.

Antes, um checklist que o PAULUS confere sozinho onde dá e pede à pessoa
onde só ela sabe:

1. a configuração fiscal revisada pelo contador ("revisado por … em …");
2. pelo menos 5 notas emitidas em produção restrita e conferidas por alguém
   (a pessoa marca que conferiu no portal e no DANFSe);
3. o certificado da nota válido;
4. o município com convênio confirmado (a consulta da produção restrita: a
   de produção só depois da liberação, porque o cliente tranca a produção);
5. o backup configurado (pasta e senha).

Liberar grava quem, quando e o checklist (tabela nfse_liberacao), muda o
ambiente da configuração e vai para a auditoria. "Voltar para produção
restrita" revoga e tranca de novo. A primeira nota de produção pede uma
confirmação a mais: "Esta nota vale de verdade. Conferiu os dados?".
"""

from __future__ import annotations

import json
from datetime import datetime

MINIMO_DE_TESTES = 5
FRASE_PRIMEIRA = "Esta nota vale de verdade. Conferiu os dados?"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Producao:
    def __init__(self, emissor) -> None:
        self.emissor = emissor
        self.base = emissor.base

    @property
    def _arquivo(self):
        return self.emissor.pasta / "producao.json"

    def _marcas(self) -> dict:
        try:
            return json.loads(self._arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def marcar_testes_conferidos(self, por: str) -> dict:
        por = " ".join(str(por or "").split())[:120]
        if not por:
            raise ValueError("diga quem conferiu as notas de teste")
        marcas = self._marcas()
        marcas["testes_conferidos_por"] = por
        marcas["testes_conferidos_em"] = _agora()
        self.emissor.pasta.mkdir(parents=True, exist_ok=True)
        self._arquivo.write_text(json.dumps(marcas, ensure_ascii=False, indent=1), encoding="utf-8")
        return self.checklist()

    def checklist(self, prefs_backup: dict | None = None) -> dict:
        prest = self.emissor.prestador.atual()["dados"]
        testes = self.base.contar("nfse_notas", "ambiente = 'producao_restrita' AND estado IN ('emitida','cancelada','substituida')")
        marcas = self._marcas()
        cert = (self.emissor.certificado_para_tela() or {}).get("certificado") or {}
        mun = self.emissor.municipios.situacao(prest.get("municipio") or "", "producao_restrita")
        backup = prefs_backup if prefs_backup is not None else (self.emissor.prefs.dados.get("backup") or {})
        itens = [
            {"id": "revisado", "ok": bool(prest.get("revisado_por")),
             "titulo": "Configuração fiscal revisada pelo contador",
             "detalhe": (f"revisada por {prest['revisado_por']} em {prest.get('revisado_em', '')}" if prest.get("revisado_por")
                         else "peça ao contador para revisar Configurações › Nota fiscal e registre quem revisou")},
            {"id": "testes", "ok": testes >= MINIMO_DE_TESTES and bool(marcas.get("testes_conferidos_por")),
             "titulo": f"Pelo menos {MINIMO_DE_TESTES} notas em produção restrita, emitidas e conferidas",
             "detalhe": f"{testes} emitida(s) em produção restrita" + (
                 f"; conferidas por {marcas['testes_conferidos_por']}" if marcas.get("testes_conferidos_por")
                 else "; falta marcar que alguém as conferiu (no portal e no DANFSe)")},
            {"id": "certificado", "ok": bool(cert) and not cert.get("erro") and not cert.get("vencido"),
             "titulo": "Certificado da nota válido",
             "detalhe": (f"válido até {cert.get('valido_ate', '')}" if cert and not cert.get("erro") else
                         (cert.get("erro") or "instale o certificado A1 da nota"))},
            {"id": "municipio", "ok": mun.get("situacao") == "conveniado",
             "titulo": "Município com convênio confirmado", "detalhe": mun.get("frase", "")},
            {"id": "backup", "ok": bool(backup.get("pasta")) and bool(backup.get("senha")),
             "titulo": "Backup configurado", "detalhe": ("pasta " + backup["pasta"]) if backup.get("pasta")
             else "configure o backup em Configurações › Backup (pasta e senha)"},
        ]
        lib = self.emissor.liberacao()
        return {"itens": itens, "pode_liberar": all(i["ok"] for i in itens), "liberada": lib is not None,
                "liberacao": lib, "ambiente": self.emissor.ambiente, "frase_primeira": FRASE_PRIMEIRA}

    def liberar(self, quem: str, confirmo: bool) -> dict:
        if not confirmo:
            raise ValueError("confirme que a nota em produção vale de verdade")
        ch = self.checklist()
        if ch["liberada"]:
            raise ValueError("a produção já está liberada")
        if not ch["pode_liberar"]:
            faltam = [i["titulo"] for i in ch["itens"] if not i["ok"]]
            raise ValueError("falta no checklist: " + "; ".join(faltam))
        self.base.escrever("INSERT INTO nfse_liberacao (liberado_em, liberado_por, checklist) VALUES (?,?,?)",
                           (_agora(), quem, json.dumps(ch["itens"], ensure_ascii=False)))
        self.emissor.prestador.mudar_ambiente("producao", quem, "produção liberada pelo titular")
        return self.checklist()

    def voltar(self, quem: str) -> dict:
        lib = self.emissor.liberacao()
        if lib:
            self.base.escrever("UPDATE nfse_liberacao SET revogado_em = ?, revogado_por = ? WHERE id = ?",
                               (_agora(), quem, lib["id"]))
        if self.emissor.ambiente != "producao_restrita":
            self.emissor.prestador.mudar_ambiente("producao_restrita", quem, "voltou para produção restrita")
        return self.checklist()

    def precisa_confirmar_primeira(self, nota: dict) -> bool:
        """A primeira nota de produção pede a confirmação a mais."""
        if nota.get("ambiente") != "producao":
            return False
        return self.base.contar("nfse_notas", "ambiente = 'producao' AND estado IN ('emitida','cancelada','substituida')") == 0
