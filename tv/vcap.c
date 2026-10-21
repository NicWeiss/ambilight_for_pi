/*
 * vcap - streams raw BGR24 frames of the TV picture (video layer [+ OSD]) from the
 * Amlogic amlvideo2 V4L2 device to stdout. No libc, raw ARM EABI syscalls.
 *
 * usage: vcap [W H FPS TYPE [L T R EX EY]]      defaults: 160 90 20 1
 *   TYPE 0 = video only, 1 = video + OSD
 * Without L T R EX EY: writes W*H*3 bytes (BGR) per frame.
 * With them: writes (L+T+R)*3 bytes per frame - mean BGR colour of L segments on the left edge
 * (bottom to top), T on the top edge (left to right) and R on the right edge (top to bottom);
 * EX / EY are the side / top strip thickness in pixels. Always delivers the newest frame, exits when the
 * reader goes away.
 */
typedef unsigned int u32;
typedef int i32;

unsigned long long __aeabi_uidivmod(unsigned n, unsigned d) {
    unsigned q = 0, r = 0;
    for (int i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1);
        if (r >= d) { r -= d; q |= 1u << i; }
    }
    return ((unsigned long long)r << 32) | q;
}
unsigned __aeabi_uidiv(unsigned n, unsigned d) { return (unsigned)__aeabi_uidivmod(n, d); }
unsigned long long __aeabi_idivmod(int n, int d) {
    int neg = (n < 0) ^ (d < 0);
    unsigned un = n < 0 ? -n : n, ud = d < 0 ? -d : d;
    unsigned long long x = __aeabi_uidivmod(un, ud);
    int q = (int)(unsigned)x, r = (int)(x >> 32);
    if (neg) q = -q;
    if (n < 0) r = -r;
    return ((unsigned long long)(unsigned)r << 32) | (unsigned)q;
}
int __aeabi_idiv(int n, int d) { return (int)(unsigned)__aeabi_idivmod(n, d); }

static i32 sc6(i32 n, i32 a, i32 b, i32 c, i32 d, i32 e, i32 f) {
    register i32 r7 __asm__("r7") = n;
    register i32 r0 __asm__("r0") = a;
    register i32 r1 __asm__("r1") = b;
    register i32 r2 __asm__("r2") = c;
    register i32 r3 __asm__("r3") = d;
    register i32 r4 __asm__("r4") = e;
    register i32 r5 __asm__("r5") = f;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r5) : "memory");
    return r0;
}
#define sc3(n, a, b, c) sc6(n, a, b, c, 0, 0, 0)

static int g_fd = -1;
static int g_streaming = 0;

/* Перед выходом останавливаем поток, чтобы драйвер освободил канал захвата */
static void die(i32 code) {
    if (g_streaming) { i32 t = 1; sc3(54, g_fd, 0x40045613, (i32)&t); }   /* VIDIOC_STREAMOFF */
    sc3(248, code, 0, 0);
    for (;;) {}
}
static void zero(void *p, int n) { char *c = p; while (n--) *c++ = 0; }
static void copy(void *d, const void *s, int n) { char *a = d; const char *b = s; while (n--) *a++ = *b++; }
static i32 ioctl(i32 fd, u32 req, void *arg) { return sc3(54, fd, (i32)req, (i32)arg); }

struct fmt { u32 type; u32 w, h, pixfmt, field, bpl, sizeimage, cs; char pad[200 - 32]; };
struct parm { u32 type; u32 capability, capturemode, num, den, extendedmode, readbuffers; char pad[200 - 28]; };
struct reqb { u32 count, type, memory, reserved[2]; };
struct buf {
    u32 index, type, bytesused, flags, field;
    i32 ts_sec, ts_usec;
    u32 tc[4];
    u32 sequence, memory, offset, length, reserved2, reserved;
};
struct ts { i32 sec, nsec; };
struct pfd { i32 fd; short events, revents; };

