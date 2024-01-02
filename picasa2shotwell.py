#!/usr/bin/env python3
"""A Python script to migrate one specific person's Picasa photo database into Shotwell,
GNOME's photo manager.

Some of this code may be useful elsewhere, but in general this file is not designed as a
reusable module."""

import argparse
import logging
import re
import sqlite3
import sys
import time

from pathlib import Path, PureWindowsPath

import picasa_db3

# Check version before doing anything else.
if sys.version_info[0] != 3 or sys.version_info[1] < 8:
    print("This script requires Python version 3.8")
    sys.exit(1)

### GLOBALS ###

# Path to the Shotwell database
shotwelldb_path = Path.home() / '.local' / 'share' / 'shotwell' / 'data' / 'photo.db'

_shotwelldb = None

### END GLOBALS ###

class ShotwellDb:
    """Provides functions for reading from or writing to the Shotwell database.

    Leaves a DB transaction open until commit() is called."""
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = shotwelldb_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        # Dictionary from tag name to a set of Shotwell-format IDs.
        self._tags_to_write = {}

    def get_photo(self, filepath):
        """If a photo record exists in the DB for the given file path,
        returns its entire PhotoTable row as a sqlite3.Row. Otherwise,
        returns None."""
        # Shotwell stores the absolute path to the file.
        filepath = Path(filepath).resolve()
        # Note that there is a unique constraint on filename.
        return self._conn.execute(
            'SELECT * FROM PhotoTable WHERE filename = ?',
            [str(filepath)]).fetchone()

    def get_video(self, filepath):
        """Like get_photo() but for videos."""
        # Shotwell stores the absolute path to the file.
        filepath = Path(filepath).resolve()
        # Note that there is a unique constraint on filename.
        return self._conn.execute(
            'SELECT * FROM VideoTable WHERE filename = ?',
            [str(filepath)]).fetchone()

    def getsert_event(self, eventname):
        """Returns the id of the event with the given name, creating it if it does not
        yet exist."""
        existing_row = self._conn.execute(
            "SELECT id FROM EventTable WHERE name = ?",
            (eventname,)
        ).fetchone()
        if existing_row:
            return existing_row[0]
        else:
            logging.info('Creating event %s in DB', eventname)
            return self._conn.execute(
                "INSERT INTO EventTable (name) VALUES (?)", (eventname,)
                ).lastrowid

    def set_event(self, filepath, eventid):
        """Sets the specified file's event id."""
        # Shotwell stores the absolute path to the file.
        filepath = filepath.resolve()
        cursor = self._conn.cursor()
        cursor.execute(
            'UPDATE PhotoTable SET event_id = ? WHERE filename = ?',
            [eventid, str(filepath)]
            )
        photo_count = cursor.rowcount
        cursor.execute(
            'UPDATE VideoTable SET event_id = ? WHERE filename = ?',
            [eventid, str(filepath)]
            )
        video_count = cursor.rowcount
        if photo_count + video_count == 0:
            logging.warning('No photo or video record found for filepath %s', filepath)
        elif photo_count + video_count > 1:
            raise Exception(f'Filepath {filepath} matched more than one photo/video!')

    def set_title(self, filepath, title):
        """Sets the specified file's title (aka caption).

        Refuses to set if the file already has a different title."""

        photo_row = self.get_photo(filepath)
        video_row = self.get_video(filepath)

        if photo_row and video_row:
            raise Exception(f'Filepath {filepath} matched more than one photo/video!')

        def warn_or_set(table_name, existing_row):
            if existing_row['title'] and existing_row['title'] != title:
                logging.warning('Refusing to overwrite existing title "%s" for file "%s"',
                                existing_row['title'], filepath)
            else:
                logging.info('Setting title "%s" for file "%s"',
                             title, filepath)
                self._conn.execute(
                    # execute() doesn't support a placeholder for the table name, so just
                    # patch that in. We provide the value so this is safe.
                    'UPDATE ' + table_name + ' SET title = ? WHERE id = ?',
                    [title, existing_row['id']])

        if photo_row:
            warn_or_set('PhotoTable', photo_row)
        elif video_row:
            warn_or_set('VideoTable', video_row)
        else:
            logging.warning(
                'No photo or video record found for filepath "%s", cannot set title %s',
                filepath, title)

    def get_id_string_for_file(self, filepath):
        """Returns the Shotwell ID string for the given file path.

        Shotwell ID strings are 'thumbXXXXXXXXXXXXXXXX' for photos and
        'video-XXXXXXXXXXXXXXXX' for videos.

        Returns None if the photo or video could not be found."""
        photo_row = self.get_photo(filepath)
        video_row = self.get_video(filepath)
        if photo_row and video_row:
            raise Exception(f'File {filepath} found in both photo and video tables!')

        if photo_row:
            photo_id = photo_row['id']
            return str.format('thumb{:016x}', photo_id)
        elif video_row:
            video_id = video_row['id']
            return str.format('video-{:016x}', video_id)
        else:
            return None

    def _ensure_tag_does_not_exist(self, tagname):
        existing_row = self._conn.execute(
            "SELECT id FROM TagTable where name = ?",
            [tagname]
        ).fetchone()
        if existing_row:
            raise Exception(f'Updating existing tag {tagname} is unsupported')

    def tag(self, filename, tagname):
        """Adds the specified tag to the specified file.

        We do not support updating an existing tag so the tag name must not yet exist in
        the database."""
        # Updating an existing tag is hard because of Shotwell's rather obtuse tag format.
        # (I wish they had just used a join table.)
        #
        # Since we only support creating brand new tags, we have to queue up tags to write
        # and then write them upon commit().
        if tagname not in self._tags_to_write:
            self._ensure_tag_does_not_exist(tagname)
            self._tags_to_write[tagname] = set()

        idstr = self.get_id_string_for_file(filename)
        if idstr is None:
            logging.warning(
                'No photo or video record found for file "%s", cannot apply tag %s',
                filename, tagname)

        self._tags_to_write[tagname] |= {idstr}

    def _write_pending_tags(self):
        for tagname, idstrs in self._tags_to_write.items():
            # We should have already checked this, but let's make sure.
            self._ensure_tag_does_not_exist(tagname)

            id_list = ','.join(idstrs) + ','

            logging.info('Creating tag %s with ids: %s...', tagname, id_list)

            self._conn.execute(
                'INSERT INTO TagTable (name, photo_id_list, time_created) VALUES (?, ?, ?)',
                (tagname, id_list, int(time.time()))
            )

        # Clear pending tags now that they are written
        self._tags_to_write = {}

    def commit(self):
        """Commits pending changes to the DB."""
        self._write_pending_tags()
        self._conn.commit()

    def __del__(self):
        self._conn.close()

