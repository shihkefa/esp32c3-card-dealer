"""Package the current release and verify each archived file against the working tree."""
import hashlib
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    release = root / "V1.0.0"
    output = root / f"發牌機_完整專案_{release.name}.zip"
    manifest = release / "SHA256SUMS.txt"
    excluded = {".git", ".build", ".build-temp", ".build-tests", "__pycache__", "generated", "node_modules", ".venv", ".pytest_cache"}
    files = sorted(
        path for path in release.rglob("*")
        if path.is_file() and path != manifest and not path.name.startswith(("~$", ".~lock."))
        and not excluded.intersection(path.relative_to(release).parts)
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )
    digests = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest.write_bytes("".join(f"{v}  {p.relative_to(release).as_posix()}\n" for p, v in digests.items()).encode())
    digests[manifest] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with tempfile.NamedTemporaryFile(dir=root, suffix=".tmp.zip", delete=False) as handle:
        candidate = Path(handle.name)
    try:
        with ZipFile(candidate, "w", ZIP_DEFLATED, compresslevel=9) as archive:
            for path in digests:
                archive.write(path, path.relative_to(root).as_posix())
        with ZipFile(candidate) as archive:
            assert len(archive.infolist()) == len(digests)
            for path, expected in digests.items():
                if hashlib.sha256(archive.read(path.relative_to(root).as_posix())).hexdigest() != expected:
                    raise ValueError(f"Archive checksum mismatch for {path}")
        candidate.replace(output)
    finally:
        candidate.unlink(missing_ok=True)
    print(f"{len(digests)} files verified, {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
