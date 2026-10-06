# Known Issues

Besides the officially listed issues on the wetterdienst repository, there are other issues regarding
running wetterdienst listed below that may be environment specific and are not likely fixable on our side.

## Cache runs stale

Also we are quite happy with our [FSSPEC](https://github.com/fsspec/filesystem_spec) backed caching system from time
to time you may run into some unexplainable error with empty result sets like
[here](https://github.com/earthobservations/wetterdienst/issues/678) and in this case it is worth try dropping the
cache entirely.

Running this

```python
import wetterdienst
wetterdienst.info()
```

will guide you the path to your caching folder.

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

On Linux, installing `eccodes` (from the `bufr` or `eccodes` extra) with pip, `uv pip` or another
installer that reads its wheel's dependencies pulls in the `eccodeslib` and `eckitlib` wheels, and
`eckitlib` bundles its own copy of PROJ. `pyproj` bundles another, and comes with the `radarplus`
extra (through wradlib and xradar) as well as with libraries such as geopandas or cartopy. A process
that loads `eccodes` and then imports `pyproj` crashes at interpreter exit (`double free or
corruption`, `free(): invalid pointer` or a segmentation fault, exit status 134 or 139):

```bash
python -c "import eccodes; import pyproj"; echo $?   # 134
python -c "import pyproj; import eccodes"; echo $?   # 0
```

wetterdienst loads `eccodes` when you ask for DWD road values (as soon as `.values` is built,
before any data is read) and when it parses DWD radar BUFR data with the `read_bufr` setting. The
crash comes after your code has finished, so files it wrote and closed are complete, but the
non-zero exit status fails scripts and CI jobs. This is the upstream bug
[ecmwf/eckit#354](https://github.com/ecmwf/eckit/issues/354), see also
[#2441](https://github.com/earthobservations/wetterdienst/issues/2441). The Docker image does not
install the `eccodeslib` wheel and is not affected. To check your own installation, run
`python -c "import importlib.metadata as m; print(m.version('eckitlib'))"` with the Python that runs
wetterdienst: if it raises `PackageNotFoundError`, you are not affected.

Until it is fixed, install your distribution's ecCodes library and set
`FINDLIBS_DISABLE_PACKAGE=yes` in the environment of the process that runs wetterdienst (the shell,
the CI job, the service unit), so that `findlibs` loads that library instead of the wheel's. On
Debian 13:

```bash
sudo apt-get install libeccodes0 libeccodes-data
FINDLIBS_DISABLE_PACKAGE=yes python my_script.py
```

Both are needed: with only the variable set and no system library, `eccodes` cannot load at all.
The variable applies to every library `findlibs` looks up, not only ecCodes, and in every process
that inherits it, so another package that relies on `findlibs` to find a library in its wheel will
no longer find it. Scope it to the one command, as above, where you can.

Alternatively, import `pyproj` (or wradlib, which imports it) before `eccodes` is first loaded, by
wetterdienst or by anything else.

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