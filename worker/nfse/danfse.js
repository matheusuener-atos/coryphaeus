// Esqueleto do DANFSe em PDF no Worker, com o pdf-lib vendorizado
// (worker/vendor/pdf-lib.min.js). É PROVA DE CUSTO, não o leiaute da NT 008:
// cabeçalho, quadros de emitente e tomador, serviço, valores e o endereço da
// consulta pública (o do QR Code, como texto - sem desenhar o QR). O leiaute
// completo continua sendo o de paulus/legal/src/nfse/danfse.py.

// UMD: no esbuild (wrangler) os nomes vêm no namespace (o pdf-lib marca
// __esModule); no node, no default. Aceita os dois.
import * as pdfLibModulo from "../vendor/pdf-lib.min.js";
const PDFLib = pdfLibModulo.PDFDocument ? pdfLibModulo : pdfLibModulo.default;

const { PDFDocument, StandardFonts, rgb } = PDFLib;
const URL_CONSULTA = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave=";

// A Helvetica padrão do PDF só escreve WinAnsi: o resto vira "?".
const WIN_ANSI_EXTRA = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ";
function texto(t) {
  return [...String(t ?? "")].map((c) => (c.charCodeAt(0) < 256 && c !== "\t" && c >= " ") || WIN_ANSI_EXTRA.includes(c) ? c : (c === "\t" ? " " : "?")).join("");
}

/**
 * dados: {chave, numero, emissao, producaoRestrita, prestador{nome, documento, municipio},
 *         tomador{nome, documento, endereco, email}, descricao,
 *         valores{servico, desconto, iss, retencoes, liquido}}
 * Devolve Uint8Array do PDF.
 */
export async function danfseEsqueleto(dados) {
  const pdf = await PDFDocument.create();
  pdf.setTitle(`DANFSe ${dados.numero || ""}`);
  pdf.setProducer("PAULUS");
  pdf.setCreationDate(new Date(0));
  pdf.setModificationDate(new Date(0));
  const pag = pdf.addPage([595.28, 841.89]); // A4 retrato
  const fonte = await pdf.embedFont(StandardFonts.Helvetica);
  const negrito = await pdf.embedFont(StandardFonts.HelveticaBold);
  const cinza = rgb(0.9, 0.9, 0.9);
  const M = 28;
  const L = 595.28 - 2 * M;
  let y = 841.89 - M;

  pag.drawRectangle({ x: M, y: M, width: L, height: 841.89 - 2 * M, borderWidth: 1, borderColor: rgb(0, 0, 0) });

  const escrever = (t, x, yy, tam = 8, f = fonte) => pag.drawText(texto(t), { x, y: yy, size: tam, font: f });
  const bloco = (titulo, linhas) => {
    y -= 14;
    pag.drawRectangle({ x: M, y: y - 3, width: L, height: 13, color: cinza });
    escrever(titulo.toUpperCase(), M + 4, y, 8, negrito);
    for (const [rotulo, valor] of linhas) {
      y -= 12;
      escrever(rotulo, M + 4, y, 7, negrito);
      escrever(valor, M + 130, y, 8);
    }
    y -= 4;
    pag.drawLine({ start: { x: M, y }, end: { x: M + L, y }, thickness: 0.5 });
  };

  y -= 18;
  escrever(dados.producaoRestrita ? "NFS-e SEM VALIDADE JURÍDICA" : "DANFSe - Documento Auxiliar da NFS-e", M + 4, y, 12, negrito);
  y -= 14;
  escrever(`Número ${dados.numero || "-"}   Emissão ${dados.emissao || "-"}`, M + 4, y, 9);
  y -= 12;
  escrever(`Chave de acesso: ${dados.chave || "-"}`, M + 4, y, 8);
  y -= 12;
  escrever(`Consulta: ${URL_CONSULTA}${dados.chave || ""}`, M + 4, y, 7);
  y -= 6;
  pag.drawLine({ start: { x: M, y }, end: { x: M + L, y }, thickness: 0.5 });

  const p = dados.prestador || {};
  const t = dados.tomador || {};
  const v = dados.valores || {};
  bloco("Prestador / emitente", [["Nome", p.nome], ["CPF/CNPJ", p.documento], ["Município", p.municipio]]);
  bloco("Tomador", [["Nome", t.nome], ["CPF/CNPJ", t.documento], ["Endereço", t.endereco], ["E-mail", t.email]]);

  y -= 14;
  pag.drawRectangle({ x: M, y: y - 3, width: L, height: 13, color: cinza });
  escrever("SERVIÇO", M + 4, y, 8, negrito);
  const palavras = texto(dados.descricao).split(/\s+/);
  let linha = "";
  for (const w of palavras) {
    const tentativa = linha ? `${linha} ${w}` : w;
    if (fonte.widthOfTextAtSize(tentativa, 8) > L - 8) {
      y -= 11;
      escrever(linha, M + 4, y);
      linha = w;
    } else linha = tentativa;
  }
  if (linha) { y -= 11; escrever(linha, M + 4, y); }
  y -= 4;
  pag.drawLine({ start: { x: M, y }, end: { x: M + L, y }, thickness: 0.5 });

  bloco("Valores", [["Valor do serviço", v.servico], ["Desconto incondicionado", v.desconto], ["ISSQN", v.iss],
    ["Retenções federais", v.retencoes], ["VALOR LÍQUIDO", v.liquido]]);

  return pdf.save({ useObjectStreams: false });
}
