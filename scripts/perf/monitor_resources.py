#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压测期间资源监控：按固定间隔采样目标进程(web 服务)与系统级指标，落盘 CSV。

用法:
  python scripts/perf/monitor_resources.py --port 8011 --duration 620 --interval 2 \
      --out test_results/jmeter/monitor_reads.csv --tag reads

说明:
  - 通过端口解析监听进程 PID（netstat -ano），失败则仅监控全系统指标。
  - 依赖 psutil；若不可用则回退到 wmic（Windows）。
  - 与 JMeter 后台进程并发启动，duration 应略大于压测总时长。
"""
import argparse
import csv
import os
import subprocess
import sys
import time

try:
    import psutil
    HAVE_PSUTIL = True
except Exception:
    HAVE_PSUTIL = False


def find_pid_by_port(port):
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(":" + str(port)) \
                and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--duration", type=int, default=600)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--out", default="test_results/jmeter/monitor_reads.csv")
    ap.add_argument("--tag", default="reads")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    pid = args.pid or find_pid_by_port(args.port)
    proc = None
    if pid:
        if HAVE_PSUTIL:
            try:
                proc = psutil.Process(pid)
                print("[monitor] 监控 PID=%d cmd=%s" % (pid, " ".join(proc.cmdline()[:3])))
            except Exception as e:
                print("[monitor] WARN 进程 %d 不可访问: %s" % (pid, e), file=sys.stderr)
        else:
            print("[monitor] WARN 无 psutil，仅监控全系统指标 (pid=%s)" % pid, file=sys.stderr)
    else:
        print("[monitor] WARN 未能解析端口 %d 的 PID，仅监控全系统指标" % args.port, file=sys.stderr)

    fields = [
        "elapsed_s", "timestamp", "sys_cpu_pct", "sys_mem_avail_mb", "sys_mem_used_pct",
        "proc_pid", "proc_cpu_pct", "proc_rss_mb", "proc_vms_mb", "proc_threads", "proc_handles",
    ]

    if HAVE_PSUTIL and proc:
        proc.cpu_percent(None)
        psutil.cpu_percent(None)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed > args.duration:
                break
            row = {
                "elapsed_s": round(elapsed, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if HAVE_PSUTIL:
                vm = psutil.virtual_memory()
                row["sys_cpu_pct"] = round(psutil.cpu_percent(None), 1)
                row["sys_mem_avail_mb"] = round(vm.available / 1024 / 1024, 1)
                row["sys_mem_used_pct"] = round(vm.percent, 1)
            else:
                row["sys_cpu_pct"] = ""
                row["sys_mem_avail_mb"] = ""
                row["sys_mem_used_pct"] = ""
            if HAVE_PSUTIL and proc:
                try:
                    row["proc_pid"] = proc.pid
                    row["proc_cpu_pct"] = round(proc.cpu_percent(None), 1)
                    mi = proc.memory_info()
                    row["proc_rss_mb"] = round(mi.rss / 1024 / 1024, 1)
                    row["proc_vms_mb"] = round(mi.vms / 1024 / 1024, 1)
                    row["proc_threads"] = proc.num_threads()
                    row["proc_handles"] = proc.num_handles()
                except Exception:
                    for k in ["proc_pid", "proc_cpu_pct", "proc_rss_mb",
                              "proc_vms_mb", "proc_threads", "proc_handles"]:
                        row[k] = ""
            else:
                for k in ["proc_pid", "proc_cpu_pct", "proc_rss_mb",
                          "proc_vms_mb", "proc_threads", "proc_handles"]:
                    row[k] = ""
            w.writerow(row)
            f.flush()
            time.sleep(args.interval)
    print("[monitor] 完成 -> %s" % args.out)


if __name__ == "__main__":
    main()
