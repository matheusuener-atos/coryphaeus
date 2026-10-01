"""
As rotas do emissor de NFS-e (src/nfse/).

A configuração fiscal, o certificado da nota e o município são só da janela
do escritório (src/acesso/politicas.py): de fora não se configura tributo,
não se instala certificado e não se consulta o Sistema Nacional em nome do
escritório.
"""

from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from nfse import tabelas
from nfse.cliente import CertificadoInvalido, NaoChegou, ProducaoBloqueada, SemResposta
from nfse.servico import Emissor


class Ligar(BaseModel):
    ligado: bool = False


class Configuracao(BaseModel):
    dados: dict = {}


class NovaNota(BaseModel):
    origem: str = "manual"
    dados: dict = {}


class EditarNota(BaseModel):
    dados: dict = {}
    gravar_no_cadastro: bool = True


class Motivo(BaseModel):
    motivo: str = ""
    texto: str = ""


class Mes(BaseModel):
    mes: str = ""


class Recorrencia(BaseModel):
    id: int | None = None
    servico_id: int | None = None
    cadastro_id: int | None = None
    dia: int = 0
    valor: str = ""
    descricao: str = ""


class Pedir(BaseModel):
    confirmou_producao: bool = False


class Liberar(BaseModel):
    confirmo: bool = False


class Por(BaseModel):
    por: str = ""


class Senha(BaseModel):
    senha: str = ""
    guardar: bool = False


def _erro(exc: Exception, status: int = 400):
    raise HTTPException(status_code=status, detail=str(exc)) from exc


