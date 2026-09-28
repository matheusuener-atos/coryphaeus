# O instalador do PAULUS

```
venv\Scripts\python.exe tools\instalador\construir.py
```

O resultado fica em `tools\instalador\_construcao\`, que está fora do git:

- `PAULUS\`: o programa pronto, com o Python dentro. Dá para abrir direto pelo `PAULUS.exe`.
- `PAULUS-<versão>-instalador.exe`: o instalador, de ~94 MB. Instalado, ocupa ~410 MB.

Para trocar só o código, sem refazer o Python e as dependências:

```
venv\Scripts\python.exe tools\instalador\construir.py --so-instalador
```

A versão vem de `src/versao.py`.

## Como é feito

O desenho das telas está em `docs/ui/instalacao/LEIA-ME.md`: o instalador faz só o que precisa acontecer antes de o app existir no disco, e as escolhas (modelo de IA, escritório, dados, módulos, conexões) ficam no **assistente de configuração**, dentro do app (`frontend/js/23-boas-vindas.js`).

- **`Instalador.cs`**: o instalador e o desinstalador, um programa só. É uma janela de 640 × 480 desenhada à mão, no padrão preto, branco e cinza, que segue o tema claro ou escuro do Windows. A lateral mostra PAVLVS e as etapas. As fontes são as do app, convertidas para TTF por `fontes/gerar.py`, porque o GDI+ não lê woff2 nem fonte variável; a licença OFL vai junto. É compilado com o `csc.exe` do .NET Framework 4, que já vem no Windows. Por isso o código é C# 5.
- **O programa vai dentro do `.exe`.** O `construir.py` comprime a pasta `PAULUS\` com o 7-Zip (`7zr.exe`, oficial, LGPL) e emenda no fim do instalador o `7zr.exe`, o `.7z` e um rodapé de 40 bytes que diz onde cada parte começa (a classe `Pacote`). Na instalação, o `7zr.exe` extrai com o andamento na tela.
- **`Desinstalar.exe`**: o mesmo programa, sem as partes emendadas. Ele se copia para a pasta temporária e roda de lá, para conseguir apagar a própria pasta.
- **`Lancador.cs`**: o `PAULUS.exe`. Repassa ao programa o que vier junto, como o `--perguntar <arquivo>` do Explorer.

## O que precisa na máquina de quem constrói

- **Este venv**, com a mesma versão do Python do instalador. O script baixa o Python "embutível" oficial dessa mesma versão (python.org) e instala nele o `requirements.txt`.
- **O csc.exe do .NET Framework 4**, que já vem no Windows 10 e 11.
- **Internet na primeira vez**, para baixar o Python embutível e o `7zr.exe` (ficam em cache).

O Inno Setup não é mais usado.

## O que o instalador faz

- **Quatro telas:** Boas-vindas, Local, Instalação e Concluído.
- **Já instalado** (pelo registro do Windows ou, sem ele, pela pasta padrão com o programa dentro): a primeira tela vira "O PAULUS já está neste computador", com **Atualizar** e **Desinstalar**. Atualizar instala por cima na mesma pasta. O programa antigo fica guardado até o novo estar inteiro; se a instalação falhar ou for cancelada, ele volta. O instalador antigo (Inno Setup, 0.9.0 de 27/09) é reconhecido, e o registro e o desinstalador dele saem.
- **Pasta:** instala **para o usuário**, sem pedir administrador, em `%LOCALAPPDATA%\Programs\PAULUS`. Procurar abre o seletor de pasta do Windows e acrescenta `PAULUS` à pasta escolhida. Se a pasta já tem algo, o instalador pergunta antes; se o PAULUS está aberto, oferece fechar.
- **Opções da tela Local:**
  - Criar um atalho na área de trabalho.
  - Adicionar ao menu Iniciar (aparece na lista de apps).
  - "Perguntar ao PAULUS" no botão direito do Explorer: vale para PDF, Word (.docx), TXT, MD e Excel (.xlsx). No Windows 11, fica em "Mostrar mais opções". O arquivo entra anexado numa conversa nova; com o PAULUS já aberto, vai para a janela aberta, que vem para frente (`src/desktop.py`, `/api/externo/perguntar`).
  - Instalar o motor de IA local: só aparece se o Ollama não estiver na máquina. Baixa o instalador oficial de ollama.com (hoje ~1,5 GB), com o andamento em MB.
- **Fixar na barra de tarefas e no menu Iniciar, como estava no mockup, não existe.** O Windows 10/11 não deixa um instalador fazer isso; só a pessoa fixa, com o botão direito. Decidido com o dono em 27/09.
- **WebView2:** se faltar (o Windows 11 já traz), baixa e instala.
- **Sem internet**, o PAULUS instala assim mesmo. O que não baixou (Ollama, WebView2) aparece na tela final, e a tela inicial do PAULUS mostra como seguir.
- **Pasta presa:** um processo "dentro" da pasta do programa impede o Windows de mover ou apagar a pasta. Era o Ollama, que o PAULUS ligava herdando a pasta de trabalho e que segue rodando depois que o PAULUS fecha. Hoje o PAULUS trabalha na pasta de dados e liga o Ollama na pasta do próprio Ollama. Mesmo assim, se a pasta estiver presa, o instalador fecha o Ollama e o liga de novo no fim. Se ainda estiver presa, esvazia a pasta e instala no lugar, sem guardar a versão anterior. O desinstalador faz o mesmo.
- **Caminhos:** o Windows escreve o mesmo caminho em forma curta (`MATHEU~1`) e longa. Toda comparação "é desta pasta?" usa a forma longa.
- **Letras:** serifa (EB Garamond) só em PAVLVS e no título de cada tela; o resto em Manrope.
- **Cancelar** antes de o programa estar inteiro desfaz tudo. Depois, cancelar só para o download que falta.
- **Dados:** os dados ficam em `%LOCALAPPDATA%\PAULUS\dados` e os modelos em `%LOCALAPPDATA%\PAULUS\modelos`. **Atualizar troca o programa e não toca nos dados.**
- **Registro:** o que o instalador faz vai para `%TEMP%\PAULUS-instalador.log`, e o que o programa imprime vai para `dados\registro\paulus.log`.

## Desinstalar

Pelo Windows (Configurações › Aplicativos), pelo `Desinstalar.exe` ou pelo instalador, na tela "já instalado". Duas caixas, as duas desmarcadas:

1. **Tirar também os modelos de IA local:** os de voz e tradução do PAULUS e os modelos de linguagem que **o PAULUS** baixou no Ollama. Eles estão anotados em `modelos\ollama_baixados.txt` e saem com `ollama rm`. O Ollama e o que a pessoa baixou por fora ficam, e a tela final diz isso.
2. **Apagar também os dados do escritório.** Os documentos das pastas que o Acervo vigia nunca são tocados.

## Linha de comando

- **Instalar em silêncio:** `/silencioso [/pasta=...] [/sem-ollama] [/sem-atalho] [/sem-iniciar] [/com-explorer]`. Sem `/pasta`, usa a pasta já instalada ou a padrão.
- **Janela com a pasta já escolhida:** `/pasta=...`.
- **Desinstalar em silêncio:** `Desinstalar.exe /silencioso [/apagar-modelos] [/apagar-dados]`. Sem as duas opções, os modelos e os dados ficam.
- **Testar sem tocar numa instalação de verdade:** instale com `/pasta=` numa pasta temporária e defina `PAULUS_CASA` para uma pasta de dados de teste. Sem isso, `/apagar-dados` apaga `%LOCALAPPDATA%\PAULUS`, os dados de quem usa o PAULUS instalado nesta máquina. Registro, atalhos, menu do Explorer e o que sobrou do Inno só saem quando apontam para a pasta instalada ou removida.

## Testado em 27/09/2026

Nesta máquina (Windows 11, tema escuro), com a pasta do programa e os dados em pastas temporárias:

- instalar clicando, tela a tela, e em silêncio (17 s);
- com o PAULUS instalado, a tela "já instalado", e desinstalar por ela com as duas caixas marcadas;
- atualizar por cima: nada de `.antigo` sobra;
- os atalhos da área de trabalho e do menu Iniciar, e o menu do Explorer, criados e removidos;
- abrir o `PAULUS.exe` instalado: o assistente de configuração abre, e o `--perguntar <arquivo>` com o PAULUS aberto entrega o arquivo à janela aberta, sem abrir um segundo programa;
- desinstalar em silêncio pelo `Desinstalar.exe`: a pasta, os atalhos, o menu do Explorer e o registro somem, e a cópia temporária se apaga.

**Não testado:** o download e a instalação do Ollama e do WebView2 pelo instalador, porque os dois já estão nesta máquina; e uma máquina limpa, sem Python e sem Visual C++. As bibliotecas do C++ vão junto (app-local), mas vale conferir num Windows recém-instalado antes de distribuir.

## O que ainda não tem

- **Assinatura digital:** o Windows mostra "editor desconhecido" (SmartScreen) na primeira vez. Assinar exige certificado de assinatura de código, que é pago.
- **Atualização automática:** a versão nova se instala por cima da antiga, baixando o instalador de novo.
