import os
import time
import shelve
import hashlib
import requests
from inscriptis import get_text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from multiprocessing import Process, Queue, Manager, Value
from module import settings
from module import notifies

class SeleniumScheduler():
    def __init__(self, config, global_setting):
        self.config = config
        self.global_setting = global_setting
        self.atom_nums = self.config['atom_nums']
        self.atoms = [Atom(self.config, global_setting, atom_index) for atom_index in range(self.atom_nums)]
        self.load_atoms_data()

    def register(self, web_container):
        index = self.min_index()
        self.atoms[index].saver.save(web_container)
        self.atoms[index].timer.register(web_container)

    def min_index(self):
        sizes = [len(atom.timer.duties) for atom in self.atoms]
        return sizes.index(min(sizes))

    def get_duties(self, tag=None):
        all_duties = [web_container for atom in self.atoms for web_container in atom.timer.duties if not tag or tag in web_container.setting.tags]
        change_times = [web_container.get_latest_changed() for web_container in all_duties]
        for index, change_time in enumerate(change_times):
            if change_time == None:
                change_times[index] = float('inf')
        
        sorted_duties = [web_container for _, web_container in sorted(zip(change_times, all_duties), reverse=True)]
        return sorted_duties

    def get_tags(self):
        all_duties = self.get_duties()
        all_tags = list(set([tag for web_container in all_duties for tag in web_container.setting.tags]))
        return all_tags

    def get_ids(self):
        all_duties = self.get_duties()
        ids = [web_container.id for web_container in all_duties]
        return ids

    def find_container(self, container_id):
        for atom_index, atom in enumerate(self.atoms):
            for web_container_index, web_container in enumerate(atom.timer.duties):
                if container_id == web_container.id:
                    return web_container, atom_index, web_container_index
        return None
    
    def update(self, web_container, atom_index, web_container_index):
        self.atoms[atom_index].timer.update_manager_list(web_container, web_container_index, 'setting')
        self.atoms[atom_index].saver.save(web_container)

    def delete(self, container_id):
        web_container, atom_index, web_container_index = self.find_container(container_id)
        self.atoms[atom_index].saver.delete(web_container)
        self.atoms[atom_index].timer.delete_manager_list(web_container, web_container_index)

    def load_atoms_data(self):
        web_containers = {}
        for root, dirs, files in os.walk(self.config['atoms_path']):
            for file_name in files:
                if file_name.endswith('.bak'):
                    file_path = os.path.join(root, file_name.rstrip('.bak'))
                    with shelve.open(file_path) as f:
                        for key in f.keys():
                            web_containers[key] = f[key]
        self.clear_atoms()
        
        for key, web_container in web_containers.items():
            self.register(web_container)

    def clear_atoms(self):
        for root, dirs, files in os.walk(self.config['atoms_path']):
            for file_name in files:
                if file_name.endswith('.bak') or file_name.endswith('.dat') or file_name.endswith('.dir'):
                    file_path = os.path.join(root, file_name)
                    os.remove(file_path)

    def recheck(self, container_id=None, tag=None):
        if container_id:
            web_container, atom_index, web_container_index = self.find_container(container_id)
            self.atoms[atom_index].timer.recheck(web_container)
        else:
            web_containers = self.get_duties(tag)
            for web_container in web_containers:
                self.recheck(web_container.id)

    def global_setting_update(self, global_setting):
        self.global_setting = global_setting
        for atom_index, atom in enumerate(self.atoms):
            self.atoms[atom_index].global_setting = global_setting
            self.atoms[atom_index].sender.update(global_setting)

class Atom():
    def __init__(self, config, global_setting, atom_index):
        self.config = config
        self.global_setting = global_setting

        self.candidates = Queue()
        self.nonupdated = Queue()
        self.completed = Queue()
        self.messages = Queue()

        self.atom_index = atom_index

        self.timer = Timer(self.config, self.candidates, self.completed)
        self.fetcher = WebFetcher(self.config, self.candidates, self.nonupdated, self.messages)
        self.saver = Saver(self.config, self.nonupdated, self.completed, self.atom_index)

        self.sender = notifies.NotifySender(self.messages, notifies.LineNotifyNotifier(global_setting.line_notify_token), notifies.MailNotifier(global_setting.mails))

class WebFetcher():
    def __init__(self, config, candidates, nonupdated, messages):
        self.config = config
        self.candidates = candidates
        self.nonupdated = nonupdated
        self.messages = messages

        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')

        self.fetch_process = Process(target=self.get_page)
        self.fetch_process.start()
    
    def __del__(self):
        self.fetch_process.terminate()
    
    def get_page(self):
        while True:
            web_container = self.candidates.get(True)
            driver = webdriver.Chrome(self.config['driver_path'], options=self.chrome_options)
            driver.get(web_container.setting.url)
            # update
            changed = web_container.update(driver.page_source)
            if changed:
                self.messages.put(notifies.LineNotifyMessage(self.config, web_container))
                self.messages.put(notifies.MailMessage(self.config, web_container))
            driver.close()

            self.nonupdated.put(web_container)

