# Copyright (C) 2012-2013 Arun Persaud <apersaud@lbl.gov>
#                         W. Trevor King <wking@tremily.us>
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"A python script that converts RSS/Atom newsfeeds to email"

import codecs as _codecs
from distutils.core import setup
import os.path as _os_path

from rss2email import __version__, __url__, __author__, __email__


_this_dir = _os_path.dirname(__file__)

setup(
    name='rss2email',
    version=__version__,
    maintainer=__author__,
    maintainer_email=__email__,
    url=__url__,
    download_url='https://github.com/wking/rss2email/archive/v{}.tar.gz'.format(__version__),
    license='GNU General Public License (GPL)',
    platforms=['all'],
    description=__doc__,
    long_description=_codecs.open(
        _os_path.join(_this_dir, 'README'), 'r', encoding='utf-8').read(),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Topic :: Communications :: Email',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    packages=['rss2email', 'rss2email.post_process'],
    scripts=['r2e'],
    provides=['rss2email'],
    requires=[
        'feedparser (>=5.0.1)',
        'html2text (>=3.0.1)',
        ],
    )
