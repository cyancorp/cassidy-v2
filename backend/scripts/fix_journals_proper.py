#!/usr/bin/env python3
"""
Properly fix journal structured insights using the actual journal tool and user template
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.agents.service import AgentService
from app.agents.tools import structure_journal_tool
from app.agents.models import CassidyAgentDependencies
from app.templates.loader import template_loader
from sqlalchemy import select, text
from pydantic_ai import RunContext


def log_step(step: str, status: str = "🔧"):
    """Log a step with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{status} [{timestamp}] {step}")


async def fix_journal_structured_data():
    """Fix structured data using the proper journal tool and user template"""
    log_step("Fixing journal structured data using proper journal tool...")
    
    async for db in get_db():
        # Get user
        result = await db.execute(select(UserDB).where(UserDB.username == "jg2950"))
        user = result.scalar_one_or_none()
        
        if not user:
            log_step("❌ User jg2950 not found!")
            return
        
        # Load user template
        user_template = template_loader.get_user_template()
        log_step(f"📋 Loaded user template with {len(user_template.get('sections', {}))} sections")
        
        # Get all journal entries
        result = await db.execute(text('''
            SELECT id, title, raw_text, created_at, session_id
            FROM journal_entries 
            WHERE user_id = :user_id
            ORDER BY created_at
        '''), {'user_id': user.id})
        
        entries = result.fetchall()
        log_step(f"Found {len(entries)} journal entries to reprocess")
        
        for i, (entry_id, title, raw_text, created_at, session_id) in enumerate(entries, 1):
            log_step(f"[{i}/{len(entries)}] Processing: {title[:40]}... ({created_at})")
            
            if not raw_text:
                log_step(f"  ⚠️  No raw text available, skipping")
                continue
            
            try:
                # Create agent dependencies context for the journal tool
                context = CassidyAgentDependencies(
                    user_id=user.id,
                    session_id=session_id,
                    conversation_type="journaling",
                    user_template=user_template,
                    user_preferences={},
                    current_journal_draft={},
                    current_tasks=[]
                )
                
                # Create RunContext for the tool
                run_context = RunContext(deps=context)
                
                log_step(f"  🤖 Running journal structuring tool...")
                start_time = datetime.now()
                
                # Use the actual journal structuring tool
                result = await asyncio.wait_for(
                    structure_journal_tool(run_context, raw_text),
                    timeout=60.0  # 1 minute timeout
                )
                
                processing_time = (datetime.now() - start_time).total_seconds()
                log_step(f"  ✅ Journal tool completed in {processing_time:.1f}s")
                
                # Get the structured data from the tool result
                if hasattr(result, 'updated_draft_data'):
                    structured_data = result.updated_draft_data
                    sections_updated = result.sections_updated
                    log_step(f"  📝 Structured into {len(sections_updated)} sections: {', '.join(sections_updated)}")
                else:
                    log_step(f"  ⚠️  No structured data returned from tool")
                    structured_data = {"Open Reflection": raw_text}
                
                # Add metadata
                structured_data['_metadata'] = {
                    'generated_at': datetime.now().isoformat(),
                    'processing_time': processing_time,
                    'method': 'journal_tool',
                    'sections_updated': result.sections_updated if hasattr(result, 'sections_updated') else []
                }
                
                # Update the journal entry
                await db.execute(text('''
                    UPDATE journal_entries 
                    SET structured_data = :data, updated_at = :now
                    WHERE id = :id
                '''), {
                    'data': json.dumps(structured_data),
                    'now': datetime.now().isoformat(),
                    'id': entry_id
                })
                
                log_step(f"  ✅ Updated with proper template-based structure")
                
            except asyncio.TimeoutError:
                log_step(f"  ❌ Journal tool timed out after 1 minute")
                continue
            except Exception as e:
                log_step(f"  ❌ Error processing: {str(e)}")
                continue
        
        await db.commit()
        log_step("✅ All journal entries properly structured")
        break


async def main():
    """Main function"""
    print("\n🔧 FIXING JOURNALS WITH PROPER TEMPLATE")
    print("=" * 60)
    
    await init_db()
    await fix_journal_structured_data()
    
    print("\n✅ Proper journal fixes completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())