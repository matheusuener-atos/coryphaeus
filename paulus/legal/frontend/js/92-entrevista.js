/* Profundidade jurídica e conversa modular (src/profundidade.py,
   src/entrevista.py, src/elaboracao.py - 03/10/2026).

   - A caixa da pergunta: a pílula do nível (Estagiário → Bacharel → Advogado
     → Juiz → Ministro). A pessoa escolhe o quanto quer que o Paulus
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
  // O nivel guardado que o plano nao tem mais (bloqueado) volta ao padrao.
  const n = prof.niveis.find((x) => x.id === id && !x.bloqueado);
  return n || prof.niveis.find((x) => x.id === prof.padrao) || null;
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
    : "Profundidade: " + (n ? n.nome + " — " + n.resumo : "") + ". Clique para escolher o quanto o Paulus trabalha.";
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
  menu.innerHTML = '<div class="mp-cabeca"><b>Quanto o Paulus trabalha este pedido</b>' +
    "<small>Você escolhe o esforço; o modelo e as etapas são por conta do programa.</small></div>" +
    prof.niveis.map((n, i) =>
      '<button type="button" role="menuitemradio" class="mp-nivel' + (atual && atual.id === n.id ? " on" : "") + (n.bloqueado ? " travado" : "") +
      '" aria-checked="' + Boolean(atual && atual.id === n.id) + '"' + (n.bloqueado ? ' aria-disabled="true" title="' + esc(n.no_plano || "") + '"' : "") +
      ' data-prof-nivel="' + esc(n.id) + '">' +
      '<span class="mp-degrau" aria-hidden="true">' + "▮".repeat(i + 1) + '<span class="mp-vazio">' + "▮".repeat(4 - i) + "</span></span>" +
      '<span class="mp-texto"><b>' + esc(n.nome) + (n.id === prof.padrao ? ' <em>padrão</em>' : "") + "</b>" +
      "<span>" + esc(n.resumo) + "</span>" +
      (n.bloqueado ? '<small class="mp-plano">' + ic("key", 13) + " " + esc(n.no_plano || "Não faz parte do seu plano.") + "</small>" : "") +
      '<small class="mp-tecnico">' + esc((n.detalhes || []).join(" · ")) + " · consome ~" +
      esc(String(n.consumo).replace(".", ",")) + "× da franquia</small></span></button>").join("") +
    '<label class="mp-perguntar"><input type="checkbox" data-prof-perguntar="1"' + (prof.perguntar ? " checked" : "") + ">" +
    "<span><b>Entender antes de trabalhar</b><small>Em pedidos de trabalho (contrato, petição, parecer…), o Paulus " +
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
      if (x.classList.contains("travado")) return;
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
  // Muitas opções de uma escolha só: a lista suspensa.
  if (q.tipo === "lista") {
    return '<select class="ent-campo ent-curto ent-lista" name="' + nome + '"><option value="">Escolha…</option>' +
      (q.opcoes || []).map((o) => '<option value="' + esc(o) + '">' + esc(o) + (o === sug ? " (sugerido)" : "") + "</option>").join("") +
      "</select>";
  }
  // A premissa para confirmar: um interruptor. Sem mexer, não é resposta.
  if (q.tipo === "confirmacao") {
    return '<label class="ent-switch"><input type="checkbox" role="switch" name="' + nome + '">' +
      '<span class="ent-trilho" aria-hidden="true"></span><span class="ent-afirmacao">' + esc(q.afirmacao || q.pergunta) + "</span></label>";
  }
  if (q.tipo === "data") return '<input class="ent-campo ent-curto" type="date" name="' + nome + '">';
  // Dinheiro com "R$" na frente; quantidade com a unidade depois (ha, sacas/ha,
  // anos...). Sem unidade conhecida, o campo fica sem rótulo.
  if (q.tipo === "valor") {
    return '<span class="ent-valor"><span>R$</span><input class="ent-campo ent-curto" type="text" inputmode="decimal" name="' + nome +
      '" placeholder="0,00"></span>';
  }
  if (q.tipo === "numero") {
    return '<span class="ent-valor"><input class="ent-campo ent-curto" type="text" inputmode="decimal" name="' + nome + '">' +
      (q.unidade ? "<span>" + esc(q.unidade) + "</span>" : "") + "</span>";
  }
  const campo = '<input class="ent-campo" type="text" name="' + nome + '"' + (idLista ? ' list="' + idLista + '"' : "") +
    (q.tipo === "parte" ? ' placeholder="nome como está nos Cadastros, ou o nome da pessoa"' : q.tipo === "documento" ? ' placeholder="nome do documento no Acervo"' : "") +
    ">" + datalist;
  // A pessoa: a ficha dos Cadastros qualifica a parte (src/redacao.py); a linha diz se achou.
  if (q.tipo === "parte") return campo + '<small class="ent-ficha" aria-live="polite"></small>';
  // O documento: do Acervo pelo nome, ou anexado agora, sem sair da pergunta.
  if (q.tipo === "documento") {
    return '<span class="ent-doc">' + campo + '<button type="button" class="com-icone" data-ent-anexar="1">' + ic("attach_file", 15) +
      "Anexar arquivo</button></span>";
  }
  return campo;
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
    if (q.tipo === "confirmacao") {
      if (campo && campo.dataset.tocado) {
        saida.push({ id: q.id, modo: "valor", resposta: (campo.checked ? "Confirmo: " : "Não confirmo: ") + (q.afirmacao || q.pergunta) });
      }
      return;
    }
    let v = campo ? campo.value.trim() : "";
    if (v && q.tipo === "valor" && !/R\$/i.test(v)) v = "R$ " + v;
    // "410" com a unidade "ha" vira "410 ha"; quem já escreveu a unidade (ou outra) fica como escreveu.
    if (v && q.tipo === "numero" && q.unidade && /^[\d.,\s]+$/.test(v)) v = v + " " + q.unidade;
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
    f.querySelectorAll(".ent-campo").forEach((c) => {
      c.addEventListener("input", () => { if (c.value.trim()) limparModo(); });
      c.addEventListener("change", () => { if (c.value.trim()) limparModo(); });
    });
    const interruptor = f.querySelector('.ent-switch input');
    if (interruptor) interruptor.onchange = () => { interruptor.dataset.tocado = "1"; limparModo(); };
    // A ficha da pessoa: achou nos Cadastros, a qualificação sai dela.
    const ficha = f.querySelector(".ent-ficha");
    if (ficha) {
      const entrada = f.querySelector("input");
      const nomes = new Set((d.cadastros || []).map((n) => n.toLowerCase()));
      const dizer = () => {
        const v = entrada.value.trim();
        ficha.textContent = !v ? "" : nomes.has(v.toLowerCase())
          ? "Está nos Cadastros: a qualificação sai da ficha (CPF ou CNPJ e endereço)."
          : "Não está nos Cadastros: entra o nome, e o resto da qualificação fica [●].";
        ficha.classList.toggle("ok", nomes.has(v.toLowerCase()));
      };
      entrada.addEventListener("input", dizer);
      entrada.addEventListener("change", dizer);
    }
    // Anexar um arquivo para esta pergunta: o pop-up de sempre, e o nome volta para o campo.
    const anexar = f.querySelector("[data-ent-anexar]");
    if (anexar) {
      anexar.onclick = () => {
        if (typeof abrirAnexar !== "function") return;
        abrirAnexar({ titulo: "Anexar para: " + (f.querySelector(".ent-titulo") || {}).textContent, verbo: "Usar",
          aoAnexar: (nomes) => {
            if (!nomes || !nomes.length) return;
            const entrada = f.querySelector("input");
            const atuais = entrada.value.split(",").map((x) => x.trim()).filter(Boolean);
            entrada.value = [...new Set(atuais.concat(nomes))].join(", ");
            limparModo();
          } });
      };
    }
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

/* ------------------------------------------------------------ a pílula do agente

   O agente da próxima pergunta (A2) saiu da barra de cima da caixa e virou
   pílula dentro dela, como a profundidade: o nome do agente (o escolhido, ou
   o que a regra sugeriu pelo pedido), e o menu com "Sem agente" e os
   ativos. Sem agente ativo no escritório, a pílula não aparece. */
