# -*- coding: utf-8; -*-
#
# Licensed to CRATE Technology GmbH ("Crate") under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  Crate licenses
# this file to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  You may
# obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations
# under the License.
#
# However, if you have executed another commercial license agreement
# with Crate these terms will supersede the license and you may use the
# software solely pursuant to the terms of the relevant commercial agreement.

from setuptools import setup, find_packages
import sys
import os
import re


requirements = [
    'setuptools',
    'colorama',
    'Pygments',
    'crate>=0.11.2',
    'appdirs>=1.2,<2.0',
    'prompt-toolkit==0.52'
]

tests_requirements = ['crate[test]', 'zc.customdoctests']

if (2, 6) == sys.version_info[:2]:
    requirements.append('argparse>=1.1')

def read(path):
    return open(os.path.join(os.path.dirname(__file__), path)).read()

long_description = (
    read('README.rst')
    + '\n' +
    read(os.path.join('src','crate','crash','usage.txt'))
)

versionf_content = open(os.path.join('src','crate','crash','__init__.py')).read()
version_rex = r'^__version__ = [\'"]([^\'"]*)[\'"]$'
m = re.search(version_rex, versionf_content, re.M)
if m:
    version = m.group(1)
else:
    raise RuntimeError('Unable to find version string')

setup(
    name='crash',
    version=version,
    url='https://github.com/crate/crash',
    author='CRATE Technology GmbH',
    author_email='office@crate.io',
    package_dir={'': 'src'},
    description='The Crate Data Shell',
    long_description=long_description,
    platforms=['any'],
    license='Apache License 2.0',
    keywords='crate db data client shell',
    packages=find_packages('src'),
    namespace_packages=['crate'],
    entry_points={
        'console_scripts': [
            'crash = crate.crash.command:main',
        ]
    },
    extras_require=dict(
        argcompletion=['argcomplete'],
        test=tests_requirements
    ),
    setup_requires=['zope.testrunner', 'eggtestinfo'],
    tests_require=tests_requirements,
    install_requires=requirements,
    package_data={'': ['*.txt']},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Database'
    ],
)
