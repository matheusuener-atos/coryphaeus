/* ------------------------------------------ Nota fiscal (NFS-e) — N1 */
/*
   Configurações › Nota fiscal: só na janela do escritório. Quem presta o
   serviço, o regime, o serviço padrão, as retenções (cada uma com "não sei,
   perguntar ao contador"), o IBS/CBS, o certificado A1 da nota e a
   verificação do município no Sistema Nacional (src/nfse/, src/rotas_nfse.py).

   Percentual e dinheiro vão como texto (`*_pct`, `*_reais`) e viram inteiro
   no servidor: nada de float no caminho do imposto.
*/

async function carregarNfse() {
  try {
    const [r, rec, prod] = await Promise.all([fetch("/api/nfse"), fetch("/api/nfse/recorrencias"), fetch("/api/nfse/producao")]);
    cfg.nfse = r.ok ? await r.json() : null;
    if (cfg.nfse) cfg.nfse.recorrencias = rec.ok ? (await rec.json()).recorrencias : [];
    if (cfg.nfse) cfg.nfse.producao = prod.ok ? await prod.json() : null;
  } catch (err) { cfg.nfse = null; }
}

function pctNfse(bp) {
  const b = Number(bp || 0);
  if (!b) return "";
  return Math.floor(b / 100) + "," + String(b % 100).padStart(2, "0");
}

function reaisNfse(c) {
  const n = Number(c || 0);
  if (!n) return "";
  return Math.floor(n / 100).toLocaleString("pt-BR") + "," + String(n % 100).padStart(2, "0");
}

function campoNfse(caminho, rotulo, valor, dica, extra) {
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-nfse-campo="' + caminho + '" value="' +
    esc(valor == null ? "" : String(valor)) + '"' + (dica ? ' placeholder="' + esc(dica) + '"' : "") + (extra || "") + "></div>";
}

function escolhaNfse(caminho, rotulo, opcoes, valor) {
  const linhas = Object.entries(opcoes || {}).map(([k, v]) =>
    '<option value="' + esc(k) + '"' + (String(k) === String(valor) ? " selected" : "") + ">" + esc(k === "" ? v : (k + " – " + v)) + "</option>").join("");
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><select data-nfse-campo="' + caminho + '">' + linhas + "</select></div>";
}

function linhaNfse(rotulo, valor, tom) {
  return '<div class="word-linha"><span>' + esc(rotulo) + '</span><b class="' + (tom || "") + '">' + esc(valor) + "</b></div>";
}

