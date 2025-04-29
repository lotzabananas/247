import argparse
import sys
from pathlib import Path

# Assume the package structure allows these imports
# If running as a script directly, PYTHONPATH might need adjustment
# or consider using `python -m kuzu_graph_builder.cli ...` after packaging
from .ingest import process_directory
from .utils import setup_logging, get_logger

# Setup root logger early
setup_logging()
logger = get_logger(__name__) # Get logger for the CLI module

def main():
    parser = argparse.ArgumentParser(
        description="Build or update a Kuzu graph database from a code repository.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "repo_path",
        type=str,
        help="Path to the root directory of the repository to ingest."
    )
    parser.add_argument(
        "-db", "--database",
        type=str,
        default="./kuzu_code_graph_db",
        help="Path to the Kuzu database directory."
    )
    # Add more arguments based on the review feedback
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging output level."
    )
    # parser.add_argument("--workers", type=int, default=os.cpu_count(), help="Number of parallel workers for hashing/parsing.")
    # parser.add_argument("--ignore", action='append', help="Glob patterns for files/folders to ignore.")
    # parser.add_argument("--max-size-mb", type=int, help="Maximum file size in MB to process.")
    # parser.add_argument("--skip-parsing", action='store_true', help="Skip the code parsing step.")
    # parser.add_argument("--schema-only", action='store_true', help="Define schema and exit.")
    # parser.add_argument("--dry-run", action='store_true', help="Scan files but do not write to the database.")

    args = parser.parse_args()

    # Re-configure logging level based on CLI argument
    setup_logging(args.log_level)

    logger.info(f"Starting Kuzu graph builder for repository: {args.repo_path}")
    logger.info(f"Database location: {args.database}")
    logger.info(f"Log level set to: {args.log_level}")

    # Convert repo_path to absolute path
    repo_path = Path(args.repo_path).resolve()

    # Basic validation
    if not repo_path.is_dir():
        logger.critical(f"Error: Repository path not found or is not a directory: {repo_path}")
        sys.exit(1)

    db_path = Path(args.database)
    # Potentially create the db directory if it doesn't exist, Kuzu might handle this
    db_path.mkdir(parents=True, exist_ok=True)

    # TODO: Handle --schema-only, --dry-run flags
    # if args.schema_only:
    #     # Connect, define schema, disconnect
    #     logger.info("Running in schema-only mode.")
    #     # ... schema definition call ...
    #     sys.exit(0)
    # if args.dry_run:
    #     logger.info("Running in dry-run mode. No database changes will be made.")
    #     # ... modify process_directory or add a dry_run flag ...

    try:
        process_directory(str(db_path), str(repo_path))
        logger.info("Ingestion process finished.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during ingestion: {repr(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # This allows running the script directly, but packaging is preferred.
    # If run directly, Python might not find modules in parent directories easily.
    # To run directly for development, navigate to the directory *above* kuzu_graph_builder
    # and run: python -m kuzu_graph_builder.cli <args>
    main() 