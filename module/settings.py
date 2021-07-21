import os
import shelve

class GlobalSetting():
    def __init__(self, config):
        self.key = 'global_setting'
        self.config = config
        self.password = None
        self.default_interval = config['default_interval']
        self.mails = []
        self.line_notify_token = config['line_notify_token']
        self.extract_title = False
        self.file_path = os.path.join(self.config['global_setting_path'], self.key)

        self.load_data()

    def set_password(self, password):
        self.password = password
        self.save()

    def update(self, mails, default_interval, extract_title, line_notify_token):
        self.mails = mails
        self.default_interval = default_interval
        self.line_notify_token = line_notify_token
        self.extract_title = extract_title

        self.save()
    
    def load_data(self):
        bak_file_path = self.file_path + '.bak'
        dat_file_path = self.file_path + '.dat'
        dir_file_path = self.file_path + '.dir'
        if os.path.isfile(bak_file_path) and dat_file_path and dir_file_path:
            with shelve.open(self.file_path) as f:
                data = f[self.key]
            self.update(data.mails, data.default_interval, data.extract_title, data.line_notify_token)
            self.set_password(data.password)

    def save(self):
        with shelve.open(self.file_path) as f:
            f[self.key] = self

class ContainerSetting():
    def __init__(self, url, interval):
        self.url = url
        self.interval = interval
        self.tags = []
        self.title = url
        self.css_selector = ''
        self.ignore_css_selector = ''
        self.ignore_text = ''
        self.notification_emails = []
        self.pause = False
        self.url_as_title = True
        self.last_error = False

    def set_interval(self, interval):
        self.interval = interval

    def set_tags(self, tags):
        self.tags = [tag for tag in tags if tag]

    def set_emails(self, emails):
        self.notification_emails = emails
    
    def set_url(self, url):
        self.url = url
        if self.url_as_title:
            self.title = self.url
    
    def set_title(self, title):
        self.title = title
        self.url_as_title = not self.title

    def update(self, url, interval, title, tags, emails):
        self.set_url(url)
        self.set_interval(interval)
        self.set_title(title)
        self.set_tags(tags)
        self.set_emails(emails)