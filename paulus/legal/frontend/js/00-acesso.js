/* ------------------------------------------------------ acesso de fora */
/*
   O primeiro script da pagina (acesso-remoto/v0). Na janela do programa ele
   nao muda nada: a pagina pergunta "sou local?", ouve que sim, e segue.

   De fora - pelo tunel da Cloudflare, com sessao do PAULUS -, tres coisas:

     - todo pedido que altera algo leva o token anti-CSRF da sessao
       (X-PAULUS-CSRF). E aqui, embrulhando o fetch, e nao em cada uma das
       centenas de chamadas das telas: tela nova ja nasce protegida;
     - resposta 401 (sessao vencida: 30 min sem uso, 12 h de idade) leva de
       volta a tela de entrar, em vez de cada tela mostrar um erro diferente;
     - <html> ganha a classe `remoto`, e o que e so do computador do
       escritorio some ou avisa (css/31-acesso.css, js/42-acesso.js).

   Os pedidos que alteram algo esperam a resposta do "sou local?" antes de
   sair: sem ela nao se sabe se o token precisa ir.
*/

const acessoDeFora = { local: true, pessoa: null, csrf: "", pronto: null, permissoes: [] };

/* O PAULUS de equipe (docs/PLANO-EQUIPE.md): os dados sao do escritorio, e
   cada coisa diz quem a criou. Na janela do servidor, o nome so aparece no que
   veio de uma conta de fora (o resto e de quem esta ali); de fora, aparece em
   tudo. Devolve "" quando nao ha o que dizer. */
function quemCriou(nome, conta) {
  if (!nome) return "";
  return Number(conta) > 0 || !acessoDeFora.local ? String(nome) : "";
}

