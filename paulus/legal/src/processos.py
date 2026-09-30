"""
Acompanhamento de processos pelo DataJud (docs/PLANO-PILOTO.md, L2).

- **Os processos do escritório**: os números CNJ que a leitura dos documentos
  já achou e validou (meta_fatos, seção "case") entram como "encontrados";
  a pessoa também põe um número à mão. Cada um pode ficar ligado a um
  Serviço - a pasta de onde o documento veio liga sozinha.
- **Acompanhar**: uma vez por dia, para cada processo acompanhado, o
  PAULUS pergunta ao DataJud (a API pública do CNJ, src/biblioteca/
  tribunais.py) os movimentos. **Só o número do processo sai desta
  máquina**, e ele é público. Desligado de fábrica (`processos.acompanhar`):
  quem liga é o escritório, na tela.
- **Movimentação nova** vira aviso na Central (T2). A primeira consulta de um
  processo só guarda o que já havia - senão o escritório ganharia cem avisos
  de coisa antiga.
- **Prazo sugerido**: movimentação de intimação, citação ou publicação vira
  um pedido em Aprovações com a conta do prazo à vista (src/prazos.py). O
  prazo é o do ato que a intimação comunica (src/tipo_de_ato.py, N1): a
  sentença, o acórdão, a decisão ou o despacho que veio antes, no ramo do
  processo; sem reconhecer o ato, 15 dias úteis, e a tela diz. É sugestão: a
  data do DataJud é a do registro do movimento, e a contagem certa depende
  da ciência - a anotação da tarefa diz isso. O sim cria a tarefa na lista
  "Prazos", com a opção que a pessoa escolheu.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from datetime import date, datetime
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel

DIAS_SUGERIDOS = 15
# Entre uma consulta e a próxima, na volta diária: o DataJud é público e lento.
PAUSA_ENTRE_CONSULTAS_S = 3
_trava = threading.Lock()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _chave(grau: str, m: dict) -> str:
    return hashlib.sha1("|".join((grau, m.get("quando", ""), m.get("nome", ""), m.get("complemento", ""))).encode()).hexdigest()[:20]


def sugerir_prazo(mov: dict, extras=None, anteriores: list[dict] | None = None, processo: dict | None = None) -> dict | None:
    """
    O prazo sugerido para uma movimentação (ou None), com a conta inteira.

    `anteriores`: as movimentações do mesmo grau antes desta, da mais nova
    para a mais antiga - é nelas que o ato comunicado aparece.
    """
    import tipo_de_ato

    if not tipo_de_ato.gatilho(mov):
        return None
    try:
        dia = date.fromisoformat(str(mov.get("quando", ""))[:10])
    except ValueError:
        return None
    texto = f"{mov.get('nome', '')} {mov.get('complemento', '')}"
    origem = "disponibilizacao" if re.search(r"publica|disponibiliza", texto, re.IGNORECASE) else "intimacao"
    p = processo or {}
    s = tipo_de_ato.do_movimento(mov, anteriores or [], classe=mov.get("classe") or p.get("classe") or "",
                                 orgao=mov.get("orgao") or p.get("orgao") or "", tribunal=p.get("tribunal") or "",
                                 grau=mov.get("grau") or "", numero=p.get("numero") or "")
    return com_conta(s, dia, origem, extras)


def com_conta(s: dict, dia: date, origem: str, extras=None) -> dict:
    """A sugestão de src/tipo_de_ato.py com o vencimento de cada opção."""
    import prazos

    base = {"ato": s["ato"], "base": s["base"], "porque": s["porque"], "certeza": s["certeza"], "ramo": s["ramo"],
            "tipo": s["tipo"], "lembrete": s["lembrete"], "origem": origem, "sem_prazo": s.get("sem_prazo") or ""}
    if base["sem_prazo"]:
        return dict(base, dias=0, uteis=True, vencimento="", passos=[s["sem_prazo"]], alternativas=[], opcoes=[])
    recesso = s["ramo"] != "penal"
    conta = prazos.calcular(dia, s["dias"], origem=origem, uteis=s["uteis"], extras=extras, recesso=recesso)
    alternativas = []
    for a in s.get("alternativas") or []:
        c = prazos.calcular(dia, a["dias"], origem=origem, uteis=a["uteis"], extras=extras, recesso=recesso)
        alternativas.append(dict(a, vencimento=c["vencimento"], passos=c["passos"]))
    principal = {"ato": s["ato"], "dias": s["dias"], "uteis": s["uteis"], "base": s["base"],
                 "vencimento": conta["vencimento"], "passos": conta["passos"]}
    return dict(base, dias=s["dias"], uteis=s["uteis"], vencimento=conta["vencimento"], passos=conta["passos"],
                alternativas=alternativas, opcoes=[principal] + alternativas)


def rotulo_prazo(o: dict) -> str:
    return f"{o['ato']} ({o['dias']} dias {'úteis' if o['uteis'] else 'corridos'})"


def _dia_br(v: str) -> str:
    return f"{v[8:10]}/{v[5:7]}/{v[:4]}" if v else ""


def resumo_do_prazo(s: dict) -> str:
    """O texto do pedido em Aprovações: o ato, o porquê, a conta e as outras opções."""
    linhas = [f"{rotulo_prazo(s)} — {s['base']}.", f"Por quê: {s['porque']}."]
    if s["certeza"] == "generico":
        linhas.append("Não reconheci o ato: confira na intimação qual é o prazo.")
    linhas += s["passos"]
    for a in s.get("alternativas") or []:
        linhas.append(f"Também pode ser: {rotulo_prazo(a)}, vence em {_dia_br(a['vencimento'])} — {a['base']}.")
    linhas.append(s["lembrete"])
    return "\n".join(linhas)


class Processos:
    def __init__(self, base, servicos=None) -> None:
        self.base = base
        self.servicos = servicos

    # ------------------------------------------------------------ cadastro
    def adicionar(self, numero: str, *, servico_id=None, origem: str = "manual", documento: str = "",
                  acompanhar: bool = True) -> dict:
        from biblioteca import tribunais

        lido = tribunais.ler_numero(numero)
        if not lido["ok"]:
            raise ValueError(lido["erro"])
        existe = self.base.um("SELECT id FROM processos WHERE numero = ?", (lido["digitos"],))
        if existe:
            if servico_id and not self.base.um("SELECT servico_id FROM processos WHERE id = ? AND servico_id IS NOT NULL", (existe["id"],)):
                self.base.escrever("UPDATE processos SET servico_id = ? WHERE id = ?", (int(servico_id), existe["id"]))
            if acompanhar and origem == "manual":
                self.base.escrever("UPDATE processos SET acompanhar = 1 WHERE id = ?", (existe["id"],))
            return self.obter(existe["id"])
        id_ = self.base.escrever(
            "INSERT INTO processos (numero, numero_fmt, tribunal, servico_id, origem, documento, acompanhar, criado_em)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (lido["digitos"], lido["numero"], lido["alias"].upper(), int(servico_id) if servico_id else None, origem,
             documento, 1 if acompanhar else 0, _agora()))
        return self.obter(id_)

    def obter(self, id_: int) -> dict | None:
        l = self.base.um(
            "SELECT p.*, s.nome AS servico_nome,"
            " (SELECT COUNT(*) FROM movimentos m WHERE m.processo_id = p.id AND m.visto = 0) AS novas,"
            " (SELECT MAX(quando) FROM movimentos m WHERE m.processo_id = p.id) AS ultimo_movimento"
            " FROM processos p LEFT JOIN servicos s ON s.id = p.servico_id WHERE p.id = ?", (int(id_),))
        if not l:
            return None
        d = dict(l)
        d["acompanhar"] = bool(d["acompanhar"])
        return d

    def listar(self, *, servico_id=None, visivel=None) -> list[dict]:
        sql = "SELECT id FROM processos" + (" WHERE servico_id = ?" if servico_id else "") + " ORDER BY criado_em DESC"
        saida = [self.obter(l["id"]) for l in self.base.buscar(sql, (int(servico_id),) if servico_id else ())]
        return [p for p in saida if p and (visivel is None or visivel(p))]

    def mudar(self, id_: int, *, acompanhar=None, servico_id="nao") -> dict:
        if acompanhar is not None:
            self.base.escrever("UPDATE processos SET acompanhar = ? WHERE id = ?", (1 if acompanhar else 0, int(id_)))
        if servico_id != "nao":
            self.base.escrever("UPDATE processos SET servico_id = ? WHERE id = ?", (int(servico_id) if servico_id else None, int(id_)))
        p = self.obter(id_)
        if not p:
            raise LookupError("processo não encontrado")
        return p

    def apagar(self, id_: int) -> None:
        self.base.escrever("DELETE FROM movimentos WHERE processo_id = ?", (int(id_),))
        self.base.escrever("DELETE FROM processos WHERE id = ?", (int(id_),))

    def movimentos(self, id_: int, limite: int = 60) -> list[dict]:
        return [dict(l, visto=bool(l["visto"])) for l in self.base.buscar(
            "SELECT * FROM movimentos WHERE processo_id = ? ORDER BY quando DESC, id DESC LIMIT ?", (int(id_), int(limite)))]

    def marcar_vistos(self, id_: int) -> int:
        return self.base.escrever("UPDATE movimentos SET visto = 1 WHERE processo_id = ? AND visto = 0", (int(id_),))

    def anteriores(self, id_: int, grau: str, quando: str, menos: int | None = None, limite: int = 25) -> list[dict]:
        """As movimentações do mesmo grau até `quando`, da mais nova para a mais antiga (sem a própria)."""
        return self.base.buscar(
            "SELECT * FROM movimentos WHERE processo_id = ? AND grau = ? AND quando <= ? AND id != ?"
            " ORDER BY quando DESC, id DESC LIMIT ?", (int(id_), grau, quando, int(menos or 0), int(limite)))

    def nao_vistos(self) -> list[dict]:
        return self.base.buscar(
            "SELECT p.id, p.numero_fmt, p.tribunal, p.servico_id, s.nome AS servico_nome, COUNT(m.id) AS novas,"
            " MAX(m.quando) AS ultimo, (SELECT nome FROM movimentos x WHERE x.processo_id = p.id AND x.visto = 0"
            " ORDER BY x.quando DESC LIMIT 1) AS ultimo_nome"
            " FROM processos p JOIN movimentos m ON m.processo_id = p.id AND m.visto = 0"
            " LEFT JOIN servicos s ON s.id = p.servico_id GROUP BY p.id")

    # ------------------------------------------------------------ achar
    def _servico_da_pasta(self, caminho: str):
        if self.servicos is None or not caminho:
            return None
        try:
            alvo = Path(caminho).resolve()
        except OSError:
            return None
        for s in self.base.buscar("SELECT id FROM servicos"):
            pasta = self.servicos.pasta_de(int(s["id"]), criar=False)
            if pasta and (alvo == Path(pasta).resolve() or alvo.is_relative_to(Path(pasta).resolve())):
                return int(s["id"])
        return None

    def descobrir(self) -> dict:
        """Os números CNJ válidos que a leitura já achou nos documentos: entram como encontrados, sem acompanhar."""
        from biblioteca import tribunais

        novos = 0
        vistos = 0
        for l in self.base.buscar(
                "SELECT f.valor, f.mostrar, d.caminho, d.titulo FROM meta_fatos f JOIN meta_documentos d"
                " ON d.versao_atual = f.versao_id WHERE f.secao = 'case' AND f.chave = 'case_number'"):
            bruto = l.get("mostrar") or l.get("valor") or ""
            lido = tribunais.ler_numero(bruto)
            if not lido["ok"]:
                continue
            vistos += 1
            if self.base.um("SELECT id FROM processos WHERE numero = ?", (lido["digitos"],)):
                continue
            self.adicionar(bruto, servico_id=self._servico_da_pasta(l.get("caminho") or ""), origem="documento",
                           documento=l.get("titulo") or Path(l.get("caminho") or "").name, acompanhar=False)
            novos += 1
        return {"encontrados": vistos, "novos": novos}

    # ------------------------------------------------------------ consultar
    def atualizar(self, id_: int, consultar) -> dict:
        """Pergunta ao DataJud e guarda os movimentos. {"novos": [...]} - vazio na primeira (a base)."""
        p = self.obter(id_)
        if not p:
            raise LookupError("processo não encontrado")
        primeira = not p.get("ultima_consulta")
        try:
            dados = consultar(p["numero"])
        except Exception as exc:  # noqa: BLE001 - o erro fica no processo, a volta segue
            self.base.escrever("UPDATE processos SET ultimo_erro = ?, ultima_consulta = ? WHERE id = ?",
                               (str(exc)[:300], _agora(), int(id_)))
            return {"novos": [], "erro": str(exc)}
        novos = []
        graus = dados.get("graus") or []
        with _trava:
            for g in graus:
                grau = str(g.get("grau") or "")
                for m in g.get("movimentos") or []:
                    chave = _chave(grau, m)
                    if self.base.um("SELECT id FROM movimentos WHERE processo_id = ? AND chave = ?", (int(id_), chave)):
                        continue
                    mid = self.base.escrever(
                        "INSERT INTO movimentos (processo_id, chave, grau, quando, nome, complemento, visto, criado_em)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (int(id_), chave, grau, m.get("quando", ""), m.get("nome", ""), m.get("complemento", ""),
                         1 if primeira else 0, _agora()))
                    if not primeira:
                        novos.append(dict(m, id=mid, grau=grau, classe=g.get("classe", ""), orgao=g.get("orgao", "")))
            g0 = graus[0] if graus else {}
            self.base.escrever(
                "UPDATE processos SET ultima_consulta = ?, ultimo_erro = '', classe = ?, orgao = ?, achado = ? WHERE id = ?",
                (_agora(), g0.get("classe", "") or p.get("classe") or "", g0.get("orgao", "") or p.get("orgao") or "",
                 1 if graus else 0, int(id_)))
        return {"novos": novos, "primeira": primeira, "graus": len(graus)}


# ------------------------------------------------------------ a volta diária

def ligado(estado) -> bool:
    return bool((estado.prefs.dados.get("processos") or {}).get("acompanhar"))


def _consultar(numero: str) -> dict:
    from biblioteca import tribunais

    return tribunais.consultar_datajud(numero, movimentos=400)


def rodar(estado, consultar=None, pausa: float = PAUSA_ENTRE_CONSULTAS_S) -> dict:
    """Uma volta: consulta cada processo acompanhado, guarda o novo e propõe os prazos."""
    consultar = consultar or _consultar
    feitos, novos, erros, propostos = 0, 0, 0, 0
    extras = None
    try:
        import prazos

        extras = prazos.extras_das_preferencias((estado.prefs.dados.get("prazos") or {}).get("feriados"))
    except Exception:  # noqa: BLE001
        extras = None
    for p in estado.processos.listar():
        if not p["acompanhar"]:
            continue
        r = estado.processos.atualizar(p["id"], consultar)
        feitos += 1
        if r.get("erro"):
            erros += 1
        for m in r.get("novos") or []:
            novos += 1
            ant = estado.processos.anteriores(p["id"], m.get("grau", ""), m.get("quando", ""), menos=m.get("id"))
            s = sugerir_prazo(m, extras, ant, p)
            if s and not s["sem_prazo"] and getattr(estado, "fila", None) is not None:
                estado.fila.pedir(
                    f"Prazo? {rotulo_prazo(s)} · processo {p['numero_fmt']}", "agenda",
                    acao="processos.prazo", pedido_por="Acompanhamento de processos",
                    resumo=resumo_do_prazo(s), etiquetas=["DataJud", p["tribunal"]], prazo=s["vencimento"],
                    dados={"processo_id": p["id"], "numero": p["numero_fmt"], "movimento": m.get("nome", ""),
                           "complemento": m.get("complemento", ""), "quando": m.get("quando", ""),
                           "vencimento": s["vencimento"], "passos": s["passos"], "dias": s["dias"],
                           "ato": s["ato"], "base": s["base"], "porque": s["porque"], "certeza": s["certeza"],
                           "opcoes": [dict(o, rotulo=rotulo_prazo(o) + " · vence em " + _dia_br(o["vencimento"])) for o in s["opcoes"]],
                           "lembrete": s["lembrete"], "servico": p.get("servico_nome") or ""})
                propostos += 1
        if pausa:
            time.sleep(pausa)
    estado.prefs.dados.setdefault("processos", {})["ultima"] = date.today().isoformat()
    return {"consultados": feitos, "novos": novos, "erros": erros, "prazos_propostos": propostos}


def escolhida(dados: dict) -> dict | None:
    """A opção de prazo que a pessoa escolheu em Aprovações (a primeira, se não escolheu)."""
    opcoes = dados.get("opcoes") or []
    if not opcoes:
        return None
    try:
        return opcoes[int(dados.get("escolha") or 0)]
    except (ValueError, IndexError, TypeError):
        return opcoes[0]


def executar_prazo(estado, pedido) -> str:
    """O sim em Aprovações: a tarefa do prazo na lista "Prazos", com a conta na anotação (e a opção escolhida)."""
    d = pedido.dados
    o = escolhida(d)
    ato = (o or {}).get("ato") or d.get("ato") or d["movimento"]
    vencimento = (o or {}).get("vencimento") or d["vencimento"]
    passos = (o or {}).get("passos") or d.get("passos") or []
    anotacao = (f"Processo {d['numero']}" + (f" · {d['servico']}" if d.get("servico") else "") +
                f"\nMovimentação no DataJud em {d['quando']}: {d['movimento']}" +
                (f" ({d['complemento']})" if d.get("complemento") else "") +
                (f"\n\n{ato} — {o['base']}" if o else "") +
                (f"\nPor quê: {d['porque']}" if d.get("porque") else "") +
                "\n\nConta sugerida (confira a data da ciência na intimação):\n" + "\n".join(passos) +
                (f"\n\n{d['lembrete']}" if d.get("lembrete") else ""))
    estado.tarefas.salvar({"titulo": f"Prazo: {ato} · {d['numero']}"[:200], "prazo": vencimento,
                           "importante": True, "lista": "Prazos", "anotacao": anotacao})
    return f"prazo anotado em Tarefas › Prazos para {_dia_br(vencimento)}" + (f" ({ato})" if o else "")


def vigiar(estado) -> None:
    """A volta diária em segundo plano, como a das publicações."""
    time.sleep(240)
    while True:
        try:
            pp = estado.prefs.dados.get("processos") or {}
            if ligado(estado) and pp.get("ultima", "") != date.today().isoformat():
                rodar(estado)
        except Exception:  # noqa: BLE001 - a volta nunca derruba o programa
            pass
        time.sleep(3600)


# ------------------------------------------------------------------ rotas

class NovoProcesso(BaseModel):
    numero: str
    servico_id: int | None = None


class MudarProcesso(BaseModel):
    acompanhar: bool | None = None
    servico_id: int | None = None
    mudar_servico: bool = False


def montar(estado, app) -> None:
    import servicos_acesso

    estado.processos = Processos(estado.base, estado.servicos)
    central = getattr(estado, "central_avisos", None)
    if central is not None:
        central.processos = estado.processos

    def _filtro(request):
        from acesso import rotas as rotas_do_acesso

        sessao = rotas_do_acesso.pessoa(request)
        if not sessao or not servicos_acesso.restrita(sessao):
            return None
        # De fora, com a equipe restrita: só os processos de Serviços que a pessoa vê.
        return lambda p: bool(p.get("servico_id")) and servicos_acesso.visivel(int(p["servico_id"]))

    def _um(id_: int, request) -> dict:
        p = estado.processos.obter(id_)
        filtro = _filtro(request)
        if not p or (filtro is not None and not filtro(p)):
            raise HTTPException(status_code=404, detail="processo não encontrado")
        return p

    @app.get("/api/processos")
    def processos_listar(servico_id: int | None = None, request: Request = None) -> dict:
        pp = estado.prefs.dados.get("processos") or {}
        return {"acompanhar": ligado(estado), "ultima": pp.get("ultima", ""),
                "processos": estado.processos.listar(servico_id=servico_id, visivel=_filtro(request))}

    @app.get("/api/processos/{id_}")
    def processos_um(id_: int, request: Request = None) -> dict:
        p = _um(id_, request)
        return {"processo": p, "movimentos": estado.processos.movimentos(id_)}

    @app.post("/api/processos")
    def processos_novo(payload: NovoProcesso) -> dict:
        try:
            return estado.processos.adicionar(payload.numero, servico_id=payload.servico_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/processos/descobrir")
    def processos_descobrir() -> dict:
        return estado.processos.descobrir()

    @app.put("/api/processos/{id_}")
    def processos_mudar(id_: int, payload: MudarProcesso) -> dict:
        try:
            return estado.processos.mudar(id_, acompanhar=payload.acompanhar,
                                          servico_id=payload.servico_id if payload.mudar_servico else "nao")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.delete("/api/processos/{id_}")
    def processos_apagar(id_: int) -> dict:
        estado.processos.apagar(id_)
        return {"apagado": True}

    @app.post("/api/processos/{id_}/consultar")
    def processos_consultar(id_: int) -> dict:
        """Consultar agora, só este (a pessoa pediu): o novo vira aviso como na volta diária."""
        if not estado.processos.obter(id_):
            raise HTTPException(status_code=404, detail="processo não encontrado")
        r = estado.processos.atualizar(id_, _CONSULTAR["fn"] or _consultar)
        return dict(r, processo=estado.processos.obter(id_), movimentos=estado.processos.movimentos(id_))

    @app.post("/api/processos/acompanhar-agora")
    def processos_rodar() -> dict:
        if not ligado(estado):
            raise HTTPException(status_code=409, detail="o acompanhamento pelo DataJud está desligado")
        return rodar(estado, _CONSULTAR["fn"] or _consultar, pausa=0)

    @app.post("/api/processos/{id_}/vistos")
    def processos_vistos(id_: int, request: Request = None) -> dict:
        _um(id_, request)
        return {"marcados": estado.processos.marcar_vistos(id_)}


# Os testes trocam a consulta ao DataJud aqui.
_CONSULTAR: dict = {"fn": None}
