# Tutorial 1: Isolated MariaDB XA Recovery Lab

In this tutorial, you configure a temporary loopback MariaDB container, create five unsettled `PREPARED` XA transactions using [`setup_test_xa_schema.sh`](../../setup_test_xa_schema.sh), inspect and settle them with [`mariadb_xa_settle.sh`](../../mariadb_xa_settle.sh), and clean up `test_xa`.

## Prerequisites

- Docker Engine (`20.10` or newer) OR local MariaDB test instance
- Local `mariadb` client, `my_print_defaults`, and `envsubst` (`gettext`)

## Step 1: Launch an Isolated Lab Container and Configure `xa_settle.cnf`

Start an ephemeral `mariadb:11` container bound strictly to `127.0.0.1`:

```bash
docker run -d --name xa-lab-mariadb --rm \
  -p 127.0.0.1:33307:3306 \
  -e MARIADB_ROOT_PASSWORD=LabXaPassword_2026 \
  mariadb:11
```

Wait until MariaDB accepts connections, then configure a temporary test `[mariadb_xa_settle]` stanza in `xa_settle.cnf` (do **not** commit credentials):

```ini
[mariadb_xa_settle]
user = root
password = "LabXaPassword_2026"
host = 127.0.0.1
port = 33307
```

Check CLI help before executing against the lab:

```bash
./mariadb_xa_settle.sh --help
```

## Step 2: Create Five Prepared XA Transactions

Run [`setup_test_xa_schema.sh`](../../setup_test_xa_schema.sh) to create schema `test_xa`, table `xa_table`, and five unsettled `XA PREPARE` transactions:

```bash
./setup_test_xa_schema.sh
```

Expected output prints `Connecting as user ...`, followed by a `PREPARED XA TRANSACTIONS, NOT YET COMMIT.` table listing `5` XIDs from `xa recover format='SQL';`.

## Step 3: Report and Settle Prepared Transactions

Run `--report` first to verify pending XIDs without modifying state:

```bash
./mariadb_xa_settle.sh --report
```

Commit all pending lab XA transactions non-interactively with a `1`-second pause:

```bash
./mariadb_xa_settle.sh --commit_all --pause 1
```

Confirm zero prepared XA transactions remain:

```bash
./mariadb_xa_settle.sh --report
```

Expected output:

```text
There are no XA transactions to commit or rollback.
```

## Step 4: Clean Up Schema and Container

Drop `test_xa`, restore `xa_settle.cnf`, and stop the container:

```bash
./cleanup_test_xa_schema.sh
git checkout -- xa_settle.cnf
docker stop xa-lab-mariadb
```

## Next Steps

- Execute production recovery procedures in [How-To: Settle or Report Prepared XA Transactions](../02-how-to-guides/settle-prepared-xa-transactions.md).
- Inspect supported flags and SQL templates in [CLI, Client Config & SQL Reference](../03-reference/cli-config-and-sql-templates.md).
