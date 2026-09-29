# Plano de produto — do que falta para a primeira venda

Pedido do dono em 29/09/2026 ("coloque todos esses planos em andamento"). A
ordem é a de risco: primeiro o que faz o escritório perder trabalho ou ficar
de fora do próprio PAULUS; depois o que faz vender.

Estado: **feito** · **em andamento** · **a fazer** · **do dono** (depende de
decisão ou conta de quem administra o produto, não de código).

## P0 — Entrar no servidor sem internet · feito

O PAULUS vinculado à conta Google abria travado e só destravava pelo Google:
sem internet, o escritório ficava de fora do próprio computador.

- O código do celular (Google Authenticator funciona sem conexão) abre o
  PAULUS travado: o da conta de titular do mesmo e-mail do vínculo, quando
  existe; senão, um código próprio do servidor, ligado uma vez em
  Configurações › Escritório e equipe › Entrar sem internet (QR + códigos de
  recuperação; segredo pela proteção de dados do Windows).
- Cada código vale uma vez; 5 erros seguidos param as tentativas por 10 min.
- Só na janela do servidor. Teste: `tests/test_e6_sem_internet.py`.

## P1 — Backup e restauração · feito

Tudo mora num computador só. Um disco perdido é o escritório perdido.

- Backup automático (diário, e ao fechar), cifrado com uma senha que só o
  escritório sabe, num destino que o escritório escolhe: pasta (HD externo,
  pasta de rede, pasta sincronizada pelo Google Drive para computador).
- O que entra: banco, preferências, contas de acesso, Acervo gerado pelo
  PAULUS, gravações. Os modelos de IA não (baixam de novo).
- Restaurar em outro computador, pelo assistente de instalação ("tenho um
  backup"), com a senha. Teste de ponta a ponta: fazer, apagar, restaurar,
  conferir.
- Segredos protegidos pela proteção de dados do Windows não viajam entre
  computadores: restaurar pede entrar de novo nas contas (e-mail, Google).
- Feito: `src/backup.py` (AES-GCM em blocos, chave por scrypt, fim marcado;
  SQLite copiado pela API de backup), Configurações › Backup
  (`js/47-backup.js`), automático diário, restaurar prepara em
  `dados.restaurar` e a troca entra ao abrir (`desktop.py`), com os dados de
  antes guardados em `dados.antes-<data>`. Teste: `tests/test_backup.py`.
- Falta: oferecer "tenho um backup" já no primeiro passo do assistente.

## P2 — Saúde do PAULUS e diagnóstico · feito

- Tela "Saúde" em Configurações: memória livre, modelo carregado, túnel,
  último backup, versão, espaço em disco — com o que fazer em cada alerta.
- "Gerar diagnóstico": um arquivo com versões, erros recentes e estado, sem
  documento nem dado de cliente, para o escritório mandar ao suporte.
- Erro visível em vez de tela branca: a janela mostra o que falhou.
- Feito: `src/saude.py` e o cartão "Saúde do PAULUS" em Configurações ›
  Desempenho (memória, disco, modelo, backup, acesso de fora, entrar sem
  internet, versão, erros de 24 h, cada um com o que fazer); "Gerar
  diagnóstico" baixa um .txt sem dado de cliente (erros com o molde da rota,
  o tipo e arquivo:linha, nunca a mensagem). Erro inesperado numa rota vira
  500 com frase. Falha ao abrir mostra uma janela do Windows e fica em
  `logs/erro-ao-abrir.log`. Teste: `tests/test_saude.py`.

## P3 — Prazos processuais e publicações · a fazer

O que faz advogado trocar de ferramenta.

- Contagem de prazo em dias úteis (CPC art. 219), com feriados nacionais,
  recesso forense (20/12 a 20/01) e feriados do tribunal cadastrados pelo
  escritório; o prazo vira tarefa com a data certa.
- Publicações: consulta ao Diário de Justiça Eletrônico Nacional (DJEN, API
  pública do CNJ) pela OAB de cada advogado; cada intimação nova vira item
  para revisar, com o prazo sugerido.

## P4 — Horas e honorários por serviço · a fazer

- Registrar tempo por serviço (manual ou cronômetro), por pessoa da equipe.
- Relatório de horas do serviço e lançamento de cobrança no Financeiro.

## P5 — Roteiro de demonstração · a fazer

- Roteiro de 5 minutos sobre o escritório fictício (`tools/demo`), com o
  texto de cada passo, para gravar e vender sem o dono presente.

## Do dono

- **Verificação do Google** (tela "app não verificado"; avaliação CASA do
  escopo do Gmail) — `docs/video-verificacao-google.md`.
- **Nuvem com chave própria** para quem aceitar a IA fora do computador —
  decisão com o cliente do piloto.
- **Trocar o segredo do cliente OAuth "Paulus Desktop"** (ficou no histórico
  público do repositório).
