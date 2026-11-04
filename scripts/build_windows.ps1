#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/4] Gerando icone..."
python scripts/make_icon.py

Write-Host "[2/4] Limpando artefatos e empacotando com PyInstaller..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
python -m PyInstaller --noconfirm --clean CryptoVault.spec

$Exe = Resolve-Path "dist\CryptoVault.exe"
$Report = Join-Path $Root "dist\self-test.json"
Write-Host "[3/4] Executando self-test do executavel..."
# O caminho do relatorio vai entre aspas: o diretorio do projeto pode ter espacos.
$Process = Start-Process -FilePath $Exe -ArgumentList @("--self-test", "--report", "`"$Report`"") -Wait -PassThru
if ($Process.ExitCode -ne 0) {
    throw "Self-test do executavel falhou com codigo $($Process.ExitCode)."
}
if (-not (Test-Path $Report)) {
    throw "O executavel nao gerou o relatorio de self-test."
}

Write-Host "[4/4] Gerando checksum..."
$Hash = (Get-FileHash -Algorithm SHA256 $Exe).Hash.ToLowerInvariant()
"$Hash  CryptoVault.exe" | Set-Content -Encoding ASCII "dist\CryptoVault.exe.sha256"
Get-Content "dist\self-test.json"
Write-Host "SHA-256: $Hash"
Write-Host "Executavel: $Exe"
