#!/usr/bin/env python3

from pathlib import Path, PurePath
import logging
import unittest

import picasa2shotwell

def makeDb():
    return picasa2shotwell.ShotwellDb(Path('testdata') / 'photo.db')

class TestShotwellDb(unittest.TestCase):

    def test_get_id_string_for_file(self):
        db = makeDb()
        cases = [
            # (filename, expected result)
            ('/home/david/Pictures/2019/legoland/20191129_133938.mp4',
                'video-000000000000000f'),
            ('/home/david/Pictures/backgrounds/04102_landofmists_1680x1050.jpg',
                'thumb0000000000000bf2'),
            ('/home/david/Pictures/Photos/2008 Caketown/2008 Caketown 1.001.JPG',
                'thumb0000000000000690'),
            ('/home/david/Pictures/Photos/2008 Caketown/2008 Caketown 1.003.JPG',
                'thumb0000000000000691'),
            ('/home/david/thispathdoesnotexist', None),
        ]

        for filename, expected_result in cases:
            with self.subTest(filename=filename):
                idstr = db.get_id_string_for_file(Path(filename))
                self.assertEqual(idstr, expected_result)

    def test_tag(self):
        db = makeDb()

        expectedTagsToWrite = {
            'caketown': {'thumb0000000000000690','thumb0000000000000691'},
            'legolund': {'video-000000000000000f'}
        }

        db.tag(Path('/home/david/Pictures/Photos/2008 Caketown/2008 Caketown 1.001.JPG'),
            'caketown')
        db.tag(Path('/home/david/Pictures/2019/legoland/20191129_133938.mp4'), 'legolund')
        db.tag(Path('/home/david/Pictures/Photos/2008 Caketown/2008 Caketown 1.003.JPG'),
            'caketown')

        # Future improvement: commit modifications and check the actual DB instead of just
        # inspecting this "private" variable.
        self.assertEqual(db._tags_to_write, expectedTagsToWrite)

    def test_get_photo_nonexistent(self):
        self.assertIsNone(makeDb().get_photo('/path/does/not/exist'))

    def test_get_photo_exists(self):
        db = makeDb()
        row = db.get_photo('/home/david/Pictures/2023/IMG_1924.JPG')
        # Not bothering to check every column, just sample them.
        self.assertEqual(row['id'], 3060, 'id should match')
        self.assertEqual(row['filename'], '/home/david/Pictures/2023/IMG_1924.JPG')
        self.assertEqual(row['title'], 'Izzy going out to see the frog')

    def test_get_video_nonexistent(self):
        self.assertIsNone(makeDb().get_video('/path/does/not/exist'))

    def test_get_video_exists(self):
        db = makeDb()
        row = db.get_video('/home/david/Pictures/2011/10/16/DSCN5978.MOV')
        # Not bothering to check every column, just sample them.
        self.assertEqual(row['id'], 3, 'id should match')
        self.assertEqual(row['filename'], '/home/david/Pictures/2011/10/16/DSCN5978.MOV')
        self.assertEqual(row['width'], 400)

    def test_set_title_photo_blank(self):
        # Arrange
        filename = '/home/david/Pictures/2010/P1230692.JPG'
        new_title = 'test_title'
        db = makeDb()

        # Sanity check
        self.assertFalse(db.get_photo(filename)['title'], 'existing title should be falsy')

        # Act
        db.set_title(filename, new_title)

        # Assert
        updated_row = db.get_photo(filename)
        self.assertEqual(updated_row['title'], new_title, 'title should be updated')

    def test_set_title_photo_equivalent(self):
        # Arrange
        filename = '/home/david/Pictures/2023/IMG_1924.JPG'
        new_title = 'Izzy going out to see the frog'
        db = makeDb()

        # Sanity check
        self.assertEqual(db.get_photo(filename)['title'], new_title)

        # Act
        db.set_title(filename, new_title)

        # Assert
        updated_row = db.get_photo(filename)
        self.assertEqual(updated_row['title'], new_title, 'title should be unchanged')

    def test_set_title_photo_no_overwrite(self):
        # Arrange
        filename = '/home/david/Pictures/2023/IMG_1924.JPG'
        existing_title = 'Izzy going out to see the frog'
        new_title = 'test title'
        db = makeDb()

        # Sanity check
        self.assertEqual(db.get_photo(filename)['title'], existing_title)

        # Act & Assert
        with self.assertLogs(level=logging.WARNING):
            db.set_title(filename, new_title)

        self.assertEqual(db.get_photo(filename)['title'], existing_title)

    def test_set_title_video_blank(self):
        filename = '/home/david/Pictures/2011/10/16/DSCN5978.MOV'
        new_title = 'test_title'
        db = makeDb()

        # Sanity check
        self.assertFalse(db.get_video(filename)['title'], 'existing title should be falsy')

        # Act
        db.set_title(filename, new_title)

        # Assert
        updated_row = db.get_video(filename)
        self.assertEqual(updated_row['title'], new_title, 'title should be updated')

    def test_set_title_not_found(self):
        """Verifies set_title() behavior when the passed filename is not found."""
        db = makeDb()
        with self.assertLogs(level=logging.WARNING):
            db.set_title('/path/does/not/exist', 'test title')

    # Missing tests:
    # - refuses to overwrite an existing title on a video
    # - no-op if the title on a video already matches


