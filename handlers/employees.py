"""Employee management handlers (for developers only)."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from api_client import APIClient
from storage import user_storage
from keyboards import (
    get_employees_list_keyboard,
    get_main_menu_keyboard,
    get_employee_detail_keyboard
)
from utils import extract_list_from_response, truncate_message, truncate_alert_message, safe_html_text
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "👨‍💼 Xodimlar")
async def cmd_employees(message: Message):
    """Show employees list (only for developers)."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    if role != 'dasturchi':
        await message.answer("❌ Bu bo'lim faqat dasturchilar uchun.")
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employees()
            employees = extract_list_from_response(response)
            
            if not employees:
                await message.answer(
                    "👨‍💼 Xodimlar ro'yxati bo'sh.\n\n"
                    "Yangi xodim qo'shish uchun quyidagi tugmani bosing:",
                    reply_markup=get_employees_list_keyboard([], page=0)
                )
            else:
                text = f"👨‍💼 <b>Xodimlar ro'yxati</b> ({len(employees)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_employees_list_keyboard(employees, page=0),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Employees list error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data.startswith("employees_page_"))
async def employees_pagination(callback: CallbackQuery):
    """Handle employees list pagination."""
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employees()
            employees = extract_list_from_response(response)
            
            await callback.message.edit_reply_markup(
                reply_markup=get_employees_list_keyboard(employees, page=page)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Employees pagination error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("employee_"))
async def show_employee_detail(callback: CallbackQuery):
    """Show employee detail."""
    employee_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employee(employee_id)
            
            if response.get('success'):
                employee = response.get('data', {})
                
                text = (
                    f"👨‍💼 <b>Xodim ma'lumotlari</b>\n\n"
                    f"<b>ID:</b> {safe_html_text(employee.get('id'))}\n"
                    f"<b>Ism:</b> {safe_html_text(employee.get('full_name'))}\n"
                    f"<b>Email:</b> {safe_html_text(employee.get('email'))}\n"
                    f"<b>Rol:</b> {safe_html_text(employee.get('role_display') or employee.get('role'))}\n"
                )
                
                if employee.get('professionality'):
                    text += f"<b>Mutaxassislik:</b> {safe_html_text(employee.get('professionality'))}\n"
                
                text += f"\n<b>Holat:</b> {'✅ Faol' if employee.get('is_active') else '❌ Nofaol'}"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_employee_detail_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Employee detail error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "back_to_employees")
async def back_to_employees(callback: CallbackQuery):
    """Go back to employees list."""
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employees()
            employees = extract_list_from_response(response)
            
            text = f"👨‍💼 <b>Xodimlar ro'yxati</b> ({len(employees)} ta)\n\n"
            text += "Quyidagilardan birini tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_employees_list_keyboard(employees, page=0),
                parse_mode="HTML"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Back to employees error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
