variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Prefix for AWS resource names"
  type        = string
  default     = "squaddraft"
}

variable "environment" {
  description = "Deployment environment tag"
  type        = string
  default     = "prod"
}

variable "frontend_origin" {
  description = "Public URL of the frontend (used for FastAPI CORS). Set after first apply if using ALB DNS."
  type        = string
  default     = ""
}

variable "database_url" {
  description = "Supabase Postgres URI"
  type        = string
  sensitive   = true
}

variable "client_token_secret" {
  description = "Secret for room player tokens"
  type        = string
  sensitive   = true
}

variable "room_code_secret" {
  description = "Secret for room codes"
  type        = string
  sensitive   = true
}

variable "backend_cpu" {
  type    = number
  default = 256
}

variable "backend_memory" {
  type    = number
  default = 512
}

variable "frontend_cpu" {
  type    = number
  default = 256
}

variable "frontend_memory" {
  type    = number
  default = 512
}

variable "github_owner" {
  description = "GitHub org or username that owns the repo"
  type        = string
  default     = "lucas120301"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "squaddraft"
}
