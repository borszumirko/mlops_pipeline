provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "sentiment-api-mlops"
      ManagedBy = "Terraform"
    }
  }
}

resource "aws_ecr_repository" "sentiment_api" {
  name                 = "sentiment-api-mlops"
  image_tag_mutability = "IMMUTABLE"

  # Require images to be removed explicitly before destroying the repository.
  force_delete = false

  encryption_configuration {
    encryption_type = "AES256"
  }
}
