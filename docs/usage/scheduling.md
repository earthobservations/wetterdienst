# Scheduling

Wetterdienst has no scheduler of its own, and does not want one: a recurring acquisition is a
single CLI invocation repeated on a clock, and every operating system already ships a clock that
survives reboots, logs its runs and reports failures. This page gives ready-made snippets for
**systemd timers** (Linux), **launchd** (macOS) and **cron** (anywhere), plus the few wetterdienst
specifics that matter when the command runs unattended.

## The command to schedule

Anything you would run by hand works unattended, as long as the result goes somewhere other than
the terminal. Use `--target` to write to a file or a database instead of stdout:

```bash
wetterdienst values \
    --provider=dwd --network=observation \
    --parameters=daily/kl/temperature_air_mean_2m \
    --periods=recent --stations=01048 \
    --target=file:///var/lib/wetterdienst/kl.csv
```

`--target` takes the same connection strings as the Python `to_target()` method, so
`duckdb:///obs.duckdb?table=weather`, `influxdb://…` or `crate://…` work equally well — see
[Export](export.md). Each database sink is an optional extra (`duckdb`, `influxdb`,
`cratedb`, `postgresql`, `mysql`), imported only when its target is used, so install the one you
schedule or the run fails at the very end, after the download. A bare `postgresql://` target
writes through psycopg 3, which the `postgresql` extra installs; `postgresql+psycopg2://…` needs
`pip install psycopg2-binary` beside it.

Three properties of the CLI matter for a scheduler:

- **The exit code is meaningful.** A run that finds nothing is no failure: it exits `0` with
  `No data available for given constraints` on stderr and, where the REST API would answer an empty
  list, the same on stdout -- a schedule that asks for today's value before it is published does not
  fail. A `--target` is then left as it is: nothing is written, so the table or file keeps what the
  last run wrote instead of being replaced with an empty one. Exit `1` is for a failure, and `2` for
  a request that cannot be served as phrased. A wrapper that wants an empty result to count as one
  tests the output, or the sentence on stderr.
- **A run without a network connection fails, it does not write an empty result.** When the
  provider cannot be reached the command exits `1` with `No internet connection: could not reach
  <url> (...)`, and the target keeps what the last run wrote, so a dropped connection is not a
  nightly export of an empty file.
- **A run replaces what the last one wrote, unless you say otherwise.** `--if-exists` defaults to
  `replace`, which for a schedule means the target holds the newest run rather than a history: a
  `file://` target is rewritten in full, and a `duckdb://`, `sqlite://` or `crate://` table is
  dropped and recreated. Pass `--if-exists=append` to accumulate instead. Not
  every sink takes every value — a file refuses `append`, and InfluxDB refuses `fail` and `skip`,
  since both would have to ask whether the measurement already exists — and a sink that refuses
  the pairing says so and exits 1 rather than writing something else. For InfluxDB, `replace` and
  `append` do the same thing: its points accumulate either way, and nothing clears the measurement.
  An `append` onto a table is matched by column name, not by position, so a `--shape=wide` schedule
  that starts asking for a parameter the table has no column for is refused rather than filing it
  under the old heading. Note what that does *not* catch: a schedule that drops a parameter is
  accepted, with nulls in the column it stopped filling, and under `--shape=long` the column set
  never changes at all, so no change of `--parameters` is refused there. The table is yours to keep
  honest either way.
- **A database path is relative unless you give it four slashes.** `duckdb:///obs.duckdb` names a
  file in the working directory, because the connection string's leading `/` separates the host
  from the path. For an absolute one, write `duckdb:////var/lib/wetterdienst/obs.duckdb`, or set
  `WorkingDirectory=` in the unit. A `file://` target is read differently: everything after
  `file://` is the path, so `file:///var/lib/wetterdienst/kl.csv` is absolute and
  `file://kl.csv` names a file in the working directory. Both paths are percent-decoded, so
  `duckdb:////home/me/my%20data/obs.duckdb` opens `/home/me/my data/obs.duckdb`; write a literal
  `%` as `%25`. A `duckdb://` path also ends at a `?` or `#`, so write those as `%3F` and `%23`.

