typedef struct db_conn db_conn;
db_conn *db_open(const char *path);
int db_close(db_conn *conn);
const char *db_error(db_conn *conn);
int db_execute(db_conn *conn, const char *sql);
