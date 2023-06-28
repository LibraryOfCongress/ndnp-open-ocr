resource "aws_apigatewayv2_api" "http" {
  name          = var.api_name
  protocol_type = "HTTP"

  tags = {
    Name        = var.api_tag_name
    Environment = var.api_tag_environment
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"

  connection_type      = "INTERNET"
  description          = "Lambda integration"
  integration_method   = "POST"
  integration_uri      = var.lambda_invoke_arn
  passthrough_behavior = "WHEN_NO_MATCH"
}

resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /{prefix}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_deployment" "deployment" {
  api_id = aws_apigatewayv2_api.http.id

  depends_on = [
    aws_apigatewayv2_integration.lambda,
    aws_apigatewayv2_route.default_route,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apigatewayv2_stage" "stage" {
  api_id        = aws_apigatewayv2_api.http.id
  name          = var.api_stage_name
  description   = var.api_stage_description
  deployment_id = aws_apigatewayv2_deployment.deployment.id

  default_route_settings {
    data_trace_enabled       = true
    detailed_metrics_enabled = true
    logging_level            = "INFO"
    throttling_burst_limit   = 5000
    throttling_rate_limit    = 10000
  }
}