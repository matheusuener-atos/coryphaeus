/* ------------------------------------------------ CPF, CNPJ e telefone */
/*
   Um campo marcado com data-campo="cpf" | "cnpj" | "cpf-cnpj" | "telefone"
   formata enquanto a pessoa digita (ou cola) e confere ao sair do campo:
   o CPF e o CNPJ pelos digitos verificadores, o telefone pelo tamanho. Vale
   em qualquer tela (assistente de configuracao, Configuracoes, Cadastros,
   Conexoes): a marcacao basta, o resto e daqui, por delegacao.

   O CNPJ aceita o formato alfanumerico da Receita (IN RFB 2.229/2024, em
   uso desde julho de 2026): as 12 primeiras posicoes podem ter letras; os
   dois verificadores continuam numeros, e a conta usa o codigo de cada
   caractere menos 48 - o mesmo calculo de sempre para quem e so numero.

   Campo vazio e valido: nenhum desses dados e obrigatorio. Quem salva
   pergunta camposInvalidos(raiz) antes e para no primeiro que nao fecha.
*/

const CAMPO_ROTULO = { cpf: "CPF", cnpj: "CNPJ", "cpf-cnpj": "CPF ou CNPJ", telefone: "Telefone" };

function soDigitos(v) { return String(v || "").replace(/\D/g, ""); }

/* O que sobra de um CPF/CNPJ digitado: numeros e, para o CNPJ novo, letras. */
function limparDocumento(v) { return String(v || "").toUpperCase().replace(/[^0-9A-Z]/g, ""); }

function formatarCpf(v) {
  const d = soDigitos(v).slice(0, 11);
  if (d.length <= 3) return d;
  if (d.length <= 6) return d.slice(0, 3) + "." + d.slice(3);
  if (d.length <= 9) return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
  return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
}

function formatarCnpj(v) {
  // Letras so nas 12 primeiras posicoes; os verificadores sao numeros.
  const bruto = limparDocumento(v);
  const c = (bruto.slice(0, 12) + soDigitos(bruto.slice(12))).slice(0, 14);
  if (c.length <= 2) return c;
  if (c.length <= 5) return c.slice(0, 2) + "." + c.slice(2);
  if (c.length <= 8) return c.slice(0, 2) + "." + c.slice(2, 5) + "." + c.slice(5);
  if (c.length <= 12) return c.slice(0, 2) + "." + c.slice(2, 5) + "." + c.slice(5, 8) + "/" + c.slice(8);
  return c.slice(0, 2) + "." + c.slice(2, 5) + "." + c.slice(5, 8) + "/" + c.slice(8, 12) + "-" + c.slice(12);
}

/* Um campo so para os dois: ate 11 numeros e CPF; passou disso, ou tem
   letra, e CNPJ. */
function formatarCpfOuCnpj(v) {
  const c = limparDocumento(v);
  return c.length > 11 || /[A-Z]/.test(c) ? formatarCnpj(c) : formatarCpf(c);
}

function formatarTelefone(v) {
  const bruto = String(v || "").trim();
  // Numero de fora do Brasil (+ que nao e 55): fica como a pessoa escreveu.
  if (/^\+(?!55)/.test(bruto)) return bruto.replace(/[^\d+ ()-]/g, "");
  let d = soDigitos(bruto);
  if (d.length > 11 && d.startsWith("55")) d = d.slice(2);
  if (d.startsWith("0800") || d.startsWith("0300")) {
    d = d.slice(0, 11);
    return d.length <= 4 ? d : d.slice(0, 4) + " " + d.slice(4, 7) + (d.length > 7 ? " " + d.slice(7) : "");
  }
  d = d.slice(0, 11);
  if (!d) return "";
  if (d.length <= 2) return "(" + d;
  const ddd = "(" + d.slice(0, 2) + ") ";
  const resto = d.slice(2);
  // Celular tem 9 digitos depois do DDD (comeca com 9); fixo, 8.
  const corte = resto.length > 8 || (resto[0] === "9" && resto.length >= 5) ? 5 : 4;
  return resto.length <= corte ? ddd + resto : ddd + resto.slice(0, corte) + "-" + resto.slice(corte);
}

function cpfValido(v) {
  const d = soDigitos(v);
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  for (const n of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < n; i += 1) soma += Number(d[i]) * (n + 1 - i);
    const dv = (soma * 10) % 11 % 10;
    if (dv !== Number(d[n])) return false;
  }
  return true;
}

function cnpjValido(v) {
  const c = limparDocumento(v);
  if (!/^[0-9A-Z]{12}\d{2}$/.test(c) || /^(.)\1{13}$/.test(c)) return false;
  const valor = (ch) => ch.charCodeAt(0) - 48;
  for (const n of [12, 13]) {
    const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    let soma = 0;
    for (let i = 0; i < n; i += 1) soma += valor(c[i]) * pesos[i];
    const resto = soma % 11;
    const dv = resto < 2 ? 0 : 11 - resto;
    if (dv !== Number(c[n])) return false;
  }
  return true;
}

function telefoneValido(v) {
  const bruto = String(v || "").trim();
  if (/^\+(?!55)/.test(bruto)) return soDigitos(bruto).length >= 8;
  let d = soDigitos(bruto);
  if (d.length > 11 && d.startsWith("55")) d = d.slice(2);
  if (d.startsWith("0800") || d.startsWith("0300")) return d.length === 11;
  if (d.length !== 10 && d.length !== 11) return false;
  if (d[0] === "0" || d[1] === "0") return false;              // DDD nao comeca nem termina em 0
  return d.length === 10 || d[2] === "9";                      // 11 digitos: celular, comeca com 9
}

