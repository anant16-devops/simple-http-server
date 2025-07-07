terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Security Group
resource "aws_security_group" "demo-web_sg" {
  name        = "demo-web_sg"
  description = "Security group for HTTP server"
  
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
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

# EC2 Instance
resource "aws_instance" "web_server" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  
  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    app_files = base64encode(data.archive_file.app_source.output_base64)
  }))
  
  tags = {
    Name = "Simple HTTP Server"
  }
}

# Archive application files
data "archive_file" "app_source" {
  type        = "zip"
  source_dir  = "${path.module}"
  output_path = "${path.module}/app.zip"
  excludes    = ["*.tf", "*.tfvars", "user_data.sh", "app.zip", ".terraform*"]
}