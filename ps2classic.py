#!/usr/bin/env python
# coding: utf-8
#

import binascii
import hashlib
import os
import struct
import subprocess

from Crypto.Cipher import AES

PS2_DEFAULT_SEGMENT_SIZE = 0x4000
PS2_META_ENTRY_SIZE      = 0x20

ps2_key_cex_meta = bytes([0x38, 0x9D, 0xCB, 0xA5, 0x20, 0x3C, 0x81, 0x59,
                          0xEC, 0xF9, 0x4C, 0x93, 0x93, 0x16, 0x4C, 0xC9])
ps2_key_cex_data = bytes([0x10, 0x17, 0x82, 0x34, 0x63, 0xF4, 0x68, 0xC1,
                          0xAA, 0x41, 0xD7, 0x00, 0xB1, 0x40, 0xF2, 0x57])
ps2_key_cex_vmc  = bytes([0x64, 0xE3, 0x0D, 0x19, 0xA1, 0x69, 0x41, 0xD6,
                          0x77, 0xE3, 0x2E, 0xEB, 0xE0, 0x7F, 0x45, 0xD2])
ps2_key_dex_meta = bytes([0x2B, 0x05, 0xF7, 0xC7, 0xAF, 0xD1, 0xB1, 0x69,
                          0xD6, 0x25, 0x86, 0x50, 0x3A, 0xEA, 0x97, 0x98])
ps2_key_dex_data = bytes([0x74, 0xFF, 0x7E, 0x5D, 0x1D, 0x7B, 0x96, 0x94,
                          0x3B, 0xEF, 0xDC, 0xFA, 0x81, 0xFC, 0x20, 0x07])
ps2_key_dex_vmc  = bytes([0x30, 0x47, 0x9D, 0x4B, 0x80, 0xE8, 0x9E, 0x2B,
                          0x59, 0xE5, 0xC9, 0x14, 0x5E, 0x10, 0x64, 0xA9])
ps2_iv           = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
npd_omac_key2    = bytes([0x6B, 0xA5, 0x29, 0x76, 0xEF, 0xDA, 0x16, 0xEF,
                          0x3C, 0x33, 0x9F, 0xB2, 0x97, 0x1E, 0x25, 0x6B])
npd_omac_key3    = bytes([0x9B, 0x51, 0x5F, 0xEA, 0xCF, 0x75, 0x06, 0x49,
                          0x81, 0xAA, 0x60, 0x4D, 0x91, 0xA5, 0x4E, 0x97])
npd_kek          = bytes([0x72, 0xF9, 0x90, 0x78, 0x8F, 0x9C, 0xFF, 0x74,
                          0x57, 0x25, 0xF0, 0x8E, 0x4C, 0x12, 0x83, 0x87])
       

