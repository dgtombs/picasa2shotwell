#!/usr/bin/env python3
#
# Requirements:
#
# 1. Extract rating tags from picasa INI files and apply to Shotwell DB.
# 2. Extract non-rating tags from " " " and print to stdout. (Since tags in the Shotwell DB
#    are tough.)
# 3. Auto-create events based on folder names.

# Picasa format notes:
#
# * Photo tags go in EXIF data (and Shotwell reads these)
#   * I think we can bulk-assign numerical ratings as long as the tags get into Shotwell.
# * Photo captions go in EXIF title. (Does Shotwell read this?)
# * Video tags go in .picasa.ini.
# * Video captions I can't find!

import argparse
import configparser
import os
import sqlite3
import sys

from itertools import chain
from pathlib import Path

### GLOBALS ###

# Path to the Shotwell database
shotwelldb_path = Path.home() / '.local' / 'share' / 'shotwell' / 'data' / 'photo.db'

shotwelldb_conn = sqlite3.connect(shotwelldb_path)

dry_run = False

### END GLOBALS ###

def writeRating(filepath, rating):
    print('Updating', filepath, 'rating to', rating, '...')
    cursor = shotwelldb_conn.cursor()
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


def writeTagsToShotwell(filepath, tags):
    for tag in tags:
        if tag == 'pythontagged':
            continue
        elif tag == 'excellent':
            writeRating(filepath, 5)
        elif tag == 'good':
            writeRating(filepath, 4)
        elif tag == 'OK':
            writeRating(filepath, 3)
        elif tag == 'bad':
            writeRating(filepath, 2)
        else:
            print('other tag', str(filepath), tag, sep='\t')

def extractTags(picasa_ini_path):
    ini = configparser.ConfigParser()
    ini.read_file(picasa_ini_path.open())
    # Section names are filenames
    for filename in ini.sections():
        filepath = (picasa_ini_path.parent / filename).resolve()
        tags = ini[filename]['keywords'].split(',')
        writeTagsToShotwell(filepath, tags)

def findPicasaInis(root_paths):
    """Returns an iterable of all the Picasa INIs in root_paths"""
    return chain.from_iterable(root_path.glob('**/.picasa.ini') for root_path in root_paths)

def main():
    global dry_run

    argparser = argparse.ArgumentParser(prog='picasa2shotwell')
    argparser.add_argument('roots', nargs='+')
    argparser.add_argument('--dry-run', action='store_true')
    args = argparser.parse_args()

    dry_run = args.dry_run
    
    if dry_run:
        print('DRY RUN MODE')
    else:
        print('UPDATE MODE')

    # Convert args roots into paths
    root_paths = [Path(path_str) for path_str in args.roots]

    print('root_paths:', root_paths)

    for picasa_ini_path in findPicasaInis(root_paths):
        print("Processing", str(picasa_ini_path), "...", file=sys.stderr)
        extractTags(picasa_ini_path)

    if dry_run == False:
        shotwelldb_conn.commit()

main()
