# Mapeamento OWASP — CryptoVault Desktop

Este documento relaciona os controles implementados ao **OWASP Top 10 (2021)** e
a capítulos selecionados do **OWASP ASVS 4.0.3**. O objetivo é dar visibilidade
honesta sobre o que existe, o que é parcial e o que não se aplica.

> **Não é uma certificação.** O projeto não passou por auditoria OWASP, ASVS ou
> de terceiros. “Implementado” significa que há código e teste correspondente na
> versão 1.0.0; “parcial” significa que há lacuna documentada; “N/A” significa
> que a categoria não se aplica ao escopo local sem contas, sessão ou rede.

## 1. Contexto de avaliação

- Aplicativo desktop local, usuário único, sem servidor, sem API HTTP, sem
  sessão web, sem banco remoto.
- A autenticação existente é a **posse da senha de criptografia**, não login de
  usuário. Não há autorização multiusuário.
- A superfície de entrada é: arquivos escolhidos, caminhos, senha, campos de
  configuração e arquivos `.cvlt` hostis.
- A superfície de saída é: arquivo `.cvlt`, arquivo restaurado, SQLite,
  `settings.json`, logs e UI.

## 2. OWASP Top 10 — 2021

### A01:2021 — Broken Access Control

| Item | Status | Evidência |
| --- | --- | --- |
| Sem acesso remoto ou multiusuário | N/A | app local; não há API |
| Confinamento de caminhos de entrada/saída | Implementado | `security/paths.py`, `tests/test_paths.py` |
| Rejeição de symlink na entrada e no diretório de saída | Implementado (POSIX) / parcial (Windows) | `validate_input_file`, `validate_output_directory`; testes de symlink ignorados no Windows |
| Sem sobrescrita de arquivo existente | Implementado | `unique_destination`, `AtomicOutput`, testes de overwrite |
| Sanitização de nome de saída | Implementado | `sanitize_filename`, propriedade com Hypothesis |
| Isolamento entre operações | Implementado | `OperationGate`, `QThreadPool` de 1 thread |
| Proteção contra outro usuário do SO | Parcial | permissões `0700/0600` (melhor esforço no Windows) |

**Lacuna:** um adversário local com escrita no diretório de destino ainda pode
explorar corrida de symlink/junction (TOCTOU). O modelo de ameaças registra isso.

### A02:2021 — Cryptographic Failures

| Item | Status | Evidência |
| --- | --- | --- |
| Cifra autenticada aprovada | Implementado | AES-256-GCM, `crypto/engine.py` |
| KDF com custo e salt | Implementado | Scrypt `N=2^15,r=8,p=1`, salt de 32 bytes |
| Nonce único | Implementado | prefixo aleatório + contador de 32 bits |
| Aleatoriedade segura | Implementado | `secrets.token_bytes` |
| Sem algoritmos legados | Implementado | parser rejeita IDs desconhecidos; sem ECB/DES/SHA-1/MD5 |
| Sem senha/chave em repouso | Implementado | `Secret`, histórico/logs sem segredo |
| Limites de parâmetros hostis | Implementado | `KdfParams.validate`, teto de 256 MiB |
| KDF moderno (Argon2id) | Parcial | Scrypt é aceitável; Argon2id pode ser `kdf_id=2` futuro |
| Auditoria criptográfica independente | Ausente | documentado em `CRYPTOGRAPHY.md` |

**Lacuna:** parâmetros de KDF não foram calibrados para um alvo de hardware
específico; 32 MiB é um padrão razoável, não uma promessa de resistência ótima.

### A03:2021 — Injection

| Item | Status | Evidência |
| --- | --- | --- |
| SQL parametrizado | Implementado | `history.py` usa `?`; nenhuma concatenação de valor |
| Sem `eval`/`exec`/shell no runtime | Implementado | busca no código; não há `subprocess` no pacote |
| Log injection | Implementado | JSON estruturado, sanitização de controles, allowlist |
| Redação de segredos em logs | Implementado | `redaction.py`, `tests/test_logging.py` |
| Validação de configuração | Implementado | allowlist de campos, normalização, JSON sem código |
| Nomes de arquivo hostis | Implementado | `sanitize_filename`, sem separadores/controles |
| Injeção em UI (HTML) | Implementado | widgets usam texto simples; não há HTML dinâmico |

