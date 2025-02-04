from typing import Any, Final

import permify as p
from rich import print

from unicon_backend.constants import PERMIFY_HOST, PERMIFY_SCHEMA_VERSION, PERMIFY_TENANT_ID
from unicon_backend.models.links import UserRole
from unicon_backend.models.organisation import Organisation, Project, Role
from unicon_backend.models.problem import ProblemORM, SubmissionORM
from unicon_backend.models.user import UserORM

CONFIGURATION = p.Configuration(host=PERMIFY_HOST)

_api_client = p.ApiClient(p.Configuration(host=PERMIFY_HOST))
_data_api = p.DataApi(_api_client)
_schema_api = p.SchemaApi(_api_client)
_perms_api = p.PermissionApi(_api_client)


def _get_latest_schema_version() -> str | None:
    """Get the latest schema version from Permify."""
    return _schema_api.schemas_list(PERMIFY_TENANT_ID, p.SchemaListBody()).head


SCHEMA_VERSION: str | None = PERMIFY_SCHEMA_VERSION or _get_latest_schema_version()

if SCHEMA_VERSION is None:
    raise RuntimeError("Failed to get Permify schema version!")


DEFAULT_METADATA: Final = {"schema_version": SCHEMA_VERSION}


def debug_list_tuples():
    attributes = _data_api.data_attributes_read(
        PERMIFY_TENANT_ID, p.ReadAttributesBody(metadata=DEFAULT_METADATA, filter={})
    )
    print(attributes)

    relations = _data_api.data_relationships_read(
        PERMIFY_TENANT_ID, p.ReadRelationshipsBody(metadata=DEFAULT_METADATA, filter={})
    )
    print(relations)


def delete_all_permission_records():
    _data_api.data_delete_without_preload_content(PERMIFY_TENANT_ID, p.DataDeleteBody())


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
    "view_own_submission_access",
    "view_others_submission_access",
]

DEPTH: Final[int] = 200


def permission_lookup(model_class: Any, permission: str, user: UserORM) -> list[int]:
    """Given a model class, return all ids that the user can do PERMISSION on.

    This function uses the Lookup Entity route (https://docs.permify.co/api-reference/permission/lookup-entity)"""
    metadata = p.PermissionLookupEntityRequestMetadata.from_dict(
        {**DEFAULT_METADATA, "depth": DEPTH}
    )

    results: list[int] = []
    result = _perms_api.permissions_lookup_entity(
        PERMIFY_TENANT_ID,
        p.LookupEntityBody(
            metadata=metadata,
            entity_type=_model_to_type(model_class),
            permission=permission,
            subject=p.Subject(type="user", id=str(user.id)),
        ),
    )

    tokens = set()
    while True:
        results.extend([int(entity_id) for entity_id in result.entity_ids or []])

        # Handles the weird case where `result.continous_token` is duplicated
        if not (result.continuous_token and result.continuous_token not in tokens):
            break
        tokens.add(result.continuous_token)

        result = _perms_api.permissions_lookup_entity(
            PERMIFY_TENANT_ID,
            p.LookupEntityBody(
                metadata=metadata,
                entity_type=_model_to_type(model_class),
                permission=permission,
                subject=p.Subject(type="user", id=str(user.id)),
                continuous_token=result.continuous_token,
            ),
        )
    return results


def permission_list_for_subject(model: Any, user: UserORM) -> dict[str, bool]:
    """Which permissions user:x can perform on entity:y?

    This function users the Subject Permission List route (https://docs.permify.co/api-reference/permission/subject-permission)
    """
    metadata = p.PermissionSubjectPermissionRequestMetadata.from_dict(
        {**DEFAULT_METADATA, "depth": DEPTH}
    )

    result = _perms_api.permissions_subject_permission(
        PERMIFY_TENANT_ID,
        p.SubjectPermissionBody(
            metadata=metadata,
            entity=_make_entity(_model_to_type(model), str(model.id)),
            subject=_make_entity("user", str(user.id)),
        ),
    )

    if not result.results:
        # This should not happen.
        raise ValueError("No results found")

    return {
        permission: allowed == p.CheckResult.CHECK_RESULT_ALLOWED
        for permission, allowed in result.results.items()
    }


def permission_create(model: Any):
    """given a model, create permission records for it"""
    model_type = type(model)

    if model_type is Project:
        tuples, attributes = _create_project(model)
    elif model_type is Role:
        tuples, attributes = _create_role(model)
    elif model_type is ProblemORM:
        tuples, attributes = _create_problem(model)
    elif model_type is SubmissionORM:
        tuples, attributes = _create_submission(model)
    elif model_type is UserRole:
        tuples, attributes = _create_user_role(model)
    elif model_type is Organisation:
        tuples, attributes = _create_organisation(model)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    if (metadata := p.DataWriteRequestMetadata.from_dict(DEFAULT_METADATA)) is None:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    _data_api.data_write(
        PERMIFY_TENANT_ID,
        p.DataWriteBody(metadata=metadata, tuples=tuples, attributes=attributes),
    )


