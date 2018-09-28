import logging
import os
import platform
import sys
import shlex
from distutils.command.build_ext import build_ext
from subprocess import check_call

from setuptools import setup, Extension
from setuptools.command.test import test as TestCommand

version = '0.2.5'

logger = logging.getLogger(__name__)

PLATFORM = sys.platform
MACHINE = platform.machine()
IN_CI_PIPELINE = False

if ('CI' in os.environ) or ('CONTINUOUS_INTEGRATION' in os.environ):
    if 'SCREWDRIVER' in os.environ:
        build_number = os.environ['BUILD_NUMBER']
    elif 'TRAVIS' in os.environ:
        build_number = os.environ['TRAVIS_BUILD_NUMBER']
    else:
        sys.exit('We currently only support building CI builds with Screwdriver or Travis')

    IN_CI_PIPELINE = True
    version = '.'.join([version, build_number])

    BASEPATH = os.path.dirname(os.path.realpath(__file__))
    NETSNMP_NAME = 'net-snmp'
    NETSNMP_VERSION = '5.7.3'
    NETSNMP_VERSIONED_NAME = '-'.join([NETSNMP_NAME, NETSNMP_VERSION])
    NETSNMP_SRC_PATH = os.path.join('src', NETSNMP_VERSIONED_NAME)
    NETSNMP_SO_PATH = os.path.join(NETSNMP_SRC_PATH,
                                   'snmplib',
                                   '.libs',
                                   'libnetsnmp.so.30.0.3')

    libdirs = []
    incdirs = ['{0}/include'.format(NETSNMP_SRC_PATH)]

else:
    netsnmp_libs = os.popen('net-snmp-config --libs').read()

    libs = [flag[2:] for flag in shlex.split(netsnmp_libs) if flag.startswith('-l')]  # noqa
    libdirs = [flag[2:] for flag in shlex.split(netsnmp_libs) if flag.startswith('-L')]  # noqa
    incdirs = []

    if PLATFORM == 'darwin':  # OS X
        brew = os.popen('brew info net-snmp').read()
        if 'command not found' not in brew and 'error' not in brew:
            # /usr/local/opt is the default brew `opt` prefix, however the user
            # may have installed it elsewhere. The `brew info <pkg>` includes
            # an apostrophe, which breaks shlex. We'll simply replace it
            libdirs = [flag[2:] for flag in shlex.split(brew.replace('\'', '')) if flag.startswith('-L')]  # noqa
            incdirs = [flag[2:] for flag in shlex.split(brew.replace('\'', '')) if flag.startswith('-I')]  # noqa
            # The homebrew version also depends on the Openssl keg
            brew = os.popen('brew info openssl').read()
            libdirs += [flag[2:] for flag in shlex.split(brew.replace('\'', '')) if flag.startswith('-L')]  # noqa
            incdirs += [flag[2:] for flag in shlex.split(brew.replace('\'', '')) if flag.startswith('-I')]  # noqa
        else:
            sys.exit('Cannot install on Mac OS X without a brew installed net-snmp')


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

        if IN_CI_PIPELINE:
            self.library_dirs.insert(0, 'yahoo_panoptes_snmp')
            self.rpath = ['$ORIGIN']

    def run(self):
        def _compile():
                print(">>>>>>>>>>> Going to build net-snmp library...")

                configureargs = "--with-defaults --with-default-snmp-version=2 --with-sys-contact=root@localhost " \
                                "--with-logfile=/var/log/snmpd.log " \
                                "--with-persistent-directory=/var/net-snmp --with-sys-location=unknown " \
                                "--with-transports=TLSTCP --without-rpm"

                featureflags = '--enable-reentrant --disable-debugging --disable-embedded-perl ' \
                               '--without-perl-modules --enable-static=no --disable-snmpv1 --disable-applications ' \
                               '--disable-manuals --with-libs=-lpthread'

                configurecmd = "./configure --build={0}-redhat-linux --host={0}-redhat-linux --target={0}" \
                               "-redhat-linux {1} {2}".format(MACHINE, configureargs, featureflags).split(' ')

                configurecmd += ['--with-security-modules=usm tsm']
                makecmd = ['make']

                print(">>>>>>>>>>> Configuring with: {0} in {1}...".format(' '.join(configurecmd), NETSNMP_SRC_PATH))
                check_call(configurecmd, cwd=NETSNMP_SRC_PATH)

                print(">>>>>>>>>>> Building net-snmp library in {}...".format(NETSNMP_SRC_PATH))
                check_call(makecmd, cwd=NETSNMP_SRC_PATH)

                print(">>>>>>>>>>> Copying shared objects")
                self.copy_file(NETSNMP_SO_PATH, 'yahoo_panoptes_snmp/libnetsnmp.so')
                print(">>>>>>>>>>> Done building net-snmp library")

        if IN_CI_PIPELINE:
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
                    extra_compile_args=['-Wno-unused-function']
            )
        ],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.6',
            'Topic :: System :: Networking',
            'Topic :: System :: Networking :: Monitoring'
        ]
)
