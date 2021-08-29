Parameters
**********

Across the multiple agencies of which data is provided through `wetterdienst` there is a multitude of parameters that
can be accessed.

.. ipython:: python

    from wetterdienst.metadata.parameter import Parameter

    parameters = [parameter.name for parameter in Parameter]

    print(f"There are currently approximately {len(parameters)} parameters made available.")

    print("\n".join(parameters))