def _write_tags_to_shotwell(filepath, tags):
    for tag in tags:
        if tag != 'pythontagged' and tag != '':
            # See requirements: prefixing tags
            _shotwelldb.tag(filepath, 'picasa2shotwell ' + tag)

def is_event_directory(dirname):
    """Returns true if the given directory name should be treated as an "event" name,
    false otherwise."""
    # The name must have more than two characters and contain at least one alphabetic
    # character.
    return len(dirname) > 2 and re.search('[a-zA-Z]', dirname)

def is_year(dirname):
    """Returns whether the given string looks like a four-digit year."""
    # We probably don't have any photos from before 1,000 AD, so just match years starting
    # with 1 or 2.
    return re.match(r'[12]\d{3}', dirname) is not None

def is_year_month(dirname):
    """Returns whether the given string looks like YYYY-MM."""
    return re.match(r'[12]\d{3}-[01]\d', dirname) is not None

def make_event_name_from_directory(directory):
    """Makes an event name from a directory path.

    A single directory name may be repeated in different years so we try to combine two
    directory names to make the event name."""
    parts = directory.parts

    # We need at least Pictures/year/event_name or Pictures/Life/event_name
    if len(parts) >= 3 and parts[0] == 'Pictures':
        if is_year(parts[1]):
            # It's a year subdirectory.
            year = parts[1]
            # Is the next directory a valid event name?
            name_under_year = parts[2]
            if is_event_directory(name_under_year):
                return year + ' - ' + name_under_year
            elif is_year_month(name_under_year) and len(parts) >= 4:
                name_under_month = parts[3]
                if is_event_directory(name_under_month):
                    return f'{name_under_year} - {name_under_month}'

        if parts[1] == 'Life':
            # It's a "Life" subdirectory, use the next two directories as the event name.
            if len(parts) > 3:
                return parts[2] + ' - ' + parts[3]
            else:
                return parts[2]

    return None


