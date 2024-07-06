// some functions borrowed from:
// Sven Peter <svenpeter@gmail.com>
// Segher Boessenkool  <segher@kernel.crashing.org>
// Licensed under the terms of the GNU GPL, version 2
// http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

#include <sys/types.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <string.h>
#include <stdarg.h>
#include <stdlib.h>
#include <assert.h>

#ifdef WIN32
#include "mingw_mmap.h"
#include <windows.h>
#include <winioctl.h>
#include <wincrypt.h>
#include <conio.h>
#else
#include <sys/mman.h>
#endif

#include "tools.h"





void *mmap_file(const char *path)
{
	int fd;
	struct stat st;
	void *ptr;

	fd = open(path, O_RDONLY);
	if(fd == -1)
		fail("open %s", path);
	if(fstat(fd, &st) != 0)
		fail("fstat %s", path);

	ptr = mmap(0, st.st_size, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, 0);
	if(ptr==NULL)
		fail("mmap");
	close(fd);

	return ptr;
}


void fail(const char *a, ...)
{
	char msg[1024];
	va_list va;

	va_start(va, a);
	vsnprintf(msg, sizeof msg, a, va);
	fprintf(stderr, "%s\n", msg);
	perror("perror");

	exit(1);
}



void print_hash(u8 *ptr, u32 len)
{
	while(len--)
		printf(" %02x", *ptr++);
}

void aes256cbc(u8 *key, u8 *iv_in, u8 *in, u64 len, u8 *out)
{
	AES_KEY k;
	u32 i;
	u8 tmp[16];
	u8 iv[16];

	memcpy(iv, iv_in, 16);
	memset(&k, 0, sizeof k);
	AES_set_decrypt_key(key, 256, &k);

	while (len > 0) {
		memcpy(tmp, in, 16);
		AES_decrypt(in, out, &k);

		for (i = 0; i < 16; i++)
			out[i] ^= iv[i];

		memcpy(iv, tmp, 16);

		out += 16;
		in += 16;
		len -= 16;

	}
}


void aes256cbc_enc(u8 *key, u8 *iv, u8 *in, u64 len, u8 *out)
{
	AES_KEY k;
	u32 i;
	u8 tmp[16];

	memcpy(tmp, iv, 16);
	memset(&k, 0, sizeof k);
	AES_set_encrypt_key(key, 256, &k);

	while (len > 0) {
		for (i = 0; i < 16; i++)
			tmp[i] ^= *in++;

		AES_encrypt(tmp, out, &k);
		memcpy(tmp, out, 16);

		out += 16;
		len -= 16;
	}
}


void aes128cbc(u8 *key, u8 *iv_in, u8 *in, u64 len, u8 *out)
{
	AES_KEY k;
	u32 i;
	u8 tmp[16];
	u8 iv[16];

	memcpy(iv, iv_in, 16);
	memset(&k, 0, sizeof k);
	AES_set_decrypt_key(key, 128, &k);

	while (len > 0) {
		memcpy(tmp, in, 16);
		AES_decrypt(in, out, &k);

		for (i = 0; i < 16; i++)
			out[i] ^= iv[i];

		memcpy(iv, tmp, 16);

		out += 16;
		in += 16;
		len -= 16;

	}
}

void aes128cbc_enc(u8 *key, u8 *iv, u8 *in, u64 len, u8 *out)
{
	AES_KEY k;
	u32 i;
	u8 tmp[16];

	memcpy(tmp, iv, 16);
	memset(&k, 0, sizeof k);
	AES_set_encrypt_key(key, 128, &k);

	while (len > 0) {
		for (i = 0; i < 16; i++)
			tmp[i] ^= *in++;

		AES_encrypt(tmp, out, &k);
		memcpy(tmp, out, 16);

		out += 16;
		len -= 16;
	}
}

void rol1(u8* worthless) {
  int i;
  u8 xor = (worthless[0]&0x80)?0x87:0;
  for(i=0;i<0xF;i++) {
    worthless[i] <<= 1;
    worthless[i] |= worthless[i+1]>>7;
  }
  worthless[0xF] <<= 1;
  worthless[0xF] ^= xor;
}

void aesOmacMode1(u8* output, u8* input, int len, u8* aes_key_data, int aes_key_bits)
{
  int i,j;
  i = 0;
  AES_KEY aes_key;
  AES_set_encrypt_key(aes_key_data, aes_key_bits, &aes_key);

  u8 running[0x10]; memset(running, 0, 0x10);
  u8 hash[0x10];
  u8 worthless[0x10];
  u8 final[0x10];

  AES_encrypt(running, worthless, &aes_key);
  rol1(worthless);

  if(len > 0x10) {
    for(i=0;i<(len-0x10);i+=0x10) {
      for(j=0;j<0x10;j++) hash[j] = running[j] ^ input[i+j];
      AES_encrypt(hash, running, &aes_key);
    }
  }
  int overrun = len&0xF;
  if( (len%0x10) == 0 ) overrun = 0x10;

  memset(hash, 0, 0x10);
  memcpy(hash, &input[i], overrun);

  if(overrun != 0x10) {
    hash[overrun] = 0x80;
    rol1(worthless);
  }

  for(j=0;j<0x10;j++) hash[j] ^= running[j] ^ worthless[j];
  AES_encrypt(hash, output, &aes_key);
}


static void sha1_fixup(struct SHA1Context *ctx, u8 *digest)
{
	u32 i;

	for(i = 0; i < 5; i++) {
		*digest++ = ctx->Message_Digest[i] >> 24 & 0xff;
		*digest++ = ctx->Message_Digest[i] >> 16 & 0xff;
		*digest++ = ctx->Message_Digest[i] >> 8 & 0xff;
		*digest++ = ctx->Message_Digest[i] & 0xff;
	}
}

void sha1(u8 *data, u32 len, u8 *digest)
{
	struct SHA1Context ctx;

	SHA1Reset(&ctx);
	SHA1Input(&ctx, data, len);
	SHA1Result(&ctx);

	sha1_fixup(&ctx, digest);
}

#ifdef WIN32
void get_rand(u8 *bfr, u32 size)
{
	HCRYPTPROV hProv;

	if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
		fail("unable to open random");

	if (!CryptGenRandom(hProv, size, bfr))
		fail("unable to read random numbers");

	CryptReleaseContext(hProv, 0);
}
#else
void get_rand(u8 *bfr, u32 size)
{
	FILE *fp;

	fp = fopen("/dev/urandom", "r");
	if (fp == NULL)
		fail("unable to open random");

	if (fread(bfr, size, 1, fp) != 1)
		printf("unable to read /dev/urandom");

	fclose(fp);
}
#endif
