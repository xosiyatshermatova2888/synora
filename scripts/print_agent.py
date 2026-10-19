#!/usr/bin/env python3
"""SYNORA print agent — run this on a PC inside the restaurant.

Why it exists: when SYNORA runs on an internet server, that server cannot open a
connection to a printer on your local network (192.168.x.x). This small program
runs *inside* the restaurant, asks the server "is there anything to print?" every
couple of seconds (outbound HTTPS only — no router settings needed), sends each
job to the LAN printer, and reports back.

Standard library only; Python 3.8+.

    python print_agent.py --server https://your-domain.uz --token pa_xxxxxxxx

For a printer plugged into this Windows PC by USB, add its Windows name:

    python print_agent.py --server ... --token ... --windows-printer "XP-80C"

(`--list-printers` shows the names; `--test-printer "XP-80C"` prints a test slip
without needing the server.) In SYNORA, add the printer in "Print agent" mode and
leave the IP empty — those jobs are sent to the Windows printer.

or set SYNORA_SERVER / SYNORA_AGENT_TOKEN. Get the token in the dashboard:
Settings -> Printers -> "Print agent". Leave this window open (or install it as
a startup task) while the restaurant is working.
"""

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def api(server, token, path, body=None, timeout=15):
    data = json.dumps(body).encode("utf-8") if body is not None else b"{}"
    request = urllib.request.Request(
        server.rstrip("/") + "/api/v1/print-agent" + path,
        data=data,
        method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def send_to_windows_printer(name, data):
    """Send RAW bytes (ESC/POS) to a printer installed in Windows, through the
    print spooler — the way USB receipt printers are normally driven."""
    import ctypes
    from ctypes import wintypes

    if os.name != "nt":
        raise OSError("--windows-printer only works on Windows")

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    winspool.StartDocPrinterW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    winspool.WritePrinter.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    for fn in ("StartPagePrinter", "EndPagePrinter", "EndDocPrinter", "ClosePrinter"):
        getattr(winspool, fn).argtypes = [ctypes.c_void_p]

    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(name, ctypes.byref(handle), None):
        raise OSError("cannot open Windows printer %r (error %s)" % (name, ctypes.get_last_error()))
    try:
        doc = DOC_INFO_1("SYNORA", None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
            raise OSError("StartDocPrinter failed (error %s)" % ctypes.get_last_error())
        try:
            winspool.StartPagePrinter(handle)
            written = wintypes.DWORD(0)
            if not winspool.WritePrinter(handle, data, len(data), ctypes.byref(written)) or written.value != len(data):
                raise OSError("WritePrinter failed (error %s)" % ctypes.get_last_error())
            winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def list_windows_printers():
    import subprocess

    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Printer | ForEach-Object { $_.Name + '  [' + $_.PortName + ']' }"],
        capture_output=True, text=True,
    )
    return out.stdout.strip() or out.stderr.strip()


TEST_SLIP = (
    b"\x1b@\x1ba\x01\x1bE\x01SYNORA\n\x1bE\x00Printer test\n"
    b"--------------------------------\n"
    b"If you can read this, the receipt\nprinter is connected correctly.\n\n\n\n\x1dVB\x00"
)


def send_to_printer(host, port, data, timeout=5.0):
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(data)


def process(server, token, job, windows_printer=None):
    try:
        data = base64.b64decode(job["data_b64"])
        if job["host"] == "local":  # a USB printer on this PC (no IP)
            if not windows_printer:
                raise OSError("job is for a local USB printer but the agent was started without --windows-printer")
            send_to_windows_printer(windows_printer, data)
        else:
            send_to_printer(job["host"], int(job["port"]), data)
    except Exception as exc:  # noqa: BLE001 — any socket error just means "not printed"
        message = "%s: %s" % (type(exc).__name__, exc)
        log("FAILED %s -> %s (%s)" % (job["id"][:8], job["host"], message))
        api(server, token, "/jobs/%s/result" % job["id"], {"ok": False, "error": message[:400]})
        return
    log("printed %s -> %s" % (job["id"][:8], windows_printer if job["host"] == "local" else "%s:%s" % (job["host"], job["port"])))
    api(server, token, "/jobs/%s/result" % job["id"], {"ok": True})


def run(server, token, interval, once, windows_printer=None):
    log("SYNORA print agent started -> %s" % server)
    failures = 0
    while True:
        try:
            jobs = (api(server, token, "/poll") or {}).get("jobs", [])
            if failures:
                log("connection restored")
            failures = 0
            for job in jobs:
                process(server, token, job, windows_printer)
            if once:
                return 0
            if jobs:
                continue  # more may be waiting: poll again right away
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                log("The token was rejected. Create a new one in Settings -> Printers.")
                return 2
            failures += 1
            log("server answered HTTP %s" % exc.code)
        except Exception as exc:  # noqa: BLE001 — offline, DNS, timeouts ...
            failures += 1
            if failures == 1 or failures % 30 == 0:
                log("cannot reach the server (%s: %s) — will keep trying" % (type(exc).__name__, exc))
        if once:
            return 1 if failures else 0
        time.sleep(min(interval * (1 + failures), 30))


def main():
    parser = argparse.ArgumentParser(description="SYNORA print agent")
    parser.add_argument("--server", default=os.environ.get("SYNORA_SERVER"), help="e.g. https://your-domain.uz")
    parser.add_argument("--token", default=os.environ.get("SYNORA_AGENT_TOKEN"), help="agent token (pa_...)")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between polls (default 2)")
    parser.add_argument("--once", action="store_true", help="poll one time and exit (for testing)")
    parser.add_argument("--windows-printer", default=os.environ.get("SYNORA_WINDOWS_PRINTER"),
                        help='name of a USB printer installed in Windows, e.g. "XP-80C"')
    parser.add_argument("--list-printers", action="store_true", help="show the printers installed in Windows and exit")
    parser.add_argument("--test-printer", metavar="NAME", help="print a test slip on this Windows printer and exit")
    args = parser.parse_args()
    if args.list_printers:
        print(list_windows_printers())
        return
    if args.test_printer:
        send_to_windows_printer(args.test_printer, TEST_SLIP)
        print("test slip sent to %r" % args.test_printer)
        return
    if not args.server or not args.token:
        parser.error("both --server and --token are required (or SYNORA_SERVER / SYNORA_AGENT_TOKEN)")
    try:
        sys.exit(run(args.server, args.token, args.interval, args.once, args.windows_printer))
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
