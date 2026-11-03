# Modelo de ameaças — CryptoVault Desktop

Documento de trabalho alinhado ao OWASP Threat Modeling e a STRIDE. Ele descreve
o que o aplicativo protege, contra quem, em quais fronteiras confia e o que
permanece como risco residual.

## 1. Escopo

**Dentro do escopo:**

- aplicativo desktop local em Windows (principal), com código aberto;
- criptografia e descriptografia de arquivos escolhidos pelo usuário;
- envelope `.cvlt` gravado no sistema de arquivos local;
- histórico SQLite, configurações JSON e logs locais;
- executável PyInstaller não assinado distribuído pelo projeto.

**Fora do escopo:**

- servidores, nuvem, sincronização e compartilhamento;
- contas, autenticação de usuário, autorização multiusuário;
- recuperação de senha, herança de chave, assinatura digital;
- atualização automática, telemetria, rede;
- proteção do computador contra comprometimento do sistema operacional;
- conformidade regulatória específica (HIPAA, PCI, LGPD como certificação);
- hardware seguro (TPM, HSM, enclave) ou token externo.

## 2. Ativos

| Ativo | Onde existe | Impacto se comprometido |
| --- | --- | --- |
| Conteúdo em claro | arquivo de origem, temporário de saída, memória | confidencialidade |
| Senha/frase-senha | memória, widget de senha | confidencialidade de todos os arquivos |
| Chave derivada (32 B) | memória do worker | confidencialidade/integridade |
| Envelope `.cvlt` | disco do usuário | confidencialidade e integridade |
| Metadados do envelope | cabeçalho `.cvlt` | revela formato, KDF, tamanho aproximado |
| Histórico | `history.db` | revela nomes, horários, resultados |
| Configurações | `settings.json` | revela caminhos locais |
| Logs | `cryptovault.log*` | podem revelar nomes/eventos se não redigidos |
| Integridade do binário | `CryptoVault.exe` | execução de código não confiável |
| Disponibilidade | processo, lock, disco | negação de uso |

## 3. Atores e capacidades

| Ator | Capacidade | Interesse |
| --- | --- | --- |
| Usuário legítimo | acesso ao perfil, senha | proteger e recuperar arquivos |
| Usuário local malicioso | outro processo na mesma máquina, perfil diferente ou acesso físico | ler/alterar dados |
| Malware no mesmo perfil | keylogger, screen capture, injeção, leitura de memória/arquivos | exfiltrar segredos |
| Atacante com o `.cvlt` | acesso offline ao arquivo | quebrar confidencialidade/integridade |
| Atacante de rede | sem canal no app | não se aplica diretamente |
| Fornecedor de dependência | código executado no processo | supply chain |
| Pessoa com acesso ao build | modifica binário/artefato | distribuir versão trojanizada |
| Atacante físico | acesso ao dispositivo desligado/ligado | obter disco, memória, backups |

## 4. Premissas de confiança

O modelo assume que:

1. O sistema operacional, o hardware, o Python e as dependências instaladas são
   confiáveis no momento da execução.
2. O gerador de aleatoriedade do sistema (`secrets`/`os.urandom`) é
   criptograficamente seguro.
3. A senha é escolhida pelo usuário, mantida em segredo e tem entropia
   suficiente.
4. O usuário não executa o aplicativo em ambiente já comprometido por malware
   com os mesmos privilégios.
5. O diretório de dados e o diretório de saída pertencem ao usuário e não são
   controlados por outro usuário.
6. O relógio do sistema é razoavelmente correto para timestamps de histórico.
7. O disco não é removido ou substituído durante uma operação (mudanças de
   arquivo de origem são detectadas por tamanho/mtime, não contra um adversário
   ativo com escrita concorrente sofisticada).

Se qualquer premissa for falsa, as garantias caem total ou parcialmente.

## 5. Fronteiras de confiança

