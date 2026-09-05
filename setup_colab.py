# `setup_colab.py`
"""
Set up the course environment in Google Colab.

This script:

1. Clones the course GitHub repository.
2. Installs a pinned version of uv.
3. Uses the committed uv.lock as the authoritative environment.
4. Exports uv.lock to a fully pinned requirements file.
5. Synchronizes Colab's existing Python environment with those requirements.
6. Optionally downloads large course datasets.
7. Verifies the Python environment.

Normal usage from Google Colab:

    !python setup_colab.py

To also download large datasets:

    !python setup_colab.py --download-data
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

# ============================================================================
# Configuration
# ============================================================================

# ---------------------------------------------------------------------------
# GitHub repository
# ---------------------------------------------------------------------------

REPO_URL = "https://github.com/kaancet/KU-invivo-neuroscience-workshop"

# Repository location inside the temporary Colab runtime.
REPO_DIR = Path("/content/KU-invivo-neuroscience-workshop")


# ---------------------------------------------------------------------------
# uv
# ---------------------------------------------------------------------------

# Pin the uv version used to construct the Colab environment.

UV_VERSION = "0.11.28"


# ---------------------------------------------------------------------------
# Course data
# ---------------------------------------------------------------------------

DATA_DIR = REPO_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"


# ---------------------------------------------------------------------------
# Optional large dataset
# ---------------------------------------------------------------------------

# Set this to the direct download URL for your large dataset.
#
# Example:
#
# LARGE_DATA_URL = (
#     "https://example.com/course-data/dataset.zip"
# )
#
LARGE_DATA_URL = None

# File where the downloaded dataset will be stored.
LARGE_DATA_FILE = RAW_DATA_DIR / "large_dataset.zip"


# ============================================================================
# Utility functions
# ============================================================================


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> None:
    """
    Run a command and stop immediately if it fails.
    """

    print(f"\n> {' '.join(command)}")

    subprocess.run(
        command,
        check=True,
        cwd=cwd,
    )


def command_exists(command: str) -> bool:
    """
    Check whether a command is available on PATH.
    """

    result = subprocess.run(
        [command, "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return result.returncode == 0


# ============================================================================
# Repository
# ============================================================================


def clone_repository() -> None:
    """
    Clone the course repository if it does not already exist.
    """

    print("\n" + "=" * 60)
    print("Course repository")
    print("=" * 60)

    if REPO_DIR.exists():
        print(f"Repository already exists: {REPO_DIR}")
        print("\nSkipping clone.")
        return

    REPO_DIR.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Cloning repository:")
    print(REPO_URL)

    print("\nDestination:")
    print(REPO_DIR)

    run_command(
        [
            "git",
            "clone",
            "--depth",
            "1",
            REPO_URL,
            str(REPO_DIR),
        ]
    )

    print("\nRepository cloned successfully.")


# ============================================================================
# uv
# ============================================================================


def install_uv() -> None:
    """
    Install the exact configured uv version.
    """

    print("\n" + "=" * 60)
    print("Installing uv")
    print("=" * 60)

    # Check whether the requested version is already installed.
    if command_exists("uv"):
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )

        installed_version = result.stdout.strip()

        print(f"Existing uv installation: {installed_version}")

        if installed_version == f"uv {UV_VERSION}":
            print("Required uv version is already installed.")
            return

        print(f"Required version: uv {UV_VERSION}")
        print("Installing the required version...")

    else:
        print("uv is not currently installed.")

    # Install the exact requested version.
    run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--upgrade",
            f"uv=={UV_VERSION}",
        ]
    )

    # Verify installation.
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    installed_version = result.stdout.strip()

    print(f"\nInstalled: {installed_version}")


# ============================================================================
# Lockfile
# ============================================================================


def check_lockfile() -> Path:
    """
    Check that the repository contains the required lockfile.
    """

    lockfile = REPO_DIR / "uv.lock"

    if not lockfile.exists():
        raise FileNotFoundError(
            f"""
            Could not find uv.lock.

            Expected:
                {lockfile}

            Make sure you have generated and committed the lockfile
            from your development environment:

                uv lock
                git add uv.lock
                git commit
                git push
            """
        )

    return lockfile


def check_pyproject() -> Path:
    """
    Check that the repository contains pyproject.toml.
    """

    pyproject = REPO_DIR / "pyproject.toml"

    if not pyproject.exists():
        raise FileNotFoundError(
            f"""
            Could not find pyproject.toml.

            Expected:
                {pyproject}
            """
        )

    return pyproject


# ============================================================================
# Locked environment
# ============================================================================


def export_locked_requirements() -> Path:
    """
    Export the committed uv.lock to a fully pinned requirements file.

    --frozen is important.

    It tells uv to use the existing lockfile exactly as committed,
    rather than updating or regenerating it.
    """

    print("\n" + "=" * 60)
    print("Exporting locked environment")
    print("=" * 60)

    check_pyproject()
    check_lockfile()

    requirements_file = REPO_DIR / ".colab-requirements.txt"

    # Remove a potentially stale export from a previous run.
    if requirements_file.exists():
        requirements_file.unlink()

    run_command(
        [
            "uv",
            "export",
            "--frozen",
            "--format",
            "requirements.txt",
            "--output-file",
            str(requirements_file),
        ],
        cwd=REPO_DIR,
    )

    if not requirements_file.exists():
        raise RuntimeError("uv export completed, but the requirements file was not created.")

    print("\nLocked requirements exported to:")
    print(requirements_file)

    return requirements_file


def synchronize_environment(
    requirements_file: Path,
) -> None:
    """
    Synchronize Colab's existing Python environment with the
    exact requirements generated from uv.lock.

    --system is intentional because Colab's Jupyter kernel uses
    the system Python environment.

    uv pip sync removes packages that are not present in the
    exported requirements file.
    """

    print("\n" + "=" * 60)
    print("Synchronizing Python environment")
    print("=" * 60)

    run_command(
        [
            "uv",
            "pip",
            "sync",
            "--system",
            str(requirements_file),
        ]
    )

    print("\nPython environment synchronized successfully.")


# ============================================================================
# Data directories
# ============================================================================


def create_data_directories() -> None:
    """
    Create the standard course data directories.
    """

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================================
# Large data
# ============================================================================


def download_large_data() -> None:
    """
    Download the optional large dataset.

    The download is skipped if:

    1. No URL has been configured, or
    2. The destination file already exists.
    """

    print("\n" + "=" * 60)
    print("Large dataset")
    print("=" * 60)

    if LARGE_DATA_URL is None:
        print("No large dataset URL has been configured.")
        print("Skipping large-data download.")
        return

    if LARGE_DATA_FILE.exists():
        print("Dataset already exists:")
        print(LARGE_DATA_FILE)
        print("\nSkipping download.")
        return

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Downloading:")
    print(LARGE_DATA_URL)

    print("\nDestination:")
    print(LARGE_DATA_FILE)

    urlretrieve(
        LARGE_DATA_URL,
        LARGE_DATA_FILE,
    )

    print("\nLarge dataset downloaded successfully.")


# ============================================================================
# Environment verification
# ============================================================================


def verify_environment() -> None:
    """
    Verify that the main course packages can be imported.
    """

    print("\n" + "=" * 60)
    print("Checking Python environment")
    print("=" * 60)

    import matplotlib
    import numpy
    import polars

    print(f"Python:       {sys.version.split()[0]}")
    print(f"NumPy:        {numpy.__version__}")
    print(f"pandas:       {polars.__version__}")
    print(f"Matplotlib:   {matplotlib.__version__}")

    print("\nEnvironment verification passed.")


# ============================================================================
# Main
# ============================================================================


def main() -> None:

    parser = argparse.ArgumentParser(description=("Set up the course environment in Google Colab."))

    parser.add_argument(
        "--download-data",
        action="store_true",
        help=("Download the optional large course dataset."),
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Course environment setup")
    print("=" * 60)

    try:
        # 1. Clone repository
        clone_repository()

        # 2. Create data directories
        create_data_directories()

        # 3. Install exact uv version
        install_uv()

        # 4. Export committed uv.lock
        requirements_file = export_locked_requirements()

        # 5. Synchronize Colab's Python environment
        synchronize_environment(requirements_file)

        # 6. Optionally download large data
        if args.download_data:
            download_large_data()
        else:
            print("\nLarge dataset download skipped.")

            print("Use:")

            print("    !python setup_colab.py --download-data")

            print("\nif this notebook requires the large dataset.")

        # 7. Verify environment
        verify_environment()

    except subprocess.CalledProcessError as error:
        print("\n" + "=" * 60)
        print("SETUP FAILED")
        print("=" * 60)

        print("\nA command failed while setting up the course environment.")

        print(f"\nCommand exit code: {error.returncode}")

        raise SystemExit(1)

    except Exception as error:
        print("\n" + "=" * 60)
        print("SETUP FAILED")
        print("=" * 60)

        print(f"\n{error}")

        raise SystemExit(1)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)

    print("\nCourse repository:")
    print(REPO_DIR)

    print("\nThe Python environment is ready.")
    print("You can now continue with the notebook.")


if __name__ == "__main__":
    main()
