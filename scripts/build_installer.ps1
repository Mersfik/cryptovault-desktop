#Requires -Version 5.1
<#
.SYNOPSIS
    Gera o executavel e o instalador do CryptoVault Desktop.

.DESCRIPTION
    1. Executa scripts\build_windows.ps1 (icone, PyInstaller, self-test, checksum).
    2. Localiza o Inno Setup 6 (ISCC.exe) e compila installer\cryptovault.iss.
    3. Confere os artefatos gerados em dist\ e release\.

    Nenhum caminho absoluto do projeto fica embutido nos artefatos: o instalador
    usa caminhos relativos ao diretorio do projeto durante a compilacao e
    caminhos padrao do Windows no destino.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#>
[CmdletBinding()]
param(
    [string]$Iscc
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/2] Gerando executavel..."
& (Join-Path $PSScriptRoot "build_windows.ps1")

Write-Host "[2/2] Compilando instalador..."

if (-not $Iscc) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $Iscc) {
    throw "Inno Setup 6 nao encontrado. Instale com: winget install --id JRSoftware.InnoSetup -e"
}

$iss = Join-Path $Root "installer\cryptovault.iss"
& $Iscc $iss
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao compilar o instalador (codigo $LASTEXITCODE)."
}

$setup = Get-ChildItem (Join-Path $Root "release") -Filter "CryptoVault-Desktop-*-setup.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $setup) {
    throw "O instalador nao foi gerado em release\."
}

Write-Host ""
Write-Host "Executavel: $((Resolve-Path 'dist\CryptoVault.exe').Path)"
Write-Host "Instalador: $($setup.FullName)"
Write-Host ("Tamanho do instalador: {0:N1} MB" -f ($setup.Length / 1MB))
