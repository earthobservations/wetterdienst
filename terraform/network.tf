resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "serverless-neg"
  project = var.project
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = google_cloud_run_v2_service.wetterdienst-restapi.name
  }
}

module "lb-http" {
  source  = "GoogleCloudPlatform/lb-http/google//modules/serverless_negs"
  name    = "loadbalancer"
  project = var.project

  https_redirect = true

  security_policy = google_compute_security_policy.default.name

  backends = {
    default = {
      description = null
      groups = [
        {
          group = google_compute_region_network_endpoint_group.serverless_neg.id
        }
      ]
      enable_cdn = false

      iap_config = {
        enable = false
      }
      log_config = {
        enable = false
      }
    }
  }
}