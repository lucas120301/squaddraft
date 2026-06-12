terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment after creating the state bucket (see infra/DEPLOY.md).
  # backend "s3" {
  #   bucket         = "squaddraft-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "eu-west-2"
  #   encrypt        = true
  #   dynamodb_table = "squaddraft-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
}
