# Plano — Área do cliente (Escritório Plus)

Pedido do dono em 04/10/2026: o advogado manda **um link do paulus.ia.br** e o
cliente acompanha a pasta do serviço — resumo, andamento, datas, documentos —,
conversa com o escritório, manda arquivos e confirma horários. Tudo o que o
cliente faz fica registrado. Inspiração: o **Asana**, em que o cliente entra
como convidado num projeto.

O recurso já existe na tabela dos planos: `pagina_cliente` (só no Escritório
Plus — `src/recursos_do_plano.py`, `worker/ia.js`).

## Decisões do dono (04/10/2026)

- **Um link por cliente.** Com uma pasta compartilhada, o link abre nela; com
  mais de uma, mostra a lista.
- **Somente o servidor.** Os dados não saem do escritório: o cliente vê ao vivo
  pelo túnel do acesso de fora. Servidor desligado = "o escritório está fora do
  ar agora, tente mais tarde". Não há cópia na nuvem.
- **E-mail pelo PAVLVS:** sai do Worker (Resend, o mesmo do painel admin) como
  **"Escritório Tal (via PAVLVS)"**, assunto "Dra. Fulana te mandou uma
  mensagem" ou "Seu código de acesso".
- **A atividade do cliente** só os **responsáveis pela pasta** (a Equipe do
  serviço) e o titular veem.
- **Simples para os dois lados.** Nada de trilha separada nem de regra por item
  para o advogado aprender: o que o cliente vê sai da pasta que já existe.

## O modelo (três regras)

1. **Nunca aparece para o cliente** — e não há botão para mostrar: anotações,
   horas, financeiro, a conversa do escritório com o agente, a trilha interna,
   a Equipe (só o nome do responsável principal aparece).
2. **Aparece por padrão** quando a pasta é compartilhada: nome e status do
   serviço, etapas (o andamento) e compromissos (as datas). Cada etapa e cada
   compromisso tem um **olhinho** para esconder.
3. **Documento só aparece com "compartilhar"** clicado naquele documento.

Mais o botão **"Ver como o cliente"**: abre a tela exatamente como ele vê. É
a resposta ao medo de "o que será que ele está vendo?".

