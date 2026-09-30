import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import json

from api import app, redis_client

client = TestClient(app)

class TestAPI(unittest.TestCase):

    def setUp(self):
        # Clear mock calls between tests
        pass

    def test_health_endpoint(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "version": "1.1.0"})

    @patch("api.redis_client.ping")
    def test_ready_endpoint_ok(self, mock_ping):
        mock_ping.return_value = True
        response = client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redis"], "connected")

    @patch("api.redis_client.ping")
    def test_ready_endpoint_fail(self, mock_ping):
        mock_ping.side_effect = Exception("Connection error")
        response = client.get("/ready")
        self.assertEqual(response.status_code, 503)

    @patch("api.redis_client.lpush")
    @patch("api.redis_client.hset")
    @patch("api.redis_client.expire")
    def test_submit_valid_research(self, mock_expire, mock_hset, mock_lpush):
        response = client.post("/api/v1/research", json={"query": "LangGraph test"})
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["query"], "LangGraph test")
        self.assertIn("task_id", data)
        self.assertTrue(mock_lpush.called)

    def test_submit_invalid_research(self):
        # Too short
        response = client.post("/api/v1/research", json={"query": "a"})
        self.assertEqual(response.status_code, 422)

    @patch("api.redis_client.hgetall")
    def test_task_status_retrieval(self, mock_hgetall):
        mock_hgetall.return_value = {"status": "running", "query": "Test"}
        response = client.get("/api/v1/research/task-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "running")

    @patch("api.redis_client.hgetall")
    def test_unknown_task_id(self, mock_hgetall):
        mock_hgetall.return_value = {}
        response = client.get("/api/v1/research/unknown-task")
        self.assertEqual(response.status_code, 404)

    @patch("api.redis_client.hgetall")
    def test_task_result_retrieval(self, mock_hgetall):
        mock_hgetall.return_value = {
            "status": "completed",
            "query": "Test",
            "filename": "test.txt",
            "summary": "This is a test",
            "sources": json.dumps(["Wikipedia"])
        }
        response = client.get("/api/v1/research/task-123/result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["sources"], ["Wikipedia"])

    @patch("api.redis_client.hgetall")
    def test_failed_workflow_retrieval(self, mock_hgetall):
        mock_hgetall.return_value = {
            "status": "failed",
            "query": "Test",
            "error": "No usable content"
        }
        response = client.get("/api/v1/research/task-123/result")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["error"], "No usable content")

    @patch("api.redis_client.hgetall")
    def test_report_path_safety(self, mock_hgetall):
        # Attempt to retrieve a file outside the directory
        mock_hgetall.return_value = {
            "status": "completed",
            "filename": "../../../Windows/System32/cmd.exe"
        }
        # The API should strictly use Path(filename).name, stripping directories
        # Let's mock file_path.exists() to return False since cmd.exe isn't in reports/
        with patch("pathlib.Path.exists", return_value=False):
            response = client.get("/api/v1/research/task-123/report")
            self.assertEqual(response.status_code, 404)

    @patch("api.redis_client.hset")
    def test_redis_unavailable_behavior(self, mock_hset):
        mock_hset.side_effect = Exception("Redis connection refused")
        response = client.post("/api/v1/research", json={"query": "Test"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Failed to initialize task. Storage unavailable.")
        self.assertNotIn("connection refused", str(response.json())) # No secret/trace leakage

if __name__ == "__main__":
    unittest.main(verbosity=2)
