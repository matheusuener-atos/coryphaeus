/* ------------------------------------------------------------ backup */
/*
   Configuracoes › Backup (src/backup.py, docs/PLANO-PRODUTO.md P1). Tudo do
   escritorio mora neste computador: o backup e um arquivo cifrado com uma
   senha que so o escritorio sabe, numa pasta que ele escolhe (HD externo,
   pasta de rede, pasta sincronizada pelo Google Drive para computador),
   automatico uma vez por dia. Restaurar prepara os dados e a troca entra
   quando o Paulus abre de novo - os de antes ficam guardados ao lado.
*/

const bkp = { relogio: null, outros: null, outraPasta: "" };

function quandoBackup(iso) {
  if (!iso) return "nunca";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR") + " às " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function tamanhoBackup(b) {
  return b >= 1e9 ? (b / 1e9).toFixed(1).replace(".", ",") + " GB" : b >= 1e6 ? Math.round(b / 1e6) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB";
}

function secaoBackup() {
  if (typeof acessoDeFora !== "undefined" && !acessoDeFora.local) {
    return aberturaCfg() + cartaoCfg("Backup", "", '<p class="cfg-texto">O backup se configura no computador do escritório.</p>');
  }
  const b = cfg.backup || {};
  const and = b.andamento || {};
  const pronto = b.pasta && b.tem_senha;
  const meta = and.fazendo ? pontoCfg("fazendo o backup", "acc") : b.ultimo_erro ? pontoCfg("falhou", "acc")
    : b.ultimo ? pontoCfg("em dia", "ok") : metaCfg(pronto ? "ainda não fez" : "desligado");
  // 1. A situacao: o que ja esta guardado e o botao de agora.
  const st = (txt, classe) => '<b class="cfg-st ' + classe + '">' + esc(txt) + "</b>";
  const situacao = '<div class="sv-ficha cfg-ficha">' +
    '<div class="sv-ficha-item"><span class="sv-kicker">Último backup</span>' + (b.ultimo_erro ? st("Falhou", "acc") : b.ultimo ? st(quandoBackup(b.ultimo), "ok") : st("Nenhum ainda", "cfg-mudo")) + "</div>" +
    '<div class="sv-ficha-item"><span class="sv-kicker">Automático</span>' + (b.automatico ? st("Todo dia", "ok") : st("Desligado", "cfg-mudo")) + "</div>" +
    '<div class="sv-ficha-item"><span class="sv-kicker">Guardados</span>' + ((b.backups || []).length ? st((b.backups.length === 1 ? "1 cópia" : b.backups.length + " cópias") + " na pasta", "ok") : st("Nenhuma cópia", "cfg-mudo")) + "</div></div>" +
    (b.ultimo_erro ? '<p class="acesso-erro">' + esc(b.ultimo_erro) + "</p>" : "") +
    (and.fazendo ? '<p class="cfg-explica">Fazendo o backup… ' + (and.total ? and.feitos + " de " + and.total + " arquivos" : "") + "</p>" : "") +
    (pronto ? "" : '<p class="cfg-explica">Para começar, escolha a pasta e crie a senha no cartão abaixo.</p>') +
    '<div class="cfg-botoes"><button class="primario com-icone" data-bkp-agora="1"' + (pronto && !and.fazendo ? "" : " disabled") + ">" + ic("archive", 16) + "Fazer backup agora</button></div>";

  // 2. A configuracao: onde, com que senha e quando.
  const linha = (icone, nome, sub, botao) => '<div class="cfg-servico"><span class="caixa-tipo">' + ic(icone, 18) + '</span><span class="duas-linhas"><b>' + nome + "</b><small>" + esc(sub) + "</small></span>" +
    '<span class="cfg-botoes">' + botao + "</span></div>";
  const config = '<div class="cfg-linhas">' +
    linha("folder_open", "Onde guardar", b.pasta || "Nenhuma pasta escolhida. Prefira um HD externo ou uma pasta do Google Drive ou do OneDrive.",
      '<button class="com-icone" data-bkp-pasta="1">' + (b.pasta ? "Trocar" : "Escolher pasta") + "</button>") +
    linha("key", "Senha do backup", b.tem_senha ? "Criada. Guarde-a fora deste computador." : "Sem senha ainda. Ela tranca o arquivo do backup.",
      '<button class="com-icone" data-bkp-senha="1">' + (b.tem_senha ? "Trocar" : "Criar senha") + "</button>") + "</div>" +
    (typeof blocoDoBackupNoLado === "function" ? blocoDoBackupNoLado() : "") +
    '<div class="acesso-energia">' +
    ligaCfg("", "Fazer sozinho todo dia", "uma vez por dia, enquanto o Paulus estiver aberto; ficam as " + (b.manter || 10) + " cópias mais novas", Boolean(b.automatico))
      .replace('class="ag-toggle', 'data-bkp-auto="1" class="ag-toggle') + "</div>" +
    '<p class="cfg-explica"><b>Sem a senha, ninguém abre o backup, nem você.</b> Anote-a num lugar seguro fora deste computador.</p>';

  const lista = (b.backups || []).length
    ? '<div class="cfg-linhas">' + b.backups.map((x) =>
        '<div class="chave-valor bkp-linha"><span>' + esc(quandoBackup(x.quando)) + " · " + esc(tamanhoBackup(x.bytes)) + "</span>" +
        '<button data-bkp-restaurar="' + esc(x.caminho) + '">Restaurar</button></div>').join("") + "</div>"
    : '<p class="cfg-texto">Nenhum backup na pasta ainda.</p>';
  const pendente = b.restauracao_pronta
    ? '<p class="cfg-texto"><b>Restauração pronta.</b> Ela entra quando o Paulus abrir de novo; os dados de agora ficam guardados ao lado.</p>' +
      '<div class="cfg-botoes"><button class="primario com-icone" data-bkp-reabrir="1">' + ic("refresh", 16) + "Reabrir o Paulus agora</button>" +
      '<button data-bkp-desistir="1">Desistir</button></div>'
    : "";
  const outros = bkp.outros
    ? '<p class="cfg-explica">Em ' + esc(bkp.outraPasta) + ":</p>" + (bkp.outros.length
        ? '<div class="cfg-linhas">' + bkp.outros.map((x) =>
            '<div class="chave-valor bkp-linha"><span>' + esc(quandoBackup(x.quando)) + " · " + esc(tamanhoBackup(x.bytes)) + "</span>" +
            '<button data-bkp-restaurar="' + esc(x.caminho) + '">Restaurar</button></div>').join("") + "</div>"
        : '<p class="cfg-texto">Nenhum backup do Paulus nessa pasta.</p>')
    : "";
  return aberturaCfg() + cartaoCfg("Backup", meta, situacao) + cartaoCfg("Onde e como guardar", metaCfg(pronto ? "configurado" : "falta configurar"), config) +
    cartaoCfg("Restaurar", metaCfg("de um backup"), pendente + lista +
      '<div class="cfg-botoes"><button class="com-icone" data-bkp-outra="1">' + ic("folder_open", 16) + "Procurar backups em outra pasta</button></div>" + outros +
      '<p class="cfg-explica">Num computador novo: instale o Paulus, abra esta tela e procure a pasta do backup. ' +
      "O que é protegido pelo Windows (as contas de e-mail e Google, o acesso externo) pede entrar de novo.</p>");
}

