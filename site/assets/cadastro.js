/* A pagina de cadastro (paulus.ia.br/cadastro): entrar com o Google e os dados
   do escritorio, com o plano escolhido em /assinatura (?plano=&periodo=), pelo Worker (worker/ia.js, /api/ia/planos e
   /api/ia/site/*). O pagamento e a pagina seguinte, /cadastro/pagamento
   (assets/pagamento.js), com o cartao nos campos seguros do Mercado Pago. O id_token do
   Google vale uma hora e fica so nesta aba (sessionStorage): e com ele que a
   pagina de pagamento sabe de quem e a assinatura. */
(function () {
  "use strict";

  // O cliente OAuth web do PAULUS (o mesmo da equipe). Identificador de
  // cliente nao e segredo; https://paulus.ia.br precisa estar entre as
  // origens JavaScript autorizadas dele no Google Cloud.
  var CLIENTE_GOOGLE = "834374999044-278vmq8hd7th777q084u0rthand7e1jn.apps.googleusercontent.com";
  var CHAVE = "pv-cadastro-token";
  var $ = function (id) { return document.getElementById(id); };
  var estado = { planos: [], escolhido: "escritorio", periodo: "mensal", pedido: false, token: "", conta: null };

  function brl(v) { return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }); }
  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function mostrarErro(id, texto) {
    var el = $(id);
    el.textContent = texto || "";
    el.hidden = !texto;
  }

  async function pedir(caminho, corpo) {
    var r = await fetch(caminho, corpo ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) } : {});
    var dados = {};
    try { dados = await r.json(); } catch (e) { dados = {}; }
    if (!r.ok) {
      var erro = new Error(dados.erro || "o site não respondeu (" + r.status + ")");
      erro.status = r.status;
      throw erro;
    }
    return dados;
  }

  /* ------------------------------------------------------------ planos */

  function plano() { return estado.planos.filter(function (x) { return x.id === estado.escolhido; })[0]; }
  function valorDe(p) { return estado.periodo === "anual" ? p.valor_anual : p.valor; }
  function sufixo() { return estado.periodo === "anual" ? "/ano" : "/mês"; }

  /* O plano escolhido em /assinatura, no alto, com o link para trocar (que
     volta para os cards com o mesmo plano e periodo marcados). */
  function desenharResumo() {
    var p = plano();
    var volta = "../assinatura/?plano=" + encodeURIComponent(estado.escolhido) + "&periodo=" + estado.periodo;
    $("cd-resumo-trocar").href = volta;
    if (!p) { $("cd-resumo-plano").textContent = "Escolha um plano"; $("cd-resumo-preco").textContent = ""; $("cd-resumo-trocar").textContent = "Ver os planos"; return; }
    $("cd-resumo-plano").textContent = p.nome + (estado.periodo === "anual" ? " · anual" : " · mensal");
    $("cd-resumo-preco").textContent = brl(valorDe(p)) + (estado.periodo === "anual" ? " por ano, à vista no Pix ou em até 12× no cartão" : " por mês, no Pix ou no cartão");
    $("cd-resumo-trocar").textContent = "Trocar";
  }

  function desenharPeriodo() {
    $("cd-selo-periodo").textContent = estado.periodo === "anual" ? "Pix ou até 12×" : "Pix ou cartão";
    $("cd-pagar-nota").textContent = estado.periodo === "anual"
      ? "O ano é pago de uma vez, na próxima página: à vista no Pix ou em até 12 vezes no cartão (os juros do parcelamento são de quem parcela). A cota de IA continua mensal. O anual não renova sozinho."
      : "Na próxima página, escolha: Pix, que paga um mês e não renova, ou cartão, que renova todo mês e se cancela no PAVLVS, em Configurações › Modelos. O número do cartão é digitado nos campos seguros do Mercado Pago e não passa pelo PAVLVS.";
  }

  /* A troca de plano, com a assinatura paga ativa: o plano escolhido em
     /assinatura que nao e o de agora (nem o ja marcado) vira o botao. */
  function desenharTroca() {
    var c = estado.conta || {};
    var paga = c.plano_vigente && !c.cortesia && c.assinatura && c.assinatura.situacao === "authorized";
    $("cd-troca").hidden = !paga;
    if (!paga) return;
    var fim = c.ciclo && c.ciclo.fim ? new Date(c.ciclo.fim).toLocaleDateString("pt-BR") : "a próxima renovação";
    var alvo = plano();
    var proximo = c.plano_proximo;
    $("cd-troca-texto").textContent = proximo
      ? "Troca marcada: a partir de " + fim + ", o plano " + proximo.nome + " (" + brl(proximo.valor) + "/mês)."
      : "Para trocar de plano, escolha outro em Trocar, no alto.";
    var mesmo = !alvo || alvo.id === (proximo || c.plano || {}).id;
    $("cd-trocar-plano").hidden = mesmo;
    if (!mesmo) {
      var volta = proximo && alvo.id === (c.plano || {}).id;
      $("cd-trocar-plano").textContent = volta ? "Ficar no " + alvo.nome + " (desfazer a troca)" : "Trocar para o " + alvo.nome + " · " + brl(alvo.valor) + "/mês";
    }
  }

  async function trocarPlano() {
    mostrarErro("cd-troca-erro", "");
    if (!estado.token) { mostrarErro("cd-troca-erro", "Entre com o Google de novo para trocar."); return; }
    var botao = $("cd-trocar-plano");
    botao.disabled = true;
    try {
      var conta = await pedir("/api/ia/site/plano", { id_token: estado.token, plano: estado.escolhido });
      mostrarConta(conta);
    } catch (e) {
      if (e.status === 401) { sair(); mostrarErro("cd-conta-erro", "A confirmação do Google venceu. Entre de novo para trocar."); return; }
      mostrarErro("cd-troca-erro", e.message.charAt(0).toUpperCase() + e.message.slice(1) + ".");
    } finally {
      botao.disabled = false;
    }
  }

  function atualizarBotao() {
    var p = plano();
    $("cd-pagar-texto").textContent = p ? (estado.periodo === "anual" ? "Pagar o ano do " : "Assinar o ") + p.nome + " · " + brl(valorDe(p)) + sufixo() : "Ir para o pagamento";
  }

  async function carregarPlanos() {
    try {
      var d = await pedir("/api/ia/planos");
      estado.planos = d.planos || [];
      if (d.recarga) {
        $("cd-recarga").textContent = "A cota é do mês, liberada por semana; uma vez por mês dá para adiantar a semana seguinte. " +
          "Se acabar, a recarga é no Pix, no preço do plano, e não vence na renovação.";
      }
      // Plano que o Worker nao tem (endereco velho): o recomendado.
      if (!plano() && !estado.conta) estado.escolhido = "escritorio";
      $("cd-recarga").hidden = !d.recarga;
      desenharResumo();
      atualizarBotao();
      desenharTroca();
    } catch (e) {
      $("cd-resumo-plano").textContent = "Não consegui ler os planos agora";
      $("cd-resumo-preco").textContent = e.message + ". Tente de novo em instantes.";
    }
  }

  /* ------------------------------------------------------------- conta */

  function mostrarConta(conta) {
    estado.conta = conta;
    $("cd-conta-texto").innerHTML = "Entrou como <b>" + esc(conta.email) + "</b>. " +
      '<button type="button" class="trocar" id="cd-trocar">Usar outra conta</button>';
    $("cd-trocar").onclick = sair;
    $("cd-google").hidden = true;
    var c = conta.cadastro || {};
    if (c.nome_escritorio && !$("cd-nome").value) $("cd-nome").value = c.nome_escritorio;
    if (c.documento && !$("cd-documento").value) $("cd-documento").value = mascararDocumento(c.documento);
    if (c.telefone && !$("cd-telefone").value) $("cd-telefone").value = mascararTelefone(c.telefone);
    if (c.oab && !$("cd-oab").value) $("cd-oab").value = c.oab;
    var e = c.endereco || {};
    if (e.cep && !$("cd-cep").value) {
      $("cd-cep").value = mascararCep(e.cep);
      cepLido = digitos(e.cep);
      [["logradouro", "cd-logradouro"], ["numero", "cd-numero"], ["complemento", "cd-complemento"], ["bairro", "cd-bairro"], ["cidade", "cd-cidade"], ["uf", "cd-uf"], ["cmun", "cd-cmun"]].forEach(function (x) {
        if (e[x[0]]) $(x[1]).value = e[x[0]];
      });
    }
    if (!estado.pedido) {
      if (conta.plano_proximo) estado.escolhido = conta.plano_proximo.id;
      else if (conta.plano && conta.plano.id) estado.escolhido = conta.plano.id;
      if (conta.periodo === "anual" || conta.periodo === "mensal") estado.periodo = conta.periodo;
      desenharPeriodo();
    }
    var ativa = conta.plano_vigente;
    $("cd-form").hidden = Boolean(ativa);
    $("cd-pronto").hidden = !ativa;
    if (ativa) {
      mostrarErro("cd-conta-erro", "");
      var fim = conta.ciclo && conta.ciclo.fim ? new Date(conta.ciclo.fim).toLocaleDateString("pt-BR") : "";
      $("cd-pronto-titulo").textContent = conta.cortesia ? "Plano de cortesia ativo" : "Assinatura ativa";
      var ano = conta.periodo === "anual" && conta.pago_ate ? new Date(conta.pago_ate).toLocaleDateString("pt-BR") : "";
      $("cd-pronto-texto").textContent = "Plano " + (conta.plano || {}).nome + (ano ? " anual, pago até " + ano : fim ? ", ciclo até " + fim : "") + ". " +
        "Agora é só baixar o PAVLVS e entrar com " + conta.email + ".";
    }
    desenharResumo();
    atualizarBotao();
    desenharTroca();
    desenharDesistencia();
  }

  /* Os 7 dias de arrependimento: o que volta e ate quando. */
  var confirmandoDesistencia = false;
  function desenharDesistencia() {
    var d = (estado.conta || {}).desistencia || {};
    var pode = Boolean(estado.conta && estado.conta.plano_vigente && d.pode);
    $("cd-desistir").hidden = !pode;
    if (!pode) return;
    confirmandoDesistencia = false;
    $("cd-desistir-texto").textContent = "Nos 7 primeiros dias, até " + new Date(d.ate).toLocaleDateString("pt-BR") + ", dá para desistir e receber " +
      brl(d.valor) + " de volta, no cartão ou no Pix em que você pagou. O plano acaba na hora.";
    $("cd-desistir-botao").textContent = "Desistir e receber de volta";
  }

  async function desistir() {
    mostrarErro("cd-desistir-erro", "");
    if (!estado.token) { mostrarErro("cd-desistir-erro", "Entre com o Google de novo para desistir."); return; }
    var botao = $("cd-desistir-botao");
    // Duas vezes: a primeira pede a confirmacao.
    if (!confirmandoDesistencia) {
      confirmandoDesistencia = true;
      botao.textContent = "Confirmar: desistir e receber " + brl(((estado.conta || {}).desistencia || {}).valor || 0) + " de volta";
      return;
    }
    botao.disabled = true;
    try {
      var r = await pedir("/api/ia/site/desistir", { id_token: estado.token });
      var conta = await pedir("/api/ia/site/situacao", { id_token: estado.token });
      mostrarConta(conta);
      $("cd-pronto").hidden = false;
      $("cd-form").hidden = true;
      $("cd-pronto-titulo").textContent = "Desistência feita";
      $("cd-pronto-texto").textContent = brl(r.valor) + " a caminho de volta, no cartão ou no Pix em que você pagou (o banco leva alguns dias para mostrar). O plano acabou." +
        ((r.avisos || []).length ? " " + r.avisos[0].charAt(0).toUpperCase() + r.avisos[0].slice(1) + "." : "");
    } catch (e) {
      if (e.status === 401) { sair(); mostrarErro("cd-conta-erro", "A confirmação do Google venceu. Entre de novo para desistir."); return; }
      mostrarErro("cd-desistir-erro", e.message.charAt(0).toUpperCase() + e.message.slice(1) + ".");
    } finally {
      botao.disabled = false;
    }
  }

  /* A volta do plano B (a pagina do Mercado Pago): o aviso pode chegar uns
     segundos depois, entao a situacao e conferida algumas vezes. */
  async function conferirVolta(token) {
    for (var i = 0; i < 6; i++) {
      var conta;
      try { conta = await pedir("/api/ia/site/situacao", { id_token: token }); } catch (e) { return entrar(token); }
      estado.token = token;
      mostrarConta(conta);
      if (conta.plano_vigente) return conta;
      mostrarErro("cd-conta-erro", "Conferindo o pagamento no Mercado Pago…");
      await new Promise(function (ok) { setTimeout(ok, 5000); });
    }
    mostrarErro("cd-conta-erro", "O Mercado Pago ainda não confirmou o pagamento. Se você concluiu, recarregue esta página em alguns minutos.");
    return null;
  }

  async function entrar(token) {
    mostrarErro("cd-conta-erro", "");
    try {
      var conta = await pedir("/api/ia/site/entrar", { id_token: token });
      estado.token = token;
      try { sessionStorage.setItem(CHAVE, token); } catch (e) { /* sem a aba guardar, entra de novo na volta */ }
      mostrarConta(conta);
      return conta;
    } catch (e) {
      if (e.status === 401) {
        try { sessionStorage.removeItem(CHAVE); } catch (x) { /* nada guardado */ }
        estado.token = "";
      }
      mostrarErro("cd-conta-erro", e.status === 401 ? "A confirmação do Google venceu. Entre de novo." : "Não consegui entrar: " + e.message);
      return null;
    }
  }

  function sair() {
    try { sessionStorage.removeItem(CHAVE); } catch (e) { /* nada guardado */ }
    estado.token = "";
    estado.conta = null;
    $("cd-form").hidden = true;
    $("cd-pronto").hidden = true;
    $("cd-troca").hidden = true;
    $("cd-google").hidden = false;
    $("cd-conta-texto").textContent = "A conta do PAVLVS é a sua conta Google: é com ela que você entra no programa depois. Nenhuma senha a mais.";
    if (window.google && google.accounts && google.accounts.id) google.accounts.id.disableAutoSelect();
  }

  function iniciarGoogle() {
    if (!(window.google && google.accounts && google.accounts.id)) { setTimeout(iniciarGoogle, 300); return; }
    google.accounts.id.initialize({
      client_id: CLIENTE_GOOGLE,
      callback: function (r) { if (r && r.credential) entrar(r.credential); },
      ux_mode: "popup",
      context: "signup",
    });
    // O botao e o do Google (so ele entrega a identidade), no tema escuro e na largura da coluna.
    var claro = document.documentElement.getAttribute("data-theme") === "light";
    google.accounts.id.renderButton($("cd-google"), { theme: claro ? "outline" : "filled_black", size: "large", text: "continue_with", shape: "rectangular", width: Math.min(360, $("cd-google").clientWidth || 360), locale: "pt-BR" });
  }

  /* ------------------------------------------------------- o formulario */

  function digitos(t) { return String(t || "").replace(/\D/g, ""); }
  function mascararDocumento(t) {
    var d = digitos(t).slice(0, 14);
    if (d.length <= 11) return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
    return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
  }
  function mascararTelefone(t) {
    var d = digitos(t).slice(0, 11);
    if (d.length < 3) return d;
    return "(" + d.slice(0, 2) + ") " + (d.length > 10 ? d.slice(2, 7) + "-" + d.slice(7) : d.slice(2, 6) + (d.length > 6 ? "-" + d.slice(6) : ""));
  }

  function mascararCep(t) {
    var d = digitos(t).slice(0, 8);
    return d.length > 5 ? d.slice(0, 5) + "-" + d.slice(5) : d;
  }

  /* O CEP com 8 digitos preenche rua, bairro, cidade e UF pela ViaCEP e guarda
     o codigo IBGE do municipio (vai na NFS-e). Se a ViaCEP falhar, a pessoa
     digita a mao e o codigo fica vazio (a casa completa na hora da nota). */
  var cepLido = "";
  async function buscarCep() {
    var cep = digitos($("cd-cep").value);
    var nota = $("cd-cep-nota");
    if (cep.length !== 8) { if (cep !== cepLido) $("cd-cmun").value = ""; nota.hidden = true; return; }
    if (cep === cepLido) return;
    cepLido = cep;
    $("cd-cmun").value = "";
    nota.textContent = "Procurando o CEP…";
    nota.hidden = false;
    try {
      var r = await fetch("https://viacep.com.br/ws/" + cep + "/json/");
      var d = await r.json();
      if (digitos($("cd-cep").value) !== cep) return;
      if (!r.ok || !d || d.erro) throw new Error("não achei");
      if (d.logradouro) $("cd-logradouro").value = d.logradouro;
      if (d.bairro) $("cd-bairro").value = d.bairro;
      if (d.localidade) $("cd-cidade").value = d.localidade;
      if (d.uf) $("cd-uf").value = d.uf;
      $("cd-cmun").value = /^\d{7}$/.test(String(d.ibge || "")) ? d.ibge : "";
      nota.hidden = true;
      (d.logradouro ? $("cd-numero") : $("cd-logradouro")).focus();
    } catch (e) {
      if (digitos($("cd-cep").value) !== cep) return;
      nota.textContent = "Não achei esse CEP agora. Confira o número ou preencha o endereço à mão.";
      nota.hidden = false;
    }
  }

  /* O CNPJ completo e certo preenche o nome, o telefone e o endereco com os
     dados da Receita, pela BrasilAPI (assets/cnpj.js). So entra no campo
     vazio ou no que a consulta anterior preencheu; o endereco vai inteiro
     (com o codigo IBGE) ou nao vai, para nao misturar dois enderecos. */
  var cnpjLido = "", peloCnpj = {};
  function livre(id) { var v = $(id).value.trim(); return !v || v === peloCnpj[id]; }
  function porPeloCnpj(id, v) { if (v && livre(id)) { $(id).value = v; peloCnpj[id] = v; return 1; } return 0; }
  async function buscarCnpj() {
    var nota = $("cd-cnpj-nota");
    var cnpj = window.PavlvsCnpj ? PavlvsCnpj.paraConsultar($("cd-documento").value) : "";
    if (cnpj === cnpjLido) return;
    cnpjLido = cnpj;
    if (!cnpj) { nota.hidden = true; return; }
    nota.textContent = "Consultando a Receita…";
    nota.hidden = false;
    try {
      var d = await PavlvsCnpj.consultar(cnpj);
      if (PavlvsCnpj.paraConsultar($("cd-documento").value) !== cnpj) return;
      var n = porPeloCnpj("cd-nome", d.razao_social) + porPeloCnpj("cd-telefone", mascararTelefone(d.telefone));
      var ends = ["cd-cep", "cd-logradouro", "cd-numero", "cd-complemento", "cd-bairro", "cd-cidade", "cd-uf"];
      if (d.cep && ends.every(livre)) {
        var vals = [mascararCep(d.cep), d.logradouro, d.numero, d.complemento, d.bairro, d.municipio, d.uf];
        ends.forEach(function (id, i) { $(id).value = vals[i]; peloCnpj[id] = vals[i]; });
        cepLido = d.cep;
        $("cd-cep-nota").hidden = true;
        $("cd-cmun").value = /^\d{7}$/.test(d.codigo_municipio_ibge) ? d.codigo_municipio_ibge : "";
        n += vals.filter(Boolean).length;
      }
      nota.textContent = PavlvsCnpj.frase(d).replace(" (Receita", (n ? " · " + n + (n === 1 ? " campo preenchido" : " campos preenchidos") : "") + " (Receita");
    } catch (e) {
      if (PavlvsCnpj.paraConsultar($("cd-documento").value) !== cnpj) return;
      nota.textContent = "Não preenchi pela Receita: " + e.message + ".";
    }
  }

  function endereco() {
    return {
      cep: $("cd-cep").value, logradouro: $("cd-logradouro").value, numero: $("cd-numero").value, complemento: $("cd-complemento").value,
      bairro: $("cd-bairro").value, cidade: $("cd-cidade").value, uf: $("cd-uf").value.trim().toUpperCase(), cmun: $("cd-cmun").value,
    };
  }

  async function pagar(ev) {
    ev.preventDefault();
    mostrarErro("cd-form-erro", "");
    if (!estado.token) { mostrarErro("cd-form-erro", "Entre com o Google primeiro."); return; }
    if (!$("cd-aceite").checked) { mostrarErro("cd-form-erro", "Para assinar, aceite os Termos de uso e a Política de privacidade."); return; }
    var botao = $("cd-pagar");
    botao.disabled = true;
    try {
      var r = await pedir("/api/ia/site/cadastro", {
        id_token: estado.token, nome_escritorio: $("cd-nome").value, documento: $("cd-documento").value,
        telefone: $("cd-telefone").value, oab: $("cd-oab").value, endereco: endereco(), aceite: true, plano: estado.escolhido, periodo: estado.periodo,
      });
      if (!r.proximo) throw new Error("o site não devolveu a página de pagamento");
      // Mesma origem: so o caminho e a busca do endereco que o Worker devolveu.
      var ida = new URL(r.proximo, location.origin);
      window.location.assign(ida.pathname + ida.search);
    } catch (e) {
      botao.disabled = false;
      if (e.status === 401) { sair(); mostrarErro("cd-conta-erro", "A confirmação do Google venceu. Entre de novo e confira os dados."); return; }
      mostrarErro("cd-form-erro", e.message.charAt(0).toUpperCase() + e.message.slice(1) + ".");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarGoogle();
    $("cd-form").addEventListener("submit", pagar);
    $("cd-trocar-plano").addEventListener("click", trocarPlano);
    $("cd-desistir-botao").addEventListener("click", desistir);
    $("cd-documento").addEventListener("input", function () { this.value = mascararDocumento(this.value); buscarCnpj(); });
    $("cd-telefone").addEventListener("input", function () { this.value = mascararTelefone(this.value); });
    $("cd-cep").addEventListener("input", function () { this.value = mascararCep(this.value); buscarCep(); });
    // Cidade digitada a mao: o codigo IBGE da ViaCEP deixa de valer.
    $("cd-cidade").addEventListener("input", function () { $("cd-cmun").value = ""; });
    $("cd-uf").addEventListener("input", function () { this.value = this.value.replace(/[^A-Za-z]/g, "").toUpperCase(); $("cd-cmun").value = ""; });
    var guardado = "";
    try { guardado = sessionStorage.getItem(CHAVE) || ""; } catch (e) { guardado = ""; }
    // Vindo de /assinatura ou do PAULUS instalado (?plano=&periodo=): o plano
    // e o periodo ja escolhidos. Sem eles, vale o da conta (ou o recomendado).
    var pedido = new URLSearchParams(location.search);
    if (pedido.get("periodo") === "anual") estado.periodo = "anual";
    if (pedido.get("plano")) { estado.escolhido = pedido.get("plano"); estado.pedido = true; }
    desenharPeriodo();
    desenharResumo();
    carregarPlanos();
    if (guardado) {
      // Voltou da pagina do Mercado Pago (o plano B do pagamento): confere la.
      if (/[?&]voltou=1/.test(location.search)) conferirVolta(guardado); else entrar(guardado);
    }
  });
})();
