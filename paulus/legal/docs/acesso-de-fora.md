# Acesso de fora

Usar o PAULUS de casa, do fórum ou do celular, com o programa rodando no
computador do escritório. Nada muda de lugar: os documentos, o índice e o
modelo de IA continuam lá. O que ganha um caminho seguro até eles é a tela.

Vem **desligado**. Só o escritório liga, e só no próprio computador, em
Configurações › Acesso de fora.

---

## Como funciona

```text
 COMPUTADOR DO ESCRITÓRIO
   PAULUS (só em 127.0.0.1)
     ├─ a janela do programa ─────────── chave da janela
     └─ cloudflared (túnel de saída, nenhuma porta aberta no roteador)
            ▼
 Cloudflare: https://<escritório>.paulus.ia.br
   └─ Cloudflare Access: código no e-mail autorizado
            ▼
 navegador de quem está de fora → conta do PAULUS: senha + código do autenticador
```

Quatro portas, uma depois da outra:

1. **O túnel.** O `cloudflared` abre uma conexão de *saída* do computador do
   escritório até a Cloudflare. Nada escuta na rede; o roteador não muda.
2. **O Cloudflare Access.** Antes de chegar ao PAULUS, a pessoa confirma um
   e-mail da lista do escritório (a Cloudflare manda um código). A lista é a
   das contas do PAULUS, até 10.
3. **O PAULUS confere de novo** o que o Access disse (a assinatura do
   crachá dele) — se um dia a regra da Cloudflare falhar, o computador diz não.
4. **A conta do PAULUS**, com senha e o código do aplicativo autenticador do
   celular. Cinco erros bloqueiam a conta por 15 minutos, e o computador do
   escritório recebe um aviso.

### O que dá e o que não dá para fazer de fora

| De fora | |
| --- | --- |
| Conversar, perguntar, ler documentos e o trecho citado | sim |
| Redigir no editor e na planilha | sim |
| Agenda, tarefas, cadastros | ver; o que se grava vira **proposta** na fila de Aprovações |
| Aprovar | só o titular; o que sai do escritório (e-mail, Drive) pede o código do autenticador de novo |
| Baixar um documento | um de cada vez, e fica registrado |
| Assinar, mover, apagar, exportar em lote, configurações, contas | só no computador do escritório |

### O que a Cloudflare vê

A conexão é criptografada do navegador até a Cloudflare e da Cloudflare até
o computador do escritório. No meio, a Cloudflare abre a conexão para
entregá-la: nesse trecho, o tráfego passa por ela descriptografado. O
endereço fica na conta Cloudflare do Atos, que cria o caminho e **não roteia,
não inspeciona e não registra** o conteúdo.

### Quem acessou

Tudo o que acontece de fora fica registrado no computador do escritório, por
um ano: quem entrou e saiu, quem errou a senha, o que abriu, o que baixou, o
que propôs e o que aprovou. Em Configurações › Acesso de fora › Quem acessou,
com filtro e PDF. Cada linha guarda o hash da anterior: se alguém editar o
arquivo à mão, a tela diz em que linha.

---

## Conectar

Precisa de:

- o `cloudflared` no computador — o instalador do PAULUS traz, marcando
  "Acesso de fora pelo celular";
- uma **conta de titular** com o autenticador confirmado (Configurações ›
  Acesso de fora › Contas › Criar a conta do titular). O cadastro mostra um
  QR para o aplicativo autenticador (Google Authenticator, Microsoft
  Authenticator, 2FAS…) e 10 códigos de recuperação — guarde-os fora do
  celular.

Então, em Configurações › Acesso de fora › Conectar:

1. Confira o nome do escritório (vira o endereço) e o e-mail do titular, e
   aperte **Conectar**.
2. O navegador abre em `paulus.ia.br/conectar`. Entre com o e-mail do
   titular: a Cloudflare manda um código para ele.
3. Confira que o código da página é o mesmo que aparece no PAULUS e aperte
   **Confirmar**.
4. Em poucos segundos o PAULUS mostra o endereço
   `https://<escritório>.paulus.ia.br` e liga o túnel.

As outras pessoas: crie uma conta para cada uma (colaborador ou titular). O
e-mail entra sozinho na lista da Cloudflare.

Para o celular funcionar a qualquer hora, o computador do escritório precisa
estar ligado e com o PAULUS aberto. Com o acesso ligado, o PAULUS pede ao
Windows para não suspender por inatividade; e dá para ligar "Abrir o PAULUS
com o Windows" (abre minimizado).

## Desligar e remover

- **Desligar** para o túnel na hora e guarda o endereço. Ligar de novo usa o
  mesmo endereço.
- **Remover** apaga o endereço, o túnel e a regra do Access na conta do Atos,
  e o que ficou guardado no computador; encerra quem estiver de fora. Para
  voltar, é conectar de novo (com outro endereço).
- **Encerrar todas as sessões** tira todo mundo que está de fora, sem
  desligar nada.
- Trocar a senha de uma conta encerra as sessões dela.

---

## Solução de problemas

**"Indisponível: porta ocupada".** Outro programa está usando a porta que o
túnel procura neste computador. Enquanto isso ninguém entra de fora (a
janela daqui funciona normalmente). Aperte **Usar outra porta**: o PAULUS
escolhe uma livre e avisa a Cloudflare.

**"Desconectado — tentando de novo".** O túnel caiu (internet oscilando,
computador acordando). O PAULUS tenta de novo sozinho, com espera crescente
até 1 minuto. Se não voltar: confira a internet do escritório; o registro do
túnel fica em `dados\logs\tunel.log` (sem o token).

**A página do celular diz "acesso não autorizado" ou pede o e-mail de novo.**
O e-mail usado não está na lista. A lista é a das contas do PAULUS: crie a
conta com esse e-mail no computador do escritório. A conta do PAULUS tem de
ser do mesmo e-mail que passou pela Cloudflare.

**"Conta bloqueada por tentativas erradas".** Espere 15 minutos (o bloqueio
dobra a cada reincidência). No escritório, o aviso do Windows diz de quem
foi. Se a senha foi esquecida, troque-a no computador do escritório.

**Perdi o celular do autenticador.** Entre com um dos códigos de recuperação
(cada um vale uma vez). No escritório, em Contas › Autenticador, cadastre o
celular novo — o antigo deixa de valer.

**"Falta o cloudflared".** Reinstale o PAULUS marcando "Acesso de fora pelo
celular". O instalador baixa a versão fixa do GitHub da Cloudflare e só usa
o arquivo se a assinatura digital for da Cloudflare.

**"O acesso de fora chegou ao limite de escritórios desta fase".** O serviço
gratuito da Cloudflare tem um número de usuários por conta, dividido entre
todos os escritórios. Escreva para contato@paulus.ia.br.
