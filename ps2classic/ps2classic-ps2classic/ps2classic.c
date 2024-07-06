/*+-----------------------------+*/
/*|2013 USER                    |*/
/*|decrypt algos by flatz       |*/
/*|                             |*/
/*|GPL v3,  DO NOT USE IF YOU   |*/
/*|DISAGREE TO RELEASE SRC :P   |*/
/*+-----------------------------+*/

#include "tools.h"
#include "types.h"
#include "iso.h"

#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>


// !!!---- IMPORTANT FOR FWRITE FILES > 2GB ON 32BIT SYSTEMS ----!!!
//  add 	-D"_LARGEFILE64_SOURCE"
//  and		-D"_FILE_OFFSET_BITS=64"
//  to		CFLAGS
// !!!-----------------------------------------------------------!!!

#define PS2_META_SEGMENT_START		1
#define PS2_DATA_SEGMENT_START		2
#define PS2_DEFAULT_SEGMENT_SIZE	0x4000
#define PS2_META_ENTRY_SIZE		0x20

#define PS2_VMC_ENCRYPT			1
#define PS2_VMC_DECRYPT			0

//prototypes
void ps2_encrypt_image(char mode[], char image_name[], char data_file[], char real_out_name[], char CID[]);
void ps2_decrypt_image(char mode[], char image_name[], char meta_file[], char data_file[]);
void ps2_crypt_vmc(char mode[], char vmc_path[], char vmc_out[], u8 root_key[], int crypt_mode);
static void build_ps2_header(u8 * buffer, int npd_type, char content_id[], char filename[], s64 iso_size);


//keys
u8 ps2_per_console_seed[] = { 0xD9, 0x2D, 0x65, 0xDB, 0x05, 0x7D, 0x49, 0xE1, 0xA6, 0x6F, 0x22, 0x74, 0xB8, 0xBA, 0xC5, 0x08 };

u8 ps2_key_cex_meta[] = { 0x38, 0x9D, 0xCB, 0xA5, 0x20, 0x3C, 0x81, 0x59, 0xEC, 0xF9, 0x4C, 0x93, 0x93, 0x16, 0x4C, 0xC9 };
u8 ps2_key_cex_data[] = { 0x10, 0x17, 0x82, 0x34, 0x63, 0xF4, 0x68, 0xC1, 0xAA, 0x41, 0xD7, 0x00, 0xB1, 0x40, 0xF2, 0x57 };
u8 ps2_key_cex_vmc[] = { 0x64, 0xE3, 0x0D, 0x19, 0xA1, 0x69, 0x41, 0xD6, 0x77, 0xE3, 0x2E, 0xEB, 0xE0, 0x7F, 0x45, 0xD2 };

u8 ps2_key_dex_meta[] = { 0x2B, 0x05, 0xF7, 0xC7, 0xAF, 0xD1, 0xB1, 0x69, 0xD6, 0x25, 0x86, 0x50, 0x3A, 0xEA, 0x97, 0x98 };
u8 ps2_key_dex_data[] = { 0x74, 0xFF, 0x7E, 0x5D, 0x1D, 0x7B, 0x96, 0x94, 0x3B, 0xEF, 0xDC, 0xFA, 0x81, 0xFC, 0x20, 0x07 };
u8 ps2_key_dex_vmc[] = { 0x30, 0x47, 0x9D, 0x4B, 0x80, 0xE8, 0x9E, 0x2B, 0x59, 0xE5, 0xC9, 0x14, 0x5E, 0x10, 0x64, 0xA9 };

u8 ps2_iv[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };

u8 fallback_header_hash[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01 };

u8 npd_omac_key2[] = {0x6B,0xA5,0x29,0x76,0xEF,0xDA,0x16,0xEF,0x3C,0x33,0x9F,0xB2,0x97,0x1E,0x25,0x6B};
u8 npd_omac_key3[] = {0x9B,0x51,0x5F,0xEA,0xCF,0x75,0x06,0x49,0x81,0xAA,0x60,0x4D,0x91,0xA5,0x4E,0x97};
u8 npd_kek[] = {0x72,0xF9,0x90,0x78,0x8F,0x9C,0xFF,0x74,0x57,0x25,0xF0,0x8E,0x4C,0x12,0x83,0x87};


