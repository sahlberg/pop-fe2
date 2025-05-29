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
import tkinter as tk
import tkinter.ttk as ttk
from tkinterdnd2 import *


have_pytube = False
try:
    import pytubefix as pytube
    have_pytube = True
except:
    True

from PIL import Image, ImageDraw
from bchunk import bchunk
import importlib  
from gamedb import games
try:
    import popfe2
except:
    popfe2 = importlib.import_module("pop-fe2")
from cue import parse_ccd, ccd2cue, write_cue

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

class PopFe2Ps3App:
    def __init__(self, master=None):
        self.myrect = None
        self.iso = None
        self.disc_id = None
        self.icon0 = None
        self.icon0_tk = None
        self.pic0 = None
        self.pic0_tk = None
        self.pic1 = None
        self.pic1_tk = None
        self.disc = None
        self.preview_tk = None
        self.pkgdir = None
        self.subdir = 'pop-fe2-ps3-work/'
        
        self.master = master
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
        shutil.rmtree(self.subdir, ignore_errors=True)
        os.mkdir(self.subdir)

        self.iso = None
        self.disc_id = None
        self.icon0 = None
        self.icon0_tk = None
        self.pic0 = None
        self.pic0_tk = None
        self.pic1 = None
        self.pic1_tk = None
        self.disc = None
        self.preview_tk = None
        
        self.builder.get_object('discid1', self.master).config(state='normal')
        self.builder.get_object('disc1', self.master).config(filetypes=[('Image files', ['.cue', '.iso']), ('All Files', ['*.*', '*'])])
        self.builder.get_variable('disc1_variable').set('')
        self.builder.get_variable('discid1_variable').set('')
        self.builder.get_object('disc1', self.master).config(state='normal')
        self.builder.get_object('create_button', self.master).config(state='disabled')
        self.builder.get_variable('title_variable').set('')
        self.builder.get_object('snd0', self.master).config(filetypes=[('Audio files', ['.wav']), ('All Files', ['*.*', '*'])])
        self.builder.get_variable('snd0_variable').set('')

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
            p1 = self.pic1.resize((382,216), Image.Resampling.HAMMING)
            p0 = self.pic0.resize((int(p1.size[0] * 0.55) , int(p1.size[1] * 0.58)), Image.Resampling.HAMMING)
            if has_transparency(p0):
                Image.Image.paste(p1, p0, box=(148,79), mask=p0)
            else:
                Image.Image.paste(p1, p0, box=(148,79))
            if self.icon0:
                i0 = None
                _i = self.icon0.resize((124, 176), Image.Resampling.NEAREST)
                i = Image.new(self.icon0.mode, (320, 176), (0,0,0)).convert('RGBA')
                i.putalpha(0)
                ns = (98, 0)
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

    def update_assets(self, subdir = 'pop-fe2-work/'):
        if not self.disc_id:
            return
        disc_id = self.disc_id
                
        print('Fetching ICON0') if verbose else None
        self.icon0 = popfe2.get_pic_from_game('icon0', disc_id, self.iso[:-4] + '_icon0.png')
        if self.icon0:
            _i = self.icon0.resize((124, 176), Image.Resampling.NEAREST)
            i = Image.new(self.icon0.mode, (320, 176), (0,0,0)).convert('RGBA')
            i.putalpha(0)
            ns = (98, 0)
            i.paste(_i, ns)
        
            temp_files.append(self.subdir + 'ICON0.PNG')
            i.resize((80,80), Image.Resampling.HAMMING).save(self.subdir + 'ICON0.PNG')
            self.icon0_tk = tk.PhotoImage(file = self.subdir + 'ICON0.PNG')
            c = self.builder.get_object('icon0_canvas', self.master)
            c.create_image(0, 0, image=self.icon0_tk, anchor='nw')
            
        print('Fetching PIC0') if verbose else None
        self.pic0 = popfe2.get_pic_from_game('pic0', disc_id, self.iso[:-4] + '_pic0.png')
        if self.pic0:
            self.pic0 = self.pic0.resize((1000, 560), Image.Resampling.LANCZOS)
            temp_files.append(self.subdir + 'PIC0.PNG')
            self.pic0.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC0.PNG')
            self.pic0_tk = tk.PhotoImage(file = self.subdir + 'PIC0.PNG')
            c = self.builder.get_object('pic0_canvas', self.master)
            c.create_image(0, 0, image=self.pic0_tk, anchor='nw')

        
        print('Fetching PIC1') if verbose else None
        self.pic1 = popfe2.get_pic_from_game('pic1', disc_id, self.iso[:-4] + '_pic1.png')
        if self.pic1:
            self.pic1 = self.pic1.resize((1920, 1080), Image.Resampling.LANCZOS)
            temp_files.append(self.subdir + 'PIC1.PNG')
            self.pic1.resize((128,80), Image.Resampling.HAMMING).save(self.subdir + 'PIC1.PNG')
            self.pic1_tk = tk.PhotoImage(file = self.subdir + 'PIC1.PNG')
            c = self.builder.get_object('pic1_canvas', self.master)
            c.create_image(0, 0, image=self.pic1_tk, anchor='nw')

        self.update_preview()
        
    def on_path_changed(self, event):
        iso = event.widget.cget('path')
        if not len(iso):
            return

        self.master.config(cursor='watch')
        self.master.update()
        print('Processing', iso)  if verbose else None

        disc_id = popfe2.get_gameid_from_iso(iso)
        if not disc_id:
            print('Could not identify the game')
            os._exit(1)
            
        self.iso = iso
        self.disc_id = disc_id

        print('disc id', disc_id)
        print('title', games[disc_id]['title'])

        self.builder.get_variable('title_variable').set(games[disc_id]['title'])
        self.builder.get_variable('discid1_variable').set(disc_id)
        if 'snd0' in games[disc_id]:
            self.builder.get_variable('snd0_variable').set(games[disc_id]['snd0'])
        self.update_assets()
            
        self.builder.get_object('create_button', self.master).config(state='normal')
        print('Finished processing', disc_id) if verbose else None
        self.master.config(cursor='')


    def on_icon0_dropped(self, event):
        self.master.config(cursor='watch')
        self.master.update()
        # try to open it as a file
        self.icon0_tk = None
        try:
            os.stat(event.data)
            self.icon0 = Image.open(event.data)
        except:
            self.icon0 = None
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
        try:
            os.stat(event.data)
            self.pic0 = Image.open(event.data)
        except:
            self.pic0 = None
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
        try:
            os.stat(event.data)
            self.pic1 = Image.open(event.data)
        except:
            self.pic1 = None
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
        # PKG in print()

    def on_create_pkg(self):        
        pkg = self.builder.get_variable('pkgfile_variable').get()
        pkgdir = self.builder.get_variable('pkgdir_variable').get()
        if len(pkg) == 0:
            pkg = 'game.pkg'
        if len(pkgdir):
            pkg = pkgdir + '/' + pkg
            
        title = self.builder.get_variable('title_variable').get()
        print('DISC', self.disc_id)
        print('TITLE', title)

        self.master.config(cursor='watch')
        self.master.update()

        snd0 = self.builder.get_variable('snd0_variable').get()
        if snd0[:24] == 'https://www.youtube.com/':
            snd0 = popfe2.get_snd0_from_link(snd0, subdir=self.subdir)
            if snd0:
                temp_files.append(snd0)

        pkgdir = self.builder.get_variable('pkgdir_variable').get()
        pkgfile = self.builder.get_variable('pkgfile_variable').get()

        if pkgdir and len(pkgdir):
            pkgfile = pkgdir + '/' + pkgfile
                
        popfe2.create_pkg(self.iso, self.disc_id, self.icon0, self.pic0, self.pic1, snd0, pkgfile, self.subdir)
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
    
