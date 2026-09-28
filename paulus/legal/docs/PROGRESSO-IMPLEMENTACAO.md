# Progresso da implementação — Acesso de fora + Melhoria da IA

Contrato: `prompt-paulus-acesso-e-ia.md` (R1…R10, I1…I9), **revisado em
28/09/2026: sem Cloudflare Access** (seção "Ajuste" abaixo). Este arquivo existe
para uma conversa nova retomar de onde a anterior parou: continue da primeira
etapa que não estiver `feita`.

## Como esta rodada foi conduzida (28/09/2026)

- O usuário pediu para trabalhar a noite inteira **sem parar nas ⏸ PAUSAS**:
  fazer tudo o que não depende dele e, no fim, listar o que ficou para ele
  decidir. As pausas viraram itens da seção "Pendente do usuário" abaixo.
- O trabalho roda num **git worktree** (`C:\coryphaeus-acesso`), com uma branch
  por etapa e `merge --ff-only` no `main` ao fim de cada uma. Motivo: havia
  outra sessão do Claude commitando no `main` na mesma hora (34ccf7a, e4357e3).
- Sem `git push` e sem chamar o agente `publicar`.
- Os testes rodam com o venv do repositório principal
  (`C:\coryphaeus\paulus\legal\venv`) e `PAULUS_MODELOS` apontando para os
  modelos de lá.

### Linha de base da suíte, antes da R1

56 de 59 passam. Três já falhavam antes de qualquer mudança desta rodada:

| Teste | O que falha | Situação |
| --- | --- | --- |
| `test_gravacoes.py` | `test_ao_vivo`: resposta vazia ao enviar o áudio com sessão ao vivo | pré-existente |
| `test_inteligencia_regressao.py` | "as 0 citações entregues existem literalmente" e "cada decisão virou uma linha de medida" | pré-existente |
| `test_planilha_excel.py` | nenhum: imprime "tudo certo" no lugar de "todos os testes passaram" | falso alarme do verificador; sai com código 0 |

## Etapas

| Id | Etapa | Estado | Commit | Portão / medidas |
| --- | --- | --- | --- | --- |
| R1 | Chave da janela local | feita | branch `r1-chave-da-janela` | 363 rotas de `app.routes`, todas 403 sem chave; 23 checagens |
| R2 | Contas, senha, TOTP, sessões | feita; refeita sem Access | branch `r2-contas` + `r-ajustes-sem-access` | Turnstile antes da senha (não conta tentativa); IP fechado 1 h no 20º erro em 10 min; mesma frase e mesmo tempo (≥ 0,45 s) para conta inexistente e senha errada; cabeçalhos de segurança em toda resposta de fora; sem sessão, toda `/api/*` 401; trocar a própria senha e encerrar sessões pedem o código de novo |
| R3 | Permissões por rota | feita | branch `r3-permissoes` | 376 rotas declaradas (114 permitido, 19 propor, 9 download, 1 titular, 10 público, 223 bloqueado); tabela testada com colaborador e titular |
| R4 | Fila do modelo | feita | branch `r4-fila-do-modelo` | 2 pessoas: nunca 2 respostas juntas, sem palavra trocada, ordem de chegada; 3ª da mesma pessoa 429; parar A e B termina |
| R5 | Provisionamento no Worker | código feito sem Access; ⏸ painel | branch `r5-worker-tunel` + `r-ajustes-sem-access` | `worker/teste-tunel.mjs`: nome escolhido (regra, reservados, reserva 15 min, sugestão), fluxo com Turnstile, nenhuma chamada a `/access/`, segredo por Bearer, Turnstile do login por hostname, desfazer em cada passo, limites, remover → 410, limpeza diária |
| R6 | Túnel dentro do PAULUS | feita; refeita sem Access | branch `r6-tunel` + `r-ajustes-sem-access` | token fora da linha de comando e do log; reinício; Turnstile pelo Worker (ok / recusado / vazio / Worker fora = ninguém entra); endereço liberado → desliga, apaga, avisa; porta ocupada; versão lida do cloudflared 2026.9.3 real |
| R7 | Instalador + passo "Acesso à distância" | feita; refeita sem Access | branch `r7-assistente` + `r-ajustes-sem-access` | sugestão de endereço (8 nomes); indisponível com motivo e sugestão; interruptor desligado = nenhuma chamada ao Worker; fluxo nome → conta TOTP → iniciar → pendente → concluído → túnel; expirado mantém o nome; remover libera o nome; instalador traz o cloudflared sempre que falta; assinatura: real aceito, Python/falso recusados; `test_tela`: passo novo depois do nome do escritório |
| R8 | Auditoria "quem acessou" | feita | branch `r8-auditoria` | 9 ações de fora registradas; edição à mão acusada na linha certa; poda de 1 ano com âncora; PDF |
| R9 | Celular, energia, iniciar com o Windows | feita | branch `r9-celular` | 4 telas em 390 px pelo caminho de fora (sem rolagem lateral, 44 px de toque); 9/9 respostas em streaming com os cabeçalhos; energia e Run testados |
| R10 | Política, documentação, roteiro do teste real | textos refeitos sem Access; ⏸ teste no 4G | branch `r10-politica` (docs) e `r10-politica-site` (site, fora do main) | política e termos: Turnstile só passa pelo site; anti-robô + senha + TOTP para todas as contas; `docs/acesso-de-fora.md` com ligar, contas da equipe e 9 problemas; roteiro de 10 passos abaixo |
| I1 | Ajustes de inferência | feita | branch `i1-inferencia` | roteiro `--tudo` 40/41 antes e depois (a mesma de ausência falha nas duas); p50 documentos 8,5 s → 8,9 s; entrada p50 2.366 tokens; 0 cortes; mesma pergunta 2× = mesma resposta |
| I2 | Medição com documentos reais | ferramenta feita; ⏸ conjunto real | branch `i2-medicao` | demo (27 perguntas, 9 de continuação): 25/27 · p50 6,6 s · p95 39,3 s · entrada p50 2.362 · R@20 0,96 · R@6 0,96 · MRR@6 0,86 · no contexto 0,90 |
| I3 | Nível 0 por molde | feita | branch `i3-molde` | 5 factuais sem modelo, mediana 5 ms, sem fila; dígito trocado rejeitado; roteiro 40/41; demo 25/27, p50 6,2 s, p95 17,2 s |
| I4 | Memória da conversa | feita | branch `i4-memoria` | 9/9 continuações herdam o sujeito, 18/18 outras intactas; histórico ≤ 600 tokens; demo 26/27 (continuação 9/9, era 8/9); roteiro 40/41 |
| I5 | Chunking estrutural | feita | branch `i5-trechos` | ids estáveis (mesmo doc e reindexação); toda página; nenhuma seção cortada; roteiro 40/41 (mediana 8,8 s); demo 26/27, p50 9,2 s, R@6 0,95; suíte 71 ok |
| I6 | FTS5 com normalização jurídica | feita | branch `i6-fts` | 4 exemplos iguais nos dois lados; mesma ordem; incremental; linha de base só-léxico R@20 0,96 · R@6 0,95 · MRR@6 0,87; roteiro 40/41; demo 26/27, p50 7,9 s; suíte 71 ok |
| I7 | Denso + RRF + reranker, virada do "ler tudo" | feita; virada ⏸ desligada | branch `i7-hibrida` | demo: R@20 léxico 1,00 · denso 1,00 · híbrido 1,00 (satura); R@6 0,99; MRR@6 0,93; contexto p50 718 tokens; reranker 34 s/20 pares (não entra); roteiro 40/41; demo 26/27, p50 7,8 s; suíte 73 ok |
| I8 | Contrato de resposta `[Tn]` | feita; chave ⏸ desligada | branch `i8-citacao` | 3 tentativas: modelo marcando 38/41 (2×); marcas em código 40/41; demo 26/27; 0 "não encontrei" indevido; 0 citação inventada; 5 "sem fonte"/27 |
| I9 | A IA ajuda sem ser perguntada | feita | branch `i9-ajuda` | cartão só com conferidos; correção manual + linha no conjunto; sugestões sem modelo; prazo → Aprovações; roteiro 40/41; demo 26/27; suíte 75 ok |