A regra vale **na API**, como em `servicos_acesso`: a rota do cliente monta a
resposta a partir de uma lista fechada de campos (não "tudo menos o
proibido"), e o teste confere que anotação, hora e trilha nunca saem nela,
nem escondidas no JSON.

## A tela do cliente (celular primeiro)

```
Escritório Tal · Dra. Fulana                 [Conversar]

PARA VOCÊ
  ☐ Enviar RG e comprovante de residência   até 10/10  [Enviar]
  ☐ Confirmar audiência 22/10, 14h          [Confirmo] [Remarcar]

RESUMO
  Seu processo está na fase de ...

PRÓXIMAS DATAS
  22/10  Audiência de conciliação

ANDAMENTO
  ✓ Petição inicial protocolada            02/09
  ✓ Citação da outra parte                 20/09
  ○ Audiência de conciliação               22/10

DOCUMENTOS
  Petição inicial.pdf
```

**A pendência do cliente** é a ideia do Asana: uma **etapa com responsável
"cliente"**. "Enviar RG" vira etapa do cliente, aparece em "Para você", o
cliente manda o arquivo e a etapa se marca feita. Confirmar audiência é a
mesma coisa com dois botões. O advogado não aprende nada novo: ele já sabe
criar etapa.

## Para o advogado, dentro da pasta

- **"Compartilhar com o cliente"**: sugere a pessoa do cadastro do serviço
  (`servicos.cadastro_id`) e o e-mail dela; dá para acrescentar outra pessoa
  (casal, sócio da empresa cliente). Cada pessoa tem o próprio código e o
  próprio registro. **"Parar de compartilhar"** corta na hora.
- Os **olhinhos** nas etapas e compromissos; o **"compartilhar"** nos
  documentos.
- **"Ver como o cliente"**.
- Aba **"Atividade do cliente"** (só responsáveis e titular).

## Entrar

Link `paulus.ia.br/<slug>/cliente/<token>` → o cliente digita o e-mail → o
servidor confere que o e-mail é de uma pessoa com acesso → pede ao Worker o
envio do **código de 6 dígitos** (vale 10 min, 5 tentativas, depois espera) →
entra. "Lembrar este aparelho por 30 dias". O link sozinho não abre nada: é
preciso o link **e** o e-mail.

A conta do cliente **não é** uma conta do acesso de fora (`contas.py`): não
tem senha, TOTP nem permissões, e a única coisa que ela alcança são as rotas
`/cliente/...`. O porteiro recusa qualquer outra rota para a sessão de
cliente. Separado de propósito, para que um erro de permissão da equipe nunca
abra o escritório para um cliente.

## O registro

Entra no registro encadeado que já existe (`src/acesso/auditoria.py`), com
ações novas: entrou, saiu, abriu documento, baixou, imprimiu (pelo navegador),
comentou, enviou arquivo, confirmou/pediu para remarcar.

**O que não se promete:** print de tela. No celular o navegador não sabe; no
computador é fácil contornar. Em troca, cada documento aberto pelo cliente leva
uma **marca d'água** com o nome dele, a data e a hora — não impede o print,
mas toda cópia diz de onde saiu.

Na entrada, o aviso: "O escritório vê quando você entra, abre ou baixa um
documento." (LGPD: informar o titular.)

## Etapas

| Id | Etapa | Estado |
| --- | --- | --- |
| AC1 | **Ver.** Compartilhar/parar, olhinhos, "compartilhar" nos documentos, "Ver como o cliente"; entrada por código no e-mail (rota no Worker para o envio pelo Resend, pedida pelo servidor com a chave da instalação); a tela do cliente só de leitura (resumo, datas, andamento, documentos com marca d'água); registro e aba "Atividade do cliente"; travado fora do Plus | feita (04/10) |
| AC2 | **Agir.** Responsável "cliente" na etapa; "Para você" com envio de arquivo (vai para "Recebidos do cliente" na pasta do serviço no Acervo; tipo conferido pelo conteúdo, limite de tamanho, Windows Defender antes de entrar) e confirmar/remarcar compromisso (+ .ics); conversa da pasta (citando a etapa quando vem dela); aviso aos responsáveis no PAULUS e e-mail ao cliente quando o escritório responde | feita (04/10) |
| AC3 | **Resumo pela IA.** Escrito em linguagem simples **lendo só o que o cliente vê**; o advogado lê, ajusta e publica na aba Cliente (o rascunho fica lá até publicar — não passa pela fila de Aprovações) | feita (04/10) |
| AC4 | **Agente para o cliente.** Só sobre o que está na pasta (status, datas, o que é um documento); não opina sobre estratégia nem chance; o que passa disso vira mensagem ao advogado; tudo visível aos responsáveis; teto de créditos por cliente | depois |

Cada etapa vale sozinha: com a AC1 o cliente já acompanha o processo.

## Pontos de atenção

- **Vazamento** é o risco que importa: lista fechada de campos na rota do
  cliente + teste que procura anotação/hora/trilha na resposta + "Ver como o
  cliente" usando a mesma rota (o advogado vê o que a API entrega, não uma
  imitação).
- O responsável de etapa hoje aponta para Cadastros › Equipe
  (`responsavel_id`); "cliente" é um valor especial, não uma pessoa da equipe —
  não pode entrar no filtro de `servicos_acesso` nem nas Tarefas de ninguém.
- Arquivo do cliente nunca abre sozinho no servidor; entra como qualquer
  arquivo do Acervo, depois da conferência.
- Texto de tela só promete o que o código faz (sem "registramos prints").

## Como ficou (04/10/2026)

Código: `src/area_cliente.py` (o modelo, a lista fechada, entrar, marca
d'água, envio, conversa, resumo), `src/rotas_area_cliente.py` (as rotas),
`frontend/cliente.html` + `js/cliente.js` + `css/cliente.css` (a página do
cliente, prefixo `pcl-`; o mesmo `cliente.js` desenha a prévia no PAULUS),
`js/94-area-cliente.js` + `css/56-area-cliente.css` (o lado do escritório,
prefixo `acp-`), migração `042_area_do_cliente`, rota
`POST /api/tunel/cliente-email` no Worker (`worker/tunel.js`).

- **Portão:** `/cliente/*` e `/api/cliente/*` têm a política nova `cliente`
  (`acesso/politicas.py`) e o portão de fora as entrega à `PortaDoCliente`:
  plano, sessão do cliente e anti-CSRF. A sessão do escritório não alcança
  essas rotas, e o cookie do cliente não abre nada do escritório.
- **De fora, o escritório:** ver é `permitido` (só quem está na Equipe da
  pasta, pelo filtro de serviços); mexer abre pelo nível "faz" em Serviços.
- **Avisos:** tipo novo "Área do cliente" no aviso do Windows.
- **Testes:** `tests/test_area_cliente.py` (servidor, de ponta a ponta) e
  `tests/test_area_cliente_tela.py` (Edge: escritório a 1440 px, cliente a
  390 px no claro e no escuro); `worker/teste-tunel.mjs` (o e-mail).

O que ficou diferente do plano:

- **"Fora do ar":** se o servidor cai com a página do cliente aberta, ela diz
  "O escritório está fora do ar agora". Se a página nem abre (o servidor já
  estava desligado), quem responde é a Cloudflare, com a página de erro do
  túnel — o Worker não faz proxy dos endereços dos escritórios, de propósito
  (`wrangler.jsonc`), e isso não mudou.
- **Documento que não é PDF:** na tela, o cliente vê o texto que o Acervo leu,
  em páginas, com a marca; o arquivo baixado vai no formato original, sem
  marca — a tela diz isso antes.
- **Resumo:** publicado na aba Cliente, sem passar por Aprovações.

## ⏸ O que é do dono

1. **E-mail:** o Worker precisa da `RESEND_API_KEY` (a mesma do painel) e do
   domínio `paulus.ia.br` verificado no Resend para `naoresponda@`. Sem ela,
   compartilhar funciona e a tela oferece o link para mandar por outro
   caminho, mas o código de entrada não chega — o cliente não entra.
2. **Página de erro do túnel (opcional):** se quiser uma página própria quando
   o servidor está desligado, uma regra de erro personalizada na Cloudflare
   para `*.paulus.ia.br` (painel da zona › Regras › Páginas de erro).
3. **Teste real:** com o acesso de fora ligado, compartilhar uma pasta com um
   e-mail seu, abrir o link no celular (4G), entrar com o código, abrir um
   documento, mandar uma foto numa pendência e confirmar um horário; conferir
   a aba Cliente e "Quem acessou".
4. **Publicar a versão** quando quiser (o push já põe a rota do Worker no ar).
