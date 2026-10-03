# Painel admin do PAVLVS - o contrato das rotas

O painel mora em `site/admin/` (estatico) e fala com `worker/admin.js` por
`/api/admin/*`. Desenho: handoff "Painel Admin" (03/10/2026). Este arquivo e o
contrato entre a pagina e o Worker; quem mudar um lado muda o outro e este texto.

## Portas

1. **Cloudflare Access** na frente de `paulus.ia.br/admin*` e `paulus.ia.br/api/admin*`
   (politica: e-mail @paulus.ia.br, codigo de uso unico). O Worker confere o JWT
   `Cf-Access-Jwt-Assertion` em toda rota `/api/admin/*` (as chaves de
   `https://<ACCESS_TEAM>/cdn-cgi/access/certs`, `aud` = `ACCESS_AUD`). Sem
   `ACCESS_TEAM`/`ACCESS_AUD` configurados, o painel fica fechado (503).
2. **GitHub** (OAuth App "PAVLVS Admin", `GITHUB_CLIENT_ID` em vars,
   `GITHUB_CLIENT_SECRET` segredo): permissao `push` em
   `matheusuener-atos/coryphaeus`. A sessao (cookie `pv_admin`, HttpOnly,
   Secure, SameSite=Lax, 24 h) fica no KV `APOIOS` em `admin:sessao:<id>`.
3. O papel (`dono` | `financeiro` | `suporte`) vem de `ADMIN_EQUIPE` (JSON
   `[{email, nome, papel}]`) ou, depois de publicado, de `admin:equipe` no KV.

Toda resposta e JSON com `cache-control: no-store`. Erro: `{erro: "frase"}`
com o status. Sem a sessao do GitHub: 401 `{erro, passo: "github"}`; sem o
Access: 401 `{erro, passo: "access"}`; papel sem permissao: 403
`{erro: "o papel X nao pode ..."}`.

## Sessao

- `GET /api/admin/sessao` - nunca 401: `{access: {ok, email}, github: {ok, login},
  papel, nome, worker: "0.x", pronto: bool, config: {access, github, email, nfse,
  tuneis, mercado_pago, nuvem}}` (cada `config.x` = `{ligado: bool, falta: "frase"}`).
- `GET /api/admin/github/entrar` - 302 para o GitHub (state no KV, 10 min).
- `GET /api/admin/github/retorno?code&state` - confere o push e grava a sessao;
  302 para `/admin/` (ou `/admin/?erro=frase`).
- `POST /api/admin/sair` - apaga a sessao; a pagina vai depois a
  `/cdn-cgi/access/logout`.

## Leitura

Datas em ISO 8601 (UTC); dinheiro em reais (numero); tokens em unidades.

- `GET /api/admin/visao` -> `{agora, kpi: {receita_mes, receita_assinaturas, receita_recargas,
  custo_usd_mes, cambio, entrada_mes, saida_mes, contas, contas_ativas, escritorios, tokens_hoje},
  dias: [{dia: "AAAA-MM-DD", turno: 0|1|2, total, saida}] (42, do mais antigo ao mais novo),
  pendencias: [{icone, titulo, sub, tela, filtro?}],
  avisos: [{quando, tipo, texto, valor, tom: "entrada"|"recusado"|"cancelado"|"neutro"}]}`
- `GET /api/admin/contas` -> `{contas: [Conta], escritorios: [{nome, slug, documento,
  contas: [id], tokens_mes, receita_mes}]}` onde
  `Conta = {id, nome, email, escritorio: {nome, slug, documento}, oab, plano: {id, nome, valor, tokens},
  situacao: "ativa"|"vencida"|"cortesia"|"pendente"|"cancelada", restantes, usados, extra,
  ultimo_uso, google: {escopos: [], conferido} | null}`
- `GET /api/admin/contas/:id` -> `Conta + {criada, ciclo: {inicio, fim, tokens, usados} | null,
  cadastro: {documento, telefone, oab, termos, quando} | null, consentimento: {versao, quem, quando} | null,
  assinatura: {id, situacao, valor, desde} | null, plano_proximo, instalacoes: [{instalacao, hash8, criado}],
  pagamentos: [{tipo: "assinatura"|"recarga", valor, quando, ref}], recargas, google_pendente | null}`
- `GET /api/admin/tuneis` -> `{tuneis: [{slug, nome, responsavel, estado: "healthy"|"degraded"|"inactive"|"down"|"desativado",
  ultima_conexao, criado_em, tunnel_id, porta, ativo, limpeza: {dias, motivo} | null,
  historico: [{quando, texto}]}], livres: [slug], cf: {ligado, falta}}`
