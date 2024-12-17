# Introduction

This chapter provides an informative overview of the data accessible via the `wetterdienst` service and the associated
usage conditions. `wetterdienst` facilitates user access to data from various agencies, including the German Weather
Service (DWD). While this data is available as open data, users are kindly requested to acknowledge the data source by
providing appropriate attribution. We have included links to the respective agencies and their licensing policies for
your convenience. Please take a moment to review these resources to ensure that you provide accurate references.

Here's a quick overview of the data sources currently supported by `wetterdienst`:

- DWD (Deutscher Wetterdienst / German Weather Service / Germany)
    - Observation
        - Historical (last ~300 years), recent (500 days to yesterday), now (yesterday up to last hour)
        - Every minute to yearly resolution
        - Time series of stations in Germany
        - see the rdwd pages for an interactive map_ and table_ of available datasets
    - Mosmix - statistical optimized scalar forecasts extracted from weather models
        - Point forecast
        - 5400 stations worldwide
        - Both MOSMIX-L and MOSMIX-S is supported
        - Up to 115 parameters
    - DMO - timeseries extracted from weather models
        - Point forecast
        - 5400 stations worldwide
        - Up to 115 parameters
    - Road
        - Historical weather observations of German highway stations
    - Radar
        - 16 locations in Germany
        - All of Composite, Radolan, Radvor, Sites and Radolan_CDC
        - Radolan: calibrated radar precipitation
        - Radvor: radar precipitation forecast
- EA (Environment Agency)
    - Hydrology
        - data of river network of UK
        - parameters flow and ground water stage
- Eaufrance
    - Hubeau
        - data of river network of France (continental)
        - parameters flow and stage of rivers of last 30 days
- ECCC (Environnement et Changement Climatique Canada / Environment and Climate Change Canada / Canada)
    - Historical Weather Observations
        - Historical (last ~180 years)
        - Hourly, daily, monthly, (annual) resolution
        - Time series of stations in Canada
- Geosphere (Geosphere Austria, formerly Central Institution for Meteorology and Geodynamics)
    - Observation
        - historical meteorological data of Austrian stations
- IMGW (Institute of Meteorology and Water Management)
    - Meteorology
        - meteorological data of polish weather stations
        - daily and monthly summaries
    - Hydrology
        - hydrological data of polish river stations
        - daily and monthly summaries
- NOAA (National Oceanic And Atmospheric Administration / National Oceanic And Atmospheric Administration / United States Of America)
    - Global Historical Climatology Network
        - Historical, hourly (ISD) and daily weather observations from around the globe
        - more then 100k stations
        - data for weather services which don't publish data themselves
- NWS (NOAA National Weather Service)
    - Observation
        - recent observations (last week) of US weather stations
        - currently the list of stations is not completely right as we use a diverging source!
- WSV (Wasserstraßen- und Schifffahrtsverwaltung des Bundes / Federal Waterways and Shipping Administration)
    - Pegelonline
        - data of river network of Germany
        - coverage of last 30 days
        - parameters like stage, runoff and more related to rivers