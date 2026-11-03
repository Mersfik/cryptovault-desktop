# Política de segurança — CryptoVault Desktop

## 1. Versões suportadas

| Versão | Suporte de segurança |
| --- | --- |
| 1.0.x | Sim |
| < 1.0 | Não |

Apenas a versão mais recente da linha 1.x recebe correções. Como o aplicativo é
local e não possui auto-atualização, o usuário deve substituir o executável
manualmente ao receber uma nova versão.

## 2. Como relatar uma vulnerabilidade

**Não abra uma issue pública para vulnerabilidades não corrigidas.**

Use o canal privado do repositório oficial:

1. Acesse a aba **Security** do repositório no GitHub.
2. Escolha **Report a vulnerability** / **Security advisories**.
3. Inclua, se possível:
   - versão do CryptoVault e hash SHA-256 do executável;
   - versão do Windows e do Python (se executar pelo código);
   - passos de reprodução mínimos;
   - impacto observado e esperado;
   - arquivos de exemplo **sem dados reais** (nunca envie sua senha);
   - logs sanitizados, se forem relevantes.

Se o repositório ainda não estiver publicado, substitua esta seção pelo contato
privado do mantenedor antes de distribuir o projeto. Nunca publique detalhes
exploráveis antes da correção.

### O que esperar

- Confirmação de recebimento: meta de 3 dias úteis.
- Avaliação inicial e classificação: meta de 10 dias úteis.
- Correção ou plano: depende da severidade e complexidade.
- Crédito: opcional, se o relator desejar.

Esses prazos são metas de melhor esforço, não garantias contratuais.

### Escopo elegível

- falhas na autenticação/confidencialidade do formato ou do motor;
- bypass de validação de caminho, sobrescrita ou publicação parcial;
- vazamento de senha/chave/conteúdo em logs, histórico, UI ou mensagens;
- negação de serviço causada por entrada maliciosa;
- vulnerabilidades no processo de build/distribuição;
- dependências vulneráveis usadas em runtime.

### Fora de escopo

- ataques que exigem malware, keylogger, root, administrador ou acesso físico
  com o app em execução;
- engenharia social, phishing ou spoof visual do sistema operacional;
- senhas fracas escolhidas pelo usuário;
- falta de assinatura de código (limitação conhecida, não vulnerabilidade);
- relatos automatizados sem impacto demonstrável;
- versões antigas não suportadas.

## 3. Postura de segurança

O CryptoVault Desktop foi projetado para proteger arquivos **em repouso** contra
quem obtém o envelope `.cvlt` sem a senha. As decisões centrais são:

- **AES-256-GCM** com tag de 128 bits e nonce de 96 bits;
- **Scrypt** com `N=2^15`, `r=8`, `p=1`, salt de 32 bytes;
- **streaming** de 1 MiB com AAD do cabeçalho, índice, comprimento e marcador
  final;
- **publicação atômica** e sem sobrescrita;
- **nenhuma persistência** de senha, chave ou conteúdo;
- **logs e histórico** sem segredos e com caminhos sanitizados;
- **processamento em worker** para manter a UI responsiva;
- **cancelamento seguro** com remoção do temporário;
- **uma operação por vez** por instância/usuário;
- **instância única** com `QLockFile`;
- **sem rede**: nenhum arquivo, senha ou telemetria é enviado.

Detalhes técnicos: [CRYPTOGRAPHY.md](CRYPTOGRAPHY.md) e
[ARCHITECTURE.md](ARCHITECTURE.md). Modelo de ameaças:
[THREAT_MODEL.md](THREAT_MODEL.md).

## 4. Uso seguro

### Senha

- Use uma **frase-senha longa, única e aleatória**, preferencialmente gerada por
  um gerenciador de senhas.
- **Não há recuperação de senha.** Se perdida, os dados são irrecuperáveis.
- Não reutilize a senha de outros serviços.
- Evite padrões óbvios (`12345678`, `senha123`, datas, nomes). A estimativa da
  interface é heurística e não mede resistência real.
- Não compartilhe a senha por e-mail, chat ou captura de tela.
- Ao usar máquina compartilhada, prefira uma conta de usuário separada.

### Arquivos e diretórios

- Mantenha o `.cvlt` e o original em locais com backup confiável.
- Verifique o SHA-256 do executável recebido contra o publicado.
- Não execute o binário de diretórios não confiáveis ou com DLLs suspeitas.
- Use disco integralmente cifrado (BitLocker, LUKS, FileVault) para reduzir
  exposição de temporários, swap e histórico.
- Armazene o `.cvlt` em mídia confiável; o envelope autentica o conteúdo, mas
  não impede exclusão/ransomware.
- Teste periodicamente a recuperação de um arquivo crítico.

### Histórico, configurações e logs

- O histórico registra **nome do arquivo**, operação, horário, resultado,
  tamanho e duração. Ele **não** registra senha, chave ou conteúdo.
- O histórico **não é auditoria inviolável**: quem tem acesso ao perfil pode
  alterá-lo ou apagá-lo.
- Os logs são JSON rotativos e sanitizados, mas ainda podem revelar nomes de
  arquivos e horários.
- Se esses metadados forem sensíveis, limpe o histórico e os logs ou use um
  diretório de dados protegido.
- O diretório padrão é `%LOCALAPPDATA%\CryptoVault`; pode ser alterado com
  `--data-dir` ou `CRYPTOVAULT_DATA_DIR`.

