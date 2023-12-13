locals {
  image_name        = "wetterdienst-standard"
  registry_hostname = "${var.region}-docker.pkg.dev"
  image_registry    = "${local.registry_hostname}/${var.project}/${google_artifact_registry_repository.docker-wetterdienst.name}"
  image_sha         = "${data.docker_registry_image.wetterdienst-standard.name}@${data.docker_registry_image.wetterdienst-standard.sha256_digest}"
  image_tagged      = data.docker_registry_image.wetterdienst-standard.name
}

data "docker_registry_image" "wetterdienst-standard" {
  name = "${local.image_registry}/${local.image_name}"
}

resource "google_cloud_run_v2_service" "wetterdienst-restapi" {
  name     = "wetterdienst-restapi"
  project = var.project
  location = var.region
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = local.image_sha
      command = ["wetterdienst", "restapi", "--listen=0.0.0.0:8080"]
      resources {
        limits = {
          cpu    = "1000m"
          memory = "1000Mi"
        }
      }
    }
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }
}
