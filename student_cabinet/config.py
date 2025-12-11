import os
from dotenv import load_dotenv

load_dotenv()

MAIN_APP_URL = os.getenv('MAIN_APP_URL', 'http://localhost:5003')
API_SECRET_KEY = os.getenv('STUDENT_API_SECRET_KEY', 'student_cabinet_api_secret_key_2024')
SECRET_KEY = os.getenv('STUDENT_CABINET_SECRET_KEY', 'student_cabinet_secret_key_2024')
PORT = int(os.getenv('STUDENT_CABINET_PORT', 5002))
STUDENT_CABINET_DOMAIN = os.getenv('STUDENT_CABINET_DOMAIN', 'http://localhost:5002')

