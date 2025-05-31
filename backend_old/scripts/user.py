import typer
from pathlib import Path
import sys
import json
import os
import re
from datetime import datetime

# Remove project root path manipulation
# PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sys.path.insert(0, str(PROJECT_ROOT))

# Revert imports to app.* style, move back to top level
# Change to relative imports
from ..app.models.user import (
    UserPreferences, 
    UserTemplate, 
    SectionDetailDef
)
from ..app.models.session import SessionStructuredContent # Assuming this is ok via __init__ or direct
from ..app.repositories import ( 
    save_user_preferences,
    save_user_template,
    user_prefs_path, 
    user_template_path, 
    session_structured_repo,
    load_user_preferences, # Make sure this is exported from repositories/__init__.py
    load_user_template    # Make sure this is exported from repositories/__init__.py
)
from ..app.services.anthropic_service import client as anthropic_client # Moved back to top
from ..app.core.config import settings # Import settings

app = typer.Typer(help="User data import/export/delete CLI tool.")

@app.command()
def export(output: Path = typer.Option(..., help="Output JSON file for export")):
    """Export all user data (preferences, template, sessions) to a JSON file."""
    # Remove model imports from inside the function
    # from backend.app.models.user import UserPreferences, UserTemplate, SectionDetailDef, SessionStructuredContent
    
    # Load using repository functions (assuming they use the correct internal paths now)
    # Need to add these back to repositories/__init__.py if needed
    prefs = load_user_preferences()
    template = load_user_template()
    # try:
    #     with open(user_prefs_path, 'r', encoding='utf-8') as f:
    #         prefs_data = json.load(f)
    #     prefs = UserPreferences(**prefs_data)
    # except FileNotFoundError:
    #     typer.echo("Warning: Preferences file not found for export.")
    #     prefs = UserPreferences() # Export empty if not found
    # except Exception as e:
    #     typer.echo(f"Error loading preferences for export: {e}")
    #     prefs = UserPreferences()

    # try:
    #     with open(user_template_path, 'r', encoding='utf-8') as f:
    #         template_data = json.load(f)
    #     if isinstance(template_data.get('sections'), dict):
    #          template_sections = {
    #              k: SectionDetailDef(**v) 
    #              for k, v in template_data['sections'].items()
    #          }
    #          template_data['sections'] = template_sections
    #     template = UserTemplate(**template_data)
    # except FileNotFoundError:
    #     typer.echo("Warning: Template file not found for export.")
    #     template = UserTemplate() # Export empty if not found
    # except Exception as e:
    #     typer.echo(f"Error loading template for export: {e}")
    #     template = UserTemplate()

    # Load all session structured data
    session_files = list(session_structured_repo.base_directory.glob('*_structured.json'))
    sessions = []
    for f_path in session_files:
        session_id_stem = f_path.stem 
        session = session_structured_repo.load(session_id_stem)
        if session:
            sessions.append(session.model_dump(mode='json'))

    export_data = {
        'preferences': prefs.model_dump(mode='json') if prefs else None,
        'template': template.model_dump(mode='json') if template else None, 
        'sessions': sessions
    }
    try:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
        typer.echo(f"Exported user data to {output}")
    except Exception as e:
        typer.echo(f"Error writing export file {output}: {e}")

@app.command(name="import")
def import_data(
    input_file: Path = typer.Option(..., "--input", help="Input JSON file containing all user data (preferences, template, and structured sessions).")
):
    """Import all user data from a single JSON file."""
    if not input_file.exists():
        typer.echo(f"Error: Input file not found: {input_file}")
        raise typer.Exit(code=1)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except Exception as e:
        typer.echo(f"Error reading or parsing input JSON file {input_file}: {e}")
        raise typer.Exit(code=1)

    imported_prefs = None
    imported_template = None
    
    # Import Preferences
    prefs_data = all_data.get('preferences')
    if prefs_data:
        try:
            # Handle null last_updated before Pydantic validation (for robustness)
            if 'last_updated' in prefs_data and prefs_data['last_updated'] is None:
                del prefs_data['last_updated'] # Pydantic will use default_factory
            
            # Ensure dates are correctly parsed if they are strings
            # Pydantic V2 usually handles ISO strings for datetime automatically if the type hint is datetime
            
            imported_prefs = UserPreferences(**prefs_data)
            save_user_preferences(imported_prefs)
            typer.echo(f"Imported and saved user preferences from {input_file}")
        except Exception as e:
            typer.echo(f"Error processing preferences from {input_file}: {e}")
            # Optionally, decide if this should be a fatal error
            # raise typer.Exit(code=1)
    else:
        typer.echo("No preferences found in the input file.")

    # Import Template
    template_data = all_data.get('template')
    if template_data:
        try:
            # Pydantic should handle the nested SectionDetailDef correctly from dict
            # Ensure 'sections' is a dict of dicts, not already model instances if json.load was used
            # The model_dump(mode='json') in export produces dicts, so this should be fine.
            imported_template = UserTemplate(**template_data)
            save_user_template(imported_template)
            typer.echo(f"Imported and saved user template from {input_file}")
        except Exception as e:
            typer.echo(f"Error processing template from {input_file}: {e}")
            # Optionally, decide if this should be a fatal error
            # raise typer.Exit(code=1)
    else:
        typer.echo("No template found in the input file.")

    # Import Sessions
    sessions_list = all_data.get('sessions')
    if sessions_list and isinstance(sessions_list, list):
        saved_count = 0
        for session_data_item in sessions_list:
            try:
                # session_data_item is expected to be a dict here from model_dump(mode='json')
                session_model = SessionStructuredContent(**session_data_item)
                save_id = f"{session_model.session_id}_structured"
                success = session_structured_repo.save(save_id, session_model)
                if success:
                    saved_count += 1
                else:
                    typer.echo(f"  Warning: Failed to save session {session_model.session_id}")
            except Exception as e:
                typer.echo(f"  Error processing session data item: {e}. Item: {str(session_data_item)[:100]}...") # Log part of item for debug
        typer.echo(f"Imported and saved {saved_count} structured sessions from {input_file}.")
    elif sessions_list is None:
        typer.echo("No sessions section found in the input file.")
    elif not isinstance(sessions_list, list):
        typer.echo(f"Error: 'sessions' field in the input file is not a list. Found type: {type(sessions_list)}")
    else: # Empty list
        typer.echo("No session data found in the 'sessions' list in the input file.")

    typer.echo("Import process completed.")

