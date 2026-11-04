# Criptografia — CryptoVault Desktop

Este documento especifica as primitivas, o formato binário, o ciclo de vida das
chaves e as propriedades de segurança do CryptoVault v1. Ele descreve o que o
código faz hoje; não é uma certificação independente.

## 1. Modelo de proteção

O CryptoVault protege **arquivos em repouso** contra leitura ou modificação por
quem obtém o arquivo `.cvlt` sem conhecer a senha. A garantia é:

- **confidencialidade** do conteúdo em relação a quem não tem a senha;
- **integridade e autenticidade** do conteúdo e dos metadados do envelope;
- **detecção de truncamento, anexo e alteração** de qualquer byte coberto pela
  autenticação.

O modelo **não** protege contra:

- malware, keylogger, captura de tela ou processo com os mesmos privilégios;
- acesso físico ao computador enquanto a operação está em andamento;
- memória, swap, hibernação, crash dumps ou backups que retenham cópias;
- adversário que conhece ou adivinha a senha;
- perda da senha (não há recuperação);
- autoria ou origem do arquivo (não há assinatura digital).

## 2. Primitivas

| Função | Escolha | Parâmetros |
| --- | --- | --- |
| Cifra autenticada | AES-256-GCM | chave de 256 bits, tag de 128 bits, nonce de 96 bits |
| Derivação de chave | Scrypt | `N=2^15` (32768), `r=8`, `p=1`, salt de 32 bytes, saída de 32 bytes |
| Aleatoriedade | `secrets.token_bytes` | salt e prefixo de nonce |
| Hash de identificação | SHA-256 truncado | fingerprint de 16 hex chars do cabeçalho |
| Comparação | `hmac.compare_digest` | usada apenas onde necessário |
| Empacotamento | `struct` big-endian | layout fixo e versionado |

Não são usados: ECB, CBC sem autenticação, DES/3DES, RC4, SHA-1, MD5, RSA,
curvas elípticas, compressão antes da cifra ou criptografia caseira. O
`cryptography` fornece AES-GCM e Scrypt; o projeto não implementa primitivas
criptográficas.

### Por que Scrypt

Scrypt é resistente a hardware dedicado por exigir memória, está disponível no
`cryptography` sem dependência adicional e tem parâmetros bem definidos. Argon2id
é uma alternativa moderna e pode ser adicionada em uma versão futura do formato
com um novo `kdf_id`; o v1 não a utiliza. A escolha não afirma que Scrypt seja
superior a Argon2id em todos os cenários.

### Custo do KDF

A memória aproximada do Scrypt é `128 × N × r` bytes:

| Parâmetros | Memória aproximada | Situação |
| --- | ---: | --- |
| `N=2^15, r=8, p=1` (padrão) | 32 MiB | usado para novos arquivos |
| `N=2^18, r=8, p=1` | 256 MiB | limite máximo aceito |
| `N=2^18, r=16, p=4` | 512 MiB | rejeitado pelo teto de 256 MiB |

Limites aceitos pelo parser e pelo motor:

- `log2(N)` entre 15 e 18 (inclusive);
- `r` entre 8 e 16;
- `p` entre 1 e 4;
- memória estimada ≤ 256 MiB;
- salt exatamente 32 bytes.

Um cabeçalho com parâmetros fora desses limites é rejeitado **antes** de derivar
a chave, evitando que um arquivo hostil force consumo excessivo de memória/CPU.
O teto de memória não impede deliberadamente um ataque local de negação de
serviço com muitos arquivos, mas limita o custo por tentativa.

## 3. Ciclo de vida da chave e da senha

1. A UI recebe a senha em um `QLineEdit` com modo senha e permite revelação
   temporária.
2. `Secret` valida o tamanho (8 a 1024 bytes) e guarda uma `bytearray`.
3. O controlador entrega o `Secret` ao worker; o worker chama o serviço.
4. O serviço usa `secret.bytes_copy()` para obter uma cópia imutável de vida
   curta. O `Secret` original é limpo pelo worker no `finally`; se o serviço
   recebeu uma `str`/`bytes`, ele cria e limpa o próprio `Secret`.
5. O motor codifica a senha em UTF-8 e chama `Scrypt.derive`.
6. A chave de 32 bytes é usada em `AESGCM(key)` e a referência é zerada no
   `finally` (`key = b""`). O Python não garante que a memória seja sobrescrita;
   a limpeza é melhor esforço.
