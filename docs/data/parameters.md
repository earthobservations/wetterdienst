---
file_format: mystnb
kernelspec:
  name: python3
---

# Parameters

The data that is provided via `wetterdienst` and its implemented services comes in all kinds of different shapes. All
parameters are summarized in a core `Parameter` enumeration and parameter enumerations of all weather services are
tested against it so that newly added parameters will be sorted and carefully added to the existing collection. The core
`Parameter` enumeration can be used for requests as well, as internally the requested parameter is always translated
to the provider specific parameter enumeration.

## Metadata Model

Import the provider specific metadata model like:

You can inspect the metadata model of the services to see the available parameters and their descriptions. The metadata 
model is a Pydantic model with all its functionality so you can also extract a JSON schema.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationMetadata

metadata = DwdObservationMetadata.model_dump_json(indent=2)
print(metadata)
```

## List of Parameters

The amount of distinct parameters and a list of the parameter names:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.metadata.parameter import Parameter

parameters = [parameter.value.lower() for parameter in Parameter]
print(f"Number of parameters: {len(parameters)}")
print("Parameters:")
print("\n".join(parameters))
```