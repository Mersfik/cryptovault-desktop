# Evidências de instalação e atalho — CryptoVault Desktop 1.0.0

Execuções reais em **2026-11-03**, Windows 11 Home build 26300, no ambiente
descrito em [`environment.txt`](environment.txt).

## 1. Executável

| Verificação | Resultado |
| --- | --- |
| `dist\CryptoVault.exe` gerado pelo PyInstaller | sim, one-file |
| Subsistema PE | `2` (GUI — sem janela de console) |
| `ProductName` / `FileVersion` | `CryptoVault Desktop` / `1.0.0.0` |
| `CompanyName` / `OriginalFilename` | `Mersfik` / `CryptoVault.exe` |
| Ícone embutido | `cryptovault/resources/logo.ico` (16–256 px) |
| Self-test do executável | **6/6 checks true**, código de saída 0 |

Cópia do `.exe` para fora do projeto, executada com `C:\Windows` como diretório
de trabalho: self-test passou com `success: true`, confirmando que o binário não
depende do diretório de desenvolvimento nem do Python instalado.

## 2. Atalho na Área de Trabalho

`scripts/create_shortcut.ps1` gerou
`C:\Users\<usuario>\OneDrive\Área de Trabalho\CryptoVault Desktop.lnk` com:

```text
TargetPath       : ...\dist\CryptoVault.exe
Arguments        : (vazio)
WorkingDirectory : ...\dist
IconLocation     : ...\dist\CryptoVault.exe,0
WindowStyle      : 1 (normal)
```

Dois cliques no atalho abriram a aplicação: processo `CryptoVault` com título
`CryptoVault Desktop`, sem janela de console, encerrado por `CloseMainWindow()`
sem erro.

## 3. Instalador Inno Setup

`scripts/build_installer.ps1` compilou `installer/cryptovault.iss` em
`release/CryptoVault-Desktop-1.0.0-setup.exe` (**49,8 MB**), com instalação por
usuário (`PrivilegesRequired=lowest`), atalho de Área de Trabalho opcional,
atalho de Menu Iniciar, `LicenseFile` e desinstalador registrado.

**Limitação real deste ambiente:** a execução do instalador foi bloqueada pelo
**Smart App Control** do Windows, que está em modo de bloqueio:

```text
HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy
  VerifiedAndReputablePolicyState = 1
```

O bloqueio não é específico deste projeto. Um instalador Inno mínimo
("hello world", apenas copiando `notepad.exe`) falhou com a mesma mensagem do
Windows: *"foi bloqueado pela política do Device Guard da sua organização"*.
O `setup.exe` do CryptoVault retorna código 1 sem gerar log, antes de qualquer
ação de instalação.

Ou seja: o artefato compila corretamente, mas **não pôde ser executado nesta
máquina**. Em máquinas com Smart App Control desativado, ou com o instalador
assinado, o fluxo é o padrão do Inno Setup. O projeto **não** desativa políticas
de segurança do sistema.

## 4. Instalador por script (testado de ponta a ponta)

`installer/install.ps1` foi executado e validado por ciclos completos de
instalação e desinstalação.

| Verificação | Resultado |
| --- | --- |
| Destino | `%LOCALAPPDATA%\Programs\CryptoVault Desktop` |
| Arquivos instalados | `CryptoVault.exe`, `README.md`, `LICENSE`, `SECURITY.md`, `CRYPTOGRAPHY.md`, `THREAT_MODEL.md`, `uninstall.ps1` |
| Hash do `.exe` instalado | idêntico ao de `dist\CryptoVault.exe` |
| Atalho no Menu Iniciar | criado, aponta para o `.exe` instalado |
| Atalho na Área de Trabalho | criado; `-NoDesktopShortcut` não cria (verificado) |
| Registro em "Aplicativos e recursos" | `DisplayName`, `DisplayVersion 1.0.0`, `Publisher`, `InstallLocation`, `EstimatedSize`, `UninstallString`, `NoModify`, `NoRepair` |
| Execução pelo atalho instalado | janela `CryptoVault Desktop` aberta, sem console |
| Privilégios | nenhum (apenas `HKCU`; nenhum `HKLM`, serviço ou tarefa agendada) |

Desinstalação (`uninstall.ps1`, o mesmo comando registrado no Windows):

| Item | Antes | Depois |
| --- | --- | --- |
| Pasta instalada | existia | **removida** |
| Atalho da Área de Trabalho | existia | **removido** |
| Atalho do Menu Iniciar | existia | **removido** |
| Chave `HKCU\...\Uninstall\CryptoVaultDesktop` | existia | **removida** |
| `%LOCALAPPDATA%\CryptoVault` (histórico, configurações, logs) | existia | **preservado** |

Código de saída 0 em todos os ciclos. `-RemoveUserData` remove também os dados
do usuário, por escolha explícita.

## 5. O que não foi possível testar

- **Reinício do Windows**: não houve reboot. A instalação não usa variáveis de
  ambiente, unidades mapeadas, `PATH` ou Python, e o `.exe` já foi validado fora
  do diretório do projeto, mas a persistência após reboot não foi observada.
- **Instalador Inno Setup em execução real**: bloqueado pela política do Windows
  descrita acima.
- **Assinatura de código**: o binário e o instalador não são assinados.
- **DPI/múltiplos monitores**: não avaliado nesta rodada.

## Como reproduzir

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
powershell -ExecutionPolicy Bypass -File installer\install.ps1
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\CryptoVault Desktop\uninstall.ps1"
```
