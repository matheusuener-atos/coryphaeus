# Acesso de fora

Usar o PAULUS de casa, do fórum ou do celular, com o programa rodando no
computador do escritório. Nada muda de lugar: os documentos, o índice e o
modelo de IA continuam lá. O que ganha um caminho seguro até eles é a tela.

Vem **desligado**. Só o escritório liga, e só no próprio computador: no
assistente de configuração (passo "Acesso à distância", logo depois do nome
do escritório) ou, depois, em Configurações › Acesso de fora.

---

## Como funciona

```text
 COMPUTADOR DO ESCRITÓRIO
   PAULUS (só em 127.0.0.1)
     ├─ a janela do programa ─────────── chave da janela
     └─ cloudflared (túnel de saída, nenhuma porta aberta no roteador)
            ▼
 Cloudflare: https://<escritório>.paulus.ia.br
            ▼
 navegador de quem está de fora → tela de entrar do PAULUS:
   verificação contra robôs → e-mail + senha → código do autenticador
```

Três portas, uma depois da outra, iguais para o titular e para a equipe:

1. **O túnel.** O `cloudflared` abre uma conexão de *saída* do computador do
   escritório até a Cloudflare. Nada escuta na rede; o roteador não muda.
2. **A verificação contra robôs** (Cloudflare Turnstile), na tela de entrar.
   Ela é conferida antes da senha: robô nem chega a tentar. O token dela só
   passa pelo site do PAULUS (paulus.ia.br) para ser conferido — nada do
   escritório vai junto.
3. **A conta do PAULUS**, com e-mail, senha e o código do aplicativo
   autenticador do celular. Cinco erros bloqueiam a conta por 15 minutos (e o
   bloqueio dobra a cada reincidência); vinte erros vindos do mesmo endereço
   de internet em 10 minutos fecham esse endereço por 1 hora. O computador
   do escritório recebe um aviso a cada bloqueio.

Sem sessão, quem chega ao endereço só vê a tela de entrar. A sessão dura até
30 minutos sem uso e no máximo 12 horas. De fora, o titular troca a própria
senha e encerra as sessões pedindo o código do autenticador de novo.

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

## Ligar

O `cloudflared` (o programa da Cloudflare que abre o túnel) vem com o
instalador do PAULUS sempre que falta na máquina. Instalá-lo não liga nada.

No assistente de configuração, ou em Configurações › Acesso de fora:

1. **Ligue o interruptor** "Acesso à distância".
2. **Escolha o endereço.** O PAULUS sugere a partir do nome do escritório
   (`Moura & Associados Advocacia` → `moura-associados`). Dá para mudar:
   letras minúsculas sem acento, números e hífen, de 3 a 24. Enquanto você
   digita, o PAULUS confere se está livre; se não estiver, diz por quê e
   sugere outro. O endereço final aparece embaixo — é por ele que você e a
   sua equipe entram.
3. **Crie a sua conta de titular**: nome, e-mail e senha (pelo menos 10
   caracteres). Leia o QR com o aplicativo autenticador do celular (Google
   Authenticator, Microsoft Authenticator, 2FAS…), digite o código que ele
   mostra e guarde os 10 códigos de recuperação fora do celular.
4. **Conecte.** O PAULUS abre o navegador em `paulus.ia.br/conectar` e
   mostra um código (`XXXX-XXXX`). Confira se o navegador mostra o mesmo
   código, passe pela verificação contra robôs e clique em **Confirmar**.
5. Em poucos segundos o PAULUS mostra o endereço
   `https://<nome>.paulus.ia.br`, com o botão de copiar, e liga o túnel.
   Sugestão: ligue "Abrir o PAULUS com o Windows" — ao ligar o computador, o
   PAULUS abre minimizado e o acesso volta sozinho.

O endereço fica reservado por 15 minutos enquanto você confirma. Se o código
vencer, **Tentar de novo** usa o mesmo nome.

