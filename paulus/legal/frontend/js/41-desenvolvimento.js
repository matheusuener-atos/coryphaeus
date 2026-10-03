/* ------------------------------------------------ desenvolvimento aberto */
/*
   A20 (docs/ui/desenvolvimento): como o PAVLVS evoluiu, mes a mes. Os dados
   sao os publicos do site (/api/publico/desenvolvimento): as versoes. Nada
   do usuario vai ou vem. Sem internet, a ultima copia. Abre por
   Configuracoes > Versao.

   Barra de periodo: o ano com setas e os doze meses; ponto = mes com versao;
   mes sem registro fica apagado e desabilitado. Abre no mes mais recente.
   Mudanca com miniatura mostra a imagem ao passar o mouse.
*/

const dev = { dados: null, sel: "", ano: "", erro: "" };
const MESES_DEV = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

async function mostrarDesenvolvimento() {
  abrirTela("Desenvolvimento aberto", { cheia: true });
  marcarDestino("config");
  $("conversa-titulo").textContent = "Desenvolvimento aberto";
  $("conversa-meta").textContent = "Software livre · as versões, mês a mês";
  $("acoes-tela").innerHTML = '<button class="com-icone" id="dev-voltar">' + ic("arrow_back", 16) + "Configurações</button>";
  $("nav-tela").innerHTML = "";
  $("dev-voltar").onclick = () => mostrarConfig("plano");
  desenharDesenvolvimento();
  try {
    const r = await fetch("/api/publico/desenvolvimento");
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "o site não respondeu");
    const meses = (d.meses || []).slice().sort((a, b) => b.month.localeCompare(a.month));
    dev.dados = { ...d, meses };
    dev.sel = meses[0] ? meses[0].month : "";
    dev.ano = dev.sel.slice(0, 4);
    dev.erro = "";
  } catch (err) {
    dev.erro = err.message;
  }
  if ($("dev-tela")) desenharDesenvolvimento();
}

