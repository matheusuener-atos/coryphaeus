# Painel admin do PAVLVS - o contrato das rotas

Desde 11/10/2026 o painel do PAVLVS mora no painel da Atos (`atos.dev.br/admin`, a pagina em
`C:\atos\public\admin\`). O servidor continua aqui, em `worker/admin.js`; a Atos (`C:\atos\worker\admin.js`)
confere quem entra e encaminha. Este arquivo e o contrato entre a pagina, a Atos e o Worker do PAVLVS; quem
mudar um lado muda o outro e este texto. `paulus.ia.br/admin` (e `/admin/*`) responde 301 para
`https://atos.dev.br/admin/` (pelo Worker: `/admin` esta no `run_worker_first`).

**O prefixo**: toda rota do painel do PAVLVS e `/api/admin/pavlvs/<rota>`, a mesma `<rota>` de antes (antes,
`/api/admin/<rota>`). A pagina chama `https://atos.dev.br/api/admin/pavlvs/<rota>`; a Atos encaminha o mesmo
caminho e a mesma query a `/api/admin/pavlvs/<rota>` no Worker do PAVLVS. Nas secoes abaixo, `/api/admin/pavlvs/x`
e sempre esse caminho; os corpos e as respostas sao os mesmos de antes, salvo o que esta dito.

## Portas

1. **Conta Atos** (na Atos): a sessao do atos.dev.br (cookie `__Host-atos`), com login de ate 12 horas, e o
   e-mail na equipe do painel da Atos (abaixo, "O painel na Atos"). Sem sessao: 401 `{erro, entrar: true}`;
   login velho: 401 `{erro, reentrar: true}`; fora da equipe: 403 `{erro}` (a pagina volta calada para `/conta/`;
   a resposta nao diz nada da configuracao). Quem esta na equipe mas nao tem a area `pavlvs` (abaixo, "As areas"):
   403 `{erro: "você não atua no PAVLVS: peça ao dono para incluir a área"}`. Nada disso chega ao PAVLVS.
2. **O encaminhamento** (Atos -> PAVLVS): a rota generica `/api/admin/<produto>/*` da Atos, pelo registro de
   produtos (abaixo, "Os produtos"); para o PAVLVS, o service binding `PAVLVS` (wrangler.jsonc da Atos,
   `service: "paulus"`).
   A Atos monta o pedido do zero - o metodo, o caminho com a query, `content-type`, `accept` e o corpo intactos;
   nenhum outro cabecalho do navegador passa - e acrescenta:
   - `Atos-Painel-Quem`: base64url (sem `=`) do JSON `{email, nome, papel, github: {login, token} | null}`.
     `github` vem quando a pessoa ligou o GitHub nesta sessao do painel (abaixo) e so porque o PAVLVS tem
     `github: true` no registro; a produto sem isso vai sempre `null`.
   - `Atos-Painel-Assinatura`: `t=<segundos>,v1=<hex>`, o HMAC-SHA256, com o segredo `PAINEL_SEGREDO_PAVLVS`
     (o mesmo valor nos dois Workers), de `"<t>.<METODO>.<caminho com a query>.<SHA-256 hex do corpo>.<Atos-Painel-Quem>"`
     (corpo vazio no GET: o SHA-256 de nada).
   A resposta do PAVLVS volta como veio (status, cabecalhos, corpo). Sem o binding (o Worker de teste da Atos, que
   nao tem PAVLVS) ou sem o segredo na Atos: 503 `{erro: "o PAVLVS não está ligado a este painel"}`. O PAVLVS
   nao respondeu: 502.
3. **O PAVLVS confere** (`conferirAtos`): assinatura que nao confere, mais de 60 s de diferenca (`JANELA_ATOS_S`),
   e-mail que nao serve ou papel fora de `dono | financeiro | suporte`: 401 `{erro: "pedido sem a assinatura do
   painel da Atos"}`. Sem `PAINEL_SEGREDO_PAVLVS` no PAVLVS: 503 `{erro: "o painel da Atos não está ligado a este
   Worker"}` (o nome do segredo so no log). Um pedido direto da internet a `paulus.ia.br/api/admin/pavlvs/*` cai
   no 401; o caminho antigo, `paulus.ia.br/api/admin/*` sem o `pavlvs/`, responde 404.
4. **O papel**: o PAVLVS confia no papel que a Atos assina, e decide aqui quem pode o que (a tabela `PODE` e a
   matriz de `GET /api/admin/pavlvs/papeis`). A Atos nao barra papel nenhum no encaminhamento.
5. **GitHub** (OAuth App "PAVLVS Admin", na Atos): so para comitar e pushar e para retroagir. Sem o GitHub na
   sessao, `POST /api/admin/pavlvs/publicar` e `/retroagir` respondem 403 `{erro, passo: "github"}`; a tela leva a
   `https://atos.dev.br/api/admin/github/entrar?volta=<tela>`, que volta a `/admin/?github=1#<tela>`.

Fora do painel ficam so o rastreio dos e-mails (`paulus.ia.br/api/e/*`) e os textos dos planos que a pagina de
assinatura le (`paulus.ia.br/api/planos/textos`). Saíram do PAVLVS: o Cloudflare Access, a sessao `pv_admin`,
`/api/admin/github/*`, `/api/admin/sair`, `/api/admin/sessoes/encerrar`, a equipe (`/api/admin/equipe*`, o convite
`/api/equipe/convite`) e as notas fiscais (`/api/admin/nfse`, `/api/admin/nfse/emissor/*`).

Toda resposta e JSON com `cache-control: no-store`. Erro: `{erro: "frase"}` com o status. Papel sem permissao:
403 `{erro: "o papel X nao pode ..."}`.

## Sessao

- `GET /api/admin/pavlvs/sessao` -> `{access: {ok: true, email}, github: {ok, login}, papel, nome, worker: "0.x",
  pronto: true, config: {email, tuneis, nuvem}}` (cada `config.x` = `{ligado: bool, falta: "frase"}`). `access` e
  quem a Atos assinou (o nome ficou por compatibilidade; nao ha mais Access). `config` perdeu `access`, `github`,
  `nfse` e `equipe`: o GitHub e da Atos (`GET /api/admin/eu`, abaixo), a NFS-e saiu do painel e a equipe e da Atos.
- `GET /api/admin/pavlvs/papeis` -> `{matriz: [{acao, dono, financeiro, suporte}]}`: quem pode o que no PAVLVS (a
  matriz que antes vinha em `GET /api/admin/equipe`). A da Atos vem em `GET /api/admin/equipe` da Atos.
- Entrar, sair e o GitHub sao da Atos (abaixo). "Encerrar todas as sessoes" e o da Conta Atos.

## Leitura

Datas em ISO 8601 (UTC); dinheiro em reais (numero); tokens em unidades.

- `GET /api/admin/pavlvs/visao` -> `{agora, kpi: {receita_mes, receita_assinaturas, receita_recargas,
  custo_usd_mes, cambio, entrada_mes, saida_mes, contas, contas_ativas, escritorios, tokens_hoje},
  dias: [{dia: "AAAA-MM-DD", turno: 0|1|2, total, saida}] (42, do mais antigo ao mais novo),
  pendencias: [{icone, titulo, sub, tela, filtro?}]}` (os `avisos` do Mercado Pago do PAVLVS sairam com a cobranca
  propria, em 10/10/2026)
- `GET /api/admin/pavlvs/contas` -> `{contas: [Conta], escritorios: [{nome, slug, documento,
  contas: [id], tokens_mes, receita_mes}]}` onde
  `Conta = {id, nome, email, escritorio: {nome, slug, documento}, oab, plano: {id, nome, valor, tokens},
  situacao: "ativa"|"vencida"|"cortesia"|"pendente"|"cancelada", restantes, usados, extra,
  ultimo_uso, google: {escopos: [], conferido} | null}`
- `GET /api/admin/pavlvs/contas/:id` -> `Conta + {criada, ciclo: {inicio, fim, tokens, usados} | null,
  cadastro: {documento, telefone, oab, termos, quando, cep, logradouro, numero, complemento, bairro, cidade, uf,
  cmun, ajustado: {quando, por, campos} | null} | null, consentimento: {versao, quem, quando} | null,
  assinatura: {id, situacao, valor, desde} | null, instalacoes: [{instalacao, hash8, criado}],
  pagamentos: [{tipo: "assinatura"|"anual"|"avulso"|"recarga", valor, quando, ref, reembolso?, situacao: "pago"|"reembolsado",
  nfse: Nfse | null}], recargas, google_pendente | null, desvinculado | null, pago_ate | null, periodo: "mensal"|...}`.
  O endereco do cadastro vem achatado (o medidor guarda em `cadastro.endereco`). Os `pagamentos` sao os que o medidor
  ainda guarda do caminho de antes da Atos (o painel nao consulta o Mercado Pago: sem `forma`, `pendentes` nem
  `plano_proximo`, que sairam em 10/10/2026); o que a Atos cobra fica nas faturas da Atos.
  `Nfse = {id, numero, estado: "emitida"|"cancelada"|"substituida", ambiente, quando, pdf: null, xml: null}`: a nota do
  pagamento no emissor do PAVLVS (a emitida - a substituta, quando houve substituicao; sem ela, a ultima cancelada ou
  substituida). Desde 11/10/2026 `pdf` e `xml` sao sempre `null`: as rotas do emissor sairam do painel (as notas sao
  da Atos). Sem o emissor ligado, `nfse` e `null` em todos.
- `GET /api/admin/pavlvs/tuneis` -> `{tuneis: [{slug, nome, responsavel, estado: "healthy"|"degraded"|"inactive"|"down"|"desativado",
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
- `GET /api/admin/pavlvs/tuneis/disponivel?nome=` -> `{ok, motivo}` (as regras de `escritorio/index.html`)
- `GET /api/admin/pavlvs/renovacoes` -> `{abertas: [Renovacao], tratadas: [Renovacao], config: {email, resumo, whats, tol}}`
  onde `Renovacao = {id (da conta), nome, email, plano: {id, nome, valor}, fim, dias_vencido, tolerancia_dias (o total: 5 com a
  assinatura autorizada, 0 sem), motivo, lembrete_em, mensagem_em}`. So entra a conta cobrada pela Atos (`cobrador: "atos"`)
  com o ciclo pago vencido; o `motivo` vem do retrato que a Atos mandou ("cancelou a assinatura na Atos", "a cobrança do
  mês não chegou da Atos (...)", "assinatura pausada na Atos" ou "o período pago na Atos acabou e não foi renovado"). A
  cortesia e o caminho antigo (fora da Atos) nao entram.
- `GET /api/admin/pavlvs/campanhas` -> `{campanhas: [{id, nome, situacao: "enviada"|"agendada"|"na fila"|"enviando"|"cancelada"|"rascunho",
  publico: {id, label}, enviados, abertos, cliques, devolvidos, quando}], publicos: [{id, label, n, gmail}],
  stats: {enviados, abertura, cliques, devolvidos}, envio: {ligado, falta, de: "naoresponda@paulus.ia.br", ritmo: 50}}`.
  Na agendada, `quando` e a hora marcada (ISO, UTC).
- `GET /api/admin/pavlvs/tokens?visao=geral|modelo|escritorio|conta&periodo=mes|30|90|ano|custom[&de=AAAA-MM-DD&ate=AAAA-MM-DD]` ->
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
- `GET /api/admin/pavlvs/planos` -> `{planos: [{id, nome, valor, valor_anual, tokens, pessoas, modelos, recarga, recursos, para, heranca,
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
- `GET /api/planos/textos` (fora do painel, `cache-control: public, max-age=60`) -> `{planos: [{id, para, heranca,
  itens: [{titulo, descricao}]}]}`: os textos que a pagina de assinatura (`site/assets/assinatura.js`) mostra - os do
  painel ou os padrao. Os numeros ela le de `/api/ia/planos`. Le os planos do cache do Worker (o mesmo de
  `/api/ia/*`): uma mudanca chega a pagina em ate 60 s.
- `GET /api/admin/pavlvs/busca?q=` -> `{contas: [...], escritorios: [...], tuneis: [...], planos: [...]}`
  (ate 6 por grupo; cada item `{titulo, desc, tela, alvo}`)
- `GET /api/admin/pavlvs/alteracoes` -> `{pendentes: [Alteracao], publicacoes: [Publicacao]}`
  onde `Alteracao = {id, quando, tela, tipo, alvo, dados, texto}` e
  `Publicacao = {id, quando, commit, resumo, n, por, revertida: {quando, por, commit} | null, retroagivel}`
  (`commit` e o sha curto, quando virou commit no GitHub, ou `"kv-xxxxx"`).

## Na hora (sem passar pela fila)

Comunicacao e marcacao, que nao mudam o que esta no ar:

- `POST /api/admin/pavlvs/tuneis/:slug/avisar` -> e-mail ao responsavel com o prazo da limpeza
- `POST /api/admin/pavlvs/renovacoes/:id/lembrete` -> e-mail "seu plano nao renovou"
- `POST /api/admin/pavlvs/renovacoes/:id/mensagem` `{texto}` (ate 4.000 caracteres) -> a mensagem do proprio punho por
  e-mail para a conta, de `"<Nome> (PAVLVS) <naoresponda@paulus.ia.br>"`, assinada com o nome de quem escreveu
  (resposta: `contato@paulus.ia.br`) -> `{abertas, tratadas, config}`. A marca da renovacao anota `mensagem_em` e
  `mensagens: [{quando, por}]` (o texto nao fica guardado). Conta sem ciclo vencido: 404; texto vazio: 400.
- `POST /api/admin/pavlvs/renovacoes/:id/tratar` / `.../reabrir`
- `POST /api/admin/pavlvs/renovacoes/config` `{email, resumo, whats, tol}`
- `POST /api/admin/pavlvs/campanhas/teste` `{campanha}` -> um e-mail de teste para quem esta na sessao
- Sem o provedor de e-mail (`RESEND_API_KEY`), essas rotas respondem 503
  `{erro: "o envio de e-mail ainda nao esta ligado: falta RESEND_API_KEY"}`.

## A fila (Confirmar alteracoes)

Tudo o que muda o que esta no ar entra na fila da sessao e so acontece em "Commitar e pushar":

- `POST /api/admin/pavlvs/alteracoes` `{tela, tipo, alvo, dados, texto}` -> `{pendentes}`.
  `texto` e a frase no passado que a lista mostra ("Apaguei moura-associados").
  O que da para conferir antes (formato, se a conta tem assinatura, se o e-mail esta ligado) volta 400 com o porque.
- `DELETE /api/admin/pavlvs/alteracoes/:id` -> `{pendentes}`
- `POST /api/admin/pavlvs/publicar` `{confirmacao: "comitar e pushar"}` ->
  `{ok, resultados: [{id, ok, erro, aviso?}], publicacao: Publicacao}`.
  Aplica em ordem; uma que falha nao desfaz as outras, e volta com o motivo. `aviso`: feita, mas com uma parte
  a mao (ex.: a campanha cancelada com parte dos e-mails ja enviados).

Tipos (`tipo` -> `dados`), e o papel que pode (a cobranca e da Atos: os tipos de dinheiro - cancelar, trocar o
plano, pausar, oferta de volta - sairam em 10/10/2026; a equipe saiu em 11/10/2026 e e a fila da Atos, abaixo; os
interruptores das notas, `nfse.config`, sairam com as notas):

| tipo | dados | papel |
| --- | --- | --- |
| `conta.creditar` | `{id, tokens}` | dono, financeiro |
| `conta.instalacao.apagar` | `{id, hash8}` | dono, suporte |
| `conta.cadastro` | `{id, escritorio?, documento?, telefone?, oab?, cep?, logradouro?, numero?, complemento?, bairro?, cidade?, uf?}` | todos |
| `google.servicos` | `{id, ligados: [escopo]}` | dono, suporte |
| `google.desvincular` | `{id}` | dono, suporte |
| `tunel.apagar` | `{slug}` | dono, suporte |
| `tunel.endereco` | `{slug, novo}` | dono, suporte |
| `tunel.ativo` | `{slug, ativo}` | dono, suporte |
| `campanha.disparar` | `{nome, publico, contas?, assunto, pre, titulo, texto, botao, link, quando, de?, hora?}` | todos |
| `campanha.cancelar` | `{id}` | todos |
| `plano.editar` | `{id, valor, valor_anual, tokens, nome?, pessoas?, recarga?: {valor, tokens}, para?, heranca?, itens?: [{titulo, descricao}]}` | dono, financeiro |
| `plano.criar` | `{id, nome, valor, valor_anual, tokens}` (modelo e recursos: os do Escritorio) | dono, financeiro |
| `planos.json` | `{planos: [{id, nome, valor, valor_anual, tokens, pessoas?, modelos?, recarga?, recursos?, para?, heranca?, itens?}]}` | dono, financeiro |

`google.servicos` vira a ordem para o PAULUS do escritorio (`google_pendente`, a mesma da Minha conta):
o servico fora de `ligados` ele para de usar - o Google nao revoga um escopo sozinho, a permissao
continua concedida la -, e `ligados` vazio ele revoga a concessao inteira no Google. A ordem sai da
conta quando ele conta que cumpriu (`POST /api/ia/google` com `aplicado`); `google` e o que ele
conta que usa, so os nomes curtos dos escopos (paulus/legal/src/google_nuvem.py, worker/teste-google.mjs).

Ver contas, tokens e receita, mandar e-mails e lembretes: todos os papeis.

O que cada tipo novo faz na publicacao:

- `conta.cadastro` - so os campos que mudaram; o resto vem do cadastro de agora, e o conjunto e conferido como o do
  site (`conferirCadastro`): CPF/CNPJ com digito, telefone com DDD, OAB/RG/CNH, endereco completo (obrigatorio se a
  conta ja tinha endereco ou se a edicao mexe nele). Cidade ou UF novas trazem o codigo IBGE pela tabela da NFS-e
  (nome exato na UF; sem bater, fica vazio e o painel completa em Notas fiscais > Clientes). O aceite dos termos
  (`termos`, `quando`) continua o que a pessoa deu; a edicao fica em `cadastro.ajustado: {quando, por, campos}`.
- `campanha.disparar` - `quando`: `"agora"`, `"amanha"` e `"segunda"` (9 h de Brasilia) ou `"agendado"` com `de`
  (`AAAA-MM-DD`) e `hora` (`HH:MM`), no horario de Brasilia: fica guardada (`agendada`, com `envio_em`) e o Cron de cada
  minuto (`enviarCampanhas`) manda na hora marcada. Na fila, sem dia ou hora, ou com a hora ja passada (ou a mais de
  um ano): 400; publicada depois da hora marcada: falha ("passou antes de publicar: agende de novo"), para nao sair
  atrasada sem ninguem ver. `publico: "escolhidas"` com `contas: [id]` (ate 2.000) manda so para elas.
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

## O painel na Atos (atos.dev.br)

As rotas da propria Atos (`C:\atos\worker\admin.js` e `C:\atos\worker\oidc-painel.js`; testes em
`C:\atos\worker\teste-admin.mjs` e `teste-oauth.mjs`). Todas pedem a Conta Atos na equipe com login de ate 12 horas
(as portas acima); os POST, a origem `https://atos.dev.br`.

### Os produtos (o registro)

O painel da Atos nao tem o PAVLVS escrito em lugar nenhum fora do registro `PRODUTOS` (`C:\atos\worker\admin.js`):

    PRODUTOS = { pavlvs: { nome: "PAVLVS", binding: "PAVLVS", segredo: "PAINEL_SEGREDO_PAVLVS", origem: "https://paulus.ia.br", github: true } }

- `*    /api/admin/<id>/<rota>` (o `<id>` de um produto do registro) -> encaminhado ao Worker do produto pelo service
  binding `binding`, com o mesmo caminho e a mesma query (`<origem>/api/admin/<id>/<rota>`), assinado com o segredo
  `segredo` (`Atos-Painel-Quem` e `Atos-Painel-Assinatura`, como nas portas acima, que descrevem o do PAVLVS). Quem
  nao tem a area `<id>`: 403 `{erro: "você não atua no <nome>: peça ao dono para incluir a área"}`, sem chamar o
  produto. Sem o binding ou sem o segredo: 503 `{erro: "o <nome> não está ligado a este painel"}`; o produto nao
  respondeu: 502 `{erro: "o <nome> não respondeu"}`. A resposta volta como veio; o que cada papel pode e decidido no
  produto.
- `github: true`: so ao produto que o tem vai o token do GitHub da sessao (`Atos-Painel-Quem.github = {login,
  token}`); para os outros, `github: null` sempre. Hoje so o PAVLVS (o OAuth App "PAVLVS Admin" e do repositorio
  dele).
- Os ids que nao podem ser de produto (sao rotas do proprio painel): `eu`, `nfse`, `equipe`, `alteracoes`,
  `publicar`, `retroagir`, `github`, `oauth`, `atos` (`RESERVADOS`).
- Um produto novo = a linha no registro + o service binding em `wrangler.jsonc` da Atos + o segredo nos dois Workers
  + a tela dele (`C:\atos\public\assets\admin-<id>.js`, grupo = o nome), que declara os prefixos dos tipos que poe
  na fila (`AdminAtos.fila.tiposDo("<id>", ["conta.", ...], {tipo: [papeis]})`). A fila do produto
  (`/api/admin/<id>/alteracoes`, `/publicar`, `/retroagir`, como as do PAVLVS) aparece sozinha em Confirmar
  alteracoes, a partir do `/eu`; `admin-fila.js` nao muda. Um tipo que nenhuma tela declarou, que casa com dois
  lugares ou que e de um produto fora do painel da pessoa nao vai a fila nenhuma: a tela diz o erro.

### As areas (onde cada pessoa atua)

O papel diz o que a pessoa faz; a area, onde. As areas sao `atos` (o que e da propria Atos: as notas fiscais) e o id
de cada produto do registro (`areas_do_painel`, na ordem do menu: `[{id: "atos", nome: "Atos"}, {id: "pavlvs", nome:
"PAVLVS"}]`).

- Cada membro da equipe pode ter `areas: [id]`. O **dono atua em todas**, sempre (nao guarda lista). O membro
  **sem a lista** (os de antes dela) tambem atua em todas. Os outros, so nas da lista que existem no registro.
- Sem a area: as rotas do produto respondem 403 sem chamar o produto; `/api/admin/nfse/*` (area `atos`) tambem, com
  uma excecao: `GET /api/admin/nfse/municipios` (a tabela do IBGE) e de consulta e serve a todos, porque as telas dos
  produtos (o cadastro de uma conta do PAVLVS) usam. O suporte so faz GET nas notas.
- A equipe em si (incluir, papeis, areas) e o Login Atos sao so do dono, em qualquer area.
- A pagina mostra no menu so as secoes das areas da pessoa (`area` da secao) e so as filas dessas areas; o servidor
  confere de novo.

### Quem esta

- `GET /api/admin/eu` -> `{email, nome, papel, areas: [id], produtos: [{id, nome, github}], areas_do_painel: [{id,
  nome}], github: login | null}`. `areas`: onde a pessoa atua (acima); `produtos`: o registro, so o que a tela usa
  (o binding, o segredo e a origem nao saem do servidor); `github` (o de fora): o GitHub ligado nesta sessao.
  Anota o ultimo acesso (no maximo uma escrita por hora por pessoa).

### O GitHub

- `GET /api/admin/github/entrar?volta=<tela>` -> 302 para o GitHub (`scope: public_repo read:user`,
  `redirect_uri: https://atos.dev.br/api/admin/github/retorno`; o state no KV, 10 min). Sem o OAuth App
  (`GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` na Atos): 503. Sem sessao: 302 para `/admin/`.
- `GET /api/admin/github/retorno?code&state` -> confere que a conta tem escrita (`admin`, `write` ou `maintain`) em
  `matheusuener-atos/coryphaeus` e guarda o token **nesta sessao** (o cookie da Conta Atos deste navegador), 24 h,
  cifrado (AES-GCM com uma chave tirada do segredo do cookie, que o KV nao tem): 302 para `/admin/` (ou
  `/admin/?github=1#<tela>`, ou `/admin/?erro=frase`). O state de uma pessoa nao serve para outra.
- `POST /api/admin/github/sair` -> `{ok}`: esquece o GitHub desta sessao. Sair da Conta Atos (`POST /api/sair`)
  tambem desliga (o token so abre com o cookie).
- O token so vai ao produto com `github: true` (acima). A fila da Atos nao precisa dele.

### As notas fiscais da Atos

- `*    /api/admin/nfse/...` -> o emissor da Atos (area `atos`, salvo `GET /api/admin/nfse/municipios`; suporte so
  GET). Sem o emissor ligado: 503.

### A equipe (o painel inteiro)

A equipe vale para o painel todo da Atos (as notas, os produtos e o que vier). Mora no KV da Atos (o `CONTAS`, que e
o mesmo namespace do `APOIOS` do PAVLVS), em `atos:admin:equipe` = `[{email, nome, papel, areas?: [id], convidado?:
{criado, por, por_nome}}]`. Enquanto essa chave nao existe, vale a **semente** `ATOS_EQUIPE` (segredo da Atos, o
mesmo formato `[{email, nome, papel, areas?}]`): e por ela que o dono entra na primeira vez, e e dela que a primeira
mudanca parte (dali em diante, a semente nao conta mais). No Worker de teste da Atos (`AMBIENTE: "teste"`), as chaves
sao `atos-teste:admin:*` e a semente e a `ATOS_EQUIPE` das vars dele. Se o KV nao responde, ninguem entra (a semente
nunca vale no lugar de uma lista que existe).

- `GET /api/admin/equipe` -> `{membros: [{email, nome, papel, areas: [id], todas, ultimo, convite?: {criado, vence:
  null, por, vencido: false}}], areas_do_painel, matriz: [{acao, dono, financeiro, suporte}], liberacao: {ligado:
  true, falta: ""}}`. `areas`: onde atua de fato; `todas`: dono ou membro sem lista. `convite`: incluida e ainda sem
  entrar. A `matriz` e a da Atos (notas, equipe, Login Atos); a do PAVLVS vem de `GET /api/admin/pavlvs/papeis`.
- O convite: o dono inclui o e-mail, o nome, o papel e as areas (pela fila, abaixo); publicado, a pessoa ja esta na
  equipe e entra com a Conta Atos daquele e-mail (se nao tem, cria em atos.dev.br/entrar com o mesmo e-mail). Nao ha
  aceite nem Access. Vai um e-mail de aviso (Resend da Atos), com as areas quando nao sao todas; se ele nao sai, a
  pessoa continua incluida e a publicacao diz no `aviso`.
- `POST /api/admin/equipe/convite/:email/reenviar` (so o dono, na hora) -> o e-mail de aviso de novo ->
  `GET /api/admin/equipe`. So para quem ainda nao entrou: senao 404.

### A fila da Atos

A mesma regra do PAVLVS: mudar a equipe ou o Login Atos entra na fila da pessoa e so vale na publicacao, com a frase.

- `GET /api/admin/alteracoes` -> `{pendentes: [Alteracao], publicacoes: [Publicacao]}` (as da Atos; as de cada
  produto em `/api/admin/<id>/alteracoes`).
- `POST /api/admin/alteracoes` `{tela, tipo, alvo, dados, texto}` -> `{pendentes}` (o que da para conferir antes
  volta 400 com o porque; tipo fora da tabela: 400 "alteração desconhecida"); `DELETE /api/admin/alteracoes/:id`.
- `POST /api/admin/publicar` `{confirmacao: "comitar e pushar"}` -> `{ok, resultados, publicacao}` (sem GitHub: nada
  aqui vira commit; `commit` e `kv-xxxxx`).
- `POST /api/admin/retroagir` `{publicacao | commit, confirmacao: "retroagir"}` (so o dono): tudo ou nada; volta o
  `equipe.papel`, o `equipe.areas` (a equipe de antes era a semente -> a chave sai e a semente volta a valer) e o
  `oauth.app`/`oauth.cliente` (o registro do Login Atos de antes), se a chave nao mudou depois (senao 409: retroaja a
  mais nova antes). `equipe.membro` nao volta por aqui (409, volta pela tela). O segredo de um cliente apagado nao
  volta (o `avisos` diz: gere outro).
- KV: `atos:admin:pendentes:<email>` (50), `atos:admin:publicacoes` (30), `atos:admin:retrato:<id>` (30 dias).

| tipo | dados | papel |
| --- | --- | --- |
| `equipe.papel` | `{email, papel}` | dono |
| `equipe.membro` | `{acao: "criar", nome, email, papel, areas}`, `{acao: "editar", de, nome, email, papel, areas?}`, `{acao: "excluir", email}` ou `{acao: "cancelar_convite", email}` | dono |
| `equipe.areas` | `{email, areas: [id]}` | dono |
| `oauth.app` | `{acao: "criar" \| "editar", id, nome, descricao, site, privacidade, termos, icone?}` ou `{acao: "apagar", id}` | dono |
| `oauth.cliente` | `{acao: "criar", id, app, tipo: "publico" \| "confidencial", voltas, loopback?, origens?}`, `{acao: "editar", id, voltas, loopback?, origens?}`, `{acao: "ligar" \| "desligar" \| "apagar", id}` | dono |

`equipe.membro`: `areas` (ao menos uma, so ids do registro) e obrigatoria ao incluir quem nao e dono; ao editar, sem
`areas` ficam as de antes; o dono nao guarda lista. `editar` com outro e-mail: o novo entra (e recebe o aviso) e o
antigo sai. `cancelar_convite`: so de quem ainda nao entrou (quem ja entrou sai por `excluir`). A equipe nunca fica
sem dono. `equipe.areas` de um dono: 400 ("o dono atua em todas as áreas"). Os tipos `oauth.*`: abaixo.

### Login Atos (os aplicativos do "Entrar com Atos")

O provedor OpenID Connect da Atos (`C:\atos\worker\oidc.js`) atende os aplicativos fixos do codigo (`APPS`,
`CLIENTES`: o PAVLVS, com os clientes `pavlvs-site`, `pavlvs-app` e `pavlvs-escritorio`, todos publicos) e os
cadastrados no painel, no KV em `atos:oidc:registro` (`atos-teste:oidc:registro` no Worker de teste) =
`{apps: {<id>: {nome, descricao, site, privacidade, termos, icone, criado, por, mudado?}}, clientes: {<id>: {app,
tipo, voltas, loopback, origens, ativo, criado, por, mudado?}}}`. O fixo vale sobre o do KV com o mesmo id e nao
muda pelo painel. Tudo aqui e so do dono (os outros papeis: 403 "o Login Atos é só do dono").

- `GET /api/admin/oauth` -> `{emissor, descoberta, autorizacao, token, userinfo, jwks, revogacao, escopos: [{id,
  texto}], token_s, apps: [...], clientes: [...]}`. Cada app e cliente diz `codigo: true|false` (do codigo, so
  leitura, ou do KV); o cliente confidencial do KV traz `segredo: {quando, por} | null` (nunca o valor).
- `GET /api/admin/oauth/log` -> `{log: [{quando, por, cliente, acao: "gerou o segredo" | "trocou o segredo"}]}` (os
  ultimos 100, sem o valor; KV `atos:oidc:log`).
- `POST /api/admin/oauth/clientes/:id/segredo` `{confirmar: true}` -> `{segredo: "atos_cs_...", quando, trocado}`
  **na hora**, fora da fila (o valor aparece uma vez so e nao poderia esperar na fila): gera ou troca o segredo de um
  cliente confidencial do KV; o anterior para de valer na hora. Fica so o SHA-256 (`atos:oidc:segredo:<id>`, com
  quem e quando). Sem `confirmar: true`, cliente do codigo ou cliente publico: 400; cliente que nao existe (ou ainda
  na fila): 404.
- Criar, editar, ligar, desligar e apagar passam pela fila da Atos (`oauth.app`, `oauth.cliente`, acima), conferidos
  ao enfileirar e de novo ao publicar:
  - aplicativo: id de 2 a 31 (`[a-z0-9][a-z0-9-]`), nome, descricao (aparece para quem entra), site, privacidade e
    termos em https, icone opcional so `data:image/png|jpeg|webp;base64` de ate 30 KB (a CSP de `/entrar` e `/conta`
    nao carrega imagem de fora). Apagar o aplicativo leva os clientes dele (e os segredos, que nao voltam).
  - cliente: client_id de 3 a 63; `app` e `tipo` nao mudam depois (crie outro cliente). `voltas` (ate 10): endereco
    exato, https, ou http so em `127.0.0.1`/`[::1]`, sem `#` nem usuario; `loopback: true` aceita qualquer porta em
    127.0.0.1/[::1] (o programa instalado, RFC 8252); pelo menos uma volta ou o loopback. `origens` (ate 10, opcional):
    esquema, host e porta, para o CORS de `/oauth/token` quando a pagina troca o codigo no navegador. Desligado ou
    apagado, o cliente nao comeca login, nao troca codigo e o access_token dele deixa de valer no userinfo (o id_token
    ja emitido vale ate vencer, 1 hora).
- **Publico** (pagina ou programa): PKCE, sem segredo; mandar `client_secret` e recusado (401 `invalid_client`).
  **Confidencial** (um servidor): PKCE **e** o `client_secret`, por `client_secret_basic` (Authorization: Basic, id e
  segredo em form-urlencoded) ou `client_secret_post` (no corpo), um jeito so; sem segredo gerado, 401 ("gere um no
  painel da Atos"). **PKCE S256 e obrigatorio para todos** (`code_challenge_method` diferente: `invalid_request`).
  A descoberta (`/.well-known/openid-configuration`) anuncia `token_endpoint_auth_methods_supported: ["none",
  "client_secret_basic", "client_secret_post"]` e `code_challenge_methods_supported: ["S256"]`.

## Retroagir

- `POST /api/admin/pavlvs/retroagir` `{publicacao (o id) | commit, confirmacao: "retroagir"}` (so o dono) ->
  `{ok, commit, publicacao: Publicacao, avisos: [frase]}`. A tela manda o `commit`.
- Cada publicacao guarda, desde 07/10/2026, o retrato do que mudou (`admin:retrato:<id>`, 30 dias). Volta: o que so
  mudou o KV do painel (`plano.criar`, `plano.editar`, `planos.json`; e, nas publicacoes de antes de 11/10/2026,
  `nfse.config` e `equipe.papel`, que sairam do PAVLVS), com o valor de antes
  e o de depois - nos planos, o historico ganha a versao "Retroagi: ..." (a cobranca e da Atos: nenhuma assinatura
  muda) -; `conta.cadastro` (o cadastro de antes); `campanha.disparar` (o que ainda nao saiu e cancelado; os e-mails
  que sairam continuam, e o aviso diz). O resto mudou fora do painel (creditos, Google, tuneis, convites, a campanha
  cancelada) e e desfeito pela propria tela.
- Tudo ou nada: se um item nao volta, ou o que ele mudou mudou de novo depois (outra publicacao por cima, um plano
  criado que ja tem conta), 409 com cada um e o porque, e nada muda. Retroaja a mais nova primeiro. Os itens desfeitos
  ficam marcados: se um parar no meio, tentar de novo termina sem desfazer duas vezes.
- As publicacoes que viraram commit no GitHub (as dos materiais, antes de 07/10) voltam num commit de reversao na
  main, pela API do GitHub com o token de quem esta logado (o que a Atos manda em `Atos-Painel-Quem.github`): cada arquivo dos commits volta ao que era antes deles (o
  que eles criaram sai), numa arvore nova sobre a ponta da main (`git/trees`, `git/commits`, `PATCH git/refs/heads/main`
  sem forcar). Se um desses arquivos mudou depois na main, nao reverte (502: "retroaja pelo git").
- Sem retrato (as publicacoes de antes de 07/10/2026 que so mudaram o KV) ou com o retrato vencido: 409 dizendo que
  nao da para retroagir aquela. Ja retroagida: 409.

## Notas fiscais (emissor da nuvem)

**Fora do painel desde 11/10/2026.** A secao Notas fiscais do PAVLVS nao veio para o painel da Atos (a Atos tem as
notas dela, `C:\atos\worker\nfse`), e as rotas `/api/admin/nfse` e `/api/admin/nfse/emissor/*` deixaram de existir
(404). O emissor continua no Worker - o Durable Object `EmissorNFSe` (`worker/nfse/emissor.js`), o `atenderEmissor`
(`worker/nfse/api.js`), o Cron do PDF e a entrega ao app do cliente -, so sem rota. O que segue e o contrato do
`atenderEmissor` (com o prefixo de antes), para quando ele voltar a ter uma porta ou sair de vez. Testes:
`worker/teste-nfse-admin.mjs` (o emissor chamado direto, sem o painel), `worker/teste-nfse-emissor.mjs` (o emissor)
e `worker/teste-nfse-danfse.mjs` (o DANFSe contra o do PAULUS). A tela (`worker/tela-nfse/`) saiu.

- **Sem porta**: os papeis (GET para todos; o resto so `dono` e `financeiro`) eram do painel e sairam com ele.
- Os tres interruptores (`admin:nfse:config`, abaixo) continuam valendo como estao no KV; o `nfse.config` saiu da
  fila do painel, entao hoje so mudam a mao no KV.
- Sem o emissor (`EMISSOR_NFSE`, `NFSE_CHAVE_MESTRA` ou `APOIOS`): 503 `{erro: "o emissor de NFS-e ainda nao esta ligado: falta ..."}`
  (menos `GET municipios`, que e so a tabela).
- O `quem` de cada passo da nota e o e-mail de quem pediu (o parametro `quem` do `atenderEmissor`).
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
