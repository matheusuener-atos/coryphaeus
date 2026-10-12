/* O CERTIFICADO DIGITAL EM CONEXOES (pedido de 11/10/2026): um cartao so para
   o A1 do escritorio - enviar, Windows, senha, validade - e onde ele e usado
   (assinatura de documentos e nota fiscal). Sai da Assinatura (que fica com o
   selo) e da Nota fiscal (que mostra um resumo e o atalho para ca).
   Reaproveita cartaoDoCertificado/ligarCertificado de js/15. */
(function () {
  if (typeof secaoConexoes !== "function" || typeof cartaoDoCertificado !== "function") return;
  let naConfig = false;

  const carregarAntes = carregarSecao;
  carregarSecao = async function () {   // eslint-disable-line no-func-assign
    await carregarAntes.apply(this, arguments);
    if (cfg.secao !== "certificado") return;
    cert.dados = cfg.cert || {};
    try { const r = await fetch("/api/nfse"); cfg.nfseCert = r.ok ? ((await r.json()).certificado || {}) : {}; } catch (e) { cfg.nfseCert = {}; }
  };

  function usos() {
    const d = cert.dados || {};
    const c = d.certificado || {};
    const n = cfg.nfseCert || {};
    const nc = n.certificado || {};
    const mesmo = n.instalado && (!c.documento || !nc.documento || String(nc.documento) === String(c.documento));
    const ponto = (t, tom) => '<span class="fin-meta-ponto' + (tom ? " " + tom : "") + '"><i></i>' + esc(t) + "</span>";
    const linha = (icone, nome, sub, estado, acao) => '<div class="cfg-servico"><span class="caixa-tipo">' + ic(icone, 18) + '</span><span class="duas-linhas"><b>' + nome + "</b><small>" + esc(sub) + "</small></span>" +
      estado + '<span class="cfg-botoes">' + (acao || "") + "</span></div>";
    return '<div class="cfx-usos">' +
      linha("draw", "Assinatura de documentos", "o selo fica em Selo de assinatura, mais abaixo", d.instalado ? ponto("em uso", "ok") : ponto("sem certificado", ""),
        "") +
      linha("receipt_long", "Nota fiscal (NFS-e)", mesmo ? "as notas saem assinadas com este certificado" : n.instalado ? "as notas usam outro certificado" : "as notas ainda não têm certificado",
        mesmo ? ponto("em uso", "ok") : ponto(n.instalado ? "outro certificado" : "sem certificado", n.instalado ? "acc" : ""),
        d.instalado && !mesmo ? '<button class="com-icone" data-cfx-nfse="1">' + ic("check", 16) + "Usar também nas notas</button>" : "") +
      "</div>";
  }

  const secaoAntes = secaoConexoes;
  secaoConexoes = function () {   // eslint-disable-line no-func-assign
    naConfig = true;
    let html;
    try { html = secaoAntes.apply(this, arguments); }
    finally { naConfig = false; }
    // A linha "Certificado digital" sai da lista de Servicos: agora tem secao propria.
    return html.replace(/<div class="cfg-servico"><span class="caixa-tipo">(?:(?!<div class="cfg-servico">)[\s\S])*?data-cfg-cx-cert="1"[\s\S]*?<\/span><\/div>/, "");
  };

  /* Configuracoes › Certificado digital (pedido de 11/10/2026): o que era a
     aba Certificados de Conexoes. */
  window.secaoCertificado = function () {
    if (!cert.dados) cert.dados = cfg.cert || {};
    naConfig = true;
    let cartao;
    try { cartao = cartaoDoCertificado(); } finally { naConfig = false; }
    const d = cert.dados || {};
    /* "Sem um certificado a mao?" sai do upload e vira cartao proprio. */
    let teste = "";
    cartao = cartao.replace(/<div class="as-teste"><b>[^<]*<\/b><p>([\s\S]*?)<\/p>(<button id="cert-teste">[\s\S]*?<\/button>)<\/div>/, (m, texto, botao) => {
      teste = cartaoCfg("Certificado de teste", metaCfg("sem validade jurídica"),
        '<p class="cfg-explica">' + texto + '</p><div class="cfg-botoes">' + botao.replace('<button id="cert-teste">', '<button class="com-icone" id="cert-teste">' + ic("workspace_premium", 16)) + "</div>");
      return "";
    });
    return aberturaCfg() +
      '<div id="cfg-cert" class="cfx-cert">' + cartaoCfg("Certificado digital", metaCfg(d.instalado ? "A1 do escritório" : "nenhum instalado"), cartao) + "</div>" +
      cartaoCfg("Onde ele é usado", metaCfg("assinatura e nota fiscal"), usos()) + teste +
      (() => {
        /* Os numeros das assinaturas saem do selo e ganham cartao proprio. */
        let chaves = "";
        const corpo = corpoDoSelo().replace(/<div class="painel-chaves">([\s\S]*?<\/b><\/div>)<\/div>(?=<div class="as-painel-rodape">)/, (m, dentro) => { chaves = dentro; return ""; });
        return '<div id="cfg-selo" class="cfx-selo">' + cartaoCfg("Selo de assinatura", metaCfg("prévia em tamanho real"), corpo) + "</div>" +
          (chaves ? cartaoCfg("Assinaturas", metaCfg("feitas com este certificado"), '<div class="painel-chaves cfx-assinaturas">' + chaves + "</div>") : "");
      })();
  };

  /* Fotografar e Assistentes de fora saem de Conexoes para a Biblioteca:
     Acervo e indice (com Fotografar) e Codigos de lei (com o MCP). */
  if (typeof secaoAprendizado === "function") {
    const aprAntes = secaoAprendizado;
    secaoAprendizado = function () {   // eslint-disable-line no-func-assign
      const html = aprAntes.apply(this, arguments);
      const s = cfg.status || {};
      const p = cfg.prefs || {};
      const indice = '<div class="cfg-chaves">' +
        chaveCfg("Pasta do acervo", p.pasta_acervo || "—") +
        chaveCfg("Documentos indexados", String(s.contratos || 0)) +
        chaveCfg("Trechos no índice", String(s.trechos || 0)) + "</div>" +
        '<div class="cfg-botoes cfg-botoes-fim"><button data-cfg-reindexar="1">' + ic("sync", 16) + "Reindexar tudo</button>" +
        '<button data-cfg-cache="1">' + ic("delete", 16) + "Limpar cache</button></div>" +
        (typeof interruptorFotografar === "function" ? interruptorFotografar() : "");
      return html +
        cartaoCfg("Acervo e índice", metaCfg("o que a busca enxerga"), indice) +
        cartaoCfg("Códigos de lei", metaCfg("para citar artigo com o texto certo"),
          '<div id="cfg-leis"><p class="nota">abrindo os códigos…</p></div>' + (typeof corpoMcp === "function" ? corpoMcp() : "") + '<div id="cfg-leis-botoes"></div>');
    };
  }

  /* O selo (antes a coluna da Assinatura › Certificado digital) vira um
     cartao de Conexoes: o mesmo painelDoSelo, sem a casca de coluna. */
  function corpoDoSelo() {
    if (typeof painelDoSelo !== "function") return "";
    const d = cert.dados || {};
    if (!d.selo) d.selo = {};
    return painelDoSelo()
      .replace('<aside class="acervo-painel"><div class="rolagem as-painel">', '<div class="cfx-selo-corpo">')
      .replace(/<div class="painel-cabeca">[\s\S]*?<\/span><\/span><\/div>/, "")
      .replace(/<\/div><\/aside>$/, "</div>");
  }

  /* "Certificado digital" (no topo da Assinatura e em todo atalho) agora so
     leva a Configuracoes › Conexoes, no cartao do certificado. */
  function rolarAte(id) {
    const el = document.getElementById(id);
    if (!el) return;
    let p = el.parentElement;
    while (p && !(p.scrollHeight > p.clientHeight && /(auto|scroll)/.test(getComputedStyle(p).overflowY))) p = p.parentElement;
    if (p) p.scrollTo({ top: el.getBoundingClientRect().top - p.getBoundingClientRect().top + p.scrollTop - 16, behavior: "smooth" });
  }
  mostrarCertificado = async function (alvo) {   // eslint-disable-line no-func-assign
    marcarDestino("config");
    await mostrarConfig("certificado");
    requestAnimationFrame(() => rolarAte(alvo || "cfg-cert"));
  };

  /* Na Assinatura, o lugar do certificado vira um resumo com o atalho; os
     campos escondidos deixam ligarCertificado seguir ate o selo. */
  const cartaoAntes = cartaoDoCertificado;
  cartaoDoCertificado = function () {   // eslint-disable-line no-func-assign
    if (!cert.dados) cert.dados = {};
    if (naConfig) return cartaoAntes.apply(this, arguments);
    const d = cert.dados || {};
    const c = d.certificado || {};
    return '<div class="as-cartao"><div class="as-cartao-topo"><span class="cresce">Certificado digital</span>' + (d.instalado ? seloDeSituacao() : "") + '</div><div class="as-rolagem">' +
      '<div class="as-bloco cfx-aponta">' + ic("workspace_premium", 24) +
      '<span class="duas-linhas"><b>' + esc(d.instalado ? (c.titular || "Certificado instalado") : "Nenhum certificado instalado") + "</b><small>" +
      esc(d.instalado ? [c.tipo || "A1", c.valido_ate ? "vence em " + dataBR(c.valido_ate) : ""].filter(Boolean).join(" · ") : "instale em Configurações › Certificado digital") + "</small></span>" +
      '<button class="com-icone" data-cfx-ir="1">' + ic("settings", 16) + (d.instalado ? "Gerenciar certificado" : "Instalar certificado") + "</button></div>" +
      '<p class="as-explica">O certificado agora fica em Configurações › Certificado digital, junto do selo.</p>' +
      '<div hidden><div id="cert-solta"></div><button id="cert-escolher"></button><button id="cert-ver-windows"></button><input type="file" id="cert-arquivo" hidden></div>' +
      "</div></div>";
  };

  // Depois de enviar, trocar ou remover em Conexoes, redesenha Conexoes (nao a Assinatura).
  const desenharAntes = desenharAssinatura;
  desenharAssinatura = function () {   // eslint-disable-line no-func-assign
    if (document.getElementById("cfg-tela") && cfg.secao === "certificado" && document.getElementById("cfg-cert")) { cfg.cert = cert.dados; desenharConfig(); return; }
    return desenharAntes.apply(this, arguments);
  };

  const ligarAntes = ligarConfig;
  ligarConfig = function () {   // eslint-disable-line no-func-assign
    ligarAntes.apply(this, arguments);
    if (cfg.secao !== "certificado" || !document.getElementById("cfg-cert")) return;
    try { ligarCertificado(); } catch (e) { console.warn("certificado/selo:", e); }
  };

  document.addEventListener("click", async (e) => {
    if (e.target.closest("[data-cfx-ir]")) { marcarDestino("config"); mostrarConfig("certificado"); return; }
    if (e.target.closest("[data-cfx-selo]")) { rolarAte("cfg-selo"); return; }
    const b = e.target.closest("[data-cfx-nfse]");
    if (b) {
      b.disabled = true;
      const r = await fetch("/api/nfse/certificado/do-assinador", { method: "POST" });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); b.disabled = false; return; }
      avisoCert("as notas fiscais passam a usar este certificado", { tom: "ok" });
      await carregarSecao(); desenharConfig();
    }
  });
})();
