/* ------------------------------------------------------------ backup */
/*
   Configuracoes › Backup (src/backup.py, docs/PLANO-PRODUTO.md P1). Tudo do
   escritorio mora neste computador: o backup e um arquivo cifrado com uma
   senha que so o escritorio sabe, numa pasta que ele escolhe (HD externo,
   pasta de rede, pasta sincronizada pelo Google Drive para computador),
   automatico uma vez por dia. Restaurar prepara os dados e a troca entra
   quando o PAULUS abre de novo - os de antes ficam guardados ao lado.
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
  const estado = '<div class="cfg-linhas">' +
    chaveCfg("Último backup", b.ultimo ? quandoBackup(b.ultimo) : "nunca", b.ultimo_erro ? "" : (b.ultimo ? "ok" : "")) +
    chaveCfg("Pasta", b.pasta || "não escolhida") +
    chaveCfg("Senha", b.tem_senha ? "definida" : "não definida") + "</div>" +
    (b.ultimo_erro ? '<p class="acesso-erro">' + esc(b.ultimo_erro) + "</p>" : "") +
    (and.fazendo ? '<p class="cfg-explica">Fazendo o backup… ' + (and.total ? and.feitos + " de " + and.total + " arquivos" : "") + "</p>" : "") +
    '<div class="acesso-energia">' +
    ligaCfg("", "Backup automático", "uma vez por dia, com o PAULUS aberto; ficam os " + (b.manter || 10) + " mais novos", Boolean(b.automatico))
      .replace('class="ag-toggle', 'data-bkp-auto="1" class="ag-toggle') + "</div>" +
    '<div class="cfg-botoes"><button class="com-icone" data-bkp-pasta="1">' + ic("folder_open", 16) + (b.pasta ? "Trocar a pasta" : "Escolher a pasta") + "</button>" +
    '<button class="com-icone" data-bkp-senha="1">' + ic("key", 16) + (b.tem_senha ? "Trocar a senha" : "Definir a senha") + "</button>" +
    '<button class="primario com-icone" data-bkp-agora="1"' + (pronto && !and.fazendo ? "" : " disabled") + ">" + ic("archive", 16) + "Fazer backup agora</button></div>" +
    '<p class="cfg-explica">Guarde a senha fora deste computador: sem ela, ninguém abre o backup — nem você. ' +
    "Uma pasta sincronizada (Google Drive para computador, OneDrive) ou um HD externo protege contra perder o computador.</p>";

  const lista = (b.backups || []).length
    ? '<div class="cfg-linhas">' + b.backups.map((x) =>
        '<div class="chave-valor bkp-linha"><span>' + esc(quandoBackup(x.quando)) + " · " + esc(tamanhoBackup(x.bytes)) + "</span>" +
        '<button data-bkp-restaurar="' + esc(x.caminho) + '">Restaurar</button></div>').join("") + "</div>"
    : '<p class="cfg-texto">Nenhum backup na pasta ainda.</p>';
  const pendente = b.restauracao_pronta
    ? '<p class="cfg-texto"><b>Restauração pronta.</b> Ela entra quando o PAULUS abrir de novo; os dados de agora ficam guardados ao lado.</p>' +
      '<div class="cfg-botoes"><button class="primario com-icone" data-bkp-reabrir="1">' + ic("refresh", 16) + "Reabrir o PAULUS agora</button>" +
      '<button data-bkp-desistir="1">Desistir</button></div>'
    : "";
  const outros = bkp.outros
    ? '<p class="cfg-explica">Em ' + esc(bkp.outraPasta) + ":</p>" + (bkp.outros.length
        ? '<div class="cfg-linhas">' + bkp.outros.map((x) =>
            '<div class="chave-valor bkp-linha"><span>' + esc(quandoBackup(x.quando)) + " · " + esc(tamanhoBackup(x.bytes)) + "</span>" +
            '<button data-bkp-restaurar="' + esc(x.caminho) + '">Restaurar</button></div>').join("") + "</div>"
        : '<p class="cfg-texto">Nenhum backup do PAULUS nessa pasta.</p>')
    : "";
  return aberturaCfg() + cartaoCfg("Backup", meta, estado) +
    cartaoCfg("Restaurar", metaCfg("de um backup"), pendente + lista +
      '<div class="cfg-botoes"><button class="com-icone" data-bkp-outra="1">' + ic("folder_open", 16) + "Procurar backups em outra pasta</button></div>" + outros +
      '<p class="cfg-explica">Num computador novo: instale o PAULUS, abra esta tela e procure a pasta do backup. ' +
      "O que é protegido pelo Windows (as contas de e-mail e Google, o acesso de fora) pede entrar de novo.</p>");
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
        { chave: "senha", rotulo: "Senha", tipo: "password", obrigatorio: true, placeholder: "pelo menos " + ((cfg.backup || {}).senha_minima || 10) + " caracteres" },
        { chave: "repetir", rotulo: "Repita a senha", tipo: "password", obrigatorio: true },
      ],
      confirmar: "Guardar a senha",
    });
    if (!r || !r.ok) return;
    if (r.valores.senha !== r.valores.repetir) { avisoCert("as duas senhas não são iguais", { tom: "erro" }); return; }
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
      texto: "Os dados de agora ficam guardados ao lado (nada se perde), e os do backup entram quando o PAULUS abrir de novo.",
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
    try { await post("/api/backup/reabrir"); avisoCert("reabrindo o PAULUS…"); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
}
