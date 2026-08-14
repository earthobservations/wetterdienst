# dynamic

## metadata

| property      | value                                                    |
|---------------|----------------------------------------------------------|
| name          | dynamic                                                  |
| original name | dynamic                                                  |
| description   | The interval is a property of the station rather than of the network: 15 minutes at most gauges, 10 at some. |
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

| name              | original name | description | unit | constraints |
|-------------------|---------------|-------------|------|-------------|
| {term}`discharge` | Q             | Flow.       | l/s  | >=0         |
| {term}`stage`     | H             | Stage.      | mm   | -           |
