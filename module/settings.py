class GlobalSetting():
    def __init__(self, config):
        self.password = None
        self.default_interval = config['default_interval']
        self.mails = []
        self.line_notify_token = config['line_notify_token']
        self.extract_title = False

    def update(self, mails, default_interval, extract_title, line_notify_token):
        self.mails = mails
        self.default_interval = default_interval
        self.line_notify_token = line_notify_token
        self.extract_title = extract_title

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