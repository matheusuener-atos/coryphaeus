# PAVLVS · Aplicativo de escritório

Assistente e ferramentas para escritórios jurídicos, parte do
[PAVLVS](../README.md) da [Atos/Coryphaeus](../../README.md).
Lê documentos, oferece busca e conversa com fontes e reúne editor,
serviços, tarefas, agenda e financeiro.

O aplicativo roda no computador do escritório. A resposta pode ser escrita
pelo modelo local ou pela nuvem configurada. A nuvem do plano tem
preferência quando ativada e consentida; “100% local” não descreve esse modo.

## Abrir pelo código-fonte

Após preparar o ambiente Windows pelo [QUICKSTART](docs/QUICKSTART.md),
na pasta `paulus/legal`:

```powershell
.\venv\Scripts\python.exe src\desktop.py
```

Para a interface no navegador:

```powershell
.\venv\Scripts\python.exe src\api.py
```

Abra o endereço completo impresso no terminal, incluindo a chave de acesso
local de uso único. O servidor escuta em `127.0.0.1`; acesso remoto é uma
funcionalidade separada, com configuração e permissões próprias.

## O que existe no código

- **Acervo:** importação de PDF, DOCX, TXT e MD, leitura de páginas escaneadas
  pelo OCR do Windows, classificação, busca e organização com plano e desfazer.
- **Conversa e produção:** resposta sobre documentos, fontes para conferir,
  editor, geração/exportação e assinatura de PDF com certificado.
- **Escritório:** clientes, serviços, equipe e permissões, tarefas, agenda,
  horas e financeiro.
- **Biblioteca e integrações:** consulta jurídica, acompanhamento de processos
  e publicações, e-mail, Drive, acesso remoto e ferramentas MCP.
- **Operação:** instalação, atualização, backup/restauração e diagnóstico.

Disponibilidade depende de configuração, plataforma, modelo, permissões e
contas externas. O [estado atual](docs/ESTADO-ATUAL.md) distingue código
implementado, experimentos e validação pendente.

## Demonstração e testes

O roteiro usa um escritório fictício em `data/demo`, separado dos dados de
uso normal. O atalho abaixo cria a base na primeira vez e abre o aplicativo:

```powershell
.\tools\demo\abrir_demo.bat
```

Para verificar extração e busca sem depender do Ollama:

```powershell
.\venv\Scripts\python.exe tests\test_pipeline.py
```

Os comandos complementares estão em [CONTRIBUTING.md](CONTRIBUTING.md).
Uma suíte aprovada não comprova a qualidade de respostas de um modelo nem
o funcionamento de serviços reais.

## Dados e processamento

No código-fonte, `PAULUS_DADOS` define a pasta da aplicação web/desktop;
sem ela, usa `data/`. O instalador usa pastas no perfil do Windows, descritas
no [guia do instalador](docs/instalador.md).

`data/samples/` contém documentos fictícios versionados. Contratos reais,
cache e dados de operação devem ficar fora do Git. O `.gitignore` reduz o
risco de inclusão acidental, mas é preciso conferir o que será enviado.

Na nuvem, o texto permitido pela configuração pode sair da máquina.
Mascaramento não é anonimização. A origem dos arquivos e as exclusões são
descritas em [dados e nuvem](docs/ESTADO-ATUAL.md#dados-e-nuvem).

## Suporte e próxima entrega

Para diagnóstico, use a tela Saúde nas Configurações e o arquivo gerado
para suporte. Uma issue de defeito deve informar versão, modo local/nuvem,
passos e resultado esperado, com exemplo fictício. Não inclua documentos,
tokens, certificados ou dados de clientes. O contato do produto está em
[paulus.ia.br](https://paulus.ia.br/).

A próxima entrega proposta é o [piloto delimitado](https://github.com/matheusuener-atos/coryphaeus/issues/1):
importar documentos, localizar informação com fonte, revisar um rascunho e
medir conclusão, tempo e falhas antes de ampliar o escopo.

## Documentação

- [QUICKSTART](docs/QUICKSTART.md): ambiente, execução e problemas comuns.
- [ESTADO-ATUAL](docs/ESTADO-ATUAL.md): escopo, evidências e limites.
- [CONTRIBUTING](CONTRIBUTING.md): verificações e contribuição.
- [ARCHITECTURE](docs/ARCHITECTURE.md): decisões e evolução da arquitetura.
- [PLANO-PRODUTO](docs/PLANO-PRODUTO.md) e [PLANO-PILOTO](docs/PLANO-PILOTO.md):
  histórico de entregas; estados e medições pertencem às datas registradas.