```text
[Usuário] ──teclado/arrastar──► [UI Qt]
                                   │ sinais/casos de uso
                                   ▼
                            [Worker / Serviço]
                                   │ senha, caminhos
                                   ▼
                            [Motor AES-GCM]
                          ┌────────┴────────┐
                          ▼                 ▼
                   [Arquivo .cvlt]     [Temporário]
                          │
                          ▼
                 [Sistema de arquivos / SO]
                          │
                          ▼
             [SQLite] [settings.json] [logs]
```

Fronteiras relevantes:

- **UI ↔ worker:** o segredo atravessa uma thread; não há serialização para
  disco nem log.
- **Worker ↔ sistema de arquivos:** caminhos fornecidos pelo usuário são
  hostis por definição até validação.
- **Envelope ↔ usuário:** o `.cvlt` pode ter sido modificado; nada é confiável
  antes da autenticação.
- **Aplicativo ↔ dependências:** `cryptography`, PySide6, Python e PyInstaller
  fazem parte da base de confiança.
- **Build ↔ distribuição:** o executável não é assinado; checksum só ajuda se o
  canal de distribuição for confiável.

## 6. Análise STRIDE

### 6.1 Spoofing (identidade)

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Site/pessoa se passa pelo CryptoVault | repositório oficial, README e checksum; não há update automático | usuário pode baixar binário falso |
| Arquivo `.cvlt` se passa por outro | AAD inclui cabeçalho completo e fingerprint exibido | fingerprint não é assinatura; origem não é provada |
| Processo se passa por instância legítima | `QLockFile` por diretório de dados | outro usuário com perfil separado pode rodar outra instância |
| UI mostra “autenticado” sem verificar | resultado só vem de `verify_file` real; self-test cobre | engenharia social/spoof visual do SO |

### 6.2 Tampering (adulteração)

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Alterar ciphertext/tag | GCM detecta; nenhuma saída é publicada | colisão de tag é desprezível, não nula |
| Alterar salt/nonce/KDF/cabeçalho | todo o cabeçalho entra no AAD; parser valida limites | — |
| Reordenar/replay de blocos | índice e AAD por registro | — |
| Truncar ou anexar dados | comprimentos esperados + checagem de bytes extras | — |
| Substituir arquivo de origem durante leitura | `fstat` de tamanho/mtime antes/depois; descritor aberto com `O_NOFOLLOW` | adversário com escrita concorrente e mesma máquina pode burlar mtime; não é proteção contra corrida sofisticada |
| Alterar histórico/configurações | SQLite/JSON locais, sem assinatura | quem tem acesso ao perfil pode alterar; não é auditoria inviolável |
| Alterar logs | arquivo local com permissão restrita | mesmo usuário/malware pode alterar |
| Substituir executável | checksum publicado; build reproduzível não garantido | binário não assinado |

### 6.3 Repudiation (repúdio)

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Negar que uma operação ocorreu | histórico local com timestamp, operação, arquivo e resultado | histórico pode ser apagado/alterado; não há assinatura ou log remoto |
| Negar autoria de um `.cvlt` | nenhuma | formato não autentica autor; chave é compartilhada por senha |
| Negar alteração de configurações | nenhuma | não é registro de auditoria |

### 6.4 Information disclosure (vazamento)

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Ler `.cvlt` sem senha | AES-256-GCM + Scrypt | ataque offline de dicionário se a senha for fraca |
| Senha em logs | redação de padrões + campos allowlist + testes | senha embutida em mensagem fora do padrão pode escapar |
| Senha no histórico | serviço nunca grava senha; teste varre DB/WAL | — |
| Caminho completo em log | `file_name` sanitizado; logs não recebem caminho | nome do arquivo ainda é registrado |
| Nome/tamanho no histórico | por design; documentado | metadados não são confidenciais |
| Conteúdo em temporário | temporário no destino, apagado/sobregravado em melhor esforço | SSD/COW/backup podem reter blocos |
| Conteúdo em memória/swap | limpeza de `Secret` e chave em melhor esforço | SO pode paginar/hibernar/dump |
| Captura de tela/keylogger | não há defesa | malware com mesma sessão vence |
| Vazamento por mensagem de erro | `user_message` seguro; detalhe interno não vai à UI | logs locais ainda registram tipo de exceção |
| Vazamento por notificação/toast | texto contém nome do arquivo, não senha | visível a quem olha a tela |
| Vazamento por clipboard | app não copia senha automaticamente | usuário pode copiar manualmente |
| Fingerprint confundido com prova | UI explica que não é assinatura | interpretação do usuário |