u8 eid_root_key[0x30];
u8 * klicensee;


static void set_ps2_iv(u8 iv[])
{
	memcpy(iv, ps2_iv, 0x10);
}


static void build_ps2_header(u8 * buffer, int npd_type, char content_id[], char filename[], s64 iso_size)
{

	int i;
	u32 type = 1;
	u8 test_hash[] = { 0xBF, 0x2E, 0x44, 0x15, 0x52, 0x8F, 0xD7, 0xDD, 0xDB, 0x0A, 0xC2, 0xBF, 0x8C, 0x15, 0x87, 0x51 };

	wbe32(buffer, 0x50533200);			// PS2\0
	wbe16(buffer + 0x4, 0x1);			// ver major
	wbe16(buffer + 0x6, 0x1);			// ver minor
	wbe32(buffer + 0x8, npd_type);			// NPD type XX
	wbe32(buffer + 0xc, type);			// type

	wbe64(buffer + 0x88, iso_size); 		//iso size
	wbe32(buffer + 0x84, PS2_DEFAULT_SEGMENT_SIZE); //segment size

	strncpy(buffer + 0x10, content_id, 0x30);

	u8 npd_omac_key[0x10];

	for(i=0;i<0x10;i++) npd_omac_key[i] = npd_kek[i] ^ npd_omac_key2[i];

	get_rand(buffer + 0x40, 0x10); //npdhash1
	//memcpy(buffer + 0x40, test_hash, 0x10);

  	int buf_len = 0x30+strlen(filename);
	char *buf = (char*)malloc(buf_len+1);
	memcpy(buf, buffer + 0x10, 0x30);
	strcpy(buf+0x30, filename);
	aesOmacMode1(buffer + 0x50, buf, buf_len, npd_omac_key3, sizeof(npd_omac_key3)*8);  //npdhash2
	free(buf);
	aesOmacMode1(buffer + 0x60, (u8*)(buffer), 0x60, npd_omac_key, sizeof(npd_omac_key)*8);  //npdhash3

}


void ps2_decrypt_image(char mode[], char image_name[], char meta_file[], char data_file[])
{
	FILE * in;
	FILE * data_out;
	FILE * meta_out;

	u8 ps2_data_key[0x10];
	u8 ps2_meta_key[0x10];
	u8 iv[0x10];

	int segment_size;
	s64 data_size;
	int i;
	u8 header[256];
	u8 * data_buffer;
	u8 * meta_buffer;
	u32 read = 0;
	int num_child_segments;

	//open files
	in = fopen(image_name, "rb");
	meta_out = fopen(meta_file, "wb");
	data_out = fopen(data_file, "wb");

	//get file info
	read = fread(header, 256, 1, in);
	segment_size = be32(header + 0x84);
	data_size = be64(header + 0x88);
	num_child_segments = segment_size / PS2_META_ENTRY_SIZE;

	printf("segment size: %x\ndata_size: %llx\n\n", segment_size, data_size);

	//alloc buffers
	data_buffer = malloc(segment_size*num_child_segments);
	meta_buffer = malloc(segment_size);

	//generate keys
	if(strcmp(mode, "cex") == 0)
	{
		printf("cex\n");
		set_ps2_iv(iv);
		aes128cbc_enc(ps2_key_cex_data, iv, klicensee, 0x10, ps2_data_key);
		aes128cbc_enc(ps2_key_cex_meta, iv, klicensee, 0x10, ps2_meta_key);
	}else{
		printf("dex\n");
		set_ps2_iv(iv);
		aes128cbc_enc(ps2_key_dex_data, iv, klicensee, 0x10, ps2_data_key);
		aes128cbc_enc(ps2_key_dex_meta, iv, klicensee, 0x10, ps2_meta_key);
	}


	//decrypt iso
	fseek(in, segment_size, SEEK_SET);

	while(read = fread(meta_buffer, 1, segment_size, in))
	{
		//decrypt meta
		aes128cbc(ps2_meta_key, iv, meta_buffer, read, meta_buffer);
		fwrite(meta_buffer, read, 1, meta_out);


		read = fread(data_buffer, 1, segment_size*num_child_segments, in);
		for(i=0;i<num_child_segments;i++)
			aes128cbc(ps2_data_key, iv, data_buffer+(i*segment_size), segment_size, data_buffer+(i*segment_size));
		if(data_size >= read)
			fwrite(data_buffer, read, 1, data_out);
		else
			fwrite(data_buffer, data_size, 1, data_out);

		data_size -= read;
	}

	//cleanup
	free(data_buffer);
	free(meta_buffer);

	fclose(in);
	fclose(data_out);
	fclose(meta_out);
}


