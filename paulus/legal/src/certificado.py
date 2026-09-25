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

import segredos

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
    valido_ate: str = ""            # data, para mostrar na tela
    vence_em: str = ""              # instante exato, em UTC, para decidir
    icp_brasil: bool = False
    arquivo: str = ""
    erro: str = ""

    # O vencimento é um instante, não um dia. Comparar a data em UTC com o
    # "hoje" do relógio local dava certificado vencido como válido durante as
    # três horas em que o Brasil ainda está na véspera de Greenwich — e
    # "pode_assinar" ia junto, deixando assinar com e-CPF fora da validade.
    @property
    def _fim(self) -> datetime | None:
        if not self.vence_em:
            return None
        try:
            return datetime.fromisoformat(self.vence_em)
        except ValueError:
            return None

    @property
    def vencido(self) -> bool:
        fim = self._fim
        return bool(fim and fim < datetime.now(timezone.utc))

    @property
    def dias_restantes(self) -> int | None:
        fim = self._fim
        if not fim:
            return None
        return (fim - datetime.now(timezone.utc)).days

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
    return _de_x509(cert, alvo.name)


def _de_x509(cert, arquivo: str) -> Certificado:
    """O que o certificado e, lido do proprio X.509 - vale para o .pfx e para
    o que esta instalado no Windows."""
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
        vence_em=cert.not_valid_after_utc.astimezone(timezone.utc).isoformat(),
        icp_brasil=e_icp(emissor),
        arquivo=arquivo,
    )


def ler_do_windows(der_base64: str) -> Certificado:
    """
    O certificado instalado no Windows, lido da parte publica guardada no
    cofre. Nao precisa de senha: titular, emissor e validade sao publicos -
    so a chave e secreta, e ela nunca sai do Windows.
    """
    import base64

    from cryptography import x509

    try:
        cert = x509.load_der_x509_certificate(base64.b64decode(der_base64))
    except Exception as exc:
        return Certificado(erro=f"não consegui ler o certificado do Windows: {exc}")
    certificado = _de_x509(cert, "instalado no Windows")
    # "A1" e o tipo do arquivo .pfx; o daqui a tela chama de "instalado no Windows".
    certificado.tipo = certificado.tipo.replace(" A1", "")
    return certificado


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
    # Certificado instalado no Windows: so a parte publica (impressao, o
    # certificado e a cadeia). A chave nunca sai do Windows. Com ele, a senha
    # de uso e uma senha do PAULUS - aqui fica so a marca dela.
    "windows": {},
    "senha_paulus": "",
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


def dpapi_disponivel() -> bool:
    return segredos.disponivel()


def _marca_da_senha(senha: str) -> str:
    """A senha do PAULUS vira uma marca (PBKDF2 com sal): da para conferir,
    nao da para ler de volta."""
    import hashlib
    import os

    sal = os.urandom(16)
    voltas = 200_000
    marca = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, voltas)
    return f"pbkdf2${voltas}${sal.hex()}${marca.hex()}"