**Lacuna:** a redação é baseada em padrões (`senha=`, `token=`, etc.). Uma senha
embutida em texto fora desses padrões pode escapar; por isso o código não registra
senhas diretamente e os campos de log são allowlist.

### A04:2021 — Insecure Design

| Item | Status | Evidência |
| --- | --- | --- |
| Modelo de ameaças documentado | Implementado | `THREAT_MODEL.md` |
| Falha fechada | Implementado | autenticação antes da publicação; erros abortam |
| Publicação atômica | Implementado | `AtomicOutput` |
| Limites de recurso | Implementado | 100 GiB, 1 MiB/bloco, 256 MiB KDF, 500 arquivos na UI |
| Sem recuperação de senha (explícito) | Implementado | UI e docs |
| Sem opções que reduzam segurança | Implementado | tela de configurações não expõe KDF/tag/nonce |
| Cancelamento seguro | Implementado | `threading.Event`, limpeza de temporário |
| Separação de camadas | Implementado | `ARCHITECTURE.md` |
| Testes de abuso | Implementado | adulteração, truncamento, path traversal, Hypothesis |

**Lacuna:** não há limite de tentativas de senha no backend (ataque offline não é
limitável pelo app); a proteção depende da entropia da senha.

### A05:2021 — Security Misconfiguration

| Item | Status | Evidência |
| --- | --- | --- |
| Executável sem console/debug | Implementado | `console=False` no `.spec` |
| Configuração validada e versionada | Implementado | `settings.py` |
| Diretórios privados | Implementado (melhor esforço) | `ensure_private_directory`, `chmod` |
| Logs rotativos e sem segredos | Implementado | 2 MiB × 5, `JsonFormatter` |
| Dependências com versão mínima segura | Implementado | `pyproject.toml`, `requirements*.txt` |
| Checklist de build | Implementado | `scripts/build_windows.ps1` |
| Assinatura de código | Ausente | executável não assinado; checksum apenas |
| Auto-update seguro | N/A | não há update automático |
| Hardening de SO/documentação | Parcial | recomendações em `SECURITY.md` |

**Lacuna:** ausência de assinatura Authenticode e de build reproduzível
verificado. O usuário precisa confiar no canal de distribuição.

### A06:2021 — Vulnerable and Outdated Components

| Item | Status | Evidência |
| --- | --- | --- |
| Inventário de dependências | Implementado | `pyproject.toml`, requirements |
| Versões mínimas corrigidas | Implementado | `cryptography>=50.0.2`, `pytest>=9.0.3` |
| Auditoria de vulnerabilidades | Implementado no processo | `pip-audit`, `docs/verification/pip-audit.txt` |
| CI automatizada | Implementado (GitHub Actions verde em Python 3.12/3.13 e build Windows) | `.github/workflows/ci.yml` |
| Faixas de versão | Parcial | não há lockfile com hashes; resolução pode variar |
| Monitoramento contínuo | Parcial | depende de CI/execução manual |

**Lacuna:** `pip-audit` é um instantâneo; novas CVEs exigem nova execução. Não há
Dependabot/Renovate configurado neste repositório.

### A07:2021 — Identification and Authentication Failures

| Item | Status | Evidência |
| --- | --- | --- |
| Login/sessão | N/A | não há contas nem sessão |
| Senha como segredo criptográfico | Implementado | `Secret`, KDF |
| Mínimo de tamanho | Implementado (8 bytes) | `passwords.py`, UI |
| Limite máximo | Implementado (1024 bytes) | `passwords.py`, KDF |
| Feedback de força | Implementado (heurístico) | `estimate_quality` |
| Bloqueio/rate limiting | N/A | ataque offline; app não autentica online |
| Verificação de senha vazada | Ausente | sem serviço de breach check (sem rede) |
| MFA | N/A | fora do escopo |
| Recuperação de senha | Ausente por design | documentado |

**Lacuna:** o mínimo de 8 bytes é menor que o recomendado pelo ASVS 4.0.3 para
senhas de usuário (12 caracteres). Como a senha é uma frase-senha de criptografia
e não um login online, o risco é diferente, mas a recomendação permanece: use
frases longas. A interface avisa, mas não bloqueia senhas comuns além do mínimo.

### A08:2021 — Software and Data Integrity Failures

