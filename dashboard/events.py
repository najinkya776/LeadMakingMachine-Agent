import redis
import json
from datetime import datetime

REDIS_URL = "redis://localhost:6379"

def publish_event(event_type: str, data: dict):
    try:
        r = redis.from_url(REDIS_URL)
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        r.publish("website_pitcher_events", json.dumps(event))
        r.close()
    except Exception as e:
        print(f"Failed to publish event: {e}")

# Event types
class EventTypes:
    PIPELINE_START = "pipeline_start"
    PIPELINE_STEP = "pipeline_step"
    LEAD_SCRAPED = "lead_scraped"
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_SCORED = "lead_scored"
    REPORT_GENERATED = "report_generated"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"