async function atualizarBackupCfg() {
  try { cfg.backup = await fetch("/api/backup").then((r) => r.json()); } catch (err) { /* fica como estava */ }
  if (cfg.secao === "backup") desenharConfig();
}

function ligarBackupCfg() {
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  const post = async (url, corpo) => {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "não deu certo");
    return d;
  };
  clearInterval(bkp.relogio);
  if ((cfg.backup || {}).andamento && cfg.backup.andamento.fazendo) bkp.relogio = setInterval(atualizarBackupCfg, 1500);

  clique("[data-bkp-pasta]", async () => {
    const pasta = await escolherPastaDoSistema("Pasta do backup");
    if (!pasta) return;
    try { cfg.backup = await post("/api/backup/configurar", { pasta: pasta }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-senha]", async () => {
    const r = await dialogo({
      titulo: "Senha do backup", contexto: "Configurações › Backup",
      texto: "Com ela o backup é cifrado: sem a senha, ninguém abre o arquivo — nem você. Guarde fora deste computador.",
      campos: [
        { chave: "senha", rotulo: "Senha", tipo: "password", obrigatorio: true, placeholder: "pelo menos " + ((cfg.backup || {}).senha_minima || 10) + " caracteres",
          conferir: (x) => (x.length < ((cfg.backup || {}).senha_minima || 10) ? "a senha precisa de pelo menos " + ((cfg.backup || {}).senha_minima || 10) + " caracteres" : "") },
        { chave: "repetir", rotulo: "Repita a senha", tipo: "password", obrigatorio: true, igualA: "senha", frase: "as duas senhas não são iguais" },
      ],
      confirmar: "Guardar a senha",
    });
    if (!r || !r.ok) return;
    try { cfg.backup = await post("/api/backup/configurar", { senha: r.valores.senha }); avisoCert("senha do backup guardada", { tom: "ok" }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-auto]", async (b) => {
    try { cfg.backup = await post("/api/backup/configurar", { automatico: !b.classList.contains("on") }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-agora]", async () => {
    try { cfg.backup = await post("/api/backup/agora"); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-outra]", async () => {
    const pasta = await escolherPastaDoSistema("Pasta com os backups");
    if (!pasta) return;
    try { bkp.outros = (await post("/api/backup/listar", { pasta: pasta })).backups || []; bkp.outraPasta = pasta; }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-restaurar]", async (b) => {
    const r = await dialogo({
      titulo: "Restaurar este backup?", contexto: "Configurações › Backup",
      texto: "Os dados de agora ficam guardados ao lado (nada se perde), e os do backup entram quando o Paulus abrir de novo.",
      campos: [{ chave: "senha", rotulo: "Senha do backup", tipo: "password", obrigatorio: true }],
      confirmar: "Preparar a restauração",
    });
    if (!r || !r.ok) return;
    try { cfg.backup = await post("/api/backup/restaurar", { arquivo: b.dataset.bkpRestaurar, senha: r.valores.senha }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-desistir]", async () => {
    try { cfg.backup = await post("/api/backup/restaurar/cancelar"); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    desenharConfig();
  });
  clique("[data-bkp-reabrir]", async () => {
    try { await post("/api/backup/reabrir"); avisoCert("reabrindo o Paulus…"); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
}
