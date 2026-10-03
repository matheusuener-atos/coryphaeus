/* Profundidade jurídica e conversa modular (src/profundidade.py,
   src/entrevista.py, src/elaboracao.py - 03/10/2026).

   - A caixa da pergunta: a pílula do nível (Estagiário → Bacharel → Advogado
     → Juiz → Ministro). A pessoa escolhe o quanto quer que o PAULUS
     trabalhe; o modelo e as etapas são do programa e aparecem discretos no
     menu. Fica neste navegador (localStorage), e vale para as próximas
     perguntas. "Perguntar antes de trabalhar" também.
   - O módulo de perguntas: o cartão que o modelo montou para ESTE pedido.
     Os componentes são fixos (escolha, múltipla, texto, data, valor, parte,
     documento); o conteúdo é do modelo. Em toda pergunta: "Não sei",
     "Decida por mim", "Depois". No cartão: Enviar, Continuar com o que
     temos, Decida por mim, Quero explicar com minhas palavras, Responder
     depois. Escrever na caixa, com o cartão aberto, também responde.
   - O trabalho pronto: o cartão de levar ao editor, com o que a revisão
     apontou e o que conferir. */

const prof = { niveis: [], padrao: "advogado", escolhido: "", perguntar: true, aberto: false };

function lerGuardado(chave, padrao) {
  try { const v = localStorage.getItem(chave); return v === null ? padrao : v; } catch (err) { return padrao; }
}
function guardar(chave, valor) {
  try { localStorage.setItem(chave, valor); } catch (err) { /* sem armazenamento: vale só nesta página */ }
}

prof.escolhido = lerGuardado("paulus.profundidade", "");
prof.perguntar = lerGuardado("paulus.perguntar_antes", "1") !== "0";

function nivelAtual() {
  const id = prof.escolhido || prof.padrao;
  return prof.niveis.find((n) => n.id === id) || prof.niveis.find((n) => n.id === prof.padrao) || null;
}

/* A situação da nuvem chega por js/75-nuvem.js; a pílula do nível só existe
   com ela - sem a nuvem, o modelo deste computador responde num nível só, e
   a pílula prometeria o que não acontece. */
function desenharPilulaProfundidade() {
  const s = (typeof nuvemTela !== "undefined" && nuvemTela.situacao) || null;
  const p = s && s.profundidade;
  if (p && p.niveis) { prof.niveis = p.niveis; prof.padrao = p.padrao || "advogado"; }
  let b = document.getElementById("pilula-profundidade");
  if (!s || !s.ligada || !prof.niveis.length) { if (b) b.remove(); fecharMenuProfundidade(); return; }
  if (!b) {
    const ancora = document.getElementById("pilula-nuvem") || document.getElementById("ditar");
    if (!ancora) return;
    b = document.createElement("button");
    b.type = "button";
    b.id = "pilula-profundidade";
    b.className = "pilula pilula-profundidade";
    b.setAttribute("aria-haspopup", "menu");
    b.onclick = (e) => { e.stopPropagation(); prof.aberto ? fecharMenuProfundidade() : abrirMenuProfundidade(); };
    ancora.parentNode.insertBefore(b, ancora);
  }
  const n = nivelAtual();
  const aqui = typeof nuvemTela !== "undefined" && nuvemTela.aqui;
  b.disabled = Boolean(aqui);
  b.title = aqui ? "A próxima pergunta fica neste computador: a profundidade vale só na nuvem."
    : "Profundidade: " + (n ? n.nome + " — " + n.resumo : "") + ". Clique para escolher o quanto o PAULUS trabalha.";
  b.innerHTML = ic("gavel", 18) + '<span class="rotulo-botao">' + esc(n ? n.nome : "Profundidade") + "</span>";
}

