variable "region" {
  default = "europe-north1"  # finland
}

variable "project" {
    default = "wetterdienst"
}

variable "gh_username" {
  default = "gutzbenj"
}

variable "gh_pat" {
}

variable "default_rules" {
    default = {
        def_rule = {
            action          = "allow"
            priority        = "2147483647"
            versioned_expr = "SRC_IPS_V1"
            src_ip_ranges   = ["*"]
            description     = "Default rule"
            preview         = false
        }
    }
    type = map(object({
        action              = string
        priority            = string
        versioned_expr      = string
        src_ip_ranges       = list(string)
        description         = string
        preview             = bool
        })
    )
}

# ---------------------------------
# Throttling traffic rules
# ---------------------------------
variable "throttle_rules" {
    default = {
        def_rule = {
            action                              = "throttle"
            priority                            = "4000"
            versioned_expr                      = "SRC_IPS_V1"
            src_ip_ranges                       = ["*"]
            description                         = "Throttling traffic rule"
            conform_action                      = "allow"
            exceed_action                       = "deny(429)"
            enforce_on_key                      = "ALL"                           #https://cloud.google.com/armor/docs/rate-limiting-overview#identifying_clients_for_rate_limiting
            rate_limit_threshold_count          = "100"
            rate_limit_threshold_interval_sec   = "60"
            preview                             = true
        }
    }
    type = map(object({
        action                              = string
        priority                            = string
        versioned_expr                      = string
        src_ip_ranges                       = list(string)
        description                         = string
        conform_action                      = string
        exceed_action                       = string
        enforce_on_key                      = string
        rate_limit_threshold_count          = number
        rate_limit_threshold_interval_sec   = number
        preview                             = bool
        })
    )
}

