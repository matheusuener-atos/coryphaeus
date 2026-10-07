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

Fora do Access ficam so o rastreio dos e-mails (`/api/e/*`), a pagina do convite
da equipe (`/api/equipe/convite`, abaixo: quem foi convidado ainda nao esta na
politica do Access) e os textos dos planos que a pagina de assinatura le
(`/api/planos/textos`).

Toda resposta e JSON com `cache-control: no-store`. Erro: `{erro: "frase"}`
com o status. Sem a sessao do GitHub: 401 `{erro, passo: "github"}`; sem o
Access: 401 `{erro, passo: "access"}`; papel sem permissao: 403
`{erro: "o papel X nao pode ..."}`.

## Sessao

- `GET /api/admin/sessao` - nunca 401: `{access: {ok, email}, github: {ok, login},
  papel, nome, worker: "0.x", pronto: bool, config: {access, github, email, nfse,
  tuneis, mercado_pago, nuvem, equipe}}` (cada `config.x` = `{ligado: bool, falta: "frase"}`;
  `equipe` e a liberacao automatica do convidado no Access, abaixo).
- `GET /api/admin/github/entrar` - 302 para o GitHub (state no KV, 10 min).
- `GET /api/admin/github/retorno?code&state` - confere o push e grava a sessao;
  302 para `/admin/` (ou `/admin/?erro=frase`). A sessao entra tambem no indice
  `admin:sessoes:<email>` (24 h), por onde "Encerrar todas as sessoes" acha as dos outros aparelhos.
- `POST /api/admin/sair` - apaga a sessao; a pagina vai depois a
  `/cdn-cgi/access/logout`.
- `POST /api/admin/sessoes/encerrar` - apaga todas as sessoes do painel da pessoa logada
  (as do indice e, para as de antes dele, uma volta em `admin:sessao:*`), esta tambem ->
  `{ok, encerradas, access: {feito, frase}, logout}` e o cookie apagado. Com `CF_ACCESS_TOKEN`
  (permissao "Access: Organizations, Identity Providers, and Groups" Edit) e `CF_ACCOUNT_ID`,
  derruba tambem as sessoes do Access dela (`POST /accounts/{conta}/access/organizations/revoke_user
  {email}`); sem eles, `access.feito: false` e a frase diz que as do Access ficam ate vencer.

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
  cadastro: {documento, telefone, oab, termos, quando, cep, logradouro, numero, complemento, bairro, cidade, uf,
  cmun, ajustado: {quando, por, campos} | null} | null, consentimento: {versao, quem, quando} | null,
  assinatura: {id, situacao, valor, desde} | null, plano_proximo, instalacoes: [{instalacao, hash8, criado}],
  pagamentos: [{tipo: "assinatura"|"anual"|"avulso"|"recarga", valor, quando, ref, reembolso?, situacao: "pago"|"reembolsado",
  forma: Forma | null, forma_falta?, nfse: Nfse | null}], pendentes: [{tipo: "anual"|"avulso", ref, valor, quando: null,
  situacao: "pendente", forma: null, forma_falta, plano}], recargas, google_pendente | null}`. O endereco do cadastro vem
  achatado (o medidor guarda em `cadastro.endereco`).
  `Forma = {tipo: "pix"} | {tipo: "cartao", bandeira?, final?, parcelas?, debito?} | {tipo: "saldo"}`. O medidor guarda de
  cada pagamento so o tipo, a referencia, o valor e a data; a forma sai do que e certo - a recarga e o mes no Pix sao Pix;
  a mensalidade e cartao, com a bandeira e o final do cartao guardado na conta (`admin_detalhe.cartao`) quando a cobranca
  e de depois que ele foi posto - e o resto (o anual, que pode ser no cartao ou no Pix, e a mensalidade de antes do
  cartao de agora) do Mercado Pago (`GET /v1/payments/{id}`; a mensalidade pela cobranca, `GET /authorized_payments/{id}`),
  ate 6 consultas por ficha, guardado em `admin:forma:<pagamento>` (so a forma; 400 dias). O que nao da para saber vem
  com `forma_falta` (a frase: sem o Mercado Pago, ele nao disse, ou "na proxima vez que a conta abrir"). `situacao` e a do
  medidor (o reembolso pelo painel ou o estorno do anual); as cobrancas recusadas nao ficam na conta. `pendentes`: o
  pagamento de uma vez que ainda espera a confirmacao (`anual_pendente`; `avulso` quando a referencia e de um mes).
  `Nfse = {id, numero, estado: "emitida"|"cancelada"|"substituida", ambiente, quando, pdf, xml}`: a nota do pagamento no
  emissor da nuvem (a emitida - a substituta, quando houve substituicao; sem ela, a ultima cancelada ou substituida);
  `pdf` e `xml` sao as rotas do painel, atras do Access, de "Notas fiscais" abaixo
  (`https://paulus.ia.br/api/admin/nfse/emissor/notas/:id/pdf?baixar=1` e `.../xml`; todos os papeis baixam).
  Sem o emissor ligado, `nfse` e `null` em todos. O extrato da aba Pagamentos (JSON e PDF, montados na pagina) leva a
  forma, a situacao, o numero, o estado e esses dois links; a tela diz quantos pagamentos ficaram sem a forma e por que.
