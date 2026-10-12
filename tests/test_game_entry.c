/* Validate short entry without connecting to any live server. */
#include <assert.h>
#include <sys/socket.h>
static int entry_connect(int,const struct sockaddr *,socklen_t);
#define connect entry_connect
#define main controller_main
#include "../pi/controller/iot_client.c"
#undef main
#undef connect
static int expected_duration;
static int entry_connect(int fd,const struct sockaddr *address,socklen_t length){
 (void)address;(void)length;
 assert(game_enabled&&cycle_enabled&&game_audio);
 assert(game_duration==expected_duration);
 close(fd);puts("game entry validated without server connection");exit(0);
}
int main(int argc,char **argv){
 expected_duration=argc==2?atoi(argv[1]):180;
 return controller_main(argc,argv);
}