- `GET /api/admin/tuneis/disponivel?nome=` -> `{ok, motivo}` (as regras de `escritorio/index.html`)
- `GET /api/admin/renovacoes` -> `{abertas: [Renovacao], tratadas: [Renovacao], config: {email, resumo, whats, tol}}`
  onde `Renovacao = {id (da conta), nome, email, plano: {nome, valor}, fim, dias_vencido, tolerancia_dias (o total: 5 com a assinatura autorizada, 0 sem), motivo, lembrete_em}`
- `GET /api/admin/campanhas` -> `{campanhas: [{id, nome, situacao: "enviada"|"agendada"|"na fila"|"enviando"|"rascunho",
  publico: {id, label}, enviados, abertos, cliques, devolvidos, quando}], publicos: [{id, label, n, gmail}],
  stats: {enviados, abertura, cliques, devolvidos}, envio: {ligado, falta, de: "contato@paulus.ia.br", ritmo: 50}}`
- `GET /api/admin/cupons` -> `{cupons: [{codigo, descricao, desconto, meses, brinde, limite, usos, validade, planos: [id], ativo}]}`
- `GET /api/admin/tokens?visao=geral|escritorio|conta&periodo=mes|30|ano` ->
  `{kpis: {entrada, saida, custo_usd, receita, contas}, linhas: [{nome, entrada, saida, custo_usd, receita}],
  precos: {entrada, saida, cambio}}` (custo em US$; a pagina converte pelo cambio)
- `GET /api/admin/planos` -> `{planos: [{id, nome, valor, tokens, assinantes}], padrao: "escritorio",
  recarga: {valor, tokens}, precos: {entrada, saida, cambio}, json: "..."}`
- `GET /api/admin/materiais` -> `{materiais: [{id, slug, tipo: "artigo"|"modelo"|"tabela", titulo, areas, licenca,
  autor, oab, enviado, situacao: "fila"|"ajustes"|"publicado"|"recusado", palavras, texto, resumo,
  varredura: {cpf, cnpj, processo, nomes}}]}`
- `GET /api/admin/nfse` -> `{config: {auto, email, mail}, emissor: {ligado, falta}, situacao: Situacao | null,
  notas: [Nota], pagamentos: [{id, conta, cliente, tipo: "mensalidade"|"recarga pix", valor, quando, nota, numero,
  motivo, erro}], cloudflare: Cloudflare, pode: {emitir: bool}, erro}`. `pagamentos` sao so os sem nota
  (nenhuma nota do emissor com aquele pagamento, fora as descartadas); `motivo` diz por que a emissao
  automatica nao saiu. `Situacao`, `Nota` e `Cloudflare` estao em "Notas fiscais", abaixo.
- `GET /api/admin/equipe` -> `{membros: [{email, nome, papel, ultimo}], matriz: [{acao, dono, financeiro, suporte}]}`
- `GET /api/admin/busca?q=` -> `{contas: [...], escritorios: [...], tuneis: [...], cupons: [...], planos: [...],
  materiais: [...]}` (ate 6 por grupo; cada item `{titulo, desc, tela, alvo}`)
- `GET /api/admin/alteracoes` -> `{pendentes: [Alteracao], publicacoes: [{quando, commit, resumo, n, por}]}`
  onde `Alteracao = {id, quando, tela, tipo, alvo, dados, texto}`

## Na hora (sem passar pela fila)

Comunicacao e marcacao, que nao mudam o que esta no ar:

- `POST /api/admin/tuneis/:slug/avisar` -> e-mail ao responsavel com o prazo da limpeza
- `POST /api/admin/renovacoes/:id/lembrete` -> e-mail "seu plano nao renovou"
- `POST /api/admin/renovacoes/:id/tratar` / `.../reabrir`
- `POST /api/admin/renovacoes/config` `{email, resumo, whats, tol}`
- `POST /api/admin/campanhas/teste` `{campanha}` -> um e-mail de teste para quem esta na sessao
- Sem o provedor de e-mail (`RESEND_API_KEY`), essas rotas respondem 503
  `{erro: "o envio de e-mail ainda nao esta ligado: falta RESEND_API_KEY"}`.

## A fila (Confirmar alteracoes)

Tudo o que muda o que esta no ar entra na fila da sessao e so acontece em "Commitar e pushar":

