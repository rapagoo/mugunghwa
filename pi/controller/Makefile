CC = gcc
CFLAGS ?= -O2
LDLIBS = -pthread
TARGET = iot_client
SOURCE = iot_client.c

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(SOURCE) cycle_trial.h
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
