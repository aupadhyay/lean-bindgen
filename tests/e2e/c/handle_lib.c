#include "handle_lib.h"
#include <stdlib.h>
#include <string.h>

struct handle {
    char *name;
};

handle *handle_create(const char *name) {
    handle *h = (handle *)malloc(sizeof(handle));
    h->name = strdup(name);
    return h;
}

const char *handle_name(handle *h) {
    return h->name;
}

int handle_close(handle *h) {
    free(h->name);
    free(h);
    return 0;
}
