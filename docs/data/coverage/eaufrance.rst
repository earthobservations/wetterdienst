Eaufrance
*********

Hubeau
======

Overview
________

The data as offered by Hubeau through ``wetterdienst`` includes:

- flow
- stage

of the French river network for last 30 days.

.. ipython:: python

    import json
    from wetterdienst.provider.eaufrance.hubeau import HubeauRequest

    meta = HubeauRequest.discover(flatten=False)

    print(json.dumps(meta, indent=4, ensure_ascii=False))
