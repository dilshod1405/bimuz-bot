"""Group management handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_client import APIClient
from storage import user_storage
from keyboards import (
    get_groups_list_keyboard,
    get_group_detail_keyboard,
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_cancel_inline_keyboard,
    get_back_inline_keyboard
)
from utils import extract_list_from_response, truncate_message, truncate_alert_message, safe_html_text, format_error_message
import logging
from permissions import (
    can_create_group,
    can_update_group,
    can_delete_group,
)

logger = logging.getLogger(__name__)

router = Router()


class CreateGroupStates(StatesGroup):
    waiting_for_speciality = State()
    waiting_for_dates = State()
    waiting_for_time = State()
    waiting_for_starting_date = State()
    waiting_for_seats = State()
    waiting_for_price = State()
    waiting_for_mentor = State()


class EditGroupStates(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()


@router.message(F.text == "📚 Guruhlar")
async def cmd_groups(message: Message):
    """Show groups list."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_groups()
            groups = extract_list_from_response(response)
            
            if not groups:
                await message.answer(
                    "📚 Guruhlar ro'yxati bo'sh.\n\n"
                    "Yangi guruh qo'shish uchun quyidagi tugmani bosing:",
                    reply_markup=get_groups_list_keyboard([], page=0, role=role)
                )
            else:
                text = f"📚 <b>Guruhlar ro'yxati</b> ({len(groups)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_groups_list_keyboard(groups, page=0, role=role),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Groups list error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data.startswith("groups_page_"))
async def groups_pagination(callback: CallbackQuery):
    """Handle groups list pagination."""
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_groups()
            groups = extract_list_from_response(response)
            
            await callback.message.edit_reply_markup(
                reply_markup=get_groups_list_keyboard(groups, page=page, role=role)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Groups pagination error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("group_"))
async def show_group_detail(callback: CallbackQuery):
    """Show group detail."""
    group_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_group(group_id)
            
            if response.get('success'):
                group = response.get('data', {})
                
                text = (
                    f"📚 <b>Guruh ma'lumotlari</b>\n\n"
                    f"<b>ID:</b> {safe_html_text(group.get('id'))}\n"
                    f"<b>Mutaxassislik:</b> {safe_html_text(group.get('speciality_display') or group.get('speciality_id'))}\n"
                    f"<b>Kunlar:</b> {safe_html_text(group.get('dates_display') or group.get('dates'))}\n"
                    f"<b>Vaqt:</b> {safe_html_text(group.get('time'))}\n"
                    f"<b>Narx:</b> {safe_html_text(group.get('price', 0))} so'm\n"
                    f"<b>O'rinlar:</b> {safe_html_text(group.get('current_students_count', 0))}/{safe_html_text(group.get('seats', 0))}\n"
                    f"<b>Bo'sh o'rinlar:</b> {safe_html_text(group.get('available_seats', 0))}\n"
                )
                
                if group.get('starting_date'):
                    text += f"<b>Boshlanish sanasi:</b> {safe_html_text(str(group.get('starting_date'))[:10])}\n"
                
                if group.get('mentor_name'):
                    text += f"<b>Mentor:</b> {safe_html_text(group.get('mentor_name'))}\n"
                
                if group.get('total_lessons'):
                    text += f"<b>Darslar soni:</b> {safe_html_text(group.get('total_lessons'))}\n"
                
                text += f"\n<b>Holat:</b> {'✅ Faol' if group.get('is_active') else '❌ Nofaol'}"
                
                # Ensure text doesn't exceed Telegram's limit
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_group_detail_keyboard(group_id, role),
                    parse_mode="HTML"
                )
                await callback.answer()
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Group detail error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "back_to_groups")
async def back_to_groups(callback: CallbackQuery):
    """Go back to groups list."""
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_groups()
            groups = extract_list_from_response(response)
            
            text = f"📚 <b>Guruhlar ro'yxati</b> ({len(groups)} ta)\n\n"
            text += "Quyidagilardan birini tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_groups_list_keyboard(groups, page=0, role=role),
                parse_mode="HTML"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Back to groups error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


