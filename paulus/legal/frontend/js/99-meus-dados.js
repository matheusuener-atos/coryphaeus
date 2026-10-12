/* MEUS DADOS, UNIFICADO (pedido de 11/10/2026): os dados de identidade que
   estavam espalhados por Configuracoes moram aqui, sem mexer no desenho da
   secao - os mesmos dois cartoes, campos a mais no mesmo padrao.
   - Escritorio: razao social, inscricao municipal e o endereco completo, que
     eram so do passo 2 da Nota fiscal. Gravados aqui, vao tambem para o
     prestador da NFS-e (/api/nfse/prestador), com o CNPJ do escritorio.
   - Voce: o certificado digital (estava em Conexoes) numa linha com o estado
     e o botao de abrir.
   - Nota fiscal, passo 2: mostra o resumo e manda editar em Meus dados. */
(function () {
  if (typeof secaoPerfil !== "function") return;
  const mdd = { base: null, rascunho: null, sujo: false };
  const CAMPOS = [
    ["razao_social", "Razão social", "como no CNPJ"],
    ["inscricao_municipal", "Inscrição municipal", "está no alvará ou no carnê do ISS"],
    ["endereco.cep", "CEP", "00000-000"], ["endereco.logradouro", "Rua", ""],
    ["endereco.numero", "Número", ""], ["endereco.complemento", "Complemento", ""],
    ["endereco.bairro", "Bairro", ""], ["municipio", "Cidade", "digite o nome"],
    ["telefone", "Telefone do escritório", "(62) 3000-0000"], ["email", "E-mail do escritório", ""],
  ];
  const ler = (o, cam) => cam.split(".").reduce((a, k) => (a || {})[k], o);
  const pôr = (o, cam, v) => { const p = cam.split("."); let a = o; p.slice(0, -1).forEach((k) => { a[k] = a[k] || {}; a = a[k]; }); a[p[p.length - 1]] = v; };

  const carregarAntes = carregarSecao;
  carregarSecao = async function () {   // eslint-disable-line no-func-assign
    await carregarAntes.apply(this, arguments);
    if (cfg.secao !== "perfil") return;
    const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    const [nf, cert, consumo] = await Promise.all([pega("/api/nfse"), pega("/api/certificado"), pega("/api/consumo")]);
    cfg.cert = cert;
    mdd.plano = (((consumo || {}).conta || {}).plano || {}).id || "";
    try { mdd.socios = JSON.parse(localStorage.getItem("paulus.socios") || "[]"); } catch (e) { mdd.socios = []; }
    mdd.sociosBase = JSON.stringify(mdd.socios);
    const dados = ((nf || {}).prestador || {}).dados || {};
    mdd.base = JSON.parse(JSON.stringify(dados));
    mdd.rascunho = JSON.parse(JSON.stringify(dados));
    mdd.municipioNome = ((nf || {}).prestador || {}).municipio_nome || "";
    mdd.sujo = false;
  };

  const campo = (cam, rotulo, dica) => {
    const v = mdd.rascunho ? ler(mdd.rascunho, cam) : "";
    return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-mdd-campo="' + cam + '" value="' + esc(v == null ? "" : String(v)) + '"' +
      (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
  };
  const duas = (a, b) => '<div class="ag-duas">' + a + b + "</div>";
  const porNome = (n) => CAMPOS.find((c) => c[0] === n);
  const c = (n) => campo.apply(null, porNome(n));

  /* "Silva & Souza Advogados" -> SS: so palavras, sem conectivos nem "advogados". */
  function iniciaisDoEscritorio(nome) {
    const fora = /^(e|de|da|do|das|dos|advogados?|associados?|sociedade|escrit[oó]rio|ltda|s\/?s)$/i;
    const p = String(nome || "").split(/\s+/).filter((w) => /^[A-Za-zÀ-ÿ]/.test(w) && !fora.test(w));
    return (p.slice(0, 2).map((w) => w[0].toUpperCase()).join("")) || "E";
  }

  const perfilAntes = secaoPerfil;
  secaoPerfil = function () {   // eslint-disable-line no-func-assign
    let html = perfilAntes.apply(this, arguments);
    if (mdd.rascunho) {
      const extra = duas(c("razao_social"), c("inscricao_municipal")) +
        duas(c("endereco.cep"), c("endereco.logradouro")) +
        duas(c("endereco.numero"), c("endereco.complemento")) +
        duas(c("endereco.bairro"), c("municipio")) +
        duas(c("telefone"), c("email"));
      const ancora = campoCfg("escritorio.rodape", "Rodapé dos documentos", cfg.rascunho.escritorio.rodape, "OAB/GO 00000 · Goiânia · GO");
      if (html.includes(ancora)) html = html.replace(ancora, extra + ancora);
    }
    // Sem logo propria, o escritorio ganha o mesmo avatar de iniciais da pessoa
    // (e nao a marca do Paulus).
    const logo = typeof marcaDaTela === "function" ? marcaDaTela("logo") : { tem: true };
    if (!logo.tem) {
      html = html.replace('<span class="cfg-logo"><img src="/img/paulus-logo.svg" alt=""></span>',
        '<span class="cad-avatar">' + esc(iniciaisDoEscritorio((cfg.rascunho.escritorio || {}).nome)) + "</span>");
    }
    html = html.replace("O nome entra nos recibos da folha. CNPJ, OAB e rodapé ficam guardados; nenhum documento os usa ainda.",
      "Entram nos recibos, no papel timbrado e na nota fiscal. A Nota fiscal lê daqui.");
    // O certificado: uma linha no fim do cartao Voce, antes do timbre.
    const ct = cfg.cert || {};
    const certInfo = ct.certificado || {};
    const linhaCert = '<div class="cfg-servico mdd-cert">' + ic("workspace_premium", 18) +
      '<span class="duas-linhas cresce"><b>Certificado digital</b><small>' +
      esc(ct.instalado ? [certInfo.titular, certInfo.tipo || "A1", certInfo.validade ? "válido até " + certInfo.validade : ""].filter(Boolean).join(" · ") : "nenhum instalado · assina PDFs e emite a nota fiscal") +
      '</small></span><button class="com-icone" data-mdd-cert="1">' + ic(ct.instalado ? "open_in_new" : "upload", 16) + (ct.instalado ? "Abrir" : "Instalar") + "</button></div>";
    const timbre = '<div class="cfg-sub">' + ligaCfg("timbre_no_pdf", "Papel timbrado nos PDFs", "nome, OAB, endereço e contato no alto de cada PDF gerado aqui", cfg.rascunho.timbre_no_pdf);
    if (html.includes(timbre)) html = html.replace(timbre, linhaCert + timbre);
    // Socios: so nos planos com equipe (fora do Advogado, que e de uma pessoa).
    if (mdd.plano && mdd.plano !== "advogado") {
      const lista = (mdd.socios || []);
      const socio = (s, i) => '<div class="mdd-socio" data-mdd-socio="' + i + '">' +
        '<div class="mdd-socio-cab"><span class="cad-avatar">' + esc(iniciaisDoRemetente(s.nome || "?")) + "</span><b>" + esc(s.nome || "Novo sócio") + "</b>" +
        '<button class="com-icone" data-mdd-socio-tirar="' + i + '">' + ic("close", 16) + "Remover</button></div>" +
        '<div class="cfg-campos">' + campoSocio(i, "nome", "Nome completo", s.nome) +
        duas(campoSocio(i, "cpf", "CPF", s.cpf, "000.000.000-00"), campoSocio(i, "oab", "OAB", s.oab, "GO 00000")) +
        duas(campoSocio(i, "telefone", "Telefone", s.telefone), campoSocio(i, "email", "E-mail", s.email)) + "</div></div>";
      const corpo = (lista.length ? lista.map(socio).join("") : '<p class="cfg-explica">Nenhum outro sócio. Os sócios entram no contrato social, nas procurações e no timbre da sociedade.</p>') +
        '<div class="cfg-botoes"><button class="com-icone" data-mdd-socio-novo="1">' + ic("person_add", 16) + "Adicionar sócio</button></div>";
      const cartao = cartaoCfg("Sócios", metaCfg(lista.length ? (lista.length === 1 ? "1 sócio além de você" : lista.length + " sócios além de você") : "além de você"), corpo);
      const marcaEsc = '<div class="cfg-cartao" data-cartao="escritorio">';
      html = html.includes(marcaEsc) ? html.replace(marcaEsc, cartao + marcaEsc) : html + cartao;
    }
    return html;
  };
  function campoSocio(i, k, rotulo, v, dica) {
    return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-mdd-socio-campo="' + i + "." + k + '" value="' + esc(v || "") + '"' +
      (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
  }

  /* Nota fiscal, passo 2: o resumo do que vem de Meus dados; os campos ficam
     escondidos para o "Gravar e continuar" do passo seguir funcionando. */
  if (typeof secaoNfse === "function") {
    const nfseAntes = secaoNfse;
    secaoNfse = function () {   // eslint-disable-line no-func-assign
      const html = nfseAntes.apply(this, arguments);
      const caixa = document.createElement("div");
      caixa.innerHTML = html;
      const cpo = caixa.querySelector('[data-nfse-campo="razao_social"]');
      const campos = cpo && cpo.closest(".cfg-campos");
      if (!campos) return html;
      const v = (n) => { const el = campos.querySelector('[data-nfse-campo="' + n + '"]'); return el ? el.value : ""; };
      const linhas = [v("razao_social"), v("documento"), [v("endereco.logradouro"), v("endereco.numero"), v("endereco.bairro")].filter(Boolean).join(", "), [v("municipio"), v("endereco.cep")].filter(Boolean).join(" · ")].filter(Boolean);
      campos.querySelectorAll("input[data-nfse-campo]").forEach((i) => { i.type = "hidden"; });
      campos.querySelectorAll(".ag-campo, .ag-duas").forEach((x) => { x.style.display = "none"; });
      campos.insertAdjacentHTML("afterbegin", '<div class="cfg-servico">' + ic("domain", 18) + '<span class="duas-linhas cresce"><b>' +
        esc(linhas[0] || "Faltam os dados do escritório") + "</b><small>" + esc(linhas.slice(1).join(" · ") || "preencha em Dados e informações") + "</small></span>" +
        '<button class="com-icone" data-cfg-secao="perfil">' + ic("edit", 16) + "Editar em Dados e informações</button></div>");
      return caixa.innerHTML;
    };
  }

  document.addEventListener("input", (e) => {
    const el = e.target.closest && e.target.closest("[data-mdd-campo]");
    if (!el || !mdd.rascunho) return;
    pôr(mdd.rascunho, el.dataset.mddCampo, el.value);
    mdd.sujo = true;
    if (typeof marcarConfigSuja === "function") marcarConfigSuja();
  });
  document.addEventListener("input", (e) => {
    const el = e.target.closest && e.target.closest("[data-mdd-socio-campo]");
    if (!el) return;
    const [i, k] = el.dataset.mddSocioCampo.split(".");
    if (mdd.socios[i]) mdd.socios[i][k] = el.value;
    if (k === "nome") { const b = el.closest(".mdd-socio").querySelector(".mdd-socio-cab b"); if (b) b.textContent = el.value || "Novo sócio"; }
    if (typeof marcarConfigSuja === "function") marcarConfigSuja();
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-mdd-socio-novo]")) {
      mdd.socios.push({ nome: "", cpf: "", oab: "", telefone: "", email: "" });
      if (typeof marcarConfigSuja === "function") marcarConfigSuja();
      desenharConfig();
      setTimeout(() => { const c = document.querySelectorAll('[data-mdd-socio-campo$=".nome"]'); if (c.length) c[c.length - 1].focus(); }, 60);
      return;
    }
    const tirar = e.target.closest("[data-mdd-socio-tirar]");
    if (tirar) { mdd.socios.splice(Number(tirar.dataset.mddSocioTirar), 1); if (typeof marcarConfigSuja === "function") marcarConfigSuja(); desenharConfig(); return; }
    if (!e.target.closest("[data-mdd-cert]")) return;
    if (typeof mostrarCertificado === "function") { if (typeof cert !== "undefined") cert.visao = "certificado"; mostrarCertificado(); }
  });

  /* Salvar: o de sempre, e o prestador da NFS-e com os campos daqui e o CNPJ. */
  const salvarAntes = salvarConfig;
  salvarConfig = async function () {   // eslint-disable-line no-func-assign
    const eraPerfil = cfg.secao === "perfil";
    const cnpj = ((cfg.rascunho || {}).escritorio || {}).cnpj || "";
    const r = await salvarAntes.apply(this, arguments);
    if (eraPerfil && mdd.socios) {
      // Os socios ficam nesta maquina ate o servidor guardar (escritorio.socios).
      const limpos = mdd.socios.filter((s) => (s.nome || "").trim());
      try { localStorage.setItem("paulus.socios", JSON.stringify(limpos)); } catch (err) { /* */ }
      mdd.socios = limpos; mdd.sociosBase = JSON.stringify(limpos);
    }
    if (eraPerfil && mdd.rascunho) {
      const dados = Object.assign({}, mdd.rascunho);
      const so = String(cnpj).replace(/\D/g, "");
      if (so) dados.documento = so;
      if (mdd.sujo || so !== String(mdd.base.documento || "")) {
        try {
          const x = await fetch("/api/nfse/prestador", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: dados }) });
          if (x.ok) { mdd.base = JSON.parse(JSON.stringify(dados)); mdd.sujo = false; }
        } catch (err) { /* a nota fiscal pede de novo quando precisar */ }
      }
    }
    return r;
  };
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-cfg-descartar]") && mdd.base) { mdd.rascunho = JSON.parse(JSON.stringify(mdd.base)); mdd.sujo = false; }
    if (e.target.closest("[data-cfg-descartar]") && mdd.sociosBase) mdd.socios = JSON.parse(mdd.sociosBase);
  }, true);

  const sec = CFG_SECOES.find((s) => s[0] === "perfil");
  if (sec) sec[1] = "Dados e informações";
  if (sec) sec[2] = "Seus dados e os do escritório, num lugar só. Entram nos documentos, nos recibos e na nota fiscal.";
})();