# ---------------------------------
# Countries limitation rules
# ---------------------------------
variable "countries_rules" {
    default = {
        def_rule = {
            action                              = "deny(403)"
            priority                            = "3000"
            expression                          = "'[CN, RU]'.contains(origin.region_code)"
            description                         = "Deny if region code is listed"
            preview                             = true
        }
    }
    type = map(object({
        action                              = string
        priority                            = string
        expression                          = string
        description                         = string
        preview                             = bool
        })
    )
}
# ---------------------------------
# OWASP top 10 rules
# ---------------------------------
variable "owasp_rules" {
    default = {
        #https://cloud.google.com/armor/docs/rule-tuning#sql_injection_sqli
        rule_sqli = {
            action      = "deny(403)"
            priority    = "1000"
            description = "SQL injection"
            preview     = true

            ### Detect Level severity (0 to 4): 0 mean no rules enabled and 4 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 4})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('sqli-v33-canary', {'sensitivity': 4})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#cross-site_scripting_xss
        rule_xss = {
            action      = "deny(403)"
            priority    = "1001"
            description = "Cross-site scripting"
            preview     = true

            ### Detect Level severity (0 to 2): 0 mean no rules enabled and 2 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 2})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('xss-v33-canary', {'sensitivity': 2})"

        }
        #https://cloud.google.com/armor/docs/rule-tuning#local_file_inclusion_lfi
        rule_lfi = {
            action      = "deny(403)"
            priority    = "1002"
            description = "Local file inclusion"
            preview     = true

            ### Detect Level severity (0 to 1): 0 mean no rules enabled and 1 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('lfi-v33-stable', {'sensitivity': 1})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('lfi-v33-canary', {'sensitivity': 1})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#remote_code_execution_rce
        rule_rce = {
            action      = "deny(403)"
            priority    = "1003"
            description = "Remote code execution"
            preview     = true

            ### Detect Level severity (0 to 3): 0 mean no rules enabled and 3 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('rce-v33-stable', {'sensitivity': 3})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('rce-v33-canary', {'sensitivity': 3})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#remote_file_inclusion_rfi
        rule_rfi = {
            action      = "deny(403)"
            priority    = "1004"
            description = "Remote file inclusion"
            preview     = true

            ### Detect Level severity (0 to 2): 0 mean no rules enabled and 2 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('rfi-v33-stable', {'sensitivity': 2})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('rfi-v33-canary', {'sensitivity': 2})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#method_enforcement
        rule_methodenforcement = {
            action      = "deny(403)"
            priority    = "1005"
            description = "Method enforcement"
            preview     = true

            ### Detect Level severity (0 to 1): 0 mean no rules enabled and 1 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('methodenforcement-v33-stable', {'sensitivity': 1})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('methodenforcement-v33-canary', {'sensitivity': 1})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#scanner_detection
        rule_scandetection = {
            action      = "deny(403)"
            priority    = "1006"
            description = "Scanner detection"
            preview     = true

            ### Detect Level severity (0 to 2): 0 mean no rules enabled and 2 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('scannerdetection-v33-stable', {'sensitivity': 2})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('scannerdetection-v33-canary', {'sensitivity': 2})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#protocol_attack
        rule_protocolattack = {
            action      = "deny(403)"
            priority    = "1007"
            description = "Protocol Attack"
            preview     = true


            ### Detect Level severity (0 to 3): 0 mean no rules enabled and 3 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('protocolattack-v33-stable', {'sensitivity': 3})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('protocolattack-v33-canary', {'sensitivity': 3})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#php
        rule_php = {
            action      = "deny(403)"
            priority    = "1008"
            description = "PHP"
            preview     = true

            ### Detect Level severity (0 to 3): 0 mean no rules enabled and 3 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('php-v33-stable', {'sensitivity': 3})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('php-v33-canary', {'sensitivity': 3})"
        }
        #https://cloud.google.com/armor/docs/rule-tuning#session_fixation
        rule_sessionfixation = {
            action      = "deny(403)"
            priority    = "1009"
            description = "Session Fixation"
            preview     = true

            ### Detect Level severity (0 to 1): 0 mean no rules enabled and 1 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('sessionfixation-v33-stable', {'sensitivity': 1})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('sessionfixation-v33-canary', {'sensitivity': 1})"
        }
        #https://cloud.google.com/armor/docs/waf-rules#java_attack
        rule_java = {
            action      = "deny(403)"
            priority    = "1010"
            description = "Java attack"
            preview     = true

            ### Detect Level severity (0 to 3): 0 mean no rules enabled and 3 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('java-v33-stable', {'sensitivity': 3})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('java-v33-canary', {'sensitivity': 3})"
        }
        #https://cloud.google.com/armor/docs/waf-rules#nodejs_attack
        rule_nodejs = {
            action      = "deny(403)"
            priority    = "1011"
            description = "NodeJS attack"
            preview     = true

            ### Detect Level severity (0 to 1): 0 mean no rules enabled and 1 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('nodejs-v33-stable', {'sensitivity': 1})"
            #Latest
            #expression  =  "evaluatePreconfiguredWaf('nodejs-v33-canary', {'sensitivity': 1})"
        }
    }
    type = map(object({
        action      = string
        priority    = string
        description = string
        preview     = bool
        expression  = string
        })
    )
}

# ---------------------------------
# Custom rules
# ---------------------------------
variable "cves_and_vulnerabilities_rules" {
    default = {
        # https://cloud.google.com/armor/docs/rule-tuning#cves_and_other_vulnerabilities
        rule_apache_log4j = {
            action          = "deny(403)"
            priority        = "2000"
            description     = "Apache Log4j CVE-2021-44228"
            preview         = true

            ### Detect Level severity (0 to 3): 0 mean no rules enabled and 3 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('cve-canary', {'sensitivity': 3})"
        }
        # https://cloud.google.com/armor/docs/rule-tuning#cves_and_other_vulnerabilities
        rule_json_sqli = {
            action          = "deny(403)"
            priority        = "2001"
            description     = "JSON-formatted content SQLi"
            preview         = true

            ### Detect Level severity (0 to 2): 0 mean no rules enabled and 2 is the most sensitive
            expression  =  "evaluatePreconfiguredWaf('json-sqli-canary', {'sensitivity': 2})"
        }
    }
    type = map(object({
        action      = string
        priority    = string
        description = string
        preview     = bool
        expression  = string
        })
    )
}