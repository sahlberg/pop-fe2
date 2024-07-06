#include "iso.h"

#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>


void *_openfile(const char *filename, int flags)
{

	if (flags & O_WRONLY)
		return fopen(filename, "wb");
	else
		return fopen(filename, "rb");
}


u64 _tellfile(void *handle)
{
	s64 cursize = ftell(handle);
	if (cursize == -1)
	{
		// try 64bit
		cursize = ftello(handle);
		if (cursize < -1)
		{
			// zero top 32 bits
			cursize &= 0xffffffff;
		}
	}
	return cursize;
}

int _seekfile(void *handle, u64 offset, int whence)
{
	int seekerr = fseeko(handle, offset, whence);

	if (seekerr == -1) printf("failed to seek\n");

	return seekerr;
}

int _readfile(void *handle, void *dst, int size)
{
	return fread(dst, 1, size, handle);
}

int _writefile(void *handle, void *src, int size)
{
	return fwrite(src, 1, size, handle);
}

void _closefile(void *handle)
{
	fclose(handle);
}


int detect(struct isoFile *iso)
{
	u8 buf[2448];
	struct cdVolDesc *volDesc;

	if (isoReadBlock(iso, buf + iso->blockofs, 16) == -1) return -1;

	volDesc = (struct cdVolDesc *)(buf + 24);

	if (strncmp((char*)volDesc->volID, "CD001", 5)) return 0;

	if (volDesc->rootToc.tocSize == 2048)
		iso->type = ISOTYPE_CD;
	else
		iso->type = ISOTYPE_DVD;

	return 1;
}

int _isoReadDtable(struct isoFile *iso)
{
	int ret;
	int i;

	_seekfile(iso->handle, 0, SEEK_END);
	iso->dtablesize = (_tellfile(iso->handle) - 16) / (iso->blocksize + 4);
	iso->dtable = (u32*)malloc(iso->dtablesize * 4);

	for (i = 0; i < iso->dtablesize; i++)
	{
		_seekfile(iso->handle, 16 + (iso->blocksize + 4)*i, SEEK_SET);
		ret = _readfile(iso->handle, &iso->dtable[i], 4);
		if (ret < 4) return -1;
	}

	return 0;
}

int isoDetect(struct isoFile *iso)   // based on florin's CDVDbin detection code :)
{
	char buf[32];
	int len;

	iso->type = ISOTYPE_ILLEGAL;

	len = strlen(iso->filename);

	_seekfile(iso->handle, 0, SEEK_SET);
	_readfile(iso->handle, buf, 4);

	if (strncmp(buf, "BDV2", 4) == 0)
	{
		iso->flags = ISOFLAGS_BLOCKDUMP;
		_readfile(iso->handle, &iso->blocksize, 4);
		_readfile(iso->handle, &iso->blocks, 4);
		_readfile(iso->handle, &iso->blockofs, 4);
		_isoReadDtable(iso);
		return detect(iso) == 1 ? 0 : -1;
	}
	else
	{
		iso->blocks = 16;
	}

	// ISO 2048
	iso->blocksize = 2048;
	iso->offset = 0;
	iso->blockofs = 24;
	if (detect(iso) == 1) return 0;

	// RAW 2336
	iso->blocksize = 2336;
	iso->offset = 0;
	iso->blockofs = 16;
	if (detect(iso) == 1) return 0;

	// RAW 2352
	iso->blocksize = 2352;
	iso->offset = 0;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	// RAWQ 2448
	iso->blocksize = 2448;
	iso->offset = 0;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	// NERO ISO 2048
	iso->blocksize = 2048;
	iso->offset = 150 * 2048;
	iso->blockofs = 24;
	if (detect(iso) == 1) return 0;

	// NERO RAW 2352
	iso->blocksize = 2352;
	iso->offset = 150 * 2048;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	// NERO RAWQ 2448
	iso->blocksize = 2448;
	iso->offset = 150 * 2048;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	// ISO 2048
	iso->blocksize = 2048;
	iso->offset = -8;
	iso->blockofs = 24;
	if (detect(iso) == 1) return 0;

	// RAW 2352
	iso->blocksize = 2352;
	iso->offset = -8;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	// RAWQ 2448
	iso->blocksize = 2448;
	iso->offset = -8;
	iso->blockofs = 0;
	if (detect(iso) == 1) return 0;

	iso->offset = 0;
	iso->blocksize = 2352;
	iso->type = ISOTYPE_AUDIO;
	return 0;

	return -1;
}