(function () {
  const original = window.fetch.bind(window);
  const SEGUROS = ["GET", "HEAD", "OPTIONS"];

  acessoDeFora.pronto = original("/api/acesso/eu", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : { local: true }))
    .then((d) => {
      acessoDeFora.local = d.local !== false;
      acessoDeFora.pessoa = d.pessoa || null;
      acessoDeFora.permissoes = d.permissoes || [];
      acessoDeFora.google = d.google || "";
      acessoDeFora.googleDisponivel = Boolean(d.google_disponivel);
      acessoDeFora.csrf = d.csrf || "";
      if (!acessoDeFora.local) document.documentElement.classList.add("remoto");
    })
    .catch(() => { /* sem resposta, fica como local: o servidor e quem barra */ });

  function mesmaOrigem(url) {
    return url.startsWith("/") || url.startsWith(location.origin + "/");
  }

  window.fetch = async function (entrada, opcoes) {
    const o = Object.assign({}, opcoes || {});
    const eRequest = typeof Request !== "undefined" && entrada instanceof Request;
    const url = typeof entrada === "string" ? entrada : (eRequest ? entrada.url : String(entrada || ""));
    const metodo = String(o.method || (eRequest ? entrada.method : "GET")).toUpperCase();
    const daqui = mesmaOrigem(url);
    if (daqui && !SEGUROS.includes(metodo)) {
      await acessoDeFora.pronto;
      if (!acessoDeFora.local && acessoDeFora.csrf) {
        const cab = new Headers(o.headers || (eRequest ? entrada.headers : undefined));
        cab.set("X-PAULUS-CSRF", acessoDeFora.csrf);
        o.headers = cab;
      }
    }
    const resposta = await original(entrada, o);
    if (!daqui || acessoDeFora.local) return resposta;
    if (resposta.status === 401 && resposta.headers.get("X-PAULUS-Sessao") === "acabou") {
      location.replace("/");
    } else if (resposta.status === 202 || (resposta.status === 403 && !SEGUROS.includes(metodo))) {
      // Proposta que foi para a fila, ou o que so se faz no escritorio: a
      // frase vem do servidor e aparece na barra de avisos, venha de que tela
      // vier. So para o que a pessoa pediu (gravar, mandar, apagar): a
      // leitura que uma tela faz sozinha ao abrir, e que e do escritorio,
      // nao merece aviso nenhum.
      resposta.clone().json().then((d) => {
        if (d && d.detail && typeof avisoCert === "function" && (d.proposto || resposta.status === 403)) {
          avisoCert(d.detail, { tom: d.proposto ? "ok" : "" });
        }
      }).catch(() => {});
    }
    return resposta;
  };

  function iniciais(nome) {
    const partes = String(nome || "").trim().split(/\s+/).filter(Boolean);
    return ((partes[0] || "?")[0] + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
  }

  async function sair() {
    try { await window.fetch("/api/acesso/sair", { method: "POST" }); } catch (e) { /* sai do mesmo jeito */ }
    location.replace("/");
  }

  /* De fora nao ha os botoes da janela do programa: no lugar deles, quem esta
     usando - as iniciais, o nome e o papel, num botao que abre a conta - e o
     Sair, so o icone. */
  function barraDeQuemEstaDeFora() {
    if (acessoDeFora.local || !acessoDeFora.pessoa) return;
    const barra = document.getElementById("barra-titulo");
    if (!barra || document.getElementById("acesso-remoto-barra")) return;
    const p = acessoDeFora.pessoa;
    const el = document.createElement("span");
    el.className = "acesso-remoto-barra";
    el.id = "acesso-remoto-barra";
    el.innerHTML =
      '<span class="acesso-de-fora-selo" title="Você está usando o PAULUS do escritório pela internet">' + ic("lan", 14) + "de fora</span>" +
      '<button type="button" class="acesso-conta-botao" data-minha-conta="1" title="Minha conta">' +
      '<span class="acesso-iniciais">' + esc(iniciais(p.nome)) + "</span>" +
      '<span class="acesso-conta-nome">' + esc(p.nome) + "</span>" +
      '<span class="acesso-conta-papel">' + (p.papel === "titular" ? "titular" : "colaborador") + "</span>" +
      ic("expand_more", 16) + "</button>" +
      '<button type="button" class="acesso-sair" data-sair="1" title="Sair" aria-label="Sair">' + ic("logout", 16) + "</button>";
    el.querySelector("[data-minha-conta]").addEventListener("click", minhaContaDeFora);
    el.querySelector("[data-sair]").addEventListener("click", (e) => { e.currentTarget.disabled = true; sair(); });
    barra.appendChild(el);
  }

  /* A conta de quem esta de fora. O titular troca a propria senha e derruba
     as sessoes - e as duas coisas pedem o codigo do autenticador de novo,
     mesmo com a sessao valida: sessao roubada nao faz nenhuma delas. */
  async function minhaContaDeFora() {
    const p = acessoDeFora.pessoa;
    const titular = p.papel === "titular";
    const linha = (acao, icone, titulo, sub, tom) =>
      '<button type="button" class="conta-acao' + (tom ? " " + tom : "") + '" data-conta-acao="' + acao + '">' +
      '<span class="caixa-tipo">' + ic(icone, 18) + '</span><span class="duas-linhas"><b>' + titulo + "</b><small>" + sub + "</small></span>" +
      ic("chevron_right", 18) + "</button>";
    const html =
      '<div class="conta-cabeca"><span class="acesso-iniciais grande">' + esc(iniciais(p.nome)) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" + esc(p.email) + " · " + (titular ? "titular" : "colaborador") + "</small></span></div>" +
      '<div class="conta-acoes">' +
      (titular
        ? linha("senha", "key", "Trocar minha senha", "pede a senha atual e o código do celular") +
          linha("sessoes", "group", "Encerrar todas as sessões", "todo mundo que está de fora sai, você também", "perigo")
        : "") +
      // O Google de trabalho da pessoa (E3b): o e-mail, a Agenda e o Drive dela.
      (acessoDeFora.googleDisponivel
        ? linha("google", "mail", acessoDeFora.google ? "Meu Google: " + esc(acessoDeFora.google) : "Conectar o meu Google",
          acessoDeFora.google ? "o seu e-mail, a sua Agenda e o seu Drive estão aqui · conectar de novo"
            : "para ver o seu e-mail, a sua Agenda e o seu Drive aqui no PAULUS")
        : "") +
      linha("sair", "logout", "Sair", "encerra esta sessão neste aparelho") + "</div>" +
      '<p class="conta-nota">' + (titular
        ? "As contas da equipe se criam e se mudam só no computador do escritório."
        : "Senha e autenticador se trocam com o titular, no computador do escritório.") + "</p>";
    let escolha = "";
    const aberto = dialogo({ titulo: "Minha conta", contexto: "Acesso de fora", html: html, confirmar: "Fechar", semCancelar: true, classe: "conta-dialogo" });
    document.querySelectorAll("[data-conta-acao]").forEach((b) => b.addEventListener("click", () => {
      escolha = b.dataset.contaAcao;
      if (dialogoAberto) dialogoAberto.fechar(null);
    }));
    await aberto;
    if (escolha === "sair") { sair(); return; }
    if (escolha === "google") {
      const r = await window.fetch("/api/acesso/google/iniciar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ finalidade: "servicos" }) });
      const d = await r.json().catch(() => ({}));
      if (r.ok && d.url) location.assign(d.url);
      else avisoCert(d.detail || "não consegui ir ao Google agora", { tom: "erro" });
      return;
    }
    if (!escolha) return;
    const codigo = { chave: "codigo", rotulo: "Código do autenticador", placeholder: "000000", max: 8, obrigatorio: true,
      dica: "os 6 números do Google Authenticator, ou um código de recuperação" };
    let url, corpo;
    if (escolha === "sessoes") {
      const r = await dialogo({
        titulo: "Encerrar todas as sessões?", contexto: "Minha conta",
        texto: "Todo mundo que está de fora sai agora — você também. Para entrar de novo: senha e código.",
        campos: [codigo], confirmar: "Encerrar", perigo: true,
      });
      if (!r || !r.ok) return;
      url = "/api/acesso/minhas-sessoes/encerrar";
      corpo = { codigo: r.valores.codigo };
    } else {
      const r = await dialogo({
        titulo: "Trocar minha senha", contexto: "Minha conta",
        texto: "Trocar a senha encerra as suas sessões; você entra de novo com a senha nova.",
        campos: [{ chave: "atual", rotulo: "Senha atual", tipo: "password" },
          { chave: "nova", rotulo: "Senha nova", tipo: "password", dica: "pelo menos 10 caracteres", obrigatorio: true },
          { chave: "repetir", rotulo: "Repita a senha nova", tipo: "password", obrigatorio: true }, codigo],
        confirmar: "Trocar a senha",
      });
      if (!r || !r.ok) return;
      if (r.valores.nova !== r.valores.repetir) { avisoCert("as duas senhas novas não são iguais", { tom: "erro" }); return; }
      url = "/api/acesso/minha-senha";
      corpo = { atual: r.valores.atual, nova: r.valores.nova, codigo: r.valores.codigo };
    }
    const resp = await window.fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    if (!resp.ok) {
      let msg = "não deu certo";
      try { msg = (await resp.json()).detail || msg; } catch (e) { /* fica a frase */ }
      // O 403 ja aparece pela barra de avisos (o fetch embrulhado, acima).
      if (resp.status !== 403) avisoCert(msg, { tom: "erro" });
      return;
    }
    location.replace("/");
  }
  acessoDeFora.pronto.then(() => {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", barraDeQuemEstaDeFora);
    else barraDeQuemEstaDeFora();
    // A volta de "Conectar o meu Google" (E3b): o resultado vem depois do #.
    const volta = new URLSearchParams(location.hash.slice(1));
    if (volta.get("google") || volta.get("google-erro")) {
      history.replaceState(null, "", location.pathname);
      const avisar = () => {
        if (typeof avisoCert !== "function") return;
        if (volta.get("google")) avisoCert("Google conectado: " + volta.get("google") + " — o seu e-mail, a sua Agenda e o seu Drive", { tom: "ok", dura: 7000 });
        else avisoCert(volta.get("google-erro"), { tom: "erro" });
      };
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => setTimeout(avisar, 800));
      else setTimeout(avisar, 800);
    }
  });
})();
