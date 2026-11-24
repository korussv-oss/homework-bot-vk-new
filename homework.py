import logging
import os
import sys
import time
from http import HTTPStatus
from random import randrange

import requests
import vk_api
from dotenv import load_dotenv

from exceptions import (
    APIResponseError,
    InvalidResponseCodeError,
    MissingTokenError,
    UnknownHomeworkStatusError,
)

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format=(
        '%(asctime)s [%(levelname)s] '
        '%(filename)s:%(funcName)s:%(lineno)d %(message)s'
    ),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'{__file__}.log', encoding='utf-8'),
    ]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ('PRACTICUM_TOKEN', 'VK_TOKEN', 'VK_USER_ID')


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing = [name for name in TOKENS if not globals().get(name)]
    if missing:
        message = (
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing)}'
        )
        logging.critical(message)
        raise MissingTokenError(message)


def send_message(vk, message):
    """Отправляет сообщение в VK-чат пользователя VK_USER_ID."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=randrange(10**10)
        )
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в VK: {error}')
        return False
    logging.debug(f'Бот отправил сообщение "{message}"')
    return True


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API сервиса Практикум Домашка."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    logging.info(
        'Начали запрос к API: {url} с заголовками {headers} '
        'и параметрами {params}'.format(**request_params)
    )
    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise ConnectionError(
            'Сбой при запросе к {url} с заголовками {headers} '
            'и параметрами {params}: {error}'.format(
                error=error, **request_params
            )
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeError(
            'Неверный код ответа API: {code}, причина: {reason}, '
            'текст: {text}'.format(
                code=response.status_code,
                reason=response.reason,
                text=response.text,
            )
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарём, получен {type(response)}'
        )
    if 'homeworks' not in response:
        raise APIResponseError(
            'Отсутствует ожидаемый ключ homeworks в ответе API'
        )
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Данные по ключу homeworks должны быть списком, '
            f'получены {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает текст уведомления."""
    if 'homework_name' not in homework:
        raise APIResponseError(
            'Отсутствует ключ homework_name в ответе API'
        )
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise APIResponseError('Отсутствует ключ status в ответе API')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise UnknownHomeworkStatusError(
            f'Неожиданный статус домашней работы: {status}'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Отсутствие в ответе новых статусов')
                continue
            message = parse_status(homeworks[0])
            if message != last_message and send_message(vk, message):
                last_message = message
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            current_message = f'Сбой в работе программы: {error}'
            logging.exception(current_message)
            if (
                current_message != last_message
                and send_message(vk, current_message)
            ):
                last_message = current_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
