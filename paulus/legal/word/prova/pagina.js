// Prova de conceito da W0: o que este Word aceita, se a página insere texto
// e se alcança o PAULUS. O resultado volta ao servidor de onde a página veio
// (POST "relato"), para ser lido sem olhar a tela.
"use strict";

(function () {
  var qs = new URLSearchParams(location.search);
  var montagem = qs.get("m") || "?";
  var alvo = qs.get("alvo") || "";
  var relato = { montagem: montagem, origem: location.origin, alvo: alvo, passos: [] };

  function anota(passo, dados) {
    relato.passos.push(Object.assign({ passo: passo, ms: Math.round(performance.now()) }, dados || {}));
    var el = document.getElementById("saida");
    if (el) el.textContent = JSON.stringify(relato, null, 1);
  }

  function envia() {
    try {
      return fetch("relato", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(relato),
      }).catch(function () {});
    } catch (e) { return Promise.resolve(); }
  }

  function conjuntos() {
    var r = {};
    var s = Office.context.requirements;
    ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9"].forEach(function (v) {
      r["WordApi " + v] = s.isSetSupported("WordApi", v);
    });
    ["1.1", "1.2", "1.3", "1.4"].forEach(function (v) {
      r["WordApiDesktop " + v] = s.isSetSupported("WordApiDesktop", v);
    });
    // Aba própria e menu do botão direito (AddinCommands), atalhos de
    // teclado (KeyboardShortcuts, que pedem o SharedRuntime) e tema.
    [["AddinCommands", "1.1"], ["AddinCommands", "1.3"], ["SharedRuntime", "1.1"],
     ["KeyboardShortcuts", "1.1"], ["RibbonApi", "1.1"], ["ContextMenuApi", "1.1"]].forEach(function (p) {
      r[p[0] + " " + p[1]] = s.isSetSupported(p[0], p[1]);
    });
    r["tema"] = Office.context.officeTheme ? {
      fundo: Office.context.officeTheme.bodyBackgroundColor,
      texto: Office.context.officeTheme.bodyForegroundColor,
      controle: Office.context.officeTheme.controlBackgroundColor,
      escuro: Office.context.officeTheme.isDarkTheme,
    } : null;
    r["DialogApi 1.1"] = s.isSetSupported("DialogApi", "1.1");
    r["IdentityAPI 1.3"] = s.isSetSupported("IdentityAPI", "1.3");
    return r;
  }

  // "alvo" aceita vários endereços separados por vírgula: mede cada um.
  function chamaUm(base) {
    var t0 = performance.now();
    return fetch(base.replace(/\/$/, "") + "/api/status", {
      method: "GET", cache: "no-store",
      // Cabeçalho próprio força o preflight, como o token do suplemento fará.
      headers: { "Authorization": "Bearer prova" },
    })
      .then(function (r) {
        return r.text().then(function (txt) {
          anota("status", { alvo: base, ok: r.ok, http: r.status, corpo: txt.slice(0, 200), ms_req: Math.round(performance.now() - t0) });
        });
      })
      .catch(function (e) {
        anota("status", { alvo: base, ok: false, erro: String(e && e.message || e), ms_req: Math.round(performance.now() - t0) });
      });
  }

  function chamaPaulus() {
    if (!alvo) return Promise.resolve(anota("status", { pulado: "sem alvo" }));
    return alvo.split(",").reduce(function (p, base) {
      return p.then(function () { return chamaUm(base); });
    }, Promise.resolve());
  }

  function insere() {
    if (!Office.context.requirements.isSetSupported("WordApi", "1.1")) {
      anota("inserir", { ok: false, erro: "sem WordApi 1.1" });
      return Promise.resolve();
    }
    return Word.run(function (ctx) {
      var p = ctx.document.body.insertParagraph("Olá do PAULUS (montagem " + montagem + ")", "End");
      p.load("text");
      var corpo = ctx.document.body;
      corpo.load("text");
      return ctx.sync().then(function () {
        anota("inserir", { ok: true, paragrafo: p.text, tamanho_corpo: corpo.text.length });
      });
    }).catch(function (e) {
      anota("inserir", { ok: false, erro: String(e && e.message || e), codigo: e && e.code });
    });
  }

  function provaComentario() {
    if (!Office.context.requirements.isSetSupported("WordApi", "1.4")) {
      return Promise.resolve(anota("comentario", { pulado: "sem WordApi 1.4" }));
    }
    return Word.run(function (ctx) {
      var achados = ctx.document.body.search("Olá do PAULUS", { matchCase: true });
      achados.load("items");
      return ctx.sync().then(function () {
        if (!achados.items.length) return anota("comentario", { ok: false, erro: "não achou o trecho" });
        achados.items[0].insertComment("Comentário de prova do PAULUS");
        return ctx.sync().then(function () { anota("comentario", { ok: true }); });
      });
    }).catch(function (e) {
      anota("comentario", { ok: false, erro: String(e && e.message || e) });
    });
  }

  function provaAlteracaoControlada() {
    // changeTrackingMode é da WordApi 1.4; a lista de alterações (aceitar,
    // rejeitar pelo código) é da 1.6. Para inserir controlado basta a 1.4.
    if (!Office.context.requirements.isSetSupported("WordApi", "1.4")) {
      return Promise.resolve(anota("controlada", { pulado: "sem WordApi 1.4" }));
    }
    return Word.run(function (ctx) {
      ctx.document.load("changeTrackingMode");
      return ctx.sync().then(function () {
        var antes = ctx.document.changeTrackingMode;
        ctx.document.changeTrackingMode = Word.ChangeTrackingMode.trackAll;
        ctx.document.body.insertParagraph("Inserido como alteração controlada", "End");
        return ctx.sync().then(function () {
          ctx.document.changeTrackingMode = antes;
          return ctx.sync();
        }).then(function () { anota("controlada", { ok: true, modo_antes: antes }); });
      });
    }).catch(function (e) {
      anota("controlada", { ok: false, erro: String(e && e.message || e) });
    });
  }

  // Sem a WordApi 1.4 (Word 2021/2019), comentário e alteração controlada
  // pela API não existem. O insertOoxml é da 1.1: se o pacote OOXML levar
  // <w:ins> e um comentário, o Word os aceita?
  var PKG = '<pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage">' +
    '<pkg:part pkg:name="/_rels/.rels" pkg:contentType="application/vnd.openxmlformats-package.relationships+xml"><pkg:xmlData>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>' +
    '</pkg:xmlData></pkg:part>' +
    '<pkg:part pkg:name="/word/_rels/document.xml.rels" pkg:contentType="application/vnd.openxmlformats-package.relationships+xml"><pkg:xmlData>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/></Relationships>' +
    '</pkg:xmlData></pkg:part>' +
    '<pkg:part pkg:name="/word/document.xml" pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"><pkg:xmlData>' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p>' +
    '<w:ins w:id="901" w:author="PAULUS" w:date="2026-10-01T00:00:00Z"><w:r><w:t xml:space="preserve">Trecho controlado via OOXML. </w:t></w:r></w:ins>' +
    '<w:commentRangeStart w:id="0"/><w:r><w:t>Trecho comentado via OOXML.</w:t></w:r><w:commentRangeEnd w:id="0"/>' +
    '<w:r><w:commentReference w:id="0"/></w:r>' +
    '</w:p></w:body></w:document></pkg:xmlData></pkg:part>' +
    '<pkg:part pkg:name="/word/comments.xml" pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"><pkg:xmlData>' +
    '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:comment w:id="0" w:author="PAULUS" w:initials="P" w:date="2026-10-01T00:00:00Z"><w:p><w:r><w:t>Comentário de prova (OOXML)</w:t></w:r></w:p></w:comment></w:comments>' +
    '</pkg:xmlData></pkg:part></pkg:package>';

  function provaOoxml() {
    return Word.run(function (ctx) {
      ctx.document.body.insertParagraph("", "End").insertOoxml(PKG, "Replace");
      return ctx.sync().then(function () {
        var x = ctx.document.body.getOoxml();
        return ctx.sync().then(function () {
          var s = x.value;
          anota("ooxml", {
            ok: true,
            tem_ins: /<w:ins\b[^>]*w:author="PAULUS"/.test(s),
            tem_referencia_comentario: s.indexOf("commentReference") >= 0,
            tem_parte_comentarios: s.indexOf("Comentário de prova (OOXML)") >= 0,
          });
        });
      });
    }).catch(function (e) {
      anota("ooxml", { ok: false, erro: String(e && e.message || e), codigo: e && e.code });
    });
  }

  anota("carregou", { ua: navigator.userAgent, seguro: window.isSecureContext });

  if (typeof Office === "undefined") {
    anota("office", { ok: false, erro: "office.js não carregou" });
    envia();
    return;
  }

  Office.onReady(function (info) {
    var diag = Office.context.diagnostics || {};
    anota("office", {
      ok: true, host: info.host, plataforma: info.platform,
      versao: diag.version, plataforma_diag: diag.platform,
      conjuntos: conjuntos(),
    });
    document.getElementById("montagem").textContent = "Montagem " + montagem;
    insere()
      .then(provaComentario)
      .then(provaAlteracaoControlada)
      .then(provaOoxml)
      .then(chamaPaulus)
      .then(function () { anota("fim"); return envia(); });
  });
})();
