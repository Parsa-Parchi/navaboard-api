from django.test import SimpleTestCase, override_settings
from drf_spectacular.generators import SchemaGenerator


@override_settings(AUTH_ENABLE_EMAIL_SIGNUP=False)
class FrontendSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def test_every_operation_has_actionable_documentation(self):
        for path, item in self.schema["paths"].items():
            for method, operation in item.items():
                if method not in {"get", "post", "patch", "put", "delete"}:
                    continue
                with self.subTest(path=path, method=method):
                    self.assertTrue(operation.get("summary"))
                    self.assertTrue(operation.get("description"))
                    self.assertNotIn("API operation", operation["summary"])
                    self.assertNotIn("management endpoint", operation["description"])

    def test_phone_first_and_cookie_contract(self):
        paths = self.schema["paths"]
        self.assertNotIn("/api/auth/email/signup/request/", paths)
        self.assertIn("/api/auth/csrf/", paths)
        operation = paths["/api/auth/token/refresh/"]["post"]
        self.assertNotIn("requestBody", operation)
        self.assertTrue(any(p["name"] == "X-CSRFToken" for p in operation["parameters"]))

    def test_examples_match_request_field_names(self):
        schemas = self.schema["components"]["schemas"]
        for path, item in self.schema["paths"].items():
            for method, operation in item.items():
                for content in operation.get("requestBody", {}).get("content", {}).values():
                    if "example" not in content:
                        continue
                    schema = content["schema"]
                    if "$ref" in schema:
                        schema = schemas[schema["$ref"].split("/")[-1]]
                    with self.subTest(path=path, method=method):
                        self.assertFalse(set(content["example"]) - set(schema.get("properties", {})))
                        self.assertTrue(set(schema.get("required", [])) <= set(content["example"]))