#define NBUF 4
#define VIDIOC_S_INPUT 0xc0045627
#define VIDIOC_S_FMT 0xc0cc5605
#define VIDIOC_S_PARM 0xc0cc5616
#define VIDIOC_REQBUFS 0xc0145608
#define VIDIOC_QUERYBUF 0xc0445609
#define VIDIOC_QBUF 0xc044560f
#define VIDIOC_DQBUF 0xc0445611
#define VIDIOC_STREAMON 0x40045612

static i32 atoi_(const char *s, i32 dflt) {
    if (!s || !*s) return dflt;
    i32 v = 0;
    while (*s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    return v;
}

static int poll_fd(i32 fd, i32 timeout_s, i32 timeout_ns) {
    struct pfd pf; pf.fd = fd; pf.events = 1; pf.revents = 0;
    struct ts to; to.sec = timeout_s; to.nsec = timeout_ns;
    return sc6(336, (i32)&pf, 1, (i32)&to, 0, 0, 0);
}

/* 1 - кадр готов, 0 - за время ожидания кадров нет, -1 - читатель (stdout) ушёл */
static int wait_frame(i32 fd, i32 timeout_s) {
    struct pfd pf[2];
    pf[0].fd = fd; pf[0].events = 1; pf[0].revents = 0;
    pf[1].fd = 1; pf[1].events = 0; pf[1].revents = 0;
    struct ts to; to.sec = timeout_s; to.nsec = 0;
    i32 r = sc6(336, (i32)pf, 2, (i32)&to, 0, 0, 0);
    if (r < 0) return 0;
    if (pf[1].revents & (8 | 16 | 32)) return -1;   /* POLLERR | POLLHUP | POLLNVAL */
    return (pf[0].revents & 1) ? 1 : 0;
}

static int write_all(const unsigned char *p, i32 n) {
    while (n > 0) {
        i32 w = sc3(4, 1, (i32)p, n);
        if (w < 0) {
            if (w == -4) continue; /* EINTR */
            return -1;
        }
        p += w;
        n -= w;
    }
    return 0;
}


static void seg_mean(const unsigned char *img, i32 bpl, i32 x0, i32 y0, i32 x1, i32 y1, unsigned char *out3) {
    unsigned sb = 0, sg = 0, sr = 0, n = 0;
    if (x1 <= x0) x1 = x0 + 1;
    if (y1 <= y0) y1 = y0 + 1;
    for (i32 y = y0; y < y1; y++) {
        const unsigned char *p = img + y * bpl + x0 * 3;
        for (i32 x = x0; x < x1; x++, p += 3) { sb += p[0]; sg += p[1]; sr += p[2]; n++; }
    }
    out3[0] = (unsigned char)(sb / n);
    out3[1] = (unsigned char)(sg / n);
    out3[2] = (unsigned char)(sr / n);
}

static void pack_segments(const unsigned char *img, i32 bpl, i32 W, i32 H, i32 L, i32 T, i32 R, i32 EX, i32 EY,
                          unsigned char *o) {
    for (i32 k = 0; k < L; k++, o += 3)
        seg_mean(img, bpl, 0, H - (k + 1) * H / L, EX, H - k * H / L, o);
    for (i32 k = 0; k < T; k++, o += 3)
        seg_mean(img, bpl, k * W / T, 0, (k + 1) * W / T, EY, o);
    for (i32 k = 0; k < R; k++, o += 3)
        seg_mean(img, bpl, W - EX, k * H / R, W, (k + 1) * H / R, o);
}

#define MAX_SEG 256

void main_c(i32 *sp) {
    i32 argc = sp[0];
    char **argv = (char **)(sp + 1);
    i32 W = argc > 1 ? atoi_(argv[1], 160) : 160;
    i32 H = argc > 2 ? atoi_(argv[2], 90) : 90;
    i32 FPS = argc > 3 ? atoi_(argv[3], 20) : 20;
    i32 TYPE = argc > 4 ? atoi_(argv[4], 1) : 1;
    i32 SL = argc > 9 ? atoi_(argv[5], 0) : 0;
    i32 ST = argc > 9 ? atoi_(argv[6], 0) : 0;
    i32 SR = argc > 9 ? atoi_(argv[7], 0) : 0;
    i32 SEX = argc > 9 ? atoi_(argv[8], 20) : 20;
    i32 SEY = argc > 9 ? atoi_(argv[9], 20) : 20;
    i32 seg_mode = argc > 9 && SL > 0 && ST > 0 && SR > 0 && SL + ST + SR <= MAX_SEG;
    if (FPS < 1) FPS = 1;

    i32 fd = sc3(322, -100, (i32)"/dev/video12", 2);
    if (fd < 0) die(2);
    g_fd = fd;

    i32 inp = TYPE ? 0x11000001 : 0x11000000;
    if (ioctl(fd, VIDIOC_S_INPUT, &inp) < 0) die(3);

    struct fmt f; zero(&f, sizeof f);
    f.type = 1; f.w = W; f.h = H; f.pixfmt = 0x33524742; /* BGR3 */
    if (ioctl(fd, VIDIOC_S_FMT, &f) < 0) die(4);
    i32 bpl = f.bpl ? (i32)f.bpl : W * 3;

    struct parm p; zero(&p, sizeof p);
    p.type = 1; p.num = 1; p.den = FPS;
    if (ioctl(fd, VIDIOC_S_PARM, &p) < 0) die(5);

    struct reqb rb; zero(&rb, sizeof rb);
    rb.count = NBUF; rb.type = 1; rb.memory = 1;
    if (ioctl(fd, VIDIOC_REQBUFS, &rb) < 0 || rb.count < 1) die(6);

    unsigned char *mem[NBUF];
    for (u32 i = 0; i < rb.count && i < NBUF; i++) {
        struct buf b; zero(&b, sizeof b);
        b.index = i; b.type = 1; b.memory = 1;
        if (ioctl(fd, VIDIOC_QUERYBUF, &b) < 0) die(7);
        i32 m = sc6(192, 0, b.length, 3, 1, fd, b.offset >> 12);
        if (m < 0 && m > -4096) die(8);
        mem[i] = (unsigned char *)m;
        if (ioctl(fd, VIDIOC_QBUF, &b) < 0) die(9);
    }
    i32 type = 1;
    if (ioctl(fd, VIDIOC_STREAMON, &type) < 0) die(10);
    g_streaming = 1;

    i32 frame_bytes = W * H * 3;
    for (;;) {
        /* Нет кадров (например, ТВ в режиме ожидания) - просто ждём; читатель ушёл - выходим */
        i32 w = wait_frame(fd, 2);
        if (w < 0) die(0);
        if (w == 0) continue;
        struct buf b; zero(&b, sizeof b); b.type = 1; b.memory = 1;
        if (ioctl(fd, VIDIOC_DQBUF, &b) < 0) die(12);
        /* skip to the newest frame if more are already waiting */
        while (poll_fd(fd, 0, 0) > 0) {
            struct buf n; zero(&n, sizeof n); n.type = 1; n.memory = 1;
            if (ioctl(fd, VIDIOC_DQBUF, &n) < 0) break;
            ioctl(fd, VIDIOC_QBUF, &b);
            copy(&b, &n, sizeof b);
        }
        if (seg_mode) {
            unsigned char seg[MAX_SEG * 3];
            pack_segments(mem[b.index], bpl, W, H, SL, ST, SR, SEX, SEY, seg);
            ioctl(fd, VIDIOC_QBUF, &b);
            if (write_all(seg, (SL + ST + SR) * 3) < 0) die(0);
        } else {
            i32 size = b.bytesused ? (i32)b.bytesused : frame_bytes;
            if (size > frame_bytes) size = frame_bytes;
            if (write_all(mem[b.index], size) < 0) die(0);
            ioctl(fd, VIDIOC_QBUF, &b);
        }
    }
}

__attribute__((naked)) void _start(void) {
    __asm__ volatile("mov r0, sp\n\tb main_c\n");
}
