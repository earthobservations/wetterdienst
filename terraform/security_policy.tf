
# Source: https://github.com/ybellerose/GCP-Cloud-Armor/blob/main/Cloud%20Armor%20Deployment/cloud_armor_sec_policy/cloud_armor_sec_policy.tf
resource "google_compute_security_policy" "default" {
    project     = var.project
    name        = "${var.project}-waf-policy"
    description = "Default rule, Top 10 OWASP, Throttling & Log4J custom rules"
    # ---------------------------------
    # Default rules
    # ---------------------------------
    dynamic "rule" {
        for_each = var.default_rules
        content {
            action      = rule.value.action
            priority    = rule.value.priority
            description = rule.value.description
            preview     = rule.value.preview
            match {
                versioned_expr = rule.value.versioned_expr
                config {
                    src_ip_ranges = rule.value.src_ip_ranges
                }
            }
        }
    }

    # ---------------------------------
    # Throttling traffic rules
    # ---------------------------------
    dynamic "rule" {
        for_each = var.throttle_rules
        content {
            action      = rule.value.action
            priority    = rule.value.priority
            description = rule.value.description
            preview     = rule.value.preview
            match {
                versioned_expr = rule.value.versioned_expr
                config {
                    src_ip_ranges = rule.value.src_ip_ranges
                }
            }
            rate_limit_options {
                conform_action  = rule.value.conform_action
                exceed_action   = rule.value.exceed_action
                enforce_on_key  = rule.value.enforce_on_key
                rate_limit_threshold {
                    count           = rule.value.rate_limit_threshold_count
                    interval_sec    = rule.value.rate_limit_threshold_interval_sec
                }
            }
        }
    }

    # ---------------------------------
    # Country limitation
    # ---------------------------------
    dynamic "rule" {
        for_each = var.countries_rules
        content {
            action      = rule.value.action
            priority    = rule.value.priority
            description = rule.value.description
            preview     = rule.value.preview
            match {
                expr {
                    expression = rule.value.expression
                }
            }
        }
    }

    # ---------------------------------
    # OWASP top 10 rules
    # ---------------------------------
    dynamic "rule" {
        for_each = var.owasp_rules
        content {
            action      = rule.value.action
            priority    = rule.value.priority
            description = rule.value.description
            preview     = rule.value.preview
            match {
                expr {
                    expression = rule.value.expression
                }
            }
        }
    }

    # ---------------------------------
    # Custom Log4j rule
    # ---------------------------------
    dynamic "rule" {
        for_each = var.cves_and_vulnerabilities_rules
        content {
            action      = rule.value.action
            priority    = rule.value.priority
            description = rule.value.description
            preview     = rule.value.preview
            match {
                expr {
                    expression = rule.value.expression
                }
            }
        }
    }
}