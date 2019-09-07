import logging
import os
import platform
import sys

from distutils.command.build_ext import build_ext
from subprocess import check_call

from setuptools import setup, Extension
from setuptools.command.test import test as TestCommand

version = '0.2.5.117'

logger = logging.getLogger(__name__)

PLATFORM = 'linux' if sys.platform.startswith('linux') else sys.platform

if PLATFORM not in ['darwin', 'linux']:
    sys.exit('Can only build on Linux or Mac OS X')

MACHINE = platform.machine()
BASEPATH = os.path.dirname(os.path.realpath(__file__))
NETSNMP_NAME = 'net-snmp'
NETSNMP_VERSION = '5.7.3'
NETSNMP_VERSIONED_NAME = '-'.join([NETSNMP_NAME, NETSNMP_VERSION])
NETSNMP_SRC_PATH = os.path.join('src', NETSNMP_VERSIONED_NAME)
NETSNMP_LIBS_PATH = os.path.join(NETSNMP_SRC_PATH, 'snmplib', '.libs')

if PLATFORM == 'linux':
    NETSNMP_SO_FILENAME = 'libnetsnmp.so.30.0.3'
    NETSNMP_SO_TARGETS = ['libnetsnmp.so.30', 'libnetsnmp.so']
else:
    NETSNMP_SO_FILENAME = 'libnetsnmp.30.dylib'
    NETSNMP_SO_TARGETS = ['libnetsnmp.30.dylib', 'libnetsnmp.dylib']


NETSNMP_SO_PATH = os.path.join(NETSNMP_LIBS_PATH, NETSNMP_SO_FILENAME)


libdirs = ['.']
incdirs = ['{0}/include'.format(NETSNMP_SRC_PATH)]
extra_compile_args = ['-Wno-unused-function']
extra_link_args = []

openssl_gt_1_1_0 = False

def set_openssl_version_flag(version):
    global openssl_gt_1_1_0

    try:
        components = version.split('.')
        if components:
            if int(components[0]) == 1 and int(components[1]) >= 1:
                openssl_gt_1_1_0 = True
    except:
        print('Error parsing OpenSSL version: {}'.format(version))

if PLATFORM == 'darwin':
    extra_compile_args.append('-Wsometimes-uninitialized')
    extra_link_args = ['-Wl,-rpath,@loader_path/.']
else:
    openssl = os.popen('openssl version').read()
    tokens = shlex.split(openssl.replace('\'', ''))
    try:
        openssl_version = tokens[1]
        set_openssl_version_flag(openssl_version)
    except:
        print('Could not parse OpenSSL version from openssl output - assuming < 1.1.0')

BUILD_WHEEL = True if 'bdist_wheel' in sys.argv else False


# Setup the py.test class for use with the test command
class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', 'Arguments to pass to py.test')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # Only run tests on Linux - Mac OS X may or may not have a working SNMP daemon
        if PLATFORM == 'linux':
            # Import here, cause outside the eggs aren't loaded
            import pytest
            errno = pytest.main(self.pytest_args)
            sys.exit(errno)


# Read the long description from README.md
with open('README.md') as f:
    long_description = f.read()