- `GET /api/admin/tuneis` -> `{tuneis: [{slug, nome, responsavel, estado: "healthy"|"degraded"|"inactive"|"down"|"desativado",
  ultima_conexao, criado_em, tunnel_id, porta, ativo, limpeza: {dias, motivo} | null,
  historico: [{quando, texto}]}], livres: [slug], cf: {ligado, falta}, registro: [Evento]}` onde
  `Evento = {quando, slug, de, evento: "criado"|"alterado"|"desativado"|"reativado"|"liberado", quem, estado: "ativo"|"desativado"|"livre", motivo}`,
  do mais novo ao mais velho (ate 2.000). `slug` e o endereco depois do evento; `de`, o de antes (so na troca);
  `quem`, o e-mail de quem mexeu (o titular, quem esta no painel), `"o escritório"` (sem dono) ou
  `"limpeza automática"`; `motivo`, o da liberacao ou da retomada. O registro (o de enderecos, nao o do escritorio)
  e do `worker/tunel.js`: cada funcao que muda endereco registra sozinha (`registrarEndereco`: provisionar, tambem
  na retomada, que e um "criado" com o motivo; `remover`, pelo escritorio, pela limpeza diaria e pelo painel;
  `alterarEndereco(env, slug, novo, agora, quem)`; `ativarEndereco(env, slug, ativo, agora, quem)`;
  `liberarEndereco(env, slug, motivo, quem)`). No KV `ESCRITORIOS`, uma chave por evento,
  `evento:<instante ISO>:<sorteio>`, com o evento nos metadados (a lista le sem um get por evento), 400 dias.
- `GET /api/admin/tuneis/disponivel?nome=` -> `{ok, motivo}` (as regras de `escritorio/index.html`)
- `GET /api/admin/renovacoes` -> `{abertas: [Renovacao], tratadas: [Renovacao], config: {email, resumo, whats, tol}}`
  onde `Renovacao = {id (da conta), nome, email, plano: {id, nome, valor}, fim, dias_vencido, tolerancia_dias (o total: 5 com a
  assinatura autorizada, 0 sem), motivo, cancelamento: {quando, motivo: "preco"|"uso"|"falta"|"outro", texto} | null,
  lembrete_em, mensagem_em, oferta: {tipo, tokens?, valor?, plano?, ate, quando, por, na_assinatura} | null}`. Quem cancelou
  pela Minha conta (`admin_detalhe.cancelamento`, de `cancelarPelaConta` no `worker/ia.js`) entra quando o ciclo pago acaba,
  com o motivo ("cancelou pela Minha conta: está caro para o escritório (“texto”)"); a cancelada sem motivo (no Mercado
  Pago ou pelo painel) continua fora.
- `GET /api/admin/campanhas` -> `{campanhas: [{id, nome, situacao: "enviada"|"agendada"|"na fila"|"enviando"|"cancelada"|"rascunho",
  publico: {id, label}, enviados, abertos, cliques, devolvidos, quando}], publicos: [{id, label, n, gmail}],
  stats: {enviados, abertura, cliques, devolvidos}, envio: {ligado, falta, de: "naoresponda@paulus.ia.br", ritmo: 50}}`.
  Na agendada, `quando` e a hora marcada (ISO, UTC).