### 6.5 Denial of service (negação)

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Cabeçalho com KDF caro | limites 15–18/8–16/1–4 e teto de 256 MiB antes da derivação | ainda pode consumir até 256 MiB e CPU por arquivo |
| Arquivo gigante | limite de 100 GiB e checagem de espaço | 100 GiB ainda pode ser custoso |
| Muitos arquivos no lote | limite de 500 na UI | serviço/CLI não impõe 500; cada arquivo é sequencial |
| Disco cheio | checagem de espaço + temporário no destino | corrida entre checagem e escrita pode falhar; erro é tratado |
| Duas operações concorrentes | `OperationGate` + pool de 1 thread | uma operação longa bloqueia as demais por design |
| Lock preso | `QLockFile` com stale lock de 30 s | pode ser removido por outro processo com acesso |
| Arquivo com milhões de blocos | `plaintext_size` limitado e comprimentos validados | leitura sequencial ainda pode demorar |
| Cancelamento ignorado | evento checado a cada bloco | operação de KDF não é interrompível no meio |

### 6.6 Elevation of privilege

| Ameaça | Mitigação | Residual |
| --- | --- | --- |
| Path traversal para gravar fora do destino | `sanitize_filename` remove separadores; `validate_output_directory`; `AtomicOutput` exige mesmo diretório | symlink/junction criado após validação (TOCTOU) pode ser explorado por adversário local com escrita no destino |
| Symlink na entrada/saída | `lstat`, rejeição de symlink, `O_NOFOLLOW` | Windows reparse points/junctions têm semântica parcial; testes de symlink são ignorados no Windows |
| Sobrescrever arquivo existente | `unique_destination`, checagem e rename/link sem overwrite | corrida entre checagem e commit é tratada por `EEXIST`/`FileExistsError` |
| Injeção de SQL | consultas parametrizadas, `CHECK` | — |
| Injeção de log | JSON estruturado, sanitização, allowlist | conteúdo de `file_name` ainda é texto livre sanitizado |
| Injeção de comando | nenhum `shell=True`, `subprocess` ou `eval` no app | scripts de build usam PowerShell, fora do runtime |
| Execução de código via configuração | JSON sem código; apenas campos allowlist | paths apontam para diretórios, não executáveis |
| Escalada via processo | app roda com privilégios do usuário, sem serviço/root | malware já com privilégios não precisa escalar |

## 7. Ameaças por componente

### Envelope `.cvlt`

- **Ameaça:** adversário altera um byte para corromper a saída.
  **Controle:** tag GCM por bloco + AAD do cabeçalho/índice/comprimento/final.
- **Ameaça:** adversário remove o último bloco.
  **Controle:** `plaintext_size` no cabeçalho e comprimento esperado por índice;
  verificação de bytes extras.
- **Ameaça:** adversário cria cabeçalho com KDF absurdo.
  **Controle:** parser valida limites antes de derivar.
- **Ameaça:** adversário afirma que o arquivo é de outra pessoa.
  **Controle:** nenhum; formato não tem assinatura. Documentado.

### Motor e KDF

- **Ameaça:** nonce repetido.
  **Controle:** prefixo aleatório por arquivo + contador; salt novo por arquivo;
  limite de blocos << 2³².
- **Ameaça:** chave permanece em memória.
  **Controle:** referência zerada em `finally`; `Secret` limpo; sem persistência.
  **Residual:** cópias do interpretador/SO.
