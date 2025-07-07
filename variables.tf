variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}



variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "key_name" {
  description = "EC2 Key Pair name"
  type        = string
}