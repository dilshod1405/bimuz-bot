"""Student management handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_client import APIClient
from storage import user_storage
from keyboards import (
    get_students_list_keyboard,
    get_student_detail_keyboard,
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_cancel_inline_keyboard
)
from utils import extract_list_from_response, format_error_message, truncate_message, truncate_alert_message, safe_html_text, validate_phone, validate_passport
import logging

logger = logging.getLogger(__name__)

router = Router()


class CreateStudentStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_email = State()
    waiting_for_phone = State()
    waiting_for_passport = State()
    waiting_for_birth_date = State()
    waiting_for_source = State()
    waiting_for_address = State()


class EditStudentStates(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()


class BookStudentStates(StatesGroup):
    waiting_for_group_selection = State()


@router.message(F.text == "👥 Talabalar")
async def cmd_students(message: Message):
    """Show students list."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_students()
            students = extract_list_from_response(response)
            
            if not students:
                await message.answer(
                    "📋 Talabalar ro'yxati bo'sh.\n\n"
                    "Yangi talaba qo'shish uchun quyidagi tugmani bosing:",
                    reply_markup=get_students_list_keyboard([], page=0)
                )
            else:
                text = f"📋 <b>Talabalar ro'yxati</b> ({len(students)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_students_list_keyboard(students, page=0),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Students list error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data.startswith("students_page_"))
async def students_pagination(callback: CallbackQuery):
    """Handle students list pagination."""
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_students()
            students = extract_list_from_response(response)
            
            await callback.message.edit_reply_markup(
                reply_markup=get_students_list_keyboard(students, page=page)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Students pagination error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("student_"))
async def show_student_detail(callback: CallbackQuery):
    """Show student detail."""
    student_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_student(student_id)
            
            if response.get('success'):
                student = response.get('data', {})
                
                birth_date = student.get('birth_date', 'N/A')
                if birth_date and birth_date != 'N/A':
                    birth_date = str(birth_date)[:10]
                else:
                    birth_date = 'N/A'
                
                text = (
                    f"👤 <b>Talaba ma'lumotlari</b>\n\n"
                    f"<b>ID:</b> {safe_html_text(student.get('id'))}\n"
                    f"<b>Ism:</b> {safe_html_text(student.get('full_name'))}\n"
                    f"<b>Email:</b> {safe_html_text(student.get('email'))}\n"
                    f"<b>Telefon:</b> {safe_html_text(student.get('phone'))}\n"
                    f"<b>Passport:</b> {safe_html_text(student.get('passport_serial_number'))}\n"
                    f"<b>Tug'ilgan sana:</b> {safe_html_text(birth_date)}\n"
                    f"<b>Manba:</b> {safe_html_text(student.get('source_display') or student.get('source') or 'N/A')}\n"
                )
                
                if student.get('group_name'):
                    text += f"<b>Guruh:</b> {safe_html_text(student.get('group_name'))}\n"
                
                if student.get('address'):
                    text += f"<b>Manzil:</b> {safe_html_text(student.get('address'))}\n"
                
                text += f"\n<b>Holat:</b> {'✅ Faol' if student.get('is_active') else '❌ Nofaol'}"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_student_detail_keyboard(student_id, role=role),
                    parse_mode="HTML"
                )
                await callback.answer()
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Student detail error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "back_to_students")
async def back_to_students(callback: CallbackQuery):
    """Go back to students list."""
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_students()
            students = extract_list_from_response(response)
            
            text = f"📋 **Talabalar ro'yxati** ({len(students)} ta)\n\n"
            text += "Quyidagilardan birini tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_students_list_keyboard(students, page=0),
                parse_mode="Markdown"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Back to students error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "create_student")
