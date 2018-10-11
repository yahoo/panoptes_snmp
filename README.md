![Build Status](https://travis-ci.org/yahoo/panoptes_snmp.svg?branch=master)

# Panoptes SNMP
> A Python wrapper on Net-SNMP

## Table of Contents

- [Introduction](#introduction)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [License](#license)
- [Credits](#credits)

## Introduction

This library, which is a fork of the excellent [EasySNMP library](https://github.com/kamakazikamikaze/easysnmp), provides a Pythonic wrapper
on top of [Net-SNMP](http://www.net-snmp.org) C library. 


## Background

The key differences from the upstream library are:

- Includes Net-SNMP source code which is used to build shared objects during installation leading to self contained distributions
- Locks down options for the Net-SNMP library: for example, SNMPv1 is and applications are disabled
- No MIBs are include in the distribution - this is by design since using symbolic OIDs is slow
- A Python based implementation of bulk_walk
- Fix support for tunneled SNMP connections

## Install

Install by running the following commands:

```
pip install yahoo_panoptes_snmp
```

## Usage

The API is similar to that of EasySNMP, which is [documented here](https://easysnmp.readthedocs.io/en/latest/session_api.html)

### bulk_walk

The implementation of BULKWALK is based on doing BULKGETs and using 'falling out' of the OID tree to terminate.

The method signature is as follows:

```python
def bulk_walk(self, oids, non_repeaters=0, max_repetitions=10):
    """
    Performs a series of bulk SNMP GET operation using the prepared session to
    retrieve multiple pieces of information in a single packet.

    :param oids: you may pass in a list of OIDs or single item; each item
                 may be a string representing the entire OID
                 (e.g. 'sysDescr.0') or may be a tuple containing the
                 name as its first item and index as its second
                 (e.g. ('sysDescr', 0))
    :param non_repeaters: the number of objects that are only expected to
                          return a single GETNEXT instance, not multiple
                          instances
    :param max_repetitions: the number of objects that should be returned
                            for all the repeating OIDs
    :return: a list of SNMPVariable objects containing the values that
             were retrieved via SNMP
    """
```

## Contribute

We welcome issues, questions, and pull requests - please have a look at [contributing](Contributing.md) to see how to do so.

## Maintainers
* Varun Varma: vvarun@oath.com

## License
This project is licensed under the terms of the [BSD](LICENSE-BSD) open source license. Please refer to [LICENSE](LICENSE) for the full terms.

## Credits
Please refer to the [CREDITS file](CREDITS.md) for a full list of credits.
