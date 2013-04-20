#!/usr/bin/env python
from __future__ import with_statement
import os, os.path
import subprocess
import socket
import struct
import ConfigParser
import StringIO

class Cli:
    extra_arguments = []
    configfile = "~/.moc/config"
    socketfile = "~/.moc/socket2"

STATE_NOT_RUNNING = -1
STATE_STOPPED = 0
STATE_PAUSED  = 1
STATE_PLAYING = 2

STATES = {
    'PLAY'  : STATE_PLAYING,
    'STOP'  : STATE_STOPPED,
    'PAUSE' : STATE_PAUSED
}

class MocError(Exception):
    """ Raised if executing a command failed """

class MocNotRunning(MocError):
    """ Raised if a command failed because the moc server does not run """

# Helper functions
def _check_file_args(files):
    """
    Checks if every element from dictonary passed in parameter is a valid 
    filepath, is a http or ftp url.

    Raises TypeError if parameter is a string or OSError if any of files
    in dictonary does not exist.
    """
    if isinstance(files, str):
        raise TypeError("Argument must be a list/iterable, not str")
    for file in files:
        if not os.path.exists(file) and not file.startswith(('http://', 'ftp://')):
            # MOC only supports HTTP and FTP, not even HTTPS.
            # (See `is_url` in `files.c`.)
            raise OSError("File %r does not exist" % file)

def _exec_command(command, parameters=[]):
    cmd = subprocess.Popen(
            ["mocp", "--%s" % command] + parameters + Cli.extra_arguments,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True
    )
    stdout, stderr = cmd.communicate()
    if cmd.returncode:
        errmsg = stderr.strip()
        if 'server is not running' in errmsg:
            raise MocNotRunning(errmsg)
        else:
            raise MocError(errmsg)
    return stdout

def set_config_file(config_file_path):
    if not os.path.exists(config_file_path):
        raise OSError("Configuration file '%r' does not exists" % config_file_path)

    Cli.configfile = config_file_path
    Cli.extra_arguments = Cli.extra_arguments + ["--config", config_file_path]
    update_moc_dir()

def update_moc_dir():
    """
    Reads configuration file and searches for mocdir
    """
    
    configF = StringIO.StringIO()
    configF.write('[dummysection]')
    configF.write(open(os.path.expanduser(Cli.configfile), 'r').read())
    configF.seek(0, os.SEEK_SET)

    config = ConfigParser.RawConfigParser()
    config.readfp(configF)
    if config.get('dummysection', 'MOCDir'):
        Cli.socketfile = config.get('dummysection','MOCDir') + '/socket2'

def start_server():
    """ Starts the moc server. """
    _exec_command('server')
    update_moc_dir()

def stop_server():
    """ Shuts down the moc server.  """
    _exec_command('exit')

def get_state():
    """
    Returns the current state of moc.

    (``STATE_STOPPED``, ``STATE_PAUSED`` or  ``STATE_PLAYING``)
    """
    try:
        return get_info_dict()['state']
    except MocNotRunning:
        return STATE_NOT_RUNNING

def is_paused():
    return get_state() == STATE_PAUSED

def is_playing():
    return get_state() == STATE_PLAYING

def is_stopped():
    return get_state() == STATE_STOPPED

def play():
    """ Restarts playback after it's been stopped. """
    _exec_command('play')

def pause():
    _exec_command('pause')

def stop():
    """ Stops current playback. """
    _exec_command('stop')

def unpause():
    """
    Aliases: ``unpause()``, ``resume()``
    """
    _exec_command('unpause')
resume = unpause

def toggle_playback():
    """
    Toggles playback: If playback was paused, resume; if not, pause.

    Aliases: ``toggle_playback()``, ``toggle_play()``, ``toggle_pause()``, ``toggle()``
    """
    _exec_command('toggle-pause')
toggle_play = toggle_pause = toggle = toggle_playback

def next():
    """ Plays next track. """
    _exec_command('next')

def previous():
    """
    Plays previous track.

    Aliases: ``previous()``, ``prev()``
    """
    _exec_command('previous')
prev = previous


def quickplay(files):
    """
    Plays the given `files` without modifying moc's playlist.

    Raises an :exc:`OSError` if any of the `files` can not be found.
    """
    _check_file_args(files)
    _exec_command('playit', files)


def _moc_output_to_dict(output):
    """
    Converts the given moc `output` into a dictonary. If the output is empty,
    return ``None`` instead.

    The conversion works as follows:
        For each line:
            split the line on first match of a ":"
            where the first part of the result is the key and the second part
            is the value.
            lowercase the key and add the key/value to the dict.
    """
    if not output:
        return
    lines = output.strip('\n').split('\n')
    if 'Running the server...' in lines[0]:
        del lines[0]
    return dict((key.lower(), value[1:]) for key, value in
                (line.split(':', 1) for line in lines))

