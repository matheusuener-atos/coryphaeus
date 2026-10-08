"""
Cria, no Paulus aberto, uma pasta de servico de teste e a compartilha com um cliente,
para testar a Area do cliente de ponta a ponta.

    venv/Scripts/python.exe tools/pasta_de_teste.py email-do-cliente@exemplo.com.br [--nome "Nome do Cliente"]

Usa o Paulus que esta rodando (a porta e a chave da janela vem de data/instancia.json)
e as mesmas rotas da tela: cadastro do cliente, pasta, etapas (uma feita, uma do
cliente), compromisso, um PDF compartilhado, o resumo para o cliente e, por fim,
"Compartilhar com o cliente" - que manda o convite ao e-mail pelo Worker.

Precisa do acesso a distancia ligado (o link do cliente e do endereco do escritorio).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

DADOS = Path(os.environ.get("PAULUS_DADOS") or Path(__file__).resolve().parent.parent / "data")


def _pdf(texto: str) -> bytes:
    """Um PDF de uma pagina, sem biblioteca."""
    conteudo = f"BT /F1 18 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(conteudo)).encode() + b" >>\nstream\n" + conteudo + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    saida, posicoes = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{p:010d} 00000 n \n".encode() for p in posicoes)
    return saida + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


class Paulus:
    def __init__(self) -> None:
        arquivo = DADOS / "instancia.json"
        if not arquivo.exists():
            sys.exit("O Paulus nao esta aberto (nao achei data/instancia.json). Abra com src\\desktop.py e rode de novo.")
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        self.base, self.chave = f"http://127.0.0.1:{d['porta']}", d["chave"]

    def pedir(self, metodo: str, caminho: str, corpo=None) -> dict:
        req = urllib.request.Request(self.base + caminho, method=metodo, data=None if corpo is None else json.dumps(corpo).encode("utf-8"),
                                     headers={"x-paulus-chave": self.chave, "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                texto = r.read().decode("utf-8")
                return json.loads(texto) if texto else {}
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode("utf-8", "replace")
            try:
                detalhe = json.loads(detalhe).get("detail", detalhe)
            except ValueError:
                pass
            raise SystemExit(f"{metodo} {caminho}: {exc.code} - {detalhe}") from None
        except urllib.error.URLError as exc:
            raise SystemExit(f"O Paulus nao respondeu em {self.base} ({exc.reason}). Ele esta aberto?") from None


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("email", help="o e-mail do cliente (onde chega o convite e o codigo)")
    a.add_argument("--nome", default="Cliente de Teste")
    op = a.parse_args()
    p = Paulus()

    hoje = date.today()
    cliente = p.pedir("POST", "/api/cadastros", {"id": None, "dados": {"tipo": "cliente", "nome": op.nome, "email": op.email,
                                                                    "telefone": "(91) 98888-0000"}})["id"]
    sid = p.pedir("POST", "/api/servicos", {"id": None, "dados": {"nome": "Revisional do financiamento (teste)", "cadastro_id": cliente}})["id"]
    print(f"- pasta #{sid} criada para {op.nome}")
    p.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Análise do contrato"})
    p.pedir("POST", f"/api/servicos/{sid}/etapas/0")  # feita
    p.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Petição inicial protocolada"})
    p.pedir("POST", f"/api/servicos/{sid}/etapas/1")  # feita
    p.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Enviar RG e comprovante de renda", "quando": (hoje + timedelta(days=5)).isoformat()})
    p.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Citação do banco", "quando": (hoje + timedelta(days=12)).isoformat()})
    p.pedir("POST", f"/api/servicos/{sid}/cliente/etapas/2", {"do_cliente": True})
    p.pedir("POST", f"/api/servicos/{sid}/anotacoes", {"texto": "Anotação interna: o cliente NÃO vê isto."})
    print("- etapas, uma com pendência do cliente, e uma anotação interna (que o cliente não vê)")

    comp = p.pedir("POST", "/api/agenda", {"dados": {"titulo": "Audiência de conciliação", "data": (hoje + timedelta(days=8)).isoformat(),
                                                    "hora": "14:30", "onde": "Online", "servico_id": sid, "cadastro_id": cliente}})
    cid = comp.get("id") or (comp.get("compromisso") or {}).get("id")
    if cid:
        p.pedir("POST", f"/api/servicos/{sid}/cliente/compromissos/{cid}", {"confirmar": True})
        print("- audiência daqui a 8 dias, pedindo ao cliente que confirme o horário")

    pdf = Path(tempfile.mkdtemp()) / "Petição inicial.pdf"
    pdf.write_bytes(_pdf("Peticao inicial - documento de teste"))
    p.pedir("POST", f"/api/servicos/{sid}/anexar", {"caminhos": [str(pdf)]})
    for arq in p.pedir("GET", f"/api/servicos/{sid}").get("arquivos", []):
        p.pedir("POST", f"/api/servicos/{sid}/cliente/documentos/{arq['sha1']}", {"compartilhado": True})
    print("- PDF da petição na pasta, compartilhado com o cliente")

    p.pedir("POST", f"/api/servicos/{sid}/cliente/resumo", {"texto": "Seu processo foi distribuído e o banco ainda vai ser citado. "
                                                                     "A audiência de conciliação está marcada: confirme o horário em \"Para você\"."})
    print("- resumo para o cliente publicado")

    r = p.pedir("POST", f"/api/servicos/{sid}/cliente/compartilhar", {"nome": op.nome, "email": op.email, "cadastro_id": cliente})
    pessoa = r.get("pessoa") or {}
    print()
    print("Pronto. Link do cliente:", pessoa.get("link", "?"))
    print("Convite por e-mail:", "enviado para " + op.email if r.get("email_enviado") else "NÃO enviado - " + str(r.get("motivo") or r.get("erro") or "veja a tela da pasta"))
    print("No celular (ou numa janela anônima): abra o link, digite", op.email, "e use o código que chega nesse e-mail.")


if __name__ == "__main__":
    main()
