import requests
from config import TELEGRAM_BOT_TOKEN

class TelegramService:
    @staticmethod
    def send_notification(tg_user_id, message, parse_mode='HTML'):
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        data = {
            'chat_id': tg_user_id,
            'text': message,
            'parse_mode': parse_mode
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    
    @staticmethod
    def send_photo(tg_user_id, photo_bytes, caption=None, parse_mode='HTML'):
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
        files = {'photo': photo_bytes}
        data = {
            'chat_id': tg_user_id,
            'caption': caption,
            'parse_mode': parse_mode
        }
        response = requests.post(url, files=files, data=data, timeout=30)
        return response.status_code == 200
    
    @staticmethod
    def send_payment_notification_with_qr(tg_user_id, student_fio, amount, room_info, qr_buf, 
                                         comment=None, start_date=None, end_date=None):
        from services.payment_service import PaymentService
        payment_text = PaymentService.format_payment_message(
            student_fio, amount, room_info, comment, start_date, end_date
        )
        qr_buf.seek(0)
        photo_sent = TelegramService.send_photo(tg_user_id, qr_buf, caption=payment_text)
        TelegramService.send_notification(tg_user_id, payment_text)
        return photo_sent









