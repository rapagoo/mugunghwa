CC = gcc
CFLAGS ?= -O2
LDLIBS = -pthread -lm
TARGET = iot_client
SOURCE = iot_client.c

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(SOURCE) cycle_trial.h game_state.h
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
