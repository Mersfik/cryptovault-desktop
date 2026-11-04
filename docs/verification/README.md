# Evidências de validação — CryptoVault Desktop 1.0.0

Registro das execuções reais feitas em **2026-11-03** no ambiente descrito em
[`environment.txt`](environment.txt). Os arquivos desta pasta são a saída bruta
dos comandos; não são resultados simulados.

## Resumo

| Verificação | Resultado | Arquivo |
| --- | --- | --- |
| Suíte de testes | **121 passed, 4 skipped** | [`pytest.txt`](pytest.txt) |
| Cobertura de `cryptovault` | **83%** (linhas/ramos) | [`pytest.txt`](pytest.txt) |
| Ruff (lint) | **All checks passed** | [`ruff-check.txt`](ruff-check.txt) |
| Ruff (formatação) | **63 files already formatted** | [`ruff-format.txt`](ruff-format.txt) |
| Bandit | **0 issues** em 5.846 linhas | [`bandit.txt`](bandit.txt) |
| pip-audit (runtime) | **No known vulnerabilities found** | [`pip-audit.txt`](pip-audit.txt) |
| pip-audit (desenvolvimento) | **No known vulnerabilities found** | [`pip-audit-dev.txt`](pip-audit-dev.txt) |
| Self-test do código | **6/6 checks true** | [`self-test-source.json`](self-test-source.json) |
| Self-test do `.exe` | **6/6 checks true** | [`self-test-exe.json`](self-test-exe.json) |
| CI (GitHub Actions) | **verde**: 3.12, 3.13 e build Windows | [`ci.md`](ci.md) |
| Instalador e atalho | **instala, inicia e desinstala** | [`installer.md`](installer.md) |

## Ambiente

```text
Windows 11 Home build 26300 (win32 x64)
Python 3.13.17
PySide6 6.9.3
cryptography 50.0.2
pytest 9.2.0
Ruff 0.17.3
Bandit 1.9.4
pip-audit 2.10.1
PyInstaller 6.22.3
```

## Comandos executados

```powershell
python -m pytest --cov=cryptovault --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m bandit -r cryptovault
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
python -m cryptovault --self-test --report docs\verification\self-test-source.json
Start-Process -FilePath dist\CryptoVault.exe `
  -ArgumentList "--self-test --report `"$PWD\docs\verification\self-test-exe.json`"" `
  -Wait -PassThru
```

## Testes ignorados

Os quatro testes ignorados não são falhas:

1. `tests/test_engine.py:228` — permissões POSIX (`0600`) não têm a mesma
   semântica no Windows.
2. `tests/test_paths.py:77` — criação de symlink indisponível no ambiente.
3. `tests/test_paths.py:89` — criação de symlink indisponível no ambiente.
4. `tests/test_paths.py:129` — permissões POSIX (`0600`) no Windows.

Em Linux/macOS, esses testes devem executar e validar as permissões/symlinks.
No Windows, a proteção de caminhos continua coberta por validação de tipo,
`lstat`, `O_NOFOLLOW` quando disponível e pelos demais testes.

## Cobertura

A cobertura é calculada com `branch = true` e exclui `cryptovault/app.py` e
`cryptovault/__main__.py` (bootstrap/CLI). O total é **83%**. Os módulos mais
críticos estão em 95–99%:

| Módulo | Cobertura |
| --- | ---: |
| `crypto/engine.py` | 96% |
| `crypto/format.py` | 87% |
| `crypto/kdf.py` | 95% |
| `domain/models.py` | 97% |
| `infrastructure/history.py` | 98% |
| `infrastructure/logging_setup.py` | 97% |
| `infrastructure/settings.py` | 91% |
| `security/passwords.py` | 87% |
| `security/paths.py` | 76% |
| `application/service.py` | 84% |
| `ui/workers.py` | 28% |
| `ui/controller.py` | 66% |

A menor cobertura em `ui/workers.py` reflete caminhos de erro defensivos e a
dificuldade de exercitar `QRunnable` em testes unitários; os fluxos reais de UI e
o self-test cobrem o caminho feliz e falhas de autenticação. Uma evolução
recomendada é adicionar testes de integração do worker com `qtbot.waitSignal`.

## Bandit

```text
Test results:
    No issues identified.

Code scanned:
    Total lines of code: 5846
    Total lines skipped (#nosec): 0
    Total potential issues skipped due to specifically being disabled: 0

Total issues (by severity): 0 em todas as severidades
```

## pip-audit

Runtime (`requirements.txt`):

```text
No known vulnerabilities found
```

Desenvolvimento (`requirements-dev.txt`):

```text
No known vulnerabilities found
```

O `pip-audit` escreve a mensagem em `stderr`; por isso a captura foi feita com
redirecionamento via `cmd /c`. O código de saída foi **0** em ambos os casos. A
auditoria de runtime cobre o que é distribuído no executável; a de
desenvolvimento cobre as ferramentas de teste/build.

## Self-test

Relatório do código:

```json
{
  "version": "1.0.0",
  "python": "3.13.17",
  "checks": {
    "encrypt": true,
    "verify_authentic": true,
    "decrypt": true,
    "tamper_rejected": true,
    "wrong_password_rejected": true,
    "no_service_residue": true
  },
  "success": true
}
```

O mesmo relatório foi produzido pelo executável `dist/CryptoVault.exe`. O
self-test usa `tempfile`, uma senha aleatória e um payload de 2 MiB + 317 bytes;
não acessa os dados do usuário.

## Limitações desta validação

- Execução em uma única máquina Windows; não houve matriz Linux/macOS.
- Testes de symlink e permissões POSIX foram ignorados.
- Não houve auditoria criptográfica independente, teste de penetração ou revisão
  formal do formato.
- `pip-audit` é um instantâneo; novas vulnerabilidades podem surgir depois.
- O executável não é assinado e o build não é reproduzível de forma atestada.
- O CI foi executado no GitHub Actions após a publicação: testes em Python 3.12
  e 3.13 e build Windows com self-test aprovados. Detalhes e links das
  execuções estão em [`ci.md`](ci.md).
- Cobertura mede execução de código, não corretude criptográfica.
- A UI foi testada com `pytest-qt` e com screenshots reais; não houve teste
  manual prolongado em múltiplos monitores/DPI.

## Como reproduzir

```powershell
python -m pip install -e ".[dev]"
python -m pytest --cov=cryptovault --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m bandit -r cryptovault
python -m pip_audit -r requirements.txt
python -m cryptovault --self-test --report "$env:TEMP\self-test.json"
```

Consulte também [`../screenshots/`](../screenshots/) para as capturas geradas por
operações reais e [`../../README.md`](../../README.md) para instruções de uso.
