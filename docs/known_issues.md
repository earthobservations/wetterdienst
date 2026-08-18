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