## Ajuste: sem Cloudflare Access (contrato revisado, 28/09/2026)

O contrato foi revisado depois das etapas R1–R10 prontas: **nenhum
Cloudflare Access, para conta nenhuma** (decisão de produto; não
reintroduzir). Refeito na branch `r-ajustes-sem-access`:

- **Login** = Turnstile → e-mail + senha → TOTP, igual para titular e
  colaborador. O Turnstile é conferido antes da senha, no Worker, com o
  segredo da instalação (`POST /api/tunel/turnstile`); falha dele não conta
  tentativa; Worker fora do ar = ninguém entra (503).
- **Bloqueio por endereço**: 20 falhas do mesmo `Cf-Connecting-IP` em 10 min
  fecham o endereço por 1 h (só de fora; tabela `tentativas_ip`), além das
  5 por conta.
- **Mesma resposta, mesmo tempo** para conta que não existe e senha errada
  (piso de 0,45 s no login; o scrypt roda igual).
- **Cabeçalhos de segurança** em toda resposta de fora (inclusive 401/403):
  CSP com o sha256 dos scripts embutidos (`index.html`, `entrar.html`) e
  `https://challenges.cloudflare.com`, sem `unsafe-inline` para script;
  `X-Frame-Options: DENY`; `Referrer-Policy: no-referrer`; `nosniff`;
  `Permissions-Policy` fechada; COOP; HSTS.
- **Sem sessão**, de fora só passam a tela de entrar e o que ela carrega
  (`politicas.SEM_SESSAO`); toda outra `/api/*` → 401 `X-PAULUS-Sessao:
  acabou`; toda outra página → a tela de entrar.
- **Ações sensíveis do titular de fora** pedem o código do autenticador de
  novo: aprovar o que sai (já era), trocar a própria senha
  (`POST /api/acesso/minha-senha`) e encerrar as sessões
  (`POST /api/acesso/minhas-sessoes/encerrar`), pelo botão "Minha conta" na
  barra de quem está de fora.
