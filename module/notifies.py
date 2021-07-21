import abc
import urllib
import requests
from urllib.parse import urljoin
from multiprocessing import Process, Queue, Manager, Value

class NotifySender():
    def __init__(self, notifier, messages):
        self.notifier = notifier
        self.messages = messages
        self.send_process = Process(target=self.send)
        self.send_process.start()

    def __del__(self):
        self.send_process.terminate()

    def send(self):
        while True:
            message = self.messages.get(True)
            self.notifier.notify(message)

class Notifier():
    def __init__(self, token=None):
        self.token = token
    
    @abc.abstractmethod
    def notify(self, message):
        return NotImplemented

class LineNotifyNotifier(Notifier):
    def __init__(self, token):
        self.token = token
        self.notify_api_url = 'https://notify-api.line.me/api/notify'
        self.headers = {
            "Authorization": "Bearer " + self.token, 
            "Content-Type" : "application/x-www-form-urlencoded"
        }
    
    def notify(self, message):
        payload = {'message': message.format_message()}
        r = requests.post(self.notify_api_url, headers = self.headers, params = payload)
        return r.status_code == 200

class Message():
    def __init__(self, config, web_container):
        self.config = config
        self.web_container = web_container
    
    @abc.abstractmethod
    def set_message(self, title, content):
        return NotImplemented
    
    @abc.abstractmethod
    def make_message(self):
        return NotImplemented
    
    @abc.abstractmethod
    def format_message(self, title, content):
        return NotImplemented

class LineNotifyMessage(Message):
    def __init__(self, config, web_container):
        self.config = config
        self.web_container = web_container
        self.make_message()
    
    def set_message(self, title, content):
        self.title = title
        self.content = content

    def make_message(self):
        origin_url = str(self.web_container.setting.url)
        diff_url = 'http://' + self.config['ip'] + ':' + str(self.config['port']) + '/diff/'
        diff_url += str(self.web_container.id)
        self.set_message(origin_url, diff_url)

    def format_message(self):
        message = '\n'
        if self.title:
            message += self.title + '\n'
        if self.content:
            message += self.content + '\n'
        return message