struct isoFile *isoOpen(const char *filename)
{
	struct isoFile *iso;
	int i;

	iso = (struct isoFile*)malloc(sizeof(struct isoFile));
	if (iso == NULL) return NULL;

	memset(iso, 0, sizeof(struct isoFile));
	strcpy(iso->filename, filename);

	iso->handle = _openfile(iso->filename, O_RDONLY);
	if (iso->handle == NULL)
	{
		printf("Error loading %s\n", iso->filename);
		return NULL;
	}

	if (isoDetect(iso) == -1) return NULL;

	//printf("detected blocksize = %d\n", iso->blocksize);

	if (strlen(iso->filename) > 3 && strncmp(iso->filename + (strlen(iso->filename) - 3), "I00", 3) == 0)
	{
		_closefile(iso->handle);
		iso->flags |= ISOFLAGS_MULTI;
		iso->blocks = 0;
		for (i = 0; i < 8; i++)
		{
			iso->filename[strlen(iso->filename) - 1] = '0' + i;
			iso->multih[i].handle = _openfile(iso->filename, O_RDONLY);
			if (iso->multih[i].handle == NULL)
			{
				break;
			}
			iso->multih[i].slsn = iso->blocks;
			_seekfile(iso->multih[i].handle, 0, SEEK_END);
			iso->blocks += (u32)((_tellfile(iso->multih[i].handle) - iso->offset) /
			                     (iso->blocksize));
			iso->multih[i].elsn = iso->blocks - 1;
		}

		if (i == 0)
		{
			return NULL;
		}
	}

	if (iso->flags == 0)
	{
		_seekfile(iso->handle, 0, SEEK_END);
		iso->blocks = (u32)((_tellfile(iso->handle) - iso->offset) /
		                    (iso->blocksize));
	}


	//printf("isoOpen: %s ok\n", iso->filename);
	/*printf("offset = %d\n", iso->offset);
	printf("blockofs = %d\n", iso->blockofs);
	printf("blocksize = %d\n", iso->blocksize);
	printf("blocks = %d\n", iso->blocks);*/
	//printf("type = %d\n", iso->type);

	return iso;
}

struct isoFile *isoCreate(const char *filename, int flags)
{
	struct isoFile *iso;
	char Zfile[256];

	iso = (struct isoFile*)malloc(sizeof(struct isoFile));
	if (iso == NULL) return NULL;

	memset(iso, 0, sizeof(struct isoFile));
	strcpy(iso->filename, filename);
	iso->flags = flags;
	iso->offset = 0;
	iso->blockofs = 24;
	iso->blocksize = CD_FRAMESIZE_RAW;
	iso->blocksize = 2048;

	if (iso->flags & (ISOFLAGS_Z | ISOFLAGS_Z2 | ISOFLAGS_BZ2))
	{
		sprintf(Zfile, "%s.table", iso->filename);
		iso->htable = _openfile(Zfile, O_WRONLY);
		if (iso->htable == NULL)
		{
			return NULL;
		}
	}

	iso->handle = _openfile(iso->filename, O_WRONLY | O_CREAT);
	if (iso->handle == NULL)
	{
		printf("Error loading %s\n", iso->filename);
		return NULL;
	}
	printf("isoCreate: %s ok\n", iso->filename);
	printf("offset = %d\n", iso->offset);

	return iso;
}

int  isoSetFormat(struct isoFile *iso, int blockofs, int blocksize, int blocks)
{
	iso->blocksize = blocksize;
	iso->blocks = blocks;
	iso->blockofs = blockofs;
	printf("blockofs = %d\n", iso->blockofs);
	printf("blocksize = %d\n", iso->blocksize);
	printf("blocks = %d\n", iso->blocks);
	if (iso->flags & ISOFLAGS_BLOCKDUMP)
	{
		if (_writefile(iso->handle, "BDV2", 4) < 4) return -1;
		if (_writefile(iso->handle, &blocksize, 4) < 4) return -1;
		if (_writefile(iso->handle, &blocks, 4) < 4) return -1;
		if (_writefile(iso->handle, &blockofs, 4) < 4) return -1;
	}

	return 0;
}

