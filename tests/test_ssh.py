"""End to end test of the SSH transport against a small paramiko git server."""

from __future__ import annotations

import io
import shlex
import socket
import subprocess
import threading

from dulwich.repo import Repo
import paramiko
import pytest
import pytest_socket

from custom_components.bastion.gitsync import repo as gitrepo
from custom_components.bastion.gitsync.collector import SourceFile
from custom_components.bastion.gitsync.remote import (
    HostKeyMismatch,
    RemoteContext,
    RemoteError,
    generate_ssh_keypair,
    host_key_line,
    parse_remote,
)


class _Server(paramiko.ServerInterface):
    def __init__(self, allowed: str) -> None:
        self.allowed = allowed
        self.command: bytes | None = None
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return "publickey"

    def check_auth_publickey(self, username, key):
        return paramiko.AUTH_SUCCESSFUL if key.get_base64() == self.allowed else paramiko.AUTH_FAILED

    def check_channel_exec_request(self, channel, command):
        self.command = command
        self.event.set()
        return True

    def check_channel_env_request(self, channel, name, value):
        return True


def _serve(sock: socket.socket, host_key: paramiko.PKey, allowed: str, stop: threading.Event) -> None:
    sock.settimeout(0.5)
    while not stop.is_set():
        try:
            conn, _ = sock.accept()
        except TimeoutError:
            continue
        threading.Thread(target=_handle, args=(conn, host_key, allowed), daemon=True).start()


def _handle(conn: socket.socket, host_key: paramiko.PKey, allowed: str) -> None:
    transport = paramiko.Transport(conn)
    transport.add_server_key(host_key)
    server = _Server(allowed)
    try:
        transport.start_server(server=server)
    except paramiko.SSHException:
        return
    chan = transport.accept(10)
    if chan is None or not server.event.wait(10):
        transport.close()
        return
    proc = subprocess.Popen(shlex.split(server.command.decode()), stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def pump_out() -> None:
        while data := proc.stdout.read1(65536):
            chan.sendall(data)

    out = threading.Thread(target=pump_out, daemon=True)
    out.start()
    while True:
        data = chan.recv(65536)
        if not data:
            break
        try:
            proc.stdin.write(data)
            proc.stdin.flush()
        except BrokenPipeError:
            break
    try:
        proc.stdin.close()
    except BrokenPipeError:
        pass
    proc.wait(10)
    out.join(5)
    proc.stdout.close()
    try:
        chan.send_exit_status(proc.returncode)
        chan.close()
    except (EOFError, OSError, paramiko.SSHException):
        pass
    transport.close()


@pytest.fixture
def ssh_git(tmp_path):
    # The Home Assistant test plugin blocks sockets; this test needs a local server.
    pytest_socket.enable_socket()
    remote = tmp_path / "remote.git"
    Repo.init_bare(str(remote), mkdir=True).close()
    private, public = generate_ssh_keypair("bastion@test")
    host_key = paramiko.Ed25519Key.from_private_key(io.StringIO(generate_ssh_keypair("host")[0]))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    stop = threading.Event()
    thread = threading.Thread(target=_serve, args=(sock, host_key, public.split()[1], stop), daemon=True)
    thread.start()
    yield {"remote": remote, "port": sock.getsockname()[1], "private": private, "host_key": host_key}
    stop.set()
    thread.join(2)
    sock.close()
    pytest_socket.socket_allow_hosts(["127.0.0.1"])
    pytest_socket.disable_socket(allow_unix_socket=True)


def _ctx(ssh_git, private: str, host_key: str = "", seen: dict | None = None) -> RemoteContext:
    url = f"ssh://git@127.0.0.1:{ssh_git['port']}{ssh_git['remote']}"

    def on_new(line: str, fp: str) -> None:
        if seen is not None:
            seen["line"] = line

    return RemoteContext(
        spec=parse_remote(url), auth="ssh", private_key=private, host_key=host_key, on_new_host_key=on_new
    )


def test_ssh_push_fetch_and_host_key_pinning(ssh_git, tmp_path) -> None:
    seen: dict = {}
    ctx = _ctx(ssh_git, ssh_git["private"], seen=seen)
    local = gitrepo.open_repo(str(tmp_path / "local.git"))
    assert gitrepo.fetch(ctx, local, "main") is None
    assert seen["line"] == host_key_line(ssh_git["host_key"])

    snap = gitrepo.build_snapshot(
        local,
        None,
        [SourceFile("homeassistant/configuration.yaml", "config", data=b"a: 1\n")],
        None,
        salt="",
        meta={},
        readme=None,
    )
    sha = gitrepo.create_commit(local, "main", snap.tree_id, None, author="T <t@t>", message="ssh")
    pinned = _ctx(ssh_git, ssh_git["private"], host_key=seen["line"])
    gitrepo.push(pinned, local, "main", sha)
    local.close()
    remote = Repo(str(ssh_git["remote"]))
    assert remote.refs[b"refs/heads/main"] == sha
    remote.close()

    fresh = gitrepo.open_repo(str(tmp_path / "fresh.git"))
    assert gitrepo.fetch(pinned, fresh, "main") == sha
    fresh.close()

    other = paramiko.Ed25519Key.from_private_key(io.StringIO(generate_ssh_keypair("other")[0]))
    wrong = _ctx(ssh_git, ssh_git["private"], host_key=host_key_line(other))
    probe = gitrepo.open_repo(str(tmp_path / "probe.git"))
    with pytest.raises((HostKeyMismatch, RemoteError)):
        gitrepo.fetch(wrong, probe, "main")
    probe.close()


def test_ssh_wrong_key_is_rejected(ssh_git, tmp_path) -> None:
    other_private, _ = generate_ssh_keypair("intruder")
    local = gitrepo.open_repo(str(tmp_path / "local.git"))
    with pytest.raises(RemoteError) as err:
        gitrepo.fetch(_ctx(ssh_git, other_private), local, "main")
    assert err.value.reason in ("auth_failed", "cannot_connect")
    local.close()
