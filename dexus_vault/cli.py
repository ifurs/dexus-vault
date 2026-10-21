"""
Command line entry point and the sync loop.
"""

import argparse
import signal
import sys
import threading
import time

from pydantic import ValidationError

from dexus_vault.__version__ import __description__, __title__, __version__
from dexus_vault.config import (
    DexConfig,
    GeneralConfig,
    MetricsConfig,
    SsmConfig,
    VaultConfig,
)
from dexus_vault.dex import DexAPI, DexError
from dexus_vault.log import logger, setup_logging
from dexus_vault.metrics import Metrics, start_http_server
from dexus_vault.sources import SecretSource, SourceError
from dexus_vault.sources.vault import VaultSource
from dexus_vault.sync import Syncer, SyncOptions

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG = 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=__title__,
        description=f"{__description__}. Every option can also be set "
        "with environment variables, see the README.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--once",
        action="store_true",
        default=None,
        help="run one sync and exit, non-zero on errors (SYNC_ONCE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="log changes without applying them (SYNC_DRY_RUN)",
    )
    parser.add_argument(
        "--prune",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="delete Dex clients missing in the source (SYNC_PRUNE)",
    )
    parser.add_argument(
        "--backend",
        choices=["vault", "aws-ssm"],
        help="where clients are read from (SECRETS_BACKEND, default: vault)",
    )
    parser.add_argument(
        "--interval", type=int, help="seconds between syncs (SYNC_INTERVAL)"
    )
    parser.add_argument("--log-level", help="log level (LOG_LEVEL)")
    parser.add_argument(
        "--log-format", choices=["text", "json"], help="log format (LOG_FORMAT)"
    )
    parser.add_argument(
        "--env-file", default=".env", help="dotenv file to read (default: .env)"
    )
    return parser.parse_args(argv)


def _overrides(args: argparse.Namespace) -> dict:
    values = {
        "sync_once": args.once,
        "sync_dry_run": args.dry_run,
        "sync_prune": args.prune,
        "sync_interval": args.interval,
        "log_level": args.log_level,
        "log_format": args.log_format,
        "secrets_backend": args.backend,
    }
    return {key: value for key, value in values.items() if value is not None}


def _install_signal_handlers(stop: threading.Event) -> None:
    def handler(signum, _frame):
        logger.info(f"Received {signal.Signals(signum).name}, stopping...")
        stop.set()

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


def build_source(
    config: VaultConfig | SsmConfig, stop: threading.Event
) -> SecretSource:
    if isinstance(config, SsmConfig):
        # boto3 is optional, only import it when the backend is used
        from dexus_vault.sources.aws_ssm import SsmSource

        return SsmSource(config)
    return VaultSource(config, stop)


def run(
    general: GeneralConfig,
    metrics_config: MetricsConfig,
    dex_config: DexConfig,
    source_config: VaultConfig | SsmConfig,
    stop: threading.Event,
) -> int:
    options = SyncOptions(
        dry_run=general.sync_dry_run,
        prune=general.sync_prune,
        prune_prefix=general.sync_prune_prefix,
        prune_exclude=general.sync_prune_exclude,
    )
    if options.dry_run:
        logger.info("Dry-run mode, no changes will be made to Dex")
    if options.prune:
        scope = (
            f"ids starting with '{options.prune_prefix}'"
            if options.prune_prefix
            else "all ids"
        )
        logger.warning(f"Pruning enabled for {scope}")

    metrics = Metrics(
        general.sync_interval,
        metrics_config.internal_metrics,
        backend=general.secrets_backend,
    )
    dex = source = server = None
    try:
        if metrics_config.metrics_enable and not general.sync_once:
            try:
                server = start_http_server(
                    metrics, metrics_config.metrics_addr, metrics_config.metrics_port
                )
            except OSError as error:
                raise OSError(
                    f"Cannot serve metrics on {metrics_config.metrics_addr}:"
                    f"{metrics_config.metrics_port}: {error.strerror}"
                ) from error
            logger.info(
                f"Serving /metrics, /healthz and /readyz on "
                f"{metrics_config.metrics_addr}:{metrics_config.metrics_port}"
            )
        dex = DexAPI(dex_config)
        dex.wait_ready(stop)
        source = build_source(source_config, stop)
        source.connect()
        syncer = Syncer(dex, source, options)

        while not stop.is_set():
            started = time.monotonic()
            report = None
            try:
                source.ensure_session(min_ttl=2 * general.sync_interval)
                report = syncer.run_once()
            except (DexError, SourceError) as error:
                logger.error(f"Sync failed: {error}")
            except Exception:
                logger.exception("Sync failed with an unexpected error")
            metrics.record(report, time.monotonic() - started)

            if general.sync_once:
                return EXIT_OK if report is not None and report.ok else EXIT_FAILURE
            logger.debug(f"Next sync in {general.sync_interval} seconds")
            stop.wait(general.sync_interval)
        return EXIT_OK

    except (DexError, SourceError, OSError) as error:
        if stop.is_set():
            # shutdown requested while still starting up
            return EXIT_OK
        logger.error(str(error))
        return EXIT_FAILURE
    finally:
        if source is not None:
            source.close()
        if dex is not None:
            dex.close()
        if server is not None:
            server.shutdown()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        general = GeneralConfig(_env_file=args.env_file, **_overrides(args))
        metrics_config = MetricsConfig(_env_file=args.env_file)
        dex_config = DexConfig(_env_file=args.env_file)
        source_config = (
            SsmConfig(_env_file=args.env_file)
            if general.secrets_backend == "aws-ssm"
            else VaultConfig(_env_file=args.env_file)
        )
    except ValidationError as error:
        # without input values, they may hold tokens or passwords
        problems = "\n".join(
            f"  {'.'.join(str(part) for part in item['loc']).upper()}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        print(f"Invalid configuration:\n{problems}", file=sys.stderr)
        return EXIT_CONFIG

    setup_logging(general.log_level, general.log_format)
    logger.info(f"Starting {__title__} {__version__}")
    stop = threading.Event()
    _install_signal_handlers(stop)
    return run(general, metrics_config, dex_config, source_config, stop)
