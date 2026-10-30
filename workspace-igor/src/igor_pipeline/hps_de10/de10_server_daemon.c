/* Compatibility launcher: old raw-DDR HAL is not a backend for Parallel8. */
#define _POSIX_C_SOURCE 200809L
#include "protocol_v2.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>

int main(int argc, char **argv) {
    char executable[PATH_MAX], script[PATH_MAX];
    ssize_t n=readlink("/proc/self/exe",executable,sizeof(executable)-1);
    if(n<0 || n>=(ssize_t)sizeof(executable)-1) {perror("readlink");return 1;}
    executable[n]='\0';
    char *slash=strrchr(executable,'/');
    if(!slash)return 1;
    *slash='\0';
    if(snprintf(script,sizeof(script),"%s/de10_udp_gateway.py",executable)>=(int)sizeof(script))return 1;
    char **arguments=calloc((size_t)argc+2,sizeof(char *));
    if(!arguments)return 1;
    arguments[0]="python3";arguments[1]=script;
    for(int i=1;i<argc;i++)arguments[i+1]=argv[i];
    execvp("python3",arguments);
    perror("exec python3 gateway");free(arguments);return 1;
}
