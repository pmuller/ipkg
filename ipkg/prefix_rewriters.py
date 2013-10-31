import os
import stat
import logging

from .utils import execute, PIPE
from .regex import PKGCONFIG_FILE, LIBTOOL_FILE


LOGGER = logging.getLogger(__name__)


def rewrite_prefix(package_file, build_prefix, install_prefix):

    file_path = os.path.join(install_prefix, package_file)

    if PKGCONFIG_FILE.match(package_file):
        rewrite_pkgconfig(file_path, build_prefix, install_prefix)

    elif LIBTOOL_FILE.match(package_file):
        rewrite_libtool(file_path, build_prefix, install_prefix)
    
    else:
        with open(file_path) as f:
            first_bytes = f.read(4)

        if first_bytes[:2] == '#!':
            rewrite_text_first_line(file_path, build_prefix, install_prefix)

        elif first_bytes in ('\xce\xfa\xed\xfe', '\xcf\xfa\xed\xfe'):
            rewrite_osx_bin(file_path, build_prefix, install_prefix)

        #else:
            #LOGGER.debug('Cannot rewrite prefix of file %s: '
            #             'cannot detect file type', file_path)


def rewrite_text_first_match(file_path, line_start, build_prefix, install_prefix):
    """Rewrite the prefix. Only apply to the first line starting with
       ``line_start``.
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    with open(file_path, 'w') as f:
        while True:
            line = lines.pop(0)

            if line.startswith(line_start):
                line = line.replace(build_prefix, install_prefix)
                f.write(line)
                f.writelines(lines)
                break

            else:
                f.write(line)


def rewrite_pkgconfig(file_path, build_prefix, install_prefix):
    #LOGGER.debug('rewrite_pkgconfig(%r, %r)', file_path,
    #             build_prefix)
    rewrite_text_first_match(file_path, 'prefix=',
                             build_prefix, install_prefix)


def rewrite_libtool(file_path, build_prefix, install_prefix):
    #LOGGER.debug('rewrite_libtool(%r, %r)', file_path,
    #             build_prefix)
    rewrite_text_first_match(file_path, 'libdir=',
                             build_prefix, install_prefix)


def rewrite_text_first_line(file_path, build_prefix, install_prefix):
    """Rewrite the prefix in the first line only.
       Mainly used to rewrite the prefix in path after the shebang in a script.
    """
    #LOGGER.debug('rewrite_text_first_line(%r, %r)', file_path,
    #             build_prefix)

    with open(file_path) as f:
        first_line = f.readline()
        other_lines = f.readlines()

    first_line = first_line.replace(build_prefix, install_prefix)

    with open(file_path, 'w') as f:
        f.write(first_line)
        f.writelines(other_lines)


def get_osx_bin_libs(file_path):
    otool_cmd = ('otool', '-L', file_path)
    otool_out = execute(otool_cmd, stdout=PIPE)[0]
    lines = otool_out.splitlines()[1:]

    return [l[1:].split()[0] for l in lines]


def rewrite_osx_bin(file_path, build_prefix, install_prefix):
    #LOGGER.debug('rewrite_osx_bin(%r, %r)', file_path,
    #             build_prefix)

    # install_name_tool fails when the file is not writable.
    # So we add the write flag before running it and
    # remove it later to restore the initial permissions.

    file_stat = os.stat(file_path)
    file_writable = file_stat.st_mode & stat.S_IWRITE

    if not file_writable:
        os.chmod(file_path, file_stat.st_mode | stat.S_IWRITE)

    name_tool_cmd = ['install_name_tool', '-id', file_path]

    for lib in get_osx_bin_libs(file_path):
        if lib.startswith(build_prefix):
            name_tool_cmd.extend(['-change', lib,
                                  lib.replace(build_prefix, install_prefix)])

    name_tool_cmd.append(file_path)

    execute(name_tool_cmd)

    if not file_writable:
        os.chmod(file_path, file_stat.st_mode)
