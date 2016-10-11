from fabric.colors import cyan, red
from fabric.api import env, cd, run, prefix, sudo
from fabric.contrib.files import exists, append
from fabric.contrib.console import confirm
# from fabric.operations import prompt, put
# from fabric.utils import abort
from contextlib import contextmanager as _contextmanager

import ex

DEFAULT_REMOTE_VIRTUALENV_DIR = '~/.virtualenvs'
DEFAULT_REQUIREMENTS_FILENAME = 'requirements.txt'
DEFAULT_REMOTE_SSH_PATH = '~/.ssh'
DEFAULT_REMOTE_AUTHORIZED_KEYS = 'authorized_keys'


def restart_supervisorctl(program, update=False, use_sudo=False):
    """
    Restart supervisorctl
    :param program: program name
    :param update: update supervisorctl programs
    :param use_sudo: execute restart supervisorctl using sudo
    :return:
    """
    execute = sudo if use_sudo else run
    execute('supervisorctl status %s' % program)
    if update:
        execute('supervisorctl update')
    execute('supervisorctl restart %s' % program)
    print cyan("program '%s' restarted." % program)
    execute('supervisorctl status %s' % program)


def add_ssh_public_key(local_ssh_key_path):
    """
    Add ssh public key to authorized_keys files
    :param local_ssh_key_path:
    :return:
    """
    if not local_ssh_key_path:
        raise ex.SSHKeyNotFound
    local_ssh_key = open(local_ssh_key_path, 'r').read()
    remote_ssh_autorized_keys = '%s/%s' % (DEFAULT_REMOTE_SSH_PATH, DEFAULT_REMOTE_AUTHORIZED_KEYS)
    if not exists(remote_ssh_autorized_keys):
        run('mkdir -p %s' % DEFAULT_REMOTE_SSH_PATH)
        run('touch %s/%s' % (DEFAULT_REMOTE_SSH_PATH, DEFAULT_REMOTE_AUTHORIZED_KEYS))
    append(remote_ssh_autorized_keys, local_ssh_key)


@_contextmanager
def virtualenv(virtualname):
    """
    Create and active virtualenv environment
    :param virtualname:
    :return: virtualenv context
    """
    if not exists(DEFAULT_REMOTE_VIRTUALENV_DIR):
        run('mkdir -p %s' % DEFAULT_REMOTE_VIRTUALENV_DIR)

    if not exists('%s/%s' % (DEFAULT_REMOTE_VIRTUALENV_DIR, virtualname)):
        with cd(DEFAULT_REMOTE_VIRTUALENV_DIR):
            print "virtualenv '%s' doesnt exist, creating..." % virtualname
            run('virtualenv %s' % virtualname)

    source = 'source %s/bin/activate' % virtualname
    with cd(DEFAULT_REMOTE_VIRTUALENV_DIR), prefix(source):
        print "virtualenv '%s' activate" % virtualname
        yield


def pip(install=None, uninstall=None):
    # while not environment_name:
    #     environment_name = prompt('Virtualenv name: ')
    # with virtualenv(environment_name):
    print red('pip installing')
    if install:
        run('pip install %s' % install)
    elif uninstall:
        run('pip uninstall %s -y' % uninstall)
    else:
        raise ValueError, 'install or uninstall...'


def collectstatic(path):
    app_name = path.split('/')[-1:][0]
    print "django application '%s' collectstatic..." % app_name
    run('cd %s && python manage.py collectstatic --no-input' % path)


def install_requirements(path, requirements_filename=DEFAULT_REQUIREMENTS_FILENAME):
    if not exists('%s/%s' % (path, requirements_filename)):
        raise ex.RequirementsFileDoesNotExist, '%s not found!' % requirements_filename
    print red('Installing %s...' % requirements_filename)
    requirements_path = '%s/%s' % (path, requirements_filename)
    pip(install='-r %s' % requirements_path)


def sync_remote_repository(repository, destination_path):
    app_name = destination_path.split('/')[-1:][0]
    print red("Sync '%s' application..." % app_name, bold=True)
    if not exists(destination_path, use_sudo=False):
        if not confirm('%s doesnt exists, would you do clone repository?' % app_name):
            raise ex.ApplicationDoesNotExist, "'%s' doesnt exist" % app_name
        print red("Cloning '%s' application..." % app_name)
        run('git clone %s %s --quiet' % (repository, destination_path))
    else:
        if not confirm('%s already exists, would you do update repository?' % app_name):
            return destination_path
        print red("Updating '%s' application..." % app_name)
        with cd(destination_path):
            run('git pull origin master --quiet')
    print red("Repository '%s' fetched" % repository, bold=True)
    return destination_path


def git_remote_last_commit(git_path):
    app_name = git_path.split('/')[-1:][0]
    print red("'%s' last commit" % app_name, bold=True)
    with cd(git_path):
        run('git show --name-status')
