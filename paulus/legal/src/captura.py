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
veio, girada como a pessoa mandou.

**L8 (docs/PLANO-PILOTO.md):** cada foto é conferida antes de guardar
(`qualidade`: a nitidez pelo contraste das bordas e a luz pela média) - a
borrada e a escura são avisadas na prévia, para fotografar de novo; o
documento pode ir direto para a pasta de um **Serviço** (de fora, só de um
Serviço que a pessoa vê); e a entrada diz o que a leitura achou - quantas
páginas vieram pelo OCR e quantos caracteres - ou por que não deu. Medido (tests/test_umbrel_e_captura.py):
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
# A nitidez e a luz de uma foto de página (medidas em tests/test_l8_captura.py,
# numa A4 de texto: nítida > 2.000, com ou sem ruído de celular; desfocada com
# raio 4 ou mais < 200; raio 3 fica perto de 600 e passa).
LIMITE_NITIDEZ = 350
LIMITE_BRILHO = 60


def qualidade(bruto: bytes) -> dict:
    """{"nitidez", "brilho", "borrada", "escura"} de uma foto, sem guardar nada."""
    from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(bruto))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("não é uma imagem") from exc
    cinza = ImageOps.exif_transpose(img).convert("L")
    cinza.thumbnail((1200, 1200))
    # A mediana tira o ruído do sensor do celular, que passaria por "nitidez".
    bordas = cinza.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
    nitidez = float(ImageStat.Stat(bordas).var[0])
    brilho = float(ImageStat.Stat(cinza).mean[0])
    return {"nitidez": round(nitidez, 1), "brilho": round(brilho, 1),
            "borrada": nitidez < LIMITE_NITIDEZ, "escura": brilho < LIMITE_BRILHO}


def _leitura(estado, destino: Path) -> dict:
    """O que a leitura achou no PDF que acabou de entrar: páginas pelo OCR, caracteres, ou o motivo."""
    searcher = getattr(estado, "searcher", None)
    doc = next((d for d in (searcher.documents if searcher is not None else []) if Path(d.path).resolve() == destino.resolve()), None)
    if doc is None:
        return {"lido": False, "motivo": "o arquivo entrou, mas ainda não foi lido"}
    if doc.chars:
        return {"lido": True, "ocr_paginas": int(getattr(doc, "ocr", 0) or 0), "caracteres": doc.chars}
    try:
        import extract

        motivo = extract.motivo_sem_texto(destino)
    except Exception:  # noqa: BLE001
        motivo = ""
    return {"lido": False, "motivo": motivo or "não consegui ler texto nas fotos"}


def _frase_da_leitura(l: dict) -> str:
    if l.get("lido"):
        return f"li {l['caracteres']:,} caracteres".replace(",", ".") + (f" ({l['ocr_paginas']} página(s) pelo OCR)" if l.get("ocr_paginas") else "")
    return "sem texto: " + l.get("motivo", "")


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


def _pasta_de_destino(estado, servico_id) -> Path:
    if servico_id:
        pasta = estado.servicos.pasta_de(int(servico_id), criar=True)
        if pasta:
            return Path(pasta)
    return Path(estado.pasta)


def receber(estado, dados_dir: Path, pessoa: dict | None, fotos: list[bytes], giros: list[int], titulo: str,
            servico_id: int | None = None) -> dict:
    """
    Na janela do escritório (pessoa None): o PDF entra no Acervo (ou na pasta
    do Serviço). De fora: fica em <dados>/captura e vira pedido em Aprovações.
    """
    import nomes as nomes_mod
    import servicos_acesso

    if servico_id and (not estado.base.um("SELECT id FROM servicos WHERE id = ?", (int(servico_id),))
                       or not servicos_acesso.visivel(int(servico_id))):
        raise LookupError("esse Serviço não existe (ou não é seu)")
    pdf, paginas = pdf_das_fotos(fotos, giros)
    nome = nome_do_documento(titulo)
    if pessoa is None:
        pasta = _pasta_de_destino(estado, servico_id)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / nomes_mod.livre(pasta, nome)
        destino.write_bytes(pdf)
        estado.recarregar()
        return {"destino": "acervo", "nome": destino.name, "paginas": paginas, "servico_id": servico_id,
                "leitura": _leitura(estado, destino)}
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
        dados={"arquivo": str(arquivo), "nome": nome, "paginas": paginas, "servico_id": servico_id})
    return {"destino": "aprovacoes", "nome": nome, "paginas": paginas, "pedido": pedido.id, "servico_id": servico_id}


def executar(estado, pedido) -> str:
    """O sim em Aprovações: o PDF fotografado de fora entra no Acervo."""
    import nomes as nomes_mod

    origem = Path(pedido.dados.get("arquivo", ""))
    if not origem.exists():
        raise RuntimeError("o arquivo fotografado não está mais na pasta de captura")
    pasta = _pasta_de_destino(estado, pedido.dados.get("servico_id"))
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nomes_mod.livre(pasta, pedido.dados.get("nome") or origem.name)
    shutil.move(str(origem), str(destino))
    estado.recarregar()
    onde = "entrou no Serviço" if pedido.dados.get("servico_id") else "entrou no Acervo"
    return f"“{destino.name}” {onde} ({pedido.dados.get('paginas', '?')} página(s)); {_frase_da_leitura(_leitura(estado, destino))}"


def montar(estado, app, dados_dir: Path) -> None:
    from acesso import rotas as rotas_do_acesso

    @app.post("/api/captura")
    async def captura_enviar(request: Request, fotos: list[UploadFile] = File(...), giros: str = Form("[]"),
                             titulo: str = Form(""), servico_id: str = Form("")) -> dict:
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
                                           lista_giros, titulo, int(servico_id) if servico_id.strip().isdigit() else None)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/captura/conferir")
    async def captura_conferir(fotos: list[UploadFile] = File(...)) -> dict:
        """A nitidez e a luz de cada foto, antes de guardar: nada fica gravado."""
        if not (estado.prefs.dados.get("umbrel") or {}).get("captura"):
            raise HTTPException(status_code=409, detail="fotografar documento está desligado em Configurações")
        saida = []
        for i, f in enumerate(fotos[:MAX_FOTOS]):
            bruto = await f.read(MAX_BYTES_FOTO + 1)
            try:
                q = qualidade(bruto) if len(bruto) <= MAX_BYTES_FOTO else {"erro": "passa de 25 MB"}
            except ValueError as exc:
                q = {"erro": str(exc)}
            saida.append(dict(q, pagina=i + 1))
        return {"fotos": saida}
