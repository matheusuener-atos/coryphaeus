# O instalador do PAULUS

```
venv\Scripts\python.exe tools\instalador\construir.py
```

O resultado fica em `tools\instalador\_construcao\`, que está fora do git:

- `PAULUS\`: o programa pronto, com o Python dentro. Dá para abrir direto pelo `PAULUS.exe`.
- `PAULUS-<versão>-instalador.exe`: o instalador, de ~100 MB. Instalado, ocupa ~410 MB.

Para trocar só o código, sem refazer o Python e as dependências:

```
venv\Scripts\python.exe tools\instalador\construir.py --so-instalador
```

A versão vem de `src/versao.py`.

## O que precisa na máquina de quem constrói

- **Este venv**, com a mesma versão do Python do instalador. O script baixa o Python "embutível" oficial dessa mesma versão (python.org) e instala nele o `requirements.txt`.
- **O csc.exe do .NET Framework 4**, para o `PAULUS.exe`. Ele já vem no Windows 10 e 11.
- **O Inno Setup 6**, para o `.exe` do instalador. É grátis: `winget install JRSoftware.InnoSetup --scope user`.

## O que o instalador faz

- **Pasta:** instala **para o usuário**, sem pedir administrador, em `%LOCALAPPDATA%\Programs\PAULUS`, com atalho no menu Iniciar e, se marcado, na área de trabalho.
- **Ollama:** oferece instalar, se ainda não estiver. Baixa de `ollama.com` na hora (~700 MB).
- **WebView2:** instala a janela do programa se faltar. O Windows 11 já traz.
- **Dados:** os dados ficam em `%LOCALAPPDATA%\PAULUS\dados` e os modelos baixados em `%LOCALAPPDATA%\PAULUS\modelos`. É o `PAULUS.exe` que diz ao programa onde ficam (`PAULUS_DADOS` e `PAULUS_MODELOS`). **Atualizar troca o programa e não toca nos dados.**
- **Registro:** o que o programa imprime vai para `dados\registro\paulus.log`. É o arquivo a pedir quando alguém conta que algo deu errado.
- **Já instalado:** abrir o instalador numa máquina que já tem o PAULUS pergunta **Atualizar ou reinstalar**, **Desinstalar** ou Cancelar. Desinstalar chama o desinstalador do Windows (o mesmo de Configurações › Aplicativos).
- **Modelo de IA:** depois de copiar os arquivos, uma página faz o teste da máquina (uns segundos, sem IA; `src/recomendar_modelo.py`) e lista os modelos do catálogo com tamanho, nota no nosso banco de provas e tempo estimado da 1ª pergunta. O recomendado vem marcado; dá para escolher outro ou **Não baixar agora**. A escolha vai para `dados\escolha_do_instalador.json`; na primeira abertura, o PAULUS põe o modelo como padrão e começa o download, com a barra na tela inicial (liga o Ollama se precisar). Sem Ollama, a página final diz isso e o cartão da tela inicial leva ao site.
- **Desinstalar:** faz duas perguntas, as duas com resposta padrão **não**:
  1. **Os modelos de IA local:** os de voz e tradução do PAULUS (`%LOCALAPPDATA%\PAULUS\modelos`) e os modelos de linguagem que **o PAULUS** baixou no Ollama (anotados em `modelos\ollama_baixados.txt`; saem com `ollama rm`). O que a pessoa baixou por fora e o próprio Ollama ficam.
  2. **Os dados do escritório.** Os documentos das pastas que o Acervo vigia nunca são tocados.
- **Aparência:** o fundo segue o tema do Windows (papel `#faf9f6` no claro, `#131312` no escuro, as cores do app) e as páginas de boas-vindas e de conclusão têm o painel da marca. As imagens são desenhadas em HTML com as letras do app, em `tools\instalador\arte\`; para mudar, edite o `.html` e rode `venv\Scripts\python.exe tools\instalador\arte\desenhar.py` (precisa do Edge).
- **Silencioso:** `/VERYSILENT /SUPPRESSMSGBOXES` instala sem perguntas e sem escolher modelo. Acrescente `/MODELO=recomendado` (o do teste da máquina) ou `/MODELO=llama3.2:3b` para já deixar um escolhido. Desinstalar em silêncio responde "não" às duas perguntas.

## Testado em 27/09/2026

Nesta máquina, com a pasta do programa numa pasta temporária:

- instalar em silêncio e abrir o PAULUS.exe instalado (a página responde e o Ollama é achado);
- instalar clicando, página por página: a de Modelo de IA mostrou esta máquina (i7-1360P, 16,9 GB, sem placa NVIDIA) com o llama3.2:3b recomendado, e a escolha foi gravada;
- com o PAULUS instalado, o instalador ofereceu Atualizar/Desinstalar, e Desinstalar abriu o desinstalador;
- desinstalar com "sim" para os modelos: saíram o modelo de teste do Ollama (`smollm:135m`, anotado como baixado pelo PAULUS) e a pasta de modelos; os outros modelos do Ollama ficaram;
- desinstalar com "não" para os dados, e em silêncio: a pasta do programa, o atalho e a entrada do Windows somem, e os dados ficam.

## O que ainda não tem

- **Assinatura digital:** o Windows mostra "editor desconhecido" (SmartScreen) na primeira vez. Assinar exige certificado de assinatura de código, que é pago.
- **Atualização automática:** a versão nova se instala por cima da antiga, baixando o instalador de novo.
- **Máquina limpa:** não foi testado numa máquina sem Python e sem Visual C++. As bibliotecas do C++ vão junto (app-local), mas vale conferir num Windows recém-instalado antes de distribuir.
