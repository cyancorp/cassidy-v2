from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.api import UserPreferencesResponse, UserPreferencesUpdate, UserTemplateResponse, TemplateUpdate, SectionDetailDef
from app.repositories.user import UserPreferencesRepository, UserTemplateRepository
from app.core.deps import get_current_user
from app.models.user import UserDB
from app.templates.loader import template_loader

router = APIRouter()


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's preferences"""
    prefs_repo = UserPreferencesRepository()
    prefs = await prefs_repo.get_by_user_id(db, current_user.id)
    
    if not prefs:
        # Create default preferences if none exist
        prefs = await prefs_repo.create(
            db,
            user_id=current_user.id,
            purpose_statement=None,
            long_term_goals=[],
            known_challenges=[],
            preferred_feedback_style="supportive",
            personal_glossary={}
        )
    
    return UserPreferencesResponse(
        user_id=prefs.user_id,
        purpose_statement=prefs.purpose_statement,
        long_term_goals=prefs.long_term_goals,
        known_challenges=prefs.known_challenges,
        preferred_feedback_style=prefs.preferred_feedback_style,
        personal_glossary=prefs.personal_glossary,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at
    )


@router.post("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    request: UserPreferencesUpdate,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's preferences"""
    prefs_repo = UserPreferencesRepository()
    
    # Get current preferences or create if don't exist
    prefs = await prefs_repo.get_by_user_id(db, current_user.id)
    if not prefs:
        prefs = await prefs_repo.create(
            db,
            user_id=current_user.id,
            purpose_statement=None,
            long_term_goals=[],
            known_challenges=[],
            preferred_feedback_style="supportive",
            personal_glossary={}
        )
    
    # Update with provided values
    update_data = {}
    if request.purpose_statement is not None:
        update_data["purpose_statement"] = request.purpose_statement
    if request.long_term_goals is not None:
        update_data["long_term_goals"] = request.long_term_goals
    if request.known_challenges is not None:
        update_data["known_challenges"] = request.known_challenges
    if request.preferred_feedback_style is not None:
        update_data["preferred_feedback_style"] = request.preferred_feedback_style
    if request.personal_glossary is not None:
        update_data["personal_glossary"] = request.personal_glossary
    
    if update_data:
        prefs = await prefs_repo.update_by_user_id(db, current_user.id, **update_data)
    
    return UserPreferencesResponse(
        user_id=prefs.user_id,
        purpose_statement=prefs.purpose_statement,
        long_term_goals=prefs.long_term_goals,
        known_challenges=prefs.known_challenges,
        preferred_feedback_style=prefs.preferred_feedback_style,
        personal_glossary=prefs.personal_glossary,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at
    )


@router.get("/template", response_model=UserTemplateResponse)
async def get_user_template(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's template from file-based system"""
    # Get template from file instead of database
    template_data = template_loader.get_user_template(current_user.id)
    
    # Convert to API response format
    sections = {}
    for section_name, section_def in template_data["sections"].items():
        sections[section_name] = SectionDetailDef(
            description=section_def["description"],
            aliases=section_def["aliases"]
        )
    
    return UserTemplateResponse(
        user_id=current_user.id,
        name=template_data["name"],
        sections=sections,
        is_active=True,
        created_at=None,  # File-based templates don't have timestamps
        updated_at=None
    )


@router.post("/template", response_model=UserTemplateResponse)
async def update_user_template(
    request: TemplateUpdate,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's template"""
    template_repo = UserTemplateRepository()
    
    # Get current template
    template = await template_repo.get_active_by_user_id(db, current_user.id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active template found"
        )
    
    # Update with provided values
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.sections is not None:
        update_data["sections"] = {k: v.model_dump() for k, v in request.sections.items()}
    
    if update_data:
        template = await template_repo.update(db, template.id, **update_data)
    
    return UserTemplateResponse(
        user_id=template.user_id,
        name=template.name,
        sections={k: SectionDetailDef(**v) for k, v in template.sections.items()},
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


@router.post("/reset")
async def reset_user_preferences(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset user preferences to defaults and refresh template from file"""
    prefs_repo = UserPreferencesRepository()
    
    # Delete existing preferences
    existing_prefs = await prefs_repo.get_by_user_id(db, current_user.id)
    if existing_prefs:
        await prefs_repo.delete(db, existing_prefs.id)
    
    # Create fresh default preferences
    new_prefs = await prefs_repo.create(
        db,
        user_id=current_user.id,
        purpose_statement=None,
        long_term_goals=[],
        known_challenges=[],
        preferred_feedback_style="supportive",
        personal_glossary={}
    )
    
    # Reload template from file
    template_loader.reload_template()
    
    return {
        "status": "success",
        "message": "User preferences reset to defaults and template refreshed from file",
        "user_id": current_user.id,
        "preferences_reset": True,
        "template_reloaded": True
    }