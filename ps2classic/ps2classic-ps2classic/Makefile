TOOLS	=	ps2classic
COMMON	=	tools.o aes.o sha1.o iso.o mingw_mmap.o
DEPS	=	Makefile tools.h types.h

CC	=	gcc
CFLAGS	=	-g -O3 -W -D"_LARGEFILE64_SOURCE" -D"_FILE_OFFSET_BITS=64" -D"__MSVCRT__" -D"__USE_MINGW_FSEEK"
LDFLAGS =	

OBJS	= $(COMMON) $(addsuffix .o, $(TOOLS))

all: $(TOOLS)

$(TOOLS): %: %.o $(COMMON) $(DEPS)
	$(CC) $(CFLAGS) -o $@ $< $(COMMON) $(LDFLAGS)

$(OBJS): %.o: %.c $(DEPS)
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	-rm -f $(OBJS) $(TOOLS)
