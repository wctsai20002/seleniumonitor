class GlobalSetting():
    def __init__(self, config):
        self.password = None
        self.default_interval = config['default_interval']
        self.mails = []
        self.line_notify_token = config['line_notify_token']
        self.extract_title = False

class ContainerSetting():
    def __init__(self, url, interval):
        self.url = url
        self.interval = interval
        self.pause = False
        self.tags = []
        self.title = ''
        self.css_selector = ''
        self.ignore_css_selector = ''
        self.ignore_text = ''
        self.notification_emails = []
        self.last_error = False

    def set_interval(self, interval):
        self.interval = interval

    def set_tags(self, tags):
        self.tags = [tag for tag in tags if tag]

    def set_emails(self, emails):
        self.notification_emails = emails

    def update(self, url, interval, title, tags, emails):
        self.url = url
        self.interval = interval
        self.title = title
        self.set_tags(tags)
        self.notification_emails = emails