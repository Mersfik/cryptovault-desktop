# Arquitetura — CryptoVault Desktop

Este documento descreve como o CryptoVault Desktop está organizado, como os
dados atravessam as camadas e quais decisões mantêm a interface responsiva sem
enfraquecer as garantias criptográficas.

## 1. Objetivo e escopo

O aplicativo é um cofre local de arquivos: recebe arquivos do usuário, deriva uma
chave a partir de uma senha, cifra ou decifra com AES-256-GCM e publica o
resultado somente depois de validar a autenticação de todos os blocos.

A arquitetura foi desenhada para:

- manter toda a criptografia em um único motor testável, independente de Qt;
- impedir que a interface bloqueie durante derivação de chave ou leitura de
  arquivos grandes;
- falhar fechado: em erro, cancelamento ou adulteração, nenhum conteúdo parcial
  é publicado com o nome final;
- minimizar vazamento por caminhos, logs, histórico ou mensagens de erro;
- permitir auditoria: cada camada tem uma responsabilidade pequena e explícita.

Não faz parte do escopo: servidor, sincronização, compartilhamento, contas de
usuário, recuperação de senha, assinatura digital, atualização automática ou
execução em ambiente multi-inquilino.

## 2. Princípios de projeto

1. **Núcleo sem Qt.** `crypto/`, `domain/`, `security/` e `application/` não
   importam PySide6. Isso permite testar as regras sem interface e reduz a
   superfície de acoplamento.
2. **Dependências apontam para dentro.** A UI chama a aplicação; a aplicação
   chama domínio, criptografia, segurança e infraestrutura. O domínio não
   conhece nenhuma dessas implementações.
3. **Um único motor criptográfico.** A interface, os testes, o self-test do
   executável e os casos de uso usam `CryptoEngine`. Não existe um “modo de
   demonstração” que simule criptografia.
4. **Publicação atômica.** A saída é escrita em um temporário no diretório de
   destino, sincronizada com `fsync` e renomeada/vinculada sem sobrescrever.
5. **Falha fechada.** Erros de formato, autenticação, caminho ou espaço são
   recusados antes de qualquer publicação.
6. **Segredo com vida curta.** Senhas vivem em `Secret` (buffer mutável) e são
   limpas em melhor esforço depois do uso; não são persistidas.
7. **Sem opções inseguras.** A tela de configurações não permite reduzir custo
   de KDF, tamanho de tag/nonce, trocar para algoritmos legados ou desativar a
   autenticação.

