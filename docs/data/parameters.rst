Parameters
##########

The data that is provided via `wetterdienst` and its implemented services comes in all kinds of different shapes. All
parameters are summarized in a core `Parameter` enumeration and parameter enumerations of all weather services are
tested against it so that newly added parameters will be sorted and carefully added to the existing collection. The core
`Parameter` enumeration can be used for requests as well, as internally the requested parameter is always translated
to the provider specific parameter enumeration.

Import the provider specific metadata model like:

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationMetadata

The amount of distinct parameters and a list of the parameter names:

.. ipython:: python

    from wetterdienst.metadata.parameter import Parameter

    parameters = [parameter.name for parameter in Parameter]

    print(f"Number of parameters: {len(parameters)}")

    print("\n".join(parameters))
