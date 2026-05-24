# Service Verification Guide

## Starting the Service

Since you're on Windows, use the provided startup script:

```bash
scripts/start-windows.ps1
```

This will:
1. Build the Docker image with all security fixes
2. Start the container named "pm-app"
3. Map port 8000 on your host to port 8000 in the container
4. Use your .env file for environment variables (create one from .env.example if needed)

## Environment Configuration

Create a `.env` file in the project root with at least:

```
# OpenRouter Configuration (get your key from https://openrouter.ai)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Application Security (change these in production!)
DEFAULT_USER=user
DEFAULT_PASSWORD=password
```

## Verification Steps

Once the service is running, verify these endpoints:

1. **Application UI**: http://localhost:8000
   - Should show login page
   - Accept any username/password combination
   - Navigate to Kanban board after login

2. **Health Endpoint**: http://localhost:8000/health
   - Should return: `{"status":"ok"}`

3. **API Test Endpoint**: http://localhost:8000/api/hello
   - Should return: `{"message":"Hello from FastAPI"}`

4. **Board API Endpoint**: http://localhost:8000/api/board
   - Should return JSON with board structure (requires auth header)
   - Test with: `curl -H "X-User: user" http://localhost:8000/api/board`

5. **API Documentation**: http://localhost:8000/docs
   - Interactive API documentation (Swagger UI)

## Stopping the Service

When finished, stop the service with:

```bash
scripts/stop-windows.ps1
```

## Testing the Fixes

To verify the security improvements:

1. **Password Hashing**: Check that passwords are stored hashed in the database
2. **Environment Variables**: Confirm credentials come from environment, not hardcoded
3. **Error Handling**: Verify error responses are informative but don't leak sensitive info
4. **Logging**: Check container logs for structured JSON output

## Expected Behavior

- Application functions identically to before from user perspective
- All existing features work: login, Kanban board, drag-and-drop, AI chat
- Enhanced security: credentials not hardcoded, passwords hashed
- Better diagnostics: comprehensive structured logging
- Improved performance: optimized database operations
- Ready for scaling: rate limiting infrastructure in place

## Troubleshooting

If you encounter issues:

1. Check container logs: `docker logs pm-app`
2. Verify environment variables are passed correctly
3. Ensure OpenRouter API key is valid and has credits
4. Check that ports aren't conflicting (8000 on host)