def get_info_dict():
    """
    Returns a dictionary with information about the track moc currently plays.
    If moc's not playing any track right now (stopped/shut down), returns ``None``.

    The returned dict looks like this::

        {'album'       : 'Whoracle',
         'artist'      : 'In Flames',
         'avgbitrate'  : '320kbps',
         'bitrate'     : '320kbps',
         'currentsec'  : '10',
         'currenttime' : '00:10',
         'file'        : '.../In Flames/Whoracle/In Flames - The Hive.mp3',
         'rate'        : '44kHz',
         'songtitle'   : 'The Hive',
         'state'       : 2, # STATE_PLAYING
         'timeleft'    : '03:53',
         'title'       : '5 In Flames - The Hive (Whoracle)',
         'totalsec'    : '243',
         'totaltime'   : '04:03'}

    Aliases: ``get_info_dict()``, ``info()``, ``get_info()``, ``current_track_info()``
    """
    dct = _moc_output_to_dict(_exec_command('info'))
    if dct is None:
        return
    dct['state'] = STATES[dct['state']]
    return dct
info = get_info = current_track_info = get_info_dict


def increase_volume(level=5):
    """
    Aliases: ``increase_volume()``, ``volume_up()``, ``louder()``, ``upper_volume()``
    """
    _exec_command('volume', ['+%d' % level])
louder = upper_volume = volume_up = increase_volume

def decrease_volume(level=5):
    """
    Aliases: ``decrease_volume()``, ``volume_down()``, ``lower()``, ``lower_volume()``
    """
    _exec_command('volume', ['-%d' % level])
lower = lower_volume = volume_down = decrease_volume

def get_volume():
    s = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
    s.connect(os.path.expanduser(Cli.socketfile))
    s.send(struct.pack('i', 0x1a))
    unpacker = struct.Struct('i i')
    data = s.recv(unpacker.size)
    s.close()

    return unpacker.unpack(data)[1]

def set_volume(level):
    _exec_command('volume', ['%d' % level])

def seek(n):
    """
    Moves the current playback seed forward by `n` seconds
    (or backward if `n` is negative).
    """
    _exec_command('seek', [n])

def _controls(what):
    makefunc = lambda action: lambda: _exec_command(action, [what]) and None or None
    return (makefunc(action) for action in ('on', 'off', 'toggle'))

enable_repeat,   disable_repeat,   toggle_repeat   = _controls('repeat')
enable_shuffle,  disable_shuffle,  toggle_shuffle  = _controls('shuffle')
enable_autonext, disable_autonext, toggle_autonext = _controls('autonext')

def playlist_get(mocdir=None):
    """
    Returns the current playlist or ``None`` if none does exist.

    The returned list has the following format::

        [(title, absolute_path_of_file), (title, absolute_path_of_file), ...]

    Contributed by Robin Wittler. Thanks!

    Aliases: ``playlist_get``, ``get_playlist``
    """
    if not mocdir:
        mocdir = os.path.expanduser('~/.moc')

    playlist_path = os.path.join(mocdir, 'playlist.m3u')

    if not os.path.exists(playlist_path):
        return None

    with open(playlist_path, 'r') as playlist_file:
        # read the first two lines of the file:
        header = [playlist_file.next() for i in xrange(2)]
        # the first two lines must be the m3u format id
        # and the serial for this playlist, e.g.
        #     #EXTM3U
        #     #MOCSERIAL: n
        # If not, it is not a moc created playlist
        # and we return None.
        if not header[0].startswith('#EXTM3U') or \
           not header[1].startswith('#MOCSERIAL'):
            return None

        # ok, everything seems to be fine with this file,
        # go on putting the rest of the content into our
        # own fancy datastructures:
        playlist = []
        for line in playlist_file:
            # Every entry for a song counts two lines:
            #     #EXTINF:n,m song_title
            #     absolute_file_path
            title = line.split(' ', 1)[1] # split at the first ' '
            path = playlist_file.next()
            playlist.append((title.strip('\r\n'), path.strip('\r\n')))
        return playlist
get_playlist = playlist_get

def playlist_append(files_directories_playlists):
    """
    Appends the files, directories and/or in `files_directories_playlists` to
    moc's playlist.
    """
    _check_file_args(files_directories_playlists)
    _exec_command('append', files_directories_playlists)
append_to_playlist = playlist_append

def playlist_clear():
    """ Clears moc's playlist. """
    _exec_command('clear')
clear_playlist = playlist_clear
