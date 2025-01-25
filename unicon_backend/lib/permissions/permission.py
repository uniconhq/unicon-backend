from typing import Any

import permify as p
from rich import print
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from unicon_backend.constants import PERMIFY_HOST, SCHEMA_VERSION
from unicon_backend.database import SessionLocal
from unicon_backend.models.links import GroupMember, GroupSupervisor, UserRole
from unicon_backend.models.organisation import Group, Organisation, Project, Role
from unicon_backend.models.problem import ProblemORM, SubmissionORM
from unicon_backend.models.user import UserORM

SCHEMA_VERSION = SCHEMA_VERSION
CONFIGURATION = p.Configuration(host=PERMIFY_HOST)
# We don't have tenancy, so this is the same for all requests.
TENANT_ID = "t1"


def debug_list_tuples():
    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)

        tokens = set()
        while True:
            attributes = data_api.data_attributes_read(
                TENANT_ID,
                p.ReadAttributesBody(metadata={"schema_version": SCHEMA_VERSION}, filter={}),
            )

            print(attributes.attributes)
            if not attributes.continuous_token or attributes.continuous_token in tokens:
                break

            tokens.add(attributes.continuous_token)

        tokens = set()
        while True:
            relations = data_api.data_relationships_read(
                TENANT_ID,
                p.ReadRelationshipsBody(
                    metadata={"schema_version": SCHEMA_VERSION},
                    filter={},
                ),
            )
            print(relations.tuples)
            if not relations.continuous_token or relations.continuous_token in tokens:
                break
            tokens.add(relations.continuous_token)


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
# group_tuples [GROUP, member, SUBMISSION]
# group_member_tuples [GROUP, member, USER]
# group_supervisor_tuples [GROUP, supervisor, USER]

# NOT YET IMPLEMENTED
# problem_group_tuples [TO DENOTE]
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
    "view_supervised_submission_access",
    "view_others_submission_access",
    "view_groups_access",
    "create_groups_access",
    "edit_groups_access",
    "delete_groups_access",
]


def permission_lookup(model_class: Any, permission: str, user: UserORM) -> list[int]:
    """Given a model class, return all ids that the user can do PERMISSION on.

    This function uses the Lookup Entity route (https://docs.permify.co/api-reference/permission/lookup-entity)"""
    metadata = p.PermissionLookupEntityRequestMetadata.from_dict(
        {"schema_version": SCHEMA_VERSION, "depth": 200}
    )

    with p.ApiClient(CONFIGURATION) as api_client:
        permission_api = p.PermissionApi(api_client)
        results: list[int] = []
        result = permission_api.permissions_lookup_entity(
            TENANT_ID,
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
            # Handles the weird case where result.continous_token is duplicated
            if not result.continuous_token or result.continuous_token in tokens:
                break
            tokens.add(result.continuous_token)
            result = permission_api.permissions_lookup_entity(
                TENANT_ID,
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
        {"schema_version": SCHEMA_VERSION, "depth": 200}
    )

    with p.ApiClient(CONFIGURATION) as api_client:
        permission_api = p.PermissionApi(api_client)
        result = permission_api.permissions_subject_permission(
            TENANT_ID,
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


def _get_tuples_and_attributes(model: Any) -> tuple[list[p.Tuple], list[p.Attribute]]:
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
    elif model_type is Group:
        tuples, attributes = _create_group(model)
    elif model_type is GroupMember:
        tuples, attributes = _create_group_member(model)
    elif model_type is GroupSupervisor:
        tuples, attributes = _create_group_supervisor(model)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    return tuples, attributes


def permission_create(model: Any):
    """given a model, create permission records for it"""
    tuples, attributes = _get_tuples_and_attributes(model)

    metadata = p.DataWriteRequestMetadata.from_dict({"schema_version": SCHEMA_VERSION})
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)
        data_api.data_write(
            TENANT_ID,
            p.DataWriteBody(metadata=metadata, tuples=tuples, attributes=attributes),
        )


def permission_delete(model: Any):
    """given a model, delete permission records for it"""
    tuples, attributes = _get_tuples_and_attributes(model)

    metadata = p.DataWriteRequestMetadata.from_dict({"schema_version": SCHEMA_VERSION})
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    _delete_tuples_and_attributes(tuples, attributes)


def _delete_tuples_and_attributes(
    delete_tuples: list[p.Tuple], delete_attributes: list[p.Attribute]
):
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
                    attribute_filter=p.AttributeFilter(),
                ),
            )

        for old_attribute in delete_attributes:
            entity = old_attribute.entity
            attribute = old_attribute.attribute
            if entity is None or attribute is None or entity.id is None:
                # This should never happen.
                raise ValueError("Failed to extract entity or attribute")

            data_api.data_delete(
                TENANT_ID,
                p.DataDeleteBody(
                    tuple_filter=p.TupleFilter(),
                    attribute_filter=p.AttributeFilter(
                        entity=p.EntityFilter(type=entity.type, ids=[entity.id]),
                        attributes=[attribute],
                    ),
                ),
            )