function desenharPilulaAgente() {
  const ativos = estado.agentesAtivos || [];
  let b = document.getElementById("pilula-agente");
  if (!ativos.length) { if (b) b.remove(); return; }
  if (!b) {
    const ancora = document.getElementById("pilula-profundidade") || document.getElementById("pilula-nuvem") || document.getElementById("ditar");
    if (!ancora) return;
    b = document.createElement("button");
    b.type = "button";
    b.id = "pilula-agente";
    b.className = "pilula pilula-agente";
    b.setAttribute("aria-haspopup", "menu");
    b.onclick = (e) => { e.stopPropagation(); document.getElementById("menu-agente") ? fecharMenuAgente() : abrirMenuAgente(); };
    ancora.parentNode.insertBefore(b, ancora);
  }
  const vez = typeof agenteDaVez === "function" ? agenteDaVez() : null;
  const revisao = !vez && !estado.agenteDecisao && (estado.agentesEmRevisao || []).length;
  b.classList.toggle("ativa", Boolean(vez));
  b.title = vez ? "Agente da próxima pergunta: " + vez.nome + (estado.agenteDecisao ? "" : " (escolhido pelo pedido)") + ". Clique para trocar."
    : revisao ? "“" + estado.agentesEmRevisao[0].nome + "” precisa de revisão: não escolhi sozinho. Clique para escolher."
      : "Sem agente. Clique para escolher um agente do escritório.";
  b.innerHTML = ic("hub", 18) + '<span class="rotulo-botao">' + esc(vez ? vez.nome : "Agente") + "</span>" +
    (revisao ? '<span class="pilula-alerta" data-barra-revisao="1" aria-label="agente precisa de revisão"></span>' : "");
}

