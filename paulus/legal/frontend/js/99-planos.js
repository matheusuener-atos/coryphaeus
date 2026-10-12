/* OS PLANOS (pedido de 11/10/2026): a janela Planos e a pagina de assinatura
   do site (paulus.ia.br/assinatura) dentro do programa - os mesmos tres
   planos, o "Por mes | Por ano", o Recomendado, os numeros de creditos e
   pessoas, o "tudo do plano X, e mais" e o botao de cada um. Escolhido o
   plano, Assinar abre o pagamento no navegador (ATOS) e o programa fica
   esperando: confere sozinho a cada 5 s, e "Verificar assinatura" confere na
   hora - sem mudanca, diz que nao deu certo e fecha; com mudanca, fecha
   sozinho e avisa. Substitui verUpgrade() de js/91-plano-consumo.js.
   Os planos vem de conta.planos (/api/consumo); sem eles, os do site. */
(function () {
  if (typeof verUpgrade !== "function") return;
  /* O pagamento na ATOS: o preco e "pavlvs.<plano>.<mes|ano>" e a volta e para
     onde a pagina manda depois de pagar. */
  const ATOS_URL = "https://atos.dev.br/pavlvs/assinar/";
  const ATOS_VOLTA = "https://paulus.ia.br/";
  const PRECO_ID = { escritorio_plus: "escritorio-plus" };
  const ESPERA_MS = 5000;
  const MESES_GRATIS = 3;

  /* O que o site mostra hoje (11/10/2026). */
  const PLANOS_DO_SITE = [
    { id: "advogado", nome: "Advogado", valor: 449, frase: "Para quem advoga sozinho.", tokens: 30e6, pessoas: 1, pessoasNota: "uma licença",
      ia: "IA Llama 3.3 70B, da Meta", rodape: "Built with Llama",
      itens: ["Converse com os seus documentos", "Processos, prazos e intimações", "Agenda, e-mail e reuniões", "Clientes e financeiro",
        "Editores e assinatura digital", "Biblioteca jurídica", "Até 3 agentes personalizados", "Acesso pelo celular", "Nada sai sem a sua aprovação"] },
    { id: "escritorio", nome: "Escritório", valor: 1290, frase: "Para escritórios com equipe.", tokens: 60e6, pessoas: 5, pessoasNota: "cada uma com o seu login",
      recomendado: true, herda: "Advogado", ia: "IA Mistral Large 3, da Mistral AI",
      itens: ["Até 5 pessoas", "Nota fiscal de serviço", ["Processos no DataJud", "parte em breve"], "Gravação de reuniões",
        "Alerta de conflito de interesses", "Agentes sem limite", "Jurisprudência completa do STJ"] },
    { id: "escritorio_plus", nome: "Escritório Plus", valor: 3490, frase: "Para escritórios que querem a melhor IA do mercado.", tokens: 40e6, pessoas: 15, pessoasNota: "cada uma com o seu login",
      herda: "Escritório", ia: "IA Claude Sonnet 5.5 e Claude Opus 5.5, da Anthropic",
      itens: ["Até 15 pessoas", "Assistente dentro do Word", "NFS-e sem limite", ["Reuniões e cliente", "parte em breve"], "Conexão com outras IAs pelo MCP", "Implantação assistida"] },
  ];

  const reais = (v) => "R$ " + Math.round(Number(v) || 0).toLocaleString("pt-BR");
  const milhoes = (n) => (Math.round(n / 1e5) / 10).toLocaleString("pt-BR") + " milhões";
  const pessoas = (n) => (n === 1 ? "1 pessoa" : "até " + n + " pessoas");
  const CHECK = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 6.2 5 8.5 9.5 3.5"/></svg>';

  async function lerConta() {
    try { const r = await fetch("/api/consumo?forcar=true"); return r.ok ? ((await r.json()).conta || {}) : null; }
    catch (e) { return null; }
  }
  function mudou(antes, depois, escolha) {
    if (!depois) return false;
    const ativa = (depois.assinatura || {}).situacao === "authorized";
    const plano = (depois.plano || {}).id, prox = (depois.plano_proximo || {}).id;
    return prox === escolha.plano || (ativa && plano === escolha.plano && depois.periodo === escolha.periodo &&
      (plano !== (antes.plano || {}).id || antes.periodo !== depois.periodo || (antes.assinatura || {}).situacao !== "authorized"));
  }

  verUpgrade = async function () {   // eslint-disable-line no-func-assign
    const c = (typeof pc !== "undefined" && pc.dados && pc.dados.conta) || (await lerConta()) || {};
    // Os do servidor, completados com o texto do site pelo id.
    const doServidor = (c.planos || []).map((p) => Object.assign({}, PLANOS_DO_SITE.find((s) => s.id === p.id) || {}, p));
    const planos = doServidor.length >= 2 ? doServidor : PLANOS_DO_SITE;
    const atual = (c.plano || {}).id;
    // Com a assinatura em dia nao se assina de novo: o atual trava e a troca e na Conta Atos (sem cobranca em dobro).
    const ativa = (c.assinatura || {}).situacao === "authorized";
    // O anual e o valor_anual da conta (pago de uma vez); sem ele, o do site.
    const precoAno = (p) => Number(p.valor_anual) || p.valor * (12 - MESES_GRATIS);
    const ref = planos.find((p) => p.recomendado) || planos[0] || {};
    const mesesGratis = ref.valor ? Math.max(0, Math.round(12 - precoAno(ref) / ref.valor)) : 0;
    const estado = {
      periodo: c.periodo === "anual" ? "anual" : "mensal",
      plano: ((planos.find((p) => p.recomendado && p.id !== atual) || planos.find((p) => p.id !== atual) || planos[0]) || {}).id,
    };

    function coluna(p) {
      const on = p.id === estado.plano;
      const anual = estado.periodo === "anual";
      const precoMes = anual ? precoAno(p) / 12 : p.valor;
      const travado = ativa && p.id === atual;
      const itens = [p.ia].concat(p.itens || []).filter(Boolean).map((x) => {
        const [texto, tag] = Array.isArray(x) ? x : [x, ""];
        return '<li><span class="pln-ok">' + CHECK + "</span><span>" + esc(texto) + "</span>" + (tag ? '<em class="pln-breve">' + esc(tag) + "</em>" : "") + "</li>";
      }).join("");
      return '<article class="pln-col' + (on ? " on" : "") + (p.recomendado ? " recomendado" : "") + '" data-pln-plano="' + esc(p.id) + '" role="radio" aria-checked="' + on + '" tabindex="0">' +
        (p.recomendado ? '<span class="pln-faixa">Recomendado</span>' : "") +
        '<header class="pln-cab"><b>' + esc(p.nome) + "</b>" + (p.id === atual ? '<span class="pln-atual">atual</span>' : "") + '<i class="ia-radio"></i></header>' +
        '<div class="pln-preco"><b>' + esc(reais(precoMes)) + "</b><span>por mês</span></div>" +
        (anual ? '<p class="pln-ano">' + esc(reais(precoAno(p))) + " por ano, de uma vez</p>" : "") +
        '<p class="pln-frase">' + esc(p.frase || "") + "</p>" +
        '<div class="pln-numeros"><div><b>' + esc(milhoes(p.tokens)) + "</b><small>créditos de IA por mês</small></div>" +
        "<div><b>" + esc(pessoas(p.pessoas)) + "</b><small>" + esc(p.pessoasNota || "") + "</small></div></div>" +
        (p.herda ? '<div class="pln-herda"><span>Tudo do plano ' + esc(p.herda) + ", e mais</span></div>" : "") +
        '<ul class="pln-lista">' + itens + "</ul>" +
        '<footer class="pln-pe">' + (p.rodape ? '<span class="pln-marca">' + esc(p.rodape) + "</span>" : "") +
        (travado
          ? '<button type="button" class="pln-escolher" disabled title="É o seu plano, em dia">Plano atual</button>'
          : '<button type="button" class="' + (on ? "primario pln-assinar" : "pln-escolher") + '" ' + (on ? 'data-pln-assinar="1"' : 'data-pln-escolher="' + esc(p.id) + '"') + ">" +
            esc((on ? (ativa ? "Trocar para " : "Assinar ") : "Escolher ") + p.nome) + "</button>") + "</footer></article>";
    }

    function desenhar(corpo) {
      corpo.innerHTML =
        '<div class="pln-topo">' +
        '<div class="pln-periodo" role="radiogroup" aria-label="Período">' +
          '<button type="button" class="' + (estado.periodo === "mensal" ? "ativa" : "") + '" data-pln-periodo="mensal">Por mês</button>' +
          '<button type="button" class="' + (estado.periodo === "anual" ? "ativa" : "") + '" data-pln-periodo="anual">Por ano' + (mesesGratis ? " <em>" + mesesGratis + (mesesGratis === 1 ? " mês grátis" : " meses grátis") + "</em>" : "") + "</button>" +
        "</div></div>" +
        '<div class="pln-grade" role="radiogroup" aria-label="Plano">' + planos.map(coluna).join("") + "</div>" +
        '<p class="pln-nota">Uma pergunta sobre documentos gasta, em média, 3.500 créditos. A cota é do mês, liberada por semana. ' +
        (ativa
          ? "Para trocar de plano, cancele a assinatura de agora na Conta Atos (o período pago vale até o fim) e assine o outro quando ele acabar. Assim não há cobrança em dobro."
          : "O pagamento é na Atos, com a Conta Atos: no cartão, com o mensal renovando todo mês, ou no Pix. O anual é pago de uma vez, sem parcelamento.") + "</p>";
    }

    let relogio = 0, conferindo = false;
    const parar = () => { clearInterval(relogio); relogio = 0; };
    const fecharJanela = () => { parar(); if (dialogoAberto) dialogoAberto.fechar(null); };
    async function conferir(manual) {
      if (conferindo) return;
      conferindo = true;
      const b = document.querySelector("#veu-dialogo [data-pln-verificar]");
      if (b && manual) { b.disabled = true; b.textContent = "Verificando…"; }
      const depois = await lerConta();
      conferindo = false;
      const escolha = { plano: estado.plano, periodo: estado.periodo };
      const nome = (planos.find((p) => p.id === escolha.plano) || {}).nome || "";
      if (mudou(c, depois, escolha)) {
        if (typeof pc !== "undefined" && pc.dados) pc.dados.conta = depois;
        fecharJanela();
        if (typeof avisoNaJanela === "function") avisoNaJanela("Assinatura confirmada · " + nome + (escolha.periodo === "anual" ? " anual" : " mensal"), { icone: "check_circle" });
        if (typeof mostrarPlanoConsumo === "function" && document.querySelector('.trilho-item.ativo[data-destino="consumo"]')) mostrarPlanoConsumo();
      } else if (manual) {
        fecharJanela();
        if (typeof avisoNaJanela === "function") avisoNaJanela("Não deu certo: a assinatura ainda não apareceu. Se você já pagou, ela chega em alguns minutos.", { tom: "erro", icone: "error" });
      }
    }
    const abrirPagamento = () => {
      const preco = "pavlvs." + (PRECO_ID[estado.plano] || estado.plano) + "." + (estado.periodo === "anual" ? "ano" : "mes");
      const url = ATOS_URL + "?preco=" + encodeURIComponent(preco) + "&volta=" + encodeURIComponent(ATOS_VOLTA);
      if (window.pywebview && window.pywebview.api && window.pywebview.api.abrir_navegador) window.pywebview.api.abrir_navegador(url);
      else window.open(url, "_blank", "noopener");
    };
    function esperar(corpo) {
      const nome = (planos.find((p) => p.id === estado.plano) || {}).nome || "";
      corpo.innerHTML = '<div class="pln-espera"><span class="pln-giro" aria-hidden="true"></span><b>Aguardando a assinatura</b>' +
        "<p>Termine o pagamento do plano " + esc(nome) + (estado.periodo === "anual" ? " anual" : " mensal") +
        " no navegador. Esta janela confere sozinha e fecha quando a assinatura chegar.</p>" +
        '<button type="button" class="sv-ligacao" data-pln-reabrir="1">Abrir a página de novo</button></div>';
      const pe = document.querySelector("#veu-dialogo .dialogo-pe");
      if (pe) pe.innerHTML = '<span class="cresce"></span><button type="button" class="dialogo-cancelar" data-pln-cancelar="1">Cancelar</button>' +
        '<button type="button" class="primario" data-pln-verificar="1">Verificar assinatura</button>';
      relogio = setInterval(() => conferir(false), ESPERA_MS);
    }

    const aberto = dialogo({ titulo: "Planos", contexto: "Plano e consumo", classe: "pc-dialogo pln-dialogo", larga: true,
      confirmar: "Fechar", semCancelar: true, html: '<div data-pln-corpo="1"></div>' });
    const veu = document.getElementById("veu-dialogo");
    const corpo = veu.querySelector("[data-pln-corpo]");
    desenhar(corpo);
    veu.addEventListener("click", (e) => {
      const per = e.target.closest("[data-pln-periodo]");
      if (per) { estado.periodo = per.dataset.plnPeriodo; desenhar(corpo); return; }
      if (e.target.closest("[data-pln-assinar]")) {
        // Com a assinatura em dia, a troca e na Conta Atos (js/75-nuvem.js), nunca um segundo pagamento.
        if (ativa && typeof trocarPlanoNaAtos === "function") {
          fecharJanela();
          trocarPlanoNaAtos(c, (planos.find((p) => p.id === estado.plano) || {}).nome || "outro plano");
          return;
        }
        abrirPagamento(); esperar(corpo); return;
      }
      const col = e.target.closest("[data-pln-escolher], [data-pln-plano]");
      if (col && !e.target.closest(".pln-espera")) { estado.plano = col.dataset.plnEscolher || col.dataset.plnPlano; desenhar(corpo); return; }
      if (e.target.closest("[data-pln-verificar]")) { conferir(true); return; }
      if (e.target.closest("[data-pln-reabrir]")) { abrirPagamento(); return; }
      if (e.target.closest("[data-pln-cancelar]")) fecharJanela();
    });
    veu.addEventListener("keydown", (e) => {
      const col = e.target.closest && e.target.closest("[data-pln-plano]");
      if (col && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); estado.plano = col.dataset.plnPlano; desenhar(corpo); }
    });
    await aberto;
    parar();
  };
})();