- `POST /api/admin/alteracoes` `{tela, tipo, alvo, dados, texto}` -> `{pendentes}`.
  `texto` e a frase no passado que a lista mostra ("Apaguei moura-associados").
- `DELETE /api/admin/alteracoes/:id` -> `{pendentes}`
- `POST /api/admin/publicar` `{confirmacao: "comitar e pushar"}` ->
  `{ok, resultados: [{id, ok, erro}], publicacao: {quando, commit, resumo, n, por}}`.
  Aplica em ordem; uma que falha nao desfaz as outras, e volta com o motivo.

Tipos (`tipo` -> `dados`), e o papel que pode:

| tipo | dados | papel |
| --- | --- | --- |
| `conta.creditar` | `{id, tokens}` | dono, financeiro |
| `conta.instalacao.apagar` | `{id, hash8}` | dono, suporte |
| `conta.cancelar` | `{id}` | dono, financeiro |
| `google.servicos` | `{id, ligados: [escopo]}` | dono, suporte |
| `google.desvincular` | `{id}` | dono, suporte |
| `tunel.apagar` | `{slug}` | dono, suporte |
| `tunel.endereco` | `{slug, novo}` | dono, suporte |
| `tunel.ativo` | `{slug, ativo}` | dono, suporte |
| `campanha.disparar` | `{nome, publico, assunto, pre, titulo, texto, botao, link, quando: "agora"|"amanha"|"segunda"}` | todos |
| `cupom.criar` | `{codigo, desconto, meses, brinde, limite, planos, validade}` | dono, financeiro |
| `cupom.ativo` | `{codigo, ativo}` | dono, financeiro |
| `plano.editar` | `{id, valor, tokens}` | dono, financeiro |
| `plano.criar` | `{id, nome, valor, tokens}` | dono, financeiro |
| `material.situacao` | `{id, situacao: "publicado"|"ajustes"|"recusado", recado}` | todos |
| `nfse.config` | `{auto, email, mail}` | dono, financeiro |
| `equipe.papel` | `{email, papel}` | dono |

Ver contas, tokens e receita, mandar e-mails e lembretes: todos os papeis.

## Notas fiscais (emissor da nuvem)

As NFS-e que o PAVLVS emite para quem assina sao emitidas pelo painel: aba Notas fiscais,
rotas `/api/admin/nfse/emissor/*` (`worker/nfse/api.js`, `atenderEmissor`) ate o Durable Object
`EmissorNFSe` (`worker/nfse/emissor.js`). Testes: `worker/teste-nfse-admin.mjs` (painel + emissor),
`worker/teste-nfse-emissor.mjs` (o emissor) e `worker/tela-nfse/teste_tela.py` (a tela, Playwright).

- **Mesmas portas do painel** (Access + sessao do GitHub). `GET` para todos os papeis; o resto
  (emitir, cancelar, substituir, enviar, certificado, parametros, token, testar, producao) so
  `dono` e `financeiro`: suporte recebe 403 `{erro: "o papel suporte só vê as notas fiscais: ..."}`.
- **Na hora**: nada disso passa pela fila de alteracoes. So os tres interruptores (`nfse.config`)
  continuam na fila.
- Sem o emissor (`EMISSOR_NFSE`, `NFSE_CHAVE_MESTRA` ou `APOIOS`): 503 `{erro: "o emissor de NFS-e ainda nao esta ligado: falta ..."}`.
  `GET /api/admin/sessao` diz o mesmo em `config.nfse`.
- O `quem` de cada passo da nota e o e-mail do Access de quem pediu.
- A ponte antiga com o PAULUS da casa (`/api/nfse-casa/*`) **saiu** em 03/10/2026 (responde 404).

Os interruptores (`admin:nfse:config`):

- `auto` - emitir ao confirmar o pagamento: o aviso do Mercado Pago (`worker/ia.js`, `anotarPagamento`,
  ja em `ctx.waitUntil`) chama `emitirAutomatico`; so emite se o tomador do cliente estiver completo
  (nome, CPF/CNPJ valido, rua, numero, bairro, CEP, municipio IBGE). Senao, o pagamento ganha
  `motivo` ("emissão automática parada: falta CEP, ...") e fica em Pagamentos sem nota.
- `email` - entregar ao app do cliente logo depois de emitir (`nfse:nota*`, como abaixo). Desligado,
  a nota so vai ao app pelo botao Enviar ao cliente (`POST notas/:id/enviar`).
