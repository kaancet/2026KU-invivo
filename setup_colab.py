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

# ============================================================================
# Configuration
# ============================================================================

# ---------------------------------------------------------------------------
# GitHub repository
# ---------------------------------------------------------------------------

REPO_URL = "https://github.com/kaancet/2026KU-invivo"

# Repository location inside the temporary Colab runtime.
REPO_DIR = Path("/content/2026KU-invivo")


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
# Public Google Drive share link (or file id) for the course-data zip.
# No Drive mount is used — the zip is downloaded via gdown, so the notebook
# never gets access to anyone's Drive.
#
# The zip MUST contain a top-level `data/` folder (data/processed, data/raw).
# Create it locally with:   zip -r course_data.zip data
LARGE_DATA_URL = "https://drive.google.com/file/d/1HBoaPmKmljGi0XI645oXc9d78KOM_gJg/view?usp=sharing"

# File where the downloaded dataset will be stored (removed after extraction).
LARGE_DATA_FILE = REPO_DIR / "course_data.zip"


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

    # --no-hashes -> one line per package, so we can filter it below.
    # uv export defaults to requirements.txt format; the --format value name
    # differs across uv versions, so we omit it to stay version-robust.
    run_command(
        [
            "uv",
            "export",
            "--frozen",
            "--no-hashes",
            "--output-file",
            str(requirements_file),
        ],
        cwd=REPO_DIR,
    )

    if not requirements_file.exists():
        raise RuntimeError("uv export completed, but the requirements file was not created.")

    _filter_colab_infra(requirements_file)

    print("\nLocked requirements exported to:")
    print(requirements_file)

    return requirements_file


# Packages Colab's runtime owns. Overwriting them breaks the kernel: e.g.
# upgrading IPython makes google.colab (built for the old IPython) crash on
# every kernel start. The course notebooks don't use these directly, so we
# keep Colab's versions and only install the scientific stack on top.
COLAB_OWNED_PACKAGES = {
    "ipython",
    "ipykernel",
    "ipython-pygments-lexers",
    "traitlets",
    "jupyter-client",
    "jupyter-core",
    "jedi",
    "parso",
    "prompt-toolkit",
    "pexpect",
    "ptyprocess",
    "matplotlib-inline",
    "pyzmq",
    "tornado",
    "debugpy",
    "comm",
    "nest-asyncio",
    "stack-data",
    "executing",
    "asttokens",
    "pure-eval",
    "pygments",
    "wcwidth",
    "decorator",
    "psutil",
}


def _requirement_name(line: str) -> str:
    """
    Extract the lowercase package name from a requirements.txt line.
    Handles `name==x`, `name @ git+...`, and environment markers.
    """

    text = line.strip()
    for separator in ("==", " @", "@", ";", "<", ">", "!", "~", " "):
        if separator in text:
            text = text.split(separator, 1)[0]
    return text.strip().lower()


def _filter_colab_infra(requirements_file: Path) -> None:
    """
    Drop Colab-owned packages (see COLAB_OWNED_PACKAGES) from the export so
    the install leaves Colab's Jupyter/IPython runtime intact.
    """

    kept = []
    dropped = []

    for line in requirements_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        if _requirement_name(line) in COLAB_OWNED_PACKAGES:
            dropped.append(_requirement_name(line))
        else:
            kept.append(line)

    requirements_file.write_text("\n".join(kept) + "\n")

    if dropped:
        print("\nKept Colab's own versions of:")
        print("    " + ", ".join(sorted(dropped)))


def synchronize_environment(
    requirements_file: Path,
) -> None:
    """
    Install the exact pinned requirements into Colab's existing
    system Python environment.

    --system is intentional because Colab's Jupyter kernel uses
    the system Python environment.

    We use `pip install`, not `pip sync`: sync REMOVES every package
    not in the requirements file, which would uninstall Colab's own
    packages (e.g. google-colab, needed for drive.mount) and break the
    runtime. install only adds/upgrades the pinned course packages.

    --no-deps means we install exactly the (already filtered) list and
    never pull a Colab-owned package (e.g. IPython) back in as a transitive
    dependency. The exported lockfile already contains the full closure, so
    nothing needed is missing.
    """

    print("\n" + "=" * 60)
    print("Synchronizing Python environment")
    print("=" * 60)

    run_command(
        [
            "uv",
            "pip",
            "install",
            "--system",
            "--no-deps",
            "-r",
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
    Download the course-data zip from a public Google Drive link and
    extract it into the repository (REPO_DIR/data).

    Uses gdown (handles Drive's large-file confirm token) — no Drive
    mount, so the notebook never gets access to anyone's Drive.

    Skipped if the link is unconfigured or the data is already present.
    """

    import zipfile

    print("\n" + "=" * 60)
    print("Course data")
    print("=" * 60)

    if not LARGE_DATA_URL or "PUT_ZIP_FILE_ID_HERE" in LARGE_DATA_URL:
        print("No course-data link configured (LARGE_DATA_URL).")
        print("Skipping data download.")
        return

    if PROCESSED_DATA_DIR.exists() and any(PROCESSED_DATA_DIR.iterdir()):
        print("Data already present:")
        print(PROCESSED_DATA_DIR)
        print("\nSkipping download.")
        return

    # gdown is preinstalled on Colab, but ensure it exists anyway.
    run_command([sys.executable, "-m", "pip", "install", "--quiet", "gdown"])
    import gdown

    print("Downloading course data (this can take a few minutes):")
    print(LARGE_DATA_URL)

    gdown.download(
        url=LARGE_DATA_URL,
        output=str(LARGE_DATA_FILE),
        quiet=False,
        fuzzy=True,
    )

    if not LARGE_DATA_FILE.exists():
        raise RuntimeError(
            "gdown finished but the zip is missing. Check that the link is "
            "public ('Anyone with the link') and points to the data zip."
        )

    print("\nExtracting into:")
    print(REPO_DIR)

    with zipfile.ZipFile(LARGE_DATA_FILE) as archive:
        archive.extractall(REPO_DIR)

    LARGE_DATA_FILE.unlink(missing_ok=True)

    if not PROCESSED_DATA_DIR.exists():
        raise RuntimeError(
            f"Extraction finished but {PROCESSED_DATA_DIR} is missing. "
            "The zip must contain a top-level `data/` folder "
            "(make it with: zip -r course_data.zip data)."
        )

    print("\nCourse data ready:")
    print(DATA_DIR)


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
