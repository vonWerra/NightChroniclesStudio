#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Series Outline Generator - Main Module
Generates structured outlines for historical YouTube series in multiple languages.
"""

import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional
import sys
import os

from src.config import Config, load_config
from src.generator import OutlineGenerator
from src.logger import setup_logging
from src.monitor import Monitor

# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 2
EXIT_API_ERROR = 3
EXIT_FILE_ERROR = 4
EXIT_UNEXPECTED = 5

# Setup structured logging
logger = setup_logging(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser with proper options."""
    parser = argparse.ArgumentParser(
        description="Generate YouTube series outlines in multiple languages",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config/outline_config.json"),
        help="Path to configuration file (default: config/outline_config.json)"
    )

    parser.add_argument(
        "--template", "-t",
        type=Path,
        default=Path("templates/outline_master.txt"),
        help="Path to template file (default: templates/outline_master.txt)"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output)"
    )

    parser.add_argument(
        "--languages", "-l",
        nargs="+",
        choices=["CS", "EN", "DE", "ES", "FR"],
        help="Languages to generate (default: all from config)"
    )

    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Process languages in parallel (faster but uses more API calls)"
    )

    parser.add_argument(
        "--cache",
        action="store_true",
        default=True,
        help="Use caching for intermediate results (default: True)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without generating outlines"
    )

    return parser


async def main():
    """Main entry point with async support."""
    # Parse CLI arguments
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging level based on verbosity
    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG

    logging.getLogger().setLevel(log_level)

    # Initialize monitoring
    monitor = Monitor()
    monitor.start()

    # Resolve output root from environment if requested (centralized outputs)
    # Priority: explicit -o argument > OUTLINE_OUTPUT_ROOT > NC_OUTPUTS_ROOT/outline > default 'output'
    env_out = os.getenv("OUTLINE_OUTPUT_ROOT")
    nc_root = os.getenv("NC_OUTPUTS_ROOT")

    try:
        # Load and validate configuration
        logger.info(f"Loading configuration from {args.config}")
        try:
            config = load_config(args.config)
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            return EXIT_FILE_ERROR
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            return EXIT_VALIDATION_ERROR

        # Override languages if specified
        if args.languages:
            config.languages = args.languages
            logger.info(f"Processing languages: {', '.join(args.languages)}")

        # Load template
        if not args.template.exists():
            logger.error(f"Template file not found: {args.template}")
            return EXIT_FILE_ERROR

        try:
            template_content = args.template.read_text(encoding='utf-8')
            logger.info(f"Loaded template from {args.template}")
        except Exception as e:
            logger.error(f"Failed to read template: {e}")
            return EXIT_FILE_ERROR

        # Dry run - just validate
        if args.dry_run:
            logger.info("Dry run mode - validating configuration only")
            logger.info("[OK] Configuration is valid")
            logger.info(f"[OK] Would generate outlines for: {', '.join(config.languages)}")
            return EXIT_SUCCESS

        # If user didn't override -o and env is set, use centralized outputs
        if str(args.output) == "output":
            if env_out:
                args.output = Path(env_out)
            elif nc_root:
                args.output = Path(nc_root) / "outline"

        # Create output directory
        args.output.mkdir(parents=True, exist_ok=True)

        # Initialize generator
        generator = OutlineGenerator(
            config=config,
            template=template_content,
            output_dir=args.output,
            use_cache=args.cache,
            monitor=monitor
        )

        # Generate outlines
        try:
            if args.parallel:
                logger.info("Generating outlines in parallel mode")
                results = await generator.generate_all_parallel()
            else:
                logger.info("Generating outlines in sequential mode")
                results = await generator.generate_all_sequential()
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            if "api" in str(e).lower() or "openai" in str(e).lower():
                return EXIT_API_ERROR
            return EXIT_UNEXPECTED

        # Report results
        successful = sum(1 for r in results.values() if r['success'])
        failed = len(results) - successful

        logger.info(f"Generation complete: {successful} successful, {failed} failed")

        # Show monitor statistics
        stats = monitor.get_stats()
        logger.info(f"API calls: {stats['api_calls']}")
        logger.info(f"Total tokens: {stats['total_tokens']}")
        logger.info(f"Estimated cost: ${stats['estimated_cost']:.2f}")
        logger.info(f"Cache hits: {stats['cache_hits']}/{stats['cache_attempts']}")

        # Report any failures
        for lang, result in results.items():
            if not result['success']:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Failed to generate {lang}: {error_msg}")

        # Exit with appropriate code
        if failed == 0:
            return EXIT_SUCCESS
        elif any('api' in str(results[lang].get('error', '')).lower() for lang in results if not results[lang]['success']):
            return EXIT_API_ERROR
        else:
            return EXIT_UNEXPECTED

    except KeyboardInterrupt:
        logger.warning("Generation interrupted by user")
        return EXIT_UNEXPECTED
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return EXIT_UNEXPECTED
    finally:
        # Cleanup API sessions
        if 'generator' in locals():
            await generator.api_client.cleanup()
        monitor.stop()


if __name__ == "__main__":
    # Run async main and exit with returned code
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