| Item | Status | Evidência |
| --- | --- | --- |
| Integridade do conteúdo | Implementado | GCM + AAD |
| Integridade do envelope | Implementado | tags, comprimentos, bytes extras |
| Self-test do binário | Implementado | `--self-test`, `dist/self-test.json` |
| Checksum de distribuição | Implementado | `dist/CryptoVault.exe.sha256` |
| Build documentado | Implementado | `CryptoVault.spec`, `build_windows.ps1` |
| Assinatura do binário | Ausente | não assinado |
| Atualização assinada | N/A | sem auto-update |
| Integridade do histórico | Parcial | SQLite local sem assinatura |

**Lacuna:** checksum não autentica origem. Sem assinatura, um binário adulterado
pode ser distribuído junto com um checksum adulterado.

### A09:2021 — Security Logging and Monitoring Failures

| Item | Status | Evidência |
| --- | --- | --- |
| Eventos de operação | Implementado | `encrypt_*`, `decrypt_*`, `verify_*` |
| Sem senha/conteúdo em log | Implementado | redação, allowlist, testes |
| Rotação | Implementado | 2 MiB × 5 |
| Exceções sem traceback sensível | Implementado | apenas tipo no JSON |
| Histórico local de resultados | Implementado | SQLite |
| Monitoramento/alertas | N/A | app local sem backend |
| Log à prova de adulteração | Ausente | arquivo local |
| Retenção configurável | Implementado | 90/180/365 dias |

**Lacuna:** não há SIEM, alerta, assinatura de log ou prevenção de alteração por
quem tem acesso ao perfil.

### A10:2021 — Server-Side Request Forgery (SSRF)

| Item | Status | Evidência |
| --- | --- | --- |
| Requisições HTTP/SSRF | N/A | app não faz rede |
| Busca de URL | N/A | entradas são caminhos locais |
| Redirecionamento | N/A | sem cliente HTTP |

## 3. ASVS 4.0.3 — capítulos selecionados

Status por capítulo, com foco no que é aplicável a um app local.

| Capítulo | Status | Observações |
| --- | --- | --- |
| V1 — Arquitetura, design e modelagem de ameaças | Parcial/Implementado | camadas documentadas, modelo de ameaças; sem revisão independente |
| V2 — Autenticação | Parcial | não há login; senha de criptografia com mínimo de 8 bytes, sem breach check |
| V3 — Gestão de sessão | N/A | sem sessão |
| V4 — Controle de acesso | Parcial | sem multiusuário; confinamento de caminhos e gate de operação |
| V5 — Validação, sanitização e encoding | Implementado | parser, caminhos, JSON, SQL parametrizado, UI texto |
| V6 — Criptografia armazenada | Implementado com lacunas | AES-256-GCM, Scrypt, nonce, salt, limites; sem auditoria externa |
| V7 — Erros e logging | Implementado | mensagens seguras, JSON, redação, rotação |
| V8 — Proteção de dados | Parcial | sem persistência de segredo; memória/temporários são melhor esforço |
| V9 — Comunicação | N/A | sem rede |
| V10 — Código malicioso | Parcial | sem download/execução dinâmica; binário não assinado |
| V11 — Lógica de negócio | Implementado | fluxo único, sem bypass de autenticação, cancelamento seguro |
| V12 — Arquivos e recursos | Implementado | limite de tamanho, tipo regular, sem symlink, espaço livre, atomicidade |
| V13 — API e web service | N/A | sem API |
| V14 — Configuração | Parcial | defaults seguros, logs, dependências; sem assinatura de código |

### Controles ASVS citados com mais detalhe