- `GET /api/admin/tokens?visao=geral|modelo|escritorio|conta&periodo=mes|30|90|ano|custom[&de=AAAA-MM-DD&ate=AAAA-MM-DD]` ->
  `{kpis: {entrada, saida, custo_usd, receita, contas}, linhas: [Linha], precos: {entrada, saida, cambio},
  periodo: {nome, de, ate}, incompleto, desde, aviso}` (custo em US$; a pagina converte pelo cambio). O periodo e
  `[de, ate]` em dias de Brasilia: `mes` (do dia 1 a hoje), `30` e `90` (os ultimos dias, hoje incluido), `ano` e
  `custom` (`de` e `ate` obrigatorios; ao contrario ou dia que nao existe: 400). O mes que cabe inteiro no periodo
  vem do total do mes do medidor (`uso_mes`); o pedaco de mes, do uso por dia (`uso`; 400 dias desde 07/10/2026,
  antes so os 62 ultimos dias com uso). Quando falta dia que o medidor ja nao guarda, `incompleto: true`, `desde`
  (o primeiro dia guardado) e `aviso` dizem que o comeco do periodo pode sair menor. A receita e a dos pagamentos
  com data no periodo. `Linha = {nome, entrada, saida, custo_usd, receita}`; na visao `modelo`, tambem `{modelo (o id),
  fabricante, planos: ["Escritório Plus (Ministro)"...], sub: "fabricante · plano ...", preco: [US$ entrada, US$ saida]
  por milhao}`, e a receita de cada conta paga vai para os modelos que ela usou, na proporcao do uso (sem uso no
  periodo, para o modelo principal do plano dela); o uso de antes do registro por modelo e uma linha propria, no
  preco do `IA_PRECOS`.
- `GET /api/admin/planos` -> `{planos: [{id, nome, valor, valor_anual, tokens, pessoas, modelos, recarga, recursos, para, heranca,
  itens: [{titulo, descricao}], textos: {para, heranca, itens}, textos_padrao: {para, heranca}, modelo_nome, custo_modelo,
  assinantes}], padrao: "escritorio",
  recarga: {valor, tokens}, precos: {entrada, saida, cambio}, json: "...", versoes: [Versao], publicado}`. Os planos que
  valem sao os de `admin:planos` (o IA_PLANOS do painel) ou, sem ele, os de fabrica (`worker/ia.js`); o painel le sempre
  do KV, nao do cache de 60 s. `para` (a frase do plano), `heranca` (o texto antes dos itens) e `itens` sao os textos da
  pagina de assinatura: os escritos no painel ou os padrao, montados com os numeros do plano
  (`worker/planos-textos.js`, o mesmo que a pagina mostrava sozinha); `textos` diz quais sao escritos no painel (true), e
  `textos_padrao` traz a frase e o texto antes dos itens que valem com o campo vazio (a aba Edicao os mostra no campo).
  `json`: a lista como fica guardada (os numeros e so os textos escritos no painel). `Versao = {n, quando, quem, resumo,
  planos}`: uma por publicacao que muda os planos (e por retroagir), as 30 ultimas, em `admin:planos:versoes`; a
  primeira e a de antes do historico (os de fabrica ou os que o painel tinha publicado). A ultima e a que esta no ar.
- `GET /api/planos/textos` (fora do Access, `cache-control: public, max-age=60`) -> `{planos: [{id, para, heranca,
  itens: [{titulo, descricao}]}]}`: os textos que a pagina de assinatura (`site/assets/assinatura.js`) mostra - os do
  painel ou os padrao. Os numeros ela le de `/api/ia/planos`. Le os planos do cache do Worker (o mesmo de
  `/api/ia/*`): uma mudanca chega a pagina em ate 60 s.
