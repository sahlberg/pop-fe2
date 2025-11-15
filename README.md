pop-fe2 is a python utility to create PS2Classic PKGs on Linux

This is a work in progress. Not all games have assets defined in the database.
Please add icon0/pic0/pic1/snd0/manual links to any entries that are
uncommented in gamedb.py.

IMPORTANT
=========
MAKE_NPDATA does not build on current Linux.
A patch for this is available at
https://github.com/Sorvigolova/make_npdata/pull/1 
but has not yet been  merged.
Use this repo for the time being:
https://github.com/masible/make_npdata/tree/wip/hadess/modern-linux


Usage
=====

To greate game.pkg from the iso stored in /path/to/game.iso :

$ ./pop-fe2.py --ps3-pkg=game.pkg /path/to/game.iso

You can also have pop-fe2 automatically use the game title from the database
as the name of the generated PKG by using the keyword 'title'

$ ./pop-fe2.py --ps3-pkg=title /path/to/game.iso

Or you can have it use the gameid as the name of the PKG using 'gameid'

$ ./pop-fe2.py --ps3-pkg=gameid /path/to/game.iso

By default pop-fe2 will create the PKG in the current directory.
You can also specify an alternative directory where the PKG should be created in
using --output-directory

$ ./pop-fe2.py --ps3-pkg=gameid --output-directory=/path/to/my/pkgs/ /path/to/game.iso


Batch processing is possible with some simple shellscripting.
For example to scan /path/to/my/isos for all ISO files and then generate a PKG
for each one of them, using the detected name of the game as the PKG filename
and writing them all to /path/to/my/pkgs  you can use something like:

$ find /path/to/my/isos | egrep ".iso$" | while read ISO; do ./pop-fe2.py --ps3-pkg=title --output-directory=/path/to/my/pkgs ${ISO}; done

Installation
============

Fedora42
--------
```console
# Prerequisites
sudo dnf group install -y development-tools
sudo dnf install -y git
sudo dnf install -y g++
sudo dnf install -y cmake
sudo dnf install -y python-is-python3
sudo dnf install -y pip3
sudo dnf install -y python3-devel
sudo dnf install -y python-tkinter
sudo dnf install -y libsndfile-devel
sudo dnf install -y ffmpeg
sudo dnf install -y nodejs
sudo dnf install -y p7zip

pip3 install pygubu
pip3 install pillow
pip3 install pytubefix
pip3 install PyPDF2
pip3 install requests
pip3 install pycdlib
pip3 install ecdsa
pip3 install tkinterdnd2
pip3 install rarfile

# Clone the repository
git clone --recursive https://github.com/sahlberg/pop-fe2.git
cd pop-fe2

wget https://archive.org/download/ps2-opl-cover-art-set/PS2_OPL_ART_kira.7z
7za x PS2_OPL_ART_kira.7z

cd PSL1GHT/tools/ps3py/
git checkout origin/use-python3
make
cd ../../..

cd make_npdata/Linux/
make
cd ../..

#
# Optional: If you want to create Software Manual
#
sudo dnf install -y wine
git clone https://github.com/BinomialLLC/crunch.git
cp crunch/bin/crunch*.exe .

```