Para o celular funcionar a qualquer hora, o computador do escritório precisa
estar ligado e com o PAULUS aberto. Com o acesso ligado, o PAULUS pede ao
Windows para não suspender por inatividade.

## Contas da equipe

Em Configurações › Acesso de fora › Contas › **Nova conta**, no computador do
escritório (de fora, ninguém mexe em contas). Cada pessoa tem a própria
conta: nome, e-mail, senha e o autenticador do celular dela. Marque
"Titular" só para quem pode aprovar de fora e cuidar das contas; o resto é
colaborador.

Na mesma tela: trocar a senha de alguém (encerra as sessões dela), cadastrar
o autenticador de novo (celular novo ou perdido), gerar códigos de
recuperação novos e remover a conta.

## Desligar e remover

- **Desligar** para o túnel na hora e guarda o endereço. Ligar de novo usa o
  mesmo endereço.
- **Remover** apaga o endereço e o túnel na conta do Atos e o que ficou
  guardado no computador; encerra quem estiver de fora. O nome fica livre:
  para voltar, é ligar de novo.
- **Encerrar todas as sessões** tira todo mundo que está de fora, sem
  desligar nada.

Endereço que nunca se conectou em 7 dias, ou que ficou parado por mais de
180 dias, é liberado sozinho pelo site. O PAULUS percebe na próxima vez que
abrir, desliga o acesso e avisa.

---

## Solução de problemas

**"Indisponível: porta ocupada".** Outro programa está usando a porta que o
túnel procura neste computador. Enquanto isso ninguém entra de fora (a
janela daqui funciona normalmente). Aperte **Usar outra porta**: o PAULUS
escolhe uma livre e avisa o site.

**"Desconectado — tentando de novo" (túnel caído).** A internet oscilou ou o
computador acordou agora. O PAULUS tenta de novo sozinho, com espera
crescente até 1 minuto. Se não voltar: confira a internet do escritório; o
registro do túnel fica em `dados\logs\tunel.log` (sem o token).

**"Muitas tentativas erradas: a conta ficou bloqueada".** Espere 15 minutos
(o bloqueio dobra a cada reincidência). No escritório, o aviso do Windows diz
de quem foi. Se a senha foi esquecida, troque-a no computador do escritório.

**"Muitas tentativas erradas deste endereço".** Vinte erros vieram da mesma
rede em 10 minutos (às vezes, a rede compartilhada de um fórum ou hotel):
ela fica fechada por 1 hora. Tente de outra rede — o 4G do celular, por
exemplo — ou espere.

**"A verificação contra robôs não passou".** Recarregue a página e faça a
verificação de novo; cada verificação vale uma vez. Se aparecer "não consegui
conferir a verificação agora", o site do PAULUS está fora do ar por um
instante: ninguém entra até ele voltar.

**"O código venceu antes da confirmação".** O código de conectar vale 15
minutos. Aperte **Tentar de novo**: o nome escolhido continua o mesmo.

**"O endereço foi liberado por falta de uso; conecte de novo".** O endereço
ficou sem uso tempo demais e foi devolvido. Ligue o acesso de novo (dá para
pedir o mesmo nome, se ainda estiver livre); as contas da equipe continuam.

**Perdi o celular do autenticador.** Entre com um dos códigos de recuperação
(cada um vale uma vez). No escritório, em Contas › Autenticador, cadastre o
celular novo — o antigo deixa de valer.

**"Falta o cloudflared".** Reinstale o PAULUS: o instalador baixa a versão
fixa do GitHub da Cloudflare e só usa o arquivo se a assinatura digital for
da Cloudflare. Se a conferência falhar, o instalador segue sem ele e avisa na
tela final.

**"O acesso de fora chegou ao limite de escritórios desta fase".** O número
de escritórios conectados é limitado nesta fase. Escreva para
contato@paulus.ia.br.
