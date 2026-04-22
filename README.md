# systemd-one-line
Create systemd jobs in one-line.

## Motivation
I can't be bothred to edit files. I don't like an LLM routing around in my system files editing stuff.
This lets you create things in one line.

## Atlernatives and prior work
Just edit the file
systemd can do something similar, but the files are not persisted.

## Installation
pipx install systemd-one-line

## Usage
Create a new service
`systemd-one-line service --exec blah --timer --every 1h`

`systemd-one-line service --edit --exec blah --timer --every 1h`
