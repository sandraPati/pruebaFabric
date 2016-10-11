import json
import os
import ex

from fabric.api import run, local
from fabric.contrib.files import exists
from fabric.utils import abort


TARGET_DEPLOYMENT = ['dev', 'qa', 'prod']
DEFAULT_REMOTE_APPS_DIR = '~/apps/deploy'
DEFAULT_LOCAL_APPS_DIR = './apps/'
DEFAULT_CONF_FILENAME = 'conf.js'
DEFAULT_DATABASES_KEY = 'databases'


def get_remote_apps_dir():
    if not exists(DEFAULT_REMOTE_APPS_DIR):
        run('mkdir -p %s' % DEFAULT_REMOTE_APPS_DIR)
    return DEFAULT_REMOTE_APPS_DIR


def get_local_apps_dir():
    if not os.path.exists(DEFAULT_LOCAL_APPS_DIR):
        local('mkdir -p %s' % DEFAULT_LOCAL_APPS_DIR)
    return DEFAULT_LOCAL_APPS_DIR


def open_json_file(path):
    if not os.path.exists(path):
        filename = path.split('/')[-1:][0]
        raise ex.FileNotFound, "'%s' not found" % filename
    conf_file = open(path, 'r')
    raw_conf = conf_file.read()
    return json.loads(raw_conf)


def load_conf():
    return open_json_file(DEFAULT_CONF_FILENAME)


def load_default_conf():
    return open_json_file('default_%s' % DEFAULT_CONF_FILENAME)


def get_databases():
    conf = load_conf()
    default_conf = load_default_conf()

    try:
        default_databases = default_conf['databases']
    except KeyError:
        default_databases = {}

    try:
        databases = conf['databases']
        default_databases.update(databases)
    except KeyError:
        pass

    return [key for key, value in default_databases.iteritems()]


def get_database_conf(name='default'):
    try:
        conf = load_conf()
        databases = conf[DEFAULT_DATABASES_KEY]
        return databases[name]
    except KeyError:
        try:
            default_conf = load_default_conf()
            default_databases = default_conf[DEFAULT_DATABASES_KEY]
            return default_databases[name]
        except KeyError:
            raise ex.RemoteDatabaseNotFound, 'remote database conf not found'


def load_default_configuration(application_name=None):
    if os.path.exists('./default_conf.js'):
        default_conf_file = open('./default_conf.js', 'r')
        raw = default_conf_file.read()
        conf = json.loads(raw)
        if application_name:
            try:
                return conf[application_name]
            except KeyError:
                abort("'application_name' doesnt exist")
        return conf
    abort('default_conf.js doesnt exists!')


def get_applications_name():
    applications = []
    for key in load_default_configuration():
        applications.append(key)
    return applications
