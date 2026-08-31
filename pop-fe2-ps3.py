#!/usr/bin/python3
#!/usr/bin/env python

import argparse
import datetime
import io
import os
import pathlib
import pygubu
import re
import requests
import shutil
import subprocess
import tempfile
import traceback
import tkinter as tk
import tkinter.ttk as ttk
from tkinterdnd2 import *


from PIL import Image, ImageDraw
from bchunk import bchunk
import importlib  
from gamedb import games
try:
    import popfe2
except:
    popfe2 = importlib.import_module("pop-fe2")
from cue import parse_ccd, ccd2cue, write_cue, is_abs_path, path_basename, path_dirname

verbose = False
temp_files = []

PROJECT_PATH = pathlib.Path(__file__).parent
PROJECT_UI = PROJECT_PATH / "pop-fe2-ps3.ui"


class FinishedDialog(tk.Toplevel):
    def __init__(self, root):
        tk.Toplevel.__init__(self, root)
        label = tk.Label(self, text="Finished creating PKG")
        label.pack(fill="both", expand=True, padx=20, pady=20)

        button = tk.Button(self, text="Continue", command=self.destroy)
        button.pack(side="bottom")

class MissingAssetsDialog(tk.Toplevel):
    def __init__(self, root):
        tk.Toplevel.__init__(self, root)
        label = tk.Label(self, text="Curated high-quality assets are missing for this game.\n" +
                         "Will fall back to and try finding assets in the low-resolution ART pack.\n" +
                         "Please help make pop-fe2 better by providing links to high quality icon0/pic0/pic1/snd0 for this game.\n\n" +
                         "Plese locate links to good high-quality images for this game and open an issue at\n" +
                         "\'https://github.com/sahlberg/pop-fe2\' and provide the links you want to use for this game.\n" +
                         "Then they can be added to the next release.\n")
        label.pack(fill="both", expand=True, padx=20, pady=20)

        button = tk.Button(self, text="Continue", command=self.destroy)
        button.pack(side="bottom")

class ErrorDialog(tk.Toplevel):
    def __init__(self, root, message):
        tk.Toplevel.__init__(self, root)
        self.title('pop-fe2 error')
        label = tk.Label(self, text=message, justify='left')
        label.pack(fill="both", expand=True, padx=20, pady=20)

        button = tk.Button(self, text="Continue", command=self.destroy)
        button.pack(side="bottom")


class MissingArtDialog(tk.Toplevel):
    def __init__(self, root):
        tk.Toplevel.__init__(self, root)
        label = tk.Label(self, text="No ART directory found. Please Doawnload and install\n\'https://archive.org/details/ps2-opl-cover-art-set\\'\nor else a lot of assets will be missing and your games will look ugly.")
        label.pack(fill="both", expand=True, padx=20, pady=20)

        button = tk.Button(self, text="Continue", command=self.destroy)
        button.pack(side="bottom")

