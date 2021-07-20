import os
import socket
import base64
import hashlib
import secrets
import flask_login
from dotenv import load_dotenv, find_dotenv

class User(flask_login.UserMixin):
    def __init__(self):
        self.id = None

    def set_password(self, password):
        return True
    
    def get_user(self, email='defaultuser@example.com'):
        return self
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)

    def check_password(self, password, global_setting):
        # Getting the values back out
        raw_salt_pass = base64.b64decode(global_setting.password)
        salt_from_storage = raw_salt_pass[:32]  # 32 is the length of the salt

        # Use the exact same setup you used to generate the key, but this time put in the password to check
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),  # Convert the password to bytes
            salt_from_storage,
            100000
        )
        new_key =  salt_from_storage + new_key

        return new_key == raw_salt_pass

def init_secret(store_path):
    secret = ''
    secret_path = os.path.join(store_path, 'secret.txt')

    try:
        with open(secret_path, 'r') as f:
            secret = f.read()
    except FileNotFoundError:
        with open(secret_path, 'w') as f:
            secret = secrets.token_hex(32)
            f.write(secret)

    return secret

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def load_env():
    try:
        load_dotenv(find_dotenv())
        driver_path = os.getenv('DRIVER_PATH')
        atom_nums = int(os.getenv('ATOM_NUMS'))
        default_interval = float(os.getenv('DEFAULT_INTERVAL'))
        store_path = os.getenv('STORE_PATH')
        port = int(os.getenv('PORT'))
        user_agent = os.getenv('USER_AGENT')
        line_notify_token = os.getenv('LINE_NOTIFY_TOKEN')
    except Exception as e:
        print('Make sure you have .env file and format is correct !!!')
        print(e)
        raise
    
    return {'driver_path' : driver_path, 'atom_nums' : atom_nums, 'default_interval' : default_interval, \
            'store_path' : store_path, 'port' : port, 'user_agent' : user_agent, 'line_notify_token' : line_notify_token}
