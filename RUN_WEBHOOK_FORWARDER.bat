@echo off
title NIIT University Assistant - GitHub to Jenkins Webhook Forwarder
echo ================================================================================
echo  NIIT University GenAI Knowledge Assistant - GitHub to Jenkins Webhook Relay
echo ================================================================================
echo.
echo Forwarding GitHub Webhook events directly to:
echo   Target: http://localhost:8080/github-webhook/
echo   Smee Channel: https://smee.io/nu-knowledge-webhook
echo.
echo Configure this URL as your GitHub Repository Webhook Payload URL:
echo   Payload URL: https://smee.io/nu-knowledge-webhook
echo   Content type: application/json
echo   Events: Just the push event
echo.
echo Starting forwarder... Press Ctrl+C to stop.
echo --------------------------------------------------------------------------------
smee -u https://smee.io/nu-knowledge-webhook -t http://localhost:8080/github-webhook/
pause
