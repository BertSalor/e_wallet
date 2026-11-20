"""Independent SQLite report jobs suitable for sequential or process execution."""

from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import time


def _query(db_path, sql, params):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return {"rows": rows, "worker_pid": os.getpid()}
    finally:
        conn.close()


def income_expense_job(db_path, start, end):
    started = time.perf_counter()
    result = _query(
        db_path,
        """
        SELECT kind, COUNT(*) AS transaction_count, COALESCE(SUM(amount),0) AS total
        FROM transactions
        WHERE transaction_date BETWEEN ? AND ? AND kind IN ('income','expense')
        GROUP BY kind ORDER BY kind
    """,
        (start, end),
    )
    result["task"] = "income_expense"
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def monthly_job(db_path, start, end):
    started = time.perf_counter()
    result = _query(
        db_path,
        """
        SELECT substr(transaction_date,1,7) AS month,
          SUM(CASE WHEN kind='income' THEN amount ELSE 0 END) AS income,
          SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END) AS expenses,
          COUNT(*) AS transaction_count
        FROM transactions WHERE transaction_date BETWEEN ? AND ?
        GROUP BY substr(transaction_date,1,7) ORDER BY month
    """,
        (start, end),
    )
    result["task"] = "monthly"
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def category_job(db_path, start, end):
    started = time.perf_counter()
    result = _query(
        db_path,
        """
        SELECT COALESCE(c.name,'Uncategorized') AS category,
          COALESCE(SUM(t.amount),0) AS total, COUNT(*) AS transaction_count
        FROM transactions t LEFT JOIN categories c
          ON c.id=t.category_id AND c.user_id=t.user_id
        WHERE t.kind='expense' AND t.transaction_date BETWEEN ? AND ?
        GROUP BY c.id,c.name ORDER BY total DESC
    """,
        (start, end),
    )
    result["task"] = "expense_categories"
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


JOBS = (income_expense_job, monthly_job, category_job)


def run_sequential(db_path, start, end):
    began = time.perf_counter()
    results = [job(db_path, start, end) for job in JOBS]
    return {
        "results": results,
        "execution_ms": round((time.perf_counter() - began) * 1000, 3),
        "worker_pids": sorted({r["worker_pid"] for r in results}),
        "mode": "sequential",
    }


def run_parallel(db_path, start, end, max_workers=3):
    from concurrent.futures import ProcessPoolExecutor

    began = time.perf_counter()
    with ProcessPoolExecutor(max_workers=min(max_workers, len(JOBS))) as pool:
        futures = [pool.submit(job, db_path, start, end) for job in JOBS]
        results = [future.result() for future in futures]
    return {
        "results": results,
        "execution_ms": round((time.perf_counter() - began) * 1000, 3),
        "worker_pids": sorted({r["worker_pid"] for r in results}),
        "mode": "parallel",
        "workers": min(max_workers, len(JOBS)),
    }


def benchmark(db_path, start, end):
    sequential = run_sequential(db_path, start, end)
    parallel = run_parallel(db_path, start, end)
    seq = sequential["execution_ms"]
    par = parallel["execution_ms"]
    return {
        "sequential": sequential,
        "parallel": parallel,
        "speedup": round(seq / par, 3) if par > 0 else None,
        "efficiency_percent": (
            round((seq / par) / parallel["workers"] * 100, 2) if par > 0 else None
        ),
        "faster_mode": "parallel" if par < seq else "sequential",
        "note": "Process startup and SQLite read overhead can make parallel execution slower for small datasets. Benchmark results are measured, not guaranteed.",
    }