### Cancelamento e encerramento

- Cancelar remove o temporário e não publica arquivo parcial.
- Fechar a janela durante uma operação pede confirmação e tenta cancelar.
- Uma operação de KDF em andamento não é interrompida no meio; o cancelamento
  ocorre no próximo ponto seguro.

## 5. Limitações conhecidas

Estas limitações são **de projeto**, não bugs:

1. **Sem recuperação de senha.** Não há backdoor, pergunta secreta ou chave de
   recuperação.
2. **Sem assinatura de autoria.** O envelope prova posse da senha e integridade,
   não quem criou o arquivo.
3. **Metadados não são confidenciais.** O cabeçalho revela que é CryptoVault v1,
   algoritmo, KDF, tamanho em claro e salt/nonce. O histórico revela nomes e
   horários.
4. **Sem proteção contra malware.** Keylogger, screen capture, injeção, leitura
   de memória e ransomware com os mesmos privilégios vencem o modelo.
5. **Limpeza de memória é melhor esforço.** Python, bibliotecas, SO, swap,
   hibernação, crash dumps e SSD/COW podem reter cópias.
6. **Sobrescrita de temporário é melhor esforço.** Não há garantia física de
   apagamento em SSD, sistemas com journaling ou snapshots.
7. **Sem rate limiting offline.** Um atacante com o `.cvlt` pode tentar senhas
   offline; o KDF aumenta o custo, mas não corrige senha fraca.
8. **Sem rekey/rotação de senha.** Trocar a senha exige descriptografar e
   criptografar novamente.
9. **Sem verificação de senhas vazadas.** O app não faz rede.
10. **Executável não assinado.** A integridade depende do canal e do checksum.
11. **Sem auto-update.** Correções exigem substituição manual.
12. **Histórico e logs não são à prova de adulteração.** São arquivos locais.
13. **Symlink/junction no Windows.** A semântica de reparse points é parcial e
    os testes de symlink são ignorados nessa plataforma.
14. **Sem auditoria independente.** O formato e a implementação não foram
    certificados por terceiros.
15. **Escopo local e monousuário.** Não há contas, permissões ou isolamento
    entre usuários do mesmo perfil.

## 6. Dependências e supply chain

- Runtime: `PySide6>=6.9.3,<7` e `cryptography>=50.0.2,<51`.
- Desenvolvimento: pytest, pytest-qt, pytest-cov, Hypothesis, Ruff, Bandit,
  pip-audit e PyInstaller.
- Versões mínimas foram elevadas após auditoria (`cryptography 50.0.2`,
  `pytest 9.0.3`).
- `pip-audit` é executado localmente e no CI; resultado registrado em
  `docs/verification/`.
- As faixas de versão **não são um lockfile com hashes**. Para builds de alto
  valor, gere um lockfile e verifique hashes.
- Não há Dependabot/Renovate configurado por padrão; recomenda-se habilitar.
- O executável é construído com PyInstaller a partir do código deste
  repositório, mas o build não é atestado/reproduzível de forma verificável.

## 7. Build e verificação de integridade

```powershell
# 1. Construir
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1

# 2. Conferir checksum
Get-FileHash -Algorithm SHA256 dist\CryptoVault.exe
Get-Content dist\CryptoVault.exe.sha256

# 3. Self-test do binário
Start-Process -FilePath dist\CryptoVault.exe `
  -ArgumentList @("--self-test", "--report", "dist\self-test.json") `
  -Wait -PassThru
Get-Content dist\self-test.json
```

O self-test cobre: criptografia, verificação autenticada, descriptografia,
rejeição de adulteração, rejeição de senha errada e ausência de resíduos.

## 8. Resposta a incidentes

Se você suspeitar de comprometimento:

1. **Desconecte** a máquina da rede, se possível.
2. **Não apague** evidências antes de copiar logs relevantes.
3. **Presuma que a senha foi exposta** se houve keylogger/malware.
4. Reencripte os arquivos com uma nova senha em um sistema limpo.
5. Revogue/rotacione credenciais que possam ter sido expostas.
6. Verifique a integridade dos `.cvlt` com a tela **Verificar**.
7. Se o binário foi obtido de fonte duvidosa, rebaixe de fonte oficial e confira
   o SHA-256.
8. Relate a vulnerabilidade por canal privado, se aplicável.

O CryptoVault não tem capacidade de “revogar” um arquivo ou uma senha: a
segurança após a exposição depende de reencriptação e de uma nova senha.

## 9. Boas práticas para desenvolvedores

Antes de contribuir, leia [CONTRIBUTING.md](CONTRIBUTING.md). Em especial:

- não registre senha, chave, conteúdo ou caminho completo;
- não adicione algoritmo legado, ECB, DES, SHA-1 ou MD5;
- não reduza tag, nonce, KDF ou validação de autenticação;
- não publique saída antes de validar todos os blocos;
- não use `shell=True`, `eval` ou SQL concatenado;
- adicione teste para toda correção de segurança;
- execute `ruff`, `bandit`, `pip-audit` e `pytest` antes de enviar.

## 10. Isenção de garantia

O software é fornecido “como está”, sem garantia de adequação a um propósito
específico. Consulte [LICENSE](LICENSE). Nenhuma afirmação deste documento
constitui certificação, garantia de segurança absoluta ou aconselhamento
jurídico/regulatório.

Última atualização: 2026-11-03.
