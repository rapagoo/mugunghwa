#include "lcd_game_protocol.h"
#include <stdio.h>
#include <string.h>

static unsigned total, passed, failed, remaining;

static bool numbers(const char *text, unsigned *values, int count, unsigned max)
{
    for(int i=0;i<count;i++) {
        unsigned value=0; int digits=0;
        while(*text>='0' && *text<='9') {
            if(++digits>4) return false;
            value=value*10+(unsigned)(*text++-'0');
            if(value>max) return false;
        }
        if(!digits) return false;
        values[i]=value;
        if(i<count-1 && *text++!='@') return false;
    }
    return !*text || !strcmp(text,"\n") || !strcmp(text,"\r\n");
}

bool game_lcd_packet(const char *packet, game_lcd_render render, game_lcd_send send)
{
    char response[64], line1[17], line2[17]; unsigned values[3];
    if(!strncmp(packet,"[PI]COUNT@",10)) {
        if(!numbers(packet+10,values,3,99) || values[1]+values[2]>values[0]) return false;
        total=values[0];passed=values[1];failed=values[2];
        snprintf(response,sizeof(response),"[PI]APPLIED@COUNT@%u@%u@%u\n",total,passed,failed);
    } else if(!strncmp(packet,"[PI]TIME@",9)) {
        if(!numbers(packet+9,values,1,3600)) return false;
        remaining=values[0];
        snprintf(response,sizeof(response),"[PI]APPLIED@TIME@%u\n",remaining);
    } else return false;
    snprintf(line1,sizeof(line1),"T:%02u:%02u ALL:%02u  ",(remaining/60)%100,remaining%60,total%100);
    snprintf(line2,sizeof(line2),"PASS:%02u FAIL:%02u ",passed%100,failed%100);
    if(render) render(line1,line2);
    if(send) send(response);
    return true;
}
