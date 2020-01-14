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

import io
import os
import re

from setuptools import setup

requirements = [
    'colorama',
    'Pygments>=2.4',
    'crate>=0.22.0',
    'appdirs>=1.2,<2.0',
    'prompt-toolkit>=2.0,<3.0'
]


def read(path):
    path = os.path.join(os.path.dirname(__file__), path)
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


long_description = (
    read('README.rst')
)

versionf_content = read(os.path.join('crate', 'crash', '__init__.py'))
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
    author='Crate.io',
    author_email='office@crate.io',
    description='CrateDB Shell',
    long_description=long_description,
    platforms=['any'],
    license='Apache License 2.0',
    keywords='crate db data client shell',
    packages=['crate.crash'],
    namespace_packages=['crate'],
    entry_points={
        'console_scripts': [
            'crash = crate.crash.command:main',
        ]
    },
    extras_require=dict(
        test=[
            'crate[test]',
            'zc.customdoctests'
        ],
        devel=[
            'coverage',
            'flake8',
            'isort',
        ],
        argcompletion=['argcomplete']
    ),
    python_requires='>=3.5',
    install_requires=requirements,
    package_data={'': ['*.txt']},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Database'
    ],
)