class PopFe2Ps3App:
    def __init__(self, master=None):
        self.myrect = None
        self.isos = []
        self.disc_ids = []
        self.disc_media = []
        self.icon0 = None
        self.icon0_tk = None
        self.pic0 = None
        self.pic0_tk = None
        self.pic1 = None
        self.pic1_tk = None
        self.disc = None
        self.preview_tk = None
        self.pkgdir = None
        self.subdir = self.pick_work_directory()
        self.manual = None
        
        self.master = master

        # The ART pack is installed next to pop-fe2-ps3 itself.  Do not
        # look for it relative to the current directory, on windows that
        # is wherever explorer happened to start us from.
        art = popfe2.app_path('ART')
        print('Looking for the ART pack in', art)
        if not os.path.isdir(art):
            print('No ART pack found in', art)
            MissingArtDialog(self.master)
        
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        self.mainwindow = builder.get_object("top_frame", master)

        callbacks = {
            'on_icon0_clicked': self.on_icon0_clicked,
            'on_icon0_dropped': self.on_icon0_dropped,
            'on_pic0_clicked': self.on_pic0_clicked,
            'on_pic0_dropped': self.on_pic0_dropped,
            'on_pic1_clicked': self.on_pic1_clicked,
            'on_pic1_dropped': self.on_pic1_dropped,
            'on_path_changed': self.on_path_changed,
            'on_dir_changed': self.on_dir_changed,
            'on_create_pkg': self.on_create_pkg,
            'on_reset': self.on_reset,
        }

        builder.connect_callbacks(callbacks)
        c = self.builder.get_object('icon0_canvas', self.master)
        c.drop_target_register(DND_FILES)
        c.dnd_bind('<<Drop>>', self.on_icon0_dropped)
        c = self.builder.get_object('pic0_canvas', self.master)
        c.drop_target_register(DND_FILES)
        c.dnd_bind('<<Drop>>', self.on_pic0_dropped)
        c = self.builder.get_object('pic1_canvas', self.master)
        c.drop_target_register(DND_FILES)
        c.dnd_bind('<<Drop>>', self.on_pic1_dropped)

        self.init_data()

    def pick_work_directory(self):
        """Return an absolute path (with a trailing separator) to scratch space.

        We keep the work directory next to wherever we were started from,
        but that is not always writable, so fall back to the system temp
        directory if we can not create it.  Everything downstream expects
        an absolute path.  Relative paths are a trap on windows since the
        current directory is whatever explorer felt like when the user
        double-clicked us, and it can be a read-only location.
        """
        candidates = [os.path.abspath('pop-fe2-ps3-work'),
                      os.path.join(tempfile.gettempdir(), 'pop-fe2-ps3-work')]
        for d in candidates:
            try:
                os.makedirs(d, exist_ok=True)
                probe = os.path.join(d, '.writable')
                with open(probe, 'w') as f:
                    f.write('')
                os.unlink(probe)
                print('Using work directory', d)
                return d + os.sep
            except Exception as e:
                print('Can not use', d, 'as the work directory:', e)
        raise RuntimeError('Could not create a writable work directory. '
                           'Tried: %s' % ', '.join(candidates))

    def dropped_file(self, event):
        """Return the path of a file dropped onto us, or None.

        tkinterdnd2 hands us a Tcl list, not a plain path.  On windows a
        path that contains spaces, which is most of them,
        'C:/Users/me/My Pictures/cover.png', arrives wrapped in braces as
        '{C:/Users/me/My Pictures/cover.png}'.  If we just os.stat() that
        string it fails and we silently ignore the drop, which is why
        dropping an image used to do nothing at all on windows.
        Let Tcl split the list for us instead of trying to guess.
        """
        print('Dropped data:', repr(event.data))
        try:
            files = self.master.tk.splitlist(event.data)
        except Exception as e:
            print('Could not split the dropped data as a Tcl list:', e)
            files = [event.data]
        for f in files:
            f = os.path.abspath(f)
            print('Dropped file:', f)
            if os.path.isfile(f):
                return f
            print('  ... not an existing file')
        return None

    def chd_is_cd(self, chdman, chd):
        """Is this CHD a CD image (2352/2448 byte sectors) or a DVD image?

        A PS2 game can be either, and chdman needs "extractcd" for the
        former and "extractdvd" for the latter.  "chdman info" tells us
        which one we have:  CD images carry a CHT2/CHTR/CHCD track
        metadata tag, DVD images carry a 'DVD ' tag.
        """
        argv = [chdman, 'info', '-i', chd]
        print('Running', argv)
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               errors='replace')
        except Exception as e:
            print('Could not run chdman info:', e)
            return None
        info = (r.stdout or '') + (r.stderr or '')
        print(info)
        for tag in ["Tag='CHT2'", "Tag='CHTR'", "Tag='CHCD'",
                    "Tag='CHGT'", "Tag='CHGD'"]:
            if tag in info:
                print('CHD contains CD track metadata', tag, '-> CD image')
                return True
        if "Tag='DVD '" in info:
            print("CHD contains a 'DVD ' tag -> DVD image")
            return False
        print('Could not tell from "chdman info" whether this is a CD or a DVD')
        return None

    def extract_chd(self, chd):
        """Uncompress a CHD into the work directory.

        Returns the path to either an .iso (DVD based game) or a .cue
        (CD based game) in the work directory.
        """
        chdman = popfe2.find_tool('chdman')

        # path_basename() rather than split(os.sep) since the path may
        # well contain the "wrong" separator for the OS we run on.
        base = self.subdir + os.path.splitext(path_basename(chd))[0]
        iso_path = base + '.iso'
        cue_path = base + '.cue'
        bin_path = base + '.bin'
        print('CHD input   :', chd)
        print('CHD basename:', path_basename(chd))
        print('Work dir    :', self.subdir)
        print('Extract to  :', iso_path, 'or', cue_path)

        is_cd = self.chd_is_cd(chdman, chd)

        print('Extracting the disc image from the CHD.  This is going to take quite a while ...')

        if not is_cd:
            argv = [chdman, 'extractdvd', '-f', '-i', chd, '-o', iso_path]
            print('Running', argv)
            r = subprocess.run(argv)
            if r.returncode == 0:
                print('Extracted', iso_path)
                temp_files.append(iso_path)
                return iso_path
            # extractdvd only handles 2048 byte sectors, so if it failed
            # this was probably a CD image after all.
            print('chdman extractdvd failed (returncode %d).' % r.returncode)
            print('Retrying as a CD image ...')
            try:
                os.unlink(iso_path)
            except:
                True

        argv = [chdman, 'extractcd', '-f', '-i', chd, '-ob', bin_path, '-o', cue_path]
        print('Running', argv)
        r = subprocess.run(argv)
        if r.returncode != 0:
            raise RuntimeError('chdman could not extract\n%s\n'
                               'Neither "extractdvd" nor "extractcd" worked.'
                               % chd)
        print('Extracted', cue_path, 'and', bin_path)
        temp_files.append(cue_path)
        temp_files.append(bin_path)
        return cue_path

    def __del__(self):
        global temp_files
        print('Delete temporary files') if verbose else None
        for f in temp_files:
            print('Deleting temp/dir file', f) if verbose else None
            try:
                os.unlink(f)
            except:
                try:
                    os.rmdir(f)
                except:
                    True
        temp_files = []  
        
    def init_data(self):
        global temp_files
        if temp_files:
            for f in temp_files:
                try:
                    os.unlink(f)
                except:
                    try:
                        os.rmdir(f)
                    except:
                        True

        temp_files = []  
        temp_files.append(self.subdir)
        print('Resetting work directory', self.subdir)
        shutil.rmtree(self.subdir, ignore_errors=True)
        os.makedirs(self.subdir, exist_ok=True)

        self.isos = []
        self.disc_ids = []
        self.disc_media = []
        self.icon0 = None
        self.icon0_tk = None
        self.pic0 = None
        self.pic0_tk = None
        self.pic1 = None
        self.pic1_tk = None
        self.disc = None
        self.preview_tk = None
        self.manual = None
        
        self.builder.get_object('discid1', self.master).config(state='normal')
        self.builder.get_object('disc1', self.master).config(filetypes=[('Image files', ['.cue', '.iso', '.chd']), ('All Files', ['*.*', '*'])])
        self.builder.get_variable('disc1_variable').set('')
        self.builder.get_variable('discid1_variable').set('')
        self.builder.get_object('disc1', self.master).config(state='normal')

        self.builder.get_object('discid2', self.master).config(state='disabled')
        self.builder.get_object('disc2', self.master).config(filetypes=[('Image files', ['.cue', '.iso', '.chd']), ('All Files', ['*.*', '*'])])        
        self.builder.get_variable('disc2_variable').set('')
        self.builder.get_variable('discid2_variable').set('')
        self.builder.get_object('disc2', self.master).config(state='disabled')

        self.builder.get_object('discid3', self.master).config(state='disabled')
        self.builder.get_object('disc3', self.master).config(filetypes=[('Image files', ['.cue', '.iso', '.chd']), ('All Files', ['*.*', '*'])])        
        self.builder.get_variable('disc3_variable').set('')
        self.builder.get_variable('discid3_variable').set('')
        self.builder.get_object('disc3', self.master).config(state='disabled')

        self.builder.get_object('discid4', self.master).config(state='disabled')
        self.builder.get_object('disc4', self.master).config(filetypes=[('Image files', ['.cue', '.iso', '.chd']), ('All Files', ['*.*', '*'])])        
        self.builder.get_variable('disc4_variable').set('')
        self.builder.get_variable('discid4_variable').set('')
        self.builder.get_object('disc4', self.master).config(state='disabled')
        
        self.builder.get_object('create_button', self.master).config(state='disabled')
        self.builder.get_variable('title_variable').set('')
        self.builder.get_object('snd0', self.master).config(filetypes=[('Audio files', ['.wav']), ('All Files', ['*.*', '*'])])
        self.builder.get_variable('snd0_variable').set('')
        self.builder.get_object('manual', self.master).config(state='disabled')
        self.builder.get_object('manual', self.master).config(filetypes=[('All Files', ['*.*', '*'])])
        self.builder.get_variable('manual_variable').set('')

    def update_preview(self):
        def has_transparency(img):
            if img.info.get("transparency", None) is not None:
                return True
            if img.mode == "P":
                transparent = img.info.get("transparency", -1)
                for _, index in img.getcolors():
                    if index == transparent:
                        return True
            elif img.mode == "RGBA":
                extrema = img.getextrema()
                if extrema[3][0] < 255:
                    return True

                return False
        
        if self.pic0 and self.pic0.mode == 'P':
            self.pic0 = self.pic0.convert(mode='RGBA')
        c = self.builder.get_object('preview_canvas', self.master)

        if self.pic1:
            p1 = self.pic1.resize((382,216), Image.Resampling.LANCZOS)
            if self.pic0:
                disc_id = self.disc_ids[0]
                if 'pic0-scaling' in games[disc_id]:
                    sc = games[disc_id]['pic0-scaling']
                else:
                    sc = (0.6, 0.6)
                if 'pic0-offset' in games[disc_id]:
                    of = games[disc_id]['pic0-offset']
                else:
                    of = (0.30, 0.30)
                size = (int(p1.size[0] * 0.65) , int(p1.size[1] * 0.66))
                p0 = self.pic0.resize((int(size[0] * sc[0]), int(size[1] * sc[1])), Image.Resampling.LANCZOS)
                i = Image.new(p0.mode, size, (0,0,0)).convert('RGBA')
                i.putalpha(0)
                i.paste(p0, (int(size[0] * of[0]), int(size[1] * of[1])))
                if has_transparency(p0):
                    Image.Image.paste(p1, i, box=(148,79), mask=i)
                else:
                    Image.Image.paste(p1, i, box=(148,79))
            if self.icon0:
                i0 = None
                _i = self.icon0.resize((124, 176), Image.Resampling.LANCZOS)
                i = Image.new(self.icon0.mode, (220, 176), (0,0,0)).convert('RGBA')
                i.putalpha(0)
                ns = (48, 0)
                i.paste(_i, ns)
                i0 = i.resize((int(p1.size[0] * 0.10) , int(p1.size[0] * 0.10)), Image.Resampling.HAMMING)
                if has_transparency(i0):
                    Image.Image.paste(p1, i0, box=(100,79), mask=i0)
                else:
                    Image.Image.paste(p1, i0, box=(100,79))

            temp_files.append(self.subdir + 'PREVIEW.PNG')
            p1.save(self.subdir + 'PREVIEW.PNG')
            self.preview_tk = tk.PhotoImage(file = self.subdir + 'PREVIEW.PNG')
            c = self.builder.get_object('preview_canvas', self.master)
            c.create_image(0, 0, image=self.preview_tk, anchor='nw')

    def update_assets(self, subdir = 'pop-fe2-ps3-work/'):
        if not len(self.disc_ids):
            return
        disc_id = self.disc_ids[0]
                
        print('Fetching ICON0') if verbose else None
        self.icon0 = popfe2.get_pic_from_game('icon0', disc_id, self.isos[0][:-4] + '_icon0.png')
        if self.icon0:
            _i = self.icon0.resize((124, 176), Image.Resampling.NEAREST)
            i = Image.new(self.icon0.mode, (220, 176), (0,0,0)).convert('RGBA')
            i.putalpha(0)
            ns = (48, 0)
            i.paste(_i, ns)
        
            temp_files.append(self.subdir + 'ICON0.PNG')
            i.resize((80,80), Image.Resampling.HAMMING).save(self.subdir + 'ICON0.PNG')
            self.icon0_tk = tk.PhotoImage(file = self.subdir + 'ICON0.PNG')
            c = self.builder.get_object('icon0_canvas', self.master)
            c.create_image(0, 0, image=self.icon0_tk, anchor='nw')
            
        print('Fetching PIC0') if verbose else None
        self.pic0 = popfe2.get_pic_from_game('pic0', disc_id, self.isos[0][:-4] + '_pic0.png')
        if self.pic0:
            self.pic0 = self.pic0.resize((1000, 560), Image.Resampling.LANCZOS)
            temp_files.append(self.subdir + 'PIC0.PNG')
            self.pic0.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC0.PNG')
            self.pic0_tk = tk.PhotoImage(file = self.subdir + 'PIC0.PNG')
            c = self.builder.get_object('pic0_canvas', self.master)
            c.create_image(0, 0, image=self.pic0_tk, anchor='nw')

        
        print('Fetching PIC1') if verbose else None
        self.pic1 = popfe2.get_pic_from_game('pic1', disc_id, self.isos[0][:-4] + '_pic1.png')
        if self.pic1:
            self.pic1 = self.pic1.resize((1920, 1080), Image.Resampling.LANCZOS)
            temp_files.append(self.subdir + 'PIC1.PNG')
            self.pic1.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC1.PNG')
            self.pic1_tk = tk.PhotoImage(file = self.subdir + 'PIC1.PNG')
            c = self.builder.get_object('pic1_canvas', self.master)
            c.create_image(0, 0, image=self.pic1_tk, anchor='nw')

        self.update_preview()
        
    def on_path_changed(self, event):
        # tkinter swallows the traceback and leaves the UI wedged if we
        # let an exception escape a callback, so catch everything here and
        # tell the user what went wrong instead.
        try:
            self.process_disc_image(event)
        except Exception as e:
            self.master.config(cursor='')
            print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
            print('Failed to process the disc image')
            traceback.print_exc()
            print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
            try:
                event.widget.configure(path='')
            except:
                True
            d = ErrorDialog(self.master,
                            'Failed to process the disc image:\n\n%s\n\n'
                            'See the console output for more details.' % e)
            self.master.wait_window(d)

    def process_disc_image(self, event):
        raw_path = event.widget.cget('path')
        print('===== Disc image selected =====')
        print('Path from the file chooser:', repr(raw_path))
        if not len(raw_path):
            return

        # Always work with an absolute path.  The file chooser hands us
        # whatever the OS gave it, which on windows is 'C:\dir\file.chd'
        # and may use either separator.  Everything below concatenates
        # paths and hands them to external tools, and a relative path
        # would silently be resolved against the current directory,
        # which is not necessarily the directory we were installed into.
        iso = os.path.abspath(os.path.normpath(raw_path))
        print('Absolute path             :', iso)
        print('Directory part            :', path_dirname(iso))
        print('File name part            :', path_basename(iso))
        print('Current directory         :', os.getcwd())
        print('Install directory         :', popfe2.APP_DIR)
        print('Work directory            :', self.subdir)
        print('os.sep / os.name          : %r / %s' % (os.sep, os.name))

        if not os.path.isfile(iso):
            raise FileNotFoundError('No such file: %s' % iso)

        package_iso = iso
        media_type = None

        # A CHD is just a container. Unpack it first, it may turn into
        # either an ISO (DVD based game) or a CUE/BIN (CD based game)
        # and we then fall through to the handling for those below.
        if os.path.splitext(iso)[1].lower() == '.chd':
            iso = self.extract_chd(iso)
            package_iso = iso
            print('CHD extracted to          :', iso)
            event.widget.configure(path=iso)

        if os.path.splitext(iso)[1].lower() == '.cue':
            metadata_iso = self.subdir + 'ISO%02d.iso' % len(self.isos)
            print('CD image. Cooking metadata ISO to', metadata_iso)
            iso, package_iso, media_type = popfe2.prepare_cd_image(
                iso, metadata_iso)
            # prepare_cd_image() only creates the cooked metadata ISO for a
            # real raw CD image. For a cue that just wraps an ISO it hands
            # back the track file itself, which we must not delete.
            if iso == metadata_iso:
                temp_files.append(metadata_iso)
            print('Metadata ISO              :', iso)
            print('Image to package          :', package_iso)
            print('Media type                :', media_type)

        disc = event.widget.cget('title')
        print('Disc', disc)

        self.master.config(cursor='watch')
        self.master.update()
        print('Processing', iso)

        disc_id = popfe2.get_gameid_from_iso(iso)
        if not disc_id:
            self.master.config(cursor='')
            print('Could not identify the game in', iso)
            event.widget.configure(path='')
            d = ErrorDialog(self.master,
                            'Could not identify the game in\n\n%s\n\n'
                            'Is this really a PS2 disc image?' % iso)
            self.master.wait_window(d)
            return

            
        if disc == 'd1':
            self.isos.insert(0, package_iso)
            self.disc_ids.insert(0, disc_id)
            self.disc_media.insert(0, media_type)
            self.builder.get_object('disc1', self.master).config(state='disabled')
            self.builder.get_object('disc2', self.master).config(state='normal')

            print('disc id', disc_id)
            print('title', games[disc_id]['title'])
            if not 'icon0' in games[disc_id]:
                d = MissingAssetsDialog(self.master)
                self.master.wait_window(d)

            if disc_id in games and 'manual' in games[disc_id]:
                print('Found a MANUAL for', disc_id)
                self.manual = games[disc_id]['manual']
            self.builder.get_variable('manual_variable').set(self.manual)
            self.builder.get_object('manual', self.master).config(state='enabled')
            self.builder.get_variable('title_variable').set(games[disc_id]['title'])
            self.builder.get_variable('discid1_variable').set(disc_id)
            if 'snd0' in games[disc_id]:
                self.builder.get_variable('snd0_variable').set(games[disc_id]['snd0'])
            self.update_assets()
            
        if disc == 'd2':
            self.isos.insert(1, package_iso)
            self.disc_ids.insert(1, disc_id)
            self.disc_media.insert(1, media_type)
            self.builder.get_object('disc2', self.master).config(state='disabled')
            self.builder.get_object('disc3', self.master).config(state='normal')
            self.builder.get_variable('discid2_variable').set(disc_id)
            self.builder.get_object('discid2', self.master).config(state='normal')
        if disc == 'd3':
            self.isos.insert(2, package_iso)
            self.disc_ids.insert(2, disc_id)
            self.disc_media.insert(2, media_type)
            self.builder.get_object('disc3', self.master).config(state='disabled')
            self.builder.get_object('disc4', self.master).config(state='normal')
            self.builder.get_variable('discid3_variable').set(disc_id)
            self.builder.get_object('discid3', self.master).config(state='normal')
        if disc == 'd4':
            self.isos.insert(3, package_iso)
            self.disc_ids.insert(3, disc_id)
            self.disc_media.insert(3, media_type)
            self.builder.get_object('disc4', self.master).config(state='disabled')
            self.builder.get_variable('discid4_variable').set(disc_id)
            self.builder.get_object('discid4', self.master).config(state='normal')
            
        self.builder.get_object('create_button', self.master).config(state='normal')
        print('Finished processing', disc_id) if verbose else None
        self.master.config(cursor='')
            

    def on_icon0_dropped(self, event):
        self.master.config(cursor='watch')
        self.master.update()
        # try to open it as a file
        self.icon0_tk = None
        self.icon0 = None
        f = self.dropped_file(event)
        if f:
            try:
                self.icon0 = Image.open(f)
            except Exception as e:
                print('Could not open', f, 'as an image:', e)
        # if that failed, check if it was a link
        if not self.icon0:
            try:
                _s = event.data
                _p = _s.find('src="')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[_p + 5:]
                _p = _s.find('"')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[:_p]
                ret = requests.get(_s, stream=True)
                if ret.status_code != 200:
                    raise Exception('Failed to fetch file ', _s)
                self.icon0 = Image.open(io.BytesIO(ret.content))
            except:
                True

        self.master.config(cursor='')
        if not self.icon0:
            return
        temp_files.append(self.subdir + 'ICON0.PNG')
        self.icon0.resize((80,80), Image.Resampling.HAMMING).save(self.subdir + 'ICON0.PNG')
        self.icon0_tk = tk.PhotoImage(file = self.subdir + 'ICON0.PNG')
        c = self.builder.get_object('icon0_canvas', self.master)
        c.create_image(0, 0, image=self.icon0_tk, anchor='nw')
        self.update_preview()
        
    def on_icon0_clicked(self, event):
        filetypes = [
            ('Image files', ['.png', '.PNG', '.jpg', '.JPG']),
            ('All Files', ['*.*', '*'])]
        path = tk.filedialog.askopenfilename(title='Select image for COVER',filetypes=filetypes)
        try:
            os.stat(path)
            self.icon0 = Image.open(path)
        except:
            return
        temp_files.append(self.subdir + 'ICON0.PNG')
        self.icon0.resize((80,80), Image.Resampling.HAMMING).save(self.subdir + 'ICON0.PNG')
        self.icon0_tk = tk.PhotoImage(file = self.subdir + 'ICON0.PNG')
        c = self.builder.get_object('icon0_canvas', self.master)
        c.create_image(0, 0, image=self.icon0_tk, anchor='nw')
        self.update_preview()

    def on_pic0_dropped(self, event):
        self.master.config(cursor='watch')
        self.master.update()
        # try to open it as a file
        self.pic0_tk = None
        self.pic0 = None
        f = self.dropped_file(event)
        if f:
            try:
                self.pic0 = Image.open(f)
            except Exception as e:
                print('Could not open', f, 'as an image:', e)
        # if that failed, check if it was a link
        if not self.pic0:
            try:
                _s = event.data
                _p = _s.find('src="')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[_p + 5:]
                _p = _s.find('"')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[:_p]
                ret = requests.get(_s, stream=True)
                if ret.status_code != 200:
                    raise Exception('Failed to fetch file ', _s)
                self.pic0 = Image.open(io.BytesIO(ret.content))
            except:
                True

        self.master.config(cursor='')
        if not self.pic0:
            return
        temp_files.append(self.subdir + 'PIC0.PNG')
        self.pic0.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC0.PNG')
        self.pic0_tk = tk.PhotoImage(file = self.subdir + 'PIC0.PNG')
        c = self.builder.get_object('pic0_canvas', self.master)
        c.create_image(0, 0, image=self.pic0_tk, anchor='nw')
        self.update_preview()
        
    def on_pic0_clicked(self, event):
        filetypes = [
            ('Image files', ['.png', '.PNG', '.jpg', '.JPG']),
            ('All Files', ['*.*', '*'])]
        path = tk.filedialog.askopenfilename(title='Select image for PIC0',filetypes=filetypes)
        try:
            os.stat(path)
            self.pic0 = Image.open(path)
        except:
            return
        temp_files.append(self.subdir + 'PIC0.PNG')
        self.pic0.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC0.PNG')
        self.pic0_tk = tk.PhotoImage(file = self.subdir + 'PIC0.PNG')
        c = self.builder.get_object('pic0_canvas', self.master)
        c.create_image(0, 0, image=self.pic0_tk, anchor='nw')
        self.update_preview()

    def on_pic1_dropped(self, event):
        self.master.config(cursor='watch')
        self.master.update()
        # try to open it as a file
        self.pic1_tk = None
        self.pic1 = None
        f = self.dropped_file(event)
        if f:
            try:
                self.pic1 = Image.open(f)
            except Exception as e:
                print('Could not open', f, 'as an image:', e)
        # if that failed, check if it was a link
        if not self.pic1:
            try:
                _s = event.data
                _p = _s.find('src="')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[_p + 5:]
                _p = _s.find('"')
                if _p < 0:
                    raise Exception('Not a HTTP link')
                _s = _s[:_p]
                ret = requests.get(_s, stream=True)
                if ret.status_code != 200:
                    raise Exception('Failed to fetch file ', _s)
                self.pic1 = Image.open(io.BytesIO(ret.content))
            except:
                True

        self.master.config(cursor='')
        if not self.pic1:
            return
        temp_files.append(self.subdir + 'PIC1.PNG')
        self.pic1.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC1.PNG')
        self.pic1_tk = tk.PhotoImage(file = self.subdir + 'PIC1.PNG')
        c = self.builder.get_object('pic1_canvas', self.master)
        c.create_image(0, 0, image=self.pic1_tk, anchor='nw')
        self.update_preview()
        
    def on_pic1_clicked(self, event):
        filetypes = [
            ('Image files', ['.png', '.PNG', '.jpg', '.JPG']),
            ('All Files', ['*.*', '*'])]
        path = tk.filedialog.askopenfilename(title='Select image for PIC1',filetypes=filetypes)
        try:
            os.stat(path)
            self.pic1 = Image.open(path)
        except:
            return
        temp_files.append(self.subdir + 'PIC1.PNG')
        self.pic1.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC1.PNG')
        self.pic1_tk = tk.PhotoImage(file = self.subdir + 'PIC1.PNG')
        c = self.builder.get_object('pic1_canvas', self.master)
        c.create_image(0, 0, image=self.pic1_tk, anchor='nw')
        self.update_preview()
            
    def on_dir_changed(self, event):
        self.pkgdir = event.widget.cget('path')
        print('PKG output directory:', self.pkgdir)

    def on_create_pkg(self):
        try:
            self.create_pkg()
        except Exception as e:
            self.master.config(cursor='')
            print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
            print('Failed to create the PKG')
            traceback.print_exc()
            print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
            d = ErrorDialog(self.master,
                            'Failed to create the PKG:\n\n%s\n\n'
                            'See the console output for more details.' % e)
            self.master.wait_window(d)

    def create_pkg(self):
        title = self.builder.get_variable('title_variable').get()
        print('GAME', self.disc_ids[0])
        print('TITLE', title)

        self.master.config(cursor='watch')
        self.master.update()

        if self.builder.get_variable('snd0_disabled_variable').get() == 'on':
            snd0 = None
            print('Disabled SND0')
        else:
            snd0 = self.builder.get_variable('snd0_variable').get()
            if snd0[:24] == 'https://www.youtube.com/':
                snd0 = popfe2.get_snd0_from_link(snd0, subdir=self.subdir)
                if snd0:
                    temp_files.append(snd0)

        manual = self.builder.get_variable('manual_variable').get()
        if manual:
            if not len(manual) or manual == 'None':
                manual = None
        if manual and self.disc_ids[0] in games:
            games[self.disc_ids[0]]['manual'] = manual

        pkgdir = self.builder.get_variable('pkgdir_variable').get()
        pkgfile = self.builder.get_variable('pkgfile_variable').get()
        if not pkgfile or not len(pkgfile):
            pkgfile = 'game.pkg'

        # os.path.join() handles the case where pkgdir is already an
        # absolute windows path, and where it does or does not end in a
        # separator.
        if pkgdir and len(pkgdir):
            pkgfile = os.path.join(pkgdir, path_basename(pkgfile))
        pkgfile = os.path.abspath(pkgfile)
        print('PKG output directory:', pkgdir)
        print('PKG file            :', pkgfile)
        print('Work directory      :', self.subdir)
        print('Install directory   :', popfe2.APP_DIR)
        print('Current directory   :', os.getcwd())
        for _i, _f in enumerate(self.isos):
            print('Disc %d image        : %s' % (_i + 1, _f))

        popfe2.create_pkg(
            self.isos, self.disc_ids[0], self.icon0, self.pic0, self.pic1,
            snd0, pkgfile, self.subdir,
            0 if self.builder.get_variable('swap_enabled_variable').get() == 'on' else None,
            disc_gameids=self.disc_ids, disc_media=self.disc_media
        )
        self.master.config(cursor='')

        d = FinishedDialog(self.master)
        self.master.wait_window(d)
        self.init_data()

    def on_reset(self):
        self.init_data()

        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='Verbose')
    args = parser.parse_args()

    if args.v:
        verbose = True

    root = TkinterDnD.Tk()

    app = PopFe2Ps3App(root)
    root.title('pop-fe PS3')
    root.mainloop()
    