function secaoNfse() {
  const n = cfg.nfse;
  if (!n) return aberturaCfg() + '<p class="cfg-explica">Não consegui ler a configuração da nota fiscal agora.</p>';
  const p = n.prestador || {};
  const d = p.dados || {};
  const o = p.opcoes || {};
  const cert = n.certificado || {};
  const mun = n.municipio || {};

  const ficha = fichaCfg([
    ["Emissão", n.ligado ? "ligada" : "desligada", n.ligado ? "ok" : ""],
    ["Ambiente", n.ambiente === "producao" ? "produção" : "produção restrita", n.ambiente === "producao" ? "aviso" : ""],
    ["Município", mun.situacao === "conveniado" ? "emite pelo nacional" : (mun.situacao === "sem_convenio" ? "sem convênio" : "não confirmado"),
      mun.situacao === "conveniado" ? "ok" : ""],
    ["Certificado", cert.instalado ? ((cert.certificado || {}).valido_ate ? "até " + cert.certificado.valido_ate : "instalado") : "falta", cert.instalado ? "" : ""],
  ]);

  const ligar = cartaoCfg("Ligar", "",
    '<div class="ag-toggle' + (n.ligado ? " on" : "") + '" data-nfse-acao="ligar" role="switch" tabindex="0" aria-checked="' + n.ligado + '">' +
    '<span class="duas-linhas"><b>Emitir NFS-e pelo PAULUS</b><small>pelo Padrão Nacional, com o certificado A1 do escritório; cada nota passa por Aprovações antes de sair. ' +
    "O PAULUS aplica a configuração abaixo e não faz planejamento tributário.</small></span><i></i></div>" +
    (n.motivos && n.motivos.length && n.ligado
      ? '<p class="cfg-explica"><b>Ainda não dá para emitir:</b> ' + esc(n.motivos.join("; ")) + ".</p>" : "") +
    '<p class="cfg-explica">Ambiente: <b>' + esc(n.ambiente_rotulo || "") + "</b>. Produção só depois do checklist da liberação, pelo titular.</p>");

  const faltas = (p.faltas || []).length
    ? '<p class="cfg-explica"><b>Falta configurar:</b> ' + esc(p.faltas.join("; ")) + ".</p>" : "";

  const prestador = cartaoCfg("Quem presta o serviço", metaCfg(p.versao ? "versão " + p.versao : "ainda não configurado"),
    faltas + '<div class="cfg-campos">' +
    '<div class="ag-duas">' + campoNfse("documento", "CNPJ (ou CPF do advogado autônomo)", d.documento, "só números") +
    campoNfse("inscricao_municipal", "Inscrição municipal", d.inscricao_municipal) + "</div>" +
    campoNfse("razao_social", "Razão social", d.razao_social, "como no CNPJ") +
    '<div class="ag-duas">' + campoNfse("municipio", "Município (código IBGE)", d.municipio, "digite o nome e escolha", ' list="nfse-municipios" data-nfse-busca-municipio="1"') +
    '<div class="ag-campo"><label>Município</label><input type="text" readonly value="' + esc(p.municipio_nome || "") + '"></div></div>' +
    '<datalist id="nfse-municipios"></datalist>' +
    '<div class="ag-duas">' + campoNfse("endereco.logradouro", "Logradouro", (d.endereco || {}).logradouro) + campoNfse("endereco.numero", "Número", (d.endereco || {}).numero) + "</div>" +
    '<div class="ag-duas">' + campoNfse("endereco.complemento", "Complemento", (d.endereco || {}).complemento) + campoNfse("endereco.bairro", "Bairro", (d.endereco || {}).bairro) + "</div>" +
    '<div class="ag-duas">' + campoNfse("endereco.cep", "CEP", (d.endereco || {}).cep, "00000000") + campoNfse("telefone", "Telefone", d.telefone) + "</div>" +
    campoNfse("email", "E-mail", d.email) +
    '<div class="ag-duas">' + campoNfse("contador.nome", "Contador (nome)", (d.contador || {}).nome) +
    campoNfse("contador.email", "E-mail do contador (para o arquivo do mês)", (d.contador || {}).email) + "</div>" +
    campoNfse("pis_cofins.cst", "CST do PIS/COFINS (quando houver PIS/COFINS/CSLL retidos)", (d.pis_cofins || {}).cst, "o contador informa") + "</div>");

  const regime = cartaoCfg("Regime tributário", metaCfg("o contador confirma"),
    '<div class="cfg-campos">' +
    escolhaNfse("opcao_simples", "Situação no Simples Nacional", o.opcao_simples, d.opcao_simples) +
    escolhaNfse("regime_apuracao_sn", "Regime de apuração (só ME/EPP do Simples)", Object.assign({ "": "não se aplica" }, o.regime_apuracao_sn), d.regime_apuracao_sn) +
    escolhaNfse("regime_especial", "Regime especial de ISS", o.regime_especial, d.regime_especial) +
    '<div class="ag-duas">' + campoNfse("regime_federal", "Regime federal (rótulo)", d.regime_federal, "presumido, real, simples…") +
    campoNfse("anexo_simples", "Anexo do Simples (se houver)", d.anexo_simples) + "</div>" +
    '<p class="cfg-explica">Sociedade de advogados com ISS fixo costuma ser “6 – Sociedade de Profissionais”: com regime especial a nota não leva alíquota de ISS nem ISS retido (regras E0604 e E0588 da Sefin).</p></div>');

  const s = d.servico || {};
  const nbsOpcoes = { "": "escolha a NBS" };
  (o.nbs_sugeridas || []).forEach((x) => { nbsOpcoes[x.codigo] = x.nbs + " " + x.descricao; });
  const servico = cartaoCfg("Serviço padrão", metaCfg("tabelas oficiais"),
    '<div class="cfg-campos">' +
    '<div class="ag-duas">' + campoNfse("servico.ctribnac", "Código de tributação nacional", s.ctribnac, "171401") +
    '<div class="ag-campo"><label>Serviço</label><input type="text" readonly value="' + esc(p.servico_descricao || "") + '"></div></div>' +
    escolhaNfse("servico.nbs", "NBS (depende da área do escritório)", nbsOpcoes, s.nbs) +
    '<div class="ag-duas">' + campoNfse("servico.ctribmun", "Código municipal (3 dígitos, se o município usar)", s.ctribmun) +
    campoNfse("servico.aliquota_iss_pct", "Alíquota do ISS do município (%)", pctNfse(s.aliquota_iss_bp), "ex.: 5 ou 2,5") + "</div>" +
    campoNfse("servico.descricao", "Descrição padrão", s.descricao, "Honorários advocatícios") +
    '<p class="cfg-explica">171401 é “Advocacia” (item 17.14 da LC 116) na lista nacional. Quando o município tem convênio, quem aplica a alíquota é a Sefin; a daqui serve para a previsão do cartão.</p></div>');

  const quando = o.quando_reter || {};
  const ret = d.retencoes || {};
  const linhasRet = Object.entries(o.retencoes || {}).map(([k, rot]) => {
    const r = ret[k] || {};
    return '<div class="nfse-retencao"><b>' + esc(rot) + '</b><small class="cfg-explica">' + esc((o.explica_retencao || {})[k] || "") + "</small>" +
      '<div class="ag-duas">' + escolhaNfse("retencoes." + k + ".quando", "Quando reter", quando, r.quando) +
      (k === "iss" ? "" : campoNfse("retencoes." + k + ".aliquota_pct", "Alíquota (%)", pctNfse(r.aliquota_bp), "ex.: 1,5")) + "</div>" +
      (k === "iss" ? "" : campoNfse("retencoes." + k + ".minimo_reais", "Não reter quando o valor retido ficar abaixo de (R$)", reaisNfse(r.minimo_centavos), "deixe vazio se não houver")) +
      "</div>";
  }).join("");
  const retencoes = cartaoCfg("Retenções", metaCfg("regra do escritório ou do contador"),
    '<p class="cfg-explica">O PAULUS aplica a regra escrita aqui. <b>“Não sei — perguntar ao contador”</b> deixa a retenção desligada e o cartão da nota avisa. PIS, COFINS e CSLL retidos vão somados num campo só da nota (NT 007).</p>' + linhasRet);

  const ib = d.ibscbs || {};
  const sug = (o.nbs_sugeridas || []).find((x) => x.codigo === s.nbs) || (o.nbs_sugeridas || [])[0];
  const ibscbs = cartaoCfg("IBS e CBS", metaCfg("reforma tributária"),
    '<div class="cfg-campos">' +
    '<div class="ag-toggle' + (ib.enviar ? " on" : "") + '" data-nfse-acao="ibscbs" role="switch" tabindex="0"><span class="duas-linhas"><b>Mandar o grupo IBS/CBS na nota</b>' +
    "<small>exigido desde 03/08/2026 fora do Simples; para o Simples, a partir de 2027. A Sefin calcula os valores; a nota só declara a classificação.</small></span><i></i></div>" +
    '<div class="ag-duas">' + campoNfse("ibscbs.cst", "CST do IBS/CBS (3 dígitos)", ib.cst) + campoNfse("ibscbs.cclasstrib", "cClassTrib (6 dígitos)", ib.cclasstrib) + "</div>" +
    campoNfse("ibscbs.cindop", "Indicador da operação (cIndOp)", ib.cindop, "100301") +
    (sug ? '<p class="cfg-explica">A tabela oficial de correlação sugere, para a advocacia, cIndOp <b>' + esc(sug.cindop) + "</b> e cClassTrib <b>" + esc(sug.cclasstrib) +
      "</b> (“" + esc(sug.descricao_cclasstrib) + "”). O próprio portal diz que é um trabalho inicial, sem regra de negócio: <b>confirme com o contador</b> antes de usar.</p>" : "") + "</div>");

  const tt = d.total_tributos || {};
  const total = cartaoCfg("Total aproximado de tributos", metaCfg("Lei 12.741/2012"),
    '<div class="cfg-campos">' + escolhaNfse("total_tributos.modo", "Como informar", { percentual: "percentuais federal, estadual e municipal", simples: "percentual do Simples (só ME/EPP)" }, tt.modo) +
    '<div class="ag-duas">' + campoNfse("total_tributos.federal_pct", "Federal (%)", pctNfse(tt.federal_bp)) + campoNfse("total_tributos.estadual_pct", "Estadual (%)", pctNfse(tt.estadual_bp)) + "</div>" +
    '<div class="ag-duas">' + campoNfse("total_tributos.municipal_pct", "Municipal (%)", pctNfse(tt.municipal_bp)) + campoNfse("total_tributos.simples_pct", "Simples (%)", pctNfse(tt.simples_bp)) + "</div></div>");

  const salvar = '<div class="word-acoes"><button class="primario" data-nfse-acao="salvar">' + ic("save", 16) + "Gravar a configuração</button>" +
    '<span class="cfg-explica">Cada gravação vira uma versão nova: nota já emitida guarda a versão com que foi feita.</span></div>';

  const c = cert.certificado || {};
  const certCorpo = (cert.instalado
    ? linhaNfse("Titular", c.titular || "—") + linhaNfse("Documento", c.documento || "—") + linhaNfse("Validade", c.valido_ate ? "até " + c.valido_ate : "—", c.vencido ? "erro" : "") +
      linhaNfse("Senha", cert.senha_guardada ? "guardada nesta conta do Windows" : (cert.minutos_restantes ? "na memória por " + cert.minutos_restantes + " min" : "pedida a cada uso")) +
      (cert.avisos || []).map((a) => '<p class="cfg-explica"><b>' + esc(a) + "</b></p>").join("") +
      (cert.precisa_senha ? '<div class="ag-duas"><div class="ag-campo"><label>Senha do certificado</label><input type="password" id="nfse-senha-desbloquear"></div>' +
        '<div class="ag-campo"><label>&nbsp;</label><button data-nfse-acao="desbloquear">Usar a senha</button></div></div>' : "")
    : '<p class="cfg-explica">A nota é assinada e enviada com o certificado A1 do prestador (e-CNPJ da sociedade, ou e-CPF do autônomo), em arquivo .pfx ou .p12. O A3 (token) não serve, e o certificado instalado no Windows sem exportar também não.</p>') +
    '<div class="ag-duas"><div class="ag-campo"><label>Arquivo .pfx ou .p12</label><input type="file" id="nfse-pfx" accept=".pfx,.p12"></div>' +
    '<div class="ag-campo"><label>Senha</label><input type="password" id="nfse-pfx-senha" autocomplete="off"></div></div>' +
    '<label class="cfg-explica"><input type="checkbox" id="nfse-pfx-guardar"> Guardar a senha nesta conta do Windows (cifrada; sem isso, ela vale 15 minutos)</label>' +
    '<div class="word-acoes"><button data-nfse-acao="certificado">' + ic("upload", 16) + (cert.instalado ? "Trocar o certificado" : "Instalar o certificado") + "</button>" +
    (cert.instalado ? '<button data-nfse-acao="remover-certificado">Tirar o certificado</button>' : "") + "</div>";
  const certificadoCartao = cartaoCfg("Certificado A1 da nota", metaCfg("separado do de assinar PDF"), certCorpo);

  const municipio = cartaoCfg("O município emite pelo nacional?", metaCfg(mun.consultado_em ? "consultado em " + mun.consultado_em.slice(0, 16).replace("T", " ") : "não consultado"),
    '<p class="cfg-explica">' + esc(mun.frase || "") + "</p>" +
    (mun.reconsultar && mun.consultado_em ? '<p class="cfg-explica">A consulta tem mais de 30 dias: consulte de novo.</p>' : "") +
    '<div class="word-acoes"><button data-nfse-acao="municipio">' + ic("search", 16) + "Consultar agora</button></div>");

  const tabs = (p.tabelas || []).map((t) => linhaNfse(t.titulo, "v" + t.versao + (t.data ? " · " + t.data : "") + " · " + t.itens + " itens")).join("");
  const tabelas = cartaoCfg("Tabelas oficiais", metaCfg("Portal da NFS-e"),
    tabs + '<p class="cfg-explica">Vêm das planilhas oficiais (municípios, lista de serviços, NBS, indicador da operação). Quando o portal publicar uma versão nova, importe a planilha aqui.</p>' +
    '<div class="word-acoes"><input type="file" id="nfse-planilha" accept=".xlsx"><button data-nfse-acao="planilha">Importar planilha</button></div>');

  const hist = (p.historico || []).map((h) => linhaNfse("versão " + h.id + " · " + (h.motivo || ""), (h.criado_em || "").slice(0, 16).replace("T", " "))).join("");
  const historico = hist ? cartaoCfg("Histórico da configuração", "", hist) : "";

  const contador = cartaoCfg("Notas do mês e contador", metaCfg("relatório, XMLs e conferência"),
    '<p class="cfg-explica">O relatório do mês soma os XMLs das notas (o que a Sefin calculou), confere por regra recebimento sem nota, nota sem recebimento, valor divergente, retenção não aplicada e competência de outro mês, e monta o .zip para o contador.</p>' +
    '<div class="word-acoes"><button data-nfse-acao="relatorio">' + ic("description", 16) + "Abrir o relatório do mês</button></div>");

  const recs = (n.recorrencias || []).map((x) => linhaNfse((x.servico_nome || x.cliente_nome || "—") + " · dia " + x.dia + " · " + x.valor,
    x.ativo ? "ligada" + (x.ultimo_mes ? " · último mês feito " + x.ultimo_mes : "") : "desligada") +
    (x.ativo ? '<div class="word-acoes"><button data-nfse-rec-desligar="' + x.id + '">Desligar</button></div>' : "")).join("");
  const recorrencias = cartaoCfg("Honorários recorrentes", metaCfg("rascunho no dia; nunca emite sozinho"),
    (recs || '<p class="cfg-explica">Nenhuma. Ligue no Serviço, em Horas › Nota todo mês.</p>') +
    '<p class="cfg-explica">No dia, o PAULUS cria o rascunho da nota do mês e o põe em Aprovações. Se faltar algo no cadastro do cliente, o rascunho espera por você, com aviso.</p>');

  const pr = n.producao || { itens: [] };
  const itensProd = (pr.itens || []).map((i) => linhaNfse((i.ok ? "✓ " : "· ") + i.titulo, i.detalhe, i.ok ? "ok" : "")).join("");
  const producao = cartaoCfg("Produção", metaCfg(pr.liberada ? "liberada" : "produção restrita"),
    itensProd +
    (pr.liberada
      ? '<p class="cfg-explica"><b>A produção está liberada:</b> as notas novas valem de verdade. A primeira pede uma confirmação a mais.</p>' +
        '<div class="word-acoes"><button data-nfse-acao="voltar">Voltar para produção restrita</button></div>'
      : '<p class="cfg-explica">Enquanto não liberar, nada sai para a produção: a nota é emitida em produção restrita, sem valor fiscal.</p>' +
        '<div class="word-acoes"><button data-nfse-acao="revisado">Registrar a revisão do contador</button>' +
        '<button data-nfse-acao="testes">Marcar as notas de teste como conferidas</button>' +
        '<button class="primario" data-nfse-acao="liberar"' + (pr.pode_liberar ? "" : " disabled") + ">Liberar a produção</button></div>"));

  return aberturaCfg() + ficha + ligar + prestador + regime + servico + retencoes + ibscbs + total + salvar +
    certificadoCartao + municipio + contador + recorrencias + producao + tabelas + historico;
}

