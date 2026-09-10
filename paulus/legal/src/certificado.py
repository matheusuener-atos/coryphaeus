"""
PAULUS - Certificado digital.

Le um certificado A1 (arquivo .pfx ou .p12) e conta o que ele e: titular,
documento, emissor, validade, e - a parte que mais importa - se ele encadeia
na ICP-Brasil ou nao.

Essa ultima resposta nao e detalhe tecnico. Assinatura com certificado
autoassinado e criptograficamente valida e juridicamente nada. Um programa que
mostra "assinado" nos dois casos, sem distinguir, engana quem depende dele - e
quem depende deste aqui e um escritorio de advocacia.

O arquivo e a senha ficam nesta maquina. O A3 (token) precisa de driver
PKCS#11 por fabricante e fica para depois; o programa diz isso em vez de
fingir que suporta.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Autoridades da ICP-Brasil aparecem com estes pedacos no nome do emissor.
# Nao substitui validacao de cadeia de verdade: e um indicio, e a tela diz isso.
MARCAS_ICP = (
    "icp-brasil",
    "autoridade certificadora raiz brasileira",
    "receita federal do brasil",
    "ac oab",
)

# As ACs credenciadas pela Receita se chamam "AC <fabricante> RFB". Manter uma
# lista de fabricantes deixaria de fora quem nao estivesse nela - o certificado
# de um cliente real desta maquina ("AC CONSULTI RFB") escapou assim.
RE_AC_RFB = re.compile(r"\bac\b.*\brfb\b", re.IGNORECASE)

RE_CPF = re.compile(r"\b\d{11}\b")
RE_CNPJ = re.compile(r"\b\d{14}\b")


@dataclass
class Certificado:
    titular: str = ""
    documento: str = ""            # CPF ou CNPJ, formatado
    tipo: str = ""                 # "e-CPF" | "e-CNPJ" | "certificado"
    emissor: str = ""
    serie: str = ""
    valido_de: str = ""
    valido_ate: str = ""
    icp_brasil: bool = False
    arquivo: str = ""
    erro: str = ""

    @property
    def vencido(self) -> bool:
        if not self.valido_ate:
            return False
        return self.valido_ate < datetime.now().strftime("%Y-%m-%d")

    @property
    def dias_restantes(self) -> int | None:
        if not self.valido_ate:
            return None
        try:
            fim = datetime.strptime(self.valido_ate, "%Y-%m-%d").date()
        except ValueError:
            return None
        return (fim - datetime.now().date()).days

    @property
    def situacao(self) -> str:
        if self.erro:
            return "com problema"
        if self.vencido:
            return "vencido"
        dias = self.dias_restantes
        if dias is not None and dias <= 30:
            return "vence em breve"
        return "válido"

    @property
    def pode_assinar(self) -> bool:
        return not self.erro and not self.vencido

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados.update(
            vencido=self.vencido,
            dias_restantes=self.dias_restantes,
            situacao=self.situacao,
            pode_assinar=self.pode_assinar,
        )
        return dados


def _formatar_documento(bruto: str) -> tuple[str, str]:
    """Devolve (documento formatado, tipo) a partir dos digitos achados."""
    if m := RE_CNPJ.search(bruto):
        d = m.group()
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}", "e-CNPJ"
    if m := RE_CPF.search(bruto):
        d = m.group()
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}", "e-CPF"
    return "", "certificado"


def _nome_legivel(nome) -> str:
    """
    O nome do titular no padrao ICP-Brasil vem como "FULANO:12345678900".

    O numero fica no proprio campo, entao o que vai para a tela e so o nome.
    """
    partes = []
    for atributo in nome:
        if atributo.rfc4514_attribute_name in ("CN", "commonName"):
            partes.append(str(atributo.value))
    texto = partes[0] if partes else nome.rfc4514_string()
    return texto.split(":")[0].strip()


def ler(caminho: Path | str, senha: str) -> Certificado:
    """
    Abre o .pfx e conta o que ele e.

    Senha errada e o caso comum, nao excecao: devolve um Certificado com erro
    em portugues, para a tela dizer o que houve.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12

    alvo = Path(caminho)
    if not alvo.exists():
        return Certificado(erro="não achei o arquivo do certificado")

    try:
        dados = alvo.read_bytes()
    except OSError as exc:
        return Certificado(erro=f"não consegui ler o arquivo: {exc}")

    try:
        _, cert, _ = pkcs12.load_key_and_certificates(dados, (senha or "").encode())
    except ValueError:
        return Certificado(erro="senha do certificado incorreta, ou arquivo inválido")
    except Exception as exc:
        return Certificado(erro=f"não consegui abrir o certificado: {exc}")

    if cert is None:
        return Certificado(erro="o arquivo não traz certificado")

    emissor = cert.issuer.rfc4514_string()
    assunto_texto = cert.subject.rfc4514_string()

    # O CPF/CNPJ da ICP-Brasil vive numa extensao (otherName), nao no nome.
    # Procurar nos dois lugares cobre os dois formatos de emissao.
    bruto = re.sub(r"\D", "", assunto_texto)
    try:
        from cryptography.x509.oid import ExtensionOID

        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        bruto += "".join(re.sub(r"\D", "", str(v)) for v in san.value)
    except Exception:
        pass

    documento, tipo = _formatar_documento(bruto)

    return Certificado(
        titular=_nome_legivel(cert.subject),
        documento=documento,
        tipo=f"{tipo} A1" if tipo != "certificado" else "certificado A1",
        emissor=_nome_curto(emissor),
        serie=_serie(cert.serial_number),
        valido_de=_data(cert.not_valid_before_utc),
        valido_ate=_data(cert.not_valid_after_utc),
        icp_brasil=e_icp(emissor),
        arquivo=alvo.name,
    )


