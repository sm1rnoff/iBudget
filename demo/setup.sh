#!/usr/bin/env sh
# Recreate the demo database used for screenshots: six months of sample expenses and budgets.
set -e
cd "$(dirname "$0")/.."
export IBUDGET_DB="${IBUDGET_DB:-.demo/ibudget.db}"
rm -f "$IBUDGET_DB"
.venv/bin/ibudget import demo/expenses.csv
.venv/bin/ibudget budget set food 450
.venv/bin/ibudget budget set entertainment 120
.venv/bin/ibudget budget set shopping 150
.venv/bin/ibudget budget set utilities 110
echo "Demo database: $IBUDGET_DB"
