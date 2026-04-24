#include <stdio.h>
#include <stdlib.h>
#include <sys/sysctl.h>
#include <unistd.h>

#define STATES 5

int main(void)
{
    size_t len;

    // First: get number of CPUs
    int ncpu;
    len = sizeof(ncpu);
    if (sysctlbyname("hw.ncpu", &ncpu, &len, NULL, 0) == -1) {
        perror("hw.ncpu");
        return 1;
    }

    // Allocate arrays
    long *cp1 = malloc(ncpu * STATES * sizeof(long));
    long *cp2 = malloc(ncpu * STATES * sizeof(long));

    if (!cp1 || !cp2) {
        perror("malloc");
        return 1;
    }

    len = ncpu * STATES * sizeof(long);

    // First sample
    if (sysctlbyname("kern.cp_times", cp1, &len, NULL, 0) == -1) {
        perror("cp_times (1)");
        return 1;
    }

    usleep(333000); // your chosen interval

    // Second sample
    if (sysctlbyname("kern.cp_times", cp2, &len, NULL, 0) == -1) {
        perror("cp_times (2)");
        return 1;
    }

    // Compute delta
    for (int i = 0; i < ncpu; i++) {

        long *c1 = &cp1[i * STATES];
        long *c2 = &cp2[i * STATES];

        long total1 = c1[0] + c1[1] + c1[2] + c1[3] + c1[4];
        long total2 = c2[0] + c2[1] + c2[2] + c2[3] + c2[4];

        long idle1 = c1[4];
        long idle2 = c2[4];

        long totald = total2 - total1;
        long idled  = idle2 - idle1;

        double usage = 0.0;

        if (totald > 0) {
            usage = (double)(totald - idled) / totald * 100.0;
        }

        printf("core%d %.2f\n", i, usage);
    }

    free(cp1);
    free(cp2);

    return 0;
}