class Timer():
    def __init__(self, config, candidates, completed, polling_interval=0.5):
        self.config = config
        self.candidates = candidates
        self.completed = completed

        self.manager = Manager()
        self.duties = self.manager.list()
        self.duties_lock = self.manager.Lock()
        self.polling_interval = polling_interval

        self.clock_process = Process(target=self.clock)
        self.clock_process.start()
    
    def __del__(self):
        self.clock_process.terminate()

    def clock(self):
        while True:
            time.sleep(self.polling_interval)
            self.check_completed()
            self.check_candidates()

    def go_check(self, web_container):
        web_container.time_value = float('inf')
        self.candidates.put(web_container)

    def recheck(self, web_container):
        if web_container.time_value != float('inf'):
            self.go_check(web_container)

    def check_completed(self):
        queue_size = self.completed.qsize()
        for _ in range(queue_size):
            try:
                web_container = self.completed.get(False)
            except:
                return

            index = self.find_index(web_container.id)
            web_container.time_value = time.time()
            self.update_manager_list(web_container, index, 'history')
            self.update_manager_list(web_container, index, 'time_value')
            
    def find_index(self, id):
        id_index = None
        for index, web_container in enumerate(self.duties):
            if web_container.id == id:
                id_index = index
                break
        return id_index

    def check_candidates(self):
        for index, web_container in enumerate(self.duties):
            time_value = time.time()
            if time_value - web_container.time_value >= web_container.setting.interval and not web_container.setting.pause:
                self.go_check(web_container)
                self.update_manager_list(web_container, index, 'time_value')

    def register(self, web_container):
        self.duties_lock.acquire()
        self.go_check(web_container)
        self.duties.append(web_container)
        self.duties_lock.release()

    def update_manager_list(self, web_container, index, attribute):
        self.duties_lock.acquire()
        tempt = list(self.duties)
        setattr(tempt[index], attribute, getattr(web_container, attribute))
        self.duties[ : ] = tempt
        self.duties_lock.release()

    def delete_manager_list(self, web_container, index):
        self.duties_lock.acquire()
        tempt = list(self.duties)
        del tempt[index]
        self.duties[ : ] = tempt
        self.duties_lock.release()

class Saver():
    def __init__(self, config, nonupdated, completed, atom_index):
        self.config = config
        self.nonupdated = nonupdated
        self.completed = completed
        self.file_path = os.path.join(self.config['atoms_path'], 'atom_' + str(atom_index))

        self.store_process = Process(target=self.store)
        self.store_process.start()
    
    def __del__(self):
        self.store_process.terminate()
    
    def store(self):
        while True:
            web_container = self.nonupdated.get(True)
            self.save(web_container)
            self.completed.put(web_container)

    def save(self, web_container):
        container_id = web_container.id
        with shelve.open(self.file_path) as f:
            f[container_id] = web_container
        self.completed.put(web_container)

    def delete(self, web_container):
        container_id = web_container.id
        with shelve.open(self.file_path) as f:
            del f[container_id]

class WebContainer():
    def __init__(self, config, url, interval):
        self.config = config
        self.id = str(time.time())
        self.time_value = time.time()
        self.setting = settings.ContainerSetting(url=url, interval=interval)
        self.history = []
    
    def update(self, html):
        changed = False
        latest_data = PageData(html)
        
        if len(self.history) and self.get_latest_history().checksum != latest_data.checksum:
            latest_data.changed = True
            self.history.append(latest_data)
            changed = True
        else:
            if len(self.history) >= 2:
                self.history[-1] = latest_data
            else:
                self.history.append(latest_data)
        
        if len(self.history) > self.config['max_snapshots']:
            self.history = self.history[1 : ]
        return changed

    def get_encoding(self):
        self.encoding = requests.get(self.setting.url).encoding
    
    def get_latest_history(self):
        return self.history[-1] if len(self.history) else None
    
    def get_previous_history(self, index=None):
        index = -2 if index == None else index
        return self.history[index]

    def get_latest_changed(self):
        for page_data in reversed(self.history):
            if page_data.changed:
                return page_data.time_stamp
        return None

    def get_time_stamps(self):
        return [page_data.time_stamp for page_data in self.history]

    def find_version_index(self, time_stamp):
        for index, version in enumerate(self.get_time_stamps()):
            if str(version) == str(time_stamp):
                return index
        return None

class PageData():
    def __init__(self, html):
        self.html = html
        self.text = get_text(self.html)
        self.checksum = self.count_checksum(self.text)
        self.time_stamp = time.time()
        self.changed = False

    def count_checksum(self, text):
        return hashlib.md5((text).encode('utf8')).hexdigest()