# Create Group Handlers
@router.callback_query(F.data == "create_group")
async def create_group_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new group."""
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if not can_create_group(role):
        await callback.answer("❌ Guruh yaratish uchun Dasturchi, Direktor yoki Administrator roli kerak.", show_alert=True)
        return

    await callback.message.answer(
        "Yangi guruh yaratish\n\n"
        "Mutaxassislikni tanlang:\n"
        "1. Revit Architecture\n"
        "2. Revit Structure\n"
        "3. Tekla Structure\n\n"
        "Raqam yuboring:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()
    await state.set_state(CreateGroupStates.waiting_for_speciality)


@router.message(CreateGroupStates.waiting_for_speciality)
async def process_speciality(message: Message, state: FSMContext):
    """Process speciality selection."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    speciality_map = {
        '1': 'revit_architecture',
        '2': 'revit_structure',
        '3': 'tekla_structure',
        'revit_architecture': 'revit_architecture',
        'revit_structure': 'revit_structure',
        'tekla_structure': 'tekla_structure'
    }
    
    speciality = speciality_map.get(message.text.strip().lower())
    if not speciality:
        await message.answer("❌ Noto'g'ri tanlov. 1-3 orasidagi raqamni yuboring.")
        return
    
    await state.update_data(speciality_id=speciality)
    await message.answer(
        "Kunlarni tanlang:\n"
        "1. Dushanba - Chorshanba - Juma\n"
        "2. Seshanba - Payshanba - Shanba\n\n"
        "Raqam yuboring:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateGroupStates.waiting_for_dates)


@router.message(CreateGroupStates.waiting_for_dates)
async def process_dates(message: Message, state: FSMContext):
    """Process dates selection."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    dates_map = {
        '1': 'mon_wed_fri',
        '2': 'tue_thu_sat',
        'mon_wed_fri': 'mon_wed_fri',
        'tue_thu_sat': 'tue_thu_sat'
    }
    
    dates = dates_map.get(message.text.strip().lower())
    if not dates:
        await message.answer("❌ Noto'g'ri tanlov. 1 yoki 2 raqamini yuboring.")
        return
    
    await state.update_data(dates=dates)
    await message.answer("Vaqtni kiriting (masalan: 10:00):")
    await state.set_state(CreateGroupStates.waiting_for_time)


@router.message(CreateGroupStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """Process time."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    time_str = message.text.strip()
    # Validate time format (HH:MM)
    try:
        from datetime import datetime
        datetime.strptime(time_str, '%H:%M')
    except ValueError:
        await message.answer("❌ Noto'g'ri vaqt formati. HH:MM formatida kiriting (masalan: 10:00)")
        return
    
    await state.update_data(time=time_str)
    await message.answer("Boshlanish sanasini kiriting (YYYY-MM-DD formatida, masalan: 2024-01-15):")
    await state.set_state(CreateGroupStates.waiting_for_starting_date)


@router.message(CreateGroupStates.waiting_for_starting_date)
async def process_starting_date(message: Message, state: FSMContext):
    """Process starting date."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    date_str = message.text.strip()
    try:
        from datetime import datetime
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        await message.answer("❌ Noto'g'ri sana formati. YYYY-MM-DD formatida kiriting (masalan: 2024-01-15)")
        return
    
    await state.update_data(starting_date=date_str)
    await message.answer("O'rinlar sonini kiriting (masalan: 12):")
    await state.set_state(CreateGroupStates.waiting_for_seats)


@router.message(CreateGroupStates.waiting_for_seats)
async def process_seats(message: Message, state: FSMContext):
    """Process seats."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    try:
        seats = int(message.text.strip())
        if seats <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri son. Iltimos, musbat butun son kiriting.")
        return
    
    await state.update_data(seats=seats)
    await message.answer("Narxni kiriting (so'm, masalan: 1500000):")
    await state.set_state(CreateGroupStates.waiting_for_price)


@router.message(CreateGroupStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    """Process price."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    try:
        price = float(message.text.strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri narx. Iltimos, musbat son kiriting.")
        return
    
    await state.update_data(price=price)
    await message.answer("Darslar sonini kiriting (masalan: 24):")
    await state.set_state(CreateGroupStates.waiting_for_mentor)


@router.message(CreateGroupStates.waiting_for_mentor)
async def process_mentor_and_create(message: Message, state: FSMContext):
    """Process total_lessons and create group."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Guruh yaratish bekor qilindi.")
        return
    
    try:
        total_lessons = int(message.text.strip())
        if total_lessons <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri son. Iltimos, musbat butun son kiriting.")
        return
    
    data = await state.get_data()
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    group_data = {
        'speciality_id': data.get('speciality_id'),
        'dates': data.get('dates'),
        'time': data.get('time'),
        'starting_date': data.get('starting_date'),
        'seats': data.get('seats'),
        'price': data.get('price'),
        'total_lessons': total_lessons,
    }
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.create_group(group_data)
            
            if response.get('success'):
                group = response.get('data', {})
                await message.answer(
                    f"✅ Guruh muvaffaqiyatli yaratildi!\n\n"
                    f"<b>ID:</b> {safe_html_text(group.get('id'))}\n"
                    f"<b>Mutaxassislik:</b> {safe_html_text(group.get('speciality_display'))}\n"
                    f"<b>Kunlar:</b> {safe_html_text(group.get('dates_display'))}\n"
                    f"<b>Vaqt:</b> {safe_html_text(group.get('time'))}\n"
                    f"<b>Narx:</b> {safe_html_text(group.get('price'))} so'm",
                    reply_markup=get_main_menu_keyboard(role),
                    parse_mode="HTML"
                )
                await state.clear()
            else:
                formatted_error = format_error_message(
                    response.get('message', 'Guruh yaratilmadi'),
                    response.get('errors')
                )
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Create group error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Edit Group Handlers
@router.callback_query(F.data.startswith("edit_group_"))
async def edit_group_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a group."""
    group_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if not can_update_group(role):
        await callback.answer("❌ Guruhni tahrirlash uchun Dasturchi, Direktor yoki Administrator roli kerak.", show_alert=True)
        return

    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_group(group_id)
            
            if response.get('success'):
                group = response.get('data', {})
                await state.update_data(group_id=group_id, group_data=group)
                
                text = (
                    "✏️ <b>Guruhni tahrirlash</b>\n\n"
                    "Qaysi maydonni tahrirlamoqchisiz?\n\n"
                    "1️⃣ Mutaxassislik\n"
                    "2️⃣ Kunlar\n"
                    "3️⃣ Vaqt\n"
                    "4️⃣ Boshlanish sanasi\n"
                    "5️⃣ O'rinlar soni\n"
                    "6️⃣ Narx\n"
                    "7️⃣ Darslar soni\n\n"
                    "Raqam yuboring:"
                )
                
                text = truncate_message(text, max_length=4000)
                await callback.message.edit_text(
                    text,
                    reply_markup=get_back_inline_keyboard(f"group_{group_id}"),
                    parse_mode="HTML"
                )
                await callback.answer()
                await state.set_state(EditGroupStates.waiting_for_field)
            else:
                error_msg = response.get('message', 'Xatolik')
                error_msg = truncate_alert_message(f"Xatolik: {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Edit group start error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "cancel_action")
async def cancel_edit_group_action(callback: CallbackQuery, state: FSMContext):
    """Cancel edit group action - go back to group detail."""
    data = await state.get_data()
    group_id = data.get('group_id')
    await state.clear()
    
    if group_id:
        # Go back to group detail
        user_id = callback.from_user.id
        access_token = await user_storage.get_access_token(user_id)
        employee = await user_storage.get_employee(user_id)
        role = employee.get('role') if employee else None
        
        try:
            async with APIClient(access_token=access_token, user_id=user_id) as client:
                response = await client.get_group(group_id)
                if response.get('success'):
                    group = response.get('data', {})
                    text = (
                        f"📚 <b>Guruh ma'lumotlari</b>\n\n"
                        f"<b>ID:</b> {safe_html_text(group.get('id'))}\n"
                        f"<b>Mutaxassislik:</b> {safe_html_text(group.get('speciality_display') or group.get('speciality_id'))}\n"
                        f"<b>Kunlar:</b> {safe_html_text(group.get('dates_display') or group.get('dates'))}\n"
                        f"<b>Vaqt:</b> {safe_html_text(group.get('time'))}\n"
                        f"<b>Narx:</b> {safe_html_text(group.get('price', 0))} so'm\n"
                        f"<b>O'rinlar:</b> {safe_html_text(group.get('current_students_count', 0))}/{safe_html_text(group.get('seats', 0))}\n"
                        f"<b>Bo'sh o'rinlar:</b> {safe_html_text(group.get('available_seats', 0))}\n"
                    )
                    if group.get('starting_date'):
                        text += f"<b>Boshlanish sanasi:</b> {safe_html_text(str(group.get('starting_date'))[:10])}\n"
                    if group.get('mentor_name'):
                        text += f"<b>Mentor:</b> {safe_html_text(group.get('mentor_name'))}\n"
                    if group.get('total_lessons'):
                        text += f"<b>Darslar soni:</b> {safe_html_text(group.get('total_lessons'))}\n"
                    text += f"\n<b>Holat:</b> {'✅ Faol' if group.get('is_active') else '❌ Nofaol'}"
                    text = truncate_message(text, max_length=4000)
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_group_detail_keyboard(group_id, role),
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Error going back to group detail: {str(e)}")
            await callback.message.edit_text("Tahrirlash bekor qilindi.")
    else:
        await callback.message.edit_text("Tahrirlash bekor qilindi.")
    await callback.answer()


@router.message(EditGroupStates.waiting_for_field)
async def process_edit_group_field(message: Message, state: FSMContext):
    """Process field selection for editing."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_menu_keyboard(None))
        return
    
    field_map = {
        '1': 'speciality_id',
        '2': 'dates',
        '3': 'time',
        '4': 'starting_date',
        '5': 'seats',
        '6': 'price',
        '7': 'total_lessons'
    }
    
    field_key = message.text.strip()
    field_name = field_map.get(field_key)
    
    if not field_name:
        await message.answer("❌ Noto'g'ri raqam. 1-7 orasidagi raqamni yuboring.")
        return
    
    data = await state.get_data()
    group_data = data.get('group_data', {})
    group_id = data.get('group_id')
    await state.update_data(field_name=field_name)
    
    # Handle special cases with inline keyboards
    if field_name == 'speciality_id':
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏗️ Revit Architecture", callback_data="edit_speciality_revit_architecture")],
            [InlineKeyboardButton(text="🏗️ Revit Structure", callback_data="edit_speciality_revit_structure")],
            [InlineKeyboardButton(text="🏗️ Tekla Structure", callback_data="edit_speciality_tekla_structure")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"edit_group_{group_id}")]
        ])
        await message.answer("Yangi mutaxassislikni tanlang:", reply_markup=keyboard)
        await state.set_state(EditGroupStates.waiting_for_value)
    elif field_name == 'dates':
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Dushanba - Chorshanba - Juma", callback_data="edit_dates_mon_wed_fri")],
            [InlineKeyboardButton(text="📅 Seshanba - Payshanba - Shanba", callback_data="edit_dates_tue_thu_sat")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"edit_group_{group_id}")]
        ])
        await message.answer("Yangi kunlarni tanlang:", reply_markup=keyboard)
        await state.set_state(EditGroupStates.waiting_for_value)
    else:
        field_labels = {
            'time': 'Vaqt (HH:MM formatida, masalan: 10:00)',
            'starting_date': 'Boshlanish sanasi (YYYY-MM-DD formatida, masalan: 2024-01-15)',
            'seats': 'O\'rinlar soni (masalan: 12)',
            'price': 'Narx (so\'m, masalan: 1500000)',
            'total_lessons': 'Darslar soni (masalan: 24)'
        }
        
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"edit_group_{group_id}")]
        ])
        
        await message.answer(
            f"Yangi {field_labels.get(field_name, field_name)} ni yuboring:",
            reply_markup=keyboard
        )
        await state.set_state(EditGroupStates.waiting_for_value)


