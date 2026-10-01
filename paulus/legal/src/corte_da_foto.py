"""
A folha na foto: cortar as bordas e endireitar a perspectiva (docs/PLANO-PILOTO.md, N10).

A foto do celular pega a mesa em volta e a folha torta. Aqui, sem OpenCV e
sem modelo (PIL e numpy, que o PAULUS já tem):

  1. a foto pequena (600 px), em cinza; o limiar de Otsu separa o claro (a
     folha) do escuro (a mesa); um fechamento tapa as letras da folha;
  2. a região clara ligada ao centro da foto é a folha (o `floodfill` do PIL
     faz a conta em C);
  3. os quatro cantos são os extremos da região (x+y e x-y): serve para a
     folha girada até uns 40 graus, e para a perspectiva de quem fotografa de
     pé;
  4. a perspectiva é desfeita pela transformação de 8 coeficientes do PIL,
     na foto inteira (não na pequena): a folha sai retangular, no tamanho
     dela.

Com cuidado: só corta quando a região é uma folha plausível - entre 20% e
97% da foto, quatro cantos convexos, lados que não se cruzam. Folha que já
ocupa a foto toda, ou fundo tão claro quanto a folha, fica como veio, e a
prévia diz por quê. A pessoa desliga o corte em cada foto.
"""

from __future__ import annotations

import io

LADO_ANALISE = 600
AREA_MIN, AREA_MAX = 0.20, 0.97


def _otsu(hist) -> int:
    total = sum(hist)
    soma = sum(i * h for i, h in enumerate(hist))
    soma_b, peso_b, melhor, limiar = 0.0, 0, -1.0, 128
    for i, h in enumerate(hist):
        peso_b += h
        if peso_b == 0:
            continue
        peso_f = total - peso_b
        if peso_f == 0:
            break
        soma_b += i * h
        m_b = soma_b / peso_b
        m_f = (soma - soma_b) / peso_f
        entre = peso_b * peso_f * (m_b - m_f) ** 2
        if entre > melhor:
            melhor, limiar = entre, i
    return limiar


def _area(q) -> float:
    """A área do quadrilátero (cantos em ordem), pela fórmula do laço."""
    s = 0.0
    for i in range(4):
        x1, y1 = q[i]
        x2, y2 = q[(i + 1) % 4]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def _convexo(q) -> bool:
    sinais = []
    for i in range(4):
        ax, ay = q[i]
        bx, by = q[(i + 1) % 4]
        cx, cy = q[(i + 2) % 4]
        sinais.append((bx - ax) * (cy - by) - (by - ay) * (cx - bx) > 0)
    return all(sinais) or not any(sinais)


def achar_folha(img) -> dict:
    """
    {"achou", "cantos" (em fração da foto: [[x, y] x4], sentido horário a
    partir do de cima à esquerda), "area", "motivo"}.
    """
    import numpy as np
    from PIL import ImageDraw, ImageFilter, ImageOps

    cinza = ImageOps.exif_transpose(img).convert("L")
    w0, h0 = cinza.size
    escala = LADO_ANALISE / max(w0, h0)
    peq = cinza.resize((max(1, int(w0 * escala)), max(1, int(h0 * escala))))
    peq = peq.filter(ImageFilter.GaussianBlur(1.2))
    limiar = _otsu(peq.histogram())
    a = np.asarray(peq)
    claro, escuro = a[a > limiar], a[a <= limiar]
    if claro.size == 0 or escuro.size == 0 or float(claro.mean()) - float(escuro.mean()) < 35:
        return {"achou": False, "motivo": "o fundo é tão claro quanto a folha: a foto vai como veio"}
    mascara = peq.point(lambda v: 255 if v > limiar else 0)
    # Fecha as letras (o escuro dentro da folha) e tira os respingos claros de fora.
    mascara = mascara.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    mascara = mascara.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    m = np.asarray(mascara)
    h, w = m.shape
    # A semente: o pixel claro mais perto do centro.
    ys, xs = np.nonzero(m > 128)
    if ys.size == 0:
        return {"achou": False, "motivo": "não achei a folha na foto"}
    d = (ys - h / 2) ** 2 + (xs - w / 2) ** 2
    i = int(np.argmin(d))
    marcada = mascara.copy()
    ImageDraw.floodfill(marcada, (int(xs[i]), int(ys[i])), 100)
    r = np.asarray(marcada) == 100
    ys, xs = np.nonzero(r)
    area = ys.size / float(h * w)
    if area < AREA_MIN:
        return {"achou": False, "motivo": "a folha ocupa pouco da foto: aproxime e fotografe de novo", "area": round(area, 3)}
    soma, dif = xs + ys, xs - ys
    cantos = [(xs[np.argmin(soma)], ys[np.argmin(soma)]), (xs[np.argmax(dif)], ys[np.argmax(dif)]),
              (xs[np.argmax(soma)], ys[np.argmax(soma)]), (xs[np.argmin(dif)], ys[np.argmin(dif)])]
    q = [(float(x), float(y)) for x, y in cantos]
    area_q = _area(q) / float(h * w)
    if area_q > AREA_MAX:
        # Sem borda entre o claro e o escuro: ou a folha ocupa a foto, ou o fundo é claro como ela.
        return {"achou": False, "area": round(area_q, 3),
                "motivo": "não vi borda entre a folha e o fundo (a folha ocupa a foto, ou o fundo é claro como ela): a foto vai como veio"}
    if area_q < AREA_MIN or not _convexo(q):
        return {"achou": False, "motivo": "não achei os quatro cantos da folha: a foto vai como veio", "area": round(area_q, 3)}
    # A região de verdade tem de preencher o quadrilátero: senão não é folha (é sombra, mesa clara...).
    if area / area_q < 0.85:
        return {"achou": False, "motivo": "a região clara não tem forma de folha: a foto vai como veio", "area": round(area_q, 3)}
    return {"achou": True, "cantos": [[round(x / w, 4), round(y / h, 4)] for x, y in q], "area": round(area_q, 3), "motivo": ""}


def _coeficientes(destino, origem):
    """Os 8 coeficientes do PIL (PERSPECTIVE): de cada ponto de destino para o ponto de origem."""
    import numpy as np

    linhas, b = [], []
    for (x, y), (u, v) in zip(destino, origem):
        linhas.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        linhas.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return [float(c) for c in np.linalg.solve(np.array(linhas, dtype=float), np.array(b, dtype=float))]


def endireitar(img, cantos):
    """A folha recortada e endireitada, a partir dos cantos em fração da foto."""
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    q = [(x * w, y * h) for x, y in cantos]

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    largura = int(max(dist(q[0], q[1]), dist(q[3], q[2])))
    altura = int(max(dist(q[0], q[3]), dist(q[1], q[2])))
    if largura < 50 or altura < 50:
        return img
    coef = _coeficientes([(0, 0), (largura, 0), (largura, altura), (0, altura)], q)
    return img.transform((largura, altura), Image.PERSPECTIVE, coef, Image.BICUBIC)


def conferir(bruto: bytes) -> dict:
    """O que a prévia mostra: os cantos achados (ou o motivo de não cortar)."""
    from PIL import Image, UnidentifiedImageError

    from PIL import ImageOps

    try:
        img = Image.open(io.BytesIO(bruto))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("não é uma imagem") from exc
    img = ImageOps.exif_transpose(img)
    # O tamanho (já de pé, pelo EXIF): a prévia desenha o contorno por cima na proporção certa.
    return dict(achar_folha(img), largura=img.width, altura=img.height)
