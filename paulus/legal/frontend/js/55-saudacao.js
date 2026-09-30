/* ------------------------------------------------- a saudacao (T1) */
/*
   Chave conversa.saudacao (src/saudacao.py, config/saudacoes.json).

   A frase continua saindo sem modelo: o servidor escolhe do banco pelo
   momento, pelo dia, pelo calendario, pelo jeito como a pessoa chegou e pela
   situacao do escritorio; a tela so diz quais frases mostrou ha pouco (as 20
   ultimas, nesta maquina), quando o programa foi aberto antes e qual conversa
   foi aberta por ultimo. A frase de antes (saudacao() em 03-assistente.js)
   aparece na hora e e trocada assim que a resposta chega.
*/

const SAUDACOES_VISTAS = "paulus.saudacoes";
const ULTIMA_ABERTURA = "paulus.ultimaAbertura";
const ULTIMA_CONVERSA = "paulus.ultimaConversa";
// A abertura anterior e lida uma vez por carga da pagina: voltar ao inicio
// dentro da mesma sessao nao e "primeira abertura do dia" de novo.
let aberturaAnterior = null;

function saudacaoNova() {
  return Boolean((window.PAULUS_CONVERSA || {}).saudacao);
}

function lerLocal(chave, padrao) {
  try { const v = localStorage.getItem(chave); return v === null ? padrao : JSON.parse(v); } catch (err) { return padrao; }
}

function gravarLocal(chave, valor) {
  try { localStorage.setItem(chave, JSON.stringify(valor)); } catch (err) { /* sem memoria: repete mais */ }
}

/* A ultima conversa aberta, para o "De volta. Seguimos com …?". */
function lembrarConversaAberta(id) {
  if (id) gravarLocal(ULTIMA_CONVERSA, { id: id, em: new Date().toISOString() });
}

async function pedirSaudacao() {
  if (!saudacaoNova()) return;
  if (aberturaAnterior === null) {
    aberturaAnterior = lerLocal(ULTIMA_ABERTURA, "") || "";
    gravarLocal(ULTIMA_ABERTURA, new Date().toISOString());
  }
  const vistas = lerLocal(SAUDACOES_VISTAS, []) || [];
  const conversa = lerLocal(ULTIMA_CONVERSA, null) || {};
  const q = new URLSearchParams({
    recentes: vistas.slice(-40).join(","),
    ultima_abertura: aberturaAnterior,
    ultima_conversa: conversa.id || "",
    conversa_aberta_em: conversa.em || "",
  });
  let d;
  try {
    const r = await fetch("/api/saudacao?" + q.toString());
    if (!r.ok) return;
    d = await r.json();
  } catch (err) { return; }
  if (!d || !d.ligado) return;
  desenharSaudacao(d);
  gravarLocal(SAUDACOES_VISTAS, vistas.concat(d.ids || []).slice(-40));
}

function desenharSaudacao(d) {
  const chamada = $("chamada");
  chamada.textContent = d.titulo;
  // "De volta. Seguimos com a conversa sobre “Contrato ACME”?": o titulo
  // citado vira o atalho para abri-la.
  if (d.conversa && d.conversa.id && d.conversa.titulo) {
    const alvo = "“" + d.conversa.titulo;
    const i = d.titulo.indexOf("“");
    if (i >= 0 && d.titulo.slice(i).startsWith(alvo.slice(0, Math.min(alvo.length, 12)))) {
      const fim = d.titulo.indexOf("”", i);
      chamada.innerHTML = esc(d.titulo.slice(0, i)) + '<button class="chamada-link" data-abrir-conversa="' + esc(d.conversa.id) + '">' +
        esc(d.titulo.slice(i, fim + 1)) + "</button>" + esc(d.titulo.slice(fim + 1));
      chamada.querySelector("[data-abrir-conversa]").onclick = () => abrirTrabalho(d.conversa.id);
    }
  }
  const sub = $("sub-chamada");
  sub.dataset.base = d.subtitulo;
  sub.textContent = d.subtitulo;
}