7. A senha nunca é gravada em `settings.json`, `history.db` ou logs. O campo da
   UI é limpo após o início e após o resultado.

**Limitação:** strings Python são imutáveis e podem ser copiadas pelo
interpretador, pela biblioteca ou pelo sistema. Não é possível garantir remoção
física de todas as cópias na memória. O aplicativo reduz a janela de exposição,
mas não a elimina.

## 4. Formato CryptoVault v1

Extensão sugerida: `.cvlt`. Todo o envelope é escrito em big-endian.

### 4.1 Cabeçalho (80 bytes)

| Offset | Tamanho | Campo | Valor/observação |
| ---: | ---: | --- | --- |
| 0 | 8 | `magic` | ASCII `CVLTFILE` |
| 8 | 1 | `format_version` | `1` |
| 9 | 1 | `algorithm_id` | `1` = AES-256-GCM |
| 10 | 1 | `kdf_id` | `1` = Scrypt |
| 11 | 1 | `kdf_log2_n` | 15–18 |
| 12 | 4 | `kdf_r` | 8–16 |
| 16 | 4 | `kdf_p` | 1–4 |
| 20 | 1 | `salt_length` | `32` |
| 21 | 32 | `salt` | aleatório por arquivo |
| 53 | 1 | `nonce_prefix_length` | `8` |
| 54 | 8 | `nonce_prefix` | aleatório por arquivo |
| 62 | 4 | `chunk_size` | `1 048 576` (1 MiB) |
| 66 | 8 | `plaintext_size` | tamanho em claro, 0–100 GiB |
| 74 | 1 | `flags` | `0` |
| 75 | 5 | `reserved` | cinco bytes zero |

O parser rejeita magic inválido, versão desconhecida, algoritmo/KDF
desconhecidos, tamanhos de salt/nonce inválidos, `chunk_size` diferente de 1 MiB,
flags não zero, bytes reservados não zero, salt/prefixo totalmente zero, tamanho
acima de 100 GiB e combinação de tamanho/blocos inconsistente.

O SHA-256 do cabeçalho, truncado para 16 caracteres hexadecimais, é exibido como
**fingerprint**. Ele serve para comparar envelopes e identificar mudanças de
metadados; **não** é uma assinatura e não prova origem.

### 4.2 Registros de conteúdo

Cada registro tem:

```text
uint32 big-endian  plaintext_len
bytes              ciphertext (mesmo comprimento de plaintext_len)
bytes              tag GCM (16 bytes)
```

O comprimento em claro é autenticado como AAD. O parser do motor exige que
`plaintext_len` seja exatamente o esperado para a posição:

- blocos cheios: 1 MiB;
- último bloco: `plaintext_size mod 1 MiB` (ou 1 MiB, se divisível);
- arquivo vazio: um único registro com `plaintext_len = 0` e tag de 16 bytes.

Um arquivo vazio tem 80 + 4 + 16 = **100 bytes**. O GCM de um texto vazio ainda
produz uma tag autenticada, portanto o arquivo vazio não fica “sem
autenticação”.

### 4.3 Nonce

Nonce de 96 bits:

```text
nonce = nonce_prefix (8 bytes aleatórios) || contador (uint32 big-endian)
```

- O prefixo é novo para cada arquivo, gerado por `secrets.token_bytes(8)`.
- O contador começa em 0 e incrementa por registro.
- O limite do formato é 100 GiB / 1 MiB = 102.400 registros, muito abaixo de
  `2^32`. O contador nunca é reutilizado dentro de um arquivo.
- Como cada arquivo usa salt e prefixo novos, a chave derivada também é nova
  (probabilisticamente); não há reutilização de par (chave, nonce) entre
  arquivos.
- O nonce não é secreto; ele é autenticado indiretamente porque o cabeçalho
  inteiro entra no AAD.

### 4.4 AAD

Para o registro de índice `i`:

```text
AAD = header_bytes (80 bytes)
    || uint64(index)
    || uint32(plaintext_len)
    || uint8(final ? 1 : 0)
```

Isso autentica:

- todos os metadados do cabeçalho (versão, algoritmo, KDF, salt, prefixo,
  tamanho, chunk size, flags);
- a posição do registro;
- o comprimento em claro;
- se o registro é o último.

Consequências:

