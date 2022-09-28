Known Issues
############

Besides the officially listed issues on the wetterdienst repository, there are other issues regarding
running wetterdienst listed below that may be environment specific and are not likely fixable on our side.

LINUX ARM (Raspberry Pi)
************************

Running wetterdienst on Raspberry Pi, you need to install **numpy**
and **lxml** prior to installing wetterdienst running the following
lines:

.. code-block:: bash

    sudo apt-get install libatlas-base-dev
    sudo apt-get install python3-lxml

Cache runs stale
****************

Also we are quite happy with our `FSSPEC <https://github.com/fsspec/filesystem_spec>`_ backed caching system from time
to time you may run into some unexplainable error with empty result sets like
`here <https://github.com/earthobservations/wetterdienst/issues/678>`_ and in this case it is worth try dropping the
cache entirely.

Running this

```python
    import wetterdienst
    wetterdienst.info()
```

will guide you the path to your caching folder.