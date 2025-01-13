from typing import Any

import permify as p

from unicon_backend.constants import PERMIFY_HOST, SCHEMA_VERSION
from unicon_backend.models.links import UserRole
from unicon_backend.models.organisation import Organisation, Project, Role
from unicon_backend.models.problem import ProblemORM, SubmissionORM
from unicon_backend.models.user import UserORM

SCHEMA_VERSION = SCHEMA_VERSION
CONFIGURATION = p.Configuration(host=PERMIFY_HOST)
# We don't have tenancy, so this is the same for all requests.
TENANT_ID = "t1"


def init_schema(schemaFilePath: str) -> str:
    """Initialise the schema for the permission system. Returns the schema version."""
    with open(schemaFilePath) as schema_text:
        schema = schema_text.read()

    schema_write_body = p.SchemaWriteBody.from_dict({"schema": str(schema)})
    if schema_write_body is None:
        # This should not happen.
        raise ValueError("Failed to create schema write body")

    with p.ApiClient(CONFIGURATION) as api_client:
        schema_api = p.SchemaApi(api_client)
        response = schema_api.schemas_write("t1", schema_write_body)

        schema_version = response.schema_version
        if not schema_version:
            raise ValueError("Schema version is unexpectedly none. Is the schema valid?")
        return schema_version


def delete_all_permission_records():
    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)
        data_api.data_delete_without_preload_content(TENANT_ID, p.DataDeleteBody())


##########################################
#    List of tuples to make consistent   #
##########################################
# project_tuples [PROJECT, role, USER]
# role_tuples [PROJECT, what_permission_access, ROLE]
# role_assign_tuples [ROLE, assignee, USER]
# problem_tuples [PROBLEM, project, PROJECT]
# submission_tuples [SUBMISSION, "problem", PROBLEM] [SUBMISSION, "owner", USER] [SUBMISSION, "group_owner", GROUP]

# NOT YET IMPLEMENTED
# group_tuples [GROUP, member, USER]
# organisation_tuples [ORGANISATION, owner|admin|observer, USER]

PERMISSIONS = [
    "view_problems_access",
    "create_problems_access",
    "edit_problems_access",
    "delete_problems_access",
    "view_restricted_problems_access",
    "edit_restricted_problems_access",
    "delete_restricted_problems_access",
    "make_submission_access",
    "view_own_submissions_access",
    "view_others_submission_access",
]


def permission_create(model: Any):
    """given a model, create permission records for it"""
    model_type = type(model)

    if model_type is Project:
        tuples = _create_project(model)
    elif model_type is Role:
        tuples = _create_role(model)
    elif model_type is ProblemORM:
        tuples = _create_problem(model)
    elif model_type is SubmissionORM:
        tuples = _create_submission(model)
    elif model_type is UserRole:
        tuples = _create_user_role(model)
    elif model_type is Organisation:
        tuples = _create_organisation(model)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    metadata = p.DataWriteRequestMetadata.from_dict({"schema_version": SCHEMA_VERSION})
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)
        data_api.data_write(
            TENANT_ID,
            p.DataWriteBody(metadata=metadata, tuples=tuples),
        )


def permission_update(old: Any, new: Any):
    """given a model, update permission records for it"""
    if type(old) != type(new):
        raise ValueError("Old and new models must be of the same type")

    if type(old) is Role:
        delete_tuples, create_tuples = _update_role(old, new)
    else:
        raise ValueError(f"Unsupported model type: {type(old)}")

    metadata = p.DataWriteRequestMetadata.from_dict({"schema_version": SCHEMA_VERSION})
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)

        # delete old tuples
        for old_tuple in delete_tuples:
            entity = old_tuple.entity
            relation = old_tuple.relation
            subject = old_tuple.subject
            if (
                entity is None
                or relation is None
                or subject is None
                or entity.id is None
                or subject.id is None
            ):
                # This should never happen.
                raise ValueError("Failed to extract entity, relation, or subject")

            data_api.data_delete(
                TENANT_ID,
                p.DataDeleteBody(
                    tuple_filter=p.TupleFilter(
                        entity=p.EntityFilter(type=entity.type, ids=[entity.id]),
                        relation=relation,
                        subject=p.SubjectFilter(type=subject.type, ids=[subject.id]),
                    ),
                ),
            )

        # recreate new tuples
        data_api.data_write(
            TENANT_ID,
            p.DataWriteBody(metadata=metadata, tuples=create_tuples),
        )