def _confere_senha(senha: str, marca: str) -> bool:
    import hashlib
    import hmac

    try:
        _, voltas, sal, esperado = (marca or "").split("$")
        calculado = hashlib.pbkdf2_hmac("sha256", (senha or "").encode("utf-8"), bytes.fromhex(sal), int(voltas))
    except ValueError:
        return False
    return hmac.compare_digest(calculado.hex(), esperado)


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
        # Um certificado por vez: o .pfx novo tira o do Windows.
        self.dados["windows"] = {}
        self.dados["senha_paulus"] = ""
        self.salvar()
        return destino

    @property
    def windows(self) -> dict:
        return self.dados.get("windows") or {}

    @property
    def origem(self) -> str:
        """De onde vem o certificado: "windows" (instalado) ou "arquivo" (.pfx)."""
        return "windows" if self.windows.get("impressao") else "arquivo"

    @property
    def instalado(self) -> bool:
        return bool(self.windows.get("impressao")) or bool(self.arquivo and self.arquivo.exists())

    def usar_windows(self, publico: dict, senha: str) -> None:
        """
        Passa a usar um certificado do Windows. Guarda so a parte publica e a
        marca da senha do PAULUS; a copia de .pfx que havia sai, porque o
        programa trabalha com um certificado por vez.
        """
        alvo = self.arquivo
        if alvo and alvo.exists() and alvo.parent.resolve() == self.pasta.resolve():
            try:
                alvo.unlink()
            except OSError:
                pass
        self.dados.update(
            arquivo="", senha_protegida="", guardar_senha=False,
            windows={k: publico.get(k) for k in ("impressao", "der", "cadeia")},
            senha_paulus=_marca_da_senha(senha),
        )
        self.esquecer_senha()
        self.lembrar(senha)
        self.salvar()

    def abrir(self, senha: str) -> Certificado:
        """
        Confere a senha e devolve o certificado. No .pfx, a senha abre o
        arquivo; no do Windows, e a senha do PAULUS, conferida pela marca.
        """
        if self.origem == "windows":
            if not _confere_senha(senha, self.dados.get("senha_paulus") or ""):
                return Certificado(erro="senha do PAULUS incorreta")
            return ler_do_windows(self.windows.get("der") or "")
        alvo = self.arquivo
        if not alvo or not alvo.exists():
            return Certificado(erro="nenhum certificado instalado")
        return ler(alvo, senha)

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
        self.dados["windows"] = {}
        self.dados["senha_paulus"] = ""
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
        guardada = segredos.proteger(senha)
        if not guardada:
            return False
        self.dados["senha_protegida"] = guardada
        self.dados["guardar_senha"] = True
        self.salvar()
        return True

    def senha_agora(self) -> str:
        """A senha em uso: a da memoria, a guardada, ou nenhuma."""
        import time

        if self._senha_viva and time.time() < self._vale_ate:
            return self._senha_viva
        self.esquecer_senha()

        return segredos.revelar(self.dados.get("senha_protegida") or "")

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
        """Le o certificado com a senha disponivel. Sem senha, nao adivinha.
        O do Windows se le sem senha: a parte publica esta no cofre."""
        if self.origem == "windows":
            return ler_do_windows(self.windows.get("der") or "")
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
        do_windows = self.origem == "windows"
        return {
            "instalado": self.instalado,
            "origem": self.origem,
            "certificado": cert.to_dict() if cert else None,
            "guardado_em": "Windows · a chave não sai de lá" if do_windows else (str(self.arquivo) if self.arquivo else ""),
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


def _powershell(script: str, extra: dict | None = None, timeout: int = 30):
    """
    Roda o Windows PowerShell 5.1 com o ambiente limpo de PSModulePath.

    Aberto a partir de um terminal do PowerShell 7, o programa herda o
    PSModulePath dele, e o 5.1 passa a procurar modulos no lugar errado: a
    unidade Cert: e o Export-PfxCertificate somem, e a lista de certificados
    saia vazia sem erro nenhum na tela. Os modulos tambem sao importados a
    mao, por garantia.
    """
    import os
    import subprocess

    ambiente = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    ambiente.update(extra or {})
    cabeca = "Import-Module Microsoft.PowerShell.Security, PKI -ErrorAction SilentlyContinue\n"
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cabeca + script],
        capture_output=True, text=True, timeout=timeout, env=ambiente,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


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
        "Select-Object Subject,Issuer,HasPrivateKey,Thumbprint,"
        "@{N='Ate';E={$_.NotAfter.ToString('yyyy-MM-dd')}} | ConvertTo-Json -Compress"
    )
    try:
        saida = _powershell(script, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []

    try:
        bruto = json.loads(saida.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(bruto, dict):
        bruto = [bruto]

    from datetime import date

    hoje = date.today().isoformat()
    achados = []
    for item in bruto:
        if not isinstance(item, dict):
            continue
        emissor = str(item.get("Issuer", ""))
        valido_ate = str(item.get("Ate", ""))[:10]
        achados.append({
            "titular": _nome_curto(str(item.get("Subject", ""))),
            "emissor": _nome_curto(emissor),
            "valido_ate": valido_ate,
            "vencido": bool(valido_ate) and valido_ate < hoje,
            "tem_chave": bool(item.get("HasPrivateKey")),
            "icp_brasil": e_icp(emissor),
            "impressao": str(item.get("Thumbprint", "")).upper(),
        })
    # Os de pessoa (ICP-Brasil) primeiro; os tecnicos do sistema depois.
    achados.sort(key=lambda c: (not c["icp_brasil"], c["vencido"], c["titular"].lower()))
    return achados


def _impressao_valida(impressao: str) -> str:
    """A impressao digital (SHA-1 em hexa) - o unico jeito de apontar um
    certificado do Windows. Qualquer outra coisa nao entra no PowerShell."""
    import re

    impressao = (impressao or "").strip().upper()
    return impressao if re.fullmatch(r"[0-9A-F]{40}", impressao) else ""


def publico_do_windows(impressao: str) -> dict:
    """
    A parte publica de um certificado instalado: o proprio certificado e a
    cadeia ate a raiz, em DER/base64. E o que o cofre guarda - nada secreto.

    A cadeia vai junto na assinatura: sem ela, quem confere o PDF depois
    nao sabe ligar o certificado a AC que o emitiu.
    """
    import json
    import subprocess

    alvo = _impressao_valida(impressao)
    if not alvo:
        return {"erro": "certificado desconhecido"}
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$c = Get-Item -LiteralPath ('Cert:\\CurrentUser\\My\\' + $env:PAULUS_IMPRESSAO)\n"
        "$cadeia = New-Object System.Security.Cryptography.X509Certificates.X509Chain\n"
        "$cadeia.ChainPolicy.RevocationMode = 'NoCheck'\n"
        "$null = $cadeia.Build($c)\n"
        "@{ der = [Convert]::ToBase64String($c.RawData); chave = $c.HasPrivateKey;"
        " cadeia = @($cadeia.ChainElements | Select-Object -Skip 1 | ForEach-Object { [Convert]::ToBase64String($_.Certificate.RawData) }) }"
        " | ConvertTo-Json -Compress\n"
    )
    try:
        feito = _powershell(script, {"PAULUS_IMPRESSAO": alvo}, timeout=30)
        dados = json.loads(feito.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"erro": "não consegui ler o certificado no Windows"}
    if not dados.get("der"):
        return {"erro": "esse certificado não está mais no Windows"}
    if not dados.get("chave"):
        return {"erro": "este certificado não tem a chave para assinar - só a parte pública"}
    cadeia = dados.get("cadeia") or []
    return {"impressao": alvo, "der": dados["der"], "cadeia": cadeia if isinstance(cadeia, list) else [cadeia]}


# Os nomes que o .NET usa para cada resumo que a pyHanko pode pedir.
_HASH_DOTNET = {"sha1": "SHA1", "sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512"}


def assinar_com_windows(impressao: str, dados: bytes, resumo: str = "sha256") -> bytes:
    """
    Assina `dados` com a chave que esta no Windows - sem tirar a chave de la.

    E o que torna possivel usar um e-CPF instalado como NAO EXPORTAVEL: essa
    trava impede exportar a chave, nao usa-la. Se o certificado foi
    instalado com protecao forte, e AQUI que o Windows abre a janela dele
    pedindo a senha. Os bytes vao por variavel de ambiente, em base64.
    """
    import base64
    import subprocess

    alvo = _impressao_valida(impressao)
    nome = _HASH_DOTNET.get((resumo or "").lower())
    if not alvo:
        raise RuntimeError("certificado desconhecido")
    if not nome:
        raise RuntimeError(f"resumo {resumo} não suportado")
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$c = Get-Item -LiteralPath ('Cert:\\CurrentUser\\My\\' + $env:PAULUS_IMPRESSAO)\n"
        "$k = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($c)\n"
        "if (-not $k) { Write-Error 'SEM_CHAVE_RSA' }\n"
        "$b = [Convert]::FromBase64String($env:PAULUS_DADOS)\n"
        "$s = $k.SignData($b, [System.Security.Cryptography.HashAlgorithmName]::" + nome + ","
        " [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)\n"
        "[Convert]::ToBase64String($s)\n"
    )
    try:
        # Sem prazo curto: a janela de senha do Windows espera a pessoa.
        feito = _powershell(script, {"PAULUS_IMPRESSAO": alvo, "PAULUS_DADOS": base64.b64encode(dados).decode("ascii")}, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("não consegui falar com o Windows para assinar") from exc
    erro = (feito.stderr or "").lower()
    if feito.returncode != 0 or not (feito.stdout or "").strip():
        if "sem_chave_rsa" in erro:
            raise RuntimeError("a chave deste certificado não é RSA - ainda não sei assinar com ela")
        if "cancel" in erro or "0x800704c7" in erro or "8010006e" in erro:
            raise RuntimeError("a senha do certificado não foi confirmada na janela do Windows")
        raise RuntimeError("o Windows não assinou com este certificado")
    return base64.b64decode(feito.stdout.strip())


def abrir_janela_do_windows() -> bool:
    """A janela "Certificados" do proprio Windows, para quem prefere ver la."""
    import subprocess
    import sys

    if sys.platform != "win32":
        return False
    try:
        subprocess.Popen(["rundll32.exe", "cryptui.dll,CryptUIStartCertMgr"])
        return True
    except OSError:
        return False