- **Worker**: o titular escolhe o nome (a-z0-9-, 3–24, lista de reservados);
  `GET /api/tunel/disponivel` com motivo e sugestão; `/conectar` com
  Turnstile; KV `escritorio:<slug>`; entrega única com `turnstile_sitekey` e
  `segredo_instalacao`; rotas com Bearer (turnstile, porta, situação,
  remover); limpeza diária por Cron (nunca conectou em 7 dias, parado há
  mais de 180); removido responde 410 e o PAULUS diz "o endereço foi
  liberado por falta de uso; conecte de novo".
- **App**: o passo "Acesso à distância" no assistente de configuração, logo
  depois do nome do escritório (o passo Escritório ganhou o campo do nome);
  o mesmo bloco em Configurações › Acesso de fora (endereço com conferência
  a 400 ms, conta do titular com QR/código/recuperação, confirmar no
  navegador com o código, tentar de novo com o mesmo nome, concluído com
  "Abrir o PAULUS com o Windows").
- **Instalador**: o `cloudflared` vem sempre que falta, sem caixa de marcar;
  saiu o "Configurar o acesso de fora agora" da tela final.
- **Saíram**: `src/acesso/jwt_access.py`, o conferidor do JWT, a lista de
  e-mails do Access (`/api/tunel/emails`, sincronizar), `aud`/`team_domain`
  nas preferências, os segredos `ACCESS_TEAM_DOMAIN`/`ACCESS_AUD_CONECTAR`.

Achados que valem para o painel:

- O widget do Turnstile com o hostname `paulus.ia.br` vale para todos os
  subdomínios (`*.paulus.ia.br`): um widget só serve todos os escritórios. O
  plano gratuito permite 10 hostnames por widget — não é limite aqui.
- O token do Turnstile vale 5 minutos e uma vez; o Worker confere também que
  o `hostname` que a Cloudflare devolve é o do escritório daquele segredo
  (token tirado na página de outro escritório não serve).
- Sem Access, nenhum assento do Zero Trust é gasto por escritório: o limite
  passa a ser só `MAX_ESCRITORIOS` (sugestão: começar com 20).

## Decisões tomadas

(uma linha por decisão, com a etapa)