## systemd timer (Linux)

Two units: a `.service` that says *what* to run and a `.timer` that says *when*. Install both into
`/etc/systemd/system/`.

`/etc/systemd/system/wetterdienst.service`:

```ini
[Unit]
Description=Acquire weather data with wetterdienst
Documentation=https://wetterdienst.readthedocs.io/
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/wetterdienst values \
    --provider=dwd --network=observation \
    --parameters=daily/kl/temperature_air_mean_2m \
    --periods=recent --stations=01048 \
    --target=file://%S/wetterdienst/kl.csv

# Give the service its own unprivileged identity and its own writable directories.
DynamicUser=yes
StateDirectory=wetterdienst
CacheDirectory=wetterdienst
Environment=WD_CACHE_DIR=%C/wetterdienst

# A request that hangs should not sit in the timer's slot until the next reboot.
TimeoutStartSec=15min
```

There is deliberately no `[Install]` section on the service: the timer is what pulls it in. Giving
it one invites `systemctl enable wetterdienst.service`, one word from the command below, which
would acquire on every boot as well as on every timer tick.

`/etc/systemd/system/wetterdienst.timer`:

```ini
[Unit]
Description=Acquire weather data with wetterdienst, daily

[Timer]
# daily, because that is how often `--periods=recent` is republished; see "Choosing an interval"
OnCalendar=daily
# Catch up after a reboot or a suspended laptop instead of silently skipping the run.
Persistent=true
# Spread load so that every installation does not hit the provider at midnight sharp.
RandomizedDelaySec=30min

[Install]
WantedBy=timers.target
```

Enable and inspect it:

```bash
systemctl daemon-reload
systemctl enable --now wetterdienst.timer

systemctl list-timers wetterdienst.timer   # when it last ran and when it runs next
systemctl start wetterdienst.service       # run once, now, without waiting
journalctl -u wetterdienst.service -f      # the output of the runs
```

