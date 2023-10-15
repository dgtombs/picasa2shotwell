picasa2shotwell
===============

A Python script to migrate one specific person's Picasa photo database into Shotwell,
GNOME's photo manager.

Requirements
------------

High-level requirements:

1. Extract rating tags from Picasa INI files and apply to Shotwell DB.
2. Extract non-rating tags from Picasa INI files and print to stdout. (Since tags in the Shotwell
   DB are tough.)
3. Auto-create events based on folder names.

Some folder -> event name examples can be found in the test suite.


Picasa Format Notes
--------------------

* Photo tags go in EXIF data (and Shotwell reads these)
  * I think we can bulk-assign numerical ratings as long as the tags get into Shotwell.
* Photo captions go in EXIF title (and Shotwell reads these)
* Video tags go in .picasa.ini.
* Video captions are stored in Picasa's proprietary DB format which is hard to read.