function dadosDoFormNfse() {
  const dados = {};
  document.querySelectorAll("[data-nfse-campo]").forEach((el) => {
    const partes = el.dataset.nfseCampo.split(".");
    let alvo = dados;
    partes.slice(0, -1).forEach((p) => { alvo[p] = alvo[p] || {}; alvo = alvo[p]; });
    alvo[partes[partes.length - 1]] = el.value;
  });
  const ib = document.querySelector('[data-nfse-acao="ibscbs"]');
  if (ib) { dados.ibscbs = dados.ibscbs || {}; dados.ibscbs.enviar = ib.classList.contains("on"); }
  return dados;
}

async function acaoNfse(acao) {
  const json = async (url, corpo) => {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  const arquivo = async (url, campos) => {
    const fd = new FormData();
    Object.entries(campos).forEach(([k, v]) => fd.append(k, v));
    const r = await fetch(url, { method: "POST", body: fd });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
    return r.json();
  };
  let d = null;
  if (acao === "relatorio") { if (typeof abrirRelatorioNfse === "function") abrirRelatorioNfse(); return; }
  if (acao === "revisado" || acao === "testes") {
    const r = await dialogo({ titulo: acao === "revisado" ? "Quem revisou a configuração fiscal?" : "Quem conferiu as notas de teste?",
      contexto: "Nota fiscal › Produção", campo: { rotulo: "Nome", placeholder: acao === "revisado" ? "o contador" : "quem conferiu no portal e no DANFSe" },
      confirmar: "Registrar" });
    if (!r || !r.ok) return;
    const x = await json(acao === "revisado" ? "/api/nfse/producao/revisado" : "/api/nfse/producao/testes-conferidos", { por: r.valor });
    if (x) { await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "liberar") {
    const ok = await dialogo({ titulo: "Liberar a produção?", contexto: "Nota fiscal › Produção",
      texto: "Depois disto, as notas novas valem de verdade e vão para o Sistema Nacional de produção. Dá para voltar para a produção restrita a qualquer momento.",
      confirmar: "Liberar a produção", perigo: true });
    if (!ok || !ok.ok) return;
    const x = await json("/api/nfse/producao/liberar", { confirmo: true });
    if (x) { avisoCert("produção liberada", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "voltar") {
    const x = await json("/api/nfse/producao/voltar");
    if (x) { avisoCert("de volta à produção restrita", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (acao === "ligar") d = await json("/api/nfse/ligar", { ligado: !(cfg.nfse && cfg.nfse.ligado) });
  else if (acao === "ibscbs") {
    const b = document.querySelector('[data-nfse-acao="ibscbs"]');
    if (b) b.classList.toggle("on");
    return;
  } else if (acao === "salvar") {
    d = await json("/api/nfse/prestador", { dados: dadosDoFormNfse() });
    if (d) avisoCert("configuração gravada", { tom: "ok" });
  } else if (acao === "certificado") {
    const f = document.getElementById("nfse-pfx");
    if (!f || !f.files || !f.files[0]) { avisoCert("escolha o arquivo .pfx ou .p12", { tom: "erro" }); return; }
    d = await arquivo("/api/nfse/certificado", { arquivo: f.files[0], senha: (document.getElementById("nfse-pfx-senha") || {}).value || "",
      guardar: (document.getElementById("nfse-pfx-guardar") || {}).checked ? "1" : "" });
    if (d) avisoCert("certificado instalado", { tom: "ok" });
  } else if (acao === "desbloquear") {
    d = await json("/api/nfse/certificado/senha", { senha: (document.getElementById("nfse-senha-desbloquear") || {}).value || "" });
  } else if (acao === "remover-certificado") {
    const ok = await dialogo({ titulo: "Tirar o certificado da nota?", contexto: "Configurações › Nota fiscal",
      texto: "A cópia do .pfx e a senha guardada saem deste computador. Para emitir de novo, instale outra vez.", confirmar: "Tirar", perigo: true });
    if (!ok || !ok.ok) return;
    d = await json("/api/nfse/certificado/remover");
  } else if (acao === "municipio") {
    avisoCert("perguntando ao Sistema Nacional…", { tom: "info" });
    d = await json("/api/nfse/municipio/consultar");
  } else if (acao === "planilha") {
    const f = document.getElementById("nfse-planilha");
    if (!f || !f.files || !f.files[0]) { avisoCert("escolha a planilha .xlsx do portal", { tom: "erro" }); return; }
    const r = await arquivo("/api/nfse/tabelas/importar", { arquivo: f.files[0] });
    if (r) { avisoCert("tabela importada", { tom: "ok" }); await carregarNfse(); desenharConfig(); }
    return;
  }
  if (d) { cfg.nfse = d; desenharConfig(); }
}

document.addEventListener("click", async (e) => {
  const rec = e.target.closest("[data-nfse-rec-desligar]");
  if (rec) {
    const r = await fetch("/api/nfse/recorrencias/" + rec.dataset.nfseRecDesligar + "/desligar", { method: "POST" });
    if (r.ok) { await carregarNfse(); desenharConfig(); }
    return;
  }
  const b = e.target.closest("[data-nfse-acao]");
  if (!b) return;
  acaoNfse(b.dataset.nfseAcao);
});
document.addEventListener("keydown", (e) => {
  const b = e.target.closest && e.target.closest('[data-nfse-acao="ligar"], [data-nfse-acao="ibscbs"]');
  if (b && (e.key === " " || e.key === "Enter")) { e.preventDefault(); acaoNfse(b.dataset.nfseAcao); }
});

/* O município pelo nome: a lista oficial do IBGE (src/nfse/tabelas.py). */
let nfseBuscaRelogio = 0;
document.addEventListener("input", (e) => {
  const el = e.target;
  if (!el.matches || !el.matches("[data-nfse-busca-municipio]")) return;
  const q = el.value.trim();
  if (q.length < 3 || /^\d{7}$/.test(q)) return;
  clearTimeout(nfseBuscaRelogio);
  nfseBuscaRelogio = setTimeout(async () => {
    const r = await fetch("/api/nfse/municipios?q=" + encodeURIComponent(q)).catch(() => null);
    if (!r || !r.ok) return;
    const itens = (await r.json()).itens || [];
    const lista = document.getElementById("nfse-municipios");
    if (lista) lista.innerHTML = itens.map((m) => '<option value="' + esc(m.codigo) + '">' + esc(m.nome + "/" + m.uf) + "</option>").join("");
  }, 250);
});
