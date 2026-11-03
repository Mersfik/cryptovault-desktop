# Contribuindo — CryptoVault Desktop

Obrigado pelo interesse. Este projeto lida com criptografia e dados sensíveis;
contribuições são bem-vindas desde que preservem as garantias descritas em
[CRYPTOGRAPHY.md](CRYPTOGRAPHY.md) e [THREAT_MODEL.md](THREAT_MODEL.md).

## 1. Código de conduta

Espera-se respeito, crítica técnica construtiva e ausência de assédio. Não
publique dados reais de terceiros, senhas, chaves ou arquivos pessoais em issues,
testes, exemplos, screenshots ou commits.

## 2. Pré-requisitos

- Windows 10/11 (alvo principal) ou Linux/macOS para desenvolvimento.
- Python **3.12 ou 3.13**.
- Git (para clonar e enviar PRs).
- PowerShell 5.1+ para o script de build no Windows.

O ambiente validado do projeto: Windows 11, Python 3.13.17, PySide6 6.9.3,
`cryptography` 50.0.2, pytest 9.2.0.

## 3. Configuração local

```powershell
git clone https://github.com/Mersfik/cryptovault-desktop.git
cd cryptovault-desktop

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python -m cryptovault
```

Em Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m cryptovault
```

Alternativa sem instalar o pacote:

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "."
python -m cryptovault
```

### Dados de desenvolvimento

Use um diretório isolado para não misturar com seus dados reais:

```powershell
python -m cryptovault --data-dir "$env:TEMP\cryptovault-dev"
```

O app cria `settings.json`, `history.db`, `logs/` e o lock nesse diretório.

## 4. Estrutura e regras de arquitetura

Leia [ARCHITECTURE.md](ARCHITECTURE.md). Regras não negociáveis:

1. `cryptovault/crypto/`, `domain/`, `security/` e `application/` **não** importam
   PySide6.
2. `domain/` não importa `cryptography`, `sqlite3`, `logging` ou Qt.
3. A UI não executa criptografia na thread principal.
4. Nenhuma saída final é publicada antes de validar todas as tags.
5. Nenhuma senha, chave, conteúdo ou caminho completo vai para logs/histórico.
6. Não adicione ECB, DES/3DES, RC4, SHA-1, MD5, `eval`, `exec` ou `shell=True`.
7. Não adicione configuração que reduza KDF, tag, nonce ou validação.
8. Toda correção de segurança precisa de teste de regressão.

## 5. Estilo de código

- Python 3.12+, tipagem moderna (`from __future__ import annotations`).
- Ruff com `line-length = 100`, aspas duplas, imports ordenados.
- Identificadores em inglês; textos de UI e mensagens de usuário em português-BR.
- Dataclasses `frozen=True, slots=True` para valores imutáveis.
- Erros de domínio devem herdar de `CryptoVaultError` e fornecer `user_message`
  seguro.
- Não use `print` no runtime; use o logger estruturado.
- Evite comentários óbvios; documente decisões e invariantes.
- Mantenha funções pequenas e dependências explícitas.

Formatar e verificar:

```powershell
python -m ruff format .
python -m ruff check .
python -m ruff format --check .
```

## 6. Testes

```powershell
python -m pytest -q
python -m pytest -q --cov=cryptovault --cov-report=term-missing
python -m pytest -q -m "not ui"
```

Marcadores disponíveis:

- `integration` — integração entre camadas;
- `security` — foco em segurança;
- `ui` — interface com `pytest-qt`;
- `slow` — testes mais demorados.

### O que testar

- **Formato:** layout, parser, limites, nonce, AAD, truncamento, flags.
- **KDF:** determinismo, salt, parâmetros inválidos, comparação.
- **Senhas:** mínimo/máximo, qualidade, limpeza de `Secret`.
- **Motor:** round-trip em tamanhos de fronteira, senha errada, adulteração de
  tag/ciphertext/header, sem saída parcial, cancelamento, overwrite, progresso.
- **Caminhos:** sanitização, symlink, arquivo não regular, atomicidade,
  permissões.
- **Histórico:** filtros, retenção, ordenação, redação, banco inválido.
- **Configurações:** defaults, normalização, migração, JSON inválido.
- **Logs:** JSON, redação, controles, exceções, allowlist.
- **Serviço:** integração, histórico, gate, segredo não proprietário.
- **UI:** navegação, revelação de senha, fluxos reais, filtros, configurações,
  estado ocupado.

Use `tmp_path` e `pytest-qt`; nunca use dados reais. Testes de symlink/permissão
POSIX são ignorados no Windows e devem continuar assim.

Resultado esperado na versão 1.0.0:

```text
116 passed, 4 skipped
cobertura total: 83% (excluindo app.py e __main__.py)
```

Uma mudança que reduza cobertura de forma relevante deve ser justificada no PR.

