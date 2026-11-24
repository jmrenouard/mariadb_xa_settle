#!/usr/bin/env bash
# mariadb_xa_settle.sh
# file distributed with mariadb_xa_settle
# By Edward Stoever for MariaDB Support

# Establish working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# shellcheck source=vsn.sh
source "${SCRIPT_DIR}/vsn.sh"

TEMPDIR="/tmp"
CONFIG_FILE="$SCRIPT_DIR/xa_settle.cnf"
SQL_DIR="$SCRIPT_DIR/SQL"
TOOL="mariadb_xa_settle"
COMMIT_SQL_FILE=$SQL_DIR/XA_COMMIT.sql
ROLLBACK_SQL_FILE=$SQL_DIR/XA_ROLLBACK.sql

# Default pause time between transactions
PAUSE_TIME=2

function display_help_message() {
printf "SETTLE PREPARED XA TRANSACTIONS.
Script version $SCRIPT_VERSION
The following options are available.
   --interactive    # run as a human-interactive script.
   --report         # displays a report of prepared transactions not yet commit or rollback
   --commit_all     # commit all prepared XA transactions
   --rollback_all   # rollback all prepared XA transactions
   --pause [seconds] # set pause time between each transaction (default is 2 seconds)
   --help           # Display the help menu
Read the file README.md for more information.\n"
}

function ts() {
   TS=$(date +%F-%T | tr ':-' '_')
   echo "$TS $*"
}

function die() {
   ts "$*" >&2
   exit 1
}

function _which() {
   if [ -x /usr/bin/which ]; then
      /usr/bin/which "$1" 2>/dev/null | awk '{print $1}'
   elif which which 1>/dev/null 2>&1; then
      which "$1" 2>/dev/null | awk '{print $1}'
   else
      echo "$1"
   fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --commit_all)
      COMMIT='TRUE'
      shift
      ;;
    --report)
      REPORT='TRUE'
      shift
      ;;
    --rollback_all)
      ROLLBACK='TRUE'
      shift
      ;;
    --interactive)
      INTERACTIVE='TRUE'
      shift
      ;;
    --pause)
      if [ $# -lt 2 ] || [[ ! "$2" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        display_help_message
        die "Option --pause requires a non-negative numeric argument (seconds)."
      fi
      PAUSE_TIME="$2"
      shift 2
      ;;
    --help)
      HELP='TRUE'
      shift
      ;;
    *)
      INVALID_INPUT="$1"
      break
      ;;
  esac
done

if [ -n "${INVALID_INPUT:-}" ]; then display_help_message; die "Invalid option: $INVALID_INPUT"; fi
if [ -n "${HELP:-}" ]; then display_help_message; exit 0; fi
if [ -n "${COMMIT:-}" ] && [ -n "${ROLLBACK:-}" ]; then die "You cannot commit_all and also rollback_all. Choose only one."; fi
if [ -z "${COMMIT:-}" ] && [ -z "${ROLLBACK:-}" ] && [ -z "${REPORT:-}" ]; then display_help_message; die "You must choose commit_all or rollback_all or report."; fi
if [ -n "${REPORT:-}" ] && [ -n "${COMMIT:-}" ]; then display_help_message; die "You must choose commit_all or report.  Choose only one."; fi
if [ -n "${REPORT:-}" ] && [ -n "${ROLLBACK:-}" ]; then display_help_message; die "You must choose rollback_all or report. Choose only one."; fi

if [ -n "$(_which mariadb 2>/dev/null)" ]; then
  CMD_MARIADB="${CMD_MARIADB:-"$(_which mariadb)"}"
else
  CMD_MARIADB="${CMD_MYSQL:-"$(_which mysql)"}"
fi

CMD_MY_PRINT_DEFAULTS="${CMD_MY_PRINT_DEFAULTS:-"$(_which my_print_defaults)"}"

if [ -z "$CMD_MARIADB" ]; then
  die "mariadb client command not available."
fi

if [ -z "$CMD_MY_PRINT_DEFAULTS" ]; then
  die "my_print_defaults command not available."
fi

if [ -n "${COMMIT:-}" ] || [ -n "${ROLLBACK:-}" ]; then
  if ! command -v envsubst >/dev/null 2>&1; then
    die "envsubst command not available (install gettext)."
  fi
fi

CLOPTS=$($CMD_MY_PRINT_DEFAULTS --defaults-file="$CONFIG_FILE" mariadb_xa_settle | sed -z -e "s/\n/ /g")

unset ERR
CONNECTING_AS=$($CMD_MARIADB $CLOPTS -ABNe "select user();") || ERR=true
if [ -n "${ERR:-}" ]; then die "Something went wrong (CONNECTING_AS)!"; fi
echo "Connecting as user $CONNECTING_AS."

if [ -n "${REPORT:-}" ]; then
  unset ERR
  LIST_OF_PREPARED_XA=$($CMD_MARIADB $CLOPTS -ABNe "xa recover format='SQL'" | awk '{print $4}') || ERR=true
  if [ -n "${ERR:-}" ]; then die "Something went wrong (LIST_OF_PREPARED_XA)!"; fi
  if [ -z "$LIST_OF_PREPARED_XA" ]; then echo "There are no XA transactions to commit or rollback."; exit 0; fi
  $CMD_MARIADB $CLOPTS -Ae "select concat('PREPARED XA TRANSACTIONS, NOT YET COMMIT.') as NOTE; xa recover format='SQL';"
  exit 0