- `GET /api/admin/nfse` -> `{config: {auto, email, mail}, emissor: {ligado, falta}, situacao: Situacao | null,
  notas: [Nota], pagamentos: [{id, conta, cliente, tipo: "mensalidade"|"recarga pix", valor, quando, nota, numero,
  motivo, erro}], cloudflare: Cloudflare, pode: {emitir: bool}, erro}`. `pagamentos` sao so os sem nota
  (nenhuma nota do emissor com aquele pagamento, fora as descartadas); `motivo` diz por que a emissao
  automatica nao saiu. `Situacao`, `Nota` e `Cloudflare` estao em "Notas fiscais", abaixo.
- `GET /api/admin/equipe` -> `{membros: [{email, nome, papel, ultimo, convite?: {criado, vence, por, vencido}}],
  matriz: [{acao, dono, financeiro, suporte}], liberacao: {ligado, falta}}`. Os convites pendentes vem como membros
  com `convite` (a tela mostra reenviar e cancelar); `liberacao` e a liberacao automatica no Access (abaixo).
- `GET /api/admin/busca?q=` -> `{contas: [...], escritorios: [...], tuneis: [...], planos: [...]}`
  (ate 6 por grupo; cada item `{titulo, desc, tela, alvo}`)
- `GET /api/admin/alteracoes` -> `{pendentes: [Alteracao], publicacoes: [Publicacao]}`
  onde `Alteracao = {id, quando, tela, tipo, alvo, dados, texto}` e
  `Publicacao = {id, quando, commit, resumo, n, por, revertida: {quando, por, commit} | null, retroagivel}`
  (`commit` e o sha curto, quando virou commit no GitHub, ou `"kv-xxxxx"`).

## Na hora (sem passar pela fila)

Comunicacao e marcacao, que nao mudam o que esta no ar:

- `POST /api/admin/tuneis/:slug/avisar` -> e-mail ao responsavel com o prazo da limpeza
- `POST /api/admin/renovacoes/:id/lembrete` -> e-mail "seu plano nao renovou"
- `POST /api/admin/renovacoes/:id/mensagem` `{texto}` (ate 4.000 caracteres) -> a mensagem do proprio punho por
  e-mail para a conta, de `"<Nome> (PAVLVS) <naoresponda@paulus.ia.br>"`, assinada com o nome de quem escreveu
  (resposta: `contato@paulus.ia.br`) -> `{abertas, tratadas, config}`. A marca da renovacao anota `mensagem_em` e
  `mensagens: [{quando, por}]` (o texto nao fica guardado). Conta sem ciclo vencido: 404; texto vazio: 400.
- `POST /api/admin/renovacoes/:id/tratar` / `.../reabrir`
- `POST /api/admin/renovacoes/config` `{email, resumo, whats, tol}`
- `POST /api/admin/campanhas/teste` `{campanha}` -> um e-mail de teste para quem esta na sessao
- `POST /api/admin/equipe/convite/:email/reenviar` (so o dono) -> um link novo (o anterior para de valer), mais
  7 dias, e o e-mail de novo -> `GET /api/admin/equipe`. Sem convite para o e-mail: 404.
- Sem o provedor de e-mail (`RESEND_API_KEY`), essas rotas respondem 503
  `{erro: "o envio de e-mail ainda nao esta ligado: falta RESEND_API_KEY"}`.

## A fila (Confirmar alteracoes)

Tudo o que muda o que esta no ar entra na fila da sessao e so acontece em "Commitar e pushar":

- `POST /api/admin/alteracoes` `{tela, tipo, alvo, dados, texto}` -> `{pendentes}`.
  `texto` e a frase no passado que a lista mostra ("Apaguei moura-associados").
  O que da para conferir antes (formato, se a conta tem assinatura, se o e-mail esta ligado) volta 400 com o porque.
- `DELETE /api/admin/alteracoes/:id` -> `{pendentes}`
- `POST /api/admin/publicar` `{confirmacao: "comitar e pushar"}` ->
  `{ok, resultados: [{id, ok, erro, aviso?}], publicacao: Publicacao}`.
  Aplica em ordem; uma que falha nao desfaz as outras, e volta com o motivo. `aviso`: feita, mas com uma parte
  a mao (ex.: tirada da equipe, mas nao do Access).