- **R1** `/entrar-local` é tratado pelo porteiro e não é rota do app: assim é a única coisa alcançável sem chave, e o teste "todas as rotas de `app.routes` dão 403" continua sem exceção.
- **R1** O endereço com a chave vale uma vez por execução; o cabeçalho `X-PAULUS-Chave` vale sempre (clientes sem janela). Endereço vaza em histórico; cabeçalho não.
- **R1** O retorno OAuth (Google/Microsoft) não precisou de exceção: cai no servidor temporário de `correio_oauth.py`.
- **R1** Rota inexistente também dá 403 para quem é de fora (e não 404): nada se descobre por tentativa.
- **R2** O QR sai do reportlab (`reportlab.graphics.barcode.qr`), que já é dependência: nenhuma dependência nova.
- ~~**R2** O e-mail do JWT do Access tem de ser o e-mail da conta do PAULUS, no login e em cada pedido. A lista do Access é montada a partir das contas (R7), então os dois coincidem por construção; se divergirem, nenhum vale.~~ *(substituída pelo ajuste sem Access)*
- **R2** O código do autenticador vale uma vez só (o último passo usado fica gravado), inclusive dentro da janela de folga.
- **R2** O bloqueio conta por e-mail digitado, com ou sem conta, e o scrypt roda igual quando a conta não existe: sem oráculo de "este e-mail tem conta".
- **R2** Sessões ficam no SQLite (`data/acesso/contas.db`), só o hash: reiniciar o PAULUS não derruba quem está de fora.
- **R2** Rotas do acesso registradas direto no `app` (não `include_router`): esta versão do FastAPI embrulha o roteador incluído e as rotas somem de `app.routes`.
- ~~**R2** Cookie `SameSite=Strict` não vai na navegação que volta do login do Cloudflare Access (outro site). A tela de entrar pergunta `/api/acesso/eu` e segue para o app se a sessão existir.~~ *(substituída pelo ajuste sem Access)*
- **R3** Registro central (`src/acesso/politicas.py`) em vez de decorador nas 10 mil linhas do `api.py`: a tabela inteira cabe numa leitura; o teste falha se uma rota de `app.routes` não estiver nela.
- **R3** Política nova `propor` para "Agenda, tarefas, cadastros: ver e propor (tudo via fila)": o pedido de fora não grava; o porteiro guarda método, caminho e corpo num item da fila (`acesso.proposta`), responde 202, e o sim refaz o pedido pela janela local (conferindo de novo que a rota é das que se propõem). O `POST /api/trabalhos/{id}/fazer` (gravar o que a conversa entendeu: compromisso, tarefa, ficha) também é `propor`.
- **R3** Aprovar de fora: o titular não aprova de fora o que a tabela proíbe fazer de fora (`organizar.mover`, `acervo.apagar`, `acervo.exportar`, `assinatura.*`); `correio.enviar`, `google.drive.enviar` e proposta com sala do Meet pedem o código do autenticador de novo (vale para todos os itens daquela decisão).
- **R3** E-mail de fora vai sempre para a fila, mesmo com "enviar sem confirmar" ligado; senha de e-mail vinda de fora é 403.
- **R3** `GET /api/preferencias` é permitido de fora (a tela lê o nome e o tema); gravar preferências é bloqueado.
- **R3** A documentação automática do FastAPI (`/openapi.json`, `/api/docs`, `/redoc`) é bloqueada de fora: é o mapa da API.
- **R3** O 401 do porteiro vem com `X-PAULUS-Sessao: acabou`; só ele manda a tela de volta ao login (outras rotas usam 401 para "falta a senha do e-mail").
- **R4** A fila vale para a conversa do Assistente (`/api/trabalhos/{id}/perguntar`) e para a conversa de um Serviço (`/api/servicos/{id}/conversar`). Outras chamadas ao modelo (editor, e-mail, resumo) não entram: não são conversa, e o contrato fala da fila "para as chamadas de conversa".
- **R4** A vez é pega dentro do gerador da resposta, não na rota: se a página fechar antes de o streaming começar, nada fica preso. A 3ª pergunta é recusada na rota (429) antes de gravar a pergunta no histórico.
- **R4** Previsão = posição × mediana de (leitura + escrita) do `ritmo.json`, descontado o que a resposta em andamento já andou. Sem medida, só a posição.
- **R4** `ceder()` existe para o segundo plano; hoje a ingestão (camada de inteligência) só roda extratores de regra, sem modelo, então quem vai usar é o backfill de vetores da I7.
- **R5** Caminhos da API da Cloudflare usados (conferidos na documentação em 28/09/2026): `POST /accounts/{a}/cfd_tunnel` `{name, config_src:"cloudflare"}`; `PUT .../cfd_tunnel/{t}/configurations` `{config:{ingress:[{hostname, service, originRequest}, {service:"http_status:404"}]}}`; `GET .../cfd_tunnel/{t}/token` (result é a string); `GET .../cfd_tunnel/{t}` (`status`: inactive/degraded/healthy/down); `DELETE .../cfd_tunnel/{t}/connections` e depois `DELETE .../cfd_tunnel/{t}`; `POST /zones/{z}/dns_records` `{type:"CNAME", name, content:"<t>.cfargotunnel.com", proxied:true, ttl:1}`; `POST /accounts/{a}/access/policies` `{name, decision:"allow", include:[{email:{email}}]}` e `PUT` com o corpo inteiro; `POST /accounts/{a}/access/apps` `{name, domain, type:"self_hosted", session_duration:"12h", policies:[{id, precedence:1}]}` (devolve `aud`).
- ~~**R5** JWT do Access: `Cf-Access-Jwt-Assertion`; chaves em `https://<time>.cloudflareaccess.com/cdn-cgi/access/certs` (escolhidas pelo `kid`; giram a cada 6 semanas); `aud` vem como lista; `iss` = `https://<time>.cloudflareaccess.com`.~~ *(substituída pelo ajuste sem Access)*
- ~~**R5** Limites do plano gratuito do Zero Trust (página account-limits, 28/09/2026): 500 aplicações Access, 1.000 regras por aplicação, 1.000 e-mails por regra, 1.000 túneis por conta. **Assentos: 50 usuários** (fonte secundária — a página de preços é montada por JS; conferir no painel). Passado o limite de assentos, logins novos são bloqueados. Esse limite é da conta do Atos, compartilhado por todos os escritórios: com até 10 e-mails por escritório, são ~5 escritórios cheios. `MAX_ESCRITORIOS` controla isso.~~ *(substituída pelo ajuste sem Access)*
- ~~**R5** Segredo a mais além dos do contrato: `ACCESS_AUD_CONECTAR` (o AUD da aplicação do Access que protege `/conectar`), sem o qual o Worker não confere o JWT daquela página.~~ *(substituída pelo ajuste sem Access)*
- **R5** O KV `ESCRITORIOS` ficou **comentado** no `wrangler.jsonc`: declarar com id que não existe quebraria o deploy do site no próximo push. `/conectar` entrou no `run_worker_first`.
- **R5** O pedido "pronto" guarda no KV o token do túnel e o segredo até o PAULUS buscar (no máximo 15 min, TTL do KV); depois da entrega é apagado.
- **R6** **Desvio do contrato, de propósito:** a porta fixa não é a porta da janela. É um segundo ouvinte uvicorn (mesmo app, `lifespan="off"`, também só em 127.0.0.1) aberto quando o acesso está ligado. Motivos: a conexão feita pelo assistente vale na hora, sem reiniciar o PAULUS para ele passar a escutar na porta nova; e a janela local nunca depende da porta fixa (o contrato já pedia que a janela abrisse "em outra porta como hoje" quando a fixa estivesse ocupada). Com a porta fixa ocupada, o túnel não liga.
- **R6** Versão mínima do `cloudflared`: 2025.4.0 (preferência `acesso_remoto.cloudflared_minimo`), a partir da qual o túnel gerenciado remotamente aceita o token por `TUNNEL_TOKEN`/`TUNNEL_TOKEN_FILE`.
- ~~**R6** O conferidor do JWT só existe com `aud` e `team_domain` gravados (vêm do Worker na conexão). Sem eles, nenhuma requisição de fora passa — mesmo com o módulo ligado.~~ *(substituída pelo ajuste sem Access)*
- **R7** Versão fixa do `cloudflared` no instalador: `VERSAO_CLOUDFLARED = "2026.9.3"` em `Instalador.cs` (quem publica atualiza a mão). A conferência de assinatura pode ser rodada sozinha: `PAULUS-instalador.exe /conferir-assinatura=<arquivo>` → código 0 se é da Cloudflare, 3 se não.
- **R7** A revogação do certificado não é consultada (`WTD_REVOKE_NONE`): pede rede e trava instalação offline; a cadeia até a raiz confiável continua conferida pelo Windows.
- ~~**R7** O e-mail do titular no assistente é escolhido entre as contas de titular com autenticador confirmado — sem ela, o assistente leva até Contas em vez de conectar.~~ *(substituída pelo ajuste sem Access)*
- ~~**R7** A lista de e-mails do Access é a de todas as contas do PAULUS (até 10), sincronizada a cada criar/mudar/remover conta. Falha de rede na sincronização vira aviso na tela, não erro.~~ *(substituída pelo ajuste sem Access)*
- **R7** Remover também encerra todas as sessões de fora.
- **Ajuste** O nome do escritório entra no passo Escritório do assistente (só no caminho "criar"): o assistente não tinha esse campo, e o contrato põe o passo novo "logo depois do passo em que o escritório recebe o nome". Quem entra num escritório existente não vê o passo (o acesso é do responsável).
- **Ajuste** O bloco de ligar é um só (`js/43-acesso-tunel.js`, `blocoConexao`), usado pelo assistente e por Configurações: o contrato pede que "ligar pela primeira vez refaça o mesmo passo".
- **Ajuste** Com o interruptor desligado, o passo não chama nada: a sugestão do endereço é local (`/api/acesso/tunel/sugestao`), e a disponibilidade só é perguntada ao Worker com o interruptor ligado.
- **Ajuste** `onclick` embutido saiu do HTML gerado (o "Tentar de novo" do assistente de conversa): a CSP de fora não roda script embutido sem hash.
- **Ajuste** `/sem-acesso-de-fora` continua existindo no instalador silencioso, só para os testes que não baixam da internet; a tela não tem essa escolha.
- ~~**R7** `--configurar-acesso` vira `#acesso` no endereço da janela, e a tela abre em Configurações › Acesso de fora.~~ *(substituída pelo ajuste sem Access)*
- **R8** "Documento aberto" = ver o documento do editor, a página de um arquivo do Acervo e o trecho citado (`ROTAS_DE_VER_DOCUMENTO` em `politicas.py`); a mesma pessoa no mesmo documento vira uma linha a cada 10 min.
- **R8** O alvo é gravado pelo nome (documento, planilha, gravação, conversa, arquivo), resolvido na hora de anotar; o que não se traduz fica com o endereço.
- **R8** Retenção: a poda roda ao abrir o programa; o hash da última linha podada fica em `acessos.ancora`.
- **R9** Celular: as regras entram abaixo de 600 px (a janela do programa tem mínimo de 900). O trilho vira barra inferior rolável, sem o menu flutuante (que abre ao passar o mouse). Não refiz as telas uma a uma para o desenho M1–M16 de `docs/ui/04-telas-mobile.md`: as quatro telas do contrato ficaram usáveis; as outras seguem as regras gerais (tabela vira lista, cabeçalho quebra).
- **R9** O aviso de 403 ("Disponível só no computador do escritório") só aparece para pedidos que alteram algo; leituras de fundo que dão 403 ficam caladas.
- **R9** "Abrir o PAULUS com o Windows" só existe no programa instalado (o `PAULUS.exe` fica duas pastas acima de `app/src`); no código-fonte a opção aparece travada, com a frase.
- **Suíte** O worktree precisa dos exemplos de `data/test_contracts` (não versionados), copiados do repositório principal. `test_tela.py` sai às vezes com segfault (código 139) — acontece também no repositório principal, sem as mudanças desta rodada. A checagem "segurar numa conversa marca" é intermitente: medida em 3 rodadas seguidas na árvore desta rodada, falhou 1 e passou 2 (a lista de conversas abre animada em 460 ms e pode se redesenhar enquanto o teste segura a linha). `test_gravacoes.py` falha quando a máquina tem menos de ~1,9 GB livres para o modelo de voz — é a causa da falha da linha de base.
- **I1** A janela fixa de fábrica é 16384 (perfil `conversa` em `config/extratores.yaml`), como pede o contrato; `janela_para` saiu. A chave `ia.opcoes_fixas` desligada volta à temperatura 0,1 sem semente/teto/keep_alive — mas não traz de volta a janela que crescia com o acervo (ela era a causa das recargas).
- **I1** O teto de 700 tokens vale só para a pergunta sobre documentos (a habilidade `perguntar` manda `tarefa="conversa"`); editor, resumos e e-mail escrevem sem teto. JSON (ferramentas, folha) tem 800.
- **I1** A linha de base do roteiro nesta rodada foi 40/41, e não 41/41: a pergunta de ausência da multa do aluguel falhou com as opções antigas também. A régua é "não cair" em relação a 40/41.
- **I1** `perguntas.jsonl` guarda também a resposta pelo programa (`caminho: programa`) e a recusa por regra (`regra`); a pergunta parada no meio não entra (como no ritmo: leitura cortada não é medida).
- **I1** Um dicionário vazio no `PADRAO` passou a ser mapa livre em `_fundir` (senão `janela_por_modelo` perdia as chaves ao reabrir).
- **I2** Sem resposta à ⏸ PAUSA I2 (o usuário estava dormindo), segui como o contrato manda para "segue com a demo": o conjunto da demonstração com as perguntas de continuação. **Limitação:** todos os números das etapas I3–I9 abaixo são da demonstração (8 documentos, 9 trechos, cabe inteira na leitura) — a busca quase não é exercitada, e o Recall é teto.
- **I2** `tools/medir.py` não mudou nada do programa (só ferramenta, conjunto e documentação): não rodei o roteiro nem a suíte inteira de novo nesta etapa; `tests/test_i2_medir.py` confere as contas e que toda frase esperada existe na demo.
- **I2** "No contexto" mede nas fontes que a conversa mostrou; resposta sem fontes (a recusa por regra, 0 s) conta zero — por isso 0,90 e não 0,96.
- **I3** Molde só para o que o contrato lista (processo, valor, tribunal, partes, assinatura, leis). CPF/CNPJ e prazos seguem pelo modelo com a conferência mecânica. Tribunal: o molde responde só "qual o tribunal/juízo?"; vara, comarca e foro (o foro de eleição de um contrato) vão ao modelo.
- **I3** `ia.molde` desliga as duas coisas (molde e conferência). A pergunta que sai sem modelo não entra na fila: a conversa pergunta à habilidade (`sem_modelo`) antes de pegar a vez.
- **I3** A suíte teve o `test_tela` falhando uma vez em "segurar numa conversa marca" (intermitente, já visto antes da I3); rodado de novo isolado.
- **I4** A reescrita é por regra, nunca pelo modelo (custaria uma leitura a mais por pergunta). Quando a regra não reconhece a continuação, a pergunta segue como foi escrita — o histórico ainda vai junto.
- **I4** O nível 0 (fatos) não leva histórico: ele responde de fatos, e a conversa de antes só aumentaria o prompt.
- **I5** A versão do `chunk_id` é o sha1 do arquivo + o nome, e não o `version_id` da biblioteca (um ULID sorteado no registro): com o ULID, reindexar do zero mudaria todos os ids. Cópias iguais com nomes diferentes ganham ids próprios.
- **I5** Documento sem página (DOCX, TXT) fica com página vazia — o mesmo que o mapa de layout diz; inventar "p. 1" num .txt seria prometer uma página que ninguém acha. "Todo trecho tem página" vale para os documentos paginados.
- **I5** O material de consulta continua fatiado por página (src/material.py): é por página que ele cita, e ele está 5/5 no roteiro. O regime A vale para lei que estiver no Acervo.
- **I5** Três trechos inspecionados (dos 20 de cada regime impressos por `tests/test_i5_trechos.py --mostrar`):
  - B, cláusula longa em janelas: `[chunk_… p.2-3] Contrato ACME > CLÁUSULA 7ª - DA OBRIGAÇÃO NÚMERO 7 / no mês 57, com a assinatura do responsável. Item 58 da cláusula sétima…` — a janela continua dentro da cláusula 7 e atravessa a quebra de página.
  - B, cláusulas curtas juntas: `[chunk_… p.1-1] Contrato ACME > CLÁUSULA 2ª … + CLÁUSULA 3ª …` — duas inteiras, nenhuma cortada.
  - A, artigo com parágrafo e incisos: `[chunk_… ] Lei 99999 > Art. 3º / Art. 3º O teste número 3… § 1º O parágrafo do artigo 3… I - inciso primeiro…`.
