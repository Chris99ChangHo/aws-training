# Fixture only -- never applied. Deliberately missing operability controls that
# no security scanner reports: no required_version, no remote backend, and one
# provider declared without a version constraint.
#
# Verified against the security agent's SCA wrapper: Trivy reports none of these
# (its only "version" findings on Terraform are S3 bucket *versioning*).

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}

provider "aws" {
  region = "ap-northeast-2"
}
