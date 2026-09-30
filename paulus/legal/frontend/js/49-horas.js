/* --------------------------------------------------- horas do servico */
/*
   A secao "Horas" do servico (src/horas.py, docs/PLANO-PRODUTO.md P4): o
   cronometro de quem esta trabalhando, registrar a mao, quem fez quanto, e
   cobrar as horas ainda nao cobradas - vira recebimento de honorarios no
   Financeiro, do cliente do servico (so na janela do servidor).
*/

const hrs = { dados: null, id: 0, relogio: null };

async function carregarHorasDoServico(id) {
  hrs.id = id;
  try {
    const r = await fetch("/api/servicos/" + id + "/horas");
    hrs.dados = r.ok ? await r.json() : null;
  } catch (err) { hrs.dados = null; }
}

function duracaoHrs(min) {
  const h = Math.floor((min || 0) / 60), m = (min || 0) % 60;
  return h ? h + "h" + String(m).padStart(2, "0") : m + "min";
}

function reaisHrs(centavos) {
  return "R$ " + ((centavos || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function secaoDasHoras(s) {
  const d = hrs.dados;
  if (!d || hrs.id !== s.id) return "";
  const local = typeof acessoDeFora === "undefined" || acessoDeFora.local;
  const c = d.cronometro;
  const correndo = c && c.neste;
  const desde = correndo ? Math.max(0, Math.floor(Date.now() / 1000 - Number(c.inicio))) : 0;
  const cron = correndo
    ? '<button class="primario com-icone" data-hrs-parar="1">' + ic("stop_circle", 16) + 'Parar · <span id="hrs-tempo">' +
      String(Math.floor(desde / 3600)).padStart(2, "0") + ":" + String(Math.floor(desde / 60) % 60).padStart(2, "0") + "</span></button>"
    : '<button class="com-icone" data-hrs-comecar="1">' + ic("play_arrow", 16) + (c ? "Trazer o cronômetro para cá" : "Começar o cronômetro") + "</button>";
  const pessoas = (d.por_pessoa || []).map((p) => esc(p.quem) + " " + duracaoHrs(p.minutos)).join(" · ");
  const linhas = (d.registros || []).slice(0, 8).map((r) =>
    '<div class="hrs-linha"><span class="duas-linhas"><b>' + esc(duracaoHrs(r.minutos)) + " · " + esc(r.descricao || "sem descrição") + "</b>" +
    "<small>" + esc([r.quem, dataBr(r.dia), r.lancamento_id ? "cobrada" : ""].filter(Boolean).join(" · ")) + "</small></span>" +
    (r.lancamento_id ? "" : '<button type="button" class="mais-linha" data-hrs-tirar="' + r.id + '" title="Apagar o registro">' + ic("close", 15) + "</button>") +
    "</div>").join("");
  const cobrar = local
    ? '<div class="hrs-cobrar"><span>' + (d.valor_hora ? reaisHrs(d.valor_hora) + " a hora" : "sem valor da hora") +
      (d.a_cobrar_min ? " · a cobrar: " + duracaoHrs(d.a_cobrar_min) + (d.valor_hora ? " = <b>" + reaisHrs(d.a_cobrar_centavos) + "</b>" : "") : "") + "</span>" +
      '<button data-hrs-valor="1">' + (d.valor_hora ? "Mudar o valor" : "Valor da hora") + "</button>" +
      (d.a_cobrar_min ? '<button class="com-icone" data-hrs-cobrar="1">' + ic("payments", 16) + "Cobrar no Financeiro</button>" : "") + "</div>"
    : "";
  return '<section class="sv-secao sv-horas"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("schedule", 16) + "Horas</span>" +
    '<span class="sv-secao-meta">' + duracaoHrs(d.total_min) + (pessoas ? " · " + pessoas : "") + "</span></div>" +
    '<div class="cfg-botoes">' + cron + '<button class="com-icone" data-hrs-registrar="1">' + ic("add", 16) + "Registrar horas</button></div>" +
    linhas + cobrar + "</section>";
}

function ligarHoras(raiz) {
  const clique = (sel, fn) => raiz.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  const post = async (url, corpo, metodo) => {
    const r = await fetch(url, { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "não deu certo");
    return d;
  };
  const base = "/api/servicos/" + hrs.id + "/horas";
  const depois = (d) => { hrs.dados = d; desenharServicos(); };
  clearInterval(hrs.relogio);
  if (hrs.dados && hrs.dados.cronometro && hrs.dados.cronometro.neste) {
    hrs.relogio = setInterval(() => {
      const el = document.getElementById("hrs-tempo");
      if (!el) { clearInterval(hrs.relogio); return; }
      const s = Math.max(0, Math.floor(Date.now() / 1000 - Number(hrs.dados.cronometro.inicio)));
      el.textContent = String(Math.floor(s / 3600)).padStart(2, "0") + ":" + String(Math.floor(s / 60) % 60).padStart(2, "0");
    }, 15000);
  }
  clique("[data-hrs-comecar]", async () => { try { depois(await post(base + "/cronometro", { acao: "comecar" })); } catch (err) { avisoCert(err.message, { tom: "erro" }); } });
  clique("[data-hrs-parar]", async () => {
    const r = await dialogo({ titulo: "Parar o cronômetro", contexto: "Horas", campos: [{ chave: "descricao", rotulo: "O que foi feito (opcional)", obrigatorio: false }], confirmar: "Parar e registrar" });
    if (!r || !r.ok) return;
    try { depois(await post(base + "/cronometro", { acao: "parar", descricao: r.valores.descricao || "" })); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
  clique("[data-hrs-registrar]", async () => {
    const r = await dialogo({
      titulo: "Registrar horas", contexto: "Horas",
      campos: [
        { chave: "duracao", rotulo: "Quanto tempo", placeholder: "1h30, 1:30, 90min", obrigatorio: true },
        { chave: "dia", rotulo: "Dia", valor: new Date().toLocaleDateString("pt-BR"), obrigatorio: true },
        { chave: "descricao", rotulo: "O que foi feito", obrigatorio: false },
      ],
      confirmar: "Registrar",
    });
    if (!r || !r.ok) return;
    const m = String(r.valores.dia || "").trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    const dia = m ? m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0") : "";
    try { depois(await post(base, { duracao: r.valores.duracao, dia: dia, descricao: r.valores.descricao || "" })); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
  clique("[data-hrs-tirar]", async (b) => { try { depois(await post(base + "/" + b.dataset.hrsTirar, undefined, "DELETE")); } catch (err) { avisoCert(err.message, { tom: "erro" }); } });
  clique("[data-hrs-valor]", async () => {
    const r = await dialogo({ titulo: "Valor da hora", contexto: "Horas", campos: [{ chave: "valor", rotulo: "Valor da hora (R$)", placeholder: "300,00", obrigatorio: true }], confirmar: "Guardar" });
    if (!r || !r.ok) return;
    try { depois(await post(base + "/valor", { valor: r.valores.valor })); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
  clique("[data-hrs-cobrar]", async () => {
    const d = hrs.dados || {};
    const r = await dialogo({
      titulo: "Cobrar as horas", contexto: "Horas › Financeiro",
      texto: duracaoHrs(d.a_cobrar_min) + " a " + reaisHrs(d.valor_hora) + " a hora = " + reaisHrs(d.a_cobrar_centavos) +
        ". Vira um recebimento de honorários no Financeiro, do cliente do serviço, e as horas passam a cobradas.",
      campos: [{ chave: "vencimento", rotulo: "Vencimento (opcional)", placeholder: "dd/mm/aaaa", obrigatorio: false }],
      confirmar: "Cobrar",
    });
    if (!r || !r.ok) return;
    const m = String(r.valores.vencimento || "").trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    try {
      depois(await post(base + "/cobrar", { vencimento: m ? m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0") : "" }));
      avisoCert("cobrança lançada no Financeiro", { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
}