- **I6** O FTS5 só é usado com trechos estruturais (precisa do `chunk_id`); com `ia.trechos_estruturais` desligada, volta o rank_bm25. A consulta vai em OU (cada termo entre aspas): em E, uma palavra a mais na pergunta zerava o resultado.
- **I7** Reranker fora do v0: 34 s para 20 pares em CPU (régua 3 s). Fica só a RRF.
- **I7** Vetores em BLOB + numpy, e não `sqlite-vec`: a extensão não está instalada no ambiente, e instalar seria dependência nova sem necessidade para o tamanho de um acervo de escritório.
- **I7** O backfill é um fio próprio (`denso.Backfill`), e não o `jobs.py`: aqui o `jobs.py` é o das conversas, não um executor de tarefas. Ele cede a vez à fila do modelo antes de cada lote.
- **I7** A virada ficou **desligada** mesmo com R@6 ≥ 0,80 na demo: a demonstração cabe inteira em ~4000 tokens e não passa pela virada; o contrato pede Recall@6 no conjunto, e o conjunto real ainda não existe. Ligar é uma linha (`ia.leitura = "trechos"`), depois de medir no conjunto real.
- **I7** O `bge-m3` foi baixado no Ollama desta máquina para medir (1,2 GB). No programa instalado ele só chega pelo botão da tela.
- **I8** O portão passa com `ia.citacao = "codigo"` (marcas postas em código); com `"modelo"` (o modelo marca) o banco de provas cai de 40/41 para 38/41 com o 3B. De fábrica a chave está desligada: o rótulo "sem fonte" e o cartão de sem fundamento mudam toda resposta — decisão do dono.
- **I8** Medições de acerto só valem sozinhas na máquina: dois roteiros ao mesmo tempo no Ollama mudaram respostas (a "garantia" falhou em todas as rodadas paralelas e passou nas sozinhas).
- **I9** A lista de pedidos (e as outras coleções) do nível 0 passou a sair por molde, sem modelo: é o que o modelo já fazia ("listar exatamente os itens"), e as perguntas sugeridas precisam responder na hora.
- **I9** O prazo do documento vira **tarefa** com prazo (e não compromisso) ao ser aprovado: vencimento não tem hora nem lugar.

