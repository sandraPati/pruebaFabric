import os
import fremote
import local as local_task
import ex

from getpass import getpass

from fabric.colors import cyan, red
from fabric.api import env, run, prefix, local, task
from contextlib import contextmanager as _contextmanager
from fabric.operations import prompt
from fabric.utils import abort
from fabric.contrib.console import confirm

from utils import (load_default_configuration, get_applications_name, TARGET_DEPLOYMENT, get_remote_apps_dir,
                   get_local_apps_dir)



env.hosts = ['192.168.1.46']
env.user = 'userver'


environment_target = ['dev', 'prod', 'qa']
trotamundia_repository = "git@bitbucket.org/trotamundia/trotamundia.git"
DEFAULT_REMOTE_VIRTUALENV_DIR = '~/.virtualenvs'
DEFAULT_LOCAL_VIRTUALENV_DIR = '%s/.virtualenvs' % os.getenv('HOME')
DEFAULT_REQUIREMENTS_FILENAME = 'requirements.txt'


@task
def sync_db(origin=None, destination=None):
    """
    Sync local database
    :param name: database name
    :return:
    """
    try:
        local_task.sync_db(origin, destination)
    except ex.DatabaseNameDoesNotExist as e:
        print red('Error: %s' % e.message, bold=True)
    except ex.DatabaseAlreadyExist as e:
        print red('Error: %s' % e.message, bold=True)
    except ex.DatabaseAuthenticationFailed as e:
        print red('Error: %s' % e.message, bold=True)


@task
def add_ssh_key(name=None):
    """
    Add SSH Key to remote server
    :param name: key name
    :return:
    """
    ssh_public_key_path = local_task.generate_ssh_public_key(name)
    fremote.add_ssh_public_key(ssh_public_key_path)


@task
def remote_pip(environment_name=None, install=None, uninstall=None):
    try:
        with fremote.virtualenv(environment_name):
            fremote.pip(install, uninstall)
    except ValueError, e:
        print e


@task
def sync_remote_repository(application_name=None, target_deployment=None):
    """
    Sync remote repository
    :param application_name:
    :param target_deployment:
    :return:
    """
    applications_name = get_applications_name()
    while not application_name in applications_name:
        applications_choices = ', '.join(applications_name)
        application_name = prompt("application '%s' doesnt exist, try again. (%s): "
                                  % (application_name, applications_choices))
    while not target_deployment in TARGET_DEPLOYMENT:
        targets_choices = ', '.join(TARGET_DEPLOYMENT)
        target_deployment = prompt("target deployment '%s' doesnt exist, try again. (%s): "
                                   % (target_deployment, targets_choices))

    remote_apps_dir = get_remote_apps_dir()
    application_conf = load_default_configuration(application_name)
    repository = application_conf['repository']
    application_path = '%s/%s-%s' % (remote_apps_dir, application_name, target_deployment)
    return fremote.sync_remote_repository(repository, application_path)


@task
def sync_local_repository(application_name=None):
    """
    Sync local repository
    :param application_name:
    :return:
    """
    applications_name = get_applications_name()
    while not application_name in applications_name:
        applications_choices = ', '.join(applications_name)
        application_name = prompt("'%s' doesnt exist, try again. (%s): " % (application_name, applications_choices))
    local_apps_dir = get_local_apps_dir()
    application_conf = load_default_configuration(application_name)
    repository = application_conf['repository']
    application_path = '%s/%s' % (local_apps_dir, application_name)
    local_task.sync_local_repository(repository, application_path)


@_contextmanager
def virtualenvwrapper(env_name=None):
    """
    Active virtualenvwrapper
    :param env_name:
    :return:
    """
    export_workon = 'export WORKON_HOME=%s' % DEFAULT_LOCAL_VIRTUALENV_DIR
    activate_virtualenvwrapper = 'source /usr/local/bin/virtualenvwrapper.sh'

    with prefix(export_workon), \
         prefix(activate_virtualenvwrapper):

        if not env_name:
            env_name = prompt('Virtualenv name:')
        if not os.path.exists('%s/%s' % (DEFAULT_LOCAL_VIRTUALENV_DIR, env_name)):
            create = confirm('virtualenv %s doesnt exist, would do you create?' % env_name)
            if not create:
                abort('virtualenv %s not found' % env_name)
            local('mkvirtualenv %s' % env_name)
            print 'Virtualenv %s created' % env_name
        with prefix('workon %s' % env_name):
            print 'Active %s' % env_name
            yield


@task
def trotamundia_library(lib=None):
    with virtualenvwrapper():
        if lib == 'install':
            local('pip install git+ssh://%s' % trotamundia_repository)
        elif lib == 'update':
            local('pip uninstall trotamundia')
            local('pip install git+ssh://%s' % trotamundia_repository)


@task
def host_type():
    env.key_filename = local_task.get_ssh_key()
    print cyan("Using key file '%s'." % env.key_filename)
    run('uname -s')


@task
def deploy(application_name=None, target_deployment=None):
    env.key_filename = local_task.get_ssh_key()
    print cyan("Using key file '%s'." % env.key_filename)

    print cyan("Deploy application")

    while not env.key_filename and not env.password:
        env.password = getpass("%s's password to %s: " % (env.user, env.hosts[0]))

    while not target_deployment in environment_target:
        if target_deployment:
            target_deployment_prompt = "target environment '%s' doesnt exists, try again: " % target_deployment
        else:
            target_deployment_prompt = 'target environment: '
        target_deployment = prompt(target_deployment_prompt, default='dev')
    while not application_name in get_applications_name():
        if application_name:
            application_name_prompt = "application name '%s' doesnt exist, try again: " % application_name
        else:
            application_name_prompt = 'application name: '
        application_name = prompt(application_name_prompt)

    print cyan("Deploy '%s' application" % application_name, bold=True)

    try:
        remote_path = sync_remote_repository(application_name, target_deployment)
    except ex.ApplicationDoesNotExist, e:
        abort(e.message)
    else:
        fremote.git_remote_last_commit(remote_path)
        app_dirname = remote_path.split('/')[-1:][0]
        virtualenv_name = app_dirname

        with fremote.virtualenv(virtualenv_name):
            try:
                if confirm('would you do reinstall trotamundia lib?'):
                    fremote.pip(uninstall='trotamundia')
                fremote.install_requirements(remote_path)
                fremote.collectstatic(remote_path)
            except ex.RequirementsFileDoesNotExist:
                print 'requirements.txt file not found'
            except ex.ManageFileDoesNotExist:
                print 'manage.py file not found'

    default_origin_server = 'trotamundia'
    default_destination_server = 'test'
    destination_database = '%s-%s' % ('trotamundia', target_deployment)

    if confirm("would you do sync '%s' database?" % default_origin_server):
        try:
            local_task.sync_db(default_origin_server, default_destination_server,
                               destination_database=destination_database, quiet=True)
        except (ex.DatabaseNameDoesNotExist, ex.DatabaseAlreadyExist, ex.DatabaseAuthenticationFailed) as e:
            print red('Error: %s' % e.message, bold=True)

    fremote.restart_supervisorctl('%s-%s' % (application_name, target_deployment))
    print cyan('%s-%s deployed success' % (application_name, target_deployment))
