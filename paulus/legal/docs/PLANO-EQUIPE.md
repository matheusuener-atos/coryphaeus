# Plano — PAULUS de equipe (servidor + colaboradores pela internet)

Mudança de regra de negócio pedida em 28/09/2026: o PAULUS fica instalado
**só no servidor do escritório**, e os colaboradores entram **pela internet**
(o acesso de fora), cada um com a própria conta, criada no PAULUS do servidor.

## Decisões do dono (28/09/2026)

- **Dados do escritório:** todos veem tudo (como hoje). Cada coisa passa a
  dizer **quem criou** e, na conversa, **quem perguntou**.
- **Entrar:** o colaborador aceita um **convite** (link mandado pelo
  WhatsApp), entra com o **Google** e confirma com o **código do celular**
  (Google Authenticator). Google + TOTP, sempre.
- **E-mail, Agenda e Drive por pessoa**, pela conta Google de quem entrou —
  e-mail incluído, com o limite de **100 usuários de teste** do Google Cloud
  até decidir a avaliação de segurança paga (CASA) do escopo do Gmail.
- **Ordem:** E1 → E2 → E4 → E3 (abaixo).

## Etapas

| Id | Etapa | Estado |
| --- | --- | --- |
| E1 | Quem criou: conversas (e quem perguntou), documentos e gravações | feita (tests/test_e1_quem_criou.py) |
| E2 | Quem mexe no quê: permissão por pessoa e por módulo (não vê / só vê / propõe / faz) e quem aprova | feita (tests/test_e2_permissoes.py) |
| E4 | Só no servidor: sai o "entrar num escritório existente" (vínculo por código); entra o convite | feita (tests/test_e4_convite.py) |
| E3a | Entrar com o Google + código do celular, no convite e na tela de entrar | feita (tests/test_e3_google.py, worker/teste-tunel.mjs); ⏸ cliente web no Google Cloud |
| E3b | E-mail, Agenda e Drive da conta de quem entrou ("Conectar o meu Google" em Minha conta) | feita (tests/test_e3b_google_da_pessoa.py); ⏸ os mesmos passos do Google Cloud |
| E5 | O PAULUS do servidor vinculado à conta Google: no assistente (dá para pular) ou em Configurações › Escritório e equipe; vinculado, abre travado e pede o Google (+ código, se a conta de titular tem autenticador) a cada abertura; "manter aberto neste computador"; a trava é do servidor (423); sem vínculo não se liga o acesso de fora nem se convida | feita (tests/test_e5_vinculo.py) |

## ⏸ E3a — o que o dono faz no Google Cloud (uma vez)

O código está pronto e **não aparece** enquanto as chaves não existirem (o
botão "Entrar com Google" some sozinho).

1. console.cloud.google.com → o projeto do PAULUS → **APIs e serviços ›
   Credenciais › Criar credenciais › ID do cliente OAuth**.
2. Tipo: **Aplicativo da Web**. Nome: `PAULUS — equipe (acesso de fora)`.
3. **URIs de redirecionamento autorizados:** `https://paulus.ia.br/oauth/google`
   (só esse; os escritórios recebem pelo Worker).
4. Copie o **ID do cliente** e a **chave secreta** para o `oauth_app.json`,
   nos campos `google_web_client_id` e `google_web_client_secret`.
5. **Tela de consentimento OAuth › Usuários de teste:** enquanto o app estiver
   em "Teste", só entra quem estiver nesta lista (até 100). Acrescente o
   e-mail de cada pessoa convidada.

O login pede só `openid email profile` — sem verificação do Google. O e-mail,
a Agenda e o Drive de cada pessoa (E3b) pedem escopos que exigem a verificação
(e, para o Gmail, a avaliação CASA acima de 100 usuários).

## O que o levantamento de 28/09 achou (o ponto de partida)

- Nenhum registro tinha dono: conversas (`src/jobs.py`), documentos
  (`src/documento.py`), gravações (`src/gravacoes.py`), e-mail (uma caixa
  só), preferências (um bloco `pessoa` só).
- Agenda e tarefas têm `responsavel_id`, que aponta para Cadastros (a
  equipe), não para as contas do acesso de fora.
- Papéis: só `titular` e `colaborador` (`src/acesso/contas.py`); a "alçada"
  de Aprovações é a autonomia do assistente, global.
- O vínculo por código entre máquinas nunca teve servidor: é `localStorage`.
- O Google entra por OAuth com retorno em `127.0.0.1` (loopback): só funciona
  com o navegador na mesma máquina. Para o convite, o retorno tem de ser um
  endereço fixo em `paulus.ia.br` que devolve ao escritório certo (o Google
  não aceita `*.paulus.ia.br`), com um cliente OAuth do tipo "Aplicativo da
  Web" criado pelo dono no Google Cloud.
- A fila do modelo atende uma pergunta por vez; com vários colaboradores, o
  servidor precisa de placa de vídeo ou da nuvem com chave própria.
