#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static double clock_now;
static char report[2][101];
static int reports;
static double monotonic_seconds(void){return clock_now;}
#include "../pi/controller/command_status.h"
static void send_all(int sock,const char *message){(void)sock;strcpy(report[reports++%2],message);}
int main(void){
 clock_now=1;command_sent("[STM]COUNT@2@0@0\n");
 command_received("STM","APPLIED@COUNT@1@0@0");assert(command_lanes[1][0].pending);
 command_received("ARD","APPLIED@COUNT@2@0@0");assert(command_lanes[1][0].pending);
 command_received("STM","APPLIED@COUNT@2@0@0");assert(!command_lanes[1][0].pending);
 clock_now=100;command_report(0);assert(strstr(report[1],"@STM@DONE@COUNT@"));
 clock_now=101;command_sent("[STM]TIME@20\n");
 clock_now=102;command_sent("[STM]TIME@19\n");
 command_received("STM","APPLIED@TIME@20");assert(command_lanes[1][1].pending);
 clock_now=105;command_report(0);assert(strstr(report[1],"@STM@WAIT@TIME@"));
 clock_now=112;command_report(0);assert(strstr(report[1],"@STM@TIMEOUT@TIME@"));
 command_received("STM","APPLIED@TIME@19");
 clock_now=113;command_report(0);assert(strstr(report[1],"@STM@DONE@TIME@"));
 command_sent("[STM]MOTOR@REAR\n");command_received("STM","MOTOR@FRONT@OK");assert(command_lanes[1][2].pending);
 command_received("STM","MOTOR@REAR@OK");assert(!command_lanes[1][2].pending);
 puts("command status tests passed");return 0;
}