def montar(estado, app, dados_dir) -> None:
    import os

    estado.nfse = Emissor(estado.base, estado.prefs, Path(dados_dir))
    # N4: depois de emitida, Acervo, registro, e-mail proposto, aviso e auditoria.
    from nfse import fluxo

    estado.nfse.envio.ao_emitir.append(lambda nota: fluxo.depois_de_emitir(estado, nota))
    central = getattr(estado, "central_avisos", None)
    if central is not None:
        central.estado_nfse = estado
    estado.nfse.estado_app = estado
    # O mapa do programa diz a verdade sobre a emissão no estado de agora (N9).
    import programa

    programa.CONDICOES["nfse:emite"] = lambda: estado.nfse.pode_emitir()[0]
    # A fila de envio (N3): retoma ao abrir o que ficou no meio e tenta de novo
    # com espera crescente. O teste desliga para controlar cada passo.
    if not os.environ.get("PAULUS_NFSE_SEM_FILA"):
        estado.nfse.envio.ligar_fila()

    @app.get("/api/nfse")
    def nfse_estado() -> dict:
        return estado.nfse.para_tela()

    @app.post("/api/nfse/ligar")
    def nfse_ligar(payload: Ligar) -> dict:
        estado.nfse.ligar(payload.ligado)
        return estado.nfse.para_tela()

    @app.post("/api/nfse/prestador")
    def nfse_prestador(payload: Configuracao) -> dict:
        try:
            estado.nfse.prestador.gravar(payload.dados, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return estado.nfse.para_tela()

    @app.post("/api/nfse/certificado")
    async def nfse_certificado(arquivo: UploadFile = File(...), senha: str = Form(""),
                               guardar: str = Form("")) -> dict:
        conteudo = await arquivo.read()
        if not conteudo or len(conteudo) > 64 * 1024:
            raise HTTPException(status_code=400, detail="o arquivo não parece um certificado A1 (.pfx)")
        try:
            estado.nfse.instalar_certificado(arquivo.filename or "certificado.pfx", conteudo, senha,
                                             guardar in ("1", "true", "sim"))
        except ValueError as exc:
            _erro(exc)
        return estado.nfse.para_tela()

    @app.post("/api/nfse/certificado/senha")
    def nfse_certificado_senha(payload: Senha) -> dict:
        try:
            estado.nfse.desbloquear(payload.senha, payload.guardar)
        except ValueError as exc:
            _erro(exc)
        return estado.nfse.para_tela()

    @app.post("/api/nfse/certificado/remover")
    def nfse_certificado_remover() -> dict:
        estado.nfse.remover_certificado()
        return estado.nfse.para_tela()

    @app.post("/api/nfse/municipio/consultar")
    def nfse_municipio_consultar() -> dict:
        try:
            estado.nfse.consultar_municipio()
        except (ValueError, CertificadoInvalido, ProducaoBloqueada) as exc:
            _erro(exc)
        except (SemResposta, NaoChegou) as exc:
            _erro(exc, 502)
        return estado.nfse.para_tela()

    @app.get("/api/nfse/municipios")
    def nfse_municipios(q: str = "", uf: str = "") -> dict:
        return {"itens": tabelas.buscar_municipios(q, uf, limite=12)}

    @app.get("/api/nfse/tabelas")
    def nfse_tabelas() -> dict:
        return {"tabelas": tabelas.versoes()}

    @app.post("/api/nfse/tabelas/importar")
    async def nfse_tabelas_importar(arquivo: UploadFile = File(...)) -> dict:
        import tempfile

        nome = Path(arquivo.filename or "").name
        if not nome.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="importe a planilha oficial (.xlsx) do portal da NFS-e")
        conteudo = await arquivo.read()
        with tempfile.TemporaryDirectory(prefix="paulus-nfse-") as pasta:
            alvo = Path(pasta) / nome
            alvo.write_bytes(conteudo)
            try:
                gravadas = tabelas.importar(alvo, estado.nfse.pasta / "tabelas")
            except ValueError as exc:
                _erro(exc)
            except Exception as exc:  # noqa: BLE001 - planilha corrompida
                _erro(ValueError(f"não consegui ler a planilha: {exc}"))
        return {"importadas": gravadas, "tabelas": tabelas.versoes()}

    # ------------------------------------------------------------ notas (N2)

    def _nota_para_tela(nota: dict) -> dict:
        nota = dict(nota)
        nota["passos"] = estado.nfse.notas.passos(nota["id"])
        nota["eventos"] = estado.nfse.eventos.da_nota(nota["id"])
        if nota["estado"] == "emitida":
            nota["prazo_cancelamento"] = estado.nfse.eventos.prazo_de_cancelamento(nota)
            nota["motivos_cancelamento"] = tabelas.dominio("motivo_cancelamento")
            nota["motivos_substituicao"] = tabelas.dominio("motivo_substituicao")
        if nota.get("substitui_id"):
            o = estado.nfse.notas.obter(nota["substitui_id"])
            nota["substitui"] = {"id": o["id"], "numero_nfse": o["numero_nfse"], "chave": o["chave"]} if o else None
        if nota.get("substituida_por_id"):
            o = estado.nfse.notas.obter(nota["substituida_por_id"])
            nota["substituida_por"] = {"id": o["id"], "numero_nfse": o["numero_nfse"], "estado": o["estado"]} if o else None
        return nota

    @app.get("/api/nfse/notas")
    def nfse_notas(estados: str = "", mes: str = "") -> dict:
        lista = [e for e in estados.split(",") if e] or None
        return {"notas": estado.nfse.notas.listar(lista, mes)}

    @app.post("/api/nfse/notas")
    def nfse_nota_criar(payload: NovaNota) -> dict:
        try:
            nota = estado.nfse.notas.criar(dict(payload.dados), payload.origem, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    @app.get("/api/nfse/notas/{id_}")
    def nfse_nota(id_: int) -> dict:
        nota = estado.nfse.notas.obter(id_)
        if not nota:
            raise HTTPException(status_code=404, detail="nota não encontrada")
        return _nota_para_tela(nota)

    @app.post("/api/nfse/notas/{id_}")
    def nfse_nota_editar(id_: int, payload: EditarNota) -> dict:
        try:
            nota = estado.nfse.notas.atualizar(id_, dict(payload.dados), quem="titular",
                                               gravar_no_cadastro=payload.gravar_no_cadastro)
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    @app.get("/api/nfse/notas/{id_}/dps")
    def nfse_nota_dps(id_: int) -> dict:
        nota = estado.nfse.notas.obter(id_)
        if not nota:
            raise HTTPException(status_code=404, detail="nota não encontrada")
        try:
            xml, ident = estado.nfse.notas.montar_xml(nota)
        except (ValueError, KeyError) as exc:
            _erro(ValueError(f"não consegui montar a DPS: {exc}"))
        return {"id_dps": ident, "xml": xml.decode("utf-8"), "previa": not nota.get("numero")}

    @app.post("/api/nfse/notas/{id_}/descartar")
    def nfse_nota_descartar(id_: int) -> dict:
        try:
            nota = estado.nfse.notas.descartar(id_, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    # ------------------------------------------------------- envio (N3)

    @app.post("/api/nfse/notas/{id_}/consultar")
    def nfse_nota_consultar(id_: int) -> dict:
        """"Atualizar situação": pergunta ao Sistema Nacional pela DPS desta nota."""
        nota = estado.nfse.notas.obter(id_)
        if not nota:
            raise HTTPException(status_code=404, detail="nota não encontrada")
        if not nota.get("id_dps"):
            raise HTTPException(status_code=400, detail="a nota ainda não foi assinada nem enviada")
        try:
            nota = estado.nfse.envio.consultar(id_, quem="titular", reenviar_se_nao_existe=False)
        except (ValueError, CertificadoInvalido, ProducaoBloqueada) as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    @app.get("/api/nfse/fila")
    def nfse_fila() -> dict:
        return {"notas": estado.nfse.envio.pendentes()}

    @app.post("/api/nfse/contrato/conferir")
    def nfse_contrato_conferir() -> dict:
        """Confere no Swagger oficial (com o certificado) os nomes que o envio usa."""
        try:
            return estado.nfse.conferir_contrato()
        except (CertificadoInvalido, ProducaoBloqueada) as exc:
            _erro(exc)
        except (SemResposta, NaoChegou) as exc:
            _erro(exc, 502)

    # ------------------------------------------------------- o fluxo (N4)

    @app.get("/api/nfse/disponivel")
    def nfse_disponivel() -> dict:
        """O que as portas (Financeiro, Serviço) precisam para mostrar "Emitir nota"."""
        pode, motivos = estado.nfse.pode_emitir()
        return {"ligado": estado.nfse.ligado, "pode_emitir": pode, "motivos": motivos,
                "ambiente": estado.nfse.ambiente}

    @app.post("/api/nfse/notas/{id_}/pedir-aprovacao")
    def nfse_nota_pedir_aprovacao(id_: int, payload: Pedir | None = None) -> dict:
        from nfse import fluxo

        try:
            nota = fluxo.pedir_aprovacao(estado, id_, quem="titular",
                                         confirmou_producao=bool(payload and payload.confirmou_producao))
        except fluxo.PrecisaConfirmar as exc:
            # 409: a tela mostra a frase e pede o sim de novo (N8).
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    @app.post("/api/nfse/notas/{id_}/enviar")
    def nfse_nota_enviar(id_: int) -> dict:
        """
        Para a nota JÁ APROVADA que não saiu (a senha do certificado não estava
        à mão quando a aprovação veio de fora, ou a fila parou): manda agora,
        consultando antes se já houve tentativa. Não emite nada sem aprovação.
        """
        from nfse.notas import APROVADA, ASSINADA, AGUARDANDO_CONFIRMACAO, NA_FILA

        nota = estado.nfse.notas.obter(id_)
        if not nota:
            raise HTTPException(status_code=404, detail="nota não encontrada")
        if nota["estado"] not in (APROVADA, ASSINADA, NA_FILA, AGUARDANDO_CONFIRMACAO):
            raise HTTPException(status_code=400, detail=f"a nota está “{nota['estado_rotulo']}”: só se manda a aprovada")
        try:
            nota = estado.nfse.envio.emitir(id_, quem="titular")
        except (ValueError, CertificadoInvalido, ProducaoBloqueada) as exc:
            _erro(exc)
        return _nota_para_tela(nota)

    # ------------------------------------- consultar, cancelar, substituir (N5)

    @app.get("/api/nfse/notas/{id_}/danfse")
    def nfse_nota_danfse(id_: int):
        from fastapi.responses import Response

        nota = estado.nfse.notas.obter(id_)
        if not nota or not nota.get("xml_nfse"):
            raise HTTPException(status_code=404, detail="a nota ainda não foi emitida")
        pdf = estado.nfse.danfse_para(nota)
        if not pdf:
            raise HTTPException(status_code=404, detail="não achei o XML da nota emitida")
        nome = f"DANFSe {nota['numero_nfse']}.pdf"
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{nome}"'})

    @app.post("/api/nfse/notas/{id_}/cancelar")
    def nfse_nota_cancelar(id_: int, payload: Motivo) -> dict:
        """Pede o cancelamento (vai para Aprovações; fora do prazo, explica)."""
        try:
            estado.nfse.eventos.pedir_cancelamento(estado, id_, payload.motivo, payload.texto, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(estado.nfse.notas.obter(id_))

    @app.post("/api/nfse/notas/{id_}/substituir")
    def nfse_nota_substituir(id_: int, payload: Motivo) -> dict:
        """Cria a nota substituta (rascunho, com o grupo subst); sai por Aprovações."""
        try:
            nova = estado.nfse.eventos.criar_substituta(id_, payload.motivo, payload.texto, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return _nota_para_tela(nova)

    @app.post("/api/nfse/notas/{id_}/situacao")
    def nfse_nota_situacao(id_: int) -> dict:
        """"Atualizar situação": os eventos da nota no Sistema Nacional."""
        if not estado.nfse.notas.obter(id_):
            raise HTTPException(status_code=404, detail="nota não encontrada")
        try:
            nota = estado.nfse.eventos.atualizar_situacao(id_, quem="titular")
        except (ValueError, CertificadoInvalido, ProducaoBloqueada) as exc:
            _erro(exc)
        except (SemResposta, NaoChegou) as exc:
            _erro(exc, 502)
        return _nota_para_tela(nota)

    # ------------------------------------------------- o contador (N6)

    def _mes(mes: str) -> str:
        import re
        from datetime import date

        mes = (mes or "").strip() or date.today().isoformat()[:7]
        if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", mes):
            raise HTTPException(status_code=400, detail="mês inválido: use AAAA-MM")
        return mes

    @app.get("/api/nfse/contador")
    def nfse_contador(mes: str = "") -> dict:
        mes = _mes(mes)
        return {"relatorio": estado.nfse.contador.relatorio(mes), "achados": estado.nfse.contador.conferir(mes)}

    def _exportar(mes: str) -> dict:
        destino = Path(estado.pasta) / "Notas fiscais" / "Contador"
        feito = estado.nfse.contador.exportar(mes, destino)
        if hasattr(estado, "recarregar_em_segundo_plano"):
            estado.recarregar_em_segundo_plano()
        return feito

    @app.post("/api/nfse/contador/exportar")
    def nfse_contador_exportar(payload: Mes) -> dict:
        feito = _exportar(_mes(payload.mes))
        return {"caminho": feito["caminho"], "arquivos": feito["arquivos"]}

    @app.post("/api/nfse/contador/enviar")
    def nfse_contador_enviar(payload: Mes) -> dict:
        """O .zip do mês ao contador, por e-mail, depois do sim em Aprovações."""
        mes = _mes(payload.mes)
        prest = estado.nfse.prestador.atual()["dados"]
        para = (prest.get("contador") or {}).get("email") or ""
        if not para:
            raise HTTPException(status_code=400, detail="falta o e-mail do contador em Configurações › Nota fiscal")
        conta = estado.contas.em_uso if hasattr(estado, "contas") else None
        if conta is None:
            raise HTTPException(status_code=400, detail="não há conta de e-mail no PAULUS para enviar")
        feito = _exportar(mes)
        rel = feito["relatorio"]
        assunto = f"NFS-e de {mes[5:7]}/{mes[:4]} — {prest.get('razao_social') or ''}".strip(" —")
        nome = prest["contador"].get("nome") or ""
        corpo = (f"Olá{(' ' + nome) if nome else ''},\n\n"
                 f"Seguem as notas fiscais de serviço de {mes[5:7]}/{mes[:4]}: {rel['contagem'].get('emitida', 0)} emitida(s), "
                 f"{rel['contagem'].get('cancelada', 0)} cancelada(s), {rel['contagem'].get('substituida', 0)} substituída(s). "
                 "No arquivo vão os XMLs, a planilha-resumo e um leia-me.\n\nAtenciosamente,\n" + (prest.get("razao_social") or ""))
        pedido = estado.fila.pedir(f"Mandar as NFS-e de {mes} ao contador ({para})", "email",
                                   resumo=f"Para {para}, com o arquivo {Path(feito['caminho']).name} ({feito['arquivos']} XMLs)",
                                   etiquetas=["não dá para desfazer", "com anexo"], acao="correio.enviar",
                                   dados={"conta_id": conta.id, "para": para, "cc": "", "cco": "", "assunto": assunto,
                                          "corpo": corpo, "corpo_html": "", "anexos": [feito["caminho"]], "responder_a": ""},
                                   reversivel=False, pedido_por="PAULUS (nota fiscal)")
        return {"pedido": pedido.id, "caminho": feito["caminho"]}

    # ------------------------------------------------- recorrência (N7)

    @app.get("/api/nfse/recorrencias")
    def nfse_recorrencias() -> dict:
        return {"recorrencias": estado.nfse.recorrencias.listar()}

    @app.post("/api/nfse/recorrencias")
    def nfse_recorrencia_salvar(payload: Recorrencia) -> dict:
        try:
            r = estado.nfse.recorrencias.salvar(payload.model_dump(), quem="titular")
        except ValueError as exc:
            _erro(exc)
        return {"recorrencia": r, "recorrencias": estado.nfse.recorrencias.listar()}

    @app.post("/api/nfse/recorrencias/{id_}/desligar")
    def nfse_recorrencia_desligar(id_: int) -> dict:
        estado.nfse.recorrencias.desligar(id_)
        return {"recorrencias": estado.nfse.recorrencias.listar()}

    # ------------------------------------------------- produção (N8)

    @app.get("/api/nfse/producao")
    def nfse_producao() -> dict:
        return estado.nfse.producao.checklist()

    @app.post("/api/nfse/producao/revisado")
    def nfse_producao_revisado(payload: Por) -> dict:
        try:
            estado.nfse.prestador.marcar_revisado(payload.por, quem="titular")
        except ValueError as exc:
            _erro(exc)
        return estado.nfse.producao.checklist()

    @app.post("/api/nfse/producao/testes-conferidos")
    def nfse_producao_testes(payload: Por) -> dict:
        try:
            return estado.nfse.producao.marcar_testes_conferidos(payload.por)
        except ValueError as exc:
            _erro(exc)

    @app.post("/api/nfse/producao/liberar")
    def nfse_producao_liberar(payload: Liberar) -> dict:
        from nfse import fluxo

        try:
            ch = estado.nfse.producao.liberar("titular (janela do escritório)", payload.confirmo)
        except ValueError as exc:
            _erro(exc)
        fluxo.auditar(estado, "liberou a PRODUÇÃO da NFS-e (checklist: " +
                      ", ".join(i["titulo"] for i in ch["itens"] if i["ok"]) + ")")
        return ch

    @app.post("/api/nfse/producao/voltar")
    def nfse_producao_voltar() -> dict:
        from nfse import fluxo

        ch = estado.nfse.producao.voltar("titular (janela do escritório)")
        fluxo.auditar(estado, "voltou a NFS-e para a produção restrita")
        return ch
