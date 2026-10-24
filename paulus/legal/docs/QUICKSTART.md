# Instalação e execução do PAVLVS

Este guia é para executar o código-fonte no Windows. Para usar um instalador
publicado, acesse as [releases do projeto](https://github.com/matheusuener-atos/coryphaeus/releases).
O código da `main` pode estar à frente do último instalador.

## 1. Preparar o ambiente

Use Windows 10/11, Python e o runtime WebView2 para a janela desktop. O
ambiente local consultado nesta revisão usa Python 3.14.3; as dependências
estão em [requirements.txt](../requirements.txt). Esse arquivo tem limites
mínimos de versões, não um lockfile de ambiente reproduzível. A lista inclui
componentes específicos do Windows, como OCR e proteção de credenciais; não
é um roteiro validado de instalação completa para Linux ou macOS.

No PowerShell, a partir da raiz do repositório:

```powershell
cd paulus\legal
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Os comandos usam o executável do venv diretamente, sem depender de ativar
scripts no PowerShell.

Para usar a inferência local, instale o Ollama e baixe um modelo compatível:

```powershell
ollama pull llama3.2:3b
```

Esse é o modelo padrão de `src/llama_client.py`, salvo configuração diferente.
O desempenho e a memória necessária variam conforme modelo, contexto e
hardware. O download do modelo requer rede; a inferência local não exige
uma API de nuvem.

## 2. Conferir extração e busca

Ainda em `paulus/legal`:

```powershell
.\venv\Scripts\python.exe tests\test_pipeline.py
```

Esse teste usa documentos fictícios e não depende de Ollama nem de rede.
Para as demais verificações essenciais, veja
[CONTRIBUTING.md](../CONTRIBUTING.md).

## 3. Abrir a janela ou o navegador

Para a janela Windows:

```powershell
.\venv\Scripts\python.exe src\desktop.py
```

Para a interface no navegador:

```powershell
.\venv\Scripts\python.exe src\api.py
```

O servidor imprime um endereço como
`http://127.0.0.1:8000/entrar-local?chave=...`. Use o endereço completo
impresso, cuja chave só vale uma vez. Não publique essa chave. A janela
desktop cuida da entrada local; sua porta pode ser diferente.

Não execute as duas entradas simultaneamente sobre a mesma pasta de dados.
O servidor fica em `127.0.0.1`; não exponha a porta diretamente para oferecer
acesso remoto. Esse acesso tem fluxo próprio de identidade e permissões.

A entrada web aceita estas opções:

```powershell
.\venv\Scripts\python.exe src\api.py --contracts data\samples
.\venv\Scripts\python.exe src\api.py --port 8080
.\venv\Scripts\python.exe src\api.py --model llama3.2:3b
```

## 4. Testar a interface com dados fictícios

```powershell
.\tools\demo\abrir_demo.bat
```

O atalho cria a base `data/demo` na primeira vez e abre o aplicativo com
`PAULUS_DADOS` apontando para ela. Para criar a demonstração sem abrir a
janela:

```powershell
.\venv\Scripts\python.exe tools\demo\criar_demo.py
```

Não use `--refazer` para uma base que precise preservar. O roteiro está em
[ROTEIRO-DEMONSTRACAO.md](ROTEIRO-DEMONSTRACAO.md). Confirme modelo, conta e
configuração antes de testar envios à nuvem.

## 5. Escolher dados e modo de processamento

A aplicação web/desktop usa `PAULUS_DADOS`, ou `data/` quando a variável não
está definida. Para um teste separado, antes de abrir:

```powershell
$env:PAULUS_DADOS = Join-Path $env:TEMP 'pavlvs-teste'
.\venv\Scripts\python.exe src\desktop.py
```

Escolha uma pasta exclusiva e não reutilize dados de cliente em experimentos.
Em outro terminal, a variável não estará definida, a menos que tenha sido
configurada de forma persistente. `PAULUS_MODELOS` define separadamente os
modelos baixados de voz/tradução; o padrão no código-fonte é `data/modelos`.

O aplicativo pode usar a nuvem do plano ou a chave de API do escritório.
**Com a nuvem do plano ativada e consentida, ela tem preferência** nas tarefas
habilitadas; o interruptor da chave própria não desliga esse modo. A retirada
do consentimento tem tratamento próprio. Leia
[ESTADO-ATUAL.md](ESTADO-ATUAL.md#dados-e-nuvem) antes de trabalhar com documentos reais.

## 6. Terminal de perguntas

O CLI é uma entrada de consulta via Ollama, distinta dos fluxos completos da
interface. Ele usa `data/test_contracts` por padrão; escolha a pasta
explicitamente com `--contracts`:

```powershell
.\venv\Scripts\python.exe src\main.py --contracts data\samples --ask "Qual é o prazo de vigência de cada contrato?"
```

A pergunta acima exige Ollama disponível e o modelo baixado. Use
`--model`, `--top`, `--reindex` e `--no-stream` conforme necessário.
O modo interativo oferece `/docs`, `/buscar TEXTO`, `/trechos`, `/top N`
e `/sair`. Confira as fontes antes de usar a resposta.

## Problemas comuns e suporte

- **Ollama indisponível:** confirme o serviço e o modelo instalado. Se o
  aplicativo estiver usando nuvem, confira também a conta, o consentimento,
  a cota e a mensagem que explica eventual retorno ao modelo local.
- **PDF escaneado:** o OCR existe, usa o Windows e depende do idioma instalado.
  Confira a qualidade do original e as marcações do texto extraído.
- **Janela não abre:** confira WebView2 e as dependências. Execute
  `src/api.py` pelo terminal para distinguir falha da janela de falha do
  servidor e consulte os logs/diagnóstico.
- **Resposta lenta ou incorreta:** confira modelo, recursos disponíveis,
  documentos recuperados e fontes. Registre um caso fictício reproduzível.

A tela Saúde nas Configurações oferece diagnóstico para suporte.
Informe versão do programa, modo de processamento, passos e erro observado.
Não envie documentos de cliente ou credenciais em issues públicas. O
contato do produto está no [site](https://paulus.ia.br/).
