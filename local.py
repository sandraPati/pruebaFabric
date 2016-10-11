import os
import ex
import datetime
import utils

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from fabric.colors import cyan, red
from fabric.api import local, settings
from fabric.context_managers import hide
from fabric.operations import prompt
from fabric.contrib.console import confirm


HOME_DIR = os.getenv('HOME')
DEFAULT_SSH_PATH = '%s/.ssh' % HOME_DIR
DEFAULT_SSH_KEYFILE = 'trotamundia_rsa'
DEFAULT_DUMPS_DIR = 'dumps'
DEFAULT_DATETIME_FORMAT = '%Y-%m-%d-%H-%M'


def get_ssh_key():
    return '%s/%s' % (DEFAULT_SSH_PATH, DEFAULT_SSH_KEYFILE)


def get_dumps_dir(dirname=DEFAULT_DUMPS_DIR):
    if not os.path.exists(dirname):
        local('mkdir -p %s' % dirname)
    return '%s' % dirname


# DEFAULT_DATABASES_CHOICES = ['local', 'remote']


def select_database(databases=None, default=None, quiet=False):
    database = None if not quiet else default
    prompt_kwargs = {}

    if default:
        prompt_kwargs.update({'default': default})

    while not database in databases:
        database = prompt("database configuration name: (%s)" % ', '.join(databases), **(prompt_kwargs))
        if not database in databases:
            print red("database '%s' does not exist, try again." % database)

    print cyan("'%s' server configuration database selected" % database)
    return {
        'name': database,
        'conf': utils.get_database_conf(database)
    }


def select_database_name(name, default=None):
    prompt_kwargs = {}
    if default:
        prompt_kwargs.update({'default': default})
    return prompt("'%s' database name: " % name, **prompt_kwargs)


def sync_db(origin=None, destination=None, database=None, destination_database=None, prefix_database=None, quiet=False):
    databases = utils.get_databases()

    print cyan("source server configuration database", bold=True)
    source_server = select_database(databases, default=origin, quiet=quiet)

    if not database:
        default_source_database_name = source_server['conf'].get('name')
        print quiet, default_source_database_name
        if quiet and default_source_database_name:
            source_database_name = default_source_database_name
        else:
            source_database_name = select_database_name(source_server['name'], default=default_source_database_name)
    else:
        source_database_name = database

    print cyan("destination destination configuration database", bold=True)
    destination_server = select_database(databases, default=destination, quiet=quiet)

    if database or destination_database:
        if prefix_database and database:
            destination_database_name = '%s_%s' % (database, prefix_database)
        else:
            destination_database_name = destination_database or database
    else:
        default_destination_database_name = destination_server['conf'].get('name', source_database_name)
        if quiet and default_destination_database_name:
            destination_database_name = default_destination_database_name
            if prefix_database:
                destination_database_name = '%s_%s '% (destination_database_name, prefix_database)
        else:
            destination_database_name = select_database_name(destination_server['name'],
                                                             default=default_destination_database_name)

    if quiet or confirm('would you do %s sync to %s' % (source_server['name'], destination_server['name'])):
        dump_path = mongodb_dump(source_server, source_database_name)
        try:
            mongodb_restore(dump_path, destination_server['conf'], destination_database_name)
        except ex.DatabaseAlreadyExist as e:
            print red(e.message)


def mongodb_dump(database, database_name):
    database_conf = database['conf']

    now = datetime.datetime.now()
    dump_name = '%s_%s_%s' % (database['name'], database_name, now.strftime(DEFAULT_DATETIME_FORMAT))
    dumps_dir = get_dumps_dir()
    destination_path = '%s/%s' % (dumps_dir, dump_name)

    database_username = database_conf.get('username', None)
    database_password = database_conf.get('password', None)
    authentication_database = database_conf.get('authentication_database', None)

    dump = 'mongodump --host={host} --port={port} ' \
           '{username} {password} {authentication_database} ' \
           '--db={db} --out {destination}'
    cmd_dump = dump.format(host=database_conf['host'],
                           port=database_conf['port'],
                           username=("--username='%s'" % database_username) if database_username else '',
                           password=("--password='%s'" % database_password) if database_password else '',
                           authentication_database=(
                           '--authenticationDatabase=%s' % authentication_database) if authentication_database else '',
                           destination=destination_path,
                           db=database_name)
    with settings(hide('running')):
        print 'mongodump --host %s --port %s ' % (database_conf['host'], database_conf['port'])
        result = local(cmd_dump)
    return '%s/%s' % (destination_path, database_name)


def delete_mongodb_database(host, port, name=None, username=None, password=None,
                            authentication_database=None, mechanism='SCRAM-SHA-1'):
    client = MongoClient(host=host, port=port)
    if username and password:
        try:
            client[authentication_database].authenticate(username, password, mechanism=mechanism)
        except OperationFailure:
            raise ex.DatabaseAuthenticationFailed, "database '%s' authentication failed" % name
        except ValueError:
            raise ex.DatabaseAuthenticationFailed, "mechanism '%s' does not exist" % mechanism

    # print client.database_names()
    # print name

    if name and name in client.database_names():
        replace_database = confirm("would you do overwrite database '%s'?" % name)
        if replace_database:
            try:
                client.drop_database(name)
                return
            except OperationFailure:
                pass
        raise ex.DatabaseAlreadyExist, "database '%s' already exist" % name


def mongodb_restore(destination_path, database_conf, database_name):
    database_conf.update({ 'name': database_name })
    delete_mongodb_database(**database_conf)

    database_username = database_conf.get('username', None)
    database_password = database_conf.get('password', None)
    authentication_database = database_conf.get('authentication_database', None)

    restore = 'mongorestore --host={local} --port={port} ' \
              '{username} {password} {authentication_database} ' \
              '--db={db} {destination}'
    cmd_restore = restore.format(local=database_conf['host'],
                                 port=database_conf['port'],
                                 username=("--username='%s'" % database_username) if database_username else '',
                                 password=("--password='%s'" % database_password) if database_password else '',
                                 authentication_database=('--authenticationDatabase=%s' % authentication_database) if authentication_database else '',
                                 destination=destination_path,
                                 db=database_name)
    return local(cmd_restore)


def generate_ssh_public_key(ssh_key=None):
    """
    Generate ssh public key from ssh-keygen
    :param ssh_key:
    :return:
    """
    ssh_key_name = ssh_key or DEFAULT_SSH_KEYFILE
    path = '%s/%s' % (DEFAULT_SSH_PATH, ssh_key_name)
    print cyan("'%s' ssh key" % path)
    if not os.path.exists(path):
        if not confirm("'%s' does not exist, would you do create ssh-key?" % ssh_key_name):
            raise ex.SSHKeyNotFound
        local("ssh-keygen -N '' -f %s" % path)
    return '%s.pub' % (path,)


def sync_local_repository(repository, destination_path):
    """
    Sync local repository
    :param repository: git repository
    :param destination_path: local path destination
    :return: full path repository
    """
    app_name = destination_path.split('/')[-1:][0]
    print "Sync '%s' application..." % app_name
    if os.path.exists(destination_path):
        if not confirm('%s already exists, would you do update repository?' % app_name):
            return
        print "Updating '%s' application..." % app_name
        local('git pull origin master --quiet')
    else:
        if not confirm('%s doesnt exists, would you do clone repository?' % app_name):
            return
        print "Cloning '%s' application..." % app_name
        local('git clone %s %s --quiet' % (repository, destination_path))
    return '%s/%s' % (os.getcwd(), destination_path)
