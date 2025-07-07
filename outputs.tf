output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.web_server.public_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.web_server.public_dns
}

output "web_url" {
  description = "URL to access the web application"
  value       = "http://${aws_instance.web_server.public_ip}:8000"
}