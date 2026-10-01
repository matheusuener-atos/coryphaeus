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


class Senha(BaseModel):
    senha: str = ""
    guardar: bool = False


def _erro(exc: Exception, status: int = 400):
    raise HTTPException(status_code=status, detail=str(exc)) from exc


def montar(estado, app, dados_dir) -> None:
    import os

    estado.nfse = Emissor(estado.base, estado.prefs, Path(dados_dir))
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
