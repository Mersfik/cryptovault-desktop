#Requires -Version 5.1
<#
.SYNOPSIS
    Cria um atalho do CryptoVault Desktop na Area de Trabalho e/ou Menu Iniciar.

.DESCRIPTION
    O atalho aponta para um executavel real (por padrao dist\CryptoVault.exe) e
    usa o proprio icone embutido no .exe. Nao exige privilegios administrativos
    e nao registra nada em inicializacao automatica.

.PARAMETER Target
    Caminho do executavel. Padrao: <raiz do projeto>\dist\CryptoVault.exe.

.PARAMETER Name
    Nome exibido do atalho. Padrao: "CryptoVault Desktop".

.PARAMETER Location
    Desktop, StartMenu ou Both. Padrao: Desktop.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1 `
        -Target "$env:LOCALAPPDATA\Programs\CryptoVault Desktop\CryptoVault.exe" `
        -Location Both
#>
[CmdletBinding()]
param(
    [string]$Target,
    [string]$Name = "CryptoVault Desktop",
    [ValidateSet("Desktop", "StartMenu", "Both")]
    [string]$Location = "Desktop"
)

$ErrorActionPreference = "Stop"

if (-not $Target) {
    $Target = Join-Path (Split-Path -Parent $PSScriptRoot) "dist\CryptoVault.exe"
}

if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
    throw "Executavel nao encontrado: $Target. Gere o binario com scripts\build_windows.ps1."
}

$Target = (Resolve-Path -LiteralPath $Target).Path
if ([IO.Path]::GetExtension($Target) -ne ".exe") {
    throw "O atalho deve apontar para um .exe, recebido: $Target"
}

$workingDirectory = Split-Path -Parent $Target
$shell = New-Object -ComObject WScript.Shell
$created = New-Object System.Collections.Generic.List[string]

function New-Shortcut {
    param([string]$Directory, [string]$FileName)

    if (-not (Test-Path -LiteralPath $Directory)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }

    $path = Join-Path $Directory $FileName
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $workingDirectory
    $shortcut.IconLocation = "$Target,0"
    $shortcut.Description = "CryptoVault Desktop - criptografia de arquivos"
    $shortcut.WindowStyle = 1
    $shortcut.Save()

    if (-not (Test-Path -LiteralPath $path)) {
        throw "Falha ao criar o atalho: $path"
    }
    $created.Add($path)
}

if ($Location -in @("Desktop", "Both")) {
    New-Shortcut -Directory ([Environment]::GetFolderPath("Desktop")) -FileName "$Name.lnk"
}

if ($Location -in @("StartMenu", "Both")) {
    New-Shortcut -Directory ([Environment]::GetFolderPath("Programs")) -FileName "$Name.lnk"
}

Write-Host "Atalho(s) criado(s) para: $Target"
foreach ($path in $created) {
    Write-Host "  $path"
}
