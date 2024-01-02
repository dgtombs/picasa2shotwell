#!/usr/bin/env python3
"""Python classes and functions for reading a Picasa "db3" database.

   Many thanks to
   <https://skisoo.com/blog/en/2013/how-to-read-picasa-3-9-database-and-extract-faces/>
   for the format description."""

import logging
import re
import struct

from pathlib import Path, PureWindowsPath

# Matcher for .pmp filenames.
# Group 1 is the "table" (e.g., 'imagedata').
# Group 2 is the field (e.g., 'caption').
PMP_FILENAME_MATCHER = re.compile(r'^([a-z]+)_([a-z]+).pmp$')

# parent index value meaning no parent
IDX_NO_PARENT = 0xFFFFFFFF

# Null-terminated string
FIELD_TYPE_STRING = 0

# 32-bit integer (unsigned?)
FIELD_TYPE_I32 = 1

# Apparently only used by imagedata_tags, seems to be a list of strings separated by
# commas.
FIELD_TYPE_STRING_LIST = 6

# Future improvement: define our own exception class to raise upon invalid data.

class ImagedataRecord:
    """Represents a single record in the 'imagedata' DB.

    Note that we do not necessarily load all fields/columns in each record,
    so the ones we do load are stored in the dictionary loaded_fields."""

    @staticmethod
    def read(file):
        """Reads a ImagedataRecord from the given file (presumably thumbindex.db)."""
        path = read_string(file)
        # Not sure what these are; don't need them for now at least.
        file.read(26)
        parentidx = read_unsigned_int(file)
        return ImagedataRecord(path, parentidx)

    def __init__(self, path, parentidx, loaded_fields=None):
        if loaded_fields is None:
            loaded_fields = {}
        self.path = path
        self.parentidx = parentidx
        self.loaded_fields = loaded_fields

    def __str__(self):
        return 'ImagedataRecord' + str(vars(self))

def read_unsigned_int(file):
    """Reads a single 4-byte unsigned integer from the given file."""
    bytes_ = file.read(4)
    if len(bytes_) < 4:
        raise Exception(f'Unable to read four bytes from file, got {bytes_}')
    return struct.unpack("<I", bytes_)[0]

def read_unsigned_short(file):
    """Reads a single 2-byte unsigned integer from the given file."""
    bytes_ = file.read(2)
    if len(bytes_) < 2:
        raise Exception(f'Unable to read two bytes from file, got {bytes_}')
    return struct.unpack("<H", bytes_)[0]

def read_string(file):
    """Reads a null-terminated string from the given file."""
    arr = bytearray()
    while True:
        read_result = file.read(1)
        if not read_result:
            raise Exception('Unexpected EOF while reading null-terminated string')
        byte = read_result[0]
        if byte == 0:
            break
        arr.append(byte)
    logging.debug('About to decode bytes %s', arr)
    # Appears to be UTF-8 🤷
    return arr.decode(encoding='utf-8')

def read_string_list(file):
    """Reads a list of strings (FIELD_TYPE_STRING_LIST) from the given file."""
    # Run through filter() to convert '' into a zero-element list.
    # Picasa appears to use string lists only for tags, and presumably all tags will be at
    # least one character.
    return list(filter(None, read_string(file).split(',')))

def read_thumbindex_db(path):
    """Reads the primary DB (thumbindex.db) for the info we want.

    Returns a list of ImagedataRecord objects in file order"""
    with open(path, "rb") as file:
        magic = read_unsigned_int(file)
        if magic != 0x40466666:
            raise Exception(f'unexpected thumbindex magic number {magic}')
        nentries = read_unsigned_int(file)
        return [ImagedataRecord.read(file) for i in range(nentries)]

def field_from_path(path):
    """Returns the field name from a path to a .pmp file.

    E.g., returns 'caption' for 'C:\\db3\\imagedata_caption.pmp'."""
    match_result = PMP_FILENAME_MATCHER.match(Path(path).name)
    if not match_result:
        raise Exception(f'Invalid pmp filename {path}')
    return match_result.group(2)

def get_field_reader(field_type):
    """Returns a function to read a field of type `field_type`.

    The function takes a file object as a single parameter and returns the read value."""
    if field_type == FIELD_TYPE_STRING:
        return read_string
    if field_type == FIELD_TYPE_I32:
        return read_unsigned_int
    if field_type == FIELD_TYPE_STRING_LIST:
        return read_string_list

    raise Exception(f'unsupported field type {field_type}')

def read_pmp(path, records):
    """Reads the specified pmp file into the given records."""
    field_name = field_from_path(path)
    with open(path, "rb") as file:
        magic = read_unsigned_int(file)
        if magic != 0x3fcccccd:
            raise Exception(f'unexpected pmp magic number {magic}')
        field_type = read_unsigned_short(file)
        file.read(6) # apparently constant data?
        # Odd that field_type is repeated, check that they match in case we're missing
        # something here.
        field_type2 = read_unsigned_short(file)
        if field_type != field_type2:
            raise Exception('non-matching field_type values in {0}: {1}, {2}'.format(
                path, field_type, field_type2))
        file.read(2)
        nentries = read_unsigned_int(file)
        reader_func = get_field_reader(field_type)
        for i in range(nentries):
            records[i].loaded_fields[field_name] = reader_func(file)

def read_imagedata(dirname, fields):
    """Reads the 'imagedata' DB from the given directory, including the specified fields.

    Returns a list of ImagedataRecords. Note that records with a blank path (perhaps
    deleted files?) are included."""
    dirpath = Path(dirname)
    records = read_thumbindex_db(dirpath / 'thumbindex.db')
    for field in fields:
        read_pmp(dirpath / f'imagedata_{field}.pmp', records)
    return records

def resolve_path(record, records):
    """Returns a PurePath object representing the path to the given
    ImageDataRecords's file.

    'records' must be the entire list of imagedata records in order to
    look up any parent records."""
    # Assumption: paths are Windows paths
    return (PureWindowsPath(record.path)
            if record.parentidx == IDX_NO_PARENT
            else PureWindowsPath(
                resolve_path(records[record.parentidx], records),
                record.path))
