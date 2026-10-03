// As tabelas oficiais da NFS-e no Worker (porte do necessário de
// paulus/legal/src/nfse/tabelas.py). Os JSON compactos saem de
// worker/nfse/tabelas/gerar.py, a partir das tabelas do PAULUS; mudar uma
// tabela é rodar o gerar.py de novo, nunca editar à mão.

import MUNICIPIOS from "./tabelas/municipios.json" with { type: "json" };
import SERVICOS from "./tabelas/servicos.json" with { type: "json" };
import NBS from "./tabelas/nbs.json" with { type: "json" };
import INDOP from "./tabelas/indop.json" with { type: "json" };
import REGRAS from "./tabelas/regras.json" with { type: "json" };
import DOMINIOS from "./tabelas/dominios.json" with { type: "json" };
import VERSOES from "./tabelas/versoes.json" with { type: "json" };
import { soDigitos } from "./texto.js";

export const UF_DO_CODIGO = {
  11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
  21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
  28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
  42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
};

const conjuntoNbs = new Set(NBS);
const conjuntoIndop = new Set(INDOP);
const tem = (obj, k) => Object.prototype.hasOwnProperty.call(obj, k);

/** {codigo, nome, uf} ou null. */
export function municipio(codigo) {
  const c = soDigitos(codigo);
  if (!tem(MUNICIPIOS, c)) return null;
  return { codigo: c, nome: MUNICIPIOS[c], uf: UF_DO_CODIGO[c.slice(0, 2)] };
}

/** {codigo, local} ou null (o cTribNac com 6 dígitos). */
export function servico(codigo) {
  const c = soDigitos(codigo).padStart(6, "0");
  return tem(SERVICOS, c) ? { codigo: c, local: SERVICOS[c] } : null;
}

export function nbs(codigo) {
  const c = soDigitos(codigo);
  return conjuntoNbs.has(c) ? { codigo: c } : null;
}

export function indop(codigo) {
  const c = soDigitos(codigo);
  return conjuntoIndop.has(c) ? { codigo: c } : null;
}

/** EP, LP ou ET para o código de serviço ("" se a tabela não diz). */
export function localDeIncidencia(ctribnac) {
  const s = servico(ctribnac);
  return s ? s.local : "";
}

/** A regra oficial (E0014, E0840...) como {mensagem, campo}, ou null. */
export function regra(codigo) {
  const c = String(codigo || "").trim().toUpperCase();
  const r = tem(REGRAS, c) ? REGRAS[c] : null;
  return r ? { mensagem: r[0], campo: r[1] } : null;
}

/** Um domínio do XSD como {código: rótulo}. */
export function dominio(nome) {
  return { ...(DOMINIOS[nome] || {}) };
}

export function versoes() {
  return VERSOES;
}
