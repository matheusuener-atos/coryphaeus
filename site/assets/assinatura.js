/* A pagina dos planos (paulus.ia.br/assinatura): os planos em cards, por mes
   ou por ano. Os numeros (preco, creditos, pessoas, modelo, limites) vem do
   Worker (worker/ia.js, /api/ia/planos); os textos de cada item, daqui. O
   botao do plano escolhido leva ao cadastro (/cadastro?plano=&periodo=), onde
   se entra com o Google e se preenchem os dados do escritorio. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var pedido = new URLSearchParams(location.search);
  var estado = { planos: [], escolhido: pedido.get("plano") || "escritorio", periodo: pedido.get("periodo") === "anual" ? "anual" : "mensal", aberto: {} };

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function milhoes(t) { return (t / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões de créditos"; }
  function brlFino(v) { return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: Number(v) % 1 ? 2 : 0, maximumFractionDigits: 2 }); }

  var NIVEL = { estagiario: "Estagiário", bacharel: "Bacharel", advogado: "Advogado", juiz: "Juiz", ministro: "Ministro" };
  var PARA = { advogado: "Para quem advoga sozinho.", escritorio: "Para escritórios com equipe.", plus: "Para escritórios que querem a melhor IA do mercado." };
  var HERANCA = { escritorio: "Tudo do Advogado, e mais", plus: "Tudo do Escritório, e mais" };
  // O plano que a pagina recomenda (a faixa). "Recomendado", e nao "mais
  // escolhido": a pagina so diz o que e verdade.
  var RECOMENDADO = "escritorio";

  /* Os itens de cada plano: [titulo, o que abre]. Os numeros (creditos,
     pessoas, NFS-e, agentes, profundidade, o modelo) vem do Worker; o texto e
     daqui. "(em breve)" no texto marca o que ainda nao existe. Plano que o
     Worker tiver e esta lista nao, mostra so os numeros. */
  function itensDoPlano(p) {
    var r = p.recursos || {};
    var modelos = p.modelos_info || [];
    var empresas = modelos.map(function (m) { return m.empresa; }).filter(function (e, i, l) { return l.indexOf(e) === i; });
    var ia = ["IA " + modelos.map(function (m) { return m.nome; }).join(" e ") + (empresas.length ? ", da " + empresas.join(" e da ") : ""),
      "Com " + milhoes(p.tokens) + " por mês, liberados por semana." + (r.profundidade ? " Profundidade até " + (NIVEL[r.profundidade] || r.profundidade) + "." : "") +
      // worker/ia.js, primeiraSemanaAte: nos 7 primeiros dias, so o modelo principal.
      (modelos.length > 1 ? " Nos 7 primeiros dias da assinatura, responde só o " + modelos[0].nome + "; o " + modelos.slice(1).map(function (m) { return m.nome; }).join(" e o ") + " libera no 8º dia." : "")];
    var pessoas = p.pessoas > 1 ? ["Até " + p.pessoas + " pessoas", "Cada uma com login Google, código no celular, permissões próprias, e-mail e agenda próprios." +
      (r.consumo_por_pessoa ? " Consumo de IA por pessoa, com limite definido por você." : "")] : null;
    var nfse = r.nfse_mes === null ? ["NFS-e sem limite", "Nota fiscal de serviço nacional" + (r.nfse_recorrente ? ", com notas recorrentes." : ".")]
      : r.nfse_mes > 0 ? ["Nota fiscal de serviço", "NFS-e nacional: até " + r.nfse_mes + " por mês." + (r.horas ? " Horas por serviço que viram cobrança no financeiro." : "")] : null;
    var agentes = r.agentes ? ["Até " + r.agentes + " agentes personalizados", "Agentes com as suas instruções, para tarefas que se repetem."]
      : r.agentes === null && r.autonomia ? ["Agentes sem limite", "Inclusive o que faz sozinho tarefas de vários passos."] : null;
    var porPlano = {
      advogado: [ia,
        ["Converse com os seus documentos", "Toda resposta mostra o trecho de onde saiu. Prazos, valores e partes lidos sozinhos dos documentos, inclusive de PDF escaneado. Foto de documento pelo celular, que vira PDF pesquisável."],
        ["Processos, prazos e intimações", "Pastas de processo com etapas, e os prazos entram na Agenda. Intimações do DJEN pela sua OAB, todo dia, com o prazo contado em dias úteis."],
        ["Agenda, e-mail e reuniões", "Agenda, tarefas, Google Agenda e Google Meet. E-mail: acompanha a caixa, acha prazos e traduz mensagens."],
        ["Clientes e financeiro", "Cadastro de clientes e financeiro, com relatórios em PDF e Excel."],
        ["Editores e assinatura digital", "Editor de peças, planilha com fórmulas em português e editor de PDF. Assinatura digital com certificado A1."],
        ["Biblioteca jurídica", "Constituição, 11 códigos, súmulas e temas do STJ, e a sua posição sobre cada artigo."],
        agentes,
        ["Acesso pelo celular", "De qualquer lugar, no seu endereço nome.paulus.ia.br."],
        ["Nada sai sem a sua aprovação", "Nada sai do programa sem a sua aprovação. Backup, WhatsApp, foco e bem-estar."]],
      escritorio: [ia, pessoas, nfse,
        r.datajud ? ["Processos no DataJud", "Processos acompanhados no DataJud todo dia. A IA explicando cada movimentação do processo (em breve)."] : null,
        r.gravacao ? ["Gravação de reuniões", "Com transcrição no seu computador e resumo."] : null,
        r.muralha ? ["Alerta de conflito de interesses", "Alerta de conflito de interesses entre clientes."] : null,
        agentes,
        r.jurisprudencia_stj ? ["Jurisprudência completa do STJ", "No seu computador."] : null],
      plus: [ia, pessoas,
        r.word ? ["Assistente dentro do Word", "Nos documentos criados pelo PAVLVS."] : null,
        nfse,
        r.ao_vivo ? ["Reuniões e cliente", "Sugestões jurídicas ao vivo durante a reunião. Página para o seu cliente acompanhar o processo (em breve)."] : null,
        r.mcp ? ["Conexão com outras IAs pelo MCP", "Conecte o PAVLVS a outras IAs e ferramentas pelo protocolo MCP."] : null,
        ["Implantação assistida", "Implantação assistida e suporte prioritário."]],
    };
    return (porPlano[p.id] || [ia, pessoas, nfse, agentes]).filter(Boolean);
  }

  function valorDe(p) { return estado.periodo === "anual" ? p.valor_anual : p.valor; }

  /* "3 meses grátis": quantos meses inteiros o anual poupa (o menor entre os planos). */
  function mesesGratis() {
    var m = estado.planos.map(function (p) { return Math.floor((p.valor * 12 - p.valor_anual) / p.valor); });
    return m.length ? Math.min.apply(null, m) : 0;
  }

  function desenharPeriodo() {
    ["mensal", "anual"].forEach(function (x) {
      var b = $("cd-periodo-" + x);
      b.setAttribute("aria-checked", String(estado.periodo === x));
      b.classList.toggle("on", estado.periodo === x);
    });
    var gratis = mesesGratis();
    $("cd-selo-anual").textContent = gratis > 0 ? gratis + (gratis === 1 ? " mês grátis" : " meses grátis") : "";
  }

  function cartao(p, on) {
    var anual = estado.periodo === "anual";
    var mesAno = Math.round((p.valor_anual / 12) * 100) / 100;
    var det = anual ? "Equivale a " + brlFino(mesAno) + " por mês. Você economiza " + brlFino(p.valor * 12 - p.valor_anual) + "."
      : "Ou " + brlFino(p.valor_anual) + " por ano, equivalente a " + brlFino(mesAno) + " por mês.";
    var porPessoa = p.pessoas > 1 ? brlFino(Math.round(((anual ? mesAno : p.valor) / p.pessoas) * 100) / 100) + " por pessoa, por mês." : "";
    var itens = itensDoPlano(p).map(function (it, i) {
      var chave = p.id + ":" + i;
      var aberto = Boolean(estado.aberto[chave]);
      var breve = /\(em breve\)/.test(it[1]);
      return '<div class="cd-item"><button type="button" class="cd-item-botao" data-item="' + esc(chave) + '" aria-expanded="' + aberto + '">' +
        '<span class="icon" aria-hidden="true">check</span><span>' + esc(it[0]) + (breve ? '<span class="cd-breve">parte em breve</span>' : "") + "</span>" +
        '<span class="icon cd-seta" aria-hidden="true">expand_more</span></button>' + (aberto ? "<p>" + esc(it[1]) + "</p>" : "") + "</div>";
    }).join("");
    // A licenca do Llama pede o "Built with Llama" visivel onde ele e oferecido.
    var llama = (p.modelos_info || []).some(function (m) { return /llama/i.test(m.nome); });
    return '<article class="cd-cartao' + (on ? " on" : "") + '" data-plano="' + esc(p.id) + '" aria-label="Plano ' + esc(p.nome) + '">' +
      (p.id === RECOMENDADO ? '<span class="cd-faixa">recomendado</span>' : "") +
      '<div class="cd-cabeca"><span class="cd-nome"><b>' + esc(p.nome) + '</b><span class="cd-radio" aria-hidden="true"></span></span>' +
      '<span class="cd-preco"><span class="cd-valor"><strong>' + brlFino(valorDe(p)) + "</strong><span>" + (anual ? "por ano" : "por mês") + "</span></span>" +
      "<small>" + esc(det) + "</small>" + (porPessoa ? "<small>" + esc(porPessoa) + "</small>" : "") + "</span>" +
      (PARA[p.id] ? '<span class="cd-para">' + esc(PARA[p.id]) + "</span>" : "") + "</div>" +
      '<div class="cd-numeros"><span><b>' + esc((p.tokens / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões") + "</b><small>créditos de IA por mês</small></span>" +
      "<span><b>" + (p.pessoas === 1 ? "1 pessoa" : "até " + p.pessoas + " pessoas") + "</b><small>" + (p.pessoas === 1 ? "uma licença" : "cada uma com o seu login") + "</small></span></div>" +
      '<div class="cd-itens">' + (HERANCA[p.id] ? '<span class="cd-heranca"><span class="icon" aria-hidden="true">add</span>' + esc(HERANCA[p.id]) + "</span>" : "") + itens + "</div>" +
      '<div class="cd-pe">' + (llama ? "<small>Built with Llama</small>" : "") +
      '<button type="button" class="cd-acao" data-acao="' + esc(p.id) + '" aria-pressed="' + on + '">' + esc((on ? "Assinar " : "Escolher ") + p.nome) + "</button></div></article>";
  }

  /* Clicar no card escolhe; o botao do card escolhido leva ao cadastro, com o
     plano e o periodo. */
  function escolher(id, irAoCadastro) {
    estado.escolhido = id;
    if (irAoCadastro) {
      window.location.assign("../cadastro/?plano=" + encodeURIComponent(id) + "&periodo=" + estado.periodo);
      return;
    }
    desenharPlanos();
  }

  function desenharPlanos() {
    $("cd-planos").innerHTML = estado.planos.map(function (p) { return cartao(p, p.id === estado.escolhido); }).join("");
    $("cd-planos").querySelectorAll(".cd-cartao").forEach(function (el) {
      el.onclick = function (e) { if (!e.target.closest("button")) escolher(el.dataset.plano, false); };
    });
    $("cd-planos").querySelectorAll("[data-acao]").forEach(function (b) {
      b.onclick = function () { escolher(b.dataset.acao, b.dataset.acao === estado.escolhido); };
    });
    $("cd-planos").querySelectorAll("[data-item]").forEach(function (b) {
      b.onclick = function () { estado.aberto[b.dataset.item] = !estado.aberto[b.dataset.item]; desenharPlanos(); };
    });
  }

  async function carregarPlanos() {
    try {
      var r = await fetch("/api/ia/planos");
      var d = await r.json();
      if (!r.ok) throw new Error(d.erro || "o site não respondeu (" + r.status + ")");
      estado.planos = d.planos || [];
      if (!estado.planos.some(function (p) { return p.id === estado.escolhido; })) estado.escolhido = RECOMENDADO;
      if (d.recarga) {
        $("cd-recarga").textContent = "Uma pergunta sobre documentos gasta, em média, 3.500 créditos. A cota é do mês, liberada por semana; " +
          "uma vez por mês dá para adiantar a semana seguinte. Se acabar, a recarga é no Pix, no preço do plano, e não vence na renovação. " +
          "Pague no Pix (um mês ou o ano, sem renovação) ou no cartão (o mensal renova sozinho; o anual, em até 12×).";
      }
      desenharPeriodo();
      desenharPlanos();
    } catch (e) {
      $("cd-planos").innerHTML = '<p class="nota-campo" style="padding:16px 14px">Não consegui ler os planos agora: ' + esc(e.message) + ". Tente de novo em instantes.</p>";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["mensal", "anual"].forEach(function (x) {
      $("cd-periodo-" + x).addEventListener("click", function () {
        estado.periodo = x;
        desenharPeriodo(); desenharPlanos();
      });
    });
    desenharPeriodo();
    carregarPlanos();
  });
})();
