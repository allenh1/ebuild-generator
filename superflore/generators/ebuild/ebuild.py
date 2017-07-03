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


from termcolor import colored
import yaml
import sys
import re

if sys.version_info[0] == 2:
    import requests

    def get_http(url):
        return requests.get(url).text
else:
    from urllib.request import urlopen

    def get_http(url):
        response = urlopen(url)
        return response.read()


base_url = \
  "https://raw.githubusercontent.com/ros/rosdistro/master/rosdep/base.yaml"
python_url = \
  "https://raw.githubusercontent.com/ros/rosdistro/master/rosdep/python.yaml"
ruby_url = \
  "https://raw.githubusercontent.com/ros/rosdistro/master/rosdep/ruby.yaml"

print(colored("Downloading latest base yml...", 'cyan'))
base_yml = yaml.load(get_http(base_url))
print(colored("Downloading latest python yml...", 'cyan'))
python_yml = yaml.load(get_http(python_url))
print(colored("Downloading latest ruby yml...", 'cyan'))
ruby_yml = yaml.load(get_http(ruby_url))


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
        raise BadLicense('bad license')


class ebuild_keyword(object):
    def __init__(self, arch, stable):
        self.arch = arch
        self.stable = stable

    def to_string(self):
        if self.stable:
            return self.arch
        else:
            return '~{0}'.format(self.arch)


