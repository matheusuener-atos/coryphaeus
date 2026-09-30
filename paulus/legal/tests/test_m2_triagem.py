"""
Portão da M2 da Biblioteca: triagem na entrada, ficha e as leis que faltam.

  - um PDF do CDC vira artigos nas leis em casa (src/leis.py), com os revogados
    marcados e nenhum artigo partido - os mesmos artigos, com o mesmo texto,
    que o HTML do Planalto dá; e não vira material;
  - o CDC entregue de novo, já guardado, não é guardado outra vez;
  - cada código novo (CDC, CF, CTN, ECA, Lei do Inquilinato): 10 artigos
    sorteados conferidos contra o texto do Planalto - o começo do artigo está
    lá, logo depois do "Art. N", e o texto dele não engole o artigo seguinte;
  - 5 fichas catalográficas realistas (com as armadilhas de verdade: o
    histórico de edições, a reimpressão com outro ano, o ISBN com um dígito
    trocado, a edição sem número): ano e edição certos ou vazios, e ZERO campo
    errado;
  - material sem ficha catalográfica entra com a ficha vazia e pede
    conferência; o que a pessoa edita vale sobre o que a regra achou;
  - lei não catalogada fica como material de lei, com o aviso; súmulas viram
    um trecho por enunciado;
  - pela API, com a chave ligada: o PDF do CDC vai para as leis, e a ficha se
    edita.

Os textos do Planalto moram em data/leis (tools/demo/biblioteca_demo.py os
baixa uma vez). Sem eles, as partes que dependem deles pulam com aviso.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m2_triagem.py
"""

from __future__ import annotations

import random
import re
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import leis as leis_mod  # noqa: E402
import material as material_mod  # noqa: E402
from base import Base  # noqa: E402
from biblioteca import ficha as ficha_mod  # noqa: E402
from biblioteca import triagem  # noqa: E402

LEIS = RAIZ / "data" / "leis"
ARQUIVOS = {"cdc": "l8078compilado.htm", "cf": "constituicaocompilado.htm", "ctn": "l5172compilado.htm",
            "eca": "l8069compilado.htm", "inquilinato": "l8245compilado.htm"}

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _junto(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def isbn13(doze: str) -> str:
    soma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(doze))
    return doze + str((10 - soma % 10) % 10)


def isbn10(nove: str) -> str:
    soma = sum(int(d) * (10 - i) for i, d in enumerate(nove))
    resto = (11 - soma % 11) % 11
    return nove + ("X" if resto == 10 else str(resto))


def _com_hifens(n: str) -> str:
    return f"{n[:3]}-{n[3:5]}-{n[5:10]}-{n[10:12]}-{n[12]}" if len(n) == 13 else f"{n[:2]}-{n[2:6]}-{n[6:9]}-{n[9]}"


# ------------------------------------------------------------ as fichas
I1 = _com_hifens(isbn13("978850000011"))
I2 = _com_hifens(isbn13("978853090022"))
I3 = _com_hifens(isbn10("857348123"))
I4 = _com_hifens(isbn13("978655500044"))
I5_ERRADO = "978-85-00000-55-" + str((int(isbn13("978850000055")[-1]) + 3) % 10)