function abrirMenuProfundidade() {
  fecharMenuProfundidade();
  const b = document.getElementById("pilula-profundidade");
  if (!b) return;
  const atual = nivelAtual();
  const menu = document.createElement("div");
  menu.id = "menu-profundidade";
  menu.className = "menu-profundidade";
  menu.setAttribute("role", "menu");
  menu.innerHTML = '<div class="mp-cabeca"><b>Quanto o PAULUS trabalha este pedido</b>' +
    "<small>Você escolhe o esforço; o modelo e as etapas são por conta do programa.</small></div>" +
    prof.niveis.map((n, i) =>
      '<button type="button" role="menuitemradio" class="mp-nivel' + (atual && atual.id === n.id ? " on" : "") +
      '" aria-checked="' + Boolean(atual && atual.id === n.id) + '" data-prof-nivel="' + esc(n.id) + '">' +
      '<span class="mp-degrau" aria-hidden="true">' + "▮".repeat(i + 1) + '<span class="mp-vazio">' + "▮".repeat(4 - i) + "</span></span>" +
      '<span class="mp-texto"><b>' + esc(n.nome) + (n.id === prof.padrao ? ' <em>padrão</em>' : "") + "</b>" +
      "<span>" + esc(n.resumo) + "</span>" +
      '<small class="mp-tecnico">' + esc((n.detalhes || []).join(" · ")) + " · consome ~" +
      esc(String(n.consumo).replace(".", ",")) + "× da franquia</small></span></button>").join("") +
    '<label class="mp-perguntar"><input type="checkbox" data-prof-perguntar="1"' + (prof.perguntar ? " checked" : "") + ">" +
    "<span><b>Entender antes de trabalhar</b><small>Em pedidos de trabalho (contrato, petição, parecer…), o PAULUS " +
    "pergunta o que muda o resultado antes de redigir. Pergunta simples não ganha perguntas.</small></span></label>";
  document.body.appendChild(menu);
  const r = b.getBoundingClientRect();
  const largura = Math.min(420, window.innerWidth - 16);
  menu.style.width = largura + "px";
  menu.style.left = Math.max(8, Math.min(r.left, window.innerWidth - largura - 8)) + "px";
  // Abre para o lado com mais espaço (a caixa da pergunta pode estar no alto
  // ou no pé da tela); sem espaço para tudo, rola por dentro.
  const acima = r.top - 16, abaixo = window.innerHeight - r.bottom - 16;
  menu.style.maxHeight = Math.max(200, Math.min(640, Math.max(acima, abaixo))) + "px";
  const altura = menu.offsetHeight;
  menu.style.top = (acima >= altura || acima >= abaixo ? Math.max(8, r.top - altura - 8) : r.bottom + 8) + "px";
  prof.aberto = true;
  b.setAttribute("aria-expanded", "true");
  menu.querySelectorAll("[data-prof-nivel]").forEach((x) => {
    x.onclick = () => {
      prof.escolhido = x.dataset.profNivel;
      guardar("paulus.profundidade", prof.escolhido);
      fecharMenuProfundidade();
      desenharPilulaProfundidade();
      const p = document.getElementById("pedido");
      if (p) p.focus();
    };
  });
  const caixa = menu.querySelector("[data-prof-perguntar]");
  caixa.onchange = () => { prof.perguntar = caixa.checked; guardar("paulus.perguntar_antes", caixa.checked ? "1" : "0"); };
  const primeiro = menu.querySelector(".mp-nivel.on") || menu.querySelector(".mp-nivel");
  if (primeiro) primeiro.focus();
}

function fecharMenuProfundidade() {
  const m = document.getElementById("menu-profundidade");
  if (m) m.remove();
  prof.aberto = false;
  const b = document.getElementById("pilula-profundidade");
  if (b) b.setAttribute("aria-expanded", "false");
}

document.addEventListener("click", (e) => {
  if (prof.aberto && !e.target.closest("#menu-profundidade") && !e.target.closest("#pilula-profundidade")) fecharMenuProfundidade();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && prof.aberto) { fecharMenuProfundidade(); const b = document.getElementById("pilula-profundidade"); if (b) b.focus(); }
});
window.addEventListener("resize", () => { if (prof.aberto) fecharMenuProfundidade(); });

/* A pílula se redesenha com a da nuvem: as duas leem a mesma situação. */
if (typeof desenharPilulaNuvem === "function") {
  const desenharNuvemAntes = desenharPilulaNuvem;
  desenharPilulaNuvem = function () {   // eslint-disable-line no-func-assign
    desenharNuvemAntes.apply(this, arguments);
    desenharPilulaProfundidade();
  };
}
desenharPilulaProfundidade();

/* O que vai junto da pergunta. */
function profundidadeDoEnvio() {
  const n = nivelAtual();
  if (!n) return {};
  return Object.assign({ profundidade: n.id }, prof.perguntar ? {} : { perguntar: false });
}

/* ------------------------------------------------------------ o módulo de perguntas */

