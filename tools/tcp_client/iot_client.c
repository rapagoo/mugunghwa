/* 서울기술 교육센터 IoT */
/* author : KSH */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <pthread.h>
#include <signal.h>
#include <errno.h>
#include <time.h>

#define BUF_SIZE 100
#define NAME_SIZE 20
#define ARR_CNT 5

void * send_msg(void * arg);
void * recv_msg(void * arg);
void error_handling(char * msg);
void lcd_demo(int sock);
void send_all(int sock, const char *data, size_t length);

char name[NAME_SIZE]="[Default]";
char msg[BUF_SIZE];
const char *demo_target = "ARD";
long demo_cycles = 0;

int main(int argc, char *argv[])
{
	int sock;
	struct sockaddr_in serv_addr;
	pthread_t snd_thread, rcv_thread;
	void * thread_return;
	int demo = 0, target_set = 0;

	if(argc < 4) {
		printf("Usage : %s <IP> <port> <name> [--lcd-demo] [--target ID] [--cycles N]\n",argv[0]);
		exit(1);
	}
	for(int i = 4; i < argc; i++) {
		if(!strcmp(argv[i], "--lcd-demo")) demo = 1;
		else if(!strcmp(argv[i], "--target") && i + 1 < argc) {
			demo_target = argv[++i];
			target_set = 1;
			if(!*demo_target || strlen(demo_target) >= NAME_SIZE ||
			   strspn(demo_target, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_") != strlen(demo_target))
				error_handling("invalid target ID");
		} else if(!strcmp(argv[i], "--cycles") && i + 1 < argc) {
			char *end;
			errno = 0;
			demo_cycles = strtol(argv[++i], &end, 10);
			if(errno || !*argv[i] || *end || demo_cycles <= 0)
				error_handling("cycles must be a positive integer");
		} else error_handling("unknown or incomplete option");
	}
	if(!demo && (demo_cycles || target_set))
		error_handling("--target and --cycles require --lcd-demo");

	if(!*argv[3] || strlen(argv[3]) >= 10 ||
	   strspn(argv[3], "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_") != strlen(argv[3]))
		error_handling("login ID must be 1-9 letters, digits or underscores");
	snprintf(name, sizeof(name), "%s",argv[3]);

	sock = socket(PF_INET, SOCK_STREAM, 0);
	if(sock == -1)
		error_handling("socket() error");

	memset(&serv_addr, 0, sizeof(serv_addr));
	serv_addr.sin_family=AF_INET;
	serv_addr.sin_addr.s_addr = inet_addr(argv[1]);
	serv_addr.sin_port = htons(atoi(argv[2]));

	if(connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) == -1)
		error_handling("connect() error");

	snprintf(msg, sizeof(msg), "[%s:PASSWD]", name);
	send_all(sock, msg, strlen(msg));
	if(demo) {
		lcd_demo(sock);
		close(sock);
		return 0;
	}
	pthread_create(&rcv_thread, NULL, recv_msg, (void *)&sock);
	pthread_create(&snd_thread, NULL, send_msg, (void *)&sock);

	pthread_join(snd_thread, &thread_return);
	//	pthread_join(rcv_thread, &thread_return);

	close(sock);
	return 0;
}

static double monotonic_seconds(void)
{
	struct timespec now;
	clock_gettime(CLOCK_MONOTONIC, &now);
	return now.tv_sec + now.tv_nsec / 1e9;
}

void send_all(int sock, const char *data, size_t length)
{
	size_t offset = 0;
	while(offset < length) {
		ssize_t n = send(sock, data + offset, length - offset, MSG_NOSIGNAL);
		if(n < 0 && errno == EINTR) continue;
		if(n <= 0) error_handling("send failed");
		offset += n;
	}
}

void lcd_demo(int sock)
{
	const int counts[][3] = {
		{1, 0, 0}, {2, 1, 0}, {3, 1, 1},
		{4, 2, 1}, {3, 1, 1}, {2, 1, 0}
	};
	char response[256];
	size_t used = 0, index = 0;
	long sent = 0;
	double next_send;

	/* Wait for the login reply before sending application messages. */
	while(used < sizeof(response) - 1) {
		ssize_t n = recv(sock, response + used, 1, 0);
		if(n < 0 && errno == EINTR) continue;
		if(n <= 0) error_handling("login reply failed");
		if(response[used++] == '\n') break;
	}
	response[used] = '\0';
	fputs(response, stdout);
	if(!strstr(response, " New connected!"))
		error_handling("login rejected");
	printf("Sending COUNT to %s every 3 seconds. Ctrl+C to stop.\n", demo_target);
	fflush(stdout);
	next_send = monotonic_seconds();
	while(1) {
		double now = monotonic_seconds();
		if(now >= next_send && demo_cycles && sent >= demo_cycles) return;
		if(now >= next_send) {
			char outgoing[BUF_SIZE];
			int len = snprintf(outgoing, sizeof(outgoing),
				"[%s]COUNT@%d@%d@%d\n", demo_target,
				counts[index][0], counts[index][1], counts[index][2]);
			if(len < 0 || (size_t)len >= sizeof(outgoing))
				error_handling("COUNT message too long");
			send_all(sock, outgoing, (size_t)len);
			printf("TX: %s", outgoing);
			fflush(stdout);
			index = (index + 1) % (sizeof(counts) / sizeof(counts[0]));
			sent++;
			next_send = monotonic_seconds() + 3.0;
		}
		fd_set readable;
		struct timeval timeout;
		double remaining = next_send - monotonic_seconds();
		if(remaining < 0) remaining = 0;
		timeout.tv_sec = (long)remaining;
		timeout.tv_usec = (long)((remaining - timeout.tv_sec) * 1e6);
		FD_ZERO(&readable);
		FD_SET(sock, &readable);
		int ret = select(sock + 1, &readable, NULL, NULL, &timeout);
		if(ret < 0 && errno == EINTR) continue;
		if(ret < 0) error_handling("select failed");
		if(ret > 0) {
			ssize_t n = recv(sock, response, sizeof(response) - 1, 0);
			if(n < 0 && errno == EINTR) continue;
			if(n <= 0) return;
			response[n] = '\0';
			fputs(response, stdout);
			fflush(stdout);
		}
	}
}

void * send_msg(void * arg)
{
	int *sock = (int *)arg;
	int str_len;
	int ret;
	fd_set initset, newset;
	struct timeval tv;
	char name_msg[NAME_SIZE + BUF_SIZE+2];

	FD_ZERO(&initset);
	FD_SET(STDIN_FILENO, &initset);

	fputs("Input a message! [ID]msg (Default ID:ALLMSG)\n",stdout);
	while(1) {
		memset(msg,0,sizeof(msg));
		name_msg[0] = '\0';
		tv.tv_sec = 1;
		tv.tv_usec = 0;
		newset = initset;
		ret = select(STDIN_FILENO + 1, &newset, NULL, NULL, &tv);
		if(FD_ISSET(STDIN_FILENO, &newset))
		{
			if(!fgets(msg, BUF_SIZE, stdin)) return NULL;
			if(!strncmp(msg,"quit\n",5)) {
				*sock = -1;
				return NULL;
			}
			else if(msg[0] != '[')
			{
				strcat(name_msg,"[ALLMSG]");
				strcat(name_msg,msg);
			}
			else
				strcpy(name_msg,msg);
			if(write(*sock, name_msg, strlen(name_msg))<=0)
			{
				*sock = -1;
				return NULL;
			}
		}
		if(ret == 0) 
		{
			if(*sock == -1) 
				return NULL;
		}
	}
}

void * recv_msg(void * arg)
{
	int * sock = (int *)arg;	
	int i;
	char *pToken;
	char *pArray[ARR_CNT]={0};

	char name_msg[NAME_SIZE + BUF_SIZE +1];
	int str_len;
	while(1) {
		memset(name_msg,0x0,sizeof(name_msg));
		str_len = read(*sock, name_msg, NAME_SIZE + BUF_SIZE );
		if(str_len <= 0) 
		{
			*sock = -1;
			return NULL;
		}
		name_msg[str_len] = 0;
		fputs(name_msg, stdout);

		/*   	pToken = strtok(name_msg,"[:]");
			i = 0;
			while(pToken != NULL)
			{
			pArray[i] =  pToken;
			if(i++ >= ARR_CNT)
			break;
			pToken = strtok(NULL,"[:]");
			}

		//		printf("id:%s, msg:%s,%s,%s,%s\n",pArray[0],pArray[1],pArray[2],pArray[3],pArray[4]);
		printf("id:%s, msg:%s\n",pArray[0],pArray[1]);
		*/
	}
}

void error_handling(char * msg)
{
	fputs(msg, stderr);
	fputc('\n', stderr);
	exit(1);
}
