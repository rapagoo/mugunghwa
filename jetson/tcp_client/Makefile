CC = gcc
CFLAGS ?= -O2
LDLIBS = -pthread
TARGET = iot_client
SOURCE = ../../tools/tcp_client/iot_client.c

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