function abrirMenuAgente() {
  fecharMenuAgente();
  const b = document.getElementById("pilula-agente");
  if (!b) return;
  const ativos = estado.agentesAtivos || [];
  const vez = typeof agenteDaVez === "function" ? agenteDaVez() : null;
  const menu = document.createElement("div");
  menu.id = "menu-agente";
  menu.className = "menu-profundidade";
  menu.setAttribute("role", "menu");
  menu.setAttribute("data-barra-agente", "1");
  const item = (slug, nome, extra, on) => '<button type="button" role="menuitemradio" class="mp-nivel' + (on ? " on" : "") +
    '" aria-checked="' + on + '" data-agente-op="' + esc(slug) + '"><span class="mp-texto"><b>' + esc(nome) + "</b>" +
    (extra ? "<span>" + esc(extra) + "</span>" : "") + "</span></button>";
  menu.innerHTML = '<div class="mp-cabeca"><b>Agente da próxima pergunta</b><small>Sem escolher, o Paulus usa o agente que o pedido indicar.</small></div>' +
    item("nenhum", "Sem agente", "", !vez) +
    ativos.map((a) => item(a.slug, a.nome, a.precisa_revisao ? "precisa de revisão" : (a.descricao || ""), Boolean(vez && vez.slug === a.slug))).join("");
  document.body.appendChild(menu);
  const r = b.getBoundingClientRect();
  const largura = Math.min(340, window.innerWidth - 16);
  menu.style.width = largura + "px";
  menu.style.left = Math.max(8, Math.min(r.left, window.innerWidth - largura - 8)) + "px";
  const acima = r.top - 16, abaixo = window.innerHeight - r.bottom - 16;
  menu.style.maxHeight = Math.max(160, Math.min(520, Math.max(acima, abaixo))) + "px";
  const altura = menu.offsetHeight;
  menu.style.top = (acima >= altura || acima >= abaixo ? Math.max(8, r.top - altura - 8) : r.bottom + 8) + "px";
  b.setAttribute("aria-expanded", "true");
  menu.querySelectorAll("[data-agente-op]").forEach((x) => {
    x.onclick = () => {
      estado.agenteDecisao = x.dataset.agenteOp || "nenhum";
      fecharMenuAgente();
      desenharPilulaAgente();
      const p = document.getElementById("pedido");
      if (p) p.focus();
    };
  });
}

