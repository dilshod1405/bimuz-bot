"""Keyboard layouts for the bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional


def get_main_menu_keyboard(role: Optional[str] = None) -> ReplyKeyboardMarkup:
    """Get main menu keyboard based on user role."""
    keyboard = []
    
    # Common buttons for all employees
    keyboard.append([KeyboardButton(text="👤 Profil")])
    keyboard.append([KeyboardButton(text="👥 Talabalar")])
    keyboard.append([KeyboardButton(text="📚 Guruhlar")])
    keyboard.append([KeyboardButton(text="💳 To'lovlar")])
    
    # Role-specific buttons
    if role == 'dasturchi':
        keyboard.append([KeyboardButton(text="👨‍💼 Xodimlar")])
        keyboard.append([KeyboardButton(text="📊 Analitika")])
    
    # Attendance for administrator and mentor
    if role in ['administrator', 'mentor', 'dasturchi']:
        keyboard.append([KeyboardButton(text="📋 Davomatlar")])
    
    # Reports and Documents for all employees
    keyboard.append([KeyboardButton(text="📄 Hisobotlar")])
    keyboard.append([KeyboardButton(text="📁 Hujjatlar")])
    
    keyboard.append([KeyboardButton(text="❌ Chiqish")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get cancel keyboard (for regular messages)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Get cancel inline keyboard (for edit_text)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")]
    ])


def get_back_inline_keyboard(callback_data: str = "back_to_groups") -> InlineKeyboardMarkup:
    """Get back inline keyboard (for edit_text)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback_data)]
    ])


def get_students_list_keyboard(students: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Get keyboard for students list with pagination."""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    for student in students[start_idx:end_idx]:
        student_name = student.get('full_name', f"Student {student.get('id')}")
        keyboard.append([
            InlineKeyboardButton(
                text=student_name,
                callback_data=f"student_{student.get('id')}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"students_page_{page-1}"))
    if end_idx < len(students):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"students_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="➕ Yangi talaba", callback_data="create_student")])
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_student_detail_keyboard(student_id: int, role: Optional[str] = None) -> InlineKeyboardMarkup:
    """Get keyboard for student detail view."""
    keyboard = [
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_student_{student_id}")],
        [InlineKeyboardButton(text="📚 Guruhga yozish", callback_data=f"book_student_{student_id}")],
    ]
    
    # Only Developer or Administrator can delete
    if role in ['dasturchi', 'administrator']:
        keyboard.append([InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delete_student_{student_id}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_students")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_groups_list_keyboard(groups: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Get keyboard for groups list with pagination."""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    for group in groups[start_idx:end_idx]:
        group_name = f"{group.get('speciality_display', 'Guruh')} - {group.get('dates_display', '')}"
        keyboard.append([
            InlineKeyboardButton(
                text=group_name,
                callback_data=f"group_{group.get('id')}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"groups_page_{page-1}"))
    if end_idx < len(groups):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"groups_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="➕ Yangi guruh", callback_data="create_group")])
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_detail_keyboard(group_id: int, role: Optional[str] = None) -> InlineKeyboardMarkup:
    """Get keyboard for group detail view."""
    keyboard = []
    
    if role in ['dasturchi', 'direktor', 'administrator']:
        keyboard.append([InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_group_{group_id}")])
        keyboard.append([InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delete_group_{group_id}")])
    
    keyboard.append([InlineKeyboardButton(text="📋 Davomat", callback_data=f"attendance_group_{group_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_groups")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_invoices_list_keyboard(invoices: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Get keyboard for invoices list with pagination."""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    for invoice in invoices[start_idx:end_idx]:
        invoice_text = f"#{invoice.get('id')} - {invoice.get('student_name', 'N/A')} - {invoice.get('amount', 0)} so'm"
        keyboard.append([
            InlineKeyboardButton(
                text=invoice_text,
                callback_data=f"invoice_{invoice.get('id')}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"invoices_page_{page-1}"))
    if end_idx < len(invoices):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"invoices_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Search and filter buttons
    keyboard.append([
        InlineKeyboardButton(text="🔍 Qidirish", callback_data="search_invoices"),
        InlineKeyboardButton(text="🔽 Filter", callback_data="filter_invoices")
    ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_invoices_filter_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for invoice status filter."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Barchasi", callback_data="filter_status_all")],
        [InlineKeyboardButton(text="✅ To'langan", callback_data="filter_status_paid")],
        [InlineKeyboardButton(text="⏳ To'lov kutilmoqda", callback_data="filter_status_pending")],
        [InlineKeyboardButton(text="🆕 Yaratilgan", callback_data="filter_status_created")],
        [InlineKeyboardButton(text="❌ Bekor qilingan", callback_data="filter_status_cancelled")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_invoices")]
    ])


def get_invoice_detail_keyboard(invoice_id: int, is_paid: bool = False, status: Optional[str] = None) -> InlineKeyboardMarkup:
    """Get keyboard for invoice detail view."""
    keyboard = []
    
    # Only show "Create payment link" button if invoice is not paid and not cancelled/refunded
    if not is_paid and status and status.lower() not in ['cancelled', 'bekor qilingan', 'refunded', 'qaytarilgan']:
        keyboard.append([InlineKeyboardButton(text="💳 To'lov linkini yaratish", callback_data=f"create_payment_{invoice_id}")])
    elif not is_paid and not status:
        # If status is not provided, show button (backward compatibility)
        keyboard.append([InlineKeyboardButton(text="💳 To'lov linkini yaratish", callback_data=f"create_payment_{invoice_id}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_invoices")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_employees_list_keyboard(employees: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Get keyboard for employees list with pagination."""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    for employee in employees[start_idx:end_idx]:
        employee_name = employee.get('full_name', f"Employee {employee.get('id')}")
        keyboard.append([
            InlineKeyboardButton(
                text=employee_name,
                callback_data=f"employee_{employee.get('id')}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"employees_page_{page-1}"))
    if end_idx < len(employees):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"employees_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="➕ Yangi xodim", callback_data="create_employee")])
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_employee_detail_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for employee detail view."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_employees")]
    ])


def get_yes_no_keyboard(action: str) -> InlineKeyboardMarkup:
    """Get yes/no confirmation keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"cancel_{action}")
        ]
    ])
