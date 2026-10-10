/* O CNPJ digitado, consultado na BrasilAPI (dados públicos da Receita).
   Usado pelo painel (assets/admin.js);
   o PAULUS instalado tem o mesmo resumo em paulus/legal/src/cnpj_receita.py.

   PavlvsCnpj.paraConsultar(texto) -> os 14 dígitos, se o CNPJ fecha; senão "".
   PavlvsCnpj.consultar(cnpj) -> Promise do resumo; rejeita com a frase do
   motivo ("a Receita não tem este CNPJ", "sem resposta…"). A resposta fica
   guardada enquanto a página está aberta. */
(function () {
  var guardado = {};
  var MINUSCULAS = { a: 1, as: 1, o: 1, os: 1, da: 1, das: 1, de: 1, "do": 1, dos: 1, e: 1, em: 1, na: 1, nas: 1, no: 1, nos: 1 };

  function digitos(t) { return String(t == null ? "" : t).replace(/\D/g, ""); }

  function valido(c) {
    if (!/^\d{14}$/.test(c) || /^(\d)\1{13}$/.test(c)) return false;
    for (var n = 12; n <= 13; n += 1) {
      var pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
      var soma = 0;
      for (var i = 0; i < n; i += 1) soma += Number(c[i]) * pesos[i];
      var resto = soma % 11;
      if ((resto < 2 ? 0 : 11 - resto) !== Number(c[n])) return false;
    }
    return true;
  }

  // Só o que tem letra conta: "12.ABC…" com letras não é consultado.
  function paraConsultar(texto) {
    var bruto = String(texto || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
    return /^\d{14}$/.test(bruto) && valido(bruto) ? bruto : "";
  }

  // "RUA DAS FLORES" -> "Rua das Flores"; romano, código com número e SN ficam.
  function titulo(t) {
    return String(t || "").trim().split(/\s+/).filter(Boolean).map(function (p, i) {
      var nucleo = p.replace(/[^\w]/g, "").toUpperCase();
      if (/^([IVXL]+|\w*\d\w*|SN)$/.test(nucleo || "-")) return p.toUpperCase();
      if (i && MINUSCULAS[p.toLowerCase()]) return p.toLowerCase();
      return p.charAt(0).toUpperCase() + p.slice(1).toLowerCase();
    }).join(" ");
  }

  function texto(x) { return x == null ? "" : String(x).trim(); }

  function resumir(b) {
    var tipo = texto(b.descricao_tipo_de_logradouro), rua = texto(b.logradouro);
    if (tipo && rua.toUpperCase().indexOf(tipo.toUpperCase()) !== 0) rua = tipo + " " + rua;
    var situacao = texto(b.descricao_situacao_cadastral).toUpperCase();
    return {
      cnpj: digitos(b.cnpj), razao_social: texto(b.razao_social), nome_fantasia: texto(b.nome_fantasia),
      situacao: situacao, ativa: situacao === "ATIVA",
      logradouro: titulo(rua), numero: texto(b.numero), complemento: titulo(b.complemento), bairro: titulo(b.bairro),
      municipio: titulo(b.municipio), uf: texto(b.uf).toUpperCase(), codigo_municipio_ibge: texto(b.codigo_municipio_ibge),
      cep: digitos(b.cep), telefone: digitos(b.ddd_telefone_1), email: texto(b.email).toLowerCase(),
    };
  }

  function consultar(cnpj) {
    if (guardado[cnpj]) return Promise.resolve(guardado[cnpj]);
    return fetch("https://brasilapi.com.br/api/cnpj/v1/" + cnpj, { headers: { Accept: "application/json" } }).then(function (r) {
      if (r.status === 404) throw new Error("a Receita não tem este CNPJ");
      if (!r.ok) throw new Error("a BrasilAPI não respondeu agora (" + r.status + ")");
      return r.json();
    }, function () {
      throw new Error("sem resposta da BrasilAPI: confira a internet ou preencha à mão");
    }).then(function (b) {
      if (!b || !b.razao_social) throw new Error("a BrasilAPI não devolveu os dados agora; tente de novo");
      guardado[cnpj] = resumir(b);
      return guardado[cnpj];
    });
  }

  // A frase abaixo do campo: quem é, e a situação quando não é ativa.
  function frase(d) {
    return (d.razao_social || "CNPJ encontrado") + (d.ativa ? "" : " · situação na Receita: " + (d.situacao || "desconhecida").toLowerCase()) +
      " (Receita, pela BrasilAPI)";
  }

  var api = { paraConsultar: paraConsultar, consultar: consultar, resumir: resumir, frase: frase, valido: valido };
  if (typeof window !== "undefined") window.PavlvsCnpj = api;
  if (typeof module !== "undefined") module.exports = api;
})();
