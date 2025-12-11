"""Сервис для работы с Telegram User Bot (отправка сообщений от имени аккаунта)"""
import asyncio
import os
import threading
from config import TELEGRAM_SESSION_PATH

# Отложенный импорт Pyrogram, чтобы избежать проблем с event loop при импорте
PYROGRAM_AVAILABLE = None
Client = None
FloodWait = None
UserNotParticipant = None
ChatWriteForbidden = None

def _import_pyrogram():
    """Ленивый импорт Pyrogram с созданием event loop если нужно"""
    global PYROGRAM_AVAILABLE, Client, FloodWait, UserNotParticipant, ChatWriteForbidden
    
    if PYROGRAM_AVAILABLE is not None:
        return PYROGRAM_AVAILABLE
    
    try:
        # Создаем event loop перед импортом, если его нет
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        from pyrogram import Client
        from pyrogram.errors import FloodWait, UserNotParticipant, ChatWriteForbidden
        PYROGRAM_AVAILABLE = True
        return True
    except ImportError:
        PYROGRAM_AVAILABLE = False
        Client = None
        FloodWait = None
        UserNotParticipant = None
        ChatWriteForbidden = None
        return False
    except Exception as e:
        print(f"Ошибка при импорте Pyrogram: {e}")
        PYROGRAM_AVAILABLE = False
        return False

# Глобальный клиент User Bot
_user_bot_client = None
_user_bot_lock = threading.Lock()  # Используем threading.Lock для синхронизации между потоками
_user_bot_loop = None  # Целевой event loop для клиента
_loop_creation_lock = threading.Lock()


def _ensure_user_bot_loop():
    """Возвращает event loop, который используется для работы User Bot"""
    global _user_bot_loop
    with _loop_creation_lock:
        if _user_bot_loop is None or _user_bot_loop.is_closed():
            _user_bot_loop = asyncio.new_event_loop()
        return _user_bot_loop


def get_user_bot_settings_from_db():
    """Получение настроек User Bot из базы данных"""
    try:
        from database import get_db
        with get_db() as conn:
            settings = {}
            for key in ['telegram_api_id', 'telegram_api_hash', 'telegram_phone_number']:
                setting = conn.execute(
                    'SELECT value FROM system_settings WHERE key = ?',
                    (key,)
                ).fetchone()
                if setting:
                    settings[key] = setting['value']
            
            # Если настройки найдены в БД, возвращаем их
            if settings.get('telegram_api_id') and settings.get('telegram_api_hash') and settings.get('telegram_phone_number'):
                return {
                    'api_id': int(settings['telegram_api_id']),
                    'api_hash': settings['telegram_api_hash'],
                    'phone_number': settings['telegram_phone_number']
                }
    except Exception as e:
        print(f"Ошибка чтения настроек User Bot из БД: {e}")
    
    # Fallback: читаем из config.py (переменные окружения)
    from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER
    if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_PHONE_NUMBER:
        return {
            'api_id': TELEGRAM_API_ID if isinstance(TELEGRAM_API_ID, int) else int(TELEGRAM_API_ID),
            'api_hash': TELEGRAM_API_HASH,
            'phone_number': TELEGRAM_PHONE_NUMBER
        }
    
    return None


async def get_user_bot_client():
    """Получение или создание клиента User Bot"""
    global _user_bot_client, Client
    
    # Импортируем Pyrogram с созданием event loop если нужно
    if not _import_pyrogram():
        raise ImportError("Pyrogram не установлен. Установите: pip install pyrogram tgcrypto")
    
    if Client is None:
        raise ImportError("Не удалось импортировать Pyrogram Client")
    
    # Получаем настройки из БД или переменных окружения
    settings = get_user_bot_settings_from_db()
    
    if not settings:
        raise ValueError("Настройки User Bot не найдены. Установите их в админке или через переменные окружения.")
    
    current_loop = asyncio.get_running_loop()
    global _user_bot_loop
    if _user_bot_loop is None:
        _user_bot_loop = current_loop
    elif _user_bot_loop is not current_loop:
        # Клиент был привязан к другому event loop - останавливаем и пересоздаем
        if _user_bot_client:
            try:
                if _user_bot_client.is_connected:
                    await _user_bot_client.stop()
            except Exception as stop_error:
                print(f"Ошибка при остановке клиента перед сменой event loop: {stop_error}")
        _user_bot_client = None
        _user_bot_loop = current_loop
    
    if _user_bot_client is None or not _user_bot_client.is_connected:
        # Создаем директорию для сессии, если её нет
        session_dir = os.path.dirname(TELEGRAM_SESSION_PATH)
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)
        
        _user_bot_client = Client(
            name=TELEGRAM_SESSION_PATH,
            api_id=settings['api_id'],
            api_hash=settings['api_hash'],
            phone_number=settings['phone_number']
        )
        
        # Подключаемся, если еще не подключены
        if not _user_bot_client.is_connected:
            await _user_bot_client.start()
            print("User Bot успешно подключен и авторизован")
    
    return _user_bot_client


