"""
PAULUS - Servicos.

A pasta de trabalho de um assunto: nome proprio, cliente, o que esta sendo
feito, o andamento em etapas, quem cuida, os arquivos ligados ao Acervo, os
prazos e a trilha do que aconteceu (docs/ui/03-telas-desktop.md, A15).

Nada aqui e inventado: os arquivos sao vinculos a documentos que existem no
Acervo, os prazos sao as tarefas e os compromissos do cliente, a equipe sao
fichas de Cadastros. O servico so junta - e guarda a trilha, que e o que
ninguem lembra depois.

Duas ligacoes com o resto do programa:

- A pasta. Cada servico tem uma pasta no Acervo, Servicos/<nome>. O que se
  adiciona ao servico e copiado para la (o original fica onde estava), e o
  que alguem poe na pasta pelo Windows entra no servico sozinho. Renomear o
  servico renomeia a pasta.
- A agenda. Etapa com data e tarefa com prazo: e criada em Tarefas, aparece
  na Agenda, e concluir de um lado conclui do outro. A etapa guarda o id da
  tarefa; a tarefa guarda o servico e quem e o responsavel - o que vai
  deixar cada pessoa da equipe ver a propria agenda.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

STATUS = {
    "andamento": "Em andamento",
    "aguardando": "Aguardando cliente",
    "revisao": "Em revisão",
    # Parado por decisao do escritorio ou do cliente, sem data para voltar.
    "suspenso": "Suspenso",
    "concluido": "Concluído",
}

CAMPOS = ("nome", "cadastro_id", "descricao", "status")

# A pasta de todos os servicos, dentro do Acervo.
PASTA_DOS_SERVICOS = "Serviços"

_PROIBIDOS_NO_NOME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVADOS_DO_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def nome_de_pasta(nome: str) -> str:
    """
    O nome do servico como nome de pasta do Windows: sem os caracteres que o
    Windows recusa, sem ponto nem espaco no fim, e nao um nome reservado.
    """
    limpo = " ".join(_PROIBIDOS_NO_NOME.sub(" ", str(nome or "")).split())[:80].rstrip(". ")
    if not limpo or limpo.upper() in _RESERVADOS_DO_WINDOWS:
        limpo = ("Serviço " + limpo).strip()
    return limpo


def remover_pasta_vazia(pasta: Path | None) -> bool:
    """A pasta de um servico apagado so sai do disco se nao tiver nada dentro."""
    try:
        if pasta and pasta.is_dir() and not any(pasta.iterdir()):
            pasta.rmdir()
            return True
    except OSError:
        pass
    return False


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(texto: str, padrao):
    try:
        valor = json.loads(texto or "")
        return valor if isinstance(valor, type(padrao)) else padrao
    except (json.JSONDecodeError, TypeError):
        return padrao


class Servicos:
    def __init__(self, base, quem=None, acervo=None) -> None:
        self.base = base
        # Quem assina a trilha quando a acao nao diz: o nome da pessoa desta maquina.
        self._quem = quem or (lambda: "você")
        # Onde fica o Acervo (pode mudar nas preferencias): a pasta dos
        # servicos mora dentro dele. Sem Acervo, servico sem pasta.
        self._acervo = acervo or (lambda: None)

    # ------------------------------------------------------------------ pasta

    def raiz_das_pastas(self) -> Path | None:
        acervo = self._acervo()
        return Path(acervo) / PASTA_DOS_SERVICOS if acervo else None

    def _pasta_livre(self, desejado: str, id_: int) -> str:
        """
        O nome de pasta que ninguem usa: nem outro servico, nem uma pasta com
        coisa dentro que ja esta no disco. "Renovação", "Renovação (2)"...
        """
        raiz = self.raiz_das_pastas()
        usados = {(l["pasta"] or "").casefold() for l in self.base.buscar(
            "SELECT pasta FROM servicos WHERE id != ? AND pasta != ''", (id_,))}
        n = 1
        while True:
            candidato = desejado if n == 1 else f"{desejado} ({n})"
            no_disco = raiz / candidato if raiz else None
            ocupada = bool(no_disco and no_disco.is_dir() and any(no_disco.iterdir()))
            if candidato.casefold() not in usados and not ocupada:
                return candidato
            n += 1

    def pasta_de(self, id_: int, criar: bool = True) -> Path | None:
        """
        A pasta do servico no disco. Servico antigo, de antes das pastas,
        ganha a sua aqui, na primeira vez que alguem precisa dela.
        """
        raiz = self.raiz_das_pastas()
        linha = self.base.um("SELECT nome, pasta FROM servicos WHERE id = ?", (id_,))
        if not raiz or not linha:
            return None
        nome = linha["pasta"] or ""
        if not nome:
            nome = self._pasta_livre(nome_de_pasta(linha["nome"]), id_)
            self.base.escrever("UPDATE servicos SET pasta = ? WHERE id = ?", (nome, id_))
        pasta = raiz / nome
        if criar:
            try:
                pasta.mkdir(parents=True, exist_ok=True)
            except OSError:
                return None
        return pasta

    def _renomear_pasta(self, id_: int, nome_do_servico: str) -> bool:
        """Renomeia a pasta junto com o servico. Devolve se algo mudou no disco."""
        raiz = self.raiz_das_pastas()
        linha = self.base.um("SELECT pasta FROM servicos WHERE id = ?", (id_,))
        if not raiz or not linha or not linha["pasta"]:
            return False
        velho = linha["pasta"]
        novo = self._pasta_livre(nome_de_pasta(nome_do_servico), id_)
        if novo == velho:
            return False
        origem, destino = raiz / velho, raiz / novo
        try:
            if origem.is_dir():
                if destino.is_dir():
                    destino.rmdir()  # vazia: _pasta_livre nao escolhe pasta com coisa dentro
                origem.rename(destino)
        except OSError:
            # Arquivo aberto em outro programa segura a pasta: fica o nome velho.
            return False
        self.base.escrever("UPDATE servicos SET pasta = ? WHERE id = ?", (novo, id_))
        return origem.is_dir() or destino.is_dir()

    def desligados(self, id_: int) -> set[str]:
        """
        Os arquivos que alguem tirou da pasta de proposito. Um arquivo que
        continua na pasta do disco nao volta sozinho para o servico depois
        de desligado - so se for adicionado de novo.
        """
        linha = self.base.um("SELECT trilha FROM servicos WHERE id = ?", (id_,))
        ultimo: dict[str, str] = {}
        for e in reversed(_json(linha["trilha"] if linha else "[]", [])):
            sha1 = (e.get("dados") or {}).get("sha1")
            if sha1 and e.get("tipo") in ("arquivo", "arquivo_desligado"):
                ultimo[sha1] = e["tipo"]
        return {sha1 for sha1, tipo in ultimo.items() if tipo == "arquivo_desligado"}

    # ---------------------------------------------------------------- leitura

    def listar(self, filtro: str = "", termo: str = "") -> list[dict]:
        sql = ("SELECT s.*, c.nome AS cliente_nome, c.documento AS cliente_documento "
               "FROM servicos s LEFT JOIN cadastros c ON c.id = s.cadastro_id WHERE 1=1")
        parametros: list = []
        if filtro == "andamento":
            sql += " AND s.status != 'concluido'"
        elif filtro == "concluidos":
            sql += " AND s.status = 'concluido'"
        if termo:
            sql += " AND (s.nome LIKE ? OR s.descricao LIKE ? OR c.nome LIKE ?)"
            like = f"%{termo}%"
            parametros += [like, like, like]
        sql += " ORDER BY (s.status = 'concluido'), s.atualizado_em DESC"
        itens = self.base.buscar(sql, tuple(parametros))
        for s in itens:
            self._enfeitar(s)
        return itens

    def contagem(self) -> dict:
        linhas = self.base.buscar("SELECT status, COUNT(*) AS n FROM servicos GROUP BY status")
        por = {l["status"]: int(l["n"]) for l in linhas}
        return {
            "andamento": por.get("andamento", 0) + por.get("revisao", 0),
            "aguardando": por.get("aguardando", 0),
            "concluidos": por.get("concluido", 0),
            "total": sum(por.values()),
        }

    def obter(self, id_: int) -> dict | None:
        # O que mudou em Tarefas (concluida, prazo trocado) volta para as
        # etapas antes de a pasta ser lida.
        self.puxar_das_tarefas(id_)
        s = self.base.um(
            "SELECT s.*, c.nome AS cliente_nome, c.documento AS cliente_documento "
            "FROM servicos s LEFT JOIN cadastros c ON c.id = s.cadastro_id WHERE s.id = ?",
            (id_,),
        )
        if not s:
            return None
        self._enfeitar(s)
        s["arquivos"] = self.arquivos_de(id_)
        s["anotacoes"] = _json(s.pop("anotacoes_json"), [])
        s["trilha"] = _json(s.pop("trilha_json"), [])
        s["prazos"] = self._prazos_de(s)
        return s

    def _enfeitar(self, s: dict) -> None:
        etapas = _json(s.get("etapas", "[]"), [])
        feitas = sum(1 for e in etapas if e.get("feita"))
        responsaveis = {p["id"]: p for p in self._equipe(sorted({e["responsavel_id"] for e in etapas if e.get("responsavel_id")}))}
        for e in etapas:
            p = responsaveis.get(e.get("responsavel_id"))
            e["responsavel"] = {"id": p["id"], "nome": p["nome"]} if p else None
        s["etapas"] = etapas
        s["etapas_feitas"] = feitas
        s["progresso"] = round(feitas * 100 / len(etapas)) if etapas else (100 if s.get("status") == "concluido" else 0)
        s["status_rotulo"] = STATUS.get(s.get("status", ""), s.get("status", ""))
        equipe_ids = _json(s.get("equipe", "[]"), [])
        s["equipe"] = self._equipe(equipe_ids)
        # anotacoes e trilha ficam como json na lista (sao pesados); o obter abre
        s["anotacoes_json"] = s.get("anotacoes", "[]")
        s["trilha_json"] = s.get("trilha", "[]")
        s["anotacoes"] = len(_json(s["anotacoes_json"], []))
        s["trilha"] = len(_json(s["trilha_json"], []))
        s["arquivos_quantos"] = self.base.contar("vinculos", "tipo = 'servico' AND alvo_id = ?", (s["id"],))
        hoje = date.today().isoformat()
        # Os prazos do cliente e os da propria pasta (etapas com data e o que
        # foi agendado por ela). Sem cliente, -1 nao casa com cadastro nenhum.
        cliente = s.get("cadastro_id") or -1
        prazos = self.base.um(
            "SELECT COUNT(*) AS n, MIN(prazo) AS proximo FROM tarefas "
            "WHERE concluida = 0 AND prazo != '' AND (cadastro_id = ? OR servico_id = ?)", (cliente, s["id"]))
        comp = self.base.um(
            "SELECT titulo, data, hora FROM compromissos WHERE (cadastro_id = ? OR servico_id = ?) AND data >= ? "
            "ORDER BY data, hora LIMIT 1", (cliente, s["id"], hoje))
        s["prazos_quantos"] = int(prazos["n"]) if prazos else 0
        s["proximo_prazo"] = (prazos or {}).get("proximo") or ""
        s["proximo_compromisso"] = dict(comp) if comp else None

    def _equipe(self, ids: list) -> list[dict]:
        if not ids:
            return []
        marcas = ",".join("?" for _ in ids)
        linhas = self.base.buscar(
            f"SELECT id, nome, tipo, observacao FROM cadastros WHERE id IN ({marcas})", tuple(ids))
        por = {l["id"]: l for l in linhas}
        return [por[i] for i in ids if i in por]

    def _prazos_de(self, s: dict) -> list[dict]:
        """
        O que tem data em volta da pasta: as tarefas do cliente (menos as que
        sao etapas desta pasta - essas ja estao nas etapas) e os compromissos
        do cliente ou marcados pela pasta.
        """
        hoje = date.today().isoformat()
        cliente = s.get("cadastro_id") or -1
        tarefas = self.base.buscar(
            "SELECT id, titulo, prazo FROM tarefas WHERE concluida = 0 AND prazo != '' AND cadastro_id = ? "
            "AND COALESCE(servico_id, 0) != ? ORDER BY prazo LIMIT 8", (cliente, s["id"]))
        compromissos = self.base.buscar(
            "SELECT id, titulo, data, hora, tipo FROM compromissos WHERE (cadastro_id = ? OR servico_id = ?) AND data >= ? "
            "ORDER BY data, hora LIMIT 8", (cliente, s["id"], hoje))
        itens = [{"quando": t["prazo"], "hora": "", "titulo": t["titulo"], "detalhe": "prazo da tarefa", "origem": "tarefa", "id": t["id"]}
                 for t in tarefas]
        itens += [{"quando": c["data"], "hora": c["hora"], "titulo": c["titulo"], "detalhe": c["tipo"], "origem": "compromisso", "id": c["id"]}
                  for c in compromissos]
        return sorted(itens, key=lambda x: (x["quando"], x["hora"]))[:8]

    def arquivos_de(self, id_: int) -> list[dict]:
        return self.base.buscar(
            "SELECT sha1, nome, criado_em FROM vinculos WHERE tipo = 'servico' AND alvo_id = ? ORDER BY criado_em DESC",
            (id_,),
        )

    # ---------------------------------------------------------------- escrita

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        nome = " ".join(str(dados.get("nome", "")).split())
        if not nome:
            raise ValueError("o serviço precisa de um nome")
        status = dados.get("status") if dados.get("status") in STATUS else "andamento"
        cadastro_id = dados.get("cadastro_id") or None
        descricao = str(dados.get("descricao", "")).strip()
        equipe = [int(x) for x in (dados.get("equipe") or []) if str(x).isdigit()]

        if id_:
            atual = self.base.um("SELECT nome, cadastro_id, descricao, status, equipe FROM servicos WHERE id = ?", (id_,))
            if not atual:
                raise ValueError("serviço não encontrado")
            self.base.escrever(
                "UPDATE servicos SET nome = ?, cadastro_id = ?, descricao = ?, status = ?, equipe = ?, "
                "atualizado_em = ?, concluido_em = CASE WHEN ? = 'concluido' AND concluido_em = '' THEN ? ELSE concluido_em END "
                "WHERE id = ?",
                (nome, cadastro_id, descricao, status, json.dumps(equipe), _agora(), status, _agora(), id_),
            )
            if atual["nome"] != nome:
                self._renomear_pasta(id_, nome)
            if (atual["nome"], atual["cadastro_id"]) != (nome, cadastro_id):
                # As tarefas das etapas levam o nome do servico e o cliente.
                self._empurrar_para_tarefas(id_, self._etapas(id_))
            # A trilha diz o que mudou, nao so que algo mudou.
            if (atual["nome"], atual["cadastro_id"], atual["descricao"]) != (nome, cadastro_id, descricao):
                self.trilha(id_, "Dados do serviço atualizados", tipo="dados")
            if _json(atual["equipe"], []) != equipe:
                self.trilha(id_, "Equipe: " + (", ".join(p["nome"] for p in self._equipe(equipe)) or "ninguém"), tipo="equipe")
            if atual["status"] != status:
                self.trilha(id_, "Status: " + STATUS[status], tipo="status", dados={"status": status})
            return id_

        novo = self.base.escrever(
            "INSERT INTO servicos (nome, cadastro_id, descricao, status, etapas, equipe, anotacoes, trilha, "
            "criado_em, atualizado_em) VALUES (?, ?, ?, ?, '[]', ?, '[]', '[]', ?, ?)",
            (nome, cadastro_id, descricao, status, json.dumps(equipe), _agora(), _agora()),
        )
        self.trilha(novo, "Serviço aberto", tipo="criado")
        self.pasta_de(novo, criar=True)
        return novo

    def apagar(self, id_: int) -> bool:
        self.base.escrever("DELETE FROM vinculos WHERE tipo = 'servico' AND alvo_id = ?", (id_,))
        return self.base.escrever("DELETE FROM servicos WHERE id = ?", (id_,)) > 0

    def mudar_status(self, id_: int, status: str) -> None:
        if status not in STATUS:
            raise ValueError("status desconhecido")
        self.base.escrever(
            "UPDATE servicos SET status = ?, atualizado_em = ?, "
            "concluido_em = CASE WHEN ? = 'concluido' THEN ? ELSE '' END WHERE id = ?",
            (status, _agora(), status, _agora(), id_),
        )
        self.trilha(id_, "Status: " + STATUS[status], tipo="status", dados={"status": status})

    # etapas

    def _etapas(self, id_: int) -> list[dict]:
        linha = self.base.um("SELECT etapas FROM servicos WHERE id = ?", (id_,))
        if not linha:
            raise ValueError("serviço não encontrado")
        return _json(linha["etapas"], [])

    def _gravar_etapas(self, id_: int, etapas: list[dict]) -> None:
        self.base.escrever("UPDATE servicos SET etapas = ?, atualizado_em = ? WHERE id = ?",
                           (json.dumps(etapas, ensure_ascii=False), _agora(), id_))

    def _responsavel(self, valor) -> int | None:
        """Quem cuida da etapa: uma ficha de Cadastros que existe, ou ninguem."""
        if valor in (None, "", 0, "0"):
            return None
        try:
            id_ = int(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError("responsável inválido") from exc
        if not self.base.um("SELECT id FROM cadastros WHERE id = ?", (id_,)):
            raise ValueError("essa pessoa não está em Cadastros")
        return id_

    def etapa_adicionar(self, id_: int, titulo: str, quando: str = "", responsavel_id=None) -> list[dict]:
        titulo = " ".join(str(titulo or "").split())
        if not titulo:
            raise ValueError("a etapa precisa de um nome")
        quando = data_de_prazo(quando)
        responsavel_id = self._responsavel(responsavel_id)
        etapas = self._etapas(id_)
        etapas.append({"titulo": titulo, "feita": False, "quando": quando, "feita_em": "", "por": "",
                       "responsavel_id": responsavel_id})
        self._empurrar_para_tarefas(id_, etapas)
        self.trilha(id_, "Etapa adicionada: " + titulo, tipo="etapa", dados={"titulo": titulo, "quando": quando})
        return etapas

    def etapa_editar(self, id_: int, indice: int, dados: dict) -> list[dict]:
        """
        Trocar o prazo, o nome ou quem cuida de uma etapa. So o que veio em
        `dados` muda; a trilha diz o que foi.
        """
        etapas = self._etapas(id_)
        if indice < 0 or indice >= len(etapas):
            raise ValueError("etapa não encontrada")
        e = etapas[indice]
        mudancas: list[tuple[str, str, dict]] = []
        if "titulo" in dados:
            titulo = " ".join(str(dados["titulo"] or "").split())
            if not titulo:
                raise ValueError("a etapa precisa de um nome")
            if titulo != e["titulo"]:
                mudancas.append(("Etapa renomeada: " + titulo, "etapa_renomeada", {"titulo": titulo, "antes": e["titulo"]}))
                e["titulo"] = titulo
        if "quando" in dados:
            quando = data_de_prazo(dados["quando"])
            if quando != e.get("quando", ""):
                e["quando"] = quando
                mudancas.append((("Prazo da etapa: " + e["titulo"] + " até " + quando) if quando else ("Etapa sem prazo: " + e["titulo"]),
                                 "etapa_prazo", {"titulo": e["titulo"], "quando": quando}))
        if "responsavel_id" in dados:
            responsavel_id = self._responsavel(dados["responsavel_id"])
            if responsavel_id != e.get("responsavel_id"):
                e["responsavel_id"] = responsavel_id
                pessoa = self._equipe([responsavel_id])[0]["nome"] if responsavel_id else ""
                mudancas.append((("Etapa com " + pessoa + ": " + e["titulo"]) if pessoa else ("Etapa sem responsável: " + e["titulo"]),
                                 "etapa_responsavel", {"titulo": e["titulo"], "responsavel": pessoa}))
        if mudancas:
            self._empurrar_para_tarefas(id_, etapas)
            for texto, tipo, extra in mudancas:
                self.trilha(id_, texto, tipo=tipo, dados=extra)
        return etapas

    def etapa_alternar(self, id_: int, indice: int, quem: str = "") -> list[dict]:
        quem = quem or self._quem()
        etapas = self._etapas(id_)
        if indice < 0 or indice >= len(etapas):
            raise ValueError("etapa não encontrada")
        e = etapas[indice]
        e["feita"] = not e.get("feita")
        e["feita_em"] = _agora() if e["feita"] else ""
        e["por"] = quem if e["feita"] else ""
        self._empurrar_para_tarefas(id_, etapas)
        self.trilha(id_, ("Etapa concluída: " if e["feita"] else "Etapa reaberta: ") + e["titulo"], quem,
                    tipo="etapa_feita" if e["feita"] else "etapa_reaberta", dados={"titulo": e["titulo"]})
        return etapas

    def etapa_remover(self, id_: int, indice: int) -> list[dict]:
        etapas = self._etapas(id_)
        if indice < 0 or indice >= len(etapas):
            raise ValueError("etapa não encontrada")
        tirada = etapas.pop(indice)
        self._empurrar_para_tarefas(id_, etapas)
        self.trilha(id_, "Etapa removida: " + tirada.get("titulo", ""), tipo="etapa_removida",
                    dados={"titulo": tirada.get("titulo", "")})
        return etapas

    # etapas <-> tarefas

    def _empurrar_para_tarefas(self, id_: int, etapas: list[dict]) -> None:
        """
        Grava as etapas e deixa Tarefas igual a elas: etapa com data tem uma
        tarefa (nome, prazo, cliente, feita, responsavel; a lista e o nome do
        servico, que e o que a Agenda mostra ao lado do titulo). Etapa que
        perdeu a data ou saiu leva a tarefa junto.
        """
        s = self.base.um("SELECT nome, cadastro_id FROM servicos WHERE id = ?", (id_,))
        if not s:
            raise ValueError("serviço não encontrado")
        existentes = {t["id"] for t in self.base.buscar("SELECT id FROM tarefas WHERE servico_id = ?", (id_,))}
        usadas: set[int] = set()
        for e in etapas:
            e.pop("responsavel", None)
            tarefa_id = e.get("tarefa_id")
            if not e.get("quando"):
                e.pop("tarefa_id", None)
                continue
            valores = (e["titulo"], s["nome"], e["quando"], s["cadastro_id"], 1 if e.get("feita") else 0,
                       (e.get("feita_em") or "")[:10], e.get("responsavel_id"))
            if tarefa_id in existentes and tarefa_id not in usadas:
                self.base.escrever(
                    "UPDATE tarefas SET titulo = ?, lista = ?, prazo = ?, cadastro_id = ?, concluida = ?, "
                    "concluida_em = ?, responsavel_id = ? WHERE id = ?", valores + (tarefa_id,))
            else:
                tarefa_id = self.base.escrever(
                    "INSERT INTO tarefas (titulo, lista, prazo, cadastro_id, concluida, concluida_em, responsavel_id, "
                    "servico_id, anotacao, criada_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                    valores + (id_, "Etapa do serviço " + s["nome"]))
                e["tarefa_id"] = tarefa_id
            usadas.add(tarefa_id)
        for sobra in existentes - usadas:
            self.base.escrever("DELETE FROM vinculos WHERE tipo = 'tarefa' AND alvo_id = ?", (sobra,))
            self.base.escrever("DELETE FROM tarefas WHERE id = ?", (sobra,))
        self._gravar_etapas(id_, etapas)

    def puxar_das_tarefas(self, id_: int) -> None:
        """
        O caminho de volta: a tarefa concluida (ou reaberta, renomeada, com
        prazo trocado) em Tarefas muda a etapa. Tarefa que sumiu - apagada
        la, ou o servico voltou da lixeira sem ela - e criada de novo: quem
        manda na etapa e o servico.
        """
        linha = self.base.um("SELECT etapas FROM servicos WHERE id = ?", (id_,))
        if not linha:
            return
        etapas = _json(linha["etapas"], [])
        if not any(e.get("quando") or e.get("tarefa_id") for e in etapas):
            return
        tarefas = {t["id"]: t for t in self.base.buscar(
            "SELECT id, titulo, prazo, concluida, concluida_em, responsavel_id FROM tarefas WHERE servico_id = ?", (id_,))}
        antes = json.dumps(etapas, sort_keys=True)
        eventos: list[tuple[str, str, dict]] = []
        for e in etapas:
            t = tarefas.get(e.get("tarefa_id"))
            if not t:
                continue
            feita = bool(t["concluida"])
            if feita != bool(e.get("feita")):
                e["feita"] = feita
                e["feita_em"] = (t["concluida_em"] or _agora()) if feita else ""
                e["por"] = "em Tarefas" if feita else ""
                eventos.append((("Etapa concluída: " if feita else "Etapa reaberta: ") + t["titulo"],
                                "etapa_feita" if feita else "etapa_reaberta", {"titulo": t["titulo"]}))
            e["titulo"] = t["titulo"]
            e["quando"] = t["prazo"] or ""
            e["responsavel_id"] = t["responsavel_id"]
        sem_tarefa = any(e.get("quando") and e.get("tarefa_id") not in tarefas for e in etapas)
        if sem_tarefa or json.dumps(etapas, sort_keys=True) != antes:
            self._empurrar_para_tarefas(id_, etapas)
        for texto, tipo, dados in eventos:
            self.trilha(id_, texto, "Tarefas", tipo=tipo, dados=dados)

    # anotacoes, arquivos, trilha, resumo

    def anotar(self, id_: int, texto: str, quem: str = "") -> list[dict]:
        quem = quem or self._quem()
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("a anotação está vazia")
        linha = self.base.um("SELECT anotacoes FROM servicos WHERE id = ?", (id_,))
        if not linha:
            raise ValueError("serviço não encontrado")
        anotacoes = _json(linha["anotacoes"], [])
        anotacoes.insert(0, {"quem": quem, "quando": _agora(), "texto": texto})
        self.base.escrever("UPDATE servicos SET anotacoes = ?, atualizado_em = ? WHERE id = ?",
                           (json.dumps(anotacoes, ensure_ascii=False), _agora(), id_))
        self.trilha(id_, "Anotação: " + (texto[:60] + ("…" if len(texto) > 60 else "")), quem,
                    tipo="anotacao", dados={"texto": texto})
        return anotacoes

    def vincular(self, id_: int, sha1: str, nome: str, quem: str = "") -> None:
        self.base.escrever(
            "INSERT OR IGNORE INTO vinculos (tipo, alvo_id, sha1, nome, criado_em) "
            "VALUES ('servico', ?, ?, ?, datetime('now','localtime'))",
            (id_, sha1, nome),
        )
        self.trilha(id_, "Arquivo ligado: " + nome, quem, tipo="arquivo", dados={"sha1": sha1, "nome": nome})

    def desvincular(self, id_: int, sha1: str) -> None:
        linha = self.base.um("SELECT nome FROM vinculos WHERE tipo = 'servico' AND alvo_id = ? AND sha1 = ?", (id_, sha1))
        self.base.escrever("DELETE FROM vinculos WHERE tipo = 'servico' AND alvo_id = ? AND sha1 = ?", (id_, sha1))
        if linha:
            self.trilha(id_, "Arquivo desligado: " + linha["nome"], tipo="arquivo_desligado",
                        dados={"sha1": sha1, "nome": linha["nome"]})

    def trilha(self, id_: int, texto: str, quem: str = "", tipo: str = "", dados: dict | None = None) -> None:
        """
        Um evento na trilha. `tipo` e `dados` sao o que o historico da pasta
        desenha: o arquivo que entrou vira linha de documento, a etapa vira a
        marca de concluir, a conversa vira pergunta e resposta. Eventos antigos
        (so texto) continuam valendo - a tela os reconhece pelo comeco.
        """
        quem = quem or self._quem()
        linha = self.base.um("SELECT trilha FROM servicos WHERE id = ?", (id_,))
        if not linha:
            return
        eventos = _json(linha["trilha"], [])
        evento = {"quando": _agora(), "quem": quem, "texto": texto}
        if tipo:
            evento["tipo"] = tipo
        if dados:
            evento["dados"] = dados
        eventos.insert(0, evento)
        self.base.escrever("UPDATE servicos SET trilha = ? WHERE id = ?",
                           (json.dumps(eventos[:200], ensure_ascii=False), id_))

    def guardar_resumo(self, id_: int, texto: str) -> None:
        self.base.escrever("UPDATE servicos SET resumo = ?, resumo_em = ? WHERE id = ?",
                           (texto, _agora(), id_))
        self.trilha(id_, "Resumo escrito pelo assistente", "Assistente", tipo="resumo", dados={"texto": texto})

    def conversar(self, id_: int, pergunta: str, resposta: str, quem: str = "") -> None:
        """A pergunta sobre a pasta e a resposta do assistente entram no historico."""
        self.trilha(id_, "Pergunta: " + pergunta[:60], quem, tipo="conversa",
                    dados={"pergunta": pergunta, "resposta": resposta})

    def texto_para_resumo(self, s: dict) -> str:
        """O que o modelo recebe: so o que esta gravado no servico."""
        linhas = [f"Serviço: {s['nome']}"]
        if s.get("cliente_nome"):
            linhas.append(f"Cliente: {s['cliente_nome']}")
        if s.get("descricao"):
            linhas.append(f"Descrição: {s['descricao']}")
        linhas.append(f"Status: {s['status_rotulo']} ({s['progresso']}%)")
        for e in s.get("etapas", []):
            linhas.append(("[x] " if e.get("feita") else "[ ] ") + e["titulo"] + (f" (até {e['quando']})" if e.get("quando") else "")
                          + (f" - com {e['responsavel']['nome']}" if e.get("responsavel") else ""))
        for p in s.get("prazos", [])[:6]:
            linhas.append(f"Prazo {p['quando']}: {p['titulo']}")
        for a in s.get("anotacoes", [])[:6]:
            linhas.append(f"Anotação ({a['quem']}, {a['quando'][:10]}): {a['texto']}")
        for arq in s.get("arquivos", [])[:12]:
            linhas.append(f"Arquivo: {arq['nome']}")
        return "\n".join(linhas)

    def texto_para_conversa(self, s: dict) -> str:
        """O servico, e as ultimas perguntas feitas sobre ele - a conversa continua."""
        linhas = [self.texto_para_resumo(s)]
        linha = self.base.um("SELECT trilha FROM servicos WHERE id = ?", (s["id"],))
        conversas = [e for e in _json(linha["trilha"] if linha else "[]", []) if e.get("tipo") == "conversa"][:3]
        for e in reversed(conversas):
            d = e.get("dados") or {}
            linhas.append(f"Pergunta anterior: {d.get('pergunta', '')}\nResposta anterior: {d.get('resposta', '')}")
        return "\n\n".join(linhas)


# Quanto a frente e quanto para tras um prazo de etapa pode ir: cinco anos
# cobre qualquer servico, e barra o ano digitado errado (2062 ou 1926 no
# lugar de 2026).
ANOS_A_FRENTE = 5
ANOS_PARA_TRAS = 5


def data_de_prazo(quando: str, hoje: date | None = None) -> str:
    """
    A data de uma etapa, conferida: ISO valida, dentro de cinco anos para
    cada lado. Data que ja passou vale - a etapa registrada depois do fato e
    comum - e a tela a mostra como atrasada. Vazia continua vazia.
    """
    quando = str(quando or "").strip()[:10]
    if not quando:
        return ""
    try:
        dia = date.fromisoformat(quando)
    except ValueError as exc:
        raise ValueError("essa data não existe") from exc
    hoje = hoje or date.today()
    if dia < hoje - timedelta(days=365 * ANOS_PARA_TRAS + 1):
        raise ValueError(f"a data da etapa passa de {ANOS_PARA_TRAS} anos atrás — confira o ano")
    if dia > hoje + timedelta(days=365 * ANOS_A_FRENTE + 1):
        raise ValueError(f"a data da etapa passa de {ANOS_A_FRENTE} anos — confira o ano")
    return dia.isoformat()


INSTRUCAO_CONVERSA = """Você é assistente de um escritório de advocacia brasileiro. Abaixo está o
que foi gravado sobre um serviço (uma pasta de trabalho) e as últimas
perguntas feitas sobre ele. Responda à pergunta em português do Brasil, em
poucas frases, usando só o que está escrito. Não invente datas, valores,
nomes nem cláusulas. Se a resposta não estiver no que foi gravado, diga isso
e sugira o que registrar na pasta."""


INSTRUCAO_RESUMO = """Você é assistente de um escritório de advocacia brasileiro. Abaixo está o
que foi gravado sobre um serviço (uma pasta de trabalho): cliente, descrição,
etapas feitas e a fazer, prazos, anotações e arquivos. Escreva, em português
do Brasil, um resumo de no máximo dois parágrafos curtos dizendo onde o
serviço está e o que falta. Use só o que está escrito; não invente datas,
valores nem cláusulas. Se faltar informação, diga que falta."""
