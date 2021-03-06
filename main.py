import os
import time
import timeago
import requests
from threading import Event
import flask_login
from flask_login import login_required
from flask import Flask, render_template, request, send_from_directory, abort, redirect, url_for, flash
from module import settings
from module import monitors
from module import forms
from module import tools

config = tools.load_env()

app = Flask(__name__)
app.config.exit = Event()
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['NEW_VERSION_AVAILABLE'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
# app.config.update(dict(DEBUG=True))

login_manager = flask_login.LoginManager(app)
login_manager.login_view = 'login'

app.secret_key = tools.init_secret(config['store_path'])

@app.template_filter('last_checked_time')
def _jinja2_filter_datetime(web_container, format='%Y-%m-%d %H:%M:%S'):
    web_container_time = time.time() if web_container.time_value == float('inf') else web_container.time_value
    return timeago.format(web_container_time, time.time())

@app.template_filter('last_changed_time')
def _jinja2_filter_datetime(web_container, format='%Y-%m-%d %H:%M:%S'):
    web_container_time = web_container.get_latest_changed()
    if web_container_time:
        return timeago.format(web_container_time, time.time())
    else:
        return 'Not yet'

@login_manager.user_loader
def user_loader(email):
    user = tools.User()
    user.get_user(email)
    return user

@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login', next=url_for('index')))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not global_setting.password:
        app.config['LOGIN_DISABLED'] = True
        flash('Login not required, no password enabled.', 'notice')
        return redirect(url_for('index'))

    elif request.method == 'GET':
        output = render_template('login.html')
        return output

    user = tools.User()
    user.id = 'defaultuser@example.com'
    password = request.form.get('password')

    if (user.check_password(password, global_setting)):
        flask_login.login_user(user, remember=True)
        next_route = request.args.get('next')
        return redirect(next_route or url_for('index'))
    else:
        flash('Incorrect password', 'error')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    form = forms.SettingForm(request.form)

    if request.method == 'GET':
        forms.populate_setting_form(form, config, global_setting)

        if request.values.get('removepassword') == 'true':
            global_setting.set_password(None)
            app.config['LOGIN_DISABLED'] = True
            flash('Password protection removed.', 'notice')
            flask_login.logout_user()

    elif request.method == 'POST' and form.validate():
        global_setting.update(form.notification_emails.data, form.interval.data, form.extract_title_as_title.data, form.line_notify_token.data)
        selenium_scheduler.global_setting_update(global_setting)
        
        if form.trigger_notify.data:
            # send notify
            flash('Notifications queued.')

        if form.password.encrypted_password:
            global_setting.set_password(form.password.encrypted_password)
            app.config['LOGIN_DISABLED'] = False
            flash('Password protection enabled.', 'notice')
            flask_login.logout_user()
            return redirect(url_for('index'))

        flash('Settings updated.')

    elif request.method == 'POST' and not form.validate():
        flash('An error occurred, please see below.', 'error')

    output = render_template('settings.html', form=form)
    return output

@app.route('/', methods=['GET'])
@login_required
def index():
    show_tag = request.args.get('tag')
    pause_container_id = request.args.get('pause')

    web_containers = selenium_scheduler.get_duties(tag=show_tag)
    all_tags = selenium_scheduler.get_tags()

    output = render_template('watch-overview.html', web_containers=web_containers, tags=all_tags, \
        show_tag=show_tag, has_unviewed=False)
    return output


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory('/app/static/images', filename='favicon.ico')

@app.route('/static/<string:group>/<string:filename>', methods=['GET'])
def static_content(group, filename):
    full_path = os.path.realpath(__file__)
    p = os.path.dirname(full_path)

    try:
        return send_from_directory('{}/static/{}'.format(p, group), filename=filename)
    except FileNotFoundError:
        abort(404)

@app.route('/api/add', methods=['POST'])
@login_required
def api_add():
    url = request.form.get('url').strip()
    tags = request.form.get('tag').strip().split(' ')

    web_container = monitors.WebContainer(config, url, global_setting.default_interval)
    web_container.setting.set_tags(tags)
    selenium_scheduler.register(web_container)

    flash('Watch added.')
    return redirect(url_for('index'))

@app.route('/edit/<string:container_id>', methods=['GET', 'POST'])
@login_required
def edit_page(container_id):
    form = forms.ContainerForm(request.form)
    web_container, atom_index, web_container_index = selenium_scheduler.find_container(container_id)

    if request.method == 'GET':
        if web_container:
            forms.populate_edit_form(form, web_container)
            output = render_template('edit.html', container_id=container_id, web_container=web_container, form=form)
            return output
        else:
            flash('No watch with the ID %s found.' % (container_id), 'error')

    elif request.method == 'POST' and form.validate():
        if web_container:
            url = form.url.data.strip()
            title = form.title.data.strip()
            interval = form.interval.data
            tags = form.tags.data.strip().split(' ')
            css_selector = form.css_selector.data.strip()
            ignore_text = form.ignore_text.data
            headers = form.headers.data
            notification_emails = form.notification_emails.data

            web_container.setting.update(url=url, interval=interval, title=title, tags=tags, emails=notification_emails)
            selenium_scheduler.update(web_container, atom_index, web_container_index)
            flash('Updated watch.')

            if form.trigger_notify.data:
                flash('Notifications queued.')
        else:
            flash('No watch with the ID %s found.' % (container_id), 'error')

    elif request.method == 'POST' and not form.validate():
        flash('An error occurred, please see below.', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/delete', methods=['GET'])
@login_required
def api_delete():
    container_id = request.args.get('id')
    selenium_scheduler.delete(container_id)
    flash('Deleted.')

    return redirect(url_for('index'))

@app.route('/preview/<string:container_id>', methods=['GET'])
@login_required
def preview_page(container_id):
    extra_stylesheets = ['/static/styles/diff.css']
    web_container, atom_index, web_container_index = selenium_scheduler.find_container(container_id)

    if web_container:
        latest_history = web_container.get_latest_history()
        output = render_template('preview.html', text_content=latest_history.text, extra_stylesheets=extra_stylesheets)
        return output
    else:
        flash('No history found for the specified link !!!', 'error')
        return redirect(url_for('index'))

@app.route('/diff/<string:container_id>', methods=['GET'])
@login_required
def diff_history_page(container_id):
    extra_stylesheets = ['/static/styles/diff.css']
    previous_version = request.args.get('previous_version')
    
    web_container, atom_index, web_container_index = selenium_scheduler.find_container(container_id)
    previous_version_index = web_container.find_version_index(previous_version) if previous_version else -2

    if web_container:
        latest_history = web_container.get_latest_history()
        previous_history = web_container.get_previous_history(previous_version_index)
        versions = web_container.get_time_stamps()
        
        output = render_template('diff.html', latest_content=latest_history.text, previous_content=previous_history.text, \
                                    extra_stylesheets=extra_stylesheets, versions=versions, container_id=container_id,
                                    latest_version=versions[-1], previous_version=versions[previous_version_index])
        return output
    else:
        flash('No history found for the specified link !!!', 'error')
        return redirect(url_for('index'))

@app.route('/api/recheck', methods=['GET'])
@login_required
def api_watch_checknow():
    tag = request.args.get('tag')
    container_id = request.args.get('id')

    if container_id:
        selenium_scheduler.recheck(container_id=container_id)
    else:
        selenium_scheduler.recheck(tag=tag)

    flash('Watches are rechecking.')
    return redirect(url_for('index', tag=tag))

if __name__ == '__main__':
    tools.init_config(config)
    global_setting = settings.GlobalSetting(config)
    selenium_scheduler = monitors.SeleniumScheduler(config, global_setting)

    app.config['LOGIN_DISABLED'] = global_setting.password == None
    app.run(host=config['ip'], port=config['port'])