async def create_student_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new student."""
    user_id = callback.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await callback.answer("Siz tizimga kirmagansiz.", show_alert=True)
        return
    
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    # Check if user has permission (only Developer or Administrator can create students)
    if role not in ['dasturchi', 'administrator']:
        await callback.answer("❌ Bu amalni bajarish uchun Dasturchi yoki Administrator roli kerak.", show_alert=True)
        return
    
    await callback.message.answer(
        "Yangi talaba qo'shish\n\n"
        "Talabaning to'liq ismini kiriting:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateStudentStates.waiting_for_full_name)
    await callback.answer()


@router.message(CreateStudentStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    await state.update_data(full_name=message.text.strip())
    await message.answer("Email manzilini kiriting:")
    await state.set_state(CreateStudentStates.waiting_for_email)


@router.message(CreateStudentStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """Process email."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    email = message.text.strip()
    if '@' not in email:
        await message.answer("Iltimos, to'g'ri email manzil kiriting:")
        return
    
    await state.update_data(email=email)
    await message.answer("Telefon raqamini kiriting (masalan: +998901234567):")
    await state.set_state(CreateStudentStates.waiting_for_phone)


@router.message(CreateStudentStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    phone = message.text.strip()
    is_valid, error_msg = validate_phone(phone)
    
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nIltimos, telefon raqamini qayta kiriting (masalan: +998901234567):")
        return
    
    await state.update_data(phone=phone)
    await message.answer("Passport seriya raqamini kiriting (masalan: AB1234567):")
    await state.set_state(CreateStudentStates.waiting_for_passport)


@router.message(CreateStudentStates.waiting_for_passport)
async def process_passport(message: Message, state: FSMContext):
    """Process passport."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    passport = message.text.strip().upper()
    is_valid, error_msg = validate_passport(passport)
    
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nIltimos, passport seriya raqamini qayta kiriting (masalan: AB1234567):")
        return
    
    await state.update_data(passport_serial_number=passport)
    await message.answer("Tug'ilgan sanani kiriting (YYYY-MM-DD formatida, masalan: 2000-01-15):")
    await state.set_state(CreateStudentStates.waiting_for_birth_date)


@router.message(CreateStudentStates.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    """Process birth date."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    await state.update_data(birth_date=message.text.strip())
    
    # Show inline keyboard for source selection
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Instagram", callback_data="source_instagram")],
        [InlineKeyboardButton(text="👥 Facebook", callback_data="source_facebook")],
        [InlineKeyboardButton(text="✈️ Telegram", callback_data="source_telegram")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_create_student")]
    ])
    
    await message.answer(
        "Manbani tanlang:",
        reply_markup=keyboard
    )
    await state.set_state(CreateStudentStates.waiting_for_source)


@router.callback_query(F.data.startswith("source_"), CreateStudentStates.waiting_for_source)
async def process_source_callback(callback: CallbackQuery, state: FSMContext):
    """Process source selection from inline keyboard."""
    source = callback.data.split("_")[1]  # source_instagram -> instagram
    await state.update_data(source=source)
    
    source_names = {
        'instagram': 'Instagram',
        'facebook': 'Facebook',
        'telegram': 'Telegram'
    }
    
    await callback.message.edit_text(f"✅ Manba tanlandi: {source_names.get(source, source)}")
    await callback.answer()
    await callback.message.answer("Manzilni kiriting (ixtiyoriy, o'tkazib yuborish uchun 'skip' yozing):")
    await state.set_state(CreateStudentStates.waiting_for_address)


@router.callback_query(F.data == "cancel_create_student")
async def cancel_create_student_callback(callback: CallbackQuery, state: FSMContext):
    """Cancel student creation."""
    await state.clear()
    await callback.message.edit_text("Talaba qo'shish bekor qilindi.")
    await callback.answer()