const ROTULO_MODO = { nao_sei: "Não sei", decida: "Decida por mim", depois: "Depois" };

function campoDaPergunta(q, d, i) {
  const nome = "q" + i;
  const sug = q.sugestao || "";
  if (q.tipo === "escolha" || q.tipo === "multipla") {
    return '<div class="ent-opcoes" role="' + (q.tipo === "escolha" ? "radiogroup" : "group") + '" aria-label="' + esc(q.pergunta) + '">' +
      (q.opcoes || []).map((o) => '<button type="button" class="ent-op" data-ent-op="' + esc(o) + '" aria-pressed="false">' + esc(o) +
        (o === sug ? ' <small class="ent-sug">sugerido</small>' : "") + "</button>").join("") + "</div>";
  }
  const lista = q.tipo === "parte" ? (d.cadastros || []) : q.tipo === "documento" ? (d.documentos || []) : [];
  const idLista = lista.length ? "ent-lista-" + esc(d.entrevista_id) + "-" + i : "";
  const datalist = lista.length ? '<datalist id="' + idLista + '">' + lista.map((n) => '<option value="' + esc(n) + '">').join("") + "</datalist>" : "";
  if (q.tipo === "texto_longo") return '<textarea class="ent-campo" name="' + nome + '" rows="3"></textarea>';
  if (q.tipo === "data") return '<input class="ent-campo ent-curto" type="date" name="' + nome + '">';
  if (q.tipo === "valor") {
    return '<span class="ent-valor"><span>R$</span><input class="ent-campo ent-curto" type="text" inputmode="decimal" name="' + nome +
      '" placeholder="0,00"></span>';
  }
  return '<input class="ent-campo" type="text" name="' + nome + '"' + (idLista ? ' list="' + idLista + '"' : "") +
    (q.tipo === "parte" ? ' placeholder="nome da pessoa ou empresa"' : q.tipo === "documento" ? ' placeholder="nome do documento no Acervo"' : "") +
    ">" + datalist;
}

function cartaoEntrevista(d) {
  const qs = d.perguntas || [];
  const cabeca = '<div class="proposta-topo"><span class="rotulo">' + (d.respondida ? "definido" : "antes de começar") + "</span>" +
    "<b>" + esc(d.titulo || "Vamos definir alguns pontos") + "</b>" +
    '<span class="ent-nivel">' + esc(d.nivel_nome || "") + (d.rodadas_max > 1 ? " · etapa " + (d.rodada || 1) + " de até " + d.rodadas_max : "") + "</span></div>";
  if (d.respondida) {
    const como = { continuar: "Seguiu com o que havia", decidir: "Pediu para eu decidir o que faltava", explicar: "Explicou com as próprias palavras" }[d.acao] || "Respondido";
    return '<div class="proposta entrevista respondida">' + cabeca +
      '<p class="explica">' + esc(como) + ". " + plural(qs.length, "ponto") + " nesta etapa.</p>" +
      '<ul class="ent-resumo">' + qs.map((q) => "<li>" + esc(q.pergunta) + "</li>").join("") + "</ul></div>";
  }
  const premissas = (d.premissas || []).length
    ? '<div class="ent-premissas"><small>Se você não disser outra coisa, vou assumir:</small><ul>' +
      d.premissas.map((p) => "<li>" + esc(p) + "</li>").join("") + "</ul></div>" : "";
  return '<div class="proposta entrevista" data-entrevista="' + esc(d.entrevista_id || "") + '">' + cabeca +
    (d.entendimento ? '<p class="explica ent-entendi">' + esc(d.entendimento) + "</p>" : "") +
    '<div class="ent-perguntas">' + qs.map((q, i) =>
      '<fieldset class="ent-q" data-ent-q="' + esc(q.id) + '" data-ent-tipo="' + esc(q.tipo) + '">' +
      '<legend class="ent-titulo">' + esc(q.pergunta) + "</legend>" +
      (q.porque ? '<small class="ent-porque">' + esc(q.porque) + "</small>" : "") +
      campoDaPergunta(q, d, i) +
      '<div class="ent-modos">' + Object.entries(ROTULO_MODO).map(([m, r]) =>
        '<button type="button" class="ent-modo" data-ent-modo="' + m + '" aria-pressed="false">' + esc(r) + "</button>").join("") +
      "</div></fieldset>").join("") + "</div>" +
    premissas +
    '<div class="ent-explicar" hidden><label class="ent-titulo" for="ent-exp-' + esc(d.entrevista_id) + '">Nas suas palavras</label>' +
    '<textarea class="ent-campo" id="ent-exp-' + esc(d.entrevista_id) + '" rows="3" placeholder="Conte o que importa neste trabalho — o que você souber, do jeito que vier."></textarea></div>' +
    '<p class="ent-dica">Você também pode só continuar conversando na caixa abaixo.</p>' +
    '<div class="linha-form ent-acoes">' +
    '<button class="primario" data-ent-acao="responder">Enviar respostas</button>' +
    '<button data-ent-acao="continuar" title="Executar agora, com o que já está definido">Continuar com o que temos</button>' +
    '<button data-ent-acao="decidir" title="Eu escolho a melhor solução para o que ficou em aberto, e digo o que escolhi">Decida por mim</button>' +
    '<button data-ent-acao="explicar">Quero explicar com minhas palavras</button>' +
    '<button data-ent-acao="depois">Responder depois</button></div></div>';
}

