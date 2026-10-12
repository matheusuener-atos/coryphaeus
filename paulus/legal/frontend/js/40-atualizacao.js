/* ---------------------------------------------------------- atualizacao */
/*
   A versao nova do Paulus (src/atualizacao.py): o programa ve uma vez por
   dia, em paulus.ia.br/atualizacao.json, se ha versao nova - se a pessoa
   deixou ligado. Com "Avisar antes de instalar", a faixa do topo avisa e
   Configuracoes › Versao baixa (conferindo o SHA-256) e instala: o
   instalador abre no modo atualizar, fecha o Paulus, troca o programa e
   abre a versao nova. Sem o aviso, baixa sozinho e instala ao fechar.
*/

const atu = { dados: null, relogio: null };

async function carregarAtualizacao() {
  try { atu.dados = await (await fetch("/api/atualizacao")).json(); } catch (err) { atu.dados = null; }
  return atu.dados;
}

/* Na abertura e depois da verificacao do dia (que roda por tras, 30 s
   depois de abrir): a faixa do topo avisa, se a pessoa quer ser avisada. */
async function avisarAtualizacao() {
  const d = await carregarAtualizacao();
  if (!d || !d.anuncio || !d.anuncio.nova || !d.avisar_antes) return;
  avisoFixoNaJanela("Paulus " + d.anuncio.versao + " disponível · você está na " + d.atual + ".", {
    icone: "download",
    acao: { rotulo: "Ver a atualização", fazer: () => { avisoFixoNaJanela(null); abrirAtualizacaoEmConfiguracoes(); } },
  });
}

function abrirAtualizacaoEmConfiguracoes() {
  mostrarConfig("plano");
}

function tamanhoAtu(bytes) {
  if (!bytes) return "";
  const mb = bytes / 1048576;
  return (mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : Math.round(mb) + " MB").replace(".", ",");
}

/* O cartao Versao de Configuracoes › Versao. */
function blocoAtualizacao() {
  const d = atu.dados;
  const r = cfg.rascunho || {};
  const a = r.atualizacoes || {};
  if (!d) return '<p class="cfg-texto">Não consegui ler a situação da atualização.</p>';
  void a;
  const an = d.anuncio;
  const nova = Boolean(an && an.nova);
  const st = (t, classe) => '<b class="cfg-st ' + classe + '">' + esc(t) + "</b>";
  const chaves = '<div class="sv-ficha cfg-ficha">' +
    '<div class="sv-ficha-item"><span class="sv-kicker">Versão instalada</span><b>Paulus ' + esc(d.atual || "—") + "</b></div>" +
    '<div class="sv-ficha-item"><span class="sv-kicker">Situação</span>' +
      (d.erro ? st("Não foi possível verificar", "acc") : nova ? st("Versão " + an.versao + " disponível", "acc") : d.ultima_consulta ? st("Em dia", "ok") : st("Ainda não verificado", "cfg-mudo")) + "</div>" +
    '<div class="sv-ficha-item"><span class="sv-kicker">Última verificação</span><b' + (d.ultima_consulta ? "" : ' class="cfg-mudo"') + ">" +
      (d.ultima_consulta ? d.ultima_consulta.slice(8, 10) + "/" + d.ultima_consulta.slice(5, 7) + " às " + d.ultima_consulta.slice(11, 16) : "Nunca") + "</b></div></div>";
  const b = d.baixando || {};
  let estado;
  if (an && an.nova) {
    const novidades = (an.novidades || []).length
      ? '<ul class="atu-novidades">' + an.novidades.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>" : "";
    let acao;
    if (b.andando) {
      acao = '<div class="barra-fina"><i style="width:' + (b.progresso || 1) + '%"></i></div>' +
        '<p class="cfg-explica">Baixando · ' + tamanhoAtu(b.baixado) + (b.total ? " de " + tamanhoAtu(b.total) : "") +
        ' · <button type="button" class="em-ligacao" data-cfg-atu="cancelar">cancelar</button></p>';
    } else if (d.pronto) {
      acao = d.instalado
        ? '<p class="cfg-explica">Baixado e conferido (SHA-256). Instalar fecha o Paulus, troca o programa e abre a versão nova — os dados ficam.</p>' +
          '<div class="cfg-botoes"><button class="primario com-icone" data-cfg-atu="instalar">' + ic("download", 16) + "Instalar agora</button></div>"
        : '<p class="cfg-explica">Este Paulus roda do código-fonte: para atualizar, use git pull.</p>';
    } else {
      acao = (b.erro ? '<p class="cfg-explica acc">O download parou: ' + esc(b.erro) + "</p>" : "") +
        '<div class="cfg-botoes"><button class="primario com-icone" data-cfg-atu="baixar">' + ic("download", 16) +
        (b.erro ? "Tentar de novo" : "Baixar a atualização") + (an.tamanho ? " · " + tamanhoAtu(an.tamanho) : "") + "</button>" +
        (an.notas ? '<button data-cfg-atu-notas="' + esc(an.notas) + '">' + ic("open_in_new", 16) + "Notas da versão</button>" : "") + "</div>";
    }
    estado = '<div class="atu-nova"><b>Paulus ' + esc(an.versao) + " disponível</b>" +
      (an.publicada ? "<small> · publicada em " + esc(an.publicada.slice(8, 10) + "/" + an.publicada.slice(5, 7)) + "</small>" : "") +
      novidades + acao + "</div>";
  } else {
    estado = d.erro ? '<p class="cfg-explica">' + esc(d.erro) + "</p>" : "";
  }
  return chaves + estado +
    '<div class="cfg-botoes cfg-botoes-fim"><button class="com-icone" data-cfg-novidades="1">' + ic("article", 16) + "O que mudou nesta versão</button>" +
    '<button class="com-icone" data-cfg-atu="verificar">' + ic("refresh", 16) + "Verificar agora</button></div>";
}

