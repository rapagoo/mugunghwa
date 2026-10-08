#include "../firmware/common/lcd_game_protocol.h"
#include <assert.h>
#include <string.h>
static char first[17], second[17], response[64];
static void render(const char *a,const char *b) { strcpy(first,a);strcpy(second,b); }
static void send_reply(const char *s) { strcpy(response,s); }
int main(void)
{
    assert(game_lcd_packet("[PI]COUNT@2@1@0",render,send_reply));
    assert(!strcmp(response,"[PI]APPLIED@COUNT@2@1@0\n"));
    assert(game_lcd_packet("[PI]TIME@180\n",render,send_reply));
    assert(!strcmp(first,"T:03:00 ALL:02  "));assert(!strcmp(second,"PASS:01 FAIL:00 "));
    assert(game_lcd_packet("[PI]TIME@0",render,send_reply));assert(!strcmp(first,"T:00:00 ALL:02  "));
    assert(!game_lcd_packet("[JETSON]TIME@10",render,send_reply));
    assert(!game_lcd_packet("[PI]COUNT@2@2@1",render,send_reply));
    assert(!game_lcd_packet("[PI]TIME@-1",render,send_reply));
    assert(!game_lcd_packet("[PI]TIME@3601",render,send_reply));
    assert(!game_lcd_packet("[PI]TIME@10@2",render,send_reply));
    return 0;
}
