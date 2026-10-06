CC = gcc
CFLAGS ?= -O2
LDLIBS = -lbluetooth -pthread
TARGET = bluetooth_client

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