function respostasDoCartao(caixa, d) {
  const saida = [];
  (d.perguntas || []).forEach((q, i) => {
    const f = caixa.querySelector('[data-ent-q="' + CSS.escape(q.id) + '"]');
    if (!f) return;
    const modo = f.querySelector(".ent-modo.on");
    if (modo) { saida.push({ id: q.id, modo: modo.dataset.entModo, resposta: "" }); return; }
    if (q.tipo === "escolha" || q.tipo === "multipla") {
      const marcadas = Array.from(f.querySelectorAll(".ent-op.on")).map((b) => b.dataset.entOp);
      if (marcadas.length) saida.push({ id: q.id, modo: "valor", resposta: q.tipo === "escolha" ? marcadas[0] : marcadas });
      return;
    }
    const campo = f.querySelector('[name="q' + i + '"]');
    let v = campo ? campo.value.trim() : "";
    if (v && q.tipo === "valor") v = "R$ " + v;
    if (v && q.tipo === "data") { const [a, m, dd] = v.split("-"); if (dd) v = dd + "/" + m + "/" + a; }
    if (v) saida.push({ id: q.id, modo: "valor", resposta: v });
  });
  return saida;
}

function resumoDasRespostas(d, respostas, explicacao, acao) {
  const porId = Object.fromEntries((d.perguntas || []).map((q) => [q.id, q]));
  const linhas = respostas.map((r) => {
    const q = porId[r.id];
    if (!q) return "";
    const v = r.modo === "valor" ? (Array.isArray(r.resposta) ? r.resposta.join(", ") : r.resposta) : ROTULO_MODO[r.modo].toLowerCase();
    return q.pergunta + " — " + v;
  }).filter(Boolean);
  if (explicacao) linhas.push(explicacao);
  if (acao === "continuar") linhas.push("Pode continuar com o que temos.");
  if (acao === "decidir") linhas.push("Decida por mim o que faltar.");
  return linhas.join("\n") || "Pode continuar com o que temos.";
}

