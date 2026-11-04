#Requires -Version 5.1
<#
.SYNOPSIS
    Instala o CryptoVault Desktop por usuario, sem privilegios administrativos.

.DESCRIPTION
    Alternativa ao instalador Inno Setup para ambientes em que o Smart App
    Control bloqueia executaveis de instalacao nao assinados.

    O que este script faz:
      1. Copia CryptoVault.exe e a documentacao para
         %LOCALAPPDATA%\Programs\CryptoVault Desktop.
      2. Cria atalho no Menu Iniciar e, opcionalmente, na Area de Trabalho.
      3. Registra a entrada em "Aplicativos e recursos" (HKCU), com
         desinstalador funcional.
      4. Copia o desinstalador para a pasta instalada.

    Nada e gravado em HKLM, nenhum servico e criado, nenhuma inicializacao
    automatica e registrada e nenhum privilegio elevado e solicitado.

.PARAMETER Source
    Caminho do CryptoVault.exe. Se omitido, procura ..\dist\CryptoVault.exe
    (execucao a partir do repositorio) ou .\CryptoVault.exe (pacote ZIP).

.PARAMETER NoDesktopShortcut
    Nao cria atalho na Area de Trabalho.

.PARAMETER Launch
    Abre a aplicacao ao final da instalacao.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -NoDesktopShortcut
#>
[CmdletBinding()]
param(
    [string]$Source,
    [switch]$NoDesktopShortcut,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

$AppName = "CryptoVault Desktop"
$AppPublisher = "Mersfik"
$AppExeName = "CryptoVault.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\CryptoVault Desktop"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CryptoVaultDesktop"
$Docs = @("README.md", "LICENSE", "SECURITY.md", "CRYPTOGRAPHY.md", "THREAT_MODEL.md")

function Resolve-SourceExe {
    param([string]$Candidate)

    if ($Candidate) {
        if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            throw "Executavel nao encontrado: $Candidate"
        }
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $options = @(
        (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\$AppExeName"),
        (Join-Path $PSScriptRoot $AppExeName)
    )
    foreach ($option in $options) {
        if (Test-Path -LiteralPath $option -PathType Leaf) {
            return (Resolve-Path -LiteralPath $option).Path
        }
    }
    throw "Executavel nao encontrado. Informe -Source <caminho do $AppExeName>."
}

function New-AppShortcut {
    param([string]$Directory, [string]$Target, [string]$WorkingDirectory)

    if (-not (Test-Path -LiteralPath $Directory)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }
    $path = Join-Path $Directory "$AppName.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.IconLocation = "$Target,0"
    $shortcut.Description = "CryptoVault Desktop - criptografia de arquivos"
    $shortcut.Save()
    return $path
}

$sourceExe = Resolve-SourceExe -Candidate $Source
$versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($sourceExe)
$version = if ($versionInfo.ProductVersion) { $versionInfo.ProductVersion } else { "1.0.0" }

Write-Host "Instalando $AppName $version"
Write-Host "  origem : $sourceExe"
Write-Host "  destino: $InstallDir"

if (Test-Path -LiteralPath $InstallDir) {
    $running = Get-Process -Name "CryptoVault" -ErrorAction SilentlyContinue
    if ($running) {
        throw "Feche o CryptoVault Desktop antes de instalar novamente."
    }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $InstallDir $AppExeName) -Force

$installerRoot = Split-Path -Parent $PSScriptRoot
foreach ($doc in $Docs) {
    foreach ($base in @($PSScriptRoot, $installerRoot)) {
        $candidate = Join-Path $base $doc
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Copy-Item -LiteralPath $candidate -Destination (Join-Path $InstallDir $doc) -Force
            break
        }
    }
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall.ps1") `
    -Destination (Join-Path $InstallDir "uninstall.ps1") -Force

$targetExe = Join-Path $InstallDir $AppExeName
$startMenu = New-AppShortcut `
    -Directory ([Environment]::GetFolderPath("Programs")) `
    -Target $targetExe `
    -WorkingDirectory $InstallDir
Write-Host "  atalho : $startMenu"

if (-not $NoDesktopShortcut) {
    $desktop = New-AppShortcut `
        -Directory ([Environment]::GetFolderPath("Desktop")) `
        -Target $targetExe `
        -WorkingDirectory $InstallDir
    Write-Host "  atalho : $desktop"
}

$sizeKb = [int](((Get-ChildItem -LiteralPath $InstallDir -Recurse -File |
    Measure-Object -Property Length -Sum).Sum) / 1KB)
$uninstallCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""

if (-not (Test-Path $UninstallKey)) {
    New-Item -Path $UninstallKey -Force | Out-Null
}
$uninstallValues = [ordered]@{
    DisplayName          = $AppName
    DisplayVersion       = $version
    Publisher            = $AppPublisher
    DisplayIcon          = "$targetExe,0"
    InstallLocation      = $InstallDir
    UninstallString      = $uninstallCommand
    QuietUninstallString = "$uninstallCommand -Quiet"
    EstimatedSize        = $sizeKb
    InstallDate          = (Get-Date).ToString("yyyyMMdd")
    NoModify             = 1
    NoRepair             = 1
}
foreach ($name in $uninstallValues.Keys) {
    New-ItemProperty -Path $UninstallKey -Name $name -Value $uninstallValues[$name] `
        -PropertyType ($(if ($uninstallValues[$name] -is [int]) { "DWord" } else { "String" })) `
        -Force | Out-Null
}

Write-Host ""
Write-Host "Instalacao concluida."
Write-Host "  aplicativo         : $targetExe"
Write-Host "  desinstalar        : Configuracoes > Aplicativos ou $InstallDir\uninstall.ps1"
Write-Host "  dados do usuario   : $env:LOCALAPPDATA\CryptoVault (preservados na desinstalacao)"

if ($Launch) {
    Start-Process -FilePath $targetExe
}