FICHAS = [
    ("histórico de edições no verso", f"""[pagina 1]
Ricardo Tavares Almeida
MANUAL DE DIREITO PROCESSUAL CIVIL
3ª edição revista, atualizada e ampliada
[pagina 2]
Dados Internacionais de Catalogação na Publicação (CIP)
(Câmara Brasileira do Livro, SP, Brasil)
Almeida, Ricardo Tavares
Manual de direito processual civil / Ricardo Tavares Almeida. – 3. ed. rev., atual. e ampl.
– São Paulo : Editora Modelo, 2019.
ISBN {I1}
1. Processo civil – Brasil I. Título.
19-12345 CDU-347.9(81)
© 2019 Editora Modelo
1ª edição: 2012 | 2ª edição: 2015 | 3ª edição: 2019
""", {"autor": "Ricardo Tavares Almeida", "titulo": "Manual de direito processual civil", "edicao": "3ª",
      "ano": "2019", "editora": "Editora Modelo", "isbn": I1}),
    ("reimpressão com outro ano", f"""[pagina 1]
Carla Menezes Vidal
CONTRATOS EMPRESARIAIS
[pagina 2]
Dados Internacionais de Catalogação na Publicação (CIP)
Vidal, Carla Menezes
Contratos empresariais : teoria e prática / Carla Menezes Vidal. – 2. ed. – Rio de Janeiro : Forense Exemplo, 2016.
ISBN {I2}
2ª edição – 2016
3ª tiragem – 2018
© 2016 by Carla Menezes Vidal
""", {"autor": "Carla Menezes Vidal", "titulo": "Contratos empresariais", "edicao": "2ª", "ano": "2016",
      "editora": "Forense Exemplo", "isbn": I2}),
    ("edição sem número e ISBN-10", f"""[pagina 1]
Paulo Henrique Duarte
LOCAÇÃO DE IMÓVEIS URBANOS
Edição revista e atualizada
[pagina 2]
Ficha catalográfica elaborada pela bibliotecária Maria Souza – CRB-9/1234
D812l Duarte, Paulo Henrique
Locação de imóveis urbanos / Paulo Henrique Duarte. – Curitiba : Juruá Exemplo, 2020.
280 p.
ISBN {I3}
1. Locação de imóveis. 2. Direito imobiliário. I. Título.
""", {"autor": "Paulo Henrique Duarte", "titulo": "Locação de imóveis urbanos", "edicao": "", "ano": "2020",
      "editora": "Juruá Exemplo", "isbn": I3}),
    ("autor com partícula e prefácio", f"""[pagina 1]
ANA PAULA DA SILVA
Direito do Consumidor
Teoria e prática
[pagina 2]
Dados Internacionais de Catalogação na Publicação (CIP)
S586d Silva, Ana Paula da
Direito do consumidor : teoria e prática / Ana Paula da Silva ; prefácio de João Souza. – Belo Horizonte :
Editora Exemplo, 2021.
350 p. ; 23 cm.
ISBN {I4}
Inclui bibliografia.
""", {"autor": "Ana Paula da Silva", "titulo": "Direito do consumidor", "edicao": "", "ano": "2021",
      "editora": "Editora Exemplo", "isbn": I4}),
    ("ISBN com dígito trocado e © de duas datas", f"""[pagina 1]
Roberto Lins
CURSO DE DIREITO DO TRABALHO
[pagina 2]
Dados Internacionais de Catalogação na Publicação (CIP)
(Câmara Brasileira do Livro, SP, Brasil)
Lins, Roberto
Curso de direito do trabalho / Roberto Lins. – 4. ed. – São Paulo : Editora Laboral, 2014.
ISBN {I5_ERRADO}
© 2010, 2014 by Roberto Lins
""", {"autor": "Roberto Lins", "titulo": "Curso de direito do trabalho", "edicao": "4ª", "ano": "2014",
      "editora": "Editora Laboral", "isbn": ""}),
]


def test_fichas() -> None:
    print("\nfichas catalográficas")
    errados, vazios, certos = [], 0, 0
    for nome, texto, esperado in FICHAS:
        f = ficha_mod.ler_ficha(texto, "doutrina")
        for campo, valor in esperado.items():
            achado = f.get(campo, "")
            if not achado:
                vazios += 1
                if valor:
                    print(f"       ({nome}: {campo} ficou vazio; o certo era {valor!r})")
            elif achado == valor:
                certos += 1
            else:
                errados.append(f"{nome}: {campo} = {achado!r}, o certo é {valor!r}")
        checar(f["ano"] in (esperado["ano"], ""), f"{nome}: ano certo ou vazio", f["ano"])
        checar(f["edicao"] in (esperado["edicao"], ""), f"{nome}: edição certa ou vazia", f["edicao"])
    checar(not errados, "zero campo errado nas 5 fichas", errados)
    print(f"       {certos} campos certos, {vazios} vazios, {len(errados)} errados")
    checar(certos >= 25, "e a regra acha a maior parte (≥ 25 de 30 campos)", certos)


