#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

const char* kProtocols[] = {
    "+rc-5", "+nec", "+rc-6", "+jvc", "+sony",
    "+rc-5-sz", "+sanyo", "+sharp", "+mce_kbd", "+xmp",
    "+imon", "+rc-mm", "+lirc"
};

int main(int argc, char** argv)
{
    if (argc != 2)
    {
        fprintf(stderr, "argument expected");
        return 1;
    }

    char buffer[128];
    sprintf(buffer, "/sys/class/rc/%s/protocols", argv[1]);

    FILE* fp = fopen(buffer, "a");
    if (!fp)
    {
        fprintf(stderr, "cannot open %s", buffer);
        return 1;
    }

    int err = 0;
    for (size_t i = 0; i < sizeof(kProtocols) / sizeof(kProtocols[0]); ++i)
    {
        size_t count = fwrite(kProtocols[i], 1, strlen(kProtocols[i]), fp);
        if (count < strlen(kProtocols[i]))
        {
            fprintf(stderr, "fail to write %s, errno: %d", kProtocols[i], errno);
            err = 1;
        }
        fflush(fp);
    }

    if (err)
        return 1;
    return 0;
}
