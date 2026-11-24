# Settle or Report Prepared XA Transactions

WARNING: Confirm the transaction coordinator state before you commit or roll back prepared XA transactions. Wrong choices cause data inconsistency.

## Prerequisites

- Confirm `mariadb`, `my_print_defaults`, and `envsubst` exist in `PATH` on the Linux host.
- Confirm your Unix user has `unix_socket` access or valid credentials in [`xa_settle.cnf`](../../xa_settle.cnf).
- Protect [`xa_settle.cnf`](../../xa_settle.cnf) with `chmod 600` if it stores a database password.

## Procedure

### Step 1: Check Script Syntax and Pending XA Transactions

1. Print CLI options and script version without connection side effects.

```bash
./mariadb_xa_settle.sh --help
```

2. Inspect prepared XA transactions safely in read-only report mode.

```bash
./mariadb_xa_settle.sh --report
```

NOTE: `--report` executes `xa recover format='SQL'` and makes zero transaction state changes.

3. If `--report` prints `There are no XA transactions to commit or rollback.`, stop this procedure.

### Step 2: Settle Pending XA Transactions

CAUTION: Prepared XA transactions lock modified InnoDB rows. Keep `--interactive` enabled for manual review on production hosts.

1. For interactive recovery, run `--rollback_all` or `--commit_all` with `--interactive`.

```bash
./mariadb_xa_settle.sh --interactive --rollback_all
```

2. Review the XID list and count, then press `C` to execute or another key to abort.

3. For scripted recovery with controlled load, specify `--pause` with seconds between transactions.

```bash
./mariadb_xa_settle.sh --commit_all --pause 5
```

## Validation

Run `--report` after settlement completes and confirm zero open XA transactions remain:

```bash
./mariadb_xa_settle.sh --report
```

## Rollback

Once `XA COMMIT` or `XA ROLLBACK` completes, MariaDB cannot undo that transaction state. Always verify application logs and execute a database backup before non-interactive recovery.

## Related Documentation

- [CLI, Client Config & SQL Reference](../03-reference/cli-config-and-sql-templates.md)
- [XA Two-Phase Recovery Architecture](../04-explanation/xa-two-phase-recovery-architecture.md)
