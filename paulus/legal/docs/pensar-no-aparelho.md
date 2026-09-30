# Escrever a resposta no aparelho

Quando o computador do escritório está ocupado com outras perguntas, quem
está de fora pode ter a resposta escrita **no próprio computador**, pelo
navegador, em vez de esperar na fila. O escritório continua procurando nos
documentos e conferindo o texto; o aparelho só escreve.

Vem **desligado**. Só o titular liga, e só no computador do escritório.
Precisa do [acesso de fora](acesso-de-fora.md) ligado.

---

## Como funciona

```text
 pergunta de fora
   ▼
 COMPUTADOR DO ESCRITÓRIO: permissões, escopo, busca → os trechos
   ▼  (o mesmo túnel do acesso de fora)
 NAVEGADOR DE QUEM PERGUNTOU: o modelo escreve com os trechos
   ▼
 COMPUTADOR DO ESCRITÓRIO: confere o texto → grava e mostra
                            (não passou: escreve de novo aqui)
```

- **O que vai ao aparelho**, a cada pergunta: a pergunta, o começo da
  conversa, as instruções e os **trechos** que respondem a ela — nunca o
  documento inteiro, até cerca de 9.000 caracteres, e só de documentos que
  aquela conta já veria pelo acesso de fora.
- **Uma vez**: o modelo de IA (hoje o Llama 3.2 3B, cerca de 2 GB) e o
  programa que o roda no navegador. Os dois saem do computador do
  escritório e são conferidos pelo SHA-256; nada vem de outro site.
- **O que fica no aparelho**: só o modelo, no armazenamento do navegador, e
  as preferências desta tela (a escolha, os números do teste, o "entendi").
  A pergunta, os trechos e a resposta não ficam.
- **O que o escritório confere** no texto que volta: números, datas e
  valores que não estão nos trechos, citação de trecho que não foi
  mandado, lei que não está nos trechos, links e e-mails estranhos.
  Reprovou: o escritório escreve de novo, e a resposta diz isso.
- **O que fica sempre no escritório**: ler o documento inteiro, editar,
  redigir peça, e-mail, OCR e incluir documentos.
- **O que não dá para garantir**: um aparelho com vírus ou com uma extensão
  maliciosa no navegador pode ler o que a página mostra. Isso já vale para
  o acesso de fora; escrever no aparelho não aumenta nem elimina esse risco.

---

## Para o titular: ligar

Tudo em **Configurações › Acesso de fora**, no computador do escritório.

1. No cartão **Escrever no aparelho**, clique em **Ligar**.
2. Em **Contas**, abra **Permissões** da pessoa e marque **Escrever a
   resposta no próprio aparelho: pode**. Conta por conta; o colaborador não
   consegue ligar para si, nem o titular pelo acesso de fora. A conta do
   titular pode sempre que o escritório liga.
3. O modelo do aparelho é o `llama3.2:3b` do Ollama deste computador. Ele
   precisa estar baixado aqui (Configurações › Modelos). Na primeira vez que
   alguém pede, o PAULUS divide o arquivo em partes de 512 MB (leva alguns
   segundos) e guarda em `<dados>/aparelho/partes/`.

**Desligar** vale na hora: no mesmo cartão, **Desligar** (para todos) ou,
na Permissão da conta, **no escritório** (só para ela). A resposta que
estava sendo escrita termina no escritório, e a pessoa vê o motivo.

### Casos "só no escritório"

No mesmo cartão, em **Só no escritório**:

- **Cliente**: vale para todos os Serviços dele, inclusive os que abrirem
  depois;
- **Serviço**: a pasta de trabalho do Serviço;
- **Pasta do Acervo**: escreva o caminho a partir da pasta do Acervo (por
  exemplo `Clientes\Fusão`) ou o caminho completo.

Pergunta cujos trechos saem de um caso marcado é escrita no escritório,
mesmo com tudo ligado, e a resposta diz "a resposta usa um caso marcado só
no escritório". Marcar e tirar ficam no registro de "Quem acessou".

### O relatório

