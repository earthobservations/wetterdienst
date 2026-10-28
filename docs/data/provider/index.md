# Provider

How every provider reads a calm, a trace, an obscured sky or a missing value is on
[special values](../special_values.md); the parameter tables of each provider say what its source writes.
The `unit` column of those tables is the unit the provider publishes the parameter in, `unit_source` in the
answer of `coverage` where it differs from `unit`; the values come back in the unit `coverage` gives as `unit` and
`glossary` lists (Kelvin as degrees Celsius, a percentage as a decimal from 0 to 1), unless `convert_units` is off.

```{toctree}
:hidden:

aemet/index.md
chmi/index.md
dmi/index.md
dwd/index.md
ea/index.md
eaufrance/index.md
eccc/index.md
fmi/index.md
geosphere/index.md
imgw/index.md
ipma/index.md
knmi/index.md
lhmt/index.md
meteofrance/index.md
meteoswiss/index.md
metno/index.md
metoffice/index.md
noaa/index.md
nws/index.md
rmi/index.md
smhi/index.md
wsv/index.md
```