async def send_message_as_user(chat_id, message):
    """
    Отправка сообщения от имени пользователя (User Bot)
    
    Args:
        chat_id: ID чата или пользователя (int или str)
        message: Текст сообщения
    
    Returns:
        bool: True если сообщение отправлено успешно, False в противном случае
    """
    try:
        # Импортируем Pyrogram если нужно
        _import_pyrogram()
        
        client = await get_user_bot_client()
        
        # Преобразуем chat_id в int, если это строка
        if isinstance(chat_id, str):
            chat_id = chat_id.strip()
            if chat_id.isdigit():
                chat_id = int(chat_id)
        
        await client.send_message(chat_id, message)
        return True
        
    except Exception as e:
        # Проверяем тип ошибки после импорта
        _import_pyrogram()
        error_text = str(e)
        
        if FloodWait and isinstance(e, FloodWait):
            print(f"FloodWait: нужно подождать {e.value} секунд")
            await asyncio.sleep(e.value)
            try:
                client = await get_user_bot_client()
                await client.send_message(chat_id, message)
                return True
            except Exception as retry_error:
                print(f"Ошибка при повторной отправке сообщения: {retry_error}")
                error_text = str(retry_error)
                e = retry_error
        
        # Дополнительная попытка при PEER_ID_INVALID
        if "PEER_ID_INVALID" in error_text.upper():
            try:
                print(f"Получен PEER_ID_INVALID для {chat_id}, выполняем повторное разрешение и отправку")
                client = await get_user_bot_client()
                await client.get_users(chat_id)
                await client.send_message(chat_id, message)
                return True
            except Exception as second_error:
                print(f"Повторная попытка после PEER_ID_INVALID не удалась: {second_error}")
                raise ValueError("PEER_ID_INVALID")
        
        if UserNotParticipant and isinstance(e, UserNotParticipant):
            print(f"Пользователь {chat_id} не является участником чата или бот не может отправить сообщение")
            raise ValueError("PEER_ID_INVALID")
        
        if ChatWriteForbidden and isinstance(e, ChatWriteForbidden):
            print(f"Нет прав на отправку сообщений в чат {chat_id}")
            raise ValueError("PEER_ID_INVALID")
        
        print(f"Ошибка отправки сообщения через User Bot: {e}")
        return False


async def disconnect_user_bot():
    """Отключение User Bot клиента"""
    global _user_bot_client, _user_bot_loop
    
    async def _stop_client():
        global _user_bot_client
        with _user_bot_lock:
            if _user_bot_client:
                try:
                    if hasattr(_user_bot_client, 'is_connected') and _user_bot_client.is_connected:
                        try:
                            await _user_bot_client.stop()
                        except RuntimeError as e:
                            error_str = str(e).lower()
                            if 'shutdown' not in error_str and 'closed' not in error_str and 'cannot schedule' not in error_str:
                                print(f"Ошибка при остановке клиента: {e}")
                        except Exception as e:
                            error_str = str(e).lower()
                            if 'shutdown' not in error_str and 'closed' not in error_str:
                                print(f"Ошибка при остановке клиента: {e}")
                except Exception as e:
                    print(f"Ошибка при завершении клиента User Bot: {e}")
                finally:
                    _user_bot_client = None
                    print("User Bot отключен")
    
    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    
    if _user_bot_loop and current_loop is not _user_bot_loop:
        try:
            future = asyncio.run_coroutine_threadsafe(_stop_client(), _user_bot_loop)
            # Добавляем таймаут для result(), чтобы не блокировать бесконечно
            try:
                future.result(timeout=2.0)
            except Exception as timeout_error:
                # Игнорируем таймаут и другие ошибки
                pass
        except Exception as e:
            # Игнорируем ошибки при остановке из другого loop
            pass
    else:
        await _stop_client()


