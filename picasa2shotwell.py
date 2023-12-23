#!/usr/bin/env python3

import argparse
import re
import sqlite3
import sys
import time

from pathlib import Path

# Check version before doing anything else.
if sys.version_info[0] != 3 or sys.version_info[1] < 8:
    print("This script requires Python version 3.8")
    sys.exit(1)

### GLOBALS ###

# Path to the Shotwell database
shotwelldb_path = Path.home() / '.local' / 'share' / 'shotwell' / 'data' / 'photo.db'

dry_run = False

### END GLOBALS ###

class ShotwellDb:
    """Provides functions for reading from or writing to the Shotwell database."""
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = shotwelldb_path
        self.conn = sqlite3.connect(db_path)
        # Dictionary from tag name to a set of Shotwell-format IDs.
        self.tagsToWrite = {}

    def setRating(self, filepath, rating):
        # Shotwell stores the absolute path to the file.
        filepath = filepath.resolve()
        print('Updating', filepath, 'rating to', rating, '...')
        cursor = self.conn.cursor()
        cursor.execute(
                'UPDATE PhotoTable SET rating = ? WHERE filename = ?',
                [rating, str(filepath)]
                )
        photo_count = cursor.rowcount
        cursor.execute(
                'UPDATE VideoTable SET rating = ? WHERE filename = ?',
                [rating, str(filepath)]
                )
        video_count = cursor.rowcount
        if photo_count + video_count != 1:
            raise Exception(
                    f'Unexpected row count for rating update: photo_count={photo_count}, video_count={video_count}')

    def createEvent(self, eventname):
        """Creates an event in the shotwell DB and returns its id"""
        existing_row = self.conn.execute(
            "SELECT id FROM EventTable WHERE name = ?",
            (eventname,)
        ).fetchone()
        if existing_row:
            return existing_row[0]
        else:
            print('Creating event', eventname)
            return self.conn.execute(
                    "INSERT INTO EventTable (name) VALUES (?)", (eventname,)
                ).lastrowid

    def setEvent(self, filepath, eventid):
        # Shotwell stores the absolute path to the file.
        filepath = filepath.resolve()
        cursor = self.conn.cursor()
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
            print(f'No photo or video record found for filepath {filepath}')
        elif photo_count + video_count > 1:
            raise Exception(f'Filepath {filepath} matched more than one photo/video!')

    def getIdStringForFilename(self, filepath):
        """Returns the Shotwell ID string for the given file path.

        Shotwell ID strings are 'thumbXXXXXXXXXXXXXXXX' for photos and
        'video-XXXXXXXXXXXXXXXX' for videos.

        Returns None if the photo or video could not be found."""
        # Shotwell stores the absolute path to the file.
        filepath = filepath.resolve()
        # Note: there is a UNIQUE contraint on `filename` in both tables.
        photo_row = self.conn.execute(
                'SELECT id FROM PhotoTable WHERE filename = ?',
                [str(filepath)]
        ).fetchone()
        video_row = self.conn.execute(
                'SELECT id FROM VideoTable WHERE filename = ?',
                [str(filepath)]
        ).fetchone()
        if photo_row and video_row:
            raise Exception(f'File {filename} found in both photo and video tables!')

        if photo_row:
            photo_id = photo_row[0]
            return str.format('thumb{:016x}', photo_id)
        elif video_row:
            video_id = video_row[0]
            return str.format('video-{:016x}', video_id)
        else:
            return None

    def ensureTagDoesNotExist(self, tagname):
        existing_row = self.conn.execute(
                "SELECT id FROM TagTable where name = ?",
                [tagname]
        ).fetchone()
        if existing_row:
            raise Exception(f'Updating existing tag {tagname} is unsupported')

    def tag(self, filename, tagname):
        # Since Shotwell's tag format is a bit obtuse, we just queue up tags to write
        # and write them upon commit().
        #
        # We also do not support modifying tags which already exist in the DB since I
        # haven't reverse-engineered every format.
        #
        # I wish they just used a join table.
        if tagname not in self.tagsToWrite:
            self.ensureTagDoesNotExist(tagname)
            self.tagsToWrite[tagname] = set()

        idstr = self.getIdStringForFilename(filename)
        if idstr is None:
            raise Exception(f'Filename {filename} not found in DB.')

        self.tagsToWrite[tagname] |= {idstr}

    def writePendingTags(self):
        for tagname, idstrs in self.tagsToWrite.items():
            # We should have already checked this, but let's make sure.
            self.ensureTagDoesNotExist(tagname)

            id_list = ','.join(idstrs) + ','

            print(f'Creating tag {tagname} with ids: {id_list}...')

            self.conn.execute(
                'INSERT INTO TagTable (name, photo_id_list, time_created) VALUES (?, ?, ?)',
                (tagname, id_list, int(time.time()))
            )

        # Clear pending tags now that they are written
        self.tagsToWrite = {}

    def commit(self):
        """Commits pending changes to the DB."""
        self.writePendingTags()
        self.conn.commit()

