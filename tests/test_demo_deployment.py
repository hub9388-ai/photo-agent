"""Deployment-only budget/preflight tests, no running services or model calls."""
import asyncio
import importlib.util
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


guard = module("demo_guard_test", "deploy/full-demo/support/demo_guard.py")
preflight = module("demo_preflight_test", "deploy/full-demo/preflight.py")


class BudgetTests(unittest.TestCase):
    def test_global_atomic_budget_shared_across_connections(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/"budget.sqlite3")
            with ThreadPoolExecutor(max_workers=8) as pool:
                accepted = list(pool.map(lambda _: guard.charge(path, 5, "2026-10-18"), range(20)))
            self.assertEqual(sum(accepted), 5)
            self.assertTrue(guard.charge(path, 5, "2026-10-19"))


class MiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_counted_attempts_block_but_get_and_brush_still_work(self):
        calls = []
        async def app(scope, receive, send):
            calls.append(scope["path"])
        async def receive():
            return {}
        with tempfile.TemporaryDirectory() as folder:
            wrapped = guard.DemoGuard(app, path=str(Path(folder)/"budget.sqlite3"), limit=1)
            output = []
            async def send(message):
                output.append(message)
            await wrapped({"type":"http","method":"POST","path":"/api/jobs"}, receive, send)
            await wrapped({"type":"http","method":"POST","path":"/api/sessions/x/tools"}, receive, send)
            self.assertEqual(output[0]["status"],429)
            await wrapped({"type":"http","method":"GET","path":"/api/jobs/x/events"}, receive, send)
            await wrapped({"type":"http","method":"POST","path":"/api/sessions/x/selection"}, receive, send)
            self.assertEqual(len(calls),3)

    async def test_database_failure_does_not_permit_paid_calls(self):
        calls=[]
        async def app(*args):
            calls.append(True)
        output=[]
        async def send(message):
            output.append(message)
        with tempfile.TemporaryDirectory() as folder:
            await guard.DemoGuard(app,path=folder,limit=1)({"type":"http","method":"POST","path":"/api/generations"},None,send)
        self.assertFalse(calls)
        self.assertEqual(output[0]["status"],429)


class PreflightTests(unittest.TestCase):
    def test_template_rejected_and_error_messages_hide_values(self):
        secret="private-fixture-value"
        errors=preflight.validate({"DEEPSEEK_API_KEY":secret})
        self.assertTrue(errors)
        self.assertNotIn(secret,"\n".join(errors))

    def test_valid_synthetic_configuration(self):
        values={"SITE_HOST":"demo.example.org","OBJECTS_HOST":"objects.example.org","ACME_EMAIL":"dev@example.org",
            "DEMO_USER":"interview","DEMO_PASSWORD_HASH":"$2b$14$"+"a"*53,
            "POSTGRES_PASSWORD":"a"*64,"MINIO_USER":"demo","MINIO_PASSWORD":"b"*64,
            "RETOUCH_JWT_SECRET":"c"*64,"DEEPSEEK_API_KEY":"fake-test","DASHSCOPE_API_KEY":"fake-test"}
        self.assertEqual(preflight.validate(values),[])


if __name__=="__main__":
    unittest.main()
