import os
import abc
import requests
from ctypes import c_char_p
from multiprocessing import Process, Queue, Manager, Value

class NotifySender():
    def __init__(self, messages, line_notify_sender, mail_sender):
        self.messages = messages
        self.line_notify_sender = line_notify_sender
        self.mail_sender = mail_sender
        
        self.send_process = Process(target=self.send)
        self.send_process.start()

    def __del__(self):
        self.send_process.terminate()

    def send(self):
        while True:
            message = self.messages.get(True)
            if message.flag == 0:
                self.line_notify_sender.notify(message)
            elif message.flag == 1:
                self.mail_sender.notify(message)
    
    def update(self, global_setting):
        self.line_notify_sender.update_token(global_setting.line_notify_token)
        self.mail_sender.update_mails(global_setting.mails)

class Notifier():
    def __init__(self, token=None):
        self.token = token
    
    @abc.abstractmethod
    def notify(self, message):
        return NotImplemented

class LineNotifyNotifier(Notifier):
    def __init__(self, token):
        self.manager = Manager()
        self.token = self.manager.list()
        self.update_token(token)
    
    def notify(self, message):
        if self.token:
            payload = {'message': message.format_message()}
            r = requests.post(self.notify_api_url, headers = self.headers, params = payload)
            return r.status_code == 200
        else:
            return False

    def update_token(self, token):
        if '*' not in token:
            self.token = [token]
            self.notify_api_url = 'https://notify-api.line.me/api/notify'
            self.headers = {
                "Authorization": "Bearer " + self.token[0], 
                "Content-Type" : "application/x-www-form-urlencoded"
            }

class MailNotifier(Notifier):
    def __init__(self, mails):
        self.manager = Manager()
        self.mails = self.manager.list()
        self.update_mails(mails)

    def notify(self, message):
        part_command = message.format_message()
        commands = [part_command + mail for mail in list(self.mails)]
        for command in commands:
            try:
                print(command)
                os.system(command)
            except Exception as e:
                print(e)

    def update_mails(self, mails):
        self.mails[ : ] = mails

class Message():
    def __init__(self, config, web_container):
        self.config = config
        self.web_container = web_container
    
    @abc.abstractmethod
    def set_text(self, title, content):
        return NotImplemented
    
    @abc.abstractmethod
    def make_text(self):
        return NotImplemented
    
    @abc.abstractmethod
    def format_message(self, title, content):
        return NotImplemented

class LineNotifyMessage(Message):
    def __init__(self, config, web_container):
        self.flag = 0
        self.config = config
        self.web_container = web_container
        self.make_text()
    
    def set_text(self, title, content):
        self.title = title
        self.content = content

    def make_text(self):
        origin_url = str(self.web_container.setting.url)
        diff_url = 'http://' + self.config['ip'] + ':' + str(self.config['port']) + '/diff/'
        diff_url += str(self.web_container.id)
        self.set_text(origin_url, diff_url)

    def format_message(self):
        message = '\n'
        if self.title:
            message += 'Url : ' + self.title + '\n'
        if self.content:
            message += 'Diff : ' + self.content + '\n'
        return message

class MailMessage(Message):
    def __init__(self, config, web_container):
        self.flag = 1
        self.config = config
        self.web_container = web_container
        self.make_text()

    def set_text(self, title, content):
        self.title = title
        self.content = content
    
    def make_text(self):
        title = '【Hospital Notifier】 ' + self.web_container.setting.title
        origin_url = str(self.web_container.setting.url)
        diff_url = 'http://' + self.config['ip'] + ':' + str(self.config['port']) + '/diff/'
        diff_url += str(self.web_container.id)
        content = origin_url + '\n' + diff_url + '\n'
        self.set_text(title, content)

    def format_message(self):
        part_command = 'echo "' + self.content + '" | mail -s "' + self.title + '" '
        return part_command
