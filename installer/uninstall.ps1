#Requires -Version 5.1
<#
.SYNOPSIS
    Desinstala o CryptoVault Desktop instalado por installer\install.ps1.

.DESCRIPTION
    Remove o executavel, a documentacao, os atalhos e a entrada de
    "Aplicativos e recursos". Os dados do usuario em
    %LOCALAPPDATA%\CryptoVault (historico, configuracoes e logs) sao
    preservados, a menos que -RemoveUserData seja informado.

.PARAMETER InstallDir
    Pasta de instalacao. Padrao: a pasta deste script.

.PARAMETER Quiet
    Nao exibe mensagens.

.PARAMETER RemoveUserData
    Remove tambem %LOCALAPPDATA%\CryptoVault (historico e configuracoes).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File uninstall.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File uninstall.ps1 -Quiet -RemoveUserData
#>
[CmdletBinding()]
param(
    [string]$InstallDir,
    [switch]$Quiet,
    [switch]$RemoveUserData,
    [switch]$FromTemp
)

$ErrorActionPreference = "Stop"

if (-not $InstallDir) {
    if (-not $PSCommandPath) {
        throw "Nao foi possivel determinar a pasta de instalacao. Informe -InstallDir."
    }
    $InstallDir = Split-Path -Parent $PSCommandPath
}

$AppName = "CryptoVault Desktop"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CryptoVaultDesktop"

function Write-Status {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host $Message
    }
}

if (-not (Test-Path -LiteralPath $InstallDir)) {
    Write-Status "Pasta de instalacao nao encontrada: $InstallDir"
    exit 1
}

# Encerra a aplicacao para liberar os arquivos.
$running = Get-Process -Name "CryptoVault" -ErrorAction SilentlyContinue
if ($running) {
    Write-Status "Encerrando o CryptoVault Desktop..."
    foreach ($process in $running) {
        if (-not $process.HasExited) {
            $process.CloseMainWindow() | Out-Null
        }
    }
    Start-Sleep -Seconds 3
    Get-Process -Name "CryptoVault" -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not $_.HasExited) { $_.Kill() }
    }
    Start-Sleep -Seconds 1
}

# O proprio script pode estar dentro da pasta que sera removida. Nesse caso ele
# se copia para %TEMP% e continua a partir de la.
$scriptPath = $PSCommandPath
if (-not $FromTemp -and $scriptPath) {
    $normalizedDir = (Resolve-Path -LiteralPath $InstallDir).Path.TrimEnd("\")
    $normalizedScript = (Resolve-Path -LiteralPath $scriptPath).Path
    if ($normalizedScript.StartsWith($normalizedDir, [StringComparison]::OrdinalIgnoreCase)) {
        $tempCopy = Join-Path $env:TEMP "cryptovault-uninstall-$([guid]::NewGuid().ToString('N')).ps1"
        Copy-Item -LiteralPath $normalizedScript -Destination $tempCopy -Force
        $arguments = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$tempCopy`"",
            "-InstallDir", "`"$normalizedDir`"", "-FromTemp"
        )
        if ($Quiet) { $arguments += "-Quiet" }
        if ($RemoveUserData) { $arguments += "-RemoveUserData" }
        $child = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Wait -PassThru
        Remove-Item -LiteralPath $tempCopy -Force -ErrorAction SilentlyContinue
        exit $child.ExitCode
    }
}

Write-Status "Removendo atalhos..."
$shortcuts = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk")
)
foreach ($shortcut in $shortcuts) {
    if (Test-Path -LiteralPath $shortcut) {
        Remove-Item -LiteralPath $shortcut -Force
        Write-Status "  removido: $shortcut"
    }
}

Write-Status "Removendo registro de desinstalacao..."
if (Test-Path $UninstallKey) {
    Remove-Item -Path $UninstallKey -Recurse -Force
}

Write-Status "Removendo arquivos de $InstallDir..."
Remove-Item -LiteralPath $InstallDir -Recurse -Force

if ($RemoveUserData) {
    $dataDir = Join-Path $env:LOCALAPPDATA "CryptoVault"
    if (Test-Path -LiteralPath $dataDir) {
        Write-Status "Removendo dados do usuario em $dataDir..."
        Remove-Item -LiteralPath $dataDir -Recurse -Force
    }
} else {
    Write-Status "Dados do usuario preservados em $env:LOCALAPPDATA\CryptoVault"
}

Write-Status "Desinstalacao concluida."
exit 0
