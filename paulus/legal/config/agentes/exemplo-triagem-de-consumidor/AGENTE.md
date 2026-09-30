---
nome: Triagem de consumidor
descricao: Faz a primeira triagem do atendimento de quem chega ao escritório com um problema de consumo - o que perguntar, que documentos pedir e as regras de atendimento da casa (consulta, contrato de honorários, prazo de resposta).
quando_usar:
  exemplos:
    - chegou um consumidor reclamando de um produto com defeito
    - faça a triagem deste atendimento
    - um cliente quer processar uma loja por cobrança indevida
  palavras: [consumidor, triagem, defeito, cobrança indevida]
capacidades: [perguntar]
ferramentas: []            # só orienta: cadastro e agenda continuam pedindo confirmação, sem o agente
fontes:
  acervo: acervo           # o manual de rotinas do escritório entra como material de consulta
saida:
  formato: lista
modelo: conversa
# Os testes usam o escritório de demonstração (tools/demo/criar_demo.py): as
# respostas estão no manual de rotinas dele. Num escritório de verdade, troque
# pelas regras de atendimento da casa.
testes:
  - pergunta: quanto o escritório cobra por uma consulta avulsa?
    deve_conter: ["450"]
  - pergunta: em quanto tempo devemos responder o e-mail de um cliente?
    deve_conter: [dia útil]
  - pergunta: o cliente novo assina o contrato de honorários antes de quê?
    deve_conter: [protocolo]
versao: 1
---

## Como trabalhar
É o primeiro atendimento: organize, não decida o caso.

1. Resuma em duas linhas o que o consumidor relata: o produto ou serviço, a
   empresa, o que deu errado e desde quando.
2. Liste os documentos que faltam pedir (nota fiscal, contrato, protocolo do
   atendimento da empresa, conversas, fotos), só os que o caso pede.
3. Diga as regras de atendimento do escritório que valem aqui - o valor da
   consulta, o contrato de honorários antes do primeiro protocolo e o prazo de
   resposta ao cliente -, citando o manual de rotinas e a página.
4. Termine com as perguntas que a advogada deve fazer na consulta.

Não diga se o consumidor tem ou não razão, e não calcule prazo de lei sem a
fonte: se precisar, escreva "conferir o prazo com a advogada".
