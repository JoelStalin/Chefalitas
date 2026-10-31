# -*- coding: utf-8 -*-
"""
Windows Service wrapper using pywin32.
Install: python win_service.py install
Start:   python win_service.py start
Stop:    python win_service.py stop
"""
import os
import sys

# Required for pywin32 service
if sys.platform != "win32":
    sys.stderr.write("This script is for Windows only.\n")
    sys.exit(1)

import win32serviceutil
import win32service
import win32event
import servicemanager

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)


class LocalPrinterAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PosPrintingSuiteAgent"
    _svc_display_name_ = "POS Printing Suite Local Agent"
    _svc_description_ = "HTTP agent for POS receipt/kitchen printing on this PC (127.0.0.1:9060)."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.main()

    def main(self):
        from config_loader import load_config
        from agent_service import setup_logging
        config = load_config()
        setup_logging(config.get("log_dir", ""))
        import threading
        self._httpd = None
        server_ready = threading.Event()
        server_thread = threading.Thread(
            target=self._run_server_thread,
            args=(config, server_ready),
            daemon=True,
        )
        server_thread.start()
        server_ready.wait(timeout=5)
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass

    def _run_server_thread(self, config, ready):
        from http.server import HTTPServer
        try:
            from http.server import ThreadingHTTPServer
        except Exception:
            ThreadingHTTPServer = HTTPServer
        from agent_service import Handler, DEFAULT_HOST, DEFAULT_PORT
        Handler.config = config
        host = config.get("host", DEFAULT_HOST)
        port = int(config.get("port", 9060))
        self._httpd = ThreadingHTTPServer((host, port), Handler)
        ready.set()
        try:
            self._httpd.serve_forever()
        finally:
            if hasattr(self._httpd, "server_close"):
                self._httpd.server_close()


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(LocalPrinterAgentService)
