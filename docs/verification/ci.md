# Evidências de CI — GitHub Actions

Execuções reais do workflow [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
no repositório <https://github.com/Mersfik/cryptovault-desktop>, em 2026-11-03.

## Execuções

| Execução | Ref | Evento | Resultado | Duração |
| --- | --- | --- | --- | --- |
| [41680514244](https://github.com/Mersfik/cryptovault-desktop/actions/runs/41680514244) | `main` @ `4c8c3fb` | push | **falha** | 1m30s |
| [41681041432](https://github.com/Mersfik/cryptovault-desktop/actions/runs/41681041432) | `main` @ `4172d31` | push | **sucesso** | 2m03s |
| [41681829074](https://github.com/Mersfik/cryptovault-desktop/actions/runs/41681829074) | `v1.0.0` @ `e8e4393` | tag | **sucesso** | 5m32s |

## O que a primeira falha revelou

A execução `41680514244` reprovou os dois jobs de teste no passo `Ruff (lint)`,
com 13 ocorrências de `I001` (bloco de import fora de ordem) em `tests/` e
`scripts/`.

A causa não estava nos imports: a regra `CryptoVault/` do `.gitignore` tinha
como alvo a pasta de dados local do aplicativo, mas o Git no Windows compara
caminhos sem diferenciar maiúsculas de minúsculas. O pacote `cryptovault/`
inteiro ficou fora do commit inicial. Sem a pasta no checkout, o Ruff classificou
`cryptovault` como dependência de terceiros e passou a exigir outra ordenação de
imports.

Correção em `4172d31`: remoção da regra ambígua e versionamento dos 50 arquivos
do pacote. A execução seguinte passou.

## Estado da execução da tag `v1.0.0`

| Job | Resultado |
| --- | --- |
| Testes (Python 3.12) | sucesso |
| Testes (Python 3.13) | sucesso |
| Build Windows | sucesso |

O job `Build Windows` executa `scripts/build_windows.ps1`, que gera o ícone,
empacota com PyInstaller, roda `CryptoVault.exe --self-test` e publica os
artefatos `dist/CryptoVault.exe`, `dist/CryptoVault.exe.sha256` e
`dist/self-test.json`.

## Relação com os artefatos da release

O executável anexado à release é o **binário validado localmente**, cujo SHA-256
está em `SHA256SUMS.txt` e foi conferido após o upload. O build do CI é uma
compilação independente e, como o empacotamento do PyInstaller não é reprodutível
de forma atestada, produz um binário com hash diferente — ele serve como
verificação de que o projeto compila e passa no self-test a partir do código
versionado, não como origem do arquivo distribuído.

## Limitações

- O CI roda apenas em `windows-latest`; não há matriz Linux/macOS.
- Os testes de symlink e de permissões POSIX continuam sendo ignorados no
  Windows, tanto localmente quanto no CI.
- Os jobs usam as actions `v7`; avisos futuros de depreciação devem ser tratados
  como manutenção normal.
