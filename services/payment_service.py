from datetime import datetime
from config import PAYMENT_RATES, PAYMENT_DETAILS, MOSCOW_TZ
import qrcode
import io

class PaymentService:
    @staticmethod
    def calculate_payment_amount(room_occupancy):
        if room_occupancy > 4:
            room_occupancy = 4
        return PAYMENT_RATES.get(room_occupancy, PAYMENT_RATES[1])
    
    @staticmethod
    def generate_payment_qr_code(amount, student_fio, room_info, comment=None, start_date=None, end_date=None):
        payment_purpose = f"Оплата проживания. {student_fio}"
        payment_purpose += f". {comment}"
        amount_kopecks = int(float(amount) * 100)
        qr_string = (
            f"ST00012|"
            f"Name={PAYMENT_DETAILS['recipient_name']}|"
            f"PersonalAcc={PAYMENT_DETAILS['account']}|"
            f"BankName={PAYMENT_DETAILS['bank_name']}|"
            f"BIC={PAYMENT_DETAILS['bic']}|"
            f"CorrespAcc={PAYMENT_DETAILS['bank_account']}|"
            f"Sum={amount_kopecks}|"
            f"Purpose={payment_purpose}"
        )
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_string)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        return qr_buf, qr_string
    
    @staticmethod
    def format_payment_message(student_fio, amount, room_info, comment=None, start_date=None, end_date=None):
        period_info = f"\n📅 Период: {start_date} - {end_date}\n"
        comment_info = f"\nℹ️ {comment}\n"
        payment_text = (
            f"💳 <b>Назначен платеж за проживание</b>\n\n"
            f"👤 Студент: {student_fio}\n"
            f"🏠 Комната: {room_info}\n"
            f"{period_info}"
            f"💰 <b>Сумма к оплате: {amount} руб.</b>\n"
            f"{comment_info}\n"
            f"📋 <b>Реквизиты для оплаты:</b>\n"
            f"Банк: {PAYMENT_DETAILS['bank_name']}\n"
            f"Получатель: {PAYMENT_DETAILS['recipient_name']}\n"
            f"ИНН: {PAYMENT_DETAILS['inn']}\n"
            f"БИК: {PAYMENT_DETAILS['bic']}\n"
            f"Счет: {PAYMENT_DETAILS['account']}\n"
            f"\n💡 Отсканируйте QR-код для быстрой оплаты через СБП"
        )
        return payment_text
    
    @staticmethod
    def get_payment_month(date_obj=None):
        date_obj = datetime.now(MOSCOW_TZ)
        return f"{date_obj.year}-{date_obj.month:02d}"
    
    @staticmethod
    def get_previous_payment_month():
        now = datetime.now(MOSCOW_TZ)
        if now.month == 1:
            return f"{now.year - 1}-12"
        else:
            return f"{now.year}-{now.month - 1:02d}"