@router.callback_query(F.data.startswith("edit_speciality_"))
async def process_edit_speciality_callback(callback: CallbackQuery, state: FSMContext):
    """Process speciality selection for editing."""
    speciality = callback.data.split("_")[2]  # edit_speciality_revit_architecture -> revit_architecture
    await state.update_data(field_name='speciality_id', field_value=speciality)
    
    speciality_names = {
        'revit_architecture': 'Revit Architecture',
        'revit_structure': 'Revit Structure',
        'tekla_structure': 'Tekla Structure'
    }
    
    await callback.message.edit_text(f"✅ Mutaxassislik tanlandi: {speciality_names.get(speciality, speciality)}")
    await callback.answer()
    await update_group_field_from_callback(callback, state)


@router.callback_query(F.data.startswith("edit_dates_"))
async def process_edit_dates_callback(callback: CallbackQuery, state: FSMContext):
    """Process dates selection for editing."""
    dates = callback.data.split("_")[2]  # edit_dates_mon_wed_fri -> mon_wed_fri
    await state.update_data(field_name='dates', field_value=dates)
    
    dates_names = {
        'mon_wed_fri': 'Dushanba - Chorshanba - Juma',
        'tue_thu_sat': 'Seshanba - Payshanba - Shanba'
    }
    
    await callback.message.edit_text(f"✅ Kunlar tanlandi: {dates_names.get(dates, dates)}")
    await callback.answer()
    await update_group_field_from_callback(callback, state)


