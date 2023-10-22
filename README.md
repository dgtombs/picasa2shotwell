picasa2shotwell
===============

A Python script to migrate one specific person's Picasa photo database into Shotwell,
GNOME's photo manager.

Requirements
------------

High-level requirements:

1. Create tags in Shotwell based on PicasaDBReader export.
2. Create captions in Shotwell based on the same.
3. Auto-create events based on folder names.

Some folder -> event name examples can be found in the test suite.


Picasa Format Notes
--------------------

* All tags go in Picasa's 'pmp' DB format.
  * See <https://github.com/skisoo/PicasaDBReader> for reading this format.
* Photo tags also go in EXIF data (and Shotwell reads these)
* Photo captions also go in EXIF title (and Shotwell reads these)
* Not sure where 'star' status is stored.
* Picasa writes some data to `.picasa.ini` files but these are incomplete enough to be
  pretty much useless.
