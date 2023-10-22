from pathlib import Path, PurePath
import picasa2shotwell
import unittest

def makeDb():
    return picasa2shotwell.ShotwellDb(Path('testdata') / 'photo.db')

class TestShotwellDb(unittest.TestCase):

    def test_getIdStringForFilename(self):
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
                idstr = db.getIdStringForFilename(Path(filename))
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

        self.assertEqual(db.tagsToWrite, expectedTagsToWrite)


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
                        picasa2shotwell.makeEventNameFromDirectory(path),
                        expected_result
                    )

if __name__ == '__main__':
    unittest.main()
