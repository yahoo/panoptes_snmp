import logging
import os
import platform
import sys
import time
import shlex
from distutils.command.build_ext import build_ext
from subprocess import check_call, CalledProcessError

from setuptools import setup, Extension
from setuptools.command.test import test as TestCommand

version = '0.2.5'

logger = logging.getLogger(__name__)

BUILD_START_TIME = int(time.time())
PLATFORM = sys.platform
MACHINE = platform.machine()
IN_CI_PIPELINE = False

BASEPATH = os.path.dirname(os.path.realpath(__file__))
NETSNMP_NAME = 'net-snmp'
NETSNMP_VERSION = '5.7.3'
NETSNMP_VERSIONED_NAME = '-'.join([NETSNMP_NAME, NETSNMP_VERSION])
NETSNMP_SRC_PATH = os.path.join('src', NETSNMP_VERSIONED_NAME)
NETSNMP_SO_PATH = os.path.join(NETSNMP_SRC_PATH, 'snmplib', '.libs', 'libnetsnmp.so.30.0.3')

libdirs = []
incdirs = ['{0}/include'.format(NETSNMP_SRC_PATH)]

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


if PLATFORM == 'darwin':  # OS X
    brew = os.popen('brew info net-snmp').read()
    if 'command not found' not in brew:
        try:
            openssl_install_dir = brew.split('\n')[3].split()[0]
        except:
            sys.exit('Cannot install on Mac OS X without a brew installed net-snmp')

        libdirs += ['/'.join([openssl_install_dir, 'lib'])]
        incdirs += ['/'.join([openssl_install_dir, 'include'])]
elif PLATFORM == 'linux2':
    openssl = os.popen('openssl version').read()
    tokens = shlex.split(openssl.replace('\'', ''))
    try:
        openssl_version = tokens[1]
        set_openssl_version_flag(openssl_version)
    except:
        print('Could not parse OpenSSL version from openssl output - assuming < 1.1.0')


if ('CI' in os.environ) or ('CONTINUOUS_INTEGRATION' in os.environ):
    if 'SCREWDRIVER' in os.environ:
        build_number = os.environ['BUILD_NUMBER']
    elif 'TRAVIS' in os.environ:
        build_number = os.environ['TRAVIS_BUILD_NUMBER']
    else:
        sys.exit('We currently only support building CI builds with Screwdriver or Travis CI')

    IN_CI_PIPELINE = True
    version = '.'.join([version, build_number])
else:
    version = '.'.join([version, str(BUILD_START_TIME)])


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

        self.library_dirs.insert(0, 'yahoo_panoptes_snmp')
        self.rpath = ['$ORIGIN']

    def run(self):
        def _compile():
            def _patch():
                if openssl_gt_1_1_0:
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

            print(">>>>>>>>>>> Going to build net-snmp library")

            _patch()

            configureargs = "--with-defaults --with-default-snmp-version=2 --with-sys-contact=root@localhost " \
                            "--with-logfile=/var/log/snmpd.log " \
                            "--with-persistent-directory=/var/net-snmp --with-sys-location=unknown " \
                            "--without-rpm"

            featureflags = '--enable-reentrant --disable-debugging --disable-embedded-perl ' \
                           '--without-perl-modules --enable-static=no --disable-snmpv1 --disable-applications ' \
                           '--disable-manuals --with-libs=-lpthread'

            configurecmd = "./configure --build={0}-unknown-linux-gnu --host={0}-unknown-linux-gnu " \
                           "{1} {2}".format(MACHINE, configureargs, featureflags).split(' ')

            configurecmd += ['--with-security-modules=usm tsm', '--with-out-transports=DTLSUDP TLSTCP']
            # Disable all gcc warnings
            os.environ['CFLAGS'] = '-w'
            makecmd = ['make']

            print(">>>>>>>>>>> Configuring with {0}".format(' '.join(configurecmd)))
            with open("/tmp/yahoo-panoptes-snmp-net-snmp-configure-{0}.log".format(BUILD_START_TIME), 'w+') as log:
               check_call(configurecmd, cwd=NETSNMP_SRC_PATH, stdout=log)

            print(">>>>>>>>>>> Building net-snmp library in {}".format(NETSNMP_SRC_PATH))
            with open("/tmp/yahoo-panoptes-snmp-net-snmp-make-{0}.log".format(BUILD_START_TIME), 'w+') as log:
               check_call(makecmd, cwd=NETSNMP_SRC_PATH, stdout=log)

            print(">>>>>>>>>>> Copying shared objects")
            self.copy_file(NETSNMP_SO_PATH, 'yahoo_panoptes_snmp/libnetsnmp.so.30')
            self.copy_file(NETSNMP_SO_PATH, 'yahoo_panoptes_snmp/libnetsnmp.so')
            self.copy_file(NETSNMP_SO_PATH, '{0}/yahoo_panoptes_snmp/libnetsnmp.so'.format(self.build_lib))
            self.copy_file(NETSNMP_SO_PATH, '{0}/yahoo_panoptes_snmp/libnetsnmp.so.30'.format(self.build_lib))
            print(">>>>>>>>>>> Done building net-snmp library")

        if PLATFORM == 'linux2':
            self.execute(_compile, [], 'Building dependencies for {}'.format(PLATFORM))
        build_ext.run(self)


setup(
        name='yahoo_panoptes_snmp',
        version=version,
        description='A Python wrapper on Net-SNMP',
        long_description=long_description,
        long_description_content_type="text/markdown",
        author='Network Automation @ Oath, Inc.',
        author_email='network-automation@oath.com',
        url='https://github.com/yahoo/panoptes_snmp',
        license='BSD',
        packages=['yahoo_panoptes_snmp'],
        cmdclass={'test': PyTest, 'build_ext': BuildEasySNMPExt},
        ext_modules=[
            Extension(
                'yahoo_panoptes_snmp.interface', ['yahoo_panoptes_snmp/interface.c'],
                library_dirs=libdirs, include_dirs=incdirs, libraries=['netsnmp'],
                extra_compile_args=['-Wno-unused-function', '-Wno-unused-result]']
            )
        ],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Topic :: System :: Networking',
            'Topic :: System :: Networking :: Monitoring'
        ]
)