void ps2_encrypt_image(char mode[], char image_name[], char data_file[], char real_out_name[], char CID[])
{
	FILE * in;
	FILE * data_out;

	u8 ps2_data_key[0x10];
	u8 ps2_meta_key[0x10];
	u8 iv[0x10];

	u32 segment_size;
	s64 data_size;
	u32 i;
	u8 header[256];
	u8 * data_buffer;
	u8 * meta_buffer;
	u8 * ps2_header;


	u32 read = 0;
	u32 num_child_segments = 0x200;
	u32 segment_number = 0;

	//open files
	in = fopen(image_name, "rb");
	data_out = fopen(data_file, "wb");

	//get file info
	segment_size = PS2_DEFAULT_SEGMENT_SIZE;
	fseeko(in, 0, SEEK_END);
	data_size = ftello(in);
	fseeko(in, 0, SEEK_SET);

	printf("segment size: %x\ndata_size: %llx\nCID: %s\niso %s\nout file: %s\n", segment_size, data_size, CID, image_name, data_file);

	//prepare buffers
	data_buffer = malloc(segment_size * 0x200);
	meta_buffer = malloc(segment_size);
	ps2_header = malloc(segment_size);
	memset(ps2_header, 0, segment_size);

	//generate keys
	if(strcmp(mode, "cex") == 0)
	{
		printf("cex\n");
		set_ps2_iv(iv);
		aes128cbc_enc(ps2_key_cex_data, iv, klicensee, 0x10, ps2_data_key);
		aes128cbc_enc(ps2_key_cex_meta, iv, klicensee, 0x10, ps2_meta_key);
	}else{
		printf("dex\n");
		set_ps2_iv(iv);
		aes128cbc_enc(ps2_key_dex_data, iv, klicensee, 0x10, ps2_data_key);
		aes128cbc_enc(ps2_key_dex_meta, iv, klicensee, 0x10, ps2_meta_key);
	}


	//write incomplete ps2 header
	build_ps2_header(ps2_header, 2, CID, real_out_name, data_size);
	fwrite(ps2_header, segment_size, 1, data_out);


	//write encrypted image
	while(read = fread(data_buffer, 1, segment_size*num_child_segments, in))
	{
		//last segments?
		if(read != (segment_size*num_child_segments))
		{
			num_child_segments = (read / segment_size);
			if((read % segment_size) > 0)
				num_child_segments += 1;
		}

		memset(meta_buffer, 0, segment_size);

		//encrypt data and create meta
		for(i=0;i<num_child_segments;i++)
		{
			aes128cbc_enc(ps2_data_key, iv, data_buffer+(i*segment_size), segment_size, data_buffer+(i*segment_size));
			sha1(data_buffer+(i*segment_size), segment_size, meta_buffer+(i*PS2_META_ENTRY_SIZE));
			wbe32(meta_buffer+(i*PS2_META_ENTRY_SIZE)+0x14, segment_number);
			segment_number++;
		}

		//encrypt meta
		aes128cbc_enc(ps2_meta_key, iv, meta_buffer, segment_size, meta_buffer);

		//write meta and data
		fwrite(meta_buffer, segment_size, 1, data_out);
		fwrite(data_buffer, segment_size*num_child_segments, 1, data_out);

		memset(data_buffer, 0, segment_size*num_child_segments);
	}

	//finalize ps2_header
	// - wtf is between signature and first segment?

	//cleanup
	free(data_buffer);
	free(meta_buffer);
	free(ps2_header);

	fclose(in);
	fclose(data_out);
}

