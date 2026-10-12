"""
DataJud: a chave que o CNJ troca, o DataJud indisponível e o perfil da vara
(src/biblioteca/tribunais.py, src/processos.py, js/64-processos.js).

Com o DataJud e a wiki do CNJ trocados por uns de mentira (nada sai daqui):

  - a chave: recusada (403), o PAULUS lê a vigente na wiki, guarda em
    <dados>/datajud.json e tenta de novo; a próxima consulta já vai com ela;
    a wiki sem chave (ou com texto que não é chave) dá o erro claro; com
    PAULUS_DATAJUD_CHAVE a wiki nem é lida;
  - indisponível: 429, 5xx e a rede caída viram DataJudIndisponivel; a volta
    diária tenta esses de novo no fim (e só esses); a volta pedida na tela
    não espera;
  - o perfil: a sentença pelo código da TPU ou pelo começo do nome ("de
    Instrução e Julgamento" é audiência); mediana e quartis; os pedidos ao
    DataJud levam só os códigos; a rota guarda 30 dias, de fora só lê;
  - no Edge: o botão no processo e o perfil aberto.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_datajud_chave_perfil.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-datajud-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ.pop("PAULUS_DATAJUD_CHAVE", None)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []

# "id-novo:segredo-novo" em base64: tem o ":" de uma chave do DataJud.
CHAVE_NOVA = "aWQtbm92bzpzZWdyZWRvLW5vdm8="


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Resp:
    def __init__(self, status: int, dados=None, texto: str = "") -> None:
        self.status_code, self._dados, self.text = status, dados, texto

    def json(self):
        if self._dados is None:
            raise ValueError("sem json")
        return self._dados


class DataJud:
    """Responde 403 a quem não traz a chave aceita; `status` força outra resposta."""

    def __init__(self, aceita: str) -> None:
        self.aceita, self.status, self.chaves, self.corpos = aceita, None, [], []

    def __call__(self, url, json=None, headers=None, timeout=None):
        chave = headers["Authorization"].split(" ", 1)[1]
        self.chaves.append(chave)
        self.corpos.append(json)
        if self.status == "rede":
            raise TimeoutError("demorou")
        if self.status:
            return Resp(self.status)
        if chave != self.aceita:
            return Resp(403)
        return Resp(200, {"hits": {"total": {"value": 1}, "hits": [{"_source": {
            "tribunal": "TJSP", "grau": "G1", "classe": {"codigo": 7, "nome": "Procedimento Comum Cível"},
            "orgaoJulgador": {"codigo": 1234, "nome": "1ª Vara Cível"}, "movimentos": []}}]}})


def wiki(texto: str):
    lidas = []

    def ler(url):
        lidas.append(url)
        return Resp(200, texto=texto)
    ler.lidas = lidas
    return ler


PAGINA = ("<p>APIKey atual:</p><pre><code>Authorization: APIKey <span>" + CHAVE_NOVA + "</span></code></pre>"
          '<p>utilize o formato "Authorization: APIKey [Chave Pública]"</p>')
NUMERO = "1000001-11.2024.8.26.0100"


def numero_cnj(seq: int, ano: int = 2024, j: str = "8", tr: str = "26", origem: str = "0100") -> str:
    n = f"{seq:07d}"
    dd = 98 - (int(n + str(ano) + j + tr + origem) * 100 % 97)
    return f"{n}-{dd:02d}.{ano}.{j}.{tr}.{origem}"


def main() -> int:
    print("=" * 55)
    print("  DataJud — chave, indisponível e perfil da vara")
    print("=" * 55)
    from biblioteca import tribunais

    numero = numero_cnj(1)
    arquivo = Path(os.environ["PAULUS_DADOS"]) / "datajud.json"

    print("\na chave trocada pelo CNJ")
    checar(tribunais.chave_atual() == tribunais.CHAVE_PUBLICA, "sem nada guardado: a de fábrica")
    dj, ler = DataJud(CHAVE_NOVA), wiki(PAGINA)
    r = tribunais.consultar_datajud(numero, pedir=dj, ler=ler)
    checar(r["graus"] and dj.chaves == [tribunais.CHAVE_PUBLICA, CHAVE_NOVA] and len(ler.lidas) == 1,
           "recusada: lê a wiki e tenta de novo com a nova", dj.chaves)
    checar(json.loads(arquivo.read_text(encoding="utf-8"))["chave"] == CHAVE_NOVA and tribunais.chave_atual() == CHAVE_NOVA,
           "a nova fica guardada na pasta de dados")
    dj.chaves.clear()
    tribunais.consultar_datajud(numero, pedir=dj, ler=ler)
    checar(dj.chaves == [CHAVE_NOVA] and len(ler.lidas) == 1, "a próxima consulta já vai com ela, sem ler a wiki")
    checar(r["graus"][0]["orgao_codigo"] == 1234 and r["graus"][0]["classe_codigo"] == 7, "o resumo traz os códigos da vara e da classe")

    arquivo.unlink()
    for nome, pagina in (("sem chave na página", "<p>APIKey atual: em manutenção</p>"),
                         ("texto que não é chave", "<p>APIKey " + "A" * 40 + "</p>")):
        try:
            tribunais.consultar_datajud(numero, pedir=DataJud(CHAVE_NOVA), ler=wiki(pagina))
            checar(False, f"wiki {nome}: erro claro")
        except PermissionError as exc:
            checar("suporte" in str(exc) and not arquivo.exists(), f"wiki {nome}: erro claro, nada guardado", str(exc))
    os.environ["PAULUS_DATAJUD_CHAVE"] = "minha"
    ler = wiki(PAGINA)
    try:
        tribunais.consultar_datajud(numero, pedir=DataJud(CHAVE_NOVA), ler=ler)
    except PermissionError:
        pass
    checar(not ler.lidas, "com PAULUS_DATAJUD_CHAVE a wiki nem é lida")
    del os.environ["PAULUS_DATAJUD_CHAVE"]
    checar(tribunais.chave_do_cnj(ler=lambda url: Resp(500)) == "", "a wiki fora: nenhuma chave")

    print("\no DataJud indisponível")
    for status in (429, 502, 503, 504, "rede"):
        dj = DataJud(tribunais.CHAVE_PUBLICA)
        dj.status = status
        try:
            tribunais.consultar_datajud(numero, pedir=dj, ler=wiki(""))
            checar(False, f"{status}: indisponível")
        except tribunais.DataJudIndisponivel as exc:
            checar("DataJud" in str(exc), f"{status}: DataJudIndisponivel", str(exc))
    dj = DataJud(tribunais.CHAVE_PUBLICA)
    dj.status = 400
    try:
        tribunais.consultar_datajud(numero, pedir=dj, ler=wiki(""))
    except tribunais.DataJudIndisponivel:
        checar(False, "400 não é indisponível")
    except ConnectionError:
        checar(True, "400 continua erro comum (não tenta de novo)")

    print("\na sentença e o tempo")
    checar(tribunais.e_sentenca({"codigo": 219, "nome": "Procedência"}), "código 219 (Procedência)")
    checar(tribunais.e_sentenca({"codigo": 0, "nome": "Extinção da execução ou do cumprimento da sentença"}), "pelo nome: extinção")
    checar(not tribunais.e_sentenca({"codigo": 12750, "nome": "de Instrução e Julgamento"}), "audiência de instrução e julgamento não é sentença")
    checar(not tribunais.e_sentenca({"codigo": 12164, "nome": "Outras Decisões"}), "decisão não é sentença")

    def proc(ajuiz: str, *movs) -> dict:
        return {"_source": {"dataAjuizamento": ajuiz, "movimentos": [
            {"codigo": c, "nome": n, "dataHora": q} for c, n, q in movs]}}
    hits = [proc("20210101000000", (219, "Procedência", "2021-04-11T10:00:00.000Z")),          # 100 dias
            proc("20210101000000", (220, "Improcedência", "2021-07-20T10:00:00.000Z"),        # 200 dias (a primeira)
                 (219, "Procedência", "2022-01-01T10:00:00.000Z")),
            proc("20210101000000", (0, "Homologação de Transação", "20211028000000")),       # 300 dias
            proc("20210101000000", (12750, "de Instrução e Julgamento", "2021-02-01T10:00:00.000Z")),
            proc("20210101000000")]
    t = tribunais.tempo_ate_sentenca(hits)
    checar(t["amostra"] == 5 and t["com_sentenca"] == 3 and t["mediana"] == 200 and t["q1"] == 150 and t["q3"] == 250,
           "3 de 5 com sentença; mediana 200 dias, meio de 150 a 250", t)

    print("\no perfil da vara (DataJud de mentira)")
    corpos = []

    def pedir_perfil(url, json=None, headers=None, timeout=None):
        corpos.append(json)
        if "aggs" in json:
            return Resp(200, {"hits": {"total": {"value": 5000}, "hits": [{"_source": {"orgaoJulgador": {"nome": "1ª Vara Cível"}}}]},
                              "aggregations": {"graus": {"buckets": [{"key": "G1", "doc_count": 5000}]},
                                               "classes": {"buckets": [{"key": "Procedimento Comum Cível", "doc_count": 3000}]},
                                               "assuntos": {"buckets": [{"key": "Dano Moral", "doc_count": 900}]},
                                               "anos": {"buckets": {"2024": {"doc_count": 700}, "2026": {"doc_count": 300}}}}})
        return Resp(200, {"hits": {"total": {"value": 40}, "hits": hits}})
    p = tribunais.perfil_do_orgao("tjsp", 1234, 7, classe="Procedimento Comum Cível", pedir=pedir_perfil, hoje=date(2026, 10, 12))
    checar(p["total"] == 5000 and p["orgao"] == "1ª Vara Cível" and p["classes"][0]["qtd"] == 3000, "contagens da vara", p)
    checar([a["nome"] for a in p["por_ano"]] == ["2022", "2023", "2024", "2025", "2026"] and p["por_ano"][2]["qtd"] == 700
           and p["por_ano"][0]["qtd"] == 0, "um balde por ano, os vazios com zero", p["por_ano"])
    checar(p["tempo"]["mediana"] == 200 and p["tempo"]["de"] == 2020 and p["tempo"]["ate"] == 2023 and p["tempo"]["populacao"] == 40,
           "o tempo da amostra, com o período", p["tempo"])
    enviado = json.dumps(corpos)
    checar(len(corpos) == 2 and "1234" in enviado and NUMERO not in enviado and "numeroProcesso" not in enviado,
           "ao DataJud vão só os códigos da vara e da classe")
    corpos.clear()
    p = tribunais.perfil_do_orgao("tjsp", 1234, 0, pedir=pedir_perfil, hoje=date(2026, 10, 12))
    checar(len(corpos) == 1 and p["tempo"] is None, "sem a classe: só as contagens, sem amostra")

    print("\nno PAULUS: a volta diária e as rotas")
    import api
    import processos
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    tentativas: dict[str, int] = {}
    cair: set[str] = set()
    quebrar: set[str] = set()

    def consultar(num: str) -> dict:
        tentativas[num] = tentativas.get(num, 0) + 1
        if num in cair and tentativas[num] == 1:
            raise tribunais.DataJudIndisponivel("o DataJud do CNJ está sobrecarregado agora (respondeu 429)")
        if num in quebrar:
            raise ConnectionError("o DataJud respondeu com erro (400)")
        return {"graus": [{"grau": "G1", "classe": "Procedimento Comum Cível", "classe_codigo": 7,
                           "orgao": "1ª Vara Cível", "orgao_codigo": 1234, "movimentos": []}]}
    processos._CONSULTAR["fn"] = consultar
    a, b, c = numero_cnj(11), numero_cnj(22), numero_cnj(33)
    ids = [local.post("/api/processos", json={"numero": n}).json()["id"] for n in (a, b, c)]
    digitos = {n: n.replace("-", "").replace(".", "") for n in (a, b, c)}
    cair.add(digitos[a])
    quebrar.add(digitos[c])
    api.estado.prefs.dados.setdefault("processos", {})["acompanhar"] = True
    r = processos.rodar(api.estado, consultar, pausa=0, espera_de_novo=0.01)
    checar(r["de_novo"] == 1 and tentativas[digitos[a]] == 2 and tentativas[digitos[b]] == 1 and tentativas[digitos[c]] == 1,
           "o indisponível vai de novo no fim; os outros, uma vez só", (r, tentativas))
    checar(r["erros"] == 1, "o erro comum conta como erro e não vai de novo", r)
    checar(not api.estado.processos.obter(ids[0])["ultimo_erro"], "deu certo na segunda: o erro some do processo")
    tentativas.clear()
    quebrar.clear()
    cair.add(digitos[b])
    r = local.post("/api/processos/acompanhar-agora").json()
    checar(r["de_novo"] == 0 and tentativas[digitos[b]] == 1 and "sobrecarregado" in api.estado.processos.obter(ids[1])["ultimo_erro"],
           "pedida na tela: não espera; o motivo fica no processo", r)
    pa = api.estado.processos.obter(ids[0])
    checar(pa["orgao_codigo"] == 1234 and pa["classe_codigo"] == 7, "o processo guarda os códigos da vara e da classe", pa)

    chamadas = []

    def perfilar(alias, orgao, classe_codigo, classe=""):
        chamadas.append((alias, orgao, classe_codigo, classe))
        return {"tribunal": alias.upper(), "orgao_codigo": orgao, "orgao": "1ª Vara Cível", "total": 5000,
                "graus": [{"nome": "G1", "qtd": 5000}], "classes": [{"nome": "Procedimento Comum Cível", "qtd": 3000}],
                "assuntos": [{"nome": "Dano Moral", "qtd": 900}],
                "por_ano": [{"nome": str(y), "qtd": 100 * (y - 2021)} for y in range(2022, 2027)],
                "tempo": {"amostra": 100, "com_sentenca": 80, "mediana": 400, "q1": 250, "q3": 700,
                          "classe": classe, "de": 2020, "ate": 2023, "populacao": 300}}
    processos._PERFIL["fn"] = perfilar
    pid = ids[0]
    checar(local.get(f"/api/processos/{pid}/perfil").json() == {"perfil": None}, "sem perfil tirado: vazio")
    r = local.post(f"/api/processos/{pid}/perfil")
    checar(r.status_code == 200 and r.json()["perfil"]["total"] == 5000 and chamadas == [("tjsp", 1234, 7, "Procedimento Comum Cível")],
           "tirar o perfil: pelo alias e pelos códigos", (r.status_code, chamadas))
    g = local.get(f"/api/processos/{pid}/perfil").json()
    checar(g["perfil"]["total"] == 5000 and not g["vencido"] and len(chamadas) == 1, "guardado: abrir de novo não consulta")
    api.estado.base.escrever("UPDATE perfis_orgao SET criado_em = '2026-01-01T00:00:00'")
    checar(local.get(f"/api/processos/{pid}/perfil").json()["vencido"], "com mais de 30 dias: vencido")

    def perfil_cheio(*args, **kw):
        raise tribunais.DataJudIndisponivel("o DataJud do CNJ está sobrecarregado agora (respondeu 429)")
    processos._PERFIL["fn"] = perfil_cheio
    r = local.post(f"/api/processos/{pid}/perfil")
    checar(r.status_code == 503 and "sobrecarregado" in r.text, "DataJud cheio: 503 com o motivo", r.status_code)
    processos._PERFIL["fn"] = perfilar
    local.post(f"/api/processos/{pid}/perfil")

    sem_codigo = api.estado.base.escrever(
        "INSERT INTO processos (numero, numero_fmt, tribunal, acompanhar, criado_em) VALUES (?,?,?,0,'2026-10-01')",
        (numero_cnj(44).replace("-", "").replace(".", ""), numero_cnj(44), "TJSP"))
    r = local.post(f"/api/processos/{sem_codigo}/perfil")
    checar(r.status_code == 200 and api.estado.processos.obter(sem_codigo)["orgao_codigo"] == 1234,
           "processo antigo, sem os códigos: consulta antes e tira o perfil", r.status_code)

    from acesso import politicas
    checar(politicas.de("GET", "/api/processos/{id_}/perfil") == politicas.PERMITIDO
           and politicas.de("POST", "/api/processos/{id_}/perfil") == politicas.BLOQUEADO,
           "de fora: vê o perfil guardado, não tira outro")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as pw:
            try:
                nav = pw.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 860}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abrirProcesso === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate(f"() => {{ abrirProcesso({pid}); }}")
                pag.wait_for_selector("[data-pr-perfil]", timeout=15000)
                pag.click("[data-pr-perfil]")
                pag.wait_for_selector(".pr-perfil .pr-barra", timeout=15000)
                texto = pag.inner_text(".pr-perfil")
                checar("5.000 processos desta vara" in texto and "Dano Moral" in texto and "2026 (até agora)" in texto,
                       "o perfil: total, assuntos e o ano corrente marcado", texto[:200])
                checar("cerca de 13 meses" in texto and "ficam fora da conta" in texto,
                       "o tempo em meses, com a ressalva dos que esperam", texto[-500:])
                pag.wait_for_timeout(700)
                pag.screenshot(path=str(TMP / "perfil-da-vara.png"))
                pag.set_viewport_size({"width": 400, "height": 800})
                pag.wait_for_timeout(300)
                larg = pag.evaluate("() => document.querySelector('.pr-perfil').scrollWidth <= document.querySelector('.pr-perfil').clientWidth + 1")
                checar(larg, "no celular (400 px) o perfil não transborda")
                pag.screenshot(path=str(TMP / "perfil-da-vara-celular.png"), full_page=True)
                pag.click("[data-dialogo='confirmar']")
                pag.wait_for_selector("[data-pr-perfil]", timeout=10000)
                checar(True, "voltar ao processo")
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

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
