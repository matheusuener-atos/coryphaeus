"""
"Quem acessou" (R8): o registro de tudo o que acontece pelo acesso de fora.

Um arquivo so, que so cresce (data/acesso/acessos.jsonl), uma linha por
acontecimento: entrada e saida, login que falhou, bloqueio, documento aberto
ou baixado de fora, aprovacao feita de fora, proposta, pedido recusado por
ser so do escritorio - e as mudancas do proprio modulo (conectar, desligar,
remover).

Cada linha guarda o sha256 da anterior somado ao proprio conteudo: mudar uma
letra de uma linha antiga quebra a corrente dali em diante, e a tela diz em
qual linha. Nao impede ninguem de apagar o arquivo inteiro - quem tem a
maquina tem o arquivo -, mas torna visivel a edicao escondida, que e o que um
registro de controle precisa mostrar (LGPD: documentar quem viu o que).

Guardado por um ano. O que sai pela idade deixa o hash da ultima linha que
saiu num arquivo ao lado (acessos.ancora), e a conferencia comeca dele.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

RETENCAO_DIAS = 365

ACOES = {
    "entrada": "entrou",
    "saida": "saiu",
    "login_falho": "errou a entrada",
    "bloqueio": "conta bloqueada",
    "documento": "abriu documento",
    "download": "baixou",
    "aprovacao": "aprovou",
    "recusa": "recusou",
    "proposta": "propôs",
    "recusado": "tentou o que é só do escritório",
    "conexao": "conectou o acesso de fora",
    "ligado": "ligou o acesso de fora",
    "desligado": "desligou o acesso de fora",
    "removido": "removeu o acesso de fora",
    "liberado": "endereço liberado por falta de uso",
    "senha": "trocou a senha",
    "sessoes": "encerrou as sessões",
    "permissoes": "mudou as permissões",
}
CAMPOS = ("quando", "pessoa", "email", "ip", "acao", "alvo")


def _resumo(anterior: str, conteudo: dict) -> str:
    bruto = anterior + json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


class Auditoria:
    def __init__(self, caminho: Path, relogio=time.time) -> None:
        self.caminho = Path(caminho)
        self.ancora = self.caminho.with_suffix(".ancora")
        self.relogio = relogio
        self._trava = threading.Lock()
        self._ultimo: str | None = None
        # Documento aberto de fora: a mesma pessoa folheando as paginas do
        # mesmo documento vira UMA linha a cada 10 minutos, e nao uma por pagina.
        self._vistos: dict[tuple[str, str], float] = {}

    # ---------------------------------------------------------- registrar

    def _ultimo_hash(self) -> str:
        if self._ultimo is not None:
            return self._ultimo
        ultimo = self._ler_ancora()
        try:
            with open(self.caminho, "rb") as f:
                for linha in f:
                    if linha.strip():
                        ultimo = json.loads(linha).get("hash", ultimo)
        except (OSError, ValueError):
            pass
        self._ultimo = ultimo
        return ultimo

    def _ler_ancora(self) -> str:
        try:
            return self.ancora.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def registrar(self, *, acao: str, alvo: str = "", pessoa: str = "", email: str = "", ip: str = "",
                  quando: str = "", **_resto) -> dict | None:
        agora = self.relogio()
        if acao == "documento":
            chave = (pessoa or email, alvo)
            if agora - self._vistos.get(chave, 0) < 600:
                return None
            self._vistos[chave] = agora
        conteudo = {
            "quando": datetime.fromtimestamp(agora).isoformat(timespec="seconds"),
            "pessoa": str(pessoa or "")[:120], "email": str(email or "")[:200], "ip": str(ip or "")[:64],
            "acao": str(acao)[:40], "alvo": str(alvo or "")[:400],
        }
        with self._trava:
            anterior = self._ultimo_hash()
            linha = {**conteudo, "anterior": anterior, "hash": _resumo(anterior, conteudo)}
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            self._ultimo = linha["hash"]
        return linha

    # ----------------------------------------------------------- conferir

    def linhas(self) -> list[dict]:
        saida = []
        try:
            with open(self.caminho, encoding="utf-8") as f:
                for texto in f:
                    if texto.strip():
                        try:
                            saida.append(json.loads(texto))
                        except ValueError:
                            saida.append({"quebrada": texto.strip()[:200]})
        except OSError:
            pass
        return saida

    def verificar(self) -> dict:
        """A corrente inteira: intacta, ou a primeira linha em que quebrou (1 = a primeira)."""
        anterior = self._ler_ancora()
        todas = self.linhas()
        for n, linha in enumerate(todas, start=1):
            conteudo = {k: linha.get(k, "") for k in CAMPOS}
            if "quebrada" in linha or linha.get("anterior") != anterior or linha.get("hash") != _resumo(anterior, conteudo):
                return {"integro": False, "linha": n, "total": len(todas)}
            anterior = linha["hash"]
        return {"integro": True, "linha": 0, "total": len(todas)}

    # ----------------------------------------------------------- guardar

    def podar(self, dias: int = RETENCAO_DIAS) -> int:
        """Tira o que passou de um ano; a ancora guarda o hash da ultima que saiu."""
        limite = (datetime.fromtimestamp(self.relogio()) - timedelta(days=dias)).isoformat(timespec="seconds")
        with self._trava:
            todas = self.linhas()
            # So se poda do comeco: o arquivo e em ordem de tempo, e a corrente
            # continua valendo da ancora em diante.
            n = 0
            for l in todas:
                if "quebrada" in l or str(l.get("quando", "")) >= limite:
                    break
                n += 1
            if not n:
                return 0
            self.ancora.write_text(todas[n - 1]["hash"], encoding="utf-8")
            with open(self.caminho, "w", encoding="utf-8") as f:
                for l in todas[n:]:
                    f.write(json.dumps(l, ensure_ascii=False) + "\n")
            self._ultimo = None
        return n

    # -------------------------------------------------------------- tela

    def filtrar(self, *, pessoa: str = "", acao: str = "", de: str = "", ate: str = "", texto: str = "") -> list[dict]:
        pessoa, texto = pessoa.strip().lower(), texto.strip().lower()
        saida = []
        for l in self.linhas():
            if "quebrada" in l:
                continue
            quando = str(l.get("quando", ""))
            if pessoa and pessoa not in (str(l.get("pessoa", "")) + " " + str(l.get("email", ""))).lower():
                continue
            if acao and l.get("acao") != acao:
                continue
            if de and quando[:10] < de:
                continue
            if ate and quando[:10] > ate:
                continue
            if texto and texto not in json.dumps(l, ensure_ascii=False).lower():
                continue
            saida.append({**{k: l.get(k, "") for k in CAMPOS}, "acao_rotulo": ACOES.get(l.get("acao", ""), l.get("acao", ""))})
        return saida

    def pdf(self, linhas: list[dict], titulo: str = "Registro de acessos de fora") -> bytes:
        """O registro filtrado em PDF, pelo reportlab que o programa ja usa, com o estado da corrente."""
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        estilos = getSampleStyleSheet()
        pequeno = estilos["BodyText"].clone("pequeno", fontSize=8, leading=10)
        saida = BytesIO()
        doc = SimpleDocTemplate(saida, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                                topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=titulo, author="PAULUS")
        conf = self.verificar()
        estado = (f"Corrente de hashes íntegra: {conf['total']} linha(s) conferidas." if conf["integro"]
                  else f"ATENÇÃO: o registro foi alterado — a corrente de hashes quebra na linha {conf['linha']} de {conf['total']}.")
        corpo = [Paragraph(titulo, estilos["Title"]),
                 Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} neste computador. {estado}", estilos["BodyText"]),
                 Paragraph("Cada linha guarda o sha256 da anterior: editar uma linha antiga quebra a corrente a partir dela. "
                           "O IP é o que a Cloudflare informou, só para referência.", pequeno),
                 Spacer(1, 10)]
        dados = [["Data e hora", "Pessoa", "E-mail (Cloudflare)", "IP", "O que aconteceu", "Sobre o quê"]]
        for l in linhas:
            quando = str(l.get("quando", "")).replace("T", " ")
            dados.append([quando, Paragraph(str(l.get("pessoa", "")), pequeno), Paragraph(str(l.get("email", "")), pequeno),
                          str(l.get("ip", "")), Paragraph(str(l.get("acao_rotulo", l.get("acao", ""))), pequeno),
                          Paragraph(str(l.get("alvo", "")).replace("&", "&amp;").replace("<", "&lt;"), pequeno)])
        if len(dados) == 1:
            dados.append(["—", "", "", "", "nada registrado no período", ""])
        tabela = Table(dados, colWidths=[3.2 * cm, 3.5 * cm, 4.8 * cm, 2.6 * cm, 4 * cm, 8.4 * cm], repeatRows=1)
        tabela.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f4f0")]),
        ]))
        corpo.append(tabela)
        doc.build(corpo)
        return saida.getvalue()
