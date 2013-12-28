#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

from codecs import open
from collections import namedtuple
import os
import shutil
import sys
from time import time

if sys.version_info[0] == 3:
    ifilter = filter
    imap = map
else:
    from itertools import ifilter
    from itertools import imap

from utils import create_dir
from utils import is_osx
from utils import is_python3
from utils import move_file


BACKUP_THRESHOLD = 24 * 60 * 60
Entry = namedtuple('Entry', ['path', 'weight'])


def dictify(entries):
    """
    Converts a list of entries into a dictionary where
        key = path
        value = weight
    """
    result = {}
    for entry in entries:
        result[entry.path] = entry.weight
    return result


def entriefy(data):
    """Converts a dictionary into an iterator of entries."""
    convert = lambda tup: Entry(*tup)
    if is_python3():
        return map(convert, data.items())
    return imap(convert, data.iteritems())


def load(config):
    """Returns a dictonary (key=path, value=weight) loaded from data file."""
    xdg_aj_home = os.path.join(
            os.path.expanduser('~'),
            '.local',
            'share',
            'autojump')

    if is_osx() and os.path.exists(xdg_aj_home):
        migrate_osx_xdg_data(config)

    if os.path.exists(config['data_path']):
        # example: u'10.0\t/home/user\n' -> ['10.0', u'/home/user']
        parse = lambda line: line.strip().split('\t')

        correct_length = lambda x: len(x) == 2

        # example: ['10.0', u'/home/user'] -> (u'/home/user', 10.0)
        tupleize = lambda x: (x[1], float(x[0]))

        try:
            with open(
                    config['data_path'],
                    'r', encoding='utf-8',
                    errors='replace') as f:
                return dict(
                        imap(
                            tupleize,
                            ifilter(correct_length, imap(parse, f))))
        except (IOError, EOFError):
            return load_backup(config)

    return {}


def load_backup(config):
    if os.path.exists(config['backup_path']):
        move_file(config['backup_path'], config['data_path'])
        return load(config)
    return {}


def migrate_osx_xdg_data(config):
    """
    Older versions incorrectly used Linux XDG_DATA_HOME paths on OS X. This
    migrates autojump files from ~/.local/share/autojump to ~/Library/autojump
    """
    assert is_osx(), "This function should only be run on OS X."

    xdg_data_home = os.path.join(os.path.expanduser('~'), '.local', 'share')
    xdg_aj_home = os.path.join(xdg_data_home, 'autojump')
    data_path = os.path.join(xdg_aj_home, 'autojump.txt'),
    backup_path = os.path.join(xdg_aj_home, 'autojump.txt.bak'),

    if os.path.exists(data_path):
        move_file(data_path, config['data_path'])
    if os.path.exists(backup_path):
        move_file(backup_path, config['backup_path'])

    # cleanup
    shutil.rmtree(xdg_aj_home)
    if len(os.listdir(xdg_data_home)) == 0:
        shutil.rmtree(xdg_data_home)


def save(config, data):
    """Save data and create backup, creating a new data file if necessary."""
    create_dir(os.path.dirname(config['data_path']))

    # atomically save by writing to temporary file and moving to destination
    try:
        # write to temp file
        with open(
                config['tmp_path'],
                'w',
                encoding='utf-8',
                errors='replace') as f:
            for path, weight in data.items():
                if is_python3():
                    f.write(("%s\t%s\n" % (weight, path)))
                else:
                    f.write(unicode(
                        "%s\t%s\n" % (weight, path)).encode('utf-8'))

            f.flush()
            os.fsync(f)
    except IOError as ex:
        print("Error saving autojump data (disk full?)" % ex, file=sys.stderr)
        sys.exit(1)

    # create backup file if it doesn't exist or is older than BACKUP_THRESHOLD
    if not os.path.exists(config['backup_path']) or \
            (time() - os.path.getmtime(config['backup_path'])
                > BACKUP_THRESHOLD):
        move_file(config['data_path'], config['backup_path'])

    # move temp_file -> autojump.txt
    move_file(config['tmp_path'], config['data_path'])
