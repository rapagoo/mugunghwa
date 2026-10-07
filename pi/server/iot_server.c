/* 서울기술교육센터 AIoT */
/* author : KSH */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/time.h>
#include <time.h>
#include <errno.h>
#include <signal.h>

#define BUF_SIZE 100
#define MAX_CLNT 35
#define ID_SIZE 10
#define ARR_CNT 5

#define DEBUG
typedef struct {
		int fd;
		char *from;
		char *to;
		char *msg;
		int len;
}MSG_INFO;

typedef struct {
		int index;
		int fd;
		char ip[20];
		char id[ID_SIZE];
		char pw[ID_SIZE];
}CLIENT_INFO;

typedef struct {
	CLIENT_INFO *client;
	CLIENT_INFO *first;
	int fd;
} CONNECTION;

void * clnt_connection(void * arg);
void send_msg(MSG_INFO * msg_info, CLIENT_INFO * first_client_info);
void error_handling(char * msg);
void log_file(char * msgstr);
void getlocaltime(char * buf);
void route_line(char *line, CLIENT_INFO *client, CLIENT_INFO *first);

int clnt_cnt=0;
pthread_mutex_t mutx;

int main(int argc, char *argv[])
{
		int serv_sock, clnt_sock;
		struct sockaddr_in serv_adr, clnt_adr;
		int clnt_adr_sz;
		int sock_option  = 1;
		pthread_t t_id;
		int str_len = 0;
		int i=0;
		char idpasswd[(ID_SIZE*2)+3];
		char msg[BUF_SIZE];
/*
		CLIENT_INFO client_info[MAX_CLNT] = {{0,-1,"","1","PASSWD"}, \
				{0,-1,"","2","PASSWD"},  {0,-1,"","3","PASSWD"}, \
				{0,-1,"","4","PASSWD"},  {0,-1,"","5","PASSWD"}, \
				{0,-1,"","6","PASSWD"},  {0,-1,"","7","PASSWD"}, \
				{0,-1,"","8","PASSWD"},  {0,-1,"","9","PASSWD"}, \
				{0,-1,"","10","PASSWD"},  {0,-1,"","11","PASSWD"}, \
				{0,-1,"","12","PASSWD"},  {0,-1,"","13","PASSWD"}, \
				{0,-1,"","14","PASSWD"},  {0,-1,"","15","PASSWD"}, \
				{0,-1,"","16","PASSWD"},  {0,-1,"","17","PASSWD"}, \
				{0,-1,"","18","PASSWD"},  {0,-1,"","19","PASSWD"}, \
				{0,-1,"","20","PASSWD"},  {0,-1,"","21","PASSWD"}, \
				{0,-1,"","22","PASSWD"},  {0,-1,"","23","PASSWD"}, \
				{0,-1,"","24","PASSWD"},  {0,-1,"","25","PASSWD"}, \
				{0,-1,"","26","PASSWD"},  {0,-1,"","27","PASSWD"}, \
				{0,-1,"","28","PASSWD"},  {0,-1,"","29","PASSWD"}, \
				{0,-1,"","30","PASSWD"},  {0,-1,"","31","PASSWD"}, \
				{0,-1,"","KSH_SQL","PASSWD"}, {0,-1,"","HM_CON","PASSWD"}};
*/
		FILE * idFd = fopen("idpasswd.txt","r");
		if(idFd == NULL)
		{
			perror("fopen(\"idpasswd.txt\",\"r\") ");
			exit(1);
		}
		char id[ID_SIZE];
		char pw[ID_SIZE];
		CLIENT_INFO * client_info = calloc(MAX_CLNT, sizeof(CLIENT_INFO));
		if(client_info == NULL)
		{
			perror("calloc()");
			exit(1);
		}
		for(int n=0; n<MAX_CLNT; n++) client_info[n].fd = -1;
		do {
			str_len = fscanf(idFd,"%9s %9s",id,pw);
			if(str_len != 2)
				break;
			client_info[i].fd=-1;
			strcpy(client_info[i].id,id);
			strcpy(client_info[i].pw,pw);
			i++;
//			printf("i:%d, %s %s\n",i,client_info[i].id,client_info[i].pw);
			if(i >= MAX_CLNT)
			{
				printf("error client_info pull(Max:%d)\n",MAX_CLNT);
				break;
			}
		} while(1);
		fclose(idFd);

		if(argc != 2) {
				printf("Usage : %s <port>\n",argv[0]);
				exit(1);
		}
		fputs("IoT Server Start!!\n",stdout);

		if(pthread_mutex_init(&mutx, NULL))
				error_handling("mutex init error");

		serv_sock = socket(PF_INET, SOCK_STREAM, 0);

		memset(&serv_adr, 0, sizeof(serv_adr));
		serv_adr.sin_family=AF_INET;
		serv_adr.sin_addr.s_addr=htonl(INADDR_ANY);
		serv_adr.sin_port=htons(atoi(argv[1]));

		setsockopt(serv_sock, SOL_SOCKET, SO_REUSEADDR, (void*)&sock_option, sizeof(sock_option));
		if(bind(serv_sock, (struct sockaddr *)&serv_adr, sizeof(serv_adr))==-1)
				error_handling("bind() error");

		if(listen(serv_sock, 5) == -1)
				error_handling("listen() error");


        signal(SIGPIPE, SIG_IGN);
        while(1) {
            clnt_adr_sz = sizeof(clnt_adr);
            clnt_sock = accept(serv_sock, (struct sockaddr *)&clnt_adr, (socklen_t *)&clnt_adr_sz);
            if(clnt_sock < 0) { if(errno != EINTR) perror("accept()"); continue; }
            struct timeval timeout = {3, 0};
            setsockopt(clnt_sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
            setsockopt(clnt_sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
            size_t used = 0;
            while(used < sizeof(idpasswd)-1) {
                ssize_t n = read(clnt_sock, idpasswd+used, 1);
                if(n < 0 && errno == EINTR) continue;
                if(n != 1) break;
                if(idpasswd[used++] == ']') break;
            }
            idpasswd[used] = '\0';
            char *colon = strchr(idpasswd, ':');
            if(used < 4 || idpasswd[0] != '[' || idpasswd[used-1] != ']' || !colon) {
                close(clnt_sock); continue;
            }
            *colon = '\0'; idpasswd[used-1] = '\0';
            for(i=0; i<MAX_CLNT; i++) {
                if(*client_info[i].id && !strcmp(client_info[i].id, idpasswd+1)
                   && !strcmp(client_info[i].pw, colon+1)) break;
            }
            if(i == MAX_CLNT) {
                const char *error = "Authentication Error!\n";
                write(clnt_sock, error, strlen(error)); close(clnt_sock); continue;
            }
            timeout.tv_sec = 0;
            setsockopt(clnt_sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
            CONNECTION *connection = malloc(sizeof(*connection));
            if(!connection) { close(clnt_sock); continue; }
            connection->client = client_info+i; connection->first = client_info; connection->fd = clnt_sock;
            pthread_mutex_lock(&mutx);
            int previous = client_info[i].fd;
            /* Authenticate first; each reader owns one immutable descriptor. */
            if(previous != -1) shutdown(previous, SHUT_RDWR); else clnt_cnt++;
            client_info[i].index = i; client_info[i].fd = clnt_sock;
            strcpy(client_info[i].ip, inet_ntoa(clnt_adr.sin_addr));
            snprintf(msg, sizeof(msg), "[%s] New connected! (ip:%s,fd:%d,sockcnt:%d)\n",
                     client_info[i].id, client_info[i].ip, clnt_sock, clnt_cnt);
            log_file(msg); write(clnt_sock, msg, strlen(msg));
            int result = pthread_create(&t_id, NULL, clnt_connection, connection);
            if(result) { client_info[i].fd = -1; clnt_cnt--; close(clnt_sock); free(connection); }
            else pthread_detach(t_id);
            pthread_mutex_unlock(&mutx);
        }

		return 0;
}

void * clnt_connection(void *arg)
{

        CONNECTION *connection = arg;
        CLIENT_INFO *client_info = connection->client, *first_client_info = connection->first;
        int fd = connection->fd;
        free(connection);
        int str_len = 0;
        char msg[BUF_SIZE], line[BUF_SIZE];
        size_t used = 0;
        int dropping = 0;
        char strBuff[BUF_SIZE*2]={0};
		while(1)
		{
				memset(msg,0x0,sizeof(msg));
				str_len = read(fd, msg, sizeof(msg)-1);
				if(str_len < 0 && errno == EINTR) continue;
                if(str_len <= 0) break;

				for(int n = 0; n < str_len; n++) {
					if(msg[n] == '\r') continue;
					if(dropping) {
						if(msg[n] == '\n') dropping = 0;
						continue;
					}
					if(msg[n] == '\0' || used >= sizeof(line) - 1) {
						used = 0;
						dropping = msg[n] != '\n';
						continue;
					}
					line[used++] = msg[n];
					if(msg[n] == '\n') {
						line[used] = '\0';
						pthread_mutex_lock(&mutx);
                        if(client_info->fd == fd) route_line(line, client_info, first_client_info);
                        pthread_mutex_unlock(&mutx);
						used = 0;
					}
				}
		}


        pthread_mutex_lock(&mutx);
        if(client_info->fd == fd) { client_info->fd = -1; clnt_cnt--; }
        snprintf(strBuff, sizeof(strBuff), "Disconnect ID:%s (fd:%d,sockcnt:%d)\n",client_info->id,fd,clnt_cnt);
        log_file(strBuff); close(fd);
        pthread_mutex_unlock(&mutx);

		return 0;
}

void route_line(char *line, CLIENT_INFO *client, CLIENT_INFO *first)
{
	char *closing = strchr(line, ']');
	char outgoing[MAX_CLNT * ID_SIZE + 1];
	char logbuf[BUF_SIZE * 2];
	if(line[0] != '[' || !closing) return;
	*closing = '\0';
	char *target = line + 1;
	char *payload = closing + 1;
	if(!*target || strlen(target) >= ID_SIZE ||
	   strspn(target, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_") != strlen(target)) return;
	MSG_INFO info = {client->fd, client->id, target, outgoing, 0};
	snprintf(outgoing, sizeof(outgoing), "[%s]%s", info.from, payload);
	info.len = strlen(outgoing);
	snprintf(logbuf, sizeof(logbuf), "msg : [%s->%s] %s", info.from, info.to, payload);
	log_file(logbuf);
	send_msg(&info, first);
}

void send_msg(MSG_INFO * msg_info, CLIENT_INFO * first_client_info)
{
		int i=0;

		if(!strcmp(msg_info->to,"ALLMSG"))
		{
				for(i=0;i<MAX_CLNT;i++)
						if((first_client_info+i)->fd != -1)
								write((first_client_info+i)->fd, msg_info->msg, msg_info->len);
		}
		else if(!strcmp(msg_info->to,"IDLIST"))
		{
				char* idlist = (char *)malloc(ID_SIZE * MAX_CLNT);
				msg_info->msg[strlen(msg_info->msg) - 1] = '\0';
				strcpy(idlist,msg_info->msg);

				for(i=0;i<MAX_CLNT;i++)
				{
						if((first_client_info+i)->fd != -1)
						{
								strcat(idlist,(first_client_info+i)->id);
								strcat(idlist," ");
						}
				}
				strcat(idlist,"\n");
				write(msg_info->fd, idlist, strlen(idlist));
				free(idlist);
		}
		else if(!strcmp(msg_info->to,"GETTIME"))
		{
			sleep(1);
			getlocaltime(msg_info->msg);
			write(msg_info->fd, msg_info->msg, strlen(msg_info->msg));
		}
		else
				for(i=0;i<MAX_CLNT;i++)
						if((first_client_info+i)->fd != -1)
								if(!strcmp(msg_info->to,(first_client_info+i)->id))
										write((first_client_info+i)->fd, msg_info->msg, msg_info->len);
}

void error_handling(char *msg)
{
		fputs(msg, stderr);
		fputc('\n', stderr);
		exit(1);
}

void log_file(char * msgstr)
{
		fputs(msgstr,stdout);
}
void  getlocaltime(char * buf)
{
	struct tm *t;
	time_t tt;
	char wday[7][4] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
	tt = time(NULL);
	if(errno == EFAULT)
		perror("time()");
	t = localtime(&tt);
	sprintf(buf,"[GETTIME]%02d.%02d.%02d %02d:%02d:%02d %s",t->tm_year+1900-2000,t->tm_mon+1,t->tm_mday,t->tm_hour,t->tm_min,t->tm_sec,wday[t->tm_wday]);
	return;
}
