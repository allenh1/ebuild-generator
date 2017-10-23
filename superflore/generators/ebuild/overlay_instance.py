# Copyright 2017 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import random
import string
import time

from superflore.docker import Docker
from superflore.repo_instance import RepoInstance


def get_random_tmp_dir():
    rand_str = ''.join(random.choice(string.ascii_letters) for x in range(10))
    return '/tmp/{0}'.format(rand_str)


def get_random_branch_name():
    rand_str = ''.join(random.choice(string.ascii_letters) for x in range(10))
    return 'gentoo-bot-{0}'.format(rand_str)


class RosOverlay(object):
    def __init__(self, repo_dir=None):
        # clone repo into a random tmp directory.
        do_clone = True
        if repo_dir:
            do_clone = not os.path.exists(os.path.realpath(repo_dir))
        self.repo = RepoInstance(
            'ros', 'ros-overlay',
            repo_dir or get_random_tmp_dir(),
            do_clone
        )
        self.branch_name = get_random_branch_name()
        if do_clone:
            self.repo.clone()
        branch_msg = 'Creating new branch {0}...'.format(self.branch_name)
        self.repo.info(branch_msg)
        self.repo.create_branch(self.branch_name)

    def clean_ros_ebuild_dirs(self, distro=None):
        if distro is not None:
            self.repo.info('Cleaning up ros-{0} directory...'.format(distro))
            self.repo.git.rm('-rf', 'ros-{0}'.format(distro))
        else:
            self.repo.info('Cleaning up ros-* directories...')
            self.repo.git.rm('-rf', 'ros-*')

    def commit_changes(self, distro):
        self.repo.info('Adding changes...')
        if not distro:
            self.repo.git.add('ros-*')
        else:
            self.repo.git.add('ros-{0}'.format(distro))
        if not distro:
            distro = 'update'
        commit_msg = {
            'update': 'rosdistro sync, {0}',
            'all': 'regenerate all distros, {0}',
            'lunar': 'regenerate ros-lunar, {0}',
            'indigo': 'regenerate ros-indigo, {0}',
            'kinetic': 'regenerate ros-kinetic, {0}',
        }[distro].format(time.ctime())
        self.repo.info('Committing to branch {0}...'.format(self.branch_name))
        self.repo.git.commit(m='{0}'.format(commit_msg))

    def regenerate_manifests(self, mode, only_pkg=None):
        self.repo.info('Building docker image...')
        dock = Docker('repoman_docker', 'gentoo_repoman')
        dock.build()
        self.repo.info('Running docker image...')
        self.repo.info('Generating manifests...')
        dock.map_directory(
            '/home/%s/.gnupg' % os.getenv('USER'),
            '/root/.gnupg'
        )
        dock.map_directory(self.repo.repo_dir, '/tmp/ros-overlay')
        if only_pkg and isinstance(only_pkg, list):
            for p in only_pkg:
                pkg_dir = '/tmp/ros-overlay/ros-{0}/{1}'.format(mode, p)
                dock.add_bash_command('cd {0}'.format(pkg_dir))
                dock.add_bash_command('repoman manifest')
                dock.add_bash_command('cd /tmp/ros-overlay')
        elif only_pkg:
            pkg_dir = '/tmp/ros-overlay/ros-{0}/{1}'.format(mode, only_pkg)
            dock.add_bash_command('cd {0}'.format(pkg_dir))
            dock.add_bash_command('repoman manifest')
            dock.add_bash_command('cd /tmp/ros-overlay')
        else:
            dock.add_bash_command('cd {0}'.format('/tmp/ros-overlay'))
            dock.add_bash_command('repoman manifest')
        dock.run(show_cmd=True)

    def pull_request(self, message):
        pr_title = 'rosdistro sync, {0}'.format(time.ctime())
        self.repo.pull_request(message, pr_title)