def aes_cmac(K, M):
    def xor(x, y):
        out = bytearray(x)
        for i in range(len(out)):
            out[i] ^= y[i]
        return out

    def generate_subkeys(KEY):
        def ls(data):
            out = bytearray(len(data))
            for i in range(len(data)):
                out[i] = (data[i] << 1) & 0xff
                if i > 0 and data[i] & 0x80:
                    out[i - 1] |= 0x01
            return out

        obj = AES.new(KEY, AES.MODE_ECB)
        L = obj.encrypt(bytes(16))
        K1 = ls(L)
        if L[0] & 0x80:
            K1[15] ^= 0x87
        K2 = ls(K1)
        if K1[0] & 0x80:
            K2[15] ^= 0x87
        return (K1, K2)

    K1, K2 = generate_subkeys(K)
    n = int((len(M) + 15) / 16)
    if n == 0:
        n = 1
        flag = False
    else:
        if (len(M) % 16) == 0:
            flag = True
        else:
            flag = False

    if flag:
        M_last = xor(M[(n - 1) * 16:n * 16], K1)
    else:
        _m = M[(n - 1) * 16:] + bytes([0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                       0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        _m = _m[:16]
        M_last = xor( _m[:16], K2)
    X = bytearray(16)
    for i in range(1, n):
        Y = xor(X, M[(i - 1) * 16:i * 16])
        obj = AES.new(K, AES.MODE_ECB)
        X = obj.encrypt(bytes(Y))
    Y = xor(M_last, X)
    obj = AES.new(K, AES.MODE_ECB)
    T = obj.encrypt(bytes(Y))
    return T

def encrypt_image(mode, klic, image_name, data_file, real_out_name, cid, disc_num):
    def rol1(worthless):
        xor = 0x87 if worthless[0] & 0x80 else 0

        for i in range(0x0f):
            worthless[i] = (worthless[i] << 1) & 0xff
            worthless[i] = worthless[i] | (worthless[i+1] >> 7)

        worthless[0xF] = (worthless[0xF] << 1) & 0xff
        worthless[0xF] = worthless[0xF] ^ xor
        return worthless

    def build_ps2_header(npd_type, cid, filename, iso_size):
        buffer = bytearray(segment_size)
        struct.pack_into('>I', buffer,    0, 0x50533200)                   # PS2\0
        struct.pack_into('>H', buffer, 0x04, 0x01)                         # ver major
        struct.pack_into('>H', buffer, 0x06, 0x01)                         # ver minor
        struct.pack_into('>I', buffer, 0x08, npd_type)                     # NPD Type
        struct.pack_into('>I', buffer, 0x0c, 1)                            # Type
        
        struct.pack_into('>I', buffer, 0x84, PS2_DEFAULT_SEGMENT_SIZE)     # Segment size
        struct.pack_into('>Q', buffer, 0x88, iso_size)                     # Iso size

        _b = bytes(cid, encoding='utf-8')
        buffer[0x10:0x10 + len(_b)] = _b

        npd_omac_key = bytearray(0x10);
        for i in range(0x10):
            npd_omac_key[i] = npd_kek[i] ^ npd_omac_key2[i];
        
        # qqq should be random
        test_hash = bytes([0xBF, 0x2E, 0x44, 0x15, 0x52, 0x8F, 0xD7, 0xDD, 0xDB, 0x0A, 0xC2, 0xBF, 0x8C, 0x15, 0x87, 0x51])
        buffer[0x40:0x50] = test_hash

        buf_len = 0x30 + len(real_out_name)
        buf = bytearray(buf_len)
        buf[0:0x30] = buffer[0x10:0x40]
        _b = bytes(real_out_name, encoding='utf-8')
        buf[0x30:0x30 + len(_b)] = _b

        cmac = aes_cmac(npd_omac_key3, buf)
        buffer[0x50:0x60] = cmac

        cmac = aes_cmac(bytes(npd_omac_key), buffer[:0x60])
        buffer[0x60:0x70] = cmac
        
        return buffer

    
    in_f = open(image_name, 'rb')
    out_f = open(data_file, 'wb')
    segment_size = PS2_DEFAULT_SEGMENT_SIZE
    in_f.seek(0, 2)
    data_size = in_f.tell()
    out_f.seek(0)
    in_f.seek(0)
    
    disc_num = (disc_num - 1) << 24

    with open(klic, 'rb') as f:
        klicensee = f.read()


    iv = ps2_iv
    if mode == 'cex':
        obj = AES.new(ps2_key_cex_data, AES.MODE_CBC, IV=bytes(iv))
        ps2_data_key = obj.encrypt(bytes(klicensee))
        obj = AES.new(ps2_key_cex_meta, AES.MODE_CBC, IV=bytes(iv))
        ps2_meta_key = obj.encrypt(bytes(klicensee))
    if mode == 'dex':
        obj = AES.new(ps2_key_dex_data, AES.MODE_CBC, IV=bytes(iv))
        ps2_data_key = obj.encrypt(bytes(klicensee))
        obj = AES.new(ps2_key_dex_meta, AES.MODE_CBC, IV=bytes(iv))
        ps2_meta_key = obj.encrypt(bytes(klicensee))

    ps2_header = build_ps2_header(2, cid, real_out_name, data_size)
    out_f.write(ps2_header)

    num_child_segments = 0x200
    segment_number = 0
    while True:
        data_buffer = bytearray(in_f.read(segment_size * num_child_segments))

        if not len(data_buffer):
            break;

        #last segments?
        if len(data_buffer) != segment_size * num_child_segments:
            num_child_segments = int(len(data_buffer) / segment_size)
            if len(data_buffer) % segment_size:
                num_child_segments += 1
        if len(data_buffer) != segment_size*num_child_segments:
            data_buffer = data_buffer + bytearray(segment_size*num_child_segments - len(data_buffer))
            
        meta_buffer = bytearray(segment_size)
        for i in range(num_child_segments):
            obj = AES.new(ps2_data_key, AES.MODE_CBC, IV=bytes(iv))
            _b = obj.encrypt(bytes(data_buffer[i * segment_size:(i +1 ) * segment_size]))
            data_buffer[i * segment_size:(i +1 ) * segment_size] = _b
            meta_buffer[i * PS2_META_ENTRY_SIZE:i*PS2_META_ENTRY_SIZE + 0x14] = hashlib.sha1(_b).digest()[:20]
            struct.pack_into('>I', meta_buffer, i * PS2_META_ENTRY_SIZE + 0x14, disc_num + segment_number)
            segment_number += 1

        obj = AES.new(ps2_meta_key, AES.MODE_CBC, IV=bytes(iv))
        meta_buffer = obj.encrypt(bytes(meta_buffer))
        out_f.write(meta_buffer)
        out_f.write(data_buffer)
