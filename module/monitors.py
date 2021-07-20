import os
import time
import pickle
import shelve
import hashlib
import requests
from inscriptis import get_text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from multiprocessing import Process, Queue, Manager, Value
from module import settings

class SeleniumScheduler():
    def __init__(self, config):
        self.config = config
        
        self.atom_nums = self.config['atom_nums']
        self.atoms = [Atom(self.config, atom_index) for atom_index in range(self.atom_nums)]
        
        self.load_data()

    def register(self, web_container):
        index = self.min_index()
        web_container.id = str(index) + '_' + web_container.id
        self.atoms[index].saver.save(web_container)
        self.atoms[index].timer.register(web_container)

    def min_index(self):
        sizes = [len(atom.timer.duties) for atom in self.atoms]
        return sizes.index(min(sizes))

    def get_duties(self, tag=None):
        all_duties = [web_container for atom in self.atoms for web_container in atom.timer.duties if not tag or tag in web_container.setting.tags]
        return all_duties

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
        self.atoms[atom_index].timer.update_manager_list(web_container, web_container_index)

    def delete(self, container_id):
        web_container, atom_index, web_container_index = self.find_container(container_id)
        self.atoms[atom_index].timer.delete_manager_list(web_container, web_container_index)

    def load_data(self):
        web_containers = []
        for root, dirs, files in os.walk(self.config['store_path']):
            for file_name in files:
                if file_name.endswith('.bak'):
                    file_path = os.path.join(root, file_name.rstrip('.bak'))
                    with shelve.open(file_path) as f:
                        for key in f.keys():
                            web_containers.append(f[key])
        
        for web_container in web_containers:
            index = self.min_index()
            self.atoms[index].timer.register(web_container)
    
    def recheck(self, container_id=None, tag=None):
        if container_id:
            web_container, atom_index, web_container_index = self.find_container(container_id)
            self.atoms[atom_index].timer.recheck(web_container)
        else:
            web_containers = self.get_duties(tag)
            for web_container in web_containers:
                self.recheck(web_container.id)

class Atom():
    def __init__(self, config, atom_index):
        self.config = config

        self.candidates = Queue()
        self.nonupdated = Queue()
        self.completed = Queue()

        self.atom_index = atom_index

        self.timer = Timer(self.config, self.candidates, self.completed)
        self.fetcher = WebFetcher(self.config, self.candidates, self.nonupdated)
        self.saver = Saver(self.config, self.nonupdated, self.completed, self.atom_index)

class WebFetcher():
    def __init__(self, config, candidates, nonupdated):
        self.config = config
        self.candidates = candidates
        self.nonupdated = nonupdated

        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')

        self.fetch_process = Process(target=self.get_page)
        self.fetch_process.start()

    def get_page(self):
        while True:
            web_container = self.candidates.get(True)
            driver = webdriver.Chrome(self.config['driver_path'], options=self.chrome_options)
            driver.get(web_container.setting.url)
            # update
            web_container.update(driver.page_source)
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
            self.update_manager_list(web_container, index)
            
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
                self.update_manager_list(web_container, index)
                

    def register(self, web_container):
        self.duties_lock.acquire()
        self.go_check(web_container)
        self.duties.append(web_container)
        self.duties_lock.release()

    def update_manager_list(self, web_container, index):
        self.duties_lock.acquire()
        tempt = list(self.duties)
        tempt[index] = web_container
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
        self.data = {}
        self.file_path = os.path.join(self.config['store_path'], 'atom_' + str(atom_index))

        self.store_process = Process(target=self.store)
        self.store_process.start()

    def store(self):
        while True:
            web_container = self.nonupdated.get(True)
            self.save(web_container)
            self.completed.put(web_container)

    def save(self, web_container):
        container_id = web_container.id
        # self.data[container_id] = web_container
        with shelve.open(self.file_path) as f:
            f[container_id] = web_container

class WebContainer():
    def __init__(self, config, url, interval):
        self.config = config
        self.id = str(time.time())
        self.setting = settings.ContainerSetting(url=url, interval=interval)

        self.time_value = time.time()
        self.history = []
    
    def update(self, html):
        latest_data = PageData(html)
        if len(self.history) >= 2:
            if self.get_latest_history().checksum != latest_data.checksum:
                self.history.append(PageData(html))
            else:
                self.history[-1] = latest_data
        else:
            self.history.append(latest_data)
        
        if len(self.history) > self.config['max_snapshots']:
            self.history = self.history[1 : ]

    def get_encoding(self):
        self.encoding = requests.get(self.setting.url).encoding
    
    def get_latest_history(self):
        return self.history[-1]
    
    def get_previous_history(self, index=None):
        index = -2 if index == None else index
        return self.history[index]

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

    def count_checksum(self, text):
        return hashlib.md5((text).encode('utf8')).hexdigest()