function fecharMenuAgente() {
  const m = document.getElementById("menu-agente");
  if (m) m.remove();
  const b = document.getElementById("pilula-agente");
  if (b) b.setAttribute("aria-expanded", "false");
}

document.addEventListener("click", (e) => {
  if (document.getElementById("menu-agente") && !e.target.closest("#menu-agente") && !e.target.closest("#pilula-agente")) fecharMenuAgente();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharMenuAgente(); });

/* ------------------------------------------------------------ cláusula por cláusula (src/clausulas.py)

   "Antes de começar": o plano das cláusulas, as leis de que o trabalho
   depende (na Biblioteca, ou falta - anexe o texto ou siga sem ela) e o
   modelo já feito (anexe, ou escolha um do Acervo). Começar redige a
   qualificação das partes; "Fazer tudo de uma vez" pode, e diz o que se perde.

   Cada cláusula chega com Aprovar e Corrigir. Corrigir abre os pontos que a
   própria cláusula deixou ajustáveis (o que foi escolhido e as alternativas)
   e um campo livre. No fim, o documento compilado. */

const FRASE_HONESTA = "Dá para fazer tudo de uma vez. Com honestidade: sem a sua aprovação em cada cláusula, o que estiver " +
  "fora da sua estratégia só aparece no fim, e o texto feito de uma vez costuma sair menos cuidadoso.";

function pluralUnidade(n, u) {
  return plural(n, u, u === "cláusula" ? "cláusulas" : "seções");
}

function cartaoPreparo(d) {
  const u = d.unidade || "cláusula";
  const leis = (d.leis || []).map((l) => "<li>" + esc(l.nome) + ' <span class="cl-estado ' + (l.na_biblioteca ? "ok" : "falta") + '">' +
    (l.na_biblioteca ? "na Biblioteca" : "falta o texto") + "</span></li>").join("");
  const faltam = (d.leis || []).filter((l) => !l.na_biblioteca).length;
  if (d.respondida) {
    return '<div class="proposta preparo respondida"><div class="proposta-topo"><span class="rotulo">plano</span><b>' + esc(d.titulo || "") +
      '</b><span class="ent-nivel">' + pluralUnidade((d.secoes || []).length, u) + "</span></div></div>";
  }
  return '<div class="proposta preparo"><div class="proposta-topo"><span class="rotulo">antes de começar</span><b>' + esc(d.titulo || "") +
    '</b><span class="ent-nivel">' + esc(d.nivel_nome || "") + "</span></div>" +
    '<details class="cl-plano"><summary>O plano: ' + pluralUnidade((d.secoes || []).length, u) +
    "</summary><ol>" + (d.secoes || []).map((s) => "<li>" + esc(s) + "</li>").join("") + "</ol></details>" +
    (leis ? '<div class="cl-bloco"><b>As leis deste trabalho</b><ul class="cl-leis">' + leis + "</ul>" +
      (faltam ? "<small>Anexe o texto da lei que falta (o PDF ou a página do Planalto) e eu fundamento cada " + esc(u) +
        " nele. Sem ela, sigo pelo que sei, e as citações dela ficam para você conferir.</small>" : "") + "</div>" : "") +
    '<div class="cl-bloco"><b>Um modelo já feito</b><small>Se você tiver um modelo deste trabalho, anexe: ajuda a entender o que deve ' +
    "ser feito (eu sigo a estrutura dele, sem copiar dados).</small>" +
    ((d.modelos_acervo || []).length ? '<div class="ent-opcoes cl-modelos">' + d.modelos_acervo.map((n) =>
      '<button type="button" class="ent-op" data-cl-modelo="' + esc(n) + '" aria-pressed="false" title="' + esc(n) + '">Usar “' +
      esc(nomeCurto(n)) + "”</button>").join("") + "</div>" : "") + "</div>" +
    '<div class="linha-form ent-acoes"><button class="primario" data-cl="comecar">Começar pela qualificação das partes</button>' +
    '<button class="com-icone" data-cl="anexar">' + ic("attach_file", 15) + "Anexar lei ou modelo</button>" +
    '<button data-cl="tudo">Fazer tudo de uma vez</button></div>' +
    '<p class="nota cl-honesta">' + esc(FRASE_HONESTA) + "</p></div>";
}