- `mail` - mandar tambem por e-mail (Resend, PDF e XML anexos), depois do PDF (`depois`) e no Enviar ao cliente.

Rotas (prefixo `/api/admin/nfse/emissor/`):

- `GET situacao` -> `Situacao = {ambiente: "producao_restrita"|"producao", ambiente_rotulo, producao_liberada,
  prestador: {versao, dados, faltas}, certificado: {instalado, titular, documento, valido_ate, dias_restantes,
  vencido, instalado_em}, municipio: {situacao, frase, pode_emitir, prazo_cancelamento_dias, consultado_em},
  pode_emitir, motivos: [frase], proximo_numero, tabelas, opcoes: {motivos_cancelamento, motivos_substituicao,
  opcao_simples, regime_especial, regime_apuracao_sn, quando_reter, retencoes}, cloudflare, config}`
- `POST prestador {prestador}` -> `{versao, mudou, faltas, prestador}` (400 com a frase quando nao confere).
  O ambiente nao muda por aqui (so por `producao/*`).
- `POST certificado {certPem, cadeiaPem: [pem], chavePkcs8 (base64 do DER), titular, documento, validoAte}` ->
  `{certificado, conexao: {ok, frase, falta_token?, etapa?, erro?, certificate_id?}, cloudflare}`.
  O .pfx e aberto **no navegador** (`site/assets/nfse-pfx.js` com `site/assets/vendor/forge.min.js`,
  carregados so quando alguem instala): o arquivo e a senha nunca vao ao Worker. O DO confere que a
  chave e a do certificado e guarda os dois cifrados (AES-GCM, `NFSE_CHAVE_MESTRA`). Com o token da
  Cloudflare, cadastra o mTLS (abaixo); sem ele, guarda e responde `conexao.falta_token: true` com
  a frase "falta o token da Cloudflare". Falha no cadastro nao desfaz o certificado guardado.
- `POST cloudflare {token}` -> `{cloudflare, conexao | null}`. O token de API (permissoes Account ›
  SSL and Certificates › Edit e Account › Workers Scripts › Edit) fica no KV cifrado
  (`admin:nfse-cf:token`, `NFSE_CHAVE_MESTRA`) e nunca volta a tela. Com um certificado guardado
  que ainda nao e o mTLS em uso, cadastra na hora. `""` apaga o token.
  `Cloudflare = {token: bool, conta, mtls: {id, nome, documento, valido_ate, quando, script} | null,
  auxiliar: "paulus-nfse-mtls", ligado_ao_auxiliar: bool, falta, como_criar_token}`.
- O cadastro do mTLS (`worker/nfse/mtls.js`, conta `CF_ACCOUNT_ID`): (1) `POST /accounts/{id}/mtls_certificates`
  `{ca: false, certificates: folha + cadeia (PEM), private_key: PKCS#8 PEM, name: "nfse-<CNPJ>-<AAAAMMDDhhmm>"}`;
  (2) `PUT /accounts/{id}/workers/scripts/paulus-nfse-mtls` (multipart: `metadata` = `{main_module: "index.js",
  compatibility_date, bindings: [{type: "mtls_certificate", name: "SEFIN", certificate_id}]}` e `index.js` =
  `worker/nfse-mtls/index.js`); (3) `DELETE /accounts/{id}/mtls_certificates/{anterior}`. Se o PUT falha, o
  certificado novo e apagado da Cloudflare e o anterior continua. O Worker principal fala com o auxiliar
  pelo service binding `SEFIN_MTLS` (`wrangler.jsonc`).
- `POST testar` -> `{ok, etapas: [{titulo: "Certificado"|"Conexão com a Sefin"|"Convênio do município", ok, detalhe, ms?}],
  municipio, quando}`.
- `GET clientes` -> `{clientes: [{id, nome, email, telefone, oab, plano, situacao, tomador, ajustado, faltas: [rotulo]}]}`.
  O `tomador` vem do cadastro da conta fundido com o ajuste em `nfse:tomador:<conta>` (o ajuste vence).
- `POST clientes/:conta {tomador}` -> o cliente. So os campos enviados mudam; `""` apaga o ajuste do campo.
  Conferido: CPF/CNPJ com digito, CEP 8 digitos, `cmun` 7 digitos, UF, e-mail, telefone com DDD.
  Nao altera o cadastro original da conta.
