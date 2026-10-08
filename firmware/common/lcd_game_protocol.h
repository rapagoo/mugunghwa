#ifndef LCD_GAME_PROTOCOL_H
#define LCD_GAME_PROTOCOL_H
#include <stdbool.h>
/* Caller supplies LCD/UART functions; no board/pin assumptions. Lines fit 16x2. */
typedef void (*game_lcd_render)(const char *line1, const char *line2);
typedef void (*game_lcd_send)(const char *response);
bool game_lcd_packet(const char *packet, game_lcd_render render, game_lcd_send send);
#endif