Embaixo, **Relatório**: por pessoa, quantas respostas foram escritas no
aparelho, quantas foram **refeitas** (a conferência reprovou) e quantas o
escritório **terminou** (o aparelho parou, o pacote venceu ou a escrita foi
desligada). Cada entrega e devolução está em "Quem acessou", com a pessoa,
os documentos dos trechos e um código curto do navegador.

---

## Para quem está de fora: usar

1. Entre pelo acesso de fora, num **Edge ou Chrome de computador**
   atualizado, numa janela **normal** (a anônima não guarda o modelo).
2. Abra a conta (seu nome, no alto) › **Este aparelho** › **Fazer o teste**.
   O teste baixa o modelo (cerca de 2 GB, uma vez), carrega e mede a
   velocidade num texto de exemplo, sem nada do escritório. Ao escritório
   vão só os números.
3. Passou: na caixa da pergunta, ao lado do microfone, aparece **Escritório ▾**. As três
   posições:
   - **Escritório**: como sempre. Se a fila do escritório estiver acima de
     ~30 s (ou 2 perguntas na sua frente), aparece uma janela pequena
     oferecendo **Usar este aparelho**, **Esperar na fila** ou **Não sugerir
     de novo hoje**;
   - **Este aparelho**: toda pergunta que pode, vai ao aparelho;
   - **Automático**: o PAULUS compara, na hora, a fila e a velocidade do
     escritório com a velocidade medida neste aparelho, e usa o mais rápido.
4. Na primeira vez em "Este aparelho", um aviso diz o que vai, o que fica e
   o que não dá para garantir. **Entendi** e pronto.
5. Cada resposta diz onde foi escrita: na assinatura ("neste aparelho") e
   em **Sobre esta resposta › Escrita** ("escrita neste aparelho · modelo ·
   conferida no escritório", ou "escrita no escritório · motivo").

**Apagar o modelo**: conta › **Este aparelho** › **Apagar o modelo deste
aparelho**. Apaga os pesos e o teste; o seletor some até o próximo teste.
Limpar os dados do site no navegador também apaga.

---

## Solução de problemas

| O que aparece | Por quê | O que fazer |
| --- | --- | --- |
| O seletor não aparece | A conta não está liberada, a escrita está desligada no escritório, ou o teste ainda não passou neste aparelho | Veja conta › Este aparelho: o motivo está lá. Se o titular acabou de liberar, recarregue a página |
| "este navegador não tem WebGPU" | O navegador não tem o recurso que o modelo usa | Edge ou Chrome de computador, atualizado. A maioria dos celulares ainda não tem |
| "escreve devagar demais" | Menos de 3 palavras por segundo: a resposta levaria minutos | Use o escritório neste aparelho |
| "O navegador não deixou guardar o modelo" | Pouco espaço, ou janela anônima | Janela normal e espaço em disco; senão, o modelo é baixado a cada vez |
| "hash do modelo não confere" | A parte baixada chegou diferente da do escritório | O aparelho apaga e recusa sozinho; tente de novo. Se repetir, a rede está mexendo no que chega |
| Resposta "escrita no escritório · conferência reprovou" | O texto do aparelho tinha número, lei ou citação que não estão nos trechos | Nada: o escritório escreveu de novo. É a proteção funcionando |
| "o aparelho não terminou" | A aba fechou, o aparelho ficou 45 s sem rede, ou passaram 10 min | O escritório terminou do que já tinha chegado, ou do zero |
| "a pergunta pede o documento inteiro" | Ler inteiro é sempre no escritório | — |
| "a resposta usa um caso marcado só no escritório" | O titular marcou o cliente, o Serviço ou a pasta | — |
| "o modelo llama3.2:3b não está baixado neste computador" | O Ollama do escritório não tem o modelo | No escritório, Configurações › Modelos |

**Conferir que nada ficou no navegador**: F12 › **Aplicativo** (Application)
› **Armazenamento**. Em *Cache Storage*, só `paulus-modelo`, com as partes
do modelo; em *Armazenamento local*, só `paulus.aparelho`, com a escolha e
números. Nenhum texto da conversa.

---

Detalhes técnicos e o que foi medido: [PROGRESSO-APARELHO.md](PROGRESSO-APARELHO.md).
O que a política de privacidade diz: `site/politica-de-privacidade/`, seção
"Escrever a resposta no aparelho".
