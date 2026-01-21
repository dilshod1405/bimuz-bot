"""Employee management handlers.

RBAC is centralized in permissions.py (same strategy as dashboard).
All authenticated roles can READ employees, but CRUD is role-based.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_client import APIClient
from storage import user_storage
from keyboards import (
    get_employees_list_keyboard,
    get_main_menu_keyboard,
    get_employee_detail_keyboard,
    get_cancel_keyboard,
    get_cancel_inline_keyboard
)
from utils import extract_list_from_response, truncate_message, truncate_alert_message, safe_html_text, format_error_message
import logging
from permissions import (
    can_view_employees,
    can_create_employee,
    can_update_employee,
    can_delete_employee,
    get_assignable_roles,
)

logger = logging.getLogger(__name__)

router = Router()


class CreateEmployeeStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_full_name = State()
    waiting_for_password = State()
    waiting_for_password_confirm = State()
    waiting_for_role = State()
    waiting_for_professionality = State()


class EditEmployeeStates(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()


@router.message(F.text == "👨‍💼 Xodimlar")
async def cmd_employees(message: Message):
    """Show employees list (read allowed for all authenticated roles)."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    if not can_view_employees(role):
        await message.answer("❌ Bu bo'limga kirish uchun ruxsat yo'q.")
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
                    reply_markup=get_employees_list_keyboard([], page=0, role=role)
                )
            else:
                text = f"👨‍💼 <b>Xodimlar ro'yxati</b> ({len(employees)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_employees_list_keyboard(employees, page=0, role=role),
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
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employees()
            employees = extract_list_from_response(response)
            
            await callback.message.edit_reply_markup(
                reply_markup=get_employees_list_keyboard(employees, page=page, role=role)
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
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employee(employee_id)
            
            if response.get('success'):
                employee_data = response.get('data', {})
                target_role = employee_data.get('role')
                
                text = (
                    f"👨‍💼 <b>Xodim ma'lumotlari</b>\n\n"
                    f"<b>ID:</b> {safe_html_text(employee_data.get('id'))}\n"
                    f"<b>Ism:</b> {safe_html_text(employee_data.get('full_name'))}\n"
                    f"<b>Email:</b> {safe_html_text(employee_data.get('email'))}\n"
                    f"<b>Rol:</b> {safe_html_text(employee_data.get('role_display') or employee_data.get('role'))}\n"
                )
                
                if employee_data.get('professionality'):
                    text += f"<b>Mutaxassislik:</b> {safe_html_text(employee_data.get('professionality'))}\n"
                
                text += f"\n<b>Holat:</b> {'✅ Faol' if employee_data.get('is_active') else '❌ Nofaol'}"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_employee_detail_keyboard(employee_id, role=role, target_role=target_role),
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
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employees()
            employees = extract_list_from_response(response)
            
            text = f"👨‍💼 <b>Xodimlar ro'yxati</b> ({len(employees)} ta)\n\n"
            text += "Quyidagilardan birini tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_employees_list_keyboard(employees, page=0, role=role),
                parse_mode="HTML"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Back to employees error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "create_employee")
async def create_employee_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new employee."""
    user_id = callback.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await callback.answer("Siz tizimga kirmagansiz.", show_alert=True)
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    if not can_create_employee(role):
        await callback.answer("❌ Bu amalni bajarish uchun ruxsat yo'q.", show_alert=True)
        return
    
    await callback.message.answer(
        "Yangi xodim qo'shish\n\n"
        "Email manzilini kiriting:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateEmployeeStates.waiting_for_email)
    await callback.answer()


@router.message(CreateEmployeeStates.waiting_for_email)
async def process_employee_email(message: Message, state: FSMContext):
    """Process email."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    email = message.text.strip()
    if '@' not in email:
        await message.answer("Iltimos, to'g'ri email manzil kiriting:")
        return
    
    await state.update_data(email=email)
    await message.answer("Ismni kiriting (first_name):")
    await state.set_state(CreateEmployeeStates.waiting_for_first_name)


@router.message(CreateEmployeeStates.waiting_for_first_name)
async def process_employee_first_name(message: Message, state: FSMContext):
    """Process first name."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    await state.update_data(first_name=message.text.strip())
    await message.answer("Familiyani kiriting (last_name):")
    await state.set_state(CreateEmployeeStates.waiting_for_last_name)


@router.message(CreateEmployeeStates.waiting_for_last_name)
async def process_employee_last_name(message: Message, state: FSMContext):
    """Process last name."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    await state.update_data(last_name=message.text.strip())
    await message.answer("To'liq ismini kiriting (full_name):")
    await state.set_state(CreateEmployeeStates.waiting_for_full_name)