| Requisito (ASVS 4.0.3) | Status | Como |
| --- | --- | --- |
| V2.1.1 — senhas com mínimo adequado | Parcial | app exige 8 bytes; recomendação é 12+ |
| V2.1.7 — verificar senhas em vazamentos | Ausente | sem rede/serviço |
| V2.4.1 — fatores/segredos não armazenados em claro | Implementado | senha nunca persistida |
| V4.1.1 — menor privilégio | Implementado | app roda como usuário, sem serviço |
| V5.1.1 — validação positiva | Implementado | parser e limites explícitos |
| V5.1.3 — validação de dados não confiáveis | Implementado | `.cvlt`, caminhos, settings |
| V5.2.1 — sanitização | Implementado | nomes, logs, controles |
| V5.3.3 — SQL parametrizado | Implementado | `history.py` |
| V6.1.1 — controles criptográficos documentados | Implementado | este documento e `CRYPTOGRAPHY.md` |
| V6.2.1 — algoritmos aprovados | Implementado | AES-256-GCM, Scrypt |
| V6.2.2 — modo com integridade | Implementado | GCM |
| V6.2.3 — IV/nonce único | Implementado | prefixo + contador |
| V6.2.4 — aleatoriedade criptográfica | Implementado | `secrets` |
| V6.4.1 — geração de chave | Implementado | Scrypt + salt |
| V6.4.2 — armazenamento de chave | Implementado | chave só em memória |
| V7.1.1 — não registrar dados sensíveis | Implementado | allowlist + redação |
| V7.1.2 — não registrar segredos em erros | Implementado | `safe_error_message` |
| V7.4.1 — mensagem de erro genérica | Implementado | `user_message` |
| V8.2.1 — dados sensíveis não em cache | Parcial | sem cache de app; SO pode reter |
| V8.3.1 — dados sensíveis em memória | Parcial | limpeza melhor esforço |
| V12.1.1 — limite de tamanho de arquivo | Implementado | 100 GiB |
| V12.2.1 — arquivo regular | Implementado | `stat.S_ISREG` |
| V12.3.1 — sem execução de arquivo enviado | N/A | não há upload/execução |
| V12.5.1 — sem path traversal | Implementado | sanitização + validação |
| V14.1.1 — SDLC seguro | Parcial | testes/CI/docs; sem auditoria |
| V14.2.1 — dependências atualizadas | Parcial | faixas + pip-audit; sem lockfile |
| V14.3.1 — configuração segura | Parcial | defaults; sem assinatura |

> Os identificadores acima são usados como referência de intenção. Consulte o
> texto oficial do ASVS para o critério exato de cada requisito.

## 4. Evidências automatizadas

| Área | Teste/arquivo |
| --- | --- |
| Autenticação de conteúdo | `tests/test_engine.py::test_tampered_ciphertext_tag_and_header_are_rejected` |
| Sem saída parcial | `test_no_partial_output_when_later_chunk_is_tampered` |
| Truncamento/anexo | `test_malformed_structure_is_rejected` |
| Sem overwrite | `test_no_overwrite_preserves_existing_file` |
| Cancelamento | `test_cancel_*` |
| KDF/limites | `tests/test_kdf.py`, `tests/test_format.py` |
| Caminhos/sanitização | `tests/test_paths.py` |
| SQL/segredo no histórico | `tests/test_service.py::test_password_is_never_written_to_history_database` |
| Logs/redação | `tests/test_logging.py` |
| Configuração | `tests/test_settings.py` |
| UI real | `tests/test_ui.py` |
| Binário | `dist/self-test.json` |
| Dependências | `docs/verification/pip-audit.txt` |
| Estilo/segurança estática | `docs/verification/ruff-*.txt`, `bandit.txt` |

## 5. Lacunas e próximos passos

1. **Assinatura de código** do executável Windows e verificação no download.
2. **Lockfile com hashes** e Dependabot/Renovate para supply chain.
3. **Auditoria criptográfica independente** do formato e do motor.
4. **Testes de symlink/junction no Windows** com privilégios adequados.
5. **Calibração de KDF** para hardware alvo e revisão de mínimo de senha.
6. **Verificação de senhas vazadas** se houver serviço local/offline confiável.
7. **Log à prova de adulteração** ou exportação assinada, se auditoria for
   requisito.
8. **Testes de build reproduzível** e atestação de proveniência.
9. **Revisão de acessibilidade** e testes com leitor de tela.
10. **Fuzzing contínuo** do parser para complementar Hypothesis.

## 6. Conclusão

O CryptoVault cobre os controles centrais de criptografia autenticada,
validação de entrada, proteção de caminhos, publicação atômica, logging seguro e
gestão de dependências. As maiores lacunas são organizacionais e de distribuição
(assinatura, auditoria independente, lockfile), não a ausência de uma primitiva
criptográfica. O usuário deve tratar o app como ferramenta local de proteção em
repouso, não como solução completa contra um adversário com controle do sistema.
