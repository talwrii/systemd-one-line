# systemd-one-line
Create systemd services and timers in a bash one liner.

## Motivation
I can't be bothred to edit service files. I don't like an LLM routing around in my system files editing stuff as it might decide to delete them.
This lets you create things with a single line.

## Alternatives and prior work
Just edit the file.
systemd can do something similar, but the files are not persisted.

## Installation
`pipx install systemd-one-line`

## Usage
Create a new service
`systemd-one-line service --exec blah --timer --every 1h`

`systemd-one-line service --edit --exec blah --timer --every 1h`

Create a user daeomon which starts when you log in:

```
systemd-one-line service \
  --user --autostart \
  --name bgmus \
  --type simple \
  --exec "$HOME/.local/bin/bgmus" \
  --edit
```