@router.message(CreateEmployeeStates.waiting_for_full_name)
async def process_employee_full_name(message: Message, state: FSMContext):
    """Process full name."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    await state.update_data(full_name=message.text.strip())
    await message.answer("Parolni kiriting:")
    await state.set_state(CreateEmployeeStates.waiting_for_password)


@router.message(CreateEmployeeStates.waiting_for_password)
async def process_employee_password(message: Message, state: FSMContext):
    """Process password."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    await state.update_data(password=message.text.strip())
    await message.answer("Parolni tasdiqlang (password_confirm):")
    await state.set_state(CreateEmployeeStates.waiting_for_password_confirm)


@router.message(CreateEmployeeStates.waiting_for_password_confirm)
async def process_employee_password_confirm(message: Message, state: FSMContext):
    """Process password confirmation."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    data = await state.get_data()
    password = data.get('password')
    password_confirm = message.text.strip()
    
    if password != password_confirm:
        await message.answer("❌ Parollar mos kelmaydi. Qayta kiriting:")
        await state.set_state(CreateEmployeeStates.waiting_for_password_confirm)
        return
    
    await state.update_data(password_confirm=password_confirm)
    
    # Show role selection keyboard (filtered by permissions)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = message.from_user.id
    current_employee = await user_storage.get_employee(user_id)
    current_role = current_employee.get('role') if current_employee else None

    role_names = {
        'dasturchi': '👨‍💻 Dasturchi',
        'direktor': '👔 Direktor',
        'administrator': '👨‍💼 Administrator',
        'mentor': '👨‍🏫 Mentor',
        'sotuv_agenti': '👨‍💼 Sotuv Agenti',
        'assistent': '👨‍🎓 Assistent',
        'buxgalter': '💰 Buxgalter'
    }

    rows = []
    for r in get_assignable_roles(current_role):
        rows.append([InlineKeyboardButton(text=role_names.get(r, r), callback_data=f"role_{r}")])
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_create_employee")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await message.answer(
        "Rolni tanlang:",
        reply_markup=keyboard
    )
    await state.set_state(CreateEmployeeStates.waiting_for_role)


@router.callback_query(F.data.startswith("role_"), CreateEmployeeStates.waiting_for_role)
async def process_employee_role(callback: CallbackQuery, state: FSMContext):
    """Process role selection."""
    role = callback.data.split("_")[1]  # role_dasturchi -> dasturchi
    await state.update_data(role=role)
    
    role_names = {
        'dasturchi': 'Dasturchi',
        'direktor': 'Direktor',
        'administrator': 'Administrator',
        'mentor': 'Mentor',
        'sotuv_agenti': 'Sotuv Agenti',
        'assistent': 'Assistent',
        'buxgalter': 'Buxgalter'
    }
    
    await callback.message.edit_text(f"✅ Rol tanlandi: {role_names.get(role, role)}")
    await callback.answer()
    await callback.message.answer("Mutaxassislikni kiriting (ixtiyoriy, o'tkazib yuborish uchun 'skip' yozing):")
    await state.set_state(CreateEmployeeStates.waiting_for_professionality)


@router.callback_query(F.data == "cancel_create_employee")
async def cancel_create_employee_callback(callback: CallbackQuery, state: FSMContext):
    """Cancel employee creation."""
    await state.clear()
    await callback.message.edit_text("Xodim qo'shish bekor qilindi.")
    await callback.answer()


@router.message(CreateEmployeeStates.waiting_for_professionality)
async def process_employee_professionality(message: Message, state: FSMContext):
    """Process professionality and create employee."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Xodim qo'shish bekor qilindi.")
        return
    
    data = await state.get_data()
    professionality = message.text.strip() if message.text.strip().lower() != 'skip' else ''
    
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    employee_data = {
        'email': data.get('email'),
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'full_name': data.get('full_name'),
        'password': data.get('password'),
        'password_confirm': data.get('password_confirm'),
        'role': data.get('role'),
        'professionality': professionality if professionality else None,
        'is_active': True
    }
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.create_employee(employee_data)
            
            if response.get('success'):
                employee_result = response.get('data', {}).get('employee', {})
                await message.answer(
                    f"✅ Xodim muvaffaqiyatli qo'shildi!\n\n"
                    f"<b>Ism:</b> {safe_html_text(employee_result.get('full_name'))}\n"
                    f"<b>Email:</b> {safe_html_text(employee_result.get('email'))}\n"
                    f"<b>Rol:</b> {safe_html_text(employee_result.get('role_display') or employee_result.get('role'))}\n\n"
                    f"⚠️ Eslatma: Yangi xodim o'z parolini o'zgartirishi tavsiya etiladi.",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Xodim qo\'shilmadi')
                errors = response.get('errors', {})
                formatted_error = format_error_message(error_msg, errors)
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Create employee error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Edit Employee Handlers
@router.callback_query(F.data.startswith("edit_employee_"))
async def edit_employee_start(callback: CallbackQuery, state: FSMContext):
    """Start editing an employee."""
    employee_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_employee(employee_id)
            
            if response.get('success'):
                employee_data = response.get('data', {})
                target_role = employee_data.get('role')
                if not can_update_employee(role, target_role):
                    await callback.answer("❌ Xodimni tahrirlash uchun ruxsat yo'q.", show_alert=True)
                    return
                await state.update_data(employee_id=employee_id, employee_data=employee_data)
                
                is_active = employee_data.get('is_active', False)
                status_text = "Profilni bloklash" if is_active else "Profilni aktivlashtirish"
                
                text = (
                    "✏️ <b>Xodimni tahrirlash</b>\n\n"
                    "Qaysi maydonni tahrirlamoqchisiz?\n\n"
                    "1️⃣ To'liq ism\n"
                    "2️⃣ Rol\n"
                    "3️⃣ Mutaxassislik\n"
                    f"4️⃣ {status_text}\n\n"
                    "Raqam yuboring yoki 'Bekor qilish' tugmasini bosing."
                )
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_cancel_inline_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
                await state.set_state(EditEmployeeStates.waiting_for_field)
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Edit employee start error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.message(EditEmployeeStates.waiting_for_field)
async def process_edit_employee_field(message: Message, state: FSMContext):
    """Process field selection for editing employee."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        employee = await user_storage.get_employee(message.from_user.id)
        role = employee.get('role') if employee else None
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_menu_keyboard(role))
        return
    
    field_map = {
        '1': 'full_name',
        '2': 'role',
        '3': 'professionality',
        '4': 'is_active'
    }
    
    field_key = message.text.strip()
    field_name = field_map.get(field_key)
    
    if not field_name:
        await message.answer("❌ Noto'g'ri raqam. 1-4 orasidagi raqamni yuboring.")
        return
    
    data = await state.get_data()
    employee_data = data.get('employee_data', {})
    
    if field_name == 'is_active':
        # Toggle is_active
        new_value = not employee_data.get('is_active', False)
        await state.update_data(field_name=field_name, field_value=new_value)
        await update_employee_field(message, state)
    elif field_name == 'role':
        # Show inline keyboard for role selection (filtered)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        user_emp = await user_storage.get_employee(message.from_user.id)
        user_role = user_emp.get('role') if user_emp else None
        role_names = {
            'dasturchi': '👨‍💻 Dasturchi',
            'direktor': '👔 Direktor',
            'administrator': '👨‍💼 Administrator',
            'mentor': '👨‍🏫 Mentor',
            'sotuv_agenti': '👨‍💼 Sotuv Agenti',
            'assistent': '👨‍🎓 Assistent',
            'buxgalter': '💰 Buxgalter'
        }
        rows = []
        for r in get_assignable_roles(user_role):
            rows.append([InlineKeyboardButton(text=role_names.get(r, r), callback_data=f"edit_role_{r}")])
        rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_edit_employee")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
        await message.answer("Yangi rolni tanlang:", reply_markup=keyboard)
        await state.set_state(EditEmployeeStates.waiting_for_value)
    else:
        await state.update_data(field_name=field_name)
        
        field_labels = {
            'full_name': 'To\'liq ism',
            'professionality': 'Mutaxassislik'
        }
        
        field_label = field_labels.get(field_name, field_name)
        await message.answer(
            f"Yangi <b>{field_label}</b> ni kiriting:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(EditEmployeeStates.waiting_for_value)


@router.callback_query(F.data.startswith("edit_role_"))
async def process_edit_role_callback(callback: CallbackQuery, state: FSMContext):
    """Process role selection for editing."""
    role = callback.data.split("_")[2]  # edit_role_dasturchi -> dasturchi
    await state.update_data(field_name='role', field_value=role)
    
    role_names = {
        'dasturchi': 'Dasturchi',
        'direktor': 'Direktor',
        'administrator': 'Administrator',
        'mentor': 'Mentor',
        'sotuv_agenti': 'Sotuv Agenti',
        'assistent': 'Assistent',
        'buxgalter': 'Buxgalter'
    }
    
    await callback.message.edit_text(f"✅ Rol tanlandi: {role_names.get(role, role)}")
    await callback.answer()
    await update_employee_field_from_callback(callback, state)


@router.callback_query(F.data == "cancel_edit_employee")
async def cancel_edit_employee_callback(callback: CallbackQuery, state: FSMContext):
    """Cancel edit action."""
    await state.clear()
    await callback.message.edit_text("Tahrirlash bekor qilindi.")
    await callback.answer()


@router.message(EditEmployeeStates.waiting_for_value)
async def process_edit_employee_value(message: Message, state: FSMContext):
    """Process new value for field."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        employee = await user_storage.get_employee(message.from_user.id)
        role = employee.get('role') if employee else None
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_menu_keyboard(role))
        return
    
    data = await state.get_data()
    field_name = data.get('field_name')
    value = message.text.strip()
    
    await state.update_data(field_value=value)
    await update_employee_field(message, state)


