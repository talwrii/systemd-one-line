#!/usr/bin/env python3
"""
systemd-one-line — create (and delete) systemd services and timers from the CLI.

AI-generated. You probably don't want to use it. And yet it exists.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def die(msg, code=1):
    print(f"systemd-one-line: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, check=True):
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=check,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        msg = f"command failed: {' '.join(cmd)}"
        if stderr:
            msg += f"\n  {stderr}"
        die(msg)


# ---------- unit dirs ----------

def system_unit_dir() -> Path:
    return Path("/etc/systemd/system")


def user_unit_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "systemd" / "user"


def unit_dir(user: bool) -> Path:
    d = user_unit_dir() if user else system_unit_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def systemctl(user: bool, *args, check=True):
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)
    return run(cmd, check=check)


# ---------- unit file rendering ----------

def render_service(exec_cmd: str, description: str, service_type: str,
                   user: str = None, extra: list = None) -> str:
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Service]",
        f"Type={service_type}",
        f"ExecStart={exec_cmd}",
    ]
    if user:
        lines.append(f"User={user}")
    if extra:
        lines.extend(extra)
    lines.append("")
    return "\n".join(lines)


def render_timer(description: str, on_calendar: str = None,
                 on_unit_active_sec: str = None,
                 persistent: bool = False) -> str:
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Timer]",
    ]
    if on_calendar:
        lines.append(f"OnCalendar={on_calendar}")
    if on_unit_active_sec:
        lines.append(f"OnUnitActiveSec={on_unit_active_sec}")
    if persistent:
        lines.append("Persistent=true")
    lines.extend([
        "",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ])
    return "\n".join(lines)


# ---------- file ops ----------

def write_unit(path: Path, content: str, user: bool):
    """Write a unit file. System mode falls back to sudo tee on permission error."""
    if user:
        path.write_text(content)
        return
    try:
        path.write_text(content)
    except PermissionError:
        p = subprocess.run(
            ["sudo", "tee", str(path)],
            input=content, text=True, capture_output=True,
        )
        if p.returncode != 0:
            die(f"couldn't write {path}: {p.stderr.strip()}")


def remove_unit(path: Path, user: bool):
    if not path.exists():
        return
    if user:
        path.unlink()
    else:
        run(["sudo", "rm", "-f", str(path)])


# ---------- subcommands ----------

def cmd_service(args):
    name = args.name
    if name.endswith(".service") or name.endswith(".timer"):
        die(f"--name should be bare ('{name.split('.')[0]}'), not include a suffix")

    udir = unit_dir(args.user)
    svc_path = udir / f"{name}.service"
    timer_path = udir / f"{name}.timer"

    has_timer = bool(args.on_calendar or args.on_unit_active_sec)

    if svc_path.exists() and not args.edit:
        die(f"{svc_path} already exists (pass --edit to overwrite)")

    if args.exec is None:
        die("--exec is required")

    description = args.description or f"{name} (managed by systemd-one-line)"

    service_body = render_service(
        exec_cmd=args.exec,
        description=description,
        service_type=args.type,
        user=args.run_as,
    )
    write_unit(svc_path, service_body, user=args.user)
    print(f"wrote {svc_path}", file=sys.stderr)

    if has_timer:
        timer_body = render_timer(
            description=f"Timer for {description}",
            on_calendar=args.on_calendar,
            on_unit_active_sec=args.on_unit_active_sec,
            persistent=args.persistent,
        )
        write_unit(timer_path, timer_body, user=args.user)
        print(f"wrote {timer_path}", file=sys.stderr)
    elif timer_path.exists() and args.edit:
        print(f"note: {timer_path} exists but no timer flags given; "
              f"not modifying it. Use `delete` to remove.", file=sys.stderr)

    if args.no_enable:
        print("skipped daemon-reload and enable (--no-enable)", file=sys.stderr)
        return

    systemctl(args.user, "daemon-reload")
    if has_timer:
        systemctl(args.user, "enable", "--now", f"{name}.timer")
        print(f"enabled and started {name}.timer", file=sys.stderr)
    else:
        systemctl(args.user, "enable", "--now", f"{name}.service")
        print(f"enabled and started {name}.service", file=sys.stderr)


def cmd_delete(args):
    name = args.name
    if name.endswith(".service") or name.endswith(".timer"):
        die(f"name should be bare ('{name.split('.')[0]}'), not include a suffix")

    udir = unit_dir(args.user)
    svc_path = udir / f"{name}.service"
    timer_path = udir / f"{name}.timer"

    for unit in [f"{name}.timer", f"{name}.service"]:
        if (udir / unit).exists():
            systemctl(args.user, "disable", "--now", unit, check=False)

    remove_unit(svc_path, user=args.user)
    remove_unit(timer_path, user=args.user)
    systemctl(args.user, "daemon-reload", check=False)
    print(f"removed {name}.service and {name}.timer (if present)", file=sys.stderr)


def cmd_status(args):
    name = args.name
    for suffix in [".timer", ".service"]:
        systemctl(args.user, "status", f"{name}{suffix}", check=False)


# ---------- argparse ----------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="systemd-one-line",
        description="Create systemd services and timers from one command.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    def add_common(p):
        p.add_argument("--user", action="store_true",
                       help="Manage user units (~/.config/systemd/user) "
                            "instead of system units (/etc/systemd/system)")

    p_service = sub.add_parser("service",
                               help="Create or edit a service (with optional timer)")
    add_common(p_service)
    p_service.add_argument("--name", required=True,
                           help="Unit name (e.g. 'btrfs-easy-snap', no .service/.timer suffix)")
    p_service.add_argument("--exec", required=False,
                           help="Command to run (becomes ExecStart=)")
    p_service.add_argument("--type", default="oneshot",
                           help="Service Type= (default: oneshot)")
    p_service.add_argument("--description",
                           help="Service description (default: auto)")
    p_service.add_argument("--run-as", default=None,
                           help="User= to run the service as "
                                "(system mode only; ignored for --user)")
    p_service.add_argument("--on-calendar", default=None,
                           help="Timer OnCalendar= value (e.g. '*:0/10')")
    p_service.add_argument("--on-unit-active-sec", default=None,
                           help="Timer OnUnitActiveSec= value (e.g. '10min')")
    p_service.add_argument("--persistent", action="store_true",
                           help="Add Persistent=true to timer "
                                "(catches up missed runs after reboot)")
    p_service.add_argument("--edit", action="store_true",
                           help="Overwrite existing unit files")
    p_service.add_argument("--no-enable", action="store_true",
                           help="Skip daemon-reload and enable/start")
    p_service.set_defaults(func=cmd_service)

    p_delete = sub.add_parser("delete", help="Stop, disable, and remove units")
    add_common(p_delete)
    p_delete.add_argument("--name", required=True)
    p_delete.set_defaults(func=cmd_delete)

    p_status = sub.add_parser("status", help="Show systemctl status for the units")
    add_common(p_status)
    p_status.add_argument("--name", required=True)
    p_status.set_defaults(func=cmd_status)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()