- **Ameaça:** senha fraca.
  **Controle:** mínimo de 8 bytes + estimativa heurística + KDF com custo.
  **Residual:** não há bloqueio de senhas comuns no backend; usuário pode
  escolher `12345678` se ignorar o aviso. A estimativa é local e não garante
  resistência.

### Interface

- **Ameaça:** senha visível na tela.
  **Controle:** campo mascarado, revelação temporária, limpeza após uso.
- **Ameaça:** operação bloqueia a UI.
  **Controle:** worker em thread separada; progresso e cancelamento.
- **Ameaça:** usuário fecha a janela no meio.
  **Controle:** confirmação, cancelamento, espera e limpeza.
- **Ameaça:** mensagem de erro vaza detalhe.
  **Controle:** `safe_error_message`; UI não mostra traceback.
- **Ameaça:** notificação de desktop revela nome de arquivo.
  **Controle:** notificações opcionais; texto não contém segredo.
  **Residual:** nome do arquivo é metadata visível.

### Persistência

- **Ameaça:** SQL injection.
  **Controle:** placeholders `?`, colunas fixas, `CHECK`.
- **Ameaça:** leitura do histórico por outro usuário.
  **Controle:** diretório `0700` e arquivo `0600` (melhor esforço).
  **Residual:** Windows ACLs não são totalmente controladas por `chmod`.
- **Ameaça:** log injection.
  **Controle:** JSON, substituição de controles, redação, campos allowlist.
- **Ameaça:** settings corrompido.
  **Controle:** validação, normalização, defaults, gravação atômica.

### Build e distribuição

- **Ameaça:** dependência vulnerável.
  **Controle:** versões mínimas, `pip-audit`, CI, revisão.
  **Residual:** intervalo de versões não é lockfile; uma instalação futura pode
  resolver versões diferentes dentro das faixas.
- **Ameaça:** binário adulterado.
  **Controle:** build local documentado, SHA-256, self-test.
  **Residual:** sem assinatura Authenticode, sem transparência de build.
- **Ameaça:** DLL hijacking / side-loading no Windows.
  **Controle:** PyInstaller one-file e dependências empacotadas; não há busca
  deliberada em diretórios do usuário.
  **Residual:** ambiente com DLLs maliciosas no PATH ainda pode interferir.

## 8. Cenários de ataque e respostas

### Cenário A — Roubo do `.cvlt`

Atacante obtém o arquivo e tenta offline:

1. **Adulterar** → tags falham; sem saída.
2. **Truncar** → formato inválido; sem saída.
3. **Adivinhar senha** → cada tentativa exige Scrypt (32 MiB, N=2¹⁵). A
   resistência depende da entropia da senha; o app não tem rate limiting porque
   o ataque é offline.
4. **Explorar parser** → limites e testes com Hypothesis reduzem a superfície,
   mas não substituem auditoria.

**Resposta:** senha longa e única; rotação de senha exige reencriptar (não há
rekey).

### Cenário B — Malware no mesmo perfil

1. Keylogger captura a senha.
2. Processo lê a memória do app durante a operação.
3. Processo lê o arquivo em claro antes/depois da operação.
4. Processo altera o executável ou dependências.

**Resposta:** o modelo assume que o SO está íntegro; nenhuma defesa do app é
suficiente contra malware com os mesmos privilégios. Recomenda-se EDR, disco
cifrado, conta separada e executável de fonte confiável.

### Cenário C — Caminho hostil

Usuário é induzido a arrastar `..\..\Windows\System32\algo` ou um symlink.

1. `validate_input_file` exige arquivo regular e rejeita symlink.
2. `sanitize_filename` remove separadores do nome de saída.
3. `validate_output_directory` exige diretório real.
4. `AtomicOutput` confina o temporário ao diretório validado.
5. Commit recusa destino existente e fora do diretório.

**Resposta:** operação recusada com mensagem de caminho inseguro.

### Cenário D — Falha no meio da escrita

1. Queda de energia/erro de disco no bloco N.
2. `AtomicOutput.__exit__` remove o temporário.
3. Nome final nunca aparece.
4. Histórico registra falha (se o processo ainda estiver vivo).

