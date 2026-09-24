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
    --periods=recent --station=01048 \
    --target=file:///var/lib/wetterdienst/kl.csv
```

`--target` takes the same connection strings as the Python `to_target()` method, so
`duckdb:///var/lib/wetterdienst/obs.duckdb?table=weather`, `influxdb://…` or `crate://…` work
equally well — see [Export](python-api.md#export).

Two properties of the CLI matter for a scheduler:

- **The exit code is meaningful.** A run that finds nothing exits `1` with
  `No data available for given constraints`. That is the same exit code as a real failure, so a
  schedule over a station that is merely quiet will look like a broken job. Either pick a query
  that always returns something, or let the wrapper decide what an empty result means.
- **File writes replace, never append.** A `file://` target is rewritten in full on every run;
  append mode is not implemented for files at all. Point consecutive runs at a database, or at a
  date-stamped filename, if you want the schedule to accumulate history.

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
    --periods=recent --station=01048 \
    --target=file://%S/wetterdienst/kl.csv

# Give the service its own unprivileged identity and its own writable directories.
DynamicUser=yes
StateDirectory=wetterdienst
CacheDirectory=wetterdienst
Environment=WD_CACHE_DIR=%C/wetterdienst

# A request that hangs should not sit in the timer's slot until the next reboot.
TimeoutStartSec=15min

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/wetterdienst.timer`:

```ini
[Unit]
Description=Acquire weather data with wetterdienst, hourly

[Timer]
OnCalendar=hourly
# Catch up after a reboot or a suspended laptop instead of silently skipping the run.
Persistent=true
# Spread load so that every installation does not hit the provider at :00 sharp.
RandomizedDelaySec=10min

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

`DynamicUser=yes` means the service has no home directory, which is worth understanding: the
default cache location comes from
[platformdirs](https://platformdirs.readthedocs.io/) and resolves under `$HOME`. The
`CacheDirectory=` and `Environment=WD_CACHE_DIR=%C/wetterdienst` pair above replaces it with
`/var/cache/wetterdienst`, owned by the service. Without them the run still works but re-downloads
everything each time. `StateDirectory=wetterdienst` does the same for output, giving `%S` =
`/var/lib`.

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
        <string>--station=01048</string>
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
17 * * * *  /usr/local/bin/wetterdienst values --provider=dwd --network=observation --parameters=daily/kl/temperature_air_mean_2m --periods=recent --station=01048 --target=file:///var/lib/wetterdienst/kl.csv >> /var/log/wetterdienst.log 2>&1
```

Note the `17`: an off-the-hour minute is deliberate, for the same reason as `RandomizedDelaySec`
above. cron passes almost no environment either, so use absolute paths, and set `WD_CACHE_DIR`
explicitly if the crontab belongs to a user without a stable `$HOME`.

One footgun if you take the date-stamped-filename advice from above: in a crontab, `%` is a command
separator, not a character. `$(date +%F)` has to be written `$(date +\%F)`.

## Docker

The image is a normal CLI container, so the scheduling unit simply runs `docker run`. Mount a
volume at the cache directory to keep it across runs:

```bash
docker run --rm \
    --volume=wetterdienst-cache:/var/cache/wetterdienst \
    --env=WD_CACHE_DIR=/var/cache/wetterdienst \
    --volume=/var/lib/wetterdienst:/data \
    ghcr.io/earthobservations/wetterdienst \
    wetterdienst values --provider=dwd --network=observation \
        --parameters=daily/kl/temperature_air_mean_2m \
        --periods=recent --station=01048 --target=file:///data/kl.csv
```

## Choosing an interval

Polling faster than the product is published only refills the cache. Each provider's page under
[Data](../data/index.md) states how often its products are refreshed; for the most-scheduled DWD
products that is:

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
