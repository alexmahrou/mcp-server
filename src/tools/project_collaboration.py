from api_connection import post
from models import (
    CreateCollaboratorRequest,
    ReadCollaboratorsRequest,
    UpdateCollaboratorRequest,
    DeleteCollaboratorRequest,
    CreateCollaboratorResponse,
    ReadCollaboratorsResponse,
    UpdateCollaboratorResponse,
    DeleteCollaboratorResponse
)
from tool_args import tool_with_args

def register_project_collaboration_tools(mcp):
    # Create
    @tool_with_args(
        mcp,
        CreateCollaboratorRequest,
        annotations={
            'title': 'Create project collaborator',
            'destructiveHint': False,
            'idempotentHint': True
        }
    )
    async def create_project_collaborator(
            model: CreateCollaboratorRequest) -> CreateCollaboratorResponse:
        """Add a collaborator to a project."""
        return await post('/projects/collaboration/create', model)

    # Read
    @tool_with_args(
        mcp,
        ReadCollaboratorsRequest,
        annotations={
            'title': 'Read project collaborators',
            'readOnlyHint': True
        }
    )
    async def read_project_collaborators(
            model: ReadCollaboratorsRequest) -> ReadCollaboratorsResponse:
        """List all collaborators on a project."""
        return await post('/projects/collaboration/read', model)

    # Update
    @tool_with_args(
        mcp,
        UpdateCollaboratorRequest,
        annotations={
            'title': 'Update project collaborator',
            'idempotentHint': True
        }
    )
    async def update_project_collaborator(
            model: UpdateCollaboratorRequest) -> UpdateCollaboratorResponse:
        """Update collaborator information in a project."""
        return await post('/projects/collaboration/update', model)

    # Delete
    @tool_with_args(
        mcp,
        DeleteCollaboratorRequest,
        annotations={
            'title': 'Delete project collaborator',
            'idempotentHint': True
        }
    )
    async def delete_project_collaborator(
            model: DeleteCollaboratorRequest) -> DeleteCollaboratorResponse:
        """Remove a collaborator from a project."""
        return await post('/projects/collaboration/delete', model)
