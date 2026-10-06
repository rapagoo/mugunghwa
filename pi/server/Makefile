CC = gcc
CFLAGS ?= -O2
LDLIBS = -pthread
TARGET = iot_server

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