## 3. Visão de camadas

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Apresentação (PySide6)                                              │
│ ui/main_window.py · ui/pages/* · ui/widgets.py · ui/theme.py        │
│ ui/controller.py · ui/workers.py · ui/notifications.py              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ chamadas de caso de uso / sinais Qt
┌───────────────────────────────▼─────────────────────────────────────┐
│ Aplicação                                                           │
│ application/service.py                                              │
│ validação de entrada, nomes de saída, histórico, logs, operação     │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
┌───────────────▼──────────────┐  ┌─────────────▼────────────────────┐
│ Criptografia                 │  │ Segurança e domínio              │
│ crypto/format.py             │  │ security/paths.py                │
│ crypto/kdf.py                │  │ security/passwords.py            │
│ crypto/engine.py             │  │ security/gate.py                 │
│ AES-256-GCM · Scrypt         │  │ security/redaction.py            │
└───────────────┬──────────────┘  │ domain/models.py · errors.py     │
                │                 └─────────────┬────────────────────┘
                │                               │
┌───────────────▼───────────────────────────────▼─────────────────────┐
│ Infraestrutura local                                                │
│ infrastructure/history.py (SQLite)                                  │
│ infrastructure/settings.py (JSON atômico)                           │
│ infrastructure/logging_setup.py (JSON rotativo + redação)           │
└─────────────────────────────────────────────────────────────────────┘
```

### Módulos e responsabilidades

| Caminho | Responsabilidade | Não faz |
| --- | --- | --- |
| `cryptovault/app.py` | CLI, `--self-test`, lock de instância, bootstrap, tema, janela | Não implementa criptografia |
| `cryptovault/crypto/format.py` | Layout binário v1, constantes, parser, AAD, limites de KDF | Não lê arquivos nem conhece UI |
| `cryptovault/crypto/kdf.py` | Scrypt com limites rígidos | Não armazena chave |
| `cryptovault/crypto/engine.py` | Streaming AES-GCM, inspeção, verificação, publicação atômica | Não grava histórico nem exibe mensagens |
| `cryptovault/domain/models.py` | Dataclasses e enums de operação/resultado | Não importa Qt ou `cryptography` |
| `cryptovault/domain/errors.py` | Hierarquia de erros com mensagem segura | Não expõe stack trace ao usuário |
| `cryptovault/security/paths.py` | Validação de caminhos, `O_NOFOLLOW`, espaço livre, `AtomicOutput` | Não decide políticas de UI |
| `cryptovault/security/passwords.py` | `Secret`, limites e estimativa heurística de força | Não persiste senha |
| `cryptovault/security/gate.py` | Impede duas operações simultâneas | Não enfileira trabalhos |
| `cryptovault/security/redaction.py` | Sanitização de logs e nomes | Não autentica dados |
| `cryptovault/application/service.py` | Casos de uso, escopo de operação, histórico, logging | Não conhece widgets |
| `cryptovault/infrastructure/history.py` | SQLite local com consultas parametrizadas | Não é auditoria inviolável |
| `cryptovault/infrastructure/settings.py` | JSON versionado, gravação atômica | Não guarda segredos |
| `cryptovault/infrastructure/logging_setup.py` | JSON rotativo, filtro de redação, `excepthook` | Não registra conteúdo ou caminho completo |
| `cryptovault/ui/main_window.py` | Navegação, integração de sinais, atalhos, ciclo de vida | Não executa criptografia na thread da UI |
| `cryptovault/ui/controller.py` | Orquestra worker, progresso, estatísticas e notificações | Não abre arquivos diretamente |
| `cryptovault/ui/workers.py` | `QRunnable` de lote, progresso e cancelamento | Não toca widgets |
| `cryptovault/ui/pages/*` | Telas e validação de formulário | Não derivam chaves |
| `cryptovault/ui/widgets.py` | Componentes reutilizáveis (drop zone, senha, banner) | Não contêm regra de negócio |

## 4. Estrutura de arquivos

```text
cryptovault/
  __init__.py              versão e identidade
  __main__.py              python -m cryptovault
  app.py                   bootstrap, CLI e self-test
  application/service.py   casos de uso e auditoria
  crypto/format.py         formato CryptoVault v1
  crypto/kdf.py            derivação Scrypt
  crypto/engine.py         motor de streaming
  domain/errors.py         erros seguros
  domain/models.py         tipos de domínio
  infrastructure/          SQLite, settings e logs
  security/                caminhos, senhas, gate e redação
  ui/                      janela, páginas, widgets, tema e workers
  resources/               logo e ícones
tests/                     unitários, integração, segurança e UI
scripts/                   ícone, screenshots e build Windows
docs/screenshots/          capturas reais
docs/verification/         evidências de validação
```

## 5. Inicialização da aplicação

`cryptovault/app.py:main()` segue esta ordem:

1. Interpreta `--version`, `--self-test`, `--report` e `--data-dir`.
2. Se `--self-test`: executa um ciclo real em diretório temporário, sem tocar
   nos dados do usuário, e retorna código 0 somente se todos os checks passarem.
3. Resolve o diretório de dados:
   `--data-dir` > `CRYPTOVAULT_DATA_DIR` > `%LOCALAPPDATA%\CryptoVault` >
   `~/.local/share/CryptoVault`.
4. Cria o diretório com permissão restritiva (melhor esforço no Windows).
5. Cria `QApplication`, define nome, organização, versão e ícone.
6. Adquire `QLockFile` em `data_dir/cryptovault.lock` com timeout de lock obsoleto
   de 30 s. Se outra instância estiver ativa, exibe aviso e retorna código 2.
7. Carrega `settings.json`; se inválido, usa padrões normalizados e tenta
   regravar. Garante os diretórios de saída e de logs.
8. Configura logging JSON rotativo e registra `application_started`.
9. Abre o SQLite, cria o serviço, o controlador e a janela.
10. Aplica retenção do histórico (`history_retention_days`) com tolerância a
    falha: uma falha de retenção não impede o uso.
11. Aplica tema, mostra a janela e entra no loop Qt.
12. No encerramento, registra `application_stopped`, libera o lock e remove o
    temporário de lock.

Erros fatais de inicialização são registrados sem segredos e exibidos como uma
mensagem genérica; o código de saída é 4. O executável empacotado usa o mesmo
caminho de código.

## 6. Fluxos principais

### 6.1 Criptografar um arquivo

```text
UI (EncryptPage)
  └─ valida seleção, senha/confirmação e diretório
     └─ MainWindow.take_password() → Secret
        └─ AppController.start_encrypt(files, Secret, output_dir)
           └─ QThreadPool (1 thread) → BatchOperationWorker.run()
              └─ FileOperationService.encrypt_file()
                 ├─ validate_input_file()          regular, sem symlink, ≤100 GiB
                 ├─ validate_output_directory()    diretório real, gravável
                 ├─ unique_destination()           nunca sobrescreve
                 ├─ engine.encrypt_file()
                 │  ├─ secure_open_input()         O_RDONLY | O_NOFOLLOW, fstat
                 │  ├─ check_free_space()
                 │  ├─ salt(32) + nonce_prefix(8)  secrets.token_bytes
                 │  ├─ build_header()             80 bytes, versão 1
                 │  ├─ derive_key()               Scrypt → 32 bytes
                 │  ├─ AtomicOutput()             .cryptovault-*.part
                 │  ├─ loop de 1 MiB              AESGCM.encrypt(nonce, chunk, AAD)
                 │  ├─ secure.assert_unchanged()  tamanho/mtime do descritor
                 │  └─ output.commit()            fsync + rename/link sem overwrite
                 ├─ registra histórico (sucesso/falha)
                 └─ registra log JSON sem senha/caminho completo
              └─ sinais: itemFinished, finished, progress
           └─ MainWindow atualiza dashboard, histórico, toast e notificação
```

O nome de saída é `<nome-sanitizado>.cvlt`; se já existir, o serviço escolhe
`<nome> (1).cvlt`, `<nome> (2).cvlt`, até 10.000 tentativas.

### 6.2 Descriptografar

1. A página inspeciona o cabeçalho ao selecionar o arquivo
   (`inspect_file`), sem derivar chave. Isso mostra formato, algoritmo, KDF,
   tamanho em claro, quantidade de blocos e fingerprint.
2. A UI deixa claro que um cabeçalho válido **não** comprova autenticidade.
3. Ao iniciar, o worker chama `FileOperationService.decrypt_file`.
4. O motor lê o cabeçalho, valida limites, deriva a chave e itera os registros.
5. Para cada registro:
   - confere o comprimento declarado contra o esperado pelo cabeçalho;
   - lê exatamente `comprimento + 16` bytes;
   - reconstrói nonce e AAD;
   - `AESGCM.decrypt` valida a tag **antes** de devolver o bloco;
   - o bloco em claro só é escrito no temporário após a validação.
6. Ao final, confere que não há bytes extras e que o total recuperado é igual a
   `plaintext_size`.
7. Só então `AtomicOutput.commit()` publica o arquivo com o nome final.
8. Falha de tag, truncamento, anexo ou cancelamento removem o temporário; o
   arquivo final não existe.

### 6.3 Verificar

`verify_file` executa o mesmo caminho autenticado da descriptografia, mas
descarta os blocos em claro e não cria saída. Retorna um `VerifyResult` com:

- `AUTHENTICATED` — todas as tags, o cabeçalho e a estrutura conferem;
- `INVALID_AUTHENTICATION` — tag inválida (senha errada ou adulteração);
- `INVALID_FORMAT` — truncamento, comprimento inconsistente ou dados extras;
- `UNSUPPORTED_VERSION` — versão desconhecida.

O GCM não permite distinguir “senha errada” de “arquivo adulterado”; a interface
informa as duas possibilidades em vez de prometer uma causa exata.

### 6.4 Inspecionar

`inspect_file` lê apenas os 80 bytes do cabeçalho, valida magic, versão,
algoritmo, KDF, tamanhos, flags, bytes reservados e limites. Não deriva chave,
não autentica conteúdo e não prova que o arquivo foi criado por esta aplicação
(alguém pode construir um cabeçalho estruturalmente válido).

## 7. Concorrência e ciclo de vida

- **Thread da UI:** apenas widgets, sinais, validação de formulário e pintura.
- **Worker:** `BatchOperationWorker` é um `QRunnable` executado em
  `QThreadPool` com `maxThreadCount = 1`.
- **Um lote por vez:** `OperationGate` no serviço também recusa escopos
  simultâneos, mesmo que outro chamador tente burlar a UI.
- **Cancelamento:** `threading.Event` consultado antes de cada bloco e antes de
  cada arquivo. O worker marca os restantes como cancelados, registra o
  histórico e limpa o segredo.
- **Progresso:** o worker emite `(percentual, mensagem)`; o controlador repassa
  aos três painéis de operação. O texto inclui apenas o nome sanitizado.
- **Encerramento:** `closeEvent` pergunta se há operação em andamento; se o
  usuário confirmar, solicita cancelamento, aguarda `waitForDone(15 s)`, para a
  bandeja e fecha. O lock é liberado no `finally` do bootstrap.
- **Sem trabalho na thread errada:** os widgets não são acessados pelo worker;
  toda atualização visual passa por sinais Qt.

## 8. Persistência local

### Configurações (`settings.json`)

- Versão de esquema `1`.
- Campos: diretório de saída, diretório de logs, notificações, densidade,
  escala de fonte e retenção do histórico.
- Normalização: valores inválidos caem para padrões seguros; retenção entre 30
  e 3.650 dias; densidade `comfortable|compact`; escala `100|110|125`.
- Chaves desconhecidas são ignoradas; versão diferente é migrada para a atual.
- Gravação em arquivo temporário no mesmo diretório, `fsync`, `chmod 0600` e
  `os.replace` atômico.
- Não existe campo de senha, chave, salt ou parâmetro criptográfico.

### Histórico (`history.db`)

- SQLite com `PRAGMA journal_mode = WAL` e `busy_timeout = 5000`.
- Tabela `operations`: id, timestamp UTC, operação, nome do arquivo, resultado,
  mensagem, tamanho e duração.
- `CHECK` constraints para operação, resultado, tamanho e duração.
- Consultas sempre parametrizadas; filtros por operação e resultado.
- Retenção por dias e limpeza total sob confirmação.
- Permissões `0600` para o banco e arquivos WAL/SHM (melhor esforço).
- O histórico **não** é um registro de auditoria inviolável: quem tiver acesso
  ao perfil do usuário pode alterá-lo.

### Logs (`cryptovault.log`)

- JSON por linha, UTF-8, um evento por linha.
- Rotação por tamanho: 2 MiB, 5 backups.
- Campos permitidos: `event`, `operation`, `result`, `file_name`, `code`,
  `duration_ms`, `size_bytes`, `output_count`, `version`, `component`.
- Filtro de redação remove padrões `password=`, `senha=`, `passphrase=`,
  `secret=`, `token=`, `key=` e `Bearer ...`; caracteres de controle são
  substituídos; exceções registram apenas o tipo, nunca traceback ou mensagem.
- O diretório de logs é privado; trocar o diretório exige reinício.
- O logger da aplicação não propaga para handlers externos.

## 9. Segurança de caminhos e publicação

`security/paths.py` concentra as defesas de sistema de arquivos:

- `validate_input_file`: exige arquivo regular, rejeita symlink, aplica limite de
  100 GiB e resolve o caminho.
- `validate_output_directory`: exige diretório real, sem symlink, com permissão
  de escrita/execução.
- `secure_open_input`: abre com `O_NOFOLLOW` quando disponível, confere `fstat`
  e detecta mudança de tamanho/mtime durante a leitura.
- `sanitize_filename`: normaliza Unicode, remove separadores, caracteres de
  controle, nomes reservados do Windows e excesso de comprimento.
- `unique_destination`: nunca substitui um arquivo existente.
- `check_free_space`: exige espaço para o envelope mais uma reserva de 16 MiB.
- `AtomicOutput`:
  - temporário no mesmo diretório de destino, prefixo `.cryptovault-`, sufixo
    `.part`;
  - `chmod 0600` (POSIX) e conteúdo em claro sobrescrito em melhor esforço no
    aborto;
  - `commit` faz `flush` + `fsync`, fecha e publica;
  - Windows: `os.rename` falha se o destino existir;
  - POSIX: `os.link` atômico falha com `EEXIST` e o temporário é removido;
  - qualquer falha remove o temporário e não deixa saída parcial.

## 10. Tratamento de erros

| Exceção | Origem típica | Mensagem ao usuário |
| --- | --- | --- |
| `ValidationError` | parâmetro inválido | “Os dados informados são inválidos.” |
| `PasswordError` | senha curta/longa/vazia | “A senha não atende aos requisitos mínimos.” |
| `FormatError` | magic/estrutura inválida | “O arquivo não possui um formato CryptoVault válido.” |
| `UnsupportedVersionError` | versão desconhecida | “A versão deste arquivo não é suportada...” |
| `AuthenticationError` | tag inválida | “Senha incorreta ou arquivo adulterado/corrompido.” |
| `PathSecurityError` | symlink, não regular, caminho inseguro | “O caminho selecionado não é seguro...” |
| `SizeLimitError` | acima de 100 GiB | “O arquivo excede o limite...” |
| `OutputExistsError` | destino existente | “Já existe um arquivo no destino. Nenhum arquivo foi sobrescrito.” |
| `InsufficientSpaceError` | disco cheio | “Não há espaço livre suficiente...” |
| `CancelledError` | cancelamento do usuário | “Operação cancelada.” |
| `BusyError` | duas operações | “Já existe uma operação em andamento.” |
| `HistoryError` | SQLite indisponível | “Não foi possível acessar o histórico...” |
| `SettingsError` | JSON inválido | “Não foi possível ler ou salvar as configurações.” |

`CryptoVaultError` carrega `detail` interno e `user_message` seguro. A UI usa
`safe_error_message`; o log registra o evento e o código, não o detalhe sensível.
Falhas inesperadas são convertidas em mensagem genérica e registradas com
`logger.exception`, mas o `JsonFormatter` grava somente o tipo da exceção.

## 11. Interface

- Janela mínima 1040×680, layout com sidebar fixa de 234 px, topbar, stack de
  páginas, status bar e toast.
- Seis páginas: Dashboard, Criptografar, Descriptografar, Verificar, Histórico e
  Configurações.
- Atalhos: `Ctrl+1..6` para navegação, `Ctrl+O` para selecionar, `Ctrl+Enter`
  para iniciar, `Ctrl+L` para focar a senha e `F5` para atualizar.
- Componentes reutilizáveis:
  - `DropZone` com drag-and-drop de arquivos;
  - `PasswordField` com botão de revelação temporária;
  - `PasswordStrengthMeter` com estimativa heurística;
  - `PathPicker` com seletor nativo;
  - `StatusBanner` e `Toast` para feedback;
  - `Card`, `StatCard` e tabelas somente leitura.
- Tema escuro aplicado por QSS, com densidade confortável/compacta e escala de
  fonte 100/110/125%.
- Acessibilidade: nomes acessíveis em botões, listas, campos e barras de
  progresso; foco visível; textos com `wordWrap`; tabelas sem edição.
- A senha é limpa do campo imediatamente após ser entregue ao controlador; o
  objeto `Secret` é limpo pelo worker no `finally`.

## 12. Dependências e fronteiras

```text
PySide6  ──► ui/*
cryptography ──► crypto/*
sqlite3 (stdlib) ──► infrastructure/history.py
json/tempfile/os (stdlib) ──► infrastructure/settings.py
```

- `crypto/` não importa `ui/`.
- `domain/` não importa `cryptography`, `PySide6`, `sqlite3` nem `logging`.
- `ui/` não importa detalhes internos de SQLite nem `cryptography`.
- O motor recebe senha como `str | ByteString`; a aplicação normalmente passa
  `Secret.bytes_copy()`, uma cópia imutável de vida curta.

## 13. Build e distribuição

- `CryptoVault.spec` usa PyInstaller one-file, sem console, com ícone ICO e os
  recursos SVG/PNG embutidos.
- `scripts/build_windows.ps1` gera o ícone, limpa `build/` e `dist/`, empacota,
  executa `dist\CryptoVault.exe --self-test --report dist\self-test.json`,
  falha se o código de saída não for 0 e grava o SHA-256.
- O executável é não assinado; a integridade do artefato é comunicada por
  checksum, não por assinatura de código.
- Não há auto-atualização nem canal de rede. Uma nova versão é um novo binário
  distribuído pelo responsável.

## 14. Estratégia de testes

| Camada | Arquivos | O que cobre |
| --- | --- | --- |
| Formato | `tests/test_format.py` | layout, parser hostil, limites, nonce, AAD |
| KDF | `tests/test_kdf.py` | determinismo, salt, limites, comparação |
| Senhas | `tests/test_passwords.py` | mínimo/máximo, qualidade, limpeza |
| Motor | `tests/test_engine.py` | round-trip, adulteração, truncamento, cancelamento, overwrite, progresso |
| Caminhos | `tests/test_paths.py` | sanitização, symlink, atômico, permissões |
| Histórico | `tests/test_history.py` | ordenação, filtros, retenção, redação, banco inválido |
| Configurações | `tests/test_settings.py` | defaults, normalização, migração, atomicidade |
| Logs | `tests/test_logging.py` | JSON, redação, controles, exceções |
| Serviço | `tests/test_service.py` | integração, histórico, gate, segredo não proprietário |
| Self-test | `tests/test_self_test.py` | checks do executável, CLI, precedência de dados |
| UI | `tests/test_ui.py` | navegação, revelação de senha, fluxos reais, filtros, configurações, busy state |

Os testes usam `pytest`, `pytest-qt`, `pytest-cov` e `hypothesis`. A plataforma
de teste em CI é Windows; localmente, testes que dependem de semântica POSIX
(symlink/permissões) são ignorados no Windows.

## 15. Decisões e trade-offs

| Decisão | Motivo | Custo |
| --- | --- | --- |
| Formato próprio versionado | controlar AAD, chunking e limites | exige parser e compatibilidade futura |
| AES-GCM por bloco | streaming com autenticação | overhead de 20 bytes por bloco |
| Scrypt em vez de Argon2id | disponível em `cryptography`, amplamente suportado, sem dependência extra | Argon2id é mais moderno; parâmetros precisam ser calibrados |
| 1 MiB por bloco | equilíbrio entre memória, overhead e granularidade | arquivos grandes têm muitos registros |
| Temporário no destino | rename/link atômico no mesmo volume | requer espaço livre e permissão no diretório |
| SQLite para histórico | consultas, filtros, transações | não é à prova de adulteração |
| PyInstaller one-file | distribuição simples | inicialização mais lenta e binário grande |
| Sem auto-update | reduz superfície de ataque | atualização manual |

## 16. Pontos de extensão

- **Novo algoritmo/KDF:** adicionar identificador ao formato, implementar no
  motor, manter rejeição explícita de IDs desconhecidos e atualizar
  `CRYPTOGRAPHY.md`/testes. Não alterar o significado dos IDs existentes.
- **Novo formato:** incrementar `FORMAT_VERSION`, manter leitor da versão 1 e
  testar migração.
- **Novo campo de histórico:** migração de esquema com `PRAGMA user_version` e
  testes de compatibilidade.
- **Novos idiomas:** separar strings de UI; hoje os textos são português-BR
  embutidos.
- **Assinatura de código:** adicionar ao pipeline de build e documentar a
  cadeia de confiança.

Qualquer extensão que reduza tamanho de tag, custo de KDF ou validação de
autenticação deve ser recusada em revisão de código.
