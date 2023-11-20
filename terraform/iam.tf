resource "google_storage_bucket_iam_member" "state" {
  bucket = google_storage_bucket.wetterdienst-state.name
  role   = "roles/storage.admin"
  member = "serviceAccount:cicd-dev@wetterdienst.iam.gserviceaccount.com"
}
