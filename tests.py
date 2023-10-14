from pathlib import PurePath
import picasa2shotwell
import unittest

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