fi

if [ -z "${INTERACTIVE:-}" ]; then
  ##### NON-INTERACTIVE
  unset ERR
  LIST_OF_PREPARED_XA=$($CMD_MARIADB $CLOPTS -ABNe "xa recover format='SQL'" | awk '{print $4}') || ERR=true
  if [ -n "${ERR:-}" ]; then die "Something went wrong (LIST_OF_PREPARED_XA)!"; fi
  if [ -z "$LIST_OF_PREPARED_XA" ]; then echo "There are no XA transactions to commit or rollback."; exit 0; fi

  if [ -n "${ROLLBACK:-}" ] && [ -z "${COMMIT:-}" ]; then
    ii=0; while IFS= read -r line; do
      export TRX="$line"
      SQL=$(envsubst < "$ROLLBACK_SQL_FILE")
      $CMD_MARIADB $CLOPTS -e "$SQL" || ERR=true
      if [ -n "${ERR:-}" ]; then die "Something went wrong (SQL_ROLLBACK)!"; fi
      ((ii++))
      sleep "$PAUSE_TIME"
    done <<< "$LIST_OF_PREPARED_XA"
    printf "Rollback of $ii XA transactions completed.\n"
  fi

  if [ -n "${COMMIT:-}" ] && [ -z "${ROLLBACK:-}" ]; then
    ii=0; while IFS= read -r line; do
      export TRX="$line"
      SQL=$(envsubst < "$COMMIT_SQL_FILE")
      $CMD_MARIADB $CLOPTS -e "$SQL" || ERR=true
      if [ -n "${ERR:-}" ]; then die "Something went wrong (SQL_COMMIT)!"; fi
      ((ii++))
      sleep "$PAUSE_TIME"
    done <<< "$LIST_OF_PREPARED_XA"
    printf "Commit of $ii XA transactions completed.\n"
  fi
  exit 0
fi

if [ -n "${INTERACTIVE:-}" ]; then
  echo "RUNNING IN INTERACTIVE MODE."
  unset ERR
  LIST_OF_PREPARED_XA=$($CMD_MARIADB $CLOPTS -ABNe "xa recover format='SQL'" | awk '{print $4}') || ERR=true
  if [ -n "${ERR:-}" ]; then die "Something went wrong (LIST_OF_PREPARED_XA)!"; fi
  if [ -z "$LIST_OF_PREPARED_XA" ]; then echo "There are no XA transactions to commit or rollback."; exit 0; fi

  if [ -n "$LIST_OF_PREPARED_XA" ]; then
    $CMD_MARIADB $CLOPTS -Ae "select concat('PREPARED XA TRANSACTIONS, NOT YET COMMIT.') as NOTE; xa recover format='SQL';" || ERR=true
    if [ -n "${ERR:-}" ]; then die "Something went wrong (LIST_OF_PREPARED_XA_TXN)!"; fi
  fi

  if [ -n "${ROLLBACK:-}" ] && [ -z "${COMMIT:-}" ]; then
    printf "ROLLBACK IN INTERACTIVE MODE\n"
    ii=0; while IFS= read -r line; do ((ii++)); done <<< "$LIST_OF_PREPARED_XA"
    printf "There are $ii XA transactions to rollback.\nPress C to continue the script and rollback all of them.\nPress any other key to exit.\n"
    read -r -s -n 1 RESPONSE
    if [[ ! "$RESPONSE" =~ ^[cC]$ ]]; then printf "================\nSCRIPT NOT RUN.\n"; exit 0; fi

    while IFS= read -r line; do
      export TRX="$line"
      SQL=$(envsubst < "$ROLLBACK_SQL_FILE")
      $CMD_MARIADB $CLOPTS -e "$SQL" || ERR=true
      if [ -n "${ERR:-}" ]; then die "Something went wrong (SQL_ROLLBACK)!"; fi
    done <<< "$LIST_OF_PREPARED_XA"
    printf "Rollback of $ii XA transactions completed.\n"
  fi

  if [ -n "${COMMIT:-}" ] && [ -z "${ROLLBACK:-}" ]; then
    printf "COMMIT IN INTERACTIVE MODE\n"
    ii=0; while IFS= read -r line; do ((ii++)); done <<< "$LIST_OF_PREPARED_XA"
    printf "There are $ii XA transactions to commit.\nPress C to continue the script and commit all of them.\nPress any other key to exit.\n"
    read -r -s -n 1 RESPONSE
    if [[ ! "$RESPONSE" =~ ^[cC]$ ]]; then printf "================\nSCRIPT NOT RUN.\n"; exit 0; fi

    while IFS= read -r line; do
      export TRX="$line"
      SQL=$(envsubst < "$COMMIT_SQL_FILE")
      $CMD_MARIADB $CLOPTS -e "$SQL" || ERR=true
      if [ -n "${ERR:-}" ]; then die "Something went wrong (SQL_COMMIT)!"; fi
    done <<< "$LIST_OF_PREPARED_XA"
    printf "Commit of $ii XA transactions completed.\n"
  fi
fi