function dataDev(s) { const [y, m, d] = String(s).split("-"); return d + "/" + m + "/" + y; }
function maiusculaDev(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function desenharDesenvolvimento() {
  const d = dev.dados;
  let corpo;
  if (!d) {
    corpo = dev.erro
      ? '<p class="dev-vazio">Não consegui ler o histórico em paulus.ia.br: ' + esc(dev.erro) + ". Confira a internet e abra de novo.</p>"
      : '<p class="dev-vazio">Lendo o histórico…</p>';
  } else if (!d.meses.length) {
    corpo = '<p class="dev-vazio">Ainda não há versões registradas.</p>';
  } else {
    corpo = barraDoPeriodo() + mesDev();
  }
  const rodape = d
    ? '<span class="dev-atualizado">' + (d.atualizadoEm ? "Atualizado em " + dataDev(d.atualizadoEm) + ". " : "") +
      "Você usa a versão v" + esc(d.versao_instalada || "") + "." + (d.offline ? " Sem internet agora: esta é a última cópia guardada." : "") + "</span>"
    : "";
  $("centro").innerHTML = '<div class="acervo sem-painel dev-tela" id="dev-tela"><div class="acervo-principal sv-principal"><div class="sv-medida">' +
    '<header class="dev-topo"><h1>Como o PAVLVS evoluiu, mês a mês</h1>' +
    "<p>Escolha um mês para ver as versões publicadas e o que mudou em cada uma.</p></header>" +
    corpo +
    '<section class="dev-sobre">' + rodape + "</section>" +
    "</div></div></div>";
  ligarDesenvolvimento();
}

function barraDoPeriodo() {
  const d = dev.dados;
  const porMes = {};
  d.meses.forEach((m) => { porMes[m.month] = m; });
  const anos = [...new Set(d.meses.map((m) => m.month.slice(0, 4)))].sort();
  const i = anos.indexOf(dev.ano);
  const celulas = MESES_DEV.map((nome, k) => {
    const id = dev.ano + "-" + String(k + 1).padStart(2, "0");
    const m = porMes[id];
    const n = m ? m.releases.length : 0;
    const dica = maiusculaDev(nome) + ": " + (m ? (n ? n + (n === 1 ? " versão" : " versões") : "sem versão") : "sem registro");
    const classe = dev.sel === id ? "dev-mes sel" : "dev-mes";
    return '<button type="button" class="' + classe + '" data-dev-mes="' + id + '"' +
      (m ? "" : " disabled") + ' title="' + esc(dica) + '">' + maiusculaDev(nome.slice(0, 3)) + (n ? "<i></i>" : "") + "</button>";
  }).join("");
  return '<div class="dev-periodo"><div class="dev-barra"><div class="dev-ano">' +
    '<button type="button" data-dev-ano="-1" aria-label="Ano anterior"' + (i <= 0 ? " disabled" : "") + ">" + ic("chevron_left", 18) + "</button>" +
    "<span>" + esc(dev.ano) + "</span>" +
    '<button type="button" data-dev-ano="1" aria-label="Ano seguinte"' + (i < 0 || i >= anos.length - 1 ? " disabled" : "") + ">" + ic("chevron_right", 18) + "</button></div>" +
    '<div class="dev-meses">' + celulas + "</div></div>" +
    '<div class="dev-legenda"><span><i></i>mês com versão publicada</span><span><b>Mai</b>sem registro</span></div></div>';
}

function mesDev() {
  const m = dev.dados.meses.find((x) => x.month === dev.sel);
  if (!m) return "";
  const nome = MESES_DEV[+m.month.slice(5) - 1];
  const n = m.releases.length;
  const frase = "Em " + nome + " de " + m.month.slice(0, 4) + ", " +
    (n ? "foram publicadas " + n + (n === 1 ? " versão" : " versões") + " do PAVLVS." : "não houve publicação de versão.");
  const instalada = dev.dados.versao_instalada;
  const versoes = m.releases.map((r) => {
    const itens = (r.changes || []).map((x) => {
      const o = typeof x === "string" ? { text: x } : x;
      const previa = previaDev(o.preview);
      return previa
        ? '<li class="com-previa" tabindex="0"><span>' + esc(o.text) + "</span>" + ic("visibility", 14) +
          '<span class="dev-previa" aria-hidden="true"><span style="background-image:url(&quot;' + esc(previa) + '&quot;)"></span><small>Como ficou em v' + esc(r.version) + "</small></span></li>"
        : "<li>" + esc(o.text) + "</li>";
    }).join("");
    return '<div class="dev-versao"><div class="dev-versao-cabeca"><b>v' + esc(r.version) + "</b><span>publicada em " + dataDev(r.date) + "</span>" +
      (r.version === instalada ? '<span class="dev-selo">é a sua versão</span>' : "") + "</div><ul>" + itens + "</ul></div>";
  }).join("");
  return '<section class="dev-selecionado"><div class="dev-titulo"><h2>' + maiusculaDev(nome) + " de " + m.month.slice(0, 4) + "</h2><p>" + esc(frase) + "</p></div>" +
    '<div class="dev-versoes"><span class="rotulo">' + (n ? "O que mudou no PAVLVS" : "Versões") + "</span>" + versoes +
    (n ? "" : "<p>Nenhuma versão foi publicada neste mês. O desenvolvimento segue entre uma versão e outra; as mudanças aparecem na próxima publicação.</p>") +
    "</div></section>";
}

/* A miniatura so vem do proprio site do projeto. */
function previaDev(caminho) {
  if (!caminho || typeof caminho !== "string") return "";
  if (caminho.startsWith("/")) return "https://paulus.ia.br" + caminho;
  return /^https:\/\/paulus\.ia\.br\//.test(caminho) ? caminho : "";
}

function ligarDesenvolvimento() {
  document.querySelectorAll("[data-dev-mes]").forEach((b) => {
    b.onclick = () => { dev.sel = b.dataset.devMes; desenharDesenvolvimento(); };
  });
  document.querySelectorAll("[data-dev-ano]").forEach((b) => {
    b.onclick = () => {
      const anos = [...new Set(dev.dados.meses.map((m) => m.month.slice(0, 4)))].sort();
      const i = anos.indexOf(dev.ano) + Number(b.dataset.devAno);
      if (i < 0 || i >= anos.length) return;
      dev.ano = anos[i];
      // O mes escolhido passa a ser o mais recente com registro no ano.
      const doAno = dev.dados.meses.filter((m) => m.month.startsWith(dev.ano));
      if (doAno.length) dev.sel = doAno[0].month;
      desenharDesenvolvimento();
    };
  });
}
