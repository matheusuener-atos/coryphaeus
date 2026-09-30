"""
Documento pelo celular (ideia E do umbrelOS, docs/DECISAO-UMBREL.md).

O advogado recebe papel no fórum ou no cliente, e ele só entrava no PAULUS
quando alguém escaneava no escritório. Agora: a tela de câmera da própria
interface (a que já roda no celular pelo acesso de fora) fotografa uma ou
várias páginas, mostra a prévia (girar, tirar), e as fotos viram **um PDF,
uma página por foto**. Dali em diante é o caminho de sempre: o PDF de imagem
passa pelo OCR do Windows página a página (src/ocr_windows.py), ganha o
cartão e os prazos propostos em Aprovações.

**De fora, a foto não entra direto no Acervo.** O envio de arquivo de fora
continua bloqueado (src/acesso/politicas.py, "para o dono revisar"); a
captura de fora guarda o PDF numa pasta à parte, `<dados>/captura/`, e pede
em Aprovações "Entrar no Acervo". O sim de quem pode (a janela do escritório,
ou o titular) põe o arquivo no Acervo. Na janela do escritório, entra direto.

Nada sai da máquina além do que o acesso de fora já faz: as fotos vão do
celular ao computador do escritório pelo mesmo túnel da conversa.

Sem app nativo, sem modelo, sem corte automático de bordas: a foto vai como
veio, girada como a pessoa mandou. Medido (tests/test_umbrel_e_captura.py):
foto de página com giro de 2°, ruído e JPEG de celular dá mais de 90% das
palavras certas pelo OCR do Windows.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

# No topo, e nao dentro de `montar`: com as anotacoes adiadas, o FastAPI
# procura UploadFile, Request etc. nas variaveis do modulo.
from fastapi import File, Form, HTTPException, Request, UploadFile

MAX_FOTOS = 40
MAX_BYTES_FOTO = 25 * 1024 * 1024
# O lado maior da página no PDF: foto de celular tem 4000 px, e o OCR não
# ganha nada acima de ~300 dpi numa folha A4 (2480 px).
LADO_MAX = 2480
PASTA = "captura"


def pdf_das_fotos(fotos: list[bytes], giros: list[int] | None = None) -> tuple[bytes, int]:
    """(o PDF, quantas páginas): uma página por foto, na ordem, girada como a pessoa pediu."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not fotos:
        raise ValueError("nenhuma foto")
    if len(fotos) > MAX_FOTOS:
        raise ValueError(f"no máximo {MAX_FOTOS} fotos por documento")
    paginas = []
    for i, bruto in enumerate(fotos):
        if len(bruto) > MAX_BYTES_FOTO:
            raise ValueError(f"a foto {i + 1} passa de 25 MB")
        try:
            img = Image.open(io.BytesIO(bruto))
            img.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"a foto {i + 1} não é uma imagem") from exc
        # A foto de celular vem deitada com a orientação no EXIF: endireita
        # antes, e depois aplica o giro que a pessoa escolheu na prévia.
        img = ImageOps.exif_transpose(img).convert("RGB")
        giro = int((giros or [0] * len(fotos))[i] or 0) % 360 if giros and i < len(giros) else 0
        if giro:
            img = img.rotate(-giro, expand=True)
        img.thumbnail((LADO_MAX, LADO_MAX))
        paginas.append(img)
    saida = io.BytesIO()
    paginas[0].save(saida, format="PDF", save_all=True, append_images=paginas[1:], resolution=300.0, quality=85)
    return saida.getvalue(), len(paginas)


def nome_do_documento(titulo: str = "", quando: datetime | None = None) -> str:
    quando = quando or datetime.now()
    limpo = re.sub(r"[^\w .,-]+", " ", titulo or "", flags=re.UNICODE)
    limpo = " ".join(limpo.split())[:80].strip(" .")
    return f"{limpo or 'Documento fotografado'} - {quando:%d-%m-%Y %Hh%M}.pdf"


def receber(estado, dados_dir: Path, pessoa: dict | None, fotos: list[bytes], giros: list[int], titulo: str) -> dict:
    """
    Na janela do escritório (pessoa None): o PDF entra no Acervo. De fora: fica
    em <dados>/captura e vira pedido em Aprovações.
    """
    import nomes as nomes_mod

    pdf, paginas = pdf_das_fotos(fotos, giros)
    nome = nome_do_documento(titulo)
    if pessoa is None:
        Path(estado.pasta).mkdir(parents=True, exist_ok=True)
        destino = Path(estado.pasta) / nomes_mod.livre(Path(estado.pasta), nome)
        destino.write_bytes(pdf)
        estado.recarregar()
        return {"destino": "acervo", "nome": destino.name, "paginas": paginas}
    pasta = Path(dados_dir) / PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{uuid.uuid4().hex[:12]}.pdf"
    arquivo.write_bytes(pdf)
    quem = str(pessoa.get("nome") or pessoa.get("email") or "alguém de fora")
    pedido = estado.fila.pedir(
        f"Entrar no Acervo: {nome}", "acervo", acao="captura.entrar",
        resumo=f"{paginas} página(s) fotografada(s) por {quem}, pelo acesso de fora. Aprovar põe o PDF no Acervo, "
               "onde ele é lido (OCR) como qualquer escaneado.",
        etiquetas=["fotografado"], pedido_por=quem,
        dados={"arquivo": str(arquivo), "nome": nome, "paginas": paginas})
    return {"destino": "aprovacoes", "nome": nome, "paginas": paginas, "pedido": pedido.id}


def executar(estado, pedido) -> str:
    """O sim em Aprovações: o PDF fotografado de fora entra no Acervo."""
    import nomes as nomes_mod

    origem = Path(pedido.dados.get("arquivo", ""))
    if not origem.exists():
        raise RuntimeError("o arquivo fotografado não está mais na pasta de captura")
    destino = Path(estado.pasta) / nomes_mod.livre(Path(estado.pasta), pedido.dados.get("nome") or origem.name)
    shutil.move(str(origem), str(destino))
    estado.recarregar()
    return f"“{destino.name}” entrou no Acervo ({pedido.dados.get('paginas', '?')} página(s))"


def montar(estado, app, dados_dir: Path) -> None:
    from acesso import rotas as rotas_do_acesso

    @app.post("/api/captura")
    async def captura_enviar(request: Request, fotos: list[UploadFile] = File(...), giros: str = Form("[]"),
                             titulo: str = Form("")) -> dict:
        """As fotos de um documento: um PDF no Acervo (ou, de fora, um pedido em Aprovações)."""
        if not (estado.prefs.dados.get("umbrel") or {}).get("captura"):
            raise HTTPException(status_code=409, detail="fotografar documento está desligado em Configurações")
        try:
            lista_giros = [int(g) for g in json.loads(giros or "[]")]
        except (ValueError, TypeError):
            lista_giros = []
        brutos = [await f.read(MAX_BYTES_FOTO + 1) for f in fotos[:MAX_FOTOS + 1]]
        try:
            from starlette.concurrency import run_in_threadpool

            return await run_in_threadpool(receber, estado, dados_dir, rotas_do_acesso.pessoa(request), brutos,
                                           lista_giros, titulo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