def create_event_if_appropriate(directory):
    """If the given directory (a Path object) appears to be an event directory (as
    determinated by `make_event_name_from_directory()`, then creates an event for the
    directory and sets it as the event for each file in the directory."""
    desired_event_name = make_event_name_from_directory(directory)
    if desired_event_name:
        logging.info('Creating event "%s" for directory %s', desired_event_name, directory)
        eventid = _shotwelldb.getsert_event(desired_event_name)
        for child in directory.iterdir():
            # Assumption: hidden files will not be in Shotwell DB.
            if child.is_file() and child.parts[-1][0] != '.':
                logging.info(
                    'Updating %s event to %s (%s)',
                    child, eventid, desired_event_name)
                _shotwelldb.set_event(child, eventid)

def create_events_for_tree(directory):
    """Creates Shotwell events for the given directory and subdirectories, as
    appropriate."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f'passed "{directory}" is not a directory')

    # Create the event for this particular directory (if appropriate)
    create_event_if_appropriate(directory)

    # Recurse.
    for child in directory.iterdir():
        if child.is_dir():
            create_events_for_tree(child)

def windows2linux(windows_path):
    r"""Returns the linux equivalent of the given Windows path.

    The given path is expected to be of form C:\Users\Username\etcetera,
    and the returned path will be /home/username/etcetera."""
    windows_path = PureWindowsPath(windows_path)
    if not windows_path.is_absolute():
        raise ValueError(f'Supplied windows path "{windows_path}" is not absolute')
    # Since is_absolute() returned true, we should have a drive letter and a root.
    # We don't care what the drive letter was, but the first path component must be
    # 'Users'.
    if len(windows_path.parts) < 3 or windows_path.parts[1] != 'Users':
        raise ValueError(
            f"Supplied windows path '{windows_path}' must be in a user's home directory")

    return Path(Path.home(), *windows_path.parts[3:])

def _copy_file_metadata(picasa_path, fields):
    """Copies metadata for a single file."""
    if fields.get('caption'):
        _shotwelldb.set_title(windows2linux(picasa_path), fields['caption'])
    if fields.get('tags'):
        _write_tags_to_shotwell(windows2linux(picasa_path), fields['tags'])

def copy_db_metadata(picasa_db3_path):
    """Copies desired metadata from the specified Picasa DB to the Shotwell DB."""
    imagedata_records = picasa_db3.read_imagedata(picasa_db3_path, ['caption', 'tags'])
    for record in imagedata_records:
        # Skip records with empty paths. (See comment on read_imagedata().)
        if record.path:
            _copy_file_metadata(
                picasa_db3.resolve_path(record, imagedata_records),
                record.loaded_fields)

def _main():
    global _shotwelldb

    # Just extract this out for readability.
    def create_events(root_paths):
        for root_path in root_paths:
            print(f'Creating events for {root_path}...')
            create_events_for_tree(root_path)

    argparser = argparse.ArgumentParser(prog='picasa2shotwell')
    argparser.add_argument('roots', nargs='*',
                           help='directories to scan for creating events')
    argparser.add_argument('--db3-path',
                           help='path to the Picasa db3 directory. '
                           "If omitted, will skip copying metadata from Picasa's database")
    argparser.add_argument('--dry-run', action='store_true')
    args = argparser.parse_args()

    dry_run = args.dry_run

    if dry_run:
        print('DRY RUN MODE')
    else:
        print('UPDATE MODE')

    _shotwelldb = ShotwellDb()

    create_events(args.roots)

    if args.db3_path:
        print('Copying metadata from Picasa...')
        copy_db_metadata(args.db3_path)

    if not dry_run:
        _shotwelldb.commit()

if __name__ == '__main__':
    _main()
