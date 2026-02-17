typedef struct handle handle;
handle *handle_create(const char *name);
const char *handle_name(handle *h);
int handle_close(handle *h);