def permission_update(old: Any, new: Any, optimised=True):
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
    elif type(old) is Group:
        (delete_tuples, delete_attributes), (create_tuples, create_attributes) = _update_group(
            old, new
        )
    else:
        raise ValueError(f"Unsupported model type: {type(old)}")

    metadata = p.DataWriteRequestMetadata.from_dict({"schema_version": SCHEMA_VERSION})
    if not metadata:
        # This should not happen.
        raise ValueError("Failed to create metadata")

    if optimised:
        # Remove the intersecton of tuples/attributes being deleted/created
        tuples_intersection = [
            t for t in delete_tuples if t in create_tuples and t in delete_tuples
        ]
        attributes_intersection = [
            a for a in delete_attributes if a in create_attributes and a in delete_attributes
        ]
        delete_tuples = [t for t in delete_tuples if t not in tuples_intersection]
        delete_attributes = [a for a in delete_attributes if a not in attributes_intersection]
        create_tuples = [t for t in create_tuples if t not in tuples_intersection]
        create_attributes = [a for a in create_attributes if a not in attributes_intersection]

    _delete_tuples_and_attributes(delete_tuples, delete_attributes)

    # recreate new tuples
    with p.ApiClient(CONFIGURATION) as api_client:
        data_api = p.DataApi(api_client)
        data_api.data_write(
            TENANT_ID,
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


def _get_permify_bool(bool: bool) -> p.Any:
    # I think the type error here is from a weird bug in p.Any where it collides with typing.Any (and should be fine)
    value = p.Any.from_dict({"@type": "type.googleapis.com/base.v1.BooleanValue", "data": bool})  # type:ignore
    return value


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

    group_links = [
        _make_tuple(
            _make_entity("submission", str(submission.id)),
            "group",
            _make_entity("group", str(group.id)),
        )
        for group in submission.user.groups
        if group.project_id == submission.problem.project_id
    ]

    return [submission_problem_link, submission_owner_link] + group_links, []


def _create_group_member(groupMember: GroupMember) -> tuple[list[p.Tuple], list[p.Attribute]]:
    with SessionLocal() as session:
        group = session.get(Group, groupMember.group_id)
        user = session.scalar(
            select(UserORM)
            .where(UserORM.id == groupMember.user_id)
            .options(selectinload(UserORM.submissions).selectinload(SubmissionORM.problem))
        )
        submissions = [
            submission
            for submission in user.submissions
            if submission.problem.project_id == group.project_id
        ]
    group_member_relation_tuple = _make_tuple(
        _make_entity("group", str(groupMember.group_id)),
        "member",
        _make_entity("user", str(groupMember.user_id)),
    )
    submission_tuples = [
        _make_tuple(
            _make_entity("submission", str(submission.id)),
            "group",
            _make_entity("group", str(groupMember.group_id)),
        )
        for submission in submissions
    ]
    return [group_member_relation_tuple] + submission_tuples, []


def _create_group_supervisor(
    groupSupervisor: GroupSupervisor,
) -> tuple[list[p.Tuple], list[p.Attribute]]:
    group_supervisor_relation_tuple = _make_tuple(
        _make_entity("group", str(groupSupervisor.group_id)),
        "supervisor",
        _make_entity("user", str(groupSupervisor.user_id)),
    )
    return [group_supervisor_relation_tuple], []


def _create_group(group: Group) -> tuple[list[p.Tuple], list[p.Attribute]]:
    group_members = [GroupMember(group_id=group.id, user_id=member.id) for member in group.members]
    group_supervisors = [
        GroupSupervisor(group_id=group.id, user_id=supervisor.id)
        for supervisor in group.supervisors
    ]

    tuples = []
    attributes = []
    for member in group_members:
        member_tuples, member_attributes = _create_group_member(member)
        tuples.extend(member_tuples)
        attributes.extend(member_attributes)

    for supervisor in group_supervisors:
        supervisor_tuples, supervisor_attributes = _create_group_supervisor(supervisor)
        tuples.extend(supervisor_tuples)
        attributes.extend(supervisor_attributes)

    return tuples, attributes


def _create_user_role(userRole: UserRole) -> tuple[list[p.Tuple], list[p.Attribute]]:
    """This is the role assignment link"""
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


def _update_group(
    old_group: Group, new_group: Group
) -> tuple[tuple[list[p.Tuple], list[p.Attribute]], tuple[list[p.Tuple], list[p.Attribute]]]:
    """Return tuple to delete and tuple to create"""
    return _create_group(old_group), _create_group(new_group)
