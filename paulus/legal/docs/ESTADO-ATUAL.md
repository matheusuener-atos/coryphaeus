# Estado atual do PAVLVS

Revisão documental em 24/10/2026, baseada na implementação do repositório.
O objetivo é orientar execução e validação; os planos antigos preservam o
histórico, mas não devem ser usados sozinhos como descrição do produto atual.

## Escopo e evidências

| Área implementada | Referências no código e nos testes |
| --- | --- |
| Acervo, extração, busca e organização | `src/extract.py`, `src/search.py`, `src/organize.py`; `tests/test_pipeline.py`, `tests/test_organizador.py` |
| OCR de PDF escaneado | `src/ocr_windows.py`, `habilidades/ocr.py`; `tests/test_ocr.py` |
| Conversa, fontes e revisão de documentos | `src/conversa_continua.py`, `src/citacao.py`, `src/api.py`; testes `test_conversa_continua.py`, `test_editor_agente.py` |
| Editor, assinatura e produção de documentos | `src/documento.py`, `src/assinatura.py`; testes `test_editor_blocos.py`, `test_assinatura.py` |
| Equipe, serviços, tarefas, horas e financeiro | `src/equipe.py`, `src/servicos.py`, `src/horas.py`; testes `test_escritorio.py`, `test_horas.py`, `test_financeiro_conversa.py` |
| Biblioteca, processos e publicações | `src/biblioteca/`, `src/processos.py`, `src/publicacoes.py`; testes `test_l2_processos.py`, `test_prazos_publicacoes.py` |
| Nuvem, consumo e integração Atos | `src/nuvem.py`, `worker/ia.js`, `worker/atos.js`; testes `test_v_nuvem.py`, `test_nuvem_segue_conta.py`, `worker/teste-atos.mjs` |
| Backup, restauração e diagnóstico | `src/backup.py`, `src/saude.py`; testes `test_backup.py`, `test_saude.py` |

A presença desses arquivos não significa que todos foram executados nesta
revisão, nem que as integrações foram homologadas em produção. As evidências
da entrega documental ficam na [issue #2](https://github.com/matheusuener-atos/coryphaeus/issues/2).

## Dados e nuvem

A decisão implementada desde 12/10/2026 é diferente da proposta inicial de
“local por padrão” e da primeira versão da nuvem opcional:

- `src/nuvem.py:ligada` dá preferência à nuvem do plano quando há chave de
  ativação da instalação e consentimento vigente. O campo `ligado` das
  preferências vale para a chave própria, não como interruptor da nuvem do plano.
- `sim_pela_assinatura` registra o consentimento pela assinatura do plano.
  Se o consentimento foi retirado, a rotina não o concede novamente sozinha.
- `usa` limita o uso às funcionalidades habilitadas: conversa, resumos e
  redação. O modelo local pode responder como reserva quando a nuvem não
  estiver disponível, conforme a operação e o motivo informado.
- Há caminhos com chave de API do escritório e um portão do produto em
  `paulus.ia.br`. O provedor/modelo do plano e as cotas devem ser conferidos
  na configuração atual; estudos antigos não são um catálogo comercial vigente.
- A proteção verifica casos marcados “só no escritório”, anexos marcados como
  vindos do e-mail e cópias do Drive feitas pelo programa. Arquivos antigos
  sem a marca de origem exigem atenção: a regra não descobre automaticamente
  toda procedência de um arquivo.
- O mascaramento troca identificadores por marcadores, mas não remove todo
  dado pessoal. Nomes, endereços e conteúdo podem permanecer no texto enviado.
- Os envios ficam registrados na pasta de dados; esse registro também deve
  ser tratado como dado do escritório.

Inferência local não significa ausência total de rede: login, cobrança,
e-mail, Drive, consultas públicas, acesso remoto, download de modelos e
atualizações têm fluxos externos próprios. Confira as conexões e permissões
habilitadas antes de definir um ambiente como isolado.

## Experimentos e validação pendente

| Situação | Como tratar |
| --- | --- |
| Alternativas de runtime/modelo local, como a ponte LiteRT-LM | Medições e ferramentas em `tools/litert_ponte.py` e `docs/MEDIDA-LITERT-LM.md`; não presumir que substituem o runtime distribuído |
| Qualidade das respostas e do editor | Bancos de provas e casos específicos não garantem desempenho no acervo de outro escritório; repetir com casos autorizados e fontes conferidas |
| Integrações reais | Login, e-mail, assinatura, cobrança e emissão fiscal dependem de contas, credenciais e configuração; testes simulados não provam homologação externa |
| Instalação e uso diário | O instalador existe, mas o fluxo do piloto precisa ser repetido numa máquina alvo com configuração e recuperação documentadas |
| Portabilidade | A aplicação completa usa recursos do Windows; não prometer instalação equivalente em Linux/macOS a partir dos READMEs antigos |

Os planos `PLANO-PRODUTO.md`, `PLANO-PILOTO.md` e `PLANO-NUVEM.md` contêm
decisões de momentos diferentes, inclusive descrições superadas por etapas
posteriores. Use a implementação e os testes da funcionalidade para resolver
essas diferenças, sem interpretar “feito” histórico como validação atual.

## Próxima entrega proposta

O [piloto delimitado](https://github.com/matheusuener-atos/coryphaeus/issues/1)
deve comprovar um fluxo: instalar/configurar, importar documentos fictícios
ou autorizados, localizar uma informação com fonte e revisar um rascunho.
Registrar modo de processamento, tempo para concluir, falhas e revisão das
fontes. A validação desse fluxo deve orientar os próximos ajustes.

O suporte começa pelo diagnóstico da tela Saúde, versão, modo local/nuvem e
passos reproduzíveis. Dados de cliente e credenciais não pertencem a issues
públicas. Para executar, veja [QUICKSTART.md](QUICKSTART.md); para verificar
alterações, veja [CONTRIBUTING.md](../CONTRIBUTING.md).
