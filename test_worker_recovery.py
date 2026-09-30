import time
import os
import signal
import sys
import subprocess
import uuid
import redis

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URI, decode_responses=True)

def test_recovery():
    print("--- Testing Worker Recovery ---")
    
    # 1. Clear queues for clean test
    redis_client.delete("research:queue")
    redis_client.delete("research:processing")
    
    # 2. Inject a fake running task directly into processing queue as if a worker crashed
    task_id = str(uuid.uuid4())
    task_key = f"task:{task_id}"
    
    redis_client.hset(task_key, mapping={
        "status": "running",
        "query": "Test crash recovery",
        "retries": "0",
        "last_heartbeat": str(time.time() - 40) # 40 seconds ago (VISIBILITY_TIMEOUT is 35)
    })
    
    redis_client.lpush("research:processing", task_id)
    print(f"Injected abandoned task {task_id} into research:processing")
    
    from worker import recover_abandoned_tasks
    
    print("Running recovery sweep...")
    recover_abandoned_tasks()
    
    # 4. Verify recovery happened
    task_data = redis_client.hgetall(task_key)
    status = task_data.get("status")
    retries = task_data.get("retries")
    
    print(f"Task status after recovery: {status}")
    print(f"Task retries after recovery: {retries}")
    
    # It should have been moved back to research:queue
    queue_len = redis_client.llen("research:queue")
    processing_len = redis_client.llen("research:processing")
    
    print(f"Queue length: {queue_len} (expected 1)")
    print(f"Processing length: {processing_len} (expected 0)")
    
    assert status == "queued", f"Expected queued, got {status}"
    assert retries == "1", f"Expected 1, got {retries}"
    assert queue_len == 1, "Task not in queue"
    assert processing_len == 0, "Task still in processing queue"
    
    # Test max retries
    redis_client.hset(task_key, mapping={
        "status": "running",
        "retries": "2",  # Max is 2
        "last_heartbeat": str(time.time() - 40)
    })
    redis_client.lpush("research:processing", task_id)
    redis_client.lrem("research:queue", 0, task_id)
    
    print("Running recovery sweep for max retries...")
    recover_abandoned_tasks()
    
    task_data = redis_client.hgetall(task_key)
    assert task_data.get("status") == "failed", "Expected failed status"
    assert redis_client.llen("research:processing") == 0, "Task should be removed from processing"
    
    print("--- Recovery Test Passed! ---")

if __name__ == "__main__":
    test_recovery()