function ligarEntrevista(caixa, d) {
  if (d.respondida) return;
  caixa.querySelectorAll(".ent-q").forEach((f) => {
    const tipo = f.dataset.entTipo;
    const limparModo = () => f.querySelectorAll(".ent-modo").forEach((m) => { m.classList.remove("on"); m.setAttribute("aria-pressed", "false"); });
    f.querySelectorAll(".ent-op").forEach((b) => {
      b.onclick = () => {
        limparModo();
        const ligar = !b.classList.contains("on");
        if (tipo === "escolha") f.querySelectorAll(".ent-op").forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); });
        b.classList.toggle("on", ligar);
        b.setAttribute("aria-pressed", String(ligar));
      };
    });
    f.querySelectorAll(".ent-campo").forEach((c) => { c.addEventListener("input", () => { if (c.value.trim()) limparModo(); }); });
    f.querySelectorAll(".ent-modo").forEach((m) => {
      m.onclick = () => {
        const ligar = !m.classList.contains("on");
        limparModo();
        if (ligar) {
          m.classList.add("on");
          m.setAttribute("aria-pressed", "true");
          f.querySelectorAll(".ent-op").forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); });
        }
      };
    });
  });
  const explicar = caixa.querySelector(".ent-explicar");
  const area = explicar ? explicar.querySelector("textarea") : null;
  caixa.querySelectorAll("[data-ent-acao]").forEach((b) => {
    b.onclick = () => {
      const acao = b.dataset.entAcao;
      if (acao === "explicar") {
        explicar.hidden = !explicar.hidden;
        if (!explicar.hidden && area) area.focus();
        return;
      }
      if (acao === "depois") {
        caixa.querySelector(".proposta").classList.add("adiada");
        b.closest(".ent-acoes").insertAdjacentHTML("beforebegin",
          '<p class="nota ent-adiada">Fica para depois. Quando quiser, responda aqui mesmo — ou escreva na caixa.</p>');
        b.remove();
        return;
      }
      if (estado.ocupado) { avisoCert("espere a resposta de agora terminar"); return; }
      const respostas = respostasDoCartao(caixa, d);
      const explicacao = area && !explicar.hidden ? area.value.trim() : (area ? area.value.trim() : "");
      if (acao === "responder" && !respostas.length && !explicacao) {
        avisoCert("responda ao menos um ponto, ou escolha “Continuar com o que temos”");
        return;
      }
      caixa.querySelectorAll("button, input, textarea").forEach((x) => { x.disabled = true; });
      caixa.querySelector(".proposta").classList.add("enviada");
      enviar({ texto: resumoDasRespostas(d, respostas, explicacao, acao),
        entrevista: { id: d.entrevista_id, acao: acao, respostas: respostas, explicacao: explicacao } });
    };
  });
}

/* ------------------------------------------------------------ o trabalho pronto */

function cartaoLevarAoEditor(d) {
  const rev = d.revisao || {};
  const problemas = rev.problemas || [];
  const conferir = d.conferir || [];
  const etapas = (d.etapas || []).map((e) => ({ analise: "analisei riscos", plano: "planejei", redacao: "redigi", revisao: "revisei",
    reescrita: "reescrevi com as correções" }[e] || e));
  let html = '<div class="proposta trabalho-pronto"><div class="proposta-topo"><span class="rotulo">trabalho pronto</span>' +
    "<b>" + esc(d.titulo || "") + "</b>" + (d.nivel_nome ? '<span class="ent-nivel">' + esc(d.nivel_nome) + "</span>" : "") + "</div>";
  if (etapas.length) html += '<p class="explica">' + esc(etapas.join(", ").replace(/^./, (c) => c.toUpperCase())) + ".</p>";
  if (problemas.length) {
    html += '<details class="ent-revisao"><summary>' + (rev.refeito ? "A revisão apontou " + plural(problemas.length, "ponto") + " — corrigi os importantes"
      : "A revisão sugeriu " + plural(problemas.length, "ajuste") + " fino" + (problemas.length > 1 ? "s" : "")) + "</summary><ul>" +
      problemas.map((p) => '<li><span class="ent-grav ' + esc(p.gravidade) + '">' + esc(p.gravidade) + "</span> " +
        (p.onde ? "<b>" + esc(p.onde) + ":</b> " : "") + esc(p.o_que) + "</li>").join("") + "</ul></details>";
  }
  if (conferir.length) {
    html += '<details class="ent-revisao"><summary>Confira ' + plural(conferir.length, "citação", "citações") +
      " que não achei na base de leis</summary><ul>" + conferir.map((c) => "<li>" + esc(c) + "</li>").join("") + "</ul></details>";
  }
  // A conferência automática só alcança os códigos da Biblioteca; lei de fora
  // dela (Estatuto da Terra, decretos) o modelo pode citar com o número errado.
  html += '<p class="nota ent-confira">Confira os dispositivos citados antes de usar: a conferência automática cobre só os ' +
    "códigos da Biblioteca, e o número de um artigo de outra lei pode vir errado.</p>";
  return html + '<div class="linha-form"><button class="primario com-icone" data-levar-editor="1">' + ic("edit_document", 15) +
    "Abrir no editor</button></div></div>";
}

function ligarLevarAoEditor(caixa, d) {
  const b = caixa.querySelector("[data-levar-editor]");
  if (!b) return;
  b.onclick = async () => {
    b.disabled = true;
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "levar_ao_editor", campos: { titulo: d.titulo || "" } }),
    });
    if (!r.ok) { b.disabled = false; avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const feito = await r.json();
    b.disabled = false;
    if (typeof fazerDoCartaoDoEditor === "function") fazerDoCartaoDoEditor(caixa, feito.proposta);
  };
}