async def update_employee_field_from_callback(callback: CallbackQuery, state: FSMContext):
    """Update employee field via API (from callback)."""
    data = await state.get_data()
    employee_id = data.get('employee_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_employee(employee_id, update_data)
            
            if response.get('success'):
                await callback.message.answer(
                    f"✅ Xodim ma'lumotlari muvaffaqiyatli yangilandi!",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Yangilash muvaffaqiyatsiz')
                errors = response.get('errors')
                if errors:
                    error_msg += f"\n\nXatolar:\n" + "\n".join([f"- {k}: {v[0]}" for k, v in errors.items()])
                await callback.message.answer(f"❌ Xatolik: {error_msg}")
    except Exception as e:
        logger.error(f"Update employee error: {str(e)}")
        await callback.message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


async def update_employee_field(message: Message, state: FSMContext):
    """Update employee field via API."""
    data = await state.get_data()
    employee_id = data.get('employee_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_employee(employee_id, update_data)
            
            if response.get('success'):
                await message.answer(
                    f"✅ Xodim ma'lumotlari muvaffaqiyatli yangilandi!",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Yangilash muvaffaqiyatsiz')
                errors = response.get('errors')
                formatted_error = format_error_message(error_msg, errors)
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Update employee error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Delete Employee Handler
@router.callback_query(F.data.startswith("delete_employee_"))
async def delete_employee_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm employee deletion."""
    employee_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Get employee info for confirmation
            response = await client.get_employee(employee_id)
            
            if response.get('success'):
                employee_data = response.get('data', {})
                target_role = employee_data.get('role')
                if not can_delete_employee(role, target_role):
                    await callback.answer("❌ Xodimni o'chirish uchun ruxsat yo'q.", show_alert=True)
                    return
                await state.update_data(employee_id=employee_id)
                
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_employee_{employee_id}")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"employee_{employee_id}")]
                ])
                
                text = (
                    f"⚠️ <b>Xodimni o'chirish</b>\n\n"
                    f"<b>Xodim:</b> {safe_html_text(employee_data.get('full_name'))}\n"
                    f"<b>ID:</b> {safe_html_text(employee_data.get('id'))}\n\n"
                    f"⚠️ Bu amalni bekor qilib bo'lmaydi!\n\n"
                    f"Xodimni o'chirishni tasdiqlaysizmi?"
                )
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.answer()
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Delete employee confirm error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_employee_"))
async def delete_employee_execute(callback: CallbackQuery, state: FSMContext):
    """Execute employee deletion."""
    employee_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Re-check permission using current target data (safer)
            emp_resp = await client.get_employee(employee_id)
            if emp_resp.get('success'):
                target_role = emp_resp.get('data', {}).get('role')
                if not can_delete_employee(role, target_role):
                    await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
                    return
            response = await client.delete_employee(employee_id)
            
            if response.get('success'):
                await callback.message.edit_text(
                    "✅ Xodim muvaffaqiyatli o'chirildi!",
                    reply_markup=None
                )
                await callback.answer("✅ Muvaffaqiyatli!", show_alert=True)
                
                # Go back to employees list
                employees_response = await client.get_employees()
                employees = extract_list_from_response(employees_response)
                
                text = f"👨‍💼 <b>Xodimlar ro'yxati</b> ({len(employees)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                
                await callback.message.answer(
                    text,
                    reply_markup=get_employees_list_keyboard(employees, page=0, role=role),
                    parse_mode="HTML"
                )
            else:
                error_msg = response.get('message', 'O\'chirish muvaffaqiyatsiz')
                error_msg_truncated = truncate_alert_message(f"❌ {error_msg}")
                await callback.answer(error_msg_truncated, show_alert=True)
    except Exception as e:
        logger.error(f"Delete employee error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
    finally:
        await state.clear()
