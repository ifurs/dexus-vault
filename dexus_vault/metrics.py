"""
Prometheus metrics and the HTTP server exposing /metrics, /healthz and /readyz.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    Info,
    PlatformCollector,
    ProcessCollector,
    disable_created_metrics,
    generate_latest,
)

from dexus_vault.__version__ import __version__
from dexus_vault.sync import SyncReport

NAMESPACE = "dexus_vault"

# *_created series only add noise for counters reset on restart
disable_created_metrics()


class Metrics:
    def __init__(
        self,
        sync_interval: int,
        internal_metrics: bool = False,
        backend: str = "vault",
    ):
        self.sync_interval = sync_interval
        self.last_success: float | None = None
        self.registry = registry = CollectorRegistry()
        if internal_metrics:
            ProcessCollector(registry=registry)
            PlatformCollector(registry=registry)
            GCCollector(registry=registry)

        Info(
            "build",
            "dexus-vault build information",
            namespace=NAMESPACE,
            registry=registry,
        ).info({"version": __version__, "backend": backend})
        self.operations = Counter(
            "client_operations",
            "Client operations applied to Dex",
            ["operation", "status"],
            namespace=NAMESPACE,
            registry=registry,
        )
        self.syncs = Counter(
            "syncs",
            "Sync runs by result",
            ["result"],
            namespace=NAMESPACE,
            registry=registry,
        )
        self.sync_duration = Histogram(
            "sync_duration_seconds",
            "Duration of a sync run",
            namespace=NAMESPACE,
            registry=registry,
        )
        self.last_sync_timestamp = Gauge(
            "last_sync_timestamp_seconds",
            "Time of the last sync run",
            namespace=NAMESPACE,
            registry=registry,
        )
        self.last_success_timestamp = Gauge(
            "last_success_timestamp_seconds",
            "Time of the last sync run without errors",
            namespace=NAMESPACE,
            registry=registry,
        )
        self.clients = Gauge(
            "clients",
            "Valid clients defined in the source",
            namespace=NAMESPACE,
            registry=registry,
        )
        self.invalid_secrets = Gauge(
            "invalid_secrets",
            "Secrets in the source that are not valid client definitions",
            namespace=NAMESPACE,
            registry=registry,
        )

    def record(self, report: SyncReport | None, duration: float) -> None:
        """
        Record a sync run, report is None when the run failed early.
        """
        now = time.time()
        self.sync_duration.observe(duration)
        self.last_sync_timestamp.set(now)
        if report is not None:
            self.clients.set(report.clients)
            self.invalid_secrets.set(report.invalid)
            for (operation, status), count in report.operations.items():
                self.operations.labels(operation=operation, status=status).inc(count)
        if report is not None and report.ok:
            self.syncs.labels(result="success").inc()
            self.last_success_timestamp.set(now)
            self.last_success = now
        else:
            self.syncs.labels(result="failure").inc()

    def ready(self) -> bool:
        """
        Ready once a sync succeeded, and as long as successes keep coming.
        """
        if self.last_success is None:
            return False
        return time.time() - self.last_success < 3 * self.sync_interval + 60


def start_http_server(metrics: Metrics, addr: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/metrics":
                self._reply(200, generate_latest(metrics.registry), CONTENT_TYPE_LATEST)
            elif path == "/healthz":
                self._reply(200, b"ok\n")
            elif path == "/readyz":
                if metrics.ready():
                    self._reply(200, b"ready\n")
                else:
                    self._reply(503, b"not ready\n")
            else:
                self._reply(404, b"not found\n")

        def _reply(self, code: int, body: bytes, content_type: str = "text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer((addr, port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
