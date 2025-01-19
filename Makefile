# Root Makefile

.PHONY: all ps2classic atracdenc ps3py make_npdata clean

# Default target
all: ps2classic atracdenc ps3py make_npdata

# Build ps2classic
ps2classic:
	@echo "Building ps2classic..."
	$(MAKE) -C ps2classic/ps2classic-ps2classic

# Build atracdenc with cmake step
atracdenc:
	@echo "Configuring atracdenc with CMake..."
	cd atracdenc/src && cmake .
	@echo "Building atracdenc..."
	$(MAKE) -C atracdenc/src

# Build ps3py
ps3py:
	@echo "Building ps3py..."
	$(MAKE) -C PSL1GHT/tools/ps3py

# Build make_npdata
make_npdata:
	@echo "Building make_npdata..."
	$(MAKE) -C make_npdata/Linux

# Clean all submodules using git reset
clean:
	@echo "Cleaning all submodules..."
	$(MAKE) -C ps2classic/ps2classic-ps2classic clean 
	@cd atracdenc/src && git reset --hard && git clean -fd
	@cd PSL1GHT/tools/ps3py && git reset --hard && git clean -fd
	@cd make_npdata/Linux && git reset --hard && git clean -fd

