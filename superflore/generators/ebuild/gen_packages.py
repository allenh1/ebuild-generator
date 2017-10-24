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

import glob
import os
import sys

from rosdistro.dependency_walker import DependencyWalker
from rosdistro.manifest_provider import get_release_tag
from rosdistro.rosdistro import RosPackage

from rosinstall_generator.distro import _generate_rosinstall
from rosinstall_generator.distro import get_distro
from rosinstall_generator.distro import get_package_names

from superflore.exceptions import UnresolvedDependency

from superflore.utils import err
from superflore.utils import get_pkg_version
from superflore.utils import make_dir
from superflore.utils import ok
from superflore.utils import warn

from superflore.generators.ebuild.ebuild import Ebuild
from superflore.generators.ebuild.metadata_xml import metadata_xml

import xmltodict

# TODO(allenh1): This is a blacklist of things that
# do not yet support Python 3. This will be updated
# on an as-needed basis until a better solution is
# found (CI?).

no_python3 = ['tf']

org = "Open Source Robotics Foundation"
org_license = "BSD"


def regenerate_pkg(overlay, pkg, distro_name=None, distro=None):
    if not distro and not distro_name:
        raise RuntimeError('Must supply distro or distro name!')
    elif not distro:
        distro = get_distro(distro_name)
    elif not distro_name:
        distro_name = distro.name
    version = get_pkg_version(distro, pkg)
    ebuild_name =\
        '/ros-{0}/{1}/{1}-{2}.ebuild'.format(distro_name, pkg, version)
    ebuild_name = overlay.repo.repo_dir + ebuild_name
    ebuild_exists = os.path.exists(ebuild_name)
    patch_path = '/ros-{}/{}/files'.format(distro_name, pkg)
    patch_path = overlay.repo.repo_dir + patch_path
    has_patches = os.path.exists(patch_path)
    pkg_names = get_package_names(distro)[0]

    if pkg not in pkg_names:
        raise RuntimeError("Unknown package '%s'" % (pkg))
    # otherwise, remove a (potentially) existing ebuild.
    existing = glob.glob(
        '{0}/ros-{1}/{2}/*.ebuild'.format(
            overlay.repo.repo_dir,
            distro_name, pkg
        )
    )
    if existing:
        overlay.repo.remove_file(existing[0])
        manifest_file = '{0}/ros-{1}/{2}/Manifest'.format(
            overlay.repo.repo_dir, distro_name, pkg
        )
        overlay.repo.remove_file(manifest_file)
    try:
        current = gentoo_installer(distro, pkg, has_patches)
        current.ebuild.name = pkg
    except Exception as e:
        err('Failed to generate installer for package {}!'.format(pkg))
        raise e
    try:
        ebuild_text = current.ebuild_text()
        metadata_text = current.metadata_text()
    except UnresolvedDependency as ud:
        dep_err = 'Failed to resolve required dependencies for'
        err("{0} package {1}!".format(dep_err, pkg))
        unresolved = current.ebuild.get_unresolved()
        borkd_pkgs[pkg] = list()
        for dep in unresolved:
            err(" unresolved: \"{}\"".format(dep))
            borkd_pkgs[pkg].append(dep)
        err("Failed to generate installer for package {}!".format(pkg))
        raise ud
    except KeyError as ke:
        err("Failed to parse data for package {}!".format(pkg))
        unresolved = current.ebuild.get_unresolved()
        err("Failed to generate installer for package {}!".format(pkg))
        raise ke
    make_dir(
        "{}/ros-{}/{}".format(overlay.repo.repo_dir, distro_name, pkg)
    )
    success_msg = 'Successfully generated installer for package'
    ok('{0} \'{1}\'.'.format(success_msg, pkg))

    try:
        ebuild_file = '{0}/ros-{1}/{2}/{2}-{3}.ebuild'.format(
            overlay.repo.repo_dir,
            distro_name, pkg, version
        )
        ebuild_file = open(ebuild_file, "w")
        metadata_file = '{0}/ros-{1}/{2}/metadata.xml'.format(
            overlay.repo.repo_dir,
            distro_name, pkg
        )
        metadata_file = open(metadata_file, "w")
        ebuild_file.write(ebuild_text)
        metadata_file.write(metadata_text)
    except Exception as e:
        err("Failed to write ebuild/metadata to disk!")
        failed_msg = 'Failed to generate installer'
        raise e
    return current


