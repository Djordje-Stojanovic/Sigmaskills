# boat without a lab wrapper

The flow of SKILL.md with the plain boat CLI (`boat <command> --help` for every flag). `ID` is a `bx_` id. Each fact names
the docs page that holds it (https://docs.boat.dev/PAGE.md).

## Keys: stdin, or a boat environment

The base and every copy run with `--no-env`: boat injects nothing of the owner's, and its own GitHub token (which reaches only the
repos its GitHub app may see, and replaces the `gh` login) stays out. Each box then gets the keys file when it starts:

```sh
base64 -w0 < "$KEYS_FILE" | boat ssh ID -- 'umask 077; base64 -d > ~/.box-keys'   # stdin, never an argument
```

On the box: `gh auth login --with-token` from the keys file, then `gh auth setup-git`.

With an API key that has `environment.write` (a `ci` key has none, `api-keys/scopes.md`), boat can hold the keys instead: once
`boat env new boxes && boat env set boxes --github false --secrets true`, then `boat env set-file boxes .box-keys < "$KEYS_FILE"`
after each key change, and fork boxes with `--environment boxes` in place of `--no-env`. A sandbox takes the environment's latest
version when it starts (`environments/versions.md`).

## Commands

| Step | Command |
|---|---|
| make the base | `boat new --no-env --name base --json`, set it up, `boat stop ID`, `boat snapshot ID base` |
| update the base | `boat resume ID --no-env`, update, `boat stop ID`, `boat snapshot ID base` (the name is replaced) |
| make a box | `boat fork BASE_ID --no-env --ttl 28800 --wait --json`, `boat rename NEW box-REPO`, then the keys |
| make a worker | the same fork with `--ttl 7200`, renamed `worker-REPO` |
| run a command | `boat exec ID --timeout 0 -- CMD` (the default timeout is 30 s) |
| move the auto-stop | `boat extend ID --ttl SECONDS` |
| pause, come back | `boat stop ID`, `boat resume ID --ttl SECONDS` |
| preview, public | `boat host ID PORT` (ask the owner first: anyone with the URL reaches it) |
| watch | `boat list --all --json`, `boat limits --all` |
| delete | `boat delete ID --yes` |

## Facts that shape the work

- **Auto-stop is a deadline, not an idle timer** (`long-running-tasks/auto-stop.md`). It counts from the start or the last resume;
  `exec`, SSH and agent work never move it. Nothing starts a stopped sandbox by itself (`readiness.md`).
- **Stop keeps the disk, ends every program** (`snapshots/stop.md`). Enabled systemd services start again on resume; anything
  started by hand does not. The IP address and the SSH host key change.
- **A stopped disk is kept at least 14 days; a saved snapshot has no end** (`snapshots/templates.md`). Saving under a name that
  exists replaces it.
- **A fork copies the latest snapshot** (`snapshots/resume-and-fork.md`), every file on the disk included. A snapshot of a
  sandbox that ran with secrets can hold them (`environments/access.md`): that is why the base runs with `--no-env`.
- **Starts are counted** per minute, hour and day and never queued (`limits.md`).
- Sizes and prices: `pricing.md`; `boat limits --all` reads the live numbers.
