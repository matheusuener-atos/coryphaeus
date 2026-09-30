# Roteiro de demonstração — PAULUS em 5 minutos

Para gravar (ou apresentar ao vivo) sem o dono presente. Tudo acontece no
escritório fictício **Moura & Campos Advocacia**, da Dra. Helena Moura
(OAB PA 12.345): nomes, documentos e valores inventados, com datas contadas a
partir do dia em que a base é criada — a demonstração não envelhece.

## Antes de gravar

1. Crie a base (apaga só a pasta da demonstração):
   `venv\Scripts\python.exe tools\demo\criar_demo.py --refazer`
2. Abra: `tools\demo\abrir_demo.bat` (usa `data\demo`, nunca os dados de verdade).
3. Confira as respostas da conversa com o modelo desta máquina:
   `venv\Scripts\python.exe tools\demo\roteiro.py` — só grave se o básico
   passar inteiro. Numa máquina lenta, grave as perguntas antes e corte a
   espera na edição (diga na narração que a IA roda no computador).
4. Tela cheia, tema claro, notificações do Windows desligadas.

## As cenas

| Tempo | Cena | O que fazer | O que dizer |
|---|---|---|---|
| 0:00 | Abertura | Tela inicial do PAULUS | "Este é o PAULUS: o assistente jurídico que roda no computador do escritório. Os documentos e a IA ficam aqui — nada vai para a nuvem." |
| 0:20 | Perguntar ao contrato | Conversa › "qual o novo valor mensal definido no aditivo?" | "Pergunto em português e ele responde lendo os contratos do escritório, com a página de onde tirou." (resposta: **R$ 19.980**) |
| 0:50 | Uma pergunta do dia a dia | "tenho alguma tarefa atrasada?" | "Ele também sabe da agenda e das tarefas." (resposta: **Enviar a minuta do aditivo**) |
| 1:10 | Publicações do DJEN | Tarefas › Publicações | "Todo dia ele consulta o Diário de Justiça Eletrônico pela OAB. Esta intimação do TRT saiu ontem." |
| 1:30 | Criar o prazo | Abrir a intimação do TRT8 › Criar prazo (8 dias) | "Um clique: conta os dias úteis, com feriados e recesso, e mostra a conta passo a passo para conferir. Virou tarefa na lista Prazos." |
| 2:10 | Serviços e equipe | Serviços › Renovação do contrato de transporte | "Cada serviço tem a sua pasta, a equipe, as etapas e os prazos. Quem não está na equipe nem vê o serviço." |
| 2:40 | Horas e cobrança | Seção Horas › Começar o cronômetro; depois "Cobrar no Financeiro" | "Cada pessoa marca o tempo. As horas viram cobrança no Financeiro, do cliente certo." |
| 3:20 | Aprovações | Aprovações | "O que sai do escritório — e-mail, documento para o cliente — passa por aqui antes. A IA propõe; o advogado decide." |
| 3:40 | De casa ou do celular | Configurações › Acesso de fora (mostrar o endereço) | "A equipe entra de fora pelo endereço do escritório, com a conta Google e o código do celular. O computador do escritório continua sendo o PAULUS." |
| 4:10 | Segurança | Configurações › Backup e Desempenho › Saúde | "Backup cifrado todo dia, numa pasta que o escritório escolhe. E aqui o PAULUS diz o que pode estar atrapalhando." |
| 4:40 | Fechamento | Tela inicial | "PAULUS: a IA trabalha no escritório, e o escritório continua dono dos próprios dados. Conheça em paulus.ia.br." |

## Se algo sair diferente

- **A conversa demora:** normal em computador sem placa de vídeo; corte na
  edição e diga "a IA roda aqui, no computador".
- **A resposta não bate com a da tabela:** rode `tools\demo\roteiro.py` de
  novo; se falhar, troque a pergunta por outra do conjunto básico que passou.
- **Publicações e horas vazias:** a base é de antes desta versão — refaça com
  `--refazer`.

## O que não mostrar

- O login do Google e o QR do autenticador (dados pessoais na tela).
- Configurações › Conexões com contas de verdade.
- Qualquer coisa fora de `data\demo`.
