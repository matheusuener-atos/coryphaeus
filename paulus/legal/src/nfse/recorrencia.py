"""
Honorários recorrentes e a rotina diária da nota fiscal (N7).

"Emitir todo mês no dia X": no dia, o PAULUS cria o RASCUNHO da nota (com o
tomador, o valor e a descrição do mês) e, se o rascunho estiver completo, o
põe em Aprovações. **Nunca emite sozinho**: a recorrência só faz o que a
pessoa faria clicando em "Emitir nota" e "Pedir aprovação". Um rascunho por
mês e por recorrência — o mês feito fica gravado (chave única).

A rotina diária, no fio da fila, roda uma vez por dia: as recorrências do
dia, a reconsulta mensal do município (para saber se a alíquota ou o prazo
mudaram) e a conferência periódica da documentação oficial (se o portal
publicou XSD novo).
"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date, datetime

log = logging.getLogger("paulus.nfse")

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Recorrencias:
    def __init__(self, emissor) -> None:
        self.emissor = emissor
        self.base = emissor.base

    def listar(self) -> list[dict]:
        linhas = self.base.buscar(
            "SELECT r.*, s.nome AS servico_nome, c.nome AS cliente_nome, "
            "(SELECT MAX(mes) FROM nfse_recorrencias_feitas f WHERE f.recorrencia_id = r.id) AS ultimo_mes "
            "FROM nfse_recorrencias r LEFT JOIN servicos s ON s.id = r.servico_id "
            "LEFT JOIN cadastros c ON c.id = COALESCE(r.cadastro_id, s.cadastro_id) ORDER BY r.id")
        from .dinheiro import reais

        for l in linhas:
            l["valor"] = reais(int(l["centavos"]))
        return linhas

    def salvar(self, dados: dict, quem: str = "titular") -> dict:
        from .dinheiro import centavos_de_texto

        dia = int(dados.get("dia") or 0)
        if not 1 <= dia <= 31:
            raise ValueError("o dia do mês vai de 1 a 31 (num mês mais curto, vale o último dia)")
        centavos = centavos_de_texto(dados.get("valor")) if "valor" in dados else int(dados.get("centavos") or 0)
        if centavos <= 0:
            raise ValueError("o valor mensal precisa ser maior que zero")
        servico_id = dados.get("servico_id") or None
        cadastro_id = dados.get("cadastro_id") or None
        if not servico_id and not cadastro_id:
            raise ValueError("a recorrência é de um Serviço ou de um cliente")
        descricao = " ".join(str(dados.get("descricao") or "").split())[:500]
        if dados.get("id"):
            self.base.escrever("UPDATE nfse_recorrencias SET dia=?, centavos=?, descricao=?, ativo=1 WHERE id=?",
                               (dia, centavos, descricao, int(dados["id"])))
            return self.obter(int(dados["id"]))
        id_ = self.base.escrever(
            "INSERT INTO nfse_recorrencias (servico_id, cadastro_id, dia, centavos, descricao, ativo, criado_em, criado_por) "
            "VALUES (?,?,?,?,?,1,?,?)", (servico_id, cadastro_id, dia, centavos, descricao, _agora(), quem))
        return self.obter(id_)

    def obter(self, id_: int) -> dict | None:
        return next((r for r in self.listar() if r["id"] == int(id_)), None)

    def desligar(self, id_: int) -> dict | None:
        self.base.escrever("UPDATE nfse_recorrencias SET ativo = 0 WHERE id = ?", (int(id_),))
        return self.obter(id_)

    # ------------------------------------------------------------ o dia

    @staticmethod
    def dia_efetivo(dia: int, hoje: date) -> int:
        """Dia 31 em fevereiro é o último dia de fevereiro."""
        return min(int(dia), calendar.monthrange(hoje.year, hoje.month)[1])

    def rodar(self, estado, hoje: date | None = None) -> list[dict]:
        """As recorrências do dia: o rascunho e o pedido de aprovação. Devolve o que fez."""
        hoje = hoje or date.today()
        mes = hoje.isoformat()[:7]
        feitas = []
        if not self.emissor.ligado:
            return feitas
        for r in self.base.buscar("SELECT * FROM nfse_recorrencias WHERE ativo = 1"):
            if hoje.day < self.dia_efetivo(r["dia"], hoje):
                continue
            # Reserva o mês ANTES de criar: duas rodadas no mesmo dia não fazem duas notas.
            try:
                self.base.escrever("INSERT INTO nfse_recorrencias_feitas (recorrencia_id, mes, feito_em) VALUES (?,?,?)",
                                   (r["id"], mes, _agora()))
            except Exception:  # noqa: BLE001 - o mês já foi feito (chave única)
                continue
            nome_mes = f"{MESES[hoje.month - 1]}/{hoje.year}"
            prest = self.emissor.prestador.atual()["dados"]
            base_desc = r.get("descricao") or (prest.get("servico") or {}).get("descricao") or "Honorários advocatícios"
            dados = {"servico_id": r.get("servico_id"), "cadastro_id": r.get("cadastro_id"), "recorrencia_id": r["id"],
                     "valor_centavos": int(r["centavos"]), "competencia": hoje.replace(day=1).isoformat(),
                     "descricao": f"{base_desc} — {nome_mes}"}
            nota = self.emissor.notas.criar(dados, origem="recorrencia", quem="recorrência")
            self.base.escrever("UPDATE nfse_recorrencias_feitas SET nota_id = ? WHERE recorrencia_id = ? AND mes = ?",
                               (nota["id"], r["id"], mes))
            resultado = {"recorrencia_id": r["id"], "nota_id": nota["id"], "pedido": False, "erros": nota["erros"]}
            if not nota["erros"]:
                from . import fluxo

                try:
                    fluxo.pedir_aprovacao(estado, nota["id"], quem="recorrência")
                    resultado["pedido"] = True
                except ValueError as exc:
                    resultado["erros"] = [str(exc)]
            feitas.append(resultado)
        return feitas

    def avisos(self, hoje: date | None = None) -> list[dict]:
        """O rascunho da recorrência do mês: em Aprovações, ou precisando de você."""
        hoje = hoje or date.today()
        mes = hoje.isoformat()[:7]
        saida = []
        for f in self.base.buscar("SELECT f.*, n.estado, n.tomador_nome, n.centavos FROM nfse_recorrencias_feitas f "
                                  "JOIN nfse_notas n ON n.id = f.nota_id WHERE f.mes = ?", (mes,)):
            from .dinheiro import reais

            if f["estado"] == "aguardando_aprovacao":
                titulo = f"Honorários do mês — NFS-e de {f['tomador_nome'] or 'cliente'} em Aprovações"
            elif f["estado"] == "rascunho":
                titulo = f"Honorários do mês — o rascunho da NFS-e de {f['tomador_nome'] or 'cliente'} precisa de você"
            else:
                continue
            saida.append({"id": f"nfse:recorrencia:{f['recorrencia_id']}:{mes}", "titulo": titulo,
                          "detalhe": reais(int(f["centavos"] or 0)) + " · nada é emitido sem o seu sim", "nota_id": f["nota_id"]})
        return saida


# ---------------------------------------------------------------- rotina

URL_DOCUMENTACAO = "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual"
XSD_CONHECIDO = "nfse-esquemas_xsd-v1-01-20260209.zip"


def conferir_documentacao(baixar=None) -> dict:
    """
    O portal publicou esquema novo? Lê a página oficial da documentação atual
    (pública, sem certificado) e compara o nome do .zip dos XSD com o que o
    PAULUS traz. `baixar(url) -> texto` existe para o teste.
    """
    if baixar is None:
        import requests

        def baixar(url):
            return requests.get(url, timeout=20, headers={"User-Agent": "PAULUS-Legal"}).text
    try:
        texto = baixar(URL_DOCUMENTACAO)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erro": str(exc)[:200]}
    nomes = sorted(set(re.findall(r"nfse-esquemas_xsd[^\"'/<>\s]*\.zip", texto, re.I)))
    novos = [n for n in nomes if n.lower() != XSD_CONHECIDO]
    return {"ok": True, "publicados": nomes, "novos": novos, "conferido_em": _agora()}
