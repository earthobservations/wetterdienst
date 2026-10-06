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

## Crash at exit with the `bufr` and `radarplus` extras on Linux

On Linux, `eccodes` (from the `bufr` or `eccodes` extra) pulls in the `eccodeslib` and `eckitlib`
wheels, and `eckitlib` bundles its own copy of PROJ. The `radarplus` extra brings in `pyproj`, which
bundles another. A process that imports `eccodes` before `pyproj` then crashes at interpreter exit
(`double free or corruption` or `free(): invalid pointer`, usually exit status 134):

```bash
python -c "import eccodes; import pyproj"; echo $?   # 134
python -c "import pyproj; import eccodes"; echo $?   # 0
```

The crash comes after your code has finished, so output is already written, but the non-zero exit
status fails scripts and CI jobs. This is the upstream bug
[ecmwf/eckit#354](https://github.com/ecmwf/eckit/issues/354), see also
[#2441](https://github.com/earthobservations/wetterdienst/issues/2441).

Until it is fixed, install your distribution's ecCodes library and tell `findlibs` to use it instead
of the one from the wheel (Debian/Ubuntu shown):

```bash
sudo apt-get install libeccodes0
export FINDLIBS_DISABLE_PACKAGE=yes
```

Both steps are needed: with only `FINDLIBS_DISABLE_PACKAGE` set and no system library,
`eccodes` cannot load at all. Importing `pyproj` before `eccodes` avoids the crash as well.

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