- trocar salt, nonce, KDF, tamanho ou versão invalida a tag;
- reordenar registros invalida a tag;
- truncar, anexar ou alterar comprimento invalida a estrutura e/ou a tag;
- um registro de outro arquivo não se encaixa, pois o cabeçalho e o índice
  fazem parte do AAD.

### 4.5 Overhead

Para `n = max(1, ceil(plaintext_size / 1 MiB))`:

```text
tamanho_cifrado = 80 + plaintext_size + n × (4 + 16)
```

Exemplos:

| Arquivo em claro | Blocos | Overhead |
| ---: | ---: | ---: |
| 0 B | 1 | 100 B |
| 1 KiB | 1 | 100 B |
| 1 MiB | 1 | 100 B |
| 1 MiB + 1 B | 2 | 120 B |
| 2 MiB | 2 | 120 B |
| 2 MiB + 1 B | 3 | 140 B |

O espaço livre exigido inclui o envelope mais uma reserva de 16 MiB.

## 5. Algoritmo de criptografia

```text
entrada: source, destination, password, kdf_params
1. validar source (arquivo regular, sem symlink, ≤100 GiB)
2. validar destination.parent (diretório real, gravável)
3. recusar destination existente ou igual a source
4. abrir source com O_RDONLY|O_NOFOLLOW e guardar fstat
5. verificar espaço livre
6. salt ← 32 bytes aleatórios
7. nonce_prefix ← 8 bytes aleatórios
8. header ← build_header(salt, nonce_prefix, plaintext_size, params)
9. key ← Scrypt(password, salt, N, r, p, 32 bytes)
10. abrir AtomicOutput no diretório de destino
11. escrever header
12. para cada bloco de até 1 MiB:
      nonce ← nonce_prefix || counter
      final ← (não há próximo bloco)
      aad ← header || counter || len(bloco) || final
      ct ← AESGCM.encrypt(nonce, bloco, aad)
      escrever uint32(len(bloco)) || ct || tag
      counter ← counter + 1
13. conferir que source não mudou (tamanho/mtime)
14. commit atômico sem sobrescrever
```

O laço lê um bloco “à frente” para saber se o atual é o último. Isso evita
precisar de um indicador separado de fim e garante que o AAD marque corretamente
o registro final.

## 6. Algoritmo de descriptografia

```text
1. validar destination.parent
2. recusar destination existente
3. abrir source seguro
4. ler e validar header (80 bytes)
5. verificar espaço livre para plaintext_size
6. key ← Scrypt(password, salt, N, r, p, 32)
7. abrir AtomicOutput sensível
8. remaining ← plaintext_size; index ← 0
9. enquanto verdadeiro:
     expected_len ← min(1 MiB, remaining)
     final ← (remaining == expected_len)
     ler uint32 declarado
     exigir declarado == expected_len
     ler declarado + 16 bytes
     nonce ← prefixo || index
     aad ← header || index || declarado || final
     plaintext ← AESGCM.decrypt(nonce, registro, aad)   # valida tag
     escrever plaintext no temporário
     remaining ← remaining - len(plaintext)
     se final:
         exigir que não haja bytes extras
         parar
     index ← index + 1
10. exigir total recuperado == plaintext_size
11. conferir que source não mudou
12. commit atômico
```

Nenhum bloco em claro é escrito antes da validação da tag correspondente. O
temporário pode conter blocos já autenticados se um bloco posterior falhar, mas
ele é removido (e sobrescrito em melhor esforço) no `finally`; o nome final nunca
é publicado.

## 7. Verificação

`verify_file` percorre o mesmo caminho autenticado, descarta os blocos e mapeia
falhas:

| Situação | Status |
| --- | --- |
| tudo válido | `AUTHENTICATED` |
| tag inválida (senha ou adulteração) | `INVALID_AUTHENTICATION` |
| truncamento, comprimento inconsistente, bytes extras | `INVALID_FORMAT` |
| versão desconhecida | `UNSUPPORTED_VERSION` |

A verificação **não** grava o conteúdo em claro. Ela também não promete que o
arquivo está livre de malware; apenas que os bytes conferem com a chave derivada
da senha fornecida.

## 8. Propriedades e garantias

### O que o GCM garante

- Confidencialidade sob a suposição de que a chave e o nonce não se repetem.
- Integridade e autenticidade do ciphertext e do AAD associado.
- Detecção de qualquer alteração de bit no ciphertext, tag, cabeçalho ou
  metadados de registro, com probabilidade desprezível de falso positivo
  (tag de 128 bits).