- `POST notas {conta?, pagamento?, tomador, valor ("300,00" ou numero) | valor_centavos, descricao, competencia: "AAAA-MM"}`
  -> `Nota`. Com `pagamento`, o que faltar (valor, descricao, competencia) vem dele; um pagamento, uma nota.
  Erro de conferencia: 400 `{erro: "a nota não passou na conferência: ...", erros: [frase], avisos}`;
  sem poder emitir: 409 `{erro, motivos}`.
  `Nota = {id, estado, estado_rotulo, ambiente, conta, pagamento, numero, chave, serie, numero_dps, id_dps, cliente,
  documento, tomador, valor, centavos, competencia, descricao, quando, erro, rejeicao, avisos, tentativas,
  proxima_tentativa, substitui_id, substituida_por_id, cliente_avisado, pdf_em, tem_pdf, email, sefin}`.
- `GET notas?estado=&limite=` -> `{notas: [Nota]}`; `GET notas/:id` -> `{nota, passos, eventos}`.
- `GET notas/:id/xml?tipo=nfse|dps` -> o XML (attachment).
- `GET notas/:id/pdf[?baixar=1]` -> o DANFSe (`application/pdf`; inline, ou attachment com `baixar`). Se o PDF
  ainda nao existe, e gerado neste pedido e guardado em `admin:nfse-pdf:<id>`.
- `POST notas/:id/depois` -> 202. O PDF (e o e-mail, com `mail`) num pedido separado do que emite; a tela
  chama logo depois de emitir. O que sobrar (emissao automatica, nota que saiu da fila) o Cron de cada
  minuto faz, uma por vez (`depoisPendentes`, lista `admin:nfse-depois`).
- `POST notas/:id/enviar` -> `{ok, nota, email, pdf}`: a nota (meta, XML e PDF) no app do cliente e, com `mail`,
  o e-mail. Nota sem conta ou nao emitida: 409.
- `POST notas/:id/tentar` | `descartar` | `situacao`; `POST notas/:id/cancelar {motivo, texto}` ->
  `{evento, nota, prazo}`; `POST notas/:id/substituir {motivo, texto, ajustes: {tomador?, valor?, descricao?,
  competencia?}}` -> `{nota, original}`.
- `POST producao/liberar` (precisa de ao menos uma nota emitida em testes) e `POST producao/voltar` -> `Situacao`.

No KV `APOIOS` (fora do prefixo `admin:nfse:`, que e a lista de pagamentos): `admin:nfse-cf:token`,
`admin:nfse-cf:mtls`, `admin:nfse-cf:cadeia`, `admin:nfse-pdf:<id>`, `admin:nfse-depois`.

### As notas no app do cliente

Emitida (com `email` ligado ou pelo Enviar ao cliente), a nota vai para as chaves que o PAULUS do
cliente le (`worker/nfse-casa.js`, `guardarNotaDoCliente`): a meta em `nfse:nota:<conta>:nuvem-<id>`,
o PDF em `nfse:nota-pdf:<conta>:nuvem-<id>` e o XML em `nfse:nota-xml:<conta>:nuvem-<id>` (base64,
ate 2 MB cada). Cancelada ou substituida, a meta ganha `cancelada` (e `substituta` com o numero da
nova); com `mail`, vai um aviso curto por e-mail. O pagamento ligado fica `nota: "emitida"|"cancelada"`.

O endereco do tomador vem do cadastro do site (`POST /api/ia/site/cadastro`, worker/ia.js), que recebe
`endereco: {cep (8 digitos), logradouro, numero, complemento?, bairro, cidade, uf, cmun (7 digitos ou "")}`,
obrigatorio para cadastro novo e para conta que ja tem endereco; conta antiga sem endereco continua
aceita sem ele. A pagina preenche rua/bairro/cidade/UF e o `cmun` (IBGE) pela ViaCEP; sem ela, a pessoa
digita e o `cmun` fica vazio (o painel completa em Clientes).

O PAULUS do cliente busca as proprias notas em `worker/ia.js`, com o segredo da
instalacao (`Authorization: Bearer pia_<conta>_...`, como as outras `/api/ia/*`):

- `GET /api/ia/nfse` -> `{notas: [{id, numero, competencia, valor, descricao, emitida_em, ambiente, cancelada}]}`
  so da conta autenticada.
- `GET /api/ia/nfse/:id/pdf` e `GET /api/ia/nfse/:id/xml` -> os bytes (`application/pdf` /
  `application/xml`, `Content-Disposition: attachment; filename="NFS-e <numero>.pdf"`); 404 se a nota
  nao for da conta ou nao tiver o arquivo.
