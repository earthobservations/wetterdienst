# 10_minutes

## metadata

| property      | value                                                    |
|---------------|----------------------------------------------------------|
| name          | 10_minutes                                               |
| original name | 10_minutes                                               |
| url           | [here](https://hubeau.eaufrance.fr/page/api-hydrometrie) |

## datasets

### data

#### metadata

| property      | value                                                    |
|---------------|----------------------------------------------------------|
| name          | data                                                     |
| original name | data                                                     |
| description   | Flow and stage for France                                |
| access        | [here](https://hubeau.eaufrance.fr/page/api-hydrometrie) |

#### parameters

| name              | original name | description                                                                                                                                                                                                                                                                                                                                                                                                                         | unit | constraints |
|-------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge` | Q             | Flow (débit, grandeur Q), published in l/s and updated by the producer every 5 to 60 minutes. Each value is dated by the instant it occurred; the source states no mean or interval.                                                                                                                                                                                                                                                | l/s  | >=0         |
| {term}`stage`     | H             | Water height (hauteur d'eau, grandeur H), published in mm and updated by the producer every 5 to 60 minutes. Each value is dated by the instant it occurred; the source states no mean or interval. It is relative to the zero of the station's gauge, so stations share no reference level. The station's `gauge_zero` is the altitude of that zero in metres, in the system `gauge_zero_datum` names, where the source gives one. | mm   | -           |
