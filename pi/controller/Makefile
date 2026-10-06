CC = gcc
CFLAGS ?= -O2
LDLIBS = -pthread
TARGET = iot_client

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
