# Margin Optimizer API

FastAPI-based REST API for generating vendor negotiation strategies.

## Features

- **Multi-vendor strategies**: Get strategies for all vendors quoting a service
- **Historical data**: Leverage past negotiation performance
- **VPL comparison**: Compare against vendor published prices
- **Alternative vendors**: Explore competitive options
- **Prioritized recommendations**: 1-3 actionable strategies per vendor
- **API Key authentication**: Secure access control
- **OpenAPI documentation**: Auto-generated interactive docs

## Quick Start

### Installation

```bash
cd DH\ -\ Margin-Optimizer-API/
pip install -r requirements.txt
```

### Configuration

Set your API key as an environment variable:

```bash
export MARGIN_OPTIMIZER_API_KEY="your-secret-api-key"
```

Or it will default to `your-secret-api-key-change-in-production`

### Run the API

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Usage

### Get Strategies for a Service

```bash
curl -X GET "http://localhost:8000/api/v1/strategies/TWS.5511.D011" \
     -H "X-API-Key: your-secret-api-key"
```

### Response Structure

```json
{
  "service_id": "TWS.5511.D011",
  "service": {
    "service_id": "TWS.5511.D011",
    "customer": "Customer Name",
    "bandwidth_display": "100 Mbps",
    "client_mrc": 419.0,
    "currency": "USD",
    "address": "...",
    "latitude": "-23.57136",
    "longitude": "-46.59819"
  },
  "vendor_strategies": [
    {
      "vendor_name": "Vendor A",
      "vendor_quote": {
        "vendor_name": "Vendor A",
        "quickbase_id": 555506,
        "current_mrc": 252.07,
        "mrc_currency": "USD",
        "current_gm": 80.3,
        "gm_status": "success",
        "lead_time": "7 days",
        "status": "desk_results_feasible",
        "bandwidth": "100 Mbps"
      },
      "negotiation_history": {
        "total_negotiations": 5,
        "successful_negotiations": 1,
        "success_rate": 20.0,
        "avg_discount": 13.3,
        "projected_mrc": 218.58,
        "projected_gm": 82.9,
        "projected_gm_status": "success"
      },
      "renewal_stats": {
        "total_renewals": 4,
        "successful_renewals": 0,
        "success_rate": 0.0,
        "avg_discount": 0.0
      },
      "delivered_services": {
        "total_mrc_usd": 15234.56,
        "delivered_count": 23
      },
      "targets": {
        "gm_40": {
          "target_mrc": 251.4,
          "discount_needed": 0.3
        },
        "gm_50": {
          "target_mrc": 209.5,
          "discount_needed": 16.9
        }
      },
      "vendor_vpl": [...],
      "alternatives": [...],
      "recommendations": [
        {
          "priority": 1,
          "title": "Negotiate with Vendor A",
          "type": "negotiate",
          "strength": "high",
          "actions": [
            {
              "text": "Historical average discount: 13.3% (success rate: 20.0%)",
              "value": 218.58
            },
            {
              "text": "For 40% GM: Request $251.40 (0.3% discount)",
              "value": 251.4
            },
            {
              "text": "For 50% GM: Request $209.50 (16.9% discount)",
              "value": 209.5
            }
          ]
        },
        {
          "priority": 2,
          "title": "Use Vendor Price List (VPL) - STRONGEST ARGUMENT",
          "type": "vpl",
          "strength": "very_high",
          "actions": [...]
        }
      ]
    }
  ],
  "total_vendors": 1
}
```

## Authentication

All API endpoints require an API key in the `X-API-Key` header.

**Example:**

```bash
curl -X GET "http://localhost:8000/api/v1/strategies/SERVICE_ID" \
     -H "X-API-Key: your-secret-api-key"
```

**Error Response (401 Unauthorized):**

```json
{
  "detail": "Invalid or missing API Key"
}
```

## Endpoints

### `GET /api/v1/strategies/{service_id}`

Get negotiation strategies for all vendors quoting a service.

**Parameters:**
- `service_id` (path): Service ID (e.g., "TWS.5511.D011")

**Headers:**
- `X-API-Key`: Your API key

**Responses:**
- `200`: Strategies generated successfully
- `401`: Invalid or missing API Key
- `404`: Service not found
- `500`: Internal server error

### `GET /api/v1/health`

Health check endpoint (no authentication required).

**Response:**

```json
{
  "status": "healthy",
  "service": "Margin Optimizer API"
}
```

## Project Structure

```
DH - Margin-Optimizer-API/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── config/
│   └── security.py           # API key authentication
├── models/
│   └── schemas.py            # Pydantic models
├── routers/
│   └── strategies.py         # API endpoints
├── services/
│   └── strategy_service.py  # Business logic
├── connectors/               # Symlink to Flask connectors
├── utils/                    # Symlink to Flask utils
└── config.py                 # Symlink to Flask config
```

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

Test the API with curl:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Get strategies
curl -X GET "http://localhost:8000/api/v1/strategies/TWS.5511.D011" \
     -H "X-API-Key: your-secret-api-key"
```

### Interactive Documentation

Visit http://localhost:8000/docs for Swagger UI documentation where you can:
- View all endpoints
- Test requests directly from the browser
- See request/response schemas
- Authorize with your API key

## Production Deployment

### Environment Variables

Set these environment variables in production:

```bash
export MARGIN_OPTIMIZER_API_KEY="your-production-api-key"
```

### Running with Gunicorn + Uvicorn Workers

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Integration Examples

### Python

```python
import requests

API_URL = "http://localhost:8000/api/v1/strategies"
API_KEY = "your-secret-api-key"

def get_strategies(service_id):
    response = requests.get(
        f"{API_URL}/{service_id}",
        headers={"X-API-Key": API_KEY}
    )
    response.raise_for_status()
    return response.json()

# Usage
strategies = get_strategies("TWS.5511.D011")
print(f"Found {strategies['total_vendors']} vendors")
for vendor_strategy in strategies['vendor_strategies']:
    print(f"Vendor: {vendor_strategy['vendor_name']}")
    print(f"Recommendations: {len(vendor_strategy['recommendations'])}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_URL = 'http://localhost:8000/api/v1/strategies';
const API_KEY = 'your-secret-api-key';

async function getStrategies(serviceId) {
  try {
    const response = await axios.get(`${API_URL}/${serviceId}`, {
      headers: { 'X-API-Key': API_KEY }
    });
    return response.data;
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
    throw error;
  }
}

// Usage
getStrategies('TWS.5511.D011')
  .then(strategies => {
    console.log(`Found ${strategies.total_vendors} vendors`);
    strategies.vendor_strategies.forEach(vs => {
      console.log(`Vendor: ${vs.vendor_name}`);
      console.log(`Recommendations: ${vs.recommendations.length}`);
    });
  });
```

## Support

For issues or questions, contact the development team.

## License

Internal use only - IG Networks