@app.command()
def delete():
    """Delete all user data (preferences, template, sessions)."""
    deleted = []
    # Use standard paths for deletion
    for path, label in [(user_prefs_path, 'preferences'), (user_template_path, 'template')]:
        if path.exists():
            path.unlink()
            deleted.append(label)
    # Delete all session structured files
    session_files = [f for f in session_structured_repo.base_directory.glob('*_structured.json') if f.is_file()]
    for f in session_files:
        f.unlink()
        deleted.append(f"session: {f.name}")
    if deleted:
        typer.echo(f"Deleted: {', '.join(deleted)}")
    else:
        typer.echo("No user data found to delete.")

# --- Debugging Command (debug-split) remains unchanged --- 

@app.command(name="debug-split")
def debug_split(
    sessions: Path = typer.Option(..., help="Input text file containing all sessions."),
    output_dir: Path = typer.Option(..., help="Directory to save individual session files.")
):
    # No model imports needed here
    def parse_date_from_title(title_line: str) -> str | None:
        match_ymd_hms = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', title_line)
        if match_ymd_hms:
            try:
                dt_obj = datetime.strptime(match_ymd_hms.group(1), '%Y-%m-%d %H:%M:%S')
                return dt_obj.strftime('%Y%m%dT%H%M%S')
            except ValueError:
                pass 

        match_month_day_year = re.search(r'([A-Za-z]+ \d{1,2}, \d{4})', title_line)
        if match_month_day_year:
            try:
                dt_obj = datetime.strptime(match_month_day_year.group(1), '%B %d, %Y')
                return dt_obj.strftime('%Y%m%dT000000')
            except ValueError:
                pass 

        match_ymd = re.search(r'(\d{4}-\d{2}-\d{2})', title_line)
        if match_ymd:
            try:
                dt_obj = datetime.strptime(match_ymd.group(1), '%Y-%m-%d')
                return dt_obj.strftime('%Y%m%dT000000')
            except ValueError:
                pass 
        return None

    if not sessions.exists():
        typer.echo(f"Error: Input session file not found: {sessions}")
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Output directory: {output_dir.resolve()}")

    with open(sessions, 'r', encoding='utf-8') as f:
        session_text = f.read()

    title_pattern = r'(\n#{1,4} Journal Entry(?: \d+)? - [^\n]+)'
    parts = re.split(title_pattern, session_text)

    session_entries = []
    current_title = None
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if re.match(r'^#{1,4} Journal Entry', part):
            current_title = part
        elif current_title and part and not part.startswith("## Journal Session Instructions"):
            session_entries.append({"title": current_title, "text": part})
            current_title = None 
        elif i == 0 and part and not part.startswith("## Journal Session Instructions"):
            typer.echo(f"Warning: Skipping preamble text before first entry: {part[:100]}...")

    typer.echo(f"Found {len(session_entries)} entries to split.")

    saved_count = 0
    for idx, entry_data in enumerate(session_entries):
        entry_title = entry_data["title"]
        entry_text = entry_data["text"]

        date_str = parse_date_from_title(entry_title)
        if date_str:
            filename_base = date_str
        else:
            filename_base = f"imported_{idx+1}"

        output_filename = output_dir / f"{filename_base}.txt"

        try:
            with open(output_filename, 'w', encoding='utf-8') as out_f:
                out_f.write(entry_title + '\n\n') 
                out_f.write(entry_text)
            saved_count += 1
        except Exception as e:
            typer.echo(f"Error writing file {output_filename}: {e}")

    typer.echo(f"Successfully saved {saved_count} split session files to {output_dir}")

if __name__ == "__main__":
    app() 