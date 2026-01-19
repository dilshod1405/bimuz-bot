"""Payment/Invoice handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_client import APIClient
from storage import user_storage
from keyboards import (
    get_invoices_list_keyboard,
    get_invoice_detail_keyboard,
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_invoices_filter_keyboard
)
from utils import extract_list_from_response, truncate_message, truncate_alert_message, safe_html_text, format_error_message
import logging

logger = logging.getLogger(__name__)

router = Router()


class InvoiceSearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_filter = State()


@router.message(F.text == "💳 To'lovlar")
async def cmd_invoices(message: Message, state: FSMContext):
    """Show invoices list."""
    user_id = message.from_user.id
    
    if not await user_storage.is_authenticated(user_id):
        await message.answer("Siz tizimga kirmagansiz. Kirish uchun /start buyrug'ini bosing.")
        return
    
    # Clear any existing search/filter state
    await state.clear()
    
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoices()
            invoices = extract_list_from_response(response)
            
            if not invoices:
                await message.answer(
                    "💳 To'lovlar ro'yxati bo'sh.",
                    reply_markup=get_invoices_list_keyboard([], page=0)
                )
            else:
                text = f"💳 <b>To'lovlar ro'yxati</b> ({len(invoices)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_invoices_list_keyboard(invoices, page=0),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Invoices list error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data.startswith("invoices_page_"))
async def invoices_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle invoices list pagination."""
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    # Get current search/filter from state
    data = await state.get_data()
    search_query = data.get('search_query')
    status_filter = data.get('status_filter')
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoices(
                search=search_query,
                status=status_filter,
                page=page
            )
            invoices = extract_list_from_response(response)
            
            await callback.message.edit_reply_markup(
                reply_markup=get_invoices_list_keyboard(invoices, page=page)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Invoices pagination error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith("invoice_"))