void ps2_crypt_vmc(char mode[], char vmc_path[], char vmc_out[], u8 root_key[], int crypt_mode)
{
	FILE * in;
	FILE * data_out;
	FILE * meta_out;

	u8 ps2_vmc_key[0x10];
	u8 iv[0x10];

	int segment_size, data_size;
	int i;
	u8 header[256];
	u8 * data_buffer;
	u8 * meta_buffer;
	u32 read = 0;

	segment_size = PS2_DEFAULT_SEGMENT_SIZE;

	//open files
	in = fopen(vmc_path, "rb");
	data_out = fopen(vmc_out, "wb");

	//alloc buffers
	data_buffer = malloc(segment_size);

	//generate keys
	if(strcmp(mode, "cex") == 0)
	{
		aes256cbc_enc(root_key, root_key+0x20, ps2_per_console_seed, 0x10, iv);
		memcpy(ps2_vmc_key, ps2_key_cex_vmc, 0x10);
	}else{
		aes256cbc_enc(root_key, root_key+0x20, ps2_per_console_seed, 0x10, iv);
		memcpy(ps2_vmc_key, ps2_key_dex_vmc, 0x10);
	}

	memset(iv+8, 0, 8);

	while(read = fread(data_buffer, 1, segment_size, in))
	{
		//decrypt or encrypt vmc
		if(crypt_mode == PS2_VMC_DECRYPT)
			aes128cbc(ps2_vmc_key, ps2_iv, data_buffer, read, data_buffer);
		else
			aes128cbc_enc(ps2_vmc_key, ps2_iv, data_buffer, read, data_buffer);
		fwrite(data_buffer, read, 1, data_out);

	}

	//cleanup
	free(data_buffer);

	fclose(in);
	fclose(data_out);

}




int main(int argc, char *argv[])
{

	u8 * root_key = NULL;

	printf("\nps2classic\nhttp://gitorious.ps3dev.net/ps2classic\nLicense: GPLv3\n\n");


	if(argc == 1)
	{
		printf("usage:\n\tiso:\n\t\t%s d [cex/dex] [klicensee] [encrypted image] [out data] [out meta]\n", argv[0]);
		printf("\t\t%s e [cex/dex] [klicensee] [iso] [out data] [real out name] [CID]\n", argv[0]);
		printf("\t\nvmc:\n\t\t%s vd [cex/dex] [vme file] [out vmc] [(eid root key)]\n", argv[0]);
		printf("\t\t%s ve [cex/dex] [vmc file] [out vme] [(eid root key)]\n", argv[0]);
		printf("\t\nimage tools:\n\t\t%s prepare [image file]\n", argv[0]);
		printf("\t\t%s info [image file]\n", argv[0]);
		exit(0);
	}

	if(argc > 6)
		klicensee = mmap_file(argv[3]);

	if(strcmp(argv[1], "d") == 0)
		if(argc == 7)
			ps2_decrypt_image(argv[2], argv[4], argv[6], argv[5]);
		else
			printf("Error: invalid number of arguments for decryption\n");
	else if(strcmp(argv[1], "e") == 0)
		if(argc == 8)
			ps2_encrypt_image(argv[2], argv[4], argv[5], argv[6], argv[7]);
		else
			printf("Error: invalid number of arguments for encryption\n");
	else if(strcmp(argv[1], "vd") == 0 || strcmp(argv[1], "ve") == 0)
	{
		if(argc == 6)
			root_key = mmap_file(argv[3]);
		else if(argc == 5){
			root_key = malloc(0x30);
			memset(root_key, 0, 0x30);
		}else{
			printf("Error: invalid number of arguments for vme processing\n");
			exit(0);
		}

		if(strcmp(argv[1], "vd") == 0)
			ps2_crypt_vmc(argv[2], argv[3], argv[4], root_key, PS2_VMC_DECRYPT);
		else
			ps2_crypt_vmc(argv[2], argv[3], argv[4], root_key, PS2_VMC_ENCRYPT);

		free(root_key);
	}
	else if(strcmp(argv[1], "prepare") == 0 && argc == 3)
	{
		prepare_iso(argv[2]);
	}
	else if(strcmp(argv[1], "info") == 0 && argc == 3)
	{
		print_ps2image_info(argv[2]);
	}
	else
		printf("FAIL: unknown option or wrong number of arguments\n");

}