/* O segundo cartao: como as atualizacoes chegam. */
function blocoAtualizacaoAuto() {
  const a = (cfg.rascunho || {}).atualizacoes || {};
  return '<div class="cfg-sub">' +
    ligaCfg("atualizacoes.verificar", "Procurar versão nova todo dia", "O Paulus consulta paulus.ia.br uma vez por dia. Nenhum dado seu vai junto.", a.verificar !== false) +
    ligaCfg("atualizacoes.avisar_antes", "Perguntar antes de instalar", a.avisar_antes !== false
      ? "Você decide quando instalar a versão nova."
      : "A versão nova é baixada sozinha e instalada na próxima vez que você fechar o Paulus.", a.avisar_antes !== false) +
    "</div>";
}

async function acaoAtualizacao(qual) {
  if (qual === "verificar") avisoCert("vendo se há versão nova…");
  const rotas = { verificar: "/api/atualizacao/verificar", baixar: "/api/atualizacao/baixar", cancelar: "/api/atualizacao/cancelar", instalar: "/api/atualizacao/instalar" };
  let r;
  try {
    r = await fetch(rotas[qual], { method: "POST" });
  } catch (err) {
    avisoCert("não consegui: " + err, { tom: "erro" });
    return;
  }
  if (!r.ok) { avisoCert(maiuscula(await erroDe(r)), { tom: "erro" }); return; }
  if (qual === "instalar") {
    avisoCert("abrindo o instalador — o Paulus fecha e volta na versão nova", { dura: 0 });
    return;
  }
  atu.dados = await r.json();
  if (qual === "verificar") {
    const an = atu.dados.anuncio;
    avisoCert(atu.dados.erro ? atu.dados.erro : (an && an.nova ? "Paulus " + an.versao + " disponível" : "você está na versão mais nova"),
      { tom: atu.dados.erro ? "erro" : "ok" });
  }
  if ($("cfg-tela")) desenharConfig();
  acompanharAtualizacao();
}

/* Enquanto baixa, a tela se redesenha a cada segundo e meio. */
function acompanharAtualizacao() {
  clearTimeout(atu.relogio);
  if (!atu.dados || !(atu.dados.baixando || {}).andando) return;
  atu.relogio = setTimeout(async () => {
    await carregarAtualizacao();
    if ($("cfg-tela") && cfg.secao === "plano") desenharConfig();
    acompanharAtualizacao();
  }, 1500);
}

function ligarAtualizacao(raiz) {
  (raiz || document).querySelectorAll("[data-cfg-atu]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); acaoAtualizacao(b.dataset.cfgAtu); };
  });
  (raiz || document).querySelectorAll("[data-cfg-atu-notas]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); window.open(b.dataset.cfgAtuNotas, "_blank"); };
  });
  acompanharAtualizacao();
}
