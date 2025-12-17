"""Command-line interface for ArrTheAudio."""

import asyncio
import sys
from pathlib import Path

import click

from arrtheaudio import __version__
from arrtheaudio.config import Config, load_config
from arrtheaudio.core.pipeline import ProcessingPipeline
from arrtheaudio.core.scanner import FileScanner
from arrtheaudio.metadata.cache import TMDBCache
from arrtheaudio.metadata.tmdb import TMDBClient
from arrtheaudio.metadata.resolver import MetadataResolver
from arrtheaudio.utils.logger import setup_logging, get_logger


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (defaults to built-in defaults)",
)
@click.pass_context
def cli(ctx, config):
    """ArrTheAudio - Automatic audio track fixer for Arr stack."""
    # Load configuration
    try:
        cfg = load_config(config)
        ctx.ensure_object(dict)
        ctx.obj["config"] = cfg

        # Setup logging
        setup_logging(cfg.logging)

    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def process(ctx, file):
    """Process a single video file.

    Args:
        file: Path to the video file to process
    """
    config = ctx.obj["config"]
    logger = get_logger(__name__)

    click.echo(f"Processing: {file}")

    async def _process():
        # Initialize TMDB client and resolver if enabled
        tmdb_client = None
        if config.tmdb.enabled and config.tmdb.api_key:
            cache = TMDBCache(Path(config.tmdb.cache_path), config.tmdb.cache_ttl_days)
            tmdb_client = TMDBClient(config.tmdb.api_key, cache)
            resolver = MetadataResolver(tmdb_client, config)
        else:
            resolver = MetadataResolver(None, config)

        # Resolve metadata from filename
        metadata = await resolver.resolve(file, arr_metadata=None)

        # Process file with metadata
        pipeline = ProcessingPipeline(config)
        result = await pipeline.process(file, metadata)

        # Close TMDB client if created
        if tmdb_client:
            await tmdb_client.close()

        return result

    result = asyncio.run(_process())

    # Display result
    if result.status == "success":
        click.secho(f"✓ {result}", fg="green")
        sys.exit(0)
    elif result.status == "skipped":
        click.secho(f"⊘ {result}", fg="yellow")
        sys.exit(0)
    elif result.status == "dry_run":
        click.secho(f"⊙ {result}", fg="cyan")
        sys.exit(0)
    else:
        click.secho(f"✗ {result}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--recursive/--no-recursive",
    "-r/-R",
    default=True,
    help="Scan subdirectories recursively (default: True)",
)
@click.option(
    "--pattern",
    "-p",
    default=None,
    help="Glob pattern to match files (e.g., '**/*.mkv')",
)
@click.pass_context
def scan(ctx, path, recursive, pattern):
    """Scan a directory and process all video files.

    Args:
        path: Path to directory to scan (or file to process)
    """
    config = ctx.obj["config"]
    logger = get_logger(__name__)

    click.echo(f"Scanning: {path}")
    if pattern:
        click.echo(f"Pattern: {pattern}")
    click.echo(f"Recursive: {recursive}")
    click.echo("")

    # Discover files
    scanner = FileScanner()

    try:
        if pattern:
            # Use pattern if provided
            base_pattern = str(path / pattern) if path.is_dir() else str(path)
            files = scanner.scan_pattern(base_pattern)
        else:
            # Regular scan
            files = scanner.scan(path, recursive=recursive)
    except Exception as e:
        click.secho(f"✗ Error scanning: {e}", fg="red", err=True)
        sys.exit(1)

    if not files:
        click.secho("⊘ No video files found", fg="yellow")
        sys.exit(0)

    click.echo(f"Found {len(files)} file(s)")
    click.echo("")

    # Process each file
    async def _scan():
        # Initialize TMDB client and resolver if enabled
        tmdb_client = None
        if config.tmdb.enabled and config.tmdb.api_key:
            cache = TMDBCache(Path(config.tmdb.cache_path), config.tmdb.cache_ttl_days)
            tmdb_client = TMDBClient(config.tmdb.api_key, cache)
            resolver = MetadataResolver(tmdb_client, config)
        else:
            resolver = MetadataResolver(None, config)

        pipeline = ProcessingPipeline(config)
        results = {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "dry_run": 0,
            "error": 0,
        }

        for idx, file in enumerate(files, 1):
            click.echo(f"[{idx}/{len(files)}] {file.name}")

            # Resolve metadata from filename
            metadata = await resolver.resolve(file, arr_metadata=None)

            # Process file
            result = await pipeline.process(file, metadata)

            # Display result
            if result.status == "success":
                click.secho(f"  ✓ {result}", fg="green")
                results["success"] += 1
            elif result.status == "skipped":
                click.secho(f"  ⊘ {result}", fg="yellow")
                results["skipped"] += 1
            elif result.status == "dry_run":
                click.secho(f"  ⊙ {result}", fg="cyan")
                results["dry_run"] += 1
            elif result.status == "failed":
                click.secho(f"  ✗ {result}", fg="red")
                results["failed"] += 1
            else:  # error
                click.secho(f"  ✗ {result}", fg="red")
                results["error"] += 1

            click.echo("")

        # Close TMDB client if created
        if tmdb_client:
            await tmdb_client.close()

        return results

    results = asyncio.run(_scan())

    # Summary
    click.echo("=" * 60)
    click.echo("Summary:")
    click.secho(f"  ✓ Success:  {results['success']}", fg="green")
    click.secho(f"  ⊙ Dry run:  {results['dry_run']}", fg="cyan")
    click.secho(f"  ⊘ Skipped:  {results['skipped']}", fg="yellow")
    click.secho(f"  ✗ Failed:   {results['failed']}", fg="red")
    click.secho(f"  ✗ Errors:   {results['error']}", fg="red")
    click.echo(f"  Total:      {len(files)}")

    # Exit with error if any failures
    if results["failed"] > 0 or results["error"] > 0:
        sys.exit(1)


@cli.command()
@click.pass_context
def daemon(ctx):
    """Start the daemon in webhook receiver mode.

    This starts a FastAPI server that listens for webhooks from Sonarr/Radarr
    and processes files automatically upon download completion.
    """
    config = ctx.obj["config"]

    click.echo("Starting ArrTheAudio daemon...")
    click.echo(f"Listening on {config.api.host}:{config.api.port}")
    click.echo(f"Webhook auth: {'enabled' if config.api.webhook_secret else 'disabled'}")
    click.echo("")
    click.echo("Endpoints:")
    click.echo(f"  - Sonarr webhook: http://{config.api.host}:{config.api.port}/webhook/sonarr")
    click.echo(f"  - Radarr webhook: http://{config.api.host}:{config.api.port}/webhook/radarr")
    click.echo(f"  - Health check:   http://{config.api.host}:{config.api.port}/health")
    click.echo(f"  - API docs:       http://{config.api.host}:{config.api.port}/docs")
    click.echo("")
    click.echo("Press Ctrl+C to stop")
    click.echo("")

    from arrtheaudio.daemon import start_daemon

    try:
        start_daemon(config)
    except KeyboardInterrupt:
        click.echo("\n\nDaemon stopped")
        sys.exit(0)


@cli.command()
@click.pass_context
def version(ctx):
    """Show version information."""
    click.echo(f"ArrTheAudio v{__version__}")


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
