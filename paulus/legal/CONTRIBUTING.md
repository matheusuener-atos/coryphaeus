# Contribuir com o PAVLVS

## Ambiente

Siga [docs/QUICKSTART.md](docs/QUICKSTART.md). A aplicação completa tem
dependências do Windows. Execute experimentos numa pasta de dados separada;
não use dados de clientes para demonstrar uma alteração.

## Verificações essenciais

Na pasta `paulus/legal`, com o venv preparado:

```powershell
.\venv\Scripts\python.exe tests\test_pipeline.py
.\venv\Scripts\python.exe tests\test_organizador.py
.\venv\Scripts\python.exe tests\test_habilidades.py
.\venv\Scripts\python.exe tests\test_frontend.py
```

Esses scripts verificam extração/busca, organização por regra, registro de
habilidades e integridade da interface. São uma base inicial, não a suíte
completa. O teste de frontend usa Node quando disponível para conferir
JavaScript; observe eventuais verificações puladas no relatório.

Para mudanças em nuvem, acesso, backup, editor ou assinatura, acrescente os
testes da área e registre no PR o comando, o resultado e o que foi simulado.
Os testes com navegador, OCR, modelos ou serviços externos têm requisitos
próprios; leia o cabeçalho do arquivo antes de executá-los. Uma aprovação com
provedor simulado não equivale a validação de API real ou de resposta do modelo.

O [estado atual](docs/ESTADO-ATUAL.md) diferencia recursos implementados de
validação operacional. Não há CI Python geral configurado neste repositório
na revisão de 24/10/2026; registre as verificações realmente executadas.

## Regras de implementação

1. **Dados de cliente fora do Git.** Use exemplos fictícios, confira o diff e
   não envie certificados, tokens, senhas ou trechos de documentos reais.
2. **Fluxos externos explícitos.** O produto tem integrações e IA em nuvem.
   Preserve consentimento, permissões, bloqueios por origem e registro do
   envio. Não introduza chamadas externas silenciosas nem descreva o produto
   inteiro como “100% local”.
3. **Resposta apoiada no contexto.** Preserve as fontes, as conferências e a
   indicação de limites. Não transforme ausência de informação em fato.
4. **Organização com conferência e reversão.** Preserve plano, diário,
   prevenção de sobrescrita e desfazer nas operações que movem documentos.
   Não prometa reversão universal para ações de outras funcionalidades.
5. **Regra antes de modelo quando suficiente.** Evite inferência para
   extração ou cálculo já resolvido por código determinístico.
6. **Habilidades no registro real.** As implementações ficam em
   `habilidades/`, carregadas por `src/registro.py`, com os estados definidos
   em `src/habilidade_base.py`. Não apresente habilidade incompleta como pronta.

## Estilo e revisão

Use type hints nas interfaces públicas, mensagens em português e comentários
que expliquem a decisão. No PR, descreva o problema, o comportamento final,
a verificação e os limites materiais.

Construir ou publicar instalador, release, site ou Worker é uma etapa
separada, conforme a orientação de publicação na raiz do repositório.
Não altere versão ou anúncio de atualização por uma mudança só documental.

## Reportar um defeito

Informe versão, comando ou passos, modelo/provedor, resultado esperado e
observado. Use um exemplo fictício mínimo; não cole documento de cliente.
Quando disponível, gere o diagnóstico pela tela Saúde para o canal de suporte.
