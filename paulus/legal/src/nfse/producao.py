"""
A liberação da produção (N8): só o titular, só na janela do escritório.

Antes, um checklist que o PAULUS confere sozinho. Travam a liberação:

1. a configuração fiscal completa;
2. o certificado da nota válido;
3. o município com convênio confirmado (a consulta da produção restrita: a
   de produção só depois da liberação, porque o cliente tranca a produção);
4. o teste do assistente (teste.py) feito com sucesso com a configuração de
   agora: uma nota emitida e cancelada em produção restrita.

Recomendados, sem travar (o escritório decide): a revisão do contador e o
backup configurado.

Liberar grava quem, quando e o checklist (tabela nfse_liberacao), muda o
ambiente da configuração e vai para a auditoria. "Voltar para produção
restrita" revoga e tranca de novo. A primeira nota de produção pede uma
confirmação a mais: "Esta nota vale de verdade. Conferiu os dados?".
"""

from __future__ import annotations

import json
from datetime import datetime

from . import tabelas

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

    def checklist(self, prefs_backup: dict | None = None) -> dict:
        prest = self.emissor.prestador.atual()["dados"]
        marcas_teste = self.emissor.teste.ultimo()
        cert = (self.emissor.certificado_para_tela() or {}).get("certificado") or {}
        mun = self.emissor.municipios.situacao(prest.get("municipio") or "", "producao_restrita")
        backup = prefs_backup if prefs_backup is not None else (self.emissor.prefs.dados.get("backup") or {})
        faltas = self.emissor.prestador.para_tela()["faltas"]
        if marcas_teste.get("vale_para_agora"):
            det_teste = f"nota nº {marcas_teste.get('numero', '')} emitida e cancelada em {marcas_teste.get('em', '')[:16].replace('T', ' ')}"
        elif marcas_teste.get("ok"):
            det_teste = "a configuração mudou depois do último teste: faça o teste de novo"
        elif marcas_teste:
            det_teste = marcas_teste.get("frase", "")
        else:
            det_teste = "faça o teste no passo 4"
        itens = [
            {"id": "configuracao", "ok": not faltas, "titulo": "Configuração completa",
             "detalhe": "tudo preenchido" if not faltas else "falta " + "; ".join(faltas)},
            {"id": "certificado", "ok": bool(cert) and not cert.get("erro") and not cert.get("vencido"),
             "titulo": "Certificado da nota válido",
             "detalhe": (f"válido até {cert.get('valido_ate', '')}" if cert and not cert.get("erro") else
                         (cert.get("erro") or "instale o certificado A1 da nota"))},
            {"id": "municipio", "ok": mun.get("situacao") == "conveniado",
             "titulo": "Município com convênio confirmado",
             # O item fala do convênio, não de "já dá para emitir": com a
             # emissão desligada, a frase da consulta prometeria demais.
             "detalhe": (f"{_nome_do_municipio(prest.get('municipio') or '')} tem convênio ativo com o Sistema Nacional "
                         "da NFS-e" if mun.get("situacao") == "conveniado" else mun.get("frase", ""))},
            {"id": "teste", "ok": bool(marcas_teste.get("vale_para_agora")),
             "titulo": "Teste feito com sucesso", "detalhe": det_teste},
        ]
        recomendados = [
            {"id": "revisado", "ok": bool(prest.get("revisado_por")),
             "titulo": "Configuração conferida pelo contador",
             "detalhe": (f"conferida por {prest['revisado_por']} em {prest.get('revisado_em', '')}" if prest.get("revisado_por")
                         else "peça ao contador para conferir o regime e as retenções")},
            {"id": "backup", "ok": bool(backup.get("pasta")) and bool(backup.get("senha")),
             "titulo": "Backup configurado", "detalhe": ("pasta " + backup["pasta"]) if backup.get("pasta")
             else "configure o backup em Configurações › Backup"},
        ]
        lib = self.emissor.liberacao()
        return {"itens": itens, "recomendados": recomendados, "pode_liberar": all(i["ok"] for i in itens),
                "liberada": lib is not None, "teste": marcas_teste,
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
                           (_agora(), quem, json.dumps(ch["itens"] + ch["recomendados"], ensure_ascii=False)))
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


def _nome_do_municipio(cmun: str) -> str:
    m = tabelas.municipio(cmun) or {}
    return f"{m.get('nome', cmun)}/{m.get('uf', '')}".rstrip("/") if m else (cmun or "o município")