@router.message(CreateStudentStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """Process address and create student."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Talaba qo'shish bekor qilindi.")
        return
    
    data = await state.get_data()
    address = message.text.strip() if message.text.strip().lower() != 'skip' else ''
    
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    student_data = {
        'full_name': data.get('full_name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'passport_serial_number': data.get('passport_serial_number'),
        'birth_date': data.get('birth_date'),
        'source': data.get('source'),
        'address': address,
        'password': 'TempPass123!',  # Default password, should be changed
        'password_confirm': 'TempPass123!',
        'inn': '',
        'pinfl': ''
    }
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.create_student(student_data)
            
            if response.get('success'):
                student = response.get('data', {})
                await message.answer(
                    f"✅ Talaba muvaffaqiyatli qo'shildi!\n\n"
                    f"<b>Ism:</b> {safe_html_text(student.get('full_name'))}\n"
                    f"<b>Email:</b> {safe_html_text(student.get('email'))}\n"
                    f"<b>Telefon:</b> {safe_html_text(student.get('phone'))}\n\n"
                    f"⚠️ Eslatma: Talaba parolini o'zgartirishi kerak.",
                    parse_mode="HTML"
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Talaba qo\'shilmadi')
                errors = response.get('errors', {})
                formatted_error = format_error_message(error_msg, errors)
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Create student error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Edit Student Handlers
@router.callback_query(F.data.startswith("edit_student_"))
async def edit_student_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a student."""
    student_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if role not in ['dasturchi', 'administrator']:
        await callback.answer("❌ Talabani tahrirlash uchun Dasturchi yoki Administrator roli kerak.", show_alert=True)
        return

    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_student(student_id)
            
            if response.get('success'):
                student = response.get('data', {})
                await state.update_data(student_id=student_id, student_data=student)
                
                is_active = student.get('is_active', False)
                status_text = "Profilni bloklash" if is_active else "Profilni aktivlashtirish"
                
                text = (
                    "✏️ <b>Talabani tahrirlash</b>\n\n"
                    "Qaysi maydonni tahrirlamoqchisiz?\n\n"
                    "1️⃣ Ism (full_name)\n"
                    "2️⃣ Telefon (phone)\n"
                    "3️⃣ Passport (passport_serial_number)\n"
                    "4️⃣ Tug'ilgan sana (birth_date)\n"
                    "5️⃣ Manba (source)\n"
                    "6️⃣ Manzil (address)\n"
                    f"7️⃣ {status_text}\n\n"
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
                await state.set_state(EditStudentStates.waiting_for_field)
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Edit student start error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "cancel_action")
async def cancel_edit_action(callback: CallbackQuery, state: FSMContext):
    """Cancel edit action."""
    await state.clear()
    await callback.message.edit_text("Tahrirlash bekor qilindi.")
    await callback.answer()


@router.message(EditStudentStates.waiting_for_field)
async def process_edit_field(message: Message, state: FSMContext):
    """Process field selection for editing."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_menu_keyboard(None))
        return
    
    field_map = {
        '1': 'full_name',
        '2': 'phone',
        '3': 'passport_serial_number',
        '4': 'birth_date',
        '5': 'source',
        '6': 'address',
        '7': 'is_active'
    }
    
    field_key = message.text.strip()
    field_name = field_map.get(field_key)
    
    if not field_name:
        await message.answer("❌ Noto'g'ri raqam. 1-7 orasidagi raqamni yuboring.")
        return
    
    data = await state.get_data()
    student_data = data.get('student_data', {})
    
    if field_name == 'is_active':
        # Toggle is_active
        new_value = not student_data.get('is_active', False)
        await state.update_data(field_name=field_name, field_value=new_value)
        await update_student_field(message, state)
    elif field_name == 'source':
        # Show inline keyboard for source selection
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📷 Instagram", callback_data="edit_source_instagram")],
            [InlineKeyboardButton(text="👥 Facebook", callback_data="edit_source_facebook")],
            [InlineKeyboardButton(text="✈️ Telegram", callback_data="edit_source_telegram")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")]
        ])
        await message.answer("Yangi manbani tanlang:", reply_markup=keyboard)
        await state.set_state(EditStudentStates.waiting_for_value)
    else:
        await state.update_data(field_name=field_name)
        
        field_labels = {
            'full_name': 'Ism',
            'phone': 'Telefon',
            'passport_serial_number': 'Passport seriya raqami',
            'birth_date': 'Tug\'ilgan sana (YYYY-MM-DD)',
            'address': 'Manzil'
        }
        
        await message.answer(
            f"Yangi {field_labels.get(field_name, field_name)} ni yuboring:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(EditStudentStates.waiting_for_value)


@router.callback_query(F.data.startswith("edit_source_"))
async def process_edit_source_callback(callback: CallbackQuery, state: FSMContext):
    """Process source selection for editing."""
    source = callback.data.split("_")[2]  # edit_source_instagram -> instagram
    await state.update_data(field_name='source', field_value=source)
    
    source_names = {
        'instagram': 'Instagram',
        'facebook': 'Facebook',
        'telegram': 'Telegram'
    }
    
    await callback.message.edit_text(f"✅ Manba tanlandi: {source_names.get(source, source)}")
    await callback.answer()
    await update_student_field_from_callback(callback, state)


@router.message(EditStudentStates.waiting_for_value)
async def process_edit_value(message: Message, state: FSMContext):
    """Process new value for field."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_menu_keyboard(None))
        return
    
    data = await state.get_data()
    field_name = data.get('field_name')
    value = message.text.strip()
    
    # Validate phone
    if field_name == 'phone':
        is_valid, error_msg = validate_phone(value)
        if not is_valid:
            await message.answer(f"❌ {error_msg}\n\nIltimos, telefon raqamini qayta kiriting (masalan: +998901234567):")
            return
    
    # Validate passport
    if field_name == 'passport_serial_number':
        value = value.upper()
        is_valid, error_msg = validate_passport(value)
        if not is_valid:
            await message.answer(f"❌ {error_msg}\n\nIltimos, passport seriya raqamini qayta kiriting (masalan: AB1234567):")
            return
    
    # Validate birth_date format
    if field_name == 'birth_date':
        try:
            from datetime import datetime
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            await message.answer("❌ Noto'g'ri sana formati. YYYY-MM-DD formatida yuboring (masalan: 2000-01-15)")
            return
    
    await state.update_data(field_value=value)
    await update_student_field(message, state)


async def update_student_field_from_callback(callback: CallbackQuery, state: FSMContext):
    """Update student field via API (from callback)."""
    data = await state.get_data()
    student_id = data.get('student_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_student(student_id, update_data)
            
            if response.get('success'):
                await callback.message.answer(
                    f"✅ Talaba ma'lumotlari muvaffaqiyatli yangilandi!",
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
        logger.error(f"Update student error: {str(e)}")
        await callback.message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


async def update_student_field(message: Message, state: FSMContext):
    """Update student field via API."""
    data = await state.get_data()
    student_id = data.get('student_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_student(student_id, update_data)
            
            if response.get('success'):
                await message.answer(
                    f"✅ Talaba ma'lumotlari muvaffaqiyatli yangilandi!",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Yangilash muvaffaqiyatsiz')
                errors = response.get('errors')
                formatted_error = format_error_message(error_msg, errors)
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Update student error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Book Student Handlers
@router.callback_query(F.data.startswith("book_student_"))
async def book_student_start(callback: CallbackQuery, state: FSMContext):
    """Start booking a student to a group."""
    student_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Get student info
            student_response = await client.get_student(student_id)
            if not student_response.get('success'):
                error_msg = student_response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
                return
            
            student = student_response.get('data', {})
            
            # Check if student already has a group
            if student.get('group'):
                await callback.answer(
                    f"⚠️ Bu talaba allaqachon '{student.get('group_name', 'guruh')}' guruhiga yozilgan.",
                    show_alert=True
                )
                return
            
            # Get available groups
            groups_response = await client.get_booking_groups()
            # Backend returns list directly or wrapped in success_response
            if isinstance(groups_response, list):
                groups = groups_response
            elif groups_response.get('success'):
                groups = groups_response.get('data', [])
            else:
                groups = groups_response if isinstance(groups_response, list) else []
            
            if not groups:
                await callback.answer("❌ Yozilish uchun mavjud guruhlar topilmadi.", show_alert=True)
                return
            
            await state.update_data(student_id=student_id)
            
            # Create keyboard with groups
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = []
            for group in groups[:10]:  # Limit to 10 groups
                group_name = group.get('name', f"Guruh #{group.get('id')}")
                available = group.get('available_seats', 0)
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{group_name} ({available} o'rin)",
                        callback_data=f"select_group_{group.get('id')}"
                    )
                ])
            keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_booking")])
            
            text = (
                f"📚 <b>Talabani guruhga yozish</b>\n\n"
                f"<b>Talaba:</b> {safe_html_text(student.get('full_name'))}\n\n"
                f"Quyidagi guruhlardan birini tanlang:"
            )
            
            # Ensure text doesn't exceed Telegram's limit
            text = truncate_message(text, max_length=4000)
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="Markdown"
            )
            await callback.answer()
            await state.set_state(BookStudentStates.waiting_for_group_selection)
    except Exception as e:
        logger.error(f"Book student start error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("select_group_"))
async def process_group_selection(callback: CallbackQuery, state: FSMContext):
    """Process group selection for booking."""
    group_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    student_id = data.get('student_id')
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.book_student(student_id, group_id)
            
            if response.get('success'):
                await callback.message.edit_text(
                    f"✅ Talaba muvaffaqiyatli guruhga yozildi!",
                    reply_markup=None
                )
                await callback.answer("✅ Muvaffaqiyatli!", show_alert=True)
                await state.clear()
            else:
                error_msg = response.get('message', 'Yozilish muvaffaqiyatsiz')
                errors = response.get('errors')
                # For callback.answer, we need shorter messages (max 200 chars for alert)
                if errors:
                    error_list = [f"{k}: {v[0]}" for k, v in list(errors.items())[:3]]  # Max 3 errors
                    error_msg += f" ({', '.join(error_list)})"
                    if len(errors) > 3:
                        error_msg += f" va {len(errors) - 3} ta boshqa xato"
                # Truncate to 200 chars for alert
                if len(error_msg) > 200:
                    error_msg = error_msg[:197] + "..."
                error_msg_truncated = truncate_alert_message(f"❌ {error_msg}")
                await callback.answer(error_msg_truncated, show_alert=True)
    except Exception as e:
        logger.error(f"Book student error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
    finally:
        await state.clear()


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Cancel booking process."""
    await state.clear()
    await callback.message.edit_text("Yozilish bekor qilindi.")
    await callback.answer()


# Delete Student Handler
@router.callback_query(F.data.startswith("delete_student_"))
async def delete_student_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm student deletion."""
    student_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if role not in ['dasturchi', 'administrator']:
        await callback.answer("❌ Talabani o'chirish uchun Dasturchi yoki Administrator roli kerak.", show_alert=True)
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Get student info for confirmation
            response = await client.get_student(student_id)
            
            if response.get('success'):
                student = response.get('data', {})
                await state.update_data(student_id=student_id)
                
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_student_{student_id}")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"student_{student_id}")]
                ])
                
                text = (
                    f"⚠️ <b>Talabani o'chirish</b>\n\n"
                    f"<b>Talaba:</b> {safe_html_text(student.get('full_name'))}\n"
                    f"<b>ID:</b> {safe_html_text(student.get('id'))}\n\n"
                    f"⚠️ Bu amalni bekor qilib bo'lmaydi!\n\n"
                    f"Talabani o'chirishni tasdiqlaysizmi?"
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
        logger.error(f"Delete student confirm error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_student_"))
async def delete_student_execute(callback: CallbackQuery, state: FSMContext):
    """Execute student deletion."""
    student_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if role not in ['dasturchi', 'administrator']:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.delete_student(student_id)
            
            if response.get('success'):
                await callback.message.edit_text(
                    "✅ Talaba muvaffaqiyatli o'chirildi!",
                    reply_markup=None
                )
                await callback.answer("✅ Muvaffaqiyatli!", show_alert=True)
                
                # Go back to students list
                students_response = await client.get_students()
                students = extract_list_from_response(students_response)
                
                text = f"📋 <b>Talabalar ro'yxati</b> ({len(students)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                
                await callback.message.answer(
                    text,
                    reply_markup=get_students_list_keyboard(students, page=0),
                    parse_mode="HTML"
                )
            else:
                error_msg = response.get('message', 'O\'chirish muvaffaqiyatsiz')
                error_msg_truncated = truncate_alert_message(f"❌ {error_msg}")
                await callback.answer(error_msg_truncated, show_alert=True)
    except Exception as e:
        logger.error(f"Delete student error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
    finally:
        await state.clear()
