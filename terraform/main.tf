terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "3.0.2"
    }
    google = {
      source  = "hashicorp/google"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
    }
    github = {
      source  = "integrations/github"
    }
  }

  backend "gcs" {
    bucket  = "wetterdienst-state"
    prefix  = "terraform/state"
  }
}

provider "docker" {
#  host = "unix:///var/run/docker.sock"
  registry_auth {
    address = "europe-north1-docker.pkg.dev"
  }
}

provider "github" {}

provider "google" {
  project = var.project
  region  = var.region
}