/* DESEMPENHO (pedido de 11/10/2026): o mesmo "Ir devagar quando eu usar o PC"
   de Assistente e modelo, num cartao no alto - e a mesma preferencia
   (cfg.rascunho.devagar), salva pelo Salvar alteracoes de sempre. */
(function () {
  if (typeof secaoDesempenho !== "function") return;
  const antes = secaoDesempenho;
  secaoDesempenho = function () {   // eslint-disable-line no-func-assign
    const html = antes.apply(this, arguments);
    const r = cfg.rascunho || {};
    const cartao = cartaoCfg("Uso do computador", metaCfg("quando a memória aperta"),
      '<div class="cfg-campos">' + ligaCfg("devagar", "Ir devagar quando eu usar o PC", "espera o computador desafogar antes de cada tarefa; a leitura demora mais e o computador continua seu", r.devagar) + "</div>");
    const fim = html.indexOf("</header>");
    return fim >= 0 ? html.slice(0, fim + 9) + cartao + html.slice(fim + 9) : cartao + html;
  };
})();

/* CONEXOES › CONTA GOOGLE (pedido de 11/10/2026): mesmo entrando com a conta
   Atos, o cartao oferece vincular a conta Google - o mesmo caminho do
   vinculo (entrarNoGoogleDoVinculo, js/45-vinculo.js), que depois libera
   Gmail, Agenda, Meet e Drive. */
