from fastapi import APIRouter, HTTPException, Body
import logging
from pydantic import BaseModel

from app import repositories
from app.models.user import UserTemplate, UserPreferences

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Request Models ---
class UpdateUserPreferencesRequest(BaseModel):
    # Allow updating specific fields, make others optional later if needed
    purpose_statement: str | None = None
    # Add other preferences fields here later (known_challenges, etc.)

# --- User Data Endpoints --- 

@router.get("/template", response_model=UserTemplate)
async def get_user_template():
    """Retrieves the current user template."""
    # Use a default user ID since we don't have auth yet
    default_user_id = "default_user"
    logger.info("Retrieving user template.")
    template = repositories.load_user_template(default_user_id)
    # load_user_template handles default creation if not found
    return template

@router.post("/template", response_model=UserTemplate)
async def update_user_template(template: UserTemplate = Body(...)):
    """Updates the user template."""
    # Use a default user ID since we don't have auth yet
    default_user_id = "default_user"
    logger.info("Updating user template.")
    success = repositories.save_user_template(default_user_id, template)
    if not success:
        logger.error("Failed to save user template.")
        raise HTTPException(status_code=500, detail="Failed to save user template.")
    return template

@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences():
    """Retrieve the current user preferences."""
    # Use a default user ID since we don't have auth yet
    default_user_id = "default_user"
    prefs = repositories.load_user_preferences(default_user_id)
    return prefs

@router.post("/preferences", response_model=UserPreferences)
async def update_user_preferences(payload: UpdateUserPreferencesRequest = Body(...)):
    """Update user preferences. Currently only supports purpose_statement."""
    # Use a default user ID since we don't have auth yet
    default_user_id = "default_user"
    logger.info(f"Updating user preferences. Provided purpose: {'{payload.purpose_statement[:50]}...' if payload.purpose_statement else 'None'}")
    
    # Load existing preferences to update them (or defaults)
    current_prefs = repositories.load_user_preferences(default_user_id)
    
    # Create updated data dictionary
    update_data = current_prefs.model_dump() # Get existing data as dict
    if payload.purpose_statement is not None:
        update_data['purpose_statement'] = payload.purpose_statement
        
    # Create new model instance with updated data
    try:
        updated_prefs = UserPreferences(**update_data)
    except Exception as e: # Catch potential validation errors
        logger.error(f"Validation error creating updated preferences: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid preference data: {e}")

    # Save the updated preferences
    success = repositories.save_user_preferences(default_user_id, updated_prefs)
    if not success:
        logger.error("Failed to save updated user preferences.")
        raise HTTPException(status_code=500, detail="Failed to save user preferences.")
        
    logger.info(f"Successfully updated user preferences.")
    return updated_prefs

@router.post("/reset", status_code=204) # 204 No Content
async def reset_user_data():
    """Deletes user preferences and template files to reset onboarding state."""
    # Use a default user ID since we don't have auth yet
    default_user_id = "default_user"
    logger.warning("Attempting to reset user preferences and template.")
    
    prefs_deleted = False
    template_deleted = False
    error_details = []
    
    # Get the paths for the specific user
    prefs_path = repositories._get_user_prefs_path(default_user_id)
    template_path = repositories._get_user_template_path(default_user_id)
    
    try:
        if prefs_path.exists():
            prefs_path.unlink() # Delete the file
            logger.info(f"Deleted preferences file: {prefs_path}")
            prefs_deleted = True
        else:
            logger.info("Preferences file did not exist, nothing to delete.")
            prefs_deleted = True # Consider it a success if already gone
    except Exception as e:
        logger.error(f"Error deleting preferences file {prefs_path}: {e}")
        error_details.append(f"Preferences delete failed: {e}")
        
    try:
        if template_path.exists():
            template_path.unlink() # Delete the file
            logger.info(f"Deleted template file: {template_path}")
            template_deleted = True
        else:
            logger.info("Template file did not exist, nothing to delete.")
            template_deleted = True # Consider it a success if already gone
    except Exception as e:
        logger.error(f"Error deleting template file {template_path}: {e}")
        error_details.append(f"Template delete failed: {e}")
        
    if not prefs_deleted or not template_deleted:
        # If either failed, return an error
        raise HTTPException(status_code=500, detail=f"Failed to fully reset user data. Errors: {'; '.join(error_details)}")

    logger.info("User data reset successfully.")
    return # Return None for 204 status

# TODO: Add endpoints for template management later
# GET /template
# POST /template 