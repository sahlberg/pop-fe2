#ifndef __LIBISO_H__
#define __LIBISO_H__

#define ISOTYPE_ILLEGAL	0
#define ISOTYPE_CD		1
#define ISOTYPE_DVD		2
#define ISOTYPE_AUDIO	3
#define ISOTYPE_DVDDL	4

#define ISOFLAGS_Z			0x0001
#define ISOFLAGS_Z2			0x0002
#define ISOFLAGS_BLOCKDUMP	0x0004
#define ISOFLAGS_MULTI		0x0008
#define ISOFLAGS_BZ2		0x0010

#define CD_FRAMESIZE_RAW	2352
#define DATA_SIZE	(CD_FRAMESIZE_RAW-12)

#define itob(i)		((i)/10*16 + (i)%10)	/* u_char to BCD */
#define btoi(b)		((b)/16*10 + (b)%16)	/* BCD to u_char */

#include "types.h"

typedef struct
{
	u32 slsn;
	u32 elsn;
	void *handle;
} _multih;

struct isoFile
{
	char filename[256];
	u32  type;
	u32  flags;
	u32  offset;
	u32  blockofs;
	u32  blocksize;
	u32  blocks;
	void *handle;
	void *htable;
	char *Ztable;
	u32  *dtable;
	int  dtablesize;
	_multih multih[8];
	int  buflsn;
	u8 *buffer;
};


struct rootDirTocHeader
{
	u16	length;			//+00
	u32 tocLBA;			//+02
	u32 tocLBA_bigend;	//+06
	u32 tocSize;		//+0A
	u32 tocSize_bigend;	//+0E
	u8	dateStamp[8];	//+12
	u8	reserved[6];	//+1A
	u8	reserved2;		//+20
	u8	reserved3;		//+21
} __attribute__((packed));


struct asciiDate
{
	char	year[4];
	char	month[2];
	char	day[2];
	char	hours[2];
	char	minutes[2];
	char	seconds[2];
	char	hundreths[2];
	char	terminator[1];
} __attribute__((packed));


struct cdVolDesc
{
	u8		filesystemType;	// 0x01 = ISO9660, 0x02 = Joliet, 0xFF = NULL
	u8		volID[5];		// "CD001"
	u8		reserved2;
	u8		reserved3;
	u8		sysIdName[32];
	u8		volName[32];	// The ISO9660 Volume Name
	u8		reserved5[8];
	u32		volSize;		// Volume Size
	u32		volSizeBig;		// Volume Size Big-Endian
	u8		reserved6[32];
	u32		unknown1;
	u32		unknown1_bigend;
	u16		volDescSize;									//+80
	u16		volDescSize_bigend;								//+82
	u32		unknown3;										//+84
	u32		unknown3_bigend;								//+88
	u32		priDirTableLBA;	// LBA of Primary Dir Table		//+8C
	u32		reserved7;										//+90
	u32		secDirTableLBA;	// LBA of Secondary Dir Table	//+94
	u32		reserved8;										//+98
	struct rootDirTocHeader	rootToc;
	s8		volSetName[128];
	s8		publisherName[128];
	s8		preparerName[128];
	s8		applicationName[128];
	s8		copyrightFileName[37];
	s8		abstractFileName[37];
	s8		bibliographyFileName[37];
	struct	asciiDate	creationDate;
	struct	asciiDate	modificationDate;
	struct	asciiDate	effectiveDate;
	struct	asciiDate	expirationDate;
	u8		reserved10;
	u8		reserved11[1166];
} __attribute__((packed));



struct isoFile *isoOpen(const char *filename);
struct isoFile *isoCreate(const char *filename, int mode);
int  isoSetFormat(struct isoFile *iso, int blockofs, int blocksize, int blocks);
int  isoDetect(struct isoFile *iso);
int  isoReadBlock(struct isoFile *iso, u8 *dst, u32 lsn);
int  isoWriteBlock(struct isoFile *iso, u8 *src, u32 lsn);
void isoClose(struct isoFile *iso);
void print_ps2image_info(const char *image_name);
void prepare_iso(char image_name[]);

void *_openfile(const char *filename, int flags);
u64 _tellfile(void *handle);
int _seekfile(void *handle, u64 offset, int whence);
int _readfile(void *handle, void *dst, int size);
int _writefile(void *handle, void *src, int size);
void _closefile(void *handle);

#endif /* __LIBISO_H__ */