def generate_installers(distro_name, overlay, preserve_existing=True):
    distro = get_distro(distro_name)
    pkg_names = get_package_names(distro)
    total = float(len(pkg_names[0]))
    borkd_pkgs = dict()
    changes = []
    installers = []
    bad_installers = []
    succeeded = 0
    failed = 0

    for i, pkg in enumerate(sorted(pkg_names[0])):
        version = get_pkg_version(distro, pkg)
        ebuild_name =\
            '/ros-{0}/{1}/{1}-{2}.ebuild'.format(distro_name, pkg, version)
        ebuild_name = overlay.repo.repo_dir + ebuild_name
        ebuild_exists = os.path.exists(ebuild_name)
        patch_path = '/ros-{}/{}/files'.format(distro_name, pkg)
        patch_path = overlay.repo.repo_dir + patch_path
        has_patches = os.path.exists(patch_path)
        percent = '%.1f' % (100 * (float(i) / total))

        if preserve_existing and ebuild_exists:
            skip_msg = 'Ebuild for package '
            skip_msg += '{0} up to date, skipping...'.format(pkg)
            status = '{0}%: {1}'.format(percent, skip_msg)
            ok(status)
            succeeded = succeeded + 1
            continue
        # otherwise, remove a (potentially) existing ebuild.
        existing = glob.glob(
            '{0}/ros-{1}/{2}/*.ebuild'.format(
                overlay.repo.repo_dir,
                distro_name, pkg
            )
        )
        if existing:
            overlay.repo.remove_file(existing[0])
            manifest_file = '{0}/ros-{1}/{2}/Manifest'.format(
                overlay.repo.repo_dir, distro_name, pkg
            )
            overlay.repo.remove_file(manifest_file)
        try:
            current = gentoo_installer(distro, pkg, has_patches)
            current.ebuild.name = pkg
        except Exception as e:
            err('Failed to generate installer for package {}!'.format(pkg))
            err('  exception: {0}'.format(e))
            failed = failed + 1
            continue
        try:
            ebuild_text = current.ebuild_text()
            metadata_text = current.metadata_text()
        except UnresolvedDependency:
            dep_err = 'Failed to resolve required dependencies for'
            err("{0} package {1}!".format(dep_err, pkg))
            unresolved = current.ebuild.get_unresolved()
            borkd_pkgs[pkg] = list()
            for dep in unresolved:
                err(" unresolved: \"{}\"".format(dep))
                borkd_pkgs[pkg].append(dep)
            err("Failed to generate installer for package {}!".format(pkg))
            failed = failed + 1
            continue  # do not generate an incomplete ebuild
        except KeyError:
            err("Failed to parse data for package {}!".format(pkg))
            unresolved = current.ebuild.get_unresolved()
            err("Failed to generate installer for package {}!".format(pkg))
            failed = failed + 1
            continue  # do not generate an incomplete ebuild
        make_dir(
            "{}/ros-{}/{}".format(overlay.repo.repo_dir, distro_name, pkg)
        )
        success_msg = 'Successfully generated installer for package'
        ok('{0}%: {1} \'{2}\'.'.format(percent, success_msg, pkg))
        succeeded = succeeded + 1

        try:
            ebuild_file = '{0}/ros-{1}/{2}/{2}-{3}.ebuild'.format(
                overlay.repo.repo_dir,
                distro_name, pkg, version
            )
            ebuild_file = open(ebuild_file, "w")
            metadata_file = '{0}/ros-{1}/{2}/metadata.xml'.format(
                overlay.repo.repo_dir,
                distro_name, pkg
            )
            metadata_file = open(metadata_file, "w")
            ebuild_file.write(ebuild_text)
            metadata_file.write(metadata_text)
            changes.append('*{0} --> {1}*'.format(pkg, version))
        except Exception:
            err("Failed to write ebuild/metadata to disk!")
            installers.append(current)
            failed_msg = 'Failed to generate installer'
            err("{0}%: {1} for package {2}!".format(percent, failed_msg, pkg))
            bad_installers.append(current)
            failed = failed + 1
    results = 'Generated {0} / {1}'.format(succeeded, failed + succeeded)
    results += ' for distro {0}'.format(distro_name)
    print("------ {0} ------".format(results))
    print()

    if len(borkd_pkgs) > 0:
        warn("Unresolved:")
        for broken in borkd_pkgs.keys():
            warn("{}:".format(broken))
            warn("  {}".format(borkd_pkgs[broken]))

    return installers, borkd_pkgs, changes


