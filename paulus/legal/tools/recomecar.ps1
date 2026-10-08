<#
  Recomeca o Paulus de desenvolvimento do zero, para testar a primeira abertura.

    .\tools\recomecar.ps1                              # so os dados desta maquina
    .\tools\recomecar.ps1 -Email nome@dominio.com.br   # e tambem a conta PAVLVS por senha desse e-mail, na nuvem
    .\tools\recomecar.ps1 -Abrir                       # e abre o Paulus no fim

  O que apaga em paulus\legal\data: contas, conversas, acervo, preferencias,
  vinculo, chaves e o banco. O que fica: o que o programa baixou (modelos,
  leis, jurisprudencia) e o que vem do repositorio (exemplos, demonstracao).
  Nao toca no Paulus instalado (%LOCALAPPDATA%), que usa outra pasta.

  Com -Email (precisa do wrangler logado: npx wrangler login), apaga na nuvem
  o cadastro por senha desse e-mail (id:conta, e os codigos e erros pendentes)
  e tira do painel /admin a conta da nuvem que nasceu dele. Uma conta que
  entrou pelo Google nao e apagada aqui.
#>
param(
  [string]$Email = "",
  [switch]$Abrir
)
$ErrorActionPreference = "Stop"
$legal = Split-Path -Parent $PSScriptRoot
$dados = Join-Path $legal "data"
$manter = "modelos", "leis", "jurisprudencia", "samples", "test_contracts", "demo", "publico", "extractions", "knowledge_base"

$aberto = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like "*desktop.py*" }
if ($aberto) {
  Write-Host "O Paulus esta aberto. Feche a janela (ou Ctrl+C no terminal dele) e rode de novo." -ForegroundColor Yellow
  exit 1
}

Write-Host "Limpando $dados ..."
Get-ChildItem $dados -Force | Where-Object { $manter -notcontains $_.Name } | Remove-Item -Recurse -Force -Confirm:$false
# As pastas que ficam podem ter lixo de teste dentro, menos o .gitkeep.
foreach ($p in "extractions", "knowledge_base") {
  $c = Join-Path $dados $p
  if (Test-Path $c) { Get-ChildItem $c -Force | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Recurse -Force -Confirm:$false }
}
Write-Host ("Ficou: " + ((Get-ChildItem $dados -Force).Name -join ", ")) -ForegroundColor Green

if ($Email) {
  $Email = $Email.Trim().ToLower()
  $worker = Join-Path (Split-Path -Parent (Split-Path -Parent $legal)) "worker"
  Push-Location $worker
  try {
    $bruto = npx --yes wrangler kv key get --binding APOIOS --remote "id:conta:$Email" --text 2>$null | Out-String
    $i = $bruto.IndexOf("{")
    if ($i -ge 0) {
      $sub = ($bruto.Substring($i) | ConvertFrom-Json).sub
      $sha = [System.Security.Cryptography.SHA256]::Create()
      $hex = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("conta-ia:$sub")) | ForEach-Object { $_.ToString("x2") })
      $conta = $hex.Substring(0, 24)
      npx --yes wrangler kv key delete --binding APOIOS --remote "admin:conta:$conta" 2>$null | Out-Null
      Write-Host "Conta da nuvem $conta tirada do painel."
    } else {
      Write-Host "Nenhum cadastro por senha para $Email na nuvem."
    }
    foreach ($k in "id:conta:", "id:pend:", "id:erros:", "id:rec:") {
      npx --yes wrangler kv key delete --binding APOIOS --remote "$k$Email" 2>$null | Out-Null
    }
    Write-Host "Cadastro por senha de $Email apagado na nuvem: pode criar de novo." -ForegroundColor Green
  } finally {
    Pop-Location
  }
}

if ($Abrir) {
  Set-Location $legal
  & (Join-Path $legal "venv\Scripts\python.exe") (Join-Path $legal "src\desktop.py")
}