Tipos (`tipo` -> `dados`), e o papel que pode:

| tipo | dados | papel |
| --- | --- | --- |
| `conta.creditar` | `{id, tokens}` | dono, financeiro |
| `conta.instalacao.apagar` | `{id, hash8}` | dono, suporte |
| `conta.cancelar` | `{id}` | dono, financeiro |
| `conta.plano` | `{id, plano}` | dono, financeiro |
| `conta.pausar` | `{id, retomar?}` | dono, financeiro |
| `conta.cadastro` | `{id, escritorio?, documento?, telefone?, oab?, cep?, logradouro?, numero?, complemento?, bairro?, cidade?, uf?}` | todos |
| `google.servicos` | `{id, ligados: [escopo]}` | dono, suporte |
| `google.desvincular` | `{id}` | dono, suporte |
| `tunel.apagar` | `{slug}` | dono, suporte |
| `tunel.endereco` | `{slug, novo}` | dono, suporte |
| `tunel.ativo` | `{slug, ativo}` | dono, suporte |
| `campanha.disparar` | `{nome, publico, contas?, assunto, pre, titulo, texto, botao, link, quando, de?, hora?}` | todos |
| `campanha.cancelar` | `{id}` | todos |
| `renov.oferta` | `{id, tipo: "creditos", tokens}` ou `{id, tipo: "preco", valor, plano}` | dono, financeiro |
| `plano.editar` | `{id, valor, valor_anual, tokens, nome?, pessoas?, recarga?: {valor, tokens}, para?, heranca?, itens?: [{titulo, descricao}]}` | dono, financeiro |
| `plano.criar` | `{id, nome, valor, valor_anual, tokens}` (modelo e recursos: os do Escritorio) | dono, financeiro |
| `planos.json` | `{planos: [{id, nome, valor, valor_anual, tokens, pessoas?, modelos?, recarga?, recursos?, para?, heranca?, itens?}]}` | dono, financeiro |
| `nfse.config` | `{auto, email, mail}` | dono, financeiro |
| `equipe.papel` | `{email, papel}` | dono |
| `equipe.membro` | `{acao: "criar", nome, email, papel}`, `{acao: "editar", de, nome, email, papel}`, `{acao: "excluir", email}` ou `{acao: "cancelar_convite", email}` | dono |

`google.servicos` vira a ordem para o PAULUS do escritorio (`google_pendente`, a mesma da Minha conta):
o servico fora de `ligados` ele para de usar - o Google nao revoga um escopo sozinho, a permissao
continua concedida la -, e `ligados` vazio ele revoga a concessao inteira no Google. A ordem sai da
conta quando ele conta que cumpriu (`POST /api/ia/google` com `aplicado`); `google` e o que ele
conta que usa, so os nomes curtos dos escopos (paulus/legal/src/google_nuvem.py, worker/teste-google.mjs).

Ver contas, tokens e receita, mandar e-mails e lembretes: todos os papeis.

O que cada tipo novo faz na publicacao:

- `conta.plano` - vale na proxima cobranca (a tela promete isso): `PUT /preapproval/{id}` com o valor do plano novo
  (`reason: "PAULUS - plano <nome>"`, o mesmo das assinaturas do `worker/ia.js`) e a conta marca `plano_proximo`; o
  ciclo pago fica no plano em que foi pago. O plano de agora de novo desfaz a troca marcada. Recusado (400, na fila):
  sem assinatura mensal ativa, cortesia, pago de uma vez (anual ou mes no Pix: a troca e na renovacao) e com uma
  cobranca de valor ajustado em curso (oferta ou a diferenca de uma troca). A troca para um mais caro valendo agora,
  com a diferenca, e a da Minha conta (`trocarPlanoAgora`), nao a do painel.
- `conta.cadastro` - so os campos que mudaram; o resto vem do cadastro de agora, e o conjunto e conferido como o do
  site (`conferirCadastro`): CPF/CNPJ com digito, telefone com DDD, OAB/RG/CNH, endereco completo (obrigatorio se a
  conta ja tinha endereco ou se a edicao mexe nele). Cidade ou UF novas trazem o codigo IBGE pela tabela da NFS-e
  (nome exato na UF; sem bater, fica vazio e o painel completa em Notas fiscais > Clientes). O aceite dos termos
  (`termos`, `quando`) continua o que a pessoa deu; a edicao fica em `cadastro.ajustado: {quando, por, campos}`.
