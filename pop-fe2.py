#!/usr/bin/env python
# coding: utf-8
#


import argparse
import binascii
import os
import struct


verbose = False

def create_limg_sector(filename, sector_size):
    limg = None
    with open(filename, 'rb') as iso:
        iso.seek(-sector_size, 2)
        buf = iso.read(sector_size)
        if buf[:4] != b'LIMG':
            print('Need to create a LIMG sector') if verbose else None
            limg = bytearray(sector_size)
            limg[:4] = b'LIMG'
            struct.pack_into('>I', limg, 4, 1)
            struct.pack_into('>I', limg, 8, int(size / sector_size))
            struct.pack_into('>I', limg, 12, sector_size)
    return limg

        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='Verbose')
    parser.add_argument('file')
    args = parser.parse_args()

    if args.v:
        verbose = True


    # Check if it is a valid ISO
    size = os.stat(args.file).st_size
    print('Checking ISO file size:', size) if verbose else None
    if size % 16384:
        print('Not a valid ISO. File size is not multiple of 16kb')
        os.exit(1)
        
    # Check if we have a LIMG sector
    sector_size = 0x0800 # DVD9 sector size
    limg = create_limg_sector(args.file, sector_size)
    if limg:
        print(binascii.hexlify(limg[:16]))