(function () {
  if (typeof cartaoGoogle !== "function") return;
  const G = '<svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';
  const antes = cartaoGoogle;
  cartaoGoogle = function () {   // eslint-disable-line no-func-assign
    const d = gg.dados;
    const vinculado = typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado;
    if (d && (!d.configurado || !d.conta) && !vinculado) {
      return cartaoCfg("Conta Google", metaCfg("Gmail · Agenda e Meet · Drive"),
        '<p class="cfg-texto">Você entrou com a conta Atos. Vincule também a sua conta Google para usar o Gmail, a Agenda com Meet e o Drive aqui.</p>' +
        '<div class="cfg-botoes"><button class="com-icone" data-cx-vincular-google="1">' + G + "Vincular conta Google</button></div>");
    }
    return antes.apply(this, arguments);
  };
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-cx-vincular-google]");
    if (!b) return;
    b.disabled = true;
    b.lastChild.textContent = "abrindo o Google…";
    try {
      if (typeof entrarNoGoogleDoVinculo === "function") {
        await entrarNoGoogleDoVinculo("vincular", async () => {
          if (typeof lerVinculoGoogle === "function") await lerVinculoGoogle();
          if (typeof carregarGoogle === "function") await carregarGoogle();
          if (typeof desenharConfig === "function") desenharConfig();
        }, true);
      }
    } catch (err) { if (typeof avisoCert === "function") avisoCert(err.message, { tom: "erro" }); b.disabled = false; b.lastChild.textContent = "Vincular conta Google"; }
  });
  // O estado do vinculo chega junto com Conexoes.
  const carregarAntes = carregarSecao;
  carregarSecao = async function () {   // eslint-disable-line no-func-assign
    await carregarAntes.apply(this, arguments);
    if (cfg.secao === "conexoes" && typeof lerVinculoGoogle === "function") await lerVinculoGoogle();
  };
})();
