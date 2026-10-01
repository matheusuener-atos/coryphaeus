"""
PAULUS - O emissor de NFS-e pelo Padrão Nacional.

O escritório configura uma vez quem presta o serviço e como ele é tributado;
depois, cada nota nasce de um recebimento, de um Serviço ou de uma frase na
conversa, vira um cartão com a conta à vista, passa por Aprovações e só então
é montada, assinada com o A1 do escritório e enviada à Sefin Nacional.

As regras que mandam em tudo (docs/PROGRESSO-NFSE.md):

1. nota fiscal não se emite duas vezes: sem resposta, primeiro consulta;
2. nada sai sem o sim de quem pode emitir; agente só propõe;
3. o PAULUS não faz planejamento tributário: aplica o que o escritório (ou o
   contador) configurou e pergunta quando não sabe;
4. começa em produção restrita; produção só depois da liberação do titular;
5. o XML enviado, o recebido e a conta ficam guardados e podem ser abertos;
6. endereço, campo, código e regra vêm da documentação oficial, registrada
   no PROGRESSO com link e versão.

Dinheiro é sempre centavo inteiro. Nenhum float passa por aqui.
"""