def test_sem_ficha(pasta: Path) -> None:
    print("\nmaterial sem ficha catalográfica")
    import criar_demo

    m = material_mod.Material(pasta)
    with _base(pasta / "b.db") as base:
        feito = triagem.entregar(m, leis_mod.Leis(base), "Manual de rotinas.pdf", criar_demo.manual_em_pdf(),
                                 pasta / "leis")
    f = feito["item"]["ficha"]
    checar(feito["destino"] == "material" and f["tipo"] == "manual", "o manual entra como manual", f["tipo"])
    checar(not any(f[c] for c in ("autor", "titulo", "edicao", "ano", "editora", "isbn")),
           "sem ficha catalográfica, a ficha fica vazia (nada chutado)", {c: f[c] for c in ("autor", "ano")})
    checar(ficha_mod.precisa_conferir(f), "e pede conferência")
    item = m.editar_ficha(feito["item"]["id"], {"autor": "Moura & Campos Advocacia", "ano": "2026"})
    checar(item["ficha"]["autor"] == "Moura & Campos Advocacia" and item["ficha"]["confirmada"],
           "o que a pessoa escreve fica, e a ficha passa a conferida")
    relida = ficha_mod.fundir(ficha_mod.ler_ficha(m.texto_de(item["id"]), "manual"), item["ficha"])
    checar(relida["autor"] == "Moura & Campos Advocacia" and relida["ano"] == "2026",
           "reler o arquivo não desfaz a correção", relida["autor"])
    try:
        m.editar_ficha(item["id"], {"isbn": I5_ERRADO})
        checar(False, "ISBN com dígito errado é recusado na edição")
    except ValueError:
        checar(True, "ISBN com dígito errado é recusado na edição")


class _base:
    """A Base fecha sozinha (with), para a pasta temporária se apagar no Windows."""

    def __init__(self, caminho):
        self.b = Base(caminho)

    def __enter__(self):
        return self.b

    def __exit__(self, *a):
        try:
            self.b.con.close()
        except Exception:  # noqa: BLE001
            pass


def test_cdc_em_pdf(pasta: Path) -> None:
    print("\no CDC em PDF")
    if not (LEIS / ARQUIVOS["cdc"]).exists():
        print("  pulado: sem data/leis/l8078compilado.htm (rode tools/demo/biblioteca_demo.py)")
        return
    import biblioteca_demo

    pdf = biblioteca_demo.cdc_em_pdf()
    m = material_mod.Material(pasta / "material")
    with _base(pasta / "b.db") as base:
        L = leis_mod.Leis(base)
        feito = triagem.entregar(m, L, "CDC atualizado.pdf", pdf, pasta / "leis")
        checar(feito["destino"] == "lei" and feito["lei"]["codigo"] == "cdc",
               "o PDF do CDC é reconhecido como lei", feito.get("triagem"))
        checar("Código de Defesa do Consumidor" in feito["mensagem"] and "artigo por artigo" in feito["mensagem"],
               "e a tela diz: é o CDC, guardado artigo por artigo", feito["mensagem"])
        checar(not m.itens, "e não vira material de consulta", [x["nome"] for x in m.itens])
        oficiais, _ = leis_mod.ler_codigo(LEIS / ARQUIVOS["cdc"], "cdc")
        guardados = base.buscar("SELECT numero, texto, revogado FROM artigos WHERE codigo = 'cdc' ORDER BY ordem")
        checar([a.numero for a in oficiais] == [g["numero"] for g in guardados],
               "os mesmos artigos do Planalto, na mesma ordem", (len(oficiais), len(guardados)))
        partidos = [a.numero for a, g in zip(oficiais, guardados) if _junto(a.texto) != _junto(g["texto"])]
        checar(not partidos, "nenhum artigo partido: o texto de cada um é o do Planalto", partidos[:5])
        checar([a.revogado for a in oficiais] == [bool(g["revogado"]) for g in guardados],
               "os revogados marcados como no Planalto")
        a18 = L.artigo("cdc", "18")
        checar(a18 and "respondem solidariamente" in a18["texto"] and "§ 1" in a18["texto"]
               and "abatimento proporcional do preço" in a18["texto"],
               "o art. 18 com o caput e os parágrafos juntos", a18 and a18["texto"][:80])
        de_novo = triagem.entregar(m, L, "CDC outra cópia.pdf", biblioteca_demo.cdc_em_pdf(), pasta / "leis")
        checar(de_novo["destino"] == "lei" and de_novo["lei"].get("ja_existia") and "já está guardado" in de_novo["mensagem"],
               "o CDC entregue de novo não é guardado outra vez", de_novo["mensagem"])