function ligarPreparo(caixa, d) {
  if (d.respondida) return;
  caixa.querySelectorAll("[data-cl-modelo]").forEach((b) => {
    b.onclick = () => { const on = !b.classList.contains("on"); b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); };
  });
  const anexar = caixa.querySelector('[data-cl="anexar"]');
  if (anexar) {
    anexar.onclick = () => {
      if (typeof abrirAnexar !== "function") return;
      abrirAnexar({ titulo: "Anexar a lei ou um modelo", verbo: "Usar", aoAnexar: (nomes) => {
        let grupo = caixa.querySelector(".cl-modelos");
        if (!grupo) {
          caixa.querySelectorAll(".cl-bloco")[caixa.querySelectorAll(".cl-bloco").length - 1]
            .insertAdjacentHTML("beforeend", '<div class="ent-opcoes cl-modelos"></div>');
          grupo = caixa.querySelector(".cl-modelos");
        }
        (nomes || []).forEach((n) => {
          if (grupo.querySelector('[data-cl-modelo="' + CSS.escape(n) + '"]')) return;
          grupo.insertAdjacentHTML("beforeend", '<button type="button" class="ent-op on" data-cl-modelo="' + esc(n) +
            '" aria-pressed="true" title="' + esc(n) + '">' + ic("attach_file", 14) + esc(nomeCurto(n)) + "</button>");
          const b = grupo.lastElementChild;
          b.onclick = () => { const on = !b.classList.contains("on"); b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); };
        });
      } });
    };
  }
  caixa.querySelectorAll('[data-cl="comecar"], [data-cl="tudo"]').forEach((b) => {
    b.onclick = () => {
      if (estado.ocupado) { avisoCert("espere a resposta de agora terminar"); return; }
      const modelos = Array.from(caixa.querySelectorAll("[data-cl-modelo].on")).map((x) => x.dataset.clModelo);
      const tudo = b.dataset.cl === "tudo";
      caixa.querySelectorAll("button").forEach((x) => { x.disabled = true; });
      const c = caixa.querySelector(".proposta");
      if (c) c.classList.add("respondida");
      enviar({ texto: tudo ? "Faça tudo de uma vez." : "Pode começar pela qualificação das partes.",
        entrevista: { id: d.entrevista_id, acao: tudo ? "tudo" : "comecar", modelos: modelos } });
    };
  });
}

function cartaoClausula(d) {
  const u = d.unidade || "cláusula";
  const topo = '<div class="proposta-topo"><span class="rotulo">' + esc(u) + " " + (Number(d.indice) + 1) + " de " + esc(String(d.total)) +
    "</span><b>" + esc(d.titulo || "") + "</b>" + (d.versao > 1 ? '<span class="ent-nivel">versão ' + d.versao + "</span>" : "") + "</div>";
  if (d.respondida) {
    const como = { aprovar: "aprovada", corrigir: "corrigida abaixo", tudo: "o resto foi feito de uma vez" }[d.acao] || "respondida";
    return '<div class="proposta clausula respondida">' + topo + '<p class="explica">' + esc(como) + ".</p></div>";
  }
  const pontos = (d.pontos || []).map((p, i) =>
    '<fieldset class="ent-q" data-cl-ponto="' + i + '"><legend class="ent-titulo">' + esc(p.ponto) + "</legend>" +
    (p.atual ? '<small class="ent-porque">Agora: ' + esc(p.atual) + "</small>" : "") +
    ((p.alternativas || []).length ? '<div class="ent-opcoes">' + p.alternativas.map((a) =>
      '<button type="button" class="ent-op" data-cl-alt="' + esc(a) + '" aria-pressed="false">' + esc(a) + "</button>").join("") + "</div>" : "") +
    '<input class="ent-campo" type="text" placeholder="ou escreva como prefere"></fieldset>').join("");
  const idPedido = "cl-pedido-" + esc(d.secao) + "-" + d.versao;
  return '<div class="proposta clausula" data-clausula="' + esc(d.secao) + '">' + topo +
    (d.aviso ? '<p class="nota cl-aviso">' + esc(d.aviso) + "</p>" : "") +
    '<div class="linha-form ent-acoes"><button class="primario" data-cl="aprovar">Aprovar' +
    (Number(d.indice) + 1 < d.total ? " e seguir" : " e compilar") + "</button>" +
    '<button data-cl="corrigir">Corrigir</button><button data-cl="tudo">Fazer o resto de uma vez</button></div>' +
    '<div class="cl-corrigir" hidden>' + (pontos ? '<div class="ent-perguntas">' + pontos + "</div>" : "") +
    '<label class="ent-titulo" for="' + idPedido + '">Outro ajuste</label>' +
    '<textarea class="ent-campo" id="' + idPedido + '" rows="3" placeholder="Diga com as suas palavras o que mudar nesta ' + esc(u) + '."></textarea>' +
    '<div class="linha-form"><button class="primario" data-cl="refazer">Refazer a ' + esc(u) + "</button></div></div>" +
    '<p class="nota cl-honesta" hidden>' + esc(FRASE_HONESTA) +
    ' <button type="button" class="sv-ligacao" data-cl="tudo-mesmo">Fazer o resto de uma vez</button></p></div>';
}