async def show_invoice_detail(callback: CallbackQuery):
    """Show invoice detail."""
    invoice_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoice(invoice_id)
            
            # Backend returns invoice directly (DRF RetrieveAPIView) or wrapped in success_response
            invoice = None
            if response.get('success'):
                invoice = response.get('data', {})
            elif response.get('id'):  # Direct invoice object
                invoice = response
            else:
                await callback.answer(f"Xatolik: To'lov topilmadi", show_alert=True)
                return
            
            if not invoice:
                await callback.answer(f"Xatolik: To'lov ma'lumotlari yuklanmadi", show_alert=True)
                return
            
            status = invoice.get('status', 'created')
            status_display = invoice.get('status_display', status)
            
            # Format status with icon if paid
            if status == 'paid' or status_display.lower() in ['to\'langan', 'paid', 'to\'langan']:
                status_text = f"✅ {status_display}"
            else:
                status_emoji = {
                    'created': '🆕',
                    'pending': '⏳',
                    'cancelled': '❌',
                    'refunded': '↩️'
                }
                emoji = status_emoji.get(status, '📄')
                status_text = f"{emoji} {status_display}"
            
            # Format payment time - remove T and show in readable format
            payment_time_str = ""
            if invoice.get('payment_time'):
                payment_time = invoice.get('payment_time')
                # Replace T with space and format: 2026-01-19T17:24:41 -> 2026-01-19 17:24:41
                payment_time_str = payment_time.replace('T', ' ')[:19]
            
            # Calculate total paid amount for this student-group combination
            student_id = invoice.get('student')
            group_id = invoice.get('group')
            total_paid = 0.0
            total_amount = 0.0
            
            if student_id and group_id:
                try:
                    # Get all invoices for this student-group combination
                    all_invoices_response = await client.get_invoices()
                    all_invoices = extract_list_from_response(all_invoices_response)
                    
                    # Filter invoices for this student and group
                    student_group_invoices = [
                        inv for inv in all_invoices 
                        if inv.get('student') == student_id and inv.get('group') == group_id
                    ]
                    
                    # Calculate total paid amount
                    for inv in student_group_invoices:
                        if inv.get('status') == 'paid' or inv.get('is_paid'):
                            total_paid += float(inv.get('amount', 0))
                    
                    # Get group price (total amount to be paid)
                    group_response = await client.get_group(group_id)
                    if group_response.get('success'):
                        group_data = group_response.get('data', {})
                        total_amount = float(group_data.get('price', 0))
                except Exception as e:
                    logger.error(f"Error calculating payment progress: {str(e)}")
                    # If error, use current invoice amount as fallback
                    if is_paid:
                        total_paid = float(invoice.get('amount', 0))
            
            text = (
                f"✅ <b>To'lov ma'lumotlari</b>\n\n"
                f"<b>ID:</b> {safe_html_text(invoice.get('id'))}\n"
                f"<b>Talaba:</b> {safe_html_text(invoice.get('student_name'))}\n"
                f"<b>Telefon:</b> {safe_html_text(invoice.get('student_phone'))}\n"
                f"<b>Guruh:</b> {safe_html_text(invoice.get('group_name'))}\n"
                f"<b>Summa:</b> {safe_html_text(invoice.get('amount'))} so'm\n"
                f"<b>Holat:</b> {status_text}\n"
            )
            
            # Add payment progress if we have the data
            if total_amount > 0:
                text += f"\n<b>To'langan:</b> {safe_html_text(f'{total_paid:,.2f}')} so'm / <b>Jami:</b> {safe_html_text(f'{total_amount:,.2f}')} so'm\n"
                if total_paid < total_amount:
                    remaining = total_amount - total_paid
                    text += f"<b>Qolgan:</b> {safe_html_text(f'{remaining:,.2f}')} so'm\n"
            
            if payment_time_str:
                text += f"<b>To'lov vaqti:</b> {safe_html_text(payment_time_str)}\n"
            
            if invoice.get('payment_method'):
                text += f"<b>To'lov usuli:</b> {safe_html_text(invoice.get('payment_method'))}\n"
            
            if invoice.get('receipt_url'):
                text += f"<b>Chek:</b> {safe_html_text(invoice.get('receipt_url'))}\n"
            
            is_paid = invoice.get('is_paid', False)
            
            # Ensure text doesn't exceed Telegram's limit
            text = truncate_message(text, max_length=4000)
            await callback.message.edit_text(
                text,
                reply_markup=get_invoice_detail_keyboard(invoice_id, is_paid, status_display),
                parse_mode="HTML"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Invoice detail error: {str(e)}", exc_info=True)
        error_msg = str(e) if str(e) and str(e) != 'None' else "To'lov ma'lumotlarini yuklashda xatolik yuz berdi"
        error_msg_truncated = truncate_alert_message(f"Xatolik: {error_msg}")
        await callback.answer(error_msg_truncated, show_alert=True)


@router.callback_query(F.data.startswith("create_payment_"))
async def create_payment_link(callback: CallbackQuery):
    """Create payment link for invoice."""
    invoice_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.create_payment_link(invoice_id)
            
            if response.get('success'):
                data = response.get('data', {})
                checkout_url = data.get('checkout_url')
                
                if checkout_url:
                    await callback.message.answer(
                        f"✅ To'lov linki yaratildi!\n\n"
                        f"🔗 <b>To'lov linki:</b>\n{safe_html_text(checkout_url)}\n\n"
                        f"Ushbu linkni talabaga yuborishingiz mumkin.",
                        parse_mode="HTML"
                    )
                    await callback.answer("✅ To'lov linki yaratildi!", show_alert=True)
                else:
                    error_msg = "To'lov linki yaratilmadi. Ma'lumotlar to'liq emas."
                    await callback.answer(error_msg, show_alert=True)
            else:
                # Translate error messages to Uzbek
                error_message = response.get('message', 'To\'lov linki yaratilmadi')
                
                # Translate common error messages
                error_translations = {
                    'Invoice is already paid.': 'Bu to\'lov allaqachon to\'langan.',
                    'Invoice is cancelled.': 'Bu to\'lov bekor qilingan.',
                    'Invoice not found.': 'To\'lov topilmadi.',
                    'You do not have permission to pay this invoice.': 'Bu to\'lovni to\'lash uchun ruxsatingiz yo\'q.',
                    'already paid': 'Bu to\'lov allaqachon to\'langan.',
                    'cancelled': 'Bu to\'lov bekor qilingan.',
                    'not found': 'To\'lov topilmadi.'
                }
                
                # Check if error message matches any translation
                translated_message = error_message
                for eng, uz in error_translations.items():
                    if eng.lower() in error_message.lower():
                        translated_message = uz
                        break
                
                # Format error message with details
                formatted_error = format_error_message(
                    translated_message,
                    response.get('errors')
                )
                error_msg = truncate_alert_message(formatted_error)
                await callback.answer(error_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Create payment link error: {str(e)}", exc_info=True)
        error_str = str(e)
        
        # Check if it's a validation error from API
        if "400" in error_str or "Validation" in error_str or "invoice" in error_str.lower():
            # Translate error messages to Uzbek
            if "already paid" in error_str.lower():
                error_msg = "Bu to'lov allaqachon to'langan."
            elif "cancelled" in error_str.lower() or "bekor" in error_str.lower():
                error_msg = "Bu to'lov bekor qilingan."
            elif "not found" in error_str.lower() or "topilmadi" in error_str.lower():
                error_msg = "To'lov topilmadi."
            elif "permission" in error_str.lower() or "ruxsat" in error_str.lower():
                error_msg = "Bu to'lovni to'lash uchun ruxsatingiz yo'q."
            else:
                error_msg = f"To'lov linki yaratilmadi."
        else:
            error_msg = f"Xatolik: {error_str}"
        
        error_msg = truncate_alert_message(error_msg)
        await callback.answer(error_msg, show_alert=True)


@router.callback_query(F.data == "back_to_invoices")
async def back_to_invoices(callback: CallbackQuery, state: FSMContext):
    """Go back to invoices list."""
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    # Clear search/filter state
    await state.clear()
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoices()
            invoices = extract_list_from_response(response)
            
            text = f"💳 <b>To'lovlar ro'yxati</b> ({len(invoices)} ta)\n\n"
            text += "Quyidagilardan birini tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_invoices_list_keyboard(invoices, page=0),
                parse_mode="HTML"
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Back to invoices error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)


# Search functionality
@router.callback_query(F.data == "search_invoices")
async def search_invoices_start(callback: CallbackQuery, state: FSMContext):
    """Start searching invoices."""
    await callback.message.answer(
        "🔍 <b>To'lovlarni qidirish</b>\n\n"
        "Talaba ismi, telefon raqami, guruh nomi yoki to'lov ID sini kiriting:\n\n"
        "Masalan: Ali, +99890, Revit, 36",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(InvoiceSearchStates.waiting_for_search)


@router.message(InvoiceSearchStates.waiting_for_search)
async def process_search_invoices(message: Message, state: FSMContext):
    """Process search query."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Qidirish bekor qilindi.")
        return
    
    search_query = message.text.strip()
    if not search_query:
        await message.answer("❌ Qidiruv so'rovi bo'sh bo'lishi mumkin emas.")
        return
    
    user_id = message.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    # Save search query to state
    await state.update_data(search_query=search_query)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoices(search=search_query)
            invoices = extract_list_from_response(response)
            
            if not invoices:
                await message.answer(
                    f"🔍 <b>Qidiruv natijalari</b>\n\n"
                    f"'{safe_html_text(search_query)}' bo'yicha hech narsa topilmadi.\n\n"
                    f"Boshqa so'rov bilan qayta urinib ko'ring.",
                    reply_markup=get_invoices_list_keyboard([], page=0),
                    parse_mode="HTML"
                )
            else:
                text = f"🔍 <b>Qidiruv natijalari</b> ({len(invoices)} ta)\n\n"
                text += f"Qidiruv: '{safe_html_text(search_query)}'\n\n"
                text += "Quyidagilardan birini tanlang:"
                await message.answer(
                    text,
                    reply_markup=get_invoices_list_keyboard(invoices, page=0),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Search invoices error: {str(e)}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        # Don't clear state, keep search query for pagination
        pass


# Filter functionality
@router.callback_query(F.data == "filter_invoices")
async def filter_invoices_start(callback: CallbackQuery, state: FSMContext):
    """Start filtering invoices by status."""
    await callback.message.edit_text(
        "🔽 <b>To'lovlarni filterlash</b>\n\n"
        "Holat bo'yicha filter tanlang:",
        reply_markup=get_invoices_filter_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filter_status_"))
async def apply_invoice_filter(callback: CallbackQuery, state: FSMContext):
    """Apply status filter to invoices."""
    status_filter = callback.data.split("_")[-1]  # filter_status_paid -> paid
    
    user_id = callback.from_user.id
    access_token = await user_storage.get_access_token(user_id)
    
    # Map filter values
    status_map = {
        'all': None,
        'paid': 'paid',
        'pending': 'pending',
        'created': 'created',
        'cancelled': 'cancelled'
    }
    
    filter_value = status_map.get(status_filter)
    
    # Save filter to state
    await state.update_data(status_filter=filter_value, search_query=None)
    
    try:
        async with APIClient(access_token=access_token, user_id=user_id) as client:
            response = await client.get_invoices(status=filter_value)
            invoices = extract_list_from_response(response)
            
            filter_names = {
                'all': "Barchasi",
                'paid': "To'langan",
                'pending': "To'lov kutilmoqda",
                'created': "Yaratilgan",
                'cancelled': "Bekor qilingan"
            }
            
            filter_name = filter_names.get(status_filter, "Barchasi")
            
            if not invoices:
                await callback.message.edit_text(
                    f"🔽 <b>Filter: {filter_name}</b>\n\n"
                    f"Hech qanday to'lov topilmadi.",
                    reply_markup=get_invoices_list_keyboard([], page=0),
                    parse_mode="HTML"
                )
            else:
                text = f"🔽 <b>Filter: {filter_name}</b> ({len(invoices)} ta)\n\n"
                text += "Quyidagilardan birini tanlang:"
                await callback.message.edit_text(
                    text,
                    reply_markup=get_invoices_list_keyboard(invoices, page=0),
                    parse_mode="HTML"
                )
            await callback.answer()
    except Exception as e:
        logger.error(f"Filter invoices error: {str(e)}")
        error_msg = truncate_alert_message(f"Xatolik: {str(e)}")
        await callback.answer(error_msg, show_alert=True)
