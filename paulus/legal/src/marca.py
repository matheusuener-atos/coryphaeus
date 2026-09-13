"""
A foto de quem usa e a logo do escritorio.

Duas imagens, o mesmo cuidado. A tela de Configuracoes pedia as duas desde o
desenho (docs/ui, A13) e as duas diziam "em breve": o avatar mostrava as
iniciais e o lugar da logo mostrava a marca do proprio PAULUS - que e uma
mentira educada, porque nos documentos do escritorio quem assina e o
escritorio.

Tres decisoes:

**A imagem e redesenhada, nao guardada como veio.** O que chega pode ser um
JPEG de 12 megapixels tirado no celular. Guardar aquilo para desenhar um
circulo de 32 pixels no canto da tela e carregar 4 MB em toda abertura, e
pior: um arquivo qualquer renomeado para .png entraria no disco sem ninguem
olhar. Abrir com o Pillow, reduzir e gravar PNG de novo faz as duas coisas -
prova que e imagem de verdade e deixa um arquivo pequeno.

**A foto e quadrada no centro.** O avatar e redondo em toda a interface; uma
foto 3x4 esticada num circulo deforma o rosto. Cortar o centro e o que a
pessoa espera ao ver a previa.

**A logo mantem a transparencia.** Ela entra no alto do papel timbrado, sobre
branco: fundo branco chapado numa logo com recorte apareceria como um
retangulo no meio da folha.
"""

from __future__ import annotations

import io
from pathlib import Path

# Quanto cada imagem pode ocupar depois de redesenhada, no maior lado. A foto
# e pequena porque nunca passa de um avatar; a logo vai para o PDF, onde a
# impressao pede mais pixels por centimetro que a tela.
LADO = {"foto": 512, "logo": 1024}

# O que a tela promete aceitar: "PNG ou JPG · ate 4 MB".
MAX_BYTES = 4 * 1024 * 1024

# Formatos que o Pillow le e que fazem sentido aqui. WEBP entra porque e o que
# sai de muito site hoje, e a pessoa nao tem por que saber a diferenca.
FORMATOS = {"PNG", "JPEG", "WEBP", "BMP", "GIF"}

TIPOS = ("foto", "logo")


class Marca:
    """As imagens desta maquina: `foto.png` e `logo.png` em data/marca."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)

    def caminho(self, tipo: str) -> Path | None:
        """O arquivo, se existir - senao None, que e o caso normal."""
        if tipo not in TIPOS:
            return None
        alvo = self.pasta / f"{tipo}.png"
        return alvo if alvo.exists() else None

    def guardar(self, tipo: str, dados: bytes) -> dict:
        """
        Recebe o arquivo escolhido e deixa um PNG pequeno no lugar.

        Levanta ValueError com o motivo em portugues: a tela mostra essa
        frase, entao ela precisa dizer o que fazer, nao o nome da excecao.
        """
        if tipo not in TIPOS:
            raise ValueError("imagem desconhecida")
        if not dados:
            raise ValueError("o arquivo chegou vazio")
        if len(dados) > MAX_BYTES:
            raise ValueError(f"a imagem tem {len(dados) / 1024 / 1024:.1f} MB; o limite e 4 MB")

        from PIL import Image, UnidentifiedImageError

        try:
            imagem = Image.open(io.BytesIO(dados))
            formato = (imagem.format or "").upper()
            imagem.load()
        except UnidentifiedImageError as exc:
            raise ValueError("esse arquivo nao e uma imagem") from exc
        except Exception as exc:  # imagem truncada, PNG quebrado, GIF sem quadro
            raise ValueError("nao consegui ler essa imagem") from exc
        if formato not in FORMATOS:
            raise ValueError(f"formato {formato or 'desconhecido'} nao serve; use PNG ou JPG")

        imagem = imagem.convert("RGBA")
        if tipo == "foto":
            imagem = _quadrado(imagem)
        lado = LADO[tipo]
        if max(imagem.size) > lado:
            imagem.thumbnail((lado, lado), Image.LANCZOS)

        alvo = self.pasta / f"{tipo}.png"
        # Grava ao lado e troca: um erro no meio da escrita deixaria a imagem
        # antiga pela metade, e o avatar ficaria quebrado ate alguem notar.
        provisorio = alvo.with_suffix(".png.novo")
        imagem.save(provisorio, format="PNG", optimize=True)
        provisorio.replace(alvo)
        return self.info()[tipo]

    def tirar(self, tipo: str) -> bool:
        """Volta para as iniciais (ou para a marca do PAULUS)."""
        alvo = self.caminho(tipo)
        if not alvo:
            return False
        alvo.unlink()
        return True

    def info(self) -> dict:
        """
        O que a tela precisa saber: se tem, o tamanho, e uma versao.

        A versao e o instante da gravacao, e vai no endereco da imagem como
        `?v=`. Sem ela, trocar a foto nao mudaria nada na tela: o navegador
        continuaria mostrando a que ja tinha em maos, com o mesmo endereco.
        """
        saida = {}
        for tipo in TIPOS:
            alvo = self.caminho(tipo)
            if not alvo:
                saida[tipo] = {"tem": False, "versao": 0}
                continue
            estado = alvo.stat()
            item = {"tem": True, "versao": int(estado.st_mtime), "kb": round(estado.st_size / 1024)}
            try:
                from PIL import Image

                with Image.open(alvo) as imagem:
                    item["largura"], item["altura"] = imagem.size
            except Exception:
                pass
            saida[tipo] = item
        return saida


def _quadrado(imagem):
    """O centro da imagem, em quadrado - o avatar e redondo."""
    largura, altura = imagem.size
    if largura == altura:
        return imagem
    lado = min(largura, altura)
    esquerda = (largura - lado) // 2
    topo = (altura - lado) // 2
    return imagem.crop((esquerda, topo, esquerda + lado, topo + lado))