def _model_to_type(model: Any) -> str:
    if type(model) is Project:
        return "project"
    if type(model) is Role:
        return "role"
    if type(model) is ProblemORM:
        return "problem"
    if type(model) is SubmissionORM:
        return "submission"
    if type(model) is UserORM:
        return "user"
    raise ValueError(f"Unsupported model type: {type(model)}")


def permission_check(entity, permission, subject) -> bool:
    """can SUBJECT (probably the user) do PERMISSION on ENTITY?"""
    metadata = p.PermissionCheckRequestMetadata.from_dict(
        {"schema_version": SCHEMA_VERSION, "depth": 200}
    )
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    with p.ApiClient(CONFIGURATION) as api_client:
        permissions_api = p.PermissionApi(api_client)
        result = permissions_api.permissions_check(
            TENANT_ID,
            p.CheckBody(
                metadata=metadata,
                entity=_make_entity(_model_to_type(entity), str(entity.id)),
                permission=permission,
                subject=_make_entity(_model_to_type(subject), str(subject.id)),
            ),
        )
        return result.can == p.CheckResult.CHECK_RESULT_ALLOWED


def _make_tuple(entity, relation, subject) -> p.Tuple:
    result = p.Tuple.from_dict({"entity": entity, "relation": relation, "subject": subject})
    if result is None:
        # This should never happen.
        raise ValueError("Failed to create tuple")
    return result


def _make_entity(type: str, id: str):
    return {"type": type, "id": id}


def _create_organisation(organisation: Organisation):
    owner_link = _make_tuple(
        _make_entity("organisation", str(organisation.id)),
        "owner",
        _make_entity("user", str(organisation.owner_id)),
    )
    return [owner_link]


def _create_project(project: Project) -> list[p.Tuple]:
    project_organisation_link = _make_tuple(
        _make_entity("project", str(project.id)),
        "org",
        _make_entity("organisation", str(project.organisation_id)),
    )
    return [project_organisation_link]


def _create_role(role: Role) -> list[p.Tuple]:
    role_access_links = [
        _make_tuple(
            _make_entity("project", str(role.project_id)),
            permission,
            {**_make_entity("role", str(role.id)), "relation": "assignee"},
        )
        for permission in PERMISSIONS
        if getattr(role, permission)
    ]
    return role_access_links


def _create_problem(problem: ProblemORM) -> list[p.Tuple]:
    problem_project_link = _make_tuple(
        _make_entity("problem", str(problem.id)),
        "project",
        _make_entity("project", str(problem.project_id)),
    )
    return [problem_project_link]


def _create_submission(submission: SubmissionORM) -> list[p.Tuple]:
    submission_problem_link = _make_tuple(
        _make_entity("submission", str(submission.id)),
        "problem",
        _make_entity("problem", str(submission.problem_id)),
    )

    # TODO: account for group submissions
    submission_owner_link = _make_tuple(
        _make_entity("submission", str(submission.id)),
        "owner",
        _make_entity("user", str(submission.user_id)),
    )
    return [submission_problem_link, submission_owner_link]


def _create_user_role(userRole: UserRole):
    """this is role assignment link"""
    assignee_link = _make_tuple(
        _make_entity("role", str(userRole.role_id)),
        "assignee",
        _make_entity("user", str(userRole.user_id)),
    )
    return [assignee_link]


def _update_role(old_role: Role, new_role: Role) -> tuple[list[p.Tuple], list[p.Tuple]]:
    """Return tuple to delete and tuple to create"""
    return _create_role(old_role), _create_role(new_role)