- `conta.pausar` - `PUT /preapproval/{id} {status: "paused"}` (com `retomar: true`, `"authorized"`), e a conta anota a
  situacao. Recusado: o pago de uma vez (anual ou mes no Pix) e o Pix mensal ("nao ha cobranca automatica no Mercado
  Pago para pausar"), sem assinatura, ou na situacao errada (so a ativa pausa, so a pausada retoma). Retomar depois
  do fim do ciclo nao abre o ciclo antes da cobranca: ele vem com a cobranca, como nas outras renovacoes.
- `campanha.disparar` - `quando`: `"agora"`, `"amanha"` e `"segunda"` (9 h de Brasilia) ou `"agendado"` com `de`
  (`AAAA-MM-DD`) e `hora` (`HH:MM`), no horario de Brasilia: fica guardada (`agendada`, com `envio_em`) e o Cron de cada
  minuto (`enviarCampanhas`) manda na hora marcada. Na fila, sem dia ou hora, ou com a hora ja passada (ou a mais de
  um ano): 400; publicada depois da hora marcada: falha ("passou antes de publicar: agende de novo"), para nao sair
  atrasada sem ninguem ver. `publico: "escolhidas"` com `contas: [id]` (ate 2.000) manda so para elas.
- `renov.oferta` - a oferta para quem nao renovou, sem cupom (o cupom saiu do sistema em 04/10/2026), pelo
  `ofertaDeVolta(env, mp, conta, oferta, por)` do `worker/ia.js`: os creditos (de 0,1 M a 500 M) entram com o
  proximo pagamento confirmado; o preco especial (entre zero e o valor do plano) vale no proximo pagamento do plano -
  na assinatura mensal que ainda existe, no mesmo plano e sem outro ajuste (`na_assinatura: true`; o Mercado Pago
  passa a cobrar o valor e volta ao cheio depois de pago), ou na assinatura nova pelo site. Vale 60 dias. A pessoa
  recebe um e-mail contando, e a marca da renovacao guarda a oferta (`Renovacao.oferta`). Na fila: a conta precisa
  estar em Nao renovacoes e o e-mail ligado (`RESEND_API_KEY`). Se a oferta ficou na conta mas o e-mail nao saiu, a
  publicacao diz no `aviso`.
- `equipe.membro` - `criar`: o convite (abaixo), so com nome, e-mail e papel (nem documento nem endereco); precisa do
  e-mail ligado. `editar` com o mesmo e-mail muda nome e papel; com outro, o novo recebe um convite e o antigo sai da
  equipe (e do Access). `excluir`: sai da equipe, as sessoes do painel dela caem e, com a API do Access, sai da
  politica e as sessoes do Access dela caem; sem a API, o `aviso` diz que o Access e a mao. `cancelar_convite`: o
  link para de valer. A equipe nunca fica sem dono.
- `plano.editar` - o valor novo vai para as assinaturas mensais que o plano cobra na proxima cobranca (o plano marcado
  para a renovacao, se houver, senao o de agora); o pago de uma vez nao tem preapproval, e quem esta com uma cobranca
  de valor ajustado fica com o ajuste e passa ao preco do plano quando ele acabar (o `aviso` diz quem). Da aba Edicao
  vem tambem o nome, as pessoas (de 1 a 500; o Paulus instalado le), a recarga (`{valor, tokens}`, os pacotes do Pix;
  `null` fica a de agora) e os textos da pagina de assinatura (a frase ate 160 caracteres, o texto antes dos itens ate
  120, ate 20 itens com titulo ate 80 e descricao ate 600). Texto vazio, ou igual ao padrao (o de antes da mudanca ou o
  de depois, com os numeros novos), nao e guardado: a pagina fica com o padrao, que acompanha os numeros do plano.
- `planos.json` - a aba .JSON: a lista inteira no lugar da de agora, conferida com as regras do Worker (sem elas ele
  ignoraria a lista e voltaria aos planos de fabrica): ate 12 planos, ids unicos, o `escritorio` (o padrao) presente, so
  os campos de plano, valores maiores que zero, tokens inteiros, pessoas de 1 a 500, modelos do catalogo (`MODELOS`)
  nos niveis que existem, recursos que existem (com `profundidade` num nivel), recarga com valor e tokens, e os textos
  como no `plano.editar`. Plano que sai da lista com conta nele (ou com a troca marcada para ele): recusado. Os textos
  iguais aos padrao nao sao guardados; quem assina um plano cujo valor mudou passa a pagar o novo na proxima cobranca.
- `campanha.cancelar` - a campanha agendada (ou a que ainda esta saindo) para: o que falta sair nao sai mais, a lista
  de e-mails sai do KV e ela fica `cancelada` (com quem e quando); o que ja saiu continua (o `aviso` diz quantos). A que
  ja saiu inteira ou ja cancelada: 400. Vale na publicacao: se a hora marcada chegar antes, ela sai.

## O convite da equipe (fora do Access)

- O e-mail do convite (Resend) leva `https://paulus.ia.br/api/equipe/convite?t=<64 hex>`; vale 7 dias. O KV guarda
  so o resumo SHA-256 do link, em `admin:convites` (`[{email, nome, papel, h, criado, vence, por, por_nome}]`, ate 50).
- `GET /api/equipe/convite?t=` -> a pagina do convite (HTML, sem script; CSP com `form-action 'self'`): quem
  convidou, nome, e-mail, papel e ate quando vale, e o botao Aceitar. Abrir o link nao aceita (os leitores de link
  dos e-mails nao aceitam pela pessoa). Link que nao existe, cancelado, trocado ou ja usado: 410; vencido: 410
  "venceu".
- `POST /api/equipe/convite` (formulario `t`) -> aceita: a pessoa entra na equipe (`admin:equipe`) com o papel do
  convite e, com a API do Access ligada, o e-mail entra na politica da aplicacao do painel
  (`GET` e `PUT /accounts/{CF_ACCOUNT_ID}/access/apps/{ACCESS_APP_ID}/policies/{ACCESS_POLICY_ID}`, a politica inteira,
  com `{email: {email}}` a mais no `include`; o resto - nome, decisao, exclude, require, duracao - fica como esta). O
  convite sai. Se o Access recusar, 502 "Quase lá": ela ja esta na equipe e o link continua valendo para tentar de novo.
  Sem a API (`CF_ACCESS_TOKEN`, permissao "Access: Apps and Policies" Edit; `ACCESS_APP_ID` e `ACCESS_POLICY_ID`), a
  pagina, o e-mail e a tela Equipe (`liberacao`, `config.equipe`) dizem que o e-mail vai a politica a mao, pelo dono.
- Limite por endereco de internet (`LIMITE`), como as outras rotas publicas.

## Retroagir

- `POST /api/admin/retroagir` `{publicacao (o id) | commit, confirmacao: "retroagir"}` (so o dono) ->
  `{ok, commit, publicacao: Publicacao, avisos: [frase]}`. A tela manda o `commit`.
- Cada publicacao guarda, desde 07/10/2026, o retrato do que mudou (`admin:retrato:<id>`, 30 dias). Volta: o que so
  mudou o KV do painel (`plano.criar`, `plano.editar`, `planos.json`, `nfse.config`, `equipe.papel`), com o valor de antes
  e o de depois - nos planos, quem assina um plano cujo valor voltou volta a pagar o de antes no Mercado Pago, e o
  historico ganha a versao "Retroagi: ..." -; `conta.cadastro` (o
  cadastro de antes); `campanha.disparar` (o que ainda nao saiu e cancelado; os e-mails que sairam continuam, e o
  aviso diz); `conta.pausar` (o Mercado Pago volta a situacao de antes). O resto mudou fora do painel (creditos,
  reembolso, cancelamento no Mercado Pago, Google, tuneis, convites, a troca de plano, a oferta, a campanha cancelada) e
  e desfeito pela propria tela.
- Tudo ou nada: se um item nao volta, ou o que ele mudou mudou de novo depois (outra publicacao por cima, a equipe
  com um convite aceito, um plano criado que ja tem conta), 409 com cada um e o porque, e nada muda. Retroaja a mais
  nova primeiro. Os itens desfeitos ficam marcados: se um parar no meio (o Mercado Pago recusou), tentar de novo
  termina sem desfazer duas vezes.
- As publicacoes que viraram commit no GitHub (as dos materiais, antes de 07/10) voltam num commit de reversao na
  main, pela API do GitHub com o token de quem esta logado: cada arquivo dos commits volta ao que era antes deles (o
  que eles criaram sai), numa arvore nova sobre a ponta da main (`git/trees`, `git/commits`, `PATCH git/refs/heads/main`
  sem forcar). Se um desses arquivos mudou depois na main, nao reverte (502: "retroaja pelo git").
- Sem retrato (as publicacoes de antes de 07/10/2026 que so mudaram o KV) ou com o retrato vencido: 409 dizendo que
  nao da para retroagir aquela. Ja retroagida: 409.

## Notas fiscais (emissor da nuvem)

As NFS-e que o PAVLVS emite para quem assina sao emitidas pelo painel: aba Notas fiscais,
rotas `/api/admin/nfse/emissor/*` (`worker/nfse/api.js`, `atenderEmissor`) ate o Durable Object
`EmissorNFSe` (`worker/nfse/emissor.js`). Testes: `worker/teste-nfse-admin.mjs` (painel + emissor),
`worker/teste-nfse-emissor.mjs` (o emissor), `worker/teste-nfse-danfse.mjs` (o DANFSe contra o do PAULUS)
e `worker/tela-nfse/teste_tela.py` (a tela, Playwright).

- **Mesmas portas do painel** (Access + sessao do GitHub). `GET` para todos os papeis; o resto
  (emitir, cancelar, substituir, enviar, certificado, parametros, token, testar, producao) so
  `dono` e `financeiro`: suporte recebe 403 `{erro: "o papel suporte só vê as notas fiscais: ..."}`.
- **Na hora**: nada disso passa pela fila de alteracoes. So os tres interruptores (`nfse.config`)
  continuam na fila.
- Sem o emissor (`EMISSOR_NFSE`, `NFSE_CHAVE_MESTRA` ou `APOIOS`): 503 `{erro: "o emissor de NFS-e ainda nao esta ligado: falta ..."}`
  (menos `GET municipios`, que e so a tabela).
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
- `GET municipios?q=<nome>&uf=<UF opcional>` -> `{municipios: [{codigo, nome, uf}]}`, ate 12, da tabela oficial
  (`worker/nfse/tabelas/municipios.json`, `buscarMunicipios`): sem acento e sem caixa, por comeco de palavra
  ("goi" -> Goiania/GO, "paulo" -> Sao Paulo/SP); primeiro o nome igual, depois o que comeca pelo texto, depois
  o que tem uma palavra que comeca por ele; em cada grupo as capitais primeiro e depois a ordem alfabetica.
  Os 7 digitos do codigo IBGE acham o municipio. Todos os papeis (suporte tambem). Nos pop-ups Emitir,
  Clientes e Parametros o campo de municipio busca por aqui: mostra "Nome/UF", guarda o codigo IBGE
  escondido (`cmun` / `municipio`) e preenche a UF do tomador; colar o codigo tambem serve.
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
  ainda nao existe, e gerado neste pedido e guardado em `admin:nfse-pdf:<id>`. O DANFSe e o do leiaute da
  NT 008 (`worker/nfse/danfse.js`, `gerarDanfse(xml)`, porte de `paulus/legal/src/nfse/danfse.py`): uma
  pagina A4, os mesmos blocos e campos do PAULUS, tirados so do XML da NFS-e, com o QR Code da consulta
  publica; fontes padrao do PDF (Helvetica). CPU: ~1,5 ms quente, ~11-13 ms na 1a chamada de um isolate.
  A conferencia visual contra o do Python fica em `worker/nfse/fixtures/danfse/`
  (`fixtures/comparar_danfse.py`).
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
