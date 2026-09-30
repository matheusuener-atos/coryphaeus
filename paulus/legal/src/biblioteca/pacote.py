"""
O pacote `.paulus-material`: um material da biblioteca num arquivo só, para
levar de um PAULUS a outro (docs/PROGRESSO-BIBLIOTECA.md, "Compartilhamento
futuro").

A frente futura é um espaço, parecido com um blog, em que advogados publicam
material PRÓPRIO - artigos, comentários, modelos de peça - e outros
escritórios trazem para a biblioteca deles. Aqui só se prepara o terreno, sem
rede nenhuma: exportar e importar localmente. A curadoria, a moderação, as
contas de autor e a publicação online são da frente futura.

O que vai no pacote (um zip):

- `manifesto.json`: o formato e a versão;
- `ficha.json`: a ficha (M2), com a declaração de autoria e a licença;
- `texto.txt`: o texto extraído, com as marcas de página;
- `anotacoes.json`: as anotações de artigos (M3).

Sem vetores (cada máquina vetoriza de novo) e sem o arquivo original.

As regras que tornam isso possível juridicamente - circula o que é dos
próprios advogados, não livro comprado:

- **só o autor exporta:** o material tem de ser `artigo`, `modelo_de_peca` ou
  `manual`, e a pessoa tem de marcar "sou o autor deste material e posso
  compartilhá-lo" e escolher uma licença. **Doutrina de editora nunca é
  exportável**, com ou sem marca;
- **o que vem de fora entra como de fora:** `origem: comunidade`, numa camada
  própria da resposta (COMUNIDADE, depois de DOUTRINA), com o aviso de que
  não foi revisado por este escritório - nunca como lei, nunca como regra da
  casa;
- **o pacote é dado, não instrução:** o texto importado nunca vira lembrete,
  e vai ao modelo cercado (src/blindagem.py) como qualquer texto de terceiro.
  Um pacote com "ignore as instruções anteriores" é só texto.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

FORMATO = "paulus-material/v1"
EXTENSAO = ".paulus-material"
EXPORTAVEIS = ("artigo", "modelo_de_peca", "manual")
LICENCAS = ("CC BY 4.0", "CC BY-SA 4.0", "CC BY-NC 4.0", "Uso livre pelo escritório que importar, sem republicar")
NOMES = {"manifesto.json", "ficha.json", "texto.txt", "anotacoes.json"}
MAX_BYTES = 20 * 1024 * 1024
DECLARACAO = "sou o autor deste material e posso compartilhá-lo"


def pode_exportar(item: dict) -> tuple[bool, str]:
    """(pode, por que não) - a regra de quem exporta."""
    ficha = item.get("ficha") or {}
    if ficha.get("origem") == "comunidade":
        return False, "material que veio de outro advogado não é reexportado daqui"
    if ficha.get("tipo") == "doutrina":
        return False, "doutrina de editora nunca é exportável: circula só o que é do próprio advogado"
    if ficha.get("tipo") not in EXPORTAVEIS:
        return False, "só artigo, modelo de peça ou manual do próprio escritório se exporta"
    if not ficha.get("autoria_declarada"):
        return False, "falta marcar: " + DECLARACAO
    if ficha.get("licenca") not in LICENCAS:
        return False, "falta escolher a licença"
    return True, ""


def declarar(material, id_: str, sou_autor: bool, licenca: str) -> dict:
    """A declaração de autoria e a licença, que só quem é autor faz (nunca deduzida)."""
    from biblioteca import ficha as ficha_mod

    item = material.item(id_)
    if item is None:
        raise KeyError(id_)
    ficha = {**ficha_mod.vazia(), **(item.get("ficha") or {})}
    if ficha.get("tipo") == "doutrina":
        raise ValueError("doutrina de editora nunca é exportável")
    if not sou_autor:
        raise ValueError("para exportar, é preciso declarar: " + DECLARACAO)
    if licenca not in LICENCAS:
        raise ValueError("escolha uma das licenças: " + "; ".join(LICENCAS))
    ficha.update(autoria_declarada=True, autoria_em=datetime.now().strftime("%Y-%m-%d %H:%M"), licenca=licenca)
    return material.definir_ficha(id_, ficha)


def exportar(material, id_: str, versao_do_paulus: str = "") -> bytes:
    item = material.item(id_)
    if item is None:
        raise KeyError(id_)
    pode, porque = pode_exportar(item)
    if not pode:
        raise ValueError(porque)
    ficha = dict(item.get("ficha") or {})
    anotacoes = [{k: a[k] for k in ("instrument_id", "codigo", "artigo", "ordem", "chunk_id", "pagina", "quote")}
                 for a in material.anotacoes.do_material(id_)] if material.chave("anotacoes") else []
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifesto.json", json.dumps({"formato": FORMATO, "criado_em": datetime.now().isoformat(timespec="seconds"),
                                                 "paulus": versao_do_paulus, "nome": item["nome"],
                                                 "id_de_origem": item.get("id_de_origem") or item["id"],
                                                 "sha1_de_origem": item.get("sha1", "")}, ensure_ascii=False, indent=1))
        z.writestr("ficha.json", json.dumps(ficha, ensure_ascii=False, indent=1))
        z.writestr("texto.txt", material.texto_de(id_))
        z.writestr("anotacoes.json", json.dumps(anotacoes, ensure_ascii=False, indent=1))
    return saida.getvalue()


def ler(conteudo: bytes) -> dict:
    """O pacote aberto e conferido - só os quatro arquivos, sem caminho estranho, do tamanho certo."""
    if len(conteudo or b"") > MAX_BYTES:
        raise ValueError("o pacote passa de 20 MB")
    try:
        z = zipfile.ZipFile(io.BytesIO(conteudo))
    except zipfile.BadZipFile as exc:
        raise ValueError("isto não é um pacote .paulus-material") from exc
    nomes = set(z.namelist())
    if nomes - NOMES or not {"manifesto.json", "ficha.json", "texto.txt"} <= nomes:
        raise ValueError("o pacote tem arquivos que não são de um .paulus-material")
    if sum(i.file_size for i in z.infolist()) > 4 * MAX_BYTES:
        raise ValueError("o pacote aberto é grande demais")
    try:
        manifesto = json.loads(z.read("manifesto.json").decode("utf-8"))
        ficha = json.loads(z.read("ficha.json").decode("utf-8"))
        texto = z.read("texto.txt").decode("utf-8")
        anotacoes = json.loads(z.read("anotacoes.json").decode("utf-8")) if "anotacoes.json" in nomes else []
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("o pacote está corrompido") from exc
    if manifesto.get("formato") != FORMATO:
        raise ValueError("formato de pacote que esta versão do PAULUS não conhece")
    if not isinstance(ficha, dict) or ficha.get("tipo") not in EXPORTAVEIS:
        raise ValueError("o pacote não é de artigo, modelo de peça ou manual - não entra")
    return {"manifesto": manifesto, "ficha": ficha, "texto": texto, "anotacoes": anotacoes}


def importar(material, conteudo: bytes, nome_do_arquivo: str = "") -> dict:
    """
    O pacote vira material de origem `comunidade`. O texto é só texto: não vira
    lembrete, e as suspeitas de ordem ao assistente (src/blindagem.py) ficam
    anotadas na ficha para a tela mostrar.
    """
    import blindagem
    from biblioteca import ficha as ficha_mod

    dados = ler(conteudo)
    m, f = dados["manifesto"], dados["ficha"]
    ficha = {**ficha_mod.vazia(f.get("tipo", "")),
             **{k: f.get(k, ficha_mod.vazia()[k]) for k in ("tipo", "titulo", "autor", "edicao", "ano", "editora",
                                                           "isbn", "areas")},
             "origem": "comunidade", "licenca": f.get("licenca", ""), "confirmada": True,
             "suspeitas": blindagem.suspeitas(dados["texto"])}
    nome = (m.get("nome") or nome_do_arquivo or "material importado").replace(EXTENSAO, "")
    return material.absorver_texto(nome, dados["texto"], ficha, id_de_origem=m.get("id_de_origem", ""),
                                   sha1=m.get("sha1_de_origem", ""))
