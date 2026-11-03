"""Exceções de domínio com mensagens seguras para apresentação."""

from __future__ import annotations


class CryptoVaultError(Exception):
    code = "cryptovault_error"
    user_message = "Não foi possível concluir a operação."

    def __init__(self, detail: str = "", *, user_message: str | None = None) -> None:
        super().__init__(detail or self.user_message)
        self.detail = detail
        if user_message is not None:
            self.user_message = user_message


class ValidationError(CryptoVaultError):
    code = "validation_error"
    user_message = "Os dados informados são inválidos."


class PasswordError(ValidationError):
    code = "password_error"
    user_message = "A senha não atende aos requisitos mínimos."


class FormatError(CryptoVaultError):
    code = "invalid_format"
    user_message = "O arquivo não possui um formato CryptoVault válido."


class UnsupportedVersionError(FormatError):
    code = "unsupported_version"
    user_message = "A versão deste arquivo não é suportada por esta aplicação."


class AuthenticationError(CryptoVaultError):
    code = "authentication_failed"
    user_message = "Senha incorreta ou arquivo adulterado/corrompido."


class PathSecurityError(ValidationError):
    code = "unsafe_path"
    user_message = "O caminho selecionado não é seguro ou não é permitido."


class SizeLimitError(ValidationError):
    code = "size_limit"
    user_message = "O arquivo excede o limite de tamanho suportado."


class OutputError(CryptoVaultError):
    code = "output_error"
    user_message = "Não foi possível gravar o arquivo de saída com segurança."


class OutputExistsError(OutputError):
    code = "output_exists"
    user_message = "Já existe um arquivo no destino. Nenhum arquivo foi sobrescrito."


class InsufficientSpaceError(OutputError):
    code = "insufficient_space"
    user_message = "Não há espaço livre suficiente no diretório de destino."


class CancelledError(CryptoVaultError):
    code = "cancelled"
    user_message = "Operação cancelada."


class BusyError(CryptoVaultError):
    code = "busy"
    user_message = "Já existe uma operação em andamento."


class HistoryError(CryptoVaultError):
    code = "history_error"
    user_message = "Não foi possível acessar o histórico de operações."


class SettingsError(CryptoVaultError):
    code = "settings_error"
    user_message = "Não foi possível ler ou salvar as configurações."


def safe_error_message(exc: BaseException) -> str:
    """Converte exceções internas em mensagens que não exponham segredos."""
    if isinstance(exc, CryptoVaultError):
        return exc.user_message
    return "Ocorreu um erro interno. Consulte o log da aplicação."
