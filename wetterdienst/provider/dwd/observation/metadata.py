from wetterdienst.metadata.metadata_model import MetadataModel

DwdObservationMetadata = [
  {
    "name": "minute_1",
    "datasets": [
      {
        "name": "precipitation",
        "parameters": [
          {
            "name": "quality",
            "original": "qn",
            "unit": "dimensionless",
            "unit_original": "dimensionless"
          },
          {
            "name": "precipitation_height",
            "original": "rs_01"
          },
          {
            "name": "precipitation_height_droplet",
            "original": "rth_01"
          },
          {
            "name": "precipitation_height_rocker",
            "original": "rwh_01"
          },
          {
            "name": "precipitation_index",
            "original": "rs_ind_01"
          }
        ]
      }
    ],
    "parameters": [
      {
        "$ref": "precipitation/precipitation_height"
      },
      {
        "$ref": "precipitation/precipitation_height_droplet"
      },
      {
        "$ref": "precipitation/precipitation_height_rocker"
      },
      {
        "$ref": "precipitation/precipitation_index"
      }
    ]
  }
]
DwdObservationMetadata = MetadataModel.model_validate(DwdObservationMetadata)