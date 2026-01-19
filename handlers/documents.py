"""Documents handlers."""
from aiogram import Router, F
from aiogram.types import Message
from api_client import APIClient
from storage import user_storage
from keyboards import get_main_menu_keyboard
from utils import safe_html_text
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "📁 Hujjatlar")
async def cmd_documents(message: Message):
    """Show documents menu."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    text = (
        "📁 <b>Hujjatlar</b>\n\n"
        "Bu bo'lim hozircha ishlab chiqilmoqda.\n\n"
        "Tez orada quyidagi hujjatlar mavjud bo'ladi:\n"
        "• Shartnomalar\n"
        "• Sertifikatlar\n"
        "• Boshqa hujjatlar"
    )
    
    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard(role),
        parse_mode="HTML"
    )