function ligarClausula(caixa, d) {
  if (d.respondida) return;
  const travar = () => {
    caixa.querySelectorAll("button, input, textarea").forEach((x) => { x.disabled = true; });
    const c = caixa.querySelector(".proposta");
    if (c) c.classList.add("respondida");
  };
  const livre = () => { if (estado.ocupado) { avisoCert("espere a resposta de agora terminar"); return false; } return true; };
  caixa.querySelectorAll(".ent-q").forEach((f) => {
    const campo = f.querySelector("input");
    f.querySelectorAll("[data-cl-alt]").forEach((b) => {
      b.onclick = () => {
        const on = !b.classList.contains("on");
        f.querySelectorAll("[data-cl-alt]").forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); });
        b.classList.toggle("on", on);
        b.setAttribute("aria-pressed", String(on));
        if (on && campo) campo.value = "";
      };
    });
    if (campo) campo.addEventListener("input", () => f.querySelectorAll("[data-cl-alt]").forEach((x) => x.classList.remove("on")));
  });
  caixa.querySelectorAll("[data-cl]").forEach((b) => {
    b.onclick = () => {
      const qual = b.dataset.cl;
      if (qual === "corrigir") {
        const f = caixa.querySelector(".cl-corrigir");
        f.hidden = !f.hidden;
        if (!f.hidden) { const t = f.querySelector("textarea"); if (t) t.focus(); }
        return;
      }
      if (qual === "tudo") { caixa.querySelector(".cl-honesta").hidden = false; return; }
      if (!livre()) return;
      if (qual === "aprovar") {
        travar();
        enviar({ texto: "Aprovada: " + (d.titulo || ""), entrevista: { id: d.entrevista_id, acao: "aprovar", secao: d.secao } });
      } else if (qual === "tudo-mesmo") {
        travar();
        enviar({ texto: "Faça o resto de uma vez.", entrevista: { id: d.entrevista_id, acao: "tudo" } });
      } else if (qual === "refazer") {
        const pontos = [];
        caixa.querySelectorAll("[data-cl-ponto]").forEach((f) => {
          const p = (d.pontos || [])[Number(f.dataset.clPonto)];
          const alt = f.querySelector("[data-cl-alt].on");
          const escrito = ((f.querySelector("input") || {}).value || "").trim();
          const escolha = alt ? alt.dataset.clAlt : escrito;
          if (p && escolha) pontos.push({ ponto: p.ponto, escolha: escolha });
        });
        const pedido = ((caixa.querySelector(".cl-corrigir textarea") || {}).value || "").trim();
        if (!pontos.length && !pedido) { avisoCert("escolha um ponto ou escreva o ajuste"); return; }
        travar();
        const resumo = ["Corrigir " + (d.titulo || "") + ":"].concat(pontos.map((p) => p.ponto + " — " + p.escolha), pedido ? [pedido] : []).join("\n");
        enviar({ texto: resumo, entrevista: { id: d.entrevista_id, acao: "corrigir", secao: d.secao, pontos: pontos, pedido: pedido } });
      }
    };
  });
}
