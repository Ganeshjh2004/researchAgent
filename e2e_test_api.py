import sys
import time
from fastapi.testclient import TestClient
from api import app

def run_e2e():
    print("Starting End-to-End Async API Test...")
    client = TestClient(app)
    
    start_time = time.time()
    
    # 1. Submit task
    response = client.post(
        "/api/v1/research", 
        json={"query": "Research FastAPI dependency injection and summarize."}
    )
    assert response.status_code == 202
    data = response.json()
    task_id = data["task_id"]
    print(f"Task submitted successfully. Task ID: {task_id}")
    
    # 2. Poll for completion
    max_wait = 60 # seconds
    poll_interval = 2
    status = "queued"
    
    while status in ["queued", "running"] and (time.time() - start_time) < max_wait:
        time.sleep(poll_interval)
        poll_resp = client.get(f"/api/v1/research/{task_id}")
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()
        status = poll_data["status"]
        print(f"  Status: {status}...")
        
    duration = time.time() - start_time
    print(f"Execution finished in {duration:.2f} seconds with status: {status}")
    
    if status not in ["completed", "failed"]:
        print("Test failed: timeout or invalid status.")
        sys.exit(1)
        
    # 3. Retrieve Result
    result_resp = client.get(f"/api/v1/research/{task_id}/result")
    assert result_resp.status_code == 200
    res_data = result_resp.json()
    
    print("\nResult JSON:")
    for k, v in res_data.items():
        if k == "summary" and v:
            print(f"  {k}: {v[:100]}...".encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        else:
            print(f"  {k}: {v}".encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
            
    if status == "completed":
        assert res_data["filename"] is not None
        
        # 4. Retrieve Report
        report_resp = client.get(f"/api/v1/research/{task_id}/report")
        assert report_resp.status_code == 200
        report_content = report_resp.text
        assert len(report_content) > 0
        print(f"\nReport downloaded successfully ({len(report_content)} bytes).")
        print("\nE2E Test Passed Successfully (Workflow Complete)!")
    else:
        assert res_data["error"] is not None
        print(f"\nE2E Test Passed Successfully (Workflow Failed gracefully with error: {res_data['error']})!")

if __name__ == "__main__":
    run_e2e()
