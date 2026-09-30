/* ------------------------------------------ IA em segundo plano (C5) */
/*
   Chave conversa.superficies (src/ia_em_fundo.py).

   O parecer do Financeiro e o resumo da gravação deixam de esperar parados:
   a chamada vira uma execução no servidor, com a vez na fila do modelo, e a
   tela mostra uma linha só - "Na fila do modelo: você é o 2º", "Escrevendo…"
   - com o Parar. O id fica guardado nesta janela, por objeto: sair da tela,
   recarregar ou reabrir o programa e voltar mostra o resultado (ele está no
   registro da execução, no servidor) ou a execução em curso.

   Só na janela do escritório: de fora, a tela usa a rota de antes (a rota
   nova é BLOQUEADA de fora, ver src/acesso/politicas.py).
*/

const IA_GUARDADAS = "paulus.ia.";

function superficiesNovas() {
  return Boolean((window.PAULUS_CONVERSA || {}).superficies) && !(acessoDeFora && acessoDeFora.pessoa);
}

function iaGuardada(chave) {
  try { return JSON.parse(localStorage.getItem(IA_GUARDADAS + chave) || "null"); } catch (err) { return null; }
}

function guardarIA(chave, valor) {
  try {
    if (valor) localStorage.setItem(IA_GUARDADAS + chave, JSON.stringify(valor));
    else localStorage.removeItem(IA_GUARDADAS + chave);
  } catch (err) { /* sem memoria: o resultado so vale nesta tela */ }
}

/* O componente: a linha de estado, o Parar e o erro com "tentar de novo". */
function blocoIA(chave, texto) {
  return '<div class="ia-trabalhando" data-ia="' + esc(chave) + '"><i class="ponto pulsa"></i><span class="ia-estado">' + esc(texto || "Na fila do modelo…") +
    '</span><button class="barra-parar" data-ia-parar="' + esc(chave) + '">' + ic("stop", 14) + "Parar</button></div>";
}

function mudarBlocoIA(chave, texto) {
  document.querySelectorAll('[data-ia="' + chave + '"] .ia-estado').forEach((el) => { el.textContent = texto; });
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-ia-parar]");
  if (!b) return;
  const g = iaGuardada(b.dataset.iaParar);
  if (!g) return;
  b.disabled = true;
  fetch("/api/execucoes/" + g.id + "/parar", { method: "POST" }).catch(() => {});
  mudarBlocoIA(b.dataset.iaParar, "Parando…");
});

/* Pede a chamada e espera o resultado (o mesmo JSON da rota de antes). */
async function chamarIA(tipo, dados, chave) {
  const r = await fetch("/api/ia/" + tipo, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: dados || {} }),
  });
  if (!r.ok) throw new Error(await erroDe(r));
  const d = await r.json();
  guardarIA(chave, { id: d.execucao_id, tipo: tipo, em: Date.now() });
  return acompanharIA(chave);
}

/* Acompanha a execucao guardada desta chave, do comeco do registro. */
async function acompanharIA(chave) {
  const g = iaGuardada(chave);
  if (!g) throw new Error("nada em andamento");
  const r = await fetch("/api/execucoes/" + g.id + "/eventos?desde=0");
  if (!r.ok) { guardarIA(chave, null); throw new Error("a chamada de antes não está mais no registro"); }
  let resultado = null, erro = "";
  for await (const ev of eventosSSE(r)) {
    if (ev.tipo === "fila") mudarBlocoIA(chave, textoDaFila(ev.dados).replace(/^na fila/, "Na fila"));
    else if (ev.tipo === "trabalhando") mudarBlocoIA(chave, "Escrevendo… (" + (ev.dados.rotulo || "o modelo desta máquina") + ")");
    else if (ev.tipo === "resultado") resultado = ev.dados;
    else if (ev.tipo === "erro") erro = ev.dados.mensagem || "não deu certo";
    else if (ev.tipo === "parado") erro = "parado";
  }
  if (erro) { if (erro === "parado") guardarIA(chave, null); throw new Error(erro); }
  return resultado;
}
