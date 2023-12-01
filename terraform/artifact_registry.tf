resource "google_artifact_registry_repository" "docker-wetterdienst" {
    repository_id = "docker-wetterdienst"
    location      = var.region
    format        = "DOCKER"
    description   = "Standard image repository for the wetterdienst project."
}