## Pendente do usuário

(o que depende de painel, conta, teste no celular ou decisão de produto)

### ⏸ I2 — o conjunto real de perguntas

De 30 a 50 perguntas sobre 10 a 20 documentos do escritório, em
`data/medicao/conjunto-real.jsonl` (na pasta de dados; fora do git). Como
anotar, com exemplo: `docs/medicao.md` e `tools/demo/conjunto-demo.jsonl`.
Depois: `tools\medir.py --real --so-busca` (confere as frases, segundos) e
`tools\medir.py --real` (com o Ollama). Os números das etapas I3–I9 foram
medidos na demonstração até lá.

### ⏸ I7 — ligar a leitura por trechos?

Pronta e atrás de `ia.leitura = "trechos"` (janela cai para 8192). Não
liguei: a demonstração não exercita a virada. Com o conjunto real anotado
(I2), rodar `tools\medir.py --real` com o `bge-m3` baixado: se o Recall@6
ficar ≥ 0,80 e a latência cair, ligar.

### ⏸ I8 — ligar as marcas de fonte `[Tn]`?

`ia.citacao = "codigo"` passou no portão (40/41, 0 citação inventada, 0
"não encontrei" indevido). Ligado, toda resposta sobre documentos mostra o
número do trecho em cada frase (clicável), "sem fonte" onde não há trecho, e
o cartão de sem fundamento quando nada se sustenta. Diga se quer de fábrica.

