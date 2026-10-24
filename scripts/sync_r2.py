"""Mirror data/ to a Cloudflare R2 bucket.

jsDelivr refuses a GitHub repo over 50 MB ("Package size exceeded the
configured limit of 50 MB"), and data/ is far past that: any file it has not
cached yet can come back 403 or 404 at random. R2 serves the same tree, under
the same paths, with no size limit and no egress charge.

Keys keep the repo layout — data/books/fiqh/... stays data/books/fiqh/... — so
the app only swaps the base URL in front of the paths it already builds.

Only new or changed files are uploaded: a file whose MD5 matches the object's
ETag is skipped. Nothing on R2 is deleted unless --delete is passed.

Credentials come from .r2.env at the repo root (gitignored), never the command
line:

    R2_ACCOUNT_ID=...
    R2_ACCESS_KEY_ID=...
    R2_SECRET_ACCESS_KEY=...
    R2_BUCKET=...
    R2_PUBLIC_URL=https://pub-....r2.dev   # optional: checked after upload

Usage:
    python scripts/sync_r2.py --dry-run     # what would go up, no network
    python scripts/sync_r2.py               # upload new and changed files
    python scripts/sync_r2.py --delete      # also remove objects gone from data/
"""

import argparse
import hashlib
import mimetypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENV_FILE = ROOT / ".r2.env"

# Types the app reads. just_audio and LockCachingAudioSource go by the
# Content-Type for .m4a, so it is set rather than left to a guess.
CONTENT_TYPES = {
    ".json": "application/json; charset=utf-8",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".zip": "application/zip",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
}

# JSON includes catalogs and manifests that change in place, so it is held for
# an hour; everything else is replaced under a new name when it changes.
CACHE_JSON = "public, max-age=3600"
CACHE_OTHER = "public, max-age=86400"


def load_env():
    if not ENV_FILE.exists():
        sys.exit(f"missing {ENV_FILE.name} at the repo root")
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    missing = [
        k
        for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
        if not env.get(k)
    ]
    if missing:
        sys.exit(f"{ENV_FILE.name} is missing: {', '.join(missing)}")
    return env


def local_files():
    files = {}
    for path in sorted(DATA.rglob("*")):
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()] = path
    return files


def md5_of(path):
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type(path):
    suffix = path.suffix.lower()
    return CONTENT_TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def remote_etags(s3, bucket):
    etags = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="data/"):
        for obj in page.get("Contents", []):
            etags[obj["Key"]] = obj["ETag"].strip('"')
    return etags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    files = local_files()
    total = sum(p.stat().st_size for p in files.values())
    print(f"local: {len(files)} files, {total / 1024 / 1024:.1f} MB under data/")
    if args.dry_run:
        biggest = sorted(files.values(), key=lambda p: p.stat().st_size, reverse=True)[:5]
        for path in biggest:
            print(f"  {path.stat().st_size / 1024 / 1024:6.1f} MB  {path.relative_to(ROOT).as_posix()}  {content_type(path)}")
        return

    import boto3
    from botocore.config import Config

    env = load_env()
    bucket = env["R2_BUCKET"]
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )

    remote = remote_etags(s3, bucket)
    print(f"remote: {len(remote)} objects in {bucket}")

    to_upload = [key for key, path in files.items() if remote.get(key) != md5_of(path)]
    print(f"to upload: {len(to_upload)}")

    def upload(key):
        path = files[key]
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": content_type(path),
                "CacheControl": CACHE_JSON if path.suffix.lower() == ".json" else CACHE_OTHER,
            },
        )
        return key

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload, key): key for key in to_upload}
        for done, future in enumerate(as_completed(futures), 1):
            key = futures[future]
            try:
                future.result()
            except Exception as e:  # noqa: BLE001 — reported and counted, the rest carry on
                failed.append(key)
                print(f"  FAILED {key}: {e}")
            if done % 200 == 0 or done == len(to_upload):
                print(f"  {done}/{len(to_upload)}")

    if args.delete:
        gone = sorted(set(remote) - set(files))
        print(f"to delete: {len(gone)}")
        for start in range(0, len(gone), 1000):
            batch = gone[start : start + 1000]
            s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch]})

    if failed:
        sys.exit(f"{len(failed)} uploads failed")

    # A 200 is not proof — a stale body is a 200 too. Compare what the public
    # address actually serves against the file on disk.
    public = env.get("R2_PUBLIC_URL", "").rstrip("/")
    if public:
        import urllib.request

        for key in ("data/catalog.json", "data/azkar/audio/ruqyah.m4a"):
            # r2.dev answers Python-urllib's own user agent with 403; the app's
            # Dart and ExoPlayer agents get 200. Ask as the app does.
            request = urllib.request.Request(
                f"{public}/{key}", headers={"User-Agent": "Dart/3.9 (dart:io)"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                served = response.read()
            same = served == files[key].read_bytes()
            print(f"public {key}: {'matches' if same else 'DIFFERS'} ({len(served)} bytes)")
    print("done")


if __name__ == "__main__":
    main()
