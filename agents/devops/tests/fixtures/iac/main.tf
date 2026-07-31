# Deliberately misconfigured Terraform. Fixture only -- never applied.
#
# Each block below violates a Trivy `config` check so the wrapper and the gate
# can be verified end to end without a real project. Do not "fix" these; the
# tests assert that findings are produced.

resource "aws_s3_bucket" "public_logs" {
  bucket = "example-public-logs"
}

# No server-side encryption, no versioning, and a public-read ACL.
resource "aws_s3_bucket_acl" "public_logs" {
  bucket = aws_s3_bucket.public_logs.id
  acl    = "public-read"
}

# Security group open to the entire internet on SSH.
resource "aws_security_group" "wide_open" {
  name = "wide-open"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