### ⏸ R5 — o que fazer no painel da Cloudflare (só o dono da conta)

O código do Worker já está no repositório e **não liga nada** até o passo 6.
Nada de Zero Trust nem de Access.

1. **Token de API.** Painel → My Profile → API Tokens → Create Token → Custom token. Só duas permissões:
   - Account → **Cloudflare Tunnel** → Edit
   - Zone → **DNS** → Edit, com *Zone Resources* = Include → Specific zone → `paulus.ia.br`

   Guarde o token (aparece uma vez).
2. **Account ID e Zone ID.** Painel → `paulus.ia.br` → Overview: na coluna da direita, "Account ID" e "Zone ID".
3. **O widget do Turnstile.** Painel → Turnstile → Add widget: nome "PAULUS", hostname **`paulus.ia.br`** (vale para todos os `*.paulus.ia.br`), modo **Managed**. Copie a **Site Key** (pública) e o **Secret Key**.
   - No `wrangler.jsonc`, acrescente `"vars": { "TURNSTILE_SITEKEY": "<site key>" }` (o comentário no fim do arquivo mostra onde).
4. **O KV `ESCRITORIOS`.** Painel → Storage & Databases → Workers KV → Create → nome `ESCRITORIOS`. Copie o **ID** e, no `wrangler.jsonc`, descomente a linha `{ "binding": "ESCRITORIOS", "id": "..." }` colando o id.
5. *(Opcional)* **Uma regra de WAF** para `paulus.ia.br/conectar` e `/api/tunel/*` (Security → WAF → Rate limiting rules), além do limite que o Worker já tem (10 por minuto por endereço). Não é necessário para funcionar.
6. **Os segredos do Worker**, na pasta do repositório:

   ```text
   npx wrangler secret put CF_API_TOKEN          (o token do passo 1)
   npx wrangler secret put CF_ACCOUNT_ID         (passo 2)
   npx wrangler secret put CF_ZONE_ID            (passo 2)
   npx wrangler secret put TURNSTILE_SECRET      (o Secret Key do passo 3)
   npx wrangler secret put MAX_ESCRITORIOS       (sugestão: 20)
   npx wrangler secret put TUNEL_ATIVO           (1 — é o que liga as rotas)
   ```

7. **Push** do `main` (publica o Worker com o KV, a sitekey e o Cron da limpeza diária, às 06:17 UTC). Conferir: `https://paulus.ia.br/api/tunel/disponivel?nome=teste-do-dono` deve responder `{"disponivel":true,...}` (antes do passo 6, 404); `https://paulus.ia.br/conectar` mostra a página com o código a digitar.
8. No painel, conferir que **nenhuma rota do Worker pega `*.paulus.ia.br`** (Workers & Pages → paulus → Settings → Domains & Routes: só `paulus.ia.br` e, se houver, `www`), e que o Cron aparece em Settings → Trigger Events.

