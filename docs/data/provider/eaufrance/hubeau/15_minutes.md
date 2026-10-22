# 15_minutes

## metadata

| property      | value                                                    |
|---------------|----------------------------------------------------------|
| name          | 15_minutes                                               |
| original name | 15_minutes                                               |
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

| name              | original name | description                                                                                                                                                         | unit | constraints |
|-------------------|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge` | Q             | Flow (débit, grandeur Q), published in l/s and updated by the producer every 5 to 60 minutes. The source states no statistic.                                       | l/s  | >=0         |
| {term}`stage`     | H             | Water height (hauteur d'eau, grandeur H), published in mm and updated by the producer every 5 to 60 minutes. The source states no statistic and no reference level. | mm   | -           |