@router.message(EditGroupStates.waiting_for_value)
async def process_edit_group_value(message: Message, state: FSMContext):
    """Process new value for field."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        data = await state.get_data()
        group_id = data.get('group_id')
        if group_id:
            # Go back to group detail
            user_id = message.from_user.id
            access_token = await user_storage.get_access_token(user_id)
            employee = await user_storage.get_employee(user_id)
            role = employee.get('role') if employee else None
            
            try:
                async with APIClient(access_token=access_token, user_id=user_id) as client:
                    response = await client.get_group(group_id)
                    if response.get('success'):
                        group = response.get('data', {})
                        text = (
                            f"📚 <b>Guruh ma'lumotlari</b>\n\n"
                            f"<b>ID:</b> {safe_html_text(group.get('id'))}\n"
                            f"<b>Mutaxassislik:</b> {safe_html_text(group.get('speciality_display') or group.get('speciality_id'))}\n"
                            f"<b>Kunlar:</b> {safe_html_text(group.get('dates_display') or group.get('dates'))}\n"
                            f"<b>Vaqt:</b> {safe_html_text(group.get('time'))}\n"
                            f"<b>Narx:</b> {safe_html_text(group.get('price', 0))} so'm\n"
                            f"<b>O'rinlar:</b> {safe_html_text(group.get('current_students_count', 0))}/{safe_html_text(group.get('seats', 0))}\n"
                            f"<b>Bo'sh o'rinlar:</b> {safe_html_text(group.get('available_seats', 0))}\n"
                        )
                        if group.get('starting_date'):
                            text += f"<b>Boshlanish sanasi:</b> {safe_html_text(str(group.get('starting_date'))[:10])}\n"
                        if group.get('mentor_name'):
                            text += f"<b>Mentor:</b> {safe_html_text(group.get('mentor_name'))}\n"
                        if group.get('total_lessons'):
                            text += f"<b>Darslar soni:</b> {safe_html_text(group.get('total_lessons'))}\n"
                        text += f"\n<b>Holat:</b> {'✅ Faol' if group.get('is_active') else '❌ Nofaol'}"
                        text = truncate_message(text, max_length=4000)
                        await message.answer(
                            text,
                            reply_markup=get_group_detail_keyboard(group_id, role),
                            parse_mode="HTML"
                        )
            except Exception as e:
                logger.error(f"Error going back to group detail: {str(e)}")
        await state.clear()
        return
    
    data = await state.get_data()
    field_name = data.get('field_name')
    value = message.text.strip()
    
    # Validate based on field type
    if field_name == 'time':
        try:
            from datetime import datetime
            datetime.strptime(value, '%H:%M')
        except ValueError:
            await message.answer("❌ Noto'g'ri vaqt formati. HH:MM formatida yuboring (masalan: 10:00)")
            return
    elif field_name == 'starting_date':
        try:
            from datetime import datetime
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            await message.answer("❌ Noto'g'ri sana formati. YYYY-MM-DD formatida yuboring (masalan: 2024-01-15)")
            return
    elif field_name == 'seats':
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Noto'g'ri son. Iltimos, musbat butun son kiriting.")
            return
    elif field_name == 'price':
        try:
            value = float(value)
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Noto'g'ri narx. Iltimos, musbat son kiriting.")
            return
    elif field_name == 'total_lessons':
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Noto'g'ri son. Iltimos, musbat butun son kiriting.")
            return
    
    await state.update_data(field_value=value)
    await update_group_field(message, state)


async def update_group_field_from_callback(callback: CallbackQuery, state: FSMContext):
    """Update group field via API (from callback)."""
    data = await state.get_data()
    group_id = data.get('group_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_group(group_id, update_data)
            
            if response.get('success'):
                await callback.message.answer(
                    f"✅ Guruh ma'lumotlari muvaffaqiyatli yangilandi!",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                formatted_error = format_error_message(
                    response.get('message', 'Yangilash muvaffaqiyatsiz'),
                    response.get('errors')
                )
                await callback.message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Update group error: {str(e)}")
        await callback.message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


async def update_group_field(message: Message, state: FSMContext):
    """Update group field via API."""
    data = await state.get_data()
    group_id = data.get('group_id')
    field_name = data.get('field_name')
    field_value = data.get('field_value')
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None
    
    update_data = {field_name: field_value}
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.update_group(group_id, update_data)
            
            if response.get('success'):
                await message.answer(
                    f"✅ Guruh ma'lumotlari muvaffaqiyatli yangilandi!",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                formatted_error = format_error_message(
                    response.get('message', 'Yangilash muvaffaqiyatsiz'),
                    response.get('errors')
                )
                await message.answer(formatted_error)
    except Exception as e:
        logger.error(f"Update group error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()


# Delete Group Handler
@router.callback_query(F.data.startswith("delete_group_"))
async def delete_group_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm group deletion."""
    group_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if not can_delete_group(role):
        await callback.answer("❌ Guruhni o'chirish uchun Dasturchi, Direktor yoki Administrator roli kerak.", show_alert=True)
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            # Get group info for confirmation
            response = await client.get_group(group_id)
            
            if response.get('success'):
                group = response.get('data', {})
                await state.update_data(group_id=group_id)
                
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_group_{group_id}")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"group_{group_id}")]
                ])
                
                text = (
                    f"⚠️ <b>Guruhni o'chirish</b>\n\n"
                    f"<b>Guruh:</b> {safe_html_text(group.get('speciality_display'))}\n"
                    f"<b>ID:</b> {safe_html_text(group.get('id'))}\n\n"
                    f"⚠️ Bu amalni bekor qilib bo'lmaydi!\n\n"
                    f"Guruhni o'chirishni tasdiqlaysizmi?"
                )
                
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
        logger.error(f"Delete group confirm error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_group_"))