def writeTagsToShotwell(filepath, tags):
    for tag in tags:
        if tag == 'pythontagged' or tag == '':
            continue
        else:
            # See requirements: prefixing tags
            shotwelldb.tag(filepath, 'picasa2shotwell ' + tag)

def isEventDirectory(dirname):
    """Returns true if the given directory name should be treated as an "event" name,
    false otherwise."""
    # The name must have more than two characters and contain at least one alphabetic
    # character.
    p = re.compile('[a-zA-Z]')
    return len(dirname) > 2 and p.search(dirname)

def isYear(dirname):
    """Returns whether the given string looks like a four-digit year."""
    # We probably don't have any photos from before 1,000 AD, so just match years starting
    # with 1 or 2.
    return re.match('[12]\d{3}', dirname) != None

def isYearMonth(dirname):
    """Returns whether the given string looks like YYYY-MM."""
    return re.match('[12]\d{3}-[01]\d', dirname) != None

def makeEventNameFromDirectory(directory):
    """Makes an event name from a directory.

    A single directory name may be repeated in different years so we try to combine two
    directory names to make the event name."""
    parts = directory.parts

    # We need at least Pictures/year/event_name or Pictures/Life/event_name
    if len(parts) >= 3 and parts[0] == 'Pictures':
        if isYear(parts[1]):
            # It's a year subdirectory.
            year = parts[1]
            # Is the next directory a valid event name?
            name_under_year = parts[2]
            if isEventDirectory(name_under_year):
                return year + ' - ' + name_under_year
            elif isYearMonth(name_under_year) and len(parts) >= 4:
                name_under_month = parts[3]
                if isEventDirectory(name_under_month):
                    return f'{name_under_year} - {name_under_month}'

        if parts[1] == 'Life':
            # It's a "Life" subdirectory, use the next two directories as the event name.
            if len(parts) > 3:
                return parts[2] + ' - ' + parts[3]
            else:
                return parts[2]


def createEventIfAppropriate(directory):
    desired_event_name = makeEventNameFromDirectory(directory)
    if desired_event_name:
        eventid = shotwelldb.createEvent(desired_event_name)
        for child in directory.iterdir():
            # Assumption: hidden files will not be in Shotwell DB.
            if child.is_file() and child.parts[-1][0] != '.':
                print(f'Updating {child} event to {eventid} ({desired_event_name})')
                shotwelldb.setEvent(child, eventid)

def createEventAndRecurse(directory):
    """Creates a Shotwell event for the given directory and subdirectories, as
    appropriate."""
    if directory.is_dir() == False:
        raise Exception('createEvent() passed non-directory ' + str(directory))

    # Create the event for this particular directory (if appropriate)
    createEventIfAppropriate(directory)

    # Recurse.
    for child in directory.iterdir():
        if child.is_dir():
            createEventAndRecurse(child)

def createEvents(root_paths):
    for root_path in root_paths: createEventAndRecurse(root_path)

def main():
    global dry_run
    global shotwelldb

    argparser = argparse.ArgumentParser(prog='picasa2shotwell')
    argparser.add_argument('roots', nargs='+')
    argparser.add_argument('--dry-run', action='store_true')
    args = argparser.parse_args()

    dry_run = args.dry_run
    
    if dry_run:
        print('DRY RUN MODE')
    else:
        print('UPDATE MODE')

    shotwelldb = ShotwellDb()

    # Convert args roots into paths
    root_paths = [Path(path_str) for path_str in args.roots]

    createEvents(root_paths)

    if dry_run == False:
        shotwelldb.commit()

if __name__ == '__main__':
    main()