def send_message_as_user_sync(chat_id, message):
    """
    Синхронная обертка для отправки сообщения через User Bot
    
    Args:
        chat_id: ID чата или пользователя
        message: Текст сообщения
    
    Returns:
        bool: True если сообщение отправлено успешно, False в противном случае
    """
    loop = _ensure_user_bot_loop()
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(send_message_as_user(chat_id, message), loop)
        return future.result()
    else:
        return loop.run_until_complete(send_message_as_user(chat_id, message))


async def send_messages_batch(messages_list, batch_size=29, delay_between_batches=60):
    """
    Отправка множественных сообщений через User Bot с разбивкой на батчи
    
    Если сообщений больше batch_size, разбивает на батчи и делает задержку delay_between_batches
    секунд между батчами.
    
    Args:
        messages_list: Список словарей с ключами 'chat_id' и 'message'
        batch_size: Размер батча (по умолчанию 29)
        delay_between_batches: Задержка между батчами в секундах (по умолчанию 60)
    
    Returns:
        dict: Словарь с результатами {'sent': int, 'failed': int, 'errors': list}
    """
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Разбиваем на батчи
    total_messages = len(messages_list)
    num_batches = (total_messages + batch_size - 1) // batch_size  # Округление вверх
    
    print(f"Отправка {total_messages} сообщений через User Bot, разбито на {num_batches} батчей по {batch_size} сообщений")
    
    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_messages)
        batch = messages_list[start_idx:end_idx]
        
        print(f"Отправка батча {batch_num + 1}/{num_batches} ({len(batch)} сообщений)")
        
        # Отправляем сообщения в текущем батче
        for msg_data in batch:
            chat_id = msg_data['chat_id']
            message = msg_data['message']
            student_info = msg_data.get('student_info', '')  # Для логирования ошибок
            
            try:
                success = await send_message_as_user(chat_id, message)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{student_info} ({chat_id}): Не удалось отправить сообщение")
            except ValueError as err:
                if str(err) == "PEER_ID_INVALID":
                    failed_count += 1
                    errors.append(f"{student_info} ({chat_id}): PEER_ID_INVALID")
                else:
                    failed_count += 1
                    errors.append(f"{student_info} ({chat_id}): {str(err)}")
            except Exception as err:
                failed_count += 1
                error_msg = f"{student_info} ({chat_id}): {str(err)}"
                errors.append(error_msg)
                print(f"Ошибка при отправке сообщения: {error_msg}")
        
        # Если это не последний батч, делаем задержку
        if batch_num < num_batches - 1:
            print(f"Задержка {delay_between_batches} секунд перед следующим батчем...")
            await asyncio.sleep(delay_between_batches)
    
    return {
        'sent': sent_count,
        'failed': failed_count,
        'errors': errors
    }


def send_messages_batch_sync(messages_list, batch_size=29, delay_between_batches=60):
    """
    Синхронная обертка для отправки множественных сообщений через User Bot с разбивкой на батчи
    
    Args:
        messages_list: Список словарей с ключами 'chat_id' и 'message'
        batch_size: Размер батча (по умолчанию 29)
        delay_between_batches: Задержка между батчами в секундах (по умолчанию 60)
    
    Returns:
        dict: Словарь с результатами {'sent': int, 'failed': int, 'errors': list}
    """
    loop = _ensure_user_bot_loop()
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            send_messages_batch(messages_list, batch_size, delay_between_batches), 
            loop
        )
        return future.result()
    else:
        return loop.run_until_complete(
            send_messages_batch(messages_list, batch_size, delay_between_batches)
        )

