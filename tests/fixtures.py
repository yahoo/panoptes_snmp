"""
Copyright 2018, Oath Inc.
Licensed under the terms of the BSD license. See LICENSE file in project root for terms.
"""

from __future__ import unicode_literals

import logging

import pytest

import yahoo_panoptes_snmp

# Disable logging for the C interface
snmp_logger = logging.getLogger('yahoo_panoptes_snmp.interface')
snmp_logger.disabled = True


@pytest.fixture
def sess_v1_args():
    return {
        'version': 1,
        'hostname': 'localhost',
        'remote_port': 11161,
        'community': 'public'
    }


@pytest.fixture
def sess_v2_args():
    return {
        'version': 2,
        'hostname': 'localhost',
        'remote_port': 11161,
        'community': 'public'
    }


@pytest.fixture
def sess_v3_args():
    return {
        'version': 3,
        'hostname': 'localhost',
        'remote_port': 11161,
        'security_level': 'authPriv',
        'security_username': 'initial',
        'privacy_password': 'priv_pass',
        'auth_password': 'auth_pass'
    }


@pytest.fixture
def sess_v1():
    return yahoo_panoptes_snmp.Session(**sess_v1_args())


@pytest.fixture
def sess_v2():
    return yahoo_panoptes_snmp.Session(**sess_v2_args())


@pytest.fixture
def sess_v3():
    return yahoo_panoptes_snmp.Session(**sess_v3_args())