### O que o formato acrescenta

- Associação explícita entre conteúdo, cabeçalho, índice, comprimento e marcador
  final.
- Rejeição de truncamento e de dados anexados.
- Rejeição de parâmetros de KDF abusivos antes da derivação.
- Publicação atômica: não há saída final parcial.

### O que não é garantido

- Resistência a um adversário que conhece a senha.
- Resistência a comprometimento do sistema operacional, do Python, do
  `cryptography` ou do executável.
- Apagamento físico garantido de memória, temporários, swap, SSD, backups ou
  snapshots.
- Anonimato do nome do arquivo, do tamanho aproximado ou do fato de que um
  arquivo é um envelope CryptoVault.
- Autoria, origem ou “arquivo seguro”.
- Proteção contra análise de tráfego (não há tráfego de rede).

## 9. Comparação e escolhas de design

| Alternativa | Por que não foi usada |
| --- | --- |
| AES-CBC + HMAC separado | mais complexo, fácil de montar incorretamente |
| AES-GCM com nonce aleatório por bloco | risco de colisão e necessidade de armazenar 12 bytes por bloco |
| Contador global sem prefixo | reutilização entre arquivos se a chave se repetir |
| Um único GCM para o arquivo inteiro | exige carregar tudo em memória, inviável para arquivos grandes |
| Compressão antes da cifra | vaza padrões e adiciona complexidade; não é objetivo |
| Argon2id | boa opção, mas exigiria dependência/roteiro adicional; pode ser `kdf_id=2` no futuro |
| Cifra de fluxo | não oferece autenticação integrada |
| Hash da senha como chave | inadequado; KDF é obrigatório |

## 10. Limites e validações

| Item | Limite |
| --- | --- |
| Tamanho do arquivo em claro | 100 GiB |
| Bloco | 1 MiB fixo |
| Salt | 32 bytes |
| Nonce | 12 bytes (8 + 4) |
| Tag | 16 bytes |
| Chave | 32 bytes |
| Senha | 8–1024 bytes (aplicação); não vazia/≤1024 no KDF |
| `log2(N)` | 15–18 |
| `r` | 8–16 |
| `p` | 1–4 |
| Memória do KDF | ≤256 MiB |
| Flags | 0 |
| Bytes reservados | 0 |

## 11. Testes criptográficos

A suíte cobre, entre outros:

- round-trip para 0 B, 1 B, 1 KiB, 1 MiB, 1 MiB + 1 B e múltiplos blocos;
- senha errada sem publicar saída;
- alteração de tag, ciphertext, salt e nonce;
- truncamento, anexo e comprimento inconsistente;
- adulteração do segundo bloco sem saída parcial;
- verificação autenticada, senha errada e truncamento;
- recusa de sobrescrita;
- cancelamento antes e durante a operação sem temporário;
- monotonicidade do progresso;
- parâmetros de KDF fora dos limites;
- parser com dados arbitrários (Hypothesis) sem exceções inesperadas;
- nonce de 96 bits e exclusividade por contador;
- AAD sensível a índice, comprimento e marcador final.

O self-test do executável executa um ciclo real de 2 MiB + 317 bytes, verifica
adulteração, senha errada e ausência de resíduos.

## 12. Status de validação

- Implementação exercitada por **121 testes** (4 ignorados no Windows por
  semântica POSIX), com cobertura global de **83%** (excluindo `app.py` e
  `__main__.py`).
- `ruff`, `bandit` e `pip-audit` sem achados na versão registrada em
  `docs/verification/`.
- **Não houve auditoria criptográfica independente nem revisão formal de
  protocolo.** O formato é simples e documentado, mas deve ser tratado como
  implementação de referência do projeto, não como padrão certificado.
- Antes de uso de alto valor, recomenda-se revisão por especialista,
  testes de interoperabilidade e análise de parâmetros de KDF no hardware alvo.

## 13. Compatibilidade futura

O leitor v1 rejeita qualquer versão diferente de 1. Uma versão futura deve:

1. incrementar `FORMAT_VERSION` (e, se necessário, `algorithm_id`/`kdf_id`);
2. manter um leitor explícito para v1;
3. documentar a migração e os novos limites;
4. adicionar vetores de teste e atualizar o self-test;
5. não alterar o significado dos campos existentes.

A adição de Argon2id, por exemplo, deve usar um novo `kdf_id`, preservando a
capacidade de abrir arquivos v1 com Scrypt.
