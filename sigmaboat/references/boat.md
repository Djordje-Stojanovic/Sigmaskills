# boat without a lab wrapper

The flow of SKILL.md with the plain boat CLI (`boat <command> --help` for every flag). `ID` is a `bx_` id. Each fact names
the docs page that holds it (https://docs.boat.dev/PAGE.md).

## One-time setup: the two environments

```sh
boat env new base-empty && boat env set base-empty --github false --secrets false --boat-credentials false --agents-credentials false
boat env new boxes && boat env set boxes --github false --secrets true --boat-credentials true --agents-credentials true
boat env set-file boxes .config/keys.txt < keys.txt     # stdin, never an argument; again whenever a key changes
```

- `--github false` on `boxes`: boat's own GitHub token reaches only the repos its GitHub app may see, and it replaces the `gh`
  login. On each box: `gh auth login --with-token` from the keys file, then `gh auth setup-git`.
- Writing an environment needs an API key with `environment.write`; a `ci` key has none (`api-keys/scopes.md`).
- A sandbox takes the environment's latest version when it starts and keeps it (`environments/versions.md`).

## Commands

| Step | Command |
|---|---|
| make the base | `boat new --environment base-empty --name base --json`, set it up, `boat stop ID`, `boat snapshot ID base` |
| update the base | `boat resume ID --environment base-empty`, update, `boat stop ID`, `boat snapshot ID base` (the name is replaced) |
| make a box | `boat fork BASE_ID --environment boxes --ttl 28800 --wait --json`, then `boat rename NEW box-REPO` |
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
  sandbox that ran with secrets can hold them (`environments/access.md`): that is why the base runs in `base-empty`.
- **Starts are counted** per minute, hour and day and never queued (`limits.md`).
- Sizes and prices: `pricing.md`; `boat limits --all` reads the live numbers.