`DynamicUser=yes` gives the service a transient account with no home directory of its own, and
that is the part worth understanding. The default cache location comes from
[platformdirs](https://platformdirs.readthedocs.io/) and resolves under `$HOME`, which here is not
a directory the service may write to. A cache directory that cannot be created or written to does not
fail the run: wetterdienst warns once per run, `the cache directory ... cannot be used (PermissionError: ...), so
this process caches in /tmp/wetterdienst-cache-... instead, which is removed when it exits ...`, and keeps
the cache of that run in a temporary directory. The run works, but it is a degraded one: nothing is
kept for the next run, so every run downloads again what the last one had already fetched.

The `CacheDirectory=wetterdienst` and `Environment=WD_CACHE_DIR=%C/wetterdienst` pair replaces it
with `/var/cache/wetterdienst`, created and owned by the service, where the cache survives the runs.
`StateDirectory=wetterdienst` does the same for output, giving `%S` = `/var/lib`.

One consequence to plan for: with `DynamicUser=yes`, systemd puts a state directory in
`/var/lib/private/wetterdienst` and leaves `/var/lib/wetterdienst` as a symlink into it. Only the
service sees through it, because `/var/lib/private` is `0700` and root-owned. The unit above writes
its CSV there, so if something else has to read that file — a dashboard, a backup, your own shell
— either drop `DynamicUser=yes` for a `User=` with a real account, or point `--target` at a
directory you create yourself and grant with `ReadWritePaths=`.

To be told when a run fails, add `OnFailure=` to the `[Unit]` section of the service and write a
matching notification unit:

```ini
OnFailure=wetterdienst-failure@%n.service
```

## launchd (macOS)

`~/Library/LaunchAgents/de.wetterdienst.acquire.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>de.wetterdienst.acquire</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/wetterdienst</string>
        <string>values</string>
        <string>--provider=dwd</string>
        <string>--network=observation</string>
        <string>--parameters=daily/kl/temperature_air_mean_2m</string>
        <string>--periods=recent</string>
        <string>--stations=01048</string>
        <string>--target=file:///Users/me/weather/kl.csv</string>
    </array>

    <!-- Every day at 06:30. For several times a day, make this an array of such dicts. -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>6</integer>
        <key>Minute</key><integer>30</integer>
    </dict>

    <!-- Do not also fire the moment the agent is loaded. A run missed because the Mac was
         asleep is not skipped the way cron skips it: launchd starts the job on the next wake,
         coalescing several missed intervals into one. -->
    <key>RunAtLoad</key><false/>

    <key>StandardOutPath</key><string>/Users/me/weather/wetterdienst.log</string>
    <key>StandardErrorPath</key><string>/Users/me/weather/wetterdienst.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/de.wetterdienst.acquire.plist
launchctl kickstart gui/$(id -u)/de.wetterdienst.acquire      # run once, now
launchctl print gui/$(id -u)/de.wetterdienst.acquire          # state, last exit status
launchctl bootout gui/$(id -u)/de.wetterdienst.acquire        # remove
```

launchd agents inherit almost no environment, so give `wetterdienst` an absolute path and set
anything it needs explicitly with an `EnvironmentVariables` dict.

## cron

The lowest common denominator, and still the right answer on a machine that has neither systemd nor
launchd:

```text
# m h dom mon dow  command
17 3 * * *  /usr/local/bin/wetterdienst values --provider=dwd --network=observation --parameters=daily/kl/temperature_air_mean_2m --periods=recent --stations=01048 --target=file://$HOME/weather/kl.csv >> $HOME/weather/wetterdienst.log 2>&1
```

Note the `17`: an off-the-hour minute is deliberate, for the same reason as `RandomizedDelaySec`
above. Note the paths too — cron has no `StateDirectory=` to create anything for it, and nothing in
wetterdienst creates a missing directory either, so a target whose parent does not exist fails with
`FileNotFoundError` on the first run. Create `$HOME/weather` once, or write the target under a
directory that already exists; `/var/lib` and `/var/log` are not writable by the account a user
crontab runs as. cron passes almost no environment, so use absolute paths, and set `WD_CACHE_DIR`
explicitly if the crontab belongs to a user without a stable `$HOME`.

One footgun if you give the target a date-stamped name, which is how a file schedule accumulates:
in a crontab, `%` is a command separator, not a character. `$(date +%F)` has to be written
`$(date +\%F)`.

## Docker

The image is a normal CLI container, so the scheduling unit simply runs `docker run`. It runs as the
unprivileged user `wetterdienst` (uid 10001): mount a volume at its cache directory to keep the
cache across runs, and make the host directory of a file target writable by that user
(`chown 10001 /var/lib/wetterdienst`). A volume that an earlier run as root filled needs a one-time
`chown -R 10001:10001` as well, see [Docker](docker.md):

```bash
docker run --rm \
    --volume=wetterdienst-cache:/home/wetterdienst/.cache/wetterdienst \
    --volume=/var/lib/wetterdienst:/data \
    ghcr.io/earthobservations/wetterdienst \
    wetterdienst values --provider=dwd --network=observation \
        --parameters=daily/kl/temperature_air_mean_2m \
        --periods=recent --stations=01048 --target=file:///data/kl.csv
```

## Choosing an interval

Polling faster than the product is published only refills the cache. The figures below are the
ones DWD publishes for its most-scheduled products; for anything else, the provider pages under
[Data](../data/index.md) give each dataset's resolution, which is the floor rather than the
publication cadence:

| Product                             | Published        | Useful interval  |
| ----------------------------------- | ---------------- | ---------------- |
| observation, `--periods=recent`     | daily            | daily            |
| observation, `--periods=historical` | rarely           | monthly or less  |
| MOSMIX-S                            | every hour       | hourly           |
| MOSMIX-L                            | every 6 hours    | every 6 hours    |
| road                                | every 15 minutes | every 15 minutes |

Wetterdienst caches upstream responses, so a schedule that runs more often than the upstream
refresh mostly hits the cache rather than the provider — but only if the cache directory survives
between runs, which is what the `WD_CACHE_DIR` settings above are for. See
[Caching](python-api.md#caching) and [Settings](settings.md) for the cache knobs, including
`WD_CACHE_DISABLE`.
