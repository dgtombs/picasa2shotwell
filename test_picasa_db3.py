#!/usr/bin/env python3
"""Tests for picasa_db3 module."""

import io
import unittest

import picasa_db3

from picasa_db3 import ImagedataRecord

#logging.basicConfig(level=logging.DEBUG)

class TestReadString(unittest.TestCase):
    def test_success(self):
        cases = [
            # (raw bytes, expected result, expected stream position after read)
            (b'\x00extra', '', 1),
            (b'C:\\Users\\test\\Pictures\x00extra', 'C:\\Users\\test\\Pictures', 23),
        ]
        for raw_bytes, expected_result, expected_pos in cases:
            with self.subTest(raw_bytes=raw_bytes):
                with io.BytesIO(raw_bytes) as bytesio:
                    actual_result = picasa_db3.read_string(bytesio)
                    self.assertEqual(actual_result, expected_result)
                    self.assertEqual(bytesio.tell(), expected_pos)

    def test_unexpected_eof(self):
        """Verifies that the function raises an exception if the input ends before the
        terminating null char is seen."""
        raw_bytes = b'hello'
        with io.BytesIO(raw_bytes) as bytesio:
            with self.assertRaises(Exception):
                picasa_db3.read_string(bytesio)

class TestReadStringList(unittest.TestCase):
    def test(self):
        cases = [
            # (raw bytes, expected result, expected stream position after read)
            (b'\x00', [], 1),
            (b'one,two\x00extra', ['one', 'two'], 8),
        ]
        for raw_bytes, expected_result, expected_pos in cases:
            with self.subTest(raw_bytes=raw_bytes):
                with io.BytesIO(raw_bytes) as bytesio:
                    actual_result = picasa_db3.read_string_list(bytesio)
                    self.assertEqual(actual_result, expected_result)
                    self.assertEqual(bytesio.tell(), expected_pos)

class TestFieldFromPath(unittest.TestCase):
    def test(self):
        self.assertEqual(
            picasa_db3.field_from_path('/test/imagedata_caption.pmp'),
            'caption')

class TestReadImagedata(unittest.TestCase):
    def assertImagedataRecordEqual(self, first, second, msg):
        self.assertEqual(first.path, second.path, msg + ': paths not equal')
        self.assertEqual(first.parentidx, second.parentidx, msg + ': parentidx not equal')
        self.assertEqual(
            first.loaded_fields,
            second.loaded_fields,
            msg + ': loaded_fields not equal')

    def test(self):
        expected_result = [
            ImagedataRecord(
                'C:\\Users\\Steve\\Pictures\\',
                picasa_db3.IDX_NO_PARENT,
                {'filetype': 1}),
            ImagedataRecord(
                'C:\\Users\\Steve\\Documents\\',
                picasa_db3.IDX_NO_PARENT,
                {'filetype': 5}),
            ImagedataRecord(
                'C:\\Users\\Steve\\Desktop\\',
                picasa_db3.IDX_NO_PARENT,
                {'filetype': 1}),
            ImagedataRecord(
                'C:\\Users\\Steve\\Videos\\',
                picasa_db3.IDX_NO_PARENT,
                {'filetype': 1}),
            ImagedataRecord(
                'C:\\',
                picasa_db3.IDX_NO_PARENT,
                {'filetype': 5}),
            ImagedataRecord(
                'ping.jpg',
                0,
                {'filetype': 2}),
        ]
        actual_result = picasa_db3.read_imagedata('testdata/db3', ['filetype'])
        # There is probably a more elegant way to compare lists...
        self.assertEqual(len(actual_result), len(expected_result))
        for i in range(len(expected_result)):
            actual = actual_result[i]
            expected = expected_result[i]
            self.assertImagedataRecordEqual(actual, expected, f'index {i} not equal')

if __name__ == '__main__':
    unittest.main()