**Resposta:** repetir a operação; não há saída parcial.

### Cenário E — Cancelamento

1. Usuário clica em cancelar.
2. Evento é sinalizado; o motor lança `CancelledError` no próximo bloco.
3. Temporário é removido/sobrescrito; segredo é limpo.
4. Histórico registra cancelamento; UI informa que nenhum final foi publicado.

**Resposta:** consistente por design; KDF em andamento não é interrompido até
terminar.

## 9. Riscos residuais

| Risco | Severidade | Probabilidade | Observação |
| --- | --- | --- | --- |
| Senha fraca quebrada offline | Alta | Média | KDF aumenta custo, mas não corrige entropia |
| Malware/keylogger no mesmo usuário | Alta | Média | fora do controle do app |
| Memória/swap/SSD retém dados | Média | Média | limpeza é melhor esforço |
| Executável não assinado | Média | Média | verificação manual por checksum |
| Dependência comprometida | Alta | Baixa/Média | `pip-audit`, faixas de versão, revisão |
| Histórico/logs alteráveis | Baixa | Alta | não é auditoria |
| TOCTOU de symlink/junction | Média | Baixa | adversário local com escrita no destino |
| Nome/tamanho do arquivo expostos | Baixa | Alta | metadata por design |
| Ausência de auditoria criptográfica independente | Média | — | recomendação antes de uso crítico |
| Sem rate limiting em senha | Baixa | Alta | ataque offline não é limitável pelo app |
| Sem rekey/rotação de senha | Baixa | Média | requer reencriptar |
| Sem assinatura de autoria | Baixa | Alta | fora do escopo |

## 10. Controles verificados por testes

| Controle | Evidência |
| --- | --- |
| Adulteração de tag/ciphertext/salt/nonce | `tests/test_engine.py` |
| Truncamento/anexo/comprimento inválido | `tests/test_engine.py`, `tests/test_format.py` |
| Sem saída parcial em falha de bloco posterior | `test_no_partial_output_when_later_chunk_is_tampered` |
| Sem sobrescrita | `test_no_overwrite_preserves_existing_file`, `test_atomic_output_never_overwrites` |
| Cancelamento sem resíduo | `test_cancel_*` |
| Limites de KDF | `tests/test_format.py`, `tests/test_kdf.py` |
| Path traversal/sanitização | `tests/test_paths.py` (Hypothesis) |
| Redação de logs | `tests/test_logging.py` |
| Senha ausente do SQLite/WAL | `tests/test_service.py` |
| Operação concorrente recusada | `tests/test_service.py` |
| Fluxos reais de UI | `tests/test_ui.py` |
| Self-test do binário | `dist/self-test.json` |

## 11. Fora de escopo e recomendações

**Fora de escopo:** TPM/HSM, autenticação de dois fatores, assinatura digital,
compartilhamento seguro, recuperação de senha, sincronização, auditoria remota,
sandbox contra malware, anti-keylogger, proteção de tela, atualização assinada.

**Recomendações para uso de alto valor:**

1. Use frase-senha longa, única e gerada por gerenciador de senhas.
2. Mantenha o sistema, Python e dependências atualizados.
3. Execute o binário a partir de uma fonte confiável e confira o SHA-256.
4. Use disco integralmente cifrado e bloqueio de tela.
5. Evite operar em máquina com malware conhecido ou conta compartilhada.
6. Faça backup dos `.cvlt` e teste a recuperação periodicamente.
7. Considere auditoria independente antes de proteger dados regulados.
8. Para dados de alto valor, combine com assinatura de código e distribuição
   autenticada.

## 12. Revisão

Este modelo deve ser revisto quando:

- o formato, KDF, algoritmo ou limites mudarem;
- houver nova superfície (rede, plugins, auto-update, compartilhamento);
- uma vulnerabilidade for relatada;
- o alvo de plataforma ou empacotamento mudar;
- uma auditoria externa for realizada.

Última revisão: 2026-11-03, correspondente à versão 1.0.0.