### ⏸ R10 — o teste real, do celular em 4G (depois da pausa da R5)

Pré-requisitos: os passos da R5 feitos (token, Turnstile, KV, segredos, `TUNEL_ATIVO`, push); o celular **fora do Wi-Fi do escritório**, no 4G.

1. **Instalar numa pasta de teste e ligar pelo assistente.** Instale o PAULUS desta versão numa pasta de teste (o instalador mostra que o cloudflared vem junto). Na primeira abertura, no passo **Escritório**, dê o nome do escritório; no passo seguinte, **Acesso à distância**, ligue o interruptor. **Esperado:** o endereço sugerido a partir do nome, com ✓ disponível; mude uma letra e veja ✓/✗ mudar. Crie a conta do titular (QR no autenticador, código, códigos de recuperação), clique em **Conectar**, confira o código `XXXX-XXXX` no navegador, passe pelo Turnstile e confirme. **Esperado:** em até ~10 s, o endereço `https://<nome>.paulus.ia.br` com Copiar e "Abrir o PAULUS com o Windows".
2. **Titular entra de fora.** Abra o endereço no celular (4G). **Esperado:** direto a tela "Entrar no PAULUS do escritório", com a verificação contra robôs (nenhuma página da Cloudflare pedindo e-mail). Verificação, e-mail, senha, código do autenticador. **Esperado:** a tela inicial, com "De fora como <nome>", **Minha conta** e **Sair** no alto, e a barra de destinos embaixo.
3. **Criar um colaborador e entrar com ele.** No computador: Configurações › Acesso de fora › Contas › **Nova conta** (colaborador), com o autenticador de outro celular (ou outro app). No celular, **Sair** e entrar com a conta nova. **Esperado:** entra; "Minha conta" não aparece para o colaborador.
4. **Colaborador tenta Configurações.** **Esperado:** a tela "Disponível só no computador do escritório".
5. **Perguntar sobre um documento.** **Esperado:** "lendo…" e depois a resposta **aparecendo palavra a palavra**, não de uma vez. Se vier de uma vez só no fim, anote: é buffer no caminho.
6. **Tentar assinar:** abra Assinatura no menu. **Esperado:** "Disponível só no computador do escritório". Tente também apagar um documento do Acervo: o aviso com a mesma frase.
7. **Baixar um documento** (Documentos › abra um › PDF ou DOCX). **Esperado:** o arquivo baixa. No computador: Configurações › Acesso de fora › Quem acessou — a linha "baixou “<nome>” (PDF)" com o e-mail do colaborador, a hora e o IP do celular; e "registro íntegro".
8. **Colaborador erra a senha 5 vezes** (com a verificação contra robôs em cada uma). **Esperado:** na 5ª, "muitas tentativas erradas: a conta ficou bloqueada por 15 minutos"; no computador, o aviso do Windows dizendo de quem; em Quem acessou, as linhas de login falho e o bloqueio.
9. **Desligar** no computador (Acesso de fora › Endereço › *Desligar*). **Esperado:** no celular, a próxima ação falha e, recarregando, a Cloudflare mostra erro de túnel (o endereço para de responder).
10. **Remover** (Acesso de fora › *Remover o acesso de fora*). **Esperado:** "acesso de fora removido"; recarregando no celular, o endereço não existe mais; no painel da Cloudflare, o túnel e o DNS sumiram. De volta ao passo de ligar, o **mesmo nome aparece disponível de novo**.

Para cada passo que não sair como o esperado: o número do passo, o que apareceu (print do celular ajuda) e as últimas linhas de `%LOCALAPPDATA%\PAULUS\dados\logs\tunel.log` do computador. Cada correção volta com teste.

### R3 — rotas bloqueadas de fora por não se encaixarem com clareza na tabela

Estão em `BLOQUEADO`, no último grupo de `src/acesso/politicas.py`. Para
liberar alguma, basta mudar a linha dela de grupo (e o teste da R3 continua
exigindo que toda rota tenha política):

- **Financeiro inteiro** (`/api/financeiro/*`, 26 rotas): dinheiro não está na tabela; ver o extrato de fora pode ser útil, mas é decisão de produto.
- **Relatórios** (`/api/relatorios*`): somam financeiro e aprovações.
- **Foco e bem-estar** (`/api/bemestar*`): é da pessoa na frente do computador.
- **Serviços — gravar** (criar, etapas, anotações, vincular, prazos): ver e conversar sobre o serviço estão liberados.
- **Gravações — gravar e transcrever** (inclui gravar ao vivo pelo microfone do celular): ver a lista e ouvir/baixar estão liberados (download registrado).
- **Enviar arquivo** (`POST /api/upload`) e **trazer para o editor** (`POST /api/documentos/importar`, que aceita caminho do disco): o segundo, liberado, leria qualquer arquivo do computador pelo caminho.
- **Guardar documento do editor no Acervo** (`POST /api/documentos/{id}/biblioteca`) e **guardar anexo de e-mail no Acervo** (`POST /api/email/anexo/guardar`): gravam arquivo no disco.
- **Apoiar** (`/api/apoio/*`): pagamento.