def test_codigos_novos(pasta: Path) -> None:
    print("\nos códigos novos contra o texto do Planalto")
    with _base(pasta / "c.db") as base:
        L = leis_mod.Leis(base)
        for codigo, arquivo in ARQUIVOS.items():
            alvo = LEIS / arquivo
            if not alvo.exists():
                print(f"  pulado: {codigo} (sem {alvo})")
                continue
            checar(leis_mod.reconhecer(alvo) == codigo, f"{codigo}: o arquivo do Planalto é reconhecido")
            r = L.importar(alvo, codigo)
            bruto = re.sub(r"\s+", " ", leis_mod._texto_do_html(alvo.read_bytes()))
            artigos = base.buscar("SELECT numero, texto, ordem FROM artigos WHERE codigo = ? ORDER BY ordem", (codigo,))
            sorteio = random.Random(codigo).sample(range(len(artigos)), 10)
            errados = []
            for i in sorteio:
                a = artigos[i]
                numero = a["numero"].replace("ADCT ", "")
                comeco = " ".join(a["texto"].split())[:60]
                # O começo do artigo está no Planalto, logo depois do "Art. N".
                achou = re.search(r"Art\.?\s*" + re.escape(re.sub(r"[º°o]$", "", numero.split("-")[0]))
                                  + r"[^\s]*\s*[-–.]?\s*" + re.escape(comeco[:30]), bruto)
                seguinte = artigos[i + 1]["numero"].replace("ADCT ", "") if i + 1 < len(artigos) else ""
                engoliu = seguinte and re.search(r"(?:^|\s)Art\.?\s*" + re.escape(seguinte) + r"[\s.]", a["texto"])
                if not achou or engoliu:
                    errados.append(a["numero"])
            checar(not errados, f"{codigo}: 10 artigos sorteados conferem com o Planalto ({r['artigos']} artigos)",
                   errados)
        if (LEIS / ARQUIVOS["cf"]).exists():
            adct = L.artigo("cf", "ADCT 2")
            checar(adct and "plebiscito" in adct["texto"] and adct["citacao"] == "CF, ADCT, art. 2º",
                   "a Constituição guarda o ADCT à parte: ADCT, art. 2º", adct and adct["citacao"])
            checar("forma federativa" not in (adct or {}).get("texto", ""), "sem misturar com o art. 2º do corpo")
            checar(L.artigo("cf", "5") and "Todos são iguais perante a lei" in L.artigo("cf", "5")["texto"],
                   "e o art. 5º do corpo continua o art. 5º")
        if (LEIS / ARQUIVOS["ctn"]).exists():
            primeiro = L.artigo("ctn", "1")
            checar(primeiro and "sistema tributário nacional" in primeiro["texto"],
                   "o art. 1º do CTN, antes do Livro Primeiro, não se perde")


