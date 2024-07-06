#!/usr/bin/env python
# coding: utf-8
#


import argparse
import struct


verbose = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='Verbose')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()

    if args.v:
        verbose = True

    print('Hello')
