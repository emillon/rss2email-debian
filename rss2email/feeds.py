# Copyright (C) 2004-2013 Aaron Swartz
#                         Brian Lalor
#                         Dean Jackson
#                         Erik Hetzner
#                         Etienne Millon <me@emillon.org>
#                         Joey Hess
#                         Lindsey Smith <lindsey.smith@gmail.com>
#                         Marcel Ackermann
#                         Martin 'Joey' Schulze
#                         Matej Cepl
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

"""Define the ``Feed`` class for handling a list of feeds
"""

import codecs as _codecs
import collections as _collections
import os as _os
import json as _json
import pickle as _pickle
import sys as _sys

from . import LOG as _LOG
from . import config as _config
from . import error as _error
from . import feed as _feed

UNIX = False
try:
    import fcntl as _fcntl
    # A pox on SunOS file locking methods
    if 'sunos' not in _sys.platform:
        UNIX = True
except:
    pass


# Path to the filesystem root, '/' on POSIX.1 (IEEE Std 1003.1-2008).
ROOT_PATH = _os.path.splitdrive(_sys.executable)[0] or _os.sep


class Feeds (list):
    """Utility class for rss2email activity.

    >>> import codecs
    >>> import os.path
    >>> import json
    >>> import tempfile
    >>> from .feed import Feed

    Setup a temporary directory to load.

    >>> tmpdir = tempfile.TemporaryDirectory(prefix='rss2email-test-')
    >>> configfile = os.path.join(tmpdir.name, 'rss2email.cfg')
    >>> with open(configfile, 'w') as f:
    ...     count = f.write('[DEFAULT]\\n')
    ...     count = f.write('to = a@b.com\\n')
    ...     count = f.write('[feed.f1]\\n')
    ...     count = f.write('url = http://a.net/feed.atom\\n')
    ...     count = f.write('to = x@y.net\\n')
    ...     count = f.write('[feed.f2]\\n')
    ...     count = f.write('url = http://b.com/rss.atom\\n')
    >>> datafile = os.path.join(tmpdir.name, 'rss2email.json')
    >>> with codecs.open(datafile, 'w', Feeds.datafile_encoding) as f:
    ...     json.dump({
    ...             'version': 1,
    ...             'feeds': [
    ...                 Feed(name='f1').get_state(),
    ...                 Feed(name='f2').get_state(),
    ...                 ],
    ...             }, f)

    >>> feeds = Feeds(configfiles=[configfile,], datafile=datafile)
    >>> feeds.load()
    >>> for feed in feeds:
    ...     print(feed)
    f1 (http://a.net/feed.atom -> x@y.net)
    f2 (http://b.com/rss.atom -> a@b.com)

    You can index feeds by array index or by feed name.

    >>> feeds[0]
    <Feed f1 (http://a.net/feed.atom -> x@y.net)>
    >>> feeds[-1]
    <Feed f2 (http://b.com/rss.atom -> a@b.com)>
    >>> feeds['f1']
    <Feed f1 (http://a.net/feed.atom -> x@y.net)>
    >>> feeds['missing']
    Traceback (most recent call last):
      ...
    IndexError: missing

    Tweak the feed configuration and save.

    >>> feeds[0].to = None
    >>> feeds.save()
    >>> print(open(configfile, 'r').read().rstrip('\\n'))
    ... # doctest: +REPORT_UDIFF, +ELLIPSIS
    [DEFAULT]
    from = user@rss2email.invalid
    ...
    verbose = warning
    <BLANKLINE>
    [feed.f1]
    url = http://a.net/feed.atom
    <BLANKLINE>
    [feed.f2]
    url = http://b.com/rss.atom

    Cleanup the temporary directory.

    >>> tmpdir.cleanup()
    """
    datafile_version = 2
    datafile_encoding = 'utf-8'

    def __init__(self, configfiles=None, datafile=None, config=None):
        super(Feeds, self).__init__()
        if configfiles is None:
            configfiles = self._get_configfiles()
        self.configfiles = configfiles
        if datafile is None:
            datafile = self._get_datafile()
        self.datafile = datafile
        if config is None:
            config = _config.CONFIG
        self.config = config
        self._datafile_lock = None

    def __getitem__(self, key):
        for feed in self:
            if feed.name == key:
                return feed
        try:
            index = int(key)
        except ValueError as e:
            raise IndexError(key) from e
        return super(Feeds, self).__getitem__(index)

    def __append__(self, feed):
        feed.load_from_config(self.config)
        feed = super(Feeds, self).append(feed)

    def __pop__(self, index=-1):
        feed = super(Feeds, self).pop(index=index)
        if feed.section in self.config:
            self.config.pop(feed.section)
        return feed

    def index(self, index):
        if isinstance(index, int):
            try:
                return self[index]
            except IndexError as e:
                raise _error.FeedIndexError(index=index, feeds=self) from e
        elif isinstance(index, str):
            try:
                index = int(index)
            except ValueError:
                pass
            else:
                return self.index(index)
            for feed in self:
                if feed.name == index:
                    return feed
        try:
            super(Feeds, self).index(index)
        except (IndexError, ValueError) as e:
            raise _error.FeedIndexError(index=index, feeds=self) from e

    def remove(self, feed):
        super(Feeds, self).remove(feed)
        if feed.section in self.config:
            self.config.pop(feed.section)

    def clear(self):
        while self:
            self.pop(0)

    def _get_configfiles(self):
        """Get configuration file paths

        Following the XDG Base Directory Specification.
        """
        config_home = _os.environ.get(
            'XDG_CONFIG_HOME',
            _os.path.expanduser(_os.path.join('~', '.config')))
        config_dirs = [config_home]
        config_dirs.extend(
            _os.environ.get(
                'XDG_CONFIG_DIRS',
                _os.path.join(ROOT_PATH, 'etc', 'xdg'),
                ).split(':'))
        # reverse because ConfigParser wants most significant last
        return list(reversed(
                [_os.path.join(config_dir, 'rss2email.cfg')
                 for config_dir in config_dirs]))

    def _get_datafile(self):
        """Get the data file path

        Following the XDG Base Directory Specification.
        """
        data_home = _os.environ.get(
            'XDG_DATA_HOME',
            _os.path.expanduser(_os.path.join('~', '.local', 'share')))
        data_dirs = [data_home]
        data_dirs.extend(
            _os.environ.get(
                'XDG_DATA_DIRS',
                ':'.join([
                        _os.path.join(ROOT_PATH, 'usr', 'local', 'share'),
                        _os.path.join(ROOT_PATH, 'usr', 'share'),
                        ]),
                ).split(':'))
        datafiles = [_os.path.join(data_dir, 'rss2email.json')
                     for data_dir in data_dirs]
        for datafile in datafiles:
            if _os.path.isfile(datafile):
                return datafile
        return datafiles[0]

    def load(self, lock=True, require=False):
        _LOG.debug('load feed configuration from {}'.format(self.configfiles))
        if self.configfiles:
            self.read_configfiles = self.config.read(self.configfiles)
        else:
            self.read_configfiles = []
        _LOG.debug('loaded configuration from {}'.format(
                self.read_configfiles))
        self._load_feeds(lock=lock, require=require)

    def _load_feeds(self, lock, require):
        _LOG.debug('load feed data from {}'.format(self.datafile))
        if not _os.path.exists(self.datafile):
            if require:
                raise _error.NoDataFile(feeds=self)
            _LOG.info('feed data file not found at {}'.format(self.datafile))
            _LOG.debug('creating an empty data file')
            dirname = _os.path.dirname(self.datafile)
            if dirname and not _os.path.isdir(dirname):
                _os.makedirs(dirname, mode=0o700, exist_ok=True)
            with _codecs.open(self.datafile, 'w', self.datafile_encoding) as f:
                self._save_feed_states(feeds=[], stream=f)
        try:
            self._datafile_lock = _codecs.open(
                self.datafile, 'r', self.datafile_encoding)
        except IOError as e:
            raise _error.DataFileError(feeds=self) from e

        locktype = 0
        if lock and UNIX:
            locktype = _fcntl.LOCK_EX
            _fcntl.flock(self._datafile_lock.fileno(), locktype)

        self.clear()

        level = _LOG.level
        handlers = list(_LOG.handlers)
        feeds = []
        try:
            data = _json.load(self._datafile_lock)
        except ValueError as e:
            _LOG.info('could not load data file using JSON')
            data = self._load_pickled_data(self._datafile_lock)
        version = data.get('version', None)
        if version != self.datafile_version:
            data = self._upgrade_state_data(data)
        for state in data['feeds']:
            feed = _feed.Feed(name='dummy-name')
            feed.set_state(state)
            if 'name' not in state:
                raise _error.DataFileError(
                    feeds=self,
                    message='missing feed name in datafile {}'.format(
                        self.datafile))
            feeds.append(feed)
        _LOG.setLevel(level)
        _LOG.handlers = handlers
        self.extend(feeds)

        if locktype == 0:
            self._datafile_lock.close()
            self._datafile_lock = None

        for feed in self:
            feed.load_from_config(self.config)

        feed_names = set(feed.name for feed in self)
        order = _collections.defaultdict(lambda: (1e3, ''))
        for i,section in enumerate(self.config.sections()):
            if section.startswith('feed.'):
                name = section[len('feed.'):]
                order[name] = (i, name)
                if name not in feed_names:
                    _LOG.debug(
                        ('feed {} not found in feed file, '
                         'initializing from config').format(name))
                    self.append(_feed.Feed(name=name, config=self.config))
                    feed_names.add(name)
        def key(feed):
            return order[feed.name]
        self.sort(key=key)

    def _load_pickled_data(self, stream):
        _LOG.info('try and load data file using Pickle')
        with open(self.datafile, 'rb') as f:
            feeds = list(feed.get_state() for feed in _pickle.load(f))
        return {
            'version': self.datafile_version,
            'feeds': feeds,
            }

    def _upgrade_state_data(self, data):
        version = data.get('version', 'unknown')
        if version == 1:
            for feed in data['feeds']:
                seen = feed['seen']
                for guid,id_ in seen.items():
                    seen[guid] = {'id': id_}
            return data
        raise NotImplementedError(
            'cannot convert data file from version {} to {}'.format(
                version, self.datafile_version))

    def save(self):
        _LOG.debug('save feed configuration to {}'.format(self.configfiles[-1]))
        for feed in self:
            feed.save_to_config()
        dirname = _os.path.dirname(self.configfiles[-1])
        if dirname and not _os.path.isdir(dirname):
            _os.makedirs(dirname, mode=0o700, exist_ok=True)
        tmpfile = self.configfiles[-1] + '.tmp'
        with open(tmpfile, 'w') as f:
            self.config.write(f)
            f.flush()
            _os.fsync(f.fileno())
        _os.rename(tmpfile, self.configfiles[-1])
        self._save_feeds()

    def _save_feeds(self):
        _LOG.debug('save feed data to {}'.format(self.datafile))
        dirname = _os.path.dirname(self.datafile)
        if dirname and not _os.path.isdir(dirname):
            _os.makedirs(dirname, mode=0o700, exist_ok=True)
        tmpfile = self.datafile + '.tmp'
        with _codecs.open(tmpfile, 'w', self.datafile_encoding) as f:
            self._save_feed_states(feeds=self, stream=f)
            f.flush()
            _os.fsync(f.fileno())
        _os.rename(tmpfile, self.datafile)
        if UNIX and self._datafile_lock is not None:
            self._datafile_lock.close()  # release the lock
            self._datafile_lock = None

    def _save_feed_states(self, feeds, stream):
        _json.dump(
            {'version': self.datafile_version,
             'feeds': list(feed.get_state() for feed in feeds),
             },
            stream,
            indent=2,
            separators=(',', ': '),
            )
        stream.write('\n')

    def new_feed(self, name=None, prefix='feed-', **kwargs):
        """Return a new feed, possibly auto-generating a name.

        >>> feeds = Feeds()
        >>> print(feeds.new_feed(name='my-feed'))
        my-feed (None -> a@b.com)
        >>> print(feeds.new_feed())
        feed-0 (None -> a@b.com)
        >>> print(feeds.new_feed())
        feed-1 (None -> a@b.com)
        """
        if name is None:
            i = 0
            while True:
                name = '{}{}'.format(prefix, i)
                feed_names = [feed.name for feed in self]
                if name not in feed_names:
                    break
                i += 1
        feed = _feed.Feed(name=name, **kwargs)
        self.append(feed)
        return feed
