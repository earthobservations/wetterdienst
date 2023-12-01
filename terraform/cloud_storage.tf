resource "google_storage_bucket" "wetterdienst-state" {
  location = var.region
  name     = "wetterdienst-state"
  versioning {
    enabled = true
  }
}