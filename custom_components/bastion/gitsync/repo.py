"""Synchronous git operations on a local bare repository (dulwich).

The local repository is a cache of the remote. Every snapshot is a full
picture of the configuration, so a new commit never needs a merge: it is
always created on top of the newest remote head.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import difflib
import json
import os
import time
from typing import Any

from dulwich.diff_tree import tree_changes
from dulwich.errors import GitProtocolError, HangupException, NotGitRepository
from dulwich.index import commit_tree
from dulwich.objects import Blob, Commit
from dulwich.repo import Repo

from ..crypto import DecryptionError, FileCipher, kdf_params
from ..secret_scan import is_text_path, scan_bytes
from .collector import ENC_SUFFIX, MANAGED_PREFIXES, MANIFEST_PATH, SourceFile
from .remote import RemoteContext, RemoteError

FILE_MODE = 0o100644
SYMLINK_MODE = 0o120000
MANIFEST_FORMAT = 1
MAX_DIFF_BYTES = 200_000


@dataclass(slots=True)
class SnapshotResult:
    """Outcome of building a snapshot tree."""

    tree_id: bytes
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    encrypted: list[str] = field(default_factory=list)
    auto_encrypted: list[str] = field(default_factory=list)
    skipped_secrets: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """True if anything differs from the parent."""
        return bool(self.added or self.modified or self.deleted)


def open_repo(path: str) -> Repo:
    """Open or create the local bare repository."""
    if os.path.isdir(path):
        try:
            return Repo(path)
        except NotGitRepository:
            pass
    os.makedirs(path, exist_ok=True)
    return Repo.init_bare(path)


def _ref(branch: str) -> bytes:
    return f"refs/heads/{branch}".encode()


def _remote_ref(branch: str) -> bytes:
    return f"refs/remotes/origin/{branch}".encode()


def local_head(repo: Repo, branch: str) -> bytes | None:
    """Head of the local branch."""
    return repo.refs.as_dict().get(_ref(branch))


def remote_head(repo: Repo, branch: str) -> bytes | None:
    """Last known head of the remote branch."""
    return repo.refs.as_dict().get(_remote_ref(branch))


def _wrap_remote_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RemoteError:
            raise
        except (GitProtocolError, HangupException) as err:
            text = str(err)
            lower = text.lower()
            if any(w in lower for w in ("auth", "permission", "denied", "401", "403")):
                raise RemoteError("auth_failed", text) from err
            if "not found" in lower or "404" in lower or "does not appear" in lower:
                raise RemoteError("repo_not_found", text) from err
            raise RemoteError("protocol_error", text) from err
        except (OSError, TimeoutError) as err:
            raise RemoteError("cannot_connect", str(err)) from err

    return wrapper


@_wrap_remote_errors
def fetch(ctx: RemoteContext, repo: Repo, branch: str) -> bytes | None:
    """Fetch the branch. Returns the remote head or None for an empty remote."""
    client, path = ctx.client()
    ref = _ref(branch)

    def determine_wants(refs: dict[bytes, bytes], depth: int | None = None) -> list[bytes]:
        sha = refs.get(ref)
        if sha is None or sha in repo.object_store:
            return []
        return [sha]

    result = client.fetch(path, repo, determine_wants=determine_wants)
    refs = dict(result.refs or {})
    sha = refs.get(ref)
    if sha is not None:
        repo.refs[_remote_ref(branch)] = sha
    elif _remote_ref(branch) in repo.refs:
        del repo.refs[_remote_ref(branch)]
    return sha


@_wrap_remote_errors
def list_remote_refs(ctx: RemoteContext) -> dict[bytes, bytes]:
    """ls-remote, used to test the connection."""
    client, path = ctx.client()
    result = client.get_refs(path.encode() if isinstance(path, str) else path)
    return dict(getattr(result, "refs", result) or {})


@_wrap_remote_errors
def push(ctx: RemoteContext, repo: Repo, branch: str, sha: bytes) -> None:
    """Push sha to the remote branch (fast forward only)."""
    client, path = ctx.client()
    ref = _ref(branch)

    def update_refs(refs: dict[bytes, bytes]) -> dict[bytes, bytes]:
        return {ref: sha}

    def generate_pack_data(have, want, *, ofs_delta: bool = False, progress=None):
        return repo.generate_pack_data(set(have), set(want), progress=progress, ofs_delta=ofs_delta)

    result = client.send_pack(
        path.encode() if isinstance(path, str) else path,
        update_refs,
        generate_pack_data=generate_pack_data,
    )
    status = getattr(result, "ref_status", None) or {}
    if (error := status.get(ref)) is not None:
        raise RemoteError("push_rejected", str(error))
    repo.refs[_remote_ref(branch)] = sha


def is_ancestor(repo: Repo, ancestor: bytes, descendant: bytes, limit: int = 5000) -> bool:
    """True if ancestor is reachable from descendant."""
    if ancestor == descendant:
        return True
    seen: set[bytes] = set()
    stack = [descendant]
    while stack and len(seen) < limit:
        sha = stack.pop()
        if sha in seen or sha not in repo.object_store:
            continue
        seen.add(sha)
        if sha == ancestor:
            return True
        commit = repo[sha]
        if isinstance(commit, Commit):
            stack.extend(commit.parents)
    return False


def choose_base(repo: Repo, branch: str) -> bytes | None:
    """Commit a new snapshot builds upon."""
    local = local_head(repo, branch)
    remote = remote_head(repo, branch)
    if remote is None:
        return local
    if local is None:
        return remote
    if is_ancestor(repo, remote, local):
        return local
    # The remote moved on (other instance or manual commit): it wins.
    return remote


def tree_files(repo: Repo, tree_id: bytes | None) -> dict[str, tuple[int, bytes]]:
    """Map path -> (mode, blob sha) for all files of a tree."""
    if tree_id is None:
        return {}
    out: dict[str, tuple[int, bytes]] = {}
    for entry in repo.object_store.iter_tree_contents(tree_id):
        out[entry.path.decode("utf-8", "surrogateescape")] = (entry.mode, entry.sha)
    return out


def commit_tree_id(repo: Repo, commit_sha: bytes | None) -> bytes | None:
    """Tree of a commit."""
    if commit_sha is None:
        return None
    commit = repo[commit_sha]
    assert isinstance(commit, Commit)
    return commit.tree


def read_blob(repo: Repo, sha: bytes) -> bytes:
    """Raw blob content."""
    blob = repo[sha]
    assert isinstance(blob, Blob)
    return blob.data


def read_manifest(repo: Repo, files: dict[str, tuple[int, bytes]]) -> dict[str, Any]:
    """Manifest of a tree, empty dict if missing or broken."""
    if (entry := files.get(MANIFEST_PATH)) is None:
        return {}
    try:
        data = json.loads(read_blob(repo, entry[1]))
    except (ValueError, KeyError):
        return {}
    return data if isinstance(data, dict) else {}


def build_snapshot(
    repo: Repo,
    parent: bytes | None,
    files: Iterable[SourceFile],
    cipher: FileCipher | None,
    *,
    salt: str,
    meta: dict[str, Any],
    readme: bytes | None,
) -> SnapshotResult:
    """Create blobs and the tree of a snapshot. Nothing is committed."""
    parent_tree = commit_tree_id(repo, parent)
    parent_files = tree_files(repo, parent_tree)
    parent_manifest = read_manifest(repo, parent_files)
    parent_macs: dict[str, str] = parent_manifest.get("encrypted", {}) if parent_manifest.get("salt") == salt else {}

    entries: dict[str, tuple[int, bytes]] = {}
    # Keep everything Bastion does not manage.
    for path, value in parent_files.items():
        if not path.startswith(MANAGED_PREFIXES):
            entries[path] = value

    macs: dict[str, str] = {}
    encrypted: list[str] = []
    auto_encrypted: list[str] = []
    skipped: list[str] = []
    store = repo.object_store

    for src in files:
        try:
            data = src.read()
        except OSError:
            continue
        must_encrypt = src.encrypt
        if not must_encrypt and is_text_path(src.repo_path) and scan_bytes(data):
            must_encrypt = True
            auto_encrypted.append(src.repo_path)
        if must_encrypt:
            if cipher is None:
                skipped.append(src.repo_path)
                continue
            enc_path = src.repo_path + ENC_SUFFIX
            mac = cipher.mac(src.repo_path, data)
            macs[enc_path] = mac
            encrypted.append(src.repo_path)
            previous = parent_files.get(enc_path)
            if previous is not None and parent_macs.get(enc_path) == mac:
                entries[enc_path] = previous
                continue
            blob = Blob.from_string(cipher.encrypt(src.repo_path, data))
        else:
            blob = Blob.from_string(data)
            enc_path = src.repo_path
        store.add_object(blob)
        entries[enc_path] = (FILE_MODE, blob.id)

    manifest = {
        "format": MANIFEST_FORMAT,
        **meta,
        "salt": salt if cipher is not None else None,
        "kdf": kdf_params() if cipher is not None else None,
        "encrypted": dict(sorted(macs.items())),
    }
    manifest_blob = Blob.from_string(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"
    )
    store.add_object(manifest_blob)
    entries[MANIFEST_PATH] = (FILE_MODE, manifest_blob.id)
    if readme is not None and "README.md" not in entries:
        readme_blob = Blob.from_string(readme)
        store.add_object(readme_blob)
        entries["README.md"] = (FILE_MODE, readme_blob.id)

    tree_id = commit_tree(
        store, [(p.encode("utf-8", "surrogateescape"), sha, mode) for p, (mode, sha) in sorted(entries.items())]
    )
    result = SnapshotResult(
        tree_id=tree_id,
        encrypted=sorted(encrypted),
        auto_encrypted=sorted(auto_encrypted),
        skipped_secrets=sorted(skipped),
    )
    for path, value in entries.items():
        if path == MANIFEST_PATH:
            continue
        old = parent_files.get(path)
        if old is None:
            result.added.append(path)
        elif old[1] != value[1]:
            result.modified.append(path)
    for path in parent_files:
        if path not in entries and path != MANIFEST_PATH:
            result.deleted.append(path)
    result.added.sort()
    result.modified.sort()
    result.deleted.sort()
    if parent_tree == tree_id:
        result.added.clear()
        result.modified.clear()
        result.deleted.clear()
    return result


def create_commit(
    repo: Repo,
    branch: str,
    tree_id: bytes,
    parent: bytes | None,
    *,
    author: str,
    message: str,
) -> bytes:
    """Write a commit object and move the local branch."""
    commit = Commit()
    commit.tree = tree_id
    commit.parents = [parent] if parent else []
    commit.author = commit.committer = author.encode("utf-8")
    now = int(time.time())
    offset = -time.timezone if time.localtime().tm_isdst == 0 else -time.altzone
    commit.author_time = commit.commit_time = now
    commit.author_timezone = commit.commit_timezone = offset
    commit.encoding = b"UTF-8"
    commit.message = message.encode("utf-8")
    repo.object_store.add_object(commit)
    repo.refs[_ref(branch)] = commit.id
    return commit.id


def history(repo: Repo, head: bytes | None, limit: int = 100) -> list[dict[str, Any]]:
    """Commit list, newest first."""
    if head is None or head not in repo.object_store:
        return []
    out: list[dict[str, Any]] = []
    for entry in repo.get_walker(include=[head], max_entries=limit):
        commit = entry.commit
        message = commit.message.decode("utf-8", "replace")
        parent_tree = commit_tree_id(repo, commit.parents[0]) if commit.parents else None
        changes = 0
        try:
            for change in tree_changes(repo.object_store, parent_tree, commit.tree):
                path = (change.new.path if change.new and change.new.path else change.old.path) or b""
                if path != MANIFEST_PATH.encode():
                    changes += 1
        except KeyError:
            changes = -1
        out.append(
            {
                "sha": commit.id.decode(),
                "short": commit.id.decode()[:8],
                "summary": message.splitlines()[0] if message else "",
                "message": message,
                "author": commit.author.decode("utf-8", "replace"),
                "time": commit.commit_time,
                "changes": changes,
                "available": True,
            }
        )
    return out


def commit_changes(repo: Repo, sha: bytes) -> list[dict[str, str]]:
    """Files changed by a commit compared to its parent."""
    commit = repo[sha]
    assert isinstance(commit, Commit)
    parent_tree = commit_tree_id(repo, commit.parents[0]) if commit.parents else None
    out = []
    for change in tree_changes(repo.object_store, parent_tree, commit.tree):
        path = (change.new.path if change.new and change.new.path else change.old.path) or b""
        if path == MANIFEST_PATH.encode():
            continue
        out.append({"type": change.type, "path": path.decode("utf-8", "replace")})
    return out


def decode_entry(
    repo: Repo,
    path: str,
    sha: bytes,
    cipher: FileCipher | None,
) -> tuple[str, bytes]:
    """Return (original repo path, plaintext) of a tree entry."""
    data = read_blob(repo, sha)
    if path.endswith(ENC_SUFFIX):
        original = path[: -len(ENC_SUFFIX)]
        if cipher is None:
            raise DecryptionError("passphrase required")
        return original, cipher.decrypt(original, data)
    return path, data


def unified_diff(old: bytes | None, new: bytes | None, path: str) -> str | None:
    """Text diff, None for binary or very large content."""
    for content in (old, new):
        if content is not None and (b"\x00" in content[:8192] or len(content) > MAX_DIFF_BYTES):
            return None
    old_lines = (old or b"").decode("utf-8", "replace").splitlines(keepends=True)
    new_lines = (new or b"").decode("utf-8", "replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", n=3))


def gc_local(repo: Repo) -> None:
    """Pack loose objects to keep the local cache small."""
    try:
        repo.object_store.pack_loose_objects()
    except (OSError, AttributeError):
        pass
