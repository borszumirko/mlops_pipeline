variable "aws_region" {
  description = "AWS Region assigned to the portfolio project."
  type        = string
  default     = "eu-north-1"
}

variable "allowed_client_cidr" {
  description = "Public IPv4 address allowed to call the demo API, with a /32 suffix."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.allowed_client_cidr)) && endswith(var.allowed_client_cidr, "/32")
    error_message = "Provide one IPv4 address with a /32 suffix."
  }
}

variable "image_digest" {
  description = "Digest of the tested API image already pushed to this project's ECR repository."
  type        = string

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "Provide a sha256: digest followed by 64 lowercase hexadecimal characters."
  }
}

variable "desired_count" {
  description = "Number of demo tasks: use 0 to stop compute or 1 to run the API."
  type        = number
  default     = 1

  validation {
    condition     = contains([0, 1], var.desired_count)
    error_message = "The demo supports either zero or one running task."
  }
}