s32 MSFtoLSN(u8 *Time)
{
	u32 lsn;

	lsn = Time[2];
	lsn += (Time[1] - 2) * 75;
	lsn += Time[0] * 75 * 60;
	return lsn;
}

void LSNtoMSF(u8 *Time, s32 lsn)
{
	u8 m, s, f;

	lsn += 150;
	m = lsn / 4500; 		// minuten
	lsn = lsn - m * 4500;	// minuten rest
	s = lsn / 75;			// sekunden
	f = lsn - (s * 75);		// sekunden rest
	Time[0] = itob(m);
	Time[1] = itob(s);
	Time[2] = itob(f);
}

int _isoReadBlock(struct isoFile *iso, u8 *dst, int lsn)
{
	u64 ofs = (u64)lsn * iso->blocksize + iso->offset;
	u32 ret;

	memset(dst, 0, iso->blockofs);
	_seekfile(iso->handle, ofs, SEEK_SET);
	ret = _readfile(iso->handle, dst, iso->blocksize);
	if (ret < iso->blocksize)
	{
		printf("read error %d\n", ret);
		return -1;
	}

	return 0;
}

int _isoReadBlockD(struct isoFile *iso, u8 *dst, u32 lsn)
{
	u32 ret;
	int i;

//	printf("_isoReadBlockD %d, blocksize=%d, blockofs=%d\n", lsn, iso->blocksize, iso->blockofs);
	memset(dst, 0, iso->blockofs);
	for (i = 0; i < iso->dtablesize;i++)
	{
		if (iso->dtable[i] != lsn) continue;

		_seekfile(iso->handle, 16 + i*(iso->blocksize + 4) + 4, SEEK_SET);
		ret = _readfile(iso->handle, dst, iso->blocksize);
		if (ret < iso->blocksize) return -1;

		return 0;
	}
	printf("block %d not found in dump\n", lsn);

	return -1;
}

int _isoReadBlockM(struct isoFile *iso, u8 *dst, u32 lsn)
{
	u64 ofs;
	u32 ret;
	int i;

	for (i = 0; i < 8; i++)
	{
		if (lsn >= iso->multih[i].slsn &&
		        lsn <= iso->multih[i].elsn)
		{
			break;
		}
	}
	if (i == 8) return -1;

	ofs = (u64)(lsn - iso->multih[i].slsn) * iso->blocksize + iso->offset;
//	printf("_isoReadBlock %d, blocksize=%d, blockofs=%d\n", lsn, iso->blocksize, iso->blockofs);
	memset(dst, 0, iso->blockofs);
	_seekfile(iso->multih[i].handle, ofs, SEEK_SET);
	ret = _readfile(iso->multih[i].handle, dst, iso->blocksize);

	if (ret < iso->blocksize)
	{
		printf("read error %d\n", ret);
		return -1;
	}

	return 0;
}

int isoReadBlock(struct isoFile *iso, u8 *dst, u32 lsn)
{
	int ret;

	if (lsn > iso->blocks)
	{
		printf("isoReadBlock: %d > %d\n", lsn, iso->blocks);
		return -1;
	}

	if (iso->flags & ISOFLAGS_BLOCKDUMP)
		ret = _isoReadBlockD(iso, dst, lsn);
	else if (iso->flags & ISOFLAGS_MULTI)
		ret = _isoReadBlockM(iso, dst, lsn);
	else
		ret = _isoReadBlock(iso, dst, lsn);

	if (ret == -1) return ret;

	if (iso->type == ISOTYPE_CD)
	{
		LSNtoMSF(dst + 12, lsn);
		dst[15] = 2;
	}

	return 0;
}


