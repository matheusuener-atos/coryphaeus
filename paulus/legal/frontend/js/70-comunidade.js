/* ------------------------------------------ materiais entre advogados (L9) */
/*
   A aba "Da comunidade" na Biblioteca (src/comunidade.py): ver o que outros
   advogados publicaram no site do PAULUS e trazer para a Biblioteca, e
   mandar um material seu - com a conferência dos dados pessoais antes, e o
   e-mail para o projeto, que a pessoa revisa. Só na janela do escritório.
*/

const com = { lista: null, erro: "", preparado: null };
const AREAS_COM = ["civil", "consumidor", "processo civil", "trabalho", "penal", "tributário", "família e sucessões", "empresarial",
  "administrativo", "previdenciário", "constitucional", "imobiliário", "outra"];

function abaComunidadeBib() {
  const lista = com.lista;
  const cartoes = lista ? (lista.materiais.length ? lista.materiais.map((m) =>
    '<div class="com-material"><div class="com-cab"><b>' + esc(m.titulo) + "</b><small>" +
    esc([m.autor + (m.oab ? " · OAB " + m.oab : ""), (m.areas || []).join(", "), String(m.publicado_em || "").slice(0, 10).split("-").reverse().join("/")].filter(Boolean).join(" · ")) + "</small></div>" +
    (m.resumo ? '<p class="com-resumo">' + esc(m.resumo) + "</p>" : "") +
    '<div class="com-pe"><span class="com-licenca">' + esc(m.licenca || "CC BY 4.0") + "</span>" +
    '<button data-com-trazer="' + esc(m.slug) + '">' + ic("download", 16) + "Trazer para a Biblioteca</button></div></div>").join("")
    : '<p class="cfg-explica">Nenhum material publicado ainda.</p>') : "";
  const areas = AREAS_COM.map((a) => '<option value="' + esc(a) + '">' + esc(a) + "</option>").join("");
  const p = com.preparado;
  const achados = p ? (p.achados.length
    ? '<div class="com-achados"><p><b>Antes de mandar, tire estes dados (ou confirme que tem autorização):</b></p><ul>' +
      p.achados.map((a) => "<li>" + esc(a.tipo) + ": <code>" + esc(a.trecho) + "</code></li>").join("") + "</ul></div>"
    : '<p class="cfg-explica">' + ic("check", 14) + " Não achei CPF, CNPJ, número de processo, e-mail, telefone nem nome de cliente do escritório.</p>") +
    '<p class="cfg-explica">Nome de pessoa que não é cliente cadastrado a regra não reconhece: releia o texto.</p>' +
    '<label class="com-conferi"><input type="checkbox" id="com-conferi"> Tirei os dados pessoais (ou tenho autorização) e autorizo publicar sob a licença CC BY 4.0</label>' +
    '<div class="cfg-botoes"><button class="primario com-icone" data-com-email="1">' + (typeof marcaDoEmail === "function" ? marcaDoEmail(16) : "") + "Escrever o e-mail</button></div>" : "";
  return aberturaBib("Da comunidade", "Materiais que outros advogados publicaram no site do PAULUS, com licença aberta, e o seu, se quiser publicar.") +
    cartaoCfg("No site do PAULUS", metaCfg("lido só quando você pede"),
      '<p class="cfg-explica">Para ver a lista, o PAULUS pede ao site paulus.ia.br o arquivo público com os materiais. Nada do escritório vai junto. ' +
      "O material trazido entra na Biblioteca com a origem “comunidade”, o autor e a licença, e é conferido pelo hash que a lista publica.</p>" +
      (com.erro ? '<p class="cfg-explica">' + esc(com.erro) + "</p>" : "") +
      (lista ? '<div class="com-lista">' + cartoes + "</div>" : '<div class="cfg-botoes"><button data-com-ver="1">' + ic("menu_book", 16) + "Ver os materiais</button></div>")) +
    cartaoCfg("Publicar um material seu", metaCfg("moderado antes de entrar"),
      '<div class="cfg-campos">' +
      '<div class="ag-campo"><label>Título</label><input type="text" id="com-titulo" placeholder="A multa moratória no contrato de locação"></div>' +
      '<div class="ag-campo"><label>Como o autor aparece</label><input type="text" id="com-autor" placeholder="Maria Souza"></div>' +
      '<div class="ag-campo"><label>OAB (opcional)</label><input type="text" id="com-oab" placeholder="SP 123.456"></div>' +
      '<div class="ag-campo"><label>Área</label><select id="com-area">' + areas + "</select></div>" +
      '<div class="ag-campo"><label>Resumo</label><input type="text" id="com-resumo" placeholder="em uma linha"></div>' +
      '<div class="ag-campo"><label>Texto</label><textarea id="com-texto" rows="8" placeholder="cole aqui o texto do material"></textarea></div></div>' +
      '<div class="cfg-botoes"><button data-com-preparar="1">' + ic("rule", 16) + "Conferir os dados pessoais</button></div>" + achados +
      '<p class="cfg-explica">O material vai por e-mail para contato@paulus.ia.br, pela sua conta, e você revisa antes (como o feedback). ' +
      "Ele é lido antes de entrar no site; publicado, fica sob a licença CC BY 4.0: outros podem usar, citando você.</p>");
}

