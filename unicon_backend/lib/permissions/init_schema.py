"""
constants.py imports this and almost everything (includes permissions.py) imports constants.py.
This is separated from permissions.py to prevent  a circular import.
"""

import permify as p

TENANT_ID = "t1"


def get_schema_version(permify_host: str) -> str | None:
    with p.ApiClient(p.Configuration(host=permify_host)) as api_client:
        schema_api = p.SchemaApi(api_client)
        response = schema_api.schemas_list(TENANT_ID, p.SchemaListBody())
        return response.head


def init_schema(permify_host: str, schema: str) -> str:
    """Initialise the schema for the permission system. Returns the schema version."""

    schema_write_body = p.SchemaWriteBody.from_dict({"schema": str(schema)})
    if schema_write_body is None:
        # This should not happen.
        raise ValueError("Failed to create schema write body")

    with p.ApiClient(p.Configuration(host=permify_host)) as api_client:
        schema_api = p.SchemaApi(api_client)
        response = schema_api.schemas_write("t1", schema_write_body)

        schema_version = response.schema_version
        if not schema_version:
            raise ValueError("Schema version is unexpectedly none. Is the schema valid?")
        return schema_version
