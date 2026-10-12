/* CONFIGURACOES › ASSISTENTE E MODELO, VERSAO NUVEM (pedido de 11/10/2026).
   A tela falava so do Ollama; hoje o caminho padrao e a nuvem do plano
   PAVLVS, e este computador fica de reserva - para quando faltar internet e
   para as tarefas do proprio sistema (agendar, organizar). Quem usa assinou
   um plano e quer usar: a tela fala disso, em portugues de gente. Tudo o que
   e de modelo de IA mora aqui (a antiga secao Modelos entrou como "Modelos
   deste computador"); indice, codigos de lei e o que ja foi lido saem daqui.

   Substitui secaoAssistente() de js/05-configuracoes.js e completa
   carregarSecao() com o plano e os modelos. As escolhas que o servidor ainda
   nao guarda (quando usar a nuvem, o mascaramento) ficam no localStorage com
   a chave paulus.ia.* - ver DIFERENCAS-POR-TELA.md. */
(function () {
  if (typeof CFG_SECOES === "undefined" || typeof secaoAssistente !== "function") return;

  const sec = CFG_SECOES.find((s) => s[0] === "assistente");
  if (sec) {
    sec[1] = "Assistente e modelo";
    sec[2] = "O Paulus responde pela nuvem do seu plano. Este computador fica de reserva.";
  }
  const iModelos = CFG_SECOES.findIndex((s) => s[0] === "modelos");
  if (iModelos >= 0) CFG_SECOES.splice(iModelos, 1);

  const ler = (k, p) => { try { const v = localStorage.getItem("paulus.ia." + k); return v === null ? p : v; } catch (e) { return p; } };
  const gravar = (k, v) => { try { localStorage.setItem("paulus.ia." + k, v); } catch (e) { /* so nesta pagina */ } };
  const mil = (n) => {
    const v = Number(n) || 0;
    if (v >= 1e6) return (Math.round(v / 1e5) / 10).toLocaleString("pt-BR") + " mi";
    if (v >= 1e3) return Math.round(v / 1e3).toLocaleString("pt-BR") + " mil";
    return String(v);
  };
  const dataCurta = (iso) => { const d = new Date(iso || ""); return isNaN(d) ? "" : d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" }); };

  const carregarAntes = carregarSecao;
  carregarSecao = async function () {   // eslint-disable-line no-func-assign
    await carregarAntes.apply(this, arguments);
    if (cfg.secao !== "assistente") return;
    const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    const [consumo] = await Promise.all([
      pega("/api/consumo"),
      typeof carregarModelos === "function" ? carregarModelos() : null,
      typeof carregarNuvemNaConfig === "function" ? carregarNuvemNaConfig() : null,
    ]);
    cfg.ia = consumo || {};
  };

  /* um grupo de escolhas (uma so), em cartoes de linha */
  function escolhas(chave, atual, opcoes) {
    return '<div class="ia-opcoes" role="radiogroup">' + opcoes.map((o) =>
      '<button type="button" class="ia-opcao' + (o.id === atual ? " on" : "") + (o.travado ? " travada" : "") + '" role="radio" aria-checked="' + (o.id === atual) + '"' +
      (o.travado ? " disabled" : "") + ' data-ia-escolha="' + chave + '" data-ia-valor="' + esc(o.id) + '">' +
      '<i class="ia-radio"></i><span class="duas-linhas"><b>' + esc(o.nome) + (o.selo ? ' <span class="ia-selo">' + esc(o.selo) + "</span>" : "") + "</b>" +
      "<small>" + esc(o.texto) + "</small></span>" + (o.lado ? '<span class="ia-lado">' + esc(o.lado) + "</span>" : "") + "</button>").join("") + "</div>";
  }
  function liga(chave, titulo, sub, padrao) {
    const on = ler(chave, padrao ? "1" : "0") === "1";
    return '<div class="ag-toggle' + (on ? " on" : "") + '" data-ia-liga="' + chave + '"><span class="duas-linhas"><b>' + esc(titulo) + "</b>" +
      (sub ? "<small>" + esc(sub) + "</small>" : "") + "</span><i></i></div>";
  }

  secaoAssistente = function () {   // eslint-disable-line no-func-assign
    const r = cfg.rascunho;
    const s = cfg.status || {};
    const conta = (cfg.ia && cfg.ia.conta) || {};
    const plano = conta.plano || {};
    const tok = conta.tokens || {};
    const ciclo = conta.ciclo || {};
    const niveis = (((cfg.ia || {}).painel || {}).profundidade || []);
    if (typeof renomearNiveis === "function") renomearNiveis(niveis);
    const ligado = Boolean(s.ollama);
    const quando = ler("quando", "sempre");
    const pct = tok.limite ? Math.min(100, (tok.usados / tok.limite) * 100) : 0;

    const ficha = fichaCfg([
      ["Plano", plano.nome || "—"],
      ["Créditos do mês", tok.limite ? mil(tok.usados) + " de " + mil(tok.limite) : "—"],
      ["Responde por", quando === "nunca" ? "este computador" : "nuvem Paulus"],
      ["Reserva", ligado ? (r.modelo || "—") : "desligada", ligado ? "" : "cfg-mudo"],
    ]);

    const cartaoPlano = '<div class="ia-plano">' +
      '<div class="ia-plano-linha"><b>' + esc(plano.nome ? "Plano " + plano.nome : "Sem plano") + "</b>" +
      '<span class="mono">' + esc(tok.limite ? mil(tok.usados) + " de " + mil(tok.limite) + " créditos" : "") + "</span></div>" +
      '<div class="ia-barra" role="progressbar" aria-valuenow="' + Math.round(pct) + '" aria-valuemin="0" aria-valuemax="100"><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
      '<p class="cfg-explica">' + esc((ciclo.fim ? "Renova em " + dataCurta(ciclo.fim) + ". " : "") +
        "Cada pergunta gasta créditos conforme a profundidade: quanto mais o Paulus confere, mais gasta.") + "</p>" +
      '<div class="cfg-botoes"><button class="primario com-icone" data-ia-upgrade="1">' + ic("arrow_upward", 16) + "Fazer upgrade</button>" +
      '<button data-ia-ir="consumo">' + ic("speed", 16) + "Ver o consumo</button></div></div>";

    const atualNivel = ler("profundidade", (typeof prof !== "undefined" && (prof.escolhido || prof.padrao)) || "advogado");
    const cartaoProfundidade = escolhas("profundidade", atualNivel, niveis.map((n) => ({
      id: n.nivel, nome: n.nome, texto: n.resumo.charAt(0).toUpperCase() + n.resumo.slice(1),
      lado: "~" + String(n.consumo).replace(".", ",") + "× créditos", selo: n.nivel === "advogado" ? "recomendado" : "",
    }))) +
      '<p class="cfg-explica">É o ponto de partida. Em cada pergunta dá para trocar pela pílula ao lado do campo.</p>' +
      '<div class="cfg-campos">' + liga("perguntar", "Perguntar antes quando faltar informação", "em vez de supor, o Paulus faz uma ou duas perguntas e só então escreve", true) + "</div>";

    const cartaoQuando = escolhas("quando", quando, [
      { id: "sempre", nome: "Sempre que precisar", texto: "As perguntas vão para a nuvem; sem internet, este computador responde.", selo: "recomendado" },
      { id: "pedir", nome: "Só quando eu pedir", texto: "Responde aqui; a nuvem entra quando você escolher na pergunta." },
      { id: "nunca", nome: "Nunca", texto: "Tudo gerado neste computador." },
    ]);

    /* A nuvem e confiavel por si (DeepInfra: SOC 2 e ISO 27001, retencao zero,
       conforme trust.deepinfra.com em 11/10/2026); o mascaramento e uma
       camada a mais, para quem preferir. */
    const cartaoPrivacidade = '<p class="cfg-texto">A nuvem do Paulus roda na DeepInfra, que tem as certificações de segurança SOC 2 e ISO 27001 e não guarda o que você envia: a pergunta é respondida e descartada.</p>' +
      '<div class="ia-selos"><span>SOC 2</span><span>ISO 27001</span><span>retenção zero</span></div>' +
      '<p class="cfg-texto">Se preferir uma camada a mais, o Paulus troca os dados pessoais por marcadores antes de enviar. A resposta volta e eles são recolocados aqui, sem que a nuvem veja o nome do seu cliente.</p>' +
      '<div class="cfg-campos">' +
      liga("mascarar_nomes", "Nomes de pessoas e empresas", "", true) +
      liga("mascarar_documentos", "CPF, CNPJ e RG", "", true) +
      liga("mascarar_contato", "Endereços, telefones e e-mails", "", true) +
      liga("mascarar_processos", "Números de processo", "deixe ligado a menos que a pergunta seja sobre o processo em si", true) +
      liga("mostrar_antes", "Mostrar o que vai antes de enviar", "cada envio para a nuvem espera o seu sim, com o texto já mascarado", false) +
      "</div>";

    const reserva = '<div class="sv-ficha cfg-ficha ia-reserva">' +
      '<div class="sv-ficha-item"><span class="sv-kicker">Estado</span><b class="cfg-st ' + (ligado ? "ok" : "cfg-mudo") + '">' + esc(ligado ? "Pronto para usar" : "Desligado") + "</b></div>" +
      '<div class="sv-ficha-item"><span class="sv-kicker">Modelo de reserva</span><b' + (r.modelo ? "" : ' class="cfg-mudo"') + ">" + esc(r.modelo || "Nenhum escolhido") + "</b></div>" +
      '<div class="sv-ficha-item"><span class="sv-kicker">Entra quando</span><b>Sem internet ou em tarefas do sistema</b></div></div>' +
      '<p class="cfg-explica">Agendar, organizar pastas, ler um e-mail para a fila: o que é do próprio Paulus roda aqui, sem gastar créditos.</p>' +
      '<div class="cfg-campos">' + ligaCfg("devagar", "Ir devagar quando eu usar o PC", "espera o computador desafogar antes de cada tarefa", r.devagar) + "</div>";

    // A antiga secao Modelos, sem o proprio cabecalho.
    let modelosLocais = "";
    if (typeof secaoModelos === "function") {
      const caixa = document.createElement("div");
      caixa.innerHTML = secaoModelos();
      // O cabecalho, a ficha e a nuvem (que aqui tem o seu proprio lugar) saem.
      caixa.querySelectorAll(':scope > header.sv-resumo-topo, :scope > .sv-ficha, [data-cartao="nuvem"]').forEach((x) => x.remove());
      // O aviso de motor parado, curto: o que e e onde se liga.
      caixa.querySelectorAll(".cfg-cartao").forEach((c) => {
        if (!/Ollama não está respondendo/i.test(c.textContent)) return;
        const corpo = c.querySelector(".cfg-cartao-corpo");
        const cab = c.querySelector(".cfg-cartao-cabeca > span");
        /* Como o aviso do Google Drive ausente (semDriveHtml, js/03): a marca,
           o titulo em duas linhas, uma frase e o botao de baixar. */
        c.outerHTML = '<div class="anx-sem-drive ia-sem-ollama"><span class="anx-drive-marca ia-marca-ollama"><img src="/img/marcas/ollama-lhama.webp?v=2" alt="Ollama"></span>' +
          "<h3>O Ollama não está<br>rodando nesta máquina.</h3>" +
          "<p>É ele que roda a reserva do Paulus quando falta internet e nas tarefas do sistema. Instale, abra uma vez e volte aqui.</p>" +
          '<div class="cfg-botoes"><button type="button" class="primario com-icone" data-ia-ollama-baixar="1">' + ic("download", 16) + "Baixar o Ollama</button>" +
          '<button type="button" class="com-icone" data-ia-ollama-conferir="1">' + ic("refresh", 16) + "Conferir de novo</button></div></div>";
        return;
      });
      modelosLocais = caixa.innerHTML;
    }
    const avancado = (titulo, sub, corpo, id) => '<details class="ia-avancado" data-ia-avancado="' + id + '"' + (ler("aberto_" + id, "0") === "1" ? " open" : "") + ">" +
      '<summary><span class="duas-linhas"><b>' + esc(titulo) + "</b><small>" + esc(sub) + '</small></span><span class="ic ic-16">expand_more</span></summary>' +
      '<div class="ia-avancado-corpo">' + corpo + "</div></details>";

    const limites = '<div class="cfg-campos">' + (cfg.prefs.autonomia_opcoes || []).map((a) => {
      const ligada = a.travada ? false : Boolean(r.autonomia[a.chave]);
      return ligaCfg(a.travada ? "" : "autonomia." + a.chave, a.titulo, a.explica, ligada, a.travada);
    }).join("") + "</div>" +
      '<p class="cfg-explica">Desligado, a ação espera o seu sim em Aprovações. Ligado, ela acontece direto.</p>';

    // A ficha do topo repetia o cartao Seu plano (plano, creditos, reserva): sai.
    void ficha;
    return aberturaCfg() +
      cartaoCfg("Seu plano", metaCfg("a nuvem Paulus"), cartaoPlano) +
      cartaoCfg("Quanto o Paulus trabalha", metaCfg("profundidade padrão das respostas"), cartaoProfundidade) +
      cartaoCfg("Quando usar a nuvem", metaCfg("para onde vão as perguntas"), cartaoQuando) +
      cartaoCfg("O que sai deste computador", metaCfg("segurança da nuvem e mascaramento"), cartaoPrivacidade) +
      cartaoCfg("Neste computador", pontoCfg(ligado ? "reserva pronta" : "reserva desligada", ""),
        reserva + avancado("Modelos deste computador", "baixar e trocar", modelosLocais, "modelos")) +
      cartaoCfg("Limites da IA", metaCfg("o que o assistente faz sem pedir"), limites) +
      cartaoCfg("Modelo de voz", metaCfg("transcreve as gravações, aqui mesmo"), cartaoDaVozCfg()) +
      // As chaves que moravam na secao antiga e nao tinham outro lugar (pedido de 12/10/2026).
      (typeof cartaoChavesConversa === "function" ? cartaoChavesConversa() : "") +
      (typeof cartaoChavesAparelho === "function" ? cartaoChavesAparelho() : "") +
      cartaoCfg("O que já foi lido", metaCfg("entendido uma vez, consultado sempre"), blocoDoQueJaFoiLido()) +
      (typeof cartaoNuvem === "function" && cartaoNuvem()
        ? avancado("Usar a minha própria chave de IA", "OpenAI, Anthropic ou Google", chaveEnxuta(cartaoNuvem()), "chave")
        : "");
  };

  /* O cartao da nuvem (js/75-nuvem.js) explica tudo por extenso; aqui, dentro
     do avancado, ele fica so com o que se faz: provedor, chave, termo e as
     chaves de ligar. O que vai a nuvem ja esta no cartao de cima. */
  function chaveEnxuta(html) {
    const caixa = document.createElement("div");
    caixa.innerHTML = html;
    const curto = {
      "Antes de ligar: o termo": "obrigatório antes de ligar",
      "Mascarar antes de sair": "CPF, CNPJ, processo, e-mail e telefone viram marcadores",
      "Pedir o sim a cada pergunta": "a pergunta espera em Aprovações",
    };
    caixa.querySelectorAll("b").forEach((b) => {
      const t = b.textContent.trim();
      const sub = b.parentElement && b.parentElement.querySelector("small");
      if (t === "Provedor" && sub) sub.remove();
      else if (curto[t] && sub) sub.textContent = curto[t];
    });
    caixa.querySelectorAll(".cfg-cartao-corpo > p, .cfg-explica, .cfg-texto").forEach((p) => {
      const t = p.textContent;
      if (/chave de API do próprio escritório/.test(t)) p.textContent = "A chave fica neste computador e o provedor cobra direto do escritório. Assinaturas como ChatGPT Plus ou Claude Pro não servem.";
      else if (/^Fica sempre neste computador/.test(t.trim())) p.remove();
    });
    caixa.querySelectorAll(".sv-kicker, .rotulo, .cfg-sub-titulo, .nuvem-rotulo").forEach((k) => { if (/o que vai à nuvem/i.test(k.textContent)) k.remove(); });
    // Icone + rotulo, como os outros botoes da tela.
    const icones = { nuvemGuardar: "key", nuvemTermo: "description" };
    caixa.querySelectorAll("button").forEach((b) => {
      const chave = Object.keys(b.dataset).find((k) => icones[k]);
      if (chave && !b.querySelector(".ic")) { b.classList.add("com-icone"); b.insertAdjacentHTML("afterbegin", ic(icones[chave], 16)); }
    });
    return caixa.innerHTML;
  }


  /* Os cliques desta secao, por delegacao (a tela se redesenha inteira). */
  document.addEventListener("click", (e) => {
    if (typeof cfg === "undefined" || cfg.secao !== "assistente") return;
    const esc_ = e.target.closest("[data-ia-escolha]");
    if (esc_ && !esc_.disabled) {
      const chave = esc_.dataset.iaEscolha, valor = esc_.dataset.iaValor;
      gravar(chave, valor);
      if (chave === "profundidade" && typeof prof !== "undefined") { prof.escolhido = valor; try { localStorage.setItem("paulus.profundidade", valor); } catch (x) { /* */ } if (typeof desenharPilulaProfundidade === "function") desenharPilulaProfundidade(); }
      esc_.parentElement.querySelectorAll("[data-ia-escolha]").forEach((b) => { const on = b === esc_; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
      if (chave === "quando") desenharConfig();
      if (typeof avisoCert === "function") avisoCert("guardado");
      return;
    }
    const lg = e.target.closest("[data-ia-liga]");
    if (lg) {
      const on = !lg.classList.contains("on");
      lg.classList.toggle("on", on);
      gravar(lg.dataset.iaLiga, on ? "1" : "0");
      if (lg.dataset.iaLiga === "perguntar" && typeof prof !== "undefined") { prof.perguntar = on; try { localStorage.setItem("paulus.perguntar_antes", on ? "1" : "0"); } catch (x) { /* */ } }
      return;
    }
    /* Fazer upgrade: os planos de Plano e consumo (verUpgrade, js/91). Sem os
       dados de la carregados, abre a tela e chama quando ela terminar. */
    if (e.target.closest("[data-ia-upgrade]")) {
      if (typeof pc !== "undefined" && pc.dados && typeof verUpgrade === "function") { verUpgrade(); return; }
      if (typeof abrirDestino === "function") abrirDestino("consumo");
      let tentativas = 0;
      const esperar = setInterval(() => {
        tentativas++;
        if (typeof pc !== "undefined" && pc.dados && typeof verUpgrade === "function") { clearInterval(esperar); verUpgrade(); }
        else if (tentativas > 40) clearInterval(esperar);
      }, 150);
      return;
    }
    if (e.target.closest("[data-ia-ollama-baixar]")) {
      const url = "https://ollama.com/download/windows";
      if (window.pywebview && window.pywebview.api && window.pywebview.api.abrir_navegador) window.pywebview.api.abrir_navegador(url);
      else window.open(url, "_blank", "noopener");
      return;
    }
    if (e.target.closest("[data-ia-ollama-conferir]")) { if (typeof mostrarConfig === "function") mostrarConfig("assistente"); return; }
    const ir = e.target.closest("[data-ia-ir]");
    if (ir && typeof abrirDestino === "function") abrirDestino(ir.dataset.iaIr);
  });
  document.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!d.matches || !d.matches("[data-ia-avancado]")) return;
    gravar("aberto_" + d.dataset.iaAvancado, d.open ? "1" : "0");
    if (d.open && d.dataset.iaAvancado === "modelos" && typeof ligarModelos === "function") ligarModelos();
    if (d.open && d.dataset.iaAvancado === "chave" && typeof ligarNuvemNaConfig === "function") ligarNuvemNaConfig($("cfg-tela"), () => desenharConfig());
    if (d.open) melhorarSelectsIa();
  }, true);

  // Ligar o que ja abre aberto.
  const ligarAntes = ligarConfig;
  ligarConfig = function () {   // eslint-disable-line no-func-assign
    ligarAntes.apply(this, arguments);
    if (cfg.secao !== "assistente") return;
    if (document.querySelector('[data-ia-avancado="modelos"][open]') && typeof ligarModelos === "function") ligarModelos();
    if (document.querySelector('[data-ia-avancado="chave"][open]') && typeof ligarNuvemNaConfig === "function") ligarNuvemNaConfig($("cfg-tela"), () => desenharConfig());
    melhorarSelectsIa();
  };
  /* Os selects desta secao com a lista de escolha do sistema (melhorarSelect,
     js/16-dialogos.js), nao a do Windows. */
  function melhorarSelectsIa() {
    if (typeof melhorarSelect !== "function") return;
    document.querySelectorAll("#cfg-tela [data-cfg-aberta='assistente'] select, #cfg-tela select#nuvem-provedor").forEach((s) => { if (!s.dataset.melhorado) melhorarSelect(s); });
  }
})();
