# Parameters

The data that is provided via `wetterdienst` and its implemented services comes in all kinds of different shapes. All
parameters are summarized in a core `Parameter` enumeration and parameter enumerations of all weather services are
tested against it so that newly added parameters will be sorted and carefully added to the existing collection. The core
`Parameter` enumeration can be used for requests as well, as internally the requested parameter is always translated
to the provider specific parameter enumeration.

Import the provider specific metadata model like:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationMetadata

# print resolutions, datasets and parameters
for resolution in DwdObservationMetadata:
    print(f"{2 * "\t"}{resolution.name}", "\n")
    for dataset in resolution:
        print(f"{3 * "\t"}{dataset.name}", "\n")
        for parameter in dataset:
            print(f"{4 * "\t"}{parameter.name}", "\n")
```

The amount of distinct parameters and a list of the parameter names:

```python exec="on"
from wetterdienst.metadata.parameter import Parameter

parameters = [parameter.value.lower() for parameter in Parameter]

print(f"Number of parameters: {len(parameters)}", "\n")

print("\n".join(f"{2*"\t"}{parameter}" for parameter in parameters))
```