def e_icp(emissor: str) -> bool:
    """
    Se o emissor parece uma autoridade da ICP-Brasil.

    E indicio, nao prova: prova exigiria validar a cadeia inteira contra as
    raizes oficiais. Por isso a tela nunca diz "tem validade juridica" - diz
    quem emitiu e deixa a conclusao com quem assina.
    """
    baixo = (emissor or "").lower()
    return any(m in baixo for m in MARCAS_ICP) or bool(RE_AC_RFB.search(baixo))


def _nome_curto(rfc: str) -> str:
    """O CN do emissor basta na tela; o resto do DN e ruido."""
    for parte in rfc.split(","):
        if parte.strip().upper().startswith("CN="):
            return parte.split("=", 1)[1].split(":")[0].strip()
    return rfc


def _serie(numero: int) -> str:
    hexa = f"{numero:X}"
    if len(hexa) % 2:
        hexa = "0" + hexa
    return " ".join(hexa[i:i + 2] for i in range(0, len(hexa), 2))[:29]


def _data(quando: datetime) -> str:
    return quando.astimezone(timezone.utc).strftime("%Y-%m-%d")


def gerar_de_teste(destino: Path, senha: str, titular: str = "CERTIFICADO DE TESTE") -> Path:
    """
    Cria um .pfx autoassinado, so para desenvolvimento.

    Existe para dar para testar o caminho da assinatura sem um e-CPF de
    verdade na mao. O certificado que sai daqui NAO e ICP-Brasil, e a tela
    mostra isso - assinar com ele produz um PDF criptograficamente assinado e
    juridicamente sem valor.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import timedelta

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"{titular}:00000000000"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PAULUS - CERTIFICADO DE TESTE"),
    ])

    agora = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(chave, hashes.SHA256())
    )

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(
        pkcs12.serialize_key_and_certificates(
            name=b"paulus-teste",
            key=chave,
            cert=cert,
            cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(senha.encode()),
        )
    )
    return destino


# ---------------------------------------------------------------- o cofre


PADRAO_SELO = {
    "texto": "Assinado digitalmente por {nome}",
    "mostrar_data": True,
    "mostrar_codigo": True,
    "mostrar_cpf": True,
    "imagem": "",            # logotipo, arquivo dentro da pasta do cofre
    "desenho": "",           # assinatura desenhada, idem
    "posicao": "rodape_direita",
}

PADRAO_COFRE = {
    "arquivo": "",
    "guardar_senha": False,
    "senha_protegida": "",   # DPAPI + base64; nunca a senha em texto
    "minutos": 15,
    "pedir_confirmacao": True,
    "mostrar_documento": False,
    "lote_sem_confirmar": False,
    "selo": dict(PADRAO_SELO),
}

POSICOES = {
    "rodape_direita": "Rodapé à direita",
    "rodape_esquerda": "Rodapé à esquerda",
    "rodape_centro": "Rodapé centralizado",
    "topo_direita": "Topo à direita",
}


def _dpapi(dados: bytes, proteger: bool) -> bytes | None:
    """
    Protege ou revela bytes usando a DPAPI do Windows.

    Guardar a senha do certificado em texto num JSON seria entregar a chave
    privada a qualquer programa que leia a pasta. A DPAPI amarra o segredo a
    esta conta do Windows: quem copiar o arquivo para outra maquina leva bytes
    inuteis. Nao e cofre inviolavel - e a diferenca entre um arquivo que
    qualquer um le e um que so esta conta le.

    Fora do Windows devolve None, e quem chama nao guarda senha nenhuma.
    """
    import sys

    if sys.platform != "win32":
        return None

    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer_ = ctypes.create_string_buffer(dados, len(dados))
    entrada = BLOB(len(dados), ctypes.cast(buffer_, ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32 = ctypes.windll.crypt32

    if proteger:
        ok = crypt32.CryptProtectData(
            ctypes.byref(entrada), "PAULUS", None, None, None, 0, ctypes.byref(saida)
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)
        )
    if not ok:
        return None

    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def dpapi_disponivel() -> bool:
    return _dpapi(b"teste", True) is not None


class Cofre:
    """
    Onde mora a referencia ao certificado, o selo e - se a pessoa quiser - a
    senha protegida.

    A senha em memoria tem prazo. O wireframe oferece "depois de digitar, ela
    vale por 15 minutos": passado o prazo, o programa pergunta de novo, porque
    senha de certificado que fica valida para sempre e certificado sem senha.
    """

    def __init__(self, caminho: Path, pasta: Path) -> None:
        import copy
        import json

        self.caminho = Path(caminho)
        self.pasta = Path(pasta)
        self.dados = copy.deepcopy(PADRAO_COFRE)
        self._senha_viva = ""
        self._vale_ate = 0.0

        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                if isinstance(bruto, dict):
                    self.dados.update({k: v for k, v in bruto.items() if k in PADRAO_COFRE})
                    selo = dict(PADRAO_SELO)
                    selo.update(bruto.get("selo") or {})
                    self.dados["selo"] = selo
            except (json.JSONDecodeError, OSError):
                pass

    def salvar(self) -> None:
        import json

        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    # ------------------------------------------------------------ o arquivo

    @property
    def arquivo(self) -> Path | None:
        bruto = self.dados.get("arquivo") or ""
        return Path(bruto) if bruto else None

    def guardar_arquivo(self, nome: str, conteudo: bytes) -> Path:
        """Copia o .pfx para a pasta do programa e passa a apontar para ela."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        sufixo = Path(nome).suffix.lower()
        if sufixo not in (".pfx", ".p12"):
            sufixo = ".pfx"
        destino = self.pasta / f"certificado{sufixo}"
        destino.write_bytes(conteudo)
        self.dados["arquivo"] = str(destino)
        self.salvar()
        return destino

    def remover(self) -> None:
        """Tira o certificado do programa: apaga a copia e a senha guardada."""
        alvo = self.arquivo
        if alvo and alvo.exists() and alvo.parent.resolve() == self.pasta.resolve():
            try:
                alvo.unlink()
            except OSError:
                pass
        self.dados["arquivo"] = ""
        self.dados["senha_protegida"] = ""
        self.dados["guardar_senha"] = False
        self.esquecer_senha()
        self.salvar()

    # -------------------------------------------------------------- a senha

    def lembrar(self, senha: str) -> None:
        """Guarda a senha na memoria do processo, pelo prazo escolhido."""
        import time

        self._senha_viva = senha
        self._vale_ate = time.time() + max(int(self.dados.get("minutos") or 0), 0) * 60

    def esquecer_senha(self) -> None:
        self._senha_viva = ""
        self._vale_ate = 0.0

    @property
    def minutos_restantes(self) -> int:
        import time

        if not self._senha_viva:
            return 0
        return max(int((self._vale_ate - time.time()) // 60), 0)

    def proteger(self, senha: str) -> bool:
        """Guarda a senha em disco, protegida pela conta do Windows."""
        import base64

        blob = _dpapi(senha.encode("utf-8"), True)
        if blob is None:
            return False
        self.dados["senha_protegida"] = base64.b64encode(blob).decode("ascii")
        self.dados["guardar_senha"] = True
        self.salvar()
        return True

    def senha_agora(self) -> str:
        """A senha em uso: a da memoria, a guardada, ou nenhuma."""
        import base64
        import time

        if self._senha_viva and time.time() < self._vale_ate:
            return self._senha_viva
        self.esquecer_senha()

        guardada = self.dados.get("senha_protegida") or ""
        if not guardada:
            return ""
        aberta = _dpapi(base64.b64decode(guardada), False)
        return aberta.decode("utf-8") if aberta else ""

    # ----------------------------------------------------------------- selo

    def gravar_selo(self, novo: dict) -> dict:
        selo = dict(self.dados.get("selo") or PADRAO_SELO)
        for chave in PADRAO_SELO:
            if chave in novo:
                selo[chave] = novo[chave]
        self.dados["selo"] = selo
        self.salvar()
        return selo

    def guardar_imagem(self, campo: str, conteudo: bytes) -> str:
        """Grava o PNG do logotipo ou do desenho da assinatura."""
        if campo not in ("imagem", "desenho"):
            raise ValueError("campo desconhecido")
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / f"{campo}.png"
        destino.write_bytes(conteudo)
        selo = dict(self.dados.get("selo") or PADRAO_SELO)
        selo[campo] = destino.name
        self.dados["selo"] = selo
        self.salvar()
        return destino.name

    def caminho_do_selo(self, campo: str) -> Path | None:
        nome = (self.dados.get("selo") or {}).get(campo) or ""
        if not nome:
            return None
        alvo = self.pasta / nome
        return alvo if alvo.exists() else None

    # -------------------------------------------------------------- leitura

    def certificado(self) -> Certificado | None:
        """Le o certificado com a senha disponivel. Sem senha, nao adivinha."""
        alvo = self.arquivo
        if not alvo or not alvo.exists():
            return None
        senha = self.senha_agora()
        if not senha:
            return Certificado(
                arquivo=alvo.name,
                erro="preciso da senha do certificado para ler os dados dele",
            )
        return ler(alvo, senha)

    def para_tela(self) -> dict:
        cert = self.certificado()
        return {
            "instalado": bool(self.arquivo and self.arquivo.exists()),
            "certificado": cert.to_dict() if cert else None,
            "guardado_em": str(self.arquivo) if self.arquivo else "",
            "guardar_senha": bool(self.dados.get("guardar_senha")),
            "tem_senha_guardada": bool(self.dados.get("senha_protegida")),
            "senha_na_memoria": bool(self._senha_viva and self.minutos_restantes),
            "minutos_restantes": self.minutos_restantes,
            "minutos": self.dados.get("minutos", 15),
            "pedir_confirmacao": bool(self.dados.get("pedir_confirmacao", True)),
            "mostrar_documento": bool(self.dados.get("mostrar_documento")),
            "lote_sem_confirmar": bool(self.dados.get("lote_sem_confirmar")),
            "selo": self.dados.get("selo") or dict(PADRAO_SELO),
            "posicoes": [{"valor": k, "rotulo": v} for k, v in POSICOES.items()],
            "pode_guardar_senha": dpapi_disponivel(),
        }


def listar_windows() -> list[dict]:
    """
    Certificados de pessoa fisica ja instalados no Windows.

    So para mostrar. Assinar com eles exigiria falar com a CryptoAPI, e a
    chave de um e-CPF instalado costuma vir marcada como nao exportavel - por
    isso a tela lista o que existe e explica que aqui se usa o arquivo .pfx,
    em vez de oferecer um botao que nao assina.
    """
    import json
    import subprocess
    import sys

    if sys.platform != "win32":
        return []

    script = (
        "Get-ChildItem Cert:\\CurrentUser\\My | "
        # NotAfter cru sai como /Date(1809...) no JSON do PowerShell: pedir o
        # texto ja formatado evita ter que decifrar isso do lado de ca.
        "Select-Object Subject,Issuer,HasPrivateKey,"
        "@{N='Ate';E={$_.NotAfter.ToString('yyyy-MM-dd')}} | ConvertTo-Json -Compress"
    )
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return []

    try:
        bruto = json.loads(saida.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(bruto, dict):
        bruto = [bruto]

    achados = []
    for item in bruto:
        if not isinstance(item, dict):
            continue
        emissor = str(item.get("Issuer", ""))
        achados.append({
            "titular": _nome_curto(str(item.get("Subject", ""))),
            "emissor": _nome_curto(emissor),
            "valido_ate": str(item.get("Ate", ""))[:10],
            "tem_chave": bool(item.get("HasPrivateKey")),
            "icp_brasil": e_icp(emissor),
        })
    return achados
