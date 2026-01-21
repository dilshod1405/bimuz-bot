"""Attendance handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from api_client import APIClient
from storage import user_storage
from keyboards import get_main_menu_keyboard
from utils import extract_list_from_response, truncate_message, truncate_alert_message
import logging
from permissions import can_view_attendance

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "📋 Davomatlar")
async def cmd_attendances(message: Message):
    """Show attendances list."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    if not can_view_attendance(role):
        await message.answer("❌ Bu bo'limga kirish uchun ruxsat yo'q.")
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_attendances()
            attendances = extract_list_from_response(response)
            
            if not attendances:
                await message.answer(
                    "📋 Davomatlar ro'yxati bo'sh.\n\n"
                    "Yangi davomat qo'shish uchun guruh bo'limidan foydalaning."
                )
            else:
                text = f"📋 **Davomatlar ro'yxati** ({len(attendances)} ta)\n\n"

                # Build a small cache for group -> mentor_name (avoid N+1)
                group_mentor_cache = {}
                preview_attendances = attendances[:10]  # Show first 10
                for a in preview_attendances:
                    gid = a.get('group')
                    if gid and gid not in group_mentor_cache:
                        # Some API responses might already include mentor_name
                        if a.get('mentor_name'):
                            group_mentor_cache[gid] = a.get('mentor_name')
                            continue
                        try:
                            g_resp = await client.get_group(gid)
                            if isinstance(g_resp, dict) and g_resp.get('success'):
                                g_data = g_resp.get('data', {}) or {}
                                group_mentor_cache[gid] = g_data.get('mentor_name') or g_data.get('mentor') or 'N/A'
                            else:
                                group_mentor_cache[gid] = 'N/A'
                        except Exception:
                            group_mentor_cache[gid] = 'N/A'

                for attendance in preview_attendances:
                    group_name = attendance.get('group_name', 'N/A')
                    date = attendance.get('date', 'N/A')[:10] if attendance.get('date') else 'N/A'
                    participants_count = len(attendance.get('participants', []))
                    gid = attendance.get('group')
                    mentor_name = attendance.get('mentor_name') or (group_mentor_cache.get(gid) if gid else None) or 'N/A'
                    
                    text += f"📅 {date} - {group_name}\n"
                    text += f"   Mentor: {mentor_name}\n"
                    text += f"   Qatnashganlar: {participants_count}\n\n"
                
                if len(attendances) > 10:
                    text += f"... va yana {len(attendances) - 10} ta"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Attendances list error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data.startswith("attendance_group_"))
async def show_group_attendance(callback: CallbackQuery):
    """Show attendance for a specific group."""
    group_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Get group info
            group_response = await client.get_group(group_id)
            if not group_response.get('success'):
                await callback.answer("Guruh topilmadi", show_alert=True)
                return
            
            group = group_response.get('data', {})
            
            # Get attendances for this group
            attendances_response = await client.get_attendances()
            all_attendances = extract_list_from_response(attendances_response)
            
            if all_attendances:
                
                group_attendances = [
                    att for att in all_attendances
                    if att.get('group') == group_id
                ]
                
                text = f"📋 **Davomat: {group.get('speciality_display', 'Guruh')}**\n\n"
                
                if not group_attendances:
                    text += "Hozircha davomat qayd etilmagan."
                else:
                    for att in group_attendances[:5]:
                        date = att.get('date', 'N/A')[:10] if att.get('date') else 'N/A'
                        participants_count = len(att.get('participants', []))
                        text += f"📅 {date}: {participants_count} ta qatnashgan\n"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.answer(text, parse_mode="Markdown")
            else:
                await callback.message.answer("Hozircha davomat qayd etilmagan.")
            await callback.answer()
    except Exception as e:
        logger.error(f"Group attendance error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
