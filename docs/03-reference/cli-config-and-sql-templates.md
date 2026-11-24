# CLI Options, Client Config & SQL Templates

## Script Inventory

| File | Purpose | Modifies DB |
| :--- | :--- | :--- |
| [`mariadb_xa_settle.sh`](../../mariadb_xa_settle.sh) | Report, commit, or roll back `PREPARED` XA XIDs | Only `--commit_all` / `--rollback_all` |
| [`setup_test_xa_schema.sh`](../../setup_test_xa_schema.sh) | Creates `test_xa.xa_table` and `5` prepared XA transactions | Yes (`test_xa` schema) |
| [`cleanup_test_xa_schema.sh`](../../cleanup_test_xa_schema.sh) | Deletes rows with `max_statement_time=3` and drops `test_xa` | Yes (`test_xa` schema) |
| [`vsn.sh`](../../vsn.sh) | Exports `SCRIPT_VERSION='1.0'` (must remain unmodified) | No |

## CLI Flags (`mariadb_xa_settle.sh`)

| Flag | Default / Behavior | Notes |
| :--- | :--- | :--- |
| `--report` | Read-only | Cannot combine with `--commit_all` or `--rollback_all` |
| `--commit_all` | Commits every `PREPARED` XID | Requires `envsubst`; incompatible with `--rollback_all`/`--report` |
| `--rollback_all` | Rolls back every `PREPARED` XID | Requires `envsubst`; incompatible with `--commit_all`/`--report` |
| `--interactive` | Prompt (`C` or `c` to confirm) | Displays full `xa recover format='SQL'` output before prompt |
| `--pause SECONDS` | `2` seconds | Applies between non-interactive transactions (`^[0-9]+([.][0-9]+)?$`) |
| `--help` | Prints usage + exit `0` | Does not require MariaDB client binaries |

## Client Configuration (`xa_settle.cnf`)

`my_print_defaults --defaults-file=xa_settle.cnf mariadb_xa_settle` reads standard MariaDB client keys under group `[mariadb_xa_settle]`:

| Key | Purpose |
| :--- | :--- |
| `user`, `password` | Account credentials (omit when connecting via `unix_socket`) |
| `host`, `port`, `socket` | TCP host (`3306`) or local Unix domain socket path |
| `ssl-cert`, `ssl-key`, `ssl-ca`, `ssl-verify-server-cert` | Client TLS certificate and server verification options |

## SQL Templates (`SQL/`)

| File | Substituted Variables | SQL Action |
| :--- | :--- | :--- |
| [`SQL/TEST_SETUP.sql`](../../SQL/TEST_SETUP.sql) | `$ATR1`, `$ATR2`, `$ATR3` | Creates `test_xa.xa_table` and executes `XA START`, `INSERT`, `XA END`, `XA PREPARE` |
| [`SQL/XA_COMMIT.sql`](../../SQL/XA_COMMIT.sql) | `$TRX` | Executes `xa commit $TRX;` |
| [`SQL/XA_ROLLBACK.sql`](../../SQL/XA_ROLLBACK.sql) | `$TRX` | Executes `xa rollback $TRX;` |

## Runtime Dependencies & Exit Codes

- **Required binaries:** `bash`, `mariadb` (or `mysql` fallback), `my_print_defaults`, `awk`, GNU `sed -z`, and `envsubst` (`gettext`, required when committing or rolling back).
- **Exit codes:** `0` on `--help`, `--report`, zero pending XIDs, interactive abort (`!= c/C`), or successful settlement; `1` on invalid CLI flags, missing binaries, connection error, or SQL failure.
