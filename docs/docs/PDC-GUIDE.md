# Parallel and Distributed Computing (PDC) module

The administrator console includes a PDC demonstration at **Parallel Computing (PDC)**.

## What it does

Three independent, read-only financial analytics jobs are implemented in `backend/pdc/report_processor.py`:

1. Income and expense totals
2. Monthly transaction aggregation
3. Expense totals by category

The sequential mode executes the jobs one after another in the Flask process. The parallel mode submits the same jobs to a `concurrent.futures.ProcessPoolExecutor` with up to three worker processes. Each worker opens its own read-only SQLite connection. No worker writes to financial records.

## Run

Start the application using the normal project instructions:

```powershell
cd Ewallet
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python run.py
```

Sign in with an administrator account, open **Parallel Computing (PDC)**, and select a date range. Use **Run benchmark** to execute both modes with the same range. The page displays elapsed time, worker process IDs, speedup, and estimated parallel efficiency.

## API endpoints

All endpoints require an authenticated active administrator session:

- `GET /api/admin/pdc/report?mode=sequential&start=YYYY-MM-DD&end=YYYY-MM-DD`
- `GET /api/admin/pdc/report?mode=parallel&start=YYYY-MM-DD&end=YYYY-MM-DD`
- `GET /api/admin/pdc/benchmark?start=YYYY-MM-DD&end=YYYY-MM-DD`

## How to interpret results

- `speedup = sequential_execution_time / parallel_execution_time`
- `efficiency = speedup / worker_count * 100`

A speedup above 1 means parallel execution was faster for that run. A value below 1 means sequential execution was faster. Small databases often favor sequential execution because process startup and inter-process coordination cost more than the queries themselves. Use a sufficiently large transaction dataset and repeat tests for a meaningful experiment. The dashboard reports measured values; it does not claim parallel execution is always faster.

## Scope and limitations

This is process-based parallel execution on one machine, not a multi-machine distributed deployment. It demonstrates task decomposition, concurrent worker processes, independent data reads, and performance measurement. To claim a truly distributed system, deploy workers on separate machines or containers and introduce a network-based task queue/broker.

The worker functions are deliberately read-only. Financial writes, balance updates, authentication, and the existing transaction workflow are not changed by this module.
