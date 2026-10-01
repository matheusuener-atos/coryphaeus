"""
A Sefin Nacional de mentira, para os testes do envio (N3 em diante).

Reproduz as respostas documentadas da API (Manual dos Contribuintes; Anexo I,
RN de recepção): sucesso com a NFS-e; rejeição com a lista `erros`; E0014
para a DPS que já gerou nota; e as falhas de rede — tempo esgotado depois de
gerar, tempo esgotado antes de gerar, servidor fora (a conexão nem abre), erro
500 depois de gerar e "trava" (gera e não responde nunca, para o teste do
processo morto no meio do envio).

O estado (as notas geradas e quantas vezes cada DPS chegou) mora num
arquivo JSON, para dois processos verem a mesma Sefin. A NFS-e devolvida é
montada no leiaute oficial e assinada com um certificado "da Sefin" de teste.
"""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path

from lxml import etree

NS = "http://www.sped.fazenda.gov.br/nfse"
_trava = threading.Lock()


class SefinSimulada:
    def __init__(self, arquivo: Path, modos: list[str] | str = "sucesso", pfx_sefin: bytes | None = None,
                 senha_sefin: str = "sefin") -> None:
        self.arquivo = Path(arquivo)
        self.modos = [modos] if isinstance(modos, str) else list(modos)
        self.pfx_sefin, self.senha_sefin = pfx_sefin, senha_sefin
        self.pedidos: list[tuple[str, str]] = []
        if not self.arquivo.exists():
            self._gravar({"geradas": {}, "recebidas": {}, "eventos": {}, "numero": 0})

    # ------------------------------------------------------------ estado

    def _ler(self) -> dict:
        return json.loads(self.arquivo.read_text(encoding="utf-8"))

    def _gravar(self, e: dict) -> None:
        tmp = self.arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(e), encoding="utf-8")
        tmp.replace(self.arquivo)

    def geradas(self) -> dict:
        return self._ler()["geradas"]

    def recebidas(self, id_dps: str) -> int:
        return int(self._ler()["recebidas"].get(id_dps, 0))

    def modo(self) -> str:
        return self.modos.pop(0) if len(self.modos) > 1 else self.modos[0]

    # ------------------------------------------------------------ NFS-e

    def _montar_nfse(self, dps: etree._Element, numero: int) -> bytes:
        from nfse import assinatura

        inf_dps = dps.find(f"{{{NS}}}infDPS")
        t = lambda c: inf_dps.findtext(c, namespaces={"n": NS}) or ""  # noqa: E731
        cmun = t("n:cLocEmi")
        doc = t("n:prest/n:CNPJ") or t("n:prest/n:CPF").zfill(14)
        tipo = "2" if t("n:prest/n:CNPJ") else "1"
        amb = t("n:tpAmb")
        agora = datetime.now()
        chave = f"{cmun}2{tipo}{doc}{numero:013d}{agora:%y%m}{random.randint(0, 999999999):09d}0"
        nfse = etree.Element(f"{{{NS}}}NFSe", nsmap={None: NS})
        nfse.set("versao", "1.01")
        inf = etree.SubElement(nfse, f"{{{NS}}}infNFSe")
        inf.set("Id", "NFS" + chave)

        def sub(pai, nome, texto=None):
            el = etree.SubElement(pai, f"{{{NS}}}{nome}")
            if texto is not None:
                el.text = str(texto)
            return el

        sub(inf, "xLocEmi", "Goiânia")
        sub(inf, "xLocPrestacao", "Goiânia")
        sub(inf, "nNFSe", str(numero))
        sub(inf, "cLocIncid", t("n:serv/n:locPrest/n:cLocPrestacao") or cmun)
        sub(inf, "xLocIncid", "Goiânia")
        sub(inf, "xTribNac", "Advocacia")
        sub(inf, "verAplic", "SefinSimulada-1.0")
        sub(inf, "ambGer", "2")
        sub(inf, "tpEmis", "1")
        sub(inf, "procEmi", "1")
        sub(inf, "cStat", "100")
        sub(inf, "dhProc", agora.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00")
        sub(inf, "nDFSe", str(numero))
        emit = sub(inf, "emit")
        sub(emit, "CNPJ" if tipo == "2" else "CPF", doc if tipo == "2" else doc[-11:])
        sub(emit, "xNome", "ESCRITORIO DE TESTE")
        end = sub(emit, "enderNac")
        sub(end, "xLgr", "Rua do Escritório")
        sub(end, "nro", "1")
        sub(end, "xBairro", "Centro")
        sub(end, "cMun", cmun)
        sub(end, "UF", "GO")
        sub(end, "CEP", "74000000")
        v = sub(inf, "valores")
        vserv = t("n:valores/n:vServPrest/n:vServ")
        from nfse.dinheiro import centavos_do_xml as cx

        cent = cx(vserv)
        cdesc = cx(t("n:valores/n:vDescCondIncond/n:vDescIncond"))
        base = cent - cdesc
        iss = (base * 500 + 5000) // 10000
        ret = 0
        for c in ("n:valores/n:trib/n:tribFed/n:vRetIRRF", "n:valores/n:trib/n:tribFed/n:vRetCSLL",
                  "n:valores/n:trib/n:tribFed/n:vRetCP"):
            ret += cx(t(c))
        if t("n:valores/n:trib/n:tribMun/n:tpRetISSQN") == "2":
            ret += iss
        fmt = lambda c: f"{c // 100}.{c % 100:02d}" if c else "0"  # noqa: E731
        sub(v, "vBC", fmt(base))
        sub(v, "pAliqAplic", "5.00")
        sub(v, "vISSQN", fmt(iss))
        sub(v, "vTotalRet", fmt(ret))
        sub(v, "vLiq", fmt(cent - cdesc - ret))
        if inf_dps.find(f"{{{NS}}}IBSCBS") is not None:
            g = sub(inf, "IBSCBS")
            sub(g, "cLocalidadeIncid", cmun)
            sub(g, "xLocalidadeIncid", "Goiânia")
            vg = sub(g, "valores")
            bc = base - iss
            sub(vg, "vBC", fmt(bc))
            uf = sub(vg, "uf"); sub(uf, "pIBSUF", "0.10"); sub(uf, "pAliqEfetUF", "0.10")
            mu = sub(vg, "mun"); sub(mu, "pIBSMun", "0"); sub(mu, "pAliqEfetMun", "0")
            fe = sub(vg, "fed"); sub(fe, "pCBS", "0.90"); sub(fe, "pAliqEfetCBS", "0.90")
            tot = sub(g, "totCIBS")
            sub(tot, "vTotNF", fmt(cent - cdesc - ret))
            gi = sub(tot, "gIBS")
            ibs = (bc * 10 + 5000) // 10000
            sub(gi, "vIBSTot", fmt(ibs))
            gu = sub(gi, "gIBSUFTot"); sub(gu, "vIBSUF", fmt(ibs))
            gm = sub(gi, "gIBSMunTot"); sub(gm, "vIBSMun", "0")
            gc = sub(tot, "gCBS")
            sub(gc, "vCBS", fmt((bc * 90 + 5000) // 10000))
        inf.append(dps)
        xml = etree.tostring(nfse, xml_declaration=True, encoding="UTF-8")
        if self.pfx_sefin:
            xml = assinatura.assinar(xml, self.pfx_sefin, self.senha_sefin, "NFS" + chave)
        return xml

    # ------------------------------------------------------------ API

    def __call__(self, metodo: str, url: str, corpo):
        from nfse.cliente import NaoChegou, Resposta, SemResposta, de_gzip_b64, gzip_b64

        self.pedidos.append((metodo, url))
        caminho = url.split("SefinNacional", 1)[-1] if "SefinNacional" in url else url.split("nfse.gov.br", 1)[-1]
        modo = self.modo()
        if modo == "fora":
            raise NaoChegou("o Sistema Nacional não atendeu (simulado)")
        if metodo == "POST" and caminho.endswith("/nfse"):
            dps_xml = de_gzip_b64(corpo["dpsXmlGZipB64"])
            dps = etree.fromstring(dps_xml)
            ident = dps.find(f"{{{NS}}}infDPS").get("Id")
            with _trava:
                e = self._ler()
                e["recebidas"][ident] = e["recebidas"].get(ident, 0) + 1
                self._gravar(e)
            if modo == "timeout_antes":
                raise SemResposta("o Sistema Nacional não respondeu a tempo (simulado, antes de gerar)")
            if modo == "rejeicao":
                return Resposta(400, {"erros": [{"Codigo": "E0595", "Descricao": "Não é permitido informar alíquota superior a 5%."}]})
            with _trava:
                e = self._ler()
                if ident in e["geradas"]:
                    return Resposta(400, {"erros": [{"Codigo": "E0014", "Descricao": "Conjunto de Série, Número, ... já existe"}]})
                e["numero"] += 1
                xml = self._montar_nfse(dps, e["numero"])
                chave = etree.fromstring(xml).find(f"{{{NS}}}infNFSe").get("Id")[3:]
                e["geradas"][ident] = {"chave": chave, "xml": gzip_b64(xml)}
                self._gravar(e)
            if modo == "timeout_depois":
                raise SemResposta("o Sistema Nacional não respondeu a tempo (simulado, depois de gerar)")
            if modo == "erro500_depois":
                return Resposta(503, None, "Service Unavailable")
            if modo == "trava":
                time.sleep(3600)
            return Resposta(201, {"chaveAcesso": chave, "nfseXmlGZipB64": gzip_b64(xml), "idDps": ident, "alertas": []})
        if caminho.startswith("/dps/"):
            ident = caminho.rsplit("/", 1)[-1]
            g = self.geradas().get(ident)
            if metodo == "HEAD":
                return Resposta(200 if g else 404, None)
            return Resposta(200, {"chaveAcesso": g["chave"]}) if g else Resposta(404, {"erros": [{"Codigo": "E2001", "Descricao": "não encontrada"}]})
        if metodo == "GET" and caminho.startswith("/nfse/") and "/eventos" not in caminho:
            chave = caminho.rsplit("/", 1)[-1]
            for g in self.geradas().values():
                if g["chave"] == chave:
                    return Resposta(200, {"chaveAcesso": chave, "nfseXmlGZipB64": g["xml"]})
            return Resposta(404, None)
        if "/parametros_municipais/" in caminho and caminho.endswith("/convenio"):
            return Resposta(200, {"situacaoConvenio": "Ativo", "permiteEmissorNacional": True, "prazoCancelamentoDias": 30})
        return Resposta(404, None, "rota não simulada")