/* O que esta errado no valor, ou "" se esta certo (vazio e certo). */
function problemaDoCampo(tipo, valor) {
  const v = String(valor || "").trim();
  if (!v) return "";
  if (tipo === "cpf") {
    if (soDigitos(v).length < 11) return "CPF incompleto: são 11 números";
    return cpfValido(v) ? "" : "CPF inválido: confira os números";
  }
  if (tipo === "cnpj") {
    if (limparDocumento(v).length < 14) return "CNPJ incompleto: são 14 caracteres";
    return cnpjValido(v) ? "" : "CNPJ inválido: confira os caracteres";
  }
  if (tipo === "cpf-cnpj") {
    const c = limparDocumento(v);
    if (c.length > 11 || /[A-Z]/.test(c)) return problemaDoCampo("cnpj", v);
    return problemaDoCampo("cpf", v);
  }
  if (tipo === "telefone") return telefoneValido(v) ? "" : "telefone incompleto: DDD e número, como (62) 99999-8888";
  return "";
}

function formatarCampo(tipo, valor) {
  if (tipo === "cpf") return formatarCpf(valor);
  if (tipo === "cnpj") return formatarCnpj(valor);
  if (tipo === "cpf-cnpj") return formatarCpfOuCnpj(valor);
  if (tipo === "telefone") return formatarTelefone(valor);
  return valor;
}

/* Reformata sem jogar o cursor para o fim: conta quantos caracteres
   "de verdade" (numeros e letras) havia antes dele e volta para o mesmo
   ponto no texto novo. Devolve se mudou alguma coisa. */
function reformatarNoLugar(el) {
  const tipo = el.dataset.campo;
  const antes = el.value;
  const pos = el.selectionStart == null ? antes.length : el.selectionStart;
  const uteis = antes.slice(0, pos).replace(/[^0-9A-Za-z+]/g, "").length;
  const novo = formatarCampo(tipo, antes);
  if (novo === antes) return false;
  el.value = novo;
  let conta = 0;
  let cursor = novo.length;
  for (let i = 0; i < novo.length; i += 1) {
    if (conta === uteis) { cursor = i; break; }
    if (/[0-9A-Za-z+]/.test(novo[i])) conta += 1;
  }
  if (document.activeElement === el) { try { el.setSelectionRange(cursor, cursor); } catch (err) { /* campo sem selecao */ } }
  return true;
}

/* O aviso fica logo abaixo do campo, no mesmo bloco (label + input). */
function mostrarProblemaDoCampo(el) {
  const problema = problemaDoCampo(el.dataset.campo, el.value);
  el.classList.toggle("campo-invalido", Boolean(problema));
  el.setAttribute("aria-invalid", problema ? "true" : "false");
  const bloco = el.closest(".campo-painel, .ag-campo, .dialogo-campo, .campo") || el.parentElement;
  let aviso = bloco ? bloco.querySelector(".campo-aviso") : null;
  if (problema && bloco) {
    if (!aviso) {
      aviso = document.createElement("span");
      aviso.className = "campo-aviso";
      aviso.setAttribute("role", "alert");
      bloco.appendChild(aviso);
    }
    aviso.textContent = problema;
  } else if (aviso) {
    aviso.remove();
  }
  return problema;
}

/* Antes de salvar: mostra o problema de cada campo e devolve o primeiro.
   O campo que mudou de mascara avisa a tela com um "input", como se a pessoa
   tivesse digitado: e assim que o modelo da tela (cad.form, cfg.rascunho)
   recebe o valor formatado. Nao entra em laco: o "input" daqui reformata de
   novo, nao muda nada e nao dispara outro. */
function camposInvalidos(raiz) {
  const r = raiz || document;
  let primeiro = null;
  r.querySelectorAll("[data-campo]").forEach((el) => {
    if (reformatarNoLugar(el)) el.dispatchEvent(new Event("input", { bubbles: true }));
    if (mostrarProblemaDoCampo(el) && !primeiro) primeiro = el;
  });
  return primeiro;
}

/* Para mostrar um valor ja gravado: formatado se fecha; se nao, como veio
   (um valor antigo torto nao deve ser cortado pela mascara na leitura). */
function exibirCampo(tipo, valor) {
  const v = String(valor || "").trim();
  if (!v || problemaDoCampo(tipo, v)) return v;
  return formatarCampo(tipo, v);
}

/* Para quem desenha o campo: o modo do teclado e o tamanho maximo. */
function atributosDoCampo(tipo) {
  const modo = tipo === "telefone" ? "tel" : (tipo === "cpf" ? "numeric" : "text");
  const maximo = { cpf: 14, cnpj: 18, "cpf-cnpj": 18, telefone: 20 }[tipo] || 40;
  return ' data-campo="' + tipo + '" inputmode="' + modo + '" maxlength="' + maximo + '" autocomplete="off" spellcheck="false"';
}

/* Fora do navegador (o teste roda no Node) nao ha pagina para ouvir. */
if (typeof document !== "undefined") {
document.addEventListener("input", (e) => {
  const el = e.target;
  if (!el || !el.dataset || !el.dataset.campo) return;
  reformatarNoLugar(el);
  // Enquanto digita, so tira o aviso quando ficar certo; nao acusa no meio.
  if (el.classList.contains("campo-invalido") && !problemaDoCampo(el.dataset.campo, el.value)) mostrarProblemaDoCampo(el);
}, true);

document.addEventListener("focusout", (e) => {
  const el = e.target;
  if (el && el.dataset && el.dataset.campo) mostrarProblemaDoCampo(el);
}, true);
}