class BuildEasySNMPExt(build_ext):
    def finalize_options(self):
        build_ext.finalize_options(self)

        if BUILD_WHEEL:
            self.target_dirs = [os.path.join(self.build_lib, 'yahoo_panoptes_snmp')]
        else:
            self.target_dirs = [os.path.join('yahoo_panoptes_snmp')]

        self.library_dirs = self.target_dirs + self.library_dirs

        if PLATFORM == 'linux':
            self.rpath = ['$ORIGIN']

    def run(self):
        def _patch():
            if PLATFORM=="linux" AND openssl_gt_1_1_0:
                print('>>>>>>>>>>> OpenSSL version > 1.1.0, checking if already patched')
                patchcmd = ["patch", "-p1", "--ignore-whitespace"]
                patchcheck = patchcmd + ["-N", "--dry-run", "--silent"]

                try:
                    patch = open("{}/patches/openssl-1.1.0.patch".format(NETSNMP_SRC_PATH))
                    check_call(patchcheck, cwd=NETSNMP_SRC_PATH, stdin=patch)
                except CalledProcessError:
                    print('>>>>>>>>>>> Patch already applied, skipping')
                    return

                print('>>>>>>>>>>> Patch not applied, applying')

                try:
                    patch = open("{}/patches/openssl-1.1.0.patch".format(NETSNMP_SRC_PATH))
                    check_call(patchcmd, cwd=NETSNMP_SRC_PATH, stdin=patch)
                except CalledProcessError:
                    sys.exit('>>>>>>>>>>> OpenSSL version 1.1.0 patch failed, aborting')


        configureargs = "--with-defaults --with-default-snmp-version=2 --with-sys-contact=root@localhost " \
                        "--with-logfile=/var/log/snmpd.log " \
                        "--with-persistent-directory=/var/net-snmp --with-sys-location=unknown " \
                        "--without-rpm"

        featureflags = "--enable-reentrant --disable-debugging --disable-embedded-perl " \
                       "--without-perl-modules --enable-static=no --disable-snmpv1 --disable-applications " \
                       "--disable-manuals --with-libs=-lpthread"


        if PLATFORM == 'linux':
            configureargs += " --build={0}-unknown-linux-gnu --host={0}-unknown-linux-gnu ".format(MACHINE)
        else:
            featureflags += " --disable-agent --disable-mibs"

        configurecmd = "./configure {0} {1}".format(configureargs, featureflags).split(' ')

        configurecmd += ['--with-security-modules=usm tsm', '--with-out-transports=DTLSUDP TLSTCP']

        makecmd = ['make']

        print(">>>>>>>>>>> Configuring with: {0} in {1}...".format(' '.join(configurecmd), NETSNMP_SRC_PATH))
        check_call(configurecmd, cwd=NETSNMP_SRC_PATH)
        print(">>>>>>>>>>> Building net-snmp library...")
        check_call(makecmd, cwd=NETSNMP_SRC_PATH)

        print(">>>>>>>>>>> Done building net-snmp library")

        print(">>>>>>>>>>> Copying shared objects")
        for path in self.target_dirs:
            for so_target in NETSNMP_SO_TARGETS:
                self.copy_file(NETSNMP_SO_PATH, '{0}/{1}'.format(path, so_target))

        build_ext.run(self)

        # https://medium.com/@donblas/fun-with-rpath-otool-and-install-name-tool-e3e41ae86172
        # https://jorgen.tjer.no/post/2014/05/20/dt-rpath-ld-and-at-rpath-dyld/
        if PLATFORM == 'darwin':
            for interface_so_path in self.get_outputs():

                install_name_tool_cmd = [
                    'install_name_tool',
                    '-change',
                    os.path.join(os.path.sep, 'usr', 'local', 'lib', NETSNMP_SO_FILENAME),
                    os.path.join('@rpath', NETSNMP_SO_FILENAME),
                    interface_so_path
                ]
                check_call(install_name_tool_cmd)


setup(
    name='yahoo_panoptes_snmp',
    version=version,
    description='A blazingly fast and Pythonic SNMP library based on the official Net-SNMP bindings',
    long_description=long_description,
    author='Network Automation @ Verizon Media',
    author_email='network-automation@verizonmedia.com',
    url='https://github.com/yahoo/panoptes_snmp',
    license='BSD',
    packages=['yahoo_panoptes_snmp'],
    cmdclass={'test': PyTest, 'build_ext': BuildEasySNMPExt},
    ext_modules=[
        Extension(
            'yahoo_panoptes_snmp.interface', ['yahoo_panoptes_snmp/interface.c'],
            library_dirs=libdirs, include_dirs=incdirs, libraries=['netsnmp'],
            extra_compile_args=extra_compile_args, extra_link_args=extra_link_args
        )
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: System :: Networking',
        'Topic :: System :: Networking :: Monitoring'
    ]
)
