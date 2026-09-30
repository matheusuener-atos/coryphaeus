# DECISÃO — ideias vindas do umbrelOS 2.0

Briefing: `docs/prompt-ideias-umbrel-v0.md` (30/09/2026). Levantamento feito no
código de 30/09/2026 (commit 6c4007e da `main` + a Biblioteca). O dono pediu
para seguir direto, sem as pausas do briefing; em troca, **nada que faça
conteúdo do escritório sair da máquina ou abra porta de rede nova vem ligado
de fábrica**.

## A tabela

| Ideia | Existe hoje? | Valor para o advogado | Risco | Esforço | Depende de | Decisão |
|---|---|---|---|---|---|---|
| **A. Servidor MCP** | Não. Há o catálogo de ferramentas com contrato JSON (`ferramentas.py`: cadastrar cliente, compromisso, exibir documento, NFS-e — todas com confirmação), a auditoria (`acesso/auditoria.py`) e as políticas por rota (`acesso/politicas.py`). | Alto: o Claude/ChatGPT do advogado para de inventar artigo de lei. | O mais sério: o que o PAULUS devolve vai para o modelo de outra empresa. | Médio (o protocolo MCP é JSON-RPC; escrito à mão, sem dependência). | — | **Fazer agora, só a parte que não tem conteúdo do escritório:** as ferramentas das **leis** (texto público, Lei 9.610, art. 8º, IV) — citar artigo, procurar, dizer se está revogado e quando mudou. Biblioteca, cartão de documento e prazos (conteúdo do escritório e de cliente) **ficam de fora**: são a pausa do briefing. Desligado de fábrica, só em 127.0.0.1, token por conexão criado na janela local. |
| **B. Ponto de restauração por tarefa** | Em boa parte: lixeira de 30 dias (`lixeira.py`), diário com "desfazer" do Organizar (`organize.py`), rascunhos versionados, backup cifrado (`backup.py`). Nenhuma tarefa de vários passos grava sem confirmação. | Médio hoje: não há agente escrevendo em lote. | Restauração parcial desencontrar índice e metadata. | Alto (tudo ou nada, por tarefa). | A com escrita | **Fazer depois:** antes de dar ferramenta de escrita a agentes pela A. Hoje o que grava passa por confirmação, e o que apaga passa pela lixeira. |
| **C. Rede do escritório** | Não: o servidor escuta só em 127.0.0.1; de fora, pelo túnel da Cloudflare com senha, TOTP e permissões. | Médio (o túnel já resolve, com o tráfego saindo do prédio). | Abre porta nova; firewall, interface e certificado. | Alto. | — | **Fazer depois**, com o dono acordado: é abrir porta de rede nova, e a regra de ouro "só 127.0.0.1" é quebrada de propósito. Não é decisão para madrugada sem ninguém olhar. |
| **D. Muralha ética** | Em parte: Serviços por colaborador (`servicos_acesso.py`, 29/09) — de fora, cada pessoa só vê os serviços de cuja Equipe participa, e o Acervo, a busca, a Agenda e as gravações deles; o filtro do Acervo (`search.FILTRO`) vale antes de a busca devolver trechos. | Alto em escritório com conflito de interesse. | Vazamento por caminho esquecido. | Alto (percorrer todas as rotas, como a R3). | decisão de produto: o titular e a janela do servidor ficam fora da muralha? | **Fazer depois:** a base existe; estender a "caso com equipe definida que vale também dentro do escritório" pede a decisão de quem fica acima da muralha. |
| **E. Documento pelo celular** | Em parte: a interface já roda no celular pelo acesso de fora; o PDF escaneado passa pelo OCR do Windows página a página (99%/95% das palavras, medido em 27/09); o envio para o Acervo existe. | Alto: o papel do fórum entra na hora. | OCR de foto torta ou cortada. | Médio (junta peças prontas). | — | **Fazer agora:** tela de câmera na interface web, fotos → um PDF → Acervo, com prévia antes de confirmar. Nada sai da máquina além do que o acesso de fora já faz. |
| **F. GPU AMD e Intel** | Não: `maquina.py` só reconhece NVIDIA (`nvidia-smi`). | Médio: máquina com placa integrada ganha a recomendação certa. | Baixo: a medida decide. | Baixo. | — | **Fazer agora:** todas as placas pelo Windows, e o uso de verdade confirmado pelo Ollama (`size_vram` do modelo carregado). |

**Ordem:** F (baixo risco, rápido), E, A. Nenhuma das três deixa conteúdo do
escritório sair da máquina: a A só devolve texto de lei.

## Contratos

### F — GPU AMD e Intel
- **Entra:** `maquina.testar()` lista todas as placas de vídeo pelo Windows
  (nome, fabricante, memória), além das NVIDIA do `nvidia-smi`; a medição de
  um modelo ("Medir", em Configurações › Modelos) guarda se o Ollama pôs o
  modelo na placa (`/api/ps`, `size_vram`), e a tela diz "o Ollama usa a
  placa" ou "a placa existe, mas o Ollama não a usa nesta máquina".
- **Fica de fora:** instalar driver ou versão do Ollama com outro backend.
- **Chave:** nenhuma para ler (é só informação a mais no teste); a
  recomendação só passa a contar a placa quando a medida confirmar o uso.
- **Portão:** `tests/test_umbrel_f_gpu.py` — leitura das placas com a saída
  do Windows simulada (Intel, AMD, NVIDIA, nenhuma) e o `size_vram` simulado;
  nesta máquina, o teste real diz o que há.

### E — Documento pelo celular
- **Entra:** um botão "Fotografar documento" (acesso de fora e janela local):
  a câmera do celular (`capture`), várias páginas, prévia com girar e tirar,
  confirmar → as fotos viram um PDF (uma página por foto) → o envio de sempre
  do Acervo → o OCR de sempre.
- **Fica de fora:** corte automático de bordas e correção de perspectiva.
- **Chave:** `umbrel.captura`.
- **Portão:** `tests/test_umbrel_e_captura.py` — fotos simuladas (texto
  conhecido, giro, ruído, JPEG de celular) viram PDF, entram no Acervo e o
  OCR acerta ≥ 90% das palavras; foto que não é imagem é recusada.

### A — MCP só das leis
- **Entra:** um servidor MCP (JSON-RPC 2.0 por HTTP, em
  `POST /mcp`, só de 127.0.0.1) com três ferramentas de leitura: `citar_artigo`,
  `procurar_na_lei`, `leis_instaladas`. Token por conexão, criado e revogado
  só na janela local (Configurações), guardado pelo mecanismo de segredos do
  projeto (só o hash), com a lista de ferramentas de cada conexão. Toda
  chamada vai para a auditoria.
- **Fica de fora:** biblioteca, documentos, cartão, prazos, agenda,
  qualquer escrita (ver B).
- **Chave:** `umbrel.mcp`, desligada. Ao criar a conexão, a tela diz o que sai
  (texto de lei, público) e o que não sai.
- **Portão:** `tests/test_umbrel_a_mcp.py` — sem token 401; token revogado 401;
  ferramenta fora da lista da conexão negada; nenhuma ferramenta devolve
  texto do Acervo, da biblioteca ou de cadastro; de fora (túnel) a rota é
  bloqueada; toda chamada auditada.

## Andamento

(em andamento — ver abaixo, por ideia)
