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

const acessoDeFora = { local: true, pessoa: null, csrf: "", pronto: null };

(function () {
  const original = window.fetch.bind(window);
  const SEGUROS = ["GET", "HEAD", "OPTIONS"];

  acessoDeFora.pronto = original("/api/acesso/eu", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : { local: true }))
    .then((d) => {
      acessoDeFora.local = d.local !== false;
      acessoDeFora.pessoa = d.pessoa || null;
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

  /* De fora nao ha os botoes da janela do programa: no lugar deles, quem
     esta usando e o Sair. */
  function barraDeQuemEstaDeFora() {
    if (acessoDeFora.local || !acessoDeFora.pessoa) return;
    const barra = document.getElementById("barra-titulo");
    if (!barra || document.getElementById("acesso-remoto-barra")) return;
    const el = document.createElement("span");
    el.className = "acesso-remoto-barra";
    el.id = "acesso-remoto-barra";
    const nome = document.createElement("span");
    nome.textContent = "De fora como " + acessoDeFora.pessoa.nome;
    const sair = document.createElement("button");
    sair.type = "button";
    sair.textContent = "Sair";
    sair.onclick = async () => {
      sair.disabled = true;
      try { await window.fetch("/api/acesso/sair", { method: "POST" }); } catch (e) { /* sai do mesmo jeito */ }
      location.replace("/");
    };
    el.append(nome);
    if (acessoDeFora.pessoa.papel === "titular") {
      const conta = document.createElement("button");
      conta.type = "button";
      conta.textContent = "Minha conta";
      conta.addEventListener("click", minhaContaDeFora);
      el.append(conta);
    }
    el.append(sair);
    barra.appendChild(el);
  }

  /* O titular de fora troca a propria senha e derruba as sessoes - e as duas
     coisas pedem o codigo do autenticador de novo, mesmo com a sessao valida:
     sessao roubada nao faz nenhuma delas. */
  async function minhaContaDeFora() {
    const escolha = await dialogo({
      titulo: "Minha conta", contexto: acessoDeFora.pessoa.nome + " · " + acessoDeFora.pessoa.email,
      texto: "As duas ações pedem o código do autenticador de novo. Contas da equipe só se mexem no computador do escritório.",
      confirmar: "Trocar minha senha", segundo: { rotulo: "Encerrar todas as sessões", perigo: true }, cancelar: "Fechar",
    });
    if (!escolha || !escolha.ok) return;
    const codigo = { chave: "codigo", rotulo: "Código do autenticador", placeholder: "000000", max: 8, obrigatorio: true };
    let url, corpo;
    if (escolha.segundo) {
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
  });
})();
