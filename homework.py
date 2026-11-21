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
    APIRequestError,
    APIResponseError,
    UnknownHomeworkStatusError,
)

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
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
REQUIRED_RESPONSE_KEYS = ('homeworks', 'current_date')


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing = [name for name in TOKENS if not globals().get(name)]
    if missing:
        logging.critical(
            'Отсутствуют обязательные переменные окружения: %s',
            ', '.join(missing)
        )
        return False
    logging.info('Переменные окружения проверены, бот может быть запущен.')
    return True


def send_message(vk, message):
    """Отправляет сообщение в VK-чат пользователя VK_USER_ID."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=randrange(10**10)
        )
    except Exception as error:
        logging.error('Сбой при отправке сообщения в VK: %s', error)
        raise
    logging.debug('Бот отправил сообщение "%s"', message)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API сервиса Практикум Домашка."""
    params = {'from_date': timestamp}
    try:
        logging.info(
            'Запрос к API: %s, from_date=%s', ENDPOINT, timestamp
        )
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise APIRequestError(
            f'Сбой при запросе к эндпоинту {ENDPOINT}: {error}'
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise APIRequestError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарём, получен {type(response)}'
        )
    for key in REQUIRED_RESPONSE_KEYS:
        if key not in response:
            logging.error('Отсутствует ожидаемый ключ %s в ответе API', key)
            raise APIResponseError(
                f'Отсутствует ожидаемый ключ {key} в ответе API'
            )
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Данные по ключу homeworks должны быть списком, '
            f'получен {type(homeworks)}'
        )


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
    if not check_tokens():
        sys.exit(
            'Программа остановлена: нет обязательных переменных окружения.'
        )

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(vk, message)
                    last_message = message
                else:
                    logging.warning(
                        'Повторное сообщение в VK не отправлено: %s',
                        message
                    )
            else:
                logging.debug('Отсутствие в ответе новых статусов')
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                try:
                    send_message(vk, message)
                    last_message = message
                except Exception:
                    pass
            else:
                logging.warning(
                    'Повторное сообщение об ошибке в VK не отправлено.'
                )
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
