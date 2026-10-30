CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror
CPPFLAGS += -I../protocol
TARGET = de10_server_daemon

all: $(TARGET)

$(TARGET): de10_server_daemon.c ../protocol/protocol_v2.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ de10_server_daemon.c

clean:
	rm -f $(TARGET) de10_server_daemon.o de10_shared_mem_ext.o

.PHONY: all clean
