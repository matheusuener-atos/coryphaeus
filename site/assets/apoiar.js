/* PAULUS - Apoiar: formulario -> Pix ou cartao (Mercado Pago) -> Obrigado.
   Pix: o QR aparece aqui e a pagina espera a confirmacao. Cartao, uma vez
   ou todo mes: a pagina segura do Mercado Pago, que volta para ca. O cartao
   nunca passa por este site. A assinatura feita aqui guarda a chave dela
   neste navegador, para poder ser interrompida daqui. */
(function () {
  var MIN = 5, MAX = 50000;
  var RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var GUARDA = 'pv-assinatura';
  var cartao = document.getElementById('aj-cartao');
  var s = { tipo: 'unica', valor: 25, outro: '', forma: 'pix', email: '', mural: false, nome: '', etapa: 'form', erro: '', ocupado: false, pix: null, aviso: '' };
  var espera = null;

  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function brl(v) { return (Number(v) || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: v % 1 ? 2 : 0 }); }
  function valor() { return s.valor === 'outro' ? (parseFloat(String(s.outro).replace(/\./g, '').replace(',', '.')) || 0) : s.valor; }
  function forma() { return s.tipo === 'mensal' ? 'cartao' : s.forma; }
  function lerGuarda() { try { return JSON.parse(localStorage.getItem(GUARDA) || 'null'); } catch (e) { return null; } }
  function gravarGuarda(v) { try { v ? localStorage.setItem(GUARDA, JSON.stringify(v)) : localStorage.removeItem(GUARDA); } catch (e) {} }

  async function pedir(caminho, corpo) {
    var r = await fetch(caminho, corpo ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) } : {});
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error(d.erro || 'o site respondeu ' + r.status);
    return d;
  }

  function formulario() {
    var v = valor();
    var tipos = [['unica', 'Única'], ['mensal', 'Mensal']].map(function (t) {
      return '<button type="button" data-tipo="' + t[0] + '" aria-pressed="' + (s.tipo === t[0]) + '">' + t[1] + '</button>';
    }).join('');
    var valores = [10, 25, 50, 100].map(function (x) {
      return '<button type="button" data-valor="' + x + '" aria-pressed="' + (s.valor === x) + '">R$ ' + x + '</button>';
    }).join('');
    var formas = [
      { id: 'pix', nome: 'Pix', desc: 'Confirmação em segundos pelo app do banco' },
      { id: 'cartao', nome: 'Cartão de crédito', desc: 'Pelo checkout seguro do Mercado Pago' }
    ].map(function (f) {
      var bloq = s.tipo === 'mensal' && f.id === 'pix';
      return '<button type="button" class="aj-forma" data-forma="' + f.id + '" aria-pressed="' + (forma() === f.id) + '"' + (bloq ? ' disabled' : '') + '>' +
        '<span class="radio"></span><span class="txt"><b>' + f.nome + '</b><small>' + (bloq ? 'Disponível só para contribuição única' : f.desc) + '</small></span></button>';
    }).join('');
    return (s.erro ? '<p class="aj-erro" role="alert">' + esc(s.erro) + '</p>' : '') +
      (s.aviso ? '<p class="pg-texto">' + esc(s.aviso) + '</p>' : '') +
      '<div class="aj-bloco"><span class="titulo">Tipo de apoio</span><div class="aj-segmento">' + tipos + '</div>' +
      '<span class="aj-nota">' + (s.tipo === 'mensal' ? 'Cobrado todo mês no cartão. Cancele quando quiser.' : 'Uma contribuição, sem cobrança futura.') + '</span></div>' +
      '<div class="aj-bloco"><span class="titulo">Valor</span><div class="aj-valores">' + valores +
      '<label class="aj-outro' + (s.valor === 'outro' ? ' ativo' : '') + '"><span>R$</span><input id="aj-outro" inputmode="decimal" placeholder="Outro" aria-label="Outro valor" value="' + esc(s.outro) + '"></label></div>' +
      '<span class="aj-nota">De R$ ' + MIN + ' a R$ ' + MAX.toLocaleString('pt-BR') + '.</span></div>' +
      '<div class="aj-bloco"><span class="titulo">Forma de pagamento</span><div class="aj-formas">' + formas + '</div></div>' +
      '<label class="aj-campo" for="aj-email">E-mail para o comprovante<input id="aj-email" type="email" autocomplete="email" placeholder="voce@exemplo.com.br" value="' + esc(s.email) + '">' +
      '<small>Usado só para enviar o comprovante. Nunca é publicado.</small></label>' +
      '<div class="aj-mural"><button type="button" class="aj-chave" id="aj-chave" role="switch" aria-checked="' + s.mural + '">' +
      '<span class="txt"><b>Aparecer na página de apoiadores</b><small>Opcional. Só o nome que você escolher é publicado.</small></span><span class="trilho"><i></i></span></button>' +
      (s.mural ? '<label class="aj-campo" for="aj-nome" style="font-weight:400"><input id="aj-nome" maxlength="60" placeholder="Nome como deve aparecer (pessoa ou escritório)" value="' + esc(s.nome) + '"></label>' : '') +
      '</div>' +
      '<button type="button" class="aj-principal" id="aj-contribuir"' + (s.ocupado ? ' disabled' : '') + '>' +
      (s.ocupado ? 'Abrindo o Mercado Pago…' : v > 0 ? 'Contribuir com ' + brl(v) + (s.tipo === 'mensal' ? ' por mês' : '') : 'Escolha um valor') + '</button>' +
      '<span class="aj-rodape-cartao">Pagamento processado pelo Mercado Pago. O PAVLVS não recebe os dados do seu cartão.</span>';
  }

  function telaPix() {
    var p = s.pix || {};
    var img = /^[A-Za-z0-9+/=]+$/.test(p.qr_code_base64 || '') ? '<div class="aj-qr"><img alt="QR Code do Pix" src="data:image/png;base64,' + p.qr_code_base64 + '"></div>' : '';
    return '<div class="aj-etapa"><span class="pg-rotulo">Pix · ' + esc(brl(p.valor)) + '</span>' +
      '<h2>Pague com o app do seu banco.</h2>' + img +
      '<div class="aj-copia"><code id="aj-codigo">' + esc(p.qr_code) + '</code><button type="button" id="aj-copiar">Copiar</button></div>' +
      '<span class="aj-esperando"><i></i>' + (s.aviso ? esc(s.aviso) : 'Aguardando a confirmação do pagamento… O código vale 30 minutos.') + '</span>' +
      '<button type="button" class="aj-voltar" data-voltar>← Voltar</button></div>';
  }

  function telaFim() {
    if (s.etapa === 'indo') {
      return '<div class="aj-etapa"><span class="pg-rotulo">Cartão · ' + esc(brl(valor())) + (s.tipo === 'mensal' ? ' / mês' : '') + '</span>' +
        '<h2>Continuando no Mercado Pago…</h2><p>Você será levado à página segura do Mercado Pago para concluir. Depois, volta automaticamente para cá.</p></div>';
    }
    if (s.etapa === 'pendente') {
      return '<div class="aj-etapa"><span class="pg-rotulo">Pagamento em análise</span><h2>O Mercado Pago está conferindo o pagamento.</h2>' +
        '<p>Quando ele confirmar, o comprovante chega no e-mail informado. Nada mais precisa ser feito aqui.</p>' +
        '<button type="button" class="aj-voltar" data-voltar>← Voltar ao formulário</button></div>';
    }
    return '<div class="aj-etapa"><span class="pg-rotulo">Contribuição confirmada</span>' +
      '<h2 class="maior">Obrigado por apoiar o PAVLVS.</h2>' +
      '<p>O comprovante do Mercado Pago chega no e-mail informado. Quem usa o PAULUS emite o extrato das contribuições no próprio programa, em Apoiar o projeto.</p>' +
      '<div class="pg-fecho links" style="border:0;padding:6px 0 0"><a class="pg-seta" href="../desenvolvimento/">Acompanhe o desenvolvimento →</a>' +
      '<button type="button" class="aj-voltar" data-voltar>Fazer outra contribuição</button></div></div>';
  }

  function desenhar() {
    cartao.innerHTML = s.etapa === 'form' ? formulario() : s.etapa === 'pix' ? telaPix() : telaFim();
    ligar();
  }

  function ligar() {
    cartao.querySelectorAll('[data-tipo]').forEach(function (b) { b.onclick = function () { s.tipo = b.dataset.tipo; s.erro = ''; desenhar(); }; });
    cartao.querySelectorAll('[data-valor]').forEach(function (b) { b.onclick = function () { s.valor = Number(b.dataset.valor); desenhar(); }; });
    cartao.querySelectorAll('[data-forma]').forEach(function (b) { b.onclick = function () { s.forma = b.dataset.forma; desenhar(); }; });
    cartao.querySelectorAll('[data-voltar]').forEach(function (b) { b.onclick = function () { parar(); s.etapa = 'form'; s.aviso = ''; s.erro = ''; desenhar(); }; });
    var outro = document.getElementById('aj-outro');
    if (outro) {
      outro.onfocus = function () { if (s.valor !== 'outro') { s.valor = 'outro'; outro.parentNode.classList.add('ativo'); atualizarBotao(); } };
      outro.oninput = function () { s.outro = outro.value; s.valor = 'outro'; atualizarBotao(); };
    }
    var email = document.getElementById('aj-email');
    if (email) email.oninput = function () { s.email = email.value; };
    var nome = document.getElementById('aj-nome');
    if (nome) nome.oninput = function () { s.nome = nome.value; };
    var chave = document.getElementById('aj-chave');
    if (chave) chave.onclick = function () { s.mural = !s.mural; desenhar(); if (s.mural) { var n = document.getElementById('aj-nome'); if (n) n.focus(); } };
    var ir = document.getElementById('aj-contribuir');
    if (ir) ir.onclick = contribuir;
    var copiar = document.getElementById('aj-copiar');
    if (copiar) copiar.onclick = function () {
      var codigo = (s.pix || {}).qr_code || '';
      (navigator.clipboard ? navigator.clipboard.writeText(codigo) : Promise.reject()).then(function () { copiar.textContent = 'Copiado'; }, function () {
        var sel = window.getSelection(), r = document.createRange();
        r.selectNodeContents(document.getElementById('aj-codigo')); sel.removeAllRanges(); sel.addRange(r);
      });
    };
  }

  function atualizarBotao() {
    var b = document.getElementById('aj-contribuir'), v = valor();
    if (b) b.textContent = v > 0 ? 'Contribuir com ' + brl(v) + (s.tipo === 'mensal' ? ' por mês' : '') : 'Escolha um valor';
    cartao.querySelectorAll('[data-valor]').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
  }

  async function contribuir() {
    var v = valor();
    s.email = (document.getElementById('aj-email') || {}).value || s.email;
    s.email = s.email.trim();
    s.nome = ((document.getElementById('aj-nome') || {}).value || s.nome).trim();
    if (!(v >= MIN && v <= MAX)) { s.erro = 'O valor precisa estar entre R$ ' + MIN + ' e R$ ' + MAX.toLocaleString('pt-BR') + '.'; return desenhar(); }
    if (!RE_EMAIL.test(s.email)) { s.erro = 'Informe um e-mail válido para o comprovante.'; return desenhar(); }
    if (s.mural && !s.nome) { s.erro = 'Diga o nome que deve aparecer, ou desligue “Aparecer na página de apoiadores”.'; return desenhar(); }
    s.erro = '';
    s.ocupado = true;
    desenhar();
    var corpo = { valor: v, email: s.email, mural: s.mural ? s.nome : '' };
    try {
      if (s.tipo === 'mensal') {
        var a = await pedir('/api/mp/assinatura', Object.assign({ origem: 'site' }, corpo));
        gravarGuarda({ id: a.id, chave: a.chave, valor: v, desde: new Date().toISOString().slice(0, 10) });
        s.etapa = 'indo'; s.ocupado = false; desenhar();
        location.href = a.link;
      } else if (forma() === 'cartao') {
        var c = await pedir('/api/mp/cartao', corpo);
        s.etapa = 'indo'; s.ocupado = false; desenhar();
        location.href = c.link;
      } else {
        s.pix = await pedir('/api/mp/pix', corpo);
        s.pix.valor = v;
        s.etapa = 'pix'; s.ocupado = false; s.aviso = '';
        desenhar();
        esperarPix(s.pix.id);
      }
    } catch (e) {
      s.ocupado = false;
      s.erro = 'Não deu para abrir o pagamento: ' + e.message + '.';
      desenhar();
    }
  }

  function parar() { if (espera) { clearInterval(espera); espera = null; } }

  function esperarPix(id) {
    parar();
    var inicio = Date.now();
    espera = setInterval(async function () {
      if (Date.now() - inicio > 31 * 60 * 1000) {
        parar();
        s.aviso = 'O código venceu sem o pagamento chegar. Volte e gere outro, se quiser.';
        return desenhar();
      }
      try {
        var d = await pedir('/api/mp/pix/' + encodeURIComponent(id));
        if (d.pago) { parar(); s.etapa = 'obrigado'; desenhar(); }
      } catch (e) { /* tenta de novo na proxima volta */ }
    }, 5000);
  }

  /* O apoio mensal assinado neste navegador: a situacao e o Interromper. */
  async function gerir() {
    var g = lerGuarda(), caixa = document.getElementById('aj-recorrente');
    if (!g || !g.id || !caixa) return;
    var d;
    try { d = await pedir('/api/mp/assinatura/' + encodeURIComponent(g.id)); } catch (e) { return; }
    if (d.situacao === 'cancelled') { gravarGuarda(null); return; }
    var painel = document.createElement('div');
    painel.className = 'aj-gerir';
    function mostrar(html) { painel.innerHTML = html; }
    function inicial() {
      mostrar('<span>Seu apoio mensal de <b>' + esc(brl(g.valor)) + '</b> · ' + (d.ativa ? 'ativo' : 'esperando o cartão no Mercado Pago') + '</span>' +
        '<div class="linha"><button type="button" class="aj-secundario" data-gerir="perguntar">Interromper</button></div>');
      painel.querySelector('[data-gerir]').onclick = perguntar;
    }
    function perguntar() {
      mostrar('<span>Interromper o apoio mensal? Nada mais será cobrado depois disso.</span>' +
        '<div class="linha"><button type="button" class="aj-secundario" data-gerir="sim">Sim, interromper</button><button type="button" class="aj-voltar" data-gerir="nao">Manter</button></div>');
      painel.querySelector('[data-gerir="nao"]').onclick = inicial;
      painel.querySelector('[data-gerir="sim"]').onclick = async function () {
        try {
          await pedir('/api/mp/assinatura/' + encodeURIComponent(g.id) + '/interromper', { chave: g.chave });
          gravarGuarda(null);
          mostrar('<span>Apoio mensal interrompido. Nada mais será cobrado. Obrigado pelo tempo em que apoiou.</span>');
        } catch (e) {
          mostrar('<span>Não deu para interromper agora: ' + esc(e.message) + '. Tente de novo em instantes.</span>');
        }
      };
    }
    inicial();
    caixa.appendChild(painel);
  }

  /* A volta do Mercado Pago. */
  async function retorno() {
    var q = new URLSearchParams(location.search);
    var cartaoQ = q.get('cartao'), ass = q.get('assinatura');
    if (!cartaoQ && !ass) return;
    history.replaceState(null, '', location.pathname);
    if (cartaoQ === 'aprovado') s.etapa = 'obrigado';
    else if (cartaoQ === 'pendente') s.etapa = 'pendente';
    else if (cartaoQ === 'recusado') s.erro = 'O Mercado Pago não aprovou o pagamento, e nada foi cobrado. Tente outro cartão ou o Pix.';
    if (ass) {
      var g = lerGuarda(), id = q.get('preapproval_id') || (g && g.id);
      s.tipo = 'mensal';
      try {
        var d = id ? await pedir('/api/mp/assinatura/' + encodeURIComponent(id)) : {};
        if (d.ativa) s.etapa = 'obrigado';
        else s.aviso = 'A assinatura ainda não aparece como ativa. Se você concluiu no Mercado Pago, a confirmação chega em alguns minutos e o comprovante vai para o seu e-mail.';
      } catch (e) {
        s.aviso = 'Não consegui conferir a assinatura agora. Se você concluiu no Mercado Pago, o comprovante chega no seu e-mail.';
      }
    }
  }

  retorno().then(desenhar, desenhar);
  gerir();
})();
