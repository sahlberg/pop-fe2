// some functions borrowed from:
// Sven Peter <svenpeter@gmail.com>
// Segher Boessenkool  <segher@kernel.crashing.org>
// Licensed under the terms of the GNU GPL, version 2
// http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

#ifndef TOOLS_H__
#define TOOLS_H__ 1
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "types.h"
#include "aes.h"
#include "sha1.h"

void fail(const char *a, ...);
void *mmap_file(const char *path);

void aes256cbc(u8 *key, u8 *iv, u8 *in, u64 len, u8 *out);
void aes256cbc_enc(u8 *key, u8 *iv, u8 *in, u64 len, u8 *out);
void aes128cbc(u8 *key, u8 *iv_in, u8 *in, u64 len, u8 *out);
void aes128cbc_enc(u8 *key, u8 *iv, u8 *in, u64 len, u8 *out);
void aesOmacMode1(u8* output, u8* input, int len, u8* aes_key_data, int aes_key_bits);

void sha1(u8 *data, u32 len, u8 *digest);

void get_rand(u8 *bfr, u32 size);
#endif