async def delete_group_execute(callback: CallbackQuery, state: FSMContext):
    """Execute group deletion."""
    group_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    employee = await user_storage.get_employee(user_id)
    role = employee.get('role') if employee else None

    if not can_delete_group(role):
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.delete_group(group_id)
            
            # Check if operation was successful (even if response format is unexpected)
            if response.get('success') or response.get('message', '').find('o\'chirildi') != -1:
                success_message = response.get('message', 'Guruh muvaffaqiyatli o\'chirildi.')
                
                await callback.message.edit_text(
                    f"✅ <b>Muvaffaqiyatli!</b>\n\n{safe_html_text(success_message)}",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                await callback.answer("✅ Guruh o'chirildi!", show_alert=True)
                
                # Go back to groups list
                try:
                    groups_response = await client.get_groups()
                    groups = extract_list_from_response(groups_response)
                    
                    text = f"📚 <b>Guruhlar ro'yxati</b> ({len(groups)} ta)\n\n"
                    text += "Quyidagilardan birini tanlang:"
                    
                    await callback.message.answer(
                        text,
                        reply_markup=get_groups_list_keyboard(groups, page=0),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error loading groups list after delete: {str(e)}")
            else:
                error_msg = response.get('message', 'O\'chirish muvaffaqiyatsiz')
                error_msg = truncate_alert_message(f"❌ {error_msg}")
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        error_str = str(e)
        # Check if it's a 204 parsing issue - if backend says success, treat as success
        if "204" in error_str or "Expected HTTP" in error_str or "o'chirildi" in error_str.lower():
            logger.info(f"Delete group completed (parsing issue ignored): {str(e)}")
            await callback.message.edit_text(
                "✅ <b>Muvaffaqiyatli!</b>\n\nGuruh muvaffaqiyatli o'chirildi.",
                reply_markup=None,
                parse_mode="HTML"
            )
            await callback.answer("✅ Guruh o'chirildi!", show_alert=True)
            
            # Try to go back to groups list
            try:
                async with APIClient(access_token=access_token, user_id=user_id) as client:
                    groups_response = await client.get_groups()
                    groups = extract_list_from_response(groups_response)
                    text = f"📚 <b>Guruhlar ro'yxati</b> ({len(groups)} ta)\n\n"
                    text += "Quyidagilardan birini tanlang:"
                    await callback.message.answer(
                        text,
                        reply_markup=get_groups_list_keyboard(groups, page=0),
                        parse_mode="HTML"
                    )
            except Exception:
                pass
        else:
            logger.error(f"Delete group error: {str(e)}")
            error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
            await callback.answer(error_msg, show_alert=True)
    finally:
        await state.clear()
