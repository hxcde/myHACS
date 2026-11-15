"""Git remote handling: URL parsing, SSH transport with pinned host keys.

Everything in here is synchronous and must run in an executor.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import io
import re
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dulwich.client import GitClient, SSHGitClient, SSHVendor, get_transport_and_path
import paramiko

SSH_TIMEOUT = 20

# Published fingerprints, used in addition to trust on first use.
# https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
PINNED_FINGERPRINTS: dict[str, set[str]] = {
    "github.com": {
        "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU",
        "SHA256:p2QAMXNIC1TJYWeIOttrVc98/R1BUFWu3/LiyKgUfQM",
        "SHA256:uNiVztksCsDhcc0u9e8BujQXVUpKZIDTMczCvj3tD2s",
    },
}

_SCP_RE = re.compile(r"^(?:(?P<user>[^@/]+)@)?(?P<host>[^:/]+):(?P<path>(?!/).+)$")


class RemoteError(Exception):
    """Generic remote failure with a user facing reason key."""

    def __init__(self, reason: str, detail: str = "") -> None:
        """Init with a reason key such as 'auth_failed'."""
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class HostKeyMismatch(RemoteError):
    """The SSH host key differs from the pinned one."""


@dataclass(frozen=True, slots=True)
class RemoteSpec:
    """Parsed remote location."""

    kind: str  # ssh | https | http | local
    url: str
    host: str = ""
    port: int | None = None
    user: str = ""
    path: str = ""

    @property
    def https_url(self) -> str | None:
        """Anonymous HTTPS URL used to check whether the repo is public."""
        if self.kind in ("https", "http"):
            parts = urlsplit(self.url)
            netloc = parts.hostname or ""
            if parts.port:
                netloc += f":{parts.port}"
            return f"{parts.scheme}://{netloc}{parts.path}"
        if self.kind == "ssh" and self.host:
            path = self.path.lstrip("/")
            return f"https://{self.host}/{path}"
        return None

    @property
    def display(self) -> str:
        """URL without credentials for logs and the UI."""
        if self.kind in ("https", "http"):
            parts = urlsplit(self.url)
            netloc = parts.hostname or ""
            if parts.port:
                netloc += f":{parts.port}"
            return f"{parts.scheme}://{netloc}{parts.path}"
        return self.url


def parse_remote(url: str) -> RemoteSpec:
    """Parse a git remote URL (scp like, ssh://, https:// or a local path)."""
    url = url.strip()
    if not url:
        raise RemoteError("invalid_url")
    if url.startswith(("https://", "http://")):
        parts = urlsplit(url)
        if not parts.hostname or not parts.path.strip("/"):
            raise RemoteError("invalid_url")
        return RemoteSpec(
            kind=parts.scheme,
            url=url,
            host=parts.hostname,
            port=parts.port,
            path=parts.path,
        )
    if url.startswith("ssh://"):
        parts = urlsplit(url)
        if not parts.hostname or not parts.path.strip("/"):
            raise RemoteError("invalid_url")
        return RemoteSpec(
            kind="ssh",
            url=url,
            host=parts.hostname,
            port=parts.port,
            user=parts.username or "git",
            path=parts.path,
        )
    if url.startswith("file://"):
        return RemoteSpec(kind="local", url=url, path=url[len("file://") :])
    if url.startswith("/"):
        return RemoteSpec(kind="local", url=url, path=url)
    if (m := _SCP_RE.match(url)) is not None:
        return RemoteSpec(
            kind="ssh",
            url=url,
            host=m.group("host"),
            user=m.group("user") or "git",
            path=m.group("path"),
        )
    raise RemoteError("invalid_url")


# --------------------------------------------------------------------- keys
def generate_ssh_keypair(comment: str) -> tuple[str, str]:
    """Generate an ed25519 key pair. Returns (private OpenSSH PEM, public line)."""
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode()
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
    comment = re.sub(r"[^A-Za-z0-9@._\-]", "-", comment)[:64]
    return private, f"{public} {comment}"


def load_private_key(pem: str) -> paramiko.PKey:
    """Load a private key in OpenSSH or PEM format."""
    errors: list[str] = []
    for key_cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_cls.from_private_key(io.StringIO(pem))
        except (paramiko.SSHException, ValueError) as err:
            errors.append(str(err))
    raise RemoteError("invalid_key", "; ".join(errors))


def fingerprint(key: paramiko.PKey) -> str:
    """OpenSSH style SHA256 fingerprint."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def host_key_line(key: paramiko.PKey) -> str:
    """'type base64' representation stored in the options."""
    return f"{key.get_name()} {key.get_base64()}"


_ALGOS_FOR_KEY_TYPE = {
    "ssh-ed25519": {"ssh-ed25519"},
    "ecdsa-sha2-nistp256": {"ecdsa-sha2-nistp256"},
    "ecdsa-sha2-nistp384": {"ecdsa-sha2-nistp384"},
    "ecdsa-sha2-nistp521": {"ecdsa-sha2-nistp521"},
    "ssh-rsa": {"rsa-sha2-512", "rsa-sha2-256"},
}


class _HostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Accept only the pinned host key, or record it on first use."""

    def __init__(self, expected: str | None, on_new: Callable[[str, str], None] | None) -> None:
        self._expected = expected
        self._on_new = on_new

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        host = hostname.strip("[]").split("]:")[0]
        line = host_key_line(key)
        fp = fingerprint(key)
        pinned = PINNED_FINGERPRINTS.get(host)
        if pinned is not None and fp not in pinned:
            raise HostKeyMismatch("host_key_mismatch", f"{host} {fp} not in published fingerprints")
        if self._expected:
            if line != self._expected:
                raise HostKeyMismatch("host_key_mismatch", f"{host} presented {fp}")
            return
        if self._on_new is not None:
            self._on_new(line, fp)


class _ChannelWrapper:
    """File like wrapper of a paramiko channel, as dulwich expects."""

    def __init__(self, client: paramiko.SSHClient, channel: paramiko.Channel) -> None:
        self._client = client
        self._channel = channel
        self._stderr = io.BytesIO()

    def read(self, n: int | None = None) -> bytes:
        if n is None:
            chunks = []
            while chunk := self._channel.recv(65536):
                chunks.append(chunk)
            return b"".join(chunks)
        buf = bytearray()
        while len(buf) < n:
            chunk = self._channel.recv(n - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def write(self, data: bytes) -> int:
        self._channel.sendall(data)
        return len(data)

    def can_read(self) -> bool:
        return self._channel.recv_ready() or self._channel.exit_status_ready()

    @property
    def stderr(self) -> io.BytesIO:
        while self._channel.recv_stderr_ready():
            self._stderr.write(self._channel.recv_stderr(65536))
        self._stderr.seek(0)
        return self._stderr

    def close(self, timeout: int | None = None) -> None:
        try:
            self._channel.close()
        finally:
            self._client.close()


class BastionSSHVendor(SSHVendor):
    """SSH vendor based on paramiko with an in memory key and pinned host key."""

    def __init__(
        self,
        pkey: paramiko.PKey,
        expected_host_key: str | None,
        on_new_host_key: Callable[[str, str], None] | None = None,
    ) -> None:
        """Init the vendor."""
        self._pkey = pkey
        self._expected = expected_host_key or None
        self._on_new = on_new_host_key

    def run_command(  # type: ignore[override]
        self,
        host: str,
        command: bytes | str,
        username: str | None = None,
        port: int | None = None,
        password: str | None = None,
        key_filename: str | None = None,
        ssh_command: str | None = None,
        protocol_version: int | None = None,
        **kwargs: Any,
    ) -> _ChannelWrapper:
        """Open a session and run the git command."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(_HostKeyPolicy(self._expected, self._on_new))
        disabled: dict[str, list[str]] | None = None
        if self._expected:
            key_type = self._expected.split(" ", 1)[0]
            allowed = _ALGOS_FOR_KEY_TYPE.get(key_type, {key_type})
            disabled = {
                "keys": [k for k in paramiko.Transport._preferred_keys if k not in allowed]  # noqa: SLF001
            }
        try:
            client.connect(
                host,
                port=port or 22,
                username=username or "git",
                pkey=self._pkey,
                timeout=SSH_TIMEOUT,
                banner_timeout=SSH_TIMEOUT,
                auth_timeout=SSH_TIMEOUT,
                allow_agent=False,
                look_for_keys=False,
                disabled_algorithms=disabled,
            )
        except HostKeyMismatch:
            client.close()
            raise
        except paramiko.AuthenticationException as err:
            client.close()
            raise RemoteError("auth_failed", str(err)) from err
        except (TimeoutError, paramiko.SSHException, OSError) as err:
            client.close()
            raise RemoteError("cannot_connect", str(err)) from err
        transport = client.get_transport()
        assert transport is not None
        channel = transport.open_session(timeout=SSH_TIMEOUT)
        if protocol_version and protocol_version > 1:
            channel.set_environment_variable("GIT_PROTOCOL", f"version={protocol_version}")
        cmd = command.decode() if isinstance(command, bytes) else command
        channel.exec_command(cmd)
        return _ChannelWrapper(client, channel)


@dataclass(slots=True)
class RemoteContext:
    """Everything needed to talk to the remote."""

    spec: RemoteSpec
    auth: str  # ssh | token | none
    username: str = ""
    token: str = ""
    private_key: str = ""
    host_key: str = ""
    on_new_host_key: Callable[[str, str], None] | None = None

    def client(self) -> tuple[GitClient, str]:
        """Return a dulwich client and the remote path."""
        spec = self.spec
        if spec.kind == "ssh":
            if not self.private_key:
                raise RemoteError("missing_key")
            vendor = BastionSSHVendor(load_private_key(self.private_key), self.host_key, self.on_new_host_key)
            client = SSHGitClient(spec.host, port=spec.port, username=spec.user, vendor=vendor)
            return client, spec.path
        if spec.kind in ("https", "http"):
            username = None
            password = None
            if self.auth == "token" and self.token:
                username = self.username or "x-access-token"
                password = self.token
            # Credentials must not be part of the URL (they would end up in logs).
            return get_transport_and_path(spec.display, username=username, password=password)
        return get_transport_and_path(spec.path)


def anonymous_refs_url(spec: RemoteSpec) -> str | None:
    """URL that answers 200 for anonymous clones of a public repository."""
    base = spec.https_url
    if base is None:
        return None
    base = base.rstrip("/")
    if not base.endswith(".git"):
        base += ".git"
    return base + "/info/refs?service=git-upload-pack"


def safe_branch(branch: str) -> str:
    """Validate a branch name (subset of git check-ref-format)."""
    branch = branch.strip() or "main"
    if (
        branch.startswith(("-", "/"))
        or branch.endswith(("/", ".", ".lock"))
        or ".." in branch
        or "//" in branch
        or "@{" in branch
        or re.search(r"[\x00-\x20~^:?*\[\\\x7f]", branch)
    ):
        raise RemoteError("invalid_branch")
    return branch
