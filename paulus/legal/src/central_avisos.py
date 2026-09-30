"""
PAULUS - Central de avisos (T2, docs/prompt-conversa-agentes-v0.md §2.7).

Junta, num lugar so, o que cada tela ja sabe que pede atencao: prazo,
compromisso, vencimento de documento, conta a pagar e a receber, publicacao
nova do DJEN, tarefa do dia, aprovacao esperando, conversa pela metade e os
lembretes do Vigia. Nao muda a regra de nenhuma fonte: cada uma continua
decidindo o que esta aberto, atrasado ou lido; aqui so se le, se da um nome
estavel a cada aviso e se guarda quem ja viu.

O ID E A ORIGEM MAIS A DATA. `prazo:<tarefa>:<vencimento>`,
`compromisso:<id>:<data>`, `pagar:<lancamento>:<vencimento>`... O mesmo
prazo, venha da Agenda ou da lista de Tarefas, da o mesmo id - e e um aviso
so. Antes do dia, o id ganha ":antes": o aviso "em 3 dias" e o "vence hoje"
sao dois avisos, e quem marcou o primeiro como visto recebe o segundo no dia
do vencimento. Visto nao conclui nada: um prazo visto continua prazo.

"Visto" e por pessoa ("local" = a janela do escritorio; "conta:<id>" = quem
entrou de fora) e fica em `avisos_vistos`, com a copia do que o aviso dizia
naquele momento - o historico conta o que a pessoa leu, e nao o que o aviso
diz hoje.

O relogio vem de fora (`hoje`, `agora`): e assim que os testes simulam o
dia seguinte sem mexer no relogio da maquina.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable

# O que cada tipo e, e ate quantos dias a frente ele entra no carrossel.
# Compromisso: hoje e amanha. Tarefa: do dia ou atrasada. Publicacao,
# pendencia e rotina nao tem "a frente": ou estao esperando agora, ou nao
# estao. A ordem desempata no mesmo dia: prazo processual primeiro.
TIPOS: dict[str, dict] = {
    "prazo": {"rotulo": "Prazo", "icone": "gavel", "ordem": 0, "horizonte": 7},
    "compromisso": {"rotulo": "Compromisso", "icone": "event", "ordem": 1, "horizonte": 1},
    "vencimento": {"rotulo": "Vencimento", "icone": "description", "ordem": 2, "horizonte": 7},
    "a_pagar": {"rotulo": "A pagar", "icone": "payments", "ordem": 3, "horizonte": 7},
    "a_receber": {"rotulo": "A receber", "icone": "receipt_long", "ordem": 4, "horizonte": 7},
    "tarefa": {"rotulo": "Tarefa", "icone": "task_alt", "ordem": 5, "horizonte": 0},
    "publicacao": {"rotulo": "Publicação", "icone": "article", "ordem": 6, "horizonte": 0},
    "processo": {"rotulo": "Processo", "icone": "gavel", "ordem": 6, "horizonte": 0},
    "pendencia": {"rotulo": "Pendência", "icone": "rate_review", "ordem": 7, "horizonte": 0},
    "rotina": {"rotulo": "Rotina", "icone": "self_improvement", "ordem": 8, "horizonte": 0},
}
# Os periodos da aba Todos: ate quantos dias a frente (o atrasado entra sempre).
PERIODOS = {"hoje": 0, "semana": 7, "mes": 30}
GRUPOS = ("atrasado", "hoje", "amanha", "semana", "depois")
# Tipos sem data de vencimento: nao ganham destaque de "vence hoje".
SEM_VENCIMENTO = {"publicacao", "processo", "pendencia", "rotina"}
# A lista de Tarefas em que o prazo tirado de uma publicacao do DJEN cai
# (api.py, publicacoes_prazo): e o prazo processual.
LISTA_DOS_PRAZOS = "Prazos"


# ------------------------------------------------------------------ os ids

def id_do_aviso(prefixo: str, chave, data: str, hoje: date) -> str:
    """O id pela origem e pela data; antes do dia, com ':antes'."""
    base = f"{prefixo}:{chave}:{data}"
    return base + ":antes" if data > hoje.isoformat() else base


def id_rotina(lembrete_id: int, vence: datetime) -> str:
    """O lembrete que venceu nesta hora. Feito de novo, vence outra: outro aviso."""
    return f"rotina:{lembrete_id}:{vence:%Y-%m-%dT%H:%M}"


def id_compromisso_do_dia(compromisso_id: int, dia: str) -> str:
    """O compromisso no dia dele - o mesmo id que o Vigia usa no aviso do Windows."""
    return f"compromisso:{compromisso_id}:{dia}"


# --------------------------------------------------------------- as frases

def _dias(n: int) -> str:
    return "1 dia" if n == 1 else f"{n} dias"


def _br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}" if len(iso) >= 10 else iso


def _quando(tipo: str, dias: int, hora: str = "") -> str:
    """'vence hoje', 'em 3 dias', 'atrasado há 2 dias', 'amanhã às 10:00'."""
    com_hora = f" às {hora}" if hora else ""
    if dias < 0:
        return "atrasado há " + _dias(-dias)
    if tipo in ("compromisso", "tarefa"):
        if dias == 0:
            return ("hoje" + com_hora) if (hora or tipo == "compromisso") else "para hoje"
        if dias == 1:
            return "amanhã" + com_hora
        return f"em {dias} dias" + com_hora
    if dias == 0:
        return "vence hoje"
    if dias == 1:
        return "vence amanhã"
    return f"em {dias} dias"


def _grupo(dias: int) -> str:
    if dias < 0:
        return "atrasado"
    if dias == 0:
        return "hoje"
    if dias == 1:
        return "amanha"
    return "semana" if dias <= 7 else "depois"


def _normal(texto: str) -> str:
    return " ".join(str(texto or "").lower().split())


def _data(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor or "")[:10])
    except ValueError:
        return None


def _sempre(metodo: str, rota: str) -> str:
    return "permitido"


class Central:
    """
    As fontes entram por injecao - cada uma e o objeto que a tela de origem
    ja usa -, para que o aviso diga exatamente o que a tela diria.

    `politica(metodo, rota)` diz o que a pessoa da vez pode naquela rota
    ("permitido", "propor", ou None quando nao pode). Na janela do escritorio
    pode tudo; de fora, o que a rota de origem permite: quem nao ve o
    Financeiro nao recebe aviso de conta, e a acao direta so aparece quando
    a rota que ela chama aceitaria o pedido.
    """

    def __init__(self, base, *, agenda=None, tarefas=None, financeiro=None, publicacoes=None, fila=None,
                 trabalhos=None, bem_estar=None, classificados: Callable[[], list] | None = None,
                 disponibilidade: Callable[[], dict] | None = None) -> None:
        self.base = base
        self.agenda = agenda
        self.tarefas = tarefas
        self.financeiro = financeiro
        self.publicacoes = publicacoes
        self.fila = fila
        self.trabalhos = trabalhos
        self.bem_estar = bem_estar
        # L2 (src/processos.py): as movimentacoes novas do DataJud.
        self.processos = None
        self.classificados = classificados or (lambda: [])
        self.disponibilidade = disponibilidade or (lambda: {})
        # A fonte que falhou na ultima volta: a tela diz que faltou uma, em
        # vez de mostrar a lista incompleta como se fosse inteira.
        self.falhas: list[str] = []

    # ------------------------------------------------------------ o relogio

    @staticmethod
    def _relogio(hoje, agora) -> tuple[date, datetime]:
        if isinstance(hoje, str):
            hoje = date.fromisoformat(hoje[:10])
        if agora is None:
            # Dia simulado sem hora: o comeco do dia - nada acabou ainda.
            agora = datetime.now() if hoje is None or hoje == date.today() else datetime.combine(hoje, time(0, 0))
        return (hoje or agora.date()), agora

    # ------------------------------------------------------------ as fontes

    def coletar(self, *, hoje=None, agora=None, horizonte: int | None = None, pessoa: str = "local",
                politica=None) -> list[dict]:
        """
        Todos os avisos, sem duplicado e na ordem da tela. `horizonte` None
        e o do carrossel (o de cada tipo); um numero vale para todos os
        tipos - e o periodo da aba Todos.
        """
        hoje, agora = self._relogio(hoje, agora)
        politica = politica or _sempre
        self.falhas = []

        def ate(tipo: str) -> int:
            return TIPOS[tipo]["horizonte"] if horizonte is None else horizonte

        avisos: list[dict] = []
        for nome, fonte in (("tarefas", self._das_tarefas), ("agenda", self._da_agenda),
                            ("financeiro", self._do_financeiro), ("publicacoes", self._das_publicacoes),
                            ("processos", self._dos_processos),
                            ("documentos", self._dos_documentos), ("aprovacoes", self._das_aprovacoes),
                            ("conversas", self._das_conversas), ("rotinas", self._das_rotinas)):
            try:
                avisos = fonte(avisos, hoje, agora, ate, pessoa, politica)
            except Exception:  # noqa: BLE001 - uma fonte quebrada nao derruba as outras
                self.falhas.append(nome)

        # Defesa final: o mesmo id duas vezes vira um so (o primeiro, que e
        # o da fonte mais especifica).
        unicos: dict[str, dict] = {}
        for a in avisos:
            unicos.setdefault(a["id"], a)
        return sorted(unicos.values(), key=self._ordem)

    @staticmethod
    def _ordem(a: dict) -> tuple:
        return (GRUPOS.index(a["grupo"]), a["data"], TIPOS[a["tipo"]]["ordem"], a.get("hora") or "99:99",
                _normal(a["titulo"]))

    @staticmethod
    def _aviso(tipo: str, id_: str, titulo: str, dias: int, data: str, *, quando: str = "", hora: str = "",
               origem: str = "", destino: dict | None = None, acoes: list | None = None, detalhe: str = "") -> dict:
        return {
            "id": id_, "tipo": tipo, "tipo_rotulo": TIPOS[tipo]["rotulo"], "icone": TIPOS[tipo]["icone"],
            "titulo": " ".join(str(titulo or "").split())[:160], "quando": quando or _quando(tipo, dias, hora),
            "origem": origem, "detalhe": detalhe, "data": data, "hora": hora, "dias": dias,
            "grupo": _grupo(dias),
            # O destaque e discreto e nunca na cor de erro: atrasado ou de hoje
            # pede atencao, nao e falha de ninguem.
            "destaque": dias < 0 or (dias == 0 and tipo not in SEM_VENCIMENTO),
            "destino": destino or {}, "acoes": acoes or [],
        }

    def _das_tarefas(self, avisos, hoje, agora, ate, pessoa, politica):
        if self.tarefas is None or not politica("GET", "/api/tarefas"):
            return avisos
        do_djen = {int(l["tarefa_id"]) for l in self.base.buscar(
            "SELECT tarefa_id FROM publicacoes WHERE tarefa_id IS NOT NULL")}
        concluir = politica("POST", "/api/tarefas/{id_}/concluir")
        for t in self.tarefas.listar("todas"):
            quando = _data(t.get("prazo"))
            if quando is None:
                continue
            dias = (quando - hoje).days
            processual = t.get("lista") == LISTA_DOS_PRAZOS or t["id"] in do_djen
            tipo = "prazo" if processual else "tarefa"
            if dias > ate(tipo):
                continue
            origem = "Publicação do DJEN, em Tarefas" if t["id"] in do_djen else \
                ("Tarefas · " + t["lista"] if t.get("lista") else "Tarefas")
            acoes = []
            if concluir:
                acoes.append({
                    "id": "concluir", "rotulo": "Concluir tarefa", "metodo": "POST",
                    "rota": f"/api/tarefas/{t['id']}/concluir", "corpo": {"valor": True},
                    "propoe": concluir == "propor",
                    "pergunta": "Concluir “" + t["titulo"][:80] + "”?",
                    "explica": "A tarefa sai da lista de abertas, como em Agenda › Tarefas"
                               + (" — e a próxima, que repete, entra no lugar." if t.get("repetir") else ".")
                               + " Marcar como visto não conclui nada; isto conclui."})
            avisos.append(self._aviso(
                tipo, id_do_aviso(tipo, t["id"], quando.isoformat(), hoje), t["titulo"], dias, quando.isoformat(),
                hora=t.get("hora") or "", origem=origem, detalhe=t.get("cadastro_nome") or "",
                destino={"tela": "tarefa", "id": t["id"], "data": quando.isoformat()}, acoes=acoes))
        return avisos

    def _da_agenda(self, avisos, hoje, agora, ate, pessoa, politica):
        if self.agenda is None or not politica("GET", "/api/agenda"):
            return avisos
        # O mesmo prazo na Agenda e em Tarefas e um aviso so: o compromisso
        # com o mesmo nome no mesmo dia de um prazo ou tarefa ja listado nao
        # entra de novo - o aviso que ficou diz que veio dos dois lugares.
        ja = {(_normal(a["titulo"]), a["data"]): a for a in avisos if a["tipo"] in ("prazo", "tarefa")}
        fim = hoje + timedelta(days=ate("compromisso"))
        for c in self.agenda.listar(hoje.isoformat(), fim.isoformat()):
            quando = _data(c.get("data"))
            if quando is None:
                continue
            dias = (quando - hoje).days
            hora = str(c.get("hora") or "")[:5]
            if dias == 0 and c.get("fim") and c["fim"] < agora.strftime("%H:%M") and hoje == agora.date():
                continue    # hoje, e ja acabou
            igual = ja.get((_normal(c["titulo"]), quando.isoformat()))
            if igual:
                if "Agenda" not in igual["origem"]:
                    igual["origem"] += " e na Agenda"
                continue
            onde = c.get("onde_rotulo") or ""
            avisos.append(self._aviso(
                "compromisso", id_do_aviso("compromisso", c["id"], quando.isoformat(), hoje), c["titulo"], dias,
                quando.isoformat(), hora=hora, origem="Agenda" + (f" · {onde}" if onde and c.get("onde") else ""),
                detalhe=c.get("cadastro_nome") or "",
                destino={"tela": "compromisso", "id": c["id"], "data": quando.isoformat()}))
        return avisos

    def _do_financeiro(self, avisos, hoje, agora, ate, pessoa, politica):
        if self.financeiro is None or not politica("GET", "/api/financeiro"):
            return avisos
        liquidar = politica("POST", "/api/financeiro/lancamentos/{id_}/liquidar")
        for l in self.financeiro.listar(situacao="aberto"):
            quando = _data(l.get("vencimento"))
            if quando is None:
                continue
            pagar = l["tipo"] != "recebimento"
            tipo = "a_pagar" if pagar else "a_receber"
            dias = (quando - hoje).days
            if dias > ate(tipo):
                continue
            acoes = []
            if liquidar:
                rotulo = "Marcar como pago" if pagar else "Marcar como recebido"
                acoes.append({
                    "id": "liquidar", "rotulo": rotulo, "metodo": "POST",
                    "rota": f"/api/financeiro/lancamentos/{l['id']}/liquidar", "corpo": {},
                    "propoe": liquidar == "propor",
                    "pergunta": rotulo + ": “" + l["descricao"][:80] + "”?",
                    "explica": ("Registra o pagamento" if pagar else "Registra o recebimento")
                               + " com a data de hoje, como o botão do Financeiro. Dá para reabrir lá."})
            avisos.append(self._aviso(
                tipo, id_do_aviso("pagar" if pagar else "receber", l["id"], quando.isoformat(), hoje),
                f"{l['descricao']} — {l.get('valor', '')}".strip(" —"), dias, quando.isoformat(),
                origem="Financeiro · " + (l.get("categoria_rotulo") or "Outros"),
                detalhe=l.get("cadastro_nome") or "",
                destino={"tela": "financeiro", "id": l["id"]}, acoes=acoes))
        return avisos

    def _das_publicacoes(self, avisos, hoje, agora, ate, pessoa, politica):
        if self.publicacoes is None or not politica("GET", "/api/publicacoes"):
            return avisos
        for p in self.publicacoes.listar("novas"):
            # A de um processo cadastrado entra no aviso do processo (N2).
            if p.get("processo_id") and self.processos is not None:
                continue
            data = str(p.get("data") or "")[:10] or hoje.isoformat()
            processo = p.get("processo") or ""
            titulo = (p.get("tipo") or "Comunicação") + (f" — processo {processo}" if processo else "")
            avisos.append(self._aviso(
                "publicacao", f"publicacao:{p['id']}:{data}", titulo, 0, hoje.isoformat(),
                quando="nova · disponibilizada em " + _br(data),
                origem="DJEN" + (f" · {p['tribunal']}" if p.get("tribunal") else ""),
                detalhe=p.get("orgao") or "", destino={"tela": "publicacao", "id": p["id"]}))
        return avisos

    def _dos_processos(self, avisos, hoje, agora, ate, pessoa, politica):
        """As movimentações novas do DataJud (L2): um aviso por processo, até a pessoa marcar como vistas."""
        if self.processos is None or not politica("GET", "/api/processos"):
            return avisos
        import servicos_acesso

        for p in self.processos.nao_vistos():
            if servicos_acesso.OCULTOS.get() and not (p.get("servico_id") and servicos_acesso.visivel(int(p["servico_id"]))):
                continue
            n = int(p.get("novas") or 0)
            npub = int(p.get("publicacoes") or 0)
            titulo = (p.get("ultima_publicacao") if npub and not n else p.get("ultimo_nome")) or "Movimentação"
            titulo += f" — processo {p['numero_fmt']}"
            quando = str(p.get("ultimo") or "")[:10]
            partes = []
            if n:
                partes.append("1 movimentação nova" if n == 1 else f"{n} movimentações novas")
            if npub:
                partes.append("1 publicação no DJEN" if npub == 1 else f"{npub} publicações no DJEN")
            fontes = " + ".join(x for x, tem in (("DataJud", n), ("DJEN", npub)) if tem)
            avisos.append(self._aviso(
                "processo", f"processo:{p['id']}:{p.get('ultimo') or ''}", titulo, 0, hoje.isoformat(),
                quando=" e ".join(partes) + (f" · {_br(quando)}" if quando else ""),
                origem=fontes + " · " + (p.get("tribunal") or ""), detalhe=p.get("servico_nome") or "",
                destino={"tela": "processo", "id": p["id"]},
                acoes=[{"id": "vistas", "rotulo": "Marcar como vistas", "metodo": "POST",
                        "rota": f"/api/processos/{p['id']}/vistos", "pergunta": f"Marcar como vistas as novidades do processo {p['numero_fmt']}?",
                        "explica": "O aviso sai; as movimentações continuam guardadas no processo, e as publicações do DJEN dele ficam lidas."}]))
        return avisos

    def _dos_documentos(self, avisos, hoje, agora, ate, pessoa, politica):
        """
        As datas dos documentos lidos (tarefas.sugerir, a mesma regra da
        Agenda): so data futura, e so a que ainda nao virou tarefa. A que
        ja esta esperando em Aprovacoes (a leitura propos) sai daqui e fica
        na aprovacao - um aviso so.
        """
        if self.tarefas is None or not politica("GET", "/api/biblioteca"):
            return avisos
        propostos = set()
        if self.fila is not None:
            propostos = {(p.dados.get("documento"), str(p.dados.get("data") or "")[:10])
                         for p in self.fila.pendentes if p.acao == "ajuda.prazo"}
        for s in self.tarefas.sugerir(list(self.classificados() or [])):
            quando = _data(s.get("prazo"))
            if quando is None or (s.get("arquivo"), quando.isoformat()) in propostos:
                continue
            dias = (quando - hoje).days
            if dias > ate("vencimento") or dias < 0:
                continue
            chave = s.get("sha1") or _normal(s.get("arquivo"))
            avisos.append(self._aviso(
                "vencimento", id_do_aviso("vencimento", chave, quando.isoformat(), hoje), s["titulo"], dias,
                quando.isoformat(), origem="Acervo" + (f" · {s['lista']}" if s.get("lista") else ""),
                detalhe=s.get("cliente") or "", destino={"tela": "documento", "nome": s.get("arquivo") or ""}))
        return avisos

    def _das_aprovacoes(self, avisos, hoje, agora, ate, pessoa, politica):
        # Aprovacao so e aviso para quem pode decidir: de fora, "so ve" nao
        # ganha cartao de uma decisao que nao e dele.
        if self.fila is None or not politica("POST", "/api/aprovacoes/decidir"):
            return avisos
        for p in self.fila.pendentes:
            criado = str(p.criado_em or "")[:10] or hoje.isoformat()
            prazo = _data(p.prazo)
            if p.acao == "ajuda.prazo" and prazo:
                dias = (prazo - hoje).days
                if dias > ate("vencimento"):
                    continue
                avisos.append(self._aviso(
                    "vencimento", id_do_aviso("aprovacao", p.id, prazo.isoformat(), hoje),
                    p.titulo.replace(" — anotar?", ""), dias, prazo.isoformat(),
                    origem="Aprovações · da leitura do documento",
                    destino={"tela": "aprovacoes", "id": p.id}))
                continue
            dias = min(0, (prazo - hoje).days) if prazo else 0
            quando = "esperando você" + (f" desde {_br(criado)}" if criado < hoje.isoformat() else "")
            avisos.append(self._aviso(
                "pendencia", f"aprovacao:{p.id}:{criado}", p.titulo, dias,
                (prazo.isoformat() if prazo and dias < 0 else hoje.isoformat()),
                quando=("atrasado há " + _dias(-dias)) if dias < 0 else quando,
                origem="Aprovações · " + p.categoria_rotulo, destino={"tela": "aprovacoes", "id": p.id}))
        return avisos

    def _das_conversas(self, avisos, hoje, agora, ate, pessoa, politica):
        """A conversa que ficou pela metade - de quem a comecou."""
        if self.trabalhos is None or not politica("GET", "/api/trabalhos/{id_}"):
            return avisos
        conta = int(pessoa.split(":", 1)[1]) if pessoa.startswith("conta:") else 0
        for t in self.trabalhos.listar().get("em_andamento", []):
            if t.get("estado") != "pausado":
                continue
            dono = int((t.get("criado_por") or {}).get("conta_id") or 0)
            if dono != conta:
                continue
            desde = str(t.get("atualizado_em") or "")[:10] or hoje.isoformat()
            avisos.append(self._aviso(
                "pendencia", f"conversa:{t['id']}:{desde}", t.get("titulo") or "Conversa", 0, hoje.isoformat(),
                quando="ficou pela metade" + (f" em {_br(desde)}" if desde < hoje.isoformat() else ""),
                origem="Conversas", destino={"tela": "conversa", "id": t["id"]}))
        return avisos

    def _das_rotinas(self, avisos, hoje, agora, ate, pessoa, politica):
        """
        Os lembretes do Vigia (Foco e bem-estar) que passaram da hora: a
        mesma conta do Vigia - ultima vez feito mais o intervalo -, no
        horario de trabalho. Lembrete que nunca foi feito ou que ainda nao
        venceu nao e aviso: senao o carrossel teria "beba agua" o dia todo.
        """
        if self.bem_estar is None or not politica("GET", "/api/bemestar"):
            return avisos
        from avisos import _no_horario

        if not _no_horario(self.disponibilidade() or {}, agora):
            return avisos
        for l in self.bem_estar.lembretes():
            if not l.get("ligado") or l.get("cumprido") or not l.get("ultima_vez"):
                continue
            try:
                vence = datetime.fromisoformat(l["ultima_vez"]) + timedelta(minutes=int(l.get("cada_min") or 60))
            except ValueError:
                continue
            if vence > agora:
                continue
            avisos.append(self._aviso(
                "rotina", id_rotina(l["id"], vence), l["titulo"], 0, hoje.isoformat(),
                quando=f"desde {vence:%H:%M} · a cada {int(l.get('cada_min') or 60)} min",
                origem="Foco e bem-estar", detalhe=l.get("meta_texto") or "", destino={"tela": "foco"}))
        return avisos

    # ------------------------------------------------------ o que a tela usa

    def do_dia(self, pessoa: str, *, hoje=None, agora=None, politica=None) -> list[dict]:
        """O carrossel: o que ainda nao foi visto por esta pessoa."""
        vistos = self.vistos_de(pessoa)
        return [a for a in self.coletar(hoje=hoje, agora=agora, pessoa=pessoa, politica=politica)
                if a["id"] not in vistos]

    def todos(self, pessoa: str, *, tipo: str = "", periodo: str = "semana", hoje=None, agora=None,
              politica=None) -> list[dict]:
        """A aba Todos: vistos e nao vistos, no periodo e no tipo pedidos."""
        dias = PERIODOS.get(periodo, PERIODOS["semana"])
        vistos = self.vistos_de(pessoa)
        saida = []
        for a in self.coletar(hoje=hoje, agora=agora, horizonte=dias, pessoa=pessoa, politica=politica):
            if tipo and a["tipo"] != tipo:
                continue
            a["visto"] = a["id"] in vistos
            a["visto_em"] = vistos.get(a["id"], "")
            saida.append(a)
        return saida

    # ------------------------------------------------------------ os vistos

    def vistos_de(self, pessoa: str) -> dict[str, str]:
        return {l["aviso_id"]: l["visto_em"] for l in self.base.buscar(
            "SELECT aviso_id, visto_em FROM avisos_vistos WHERE pessoa = ?", (pessoa,))}

    def visto(self, aviso_id: str, pessoa: str = "local") -> bool:
        return self.base.um("SELECT 1 AS s FROM avisos_vistos WHERE aviso_id = ? AND pessoa = ?",
                            (aviso_id, pessoa)) is not None

    def marcar(self, aviso_id: str, pessoa: str, *, nome: str = "", de_onde: str = "local", hoje=None, agora=None,
               politica=None) -> dict:
        """
        Marca como visto e guarda a copia do que o aviso dizia. So um aviso
        que existe agora (para esta pessoa) se marca: id inventado nao entra
        no historico. Marcar de novo so atualiza a hora.
        """
        _, momento = self._relogio(hoje, agora)
        aviso = next((a for a in self.coletar(hoje=hoje, agora=agora, horizonte=PERIODOS["mes"], pessoa=pessoa,
                                              politica=politica) if a["id"] == aviso_id), None)
        if aviso is None:
            raise LookupError("esse aviso não está mais na lista — talvez já tenha sido resolvido")
        quando = momento.isoformat(timespec="seconds")
        self.base.escrever(
            "INSERT INTO avisos_vistos (aviso_id, pessoa, pessoa_nome, visto_em, de_onde, tipo, titulo, quando, origem) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(aviso_id, pessoa) DO UPDATE SET "
            "visto_em = excluded.visto_em, de_onde = excluded.de_onde, pessoa_nome = excluded.pessoa_nome",
            (aviso_id, pessoa, nome, quando, "remoto" if de_onde == "remoto" else "local", aviso["tipo"],
             aviso["titulo"], aviso["quando"], aviso["origem"]))
        return {**aviso, "visto": True, "visto_em": quando}

    def desmarcar(self, aviso_id: str, pessoa: str) -> bool:
        """Apaga a linha: o aviso volta ao carrossel de quem desmarcou."""
        # Base.escrever devolve o lastrowid da conexao quando ha um, e num
        # DELETE ele e o do ultimo INSERT: a conferencia vem antes.
        if not self.visto(aviso_id, pessoa):
            return False
        self.base.escrever("DELETE FROM avisos_vistos WHERE aviso_id = ? AND pessoa = ?", (aviso_id, pessoa))
        return True

    def historico(self, pessoa: str, *, titular: bool = False, limite: int = 300) -> list[dict]:
        """
        O que foi marcado como visto, do mais novo para o mais antigo. Cada
        pessoa ve os proprios; o titular ve tambem os da equipe - e so
        desmarca os dele (o carrossel de cada um e de cada um).
        """
        if titular:
            linhas = self.base.buscar("SELECT * FROM avisos_vistos ORDER BY visto_em DESC, id DESC LIMIT ?", (limite,))
        else:
            linhas = self.base.buscar("SELECT * FROM avisos_vistos WHERE pessoa = ? ORDER BY visto_em DESC, id DESC "
                                      "LIMIT ?", (pessoa, limite))
        for l in linhas:
            l["meu"] = l["pessoa"] == pessoa
            l["tipo_rotulo"] = TIPOS.get(l["tipo"], {}).get("rotulo", l["tipo"])
            l["icone"] = TIPOS.get(l["tipo"], {}).get("icone", "notifications")
        return linhas


def tipos_para_tela() -> list[dict]:
    return [{"id": k, "rotulo": v["rotulo"], "icone": v["icone"]} for k, v in TIPOS.items()]

