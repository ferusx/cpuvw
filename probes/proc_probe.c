


#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/sysctl.h>
#include <sys/user.h>

int main(void)
{
    int mib[4];
    size_t len;
    struct kinfo_proc *procs;
    int count, i;

    // --------------------------------------------
    // Build MIB: kern.proc.all
    // --------------------------------------------
    mib[0] = CTL_KERN;
    mib[1] = KERN_PROC;
    mib[2] = KERN_PROC_PROC;
    mib[3] = 0;

    // --------------------------------------------
    // First call to get size
    // --------------------------------------------
    if (sysctl(mib, 4, NULL, &len, NULL, 0) == -1) {
        perror("sysctl size");
        return 1;
    }

    procs = malloc(len);
    if (!procs) {
        perror("malloc");
        return 1;
    }

    // --------------------------------------------
    // Second call to get data
    // --------------------------------------------
    if (sysctl(mib, 4, procs, &len, NULL, 0) == -1) {
        perror("sysctl data");
        free(procs);
        return 1;
    }

    count = len / sizeof(struct kinfo_proc);

    // --------------------------------------------
    // Print PID + CPU
    // --------------------------------------------
    for (i = 0; i < count; i++) {
        double cpu = procs[i].ki_pctcpu * 100.0 / FSCALE;

        if (cpu > 0.1) {
            printf("%d %.2f\n", procs[i].ki_pid, cpu);
        }
    }

    free(procs);
    return 0;
}