def test_triagem_outros(pasta: Path) -> None:
    print("\nlei não catalogada, súmulas, doutrina")
    lei = "LEI Nº 9.999, DE 1º DE JANEIRO DE 2020\nDispõe sobre o teste.\n" + "\n".join(
        f"Art. {n}º Dispositivo de teste número {n}, com o texto da lei." for n in range(1, 31))
    t = triagem.triar("lei-teste.txt", lei)
    checar(t["destino"] == "material" and t["tipo"] == "lei" and "vigência" in t["mensagem"],
           "lei que eu não conheço fica como material de lei, sem conferência de vigência", t)
    sumulas_txt = "\n".join(f"Súmula nº {n}\nEnunciado da súmula de teste número {n}, sobre o assunto {n}." for n in
                            range(300, 310))
    t = triagem.triar("sumulas-stj.txt", sumulas_txt)
    checar(t["tipo"] == "sumulas", "lista de súmulas é súmulas", t["tipo"])
    from biblioteca import indice

    item = {"id": "x", "nome": "sumulas-stj.txt", "sha1": "abc", "ficha": {"tipo": "sumulas"}}
    chunks = indice.trechos_do_material(item, sumulas_txt)
    checar(len(chunks) == 10 and all(c.text.startswith("Súmula nº") for c in chunks),
           "um trecho por enunciado", [c.text[:20] for c in chunks][:3])
    import biblioteca_demo

    obra = biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_A)
    m = material_mod.Material(pasta)
    with _base(pasta / "d.db") as base:
        feito = triagem.entregar(m, leis_mod.Leis(base), biblioteca_demo.OBRA_A["arquivo"], obra, pasta / "leis")
    f = feito["item"]["ficha"]
    checar(f["tipo"] == "doutrina" and f["autor"] == "Heitor Valadares Brandão" and f["ano"] == "2015"
           and f["edicao"] == "2ª" and f["areas"] == ["consumidor"],
           "a obra de doutrina entra com a ficha lida da ficha catalográfica", f)
    checar(f["origem"] == "escritorio" and f["licenca"] == "", "origem do escritório e licença vazia de fábrica")
    checar(all(c.regime == "C" for c in m._montar_hibrido().searcher.chunks), "e é cortada no regime C")


def test_api(pasta: Path) -> None:
    print("\npela API, com a chave ligada")
    if not (LEIS / ARQUIVOS["cdc"]).exists():
        print("  pulado: sem o CDC do Planalto")
        return
    from fastapi.testclient import TestClient

    import api
    import biblioteca_demo

    original_m, original_l, prefs = api.estado.material, api.estado.leis, dict(api.estado.prefs.dados.get("biblioteca") or {})
    base = Base(pasta / "api.db")
    # A lei entregue vai para <dados>/leis: aqui, a pasta do teste, e nao a de verdade.
    dados_de_verdade, api.DADOS_DIR = api.DADOS_DIR, pasta
    api.estado.material = material_mod.Material(pasta / "material")
    api.estado.leis = leis_mod.Leis(base)
    api.estado.prefs.dados["biblioteca"] = {**prefs, "triagem": True}
    try:
        c = TestClient(api.app, headers=api.cabecalho_local())
        r = c.post("/api/material", files=[("arquivos", ("cdc.pdf", biblioteca_demo.cdc_em_pdf(), "application/pdf")),
                                           ("arquivos", ("obra.pdf", biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_B),
                                                         "application/pdf"))])
        d = r.json()
        checar(r.status_code == 200 and d["leis"] and d["leis"][0]["codigo"] == "cdc", "o CDC foi para as leis", d.get("leis"))
        checar(len(d["entraram"]) == 1 and d["entraram"][0]["ficha"]["autor"] == "Marina Albuquerque Teles",
               "a obra entrou no material, com a ficha", [x.get("ficha", {}).get("autor") for x in d["entraram"]])
        checar(any("artigo por artigo" in a["mensagem"] for a in d["avisos"]), "e o aviso da lei vai para a tela")
        id_ = d["entraram"][0]["id"]
        r = c.put(f"/api/material/{id_}/ficha", json={"edicao": "2ª", "areas": ["civil", "inexistente"]})
        checar(r.status_code == 200 and r.json()["item"]["ficha"]["edicao"] == "2ª"
               and r.json()["item"]["ficha"]["areas"] == ["civil"], "a ficha se edita, e área que não existe não entra")
        r = c.put(f"/api/material/{id_}/ficha", json={"ano": "22"})
        checar(r.status_code == 400, "ano que não é ano volta com o motivo", r.json())
        checar(c.get("/api/leis").json()["contagem"]["codigos"] == 1, "a tela de leis mostra o CDC instalado")
    finally:
        api.estado.material, api.estado.leis = original_m, original_l
        api.DADOS_DIR = dados_de_verdade
        api.estado.prefs.dados["biblioteca"] = prefs
        base.con.close()


def main() -> int:
    print("=" * 55)
    print("  M2 — triagem, ficha e as leis que faltam")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-m2-{i}-")) for i in range(5)]
    try:
        test_fichas()
        test_sem_ficha(pastas[0])
        test_cdc_em_pdf(pastas[1])
        test_codigos_novos(pastas[2])
        test_triagem_outros(pastas[3])
        test_api(pastas[4])
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
