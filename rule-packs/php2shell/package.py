#!/usr/bin/env python3
"""Produce a deterministic publication archive and SHA-256 checksum."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
NAME = "socfortress-php2shell-1.0.0"


def build():
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and not any(part in {'dist', '__pycache__'} for part in p.relative_to(ROOT).parts)
                   and p.name != 'SHA256SUMS')
    sums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
    (ROOT / 'SHA256SUMS').write_text(sums)
    files.append(ROOT / 'SHA256SUMS')
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(files):
            data = path.read_bytes()
            info = tarfile.TarInfo(f'{NAME}/{path.relative_to(ROOT).as_posix()}')
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
    dest = ROOT / 'dist'
    dest.mkdir(exist_ok=True)
    archive = dest / f'{NAME}.tar.gz'
    archive.write_bytes(gzip.compress(out.getvalue(), mtime=0))
    (dest / f'{NAME}.tar.gz.sha256').write_text(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
    print(archive)


if __name__ == '__main__':
    build()
