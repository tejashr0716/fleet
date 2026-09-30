"""Safely apply this complete rebuild to a clean clone; never pushes or force-pushes."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Clean clone of tejashr0716/fleet")
    parser.add_argument(
        "--apply", action="store_true", help="Create local backup/rebuild branches and copy files"
    )
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = Path(args.target).resolve()
    manifest = json.loads((source / "SOURCE_MANIFEST.json").read_text())
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise SystemExit("Extract the package separately from the target repository.")
    remote = git(target, "remote", "get-url", "origin")
    if remote.removesuffix(".git") not in {
        "https://github.com/tejashr0716/fleet",
        "git@github.com:tejashr0716/fleet",
    }:
        raise SystemExit("Refusing to modify a repository other than tejashr0716/fleet.")
    if git(target, "status", "--porcelain"):
        raise SystemExit("Target has local changes. Commit/back them up before proceeding.")
    if git(target, "rev-parse", "HEAD") != manifest["expected_base_revision"]:
        raise SystemExit(
            "Target HEAD changed since this rebuild's base. Review/rebase manually; no files changed."
        )
    paths = list(manifest["files"]) + manifest["delete_paths"] + ["SOURCE_MANIFEST.json"]
    for relative in paths:
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not (target / relative).resolve().is_relative_to(target)
        ):
            raise SystemExit("Unsafe path or external symlink in target; no files changed.")
    for relative, expected in manifest["files"].items():
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Source checksum changed: {relative}. Re-verify before publishing.")
    print(
        f"Verified {len(manifest['files'])} source files; {len(manifest['delete_paths'])} obsolete files to remove."
    )
    if not args.apply:
        print("Dry run only. Add --apply after reviewing; no files or branches changed.")
        return
    backup = "backup/fleet-before-rebuild-2026-09-30"
    branch = "rebuild/fleet-interview-ready-2026-09-30"
    existing = set(git(target, "branch", "--format=%(refname:short)").splitlines())
    if backup in existing or branch in existing:
        raise SystemExit("A safety/rebuild branch already exists. Review it before running again.")
    git(target, "branch", backup)
    git(target, "switch", "-c", branch)
    for relative in manifest["delete_paths"]:
        (target / relative).unlink(missing_ok=True)
    for relative in [*manifest["files"], "SOURCE_MANIFEST.json"]:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)
    print("Copied the rebuild onto a new LOCAL branch. Nothing was pushed; main was not modified.")
    print(
        "Review with git diff, then commit/publish through your normal Git credentials or GitHub Desktop."
    )


if __name__ == "__main__":
    main()