def permission_update(old: Any, new: Any):
    """given a model, update permission records for it"""
    if type(old) != type(new):
        raise ValueError("Old and new models must be of the same type")

    if type(old) is Role:
        (delete_tuples, delete_attributes), (create_tuples, create_attributes) = _update_role(
            old, new
        )
    elif type(old) is ProblemORM:
        (delete_tuples, delete_attributes), (create_tuples, create_attributes) = _update_problem(
            old, new
        )
    else:
        raise ValueError(f"Unsupported model type: {type(old)}")

    if (metadata := p.DataWriteRequestMetadata.from_dict(DEFAULT_METADATA)) is None:
        # This should not happen.
        raise ValueError("Failed to create metadata")

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

        _data_api.data_delete(
            PERMIFY_TENANT_ID,
            p.DataDeleteBody(
                tuple_filter=p.TupleFilter(
                    entity=p.EntityFilter(type=entity.type, ids=[entity.id]),
                    relation=relation,
                    subject=p.SubjectFilter(type=subject.type, ids=[subject.id]),
                ),
                attribute_filter=p.AttributeFilter(),
            ),
        )

    for old_attribute in delete_attributes:
        entity = old_attribute.entity
        attribute = old_attribute.attribute
        if entity is None or attribute is None or entity.id is None:
            # This should never happen.
            raise ValueError("Failed to extract entity or attribute")

        _data_api.data_delete(
            PERMIFY_TENANT_ID,
            p.DataDeleteBody(
                tuple_filter=p.TupleFilter(),
                attribute_filter=p.AttributeFilter(
                    entity=p.EntityFilter(type=entity.type, ids=[entity.id]),
                    attributes=[attribute],
                ),
            ),
        )

    # recreate new tuples
    _data_api.data_write(
        PERMIFY_TENANT_ID,
        p.DataWriteBody(metadata=metadata, tuples=create_tuples, attributes=create_attributes),
    )


def _model_to_type(model: Any) -> str:
    model_type = model if isinstance(model, type) else type(model)

    if model_type is Organisation:
        return "organisation"
    if model_type is Project:
        return "project"
    if model_type is Role:
        return "role"
    if model_type is ProblemORM:
        return "problem"
    if model_type is SubmissionORM:
        return "submission"
    if model_type is UserORM:
        return "user"
    raise ValueError(f"Unsupported model type: {type(model)}")


def permission_check(entity, permission, subject) -> bool:
    """can SUBJECT (probably the user) do PERMISSION on ENTITY?"""
    if (
        metadata := p.PermissionCheckRequestMetadata.from_dict({**DEFAULT_METADATA, "depth": DEPTH})
    ) is None:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    result = _perms_api.permissions_check(
        PERMIFY_TENANT_ID,
        p.CheckBody(
            metadata=metadata,
            entity=_make_entity(_model_to_type(entity), str(entity.id)),
            permission=permission,
            subject=_make_entity(_model_to_type(subject), str(subject.id)),
        ),
    )
    return result.can == p.CheckResult.CHECK_RESULT_ALLOWED


def _make_tuple(entity, relation, subject) -> p.Tuple:
    if (
        result := p.Tuple.from_dict({"entity": entity, "relation": relation, "subject": subject})
    ) is None:
        # This should never happen.
        raise ValueError("Failed to create tuple")

    return result


def _get_permify_bool(bool: bool) -> p.Any:
    # I think the type error here is from a weird bug in p.Any where it collides with typing.Any (and should be fine)
    return p.Any.from_dict({"@type": "type.googleapis.com/base.v1.BooleanValue", "data": bool})  # type:ignore


def _make_attribute(entity, attribute, value) -> p.Attribute:
    attribute = p.Attribute.from_dict({"entity": entity, "attribute": attribute, "value": value})
    if not attribute:
        raise ValueError("Failed to create attribute")
    return attribute


def _make_entity(type: str, id: str):
    return {"type": type, "id": id}


def _create_organisation(organisation: Organisation) -> tuple[list[p.Tuple], list[p.Attribute]]:
    owner_link = _make_tuple(
        _make_entity("organisation", str(organisation.id)),
        "owner",
        _make_entity("user", str(organisation.owner_id)),
    )
    return [owner_link], []


def _create_project(project: Project) -> tuple[list[p.Tuple], list[p.Attribute]]:
    project_organisation_link = _make_tuple(
        _make_entity("project", str(project.id)),
        "org",
        _make_entity("organisation", str(project.organisation_id)),
    )
    return [project_organisation_link], []


def _create_role(role: Role) -> tuple[list[p.Tuple], list[p.Attribute]]:
    role_access_links = [
        _make_tuple(
            _make_entity("project", str(role.project_id)),
            permission,
            {**_make_entity("role", str(role.id)), "relation": "assignee"},
        )
        for permission in PERMISSIONS
        if getattr(role, permission)
    ]
    return role_access_links, []


def _create_problem(problem: ProblemORM) -> tuple[list[p.Tuple], list[p.Attribute]]:
    problem_project_link = _make_tuple(
        _make_entity("problem", str(problem.id)),
        "project",
        _make_entity("project", str(problem.project_id)),
    )
    restricted = problem.restricted
    attribute = _make_attribute(
        _make_entity("problem", str(problem.id)),
        "restricted",
        _get_permify_bool(restricted),
    )
    return [problem_project_link], [attribute]


def _create_submission(submission: SubmissionORM) -> tuple[list[p.Tuple], list[p.Attribute]]:
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
    return [submission_problem_link, submission_owner_link], []


def _create_user_role(userRole: UserRole) -> tuple[list[p.Tuple], list[p.Attribute]]:
    """this is role assignment link"""
    assignee_link = _make_tuple(
        _make_entity("role", str(userRole.role_id)),
        "assignee",
        _make_entity("user", str(userRole.user_id)),
    )
    return [assignee_link], []


def _update_role(
    old_role: Role, new_role: Role
) -> tuple[tuple[list[p.Tuple], list[p.Attribute]], tuple[list[p.Tuple], list[p.Attribute]]]:
    """Return tuple to delete and tuple to create"""
    return _create_role(old_role), _create_role(new_role)


def _update_problem(
    old_problem: ProblemORM, new_problem: ProblemORM
) -> tuple[tuple[list[p.Tuple], list[p.Attribute]], tuple[list[p.Tuple], list[p.Attribute]]]:
    """Return tuple to delete and tuple to create"""
    return _create_problem(old_problem), _create_problem(new_problem)
