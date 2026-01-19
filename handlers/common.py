"""Common handlers."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from storage import user_storage
from keyboards import get_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Go back to main menu."""
    user_id = callback.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await callback.answer("Siz tizimga kirmagansiz.", show_alert=True)
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    await callback.message.answer(
        "🏠 **Asosiy menyu**\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_main_menu_keyboard(role),
        parse_mode="Markdown"
    )
    await callback.message.delete()
    await callback.answer()