class Ebuild(object):
    """
    Basic definition of an ebuild.
    This is where any necessary variables will be filled.
    """
    def __init__(self):
        self.eapi = str(6)
        self.description = ""
        self.homepage = "https://wiki.ros.org"
        self.src_uri = None
        self.upstream_license = "LGPL-2"
        self.keys = list()
        self.rdepends = list()
        self.rdepends_external = list()
        self.depends = list()
        self.depends_external = list()
        self.distro = None
        self.cmake_package = True
        self.base_yml = None
        self.unresolved_deps = list()
        self.name = None
        self.has_patches = False
        self.die_msg = None

    def add_build_depend(self, depend, internal=True):
        if depend in self.rdepends:
            return
        elif depend in self.rdepends_external:
            return
        elif internal:
            self.depends.append(depend)
        else:
            self.depends_external.append(depend)

    def add_run_depend(self, rdepend, internal=True):
        if internal:
            self.rdepends.append(rdepend)
        else:
            self.rdepends_external.append(rdepend)

    def add_keyword(self, keyword, stable=False):
        self.keys.append(ebuild_keyword(keyword, stable))

    def get_ebuild_text(self, distributor, license_text, die_msg=None):
        """
        Generate the ebuild in text, given the distributor line
        and the license text.

        @todo: make the year dynamic
        """
        ret = "# Copyright 2017 " + distributor + "\n"
        ret += "# Distributed under the terms of the " + license_text
        ret += " license\n\n"

        # EAPI=<eapi>
        ret += "EAPI=" + self.eapi + "\n\n"
        """
        @todo: don't hard code this
        """

        # inherits
        ret += "inherit ros-cmake\n"

        # description, homepage, src_uri
        py_ver = sys.version_info
        if isinstance(self.description, str):
            ret += "DESCRIPTION=\"" + self.description + "\"\n"
        elif py_ver <= (3, 0) and isinstance(self.description, unicode):
            ret += "DESCRIPTION=\"" + self.description + "\"\n"
        else:
            ret += "DESCRIPTION=\"NONE\"\n"

        ret += "HOMEPAGE=\"" + self.homepage + "\"\n"
        ret += "SRC_URI=\"" + self.src_uri + " -> ${PN}-${PV}.tar.gz\"\n\n"
        try:
            # license -- only add if valid
            if isinstance(self.upstream_license, str):
                split = self.upstream_license.split(',')
                if len(split) > 1:
                    # they did something like "BSD,GPL,blah"
                    ret += 'LICENSE="( '
                    for l in split:
                        l = get_license(l)
                        ret += '{0} '.format(l)
                    ret += ')"\n'
                else:
                    ret += "LICENSE=\""
                    ret += get_license(self.upstream_license) + "\"\n\n"
            elif py_ver < (3, 0) and isinstance(self.upstream_license, unicode):
                self.upstream_license = self.upstream_license.decode()
                split = self.upstream_license.split(',')
                if len(split) > 1:
                    # they did something like "BSD,GPL,blah"
                    ret += 'LICENSE="( '
                    for l in split:
                        l = get_license(l.replace(' ', ''))
                        ret += '{0} '.format(l)
                    ret += ')"\n'
                else:
                    ret += "LICENSE=\""
                    ret += get_license(self.upstream_license) + "\"\n\n"
            elif isinstance(self.upstream_license, list):
                ret += "LICENSE=\"( "
                for l in self.upstream_license:
                    l = get_license(l)
                    ret += '{0} '.format(l)
                ret += ")\"\n"
        except:
            pass
        # iterate through the keywords, adding to the KEYWORDS line.
        ret += "KEYWORDS=\""

        first = True
        for i in self.keys:
            if not first:
                ret += " "
            ret += i.to_string()
            first = False

        ret += "\"\n"
        """
        @todo: uh... probably shouldn't force PYTHON 3.5
        """
        ret += "PYTHON_DEPEND=\"3::3.5\"\n\n"
        # RDEPEND
        ret += "RDEPEND=\"\n"
        for rdep in sorted(self.rdepends):
            ret += "    " + "ros-" + self.distro + "/" + rdep + "\n"
        for rdep in sorted(self.rdepends_external):
            try:
                ret += "    " + self.resolve(rdep) + "\n"
            except UnresolvedDependency:
                self.unresolved_deps.append(rdep)

        ret += "\"\n"

        # DEPEND
        ret += "DEPEND=\"${RDEPEND}\n"
        for bdep in sorted(self.depends):
            ret += "    " + 'ros-{0}/{1}\n'.format(self.distro, bdep)
        for bdep in sorted(self.depends_external):
            try:
                ret += "    " + self.resolve(bdep) + "\n"
            except UnresolvedDependency:
                self.unresolved_deps.append(bdep)
        ret += "\"\n\n"

        # SLOT
        ret += "SLOT=\"{}\"\n".format(self.distro)
        # CMAKE_BUILD_TYPE
        ret += "CMAKE_BUILD_TYPE=RelWithDebInfo\n"
        ret += "ROS_DISTRO=\"{0}\"\n".format(self.distro)
        ret += "ROS_PREFIX=\"opt/ros/${ROS_DISTRO}\"\n\n"

        # Patch source if needed.
        if self.has_patches:
            ret += "src_prepare() {\n"
            ret += "    cd ${P}\n"
            ret += "    EPATCH_SOURCE=\"${FILESDIR}\""
            ret += " EPATCH_SUFFIX=\"patch\" \\\n"
            ret += "    EPATCH_FORCE=\"yes\" epatch\n"
            ret += "ros-cmake_src_prepare\n"
            ret += "}\n\n"

        # If we're writing the ebuild for catkin, don't build in binary mode.
        binary_package = '0' if self.name == 'catkin' else '1'

        special_pkgs = ['catkin', 'opencv3', 'stage']
        catkin_cmake_args = "    local mycmakeargs=(\n"\
            + "        -DCMAKE_INSTALL_PREFIX=${D%/}${ROS_PREFIX}\n"\
            + "        -DCMAKE_PREFIX_PATH=${ROS_PREFIX}\n"\
            + "        -DPYTHON_INSTALL_DIR=lib64/python3.5/site-packages\n"\
            + "        -DCATKIN_BUILD_BINARY_PACKAGE=0\n"\
            + "    )\n"
        # source configuration
        if self.name in special_pkgs:
            ret += "src_configure() {\n"
            if self.name == 'openvc3':
                ret += "    filter-flags '-march=*' '-mcpu=*' '-mtune=*'\n"
            elif self.name == 'stage':
                ret += "    filter-flags '-std=*'\n"
            elif self.name == 'catkin':
                ret += catkin_cmake_args
            ret += "    cmake-utils_src_configure\n"
            ret += "}\n\n"

        if self.name == 'catkin':
            ret += "src_compile() {\n"
            ret += "    ${CC} ${FILESDIR}/ros-python.c"
            ret += " -o ${WORKDIR}/${P}/"
            ret += "ros-python-{0}".format(self.distro)
            ret += " || die 'could not build ros-python!'\n"
            ret += "    ros-cmake_src_compile\n"
            ret += "}\n\n"

        if self.die_msg is not None:
            self.die_msg = ' {0}'.format(die_msg)
        else:
            self.die_msg = ''

        if self.name == 'catkin':
            ret += "src_install() {\n"
            ret += "    cd ${WORKDIR}/${P}\n"
            ret += "    mkdir -p ${D}/usr/bin\n"
            ret += "    cp ros-python-{0} ".format(self.distro)
            ret += "${D%/}/usr/bin "
            ret += "|| die 'could not install ros-python!'\n"
            ret += "}\n"

        if len(self.unresolved_deps) > 0:
            raise UnresolvedDependency("failed to satisfy dependencies!")

        return ret.replace('    ', '\t')

    def get_unresolved(self):
        return self.unresolved_deps

    @staticmethod
    def resolve(pkg):
        if pkg not in base_yml:
            if pkg not in python_yml:
                if pkg not in ruby_yml:
                    raise UnresolvedDependency(
                        "could not resolve package {} for Gentoo.".format(pkg))
                elif 'gentoo'not in ruby_yml[pkg]:
                    raise UnresolvedDependency(
                        "could not resolve package {} for Gentoo.".format(pkg))
                elif 'portage' in ruby_yml[pkg]['gentoo']:
                    return ruby_yml[pkg]['gentoo']['portage']['packages'][0]
                else:
                    resolution = ruby_yml[pkg]['gentoo'][0]
                    return resolution
            elif 'gentoo'not in python_yml[pkg]:
                raise UnresolvedDependency(
                    "could not resolve package {} for Gentoo.".format(pkg))
            elif 'portage' in python_yml[pkg]['gentoo']:
                return python_yml[pkg]['gentoo']['portage']['packages'][0]
            else:
                resolution = python_yml[pkg]['gentoo'][0]
                return resolution
        elif 'gentoo'not in base_yml[pkg]:
            raise UnresolvedDependency(
                "could not resolve package {} for Gentoo.".format(pkg))
        elif 'portage' in base_yml[pkg]['gentoo']:
            resolution = base_yml[pkg]['gentoo']['portage']['packages'][0]
            return resolution
        else:
            resolution = base_yml[pkg]['gentoo'][0]
            return resolution


class UnresolvedDependency(Exception):
    def __init__(self, message):
        self.message = message


class UnknownLicense(Exception):
    def __init__(self, message):
        self.message = message