function ligarComunidadeBib() {
  const tela = $("bib-tela");
  if (!tela) return;
  const ver = tela.querySelector("[data-com-ver]");
  if (ver) ver.onclick = async () => {
    ver.disabled = true;
    const r = await fetch("/api/comunidade/materiais");
    com.erro = r.ok ? "" : await erroDe(r);
    com.lista = r.ok ? await r.json() : null;
    desenharBib();
  };
  tela.querySelectorAll("[data-com-trazer]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch("/api/comunidade/materiais/" + encodeURIComponent(b.dataset.comTrazer) + "/trazer", { method: "POST" });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); b.disabled = false; return; }
      avisoCert("Entrou na Biblioteca, com a origem “comunidade”.", { tom: "ok" });
      b.textContent = "Na Biblioteca";
    };
  });
  const preparar = tela.querySelector("[data-com-preparar]");
  if (preparar) preparar.onclick = async () => {
    const v = (id) => (($(id) || {}).value || "").trim();
    const r = await fetch("/api/comunidade/preparar", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo: v("com-titulo"), autor: v("com-autor"), oab: v("com-oab"), area: v("com-area"), resumo: v("com-resumo"),
        texto: v("com-texto") }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const guardar = { titulo: v("com-titulo"), autor: v("com-autor"), oab: v("com-oab"), area: v("com-area"), resumo: v("com-resumo"), texto: v("com-texto") };
    com.preparado = await r.json();
    desenharBib();
    Object.entries({ "com-titulo": guardar.titulo, "com-autor": guardar.autor, "com-oab": guardar.oab, "com-resumo": guardar.resumo, "com-texto": guardar.texto })
      .forEach(([id, valor]) => { if ($(id)) $(id).value = valor; });
    const area = $("com-area");
    if (area) { area.value = guardar.area; area.dispatchEvent(new Event("change")); }
  };
  const email = tela.querySelector("[data-com-email]");
  if (email) email.onclick = async () => {
    if (!($("com-conferi") || {}).checked) { avisoCert("marque que tirou os dados pessoais (ou tem autorização)", { tom: "erro" }); return; }
    const e = com.preparado.email;
    let contas = [];
    try { contas = ((await (await fetch("/api/email/contas")).json()).contas) || []; } catch (err) { contas = []; }
    if (!contas.length) { copiarTexto(e.assunto + "\n\n" + e.corpo, "sem conta de e-mail no PAULUS: copiei o material — mande para " + e.para); return; }
    telaEscrever({ para: e.para, assunto: e.assunto, corpo: e.corpo });
  };
}
