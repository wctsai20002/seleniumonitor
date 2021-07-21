from wtforms import Form, BooleanField, StringField, PasswordField, validators, IntegerField, FloatField, fields, TextAreaField, Field
from wtforms import widgets
from wtforms.validators import ValidationError
from wtforms.fields import html5

class StringListField(StringField):
    widget = widgets.TextArea()

    def _value(self):
        if self.data:
            return '\n'.join(self.data)
        else:
            return u''

    def process_formdata(self, valuelist):
        if valuelist:
            cleaned = list(filter(None, valuelist[0].split('\n')))
            self.data = [x.strip() for x in cleaned]
        else:
            self.data = []

class SaltyPasswordField(StringField):
    widget = widgets.PasswordInput()
    encrypted_password = ''

    def build_password(self, password):
        import hashlib
        import base64
        import secrets

        # Make a new salt on every new password and store it with the password
        salt = secrets.token_bytes(32)

        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        store = base64.b64encode(salt + key).decode('ascii')

        return store

    # incoming
    def process_formdata(self, valuelist):
        if valuelist:
            # Be really sure it's non-zero in length
            if len(valuelist[0].strip()) > 0:
                self.encrypted_password = self.build_password(valuelist[0])
                self.data = ''
        else:
            self.data = False

# Separated by  key:value
class StringDictKeyValue(StringField):
    widget = widgets.TextArea()

    def _value(self):
        if self.data:
            output = u''
            for k in self.data.keys():
                output += '{}: {}\r\n'.format(k, self.data[k])

            return output
        else:
            return u''

    # incoming
    def process_formdata(self, valuelist):
        if valuelist:
            self.data = {}
            # Remove empty strings
            cleaned = list(filter(None, valuelist[0].split('\n')))
            for s in cleaned:
                parts = s.strip().split(':')
                if len(parts) == 2:
                    self.data.update({parts[0].strip(): parts[1].strip()})

        else:
            self.data = {}

class ListRegex(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        import re

        for line in field.data:
            if line[0] == '/' and line[-1] == '/':
                # Because internally we dont wrap in /
                line = line.strip('/')
                try:
                    re.compile(line)
                except re.error:
                    message = field.gettext('RegEx \'%s\' is not a valid regular expression.')
                    raise ValidationError(message % (line))


class ContainerForm(Form):
    url = html5.URLField('URL', [validators.URL(require_tld=False)])
    title = StringField('Title')
    tags = StringField('Tags', [validators.Optional(), validators.Length(max=35)])
    interval = FloatField('Maximum time in seconds until recheck', [validators.Optional(), validators.NumberRange(min=1)])
    css_selector = StringField('CSS Filter')

    ignore_text = StringListField('Ignore Text', [ListRegex()])
    notification_emails = StringListField('Notification Email')
    headers = StringDictKeyValue('Request Headers')
    trigger_notify = BooleanField('Send test notification on save')


class SettingForm(Form):
    password = SaltyPasswordField()

    interval = FloatField('Maximum time in seconds until recheck', [validators.NumberRange(min=1)])
    extract_title_as_title = BooleanField('Extract <title> from document and use as watch title')
    notification_emails = StringListField('Notification Email')
    line_notify_token = StringField('Line Notify Token')
    trigger_notify = BooleanField('Send test notification on save')

def populate_edit_form(form, web_container):
    form.url.data = web_container.setting.url
    form.title.data = web_container.setting.title
    form.tags.data = ' '.join(web_container.setting.tags)
    form.interval.data = web_container.setting.interval
    form.css_selector.data = web_container.setting.css_selector
    form.notification_emails.data = web_container.setting.notification_emails

def populate_setting_form(form, config, global_setting):
    form.interval.data = global_setting.default_interval
    form.extract_title_as_title.data = global_setting.extract_title
    form.notification_emails.data = global_setting.mails
    form.line_notify_token.data = make_hidden_token(global_setting.line_notify_token)

def make_hidden_token(token):
    token_size = len(token)
    start_index, end_index = int(token_size / 4), int(3 * token_size/ 4)
    token = token[ : start_index] + '*' * (end_index - start_index) + token[end_index : ]
    return token
