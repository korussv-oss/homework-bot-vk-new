class HomeworkBotError(Exception):
    """Базовое исключение бота проверки домашней работы."""


class MissingTokenError(HomeworkBotError):
    """Отсутствует обязательная переменная окружения."""


class InvalidResponseCodeError(HomeworkBotError):
    """API вернул неожиданный HTTP-код."""


class APIResponseError(HomeworkBotError):
    """Ответ API не соответствует ожидаемой структуре."""


class UnknownHomeworkStatusError(ValueError):
    """API вернул недокументированный статус домашней работы."""
