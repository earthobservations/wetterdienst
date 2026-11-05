# Known Issues

Besides the officially listed issues on the wetterdienst repository, there are other issues regarding
running wetterdienst listed below that may be environment specific and are not likely fixable on our side. What an
error of the library means, whatever the machine, is in [Troubleshooting](usage/troubleshooting.md).

## Cache runs stale

Also we are quite happy with our [FSSPEC](https://github.com/fsspec/filesystem_spec) backed caching system from time
to time you may run into some unexplainable error with empty result sets like
[here](https://github.com/earthobservations/wetterdienst/issues/678) and in this case it is worth try dropping the
cache entirely.

Running this

```bash
wetterdienst cache
```

prints the path to your caching folder (`wetterdienst info` shows it among other details).

## SSL Certificate Verification Issues

If you encounter SSL certificate verification errors, especially in corporate environments with custom
certificates or when your system certificates are outdated, you may see errors like:

- `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]`
- Connection failures when downloading data

You can resolve this by enabling the certifi certificate bundle:

```python
from wetterdienst import Settings

settings = Settings(use_certifi=True)
# Use this settings object with your requests
```

Or via environment variable:

```bash
export WD_USE_CERTIFI=true
```

This uses Mozilla's curated collection of root certificates instead of your system certificates.
For more information, see the [settings documentation](usage/settings.md).

## Crash at exit with ecCodes and pyproj on Linux

This applies to `findlibs` older than 0.1.4 only. The `bufr` and `eccodes` extras require 0.1.4 or
newer from the release after 0.183.0 on, so an install through them is not affected.

On Linux, installing `eccodes` 2.43 or newer with pip, `uv pip` or another installer that reads its
wheel's dependencies pulls in the `eccodeslib` and `eckitlib` wheels, and `eckitlib` bundles its own
copy of PROJ. (An install that follows a lock file made without them, such as this project's
`uv.lock` with `uv sync`, does not get the wheels and uses a system library, so it was never
affected.) `findlibs` 0.1.3 and older loaded that library globally, so a process that loaded
`eccodes` and then imported `pyproj` (which the `radarplus` extra brings, as do geopandas or
cartopy) crashed at interpreter exit with `double free or corruption`, `free(): invalid pointer` or
a segmentation fault, exit status 134 or 139. Files your code wrote and closed are complete, but
the exit status fails scripts and CI jobs. It was seen with `eckitlib` 2.3.0 and 2.5.0, not with
2.0.1. This was the upstream bug [ecmwf/eckit#354](https://github.com/ecmwf/eckit/issues/354),
fixed by `findlibs` 0.1.4 ([ecmwf/findlibs#30](https://github.com/ecmwf/findlibs/pull/30)), which
loads the library locally; see also
[#2441](https://github.com/earthobservations/wetterdienst/issues/2441).

You can still meet it where `eccodes` was installed without these extras and the environment keeps
an older `findlibs` (pip does not upgrade a package that already satisfies `eccodes`' own
requirement, which names no version), or where a constraint pins one. Wetterdienst no longer
imports `pyproj` ahead of `eccodes` for you, so code that reads DWD road BUFR and then imports
`pyproj` is affected too. Check with
`python -c "import importlib.metadata as m; print(m.version('findlibs'))"`, and upgrade:

```bash
pip install --upgrade "findlibs>=0.1.4"
```

If you cannot, import `pyproj` first, which the crash needs the other way round:

```bash
python -c "import eccodes; import pyproj"; echo $?   # 134, with findlibs 0.1.3
python -c "import pyproj; import eccodes"; echo $?   # 0
```

or install your distribution's ecCodes library and set `FINDLIBS_DISABLE_PACKAGE=yes` for the
command that runs your code, so that `findlibs` loads that library instead of the `eccodeslib`
wheel's (on Debian 13, `sudo apt-get install libeccodes0 libeccodes-data`). Both are needed: with
the variable and no system library, `eccodes` does not load at all. The variable applies to every
library `findlibs` looks up, so another package that relies on it to find a library in its wheel no
longer finds it: scope it to the one command, as in
`FINDLIBS_DISABLE_PACKAGE=yes python my_script.py`.

Installs without the `eckitlib` wheel were never affected: where
`python -c "import importlib.metadata as m; print(m.version('eckitlib'))"` raises
`PackageNotFoundError`, yours is not. The Docker image does not install it.

## Raspberry Pi / Linux ARM

On a Raspberry Pi, **numpy** and **lxml** have to be in place before wetterdienst is installed:

```bash
# not all of these may be required to get lxml running
sudo apt-get install gfortran
sudo apt-get install libopenblas-base
sudo apt-get install libopenblas-dev
sudo apt-get install libatlas-base-dev
sudo apt-get install python3-lxml
```

Expanding the swap to 2048 MB may be required as well, via the swap file:

```bash
sudo nano /etc/dphys-swapfile
```

Thanks [chr-sto](https://github.com/chr-sto) for reporting back to us!