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


import re


def sanitize_string(string, illegal_chars):
    ret = str()
    for c in string:
        if c in illegal_chars:
            ret += '\\'
        ret += c
    return ret


def get_license(l):
    bsd_re = '^(BSD)((.)*([1234]))?'
    gpl_re = '^(GPL)((.)*([123]))?'
    lgpl_re = '^(LGPL)((.)*([23]|2\\.1))?'
    apache_re = '^(Apache)((.)*(1\\.0|1\\.1|2\\.0|2))?'
    cc_re = '^(Creative Commons)|'
    moz_re = '^(Mozilla)((.)*(1\\.1))?'
    mit_re = '^MIT'
    f = re.IGNORECASE

    if re.search(apache_re, l, f) is not None:
        version = re.search(apache_re, l, f).group(4)
        if version is not None:
            return 'Apache-{0}'.format(version)
        return 'Apache-1.0'
    elif re.search(bsd_re, l, f) is not None:
        version = re.search(bsd_re, l, f).group(4)
        if version is not None:
            return 'BSD-{0}'.format(version)
        return 'BSD'
    elif re.search(gpl_re, l, f) is not None:
        version = re.search(gpl_re, l, f).group(4)
        if version is not None:
            return 'GPL-{0}'.format(version)
        return 'GPL-1'
    elif re.search(lgpl_re, l, f) is not None:
        version = re.search(lgpl_re, l, f).group(4)
        if version is not None:
            return 'LGPL-{0}'.format(version)
        return 'LGPL-2'
    elif re.search(moz_re, l, f) is not None:
        version = re.search(moz_re, l, f).group(4)
        if version is not None:
            return 'MPL-{0}'.format(version)
        return 'MPL-2.0'
    elif re.search(mit_re, l, f) is not None:
        return 'MIT'
    elif re.search(cc_re, l, f) is not None:
        return 'CC-BY-SA-3.0'
    else:
        print(colored('Could not match license "{0}".'.format(l), 'red'))
        raise UnknownLicense('bad license')


def resolve_dep(pkg, os):
    """
    TODO(allenh1): integrate rosdep
    """
    if os == 'oe':
        return _resolve_dep_open_embedded(pkg)
    else:
        msg = "Unknown target platform '{0}'".format(os)
        raise UnresolvedDependency(msg)


def _resolve_dep_open_embedded(pkg):
    if pkg == 'python-yaml':
        return 'python-pyyaml'
    elif pkg == 'tinyxml2':
        return 'libtinyxml2'
    elif pkg == 'tinyxml':
        return 'libtinyxml'
    elif pkg == 'pkg-config':
        return 'pkgconfig'
    elif pkg == 'libconsole-bridge':
        return 'console-bridge'
    elif pkg == 'libconsole-bridge-dev':
        return 'console-bridge'
    elif pkg == 'python-empy':
        return 'python-empy-native'
    elif pkg == 'catkin':
        return 'python-empy-native'
    elif pkg == 'python-catkin-pkg':
        return 'python-catkin-pkg-native'
    else:
        return pkg.replace('_', '-')
        

class UnknownLicense(Exception):
    def __init__(self, message):
        self.message = message


class UnresolvedDependency(Exception):
    def __init__(self, message):
        self.message = message


class NoPkgXml(Exception):
    def __init__(self, message):
        self.message = message
