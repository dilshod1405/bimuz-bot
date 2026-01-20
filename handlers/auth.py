"""Authentication handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_client import APIClient
from storage import user_storage
from keyboards import get_main_menu_keyboard, get_cancel_keyboard
from utils import truncate_message
import logging

logger = logging.getLogger(__name__)

router = Router()


class LoginStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    user_id = message.from_user.id
    
    # Check if user is already authenticated
    if await user_storage.is_authenticated(user_id):
        employee = await user_storage.get_employee(user_id)
        role = employee.get('role') if employee else None
        await message.answer(
            f"Salom, {employee.get('full_name', 'Foydalanuvchi')}!\n\n"
            "Siz allaqachon tizimga kirgansiz.",
            reply_markup=get_main_menu_keyboard(role)
        )
        return
    
    await message.answer(
        "Salom! BIMUZ tizimiga xush kelibsiz.\n\n"
        "Tizimga kirish uchun email manzilingizni kiriting:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(LoginStates.waiting_for_email)


@router.message(LoginStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """Process email input."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Kirish bekor qilindi.", reply_markup=None)
        return
    
    email = message.text.strip()
    
    # Basic email validation
    if '@' not in email:
        await message.answer("Iltimos, to'g'ri email manzil kiriting:")
        return
    
    logger.info(f"Email received: {email}, user_id: {message.from_user.id}")
    await state.update_data(email=email)
    await message.answer("Parolingizni kiriting:")
    await state.set_state(LoginStates.waiting_for_password)


@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Process password and login."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Kirish bekor qilindi.", reply_markup=None)
        return
    
    password = message.text
    data = await state.get_data()
    email = data.get('email')
    
    if not email:
        logger.error("Email not found in state data")
        await message.answer(
            "❌ Email topilmadi. Qayta urinib ko'ring.\n\n"
            "Email manzilingizni kiriting:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(LoginStates.waiting_for_email)
        return
    
    logger.info(f"Attempting login for email: {email}")
    
    try:
        async with APIClient(user_id=message.from_user.id) as client:
            logger.info(f"Making login request for email: {email}")
            response = await client.login(email, password)
            logger.info(f"Login response: success={response.get('success')}, message={response.get('message')}")
            
            if response.get('success'):
                response_data = response.get('data', {})
                employee = response_data.get('employee', {})
                tokens = response_data.get('tokens', {})
                
                if not employee:
                    logger.error("Employee data not found in response")
                    await message.answer(
                        "❌ Xodim ma'lumotlari topilmadi.\n\n"
                        "Qayta urinib ko'ring. Email manzilingizni kiriting:",
                        reply_markup=get_cancel_keyboard()
                    )
                    await state.set_state(LoginStates.waiting_for_email)
                    return
                
                if not tokens.get('access') or not tokens.get('refresh'):
                    logger.error("Tokens not found in response")
                    await message.answer(
                        "❌ Tokenlar topilmadi.\n\n"
                        "Qayta urinib ko'ring. Email manzilingizni kiriting:",
                        reply_markup=get_cancel_keyboard()
                    )
                    await state.set_state(LoginStates.waiting_for_email)
                    return
                
                # Store user session
                logger.info(f"Storing session for user_id: {message.from_user.id}")
                await user_storage.set_user_data(
                    user_id=message.from_user.id,
                    access_token=tokens.get('access'),
                    refresh_token=tokens.get('refresh'),
                    employee_data=employee
                )
                
                role = employee.get('role')
                role_display = employee.get('role_display', role)
                
                logger.info(f"Login successful for user_id: {message.from_user.id}, role: {role}")
                await message.answer(
                    f"✅ Muvaffaqiyatli kirildi!\n\n"
                    f"👤 Ism: {employee.get('full_name')}\n"
                    f"📧 Email: {employee.get('email')}\n"
                    f"🎭 Rol: {role_display}\n\n"
                    "Quyidagi menyudan kerakli bo'limni tanlang:",
                    reply_markup=get_main_menu_keyboard(role)
                )
                await state.clear()
            else:
                error_msg = response.get('message', 'Kirishda xatolik yuz berdi')
                logger.warning(f"Login failed: {error_msg}")
                await message.answer(
                    f"❌ Xatolik: {error_msg}\n\n"
                    "Qayta urinib ko'ring. Email manzilingizni kiriting:",
                    reply_markup=get_cancel_keyboard()
                )
                await state.set_state(LoginStates.waiting_for_email)
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        error_msg = str(e)
        await message.answer(
            f"❌ Xatolik: {error_msg}\n\n"
            "Iltimos, qayta urinib ko'ring. Email manzilingizni kiriting:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(LoginStates.waiting_for_email)


@router.message(F.text == "❌ Chiqish")
async def cmd_logout(message: Message):
    """Handle logout."""
    user_id = message.from_user.id
    
    if await user_storage.is_authenticated(user_id):
        await user_storage.remove_user(user_id)
        await message.answer(
            "✅ Tizimdan chiqildi.\n\n"
            "Qayta kirish uchun /start buyrug'ini bosing.",
            reply_markup=None
        )
    else:
        await message.answer("Siz tizimga kirmagansiz.")


@router.message(F.text == "👤 Profil")
async def cmd_profile(message: Message):
    """Show user profile."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer(
            "Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing."
        )
        return
    
    employee = await user_storage.get_employee(user_id)
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_profile()
            
            if response.get('success'):
                profile = response.get('data', {})
                
                profile_text = (
                    f"👤 **Profil ma'lumotlari**\n\n"
                    f"**Ism:** {profile.get('full_name')}\n"
                    f"**Email:** {profile.get('email')}\n"
                    f"**Rol:** {profile.get('role_display', profile.get('role'))}\n"
                )
                
                if profile.get('professionality'):
                    profile_text += f"**Mutaxassislik:** {profile.get('professionality')}\n"
                
                profile_text += f"\n**Ro'yxatdan o'tgan:** {profile.get('created_at', 'N/A')[:10]}"
                
                # Ensure text doesn't exceed Telegram's limit
                profile_text = truncate_message(profile_text, max_length=4000)
                await message.answer(profile_text, parse_mode="Markdown")
            else:
                await message.answer(f"❌ Xatolik: {response.get('message', 'Profil yuklanmadi')}")
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