## 7. Segurança estática e dependências

```powershell
python -m bandit -r cryptovault -q
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
```

- `bandit` deve ficar sem achados (B101 é ignorado por causa de asserts).
- `pip-audit` deve ficar sem vulnerabilidades conhecidas.
- Se atualizar uma dependência, rode a suíte completa e registre o resultado em
  `docs/verification/`.
- Não fixe versões inseguras para “fazer o teste passar”.

## 8. Self-test e execução

```powershell
python -m cryptovault --version
python -m cryptovault --self-test --report "$env:TEMP\self-test.json"
Get-Content "$env:TEMP\self-test.json"
```

O self-test não toca nos dados do usuário (usa `tempfile`) e deve passar com
todos os checks `true`.

## 9. Build Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

O script:

1. gera `cryptovault/resources/logo.ico` e `logo.png`;
2. remove `build/` e `dist/`;
3. executa PyInstaller com `CryptoVault.spec`;
4. executa o self-test do `.exe` e falha se necessário;
5. grava `dist/CryptoVault.exe.sha256`.

Requisitos: `pyinstaller>=6.11,<7`. O binário é one-file, sem console, e não é
assinado. Se alterar recursos, ícone, versão ou `CryptoVault.spec`, rode o build
e o self-test antes do PR.

## 10. Screenshots

```powershell
python scripts/generate_screenshots.py
```

O script usa uma sessão Qt isolada, executa operações criptográficas reais em
`C:\Users\Public\CryptoVaultDemo` e grava as imagens em `docs/screenshots/`.
Não use dados pessoais. No Windows, o modo nativo é necessário porque o modo
`offscreen` pode não ter fontes.

## 11. CI (GitHub Actions)

O workflow `.github/workflows/ci.yml` executa em `windows-latest` com Python 3.12
e 3.13:

1. instala dependências de desenvolvimento;
2. `ruff check` e `ruff format --check`;
3. `bandit`;
4. `pip-audit`;
5. `pytest` com cobertura;
6. upload do relatório de cobertura como artefato.

Em tags `v*`, um job adicional constrói o executável, roda o self-test e publica
o artefato e o checksum. O workflow não assina o binário.

Para reproduzir localmente:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m bandit -r cryptovault -q
python -m pip_audit -r requirements.txt
python -m pytest -q --cov=cryptovault --cov-report=term-missing
```

## 12. Fluxo de contribuição

1. Abra uma issue descrevendo o problema/objetivo (exceto vulnerabilidades, que
   seguem [SECURITY.md](SECURITY.md)).
2. Crie um branch: `feat/...`, `fix/...`, `docs/...` ou `test/...`.
3. Escreva o teste primeiro quando possível.
4. Implemente a menor mudança que resolve o problema.
5. Rode a suíte, Ruff, Bandit e pip-audit.
6. Atualize a documentação afetada (`README`, `ARCHITECTURE`, `CRYPTOGRAPHY`,
   `THREAT_MODEL`, `OWASP_MAPPING`, `SECURITY`).
7. Abra o PR com:
   - resumo e motivação;
   - riscos/impacto de segurança;
   - comandos e resultados dos testes;
   - screenshots, se mudar a UI;
   - checklist abaixo.

### Checklist do PR

- [ ] A mudança mantém as camadas e não importa Qt no núcleo.
- [ ] Nenhum segredo/caminho completo em log, histórico ou teste.
- [ ] Nenhuma saída parcial é publicada em erro/cancelamento.
- [ ] Testes novos cobrem o comportamento e casos de falha.
- [ ] `pytest` passa (116+ passed, skips esperados).
- [ ] `ruff check` e `ruff format --check` passam.
- [ ] `bandit` sem achados.
- [ ] `pip-audit` sem vulnerabilidades conhecidas.
- [ ] Documentação e screenshots atualizados.
- [ ] Nenhum arquivo gerado (`build/`, `dist/`, `.coverage`, caches) no commit.

## 13. Versionamento e release

- Versão em `cryptovault/__init__.py` e `pyproject.toml` deve coincidir.
- Atualize `README.md` com resultados reais e screenshots.
- Atualize `CHANGELOG` se existir (não incluído nesta versão).
- Gere o build, o self-test, o checksum e os ZIPs de release.
- Verifique o conteúdo dos ZIPs antes de publicar.
- Nunca publique uma release sem o self-test do binário passando.
- Comunique claramente que o executável não é assinado.

## 14. Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a MIT, conforme
[LICENSE](LICENSE).

## 15. Dúvidas

Abra uma issue de discussão (não de segurança) com:
- objetivo;
- comportamento atual e esperado;
- versão e ambiente;
- logs sanitizados, se aplicável.

Obrigado por ajudar a manter o CryptoVault simples, auditável e seguro.