class TestMakeEventNameFromDirectory(unittest.TestCase):

    def test_returns_correct_name(self):
        cases = [
            # (Path, excepted result)
            ('Pictures/2010/12',                          None),
            ('Pictures/1969/Baby #3 - 12 weeks',          '1969 - Baby #3 - 12 weeks'),
            ('Pictures/2011',                             None),
            ("Pictures/2011/05.07.11, Heather's wedding",
                    "2011 - 05.07.11, Heather's wedding"),
            ("Pictures/2010/Baby's 4th week 10.20-10.26/Originals",
                    "2010 - Baby's 4th week 10.20-10.26"),
            ("Videos/Yerim",                              None),
            ("Pictures/Ebaying/20150427",                 None),
            ("Pictures/2020/2020-12/1225_Christmas",      "2020-12 - 1225_Christmas"),
            ("Pictures/2022/2022-10",                     None),
            ("Pictures/2022/2022-11/11.24 Thanksgiving",  "2022-11 - 11.24 Thanksgiving"),
            ("Pictures/2022/2022 Pro Fam Photos/familysession",
                    "2022 - 2022 Pro Fam Photos"),

            ("Pictures/Life/Fall 2010",                   "Fall 2010"),
            ("Pictures/Life/Fall 2010/20100916_Whoopie pies",
                    "Fall 2010 - 20100916_Whoopie pies"),
            ("Pictures/Life/Fall 2010/20100917 (Pillow cookies)", 
                    "Fall 2010 - 20100917 (Pillow cookies)"),
            ("Pictures/Life/02-03",                       "02-03"),
            ("Pictures/Life/06-07/BCM Banquet/Originals", "06-07 - BCM Banquet"),
        ]

        for path_str, expected_result in cases:
            with self.subTest(path=path_str):
                path = PurePath(path_str)
                self.assertEqual(
                        picasa2shotwell.make_event_name_from_directory(path),
                        expected_result
                    )

class TestWindow2Linux(unittest.TestCase):
    def test_non_absolute_raises_error(self):
        with self.assertRaises(ValueError):
            picasa2shotwell.windows2linux(r'\Users\Steve')

    def test_non_home_raises_error(self):
        bad_paths = [
            r'C:\Program Files\Pictures\ping.jpg',
            r'C:\Users',
        ]
        for bad_path in bad_paths:
            with self.subTest(path=bad_path):
                with self.assertRaises(ValueError):
                    picasa2shotwell.windows2linux(bad_path)

    def test_success(self):
        good_paths = [
            # input, expected suffix appended to home dir
            (r'C:\Users\Steve', ''),
            (r'C:\Users\Steve\Pictures\ping.jpg', 'Pictures/ping.jpg'),
        ]
        for (path, expected_suffix) in good_paths:
            with self.subTest(path=path):
                self.assertEqual(
                    picasa2shotwell.windows2linux(path),
                    Path(Path.home(), expected_suffix))

if __name__ == '__main__':
    unittest.main()
