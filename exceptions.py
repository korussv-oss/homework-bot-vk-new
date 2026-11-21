class HomeworkBotError(Exception):
    """Базовое исключение бота проверки домашней работы."""


class APIRequestError(HomeworkBotError):
    """Ошибка при запросе к API Практикум.Домашка."""


class APIResponseError(HomeworkBotError):
    """Ответ API не соответствует ожидаемой структуре."""


class UnknownHomeworkStatusError(HomeworkBotError):
    """API вернул недокументированный статус домашней работы."""
