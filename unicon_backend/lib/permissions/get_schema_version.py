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
