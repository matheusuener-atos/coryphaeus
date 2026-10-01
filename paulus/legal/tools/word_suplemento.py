"""
Gera o que o suplemento do Word leva pronto (W1):

  - word/manifesto.xml: o modelo do manifesto, com $ID, $BASE, $VERSAO e
    $NOME trocados por instalação em src/word_instalar.py. A aba, os botões e
    o menu do botão direito saem da tabela abaixo;
  - word/icones/<nome>-<tamanho>.png: cada ícone nos tamanhos que o Word
    pede (16, 32 e 80) e nos de tela de alta resolução (20, 24, 40, 48, 64),
    desenhados do mesmo SVG pelo Edge (Playwright), sem dependência nova.

Uso: python tools/word_suplemento.py [manifesto|icones]
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WORD = RAIZ / "word"
TAMANHOS = (16, 20, 24, 32, 40, 48, 64, 80)

# Todos os botões abrem o mesmo painel. O id dele é o reservado
# Office.AutoShowTaskpaneWithDocument: é o que deixa um documento abrir o
# painel sozinho ao ser aberto (medido no Word 2021: com outro id, o Word diz
# "não foi possível encontrar o painel de tarefas").
# id, ícone, rótulo, dica (até 250 caracteres), tela do painel
BOTOES = [
    ("Conferir", "conferir", "Conferir citações",
     "Confere as leis, súmulas e processos citados no documento e abre o painel com o resultado.", "conferir"),
    ("Lei", "lei", "Inserir lei",
     "Procura um artigo e insere o texto vigente com a referência, como alteração controlada.", "lei"),
    ("Fundamentacao", "fundamentacao", "Fundamentação",
     "Lei, súmula e doutrina da Biblioteca para o parágrafo onde está o cursor.", "fundamentacao"),
    ("Qualificacao", "qualificacao", "Qualificação",
     "Monta a qualificação de uma parte a partir dos Cadastros; o que falta entra marcado, nunca inventado.", "qualificacao"),
    ("Perguntar", "perguntar", "Perguntar",
     "Pergunta sobre o documento aberto ou o trecho selecionado, com as fontes do escritório.", "perguntar"),
    ("Revisar", "revisar", "Revisar com agente",
     "Um agente do escritório revisa o trecho; os apontamentos viram comentários e o texto não muda.", "revisar"),
    ("Guardar", "guardar", "Guardar no PAULUS",
     "Guarda uma cópia do documento no Acervo, no cliente ou Serviço escolhido.", "guardar"),
    ("Painel", "painel", "Painel", "Abre o painel do PAVLVS.", "inicio"),
]
# id, rótulo (o do PAVLVS é $NOME), botões
GRUPOS = [("Conferir", "Conferir", ["Conferir"]), ("Inserir", "Inserir", ["Lei", "Fundamentacao", "Qualificacao"]),
          ("Pensar", "Pensar", ["Perguntar", "Revisar"]), ("Paulus", "$NOME", ["Guardar", "Painel"])]
# O menu do botão direito sobre o texto (ContextMenuText): um submenu PAVLVS.
CONTEXTO = [
    ("CtxPerguntar", "perguntar", "Perguntar ao PAULUS sobre isto", "Pergunta sobre o trecho selecionado.",
     "perguntar&amp;origem=selecao"),
    ("CtxConferir", "conferir", "Conferir esta citação", "Confere a lei, súmula ou processo do trecho selecionado.",
     "conferir&amp;origem=selecao"),
    ("CtxRevisar", "revisar", "Revisar com agente", "Revisa o trecho selecionado com um agente do escritório.",
     "revisar&amp;origem=selecao"),
]

# Os desenhos: os mesmos da maquete aprovada (word/prova/maquete.html). Traço
# cinza médio, legível no Office claro e no escuro (o Office não recolore
# ícone de suplemento), e um detalhe no vinho do PAULUS.
TRACO, VINHO = "#7a7a76", "#b0443a"
DESENHOS = {
    "conferir": f'<path d="M5 3.5h9l5 5V20.5H5z" stroke="{TRACO}"/><path d="M14 3.5v5h5" stroke="{TRACO}"/><path d="M8.5 14.5l2.2 2.2 4.8-4.8" stroke="{VINHO}"/>',
    "lei": f'<path d="M4 5.5c2.7-1.3 5.3-1.3 8 0v14c-2.7-1.3-5.3-1.3-8 0z" stroke="{TRACO}"/><path d="M12 5.5c2.7-1.3 5.3-1.3 8 0v14c-2.7-1.3-5.3-1.3-8 0z" stroke="{TRACO}"/><path d="M15 9.5h2.5M15 12.5h2.5" stroke="{VINHO}"/>',
    "fundamentacao": f'<path d="M4 20.5h16M6 17.5h12M7 17.5v-7M12 17.5v-7M17 17.5v-7" stroke="{TRACO}"/><path d="M4.5 10.5L12 4l7.5 6.5z" stroke="{VINHO}"/>',
    "qualificacao": f'<rect x="3" y="5" width="18" height="14" rx="2" stroke="{TRACO}"/><circle cx="9" cy="11" r="2.3" stroke="{VINHO}"/><path d="M5.8 16c.6-1.7 1.8-2.6 3.2-2.6s2.6.9 3.2 2.6M14.5 10h4M14.5 13h3" stroke="{TRACO}"/>',
    "perguntar": f'<path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z" stroke="{TRACO}"/><path d="M10 9.3a2 2 0 1 1 2.6 1.9c-.4.2-.6.5-.6.9v.3M12 14.3v.1" stroke="{VINHO}"/>',
    "revisar": f'<path d="M4 4.5h11v6M4 4.5v15h7" stroke="{TRACO}"/><path d="M7 8.5h5M7 11.5h3" stroke="{TRACO}"/><path d="M14 13.5h7v5h-3.5L15 20.5v-2h-1z" stroke="{VINHO}"/>',
    "guardar": f'<path d="M3.5 13.5l2.5-8h12l2.5 8v6h-17z" stroke="{TRACO}"/><path d="M3.5 13.5h5l1 2h5l1-2h5" stroke="{TRACO}"/><path d="M12 7.5v5M9.8 10.3L12 12.5l2.2-2.2" stroke="{VINHO}"/>',
    "painel": f'<rect x="3.5" y="4.5" width="17" height="15" rx="2" stroke="{TRACO}"/><path d="M14.5 4.5v15" stroke="{TRACO}"/><path d="M16.8 8.5h1.7M16.8 11h1.7" stroke="{VINHO}"/>',
    # A marca: o P do PAVLVS numa coluna, em vinho.
    "marca": f'<path d="M6 20.5V3.5h7a4.5 4.5 0 0 1 0 9H6" stroke="{VINHO}"/><path d="M4 20.5h5" stroke="{VINHO}"/>',
}


def manifesto() -> str:
    por_id = {b[0]: b for b in BOTOES}

    def icone(nome: str, rec: str) -> str:
        return (rec + "<Icon>\n" + "".join(f'{rec}  <bt:Image size="{t}" resid="Ic.{nome}.{t}"/>\n' for t in TAMANHOS)
                + rec + "</Icon>\n")

    def botao(id_: str, rec: str) -> str:
        b = por_id[id_]
        return (f'{rec}<Control xsi:type="Button" id="Paulus.Btn.{id_}">\n'
                f'{rec}  <Label resid="Txt.{id_}"/>\n'
                f'{rec}  <Supertip><Title resid="Txt.{id_}"/><Description resid="Dica.{id_}"/></Supertip>\n'
                + icone(b[1], rec + "  ")
                + f'{rec}  <Action xsi:type="ShowTaskpane"><TaskpaneId>Office.AutoShowTaskpaneWithDocument</TaskpaneId><SourceLocation resid="Url.{id_}"/></Action>\n'
                f'{rec}</Control>\n')

    rec = " " * 14
    grupos = ""
    for gid, _rot, itens in GRUPOS:
        grupos += f'{rec}<Group id="Paulus.G.{gid}">\n{rec}  <Label resid="Grupo.{gid}"/>\n' + icone(por_id[itens[0]][1], rec + "  ")
        grupos += "".join(botao(i, rec + "  ") for i in itens)
        grupos += f"{rec}</Group>\n"

    ctx = (f'{rec}<Control xsi:type="Menu" id="Paulus.Ctx">\n{rec}  <Label resid="Txt.Ctx"/>\n'
           f'{rec}  <Supertip><Title resid="Txt.Ctx"/><Description resid="Dica.Ctx"/></Supertip>\n'
           + icone("marca", rec + "  ") + f"{rec}  <Items>\n")
    for cid, ic, _rot, _dica, _tela in CONTEXTO:
        r2 = rec + "    "
        ctx += (f'{r2}<Item id="Paulus.{cid}">\n{r2}  <Label resid="Txt.{cid}"/>\n'
                f'{r2}  <Supertip><Title resid="Txt.{cid}"/><Description resid="Dica.{cid}"/></Supertip>\n'
                + icone(ic, r2 + "  ")
                + f'{r2}  <Action xsi:type="ShowTaskpane"><TaskpaneId>Office.AutoShowTaskpaneWithDocument</TaskpaneId><SourceLocation resid="Url.{cid}"/></Action>\n'
                f"{r2}</Item>\n")
    ctx += f"{rec}  </Items>\n{rec}</Control>\n"

    r = " " * 8
    nomes = sorted({b[1] for b in BOTOES} | {"marca"})
    imagens = "".join(f'{r}<bt:Image id="Ic.{n}.{t}" DefaultValue="$BASE/word/icones/{n}-{t}.png"/>\n' for n in nomes for t in TAMANHOS)
    urls = "".join(f'{r}<bt:Url id="Url.{b[0]}" DefaultValue="$BASE/word/painel.html?tela={b[4]}"/>\n' for b in BOTOES)
    urls += "".join(f'{r}<bt:Url id="Url.{c[0]}" DefaultValue="$BASE/word/painel.html?tela={c[4]}"/>\n' for c in CONTEXTO)
    curtos = f'{r}<bt:String id="Aba" DefaultValue="$NOME"/>\n{r}<bt:String id="Txt.Ctx" DefaultValue="$NOME"/>\n'
    curtos += "".join(f'{r}<bt:String id="Grupo.{g[0]}" DefaultValue="{g[1]}"/>\n' for g in GRUPOS)
    curtos += "".join(f'{r}<bt:String id="Txt.{b[0]}" DefaultValue="{b[2]}"/>\n' for b in BOTOES)
    curtos += "".join(f'{r}<bt:String id="Txt.{c[0]}" DefaultValue="{c[2]}"/>\n' for c in CONTEXTO)
    longos = f'{r}<bt:String id="Dica.Ctx" DefaultValue="Os comandos do PAVLVS para o trecho selecionado."/>\n'
    longos += "".join(f'{r}<bt:String id="Dica.{b[0]}" DefaultValue="{b[3]}"/>\n' for b in BOTOES)
    longos += "".join(f'{r}<bt:String id="Dica.{c[0]}" DefaultValue="{c[3]}"/>\n' for c in CONTEXTO)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  O manifesto do suplemento do Word (W1). Modelo: src/word_instalar.py troca
  $$ID, $$BASE, $$VERSAO e $$NOME por instalação. Gerado por
  tools/word_suplemento.py: mude a tabela de lá, não este arquivo à mão.
  AddinCommands 1.1 (medido no Word 2021) dá a aba e o menu do botão direito.
  Atalhos de teclado pedem SharedRuntime + KeyboardShortcuts, que o Word 2021
  não tem: não entram.
-->
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
           xmlns:ov="http://schemas.microsoft.com/office/taskpaneappversionoverrides"
           xsi:type="TaskPaneApp">
  <Id>$ID</Id>
  <Version>$VERSAO</Version>
  <ProviderName>PAULUS</ProviderName>
  <DefaultLocale>pt-BR</DefaultLocale>
  <DisplayName DefaultValue="$NOME"/>
  <Description DefaultValue="O PAULUS do escritório dentro do Word: confere citações, insere lei e qualificação e responde sobre o documento."/>
  <IconUrl DefaultValue="$BASE/word/icones/marca-32.png"/>
  <HighResolutionIconUrl DefaultValue="$BASE/word/icones/marca-64.png"/>
  <SupportUrl DefaultValue="https://paulus.ia.br"/>
  <AppDomains>
    <AppDomain>$BASE</AppDomain>
  </AppDomains>
  <Hosts>
    <Host Name="Document"/>
  </Hosts>
  <Requirements>
    <Sets DefaultMinVersion="1.3">
      <Set Name="WordApi" MinVersion="1.3"/>
    </Sets>
  </Requirements>
  <DefaultSettings>
    <SourceLocation DefaultValue="$BASE/word/painel.html?tela=inicio"/>
  </DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/taskpaneappversionoverrides" xsi:type="VersionOverridesV1_0">
    <Hosts>
      <Host xsi:type="Document">
        <DesktopFormFactor>
          <ExtensionPoint xsi:type="PrimaryCommandSurface">
            <CustomTab id="Paulus.Aba">
{grupos}              <Label resid="Aba"/>
            </CustomTab>
          </ExtensionPoint>
          <ExtensionPoint xsi:type="ContextMenu">
            <OfficeMenu id="ContextMenuText">
{ctx}            </OfficeMenu>
          </ExtensionPoint>
        </DesktopFormFactor>
      </Host>
    </Hosts>
    <Resources>
      <bt:Images>
{imagens}      </bt:Images>
      <bt:Urls>
{urls}      </bt:Urls>
      <bt:ShortStrings>
{curtos}      </bt:ShortStrings>
      <bt:LongStrings>
{longos}      </bt:LongStrings>
    </Resources>
  </VersionOverrides>
</OfficeApp>
"""


def icones() -> int:
    from playwright.sync_api import sync_playwright

    pasta = WORD / "icones"
    pasta.mkdir(parents=True, exist_ok=True)
    n = 0
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="msedge")
        pag = nav.new_page(device_scale_factor=1)
        for nome, desenho in DESENHOS.items():
            for t in TAMANHOS:
                # Traço de 1,6 no desenho de 24: ~1 px em 16, ~5 px em 80.
                svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{t}" height="{t}" viewBox="0 0 24 24" fill="none" '
                       f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{desenho}</svg>')
                pag.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
                pag.locator("svg").screenshot(path=str(pasta / f"{nome}-{t}.png"), omit_background=True)
                n += 1
        nav.close()
    return n


if __name__ == "__main__":
    o_que = sys.argv[1:] or ["manifesto", "icones"]
    if "manifesto" in o_que:
        (WORD / "manifesto.xml").write_text(manifesto(), encoding="utf-8", newline="\n")
        print("manifesto:", WORD / "manifesto.xml")
    if "icones" in o_que:
        print("ícones:", icones())