def _gen_metadata_for_package(distro, pkg_name, pkg,
                              repo, ros_pkg, pkg_rosinstall):
    pkg_metadata_xml = metadata_xml()
    try:
        pkg_xml = ros_pkg.get_package_xml(distro.name)
    except Exception:
        warn("fetch metadata for package {}".format(pkg_name))
        return pkg_metadata_xml
    pkg_fields = xmltodict.parse(pkg_xml)
    if 'description' in pkg_fields['package']:
        # fill longdescription, if available (defaults to "NONE").
        pkg_metadata_xml.longdescription = pkg_fields['package']['description']
    if 'maintainer' in pkg_fields['package']:
        if isinstance(pkg_fields['package']['maintainer'], list):
            pkg_metadata_xml.upstream_email =\
                pkg_fields['package']['maintainer'][0]['@email']
            pkg_metadata_xml.upstream_name =\
                pkg_fields['package']['maintainer'][0]['#text']
        elif isinstance(pkg_fields['package']['maintainer']['@email'], list):
            pkg_metadata_xml.upstream_email =\
                pkg_fields['package']['maintainer'][0]['@email']
            pkg_metadata_xml.upstream_name =\
                pkg_fields['package']['maintainer'][0]['#text']
        else:
            pkg_metadata_xml.upstream_email =\
                pkg_fields['package']['maintainer']['@email']
            if '#text' in pkg_fields['package']['maintainer']:
                pkg_metadata_xml.upstream_name =\
                    pkg_fields['package']['maintainer']['#text']
            else:
                pkg_metadata_xml.upstream_name = "UNKNOWN"

        pkg_metadata_xml.upstream_bug_url =\
            repo.url.replace("-release", "").replace(".git", "/issues")

    """
    @todo: longdescription
    """
    return pkg_metadata_xml


def _gen_ebuild_for_package(distro, pkg_name, pkg,
                            repo, ros_pkg, pkg_rosinstall):
    pkg_ebuild = Ebuild()

    pkg_ebuild.distro = distro.name
    pkg_ebuild.src_uri = pkg_rosinstall[0]['tar']['uri']
    pkg_names = get_package_names(distro)
    pkg_dep_walker = DependencyWalker(distro)

    pkg_buildtool_deps = pkg_dep_walker.get_depends(pkg_name, "buildtool")
    pkg_build_deps = pkg_dep_walker.get_depends(pkg_name, "build")
    pkg_run_deps = pkg_dep_walker.get_depends(pkg_name, "run")

    pkg_keywords = ['x86', 'amd64', 'arm', 'arm64']

    # add run dependencies
    for rdep in pkg_run_deps:
        pkg_ebuild.add_run_depend(rdep, rdep in pkg_names[0])

    # add build dependencies
    for bdep in pkg_build_deps:
        pkg_ebuild.add_build_depend(bdep, bdep in pkg_names[0])

    # add build tool dependencies
    for tdep in pkg_buildtool_deps:
        pkg_ebuild.add_build_depend(tdep, tdep in pkg_names[0])

    # add keywords
    for key in pkg_keywords:
        pkg_ebuild.add_keyword(key)

    # parse throught package xml
    try:
        pkg_xml = ros_pkg.get_package_xml(distro.name)
    except Exception as e:
        warn("fetch metadata for package {}".format(pkg_name))
        return pkg_ebuild
    pkg_fields = xmltodict.parse(pkg_xml)

    pkg_ebuild.upstream_license = pkg_fields['package']['license']
    pkg_ebuild.description = pkg_fields['package']['description']
    if isinstance(pkg_ebuild.description, str):
        pkg_ebuild.description = pkg_ebuild.description.replace('`', "")
    if len(pkg_ebuild.description) > 80:
        pkg_ebuild.description = pkg_ebuild.description[:80]
    try:
        if 'url' not in pkg_fields['package']:
            warn("no website field for package {}".format(pkg_name))
        elif sys.version_info <= (3, 0):
            pkg_ebuild.homepage = pkg_fields['package']['url'].decode()
        elif isinstance(pkg_fields['package']['url'], str):
            pkg_ebuild.homepage = pkg_fields['package']['url']
        elif '@type' in pkg_fields['package']['url']:
            if pkg_fields['package']['url']['@type'] == 'website':
                if '#text' in pkg_fields['package']['url']:
                    pkg_ebuild.homepage = pkg_fields['package']['url']['#text']
        else:
            warn("failed to parse website for package {}".format(pkg_name))
    except TypeError as e:
        warn("failed to parse website package {}: {}".format(pkg_name, e))
    return pkg_ebuild


class gentoo_installer(object):
    def __init__(self, distro, pkg_name, has_patches=False):
        pkg = distro.release_packages[pkg_name]
        repo = distro.repositories[pkg.repository_name].release_repository
        ros_pkg = RosPackage(pkg_name, repo)

        pkg_rosinstall =\
            _generate_rosinstall(pkg_name, repo.url,
                                 get_release_tag(repo, pkg_name), True)

        self.metadata_xml =\
            _gen_metadata_for_package(distro, pkg_name,
                                      pkg, repo, ros_pkg, pkg_rosinstall)
        self.ebuild =\
            _gen_ebuild_for_package(distro, pkg_name,
                                    pkg, repo, ros_pkg, pkg_rosinstall)
        self.ebuild.has_patches = has_patches

        if pkg_name in no_python3:
            self.ebuild.python_3 = False

    def metadata_text(self):
        return self.metadata_xml.get_metadata_text()

    def ebuild_text(self):
        return self.ebuild.get_ebuild_text(org, org_license)
