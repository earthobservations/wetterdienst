resource "google_cloud_run_v2_service" "wetterdienst-restapi" {
  name     = "wetterdienst-restapi"
  project = var.project
  location = var.region
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.docker-wetterdienst.name}/wetterdienst-standard:latest"
      command = ["wetterdienst", "restapi", "--listen=0.0.0.0:8080"]
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }
}