int _isoWriteBlock(struct isoFile *iso, u8 *src, u32 lsn)
{
	u64 ofs = (u64)lsn * iso->blocksize + iso->offset;
	u32 ret;

	_seekfile(iso->handle, ofs, SEEK_SET);
	ret = _writefile(iso->handle, src, iso->blocksize);
	if (ret < iso->blocksize) return -1;

	return 0;
}

int _isoWriteBlockD(struct isoFile *iso, u8 *src, u32 lsn)
{
	u32 ret;

//	printf("_isoWriteBlock %d (ofs=%d)\n", iso->blocksize, ofs);
	ret = _writefile(iso->handle, &lsn, 4);
	if (ret < 4) return -1;
	ret = _writefile(iso->handle, src, iso->blocksize);
//	printf("_isoWriteBlock %d\n", ret);
	if (ret < iso->blocksize) return -1;

	return 0;
}

int isoWriteBlock(struct isoFile *iso, u8 *src, u32 lsn)
{
	int ret;

	if (iso->flags & ISOFLAGS_BLOCKDUMP)
		ret = _isoWriteBlockD(iso, src, lsn);
	else
		ret = _isoWriteBlock(iso, src, lsn);

	if (ret == -1) return ret;
	return 0;
}

void isoClose(struct isoFile *iso)
{
	if (iso->handle) _closefile(iso->handle);
	if (iso->htable) _closefile(iso->htable);
	if (iso->buffer) free(iso->buffer);

	free(iso);
}

void print_ps2image_info(const char *image_name)
{
	struct isoFile *iso;
	u8 * buffer;

	iso = isoOpen(image_name);

	printf("\nImage info:\n\n");

	printf("offset:\t\t %d\n", iso->offset);
	printf("blockofs:\t %d\n", iso->blockofs);
	printf("blocksize:\t %d\n", iso->blocksize);
	printf("blocks:\t\t %d\n", iso->blocks);

	if((iso->blocksize*iso->blocks) % 0x4000 == 0)
		printf("image size:\t OK\n");
	else
		printf("image size:\t NG\n");


	buffer = (u8*)malloc(iso->blocksize);
	isoReadBlock(iso, buffer, iso->blocks - 8);

	if(strncmp(buffer, "LIMG", 4) && be32(buffer+4) != 1 &&  be32(buffer+8) != ((iso->blocks) - 8 / 0x800) && be32(buffer+12) != 0x800)
		printf("LIMG block:\t NG\n");
	else
		printf("LIMG block:\t OK\n");

	isoClose(iso);
}


void prepare_iso(char image_name[])
{

	FILE * in;
	u64 data_size;
	u32 data_append;
	u64 ret;
	u8 buffer[0x4000];
	u8 header_buffer[0x10];
	char limg_header[4] = "LIMG";

	memset(buffer, 0, 0x4000);

	in = fopen(image_name, "r+b");

	printf("\nPreparing Image:\n\n");

	//get file info
	fseeko(in, 0, SEEK_END);
	data_size = ftello(in);


	//append iso
	data_append = 0x4000 - (data_size % 0x4000);

	if(data_append != 0x4000)
	{
		fwrite(buffer, data_append, 1, in);
		data_size += data_append;
		printf("\timage size:\t FIXED\n");
	}else{
		printf("\timage size:\t OK\n");
	}


	//add limg header
	fseeko(in, data_size - 0x4000, SEEK_SET);
	ret = fread(header_buffer, 0x10, 1, in);

	if(memcmp(header_buffer, limg_header, 4) && be32(header_buffer+4) != 1 &&  be32(header_buffer+8) != (data_size/0x800) && be32(header_buffer+12) != 0x800)
	{
		memcpy(buffer, limg_header, 4);
		wbe32(buffer+8, data_size/0x800);
		wbe32(buffer+12, 0x800);
		wbe32(buffer+4, 1);

		if(memcmp(header_buffer, limg_header, 4))
			fseeko(in, 0, SEEK_END);
		else
			fseeko(in, data_size - 0x4000, SEEK_SET);
		fwrite(buffer, 0x4000, 1, in);
		printf("\tLIMG sector:\t ADDED/FIXED\n");
	}else{
		printf("\tLIMG sector:\t OK\n");
	}

	fclose(in);
}
